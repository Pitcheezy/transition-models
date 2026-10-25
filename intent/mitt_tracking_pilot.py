"""Bounded offline patch-tracker pilot on saved development frames; no network/model calls.

Use original unannotated frame_*.jpg, never coordinate-grid crop_*.jpg. Saved sequence answers
select only the first usable point per pitch. Later AI points are comparison data, not truth.
The release-nearest annotation restricts the evaluation window, not the tracking algorithm.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import platform
import re
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from intent import mitt_pilot, mitt_temporal
from intent.mitt_tracking import PatchTracker, TrackParams

CROP = (330, 100, 950, 600)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def distribution(values):
    return {
        "n": len(values),
        "median": float(np.median(values)) if values else None,
        "p95": float(np.percentile(values, 95)) if values else None,
    }


def synchronize(device):
    if device == "cuda":
        torch.cuda.synchronize()


def benchmark(device):
    """Synthetic in-memory sustained tracking, including transfers and host result retrieval."""
    frames = []
    patch = np.random.default_rng(37).integers(40, 200, (21, 21), dtype=np.uint8)
    for i in range(16):
        frame = np.full((500, 620), 30, np.uint8)
        x = 100 + i
        frame[90:111, x - 10 : x + 11] = patch
        frames.append(frame)
    timings, seeds, states = [], [], Counter()
    for repeat in range(4):  # first sequence is warm-up; three measured repetitions
        tracker = PatchTracker(device=device)
        for i, frame in enumerate(frames):
            synchronize(device)
            start = time.perf_counter()
            row = tracker.step(
                frame,
                pitch_id="synthetic",
                frame_index=i,
                frame_seconds=i / 10,
                seed=[100, 100] if i == 0 else None,
            )
            synchronize(device)
            ms = (time.perf_counter() - start) * 1000
            if repeat:
                (seeds if i == 0 else timings).append(ms)
                states[row["state"]] += 1
            if row["point_px"] != [100 + i, 100]:
                raise ValueError("synthetic benchmark did not follow known translation")
    return {
        "active_tracking_ms": distribution(timings),
        "seed_ms": distribution(seeds),
        "states": dict(states),
        "warmup_sequences": 1,
        "measured_repetitions": 3,
        "scope": "synthetic pixels already decoded; includes host/device transfer and result retrieval",
    }


def load_inputs(bundle, pilot):
    manifest_path = bundle / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    meta, answers, problems, missing = mitt_pilot.load_answers(pilot)
    if problems or missing or meta["bundle_manifest_sha256"] != sha(manifest_path):
        raise ValueError("saved pilot input integrity failed")
    if (
        manifest["source"].get("time_base") != "1/60000"
        or manifest["source"].get("ticks_per_frame") != 1001
    ):
        raise ValueError("this pilot requires the frozen 747139 time base")
    plans = mitt_pilot.plan(manifest)
    if [p["pitch_id"] for p in plans] != meta["pitches"] or len(plans) != 10:
        raise ValueError("expected fixed first ten pitches")
    observations = {}
    for mapping in meta["mapping"]:
        if mapping["kind"] != "sequence":
            continue
        obs, error = mitt_pilot.to_observation(mapping, answers[mapping["id"]])
        if error:
            raise ValueError("saved observation invalid: " + error)
        key = (mapping["pitch_id"], mapping["index"])
        if key in observations:
            raise ValueError("duplicate sequence frame")
        observations[key] = obs
    expected = {(p["pitch_id"], f["index"]) for p in plans for f in p["frames"]}
    if set(observations) != expected:
        raise ValueError("sequence observations do not match the frozen frame plan")
    selected = []
    preserved = {
        str(manifest_path): sha(manifest_path),
        str(pilot / "pilot_private.json"): sha(pilot / "pilot_private.json"),
    }
    preserved.update({str(p): sha(p) for p in sorted((pilot / "answers").glob("b*.json"))})
    for p in [p for p in manifest["pitches"] if p["status"] == "extracted"][:10]:
        pitch = p["pitch_id"]
        if not re.fullmatch(r"747139:[1-9]\d*:[1-9]\d*", pitch):
            raise ValueError("unexpected pitch key")
        _, ab, pn = pitch.split(":")
        frames = [
            f
            for f in p["frames"]
            if "grid" in f["roles"] and f["index"] <= p["window"]["release_index"]
        ]
        indices = [f["index"] for f in frames]
        if indices != sorted(set(indices)):
            raise ValueError("frame order or duplicate mismatch")
        seed = None
        for f in frames:
            if (
                not math.isfinite(f["pts_time"])
                or abs(f["pts_time"] - f["index"] * 1001 / 60000) > 1e-6
            ):
                raise ValueError("PTS mismatch")
            path = bundle / f"pa{ab}_p{pn}" / f"frame_{f['index']:06d}.jpg"
            if path.stat().st_size != f["bytes"] or sha(path) != f["sha256"]:
                raise ValueError("source frame integrity mismatch")
            preserved[str(path)] = f["sha256"]
            f = dict(f, path=path)
            selected.append((pitch, f))
            obs = observations.get((pitch, f["index"]))
            if seed is None and obs is not None and mitt_temporal.unusable_reason(obs) is None:
                seed = (f["index"], obs["mitt_center_px"])
        p["tracking_seed"] = seed
    seeds = {p["pitch_id"]: p["tracking_seed"] for p in manifest["pitches"] if "tracking_seed" in p}
    return selected, seeds, observations, preserved, sha(manifest_path)


def replay(selected, seeds, observations, device):
    records, times, active, decode_times, init_times = [], [], [], [], []
    tracker, current_pitch = None, None
    for pitch, frame in selected:
        if pitch != current_pitch:
            tracker, current_pitch = PatchTracker(origin=CROP[:2], device=device), pitch
        seed = seeds[pitch]
        seed_point = seed[1] if seed and seed[0] == frame["index"] else None
        synchronize(device)
        total_start = time.perf_counter()
        raw = frame["path"].read_bytes()
        if hashlib.sha256(raw).hexdigest() != frame["sha256"]:
            raise ValueError("frame changed after integrity check")
        with Image.open(io.BytesIO(raw)) as image:
            if image.size != (1280, 720):
                raise ValueError("source dimensions changed")
            pixels = np.array(image.convert("L").crop(CROP), copy=True)
        decoded = time.perf_counter()
        prior_state = tracker.state
        row = tracker.step(
            pixels,
            pitch_id=pitch,
            frame_index=frame["index"],
            frame_seconds=frame["pts_time"],
            seed=seed_point,
        )
        synchronize(device)
        ended = time.perf_counter()
        elapsed = (ended - decoded) * 1000
        decode_times.append((decoded - total_start) * 1000)
        times.append((ended - total_start) * 1000)
        if prior_state == "tracking":
            active.append(elapsed)
        if seed_point is not None:
            init_times.append(elapsed)
        obs = observations.get((pitch, frame["index"]))
        row.update(
            source_sha256=frame["sha256"],
            source_pts_ticks=frame["index"] * 1001,
            source_time_base="1/60000",
            crop_origin=list(CROP[:2]),
            raw_ai_point_px=obs["mitt_center_px"] if obs else None,
            seed_source="saved_AI_first_usable_sequence_point" if seed_point else None,
        )
        records.append(row)
    distances = [
        math.dist(r["point_px"], r["raw_ai_point_px"])
        for r in records
        if r["point_px"] is not None and r["raw_ai_point_px"] is not None and not r["seed_source"]
    ]
    return records, {
        "states": dict(Counter(r["state"] for r in records)),
        "reasons": dict(Counter(r["reason"] for r in records)),
        "active_attempt_ms": distribution(active),
        "seed_ms": distribution(init_times),
        "jpeg_read_hash_decode_crop_ms": distribution(decode_times),
        "read_to_host_result_ms": distribution(times),
        "same_frame_AI_disagreement_px_not_accuracy": distribution(distances),
    }


def run(bundle, pilot, out, devices):
    if out.exists():
        raise ValueError("output directory must be new")
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    selected, seeds, observations, preserved, source_sha = load_inputs(bundle, pilot)
    report = {
        "schema": "pitcheezy-mitt-tracking-pilot-dev-v1",
        "evidence_kind": "offline exposed development; no new model or human calls",
        "params": asdict(TrackParams()),
        "params_sha256": TrackParams().digest(),
        "crop": list(CROP),
        "source_manifest_sha256": source_sha,
        "pitches": len(seeds),
        "frames": len(selected),
        "sequence_AI_observations": len(observations),
        "seed_rule": "first usable saved sequence AI point per pitch; no retries or automatic reseeding",
        "environment": {
            "python": platform.python_version(),
            "torch": torch.__version__,
            "cuda_runtime": torch.version.cuda,
            "cpu_threads": 4,
            "tf32": False,
            "gpu": torch.cuda.get_device_name(0) if "cuda" in devices else None,
        },
        "devices": {},
        "limits": [
            "tracking is patch continuity, not verified mitt identity",
            "no independent accuracy or live latency",
            "no automatic shot classifier; appearance discontinuity heuristic only",
            "JPEG cache/order can affect decode timings; synthetic sustained tracking reported separately",
        ],
    }
    out.mkdir(parents=True)
    by_device = {}
    for device in devices:
        if device == "cuda" and not torch.cuda.is_available():
            raise ValueError("CUDA requested but unavailable")
        benchmark_report = benchmark(device)
        rows, summary = replay(selected, seeds, observations, device)
        by_device[device] = rows
        path = out / f"records_{device}.json"
        path.write_text(json.dumps(rows, indent=2, allow_nan=False) + "\n", encoding="utf-8")
        report["devices"][device] = {
            **summary,
            "synthetic_sustained": benchmark_report,
            "records_sha256": sha(path),
        }
    if "cpu" in by_device and "cuda" in by_device:
        pairs = list(zip(by_device["cpu"], by_device["cuda"], strict=True))
        report["cpu_cuda_state_point_equal"] = all(
            (a["state"], a["reason"], a["point_px"]) == (b["state"], b["reason"], b["point_px"])
            for a, b in pairs
        )
    if any(sha(Path(path)) != digest for path, digest in preserved.items()):
        raise ValueError("an input changed during replay")
    report["preserved_input_files"] = len(preserved)
    (out / "report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--devices", nargs="+", choices=("cpu", "cuda"), default=["cpu"])
    args = parser.parse_args()
    report = run(args.bundle, args.pilot, args.out, args.devices)
    print(
        json.dumps(
            {
                "pitches": report["pitches"],
                "frames": report["frames"],
                "devices": list(report["devices"]),
            }
        )
    )


if __name__ == "__main__":
    main()

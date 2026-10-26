"""Offline comparison of PatchTracker and the limited re-search baseline on the same saved frames.

Same 625 frames, same first-usable saved AI seeds and same crop as the tracking pilot. The base
replay must reproduce the saved tracking records before the candidate is compared with it.
Longer tracking, more segments or fewer abstentions are not accuracy: no human truth is used,
and a geometric re-match never verifies that the re-found patch is a mitt.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import time
from collections import Counter
from dataclasses import asdict
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from intent import mitt_temporal
from intent import mitt_tracking_pilot as base_pilot
from intent.mitt_reacquire import (
    SEGMENT_START_REASONS,
    TERMINAL_LOSSES,
    ReacquireParams,
    ReacquiringTracker,
    SegmentedStationarySelector,
)
from intent.mitt_stationary import StationaryParams, StationarySelector
from intent.mitt_tracking import TrackParams

CROP = base_pilot.CROP
COMPARED = ("pitch_id", "frame_index", "source_sha256", "state", "reason", "point_px")
sha = base_pilot.sha
distribution = base_pilot.distribution


def decode(frame):
    raw = frame["path"].read_bytes()
    if hashlib.sha256(raw).hexdigest() != frame["sha256"]:
        raise ValueError("frame changed after integrity check")
    with Image.open(io.BytesIO(raw)) as image:
        if image.size != (1280, 720):
            raise ValueError("source dimensions changed")
        return np.array(image.convert("L").crop(CROP), copy=True)


def replay_candidate(selected, seeds, observations, device, params=None, reacquire=None):
    """Candidate tracker plus per-segment stationary selector; timings are the tracker step."""
    rows, timings = [], {}
    tracker = selector = current = None
    for pitch, frame in selected:
        if pitch != current:
            tracker = ReacquiringTracker(
                origin=CROP[:2], device=device, params=params, reacquire=reacquire
            )
            selector, current = SegmentedStationarySelector(), pitch
        seed = seeds[pitch]
        seed_point = seed[1] if seed and seed[0] == frame["index"] else None
        pixels = decode(frame)
        prior = tracker.state
        base_pilot.synchronize(device)
        start = time.perf_counter()
        row = tracker.step(
            pixels,
            pitch_id=pitch,
            frame_index=frame["index"],
            frame_seconds=frame["pts_time"],
            seed=seed_point,
        )
        base_pilot.synchronize(device)
        elapsed = (time.perf_counter() - start) * 1000
        timings.setdefault("seed" if seed_point else prior, []).append(elapsed)
        snapshot = selector.step(row)
        obs = observations.get((pitch, frame["index"]))
        row.update(
            prior_state=prior,
            source_sha256=frame["sha256"],
            source_pts_ticks=frame["index"] * 1001,
            source_time_base="1/60000",
            crop_origin=list(CROP[:2]),
            raw_ai_point_px=obs["mitt_center_px"] if obs else None,
            ai_unusable_reason=mitt_temporal.unusable_reason(obs)
            if obs is not None
            else "no_saved_observation",
            seed_source="saved_AI_first_usable_sequence_point" if seed_point else None,
            stationary=snapshot,
        )
        rows.append(row)
    return rows, {key: distribution(values) for key, values in sorted(timings.items())}


def base_stationary_events(base_rows):
    """First stationary candidate per pitch from the unchanged tracker and selector."""
    events, selector, current = [], None, None
    for row in base_rows:
        if row["pitch_id"] != current:
            selector, current = StationarySelector(), row["pitch_id"]
        snapshot = selector.step(row)
        if snapshot["event"] is not None:
            events.append(snapshot["event"])
    return events


def _segments_and_windows(rows):
    segments, windows, segment, window = [], [], None, None
    for row in rows:
        state, quality = row["state"], row["quality"]
        if state == "tracking":
            if row["reason"] in SEGMENT_START_REASONS:
                segment = {
                    "segment_id": row["segment_id"],
                    "start_reason": row["reason"],
                    "start_frame": row["frame_index"],
                    "start_seconds": row["frame_seconds"],
                    "frames": 0,
                    "fb_error_px": [],
                    "step_px": [],
                    "last_point": None,
                }
                segments.append(segment)
                if window is not None:
                    window["outcome"] = "reacquired"
                    window = None
            segment["frames"] += 1
            segment["end_frame"], segment["end_seconds"] = row["frame_index"], row["frame_seconds"]
            if "fb_error_px" in quality:
                segment["fb_error_px"].append(quality["fb_error_px"])
            if segment["last_point"] is not None:
                segment["step_px"].append(math.dist(row["point_px"], segment["last_point"]))
            segment["last_point"] = row["point_px"]
            continue
        if row["segment_end_reason"] is not None:
            segment["end_reason"] = row["segment_end_reason"]
            segment["loss_frame"] = row["frame_index"]
            segment = None
            if state != "lost" or row["reason"] not in TERMINAL_LOSSES + ("reacquire_limit",):
                window = {
                    "loss_frame": row["frame_index"],
                    "loss_reason": row["segment_end_reason"],
                    "window_frames": 0,
                    "search_frames": 0,
                    "candidates": 0,
                    "abstain_reasons": Counter(),
                    "rejected_reasons": Counter(),
                    "anchor_distance_px": [],
                    "seed_template_ncc_diagnostic_only": [],
                    "outcome": None,
                }
                windows.append(window)
        if window is None:
            continue
        window["window_frames"] = max(window["window_frames"], quality.get("reacquire_attempt", 0))
        window["search_frames"] += bool(quality.get("reacquire_searched"))
        if state == "reacquire_candidate":
            window["candidates"] += 1
            window["anchor_distance_px"].append(quality["anchor_distance_px"])
            window["seed_template_ncc_diagnostic_only"].append(
                quality["seed_template_ncc_diagnostic_only"]
            )
        elif state == "reacquire_search":
            if row["reason"].startswith("reacquire_candidate_"):
                window["rejected_reasons"][row["reason"]] += 1
            else:
                window["abstain_reasons"][row["reason"]] += 1
        elif state == "lost":
            window["outcome"] = row["reason"]
            if row["reason"] == "reacquire_exhausted":
                last = quality.get("last_attempt_reason", "unknown")
                kind = (
                    "rejected_reasons"
                    if last.startswith("reacquire_candidate_")
                    else "abstain_reasons"
                )
                window[kind][last] += 1
            window = None
    for segment in segments:
        segment.pop("last_point")
        segment["span_seconds"] = segment["end_seconds"] - segment["start_seconds"]
        segment["fb_error_px"] = distribution(segment["fb_error_px"])
        segment["step_px"] = distribution(segment["step_px"])
    for window in windows:
        window["abstain_reasons"] = dict(window["abstain_reasons"])
        window["rejected_reasons"] = dict(window["rejected_reasons"])
        window["anchor_distance_px"] = distribution(window["anchor_distance_px"])
        window["seed_template_ncc_diagnostic_only"] = distribution(
            window["seed_template_ncc_diagnostic_only"]
        )
    return segments, windows


def _consistency(rows):
    """Invariants that must hold for every row; counts are violations, expected 0."""
    stale_points = candidate_points = candidate_mismatch = history_future = 0
    events_decrease = segment_order = selector_point = 0
    last_events, last_segment, pitch = 0, 0, None
    for row in rows:
        snapshot = row["stationary"]
        if row["pitch_id"] != pitch:
            last_events, last_segment, pitch = 0, 0, row["pitch_id"]
        if row["state"] != "tracking" and row["point_px"] is not None:
            stale_points += 1
        if (row["state"] == "reacquire_candidate") != (row["reacquire_candidate_px"] is not None):
            candidate_points += 1
        current = snapshot["current_candidate"]
        if current is not None and (
            row["state"] != "tracking"
            or snapshot["selection_state"] != "stationary"
            or current["segment_id"] != row["segment_id"]
        ):
            candidate_mismatch += 1
        history = snapshot["last_historical_candidate"]
        if history is not None and history["frame_index"] > row["frame_index"]:
            history_future += 1
        if snapshot["events_total"] < last_events:
            events_decrease += 1
        last_events = snapshot["events_total"]
        if row["state"] == "tracking" and row["reason"] in SEGMENT_START_REASONS:
            if row["segment_id"] <= last_segment:
                segment_order += 1
            last_segment = row["segment_id"]
        if row["state"] != "tracking" and snapshot["current_track_point_px"] is not None:
            selector_point += 1
    return {
        "point_shown_outside_confirmed_tracking": stale_points,
        "candidate_point_outside_candidate_state": candidate_points,
        "current_candidate_outside_stationary_tracking": candidate_mismatch,
        "historical_candidate_from_the_future": history_future,
        "events_total_decreased": events_decrease,
        "segment_id_not_increasing": segment_order,
        "selector_point_outside_tracking": selector_point,
    }


def _ai_disagreement(rows):
    """Same-frame distance to the saved AI point by segment class; disagreement, not accuracy."""
    out = {}
    for label, first in (("first_segment", True), ("reacquired_segments", False)):
        pairs = [
            r
            for r in rows
            if r["state"] == "tracking"
            and (r["segment_id"] == 1) == first
            and r["raw_ai_point_px"] is not None
            and not r["seed_source"]
        ]
        out[label] = {
            "all_px_not_accuracy": distribution(
                [math.dist(r["point_px"], r["raw_ai_point_px"]) for r in pairs]
            ),
            "usable_px_not_accuracy": distribution(
                [
                    math.dist(r["point_px"], r["raw_ai_point_px"])
                    for r in pairs
                    if r["ai_unusable_reason"] is None
                ]
            ),
        }
    return out


def compare(base_rows, candidate_rows):
    if [(r["pitch_id"], r["frame_index"]) for r in base_rows] != [
        (r["pitch_id"], r["frame_index"]) for r in candidate_rows
    ]:
        raise ValueError("base and candidate replays must cover the same frames")
    per_pitch = {}
    pitches = []
    for row in base_rows:
        if row["pitch_id"] not in pitches:
            pitches.append(row["pitch_id"])
    for pitch in pitches:
        base = [r for r in base_rows if r["pitch_id"] == pitch]
        cand = [r for r in candidate_rows if r["pitch_id"] == pitch]
        seed = next((r for r in base if r["seed_source"]), None)
        base_loss = next(
            (r for r in base if r["prior_state"] == "tracking" and r["state"] == "lost"), None
        )
        segments, windows = _segments_and_windows(cand)
        base_tracking = [r for r in base if r["state"] == "tracking"]
        cand_tracking = [r for r in cand if r["state"] == "tracking"]
        per_pitch[pitch] = {
            "frames": len(base),
            "seed_frame": seed["frame_index"] if seed else None,
            "base": {
                "states": dict(Counter(r["state"] for r in base)),
                "tracking_frames": len(base_tracking),
                "tracked_span_seconds": (
                    base_tracking[-1]["frame_seconds"] - base_tracking[0]["frame_seconds"]
                )
                if base_tracking
                else None,
                "first_loss": {
                    "frame_index": base_loss["frame_index"],
                    "seconds_after_seed": base_loss["frame_seconds"] - seed["frame_seconds"],
                    "reason": base_loss["reason"],
                }
                if base_loss and seed
                else None,
                "stationary_events": 0,  # filled from the base selector by run()
            },
            "candidate": {
                "states": dict(Counter(r["state"] for r in cand)),
                "tracking_frames": len(cand_tracking),
                "tracked_span_seconds": (
                    cand_tracking[-1]["frame_seconds"] - cand_tracking[0]["frame_seconds"]
                )
                if cand_tracking
                else None,
                "first_segment_loss_same_as_base": bool(
                    segments
                    and base_loss
                    and segments[0].get("loss_frame") == base_loss["frame_index"]
                    and segments[0].get("end_reason") == base_loss["reason"]
                ),
                "segments": segments,
                "windows": windows,
                "reacquisitions": cand[-1]["reacquisitions"],
                "terminal_reason": cand[-1]["reason"] if cand[-1]["state"] == "lost" else None,
                "stationary_events": cand[-1]["stationary"]["events_total"],
            },
        }
    windows = [w for p in per_pitch.values() for w in p["candidate"]["windows"]]
    segments = [s for p in per_pitch.values() for s in p["candidate"]["segments"]]
    return {
        "per_pitch": per_pitch,
        "totals": {
            "frames": len(base_rows),
            "pitches": len(pitches),
            "base_states": dict(Counter(r["state"] for r in base_rows)),
            "candidate_states": dict(Counter(r["state"] for r in candidate_rows)),
            "base_tracking_frames": sum(r["state"] == "tracking" for r in base_rows),
            "candidate_tracking_frames": sum(r["state"] == "tracking" for r in candidate_rows),
            "windows": len(windows),
            "window_frames": sum(w["window_frames"] for w in windows),
            "search_frames": sum(w["search_frames"] for w in windows),
            "candidates": sum(w["candidates"] for w in windows),
            "accepted": sum(w["outcome"] == "reacquired" for w in windows),
            "rejected_reasons": dict(
                sum((Counter(w["rejected_reasons"]) for w in windows), Counter())
            ),
            "abstain_reasons": dict(
                sum((Counter(w["abstain_reasons"]) for w in windows), Counter())
            ),
            "window_outcomes": dict(Counter(w["outcome"] for w in windows)),
            "segments": len(segments),
            "reacquired_segments": sum(
                s["start_reason"] == "reacquired_continuity" for s in segments
            ),
            "reacquired_segment_frames": distribution(
                [s["frames"] for s in segments if s["start_reason"] == "reacquired_continuity"]
            ),
            "reacquired_segment_span_seconds": distribution(
                [
                    s["span_seconds"]
                    for s in segments
                    if s["start_reason"] == "reacquired_continuity"
                ]
            ),
            "anchor_distance_px": distribution(
                [
                    r["quality"]["anchor_distance_px"]
                    for r in candidate_rows
                    if r["state"] == "reacquire_candidate"
                ]
            ),
            "seed_template_ncc_at_candidates_diagnostic_only": distribution(
                [
                    r["quality"]["seed_template_ncc_diagnostic_only"]
                    for r in candidate_rows
                    if r["state"] == "reacquire_candidate"
                    and r["quality"]["seed_template_ncc_diagnostic_only"] is not None
                ]
            ),
            "candidate_stationary_events": sum(
                p["candidate"]["stationary_events"] for p in per_pitch.values()
            ),
        },
        "consistency_violations": _consistency(candidate_rows),
        "same_frame_AI_disagreement": _ai_disagreement(candidate_rows),
    }


def prefix_invariance(selected, seeds, observations, rows, device):
    """Replaying only the first half of each pitch must reproduce the full replay's prefix."""
    checked = 0
    for pitch in dict.fromkeys(p for p, _ in selected):
        frames = [item for item in selected if item[0] == pitch]
        half = frames[: max(1, len(frames) // 2)]
        partial, _ = replay_candidate(half, seeds, observations, device)
        full = [r for r in rows if r["pitch_id"] == pitch][: len(half)]
        for a, b in zip(partial, full, strict=True):
            # Whole rows, stationary snapshot included: history and event counts are outputs too.
            if a != b:
                raise ValueError("future frames changed an earlier output")
            checked += 1
    return checked


def run(bundle, pilot, saved_records, out, device="cpu"):
    if out.exists():
        raise ValueError("output directory must be new")
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    selected, seeds, observations, preserved, source_sha = base_pilot.load_inputs(bundle, pilot)
    preserved[str(saved_records)] = sha(saved_records)
    base_rows, base_summary = base_pilot.replay(selected, seeds, observations, device)
    saved = json.loads(saved_records.read_text(encoding="utf-8"))
    projected = [{key: r[key] for key in COMPARED} for r in base_rows]
    if projected != [{key: r[key] for key in COMPARED} for r in saved]:
        raise ValueError("base replay does not reproduce the saved tracking records")
    candidate_rows, candidate_timings = replay_candidate(selected, seeds, observations, device)
    base_events = base_stationary_events(base_rows)
    metrics = compare(base_rows, candidate_rows)
    for event in base_events:
        metrics["per_pitch"][event["pitch_id"]]["base"]["stationary_events"] += 1
    metrics["totals"]["base_stationary_events"] = len(base_events)
    checked = prefix_invariance(selected, seeds, observations, candidate_rows, device)
    if any(sha(Path(path)) != digest for path, digest in preserved.items()):
        raise ValueError("an input changed during replay")
    out.mkdir(parents=True)
    records = out / f"records_candidate_{device}.json"
    records.write_text(
        json.dumps(candidate_rows, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    report = {
        "schema": "pitcheezy-mitt-reacquire-pilot-dev-v1",
        "evidence_kind": "offline development replay; no new model, video or human calls",
        "track_params": asdict(TrackParams()),
        "track_params_sha256": TrackParams().digest(),
        "reacquire_params": asdict(ReacquireParams()),
        "reacquire_params_sha256": ReacquireParams().digest(),
        "stationary_params": asdict(StationaryParams()),
        "stationary_params_sha256": StationaryParams().digest(),
        "crop": list(CROP),
        "device": device,
        "source_manifest_sha256": source_sha,
        "saved_pilot_inputs": base_pilot.saved_pilot_provenance(pilot, preserved),
        "saved_tracking_records_sha256": preserved[str(saved_records)],
        "base_regression": {
            "equal_to_saved_records": True,
            "compared_fields": list(COMPARED),
            "rows": len(base_rows),
        },
        "prefix_invariance_rows_checked": checked,
        "preserved_input_files": len(preserved),
        "environment": base_pilot.environment_info([device]),
        "timing_ms": {
            "base_active_attempt": base_summary["active_attempt_ms"],
            "base_seed": base_summary["seed_ms"],
            "candidate_tracker_step_by_prior_state": candidate_timings,
            "scope": "tracker step after decode, single run, same process; not live latency",
        },
        "metrics": metrics,
        "candidate_records_sha256": sha(records),
        "limits": [
            "tracking and re-acquisition are patch continuity, not verified mitt identity",
            "seed-template similarity at a candidate is a diagnostic, not re-identification",
            "more tracked frames or fewer abstentions are not accuracy; no human truth used",
            "a reacquired segment must requalify for stationarity; events are not stitched",
            "saved AI points are comparison data from the same development material",
            "timings are single-run host measurements on decoded frames",
        ],
    }
    (out / "report.json").write_text(
        json.dumps(report, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--bundle", type=Path, required=True)
    parser.add_argument("--pilot", type=Path, required=True)
    parser.add_argument("--saved-records", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--device", choices=("cpu", "cuda"), default="cpu")
    args = parser.parse_args()
    report = run(args.bundle, args.pilot, args.saved_records, args.out, args.device)
    totals = report["metrics"]["totals"]
    print(
        json.dumps(
            {
                "frames": totals["frames"],
                "windows": totals["windows"],
                "accepted": totals["accepted"],
                "candidate_tracking_frames": totals["candidate_tracking_frames"],
                "base_tracking_frames": totals["base_tracking_frames"],
            }
        )
    )


if __name__ == "__main__":
    main()

"""CV-32: a fixed-rule continuous development bundle from the 747139 full-game broadcast.

Rule (written before any frame of the bundle was read): game 747139, pitch order
(at_bat_number, pitch_number) starting at PA3 pitch 1, the next 40 pitch keys. Each pitch with
annotated timing gets the window [decision - 1.0 s, release + 0.5 s] at every 6th source frame
(about 10 fps), plus the frame at the decision index v0 recorded (round rule) and the
release-nearest frame. The image v0 actually read is the first frame at or after the decision
time, one frame later for about half the pitches; ``check-v0-frames`` keeps it separately.
A key without annotated timing stays in the denominator as excluded, with its reason.

Frames are selected by decoded presentation time, never by output order: the stream time base is
1/60000 and every frame lasts 1001 ticks, so the source index is ``pts / 1001`` and must be an
integer. A second showinfo before the selector logs every decoded frame, so the receipt also
proves the decoded run around each window has no index gap.

Decision and release seconds are AI visual annotations (not human ground truth). The window bounds
use them for bundle cutting only; a causal reader must still look only at frames up to its own
time, and release is used only for after-the-fact evaluation.

    python -m intent.mitt_dev_bundle extract --out outputs/cv_mitt_dev_20261025/bundle_v1
    python -m intent.mitt_dev_bundle summarize --bundle outputs/cv_mitt_dev_20261025/bundle_v1 \
        --out docs/results/cv_mitt_20261025/dev_bundle_v1.json
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
import shutil
import statistics
import subprocess
import time
from collections import Counter
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs/results/mlb_p0"
FPS = Fraction(60000, 1001)
TICKS_PER_FRAME = 1001
SCHEMA = "pitcheezy-mitt-dev-bundle-v1"
RULE = {
    "game_pk": 747139,
    "order": "at_bat_number, pitch_number",
    "first_key": [3, 1],
    "count": 40,
    "before_decision_seconds": 1.0,
    "after_release_seconds": 0.5,
    "step_source_frames": 6,
    "always_include": [
        "frame at the decision index recorded by v0 (round(seconds * fps))",
        "release-nearest frame",
    ],
    "fixed_before_reading": True,
}
MAIN_BOX = (440, 120, 840, 400)  # the frozen 747139 reader crop (intent points v0)
SHOWINFO = re.compile(
    r"\[showinfo@(all|kept) @ [0-9A-Fa-fx]+\] n:\s*(\d+) pts:\s*(-?\d+) pts_time:(-?[0-9.]+)"
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def read_json(path: Path):
    return json.loads(path.read_text(encoding="utf-8"))


def frame_at(seconds) -> int:
    return int(round(Fraction(str(seconds)) * FPS))


def select_pitches(annotations, rule=RULE):
    """The fixed rule: pitch keys in order from first_key, `count` of them, with exclusions."""
    ordered = sorted(
        (a for a in annotations if a["game_pk"] == rule["game_pk"]),
        key=lambda a: (a["at_bat_number"], a["pitch_number"]),
    )
    keys = [(a["at_bat_number"], a["pitch_number"]) for a in ordered]
    if len(set(keys)) != len(keys):
        raise ValueError("duplicate pitch keys in timing annotations")
    first = tuple(rule["first_key"])
    start = next((i for i, k in enumerate(keys) if k >= first), None)
    if start is None or len(ordered) - start < rule["count"]:
        raise ValueError("not enough pitch keys after the first key")
    chosen = []
    for a in ordered[start : start + rule["count"]]:
        item = {
            "pitch_id": f"{a['game_pk']}:{a['at_bat_number']}:{a['pitch_number']}",
            "play_id": a.get("play_id"),
            "timing_status": a["status"],
            "decision_seconds": a.get("decision_seconds"),
            "release_seconds": a.get("release_seconds"),
            "uncertainty_seconds": a.get("uncertainty_seconds"),
        }
        if a["status"] != "annotated":
            item["included"], item["exclusion_reason"] = False, "timing_unavailable_in_annotations"
        elif a.get("decision_seconds") is None or a.get("release_seconds") is None:
            item["included"], item["exclusion_reason"] = False, "decision_or_release_missing"
        elif a["release_seconds"] <= a["decision_seconds"]:
            item["included"], item["exclusion_reason"] = False, "release_not_after_decision"
        else:
            item["included"], item["exclusion_reason"] = True, None
        chosen.append(item)
    return chosen


def window(item, rule=RULE):
    """Source frame indices kept for one pitch, with the role of each index."""
    first = frame_at(item["decision_seconds"] - rule["before_decision_seconds"])
    last = frame_at(item["release_seconds"] + rule["after_release_seconds"])
    decision, release = frame_at(item["decision_seconds"]), frame_at(item["release_seconds"])
    roles = {i: ["grid"] for i in range(first, last + 1, rule["step_source_frames"])}
    roles.setdefault(decision, []).append("decision")
    roles.setdefault(release, []).append("release_nearest")
    return {
        "first_index": first,
        "last_index": last,
        "decision_index": decision,
        "release_index": release,
        "roles": dict(sorted(roles.items())),
    }


def select_expression(win, step):
    i = "round(t*60000/1001)"
    terms = [
        f"between({i}\\,{win['first_index']}\\,{win['last_index']})*not(mod({i}-{win['first_index']}\\,{step}))",
        f"eq({i}\\,{win['decision_index']})",
        f"eq({i}\\,{win['release_index']})",
    ]
    return f"gt({'+'.join(terms)}\\,0)"


def ffmpeg_command(ffmpeg, url, win, step, pattern, lead_frames=30):
    seek = max(0, win["first_index"] - lead_frames)
    span = win["last_index"] - seek + 2 * lead_frames
    return [
        ffmpeg,
        "-hide_banner",
        "-nostdin",
        "-loglevel",
        "info",
        "-ss",
        f"{float(Fraction(seek) / FPS):.6f}",
        "-t",
        f"{float(Fraction(span) / FPS):.6f}",
        "-copyts",
        "-i",
        url,
        "-an",
        "-vf",
        f"showinfo@all,select='{select_expression(win, step)}',showinfo@kept",
        "-fps_mode",
        "passthrough",
        "-q:v",
        "2",
        str(pattern),
    ]


def parse_showinfo(log: str):
    """{'all': [index...], 'kept': [index...]} from showinfo lines; pts must be whole frames."""
    out = {"all": [], "kept": []}
    for name, _n, pts, _t in SHOWINFO.findall(log):
        pts = int(pts)
        if pts % TICKS_PER_FRAME:
            raise ValueError(f"pts {pts} is not a whole source frame")
        out[name].append(pts // TICKS_PER_FRAME)
    return out


def verify_decode(indices, win):
    """Decoded run must cover the window without an index gap or repeat."""
    inside = [i for i in indices["all"] if win["first_index"] <= i <= win["last_index"]]
    gaps = sum(1 for a, b in zip(inside, inside[1:], strict=False) if b != a + 1)
    expected = list(win["roles"])
    return {
        "decoded_first": indices["all"][0] if indices["all"] else None,
        "decoded_last": indices["all"][-1] if indices["all"] else None,
        "window_covered": bool(inside)
        and inside[0] == win["first_index"]
        and inside[-1] == win["last_index"],
        "index_gaps_in_window": gaps,
        "kept_equals_expected": indices["kept"] == expected,
    }


def _decode_evidence(log, outputs, win, target, returncode, timed_out):
    """Retain only decoder scalars; derive rational time from the reported input time base."""
    config, rows, filtered, errors = {"all": [], "kept": []}, {"all": [], "kept": []}, [], []
    for line in log.splitlines():
        prefix = re.search(r"\[showinfo@(all|kept) @ [^]]+\]\s*(.*)", line)
        if not prefix:
            continue
        name, body = prefix.groups()
        if body.startswith("config in time_base:"):
            match = re.match(r"config in time_base:\s*(\d+)/(\d+)", body)
            if not match:
                errors.append("malformed_time_base")
                continue
            value = "/".join(match.groups())
            config[name].append(value)
            filtered.append(f"showinfo@{name} config in time_base: {value}")
        elif body.startswith("n:"):
            match = re.match(r"n:\s*(\S+)\s+pts:\s*(\S+)\s+pts_time:(\S+)", body)
            try:
                n, pts, text = match.groups() if match else (None, None, None)
                n, pts = int(n), int(pts)
                if not (
                    0 <= n <= 2**53 - 1
                    and 0 <= pts <= 2**53 - 1
                    and pts % TICKS_PER_FRAME == 0
                    and math.isfinite(float(text))
                ):
                    raise ValueError
                # Store the printed decimal only after numeric parsing, never arbitrary log text.
                printed = str(Fraction(text))
                rows[name].append({"n": n, "pts": pts, "printed_pts_time_rational": printed})
                filtered.append(f"showinfo@{name} n:{n} pts:{pts} pts_time_rational:{printed}")
            except (ValueError, TypeError, OverflowError):
                errors.append("invalid_showinfo_frame")
    for name in rows:
        if not config[name] or any(value != "1/60000" for value in config[name]):
            errors.append(f"{name}_time_base_missing_or_mismatch")
        if not rows[name] or [r["n"] for r in rows[name]] != list(range(len(rows[name]))):
            errors.append(f"{name}_count_or_order")
        for row in rows[name]:
            if config[name] and len(set(config[name])) == 1:
                try:
                    row["pts_time_rational"] = str(row["pts"] * Fraction(config[name][0]))
                except (ValueError, ZeroDivisionError):
                    errors.append("invalid_time_base")
        indices = [r["pts"] // TICKS_PER_FRAME for r in rows[name]]
        if name == "all" and any(b != a + 1 for a, b in zip(indices, indices[1:], strict=False)):
            errors.append("decoded_pts_gap_or_order")
    indices = {name: [r["pts"] // TICKS_PER_FRAME for r in values] for name, values in rows.items()}
    check = verify_decode(indices, win)
    if not check["window_covered"] or not check["kept_equals_expected"]:
        errors.append("window_or_kept_order_mismatch")
    if len(outputs) != len(rows["kept"]):
        errors.append("jpeg_count_mismatch")
    if [p.name for p in outputs] != [f"out_{i:05d}.jpg" for i in range(1, len(outputs) + 1)]:
        errors.append("jpeg_sequence_mismatch")
    ok = returncode == 0 and not timed_out and not errors
    return {
        "status": "timeout"
        if timed_out
        else "ffmpeg_failed"
        if returncode != 0
        else "validation_failed"
        if errors
        else "saved_decode_evidence",
        "input_time_base_config": config,
        "decoded": rows,
        "filtered_decoder_log": filtered,
        "validation_errors": sorted(set(errors)),
        "independent_decoded_pts_verified": False,
        "kept_jpegs": [
            {
                "relative_path": f"{target.name}/frame_{row['pts'] // TICKS_PER_FRAME:06d}.jpg",
                "pts": row["pts"],
                "pts_time_rational": row["pts_time_rational"],
                "sha256": sha256_file(path),
                "bytes": path.stat().st_size,
            }
            for row, path in zip(rows["kept"], outputs, strict=True)
        ]
        if ok
        else [],
    }


def extract_one(
    item,
    out_dir: Path,
    ffmpeg: str,
    url: str,
    rule=RULE,
    retries=3,
    crop=True,
    save_decode_evidence=False,
    ffmpeg_version=None,
):
    win = window(item, rule)
    _, ab, pn = item["pitch_id"].split(":")
    target = out_dir / f"pa{ab}_p{pn}"
    staging = out_dir / f".staging_{target.name}"
    record = {
        "pitch_id": item["pitch_id"],
        "window": {k: v for k, v in win.items() if k != "roles"},
        "attempts": [],
    }
    command = ffmpeg_command(ffmpeg, url, win, rule["step_source_frames"], staging / "out_%05d.jpg")
    record["command"] = [c if c != url else "<media_url>" for c in command[1:]]
    if save_decode_evidence:
        evidence_dir = out_dir / "decode_evidence" / target.name
        if evidence_dir.exists() or target.exists():
            raise FileExistsError("decode evidence and target must be new")
        evidence_dir.mkdir(parents=True)
        if ffmpeg_version is None:
            try:
                ffmpeg_version = subprocess.run(
                    [ffmpeg, "-version"], capture_output=True, text=True, timeout=10
                ).stdout
            except (OSError, subprocess.TimeoutExpired):
                ffmpeg_version = "unavailable"
        version = re.match(r"ffmpeg version ([A-Za-z0-9._+~-]+)", ffmpeg_version)
        evidence_base = {
            "schema": "pitcheezy-decode-evidence-dev-v1",
            "pitch_id": item["pitch_id"],
            "ffmpeg_version": version[1] if version else "unavailable",
            "source_code_sha256": sha256_file(Path(__file__)),
            "command": ["ffmpeg", *record["command"][:-1], "<staging>/out_%05d.jpg"],
            "ticks_per_frame": TICKS_PER_FRAME,
        }
        record["command"] = evidence_base["command"][1:]
        record["independent_decoded_pts_verified"] = False
    for attempt in range(1, retries + 1):
        if staging.exists():
            shutil.rmtree(staging)
        staging.mkdir(parents=True)
        started = time.monotonic()
        timed_out = False
        try:
            proc = subprocess.run(
                command,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=600,
            )
        except subprocess.TimeoutExpired as error:
            if not save_decode_evidence:
                raise
            timed_out = True
            stderr = error.stderr or ""
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            proc = subprocess.CompletedProcess(command, None, "", stderr)
        elapsed = round(time.monotonic() - started, 2)
        try:
            indices = parse_showinfo(proc.stderr)
            check = verify_decode(indices, win)
        except ValueError as error:
            indices, check = {"all": [], "kept": []}, {"parse_error": str(error)}
        outputs = sorted(staging.glob("out_*.jpg"))
        ok = (
            proc.returncode == 0
            and check.get("window_covered")
            and check.get("index_gaps_in_window") == 0
            and check.get("kept_equals_expected")
            and len(outputs) == len(indices["kept"])
        )
        if save_decode_evidence:
            evidence = {
                **evidence_base,
                "attempt": attempt,
                "returncode": proc.returncode,
                "elapsed_seconds": elapsed,
                **_decode_evidence(proc.stderr, outputs, win, target, proc.returncode, timed_out),
            }
            if evidence["ffmpeg_version"] == "unavailable":
                evidence["validation_errors"].append("ffmpeg_version_unavailable")
                if evidence["status"] == "saved_decode_evidence":
                    evidence["status"], evidence["kept_jpegs"] = "validation_failed", []
            ok = ok and evidence["status"] == "saved_decode_evidence"
            evidence_path = evidence_dir / f"attempt_{attempt:02d}.json"
            with evidence_path.open("x", encoding="utf-8") as stream:
                stream.write(json.dumps(evidence, indent=2, allow_nan=False) + "\n")
            check["decode_evidence"] = {
                "relative_path": evidence_path.relative_to(out_dir).as_posix(),
                "sha256": sha256_file(evidence_path),
                "status": evidence["status"],
            }
        record["attempts"].append(
            {
                "attempt": attempt,
                "returncode": proc.returncode,
                "elapsed_seconds": elapsed,
                "outputs": len(outputs),
                **check,
            }
        )
        if ok:
            break
        record["attempts"][-1]["stderr_tail"] = (
            evidence["filtered_decoder_log"][-4:]
            if save_decode_evidence
            else [line.replace(url, "<media_url>") for line in proc.stderr.splitlines()[-4:]]
        )
        time.sleep(2 * attempt)
    else:
        shutil.rmtree(staging, ignore_errors=True)
        record["status"] = "extraction_failed"
        return record
    target.mkdir(parents=True)
    frames = []
    for index, path in zip(indices["kept"], outputs, strict=True):
        final = target / f"frame_{index:06d}.jpg"
        path.replace(final)
        frames.append(
            {
                "index": index,
                "pts_time": float(Fraction(index) / FPS),
                "seconds_from_decision": round(
                    float(Fraction(index - win["decision_index"]) / FPS), 4
                ),
                "roles": win["roles"][index],
                "bytes": final.stat().st_size,
                "sha256": sha256_file(final),
            }
        )
        if crop:
            from PIL import Image

            from intent.broadcast_windows import _grid

            with Image.open(final) as image:
                _grid(image.convert("RGB"), MAIN_BOX, 2).save(
                    target / f"crop_{index:06d}.jpg", quality=92
                )
    shutil.rmtree(staging)
    record.update(status="extracted", frames=frames, crop_box=list(MAIN_BOX) if crop else None)
    return record


def extract(out_dir: Path, ffmpeg: str, limit=None, save_decode_evidence=False):
    timing_path = RESULTS / "game_747139_timing.json"
    timing = read_json(timing_path)
    url = timing["source"]["media_url"]
    chosen = select_pitches(timing["annotations"])
    if out_dir.exists() and any(out_dir.iterdir()):
        raise SystemExit("bundle directory must be new or empty")
    out_dir.mkdir(parents=True, exist_ok=True)
    version = subprocess.run(
        [ffmpeg, "-version"], capture_output=True, text=True
    ).stdout.splitlines()[0]
    records = []
    for item in chosen[:limit] if limit else chosen:
        if not item["included"]:
            records.append(
                {
                    "pitch_id": item["pitch_id"],
                    "status": "excluded",
                    "reason": item["exclusion_reason"],
                }
            )
            continue
        extra = (
            {"save_decode_evidence": True, "ffmpeg_version": version}
            if save_decode_evidence
            else {}
        )
        rec = extract_one(item, out_dir, ffmpeg, url, **extra)
        records.append(rec)
        print(item["pitch_id"], rec["status"], len(rec.get("frames", [])), flush=True)
    manifest = {
        "schema": SCHEMA,
        "rule": RULE,
        "source": {
            "media_url": url,
            "duration_seconds": timing["source"]["duration_seconds"],
            "time_base": "1/60000",
            "ticks_per_frame": TICKS_PER_FRAME,
            "timing_file_sha256": sha256_file(timing_path),
        },
        "ffmpeg_version": version,
        "selection": chosen,
        "pitches": records,
    }
    (out_dir / "manifest.json").write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    return manifest


def existing_method(chosen):
    """What the frozen v0 reader produced for the same keys: one decision frame per pitch."""
    from intent.mitt_inventory import REASON_TABLE

    rows = {
        r["pitch_id"]: r
        for r in (
            json.loads(x)
            for x in (RESULTS / "game_747139_intent_v0.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if x
        )
    }
    out, counts, cats = [], Counter(), Counter()
    for item in chosen:
        row = rows.get(item["pitch_id"])
        if row is None:
            out.append({"pitch_id": item["pitch_id"], "v0": "no_output_row"})
            counts["no_output_row"] += 1
            continue
        same_index = item["included"] and row["evidence"]["frame_index"] == frame_at(
            item["decision_seconds"]
        )
        entry = {
            "pitch_id": item["pitch_id"],
            "v0_status": row["status"],
            "v0_reason": row.get("unavailable_reason"),
            "v0_category": REASON_TABLE.get(row.get("unavailable_reason"))
            if row["status"] != "estimated"
            else None,
            "v0_deepest_frame": row.get("deepest_frame"),
            "v0_blocked_by": row.get("blocked_by"),
            "v0_frame_index": row["evidence"]["frame_index"],
            "v0_recorded_index_equals_bundle_decision_index": same_index,
        }
        counts[row["status"]] += 1
        if entry["v0_category"]:
            cats[entry["v0_category"]] += 1
        out.append(entry)
    return {
        "frames_read_per_pitch": 1,
        "frame_rule": "decision frame (start of the set window) only",
        "status_counts": dict(counts),
        "unavailable_categories": dict(cats),
        "deepest_frame_counts": dict(
            Counter(
                f"{e.get('v0_deepest_frame')}|{e.get('v0_blocked_by')}"
                for e in out
                if e.get("v0_status") == "estimated"
            )
        ),
        "rows": out,
    }


def check_v0_frames(bundle: Path, reference_dir: Path, ffmpeg: str):
    """Which source frame each frozen v0 decision image really is (pixel equality, read-only).

    The v0 images were grabbed by playback time; their JSONL records round(seconds x fps).
    Frames D-1..D+2 are decoded by presentation time and compared pixel for pixel with the
    v0 image (whose SHA must equal the JSONL clip_sha256). The matching frame is kept in
    ``v0_read_frames/`` so later same-frame comparisons use the image v0 actually read.
    """
    import numpy as np
    from PIL import Image

    manifest = read_json(bundle / "manifest.json")
    url = manifest["source"]["media_url"]
    rows = {
        r["pitch_id"]: r
        for r in (
            json.loads(x)
            for x in (RESULTS / "game_747139_intent_v0.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
            if x
        )
    }
    keep = bundle / "v0_read_frames"
    keep.mkdir(exist_ok=True)
    results = []
    for rec in manifest["pitches"]:
        if rec["status"] != "extracted":
            continue
        row, d = rows[rec["pitch_id"]], rec["window"]["decision_index"]
        reference = reference_dir / row["clip_id"].rsplit(":", 1)[1]
        entry = {"pitch_id": rec["pitch_id"], "recorded_index": row["evidence"]["frame_index"]}
        if not reference.is_file() or sha256_file(reference) != row["clip_sha256"]:
            results.append({**entry, "status": "reference_missing_or_sha_mismatch"})
            continue
        probe = {
            "first_index": d - 1,
            "last_index": d + 2,
            "decision_index": d,
            "release_index": d,
            "roles": {i: ["probe"] for i in range(d - 1, d + 3)},
        }
        staging = bundle / f".v0probe_{rec['pitch_id'].replace(':', '_')}"
        for attempt in range(1, 5):
            shutil.rmtree(staging, ignore_errors=True)
            staging.mkdir()
            proc = subprocess.run(
                ffmpeg_command(ffmpeg, url, probe, 1, staging / "o_%05d.jpg"),
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=300,
            )
            files = sorted(staging.glob("o_*.jpg"))
            kept = parse_showinfo(proc.stderr)["kept"] if proc.returncode == 0 else []
            if kept == list(probe["roles"]) and len(files) == len(kept):
                break
            time.sleep(2 * attempt)
        else:
            shutil.rmtree(staging, ignore_errors=True)
            results.append({**entry, "status": "probe_failed", "attempts": attempt})
            continue
        with Image.open(reference) as image:
            ref = np.asarray(image.convert("L"), dtype=np.int16)
        pixels = {}
        for index, path in zip(kept, files, strict=True):
            with Image.open(path) as image:
                pixels[index] = np.asarray(image.convert("L"), dtype=np.int16)
        exact = [i - d for i in kept if np.array_equal(pixels[i], ref)]
        cut = float(np.abs(pixels[d] - pixels[d + 1]).mean())
        if len(exact) == 1:
            index = d + exact[0]
            shutil.copy2(
                files[kept.index(index)],
                keep / f"{rec['pitch_id'].replace(':', '_')}_frame_{index:06d}.jpg",
            )
        shutil.rmtree(staging)
        seconds = Fraction(str(row["evidence"]["frame_time"]))
        results.append(
            {
                **entry,
                "status": "checked",
                "attempts": attempt,
                "pixel_identical_offsets": exact,
                "first_frame_at_or_after_time_offset": math.ceil(seconds * FPS) - d,
                "mean_abs_diff_recorded_vs_next": round(cut, 2),
            }
        )
    checked = [r for r in results if r["status"] == "checked"]
    report = {
        "checked": len(checked),
        "not_checked": len(results) - len(checked),
        "identical_at_recorded_index": sum(
            1 for r in checked if r["pixel_identical_offsets"] == [0]
        ),
        "identical_at_recorded_plus_one": sum(
            1 for r in checked if r["pixel_identical_offsets"] == [1]
        ),
        "other": sum(1 for r in checked if r["pixel_identical_offsets"] not in ([0], [1])),
        "explained_by_first_frame_at_or_after_time": sum(
            1
            for r in checked
            if r["pixel_identical_offsets"] == [r["first_frame_at_or_after_time_offset"]]
        ),
        "recorded_frame_in_a_different_shot": [
            r["pitch_id"]
            for r in checked
            if r["pixel_identical_offsets"] != [0] and r["mean_abs_diff_recorded_vs_next"] > 10
        ],
        "shot_change_threshold": "mean absolute grey difference between frames D and D+1 above 10",
        "rows": results,
    }
    (bundle / "v0_read_check.json").write_text(
        json.dumps(report, indent=1) + "\n", encoding="utf-8"
    )
    return report


def rule_clarification(bundle: Path, manifest):
    """What the 'decision' role holds, derived from the v0 read check when it exists."""
    check_path = bundle / "v0_read_check.json"
    if not check_path.is_file():
        return "the 'decision' role is the index v0 recorded (round rule); which image v0 read is not checked"
    check = read_json(check_path)
    frames = {
        p["pitch_id"]: {f["index"] for f in p["frames"]}
        for p in manifest["pitches"]
        if p.get("frames")
    }
    later = [r for r in check["rows"] if r.get("pixel_identical_offsets") == [1]]
    on_grid = sorted(
        r["pitch_id"] for r in later if r["recorded_index"] + 1 in frames.get(r["pitch_id"], ())
    )
    return (
        f"the 'decision' role is the index v0 recorded (round rule); v0 read the first frame at or after the "
        f"decision time, which is one frame later for {len(later)} of {check['checked']} checked pitches; for "
        f"{len(later) - len(on_grid)} of those that frame is not in the bundle frame list (on the grid only for "
        f"{', '.join(on_grid) or 'none'}); the read images are kept privately in v0_read_frames/"
    )


def summarize(bundle: Path, out: Path):
    manifest_path = bundle / "manifest.json"
    manifest = read_json(manifest_path)
    from intent.mitt_inventory import nearest_rank

    frame_lines, pitches, per_pitch_frames, attempt_seconds = [], [], [], []
    frames_total, seconds_total = 0, 0.0
    for rec in manifest["pitches"]:
        entry = {"pitch_id": rec["pitch_id"], "status": rec["status"]}
        if rec["status"] == "excluded":
            entry["reason"] = rec["reason"]
        if rec["status"] == "extracted":
            last = rec["attempts"][-1]
            # per-pitch windows and frame counts stay in the private manifest: with them a blind
            # review sequence could be joined back to its pitch
            entry.update(
                attempts=len(rec["attempts"]),
                index_gaps_in_window=last["index_gaps_in_window"],
            )
            frames_total += len(rec["frames"])
            seconds_total += float(
                Fraction(rec["window"]["last_index"] - rec["window"]["first_index"]) / FPS
            )
            per_pitch_frames.append(len(rec["frames"]))
            attempt_seconds.extend(a["elapsed_seconds"] for a in rec["attempts"])
            for f in rec["frames"]:
                frame_lines.append(f"{rec['pitch_id']}\t{f['index']}\t{f['sha256']}")
        pitches.append(entry)
    extracted = [p for p in pitches if p["status"] == "extracted"]
    selection = [s for s in manifest["selection"] if s["included"]]
    lead = sorted(s["release_seconds"] - s["decision_seconds"] for s in selection)
    summary = {
        "schema": SCHEMA + "-public-summary",
        "scope": "development data (747139 was already development data in M3); not an independent evaluation",
        "rule": manifest["rule"],
        "rule_wording_note": "rule is copied as recorded at extraction; its first always_include item "
        "names the frame at the index v0 recorded, not necessarily the image v0 read",
        "rule_clarification": rule_clarification(bundle, manifest),
        "source": {k: v for k, v in manifest["source"].items()},
        "ffmpeg_version": manifest["ffmpeg_version"],
        "manifest_sha256": sha256_file(manifest_path),
        "frames_digest_sha256": hashlib.sha256(
            ("\n".join(sorted(frame_lines)) + "\n").encode()
        ).hexdigest(),
        "counts": {
            "planned_pitch_keys": len(pitches),
            "extracted": len(extracted),
            "excluded": sum(1 for p in pitches if p["status"] == "excluded"),
            "failed": sum(1 for p in pitches if p["status"] == "extraction_failed"),
            "frames": frames_total,
            "frames_per_pitch_range": [min(per_pitch_frames), max(per_pitch_frames)]
            if per_pitch_frames
            else None,
            "seconds_covered": round(seconds_total, 3),
            "windows_with_index_gap": sum(1 for p in extracted if p["index_gaps_in_window"]),
            "retried_pitches": sum(1 for p in extracted if p["attempts"] > 1),
            "attempt_seconds_range": [min(attempt_seconds), max(attempt_seconds)]
            if attempt_seconds
            else None,
        },
        "decision_to_release_seconds": {
            "n": len(lead),
            "median": round(statistics.median(lead), 3),
            "p10": round(nearest_rank(lead, 0.1), 3),
            "p90": round(nearest_rank(lead, 0.9), 3),
            "min": round(lead[0], 3),
            "max": round(lead[-1], 3),
            "percentile_rule": "nearest rank (ceil(q*n)-th value)",
        }
        if lead
        else None,
        "timing_basis": "decision/release seconds are AI visual annotations (Codex/Claude agents), not human ground truth",
        "pitches": pitches,
        "existing_method_on_same_keys": existing_method(manifest["selection"]),
        "v0_read_image_check": (
            {k: v for k, v in read_json(bundle / "v0_read_check.json").items() if k != "rows"}
            if (bundle / "v0_read_check.json").is_file()
            else None
        ),
        "private_location": "outputs/ (git-ignored); frames and crops are not published",
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(summary, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    ext = sub.add_parser("extract")
    ext.add_argument("--out", type=Path, required=True)
    ext.add_argument("--ffmpeg", default=shutil.which("ffmpeg") or "ffmpeg")
    ext.add_argument("--limit", type=int)
    ext.add_argument("--save-decode-evidence", action="store_true")
    chk = sub.add_parser("check-v0-frames")
    chk.add_argument("--bundle", type=Path, required=True)
    chk.add_argument("--reference-dir", type=Path, required=True)
    chk.add_argument("--ffmpeg", default=shutil.which("ffmpeg") or "ffmpeg")
    summ = sub.add_parser("summarize")
    summ.add_argument("--bundle", type=Path, required=True)
    summ.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.cmd == "check-v0-frames":
        report = check_v0_frames(args.bundle, args.reference_dir, args.ffmpeg)
        print(json.dumps({k: v for k, v in report.items() if k != "rows"}))
        return
    if args.cmd == "extract":
        if "outputs" not in args.out.resolve().parts:
            parser.error("frames go under outputs/ (git-ignored)")
        manifest = extract(args.out, args.ffmpeg, args.limit, args.save_decode_evidence)
        print(json.dumps(Counter(p["status"] for p in manifest["pitches"])))
    else:
        s = summarize(args.bundle, args.out)
        print(json.dumps(s["counts"]))


if __name__ == "__main__":
    main()

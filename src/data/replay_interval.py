"""Every decoded frame in three fixed CV48b development intervals; no visual judgments."""

from __future__ import annotations

import json
from pathlib import Path

from src.data import replay_context as context

SCHEMA = "pitcheezy-replay-interval-v1"
TIME_BASE = "1/90000"
# Inclusive PTS bounds, decoded frame count, existing representative PTS.
INTERVALS = {
    "849843:1:1": (173842, 209977, 24, 191959),
    "849843:1:2": (173890, 209926, 25, 191908),
    "849843:1:3": (163438, 208483, 31, 190465),
}


def select_interval(pitch_key, time_base, rows):
    """Keep all actual decoded frames; neither resample nor fill timestamp gaps."""
    if pitch_key not in INTERVALS:
        raise ValueError("only the fixed development PA1 intervals are allowed")
    if time_base != TIME_BASE or not rows:
        raise ValueError("the interval requires decoded frames on the fixed 1/90000 clock")
    previous_pts = None
    for ordinal, row in enumerate(rows):
        if (
            not isinstance(row, dict)
            or type(row.get("ordinal")) is not int
            or row["ordinal"] != ordinal
            or type(row.get("pts")) is not int
            or (previous_pts is not None and row["pts"] <= previous_pts)
        ):
            raise ValueError("decoded frame ordinals and PTS must be complete and strictly ordered")
        previous_pts = row["pts"]
    lower, upper, expected_count, representative = INTERVALS[pitch_key]
    selected = [dict(row) for row in rows if lower <= row["pts"] <= upper]
    if not selected or (selected[0]["pts"], selected[-1]["pts"]) != (lower, upper):
        raise ValueError("both fixed interval boundaries must be actual decoded frames")
    if len(selected) != expected_count:
        raise ValueError("decoded interval frame count differs from the fixed review")
    if representative not in {row["pts"] for row in selected}:
        raise ValueError("the reviewed representative frame is missing from the interval")
    return selected


def build_intervals(root, destination, ffprobe, ffmpeg):
    destination = context.private_destination(destination)
    context.validate_crop(context.CROP, context.FRAME_SIZE)
    root = Path(root).resolve(strict=True)
    registry = root / "registry.sqlite"
    registry_sha = context.digest(registry)
    rows = context.first_three(root)
    for row in rows:
        context.clip_file(root, row)
    destination.mkdir(parents=True)
    records = []
    for row in rows:
        pitch_key = row["pitch_key"]

        def selector(time_base, frames, key=pitch_key):
            return select_interval(key, time_base, frames)

        record = context.extract_context(
            root, row, destination, ffprobe, ffmpeg, frame_selector=selector
        )
        lower, upper, count, representative = INTERVALS[pitch_key]
        record["interval"] = {
            "lower_pts_inclusive": lower,
            "upper_pts_inclusive": upper,
            "expected_decoded_frames": count,
            "representative_pts": representative,
        }
        records.append(record)
    if context.digest(registry) != registry_sha:
        raise ValueError("source registry changed during extraction")
    report = {
        "schema": SCHEMA,
        "game_pk": context.GAME,
        "at_bat_number": 1,
        "source_registry_sha256": registry_sha,
        "evidence_kind": "offline_development_decoded_intervals_not_visual_or_human_truth",
        "selection": {
            "kind": "all_decoded_frames_in_fixed_inclusive_pts_intervals",
            "time_base": TIME_BASE,
            "expected_total_frames": sum(value[2] for value in INTERVALS.values()),
            "frame_list_field": "sampled_frames retained for existing evidence-tool compatibility",
            "timestamp_gaps": "preserved; no FPS interpolation or claim of source capture continuity",
        },
        "crop_rectangle_xyxy": list(context.CROP),
        "crop_coordinates": "left/top inclusive, right/bottom exclusive; crop xy + origin = full-frame xy",
        "records": records,
    }
    (destination / "audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return report

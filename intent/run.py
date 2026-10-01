"""Emit IntentEstimate v1 JSONL for one game from committed mitt/plate point annotations.

    python -m intent.run --game 747139 --out intent_747139.jsonl

Inputs (defaults under docs/results/mlb_p0): the frozen manual timing (decision frame per
pitch) and the v0 point file written by the annotation step. Every emitted line is validated
with ``validate_intent_estimate``; the run never invents a point for a pitch that has none.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intent.geometry import (  # noqa: E402
    CORNER_ORDER,
    homography_from_corners,
    inside_unit_square,
    project_point,
    reprojection_error_pixels,
)
from intent.schema import make_estimate, make_unavailable, validate_intent_estimate  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs/results/mlb_p0"
POINTS_SCHEMA = "intent_points_v0"


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def build_records(game_pk, timing, points, *, frames_root=None, verify_frames=False):
    """Return (records, counters) for every annotated timing row of the game."""
    if points.get("schema") != POINTS_SCHEMA or points.get("game_pk") != game_pk:
        raise ValueError("point file schema/game mismatch")
    method = points["method"]
    label_source = points["label_source"]
    by_key = {}
    for frame in points["frames"]:
        key = (frame["at_bat_number"], frame["pitch_number"])
        if key in by_key:
            raise ValueError(f"duplicate point annotation for {key}")
        by_key[key] = frame
    rows = sorted(
        (r for r in timing["annotations"] if r["status"] == "annotated"),
        key=lambda r: (r["at_bat_number"], r["pitch_number"]),
    )
    records, counters = (
        [],
        {"lines": 0, "estimated": 0, "unavailable": 0, "zone": 0, "missing_annotation": 0},
    )
    for row in rows:
        key = (row["at_bat_number"], row["pitch_number"])
        pitch_id = f"{game_pk}:{key[0]}:{key[1]}"
        t = float(row["decision_seconds"])
        frame = by_key.get(key)
        if frame is None:
            counters["missing_annotation"] += 1
            clip_id, sha = f"{game_pk}:decision_frame:{t:.2f}", "0" * 64
            records.append(
                make_unavailable(
                    pitch_id, clip_id, sha, method, t, label_source, "no_point_annotation_for_pitch"
                )
            )
            counters["unavailable"] += 1
            continue
        if abs(float(frame["frame_seconds"]) - t) > 1e-6:
            raise ValueError(f"point annotation for {key} is not on the decision frame")
        clip_id = f"{game_pk}:decision_frame:{t:.2f}:{Path(frame['path']).name}"
        sha = frame["image_sha256"]
        if verify_frames:
            actual = _sha256(Path(frames_root or ROOT) / frame["path"])
            if actual != sha:
                raise ValueError(f"frame bytes changed for {key}")
        if frame["status"] == "unavailable":
            records.append(
                make_unavailable(
                    pitch_id, clip_id, sha, method, t, label_source, frame["unavailable_reason"]
                )
            )
            counters["unavailable"] += 1
            continue
        mitt = frame["mitt_center"]
        basis = (
            frame.get("uncertainty_basis")
            or points.get("uncertainty_basis")
            or "annotator estimate"
        )
        corners = frame.get("plate_corners")
        zone = transform = None
        if corners and all(corners.get(name) for name in CORNER_ORDER):
            h = homography_from_corners(corners)
            uv = project_point(h, mitt)
            zone = (uv[0], uv[1], inside_unit_square(uv))
            transform = {
                "source_frame": "image_pixels",
                "target_frame": "annotated_image_zone",
                "method": "plane_homography_plate_corners_to_unit_square",
                "version": "v0",
                "error": None,
                "error_units": "pixels",
                "error_status": "unmeasured",
                "evidence": {
                    "plate_corners_image_pixels": {
                        name: [float(v) for v in corners[name]] for name in CORNER_ORDER
                    },
                    "corner_order": list(CORNER_ORDER),
                    "corner_reprojection_rms_pixels": reprojection_error_pixels(h, corners),
                    "note": "mitt is above the plate plane; this hop normalizes the image zone only",
                },
            }
            counters["zone"] += 1
        records.append(
            make_estimate(
                pitch_id,
                clip_id,
                sha,
                method,
                t,
                label_source,
                mitt,
                frame["uncertainty_pixels"],
                basis,
                annotated_zone=zone,
                zone_transform=transform,
            )
        )
        counters["estimated"] += 1
    counters["lines"] = len(records)
    return records, counters


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--game", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--timing", type=Path, default=None)
    parser.add_argument("--points", type=Path, default=None)
    parser.add_argument(
        "--frames-root", type=Path, default=None, help="checkout holding outputs/frames"
    )
    parser.add_argument(
        "--verify-frames", action="store_true", help="re-hash the local decision frames"
    )
    args = parser.parse_args(argv)
    started = time.perf_counter()
    timing = _load(args.timing or RESULTS / f"game_{args.game}_timing.json")
    points = _load(args.points or RESULTS / f"game_{args.game}_intent_points_v0.json")
    if timing["game_pk"] != args.game:
        parser.error("timing file is for another game")
    records, counters = build_records(
        args.game, timing, points, frames_root=args.frames_root, verify_frames=args.verify_frames
    )
    for record in records:
        validate_intent_estimate(record)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(
        "".join(json.dumps(r, ensure_ascii=False, allow_nan=False) + "\n" for r in records),
        encoding="utf-8",
    )
    elapsed = round(time.perf_counter() - started, 3)
    summary = {
        "game_pk": args.game,
        "out": str(args.out),
        **counters,
        "elapsed_seconds_this_run": elapsed,
        "annotation_elapsed": points.get("annotation_elapsed"),
        "method": points["method"],
        "label_source": points["label_source"],
        "review_status": "unreviewed",
        "frames_verified": bool(args.verify_frames),
    }
    Path(str(args.out) + ".run.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

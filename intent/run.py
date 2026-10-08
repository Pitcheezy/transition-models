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
import math
import sys
import time
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intent.geometry import CORNER_ORDER, front_edge_similarity, project_point  # noqa: E402
from intent.plate_feet import (  # noqa: E402
    CALIBRATION_SCHEMA,
    PLATE_WIDTH_FEET,
    feet_transform_step,
    hop2_parameters,
    load_calibration,
    zone_to_plate_feet,
)
from intent.schema import (  # noqa: E402
    frame_index_from_time,
    make_estimate,
    make_unavailable,
    validate_intent_estimate,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs/results/mlb_p0"
POINTS_SCHEMA = "intent_points_v0"
ZONE_METHOD = "plate_front_edge_similarity"
ZONE_VERSION = "v1"
POOLED_WIDTH_TOLERANCE = 0.08


def camera_constants(frames):
    """Pooled front-edge roll (camera constant) and per-PA median front-edge widths."""
    rolls, widths = [], {}
    for frame in frames:
        corners = frame.get("plate_corners") or {}
        if not (corners.get("front_left") and corners.get("front_right")):
            continue
        fl, fr = corners["front_left"], corners["front_right"]
        rolls.append(math.atan2(fr[1] - fl[1], fr[0] - fl[0]))
        widths.setdefault(frame["at_bat_number"], []).append(
            math.hypot(fr[0] - fl[0], fr[1] - fl[1])
        )
    roll = float(np.median(rolls)) if rolls else 0.0
    pooled = {pa: float(np.median(w)) for pa, w in widths.items()}
    return {"roll_radians": roll, "roll_frames": len(rolls), "pa_median_width_px": pooled}


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def video_fps(points):
    """Source frame rate as an integer ratio, from the points file's ``video`` block."""
    video = points.get("video") or {}
    num, den = video.get("fps_num"), video.get("fps_den")
    if not (isinstance(num, int) and isinstance(den, int) and num > 0 and den > 0):
        raise ValueError(
            "points file needs video.fps_num and video.fps_den (source frame rate) so that "
            "evidence.frame_index can be numbered"
        )
    return num, den


def build_records(
    game_pk, timing, points, *, frames_root=None, verify_frames=False, calibration=None
):
    """Return (records, counters) for every annotated timing row of the game.

    ``calibration`` is the measured hop-2 document (``intent.plate_feet.load_calibration``) or
    None; plate feet are emitted either way, with error_status measured only when it exists.
    """
    if not isinstance(timing, dict) or timing.get("game_pk") != game_pk:
        raise ValueError("timing file game mismatch")
    if calibration is not None and (
        not isinstance(calibration, dict)
        or calibration.get("schema") != CALIBRATION_SCHEMA
        or calibration.get("game_pk") != game_pk
    ):
        raise ValueError("calibration file schema/game mismatch")
    if points.get("schema") != POINTS_SCHEMA or points.get("game_pk") != game_pk:
        raise ValueError("point file schema/game mismatch")
    method = points["method"]
    label_source = points["label_source"]
    fps_num, fps_den = video_fps(points)
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
    camera = camera_constants(points["frames"])
    hop2 = hop2_parameters(calibration)
    records, counters = (
        [],
        {
            "lines": 0,
            "estimated": 0,
            "unavailable": 0,
            "zone": 0,
            "plate_feet": 0,
            "missing_annotation": 0,
        },
    )
    for row in rows:
        key = (row["at_bat_number"], row["pitch_number"])
        pitch_id = f"{game_pk}:{key[0]}:{key[1]}"
        t = float(row["decision_seconds"])
        # frames were grabbed by playback time, so the frame number is round(t * fps)
        frame_index = frame_index_from_time(t, fps_num, fps_den)
        frame = by_key.get(key)
        if frame is None:
            counters["missing_annotation"] += 1
            clip_id, sha = f"{game_pk}:decision_frame:{t:.2f}", "0" * 64
            records.append(
                make_unavailable(
                    pitch_id,
                    clip_id,
                    sha,
                    method,
                    t,
                    label_source,
                    "no_point_annotation_for_pitch",
                    frame_index=frame_index,
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
                    pitch_id,
                    clip_id,
                    sha,
                    method,
                    t,
                    label_source,
                    frame["unavailable_reason"],
                    frame_index=frame_index,
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
        zone = transform = feet = feet_step = None
        if corners and all(corners.get(name) for name in ("front_left", "front_right")):
            own_width = math.hypot(
                corners["front_right"][0] - corners["front_left"][0],
                corners["front_right"][1] - corners["front_left"][1],
            )
            pooled = camera["pa_median_width_px"].get(key[0], own_width)
            use_pooled = abs(own_width - pooled) <= POOLED_WIDTH_TOLERANCE * pooled
            h, diagnostics = front_edge_similarity(
                corners,
                roll_radians=camera["roll_radians"],
                width_px=pooled if use_pooled else own_width,
            )
            diagnostics["width_source"] = (
                "median of this plate appearance's M1 front edges"
                if use_pooled
                else "this frame only (differs from the PA median by more than 8 percent)"
            )
            diagnostics["roll_source"] = (
                f"median front-edge direction over {camera['roll_frames']} M1 frames"
            )
            uv = project_point(h, mitt)
            # v1 flag: within the plate's lateral extent and at a plausible height (0-3 plate
            # widths = 0-4.25 ft); the M1 ground-quad meaning no longer applies to a mitt.
            zone = (uv[0], uv[1], 0.0 <= uv[0] <= 1.0 and 0.0 <= uv[1] <= 3.0)
            hop1_error = (calibration or {}).get("hop1_front_edge_rms_pixels")
            transform = {
                "source_frame": "image_pixels",
                "target_frame": "annotated_image_zone",
                "method": ZONE_METHOD,
                "version": ZONE_VERSION,
                "error": float(hop1_error) if hop1_error is not None else None,
                "error_units": "pixels",
                "error_status": "measured" if hop1_error is not None else "unmeasured",
                "evidence": {
                    "plate_corners_image_pixels": {
                        name: [float(v) for v in corners[name]]
                        for name in CORNER_ORDER
                        if corners.get(name)
                    },
                    "corner_order": list(CORNER_ORDER),
                    "anchor": "front_left/front_right only; u along the 17-inch front edge, "
                    "v up from that ground line, both in front-edge widths",
                    "inside_annotated_quad": "0 <= u <= 1 and 0 <= v <= 3 (lateral plate extent, "
                    "height below 4.25 ft); not a strike-zone test",
                    "diagnostics": diagnostics,
                    "note": "the mitt is above the plate plane, so a plane homography (M1 v0) "
                    "gave a meaningless v; v1 uses the front-edge similarity instead",
                },
            }
            counters["zone"] += 1
            feet = zone_to_plate_feet(uv, hop2["matrix"])
            feet_step = feet_transform_step(
                diagnostics["width_used_px"] / PLATE_WIDTH_FEET, diagnostics, calibration
            )
            counters["plate_feet"] += 1
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
                plate_feet=feet,
                feet_transform=feet_step,
                frame_index=frame_index,
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
    parser.add_argument(
        "--calibration",
        type=Path,
        default=None,
        help="measured hop-2 calibration (default docs/results/mlb_p0/game_<game>_intent_plate_calibration_v0.json)",
    )
    args = parser.parse_args(argv)
    started = time.perf_counter()
    timing = _load(args.timing or RESULTS / f"game_{args.game}_timing.json")
    points = _load(args.points or RESULTS / f"game_{args.game}_intent_points_v0.json")
    if timing["game_pk"] != args.game:
        parser.error("timing file is for another game")
    calibration = load_calibration(
        args.calibration or RESULTS / f"game_{args.game}_intent_plate_calibration_v0.json"
    )
    records, counters = build_records(
        args.game,
        timing,
        points,
        frames_root=args.frames_root,
        verify_frames=args.verify_frames,
        calibration=calibration,
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
        "frame_index_rule": {
            "rule": (points.get("video") or {}).get(
                "frame_index_rule", "round(frame_time * fps) of the source video"
            ),
            "fps": "{}/{}".format(*video_fps(points)),
        },
        "plate_calibration": None
        if calibration is None
        else {
            k: calibration.get(k)
            for k in (
                "rms_error_feet",
                "rms_basis",
                "error_status",
                "human_verified_count",
                "measured_on",
            )
        },
        "hop2_parameters": {k: v for k, v in hop2_parameters(calibration).items() if k != "matrix"},
        "caveats": [
            "evidence.frame_index rule: "
            + (points.get("video") or {}).get(
                "frame_index_rule", "round(frame_time * fps) of the source video"
            )
            + " (fps from the points file).",
            "annotated_image_zone (v1) is a similarity anchored on the plate's front edge: u along "
            "the 17-inch edge, v up from the ground line, both in plate widths (camera roll and "
            "per-PA width pooled over the M1 corners); plate_feet (v0) scales that by 17/12 ft "
            "with the Statcast plate_x sign and removes the depth parallax for a nominal mitt "
            "depth using the calibrated camera tilt (uncorrected when no calibration file is "
            "present); the calibration file reports what was measured (null error until then).",
            "points come from assistant visual estimates with no human review and no measured "
            "accuracy; accuracy_estimate stays null until measured on an independent sample.",
        ],
    }
    Path(str(args.out) + ".run.json").write_text(
        json.dumps(summary, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

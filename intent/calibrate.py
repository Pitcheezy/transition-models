"""Measure hop 1/hop 2 errors from committed pixel readings and write the plate calibration file.

    python -m intent.calibrate --game 747139

Input (default ``docs/results/mlb_p0/game_<game>_intent_calibration_readings_v0.json``): pixel
readings by two independent assistant readers (A, B) on decision frames, catch frames and
batter's-box frames, plus the frozen feed-derived Statcast references. Coordinates only.

Output ``game_<game>_intent_plate_calibration_v0.json``:

- ``hop1_front_edge_rms_pixels``: single-reader repeatability of the plate front-edge ends,
  rms(A - B) / sqrt(2) over both ends and both coordinates (shared systematic errors of two
  sessions of the same model are not visible here);
- ``camera``: tilt from the 6-ft batter's-box depth (long baseline), pan from the plate quads,
  and the depth-parallax term d*tan(tilt) they imply for a mitt 2.5 ft behind the plate front;
- ``lateral_check``: batter's-box chalk lines (inner +/-14.5 in, outer +/-62.5 in from the
  plate centre) mapped through hops 1-2 versus their known plate_x (transform-only check,
  on-plane, line-width convention not controlled);
- ``end_to_end_check``: the ball/pocket on the FIRST frame with the ball in the mitt mapped
  through hops 1-2 versus the Statcast trajectory evaluated at the catch depth (y = -1.0 ft,
  sensitivity at -0.5/-1.5 ft); per axis: mean signed error (bias) with its standard error,
  spread (SD), rms, and the slope/intercept of mapped-vs-reference;
- ``overlay_check``: the broadcast strike-zone overlay's implied height versus the feed zone
  (a finding, not a calibration input);
- ``rms_error_feet``: the headline number used by ``intent.run`` = end-to-end 2-D rms at
  y = -1.0 ft over A/B-mean readings, or null when fewer than ``min_pitches`` qualify.

``human_verified_count`` comes only from an optional file of pitch ids a person confirmed.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intent.geometry import front_edge_similarity, project_point  # noqa: E402
from intent.plate_feet import (  # noqa: E402
    CALIBRATION_SCHEMA,
    METHOD,
    NOMINAL_MITT_DEPTH_FEET,
    PLATE_WIDTH_FEET,
    UNCORRECTED_MATRIX,
    VERSION,
    X_CONVENTION,
    zone_to_feet_matrix,
    zone_to_plate_feet,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs/results/mlb_p0"
READINGS_SCHEMA = "intent_calibration_readings_v0"
CHALK_KNOWN_FEET = {  # image-left is the first-base side: positive plate_x
    "left_inner_x": +(8.5 + 6.0) / 12.0,
    "right_inner_x": -(8.5 + 6.0) / 12.0,
    "left_outer_x": +(8.5 + 6.0 + 48.0) / 12.0,
    "right_outer_x": -(8.5 + 6.0 + 48.0) / 12.0,
}
BOX_DEPTH_FEET = 6.0
MIN_PITCHES = 10
DEPTHS = ("-0.5", "-1.0", "-1.5")


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _mean(values):
    values = [float(v) for v in values]
    return float(sum(values) / len(values)) if values else None


def _sd(values):
    values = [float(v) for v in values]
    if len(values) < 2:
        return None
    m = _mean(values)
    return float(math.sqrt(sum((v - m) ** 2 for v in values) / (len(values) - 1)))


def _rms(values):
    values = [float(v) for v in values]
    return float(math.sqrt(sum(v * v for v in values) / len(values))) if values else None


def _axis_stats(errors):
    n = len(errors)
    sd = _sd(errors)
    return {
        "n": n,
        "mean_signed_feet": _mean(errors),
        "se_of_mean_feet": (sd / math.sqrt(n)) if sd is not None and n else None,
        "sd_feet": sd,
        "rms_feet": _rms(errors),
    }


def _regression(xs, ys):
    """Least-squares slope/intercept of ys on xs (None with fewer than 3 points)."""
    if len(xs) < 3:
        return None
    mx, my = _mean(xs), _mean(ys)
    sxx = sum((x - mx) ** 2 for x in xs)
    if sxx == 0:
        return None
    slope = sum((x - mx) * (y - my) for x, y in zip(xs, ys, strict=True)) / sxx
    intercept = my - slope * mx
    resid = [y - (intercept + slope * x) for x, y in zip(xs, ys, strict=True)]
    n = len(xs)
    s2 = sum(r * r for r in resid) / (n - 2)
    return {
        "slope": slope,
        "intercept": intercept,
        "slope_se": math.sqrt(s2 / sxx),
        "n": n,
        "x_range": [min(xs), max(xs)],
    }


def _corners(plate_front):
    return {"front_left": plate_front["left_end"], "front_right": plate_front["right_end"]}


def pixel_to_feet(plate_front, pixel, matrix=UNCORRECTED_MATRIX):
    h, diag = front_edge_similarity(_corners(plate_front))
    uv = project_point(h, pixel)
    return zone_to_plate_feet(uv, matrix), diag


def front_edge_noise(decision_frames):
    diffs, pairs = [], 0
    for frame in decision_frames:
        a, b = frame["readers"].get("A"), frame["readers"].get("B")
        if not (a and b and a.get("plate_front") and b.get("plate_front")):
            continue
        pairs += 1
        for end in ("left_end", "right_end"):
            for k in (0, 1):
                diffs.append(a["plate_front"][end][k] - b["plate_front"][end][k])
    rms = _rms(diffs)
    return {
        "frames_with_both_readers": pairs,
        "rms_pixels": rms / math.sqrt(2) if rms else None,
        "definition": "rms(A - B)/sqrt(2) over both ends and both coordinates",
    }


NOMINAL_MITT_DEPTH_FEET_FOR_PARALLAX = NOMINAL_MITT_DEPTH_FEET


RUBBER_TO_PLATE_FRONT_FEET = 60.5 - 17.0 / 12.0  # front edge of the rubber to the plate front
RUBBER_WIDTH_FEET = 2.0


def pan_from_rubber(rubber_frames):
    """Camera pan (tan, plate_x sign) from the rubber's position on the plate-front scale.

    For each frame: map the rubber centre through hop 1 with that frame's plate front edge
    (x_r = -(17/12)(u - 0.5)); the rubber's own width gives the scale ratio r = s_rubber /
    s_plate, hence the camera distance Y = L*r/(r-1) for the rubber-to-plate distance L; then
    pan_tan = -x_r * (Y - L) / (L * Y).
    """
    rows = []
    for frame in rubber_frames:
        for reader, read in frame["readers"].items():
            if not read or not read.get("plate_front") or not read.get("rubber_center"):
                continue
            (x_r, _), diag = pixel_to_feet(read["plate_front"], read["rubber_center"])
            plate_px_per_ft = diag["front_edge_px"] / PLATE_WIDTH_FEET
            width = read.get("rubber_width_px")
            r = (width / RUBBER_WIDTH_FEET) / plate_px_per_ft if width else None
            length = RUBBER_TO_PLATE_FRONT_FEET
            distance = length * r / (r - 1.0) if r and r > 1.02 else None
            pan_tan = -x_r * (distance - length) / (length * distance) if distance else None
            rows.append(
                {
                    "frame": frame.get("frame"),
                    "reader": reader,
                    "rubber_x_on_plate_scale_feet": x_r,
                    "scale_ratio": r,
                    "camera_distance_feet": distance,
                    "pan_tan": pan_tan,
                }
            )
    values = [row["pan_tan"] for row in rows if row["pan_tan"] is not None]
    mean = _mean(values)
    return {
        "pan_tan": mean,
        "pan_degrees": math.degrees(math.atan(mean)) if mean is not None else None,
        "sd": _sd(values),
        "n": len(values),
        "basis": "rubber centre and width read on centre-field frames, plate front edge of the same frame",
        "rows": rows,
    }


def camera_estimates(readings):
    """Tilt from the batter's-box depth, pan from the plate quads, parallax term they imply."""
    tilt_sins, rows = [], []
    for frame in readings.get("box_frames", []):
        width = frame.get("plate_front_width_px")
        if not width:
            continue
        px_per_ft = width / PLATE_WIDTH_FEET
        for reader, read in frame["readers"].items():
            if not read:
                continue
            for side in ("left_box", "right_box"):
                box = read.get(side)
                if not box or box.get("front_y") is None or box.get("back_y") is None:
                    continue
                dy = box["front_y"] - box["back_y"]
                sin_t = (dy / BOX_DEPTH_FEET) / px_per_ft
                tilt_sins.append(sin_t)
                rows.append(
                    {
                        "at_bat_number": frame["at_bat_number"],
                        "pitch_number": frame["pitch_number"],
                        "reader": reader,
                        "box": side,
                        "depth_px": dy,
                        "px_per_foot": px_per_ft,
                        "sin_tilt": sin_t,
                    }
                )
    valid = [s for s in tilt_sins if 0 < s < 1]
    sin_mean = _mean(valid)
    sin_sd = _sd(valid)
    return {
        "tilt": {
            "sin_mean": sin_mean,
            "sin_sd": sin_sd,
            "sin_se": (sin_sd / math.sqrt(len(valid))) if sin_sd and valid else None,
            "degrees": math.degrees(math.asin(sin_mean)) if sin_mean else None,
            "n_box_readings": len(valid),
            "basis": "batter's box front/back chalk lines 6 ft apart, lateral scale from the "
            "same frame's plate front edge (M1 corners)",
            "rows": rows,
        },
        "pan": readings.get("pan_from_plate_quads") or {},
        "pan_from_rubber": readings.get("pan_from_rubber"),
        "depth_parallax_feet_at_nominal_mitt_depth": (
            NOMINAL_MITT_DEPTH_FEET * math.tan(math.asin(sin_mean)) if sin_mean else None
        ),
        "nominal_mitt_depth_feet": NOMINAL_MITT_DEPTH_FEET,
    }


def lateral_check(decision_frames):
    rows, errors = [], {k: [] for k in CHALK_KNOWN_FEET}
    for frame in decision_frames:
        for reader, read in frame["readers"].items():
            if not read or not read.get("plate_front") or not read.get("chalk"):
                continue
            y_row = (read["plate_front"]["left_end"][1] + read["plate_front"]["right_end"][1]) / 2
            for line, known in CHALK_KNOWN_FEET.items():
                x = read["chalk"].get(line)
                if x is None:
                    continue
                (plate_x, _), _ = pixel_to_feet(read["plate_front"], (x, y_row))
                err = plate_x - known
                errors[line].append(err)
                rows.append(
                    {
                        "at_bat_number": frame["at_bat_number"],
                        "pitch_number": frame["pitch_number"],
                        "reader": reader,
                        "line": line,
                        "x_px": x,
                        "plate_x_feet": round(plate_x, 4),
                        "known_feet": round(known, 4),
                        "error_feet": round(err, 4),
                    }
                )
    inner = [e for line in ("left_inner_x", "right_inner_x") for e in errors[line]]
    outer = [e for line in ("left_outer_x", "right_outer_x") for e in errors[line]]
    return {
        "known_feet": CHALK_KNOWN_FEET,
        "all": _axis_stats([r["error_feet"] for r in rows]),
        "inner_lines": _axis_stats(inner),
        "outer_lines": _axis_stats(outer),
        "per_line_mean_signed_feet": {k: _mean(v) for k, v in errors.items()},
        "caveat": "readers marked line centres; chalk lines are 2-4 in wide, so a +/-0.1-0.17 ft "
        "convention term is included; transform-only, on-plane, no depth parallax",
        "rows": rows,
    }


def overlay_check(decision_frames):
    rows = []
    for frame in decision_frames:
        for reader, read in frame["readers"].items():
            kz = read.get("kzone") if read else None
            pf = read.get("plate_front") if read else None
            if not (kz and pf and frame.get("sz_top") and frame.get("sz_bot")):
                continue
            width_px = pf["right_end"][0] - pf["left_end"][0]
            if width_px <= 0:
                continue
            px_per_ft = width_px / PLATE_WIDTH_FEET
            top = (kz["top_left"][1] + kz["top_right"][1]) / 2
            bottom = (kz["bottom_left"][1] + kz["bottom_right"][1]) / 2
            left = (kz["top_left"][0] + kz["bottom_left"][0]) / 2
            right = (kz["top_right"][0] + kz["bottom_right"][0]) / 2
            ground = (pf["left_end"][1] + pf["right_end"][1]) / 2
            rows.append(
                {
                    "at_bat_number": frame["at_bat_number"],
                    "pitch_number": frame["pitch_number"],
                    "reader": reader,
                    "overlay_width_over_plate_width": (right - left) / width_px,
                    "implied_height_feet": (bottom - top) / px_per_ft,
                    "implied_bottom_feet": (ground - bottom) / px_per_ft,
                    "implied_top_feet": (ground - top) / px_per_ft,
                    "feed_sz_bot": frame["sz_bot"],
                    "feed_sz_top": frame["sz_top"],
                    "feed_height_feet": frame["sz_top"] - frame["sz_bot"],
                }
            )
    ratios = [r["implied_height_feet"] / r["feed_height_feet"] for r in rows]
    ratio_mean = _mean(ratios)
    consistent = ratio_mean is not None and abs(ratio_mean - 1.0) < 0.05
    return {
        "n": len(rows),
        "width_ratio_mean": _mean([r["overlay_width_over_plate_width"] for r in rows]),
        "height_ratio_implied_over_feed": _axis_stats(ratios) if rows else None,
        "implied_height_feet_mean": _mean([r["implied_height_feet"] for r in rows]),
        "feed_height_feet_mean": _mean([r["feed_height_feet"] for r in rows]),
        "implied_minus_feed_bottom_mean": _mean(
            [r["implied_bottom_feet"] - r["feed_sz_bot"] for r in rows]
        ),
        "implied_minus_feed_top_mean": _mean(
            [r["implied_top_feet"] - r["feed_sz_top"] for r in rows]
        ),
        "conclusion": (
            "the overlay's width matches the plate width and its height reproduces the per-pitch "
            "feed zone height under the lateral px/ft scale, so the vertical scale equals the "
            "lateral scale; the overlay sits a constant offset above the plate-front ground "
            "line (it is drawn at a deeper point of the plate), so its edges are not used as an "
            "origin"
            if consistent
            else "the overlay's height does not follow the per-pitch feed zone under the lateral "
            "scale; its vertical edges are not usable as sz ground truth"
        ),
        "vertical_scale_verified": consistent,
        "rows": rows,
    }


def end_to_end_check(catch_pitches, matrix):
    per_pitch, used = [], 0
    for pitch in catch_pitches:
        reads, skipped = {}, []
        for reader, read in pitch["readers"].items():
            if not read:
                continue
            if read.get("chosen_offset") is None:
                skipped.append(f"{reader}: {read.get('chosen_reason')}")
                continue
            if not (read.get("pocket_center") and read.get("plate_front")):
                skipped.append(f"{reader}: no pocket/plate reading on the chosen frame")
                continue
            (x, z), diag = pixel_to_feet(read["plate_front"], read["pocket_center"], matrix)
            (_, z_raw), _ = pixel_to_feet(read["plate_front"], read["pocket_center"])
            chosen_frame = next(
                (f for f in read.get("frames", []) if f.get("offset") == read["chosen_offset"]),
                {},
            )
            reads[reader] = {
                "offset": read["chosen_offset"],
                "ball_visible": chosen_frame.get("ball_center") is not None,
                "pocket_px": read["pocket_center"],
                "plate_front_px": read["plate_front"],
                "plate_front_reason": read.get("plate_front_reason"),
                "px_per_foot": diag["front_edge_px"] / PLATE_WIDTH_FEET,
                "plate_x_feet": round(x, 4),
                "plate_z_feet": round(z, 4),
                "plate_z_feet_uncorrected": round(z_raw, 4),
                "uncertainty_pixels": read.get("uncertainty_pixels"),
            }
        base = {
            "at_bat_number": pitch["at_bat_number"],
            "pitch_number": pitch["pitch_number"],
            "call": pitch.get("call"),
            "pitch_type": pitch.get("pitch_type"),
        }
        if not reads or skipped:
            # consensus rule: a pitch is used only when every reader who looked at it found a
            # first ball-in-mitt frame; one reader seeing a bounce/block or no catch excludes it
            per_pitch.append({**base, "used": False, "reason": "; ".join(skipped) or "no reading"})
            continue
        used += 1
        mean_x = _mean([r["plate_x_feet"] for r in reads.values()])
        mean_z = _mean([r["plate_z_feet"] for r in reads.values()])
        mean_z_raw = _mean([r["plate_z_feet_uncorrected"] for r in reads.values()])
        errors = {
            depth: {
                "dx_feet": round(mean_x - pitch["statcast_at_depth_y"][depth]["x"], 4),
                "dz_feet": round(mean_z - pitch["statcast_at_depth_y"][depth]["z"], 4),
                "dz_feet_uncorrected": round(
                    mean_z_raw - pitch["statcast_at_depth_y"][depth]["z"], 4
                ),
            }
            for depth in DEPTHS
        }
        agreement = None
        if len(reads) > 1:
            xs = [r["plate_x_feet"] for r in reads.values()]
            zs = [r["plate_z_feet"] for r in reads.values()]
            agreement = {
                "same_frame": len({r["offset"] for r in reads.values()}) == 1,
                "offsets": sorted({r["offset"] for r in reads.values()}),
                "dx_feet": round(max(xs) - min(xs), 4),
                "dz_feet": round(max(zs) - min(zs), 4),
            }
        per_pitch.append(
            {
                **base,
                "used": True,
                "ball_visible_all_readers": all(r["ball_visible"] for r in reads.values()),
                "readers": reads,
                "skipped_readers": skipped,
                "reader_agreement": agreement,
                "mean_plate_feet": {
                    "x": round(mean_x, 4),
                    "z": round(mean_z, 4),
                    "z_uncorrected": round(mean_z_raw, 4),
                },
                "statcast_front": pitch["statcast_front"],
                "statcast_at_depth_y": pitch["statcast_at_depth_y"],
                "error_vs_depth": errors,
            }
        )
    usable = [p for p in per_pitch if p["used"]]
    agreed = [p for p in usable if p["reader_agreement"]]
    summary = {
        "pitches_sampled": len(catch_pitches),
        "pitches_used": used,
        "pitches_skipped": [
            {
                "at_bat_number": p["at_bat_number"],
                "pitch_number": p["pitch_number"],
                "reason": p["reason"],
            }
            for p in per_pitch
            if not p["used"]
        ],
        "chosen_offset_seconds": {
            "definition": "offset of the first ball-in-mitt frame relative to release_seconds + "
            "plateTime (the catch-time residual of the manual release annotation)",
            "values": sorted(r["offset"] for p in usable for r in p["readers"].values()),
            "mean": _mean([r["offset"] for p in usable for r in p["readers"].values()]),
        },
        "reader_disagreement_feet": {
            "dx_sd": _sd([p["reader_agreement"]["dx_feet"] for p in agreed]),
            "dz_sd": _sd([p["reader_agreement"]["dz_feet"] for p in agreed]),
            "same_frame_fraction": _mean(
                [1.0 if p["reader_agreement"]["same_frame"] else 0.0 for p in agreed]
            ),
        },
        "by_depth_y": {},
    }
    for depth in DEPTHS:
        dx = [p["error_vs_depth"][depth]["dx_feet"] for p in usable]
        dz = [p["error_vs_depth"][depth]["dz_feet"] for p in usable]
        dz_raw = [p["error_vs_depth"][depth]["dz_feet_uncorrected"] for p in usable]
        ref_x = [p["statcast_at_depth_y"][depth]["x"] for p in usable]
        ref_z = [p["statcast_at_depth_y"][depth]["z"] for p in usable]
        map_x = [p["mean_plate_feet"]["x"] for p in usable]
        map_z = [p["mean_plate_feet"]["z"] for p in usable]
        visible = [p for p in usable if p["ball_visible_all_readers"]]
        hidden = [p for p in usable if not p["ball_visible_all_readers"]]
        summary["by_depth_y"][depth] = {
            "x": _axis_stats(dx),
            "z": _axis_stats(dz),
            "x_by_ball_visibility": {
                "ball_read_directly": _axis_stats(
                    [p["error_vs_depth"][depth]["dx_feet"] for p in visible]
                ),
                "pocket_inferred_by_a_reader": _axis_stats(
                    [p["error_vs_depth"][depth]["dx_feet"] for p in hidden]
                ),
            },
            "z_by_ball_visibility": {
                "ball_read_directly": _axis_stats(
                    [p["error_vs_depth"][depth]["dz_feet"] for p in visible]
                ),
                "pocket_inferred_by_a_reader": _axis_stats(
                    [p["error_vs_depth"][depth]["dz_feet"] for p in hidden]
                ),
            },
            "z_uncorrected_diagnostic": _axis_stats(dz_raw),
            "rms_2d_feet": _rms([math.hypot(a, b) for a, b in zip(dx, dz, strict=True)]),
            "regression_mapped_on_reference": {
                "x": _regression(ref_x, map_x),
                "z": _regression(ref_z, map_z),
            },
        }
    summary["per_pitch"] = per_pitch
    return summary


def human_verified_check(per_pitch, game_pk, verified_ids):
    """End-to-end error at y = -1.0 ft restricted to the pitches a person confirmed."""
    wanted = set(verified_ids)
    rows = [
        p
        for p in per_pitch
        if p["used"] and f"{game_pk}:{p['at_bat_number']}:{p['pitch_number']}" in wanted
    ]
    if not rows:
        return None
    dx = [p["error_vs_depth"]["-1.0"]["dx_feet"] for p in rows]
    dz = [p["error_vs_depth"]["-1.0"]["dz_feet"] for p in rows]
    return {
        "n": len(rows),
        "depth_y": "-1.0",
        "x": _axis_stats(dx),
        "z": _axis_stats(dz),
        "rms_2d_feet": _rms([math.hypot(a, b) for a, b in zip(dx, dz, strict=True)]),
    }


def load_verification(path):
    """Read a person's confirmation file: a JSON list of pitch ids, or an object with pitch_ids."""
    doc = _load(path)
    if isinstance(doc, list):
        return [str(p) for p in doc], None
    if not isinstance(doc, dict) or not isinstance(doc.get("pitch_ids"), list):
        raise ValueError("human verification file needs a list or an object with pitch_ids")
    meta = {k: v for k, v in doc.items() if k != "pitch_ids"}
    return [str(p) for p in doc["pitch_ids"]], meta


def build(readings, human_verified_ids, verification_meta=None):
    frames = readings["decision_frames"]
    pitches = readings["catch_pitches"]
    noise = front_edge_noise(frames)
    camera = camera_estimates(readings)
    tilt_sin = camera["tilt"]["sin_mean"] or 0.0
    pan = pan_from_rubber(readings.get("rubber_frames", []))
    pan_tan = pan["pan_tan"] or 0.0
    depth = NOMINAL_MITT_DEPTH_FEET if (tilt_sin or pan_tan) else 0.0
    matrix = zone_to_feet_matrix(tilt_sin, depth, pan_tan)
    lateral = lateral_check(frames)
    overlay = overlay_check(frames)
    e2e = end_to_end_check(pitches, matrix)
    main = e2e["by_depth_y"]["-1.0"]
    used_ids = {
        f"{readings['game_pk']}:{p['at_bat_number']}:{p['pitch_number']}"
        for p in e2e["per_pitch"]
        if p["used"]
    }
    verified = sorted(pid for pid in human_verified_ids if pid in used_ids)
    human = human_verified_check(e2e["per_pitch"], readings["game_pk"], verified)
    if human is not None and human["n"] >= MIN_PITCHES:
        rms, rms_basis = human["rms_2d_feet"], "human_verified_subset"
    elif main["x"]["n"] >= MIN_PITCHES:
        rms, rms_basis = main["rms_2d_feet"], "all_used_pitches_assistant_read"
    else:
        rms, rms_basis = None, None
    camera_summary = {k: v for k, v in camera.items() if k != "tilt"}
    camera_summary["tilt"] = {k: v for k, v in camera["tilt"].items() if k != "rows"}
    return {
        "schema": CALIBRATION_SCHEMA,
        "game_pk": readings["game_pk"],
        "readings_sha256": readings.get("readings_sha256"),
        "hop2": {
            "method": METHOD,
            "version": VERSION,
            "matrix": [list(r) for r in matrix],
            "tilt_sin": tilt_sin,
            "pan_tan": pan_tan,
            "pan_estimate": {k: v for k, v in pan.items() if k != "rows"},
            "mitt_depth_feet": depth,
            "x_convention": X_CONVENTION,
            "source": "tilt = mean sin(tilt) from the batter's-box 6-ft depth readings; pan = mean "
            "from rubber readings (0 when none were read); nominal mitt depth 2.5 ft behind the "
            "plate front (assumed, not measured)"
            if (tilt_sin or pan_tan)
            else "no tilt or pan reading: uncorrected matrix",
        },
        "hop1_front_edge_rms_pixels": noise["rms_pixels"],
        "hop1_front_edge_noise": noise,
        "camera": camera_summary,
        "lateral_check": {k: v for k, v in lateral.items() if k != "rows"},
        "overlay_check": {k: v for k, v in overlay.items() if k != "rows"},
        "end_to_end_check": {k: v for k, v in e2e.items() if k != "per_pitch"},
        "human_verified_check": human,
        "rms_error_feet": rms,
        "rms_basis": rms_basis,
        "error_status": "measured" if rms is not None else "unmeasured",
        "error_definition": "2-D rms over called pitches of (hops 1-2 with the calibrated matrix "
        "applied to the ball/pocket on the first frame with the ball in the mitt, A/B reader "
        "mean) minus (Statcast trajectory at y = -1.0 ft, i.e. 2.4 ft behind the plate front); "
        "computed on the human-verified pitches when at least min_pitches were confirmed, "
        "otherwise on all used pitches; the parallax term is removed for the nominal 2.5 ft "
        "depth, so a residual mean offset reflects the true catch depth differing from that "
        "assumption plus reader noise; pixel readings are assistant visual estimates (a person "
        "confirmed them on a montage, not re-marked them); development game",
        "measured_on": (
            f"{human['n']} human-verified called pitches of game {readings['game_pk']} (in-sample)"
            if rms_basis == "human_verified_subset"
            else f"{main['x']['n']} called pitches of game {readings['game_pk']} (in-sample)"
        ),
        "min_pitches": MIN_PITCHES,
        "human_verified_count": len(verified),
        "human_verified_pitch_ids": verified,
        "human_verification": verification_meta,
        "per_item": {
            "tilt_rows": camera["tilt"]["rows"],
            "pan_rows": pan["rows"],
            "lateral_rows": lateral["rows"],
            "overlay_rows": overlay["rows"],
            "end_to_end_per_pitch": e2e["per_pitch"],
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--game", type=int, required=True)
    parser.add_argument("--readings", type=Path, default=None)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--human-verified",
        type=Path,
        default=None,
        help="pitch ids a person confirmed: a JSON list or an object with pitch_ids "
        "(default docs/results/mlb_p0/game_<game>_intent_human_verified_v0.json when present)",
    )
    args = parser.parse_args(argv)
    readings = _load(
        args.readings or RESULTS / f"game_{args.game}_intent_calibration_readings_v0.json"
    )
    if readings.get("schema") != READINGS_SCHEMA or readings.get("game_pk") != args.game:
        parser.error("readings file schema/game mismatch")
    verification_path = (
        args.human_verified or RESULTS / f"game_{args.game}_intent_human_verified_v0.json"
    )
    verified, meta = (
        load_verification(verification_path) if verification_path.is_file() else ([], None)
    )
    doc = build(readings, verified, meta)
    out = args.out or RESULTS / f"game_{args.game}_intent_plate_calibration_v0.json"
    out.write_text(
        json.dumps(doc, ensure_ascii=False, indent=1, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(
        json.dumps({k: v for k, v in doc.items() if k != "per_item"}, ensure_ascii=False, indent=1)
    )


if __name__ == "__main__":
    main()

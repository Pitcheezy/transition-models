"""intent.calibrate: synthetic readings with a known camera reproduce the matrix and ~zero error."""

import json
import math
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intent.calibrate import BOX_DEPTH_FEET, MIN_PITCHES, build, main  # noqa: E402
from intent.geometry import front_edge_similarity  # noqa: E402
from intent.plate_feet import (  # noqa: E402
    NOMINAL_MITT_DEPTH_FEET,
    PLATE_WIDTH_FEET,
    load_calibration,
    zone_to_feet_matrix,
)

TILT_SIN = 0.15
PLATE_FRONT = {"left_end": [636.0, 322.0], "right_end": [690.0, 322.0]}
PX_PER_FT = 54.0 / PLATE_WIDTH_FEET


def _pixel_for_feet(x_ft, z_ft, matrix):
    """Invert hops 1-2 for the synthetic plate front edge."""
    h, _ = front_edge_similarity(
        {"front_left": PLATE_FRONT["left_end"], "front_right": PLATE_FRONT["right_end"]}
    )
    uv = np.linalg.solve(np.asarray(matrix, dtype=float), np.array([x_ft, z_ft, 1.0]))
    px = np.linalg.solve(h, np.array([uv[0] / uv[2], uv[1] / uv[2], 1.0]))
    return [float(px[0] / px[2]), float(px[1] / px[2])]


def _readings(n_pitches, jitter=0.0):
    matrix = zone_to_feet_matrix(TILT_SIN, NOMINAL_MITT_DEPTH_FEET)
    decision = []
    for i in range(2):
        chalk = {
            name: _pixel_for_feet(known, 0.0, matrix)[0]
            for name, known in (
                ("left_inner_x", 14.5 / 12),
                ("right_inner_x", -14.5 / 12),
                ("left_outer_x", 62.5 / 12),
                ("right_outer_x", -62.5 / 12),
            )
        }
        read = {
            "kzone_visibility": "full",
            "kzone": {
                "top_left": [636, 190],
                "top_right": [690, 190],
                "bottom_right": [690, 270],
                "bottom_left": [636, 270],
            },
            "kzone_reason": None,
            "plate_front": PLATE_FRONT,
            "plate_front_reason": None,
            "chalk": chalk,
            "chalk_reason": None,
            "uncertainty_pixels": 2,
            "note": "",
        }
        other = json.loads(json.dumps(read))
        other["plate_front"] = {"left_end": [637.0, 322.0], "right_end": [691.0, 323.0]}
        decision.append(
            {
                "at_bat_number": i + 1,
                "pitch_number": 1,
                "sz_top": 3.4,
                "sz_bot": 1.6,
                "readers": {"A": read, "B": other},
            }
        )
    depth_px = BOX_DEPTH_FEET * PX_PER_FT * TILT_SIN
    box = {
        "at_bat_number": 1,
        "pitch_number": 1,
        "plate_front_width_px": 54.0,
        "readers": {
            "A": {
                "left_box": {
                    "x_used": 560,
                    "front_y": 330.0,
                    "back_y": 330.0 - depth_px,
                    "inner_x_at_front": 590,
                    "inner_x_at_back": 592,
                },
                "right_box": {
                    "x_used": 760,
                    "front_y": 331.0,
                    "back_y": 331.0 - depth_px,
                    "inner_x_at_front": 740,
                    "inner_x_at_back": 738,
                },
                "plate_front_y": 322,
                "uncertainty_pixels": 2,
                "note": "",
            }
        },
    }
    pitches = []
    rng = np.random.default_rng(0)
    for i in range(n_pitches):
        x_ft, z_ft = float(rng.uniform(-1.0, 1.0)), float(rng.uniform(1.2, 3.6))
        pocket = _pixel_for_feet(x_ft, z_ft, matrix)
        pocket = [
            pocket[0] + jitter * rng.standard_normal(),
            pocket[1] + jitter * rng.standard_normal(),
        ]
        ref = {
            "-0.5": {"x": x_ft, "z": z_ft + 0.05},
            "-1.0": {"x": x_ft, "z": z_ft},
            "-1.5": {"x": x_ft, "z": z_ft - 0.05},
        }
        read = {
            "chosen_offset": 0.0,
            "chosen_reason": "",
            "pocket_center": pocket,
            "plate_front": PLATE_FRONT,
            "plate_front_reason": None,
            "chalk_inner_left_x": None,
            "chalk_inner_right_x": None,
            "uncertainty_pixels": 3,
            "note": "",
            "frames": [],
        }
        pitches.append(
            {
                "at_bat_number": 10 + i,
                "pitch_number": 1,
                "call": "Called Strike",
                "pitch_type": "FF",
                "statcast_front": {"pX": x_ft, "pZ": z_ft + 0.3},
                "statcast_at_depth_y": ref,
                "readers": {"A": read, "B": json.loads(json.dumps(read))},
            }
        )
    return {
        "schema": "intent_calibration_readings_v0",
        "game_pk": 747139,
        "readings_sha256": "0" * 64,
        "decision_frames": decision,
        "catch_pitches": pitches,
        "box_frames": [box],
        "pan_from_plate_quads": {"degrees": 0.3},
    }


def test_synthetic_readings_recover_the_tilt_matrix_and_near_zero_error(tmp_path):
    doc = build(_readings(MIN_PITCHES + 2), ["747139:10:1", "747139:99:1"])
    assert doc["camera"]["tilt"]["sin_mean"] == pytest.approx(TILT_SIN)
    assert doc["hop2"]["tilt_sin"] == pytest.approx(TILT_SIN)
    assert doc["hop2"]["mitt_depth_feet"] == NOMINAL_MITT_DEPTH_FEET
    assert np.allclose(
        doc["hop2"]["matrix"], np.asarray(zone_to_feet_matrix(TILT_SIN, NOMINAL_MITT_DEPTH_FEET))
    )
    main_depth = doc["end_to_end_check"]["by_depth_y"]["-1.0"]
    assert main_depth["x"]["n"] == MIN_PITCHES + 2
    # per-pitch feet are stored rounded to 4 decimals, hence the 1e-3 tolerances
    assert (
        abs(main_depth["x"]["mean_signed_feet"]) < 1e-3
        and abs(main_depth["z"]["mean_signed_feet"]) < 1e-3
    )
    assert doc["rms_error_feet"] == pytest.approx(0.0, abs=1e-3)
    assert doc["error_status"] == "measured"
    # the uncorrected diagnostic shows the parallax term that the matrix removed, less the
    # small 1/cos(tilt) scale term (~0.03 ft at these heights)
    expected_parallax = NOMINAL_MITT_DEPTH_FEET * TILT_SIN / math.sqrt(1 - TILT_SIN**2)
    assert main_depth["z_uncorrected_diagnostic"]["mean_signed_feet"] == pytest.approx(
        expected_parallax, abs=0.05
    )
    assert main_depth["regression_mapped_on_reference"]["z"]["slope"] == pytest.approx(
        1.0, abs=1e-3
    )
    # reader B's front edge is perturbed by a pixel, so its chalk mapping is not exact
    assert doc["lateral_check"]["all"]["rms_feet"] < 0.05
    assert doc["hop1_front_edge_rms_pixels"] == pytest.approx(
        math.sqrt(3 / 4) / math.sqrt(2) * math.sqrt(2) / 1, abs=0.5
    )
    assert doc["human_verified_count"] == 1 and doc["human_verified_pitch_ids"] == ["747139:10:1"]
    assert doc["overlay_check"]["n"] == 4
    path = tmp_path / "cal.json"
    path.write_text(json.dumps(doc), encoding="utf-8")
    assert load_calibration(path)["hop2"]["tilt_sin"] == pytest.approx(TILT_SIN)


def test_too_few_catch_pitches_leave_the_error_unmeasured():
    doc = build(_readings(MIN_PITCHES - 1), [])
    assert doc["rms_error_feet"] is None and doc["error_status"] == "unmeasured"
    assert doc["end_to_end_check"]["pitches_used"] == MIN_PITCHES - 1


def test_jittered_readings_give_a_positive_rms_and_the_cli_writes_the_file(tmp_path):
    readings = _readings(MIN_PITCHES + 5, jitter=4.0)
    src = tmp_path / "readings.json"
    src.write_text(json.dumps(readings), encoding="utf-8")
    out = tmp_path / "cal.json"
    main(["--game", "747139", "--readings", str(src), "--out", str(out)])
    doc = json.loads(out.read_text(encoding="utf-8"))
    assert 0.0 < doc["rms_error_feet"] < 0.5
    assert doc["end_to_end_check"]["by_depth_y"]["-1.0"]["z"]["se_of_mean_feet"] > 0
    assert "per_item" in doc and len(doc["per_item"]["end_to_end_per_pitch"]) == MIN_PITCHES + 5


def test_headline_error_uses_the_human_verified_subset_once_it_reaches_the_minimum(tmp_path):
    readings = _readings(MIN_PITCHES + 4, jitter=4.0)
    ids = [f"747139:{10 + i}:1" for i in range(MIN_PITCHES)]
    doc = build(readings, ids, {"verified_by": "test"})
    assert doc["rms_basis"] == "human_verified_subset"
    assert doc["human_verified_check"]["n"] == MIN_PITCHES
    assert doc["rms_error_feet"] == pytest.approx(doc["human_verified_check"]["rms_2d_feet"])
    assert doc["human_verification"] == {"verified_by": "test"}
    few = build(readings, ids[: MIN_PITCHES - 1])
    assert few["rms_basis"] == "all_used_pitches_assistant_read"
    assert few["rms_error_feet"] == pytest.approx(
        few["end_to_end_check"]["by_depth_y"]["-1.0"]["rms_2d_feet"]
    )
    # the CLI reads an object with pitch_ids and keeps its metadata
    src = tmp_path / "readings.json"
    src.write_text(json.dumps(readings), encoding="utf-8")
    ver = tmp_path / "verified.json"
    ver.write_text(
        json.dumps({"pitch_ids": ids, "verified_by": "owner", "excluded": []}), encoding="utf-8"
    )
    out = tmp_path / "cal.json"
    main(
        [
            "--game",
            "747139",
            "--readings",
            str(src),
            "--out",
            str(out),
            "--human-verified",
            str(ver),
        ]
    )
    saved = json.loads(out.read_text(encoding="utf-8"))
    assert saved["human_verified_count"] == MIN_PITCHES
    assert saved["human_verification"]["verified_by"] == "owner"

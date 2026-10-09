"""M2: hop 1 v1 (front-edge similarity) and hop 2 (plate feet) of the intent chain."""

import copy
import json
import sys
from pathlib import Path

import numpy as np
import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intent.geometry import front_edge_similarity, inside_unit_square, project_point  # noqa: E402
from intent.plate_feet import (  # noqa: E402
    PLATE_WIDTH_FEET,
    UNCORRECTED_MATRIX,
    feet_transform_step,
    load_calibration,
    zone_to_feet_matrix,
    zone_to_plate_feet,
)
from intent.run import ROOT, build_records  # noqa: E402
from intent.run import main as run_main
from intent.schema import IntentEstimateError, make_estimate, validate_intent_estimate  # noqa: E402


@pytest.mark.parametrize("status", ["annotated", "unavailable"])
@pytest.mark.parametrize("verify_frames", [False, True])
def test_duplicate_timing_rejected_before_camera_or_frame_access(
    tmp_path, monkeypatch, status, verify_frames
):
    timing, points = _timing_and_points(tmp_path)
    duplicate = dict(timing["annotations"][0], status=status)
    if status == "unavailable":
        duplicate["decision_seconds"] = None
    timing["annotations"].append(duplicate)
    before = copy.deepcopy((timing, points))
    monkeypatch.setattr("intent.run.camera_constants", lambda _: pytest.fail("camera was reached"))
    with pytest.raises(ValueError, match="duplicate timing annotation"):
        build_records(747139, timing, points, verify_frames=verify_frames, frames_root=tmp_path)
    assert (timing, points) == before


@pytest.mark.parametrize(
    ("source", "value"),
    [
        ("point", float("nan")),
        ("unavailable_point", float("nan")),
        ("point", float("inf")),
        ("point", float("-inf")),
        ("point", -1e-7),
        ("point", True),
        ("point", "1"),
        ("point", None),
        ("decision", float("nan")),
        ("decision", False),
        ("decision", "1"),
    ],
)
def test_invalid_source_seconds_rejected_before_camera(tmp_path, monkeypatch, source, value):
    timing, points = _timing_and_points(tmp_path)
    timing["annotations"][0]["decision_seconds"] = 0
    points["frames"][0]["frame_seconds"] = 0
    if source == "decision":
        timing["annotations"][0]["decision_seconds"] = value
        field = "decision_seconds"
    else:
        points["frames"][0]["frame_seconds"] = value
        if source == "unavailable_point":
            points["frames"][0].update(status="unavailable", unavailable_reason="synthetic")
        field = "frame_seconds"
    monkeypatch.setattr("intent.run.camera_constants", lambda _: pytest.fail("camera was reached"))
    with pytest.raises(ValueError, match=field):
        build_records(747139, timing, points)


def test_unmatched_point_seconds_are_checked_before_camera_pooling(tmp_path, monkeypatch):
    timing, points = _timing_and_points(tmp_path)
    unused = dict(points["frames"][0], pitch_number=99, frame_seconds=float("nan"))
    points["frames"].append(unused)
    monkeypatch.setattr("intent.run.camera_constants", lambda _: pytest.fail("camera was reached"))
    with pytest.raises(ValueError, match="frame_seconds"):
        build_records(747139, timing, points)


def test_unique_unavailable_timing_and_zero_seconds_remain_supported(tmp_path):
    timing, points = _timing_and_points(tmp_path)
    timing["annotations"][0]["decision_seconds"] = 0
    points["frames"][0]["frame_seconds"] = 0
    expected = build_records(747139, timing, points, frames_root=tmp_path, verify_frames=True)
    timing["annotations"].append(
        {"at_bat_number": 1, "pitch_number": 3, "status": "unavailable", "decision_seconds": None}
    )
    timing["annotations"].reverse()
    points["frames"].reverse()
    assert (
        build_records(747139, timing, points, frames_root=tmp_path, verify_frames=True) == expected
    )
    assert expected[0][0]["evidence"] == {"frame_index": 0, "frame_time": 0.0}


@pytest.mark.parametrize("problem", ["duplicate", "nan"])
@pytest.mark.parametrize("existing_output", [False, True])
def test_cli_bad_frame_binding_preserves_output_and_receipt(tmp_path, problem, existing_output):
    timing, points = _timing_and_points(tmp_path)
    # A distinct synthetic game avoids the repository's default saved calibration.
    timing["game_pk"] = points["game_pk"] = 123456
    if problem == "duplicate":
        timing["annotations"].append(dict(timing["annotations"][0]))
    else:
        points["frames"][0]["frame_seconds"] = float("nan")
    timing_path, points_path = tmp_path / "timing.json", tmp_path / "points.json"
    timing_path.write_text(json.dumps(timing), encoding="utf-8")
    points_path.write_text(json.dumps(points), encoding="utf-8")
    out, receipt = tmp_path / "result.jsonl", tmp_path / "result.jsonl.run.json"
    original = b"existing result must survive\n"
    if existing_output:
        out.write_bytes(original)
        receipt.write_bytes(original)
    with pytest.raises(ValueError, match="duplicate timing annotation|frame_seconds"):
        run_main(
            [
                "--game",
                "123456",
                "--timing",
                str(timing_path),
                "--points",
                str(points_path),
                "--out",
                str(out),
                "--frames-root",
                str(tmp_path),
                "--verify-frames",
            ]
        )
    for path in (out, receipt):
        if existing_output:
            assert path.read_bytes() == original
        else:
            assert not path.exists()


CORNERS = {
    "front_left": [636.0, 322.0],
    "front_right": [690.0, 322.0],
    "back_right": [687.0, 318.0],
    "back_left": [640.0, 318.0],
}
METHOD = {"kind": "assistant_visual_estimate", "version": "v0"}


def test_front_edge_similarity_maps_the_edge_to_the_unit_interval_and_up_to_positive_v():
    h, diag = front_edge_similarity(CORNERS)
    assert project_point(h, CORNERS["front_left"]) == pytest.approx((0.0, 0.0))
    assert project_point(h, CORNERS["front_right"]) == pytest.approx((1.0, 0.0))
    # a point 54 px above the front-edge midpoint is one plate width up, centred
    assert project_point(h, (663.0, 322.0 - 54.0)) == pytest.approx((0.5, 1.0))
    assert diag["front_edge_px"] == pytest.approx(54.0)
    assert diag["plate_depth_px"] == pytest.approx(4.0)
    assert diag["tilt_sin_estimate"] == pytest.approx(2 * 4.0 / 54.0)
    assert diag["back_edge_lateral_shift_px"] == pytest.approx(0.5)
    assert inside_unit_square(project_point(h, (650.0, 300.0)))
    assert not inside_unit_square(project_point(h, (650.0, 240.0)))


def test_front_edge_similarity_handles_a_rolled_edge_and_rejects_zero_length():
    rolled = {"front_left": [0.0, 10.0], "front_right": [30.0, 20.0]}
    h, diag = front_edge_similarity(rolled)
    assert project_point(h, rolled["front_right"]) == pytest.approx((1.0, 0.0))
    # the normal must point up in the image (negative y): a point above the midpoint has v > 0
    mid = (15.0, 15.0)
    normal_up = (mid[0] + 10.0 / np.hypot(30, 10) * 1, mid[1] - 30.0 / np.hypot(30, 10) * 1)
    _, v = project_point(h, normal_up)
    assert v > 0
    assert "plate_depth_px" not in diag
    with pytest.raises(ValueError):
        front_edge_similarity({"front_left": [1.0, 1.0], "front_right": [1.0, 1.0]})


def test_hop2_matrix_uses_statcast_sign_and_plate_width_scale():
    assert zone_to_plate_feet((0.5, 0.0)) == pytest.approx((0.0, 0.0))
    # image-left end of the plate (u=0) is the first-base side: positive plate_x
    assert zone_to_plate_feet((0.0, 0.0)) == pytest.approx((PLATE_WIDTH_FEET / 2, 0.0))
    assert zone_to_plate_feet((1.0, 0.0)) == pytest.approx((-PLATE_WIDTH_FEET / 2, 0.0))
    assert zone_to_plate_feet((0.5, 2.0)) == pytest.approx((0.0, 2 * PLATE_WIDTH_FEET))
    assert np.asarray(UNCORRECTED_MATRIX).shape == (3, 3)
    assert UNCORRECTED_MATRIX[2] == (0.0, 0.0, 1.0)


def test_hop2_matrix_removes_depth_parallax_for_the_calibrated_tilt():
    tilt_sin, depth = 0.15, 2.5
    m = zone_to_feet_matrix(tilt_sin, depth)
    cos_t = np.sqrt(1 - tilt_sin**2)
    x, z = zone_to_plate_feet((0.5, 2.0), m)
    assert x == pytest.approx(0.0)
    assert z == pytest.approx(2.0 * PLATE_WIDTH_FEET / cos_t - depth * tilt_sin / cos_t)
    assert zone_to_plate_feet((0.0, 0.0), m)[0] == pytest.approx(PLATE_WIDTH_FEET / 2)
    with pytest.raises(ValueError):
        zone_to_feet_matrix(1.0, 0.0)
    with pytest.raises(ValueError):
        zone_to_feet_matrix(0.1, -1.0)


def test_similarity_accepts_a_fixed_roll_and_a_pooled_width():
    h, diag = front_edge_similarity(CORNERS, roll_radians=0.0, width_px=50.0)
    assert diag["width_used_px"] == 50.0 and diag["front_edge_px"] == pytest.approx(54.0)
    # midpoint stays at u=0.5; the ends now map to +/-27/50 around it
    assert project_point(h, (663.0, 322.0)) == pytest.approx((0.5, 0.0))
    assert project_point(h, CORNERS["front_right"]) == pytest.approx((0.5 + 27 / 50, 0.0))
    assert project_point(h, (663.0, 272.0)) == pytest.approx((0.5, 1.0))


def test_estimate_reaching_plate_feet_sets_claims_and_clears_the_blocker():
    h, diag = front_edge_similarity(CORNERS)
    uv = project_point(h, (654.0, 240.0))
    zone_step = {
        "source_frame": "image_pixels",
        "target_frame": "annotated_image_zone",
        "method": "plate_front_edge_similarity",
        "version": "v1",
        "error": None,
        "error_units": "pixels",
        "error_status": "unmeasured",
        "evidence": {},
    }
    feet_step = feet_transform_step(diag["front_edge_px"] / PLATE_WIDTH_FEET, diag, None)
    doc = make_estimate(
        "747139:1:1",
        "clip",
        "0" * 64,
        METHOD,
        75.25,
        "assistant_visual_estimate",
        (654.0, 240.0),
        15.0,
        "test",
        annotated_zone=(uv[0], uv[1], inside_unit_square(uv)),
        zone_transform=zone_step,
        plate_feet=zone_to_plate_feet(uv),
        feet_transform=feet_step,
        frame_index=4510,
    )
    assert doc["deepest_frame"] == "plate_feet" and doc["blocked_by"] == "no_batter_zone_bounds"
    assert doc["claims"]["physical_plate_coordinates"] is True
    assert doc["points"]["plate_feet"]["x_convention"] == "statcast_plate_x_catcher_view"
    assert doc["points"]["plate_feet"]["x"] == pytest.approx(-PLATE_WIDTH_FEET * (uv[0] - 0.5))
    assert set(doc["points"]["plate_feet"]) == {"x", "z", "x_convention"}
    assert doc["points"]["plate_feet"]["z"] == pytest.approx(PLATE_WIDTH_FEET * uv[1])
    assert feet_step["error_status"] == "unmeasured" and feet_step["error"] is None
    assert json.loads(json.dumps(doc)) == validate_intent_estimate(doc)
    with pytest.raises(IntentEstimateError):
        make_estimate(
            "747139:1:1",
            "clip",
            "0" * 64,
            METHOD,
            75.25,
            "assistant_visual_estimate",
            (654.0, 240.0),
            15.0,
            "test",
            plate_feet=(0.0, 2.0),
            feet_transform=feet_step,
            frame_index=4510,
        )


def _timing_and_points(tmp_path, corners=CORNERS):
    timing = {
        "game_pk": 747139,
        "annotations": [
            {
                "at_bat_number": 1,
                "pitch_number": 1,
                "status": "annotated",
                "decision_seconds": 75.25,
            },
            {
                "at_bat_number": 1,
                "pitch_number": 2,
                "status": "annotated",
                "decision_seconds": 87.5,
            },
        ],
    }
    frame = tmp_path / "f.jpg"
    frame.write_bytes(b"x")
    import hashlib

    sha = hashlib.sha256(b"x").hexdigest()
    points = {
        "schema": "intent_points_v0",
        "game_pk": 747139,
        "method": METHOD,
        "label_source": "assistant_visual_estimate",
        "video": {"fps_num": 60000, "fps_den": 1001},
        "uncertainty_basis": "test",
        "frames": [
            {
                "at_bat_number": 1,
                "pitch_number": 1,
                "frame_seconds": 75.25,
                "image_sha256": sha,
                "path": "f.jpg",
                "status": "estimated",
                "unavailable_reason": None,
                "mitt_center": [663.0, 268.0],
                "uncertainty_pixels": 10.0,
                "plate_corners": corners,
            },
            {
                "at_bat_number": 1,
                "pitch_number": 2,
                "frame_seconds": 87.5,
                "image_sha256": sha,
                "path": "f.jpg",
                "status": "estimated",
                "unavailable_reason": None,
                "mitt_center": [663.0, 268.0],
                "uncertainty_pixels": 10.0,
                "plate_corners": None,
            },
        ],
    }
    return timing, points


def test_build_records_emits_plate_feet_only_with_a_front_edge_and_marks_the_calibration(tmp_path):
    timing, points = _timing_and_points(tmp_path)
    records, counters = build_records(
        747139, timing, points, frames_root=tmp_path, verify_frames=True
    )
    assert counters["plate_feet"] == 1 and counters["zone"] == 1
    feet = records[0]["points"]["plate_feet"]
    assert feet["x"] == pytest.approx(0.0) and feet["z"] == pytest.approx(
        54 / 54 * PLATE_WIDTH_FEET
    )
    assert records[0]["transform_chain"][1]["error_status"] == "unmeasured"
    assert records[1]["deepest_frame"] == "image_pixels"
    calibration = {
        "schema": "intent_plate_calibration_v0",
        "game_pk": 747139,
        "hop2": {
            "matrix": [list(r) for r in zone_to_feet_matrix(0.15, 2.5)],
            "tilt_sin": 0.15,
            "mitt_depth_feet": 2.5,
        },
        "hop1_front_edge_rms_pixels": 1.5,
        "rms_error_feet": 0.31,
        "error_status": "measured",
        "human_verified_count": 0,
        "measured_on": "test",
        "per_item": [{"x": 1}],
    }
    path = tmp_path / "cal.json"
    path.write_text(json.dumps(calibration), encoding="utf-8")
    loaded = load_calibration(path)
    records, _ = build_records(
        747139, timing, points, frames_root=tmp_path, verify_frames=True, calibration=loaded
    )
    chain = records[0]["transform_chain"]
    assert chain[0]["error_status"] == "measured" and chain[0]["error"] == 1.5
    assert chain[1]["error_status"] == "measured" and chain[1]["error"] == 0.31
    assert "per_item" not in chain[1]["evidence"]["calibration"]
    assert chain[1]["evidence"]["camera_tilt_sin"] == 0.15
    expected_z = 1.0 * PLATE_WIDTH_FEET / np.sqrt(1 - 0.15**2) - 2.5 * 0.15 / np.sqrt(1 - 0.15**2)
    assert records[0]["points"]["plate_feet"]["z"] == pytest.approx(expected_z)
    assert load_calibration(tmp_path / "missing.json") is None
    bad = dict(
        calibration,
        hop2={
            "matrix": [[1, 0, 0], [0, 1, 0], [0, 0, 1]],
            "tilt_sin": 0.15,
            "mitt_depth_feet": 2.5,
        },
    )
    (tmp_path / "bad.json").write_text(json.dumps(bad), encoding="utf-8")
    with pytest.raises(ValueError):
        load_calibration(tmp_path / "bad.json")


@pytest.mark.parametrize("bad_timing", [None, [], {}, {"game_pk": 849845}])
def test_build_records_rejects_missing_or_other_game_timing(tmp_path, bad_timing):
    _, points = _timing_and_points(tmp_path)
    with pytest.raises(ValueError, match="timing file game mismatch"):
        build_records(747139, bad_timing, points)


@pytest.mark.parametrize(
    "bad_calibration",
    [
        [],
        {},
        {"schema": "intent_plate_calibration_v0"},
        {"game_pk": 747139},
        {"schema": "other", "game_pk": 747139},
        {"schema": "intent_plate_calibration_v0", "game_pk": 849845},
    ],
)
def test_build_records_rejects_calibration_identity_before_transform(tmp_path, bad_calibration):
    timing, points = _timing_and_points(tmp_path)
    with pytest.raises(ValueError, match="calibration file schema/game mismatch"):
        build_records(747139, timing, points, calibration=bad_calibration)


@pytest.mark.parametrize("existing_output", [False, True])
def test_cli_wrong_game_calibration_never_writes_output(tmp_path, existing_output):
    timing, points = _timing_and_points(tmp_path)
    calibration = {
        "schema": "intent_plate_calibration_v0",
        "game_pk": 849845,
        "hop2": {
            "matrix": [list(row) for row in zone_to_feet_matrix(0.15, 2.5)],
            "tilt_sin": 0.15,
            "mitt_depth_feet": 2.5,
        },
    }
    for name, document in (("timing", timing), ("points", points), ("calibration", calibration)):
        (tmp_path / f"{name}.json").write_text(json.dumps(document), encoding="utf-8")
    out = tmp_path / "existing.jsonl"
    if existing_output:
        out.write_bytes(b"existing output must be preserved\n")
    with pytest.raises(ValueError, match="calibration file schema/game mismatch"):
        run_main(
            [
                "--game",
                "747139",
                "--timing",
                str(tmp_path / "timing.json"),
                "--points",
                str(tmp_path / "points.json"),
                "--calibration",
                str(tmp_path / "calibration.json"),
                "--out",
                str(out),
            ]
        )
    assert not Path(str(out) + ".run.json").exists()
    if existing_output:
        assert out.read_bytes() == b"existing output must be preserved\n"
    else:
        assert not out.exists()


@pytest.mark.parametrize("path_kind", ["missing", "directory"])
@pytest.mark.parametrize("existing_output", [False, True])
def test_cli_explicit_unreadable_calibration_preserves_outputs(
    tmp_path, path_kind, existing_output
):
    timing, points = _timing_and_points(tmp_path)
    for name, document in (("timing", timing), ("points", points)):
        (tmp_path / f"{name}.json").write_text(json.dumps(document), encoding="utf-8")
    calibration = tmp_path / "calibration.json"
    if path_kind == "directory":
        calibration.mkdir()
    out = tmp_path / "result.jsonl"
    summary = Path(str(out) + ".run.json")
    if existing_output:
        out.write_bytes(b"previous records\n")
        summary.write_bytes(b"previous summary\n")
    with pytest.raises(SystemExit) as exc:
        run_main(
            [
                "--game",
                "747139",
                "--timing",
                str(tmp_path / "timing.json"),
                "--points",
                str(tmp_path / "points.json"),
                "--calibration",
                str(calibration),
                "--out",
                str(out),
            ]
        )
    assert exc.value.code == 2
    if existing_output:
        assert out.read_bytes() == b"previous records\n"
        assert summary.read_bytes() == b"previous summary\n"
    else:
        assert not out.exists() and not summary.exists()


def test_cli_omitted_missing_calibration_keeps_uncorrected_fallback(tmp_path, monkeypatch):
    timing, points = _timing_and_points(tmp_path)
    for name, document in (("timing", timing), ("points", points)):
        (tmp_path / f"{name}.json").write_text(json.dumps(document), encoding="utf-8")
    monkeypatch.setitem(run_main.__globals__, "RESULTS", tmp_path / "missing_defaults")
    out = tmp_path / "result.jsonl"
    run_main(
        [
            "--game",
            "747139",
            "--timing",
            str(tmp_path / "timing.json"),
            "--points",
            str(tmp_path / "points.json"),
            "--out",
            str(out),
        ]
    )
    records = [json.loads(line) for line in out.read_text().splitlines()]
    for record in records:
        validate_intent_estimate(record)
    summary = json.loads(Path(str(out) + ".run.json").read_text())
    assert summary["plate_calibration"] is None
    assert summary["hop2_parameters"]["tilt_sin"] == 0.0
    assert records[0]["transform_chain"][1]["error_status"] == "unmeasured"
    assert records[1]["deepest_frame"] == "image_pixels"


def test_hop2_pan_term_shifts_x_by_depth_times_pan_and_leaves_z_alone():
    base = zone_to_feet_matrix(0.1, 2.5)
    panned = zone_to_feet_matrix(0.1, 2.5, pan_tan=-0.06)
    x0, z0 = zone_to_plate_feet((0.4, 1.7), base)
    x1, z1 = zone_to_plate_feet((0.4, 1.7), panned)
    # camera on the third-base side (pan_tan < 0): deeper points map too far toward third,
    # so the correction moves them back toward first base by depth * |pan_tan|
    assert x1 - x0 == pytest.approx(2.5 * 0.06)
    assert z1 == pytest.approx(z0)
    assert zone_to_feet_matrix(0.1, 2.5, 0.0) == base


def _assert_depth_correction_evidence(calibration):
    step = feet_transform_step(40.0, {}, calibration)
    evidence = step["evidence"]
    matrix = evidence["matrix"]
    correction = evidence["applied_depth_parallax_correction"]
    # These are the signed translations actually present in the matrix, excluding
    # the plate-centre origin shift and the independent vertical scale correction.
    assert correction["x_feet"] == pytest.approx(matrix[0][2] - PLATE_WIDTH_FEET / 2)
    assert correction["z_feet"] == pytest.approx(matrix[1][2])
    assert correction["x_formula"] == "-nominal_mitt_depth_feet * camera_pan_tan"
    assert correction["z_formula"] == (
        "-nominal_mitt_depth_feet * camera_tilt_sin / sqrt(1 - camera_tilt_sin**2)"
    )
    assert "not a measured accuracy" in correction["scope"]
    residual = evidence["uncorrected_terms"]
    assert "depth_parallax_x_feet" not in residual
    assert residual["depth_error_definition"] == "actual mitt depth minus nominal mitt depth (feet)"
    assert residual["coordinate_error_definition"] == "estimated coordinate minus true coordinate"
    # Generate the image-zone point for a mitt deeper than the nominal assumption.
    # Applying the nominal matrix must leave exactly the stated signed residual.
    tilt = evidence["camera_tilt_sin"]
    cos_t = np.sqrt(1 - tilt**2)
    pan = evidence["camera_pan_tan"]
    extra_depth = 0.75
    actual_depth = evidence["nominal_mitt_depth_feet"] + extra_depth
    true_x, true_z = 0.2, 2.0
    uv = (
        0.5 - (true_x + actual_depth * pan) / PLATE_WIDTH_FEET,
        (true_z + actual_depth * tilt / cos_t) * cos_t / PLATE_WIDTH_FEET,
    )
    estimated_x, estimated_z = zone_to_plate_feet(uv, matrix)
    assert estimated_x - true_x == pytest.approx(
        extra_depth * residual["depth_parallax_x_feet_per_foot_of_depth_error"]
    )
    assert estimated_z - true_z == pytest.approx(
        extra_depth * residual["depth_parallax_z_feet_per_foot_of_depth_error"]
    )
    assert step["method"] == "plate_front_edge_affine_with_depth_parallax"
    assert step["version"] == "v0"
    return step


@pytest.mark.parametrize(
    ("pan", "tilt", "depth"),
    [(0.06, 0.15, 2.5), (-0.06, 0.15, 2.5), (0.0, 0.15, 2.5), (0.06, 0.15, 0.0), (0.06, 0.0, 2.5)],
)
def test_depth_evidence_reports_applied_translation_and_signed_residual(pan, tilt, depth):
    calibration = {
        "hop2": {
            "matrix": [list(row) for row in zone_to_feet_matrix(tilt, depth, pan)],
            "tilt_sin": tilt,
            "pan_tan": pan,
            "mitt_depth_feet": depth,
        },
        "rms_error_feet": 0.0,
    }
    original = json.dumps(calibration, sort_keys=True)
    step = _assert_depth_correction_evidence(calibration)
    assert step["evidence"]["matrix"] == calibration["hop2"]["matrix"]
    assert step["error_status"] == "measured" and step["error"] == 0.0
    assert json.dumps(calibration, sort_keys=True) == original


def test_depth_evidence_without_calibration_has_zero_offsets_and_unmeasured_error():
    step = _assert_depth_correction_evidence(None)
    evidence = step["evidence"]
    assert evidence["applied_depth_parallax_correction"]["x_feet"] == 0.0
    assert evidence["applied_depth_parallax_correction"]["z_feet"] == 0.0
    assert evidence["matrix"] == [list(row) for row in UNCORRECTED_MATRIX]
    assert evidence["parameters_source"] == "no calibration file: uncorrected (tilt 0, depth 0)"
    assert evidence["calibration"] is None
    assert step["error_status"] == "unmeasured" and step["error"] is None


@pytest.mark.parametrize("game", [747139, 823407, 849843, 849845, 849849])
def test_depth_evidence_matches_five_saved_calibrations_and_preserves_contract(tmp_path, game):
    calibration_path = (
        ROOT / "docs/results/mlb_p0" / f"game_{game}_intent_plate_calibration_v0.json"
    )
    calibration = load_calibration(calibration_path)
    assert calibration is not None
    step = _assert_depth_correction_evidence(calibration)
    assert step["evidence"]["matrix"] == calibration["hop2"]["matrix"]
    timing, points = _timing_and_points(tmp_path)
    timing["game_pk"] = points["game_pk"] = game
    records, _ = build_records(game, timing, points, calibration=calibration)
    for record in records:
        validate_intent_estimate(record)
    assert (
        records[0]["transform_chain"][1]["evidence"]
        == feet_transform_step(
            54.0 / PLATE_WIDTH_FEET,
            {"tilt_sin_estimate": 2 * 4.0 / 54.0},
            calibration,
        )["evidence"]
    )
    assert records[0]["claims"]["accuracy_estimate"] is None
    assert records[0]["claims"]["catcher_intent_verified"] is False

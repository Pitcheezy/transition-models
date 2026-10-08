"""Identity-safe diagnostics, availability denominators and coordinate sensitivity."""

import json
import math
from copy import deepcopy

import pytest

from intent.plate_feet import PLATE_WIDTH_FEET, zone_to_feet_matrix
from intent.quality_audit import (
    availability,
    build_game,
    main,
    sensitivity,
    validate_inputs,
)
from intent.run import build_records


@pytest.fixture
def sample():
    game = 123456
    frames = []
    for pitch in range(1, 4):
        marked = pitch == 1
        frames.append(
            {
                "at_bat_number": 1,
                "pitch_number": pitch,
                "frame_seconds": float(pitch),
                "path": f"frames/{pitch}.jpg",
                "image_sha256": str(pitch) * 64,
                "status": "estimated" if marked else "unavailable",
                "unavailable_reason": None if marked else "not_in_setup",
                "mitt_center": [60.0, -100.0] if marked else None,
                "uncertainty_pixels": 2.0 if marked else None,
                "plate_corners": {"front_left": [0.0, 0.0], "front_right": [100.0, 0.0]}
                if marked
                else None,
            }
        )
    points = {
        "schema": "intent_points_v0",
        "game_pk": game,
        "frames": frames,
        "method": {"kind": "assistant_visual_estimate", "version": "v0"},
        "label_source": "assistant_visual_estimate",
        "video": {"fps_num": 30, "fps_den": 1},
    }
    manifest = {
        "schema": "intent_label_pack_v0",
        "game_pk": game,
        "pack_id": "example",
        "frames": [
            {"pitch_id": f"{game}:1:{i}", "frame_seconds": float(i), "image_sha256": str(i) * 64}
            for i in range(1, 4)
        ],
    }
    labels = {
        "schema": "intent_human_labels_v0",
        "game_pk": game,
        "pack_id": "example",
        "frames": [
            dict(
                frame,
                mitt_status="marked" if i < 3 else None,
                mitt=[60.0, -100.0] if i < 3 else None,
                plate_status=None,
                plate_front=None,
            )
            for i, frame in enumerate(manifest["frames"], 1)
        ],
    }
    calibration = {
        "schema": "intent_plate_calibration_v0",
        "game_pk": game,
        "error_status": "unmeasured",
        "rms_error_feet": None,
        "hop2": {
            "tilt_sin": 0.1,
            "pan_tan": 0.05,
            "mitt_depth_feet": 2.5,
            "matrix": zone_to_feet_matrix(0.1, 2.5, 0.05),
        },
    }
    timing = {
        "game_pk": game,
        "annotations": [
            dict(f, status="annotated", decision_seconds=f["frame_seconds"]) for f in frames
        ],
    }
    records, _ = build_records(game, timing, points, calibration=calibration)
    return dict(
        game=game,
        points=points,
        labels=labels,
        manifest=manifest,
        records=records,
        calibration=calibration,
    )


def test_id_join_is_order_independent_and_abstention_is_not_error(sample):
    sample["records"].reverse()
    sample["labels"]["frames"].reverse()
    points, labels, _ = validate_inputs(**sample)
    audit = availability(points, labels)
    assert audit["denominators"] == {
        "all_output_pitches": 3,
        "human_pack_pitches": 3,
        "human_decided": 2,
        "both_marked": 1,
    }
    assert audit["ai_abstained"] == 2 and audit["human_abstained"] == 0
    assert audit["cells"]["human_only"] == audit["cells"]["human_undecided"] == 1
    assert audit["disagreements"][0]["adjudication"] == "unknown_not_reviewed"


@pytest.mark.parametrize("field", ["points", "labels", "manifest", "records"])
def test_duplicate_ids_are_rejected_in_every_input(sample, field):
    rows = sample[field] if field == "records" else sample[field]["frames"]
    rows.append(deepcopy(rows[0]))
    with pytest.raises(ValueError, match="duplicate"):
        validate_inputs(**sample)


@pytest.mark.parametrize(
    "field,hash_key",
    [
        ("points", "image_sha256"),
        ("labels", "image_sha256"),
        ("manifest", "image_sha256"),
        ("records", "clip_sha256"),
    ],
)
def test_frame_hash_mismatches_are_rejected(sample, field, hash_key):
    rows = sample[field] if field == "records" else sample[field]["frames"]
    rows[0][hash_key] = "f" * 64
    with pytest.raises(ValueError, match="hash|frame"):
        validate_inputs(**sample)


def test_missing_and_wrong_game_pitch_ids_are_rejected(sample):
    sample["records"][0]["pitch_id"] = "123457:1:1"
    with pytest.raises(ValueError, match="pitch_id sets"):
        validate_inputs(**sample)


@pytest.mark.parametrize("field", ["points", "labels", "manifest", "records", "calibration"])
def test_nonfinite_nested_input_is_rejected(sample, field):
    value = sample[field][0] if field == "records" else sample[field]
    value["unexpected_metadata"] = {"number": float("nan")}
    with pytest.raises(ValueError, match="nonfinite"):
        validate_inputs(**sample)


def test_frame_time_and_coordinate_changes_are_rejected(sample):
    sample["labels"]["frames"][0]["frame_seconds"] += 1
    with pytest.raises(ValueError, match="frame time"):
        validate_inputs(**sample)
    sample["labels"]["frames"][0]["frame_seconds"] -= 1
    sample["points"]["frames"][0]["mitt_center"][0] += 1
    with pytest.raises(ValueError, match="mitt coordinate"):
        validate_inputs(**sample)


@pytest.mark.parametrize("field", ["points", "labels", "manifest"])
def test_timestamp_numeric_strings_cannot_hide_nonfinite_input(sample, field):
    sample[field]["frames"][0]["frame_seconds"] = "NaN"
    with pytest.raises(ValueError, match="finite number"):
        validate_inputs(**sample)


def test_x_sensitivity_matches_geometry_and_keeps_other_variables_fixed(sample):
    point, record = sample["points"]["frames"][0], sample["records"][0]
    before = deepcopy(sample)
    row = sensitivity(point, record, sample["calibration"])

    def delta(name):
        return row["changes"][name]["delta_x_ft"]

    assert row["baseline_x_ft"] == pytest.approx(-PLATE_WIDTH_FEET * 0.1 - 0.125)
    assert delta("mitt_x_+1px") == pytest.approx(-PLATE_WIDTH_FEET / 100)
    assert delta("front_midpoint_x_+1px") == pytest.approx(PLATE_WIDTH_FEET / 100)
    assert delta("mitt_y_+1px") == pytest.approx(0)
    assert delta("tilt_+1deg") == pytest.approx(0)
    assert delta("nominal_depth_+1ft") == pytest.approx(-0.05)
    expected_pan = -2.5 * (math.tan(math.atan(0.05) + math.radians(1)) - 0.05)
    assert delta("pan_+1deg") == pytest.approx(expected_pan)
    assert delta("front_width_+5percent") == pytest.approx(PLATE_WIDTH_FEET * (0.1 - 10 / 105))
    assert sample == before
    unavailable = sensitivity(sample["points"]["frames"][1], sample["records"][1], None)
    assert unavailable["baseline_x_ft"] is None and unavailable["changes"] == {}


def test_corrupt_published_transform_is_rejected(sample):
    point, record = sample["points"]["frames"][0], sample["records"][0]
    record["points"]["plate_feet"]["x"] += 0.1
    with pytest.raises(ValueError, match="cannot be reproduced"):
        sensitivity(point, record, sample["calibration"])


def test_calibration_mismatch_and_false_measured_status_are_rejected(sample):
    calibration = sample["calibration"]
    calibration["hop2"]["pan_tan"] = 0.07
    calibration["hop2"]["matrix"] = zone_to_feet_matrix(0.1, 2.5, 0.07)
    with pytest.raises(ValueError, match="disagrees with calibration"):
        sensitivity(sample["points"]["frames"][0], sample["records"][0], calibration)
    calibration["error_status"] = "measured"
    with pytest.raises(ValueError, match="measured status"):
        validate_inputs(**sample)


def _save(sample, path):
    for key, suffix in (
        ("points", "points_v0.json"),
        ("labels", "human_labels_v0.json"),
        ("manifest", "label_pack_v0.json"),
        ("calibration", "plate_calibration_v0.json"),
    ):
        (path / f"game_{sample['game']}_intent_{suffix}").write_text(
            json.dumps(sample[key]), encoding="utf-8"
        )
    (path / f"game_{sample['game']}_intent_v0.jsonl").write_text(
        "\n".join(json.dumps(r) for r in sample["records"]) + "\n", encoding="utf-8"
    )


def test_cli_writes_new_bound_report_and_refuses_overwrites(sample, tmp_path):
    _save(sample, tmp_path)
    source_bytes = {p: p.read_bytes() for p in tmp_path.iterdir()}
    out = tmp_path / "diagnostics/new_report.json"
    argv = ["--games", str(sample["game"]), "--results-dir", str(tmp_path), "--out", str(out)]
    main(argv)
    report = json.loads(out.read_text(encoding="utf-8"))
    game = report["games"][0]
    assert report["scope"] == "development_diagnostic"
    assert game["calibration"]["recorded_rms_error_feet"] is None
    assert game["sensitivity"]["eligible_pitches"] == 1
    assert len(game["sources"]) == 5
    assert all(len(s["sha256"]) == 64 for s in game["sources"].values())
    with pytest.raises(SystemExit):
        main(argv)
    with pytest.raises(SystemExit):
        main(argv[:-1] + [str(next(iter(source_bytes)))])
    assert all(p.read_bytes() == before for p, before in source_bytes.items())


def test_absent_calibration_remains_unknown_and_cannot_be_output_target(sample, tmp_path):
    _save(sample, tmp_path)
    cal_path = tmp_path / f"game_{sample['game']}_intent_plate_calibration_v0.json"
    cal_path.unlink()
    report, _ = build_game(sample["game"], tmp_path)
    assert report["calibration"]["recorded_error_status"] == "unknown_no_file"
    assert report["sensitivity"]["eligible_pitches"] == 1
    with pytest.raises(SystemExit):
        main(
            ["--games", str(sample["game"]), "--results-dir", str(tmp_path), "--out", str(cal_path)]
        )
    assert not cal_path.exists()

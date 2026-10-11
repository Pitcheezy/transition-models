"""Future evidence and missing availability must never become pre-pitch claims."""

import json
from copy import deepcopy

import pytest

from intent.schema import make_estimate
from intent.temporal_audit import (
    TRACE_SCHEMA,
    audit_game,
    prefix_camera_constants,
    sha256,
    validate_trace,
)


def trace_fixture(tmp_path):
    artifacts = []
    for index, kind in enumerate(
        ("pitch_identity", "setup_frame", "camera_calibration", "cv_output")
    ):
        path = tmp_path / f"{kind}.json"
        path.write_text(json.dumps({"pitch_id": "1:1:1"}), encoding="utf-8")
        artifacts.append(
            {
                "id": kind,
                "kind": kind,
                "path": path.name,
                "sha256": sha256(path),
                "clock_id": "video-hash:playback",
                "evidence_max_seconds": 1.0 + index,
                "available_at_seconds": 2.0 + index,
                "availability_basis": "measured",
                "depends_on": [] if index < 3 else [r["id"] for r in artifacts],
            }
        )
    record = make_estimate(
        "1:1:1",
        "test-frame",
        artifacts[1]["sha256"],
        {"kind": "assistant_visual_estimate", "version": "v0"},
        2.0,
        "assistant_visual_estimate",
        (4, 8),
        1,
        "synthetic test",
        frame_index=2,
    )
    output_path = tmp_path / artifacts[-1]["path"]
    output_path.write_text(json.dumps(record), encoding="utf-8")
    artifacts[-1]["sha256"] = sha256(output_path)
    return {
        "schema": TRACE_SCHEMA,
        "pitch_id": "1:1:1",
        "clock_id": "video-hash:playback",
        "decision_deadline_seconds": 10.0,
        "artifacts": artifacts,
    }


def test_complete_measured_trace_and_bound_files_can_pass(tmp_path):
    assert validate_trace(trace_fixture(tmp_path), tmp_path)["eligible"]


@pytest.mark.parametrize(
    "field,value",
    [
        ("evidence_max_seconds", 10),
        ("available_at_seconds", 10),
        ("evidence_max_seconds", None),
        ("available_at_seconds", None),
        ("clock_id", "different-video"),
        ("availability_basis", "estimated"),
    ],
)
def test_future_unknown_or_mixed_clock_fails_closed(tmp_path, field, value):
    trace = trace_fixture(tmp_path)
    trace["artifacts"][1][field] = value
    assert not validate_trace(trace, tmp_path)["eligible"]


def test_output_cannot_precede_dependency(tmp_path):
    trace = trace_fixture(tmp_path)
    trace["artifacts"][2]["available_at_seconds"] = 7
    result = validate_trace(trace, tmp_path)
    assert not result["eligible"]
    assert any(r["reason"] == "available_before_dependency" for r in result["reasons"])


def test_unlinked_sources_do_not_pass(tmp_path):
    trace = trace_fixture(tmp_path)
    trace["artifacts"][-1]["depends_on"] = []
    assert not validate_trace(trace, tmp_path)["eligible"]


@pytest.mark.parametrize("mutation", ["future_frame", "invalid_schema", "wrong_hash", "setup_time"])
def test_trace_cannot_disguise_output_contents(tmp_path, mutation):
    trace = trace_fixture(tmp_path)
    output_path = tmp_path / trace["artifacts"][-1]["path"]
    record = json.loads(output_path.read_text())
    if mutation == "future_frame":
        record["evidence"]["frame_time"] = 20
    elif mutation == "invalid_schema":
        record = {"pitch_id": "1:1:1"}
    elif mutation == "wrong_hash":
        record["clip_sha256"] = "f" * 64
    else:
        trace["artifacts"][1]["evidence_max_seconds"] = 1
    output_path.write_text(json.dumps(record), encoding="utf-8")
    trace["artifacts"][-1]["sha256"] = sha256(output_path)
    if mutation == "wrong_hash":
        assert not validate_trace(trace, tmp_path)["eligible"]
    else:
        with pytest.raises(ValueError):
            validate_trace(trace, tmp_path)


def test_transitive_unknown_and_cycle(tmp_path):
    trace = trace_fixture(tmp_path)
    trace["artifacts"][2]["depends_on"] = ["setup_frame"]
    trace["artifacts"][-1]["depends_on"] = ["camera_calibration", "pitch_identity"]
    trace["artifacts"][1]["available_at_seconds"] = None
    assert not validate_trace(trace, tmp_path)["eligible"]
    trace["artifacts"][1]["depends_on"] = ["cv_output"]
    with pytest.raises(ValueError, match="cyclic"):
        validate_trace(trace, tmp_path)


@pytest.mark.parametrize(
    "mutation", ["hash", "duplicate", "missing", "escape", "nan", "wrong_pitch"]
)
def test_trace_corruption_is_rejected(tmp_path, mutation):
    trace = trace_fixture(tmp_path)
    if mutation == "hash":
        (tmp_path / "setup_frame.json").write_text("modified", encoding="utf-8")
    elif mutation == "duplicate":
        trace["artifacts"].append(deepcopy(trace["artifacts"][0]))
    elif mutation == "missing":
        trace["artifacts"][-1]["depends_on"].append("missing")
    elif mutation == "escape":
        trace["artifacts"][0]["path"] = "../elsewhere.json"
    elif mutation == "nan":
        trace["artifacts"][0]["available_at_seconds"] = float("nan")
    else:
        trace["pitch_id"] = "1:2:1"
    with pytest.raises(ValueError):
        validate_trace(trace, tmp_path)


def point(pitch, at, width=10, status="estimated"):
    return {
        "at_bat_number": 1,
        "pitch_number": pitch,
        "frame_seconds": at,
        "status": status,
        "plate_corners": {"front_left": [0, 10], "front_right": [width, 10]},
        "mitt_center": [4, 8] if status == "estimated" else None,
    }


def test_prefix_is_invariant_to_future_and_preserves_abstained_edges():
    frames = [point(1, 1), point(2, 2, 12, "unavailable"), point(3, 20, 100)]
    prefix = prefix_camera_constants(frames, 2)
    assert prefix["pa_median_width_px"][1] == 11
    frames[-1]["plate_corners"]["front_right"] = [1000, 100]
    assert prefix_camera_constants(frames, 2) == prefix


def test_prefix_rejects_missing_clock_and_duplicate_pitch():
    with pytest.raises(ValueError):
        prefix_camera_constants([point(1, None)], 2)
    with pytest.raises(ValueError, match="duplicate"):
        prefix_camera_constants([point(1, 1), point(1, 2)], 2)


def legacy_fixture(tmp_path):
    frames = [point(1, 1), point(2, 20)]
    for frame in frames:
        frame["frame_index"] = int(frame["frame_seconds"])
        frame["image_sha256"] = "a" * 64
    data = {
        "intent_points_v0": {"game_pk": 1, "frames": frames, "video": {"fps_num": 1, "fps_den": 1}},
        "timing": {
            "game_pk": 1,
            "source": {"media_url": "fixture://video", "fps": "1/1"},
            "annotations": [
                {
                    "at_bat_number": 1,
                    "pitch_number": 1,
                    "release_seconds": 2,
                    "decision_seconds": 1,
                },
                {
                    "at_bat_number": 1,
                    "pitch_number": 2,
                    "release_seconds": None,
                    "decision_seconds": 20,
                },
            ],
        },
        "condensed_windows_v0": {
            "game_pk": 1,
            "media_url": "fixture://video",
            "fps": "1/1",
            "windows": [
                {
                    "pitch": "1:1",
                    "frames": [
                        {"frame_time": 1, "frame_index": 1, "image_sha256": "a" * 64},
                        {"frame_time": 3, "frame_index": 3, "image_sha256": "b" * 64},
                    ],
                },
                {
                    "pitch": "1:2",
                    "frames": [
                        {"frame_time": 20, "frame_index": 20, "image_sha256": "a" * 64},
                    ],
                },
            ],
        },
    }
    for suffix, doc in data.items():
        (tmp_path / f"game_1_{suffix}.json").write_text(json.dumps(doc), encoding="utf-8")
    return data


def test_legacy_audit_distinguishes_frame_time_window_and_availability(tmp_path):
    legacy_fixture(tmp_path)
    report = audit_game(1, tmp_path)
    first = report["rows"][0]
    assert first["frame_before_release"]
    assert first["offered_window_after_release"]
    assert not first["prepitch_eligible"]
    assert report["rows"][1]["frame_before_release"] is None
    assert report["summary"]["measured_prepitch_availability_rows"] == 0


@pytest.mark.parametrize("mutation", ["time", "url", "fps", "hash", "frame", "missing_window"])
def test_legacy_rejects_mixed_sources(tmp_path, mutation):
    data = legacy_fixture(tmp_path)
    if mutation == "time":
        data["timing"]["annotations"][0]["decision_seconds"] = 0.5
    elif mutation == "url":
        data["condensed_windows_v0"]["media_url"] = "fixture://different"
    elif mutation == "fps":
        data["intent_points_v0"]["video"]["fps_num"] = 30
    elif mutation == "hash":
        data["intent_points_v0"]["frames"][0]["image_sha256"] = "f" * 64
    elif mutation == "frame":
        data["intent_points_v0"]["frames"][0]["frame_index"] = 2
    else:
        data["condensed_windows_v0"]["windows"].pop()
    for suffix, doc in data.items():
        (tmp_path / f"game_1_{suffix}.json").write_text(json.dumps(doc), encoding="utf-8")
    with pytest.raises(ValueError):
        audit_game(1, tmp_path)

"""Offline deadline boundaries and provenance checks; no model calls."""

import copy
import hashlib
import json

import pytest

from intent import replay_pitch_deadlines as deadlines


def reference(pitch=1, decision=10, release=20, uncertainty=1):
    return {
        "pitch_id": f"747139:2:{pitch}",
        "clock_id": "source",
        "decision_seconds": decision,
        "release_seconds": release,
        "uncertainty_seconds": uncertainty,
    }


def observation(index=0, frame="12", publication="15", status="accepted"):
    return {
        "index": index,
        "clock_id": "source",
        "status": status,
        "frame_seconds_exact": frame,
        "publication_seconds_exact": publication,
        "observation_status": "unavailable",
        "candidate_status": "candidate",
    }


def evaluate(rows, refs=None):
    return deadlines.evaluate(rows, [reference()] if refs is None else refs, clock_id="source")


@pytest.mark.parametrize(
    "publication,expected",
    [
        ("18.999999999", "before_lower"),
        ("19", "overlaps_uncertainty"),
        ("20", "overlaps_uncertainty"),
        ("21", "overlaps_uncertainty"),
        ("21.000000001", "after_upper"),
    ],
)
def test_exact_release_boundaries(publication, expected):
    result = evaluate([observation(publication=publication)])
    row = result["pitches"][0]["observations"][0]
    assert row["publication_relative_to_release"] == expected
    assert row["nominal_start_temporal_ready"] == (expected == "before_lower")
    assert result["counts"]["usable_mitt_pitches"] == 0


def test_late_previous_pitch_is_not_reused_for_next():
    result = evaluate(
        [observation(frame="12", publication="32")], [reference(), reference(2, 30, 40)]
    )
    assert len(result["pitches"][0]["observations"]) == 1
    assert result["pitches"][1]["observations"] == []
    assert result["counts"]["nominal_start_temporal_ready_pitches"] == 0


def test_frame_before_decision_is_not_carried_forward():
    result = evaluate([observation(frame="9", publication="15")])
    assert result["pitches"][0]["observations"] == []
    assert len(result["unassigned_observations"]) == 1


def test_uncertain_decision_is_explicit_and_conservative_result_fails():
    result = evaluate([observation(frame="10.5", publication="15")])
    pitch = result["pitches"][0]
    assert pitch["nominal_start_temporal_ready"]
    assert not pitch["conservative_temporal_ready"]
    assert pitch["observations"][0]["input_overlaps_decision_uncertainty"]


def test_frame_in_release_uncertainty_is_not_definitely_pre_release():
    result = evaluate([observation(frame="19.5", publication="20")])
    row = result["pitches"][0]["observations"][0]
    assert row["input_overlaps_release_uncertainty"]
    assert not row["nominal_start_temporal_ready"]


def test_short_reference_retained_when_uncertainty_bands_overlap():
    result = evaluate(
        [observation(frame="10.1", publication="10.2")],
        [reference(decision=10, release=11.5, uncertainty=1)],
    )
    pitch = result["pitches"][0]
    assert pitch["status"] == "measured_reference"
    assert pitch["conservative_window_empty"]
    assert pitch["nominal_start_temporal_ready"]
    assert not pitch["conservative_temporal_ready"]
    assert result["counts"]["reference_pitches"] == 1


@pytest.mark.parametrize("field", ["decision_seconds", "release_seconds", "uncertainty_seconds"])
def test_missing_reference_bound_is_unmeasured(field):
    ref = reference()
    ref[field] = None
    result = evaluate([observation()], [ref])
    assert result["pitches"][0]["status"] == "unmeasured"
    assert result["counts"]["reference_pitches"] == 1
    assert len(result["unassigned_observations"]) == 1


def test_failures_unknown_and_unattempted_keep_denominator():
    rows = [
        observation(),
        observation(1, "13", None, "error"),
        observation(2, None, None, "not_attempted"),
    ]
    rows[0]["observation_status"] = "unknown"
    result = evaluate(rows)
    assert result["counts"]["planned_observations"] == 3
    assert result["counts"]["observation_status"] == {"accepted": 1, "error": 1, "not_attempted": 1}
    assert result["counts"]["usable_mitt_pitches"] == 0


@pytest.mark.parametrize("value", [True, float("nan"), float("inf"), "-1", "1/0"])
def test_bad_times_rejected(value):
    with pytest.raises(ValueError):
        evaluate([observation(frame=value)])


@pytest.mark.parametrize("which", ["observation", "reference"])
def test_mixed_clocks_rejected(which):
    row, ref = observation(), reference()
    (row if which == "observation" else ref)["clock_id"] = "another_source"
    with pytest.raises(ValueError, match="clock mismatch"):
        evaluate([row], [ref])


def test_duplicates_overlaps_and_unaccepted_publication_rejected():
    cases = [
        ([observation(), observation()], [reference()]),
        ([observation()], [reference(), reference()]),
        ([observation()], [reference(), reference(2, 18, 30)]),
        ([observation(status="error")], [reference()]),
        ([observation(frame="16", publication="15")], [reference()]),
    ]
    for rows, refs in cases:
        with pytest.raises(ValueError):
            evaluate(rows, refs)


def capture_documents():
    manifest = {
        "plan": {"capture_dir": "capture"},
        "input_code_bindings": [{"path": "capture/receipt.json", "sha256": "a" * 64}],
    }
    capture = {
        "schema": "intent_clip_capture_v1",
        "status": "captured",
        "source": {"kind": "url", "value": "https://example.test/video"},
        "clip": {"unchanged": True, "sha256_before": "b" * 64, "sha256_after": "b" * 64},
        "artifacts": {
            "source.framemd5": {"sha256": "c" * 64},
            "clip.framemd5": {"sha256": "d" * 64},
        },
    }
    timing = {"source": {"media_url": "https://example.test/video"}}
    return manifest, capture, timing


def test_capture_hash_and_source_binding():
    manifest, capture, timing = capture_documents()
    expected = deadlines._capture_binding(manifest, capture, "a" * 64, timing)
    assert expected["clip_media_sha256"] == "b" * 64
    with pytest.raises(ValueError, match="bound"):
        deadlines._capture_binding(manifest, capture, "e" * 64, timing)
    other = copy.deepcopy(timing)
    other["source"]["media_url"] += "-different"
    with pytest.raises(ValueError, match="same unchanged"):
        deadlines._capture_binding(manifest, capture, "a" * 64, other)


def test_new_output_required(tmp_path):
    path = tmp_path / "existing.json"
    path.write_text("original", encoding="utf-8")
    with pytest.raises(FileExistsError):
        deadlines.main(
            [
                "--run",
                "unused",
                "--timing",
                "unused",
                "--manifest",
                "unused",
                "--sources",
                "unused",
                "--capture-receipt",
                "unused",
                "--pa",
                "2",
                "--out",
                str(path),
            ]
        )
    assert path.read_text(encoding="utf-8") == "original"


def test_windows_capture_identity_does_not_require_windows_host():
    manifest, capture, timing = capture_documents()
    manifest["plan"]["capture_dir"] = "C:\\private\\capture"
    manifest["input_code_bindings"][0]["path"] = "C:\\private\\capture\\receipt.json"
    assert deadlines._capture_binding(manifest, capture, "a" * 64, timing)


@pytest.mark.parametrize("change", ["source_hash", "image_hash", "frame_time", "source_url"])
def test_frame_provenance_cannot_be_detached(tmp_path, change):
    manifest, capture, timing = capture_documents()
    expected = deadlines._capture_binding(manifest, capture, "a" * 64, timing)
    receipt = {
        "status": "extracted",
        "input_hashes": copy.deepcopy(expected),
        "source": copy.deepcopy(capture["source"]),
        "actual_source_seconds_exact": "12",
        "requested_source_seconds_exact": "13",
        "artifacts": {"image.jpg": {"sha256": "f" * 64}},
    }
    session = {"image_sha256": "f" * 64}
    attempt = {"actual_source_seconds_exact": "12", "cutoff_seconds_exact": "13"}
    if change == "source_hash":
        receipt["input_hashes"]["source_framemd5_sha256"] = "0" * 64
    elif change == "image_hash":
        receipt["artifacts"]["image.jpg"]["sha256"] = "0" * 64
    elif change == "frame_time":
        receipt["actual_source_seconds_exact"] = "14"
    else:
        receipt["source"]["value"] += "-different"
    raw = json.dumps(receipt).encode()
    session["source_receipt_sha256"] = hashlib.sha256(raw).hexdigest()
    frame_dir = tmp_path / "frames/frame_000"
    frame_dir.mkdir(parents=True)
    (frame_dir / "receipt.json").write_bytes(raw)
    output_dir = tmp_path / "outputs/cv_observation_000"
    output_dir.mkdir(parents=True)
    (output_dir / "session.json").write_text(json.dumps(session), encoding="utf-8")
    with pytest.raises(ValueError, match="binding mismatch"):
        deadlines._frame_binding(tmp_path, 0, attempt, capture, expected)

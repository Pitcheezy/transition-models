"""Input binding and honest current/history denominators for the offline replay."""

import copy
import hashlib
import json

import pytest

from intent.mitt_stationary_pilot import build, replay


def stream(pitch="g:1:1"):
    rows = [
        {
            "pitch_id": pitch,
            "frame_index": i,
            "frame_seconds": i / 10,
            "state": "tracking",
            "reason": "external_seed" if i == 0 else "patch_continuity",
            "point_px": [100, 200],
            "mitt_identity": "unverified",
        }
        for i in range(5)
    ]
    rows += [
        {
            **rows[-1],
            "frame_index": 5,
            "frame_seconds": 0.5,
            "state": "lost",
            "reason": "low_similarity",
            "point_px": None,
        }
    ]
    return rows


def save(path, value):
    raw = (json.dumps(value, indent=2) + "\n").encode()
    path.write_bytes(raw)
    return hashlib.sha256(raw).hexdigest()


def fixture_bundle(tmp_path, cuda_rows=None):
    cpu, cuda, source = [tmp_path / name for name in ("cpu.json", "cuda.json", "source.json")]
    hcpu = save(cpu, stream())
    hcuda = save(cuda, stream() if cuda_rows is None else cuda_rows)
    hsource = save(
        source,
        {
            "schema": "pitcheezy-mitt-tracking-pilot-dev-v2",
            "frames": 6,
            "pitches": 1,
            "devices": {"cpu": {"records_sha256": hcpu}, "cuda": {"records_sha256": hcuda}},
        },
    )
    return {
        "tracking_report": source,
        "report_sha256": hsource,
        "cpu": cpu,
        "cuda": cuda,
        "out": tmp_path / "new",
    }


def test_denominators_are_events_current_and_history_only():
    rows = stream() + stream("g:1:2")
    original = copy.deepcopy(rows)
    results, summary = replay(rows)
    assert rows == original
    assert len(results) == 12 and summary["pitches"] == 2
    assert summary["events"] == summary["pitches_with_event"] == 2
    assert summary["current_candidate_frames"] == 4
    assert summary["history_only_frames"] == 2
    for p in summary["pitch_summaries"]:
        assert not p["final_current_candidate_present"] and p["final_history_present"]
        assert p["final_tracker_state"] == "lost"
        interval = p["current_intervals"][0]
        assert interval["first_seconds"] == 0.3
        assert interval["last_seconds"] == 0.4
        assert interval["observed_span_seconds"] == pytest.approx(0.1)


def test_report_binds_input_bytes_and_does_not_modify_them(tmp_path):
    args = fixture_bundle(tmp_path)
    before = {k: args[k].read_bytes() for k in ("cpu", "cuda", "tracking_report")}
    report = build(**args)
    assert report["input_unchanged"] and report["cpu_cuda_selection_equal"]
    assert before == {k: args[k].read_bytes() for k in before}
    for device in ("cpu", "cuda"):
        path = args["out"] / f"records_{device}.json"
        assert (
            hashlib.sha256(path.read_bytes()).hexdigest()
            == report["devices"][device]["output_sha256"]
        )
    assert len(report["source_files_sha256"]) == 2
    assert json.loads((args["out"] / "report.json").read_text()) == report
    with pytest.raises(FileExistsError):
        build(**args)


@pytest.mark.parametrize("which", ["cpu", "cuda", "tracking_report"])
def test_byte_change_rejected_before_output(tmp_path, which):
    args = fixture_bundle(tmp_path)
    args[which].write_bytes(args[which].read_bytes() + b" ")
    with pytest.raises(ValueError, match="SHA mismatch"):
        build(**args)
    assert not args["out"].exists()


def test_device_semantic_disagreement_is_not_silently_accepted(tmp_path):
    cuda_rows = stream()
    cuda_rows[1]["point_px"] = [101, 200]
    args = fixture_bundle(tmp_path, cuda_rows)
    with pytest.raises(ValueError, match="outputs differ"):
        build(**args)
    assert not args["out"].exists()


def test_denominator_mismatch_rejected_even_if_bytes_pinned(tmp_path):
    args = fixture_bundle(tmp_path)
    report = json.loads(args["tracking_report"].read_text())
    report["frames"] = 7
    args["report_sha256"] = save(args["tracking_report"], report)
    with pytest.raises(ValueError, match="denominator mismatch"):
        build(**args)
    assert not args["out"].exists()


@pytest.mark.parametrize(
    "rows", [[], {}, [None], [{"pitch_id": []}], stream() + stream("g:2:1") + stream()]
)
def test_invalid_or_regrouped_stream_rejected(rows):
    with pytest.raises(ValueError):
        replay(rows)


def test_extra_future_labels_do_not_affect_selection():
    rows = stream()
    changed = [
        {**r, "raw_ai_point_px": [123, 456], "release": 99, "outcome": "single"} for r in rows
    ]
    assert replay(rows) == replay(changed)

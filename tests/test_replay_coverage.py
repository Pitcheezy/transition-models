"""Coverage uses synthetic bound bytes; it must not decode or call a model."""

import json
import subprocess

import pytest

from intent import clip_capture, replay_coverage


def table(rows):
    header = (
        "#format: frame checksums\n#version: 2\n#hash: MD5\n#tb 0: 1/10\n"
        "#media_type 0: video\n#codec_id 0: rawvideo\n#dimensions 0: 4x4\n"
        "#stream#, dts, pts, duration, size, hash\n"
    )
    return (
        header
        + "".join(
            f"0, {pts}, {pts}, {duration}, 24, {identity:032x}\n"
            for pts, duration, identity in rows
        )
    ).encode()


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    def prohibited(*args, **kwargs):
        pytest.fail("Coverage audit must not launch decoder or model processes")

    monkeypatch.setattr(subprocess, "run", prohibited)
    monkeypatch.setattr(subprocess, "Popen", prohibited)
    monkeypatch.setattr(replay_coverage.clip_frames, "extract_frame", prohibited)
    directory = tmp_path / "private capture"
    directory.mkdir()
    media = tmp_path / "private clip.mp4"
    media.write_bytes(b"synthetic local clip")
    rows = [(10, 1, 1), (11, 1, 2), (12, 1, 3), (13, 1, 4)]

    def prepare(clip_rows=None, source_rows=None):
        (directory / "source.framemd5").write_bytes(table(source_rows or rows))
        (directory / "clip.framemd5").write_bytes(table(rows if clip_rows is None else clip_rows))
        digest = clip_capture._sha256(media)
        receipt = {
            "schema": "intent_clip_capture_v1",
            "status": "captured",
            "errors": [],
            "source": {"kind": "url", "value": "https://example.invalid/private-token"},
            "clip": {
                "path": str(media),
                "sha256_before": digest,
                "sha256_after": digest,
                "unchanged": True,
            },
            "artifacts": {
                name: {
                    "sha256": clip_capture._sha256(directory / name),
                    "bytes": (directory / name).stat().st_size,
                }
                for name in ("source.framemd5", "clip.framemd5")
            },
        }
        (directory / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")

    prepare()
    args = {"capture_dir": directory, "start": "1", "end": "1.4", "out": tmp_path / "out.json"}
    return args, prepare, media


def test_complete_coverage_and_path_free_report(inputs):
    args, _, _ = inputs
    result = replay_coverage.audit_replay_coverage(**args)
    assert result["fully_covered"] is True
    assert result["covering_frame_count"] == 4
    assert result["covered_duration_seconds_exact"] == "2/5"
    assert result["gaps"] == []
    assert result["cutoffs_requested"] == 0
    for field in (
        "source_identity_authenticated",
        "full_pa_verified",
        "accuracy_evaluated",
        "live_availability_verified",
    ):
        assert result[field] is False
    raw = args["out"].read_text(encoding="utf-8")
    assert result == json.loads(raw)
    assert "private" not in raw and "example.invalid" not in raw
    assert len(result["input_hashes"]["capture_receipt_sha256"]) == 64


def test_internal_gap_is_reported_even_when_every_cutoff_maps(inputs, tmp_path):
    args, prepare, _ = inputs
    prepare([(10, 1, 1), (11, 1, 2), (13, 1, 4)])
    cutoffs = tmp_path / "cutoffs.json"
    cutoffs.write_text('["1", "1.1", "1.3"]')
    result = replay_coverage.audit_replay_coverage(**args, cutoffs_json=cutoffs)
    assert result["cutoffs_mapped"] == 3 and result["cutoffs_unavailable"] == 0
    assert result["fully_covered"] is False and result["covering_frame_count"] == 3
    assert result["gaps"] == [
        {
            "start_seconds_exact": "6/5",
            "end_seconds_exact": "13/10",
            "duration_seconds_exact": "1/10",
        }
    ]
    assert result["covered_duration_seconds_exact"] == "3/10"


def test_missing_prefix_suffix_and_fully_disjoint_interval(inputs):
    args, _, _ = inputs
    result = replay_coverage.audit_replay_coverage(**{**args, "start": "0.9", "end": "1.5"})
    assert result["covering_frame_count"] == 4
    assert [(gap["start_seconds_exact"], gap["end_seconds_exact"]) for gap in result["gaps"]] == [
        ("9/10", "1"),
        ("7/5", "3/2"),
    ]
    other = {**args, "start": "2", "end": "3", "out": args["out"].with_name("other.json")}
    result = replay_coverage.audit_replay_coverage(**other)
    assert result["covering_frame_count"] == 0 and result["covered_duration_seconds_exact"] == "0"
    assert result["uncovered_duration_seconds_exact"] == "1"


def test_variable_duration_frame_covering_start_is_counted(inputs):
    args, prepare, _ = inputs
    rows = [(10, 2, 1), (12, 3, 2), (15, 1, 3)]
    prepare(rows, rows)
    result = replay_coverage.audit_replay_coverage(**{**args, "start": "1.15", "end": "1.45"})
    assert result["fully_covered"] is True and result["covering_frame_count"] == 2
    assert result["covered_duration_seconds_exact"] == "3/10"


def test_half_open_end_does_not_include_next_frame_or_gap(inputs):
    args, prepare, _ = inputs
    prepare([(10, 1, 1), (11, 1, 2), (13, 1, 4)])
    before = replay_coverage.audit_replay_coverage(**{**args, "end": "1.2"})
    assert before["fully_covered"] is True and before["covering_frame_count"] == 2
    gap = replay_coverage.audit_replay_coverage(
        **{**args, "start": "1.2", "end": "1.3", "out": args["out"].with_name("gap.json")}
    )
    assert gap["covering_frame_count"] == 0 and gap["fully_covered"] is False


def test_cutoff_failures_and_exact_boundary_semantics_are_preserved(inputs, tmp_path):
    args, prepare, _ = inputs
    prepare([(10, 1, 1), (11, 1, 2), (13, 1, 4)])
    cutoffs = tmp_path / "cutoffs.json"
    cutoffs.write_text('["0.99", 1, "1.1999", "1.2", "1.3", "1.4"]')
    result = replay_coverage.audit_replay_coverage(**args, cutoffs_json=cutoffs)
    assert result["cutoffs_requested"] == 6 and result["cutoffs_mapped"] == 3
    assert result["cutoffs_unavailable"] == 3
    rows = result["cutoffs"]
    assert rows[0]["reason"] == rows[-1]["reason"] == "outside_requested_interval"
    assert rows[3]["reason"] == "outside_mapped_coverage"
    assert rows[2]["frame"]["source_seconds_exact"] == "11/10"
    assert rows[4]["frame"]["source_seconds_exact"] == "13/10"


def test_invalid_exact_times_and_nonpositive_intervals_fail_without_output(inputs):
    args, _, _ = inputs
    for start, end in [
        (1.0, "2"),
        (True, "2"),
        ("NaN", "2"),
        ("1/0", "2"),
        ("-1", "2"),
        ("1", "1"),
        ("2", "1"),
        ("1", float("inf")),
        (None, "2"),
        ("", "2"),
    ]:
        with pytest.raises(ValueError):
            replay_coverage.audit_replay_coverage(**{**args, "start": start, "end": end})
        assert not args["out"].exists()


def test_malformed_nonfinite_and_wrong_cutoff_types_are_rejected(inputs, tmp_path):
    args, _, _ = inputs
    cutoffs = tmp_path / "cutoffs.json"
    for content in ("{", "{}", "[NaN]", "[Infinity]", "[1.1]", "[true]", "[null]"):
        cutoffs.write_text(content)
        with pytest.raises(ValueError):
            replay_coverage.audit_replay_coverage(**args, cutoffs_json=cutoffs)
        assert not args["out"].exists()


def test_empty_duplicate_descending_or_excessive_cutoffs_are_rejected(inputs, tmp_path):
    args, _, _ = inputs
    cutoffs = tmp_path / "cutoffs.json"
    for values in ([], [1, 1], [2, 1], list(range(51))):
        cutoffs.write_text(json.dumps(values))
        with pytest.raises(ValueError):
            replay_coverage.audit_replay_coverage(**args, cutoffs_json=cutoffs)
        assert not args["out"].exists()


def test_existing_output_is_preserved_and_capture_directory_is_not_modified(inputs):
    args, _, _ = inputs
    args["out"].write_bytes(b"keep original")
    with pytest.raises(FileExistsError):
        replay_coverage.audit_replay_coverage(**args)
    assert args["out"].read_bytes() == b"keep original"
    with pytest.raises(ValueError, match="outside capture"):
        replay_coverage.audit_replay_coverage(**{**args, "out": args["capture_dir"] / "new.json"})
    assert not (args["capture_dir"] / "new.json").exists()


def test_tampered_bound_media_is_rejected_before_output(inputs):
    args, _, media = inputs
    media.write_bytes(b"tampered media")
    with pytest.raises(ValueError, match="SHA256"):
        replay_coverage.audit_replay_coverage(**args)
    assert not args["out"].exists()


def test_media_changed_during_report_construction_is_rechecked(inputs, monkeypatch):
    args, _, media = inputs
    original = replay_coverage._coverage

    def mutate(*values):
        result = original(*values)
        media.write_bytes(b"tampered during report")
        return result

    monkeypatch.setattr(replay_coverage, "_coverage", mutate)
    with pytest.raises(ValueError, match="SHA256"):
        replay_coverage.audit_replay_coverage(**args)
    assert not args["out"].exists()


def test_cutoff_file_changed_during_report_construction_is_rechecked(inputs, tmp_path, monkeypatch):
    args, _, _ = inputs
    cutoffs = tmp_path / "cutoffs.json"
    cutoffs.write_text('["1.1"]')
    original = replay_coverage._lookup

    def mutate(*values):
        result = original(*values)
        cutoffs.write_text('["1.3"]')
        return result

    monkeypatch.setattr(replay_coverage, "_lookup", mutate)
    with pytest.raises(ValueError, match="SHA256"):
        replay_coverage.audit_replay_coverage(**args, cutoffs_json=cutoffs)
    assert not args["out"].exists()


def test_cli_keeps_report_semantics(inputs, capsys):
    args, _, _ = inputs
    assert (
        replay_coverage.main(
            [
                "--capture-dir",
                str(args["capture_dir"]),
                "--start",
                "1",
                "--end",
                "7/5",
                "--out",
                str(args["out"]),
            ]
        )
        == 0
    )
    result = json.loads(capsys.readouterr().out)
    assert result["requested_interval"]["semantics"] == "[start,end)"
    assert result["requested_interval"]["end_seconds_exact"] == "7/5"
    assert result["fully_covered"] is True

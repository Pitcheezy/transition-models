"""Synthetic checksum tables test exact correspondence without fetching or decoding media."""

import json
from fractions import Fraction

import pytest

from intent import clip_clock as clock


def table(rows, *, time_base="1/10", dimensions="4x4", size=24):
    header = (
        "#format: frame checksums\n#version: 2\n#hash: MD5\n#software: synthetic-test\n"
        f"#tb 0: {time_base}\n#media_type 0: video\n#codec_id 0: rawvideo\n"
        f"#dimensions 0: {dimensions}\n#sar 0: 1/1\n"
        "#stream#, dts, pts, duration, size, hash\n"
    )
    return (
        header
        + "".join(
            f"0, {pts}, {pts}, {duration}, {size}, {identity:032x}\n"
            for pts, duration, identity in rows
        )
    ).encode()


def mapped_gap():
    source = table([(10, 1, 1), (11, 1, 2), (12, 1, 3), (13, 1, 4)])
    clip = table([(0, 1, 1), (1, 1, 2), (3, 1, 4)])
    return clock.audit_mapping(source, clip)


def test_ordinal_pts_and_missing_tick_are_distinct():
    report = mapped_gap()
    assert report["matched_frames"] == 3
    assert report["constant_offset"] == {"exact": "1", "seconds": 1.0}
    assert report["rows"][-1]["clip_decode_ordinal"] == 2
    assert report["rows"][-1]["clip_pts"] == 3
    assert report["rows"][-1]["source_decode_ordinal"] == 3
    assert report["rows"][-1]["source_pts"] == 13
    gap = report["clip"]["gaps"][0]
    assert gap["previous_end_pts"] == 2
    assert gap["next_pts"] == 3
    assert gap["delta_ticks"] == 1
    assert gap["delta_seconds_exact"] == "1/10"


def test_exact_fraction_with_different_time_bases():
    source = table([(10490, 1, 1), (10491, 1, 2)], time_base="1001/60000")
    clip = table([(0, 1001, 1), (1001, 1001, 2)], time_base="1/60000")
    report = clock.audit_mapping(source, clip)
    assert report["constant_offset"]["exact"] == str(Fraction(10490 * 1001, 60000))
    assert report["rows"][1]["clip_seconds_exact"] == "1001/60000"
    assert report["source"]["gaps"] == report["clip"]["gaps"] == []


def test_varying_clock_offsets_are_preserved_without_global_correction():
    source = table([(11000, 1001, 1), (12001, 1001, 2), (13002, 1001, 3)], time_base="1/60000")
    clip = table([(0, 1, 1), (1, 1, 2), (2, 1, 3)], time_base="1001/60000")
    report = clock.audit_mapping(source, clip)
    assert report["constant_offset"] is not None
    quantized = table([(11000, 1001, 1), (12002, 1001, 2), (13002, 1001, 3)], time_base="1/60000")
    report = clock.audit_mapping(quantized, clip)
    assert report["constant_offset"] is None
    assert report["offset_range"]["span_exact"] == "1/60000"
    assert [row["offset_seconds_exact"] for row in report["rows"]] == [
        "11/60",
        "3667/20000",
        "11/60",
    ]


def test_variable_durations_do_not_imply_constant_frame_rate():
    source = table([(100, 2, 1), (102, 5, 2), (107, 3, 3)])
    clip = table([(0, 2, 1), (2, 5, 2), (7, 3, 3)])
    report = clock.audit_mapping(source, clip)
    assert report["source"]["gaps"] == []
    assert clock.latest_mapped_frame(report, "10.69")["source_pts"] == 102
    assert clock.latest_mapped_frame(report, Fraction(107, 10))["source_pts"] == 107


def test_causal_query_never_uses_future_or_fills_gap():
    report = mapped_gap()
    assert clock.latest_mapped_frame(report, 1)["source_pts"] == 10
    assert clock.latest_mapped_frame(report, "1.1999")["source_pts"] == 11
    assert clock.latest_mapped_frame(report, "1.3")["source_pts"] == 13
    for time in ("0.99", "1.2", "1.2999", "1.4", "999"):
        with pytest.raises(ValueError, match="coverage|missing"):
            clock.latest_mapped_frame(report, time)


@pytest.mark.parametrize("invalid", [True, False, "NaN", "inf", None])
def test_query_rejects_invalid_time(invalid):
    with pytest.raises(ValueError, match="finite rational"):
        clock.latest_mapped_frame(mapped_gap(), invalid)


def test_source_overlap_is_explicit_and_lookup_uses_next_source_boundary():
    source = table([(10, 2, 1), (11, 1, 2)])
    clip = table([(0, 1, 1)])
    report = clock.audit_mapping(source, clip)
    assert report["source"]["duration_overlaps"][0]["delta_ticks"] == -1
    assert report["rows"][0]["source_interval_end_exact"] == "11/10"
    with pytest.raises(ValueError, match="coverage|missing"):
        clock.latest_mapped_frame(report, "1.1")


@pytest.mark.parametrize(
    "old,new",
    [
        ("#hash: MD5", "#hash: SHA256"),
        ("#version: 2", "#version: 1"),
        ("#codec_id 0: rawvideo", "#codec_id 0: h264"),
        ("#media_type 0: video", "#media_type 0: audio"),
        ("#tb 0: 1/10", "#tb 0: 0/10"),
        ("#tb 0: 1/10", "#tb 0: 1/0"),
        ("#tb 0: 1/10", "#tb 0: 0.1"),
        ("#tb 0: 1/10", "#tb 0: 1/10\n#tb 0: 1/10"),
        ("#tb 0: 1/10", "#tb 0: 1/10\n#tb 1: 1/10"),
        ("#dimensions 0: 4x4", "#dimensions 0: 0x4"),
        ("#dimensions 0: 4x4\n", ""),
        ("#sar 0: 1/1", "#sar 0: 1/1\n#sar 0: 1/1"),
        ("#stream#, dts, pts, duration, size, hash", "#stream#, pts, dts, duration, size, hash"),
        ("0, 10, 10, 1, 24,", "1, 10, 10, 1, 24,"),
        ("0, 10, 10, 1, 24,", "0, 10, 10, 0, 24,"),
        ("0, 10, 10, 1, 24,", "0, 10, 10, 1, 0,"),
        ("00000000000000000000000000000001", "not-a-digest"),
    ],
)
def test_reject_malformed_schema_headers_and_records(old, new):
    data = table([(10, 1, 1)]).decode().replace(old, new)
    with pytest.raises(ValueError):
        clock.parse_framemd5(data)


@pytest.mark.parametrize("rows", [[(10, 1, 1), (10, 1, 2)], [(10, 1, 1), (9, 1, 2)]])
def test_reject_duplicate_or_regressive_pts(rows):
    with pytest.raises(ValueError, match="strictly increasing"):
        clock.parse_framemd5(table(rows).decode())


def test_reject_empty_table_and_changing_frame_size():
    with pytest.raises(ValueError, match="no decoded frames"):
        clock.parse_framemd5(table([]).decode())
    changing = (
        table([(10, 1, 1), (11, 1, 2)]).decode().replace("0, 11, 11, 1, 24", "0, 11, 11, 1, 30")
    )
    with pytest.raises(ValueError, match="byte size changed"):
        clock.parse_framemd5(changing)


@pytest.mark.parametrize(
    "source,clip,reason",
    [
        ([(10, 1, 1), (11, 1, 1)], [(0, 1, 1)], "ambiguous"),
        ([(10, 1, 1)], [(0, 1, 1), (1, 1, 1)], "ambiguous"),
        ([(10, 1, 1)], [(0, 1, 2)], "Unmatched"),
        ([(10, 1, 1), (11, 1, 2)], [(0, 1, 2), (1, 1, 1)], "presentation order"),
    ],
)
def test_correspondence_rejects_ambiguity_missing_and_reordering(source, clip, reason):
    with pytest.raises(ValueError, match=reason):
        clock.audit_mapping(table(source), table(clip))


@pytest.mark.parametrize("kwargs", [{"dimensions": "2x8"}, {"size": 48}])
def test_reject_incompatible_decoded_geometry_or_size(kwargs):
    with pytest.raises(ValueError, match="incompatible"):
        clock.audit_mapping(table([(10, 1, 1)]), table([(0, 1, 1)], **kwargs))


def test_input_hashes_bind_exact_file_bytes():
    source, clip = table([(10, 1, 1)]), table([(0, 1, 1)])
    before = clock.audit_mapping(source, clip)
    after = clock.audit_mapping(source.replace(b"\n", b"\r\n"), clip)
    assert before["rows"] == after["rows"]
    assert before["input_hashes"]["source_sha256"] != after["input_hashes"]["source_sha256"]
    with pytest.raises(ValueError, match="exact input bytes"):
        clock.audit_mapping(source.decode(), clip)


def test_cli_writes_new_report_and_refuses_overwrite(tmp_path):
    source, clip, out = tmp_path / "source.md5", tmp_path / "clip.md5", tmp_path / "audit.json"
    source.write_bytes(table([(10, 1, 1)]))
    clip.write_bytes(table([(0, 1, 1)]))
    arguments = [
        "audit",
        "--source-frames",
        str(source),
        "--clip-frames",
        str(clip),
        "--out",
        str(out),
    ]
    clock.main(arguments)
    original = out.read_bytes()
    assert json.loads(original)["matched_frames"] == 1
    with pytest.raises(SystemExit) as error:
        clock.main(arguments)
    assert error.value.code == 2
    assert out.read_bytes() == original
    arguments[-1] = str(source)
    with pytest.raises(SystemExit):
        clock.main(arguments)
    assert source.read_bytes() == table([(10, 1, 1)])

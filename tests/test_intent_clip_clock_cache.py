"""Synthetic exact-byte cache and warm-cache input-integrity regressions."""

import json
from pathlib import Path
from threading import Event, Thread

import pytest

from intent import clip_clock as clock
from intent import clip_frames


def table(start):
    return (
        "#format: frame checksums\n#version: 2\n#hash: MD5\n#tb 0: 1/10\n"
        "#media_type 0: video\n#codec_id 0: rawvideo\n#dimensions 0: 4x4\n"
        "#sar 0: 1/1\n#stream#, dts, pts, duration, size, hash\n"
        + "".join(f"0, {start + i}, {start + i}, 1, 24, {i + 1:032x}\n" for i in range(2))
    ).encode()


@pytest.fixture(autouse=True)
def clear_cache():
    clock.clear_mapping_cache()
    yield
    clock.clear_mapping_cache()


@pytest.fixture
def counted_audit(monkeypatch):
    original = clock.audit_mapping
    calls = []

    def counted(source, clip):
        calls.append((source, clip))
        return original(source, clip)

    monkeypatch.setattr(clock, "audit_mapping", counted)
    return original, calls


def test_identical_bytes_hit_and_preserve_exact_original_report(counted_audit):
    original, calls = counted_audit
    source, clip = table(10), table(0)
    first = clock.cached_audit_mapping(source, clip)
    second = clock.cached_audit_mapping(memoryview(source).tobytes(), memoryview(clip).tobytes())
    assert first == second == original(source, clip)
    assert len(calls) == 1
    assert first is not second and first["rows"] is not second["rows"]


@pytest.mark.parametrize("changed", ["source", "clip"])
def test_same_length_input_mutation_is_a_miss(counted_audit, changed):
    original, calls = counted_audit
    source, clip = table(10), table(0)
    first = clock.cached_audit_mapping(source, clip)
    new_source = table(20) if changed == "source" else source
    new_clip = table(2) if changed == "clip" else clip
    assert len(source) == len(new_source) and len(clip) == len(new_clip)
    second = clock.cached_audit_mapping(new_source, new_clip)
    assert len(calls) == 2
    assert second == original(new_source, new_clip) and second != first


def test_only_latest_cacheable_pair_is_retained(counted_audit):
    _, calls = counted_audit
    clock.cached_audit_mapping(table(10), table(0))
    clock.cached_audit_mapping(table(20), table(0))
    clock.cached_audit_mapping(table(10), table(0))
    assert len(calls) == 3


def test_key_keeps_the_pair_boundary_not_only_concatenated_bytes(monkeypatch):
    calls = []

    def audit(source, clip):
        calls.append((source, clip))
        return {"source": source.decode(), "clip": clip.decode()}

    monkeypatch.setattr(clock, "audit_mapping", audit)
    assert clock.cached_audit_mapping(b"a", b"bc") == {"source": "a", "clip": "bc"}
    assert clock.cached_audit_mapping(b"ab", b"c") == {"source": "ab", "clip": "c"}
    assert len(calls) == 2


def test_errors_are_not_cached_or_replaced_by_previous_success(counted_audit):
    original, calls = counted_audit
    source, clip = table(10), table(0)
    expected = clock.cached_audit_mapping(source, clip)
    for _ in range(2):
        with pytest.raises(ValueError):
            clock.cached_audit_mapping(b"malformed checksum table", clip)
    assert len(calls) == 3
    assert clock.cached_audit_mapping(source, clip) == expected == original(source, clip)
    assert len(calls) == 3


def test_nested_mutation_of_first_and_hit_reports_cannot_poison_cache(counted_audit):
    original, calls = counted_audit
    source, clip = table(10), table(0)
    first = clock.cached_audit_mapping(source, clip)
    first["rows"][0]["source_pts"] = 999
    first["source"]["gaps"].append({"fabricated": True})
    second = clock.cached_audit_mapping(source, clip)
    second["input_hashes"]["source_sha256"] = "wrong"
    second["limitations"].clear()
    assert clock.cached_audit_mapping(source, clip) == original(source, clip)
    assert len(calls) == 1


@pytest.mark.parametrize("delta,expected_calls", [(0, 1), (-1, 2)])
def test_combined_input_byte_limit_is_inclusive(monkeypatch, counted_audit, delta, expected_calls):
    original, calls = counted_audit
    source, clip = table(10), table(0)
    monkeypatch.setattr(clock, "_MAPPING_CACHE_MAX_INPUT_BYTES", len(source) + len(clip) + delta)
    for _ in range(2):
        assert clock.cached_audit_mapping(source, clip) == original(source, clip)
    assert len(calls) == expected_calls


@pytest.mark.parametrize("delta,expected_calls", [(0, 1), (-1, 2)])
def test_serialized_utf8_result_limit_is_inclusive(monkeypatch, delta, expected_calls):
    expected = {"nested": ["한글", "é"], "point": [1, 2]}
    serialized = json.dumps(
        expected, ensure_ascii=False, allow_nan=False, separators=(",", ":")
    ).encode()
    calls = []
    monkeypatch.setattr(clock, "_MAPPING_CACHE_MAX_RESULT_BYTES", len(serialized) + delta)

    def audit(source, clip):
        calls.append((source, clip))
        return {"nested": ["한글", "é"], "point": [1, 2]}

    monkeypatch.setattr(clock, "audit_mapping", audit)
    for _ in range(2):
        assert clock.cached_audit_mapping(b"source", b"clip") == expected
    assert len(calls) == expected_calls


@pytest.mark.parametrize("limit", ["input", "result"])
def test_oversize_input_never_falls_back_to_unrelated_cached_result(monkeypatch, limit):
    monkeypatch.setattr(clock, "audit_mapping", lambda source, clip: {"source": source.decode()})
    assert clock.cached_audit_mapping(b"a", b"b") == {"source": "a"}
    if limit == "input":
        monkeypatch.setattr(clock, "_MAPPING_CACHE_MAX_INPUT_BYTES", 2)
    else:
        monkeypatch.setattr(clock, "_MAPPING_CACHE_MAX_RESULT_BYTES", 1)
    assert clock.cached_audit_mapping(b"different", b"b") == {"source": "different"}


def test_lock_contention_bypasses_cache_without_waiting_or_using_old_result(counted_audit):
    original, calls = counted_audit
    clock.cached_audit_mapping(table(10), table(0))
    finished, outcome = Event(), {}

    def work():
        try:
            outcome["report"] = clock.cached_audit_mapping(table(20), table(0))
        finally:
            finished.set()

    clock._MAPPING_CACHE_LOCK.acquire()
    worker = Thread(target=work, daemon=True)
    try:
        worker.start()
        completed_while_locked = finished.wait(2)
    finally:
        clock._MAPPING_CACHE_LOCK.release()
        worker.join(2)
    assert completed_while_locked and not worker.is_alive()
    assert outcome["report"] == original(table(20), table(0))
    assert len(calls) == 2


def test_cache_clear_forces_recalculation(counted_audit):
    _, calls = counted_audit
    clock.cached_audit_mapping(table(10), table(0))
    clock.clear_mapping_cache()
    clock.cached_audit_mapping(table(10), table(0))
    assert len(calls) == 2


@pytest.mark.parametrize("value", [None, "text", bytearray(b"not immutable")])
def test_invalid_input_types_keep_original_error_behavior(value):
    with pytest.raises(ValueError, match="exact input bytes"):
        clock.cached_audit_mapping(value, table(0))


@pytest.fixture
def capture(tmp_path):
    directory = tmp_path / "capture"
    directory.mkdir()
    source_media, clip_media = tmp_path / "source.mp4", tmp_path / "clip.mp4"
    source_media.write_bytes(b"original-source")
    clip_media.write_bytes(b"original-clip")
    for name, raw in (("source.framemd5", table(10)), ("clip.framemd5", table(0))):
        (directory / name).write_bytes(raw)
    source_sha = clock._sha(source_media.read_bytes())
    clip_sha = clock._sha(clip_media.read_bytes())
    receipt = {
        "schema": "intent_clip_capture_v1",
        "status": "captured",
        "errors": [],
        "source": {
            "kind": "local_file",
            "value": str(source_media),
            "sha256_before": source_sha,
            "sha256_after": source_sha,
            "unchanged": True,
        },
        "clip": {
            "path": str(clip_media),
            "sha256_before": clip_sha,
            "sha256_after": clip_sha,
            "unchanged": True,
        },
        "artifacts": {
            path.name: {"sha256": clock._sha(path.read_bytes()), "bytes": path.stat().st_size}
            for path in directory.iterdir()
        },
    }
    (directory / "receipt.json").write_text(json.dumps(receipt))
    return directory, source_media, clip_media


def test_capture_input_reuse_still_reads_and_verifies_files(capture, counted_audit):
    original, calls = counted_audit
    directory, _, _ = capture
    first = clip_frames._capture_inputs(directory)
    second = clip_frames._capture_inputs(directory)
    assert first[3] == second[3] == original(table(10), table(0))
    assert first[3] is not second[3] and len(calls) == 1


@pytest.mark.parametrize(
    "mutation", ["source", "clip", "source_table", "clip_table", "receipt", "symlink"]
)
def test_warm_cache_never_bypasses_source_media_table_receipt_or_path_guards(
    capture, counted_audit, monkeypatch, mutation
):
    directory, source_media, clip_media = capture
    clip_frames._capture_inputs(directory)
    if mutation in ("source", "clip"):
        path = source_media if mutation == "source" else clip_media
        raw = path.read_bytes()
        path.write_bytes(b"X" + raw[1:])
    elif mutation in ("source_table", "clip_table"):
        name = "source.framemd5" if mutation == "source_table" else "clip.framemd5"
        path = directory / name
        raw = path.read_bytes()
        path.write_bytes(
            raw.replace(b"00000000000000000000000000000001", b"00000000000000000000000000000009")
        )
    elif mutation == "receipt":
        path = directory / "receipt.json"
        receipt = json.loads(path.read_bytes())
        receipt["status"] = "failed"
        path.write_text(json.dumps(receipt))
    else:
        original = Path.is_symlink
        monkeypatch.setattr(Path, "is_symlink", lambda path: path == source_media or original(path))
    with pytest.raises(ValueError):
        clip_frames._capture_inputs(directory)
    assert len(counted_audit[1]) == 1

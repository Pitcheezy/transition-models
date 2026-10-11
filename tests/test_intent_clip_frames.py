"""Exercise exact ordinal extraction with synthetic tables and a mocked FFmpeg process."""

import json
import subprocess
from fractions import Fraction
from pathlib import Path

import pytest
from PIL import Image

from intent import clip_capture, clip_frames


def table(rows):
    return (
        "#format: frame checksums\n#version: 2\n#hash: MD5\n#tb 0: 1/10\n"
        "#media_type 0: video\n#codec_id 0: rawvideo\n#dimensions 0: 4x4\n#sar 0: 1/1\n"
        "#stream#, dts, pts, duration, size, hash\n"
        + "".join(f"0, {pts}, {pts}, 1, 24, {identity:032x}\n" for pts, identity in rows)
    ).encode()


def save_receipt(directory, receipt):
    (directory / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")


@pytest.fixture
def inputs(tmp_path):
    clip, directory = tmp_path / "clip with spaces.mp4", tmp_path / "capture"
    clip.write_bytes(b"synthetic-video-bytes")
    directory.mkdir()
    (directory / "source.framemd5").write_bytes(table([(10, 1), (11, 2), (12, 3), (13, 4)]))
    (directory / "clip.framemd5").write_bytes(table([(0, 1), (1, 2), (3, 4)]))
    (directory / "version.stdout.txt").write_bytes(b"ffmpeg synthetic test")
    digest = clip_capture._sha256(clip)
    receipt = {
        "schema": "intent_clip_capture_v1",
        "status": "captured",
        "errors": [],
        "source": {"kind": "url", "value": "https://example.invalid/synthetic.mp4"},
        "clip": {
            "path": str(clip),
            "sha256_before": digest,
            "sha256_after": digest,
            "unchanged": True,
        },
        "artifacts": {
            path.name: {"sha256": clip_capture._sha256(path), "bytes": path.stat().st_size}
            for path in directory.iterdir()
        },
    }
    save_receipt(directory, receipt)
    return (
        {"capture_dir": directory, "source_seconds": "1.35", "out": tmp_path / "frame"},
        receipt,
        clip,
    )


def success(command, **kwargs):
    assert kwargs["shell"] is False
    assert kwargs["stdin"] == subprocess.DEVNULL
    assert "-ss" not in command and "-n" in command and "-copyts" in command
    assert (
        command[command.index("-filter_complex") + 1]
        == "[0:v:0]select=eq(n\\,2),split=2[check][image]"
    )
    checksum = Path(command[command.index("framemd5") + 1])
    checksum.write_bytes(table([(3, 4)]))
    Image.new("RGB", (4, 4), "blue").save(command[-1], format="JPEG")
    return subprocess.CompletedProcess(command, 0)


def test_extract_ordinal_not_pts_preserves_requested_and_actual_time(inputs, monkeypatch):
    args, _, _ = inputs
    monkeypatch.setattr(subprocess, "run", success)
    result = clip_frames.extract_frame(**args)
    assert result["status"] == "extracted"
    assert result["requested_source_seconds_exact"] == "27/20"
    assert result["actual_source_seconds_exact"] == "13/10"
    assert result["actual_clip_seconds_exact"] == "3/10"
    assert result["mapping"]["clip_decode_ordinal"] == 2
    assert result["mapping"]["clip_pts"] == 3
    assert result["artifacts"]["image.jpg"]["sha256"]
    assert result["elapsed_seconds"] >= 0
    assert result == json.loads((args["out"] / "receipt.json").read_text())
    assert result["schema"] != "broadcast_frame_cache_v1"


@pytest.mark.parametrize("cutoff", ["0.99", "1.2", "1.2999", "1.4", True, "nan"])
def test_future_boundary_gap_and_bad_cutoff_refuse_before_process(inputs, monkeypatch, cutoff):
    args, _, _ = inputs
    args["source_seconds"] = cutoff
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("must not run"))
    with pytest.raises(ValueError):
        clip_frames.extract_frame(**args)
    assert not args["out"].exists()


@pytest.mark.parametrize(
    "mutation",
    ["clip", "source_table", "receipt_failed", "receipt_before", "artifact_size", "logs"],
)
def test_bound_capture_mutations_refuse_before_extraction(inputs, monkeypatch, mutation):
    args, receipt, clip = inputs
    if mutation == "clip":
        clip.write_bytes(b"changed")
    elif mutation == "source_table":
        (args["capture_dir"] / "source.framemd5").write_bytes(table([(10, 9)]))
    elif mutation == "receipt_failed":
        receipt["status"] = "failed"
    elif mutation == "receipt_before":
        receipt["clip"]["sha256_before"] = "0" * 64
    elif mutation == "artifact_size":
        receipt["artifacts"]["source.framemd5"]["bytes"] += 1
    elif mutation == "logs":
        (args["capture_dir"] / "version.stdout.txt").write_bytes(b"tampered")
    save_receipt(args["capture_dir"], receipt)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("must not run"))
    with pytest.raises(ValueError):
        clip_frames.extract_frame(**args)
    assert not args["out"].exists()


def test_local_source_bytes_also_remain_bound(inputs, monkeypatch, tmp_path):
    args, receipt, _ = inputs
    source = tmp_path / "source.mp4"
    source.write_bytes(b"original")
    digest = clip_capture._sha256(source)
    receipt["source"] = {
        "kind": "local_file",
        "value": str(source),
        "sha256_before": digest,
        "sha256_after": digest,
        "unchanged": True,
    }
    save_receipt(args["capture_dir"], receipt)
    source.write_bytes(b"changed")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("must not run"))
    with pytest.raises(ValueError, match="SHA256 changed"):
        clip_frames.extract_frame(**args)


@pytest.mark.parametrize(
    "mutation", ["wrong_pts", "wrong_checksum", "wrong_tb", "two_frames", "missing_image"]
)
def test_output_must_match_one_exact_decoded_frame(inputs, monkeypatch, mutation):
    args, _, _ = inputs

    def run(command, **kwargs):
        result = success(command, **kwargs)
        checksum = Path(command[command.index("framemd5") + 1])
        if mutation == "wrong_pts":
            checksum.write_bytes(table([(2, 4)]))
        elif mutation == "wrong_checksum":
            checksum.write_bytes(table([(3, 9)]))
        elif mutation == "wrong_tb":
            checksum.write_bytes(table([(3, 4)]).replace(b"1/10", b"1/20"))
        elif mutation == "two_frames":
            checksum.write_bytes(table([(3, 4), (4, 5)]))
        elif mutation == "missing_image":
            Path(command[-1]).unlink()
        return result

    monkeypatch.setattr(subprocess, "run", run)
    result = clip_frames.extract_frame(**args)
    assert result["status"] == "failed"
    assert result["errors"]
    assert (args["out"] / "selected.framemd5").exists()
    assert (args["out"] / "receipt.json").exists()


@pytest.mark.parametrize("mutation", ["clip", "table", "receipt"])
def test_inputs_mutating_during_ffmpeg_fail_final_check(inputs, monkeypatch, mutation):
    args, receipt, clip = inputs

    def run(command, **kwargs):
        result = success(command, **kwargs)
        if mutation == "clip":
            clip.write_bytes(b"changed-after-start")
        elif mutation == "table":
            (args["capture_dir"] / "source.framemd5").write_bytes(b"changed")
        else:
            receipt["status"] = "failed"
            save_receipt(args["capture_dir"], receipt)
        return result

    monkeypatch.setattr(subprocess, "run", run)
    result = clip_frames.extract_frame(**args)
    assert result["status"] == "failed"
    assert any("Final input check" in error for error in result["errors"])


@pytest.mark.parametrize("failure", ["exit", "timeout", "missing_binary"])
def test_process_failures_preserve_logs_and_failed_receipt(inputs, monkeypatch, failure):
    args, _, _ = inputs

    def run(command, **kwargs):
        kwargs["stderr"].write(b"synthetic process failure")
        if failure == "exit":
            return subprocess.CompletedProcess(command, 9)
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, kwargs["timeout"])
        raise FileNotFoundError("synthetic missing ffmpeg")

    monkeypatch.setattr(subprocess, "run", run)
    result = clip_frames.extract_frame(**args)
    assert result["status"] == "failed"
    assert result["command"]["error"]
    assert (args["out"] / "extract.stderr.txt").read_bytes() == b"synthetic process failure"
    assert (args["out"] / "receipt.json").exists()


def test_existing_output_preserved_and_overlap_refused(inputs, monkeypatch):
    args, _, _ = inputs
    args["out"].mkdir()
    marker = args["out"] / "keep.txt"
    marker.write_bytes(b"preserve")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("must not run"))
    with pytest.raises(FileExistsError):
        clip_frames.extract_frame(**args)
    assert marker.read_bytes() == b"preserve"
    args["out"] = args["capture_dir"] / "new"
    with pytest.raises(ValueError, match="overlap"):
        clip_frames.extract_frame(**args)


def test_invalid_artifact_path_refused(inputs):
    args, receipt, _ = inputs
    receipt["artifacts"]["../outside"] = {"sha256": "0" * 64, "bytes": 0}
    save_receipt(args["capture_dir"], receipt)
    with pytest.raises(ValueError, match="plain filename"):
        clip_frames.extract_frame(**args)


@pytest.mark.parametrize("exception", [KeyboardInterrupt, ArithmeticError])
def test_interruption_or_unexpected_error_cannot_record_success(inputs, monkeypatch, exception):
    args, _, _ = inputs
    monkeypatch.setattr(subprocess, "run", success)

    def fail(*_):
        raise exception("synthetic verification failure")

    monkeypatch.setattr(clip_frames, "_verify_extraction", fail)
    result = clip_frames.extract_frame(**args)
    assert result["status"] == "failed"
    assert result["extraction_verified"] is False
    assert result["bindings_verified"] is True
    assert exception.__name__ in result["errors"][0]
    assert json.loads((args["out"] / "receipt.json").read_text())["status"] == "failed"


def test_interrupted_final_input_check_cannot_record_success(inputs, monkeypatch):
    args, _, _ = inputs
    monkeypatch.setattr(subprocess, "run", success)
    original = clip_frames._verify_files
    calls = 0

    def verify(bindings):
        nonlocal calls
        calls += 1
        if calls == 2:
            raise KeyboardInterrupt("synthetic final interruption")
        original(bindings)

    monkeypatch.setattr(clip_frames, "_verify_files", verify)
    result = clip_frames.extract_frame(**args)
    assert result["status"] == "failed"
    assert result["extraction_verified"] is True
    assert result["bindings_verified"] is False


@pytest.mark.parametrize("bad_image", ["corrupt", "PNG", "wrong_dimensions", "truncated"])
def test_output_must_be_a_decodable_full_size_jpeg(inputs, monkeypatch, bad_image):
    args, _, _ = inputs

    def run(command, **kwargs):
        result = success(command, **kwargs)
        image = Path(command[-1])
        if bad_image == "corrupt":
            image.write_bytes(b"not an image")
        elif bad_image == "PNG":
            Image.new("RGB", (4, 4), "blue").save(image, format="PNG")
        elif bad_image == "wrong_dimensions":
            Image.new("RGB", (5, 4), "blue").save(image, format="JPEG")
        else:
            image.write_bytes(image.read_bytes()[:-20])
        return result

    monkeypatch.setattr(subprocess, "run", run)
    result = clip_frames.extract_frame(**args)
    assert result["status"] == "failed"
    assert result["extraction_verified"] is False
    assert result["errors"]


def test_load_recomputes_capture_and_returns_exact_time(inputs, monkeypatch):
    args, _, _ = inputs
    monkeypatch.setattr(subprocess, "run", success)
    result = clip_frames.extract_frame(**args)
    assert result["capture_directory"] == str(args["capture_dir"].resolve())
    loaded = clip_frames.load_verified_frame(args["out"])
    assert loaded["source_seconds"] == Fraction(13, 10)
    assert loaded["requested_source_seconds"] == Fraction(27, 20)
    assert loaded["dimensions"] == (4, 4)
    assert loaded["image_path"] == args["out"] / "image.jpg"
    assert loaded["receipt_sha256"] == clip_capture._sha256(loaded["receipt_path"])


@pytest.mark.parametrize(
    "mutation",
    [
        "image_bytes",
        "checksum_bytes",
        "capture_bytes",
        "clip_bytes",
        "failed_status",
        "false_flag",
        "command_failure",
        "actual_time",
        "cutoff",
        "mapping",
        "input_hash",
        "artifact_path",
        "missing_capture_directory",
    ],
)
def test_load_rejects_changed_evidence_failed_or_fabricated_receipts(inputs, monkeypatch, mutation):
    args, _, clip = inputs
    monkeypatch.setattr(subprocess, "run", success)
    result = clip_frames.extract_frame(**args)
    if mutation == "image_bytes":
        (args["out"] / "image.jpg").write_bytes(b"changed")
    elif mutation == "checksum_bytes":
        (args["out"] / "selected.framemd5").write_bytes(table([(3, 9)]))
    elif mutation == "capture_bytes":
        (args["capture_dir"] / "source.framemd5").write_bytes(b"changed")
    elif mutation == "clip_bytes":
        clip.write_bytes(b"changed")
    elif mutation == "failed_status":
        result["status"] = "failed"
    elif mutation == "false_flag":
        result["bindings_verified"] = False
    elif mutation == "command_failure":
        result["command"]["exit_code"] = 1
    elif mutation == "actual_time":
        result["actual_source_seconds_exact"] = "27/20"
    elif mutation == "cutoff":
        result["requested_source_seconds_exact"] = "11/10"
    elif mutation == "mapping":
        result["mapping"]["source_pts"] = 12
    elif mutation == "input_hash":
        result["input_hashes"]["capture_receipt_sha256"] = "0" * 64
    elif mutation == "artifact_path":
        result["artifacts"]["../outside"] = {"sha256": "0" * 64, "bytes": 0}
    else:
        del result["capture_directory"]
    save_receipt(args["out"], result)
    with pytest.raises(ValueError):
        clip_frames.load_verified_frame(args["out"])


@pytest.mark.parametrize("exception", [OSError, KeyboardInterrupt])
def test_module_hash_failure_after_creation_still_records_failure(inputs, monkeypatch, exception):
    args, _, _ = inputs
    original = clip_capture._sha256

    def digest(path):
        if path == Path(clip_frames.__file__):
            raise exception("synthetic code hash failure")
        return original(path)

    monkeypatch.setattr(clip_capture, "_sha256", digest)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("must not run"))
    result = clip_frames.extract_frame(**args)
    assert result["status"] == "failed"
    assert result["module_sha256"] is None and result["command"] is None
    assert result["extraction_verified"] is False
    assert json.loads((args["out"] / "receipt.json").read_text())["status"] == "failed"


def test_final_artifact_hash_failure_records_failure_and_preserves_image(inputs, monkeypatch):
    args, _, _ = inputs
    monkeypatch.setattr(subprocess, "run", success)
    original = clip_capture._sha256

    def digest(path):
        if path == args["out"] / "image.jpg":
            raise OSError("synthetic image hash failure")
        return original(path)

    monkeypatch.setattr(clip_capture, "_sha256", digest)
    result = clip_frames.extract_frame(**args)
    assert result["status"] == "failed"
    assert result["extraction_verified"] is True
    assert any("artifact hash failed" in error for error in result["errors"])
    assert (args["out"] / "image.jpg").exists()
    assert json.loads((args["out"] / "receipt.json").read_text())["status"] == "failed"

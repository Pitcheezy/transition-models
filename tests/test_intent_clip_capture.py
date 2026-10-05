"""Capture evidence and refusal boundaries without invoking FFmpeg or networking."""

import json
import subprocess
from pathlib import Path

import pytest

from intent import clip_capture
from intent.clip_capture import capture, main

FRAME_HEADERS = """#format: frame checksums
#version: 2
#hash: MD5
#tb 0: 1/60000
#media_type 0: video
#codec_id 0: rawvideo
#dimensions 0: 2x2
#sar 0: 1/1
#stream#, dts, pts, duration, size, hash
"""
FRAME_ROW = "0, 10323000, 10323000, 3003, 6, 00112233445566778899aabbccddeeff\n"


@pytest.fixture
def inputs(tmp_path):
    clip = tmp_path / "clip with spaces.mp4"
    clip.write_bytes(b"local-clip")
    return dict(
        source="https://example.test/video.mp4?x=1&y=2",
        source_start=172,
        source_duration=62,
        clip=clip,
        out=tmp_path / "fresh",
    )


def fake_success(command, **kwargs):
    assert isinstance(command, list)
    assert kwargs["shell"] is False and kwargs["stdin"] == subprocess.DEVNULL
    assert kwargs["timeout"] > 0
    if "-version" in command:
        kwargs["stdout"].write(b"ffmpeg version test-build\nconfiguration: synthetic\n")
    else:
        Path(command[-1]).write_text(FRAME_HEADERS + FRAME_ROW)
    return subprocess.CompletedProcess(command, 0)


def test_success_preserves_requested_interval_commands_raw_pts_and_hashes(inputs, monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        return fake_success(command, **kwargs)

    monkeypatch.setattr(subprocess, "run", run)
    receipt = capture(**inputs, ffmpeg="custom ffmpeg.exe")
    assert receipt["status"] == "captured"
    assert len(calls) == 3
    source, clip = calls[1:]
    assert source[source.index("-ss") + 1] == "172"
    assert source[source.index("-t") + 1] == "62"
    assert source.index("-ss") < source.index("-i")
    assert source[source.index("-i") + 1] == inputs["source"]
    assert "-ss" not in clip and "-t" not in clip
    assert "-copyts" in source and "-copyts" in clip
    assert "-n" in source and "-y" not in source
    assert receipt["clip"]["unchanged"]
    assert receipt["clip"]["sha256_before"] == receipt["clip"]["sha256_after"]
    assert receipt["actual_pts_parsed"] is True and receipt["alignment_verified"] is False
    assert receipt["frame_tables"]["source"]["frame_count"] == 1
    assert receipt["frame_tables"]["clip"]["first_pts"] == 10323000
    assert receipt["source"]["identity_claim_verified"] is False
    assert receipt["requested_source_interval"]["end_seconds"] == 234
    assert "10323000" in (inputs["out"] / "source.framemd5").read_text()
    assert receipt["artifacts"]["source.framemd5"]["sha256"]
    assert receipt == json.loads((inputs["out"] / "receipt.json").read_text())


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_start", -1),
        ("source_start", float("nan")),
        ("source_duration", 0),
        ("source_duration", float("inf")),
        ("source_duration", True),
        ("timeout", 0),
        ("timeout", 3601),
        ("source", "ftp://example.test/a.mp4"),
        ("source", "https:///video.mp4"),
        ("source", "https://user:password@example.test/video.mp4"),
    ],
)
def test_invalid_arguments_have_no_process_or_directory_side_effects(
    inputs, monkeypatch, field, value
):
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("process must not start"))
    inputs[field] = value
    with pytest.raises(ValueError):
        capture(**inputs)
    assert not inputs["out"].exists()


def test_existing_folder_never_touched(inputs, monkeypatch):
    inputs["out"].mkdir()
    sentinel = inputs["out"] / "keep"
    sentinel.write_text("original")
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("process must not start"))
    with pytest.raises(FileExistsError):
        capture(**inputs)
    assert sentinel.read_text() == "original"
    assert list(inputs["out"].iterdir()) == [sentinel]


def test_nonzero_and_timeout_preserve_partial_artifacts_and_receipt(inputs, monkeypatch):
    def run(command, **kwargs):
        if "-version" in command:
            return fake_success(command, **kwargs)
        Path(command[-1]).write_bytes(b"partial evidence")
        kwargs["stderr"].write(b"decode failure evidence")
        if command[-1].endswith("source.framemd5"):
            return subprocess.CompletedProcess(command, 7)
        raise subprocess.TimeoutExpired(command, kwargs["timeout"])

    monkeypatch.setattr(subprocess, "run", run)
    result = capture(**inputs)
    assert result["status"] == "failed"
    assert result["commands"]["source"]["exit_code"] == 7
    assert result["commands"]["clip"]["error"]["type"] == "TimeoutExpired"
    assert result["artifacts"]["clip.framemd5"]["bytes"] == 16
    assert (inputs["out"] / "source.stderr.txt").read_text() == "decode failure evidence"
    assert (inputs["out"] / "receipt.json").is_file()


def test_missing_ffmpeg_records_failure_and_does_not_decode(inputs, monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        raise FileNotFoundError("ffmpeg missing")

    monkeypatch.setattr(subprocess, "run", run)
    result = capture(**inputs)
    assert result["status"] == "failed" and len(calls) == 1
    assert result["clip"]["unchanged"]
    assert "version: FileNotFoundError" in result["errors"]


def test_success_exit_without_frame_output_is_failed(inputs, monkeypatch):
    monkeypatch.setattr(
        subprocess, "run", lambda command, **kw: subprocess.CompletedProcess(command, 0)
    )
    result = capture(**inputs)
    assert result["status"] == "failed"
    assert any("missing or empty" in error for error in result["errors"])


@pytest.mark.parametrize("content", [FRAME_HEADERS, FRAME_HEADERS + FRAME_ROW.replace("3003", "0")])
def test_header_only_eof_or_invalid_rows_are_failed(inputs, monkeypatch, content):
    def run(command, **kwargs):
        result = fake_success(command, **kwargs)
        if command[-1].endswith("source.framemd5"):
            Path(command[-1]).write_text(content)
        return result

    monkeypatch.setattr(subprocess, "run", run)
    result = capture(**inputs)
    assert result["status"] == "failed" and result["actual_pts_parsed"] is False
    assert "source" not in result["frame_tables"] and "clip" in result["frame_tables"]
    assert all(record["exit_code"] == 0 for record in result["commands"].values())
    assert any("invalid framemd5" in error for error in result["errors"])
    assert (inputs["out"] / "source.framemd5").read_text() == content


@pytest.mark.parametrize("stage", ["module_hash", "clip_hash", "version_read", "before_source"])
def test_capture_body_interrupt_is_recorded_and_never_captured(inputs, monkeypatch, stage):
    monkeypatch.setattr(subprocess, "run", fake_success)
    interrupted = False
    original_hash, original_read, original_run = (
        clip_capture._sha256,
        Path.read_text,
        clip_capture._run,
    )

    def hash_file(path):
        nonlocal interrupted
        target = Path(clip_capture.__file__) if stage == "module_hash" else inputs["clip"]
        if stage in ("module_hash", "clip_hash") and path == target and not interrupted:
            interrupted = True
            raise KeyboardInterrupt()
        return original_hash(path)

    def read_file(path, *args, **kwargs):
        nonlocal interrupted
        if stage == "version_read" and path.name == "ffmpeg_version.stdout.txt" and not interrupted:
            interrupted = True
            raise KeyboardInterrupt()
        return original_read(path, *args, **kwargs)

    def run(command, name, *args):
        nonlocal interrupted
        if stage == "before_source" and name == "source" and not interrupted:
            interrupted = True
            raise KeyboardInterrupt()
        return original_run(command, name, *args)

    monkeypatch.setattr(clip_capture, "_sha256", hash_file)
    monkeypatch.setattr(Path, "read_text", read_file)
    monkeypatch.setattr(clip_capture, "_run", run)
    result = capture(**inputs)
    assert interrupted and result["status"] == "failed"
    assert result["actual_pts_parsed"] is False
    assert any("KeyboardInterrupt" in error for error in result["errors"])
    assert any("command missing" in error for error in result["errors"])
    assert json.loads((inputs["out"] / "receipt.json").read_text())["status"] == "failed"


@pytest.mark.parametrize("stage", ["version", "source", "clip"])
@pytest.mark.parametrize("exit_code", [None, 1])
def test_error_none_does_not_override_required_exit_status(inputs, monkeypatch, stage, exit_code):
    monkeypatch.setattr(subprocess, "run", fake_success)
    original_run = clip_capture._run

    def run(command, name, *args):
        record = original_run(command, name, *args)
        if name == ("ffmpeg_version" if stage == "version" else stage):
            record.update(exit_code=exit_code, error=None)
        return record

    monkeypatch.setattr(clip_capture, "_run", run)
    result = capture(**inputs)
    assert result["status"] == "failed"
    assert any("unsuccessful" in error for error in result["errors"])


def test_local_source_mutation_is_detected(inputs, monkeypatch, tmp_path):
    source = tmp_path / "source.mp4"
    source.write_bytes(b"before")
    inputs["source"] = source

    def run(command, **kwargs):
        result = fake_success(command, **kwargs)
        if command[-1].endswith("source.framemd5"):
            source.write_bytes(b"changed")
        return result

    monkeypatch.setattr(subprocess, "run", run)
    result = capture(**inputs)
    assert result["status"] == "failed"
    assert result["source"]["unchanged"] is False
    assert result["clip"]["unchanged"] is True


def test_clip_mutation_is_detected(inputs, monkeypatch):
    def run(command, **kwargs):
        result = fake_success(command, **kwargs)
        if command[-1].endswith("clip.framemd5"):
            inputs["clip"].write_bytes(b"changed")
        return result

    monkeypatch.setattr(subprocess, "run", run)
    result = capture(**inputs)
    assert result["status"] == "failed"
    assert result["clip"]["unchanged"] is False


def test_interrupt_records_failure_and_stops_remaining_decode(inputs, monkeypatch):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        if "-version" in command:
            return fake_success(command, **kwargs)
        raise KeyboardInterrupt()

    monkeypatch.setattr(subprocess, "run", run)
    result = capture(**inputs)
    assert result["status"] == "failed"
    assert len(calls) == 2 and "clip" not in result["commands"]
    assert result["commands"]["source"]["error"]["type"] == "KeyboardInterrupt"
    assert (inputs["out"] / "receipt.json").is_file()


def test_output_inside_clip_path_is_refused_before_creation(inputs, monkeypatch):
    inputs["out"] = inputs["clip"] / "nested"
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("process must not start"))
    with pytest.raises(ValueError, match="overlap"):
        capture(**inputs)
    assert inputs["clip"].read_bytes() == b"local-clip"


def test_symlink_input_refused(inputs, monkeypatch, tmp_path):
    linked = tmp_path / "link.mp4"
    try:
        linked.symlink_to(inputs["clip"])
    except OSError:
        pytest.skip("host does not permit symlink creation")
    inputs["clip"] = linked
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("process must not start"))
    with pytest.raises(ValueError, match="Symlinks"):
        capture(**inputs)


def test_cli_reports_runtime_failure(inputs, monkeypatch, capsys):
    monkeypatch.setattr(
        subprocess, "run", lambda command, **kw: subprocess.CompletedProcess(command, 1)
    )
    code = main(
        [
            "--source",
            inputs["source"],
            "--source-start",
            "172",
            "--source-duration",
            "62",
            "--clip",
            str(inputs["clip"]),
            "--out",
            str(inputs["out"]),
        ]
    )
    assert code == 1
    assert json.loads(capsys.readouterr().out)["status"] == "failed"

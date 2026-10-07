"""Verify seeking cannot change a mapped frame or weaken extraction failures."""

import json
import os
import shutil
import subprocess
from fractions import Fraction
from pathlib import Path

import pytest
from PIL import Image

from intent import clip_capture, clip_clock, clip_frames


def _table(rows):
    return (
        "#format: frame checksums\n#version: 2\n#hash: MD5\n#tb 0: 1/10\n"
        "#media_type 0: video\n#codec_id 0: rawvideo\n#dimensions 0: 4x4\n#sar 0: 1/1\n"
        "#stream#, dts, pts, duration, size, hash\n"
        + "".join(f"0, {pts}, {pts}, 1, 24, {identity:032x}\n" for pts, identity in rows)
    ).encode()


def _synthetic_capture(tmp_path, target):
    clip = tmp_path / "input with spaces.mp4"
    clip.write_bytes(b"mock video: decoded bytes are supplied by the process double")
    capture = tmp_path / "capture"
    capture.mkdir()
    for name in ("source.framemd5", "clip.framemd5"):
        (capture / name).write_bytes(_table([(target - 1, 1), (target, 2)]))
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
            for path in capture.iterdir()
        },
    }
    (capture / "receipt.json").write_text(json.dumps(receipt), encoding="utf-8")
    return {
        "capture_dir": capture,
        "source_seconds": str(Fraction(target, 10)),
        "out": tmp_path / "frame",
    }


def _fake_extraction(monkeypatch, target, *, corrupt=False):
    calls = []

    def run(command, **kwargs):
        calls.append(command)
        assert kwargs["shell"] is False
        assert kwargs["stdin"] == subprocess.DEVNULL
        checksum = Path(command[command.index("framemd5") + 1])
        checksum.write_bytes(_table([(target + int(corrupt), 2)]))
        Image.new("RGB", (4, 4), "blue").save(command[-1], format="JPEG")
        return subprocess.CompletedProcess(command, 0)

    monkeypatch.setattr(subprocess, "run", run)
    return calls


def test_late_default_seeks_but_retains_the_exact_ordinal_reference(tmp_path, monkeypatch):
    args = _synthetic_capture(tmp_path, 123)
    calls = _fake_extraction(monkeypatch, 123)
    sought = clip_frames.extract_frame(**args)
    args["out"] = tmp_path / "reference"
    reference = clip_frames.extract_frame(**args, extraction_mode="ordinal")
    assert sought["status"] == reference["status"] == "extracted"
    assert sought["requested_extraction_mode"] == sought["actual_extraction_mode"] == "seek_pts"
    assert (
        reference["requested_extraction_mode"] == reference["actual_extraction_mode"] == "ordinal"
    )
    assert sought["mapping"] == reference["mapping"]
    assert sought["mapping"]["clip_decode_ordinal"] == 1
    assert sought["actual_clip_seconds_exact"] == "123/10"
    assert sought["artifacts"]["image.jpg"] == reference["artifacts"]["image.jpg"]
    assert len(calls) == 2
    assert "-ss" in calls[0] and "-ss" not in calls[1]
    assert calls[0].index("-ss") < calls[0].index("-i")
    assert Fraction(calls[0][calls[0].index("-ss") + 1]) < Fraction("123/10")
    assert "-seek_timestamp" in calls[0] and "-noaccurate_seek" in calls[0]
    assert "-copyts" in calls[0]
    assert "eq(pts\\,123)" in calls[0][calls[0].index("-filter_complex") + 1]
    loaded = clip_frames.load_verified_frame(tmp_path / "frame")
    assert loaded["source_seconds"] == Fraction(123, 10)
    # Old receipts had neither mode field; their checksum and capture evidence still load.
    del reference["requested_extraction_mode"], reference["actual_extraction_mode"]
    legacy = args["out"] / "receipt.json"
    legacy.write_text(json.dumps(reference), encoding="utf-8")
    loaded_legacy = clip_frames.load_verified_frame(args["out"])
    assert loaded_legacy["source_seconds"] == Fraction(123, 10)
    assert loaded_legacy["receipt_sha256"] == clip_capture._sha256(legacy)


@pytest.mark.parametrize("target", [-13, -1, 0, 29, 2**53, 2**53 + 1])
def test_unsafe_seek_times_keep_the_exact_ordinal_path(tmp_path, monkeypatch, target):
    args = _synthetic_capture(tmp_path, target)
    calls = _fake_extraction(monkeypatch, target)
    result = clip_frames.extract_frame(**args)
    assert result["status"] == "extracted"
    assert result["requested_extraction_mode"] == "seek_pts"
    assert result["actual_extraction_mode"] == "ordinal"
    assert len(calls) == 1 and "-ss" not in calls[0]
    assert result["mapping"]["clip_pts"] == target
    assert "eq(n\\,1)" in calls[0][calls[0].index("-filter_complex") + 1]


@pytest.mark.parametrize("target", [30, 31, 2**53 - 1])
def test_exact_seek_boundaries_preserve_requested_frame(tmp_path, monkeypatch, target):
    args = _synthetic_capture(tmp_path, target)
    calls = _fake_extraction(monkeypatch, target)
    result = clip_frames.extract_frame(**args)
    assert result["status"] == "extracted"
    assert result["requested_extraction_mode"] == result["actual_extraction_mode"] == "seek_pts"
    assert len(calls) == 1 and "-ss" in calls[0]
    seek = Fraction(calls[0][calls[0].index("-ss") + 1])
    assert 0 < seek < Fraction(target, 10)
    assert result["mapping"]["clip_pts"] == target
    if target in (30, 31):
        assert seek == 1


@pytest.mark.parametrize("mode", ["nearby", "", None, True, 1, []])
def test_unknown_mode_cannot_start_a_process_or_create_output(tmp_path, monkeypatch, mode):
    args = _synthetic_capture(tmp_path, 123)
    monkeypatch.setattr(subprocess, "run", lambda *a, **k: pytest.fail("unexpected process"))
    with pytest.raises(ValueError, match="extraction_mode"):
        clip_frames.extract_frame(**args, extraction_mode=mode)
    assert not args["out"].exists()


def test_wrong_seek_frame_is_preserved_as_failure_without_retry(tmp_path, monkeypatch):
    args = _synthetic_capture(tmp_path, 123)
    calls = _fake_extraction(monkeypatch, 123, corrupt=True)
    result = clip_frames.extract_frame(**args)
    assert len(calls) == 1 and "-ss" in calls[0]
    assert result["status"] == "failed" and result["extraction_verified"] is False
    assert result["bindings_verified"] is True
    assert any("PTS/duration/size/checksum differs" in error for error in result["errors"])
    assert (args["out"] / "image.jpg").is_file()
    assert json.loads((args["out"] / "receipt.json").read_text())["status"] == "failed"
    with pytest.raises(ValueError):
        clip_frames.load_verified_frame(args["out"])


def _checked_process(argv):
    result = subprocess.run(
        argv,
        stdin=subprocess.DEVNULL,
        capture_output=True,
        shell=False,
        timeout=30,
        check=False,
    )
    assert result.returncode == 0, result.stderr.decode("utf-8", errors="replace")
    return result


@pytest.mark.parametrize("start_seconds", [0, 5])
def test_real_decoder_seek_matches_ordinal_with_b_frames_and_pts_gaps(tmp_path, start_seconds):
    """Opt in with INTENT_TEST_FFMPEG; all media are generated inside the test directory."""
    configured = os.environ.get("INTENT_TEST_FFMPEG")
    if not configured:
        pytest.skip("Set INTENT_TEST_FFMPEG to run the local synthetic decoder regression")
    resolved = shutil.which(configured)
    assert resolved, "INTENT_TEST_FFMPEG must name an available FFmpeg binary"
    ffmpeg = str(Path(resolved).resolve())
    ffprobe = str(Path(ffmpeg).with_name("ffprobe" + Path(ffmpeg).suffix))
    assert Path(ffprobe).is_file(), "The configured FFmpeg needs its adjacent ffprobe binary"
    clip = tmp_path / "synthetic b frames and gaps.mp4"
    _checked_process(
        [
            ffmpeg,
            "-nostdin",
            "-n",
            "-v",
            "error",
            "-f",
            "lavfi",
            "-i",
            "testsrc2=size=96x64:rate=12:duration=10",
            "-vf",
            f"select='not(between(n,44,46))',setpts=PTS+{start_seconds}/TB",
            "-fps_mode",
            "passthrough",
            "-c:v",
            "libx264",
            "-pix_fmt",
            "yuv420p",
            "-x264-params",
            "bframes=3:b-adapt=0:keyint=24:min-keyint=24:scenecut=0",
            str(clip),
        ]
    )
    probe = _checked_process(
        [
            ffprobe,
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_frames",
            "-show_entries",
            "frame=pict_type",
            "-of",
            "json",
            str(clip),
        ]
    )
    assert any(frame["pict_type"] == "B" for frame in json.loads(probe.stdout)["frames"])
    capture = tmp_path / "capture"
    receipt = clip_capture.capture(
        source=clip,
        source_start=0,
        source_duration=30,
        clip=clip,
        out=capture,
        ffmpeg=ffmpeg,
        timeout=30,
    )
    assert receipt["status"] == "captured", receipt["errors"]
    report = clip_clock.audit_mapping(
        (capture / "source.framemd5").read_bytes(), (capture / "clip.framemd5").read_bytes()
    )
    assert Fraction(report["clip"]["first_seconds_exact"]) == start_seconds
    assert report["clip"]["gaps"], "The fixture must really contain timestamp gaps"
    for index in (0, len(report["rows"]) // 2, len(report["rows"]) - 1):
        mapping = report["rows"][index]
        cutoff = mapping["source_seconds_exact"]
        results = {}
        for mode in ("ordinal", "seek_pts"):
            output = tmp_path / f"{index}_{mode}"
            result = clip_frames.extract_frame(
                capture_dir=capture,
                source_seconds=cutoff,
                out=output,
                ffmpeg=ffmpeg,
                timeout=30,
                extraction_mode=mode,
            )
            assert result["status"] == "extracted", result["errors"]
            assert result["mapping"] == mapping
            loaded = clip_frames.load_verified_frame(output)
            assert loaded["source_seconds"] == Fraction(cutoff)
            results[mode] = (result, output)
        reference, sought = (results[mode][1] for mode in ("ordinal", "seek_pts"))
        assert (reference / "image.jpg").read_bytes() == (sought / "image.jpg").read_bytes()
        ref_table, seek_table = (
            clip_clock.parse_framemd5((path / "selected.framemd5").read_text())
            for path in (reference, sought)
        )
        assert ref_table == seek_table
        if index == len(report["rows"]) - 1:
            assert "-ss" in results["seek_pts"][0]["command"]["argv"]
    gap = report["source"]["gaps"][0]
    cutoff = Fraction(gap["previous_end_pts"] + gap["next_pts"], 2) * Fraction(
        report["source"]["time_base"]
    )
    output = tmp_path / "in_gap"
    with pytest.raises(ValueError, match="missing interval"):
        clip_frames.extract_frame(
            capture_dir=capture,
            source_seconds=str(cutoff),
            out=output,
            ffmpeg=ffmpeg,
        )
    assert not output.exists()

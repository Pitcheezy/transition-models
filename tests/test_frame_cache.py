"""Cache reuse requires source, millisecond seek and bytes; extraction remains offline here."""

import json
import subprocess
from pathlib import Path

import pytest
from PIL import Image

from src.vision import frames

URL = "https://example.invalid/game.mp4"


@pytest.fixture
def fake_capture(monkeypatch):
    calls = []
    monkeypatch.setattr(frames, "_legacy_receipts", lambda root: {})
    monkeypatch.setattr(frames.shutil, "which", lambda ffmpeg: ffmpeg)

    def run(command, **kwargs):
        calls.append(command)
        Image.new("RGB", (16, 16), (20, 40, 60)).save(command[-1])
        return subprocess.CompletedProcess(command, 0, stdout="", stderr="")

    monkeypatch.setattr(frames.subprocess, "run", run)
    return calls


def test_capture_receipt_reuse_and_source_isolation(tmp_path, fake_capture):
    first = frames.resolve_frame(URL, 5.001, tmp_path, "scan")
    assert first.name == "scan_5.001.jpg"
    command = fake_capture[0]
    assert command[command.index("-ss") + 1] == "5.001"
    assert command[command.index("-i") + 1] == URL
    receipt = json.loads(first.with_suffix(".jpg.json").read_text())
    assert receipt["frame_seconds"] == 5.001
    assert receipt["sha256"] == frames._sha256(first.read_bytes())
    assert frames.resolve_frame(URL, 5.001, tmp_path, "another", no_grab=True) == first
    assert len(fake_capture) == 1
    second = frames.resolve_frame(URL + "?other-edit", 5.001, tmp_path, "scan")
    assert first.parent != second.parent and len(fake_capture) == 2
    assert first.exists() and second.exists()


def test_unbound_legacy_file_is_preserved_and_never_silently_retagged(tmp_path, fake_capture):
    old = tmp_path / "scan_5.00.jpg"
    old.write_bytes(b"unproven pixels")
    with pytest.raises(FileNotFoundError, match="verified"):
        frames.resolve_frame(URL, 5.0, tmp_path, "scan", no_grab=True)
    with pytest.raises(FileExistsError, match="unverified"):
        frames.grab_frame(URL, 5.0, old)
    new = frames.resolve_frame(URL, 5.0, tmp_path, "scan")
    assert new.parent != old.parent
    assert old.read_bytes() == b"unproven pixels"
    assert not old.with_suffix(".jpg.json").exists()


@pytest.mark.parametrize("change", ["source", "time", "pixels", "missing", "malformed"])
def test_modified_cache_is_rejected_without_overwriting_it(tmp_path, fake_capture, change):
    path = frames.resolve_frame(URL, 10.0, tmp_path, "scan")
    receipt_path = path.with_suffix(".jpg.json")
    receipt = json.loads(receipt_path.read_text())
    if change == "pixels":
        path.write_bytes(b"changed pixels")
    elif change == "missing":
        receipt_path.unlink()
    elif change == "malformed":
        receipt_path.write_text("{not json}")
    else:
        receipt["media_url" if change == "source" else "frame_seconds"] = (
            URL + "/other" if change == "source" else 11.0
        )
        receipt_path.write_text(json.dumps(receipt))
    before = path.read_bytes()
    with pytest.raises(FileNotFoundError, match="verified"):
        frames.resolve_frame(URL, 10.0, tmp_path, "scan", no_grab=True)
    with pytest.raises(FileExistsError, match="unverified"):
        frames.resolve_frame(URL, 10.0, tmp_path, "scan")
    assert path.read_bytes() == before and len(fake_capture) == 1


def test_millisecond_names_do_not_collide(tmp_path, fake_capture):
    first = frames.resolve_frame(URL, 5.001, tmp_path, "scan")
    second = frames.resolve_frame(URL, 5.002, tmp_path, "scan")
    assert first != second and first.exists() and second.exists()
    with pytest.raises(ValueError, match="millisecond"):
        frames.resolve_frame(URL, 5.0014, tmp_path, "scan")


@pytest.mark.parametrize("time", [True, -1, float("nan"), float("inf")])
def test_invalid_time_never_captures(tmp_path, fake_capture, time):
    with pytest.raises(ValueError, match="Playback time"):
        frames.resolve_frame(URL, time, tmp_path, "scan")
    assert not fake_capture


def test_legacy_cache_requires_committed_exact_source_time_and_hash(tmp_path, monkeypatch):
    image = tmp_path / "evalset_5.00.jpg"
    image.write_bytes(b"historically recorded JPEG")
    document = {
        "source": {"media_url": URL},
        "frame_cache": {
            "frames": [
                {
                    "frame_seconds": 5.0,
                    "path": "outputs/frames/evalset_5.00.jpg",
                    "sha256": frames._sha256(image.read_bytes()),
                }
            ]
        },
    }
    calls = []

    def committed_provenance(command, **kwargs):
        calls.append(command)
        assert command[:2] == ["git", "show"] and command[2].startswith("HEAD:")
        return subprocess.CompletedProcess(command, 0, stdout=json.dumps(document).encode())

    monkeypatch.setattr(frames.subprocess, "run", committed_provenance)
    frames._legacy_receipts.cache_clear()
    try:
        assert (
            frames.resolve_frame(URL, 5.0, tmp_path, "other", no_grab=True, root=tmp_path) == image
        )
        assert len(calls) == 4
        for url, t in [(URL + "?other", 5.0), (URL, 5.001)]:
            with pytest.raises(FileNotFoundError):
                frames.resolve_frame(url, t, tmp_path, "scan", no_grab=True, root=tmp_path)
        image.write_bytes(b"tampered")
        with pytest.raises(FileNotFoundError):
            frames.resolve_frame(URL, 5.0, tmp_path, "scan", no_grab=True, root=tmp_path)
        assert len(calls) == 4  # provenance is loaded once, images are rehashed on every reuse
    finally:
        frames._legacy_receipts.cache_clear()


def test_failed_capture_does_not_publish_a_receipt_or_replace_old_files(tmp_path, monkeypatch):
    monkeypatch.setattr(frames.shutil, "which", lambda ffmpeg: ffmpeg)

    def failed(command, **kwargs):
        Path(command[-1]).write_bytes(b"partial")
        return subprocess.CompletedProcess(command, 1, stdout="", stderr="partial file")

    monkeypatch.setattr(frames.subprocess, "run", failed)
    path = frames.frame_path(tmp_path, "scan", 1.0, URL)
    with pytest.raises(RuntimeError, match="failed 2 times"):
        frames.grab_frame(URL, 1.0, path, attempts=2)
    assert not path.exists() and not path.with_suffix(".jpg.json").exists()
    assert list(path.parent.iterdir()) == []


def test_receipt_cache_remains_usable_without_git(tmp_path, monkeypatch):
    def missing_git(command, **kwargs):
        raise FileNotFoundError("Git not installed")

    monkeypatch.setattr(frames.subprocess, "run", missing_git)
    path = frames.frame_path(tmp_path, "scan", 2.0, URL)
    path.parent.mkdir()
    path.write_bytes(b"known frame bytes")
    path.with_suffix(".jpg.json").write_text(
        json.dumps(
            {
                "schema": frames.CACHE_SCHEMA,
                "media_url": URL,
                "frame_seconds": 2.0,
                "sha256": frames._sha256(path.read_bytes()),
            }
        )
    )
    frames._legacy_receipts.cache_clear()
    try:
        assert frames.resolve_frame(URL, 2.0, tmp_path, "scan", no_grab=True, root=tmp_path) == path
    finally:
        frames._legacy_receipts.cache_clear()

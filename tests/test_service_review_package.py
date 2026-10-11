"""Exercise private package boundaries with invented data, never teammate raw responses."""

import hashlib
import json
import shutil
import subprocess
import sys
from zipfile import ZipFile

import pytest

from scripts.build_service_review import ROOT, build_review
from scripts.inspect_service_game import AuditInputError
from src.integration.service_game import ServiceGameError


@pytest.fixture
def source(tmp_path):
    payload = json.loads(
        (ROOT / "docs/examples/service_game_v2_synthetic.json").read_text(encoding="utf-8")
    )
    payload["cutoff"] = None
    payload["game"]["date_kst"] = "2026-10-06"
    for pitch in payload["pitches"]:
        if pitch.get("actual") is not None:
            pitch["actual"]["catcher_setup"] = None
    path = tmp_path / "source.json"
    path.write_text(json.dumps(payload), encoding="utf-8")
    return path


def test_build_preserves_input_and_records_exact_assets(source, tmp_path):
    original = source.read_bytes()
    target = tmp_path / "private"
    receipt = build_review(source, target, input_kind="synthetic")
    assert source.read_bytes() == original
    assert receipt["source_sha256"] == hashlib.sha256(original).hexdigest()
    report = json.loads((target / "review-data.json").read_text(encoding="utf-8"))
    assert report["source"]["input_kind"] == "synthetic"
    assert report["profile"] == "teammate_export_20261009_v1"
    assert receipt["public_distribution"] is False
    assert receipt["live_validation"] is False
    for name, digest in receipt["assets_sha256"].items():
        assert hashlib.sha256((target / name).read_bytes()).hexdigest() == digest
    assert set(p.name for p in target.iterdir()) == {
        "index.html",
        "review.js",
        "style.css",
        "review-data.json",
        "receipt.json",
        "PRIVATE.txt",
        "review-media.json",
        "launch_review.py",
        "START_WINDOWS.cmd",
        "START_MAC.command",
    }


def test_existing_output_is_untouched(source, tmp_path):
    target = tmp_path / "existing"
    target.mkdir()
    marker = target / "keep.txt"
    marker.write_text("KEEP", encoding="utf-8")
    with pytest.raises(AuditInputError):
        build_review(source, target, input_kind="synthetic")
    assert list(target.iterdir()) == [marker]
    assert marker.read_text() == "KEEP"


def test_invalid_input_creates_no_package(source, tmp_path):
    source.write_text('{"schema":"wrong"}', encoding="utf-8")
    target = tmp_path / "not-created"
    with pytest.raises(ServiceGameError):
        build_review(source, target, input_kind="provided_export")
    assert not target.exists()


@pytest.mark.parametrize("directory", ["web", "docs"])
def test_public_directories_rejected_before_writes(source, directory):
    target = ROOT / directory / "must-not-create-private-service-review"
    with pytest.raises(AuditInputError, match="outside web and docs"):
        build_review(source, target, input_kind="provided_export")
    assert not target.exists()


def test_private_review_javascript_contract():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js not installed")
    result = subprocess.run(
        [node, "--test", str(ROOT / "web/service-review/review.test.cjs")],
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=45,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_oversized_normalized_report_creates_no_package(source, tmp_path, monkeypatch):
    from scripts import build_service_review

    monkeypatch.setattr(build_service_review, "MAX_INPUT_BYTES", 20)
    target = tmp_path / "not-created-too-large"
    with pytest.raises(AuditInputError, match="viewer 5 MiB limit"):
        build_review(source, target, input_kind="synthetic")
    assert not target.exists()


def test_zip_relocation_and_isolated_stdlib_launch(source, tmp_path):
    target = tmp_path / "package"
    archive_path = tmp_path / "review.zip"
    build_review(source, target, input_kind="synthetic", zip_path=archive_path)
    relocated = tmp_path / "another folder"
    with ZipFile(archive_path) as archive:
        assert archive.testzip() is None
        assert "source.json" not in archive.namelist()
        assert archive.getinfo("START_MAC.command").external_attr >> 16 & 0o111
        archive.extractall(relocated)
    for original in target.iterdir():
        assert original.read_bytes() == (relocated / original.name).read_bytes()
    result = subprocess.run(
        [sys.executable, "-I", str(relocated / "launch_review.py"), "--check"],
        cwd=tmp_path,
        capture_output=True,
        timeout=15,
    )
    assert result.returncode == 0, result.stdout + result.stderr


def test_existing_zip_prevents_output_creation(source, tmp_path):
    archive_path = tmp_path / "keep.zip"
    archive_path.write_bytes(b"KEEP")
    target = tmp_path / "package"
    with pytest.raises(AuditInputError):
        build_review(source, target, input_kind="synthetic", zip_path=archive_path)
    assert archive_path.read_bytes() == b"KEEP"
    assert not target.exists()


def test_video_map_is_bound_to_source_before_output(source, tmp_path):
    target = tmp_path / "wrong-source"
    with pytest.raises(AuditInputError, match="different source snapshot"):
        build_review(source, target, input_kind="synthetic", include_video=True)
    assert not target.exists()


@pytest.fixture
def bound_media(source, tmp_path, monkeypatch):
    from scripts import build_service_review as module

    payload = json.loads(source.read_text())
    game = payload["game"]["game_pk"]
    # Invented local bytes test integrity/packaging, not video decoding or real provenance.
    root = tmp_path / "assets"
    (root / "media").mkdir(parents=True)
    video, poster = b"invented-mp4", b"invented-jpeg"
    (root / "media/clip.mp4").write_bytes(video)
    (root / "media/clip.jpg").write_bytes(poster)
    binding = {
        "schema": "pitcheezy-service-review-media-v1",
        "game_pk": game,
        "source_sha256": hashlib.sha256(source.read_bytes()).hexdigest(),
        "clips": [
            {
                "pitch_key": payload["pitches"][0]["key"],
                "play_id": "00000000-0000-4000-8000-000000000001",
                "video": "media/clip.mp4",
                "poster": "media/clip.jpg",
                "video_sha256": hashlib.sha256(video).hexdigest(),
                "poster_sha256": hashlib.sha256(poster).hexdigest(),
                "duration_seconds": 1.0,
            }
        ],
    }
    path = tmp_path / "binding.json"
    path.write_text(json.dumps(binding), encoding="utf-8")
    monkeypatch.setattr(module, "MEDIA_SOURCE", root)
    monkeypatch.setattr(module, "MEDIA_MANIFEST", path)
    return root, path


def test_bound_media_is_copied_with_hashes(source, tmp_path, bound_media):
    root, _ = bound_media
    target = tmp_path / "with-video"
    receipt = build_review(source, target, input_kind="synthetic", include_video=True)
    assert receipt["clip_count"] == 1
    for name in ("clip.mp4", "clip.jpg"):
        assert (target / "media" / name).read_bytes() == (root / "media" / name).read_bytes()


def test_changed_media_rejected_without_creating_package(source, tmp_path, bound_media):
    root, _ = bound_media
    (root / "media/clip.mp4").write_bytes(b"changed")
    target = tmp_path / "not-created-video"
    with pytest.raises(AuditInputError, match="Media hash"):
        build_review(source, target, input_kind="synthetic", include_video=True)
    assert not target.exists()

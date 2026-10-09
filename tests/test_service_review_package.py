"""Exercise private package boundaries with invented data, never teammate raw responses."""

import hashlib
import json
import shutil
import subprocess

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

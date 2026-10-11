"""Operational transfer bundles preserve only allowlisted, verified artifact bytes."""

import hashlib
import importlib.util
import json
import os
import subprocess
import sys
from pathlib import Path
from zipfile import BadZipFile, ZipFile

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/build_operational_bundle.py"
SPEC = importlib.util.spec_from_file_location("operational_bundle", SCRIPT)
bundle = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(bundle)

COMMIT = "a" * 40
EXPECTED_FILES = {
    "data/operational_20260921_v2/dataset_manifest.json",
    "data/operational_20260921_v2/feature_builder.pkl",
    "data/operational_20260921_v2/run_value_model.npz",
    "outputs/operational_20260921/evaluation/selection.json",
    "outputs/operational_20260921/evaluation/probability_report.json",
    "outputs/operational_20260921/evaluation/empirical.pkl",
    "outputs/operational_20260921/mlp135_seed42/manifest.json",
    "outputs/operational_20260921/mlp135_seed42/best.pt",
    "outputs/operational_20260921/mlp135_seed43/manifest.json",
    "outputs/operational_20260921/mlp135_seed43/best.pt",
    "outputs/operational_20260921/mlp135_seed44/manifest.json",
    "outputs/operational_20260921/mlp135_seed44/best.pt",
    "outputs/operational_20260921/policy_nuisance_v2/manifest.json",
    "outputs/operational_20260921/policy_nuisance_v2/propensity.txt",
}
REJECTIONS = (ValueError, OSError)


def evidence(data):
    return {"bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}


def save_inventory(case):
    case["inventory"].write_text(json.dumps(case["document"]), encoding="utf-8")


def build(case, out=None, commit=COMMIT):
    return bundle.build(case["inventory"], case["root"], out or case["out"], commit)


@pytest.fixture
def artifacts(tmp_path):
    root = tmp_path / "artifacts"
    originals = {}
    rows = []
    for index, relative in enumerate(sorted(EXPECTED_FILES)):
        # Deliberately not valid pickle, checkpoint, NPZ or JSON content.
        data = f"opaque synthetic payload {index}: {relative}\r\n".encode()
        target = root / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
        originals[relative] = data
        rows.append(
            {
                "path_alias": "LEGACY_PROJECT",
                "relative_path": relative,
                "observed": True,
                **evidence(data),
            }
        )
    case = {
        "root": root,
        "inventory": tmp_path / "inventory.json",
        "document": {"schema": "pitcheezy_external_inventory_v1", "artifacts": rows},
        "originals": originals,
        "out": tmp_path / "runtime.zip",
    }
    save_inventory(case)
    return case


def test_roundtrip_exact_members_and_extracted_identity(artifacts, tmp_path):
    assert len(bundle.REQUIRED_FILES) == 14
    assert set(bundle.REQUIRED_FILES) == EXPECTED_FILES
    result = build(artifacts)
    assert result["files"] == 14
    assert result["source_commit"] == COMMIT
    assert result["archive_bytes"] == artifacts["out"].stat().st_size
    assert result["archive_sha256"] == evidence(artifacts["out"].read_bytes())["sha256"]
    manifest = bundle.verify_archive(artifacts["out"])
    assert manifest["schema"] == "pitcheezy_operational_bundle_v1"
    assert manifest["source_repository"] == "Pitcheezy/transition-models"
    assert manifest["source_commit"] == COMMIT
    assert set(manifest["files"]) == EXPECTED_FILES
    assert manifest["inventory"] == {
        "schema": "pitcheezy_external_inventory_v1",
        **evidence(artifacts["inventory"].read_bytes()),
    }
    extracted = tmp_path / "extracted"
    with ZipFile(artifacts["out"]) as archive:
        expected = EXPECTED_FILES | {bundle.MANIFEST, bundle.GUIDE}
        assert set(archive.namelist()) == expected
        assert len(archive.namelist()) == 16
        archive.extractall(extracted)
        guide = archive.read(bundle.GUIDE).decode("utf-8")
        assert any("\uac00" <= char <= "\ud7a3" for char in guide)
        assert manifest["guide"] == evidence(archive.read(bundle.GUIDE))
        for relative, data in artifacts["originals"].items():
            assert archive.read(relative) == data
            assert (extracted / relative).read_bytes() == data
            assert manifest["files"][relative] == evidence(data)
        public_metadata = archive.read(bundle.MANIFEST) + archive.read(bundle.GUIDE)
        assert str(tmp_path).encode() not in public_metadata
        assert tmp_path.as_posix().encode() not in public_metadata


@pytest.mark.parametrize("change", ["corrupt", "missing"])
def test_bad_source_rejected_before_output(artifacts, change):
    relative = "data/operational_20260921_v2/feature_builder.pkl"
    target = artifacts["root"] / relative
    if change == "corrupt":
        original = target.read_bytes()
        target.write_bytes(b"X" + original[1:])
    else:
        target.unlink()
    with pytest.raises(REJECTIONS):
        build(artifacts)
    assert not artifacts["out"].exists()


def test_existing_archive_is_never_overwritten(artifacts):
    artifacts["out"].write_bytes(b"existing destination must survive")
    original = artifacts["out"].read_bytes()
    with pytest.raises(FileExistsError):
        build(artifacts)
    assert artifacts["out"].read_bytes() == original


def test_unrelated_secret_and_image_are_never_included(artifacts):
    for relative in ("private/.env", "outputs/unrelated/reviewer_frame.png"):
        target = artifacts["root"] / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"do not transfer this unrelated content")
        # Unrelated entries need not even be valid artifact records.
        artifacts["document"]["artifacts"].append(
            {"path_alias": "LEGACY_PROJECT", "relative_path": relative}
        )
    save_inventory(artifacts)
    build(artifacts)
    with ZipFile(artifacts["out"]) as archive:
        assert set(archive.namelist()) == EXPECTED_FILES | {bundle.MANIFEST, bundle.GUIDE}
        assert all(b"do not transfer" not in archive.read(name) for name in archive.namelist())


def test_unknown_operational_artifact_rejected(artifacts):
    artifacts["document"]["artifacts"].append(
        {
            "path_alias": "LEGACY_PROJECT",
            "relative_path": "outputs/operational_20260921/unreviewed.pt",
            "observed": True,
            **evidence(b"unreviewed"),
        }
    )
    save_inventory(artifacts)
    with pytest.raises(REJECTIONS):
        build(artifacts)
    assert not artifacts["out"].exists()


def test_duplicate_selected_inventory_entry_rejected(artifacts):
    artifacts["document"]["artifacts"].append(dict(artifacts["document"]["artifacts"][0]))
    save_inventory(artifacts)
    with pytest.raises(REJECTIONS):
        build(artifacts)
    assert not artifacts["out"].exists()


@pytest.mark.parametrize("path", ["../outside.pkl", "data/operational_20260921_v2/../outside.pkl"])
def test_inventory_path_escape_rejected(artifacts, path):
    artifacts["document"]["artifacts"][0]["relative_path"] = path
    save_inventory(artifacts)
    with pytest.raises(REJECTIONS):
        build(artifacts)
    assert not artifacts["out"].exists()


@pytest.mark.parametrize(
    ("field", "invalid"),
    [("bytes", True), ("bytes", -1), ("sha256", "A" * 64), ("observed", False)],
)
def test_selected_inventory_evidence_must_be_strict(artifacts, field, invalid):
    artifacts["document"]["artifacts"][0][field] = invalid
    save_inventory(artifacts)
    with pytest.raises(REJECTIONS):
        build(artifacts)
    assert not artifacts["out"].exists()


def test_source_file_symlink_rejected(artifacts, tmp_path):
    relative = "data/operational_20260921_v2/feature_builder.pkl"
    target = artifacts["root"] / relative
    outside = tmp_path / "outside.pkl"
    target.rename(outside)
    try:
        target.symlink_to(outside)
    except OSError:
        pytest.skip("This host does not permit creating file symlinks")
    with pytest.raises(REJECTIONS):
        build(artifacts)
    assert not artifacts["out"].exists()


def test_source_parent_link_rejected(artifacts, tmp_path):
    link = artifacts["root"] / "data"
    outside = tmp_path / "outside_data"
    link.rename(outside)
    try:
        link.symlink_to(outside, target_is_directory=True)
    except OSError:
        if os.name != "nt":
            pytest.skip("This host does not permit creating directory links")
        # Windows junctions are reparse points and often need no elevation.
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(outside)],
            capture_output=True,
            check=False,
        )
        if result.returncode:
            pytest.skip("This host does not permit creating directory links or junctions")
    with pytest.raises(REJECTIONS):
        build(artifacts)
    assert not artifacts["out"].exists()


def test_same_inputs_produce_identical_archive_bytes(artifacts, tmp_path):
    build(artifacts)
    second = tmp_path / "second.zip"
    # Filesystem metadata must not leak into the reproducible archive.
    for relative in EXPECTED_FILES:
        os.utime(artifacts["root"] / relative, (1_000_000_000, 1_000_000_000))
    build(artifacts, out=second)
    assert second.read_bytes() == artifacts["out"].read_bytes()
    with ZipFile(second) as archive:
        assert archive.namelist() == sorted(archive.namelist())
        assert all(info.date_time == (1980, 1, 1, 0, 0, 0) for info in archive.infolist())


@pytest.mark.parametrize("change", ["corrupt", "unlisted", "missing"])
def test_archive_payload_or_membership_changes_rejected(artifacts, tmp_path, change):
    build(artifacts)
    altered = tmp_path / "altered.zip"
    selected = "data/operational_20260921_v2/feature_builder.pkl"
    with ZipFile(artifacts["out"]) as original, ZipFile(altered, "w") as output:
        for info in original.infolist():
            if info.filename == selected and change == "missing":
                continue
            data = original.read(info.filename)
            if info.filename == selected and change == "corrupt":
                data = b"X" + data[1:]
            output.writestr(info, data)
        if change == "unlisted":
            output.writestr("private/.env", b"unexpected payload")
    with pytest.raises(REJECTIONS):
        bundle.verify_archive(altered)


def test_non_zip_rejected(tmp_path):
    archive = tmp_path / "bad.zip"
    archive.write_bytes(b"not a zip archive")
    with pytest.raises((*REJECTIONS, BadZipFile)):
        bundle.verify_archive(archive)


def test_standalone_cli_build_and_check_without_site_packages(artifacts, tmp_path):
    command = [sys.executable, "-I", "-S", "-B", str(SCRIPT)]
    result = subprocess.run(
        [
            *command,
            "build",
            "--inventory",
            str(artifacts["inventory"]),
            "--artifact-root",
            str(artifacts["root"]),
            "--out",
            str(artifacts["out"]),
            "--source-commit",
            COMMIT,
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(result.stdout)["files"] == 14
    checked = subprocess.run(
        [*command, "check", str(artifacts["out"])],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(checked.stdout) == {
        "status": "verified",
        "files": 14,
        "source_commit": COMMIT,
    }
    assert result.stderr == checked.stderr == ""

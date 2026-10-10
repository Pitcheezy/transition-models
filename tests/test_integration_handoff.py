"""Source handoffs preserve pinned Git bytes and exclude non-source artifacts."""

import hashlib
import importlib.util
import json
import shutil
import subprocess
import sys
from pathlib import Path
from zipfile import ZipFile

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/build_integration_handoff.py"
SPEC = importlib.util.spec_from_file_location("integration_handoff", SCRIPT)
handoff = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(handoff)


def git(root, *args):
    return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE)


@pytest.fixture
def repository(tmp_path):
    if shutil.which("git") is None:
        pytest.skip("A local Git executable is required for commit-byte tests")
    root = tmp_path / "repository"
    root.mkdir()
    git(root, "init", "--quiet")
    git(root, "config", "user.name", "Synthetic Test")
    git(root, "config", "user.email", "synthetic@example.invalid")
    git(root, "config", "core.autocrlf", "false")
    return root


def commit_selection(root, content=None, extra=None):
    """Create only small synthetic source files in an isolated temporary repository."""
    files = {"example.py": b"value = 1\r\n# exact Git bytes\r\n"}
    files.update(content or {})
    files["scripts/build_integration_handoff.py"] = SCRIPT.read_bytes()
    paths = [*files, handoff.CONFIG]
    rows = [
        {"path": path, "role": "synthetic_test", "distribution": "source_only"} for path in paths
    ]
    rows.extend(extra or [])
    config = {
        "schema": "pitcheezy_handoff_selection_v1",
        "repository": handoff.REPOSITORY,
        "files": rows,
        "exclusions": ["MLB media and model weights"],
    }
    files[handoff.CONFIG] = json.dumps(config).encode("utf-8")
    for relative, data in files.items():
        path = root / relative
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(data)
    git(root, "add", ".")
    git(root, "commit", "--quiet", "-m", "Synthetic source selection")
    return git(root, "rev-parse", "HEAD").decode().strip(), files


def test_pinned_bytes_zip_roundtrip_and_standalone_check(repository, tmp_path):
    commit, originals = commit_selection(repository)
    (repository / "example.py").write_bytes(b"uncommitted working-tree bytes\n")
    out = tmp_path / "handoff"
    result = handoff.build(repository, commit, out)
    assert result["source_commit"] == commit
    assert result["files"] == len(originals)
    manifest = handoff.verify_bundle(out)
    assert manifest["source_repository"] == handoff.REPOSITORY
    assert handoff.MANIFEST not in manifest["files"]
    assert manifest["exclusions"] == ["MLB media and model weights"]
    for relative, data in originals.items():
        assert (out / relative).read_bytes() == data
        assert manifest["files"][relative]["sha256"] == hashlib.sha256(data).hexdigest()
    extracted = tmp_path / "extracted"
    with ZipFile(result["archive"]) as archive:
        assert set(archive.namelist()) == {f"handoff/{p}" for p in [*originals, handoff.MANIFEST]}
        archive.extractall(extracted)
    portable = extracted / "handoff"
    checked = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            str(portable / "scripts/build_integration_handoff.py"),
            "check",
            str(portable),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(checked.stdout)["status"] == "verified"
    assert not (portable / ".git").exists()


@pytest.mark.parametrize("change", ["tamper", "extra", "missing", "traversal"])
def test_changed_inventory_is_rejected(repository, tmp_path, change):
    commit, _ = commit_selection(repository)
    out = tmp_path / "handoff"
    handoff.build(repository, commit, out)
    if change == "tamper":
        (out / "example.py").write_bytes(b"changed\n")
    elif change == "extra":
        (out / "unexpected.txt").write_text("extra")
    elif change == "missing":
        (out / "example.py").unlink()
    else:
        manifest = json.loads((out / handoff.MANIFEST).read_bytes())
        manifest["files"]["../escape.py"] = manifest["files"].pop("example.py")
        (out / handoff.MANIFEST).write_text(json.dumps(manifest))
    with pytest.raises(ValueError):
        handoff.verify_bundle(out)


@pytest.mark.parametrize("existing", ["folder", "zip"])
def test_existing_destination_is_preserved(repository, tmp_path, existing):
    commit, _ = commit_selection(repository)
    out = tmp_path / "handoff"
    if existing == "folder":
        out.mkdir()
        marker = out / "existing.txt"
    else:
        marker = tmp_path / "handoff.zip"
    marker.write_bytes(b"preserve me")
    with pytest.raises(FileExistsError):
        handoff.build(repository, commit, out)
    assert marker.read_bytes() == b"preserve me"


@pytest.mark.parametrize(
    ("relative", "data"),
    [
        ("media.mp4", b"synthetic media"),
        ("weights.pt", b"synthetic weights"),
        ("pointer.txt", handoff.LFS_HEADER + b"\noid sha256:" + b"0" * 64 + b"\nsize 12\n"),
    ],
)
def test_media_weights_and_lfs_rejected_before_output(repository, tmp_path, relative, data):
    commit, _ = commit_selection(repository, {relative: data})
    out = tmp_path / "handoff"
    with pytest.raises(ValueError):
        handoff.build(repository, commit, out)
    assert not out.exists()
    assert not out.with_suffix(".zip").exists()


def test_git_symlink_rejected_before_output(repository, tmp_path):
    commit_selection(repository)
    target = (
        subprocess.check_output(
            ["git", "-C", str(repository), "hash-object", "-w", "--stdin"], input=b"example.py"
        )
        .decode()
        .strip()
    )
    git(repository, "update-index", "--cacheinfo", f"120000,{target},example.py")
    git(repository, "commit", "--quiet", "-m", "Synthetic Git symlink")
    commit = git(repository, "rev-parse", "HEAD").decode().strip()
    with pytest.raises(ValueError, match="regular Git blob"):
        handoff.build(repository, commit, tmp_path / "handoff")
    assert not (tmp_path / "handoff").exists()


def test_extracted_symlink_rejected(repository, tmp_path):
    commit, _ = commit_selection(repository)
    out = tmp_path / "handoff"
    handoff.build(repository, commit, out)
    link = out / "linked.txt"
    try:
        link.symlink_to(tmp_path / "external.txt")
    except OSError:
        pytest.skip("This host does not permit creating test symlinks")
    with pytest.raises(ValueError, match="Links"):
        handoff.verify_bundle(out)


@pytest.mark.parametrize(
    "relative", ["/absolute.py", "../parent.py", "a/../b.py", "a\\b.py", "a//b.py"]
)
def test_invalid_selection_paths_rejected(repository, tmp_path, relative):
    commit, _ = commit_selection(
        repository, extra=[{"path": relative, "role": "test", "distribution": "source_only"}]
    )
    with pytest.raises(ValueError):
        handoff.build(repository, commit, tmp_path / "handoff")
    assert not (tmp_path / "handoff").exists()


def test_selected_source_builds_current_review_without_repository_imports(tmp_path):
    """Catch missing transitive files using only the actual source selection in isolation."""
    root = SCRIPT.parents[1]
    selection, _ = handoff._selection((root / handoff.CONFIG).read_bytes())
    exported = tmp_path / "source-only"
    for relative in selection:
        target = exported / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes((root / relative).read_bytes())
    originals = {path: (exported / path).read_bytes() for path in selection}
    fixture = exported / "docs/examples/service_game_v2_export_synthetic.json"
    output = tmp_path / "private-review"
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            "-X",
            "utf8",
            str(exported / "scripts/build_service_review.py"),
            "--input",
            str(fixture),
            "--source-kind",
            "synthetic",
            "--out-dir",
            str(output),
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=30,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    receipt = json.loads(result.stdout)
    assert receipt["input_kind"] == "synthetic"
    assert receipt["profile"] == "teammate_export_20261009_v1"
    assert receipt["clip_count"] == 0
    assert {
        key: receipt["summary"][key] for key in ("pitches", "ready", "unsupported", "missing")
    } == {
        "pitches": 3,
        "ready": 1,
        "unsupported": 1,
        "missing": 1,
    }
    checked = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            "-X",
            "utf8",
            str(output / "launch_review.py"),
            "--check",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=15,
    )
    assert checked.returncode == 0, checked.stdout + checked.stderr
    assert not (exported / ".git").exists()
    assert {p.relative_to(exported).as_posix() for p in exported.rglob("*") if p.is_file()} == set(
        selection
    )
    assert all((exported / path).read_bytes() == data for path, data in originals.items())

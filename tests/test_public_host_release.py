"""Offline release checks must fail closed without executing supplied artifacts."""

import json
import os
import stat
import subprocess
import sys
import zipfile
from pathlib import Path

import pytest

from src.operations import release_bundle as rb

ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture
def provenance():
    return {
        "frontend": {
            "repository": "SongRoute/pitcheezy",
            "commit": "1" * 40,
            "build_command": ["npm", "run", "build:public"],
            "tools": {"node": "24.1.0", "npm": "11.3.0"},
        },
        "contracts": [{"name": "public-publish", "version": "synthetic", "commit": "2" * 40}],
    }


@pytest.fixture
def payload():
    return {
        **{"host/" + name: b"synthetic host fixture\n" for name in rb.HOST_FILES},
        "public/index.html": b"<!doctype html><title>Synthetic release test</title>",
        "public/assets/app.js": b"console.info('synthetic');",
    }


@pytest.fixture
def files(payload, provenance):
    return rb.assemble(payload, provenance, "3" * 40)


def archive_path(tmp_path, files):
    target = tmp_path / "release.zip"
    target.write_bytes(rb.make_zip(files))
    return target


def test_reproducible_bytes_and_receipt(tmp_path, files):
    first = rb.make_zip(files)
    assert first == rb.make_zip(dict(reversed(list(files.items()))))
    path = archive_path(tmp_path, files)
    report = rb.check_bundle(path)
    assert report["bundle_sha256"] == rb.digest(first)
    assert report["manifest_sha256"] == rb.digest(files[rb.MANIFEST])
    assert report["files"] == len(rb.HOST_FILES) + 2
    assert report["deployable"] is False
    assert report["mode"] == "synthetic"
    with zipfile.ZipFile(path) as archive:
        for item in archive.infolist():
            assert item.date_time == (1980, 1, 1, 0, 0, 0)
            assert item.compress_type == zipfile.ZIP_STORED


@pytest.mark.parametrize("mutation", ["change", "missing", "extra"])
def test_hash_inventory_rejects_changes(tmp_path, files, mutation):
    changed = dict(files)
    if mutation == "change":
        changed["public/index.html"] += b"\n"
    elif mutation == "missing":
        del changed["public/assets/app.js"]
    else:
        changed["public/assets/extra.js"] = b"extra"
    with pytest.raises(rb.BundleError, match="inventory_mismatch"):
        rb.check_bundle(archive_path(tmp_path, changed))


@pytest.mark.parametrize(
    "name",
    [
        "../x.js",
        "/x.js",
        "a//x.js",
        "a/./x.js",
        "a\\x.js",
        "a:x.js",
        "%2e.js",
        "a/NUL.txt",
        "COM1.js",
        "a./x.js",
        ".env",
        "한글.js",
        "a/" + "x" * 241,
    ],
)
def test_portable_paths_reject_ambiguous_names(name):
    with pytest.raises(rb.BundleError):
        rb.safe_path(name)


@pytest.mark.parametrize(
    "name",
    [
        "public/a.mp4",
        "public/a.zip",
        "public/a.map",
        "public/a.sqlite",
        "public/.env",
        "public/package.json",
        "public/wrangler.jsonc",
        "public/credentials.json",
        "public/api/state.json",
        "public/v1/health.json",
        "host/extra.mjs",
    ],
)
def test_private_or_reserved_files_rejected(payload, provenance, name):
    payload[name] = b"synthetic"
    with pytest.raises(rb.BundleError):
        rb.assemble(payload, provenance, "3" * 40)


def test_lfs_and_limited_secret_markers_rejected(payload, provenance):
    for raw in (rb.LFS_PREFIX + b"\noid sha256:" + b"0" * 64, b"-----BEGIN PRIVATE KEY-----"):
        payload["public/assets/app.js"] = raw
        with pytest.raises(rb.BundleError, match="lfs_pointer|possible_secret"):
            rb.assemble(payload, provenance, "3" * 40)


def test_case_and_file_directory_conflicts_rejected(payload, provenance):
    payload["public/INDEX.html"] = b"collision"
    with pytest.raises(rb.BundleError, match="case_collision"):
        rb.assemble(payload, provenance, "3" * 40)
    del payload["public/INDEX.html"]
    payload["public/assets/app.js/sub.js"] = b"collision"
    with pytest.raises(rb.BundleError, match="path_conflict"):
        rb.assemble(payload, provenance, "3" * 40)


@pytest.mark.parametrize(
    "change", ["deployable", "size_bool", "hash", "host", "contract", "unknown"]
)
def test_false_manifest_claims_rejected(files, change):
    manifest = json.loads(files[rb.MANIFEST])
    if change == "deployable":
        manifest["deployable"] = True
    elif change == "size_bool":
        manifest["files"][0]["bytes"] = True
    elif change == "hash":
        manifest["files"][0]["sha256"] = "0" * 64
    elif change == "host":
        manifest["host"]["commit"] = "main"
    elif change == "contract":
        manifest["contracts"][0]["commit"] = "latest"
    else:
        manifest["surprise"] = True
    files[rb.MANIFEST] = rb.canonical(manifest)
    with pytest.raises(rb.BundleError):
        rb.verify_files(files)


def test_duplicate_json_keys_rejected(files):
    files[rb.MANIFEST] = b'{"schema":"x","schema":"y"}'
    with pytest.raises(rb.BundleError, match="duplicate_json_key"):
        rb.verify_files(files)


@pytest.mark.parametrize("kind", ["duplicate", "symlink", "directory", "compressed", "traversal"])
def test_unsafe_zip_entries_rejected(tmp_path, files, kind):
    path = archive_path(tmp_path, files)
    with zipfile.ZipFile(path, "a") as archive:
        if kind == "duplicate":
            with pytest.warns(UserWarning, match="Duplicate name"):
                archive.writestr(rb.MANIFEST, files[rb.MANIFEST])
        else:
            name = "../escape.js" if kind == "traversal" else "public/extra.js"
            info = zipfile.ZipInfo(name)
            info.create_system = 3
            mode = stat.S_IFLNK if kind == "symlink" else stat.S_IFREG
            if kind == "directory":
                mode = stat.S_IFDIR
                info.filename += "/"
            info.external_attr = (mode | 0o644) << 16
            if kind == "compressed":
                info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, b"synthetic")
    with pytest.raises(rb.BundleError):
        rb.check_bundle(path)


def test_corrupt_zip_fails(tmp_path, files):
    path = archive_path(tmp_path, files)
    raw = path.read_bytes()
    changed = raw.replace(b"synthetic host fixture", b"synthetic host fixturE", 1)
    assert changed != raw
    path.write_bytes(changed)
    with pytest.raises(rb.BundleError, match="invalid_zip"):
        rb.check_bundle(path)


def test_limits_enforced_before_packaging(monkeypatch, payload, provenance):
    monkeypatch.setattr(rb, "MAX_FILE_BYTES", 8)
    with pytest.raises(rb.BundleError, match="file_too_large"):
        rb.assemble(payload, provenance, "3" * 40)


def test_read_frontend_order_and_mtime_do_not_change_content(tmp_path):
    (tmp_path / "assets").mkdir()
    (tmp_path / "assets/app.js").write_bytes(b"synthetic")
    (tmp_path / "index.html").write_bytes(b"synthetic")
    before = rb.read_frontend(tmp_path)
    os.utime(tmp_path / "index.html", (1_000_000, 1_000_000))
    assert rb.read_frontend(tmp_path) == before


def test_symlinks_are_not_followed(tmp_path):
    source = tmp_path / "outside.html"
    source.write_bytes(b"synthetic")
    front = tmp_path / "front"
    front.mkdir()
    try:
        (front / "index.html").symlink_to(source)
    except OSError:
        pytest.skip("OS does not permit creating a symlink in this test account")
    with pytest.raises(rb.BundleError, match="linked_path"):
        rb.read_frontend(front)


def test_windows_reparse_guard(monkeypatch, tmp_path):
    original = Path.lstat

    class Reparse:
        st_mode = stat.S_IFDIR
        st_file_attributes = 0x400

    monkeypatch.setattr(Path, "lstat", lambda p: Reparse() if p == tmp_path else original(p))
    with pytest.raises(rb.BundleError, match="linked_path"):
        rb._plain_path(tmp_path)


def test_no_overwrite_or_output_inside_source(tmp_path, files):
    front = tmp_path / "frontend"
    front.mkdir()
    target = tmp_path / "candidate"
    report = rb.write_bundle(target, files, front)
    saved = (target / "release.zip").read_bytes()
    assert report["deployable"] is False
    with pytest.raises(FileExistsError):
        rb.write_bundle(target, files, front)
    assert (target / "release.zip").read_bytes() == saved
    with pytest.raises(rb.BundleError, match="output_inside_input"):
        rb.write_bundle(front / "output", files, front)
    with pytest.raises(rb.BundleError, match="output_inside_input"):
        rb.write_bundle(tmp_path / "unused" / ".." / "frontend" / "output", files, front)


def test_git_host_uses_fixed_commit_not_working_tree(tmp_path):
    repo = tmp_path / "repo"
    repo.mkdir()
    git = ["git", "-C", str(repo)]
    subprocess.run(git + ["init", "-q"], check=True)
    for name in rb.HOST_FILES:
        target = repo / "ops/public-host" / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(b"fixed git blob\n")
    subprocess.run(git + ["add", "."], check=True)
    subprocess.run(
        git
        + [
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "synthetic fixture",
        ],
        check=True,
    )
    commit = subprocess.check_output(git + ["rev-parse", "HEAD"], text=True).strip()
    (repo / "ops/public-host/worker.mjs").write_bytes(b"changed local working tree\n")
    assert rb.read_host_commit(repo, commit)["host/worker.mjs"] == b"fixed git blob\n"
    with pytest.raises(rb.BundleError, match="full_host_commit_required"):
        rb.read_host_commit(repo, "HEAD")
    # A git replace ref pointing the pinned commit at other bytes is ignored.
    subprocess.run(git + ["add", "."], check=True)
    subprocess.run(
        git
        + [
            "-c",
            "user.name=Test",
            "-c",
            "user.email=test@example.invalid",
            "commit",
            "-qm",
            "replacement candidate",
        ],
        check=True,
    )
    other = subprocess.check_output(git + ["rev-parse", "HEAD"], text=True).strip()
    subprocess.run(git + ["replace", commit, other], check=True)
    assert rb.read_host_commit(repo, commit)["host/worker.mjs"] == b"fixed git blob\n"


def test_candidate_is_never_a_deployment_approval(payload, provenance):
    report = rb.verify_files(rb.assemble(payload, provenance, "3" * 40, mode="candidate"))
    assert report["mode"] == "candidate"
    assert report["deployable"] is False
    assert "provenance" in report["scope"]


def test_cli_check_clean_and_changed_bundle(tmp_path, files):
    path = archive_path(tmp_path, files)
    cmd = [
        sys.executable,
        "-B",
        "-S",
        str(ROOT / "scripts/build_public_host_release.py"),
        "check",
        str(path),
    ]
    good = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    assert good.returncode == 0, good.stderr
    assert json.loads(good.stdout)["deployable"] is False
    files["public/index.html"] += b"tamper"
    path.write_bytes(rb.make_zip(files))
    bad = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8")
    assert bad.returncode == 2
    assert "inventory_mismatch" in bad.stderr
    assert "Traceback" not in bad.stderr
    missing = tmp_path / "secret-dir-name" / "absent.zip"
    gone = subprocess.run(
        cmd[:-1] + [str(missing)], capture_output=True, text=True, encoding="utf-8"
    )
    assert gone.returncode == 2
    payload = json.loads(gone.stderr)
    assert payload["error"] == "io_error" and isinstance(payload["errno"], int)
    assert "secret-dir-name" not in gone.stderr, "OSError text (paths) is not echoed"


@pytest.mark.parametrize("position", ["prefix", "suffix", "comment"])
def test_unlisted_archive_bytes_rejected(tmp_path, files, position):
    path = archive_path(tmp_path, files)
    if position == "comment":
        with zipfile.ZipFile(path, "a") as archive:
            archive.comment = b"unlisted data"
    else:
        raw = path.read_bytes()
        path.write_bytes(b"unlisted data" + raw if position == "prefix" else raw + b"unlisted data")
    with pytest.raises(rb.BundleError, match="noncanonical_zip"):
        rb.check_bundle(path)


@pytest.mark.parametrize("mode", [[], {}, None, 1])
def test_manifest_wrong_mode_type_rejected_cleanly(files, mode):
    manifest = json.loads(files[rb.MANIFEST])
    manifest["mode"] = mode
    files[rb.MANIFEST] = rb.canonical(manifest)
    with pytest.raises(rb.BundleError, match="invalid_manifest"):
        rb.verify_files(files)


def test_large_json_integer_is_rejected_with_a_stable_diagnostic():
    raw = b'{"number":' + b"1" * 5000 + b"}"
    previous = sys.get_int_max_str_digits()
    try:
        sys.set_int_max_str_digits(640)
        with pytest.raises(rb.BundleError, match="^invalid_json$"):
            rb.parse_json(raw)
    finally:
        sys.set_int_max_str_digits(previous)


@pytest.mark.parametrize("mode", ["build", "check"])
def test_large_json_integer_cli_preserves_inputs_and_does_not_create_output(tmp_path, files, mode):
    raw = b'{"number":' + b"1" * 5000 + b"}"
    private_input = tmp_path / "private-input-location"
    private_input.mkdir()
    output = tmp_path / "not-created-release"
    command = [
        sys.executable,
        "-B",
        "-S",
        "-X",
        "int_max_str_digits=640",
        str(ROOT / "scripts/build_public_host_release.py"),
        mode,
    ]
    if mode == "build":
        source = private_input / "provenance.json"
        source.write_bytes(raw)
        command += [
            "--frontend",
            str(tmp_path / "unused-frontend"),
            "--provenance",
            str(source),
            "--output",
            str(output),
            "--mode",
            "synthetic",
            "--host-commit",
            "3" * 40,
        ]
    else:
        source = archive_path(private_input, {**files, rb.MANIFEST: raw})
        command.append(str(source))
    before = source.read_bytes()
    result = subprocess.run(command, capture_output=True, text=True, encoding="utf-8")
    assert result.returncode == 2
    assert result.stdout == ""
    assert json.loads(result.stderr) == {"ok": False, "error": "invalid_json"}
    assert "Traceback" not in result.stderr
    assert "private-input-location" not in result.stderr
    assert source.read_bytes() == before
    assert not output.exists()

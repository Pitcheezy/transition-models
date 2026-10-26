"""Portable replay validation refuses changed files and unsafe archives before use."""

import hashlib
import json
import os
import stat
import subprocess
import sys
import threading
import urllib.error
import urllib.request
import zipfile
from pathlib import Path
from types import SimpleNamespace

import pytest

from intent import mitt_replay_package as kit


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def save(path, value):
    path.write_bytes(kit._encoded(value))


@pytest.fixture
def source(tmp_path):
    pack = tmp_path / "source"
    pack.mkdir()
    files = {name: f"source {name}".encode() for name in kit.VIEW_ASSETS}
    files["index.html"] = b"<html>saved development replay</html>"
    for i in range(3):
        files[f"frames/747139_3_1/{i}.jpg"] = b"saved JPEG " + bytes([i])
    for name, raw in files.items():
        path = pack / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    receipt = {
        "schema": kit.RECEIPT_SCHEMA,
        "comparison_schema": kit.COMPARISON_SCHEMA,
        "input_unchanged": True,
        "frame_images_unchanged": True,
        "no_new_tracking_or_model_calls": True,
        "no_new_ocr_calls": True,
        "independent_decoded_pts_verified": False,
        "displayed_frames": 3,
        "files": {n: {"sha256": sha(raw), "bytes": len(raw)} for n, raw in files.items()},
    }
    save(pack / "receipt.json", receipt)
    return {
        "pack": pack,
        "receipt_sha256": sha((pack / "receipt.json").read_bytes()),
        "source_commit": "a" * 40,
        "out": tmp_path / "portable",
        "archive": tmp_path / "portable.zip",
    }


@pytest.fixture
def built(source):
    result = kit.build(**source)
    return source, result


def test_build_extract_preserve_every_byte_and_source(built, tmp_path):
    args, report = built
    original = kit._tree(args["pack"])
    assert report["source_files"] == 9 and report["package_files"] == 13
    assert report["input_unchanged"] is True
    assert kit._tree(args["out"] / "viewer") == original
    snapshot = kit.check(args["out"])
    assert len(snapshot) == 8
    assert set(snapshot) == {"/" + name for name in original if name != "receipt.json"}
    with pytest.raises(TypeError):
        snapshot["/index.html"] = (b"changed", "text/html")
    destination = tmp_path / "extracted"
    extracted = kit.extract(
        archive=args["archive"], archive_sha256=report["archive_sha256"], out=destination
    )
    assert extracted["package_files"] == report["package_files"]
    assert kit._tree(destination) == kit._tree(args["out"])
    assert kit._tree(args["pack"]) == original
    assert "별도 신뢰 경로" in (destination / "README.txt").read_text(encoding="utf-8")


def test_standalone_check_runs_with_no_site_packages_and_does_not_import_helper(built):
    args, _ = built
    env = dict(os.environ, PYTHONUTF8="1")
    done = subprocess.run(
        [sys.executable, "-B", "-S", "run_replay.py", "--check"],
        cwd=args["out"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert done.returncode == 0, done.stderr
    assert "검사 통과" in done.stdout
    assert not (args["out"] / "__pycache__").exists()
    code = (
        "import runpy,sys; m=runpy.run_path('run_replay.py'); m['check']('.'); "
        "assert not {'torch','PIL','review_server','intent.review_server'} & sys.modules.keys()"
    )
    done = subprocess.run(
        [sys.executable, "-B", "-S", "-c", code],
        cwd=args["out"],
        env=env,
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert done.returncode == 0, done.stderr


@pytest.mark.parametrize("mutation", ["changed", "missing", "extra", "empty_directory", "helper"])
def test_check_rejects_changes_without_executing_unverified_helper(built, mutation):
    args, _ = built
    root = args["out"]
    target = root / "viewer" / "payload.json"
    if mutation == "changed":
        target.write_bytes(b"different")
    elif mutation == "missing":
        target.unlink()
    elif mutation == "extra":
        (root / "extra.txt").write_text("extra")
    elif mutation == "empty_directory":
        (root / "empty").mkdir()
    elif mutation == "helper":
        (root / "review_server.py").write_text("raise AssertionError('unverified helper executed')")
    with pytest.raises(ValueError):
        kit.check(root)
    with pytest.raises(ValueError):
        kit.open_server(root)


def test_loopback_serves_only_original_snapshot_and_no_runtime_files(built):
    args, _ = built
    expected = (args["out"] / "viewer" / "index.html").read_bytes()
    with kit.open_server(args["out"]) as server:
        assert server.server_address[0] == "127.0.0.1" and server.server_address[1] > 0
        thread = threading.Thread(target=server.serve_forever, daemon=True)
        thread.start()
        base = f"http://127.0.0.1:{server.server_address[1]}"
        try:
            (args["out"] / "viewer" / "index.html").write_bytes(b"changed after verification")
            with urllib.request.urlopen(base + "/", timeout=5) as response:
                assert response.read() == expected
                assert response.headers["Cache-Control"] == "no-store"
                assert response.headers["X-Content-Type-Options"] == "nosniff"
            for path in (
                "manifest.json",
                "run_replay.py",
                "review_server.py",
                "README.txt",
                "receipt.json",
                "viewer/receipt.json",
                "../manifest.json",
                "frames/",
            ):
                with pytest.raises(urllib.error.HTTPError) as error:
                    urllib.request.urlopen(base + "/" + path, timeout=5)
                assert error.value.code == 404
        finally:
            server.shutdown()
            thread.join(timeout=5)


def test_verified_helper_bytes_are_used_even_if_disk_changes_after_check(built, monkeypatch):
    args, _ = built
    validate = kit._validate

    def change_after(files):
        viewer = validate(files)
        (args["out"] / "review_server.py").write_text("raise AssertionError('reread helper')")
        return viewer

    monkeypatch.setattr(kit, "_validate", change_after)
    with kit.open_server(args["out"]) as server:
        assert server.server_address[0] == "127.0.0.1"


@pytest.mark.parametrize("target", ["out", "archive"])
def test_build_does_not_overwrite_existing_outputs(source, target):
    if target == "out":
        source[target].mkdir()
        marker = source[target] / "keep.txt"
    else:
        marker = source[target]
    marker.write_bytes(b"keep")
    with pytest.raises(ValueError, match="already exists"):
        kit.build(**source)
    assert marker.read_bytes() == b"keep"
    if target == "archive":
        assert not source["out"].exists()


@pytest.mark.parametrize("mutation", ["pin", "commit", "extra", "receipt_file_hash"])
def test_build_refuses_unbound_source_before_output(source, mutation):
    if mutation == "pin":
        source["receipt_sha256"] = "b" * 64
    elif mutation == "commit":
        source["source_commit"] = "main"
    elif mutation == "extra":
        (source["pack"] / "unlisted.txt").write_bytes(b"unlisted")
    else:
        (source["pack"] / "payload.json").write_bytes(b"wrong")
    with pytest.raises(ValueError):
        kit.build(**source)
    assert not source["out"].exists() and not source["archive"].exists()


@pytest.mark.parametrize(
    "names",
    [
        ["../outside"],
        ["/absolute"],
        ["C:/outside"],
        ["a\\b"],
        ["a//b"],
        ["a/./b"],
        ["a/../b"],
        ["CON.txt"],
        ["a."],
        ["same", "same"],
        ["a", "A"],
        ["one/x", "ONE/y"],
        ["a", "a/file"],
    ],
)
def test_paths_are_portable_and_unambiguous(names):
    with pytest.raises(ValueError):
        kit._names(names)


def rewrite_zip(path, files, extra=None):
    with zipfile.ZipFile(path, "w", compression=zipfile.ZIP_STORED) as stream:
        for name, raw in files.items():
            stream.writestr(name, raw)
        if extra is not None:
            stream.writestr(*extra)


@pytest.mark.parametrize(
    "mutation",
    ["duplicate", "traversal", "case", "symlink", "directory", "extra", "missing", "crc"],
)
def test_unsafe_or_incomplete_zip_rejected_before_writing(built, tmp_path, mutation):
    args, _ = built
    files = kit._tree(args["out"])
    archive, out = tmp_path / "bad.zip", tmp_path / "bad_extracted"
    extra = None
    if mutation == "duplicate":
        extra = ("manifest.json", files["manifest.json"])
    elif mutation == "traversal":
        extra = ("../outside.txt", b"escape")
    elif mutation == "case":
        extra = ("Viewer/extra.txt", b"ambiguous directory")
    elif mutation == "symlink":
        link = zipfile.ZipInfo("outside")
        link.create_system = 3
        link.external_attr = (stat.S_IFLNK | 0o777) << 16
        extra = (link, b"../outside")
    elif mutation == "directory":
        extra = ("empty/", b"")
    elif mutation == "extra":
        extra = ("extra.txt", b"extra")
    elif mutation == "missing":
        del files["viewer/payload.json"]
    if mutation == "duplicate":
        with pytest.warns(UserWarning, match="Duplicate"):
            rewrite_zip(archive, files, extra)
    else:
        rewrite_zip(archive, files, extra)
    raw = archive.read_bytes()
    if mutation == "crc":
        raw = raw.replace(b"saved development replay", b"saved development replaY", 1)
        archive.write_bytes(raw)
    with pytest.raises(ValueError):
        kit.extract(archive=archive, archive_sha256=sha(raw), out=out)
    assert not out.exists() and not (tmp_path / "outside.txt").exists()


def test_zip_requires_external_hash_and_new_destination(built, tmp_path):
    args, result = built
    out = tmp_path / "new"
    with pytest.raises(ValueError, match="ZIP SHA"):
        kit.extract(archive=args["archive"], archive_sha256="0" * 64, out=out)
    assert not out.exists()
    out.mkdir()
    with pytest.raises(ValueError, match="already exists"):
        kit.extract(archive=args["archive"], archive_sha256=result["archive_sha256"], out=out)


def test_receipt_pin_survives_resealed_outer_manifest(built):
    args, _ = built
    root = args["out"]
    path = root / "viewer" / "receipt.json"
    path.write_bytes(path.read_bytes() + b" ")
    manifest = json.loads((root / "manifest.json").read_bytes())
    manifest["files"]["viewer/receipt.json"] = {
        "sha256": sha(path.read_bytes()),
        "bytes": path.stat().st_size,
    }
    save(root / "manifest.json", manifest)
    with pytest.raises(ValueError, match="source receipt SHA"):
        kit.check(root)


def test_windows_reparse_flag_is_rejected_without_is_junction():
    class OlderWindowsPath:
        def is_symlink(self):
            return False

        def lstat(self):
            return SimpleNamespace(st_file_attributes=0x400)

    assert kit._linked(OlderWindowsPath()) is True


def test_oversized_archive_rejected_before_read(built, tmp_path, monkeypatch):
    args, result = built
    original = Path.read_bytes

    def forbid_zip_read(path):
        if path == args["archive"]:
            pytest.fail("oversized archive must not be read into memory")
        return original(path)

    monkeypatch.setattr(kit, "MAX_TOTAL_BYTES", args["archive"].stat().st_size - 1)
    monkeypatch.setattr(Path, "read_bytes", forbid_zip_read)
    with pytest.raises(ValueError, match="archive size limit"):
        kit.extract(
            archive=args["archive"],
            archive_sha256=result["archive_sha256"],
            out=tmp_path / "no_output",
        )
    assert not (tmp_path / "no_output").exists()


def test_actual_link_outside_source_is_rejected(source, tmp_path):
    outside = tmp_path / "outside.txt"
    outside.write_bytes(b"must not be packaged")
    link = source["pack"] / "linked.txt"
    try:
        link.symlink_to(outside)
    except OSError:
        pytest.skip("creating symlinks requires host permission")
    with pytest.raises(ValueError, match="linked"):
        kit.build(**source)
    assert not source["out"].exists()


def test_reparse_directory_never_traversed(source, tmp_path, monkeypatch):
    directory = source["pack"] / "frames"
    original = kit._linked
    monkeypatch.setattr(kit, "_linked", lambda path: path == directory or original(path))
    with pytest.raises(ValueError, match="linked"):
        kit.build(**source)
    assert not source["out"].exists()


@pytest.mark.parametrize("value", [True, -1, 10**100])
def test_manifest_byte_count_is_strict(built, value):
    args, _ = built
    manifest = json.loads((args["out"] / "manifest.json").read_bytes())
    manifest["files"]["README.txt"]["bytes"] = value
    save(args["out"] / "manifest.json", manifest)
    with pytest.raises(ValueError):
        kit.check(args["out"])

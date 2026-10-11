"""Portable package and HTTP checks use invented report/media bytes, never private exports."""

import hashlib
import http.client
import importlib.util
import io
import json
import subprocess
import sys
import threading
from copy import deepcopy
from pathlib import Path

import pytest

MODULE_PATH = Path(__file__).resolve().parents[1] / "src/integration/service_review_server.py"
SPEC = importlib.util.spec_from_file_location("portable_service_review", MODULE_PATH)
server_module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(server_module)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def refresh_receipt(root):
    """Bind explicitly changed synthetic fixtures, not arbitrary real package files."""
    path = root / "receipt.json"
    receipt = json.loads(path.read_bytes())
    receipt["report_sha256"] = sha((root / "review-data.json").read_bytes())
    receipt["assets_sha256"] = {
        name: sha((root / name).read_bytes()) for name in receipt["assets_sha256"]
    }
    write_json(path, receipt)


@pytest.fixture
def package(tmp_path):
    root = tmp_path / "private-review"
    (root / "media").mkdir(parents=True)
    report = {
        "schema": server_module.REPORT_SCHEMA,
        "profile": server_module.PROFILE,
        "source": {"sha256": "a" * 64, "input_kind": "synthetic"},
        "game": {"game_pk": 900001},
        "pitches": [
            {"key": f"900001:1:{n}", "pa_key": "900001:1", "at_bat_number": 1, "pitch_number": n}
            for n in (1, 2)
        ],
        "summary": {"pitches": 2, "ready": 2},
    }
    files = {
        "index.html": b"<!doctype html><title>Synthetic private review</title>",
        "review.js": b"'use strict';",
        "style.css": b"body { color: black; }",
        "media/synthetic.mp4": b"0123456789abcdefghijklmnopqrstuvwxyz",
        "media/synthetic.jpg": b"synthetic poster bytes",
        "launch_review.py": MODULE_PATH.read_bytes(),
        "START_WINDOWS.cmd": b"@echo off\r\npython launch_review.py --open\r\n",
        "START_MAC.command": b"#!/bin/sh\npython3 launch_review.py --open\n",
        "PRIVATE.txt": b"Synthetic private review; do not publish.\n",
    }
    media = {
        "schema": server_module.MEDIA_SCHEMA,
        "game_pk": report["game"]["game_pk"],
        "source_sha256": report["source"]["sha256"],
        "clips": [
            {
                "pitch_key": "900001:1:1",
                "play_id": "synthetic-play-1",
                "video": "media/synthetic.mp4",
                "poster": "media/synthetic.jpg",
                "video_sha256": sha(files["media/synthetic.mp4"]),
                "poster_sha256": sha(files["media/synthetic.jpg"]),
                "duration_seconds": 1.25,
            }
        ],
    }
    files["review-media.json"] = json.dumps(media).encode("utf-8")
    for name, raw in files.items():
        (root / name).write_bytes(raw)
    write_json(root / "review-data.json", report)
    receipt = {
        "schema": server_module.PACKAGE_SCHEMA,
        "profile": server_module.PROFILE,
        "source_sha256": report["source"]["sha256"],
        "report_sha256": sha((root / "review-data.json").read_bytes()),
        "assets_sha256": {name: sha(raw) for name, raw in files.items()},
        "summary": report["summary"],
        "public_distribution": False,
        "live_validation": False,
        "extra_metadata": {"fixture": "invented"},
    }
    write_json(root / "receipt.json", receipt)
    return root


def test_snapshot_verifies_and_exposes_only_browser_files(package):
    (package / "unlisted-secret.txt").write_text("private sentinel", encoding="utf-8")
    snapshot = server_module.load_snapshot(package)
    assert set(snapshot) == {
        "/index.html",
        "/review.js",
        "/style.css",
        "/review-data.json",
        "/review-media.json",
        "/media/synthetic.mp4",
        "/media/synthetic.jpg",
    }
    assert snapshot["/media/synthetic.mp4"][1] == "video/mp4"
    assert snapshot["/media/synthetic.jpg"][1] == "image/jpeg"
    with pytest.raises(TypeError):
        snapshot["/receipt.json"] = (b"unsafe", "text/plain")


@pytest.mark.parametrize(
    "name",
    [
        "review-data.json",
        "review-media.json",
        "review.js",
        "launch_review.py",
        "media/synthetic.mp4",
    ],
)
def test_changed_bytes_fail_instead_of_being_served(package, name):
    path = package / name
    path.write_bytes(path.read_bytes() + b"tamper")
    with pytest.raises(ValueError, match="SHA256"):
        server_module.load_snapshot(package)


@pytest.mark.parametrize("name", ["receipt.json", "media/synthetic.jpg", "START_MAC.command"])
def test_missing_required_file_is_rejected(package, name):
    (package / name).unlink()
    with pytest.raises((OSError, ValueError)):
        server_module.load_snapshot(package)


@pytest.mark.parametrize(
    ("file", "field", "value"),
    [
        ("receipt.json", "schema", "pitcheezy-private-service-review-package-v1"),
        ("receipt.json", "profile", "unexpected"),
        ("receipt.json", "public_distribution", True),
        ("receipt.json", "live_validation", 0),
        ("receipt.json", "source_sha256", "B" * 64),
        ("receipt.json", "summary", {"pitches": 1}),
        ("review-data.json", "schema", "raw-response"),
        ("review-data.json", "profile", "legacy-profile"),
        ("review-data.json", "source", {"sha256": "b" * 64}),
        ("review-data.json", "game", {"game_pk": True}),
        ("review-media.json", "game_pk", 900002),
        ("review-media.json", "source_sha256", "b" * 64),
    ],
)
def test_receipt_report_and_media_identity_must_agree(package, file, field, value):
    path = package / file
    data = json.loads(path.read_bytes())
    data[field] = value
    write_json(path, data)
    if file != "receipt.json":
        refresh_receipt(package)
    with pytest.raises(ValueError):
        server_module.load_snapshot(package)


@pytest.mark.parametrize("file", ["receipt.json", "review-data.json", "review-media.json"])
@pytest.mark.parametrize(
    "invalid_tail", [',"schema":"duplicate"}', ',"extra":NaN}', ',"extra":1e999}']
)
def test_all_json_documents_reject_duplicate_keys_and_nonfinite_numbers(
    package, file, invalid_tail
):
    path = package / file
    path.write_bytes(path.read_bytes()[:-1] + invalid_tail.encode("ascii"))
    if file != "receipt.json":
        refresh_receipt(package)
    with pytest.raises(ValueError):
        server_module.load_snapshot(package)


@pytest.mark.parametrize(
    "name",
    [
        "../outside.txt",
        "media/../outside.mp4",
        "/absolute",
        "media\\file.mp4",
        "media/CON.mp4",
        "INDEX.HTML",
    ],
)
def test_receipt_paths_cannot_escape_or_collide_across_platforms(package, name):
    path = package / "receipt.json"
    receipt = json.loads(path.read_bytes())
    receipt["assets_sha256"][name] = "a" * 64
    write_json(path, receipt)
    with pytest.raises(ValueError):
        server_module.load_snapshot(package)


@pytest.mark.parametrize("kind", ["file", "directory", "root"])
def test_linked_assets_or_roots_are_rejected(package, tmp_path, kind):
    outside = tmp_path / "outside"
    outside.mkdir()
    try:
        if kind == "file":
            path = package / "media/synthetic.mp4"
            target = outside / "same.mp4"
            target.write_bytes(path.read_bytes())
            path.unlink()
            path.symlink_to(target)
        elif kind == "directory":
            media = package / "media"
            moved = outside / "media"
            media.rename(moved)
            media.symlink_to(moved, target_is_directory=True)
        else:
            linked_root = tmp_path / "linked-root"
            linked_root.symlink_to(package, target_is_directory=True)
            package = linked_root
    except (OSError, NotImplementedError):
        pytest.skip("Host does not permit unprivileged symlink creation")
    with pytest.raises(ValueError, match="[Ll]ink"):
        server_module.load_snapshot(package)


@pytest.mark.parametrize("limit", ["report", "asset", "total"])
def test_size_limits_apply_before_loading_large_content(package, monkeypatch, limit):
    if limit == "report":
        monkeypatch.setattr(server_module, "MAX_JSON_BYTES", 20)
    elif limit == "asset":
        monkeypatch.setattr(server_module, "MAX_FILE_BYTES", 2)
    else:
        size = sum(path.stat().st_size for path in package.rglob("*") if path.is_file())
        monkeypatch.setattr(server_module, "MAX_TOTAL_BYTES", size - 1)
    with pytest.raises(ValueError, match="size limit"):
        server_module.load_snapshot(package)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("pitch_key", "900002:1:1"),
        ("play_id", ""),
        ("duration_seconds", True),
        ("duration_seconds", 0),
        ("duration_seconds", "1.25"),
        ("video_sha256", "b" * 64),
        ("poster", "index.html"),
    ],
)
def test_media_binding_and_units_are_not_guessed(package, field, value):
    path = package / "review-media.json"
    media = json.loads(path.read_bytes())
    media["clips"][0][field] = value
    write_json(path, media)
    refresh_receipt(package)
    with pytest.raises(ValueError):
        server_module.load_snapshot(package)


def test_duplicate_media_play_and_report_pitch_keys_are_rejected(package):
    path = package / "review-media.json"
    media = json.loads(path.read_bytes())
    second = deepcopy(media["clips"][0])
    second["pitch_key"] = "900001:1:2"
    media["clips"].append(second)
    write_json(path, media)
    refresh_receipt(package)
    with pytest.raises(ValueError, match="play identity"):
        server_module.load_snapshot(package)
    media["clips"].pop()
    write_json(path, media)
    report_path = package / "review-data.json"
    report = json.loads(report_path.read_bytes())
    report["pitches"][1] = report["pitches"][0]
    write_json(report_path, report)
    refresh_receipt(package)
    with pytest.raises(ValueError, match="pitch keys"):
        server_module.load_snapshot(package)


def test_empty_media_list_is_valid_and_unlisted_files_stay_private(package):
    media_path = package / "review-media.json"
    media = json.loads(media_path.read_bytes())
    media["clips"] = []
    write_json(media_path, media)
    receipt_path = package / "receipt.json"
    receipt = json.loads(receipt_path.read_bytes())
    receipt["assets_sha256"] = {
        name: digest
        for name, digest in receipt["assets_sha256"].items()
        if not name.startswith("media/")
    }
    write_json(receipt_path, receipt)
    refresh_receipt(package)
    snapshot = server_module.load_snapshot(package)
    assert len(snapshot) == 5
    assert not any(path.startswith("/media/") for path in snapshot)


@pytest.fixture
def running_server(package):
    snapshot = server_module.load_snapshot(package)
    server = server_module.ReviewServer(("127.0.0.1", 0), server_module.make_handler(snapshot))
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield server, snapshot
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def request(server, path, method="GET", headers=None):
    connection = http.client.HTTPConnection(*server.server_address, timeout=5)
    try:
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def test_zero_port_get_head_and_snapshot_survive_file_changes(running_server, package):
    server, snapshot = running_server
    assert server.server_address[0] == "127.0.0.1"
    assert 0 < server.server_address[1] <= 65535
    expected = snapshot["/media/synthetic.mp4"][0]
    (package / "media/synthetic.mp4").write_bytes(b"changed after verification")
    (package / "index.html").unlink()
    status, headers, body = request(server, "/media/synthetic.mp4")
    assert (status, body) == (200, expected)
    assert headers["Content-Type"] == "video/mp4"
    assert headers["Accept-Ranges"] == "bytes"
    assert headers["Cache-Control"] == "no-store"
    status, head, body = request(server, "/media/synthetic.mp4", method="HEAD")
    assert status == 200 and body == b""
    assert head["Content-Length"] == str(len(expected))
    assert request(server, "/")[2] == snapshot["/index.html"][0]


@pytest.mark.parametrize(
    "path",
    [
        "/receipt.json",
        "/launch_review.py",
        "/PRIVATE.txt",
        "/START_WINDOWS.cmd",
        "/START_MAC.command",
        "/unlisted.txt",
        "/../review-data.json",
        "/media/%2e%2e/review-data.json",
        "/media/",
    ],
)
def test_http_never_serves_metadata_unlisted_files_or_traversal(running_server, path):
    server, _ = running_server
    assert request(server, path)[0] == 404


@pytest.mark.parametrize(
    ("range_value", "bounds"),
    [
        ("bytes=0-1", (0, 1)),
        ("bytes=10-", (10, 35)),
        ("bytes=-4", (32, 35)),
        ("bytes=30-999", (30, 35)),
        ("bytes=-999", (0, 35)),
    ],
)
def test_single_mp4_ranges_support_seeking_and_head(running_server, range_value, bounds):
    server, snapshot = running_server
    raw = snapshot["/media/synthetic.mp4"][0]
    start, stop = bounds
    status, headers, body = request(server, "/media/synthetic.mp4", headers={"Range": range_value})
    assert status == 206
    assert headers["Content-Range"] == f"bytes {start}-{stop}/{len(raw)}"
    assert headers["Content-Length"] == str(stop - start + 1)
    assert body == raw[start : stop + 1]
    status, head, body = request(server, "/media/synthetic.mp4", "HEAD", {"Range": range_value})
    assert status == 206 and body == b""
    assert head["Content-Range"] == headers["Content-Range"]


@pytest.mark.parametrize(
    "value",
    [
        "bytes=99-",
        "bytes=5-3",
        "bytes=-0",
        "bytes=-",
        "bytes=0-1,4-5",
        "items=0-1",
        "bytes=wrong",
        "bytes=" + "9" * 200 + "-",
    ],
)
def test_invalid_multiple_and_unsatisfiable_ranges_return_416(running_server, value):
    server, _ = running_server
    status, headers, body = request(server, "/media/synthetic.mp4", headers={"Range": value})
    assert status == 416 and body == b""
    assert headers["Content-Range"] == "bytes */36"
    assert headers["Content-Length"] == "0"


def test_copied_launcher_checks_package_without_site_packages_or_repo_imports(package, tmp_path):
    result = subprocess.run(
        [
            sys.executable,
            "-I",
            "-S",
            "-B",
            "-X",
            "utf8",
            str(package / "launch_review.py"),
            "--check",
        ],
        cwd=tmp_path,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        check=False,
    )
    assert result.returncode == 0, result.stderr
    assert "영상 1개" in result.stdout
    assert not list(package.rglob("__pycache__"))


def test_check_mode_never_opens_a_browser_and_bad_port_fails_early(package, monkeypatch):
    def forbidden(*args):
        raise AssertionError("A check-only invocation must not open a browser")

    monkeypatch.setattr(server_module.webbrowser, "open", forbidden)
    assert server_module.main(["--directory", str(package), "--check", "--open"]) == 0
    with pytest.raises(SystemExit) as error:
        server_module.main(["--port", "-1"])
    assert error.value.code == 2


class InterruptedClient:
    """Exercise the HTTP handler's real header/body writer without OS timing races."""

    def __init__(self, method, path, headers=None, fail_write=None, error_type=None):
        request_lines = [f"{method} {path} HTTP/1.0", "Host: localhost"]
        request_lines.extend(f"{name}: {value}" for name, value in (headers or {}).items())
        self.request = io.BytesIO(("\r\n".join(request_lines) + "\r\n\r\n").encode())
        self.fail_write = fail_write
        self.error_type = error_type
        self.writes = []
        self.attempts = 0

    def makefile(self, mode, *args):
        assert mode == "rb"
        return self.request

    def sendall(self, data):
        self.attempts += 1
        if self.attempts == self.fail_write:
            raise self.error_type("simulated client cancellation")
        self.writes.append(bytes(data))


@pytest.mark.parametrize(
    "error_type", [ConnectionAbortedError, ConnectionResetError, BrokenPipeError]
)
@pytest.mark.parametrize(
    ("method", "path", "headers", "fail_write"),
    [
        ("GET", "/media/synthetic.mp4", {}, 1),
        ("GET", "/media/synthetic.mp4", {"Range": "bytes=0-1"}, 2),
        ("HEAD", "/media/synthetic.mp4", {}, 1),
        ("GET", "/missing", {}, 1),
        ("GET", "/missing", {}, 2),
        ("GET", "/media/synthetic.mp4", {"Range": "bytes=999-"}, 1),
    ],
)
def test_expected_client_cancellation_is_quiet_and_next_response_succeeds(
    package, method, path, headers, fail_write, error_type
):
    snapshot = server_module.load_snapshot(package)
    handler = server_module.make_handler(snapshot)
    interrupted = InterruptedClient(method, path, headers, fail_write, error_type)
    handler(interrupted, ("127.0.0.1", 10000), None)
    assert interrupted.attempts == fail_write
    # A new request still returns the correct range and bytes after the aborted response.
    next_client = InterruptedClient("GET", "/media/synthetic.mp4", {"Range": "bytes=10-"})
    handler(next_client, ("127.0.0.1", 10001), None)
    assert b" 206 " in next_client.writes[0]
    assert b"Content-Range: bytes 10-35/36" in next_client.writes[0]
    assert next_client.writes[1] == snapshot["/media/synthetic.mp4"][0][10:]


@pytest.mark.parametrize("fail_write", [1, 2])
def test_unexpected_write_errors_are_not_silenced(package, fail_write):
    handler = server_module.make_handler(server_module.load_snapshot(package))
    client = InterruptedClient("GET", "/media/synthetic.mp4", {}, fail_write, PermissionError)
    with pytest.raises(PermissionError, match="simulated client cancellation"):
        handler(client, ("127.0.0.1", 10000), None)

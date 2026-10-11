"""Private playback adapter: verified snapshots and real loopback Range responses."""

import hashlib
import http.client
import json
import threading
from contextlib import contextmanager

import pytest

from intent import observation_playback_server as server


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def package(tmp_path):
    root = tmp_path / "package"
    root.mkdir()
    data = {
        "schema": server.SCHEMA,
        "media": {
            "path": "media/clip.mp4",
            "sha256": sha(b"0123456789"),
            "source_offset_seconds_exact": "10",
            "clip_end_seconds_exact": "30",
        },
        "scope": {
            "game_pk": 747139,
            "pa": 2,
            "start_source_seconds_exact": "14",
            "end_source_seconds_exact": "32",
            "full_pa_verified": False,
            "live_availability_verified": False,
            "human_label": False,
        },
        "observations": [
            {
                "index": 0,
                "cutoff_seconds_exact": "16",
                "frame_seconds_exact": "16",
                "publication_seconds_exact": "17",
                "status": "accepted",
                "observation_status": "unknown",
                "candidate_status": "candidate",
                "reference_pitch_id": "747139:2:1",
                "image_path": "frames/000.jpg",
            }
        ],
        "references": [
            {
                "pitch_id": "747139:2:1",
                "decision_seconds_exact": "15",
                "decision_upper_seconds_exact": "61/4",
                "release_lower_seconds_exact": "71/4",
                "release_upper_seconds_exact": "73/4",
                "conservative_temporal_ready": True,
                "nominal_start_temporal_ready": True,
                "usable_mitt": False,
            }
        ],
        "summary": {
            "planned_observations": 1,
            "interval_observations": 1,
            "outside_interval_observations": 0,
            "accepted": 1,
            "errors": 0,
            "not_attempted": 0,
            "verified_mitt": 0,
            "conservative_ready_pitches": 1,
        },
    }
    files = {
        "index.html": b"<html>private replay</html>",
        "playback.js": b"'use strict';",
        "style.css": b"body{}",
        "replay-data.json": json.dumps(data).encode(),
        "PRIVATE.txt": b"Private, local only",
        "media/clip.mp4": b"0123456789",
        "frames/000.jpg": b"synthetic image bytes",
    }
    for name, raw in files.items():
        path = root / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(raw)
    write_json(
        root / "manifest.json",
        {
            "schema": server.PACKAGE_SCHEMA,
            "private": True,
            "input_files_unchanged": True,
            "input_evidence_sha256": dict.fromkeys(server._EVIDENCE_KEYS, "a" * 64),
            "artifacts": {
                name: {"sha256": sha(raw), "bytes": len(raw)} for name, raw in files.items()
            },
        },
    )
    return root


def modify_manifest(package, action):
    path = package / "manifest.json"
    value = json.loads(path.read_bytes())
    action(value)
    write_json(path, value)


def modify_data(package, action):
    path = package / "replay-data.json"
    value = json.loads(path.read_bytes())
    action(value)
    write_json(path, value)
    raw = path.read_bytes()
    modify_manifest(
        package,
        lambda m: m["artifacts"].update(
            {"replay-data.json": {"sha256": sha(raw), "bytes": len(raw)}}
        ),
    )


@contextmanager
def running(snapshot):
    httpd = server.ReviewServer(("127.0.0.1", 0), server.make_handler(snapshot))
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        yield httpd.server_address
    finally:
        httpd.shutdown()
        thread.join(timeout=3)
        httpd.server_close()


def request(address, path, *, method="GET", headers=None):
    connection = http.client.HTTPConnection(*address, timeout=3)
    try:
        connection.request(method, path, headers=headers or {})
        response = connection.getresponse()
        return response.status, dict(response.getheaders()), response.read()
    finally:
        connection.close()


def test_verified_snapshot_has_only_served_allowlist(package):
    snapshot = server.load_snapshot(package)
    assert set(snapshot) == {
        "/index.html",
        "/playback.js",
        "/style.css",
        "/replay-data.json",
        "/media/clip.mp4",
        "/frames/000.jpg",
    }
    with pytest.raises(TypeError):
        snapshot["/injected"] = (b"bad", "text/plain")


def test_real_http_range_head_and_frozen_media(package):
    snapshot = server.load_snapshot(package)
    (package / "media/clip.mp4").write_bytes(b"replaced after verified snapshot")
    with running(snapshot) as address:
        status, headers, body = request(address, "/media/clip.mp4", headers={"Range": "bytes=2-5"})
        assert status == 206 and body == b"2345"
        assert headers["Content-Range"] == "bytes 2-5/10"
        assert headers["Accept-Ranges"] == "bytes"
        assert headers["Content-Type"] == "video/mp4"
        assert headers["Cache-Control"] == "no-store"
        status, headers, body = request(
            address, "/media/clip.mp4", method="HEAD", headers={"Range": "bytes=-3"}
        )
        assert status == 206 and body == b"" and headers["Content-Length"] == "3"
        assert headers["Content-Range"] == "bytes 7-9/10"
        assert request(address, "/media/clip.mp4")[2] == b"0123456789"
        assert request(address, "/")[0] == 200
    with pytest.raises(ValueError, match="size limit|SHA256"):
        server.load_snapshot(package)


def test_http_unknown_private_and_invalid_ranges(package):
    with running(server.load_snapshot(package)) as address:
        for path in (
            "/manifest.json",
            "/PRIVATE.txt",
            "/../secret",
            "/%2e%2e/secret",
            "/frames/999.jpg",
            "/media/",
        ):
            assert request(address, path)[0] == 404
        for value in ("bytes=10-", "bytes=1-2,4-5", "bytes=-0", "bytes=x-y"):
            status, headers, body = request(address, "/media/clip.mp4", headers={"Range": value})
            assert status == 416 and headers["Content-Range"] == "bytes */10" and body == b""


@pytest.mark.parametrize(
    "name", ["../secret", "unlisted.log", "frames/999.jpg", "manifest.json", "C:/private.txt"]
)
def test_unexpected_manifest_paths_rejected(package, name):
    modify_manifest(
        package, lambda m: m["artifacts"].update({name: {"sha256": "a" * 64, "bytes": 1}})
    )
    with pytest.raises(ValueError):
        server.load_snapshot(package)


@pytest.mark.parametrize(
    "field,value", [("private", False), ("input_files_unchanged", False), ("schema", "other")]
)
def test_invalid_receipt_claims_rejected(package, field, value):
    modify_manifest(package, lambda m: m.update({field: value}))
    with pytest.raises(ValueError, match="private"):
        server.load_snapshot(package)


def test_modified_same_size_asset_rejected(package):
    (package / "media/clip.mp4").write_bytes(b"9876543210")
    with pytest.raises(ValueError, match="SHA256"):
        server.load_snapshot(package)


def test_dto_cannot_reference_arbitrary_image_path(package):
    modify_data(package, lambda d: d["observations"][0].update(image_path="../../secret.jpg"))
    with pytest.raises(ValueError, match="image path"):
        server.load_snapshot(package)


@pytest.mark.parametrize("flag", ["full_pa_verified", "live_availability_verified", "human_label"])
def test_dto_verification_flags_not_promoted(package, flag):
    modify_data(package, lambda d: d["scope"].update({flag: True}))
    with pytest.raises(ValueError, match="unverified"):
        server.load_snapshot(package)


def test_media_hash_bound_to_manifest(package):
    modify_data(package, lambda d: d["media"].update(sha256="f" * 64))
    with pytest.raises(ValueError, match="Media path or SHA256"):
        server.load_snapshot(package)


def test_total_limit_checked_before_media_loading(package, monkeypatch):
    monkeypatch.setattr(server, "MAX_PACKAGE_BYTES", (package / "manifest.json").stat().st_size + 1)
    with pytest.raises(ValueError, match="size limit"):
        server.load_snapshot(package)


def test_per_asset_limit_checked_without_allocating_media(package):
    modify_manifest(
        package, lambda m: m["artifacts"]["media/clip.mp4"].update(bytes=server.MAX_FILE_BYTES + 1)
    )
    with pytest.raises(ValueError, match="hash or size"):
        server.load_snapshot(package)


def test_json_size_limit_and_duplicate_keys(package, monkeypatch):
    monkeypatch.setattr(server, "MAX_JSON_BYTES", 10)
    with pytest.raises(ValueError, match="size limit"):
        server.load_snapshot(package)
    monkeypatch.undo()
    path = package / "manifest.json"
    raw = path.read_text()
    path.write_text(raw[:-1] + ', "private": true}')
    with pytest.raises(ValueError, match="unique"):
        server.load_snapshot(package)


def test_linked_media_rejected(package):
    image = package / "frames/000.jpg"
    target = package / "original.jpg"
    image.rename(target)
    try:
        image.symlink_to(target)
    except OSError as exc:
        pytest.skip(f"OS cannot create test symlink: {exc}")
    with pytest.raises(ValueError, match="Linked"):
        server.load_snapshot(package)


def test_check_cli_does_not_open_socket(package, monkeypatch, capsys):
    def no_server(*args):
        pytest.fail("--check must not open a socket")

    monkeypatch.setattr(server, "ReviewServer", no_server)
    assert server.main(["--directory", str(package), "--check"]) == 0
    assert "verified" in capsys.readouterr().out
    with pytest.raises(SystemExit):
        server.main(["--directory", str(package), "--port", "65536", "--check"])

import importlib.util
import json
import mimetypes
import threading
import urllib.error
import urllib.request
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[1]


def load(name, path):
    s = importlib.util.spec_from_file_location(name, path)
    m = importlib.util.module_from_spec(s)
    s.loader.exec_module(m)
    return m


pack = load("clip_pack", ROOT / "scripts/build_exhibition_clip_pack.py")
serve = load("clip_serve", ROOT / "scripts/clip_pack_runtime/serve.py")
verify = load("clip_verify", ROOT / "scripts/clip_pack_runtime/verify.py")


@pytest.fixture
def sample(tmp_path):
    pid = "12345678-1234-1234-1234-123456789abc"
    filename = f"001_01_{pid}.mp4"
    data = b"0123456789"
    (tmp_path / filename).write_bytes(data)
    digest = pack.sha(tmp_path / filename)
    g = {
        "schema": "pitcheezy-service-game-v2",
        "game": {"game_pk": 849843},
        "pitches": [
            {
                "index": 0,
                "key": "849843:1:1",
                "at_bat_number": 1,
                "pitch_number": 1,
                "inning": 1,
                "half": "Top",
                "batter": {"id": 1, "name": "B"},
                "pitcher": {"id": 2, "name": "P"},
                "actual": {"pitch_type": "SI"},
            }
        ],
    }
    record = {
        "pitch_id": "849843:1:1",
        "play_id": pid,
        "at_bat_number": 1,
        "pitch_number": 1,
        "pitcher_id": 2,
        "batter_id": 1,
        "pitch_type": "SI",
        "video_sha256": digest,
        "bytes": 10,
        "video": "https://example.invalid/clip",
        "duration_seconds": 2.5,
    }
    m = {"game_pk": 849843, "records": [record], "excluded": []}
    d = {
        **record,
        "status": "downloaded",
        "file_path": "clips/849843/" + filename,
        "file_sha256": digest,
        "media_url": record["video"],
        "duration_s": 2.5,
    }
    return g, m, [d], tmp_path


def test_binding_joins_by_id_even_if_source_reordered(sample):
    g, m, d, p = sample
    rows, copies = pack.bind_registry(g, m, d, p)
    assert rows[0]["pitch_key"] == "849843:1:1" and rows[0]["src"].startswith("clips/")
    assert rows[0]["game_pitch_number"] == 1 and len(copies) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("pitcher_id", 3),
        ("batter_id", 3),
        ("pitch_type", "FF"),
        ("at_bat_number", 2),
        ("pitch_number", 2),
    ],
)
def test_semantic_mismatch_rejected(sample, field, value):
    g, m, d, p = sample
    m["records"][0][field] = value
    with pytest.raises(ValueError, match="semantic mismatch"):
        pack.bind_registry(g, m, d, p)


def test_duplicate_id_rejected(sample):
    g, m, d, p = sample
    g["pitches"] *= 2
    with pytest.raises(ValueError, match="duplicate"):
        pack.bind_registry(g, m, d, p)


def test_missing_id_rejected(sample):
    g, m, d, p = sample
    m["records"] = []
    with pytest.raises(ValueError, match="missing/extra"):
        pack.bind_registry(g, m, d, p)


def test_registry_path_traversal_rejected(sample):
    g, m, d, p = sample
    d[0]["file_path"] = "clips/849843/../../../private.mp4"
    with pytest.raises(ValueError, match="unexpected registry"):
        pack.bind_registry(g, m, d, p)


def test_content_corruption_rejected(sample):
    g, m, d, p = sample
    next(p.glob("*.mp4")).write_bytes(b"9876543210")
    with pytest.raises(ValueError, match="bytes/SHA mismatch"):
        pack.bind_registry(g, m, d, p)


def test_exclusion_requires_actual_mismatch(sample):
    g, m, d, p = sample
    m["records"] = []
    m["excluded"] = [
        {
            "pitch_id": "849843:1:1",
            "reason": "pitch_type_mismatch",
            "registry_pitch_type": "SI",
            "received_pitch_type": "FC",
        }
    ]
    g["pitches"][0]["actual"]["pitch_type"] = "FC"
    rows, copies = pack.bind_registry(g, m, d, p)
    assert rows[0]["src"] is None and rows[0]["reason"] == "pitch_type_mismatch" and copies == []
    m["excluded"][0]["received_pitch_type"] = "SI"
    with pytest.raises(ValueError, match="unsubstantiated"):
        pack.bind_registry(g, m, d, p)


@pytest.mark.parametrize(
    "header,expected",
    [
        ("bytes=2-5", (2, 5, True)),
        ("bytes=8-", (8, 9, True)),
        ("bytes=-3", (7, 9, True)),
        ("bytes=0-999", (0, 9, True)),
        (None, (0, 9, False)),
    ],
)
def test_ranges(header, expected):
    assert serve.parse_range(header, 10) == expected


@pytest.mark.parametrize(
    "header", ["bytes=10-", "bytes=6-2", "bytes=-0", "bytes=0-2,4-5", "bytes=-", "bad"]
)
def test_invalid_ranges(header):
    with pytest.raises(ValueError):
        serve.parse_range(header, 10)


@pytest.mark.parametrize(
    "path", ["../secret", "/secret", "a/../secret", "a\\b", "C:/secret", "a//b"]
)
def test_verifier_unsafe_path(tmp_path, path):
    with pytest.raises(ValueError):
        verify.safe_file(tmp_path, path)


def test_http_range_and_allowlist(tmp_path):
    (tmp_path / "clips").mkdir()
    (tmp_path / "clips/a.mp4").write_bytes(b"0123456789")
    (tmp_path / "index.html").write_text("ok")
    (tmp_path / "secret.txt").write_text("secret")
    (tmp_path / "MANIFEST.json").write_text(
        json.dumps(
            {"files": [{"path": "clips/a.mp4"}, {"path": "index.html"}, {"path": "secret.txt"}]}
        )
    )
    server = serve.create_server(tmp_path, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f"http://127.0.0.1:{server.server_port}"
    try:
        with urllib.request.urlopen(
            urllib.request.Request(base + "/clips/a.mp4", headers={"Range": "bytes=2-5"})
        ) as r:
            assert (
                r.status == 206
                and r.read() == b"2345"
                and r.headers["Content-Range"] == "bytes 2-5/10"
                and r.headers["Content-Type"] == "video/mp4"
            )
        with urllib.request.urlopen(
            urllib.request.Request(base + "/clips/a.mp4", method="HEAD")
        ) as r:
            assert r.status == 200 and r.read() == b"" and r.headers["Content-Length"] == "10"
        with urllib.request.urlopen(base + "/") as r:
            assert r.headers["Content-Type"] == "text/html; charset=utf-8"
        for suffix, status in [
            ("/secret.txt", 404),
            ("/../secret.txt", 404),
            ("/clips/a.mp4", 416),
        ]:
            request = urllib.request.Request(
                base + suffix, headers={"Range": "bytes=100-"} if status == 416 else {}
            )
            with pytest.raises(urllib.error.HTTPError) as e:
                urllib.request.urlopen(request)
            assert e.value.code == status
    finally:
        server.shutdown()
        server.server_close()
        thread.join()


def test_manifest_detects_extra_files(tmp_path):
    (tmp_path / "a").write_bytes(b"a")
    manifest = {"files": [{"path": "a", "bytes": 1, "sha256": pack.sha(tmp_path / "a")}]}
    (tmp_path / "MANIFEST.json").write_text(json.dumps(manifest))
    assert verify.verify(tmp_path) == 1
    (tmp_path / "extra").write_text("no")
    with pytest.raises(ValueError, match="unexpected"):
        verify.verify(tmp_path)


def serve_pack(tmp_path):
    """Allowlisted files with the extensions the player needs, served from a thread."""
    (tmp_path / "clips").mkdir()
    (tmp_path / "clips/a.mp4").write_bytes(b"0123456789")
    for name, text in [("index.html", "<!doctype html>"), ("player.css", "body{}"), ("core.js", "1"), ("player.js", "2"), ("registry.json", "{}")]:
        (tmp_path / name).write_text(text)
    (tmp_path / "MANIFEST.json").write_text(json.dumps({"files": [{"path": p} for p in ["clips/a.mp4", "index.html", "player.css", "core.js", "player.js", "registry.json"]]}))
    server = serve.create_server(tmp_path, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, thread


def stop(server, thread):
    server.shutdown()
    server.server_close()
    thread.join()


def head(server, name):
    with urllib.request.urlopen(urllib.request.Request(f"http://127.0.0.1:{server.server_port}/{name}", method="HEAD")) as r:
        return r.status, r.headers["Content-Type"], r.headers["X-Content-Type-Options"]


def test_content_type_is_fixed_and_ignores_registry_mimetypes(tmp_path, monkeypatch):
    # Windows HKCR '.js => text/plain' reaches mimetypes.guess_type; with nosniff Chrome refuses such a script.
    monkeypatch.setattr(mimetypes, "_db", None)
    mimetypes.add_type("text/plain", ".js")
    mimetypes.add_type("text/plain", ".css")
    mimetypes.add_type("text/plain", ".json")
    assert mimetypes.guess_type("core.js")[0] == "text/plain"
    server, thread = serve_pack(tmp_path)
    try:
        expected = {"core.js": "text/javascript; charset=utf-8", "player.js": "text/javascript; charset=utf-8",
                    "player.css": "text/css; charset=utf-8", "index.html": "text/html; charset=utf-8",
                    "": "text/html; charset=utf-8", "registry.json": "application/json", "clips/a.mp4": "video/mp4"}
        for name, content_type in expected.items():
            assert head(server, name) == (200, content_type, "nosniff"), name
    finally:
        stop(server, thread)


def test_allowlisted_file_with_unknown_extension_is_not_served(tmp_path):
    (tmp_path / "clips").mkdir()
    (tmp_path / "clips/odd.bin").write_bytes(b"x")
    (tmp_path / "MANIFEST.json").write_text(json.dumps({"files": [{"path": "clips/odd.bin"}]}))
    server = serve.create_server(tmp_path, port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with pytest.raises(urllib.error.HTTPError) as e:
            urllib.request.urlopen(f"http://127.0.0.1:{server.server_port}/clips/odd.bin")
        assert e.value.code == 404
    finally:
        stop(server, thread)


def test_default_port_is_fixed_and_in_the_exhibition_range():
    assert 8700 <= serve.DEFAULT_PORT <= 8799
    assert serve.Server.allow_reuse_address is False


def test_fixed_port_cannot_bind_over_a_listening_server(tmp_path):
    # On Windows, SO_REUSEADDR (HTTPServer default) lets a second server bind a port that is already listening.
    (tmp_path / "MANIFEST.json").write_text(json.dumps({"files": []}))
    first = serve.create_server(tmp_path, port=0)
    try:
        with pytest.raises(OSError):
            serve.create_server(tmp_path, port=first.server_port)
    finally:
        first.server_close()


def test_reuse_address_stays_on_where_exclusive_bind_is_unavailable(monkeypatch):
    # macOS/Linux have no SO_EXCLUSIVEADDRUSE; there SO_REUSEADDR cannot bind over a listener, and without it an
    # immediate restart loses the fixed port to the stopped server's TIME_WAIT connections.
    import socket
    assert serve.Server.allow_reuse_address is (not hasattr(socket, "SO_EXCLUSIVEADDRUSE"))
    monkeypatch.delattr(socket, "SO_EXCLUSIVEADDRUSE", raising=False)
    posix = load("serve_posix_probe", ROOT / "scripts" / "clip_pack_runtime" / "serve.py")
    assert posix.Server.allow_reuse_address is True


def test_busy_default_port_falls_back_with_message_and_explicit_port_refuses(tmp_path):
    (tmp_path / "MANIFEST.json").write_text(json.dumps({"files": []}))
    first = serve.create_server(tmp_path, port=0)
    busy = first.server_port
    try:
        fallback, message = serve.start_server(tmp_path, busy, explicit=False)
        try:
            assert fallback.server_port != busy and fallback.server_port > 0
            assert str(busy) in message and str(fallback.server_port) in message and "busy" in message
        finally:
            fallback.server_close()
        with pytest.raises(OSError, match=f"port {busy} is already in use"):
            serve.start_server(tmp_path, busy, explicit=True)
        free, message = serve.start_server(tmp_path, 0, explicit=False)
        free.server_close()
        assert message is None
    finally:
        first.server_close()


def mini_pack(tmp_path):
    (tmp_path / "clips").mkdir()
    (tmp_path / "clips/a.mp4").write_bytes(b"0123456789")
    (tmp_path / "index.html").write_text("<!doctype html>")
    files = [{"path": p, "bytes": (tmp_path / p).stat().st_size, "sha256": pack.sha(tmp_path / p)} for p in ["clips/a.mp4", "index.html"]]
    (tmp_path / "MANIFEST.json").write_text(json.dumps({"files": files}))
    assert verify.verify(tmp_path) == 2


@pytest.mark.parametrize(
    "name",
    [".DS_Store", "clips/.DS_Store", "clips/._a.mp4", "._MANIFEST.json", "._clips", "._index.html",
     "__MACOSX/._index.html", "__MACOSX/clips/._a.mp4", "__MACOSX/.DS_Store", "Thumbs.db", "clips/desktop.ini"],
)
def test_verify_tolerates_well_known_os_metadata_with_a_warning(tmp_path, name):
    mini_pack(tmp_path)
    target = tmp_path / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"\x00\x05\x16\x07 metadata")
    warnings = []
    assert verify.verify(tmp_path, warn=warnings.append) == 2
    assert len(warnings) == 1 and name in warnings[0] and "never served" in warnings[0]
    assert verify.verify(tmp_path) == 2  # no warn callback: still passes quietly


@pytest.mark.parametrize(
    "name",
    ["stray.bin", "clips/._stray.mp4", "__MACOSX/real.mp4", "__MACOSX/clips/a.mp4", ".DS_Store.bak", "clips/extra.mp4", "._"],
)
def test_verify_names_each_unexpected_file_instead_of_a_bare_message(tmp_path, name):
    mini_pack(tmp_path)
    target = tmp_path / name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(b"not a pack file")
    with pytest.raises(ValueError) as e:
        verify.verify(tmp_path)
    assert "unexpected files (1: " + name + ")" in str(e.value)


def test_verify_unexpected_list_is_bounded(tmp_path):
    mini_pack(tmp_path)
    names = [f"stray{i:02d}.bin" for i in range(12)]
    for name in names:
        (tmp_path / name).write_bytes(b"x")
    with pytest.raises(ValueError) as e:
        verify.verify(tmp_path)
    text = str(e.value)
    assert "unexpected files (12: " in text and "… and 4 more" in text
    assert all(n in text for n in names[:8]) and not any(n in text for n in names[8:])


@pytest.mark.parametrize("disconnect", [ConnectionResetError, ConnectionAbortedError])
def test_browser_disconnect_during_keepalive_is_quiet(monkeypatch, disconnect):
    def aborted(_self):
        raise disconnect("browser closed connection")

    monkeypatch.setattr(serve.BaseHTTPRequestHandler, "handle", aborted)
    handler = object.__new__(serve.Handler)
    handler.close_connection = False
    handler.handle()
    assert handler.close_connection is True


def test_keepalive_unrelated_error_is_not_hidden(monkeypatch):
    def unexpected(_self):
        raise ValueError("unexpected handler defect")

    monkeypatch.setattr(serve.BaseHTTPRequestHandler, "handle", unexpected)
    handler = object.__new__(serve.Handler)
    with pytest.raises(ValueError, match="unexpected handler defect"):
        handler.handle()


def test_existing_receipt_refuses_build_before_any_output(tmp_path):
    zip_path = tmp_path / "pack.zip"
    receipt_path = zip_path.with_suffix(".receipt.json")
    original = b"previous receipt must survive"
    receipt_path.write_bytes(original)
    args = SimpleNamespace(output=tmp_path / "new-output", zip=zip_path, source_commit=None)
    with pytest.raises(ValueError, match="receipt"):
        pack.build(args)
    assert receipt_path.read_bytes() == original
    assert not args.output.exists() and not zip_path.exists()


def test_receipt_created_between_preflight_and_write_is_preserved(tmp_path):
    receipt_path = tmp_path / "pack.receipt.json"
    assert not receipt_path.exists()
    original = b"receipt created by another process"
    receipt_path.write_bytes(original)
    with pytest.raises(FileExistsError):
        pack.json_write(receipt_path, {"replacement": True}, exclusive=True)
    assert receipt_path.read_bytes() == original

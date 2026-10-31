import importlib.util
import json
import threading
import urllib.error
import urllib.request
from pathlib import Path

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
    server = serve.create_server(tmp_path)
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
            )
        with urllib.request.urlopen(
            urllib.request.Request(base + "/clips/a.mp4", method="HEAD")
        ) as r:
            assert r.status == 200 and r.read() == b"" and r.headers["Content-Length"] == "10"
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

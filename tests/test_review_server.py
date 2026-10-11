"""Portable review delivery validates source binding without producing labels."""

import hashlib
import http.client
import json
import shutil
import subprocess
import sys
import threading
from pathlib import Path

import pytest

from intent import review_server
from intent.reviewer_ui import render_review_page


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def refresh(pack, *, update_binding=True):
    manifest = json.loads((pack / "manifest.json").read_bytes())
    response = json.loads((pack / "response_template.json").read_bytes())
    if update_binding:
        response["manifest_sha256"] = hashlib.sha256(
            (pack / "manifest.json").read_bytes()
        ).hexdigest()
        write_json(pack / "response_template.json", response)
    (pack / "index.html").write_text(
        render_review_page(manifest, response, "test"), encoding="utf-8"
    )


@pytest.fixture
def pack(tmp_path):
    reviewer = tmp_path / "reviewer"
    (reviewer / "images").mkdir(parents=True)
    frames = []
    rows = []
    for index in (1, 2):
        oid = f"review_{index:024x}"
        # These are synthetic bytes: validation checks a binding, not an image decoder.
        raw = f"synthetic image {index}".encode()
        name = f"images/{oid}.jpg"
        (reviewer / name).write_bytes(raw)
        digest = hashlib.sha256(raw).hexdigest()
        frames.append(
            {"observation_id": oid, "image_sha256": digest, "path": name, "width": 20, "height": 12}
        )
        rows.append(
            {
                "observation_id": oid,
                "image_sha256": digest,
                "status": "unreviewed",
                "mitt": None,
                "visibility": "unknown",
                "pose": "unknown",
                "reason": "",
            }
        )
    write_json(
        reviewer / "manifest.json",
        {
            "schema": "intent_source_review_pack_v1",
            "protocol_version": "cv_observation_v1",
            "scope": "development_source_only_recheck",
            "frames": frames,
        },
    )
    write_json(
        reviewer / "response_template.json",
        {
            "schema": "intent_source_review_response_v1",
            "protocol_version": "cv_observation_v1",
            "manifest_sha256": "",
            "reviewer_id": "",
            "rows": rows,
        },
    )
    (reviewer / "review_ui.js").write_bytes(b"/* synthetic UI */")
    refresh(reviewer)
    return reviewer


def test_snapshot_is_read_only_public_and_bound(pack):
    before = {p: p.read_bytes() for p in pack.rglob("*") if p.is_file()}
    snapshot = review_server.load_snapshot(pack)
    assert len(snapshot) == 6
    assert snapshot["/manifest.json"][0] == before[pack / "manifest.json"]
    with pytest.raises(TypeError):
        snapshot["/private.json"] = (b"secret", "application/json")
    assert before == {p: p.read_bytes() for p in before}


@pytest.mark.parametrize(
    "change",
    ["missing", "hash", "path", "duplicate", "bad_dimension", "manifest_keys", "unknown_schema"],
)
def test_invalid_source_is_rejected(pack, change):
    manifest = json.loads((pack / "manifest.json").read_bytes())
    frame = manifest["frames"][0]
    if change == "missing":
        (pack / frame["path"]).unlink()
    elif change == "hash":
        (pack / frame["path"]).write_bytes(b"changed")
    elif change == "path":
        frame["path"] = "../private_selection.json"
    elif change == "duplicate":
        manifest["frames"][1] = frame.copy()
    elif change == "bad_dimension":
        frame["width"] = True
    elif change == "manifest_keys":
        manifest["private_selection"] = "private"
    else:
        manifest["schema"] = "intent_ai_response_v1"
    write_json(pack / "manifest.json", manifest)
    refresh(pack)
    with pytest.raises(ValueError):
        review_server.load_snapshot(pack)


@pytest.mark.parametrize(
    "change",
    [
        "manifest_hash",
        "reviewer",
        "status",
        "point",
        "pose",
        "row_id",
        "row_sha",
        "extra_row_key",
        "rows_reordered",
    ],
)
def test_nonblank_or_unbound_template_is_rejected(pack, change):
    response = json.loads((pack / "response_template.json").read_bytes())
    if change == "manifest_hash":
        response["manifest_sha256"] = "0" * 64
    elif change == "reviewer":
        response["reviewer_id"] = "saved-reviewer"
    elif change == "rows_reordered":
        response["rows"].reverse()
    else:
        key, value = {
            "status": ("status", "marked"),
            "point": ("mitt", [3, 4]),
            "pose": ("pose", "resting"),
            "row_id": ("observation_id", "review_other"),
            "row_sha": ("image_sha256", "0" * 64),
            "extra_row_key": ("private", "data"),
        }[change]
        response["rows"][0][key] = value
    write_json(pack / "response_template.json", response)
    refresh(pack, update_binding=False)
    with pytest.raises(ValueError):
        review_server.load_snapshot(pack)


@pytest.mark.parametrize(
    "change", ["data_mismatch", "extra_script", "duplicate_data", "missing_data"]
)
def test_html_mismatch_is_rejected(pack, change):
    page = (pack / "index.html").read_text(encoding="utf-8")
    if change == "data_mismatch":
        page = page.replace('"width": 20', '"width": 21')
    elif change == "extra_script":
        page += '<script src="other.js"></script>'
    elif change == "duplicate_data":
        page += '<script type="application/json" id="review-data">{}</script>'
    else:
        page = page.replace('id="review-data"', 'id="other-data"')
    (pack / "index.html").write_text(page, encoding="utf-8")
    with pytest.raises(ValueError):
        review_server.load_snapshot(pack)


def test_duplicate_json_keys_are_rejected(pack):
    path = pack / "manifest.json"
    path.write_bytes(path.read_bytes().replace(b'{"schema":', b'{"schema":"wrong","schema":', 1))
    with pytest.raises(ValueError, match="중복"):
        review_server.load_snapshot(pack)


def test_symlinked_image_is_rejected(pack, monkeypatch):
    # Link detection is deterministic even on Windows machines without symlink privileges.
    original = Path.is_symlink
    monkeypatch.setattr(Path, "is_symlink", lambda p: p.suffix == ".jpg" or original(p))
    with pytest.raises(ValueError, match="링크"):
        review_server.load_snapshot(pack)


def test_server_only_serves_verified_snapshot(pack):
    snapshot = review_server.load_snapshot(pack)
    image_path = next(k for k in snapshot if k.startswith("/images/"))
    for name in ("private_selection.json", "response.json", "start_review.py"):
        (pack / name).write_bytes(b"PRIVATE")
    (pack.parent / "private_selection.json").write_bytes(b"PRIVATE PARENT")
    (pack / image_path[1:]).write_bytes(b"CHANGED AFTER VALIDATION")
    (pack / "index.html").write_bytes(b"CHANGED AFTER VALIDATION")
    with review_server.ReviewServer(
        ("127.0.0.1", 0), review_server.make_handler(snapshot)
    ) as server:
        worker = threading.Thread(target=server.serve_forever, daemon=True)
        worker.start()
        try:
            connection = http.client.HTTPConnection(*server.server_address, timeout=3)
            for route in (
                "/",
                "/index.html",
                "/manifest.json",
                "/response_template.json",
                "/review_ui.js",
                image_path,
            ):
                connection.request("GET", route)
                response = connection.getresponse()
                assert response.status == 200
                assert response.read() == snapshot["/index.html" if route == "/" else route][0]
            connection.request("HEAD", image_path)
            response = connection.getresponse()
            assert response.status == 200 and response.read() == b""
            for route in (
                "/images/",
                "/response.json",
                "/private_selection.json",
                "/start_review.py",
                "/../private_selection.json",
                "/%2e%2e/private_selection.json",
                "/%252e%252e/private_selection.json",
                "/images%5c..%5cresponse.json",
            ):
                connection.request("GET", route)
                response = connection.getresponse()
                assert response.status == 404
                assert b"PRIVATE" not in response.read()
            connection.close()
        finally:
            server.shutdown()
            worker.join(timeout=3)
            assert not worker.is_alive()


def test_check_does_not_bind_or_open_browser(pack, monkeypatch, capsys):
    def forbidden(*args, **kwargs):
        pytest.fail("--check must not bind or open a browser")

    monkeypatch.setattr(review_server, "ReviewServer", forbidden)
    monkeypatch.setattr(review_server.webbrowser, "open", forbidden)
    assert review_server.main(["--reviewer", str(pack), "--check", "--open"]) == 0
    assert "2장" in capsys.readouterr().out


@pytest.mark.parametrize("open_browser", [False, True])
def test_main_uses_loopback_autoport_and_browser_is_opt_in(pack, monkeypatch, capsys, open_browser):
    opened = []

    class FakeServer:
        def __init__(self, address, handler):
            assert address == ("127.0.0.1", 0)
            self.server_address = ("127.0.0.1", 23456)

        def __enter__(self):
            return self

        def __exit__(self, *args):
            pass

        def serve_forever(self):
            raise KeyboardInterrupt

    monkeypatch.setattr(review_server, "ReviewServer", FakeServer)
    monkeypatch.setattr(review_server.webbrowser, "open", lambda url: opened.append(url) or True)
    args = ["--reviewer", str(pack)] + (["--open"] if open_browser else [])
    assert review_server.main(args) == 0
    assert opened == (["http://127.0.0.1:23456/"] if open_browser else [])
    message = capsys.readouterr().out
    assert "Mac/Windows" in message and "Ctrl+C" in message and "23456" in message


def test_port_collision_has_actionable_error(pack, capsys):
    with review_server.ReviewServer(("127.0.0.1", 0), review_server.make_handler({})) as server:
        assert review_server.main(["--reviewer", str(pack), "--port", str(server.server_port)]) == 1
    assert "--port 0" in capsys.readouterr().err


def test_missing_pack_has_clear_error_without_binding(tmp_path, monkeypatch, capsys):
    monkeypatch.setattr(review_server, "ReviewServer", lambda *args: pytest.fail("must not bind"))
    assert review_server.main(["--reviewer", str(tmp_path), "--check"]) == 1
    assert "manifest.json" in capsys.readouterr().err


def test_copied_launcher_runs_without_project_or_third_party(pack, tmp_path):
    launcher = pack / "start_review.py"
    shutil.copyfile(review_server.__file__, launcher)
    result = subprocess.run(
        [sys.executable, "-I", "-S", str(launcher), "--check"],
        cwd=tmp_path,
        capture_output=True,
        timeout=10,
    )
    assert result.returncode == 0, result.stderr
    assert b"2" in result.stdout

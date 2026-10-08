"""Serve a verified source-only review pack, using only the Python standard library."""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
import webbrowser
from html.parser import HTMLParser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import MappingProxyType
from urllib.parse import unquote, urlsplit


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, f"JSON 키가 중복되었습니다: {key}")
        result[key] = value
    return result


def _json(raw):
    def reject_constant(value):
        raise ValueError(f"JSON에 유효하지 않은 숫자가 있습니다: {value}")

    return json.loads(raw, object_pairs_hook=_pairs, parse_constant=reject_constant)


def _keys(value, expected, label):
    _require(isinstance(value, dict) and set(value) == set(expected.split()), f"{label}: 키 불일치")


def _linked(path):
    return path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction())


class _EmbeddedData(HTMLParser):
    def __init__(self):
        super().__init__()
        self.blocks = []
        self.scripts = []
        self.current = None

    def handle_starttag(self, tag, attrs):
        if tag != "script":
            return
        attrs = dict(attrs)
        if attrs.get("id") == "review-data":
            _require(
                attrs.get("type") == "application/json" and "src" not in attrs,
                "HTML의 검토 자료 형식이 다릅니다",
            )
            self.current = []
            self.blocks.append(self.current)
        else:
            self.scripts.append(attrs.get("src"))

    def handle_data(self, data):
        if self.current is not None:
            self.current.append(data)

    def handle_endtag(self, tag):
        if tag == "script":
            self.current = None


def load_snapshot(reviewer):
    """Validate bindings and blank state; retain only public, verified file bytes."""
    root = Path(reviewer).absolute()
    _require(not _linked(root) and root.is_dir(), "reviewer 폴더가 없거나 링크입니다")
    root = root.resolve()
    files = {}

    def read(name, content_type):
        path = root / name
        _require(path.resolve().is_relative_to(root), f"검토 폴더 밖 경로입니다: {name}")
        for part in (path, *path.parents):
            if part == root:
                break
            _require(not _linked(part), f"링크는 제공하지 않습니다: {name}")
        _require(path.is_file(), f"필수 파일이 없습니다: {name}")
        raw = path.read_bytes()
        files["/" + name] = (raw, content_type)
        return raw

    raw_manifest = read("manifest.json", "application/json; charset=utf-8")
    manifest = _json(raw_manifest)
    _keys(manifest, "schema protocol_version scope frames", "manifest")
    _require(
        manifest["schema"] == "intent_source_review_pack_v1"
        and manifest["protocol_version"] == "cv_observation_v1"
        and manifest["scope"] == "development_source_only_recheck",
        "지원하지 않는 검토 팩입니다",
    )
    frames = manifest["frames"]
    _require(isinstance(frames, list) and bool(frames), "검토 이미지 목록이 비어 있습니다")
    identifiers = set()
    for frame in frames:
        _keys(frame, "observation_id image_sha256 path width height", "manifest frame")
        oid, digest = frame["observation_id"], frame["image_sha256"]
        _require(
            isinstance(oid, str) and re.fullmatch(r"review_[A-Za-z0-9_-]+", oid),
            "관측 ID 형식이 다릅니다",
        )
        _require(oid not in identifiers, "관측 ID가 중복되었습니다")
        identifiers.add(oid)
        _require(
            isinstance(digest, str) and re.fullmatch(r"[0-9a-f]{64}", digest),
            "이미지 SHA 형식이 다릅니다",
        )
        _require(frame["path"] == f"images/{oid}.jpg", "이미지 경로가 관측 ID와 다릅니다")
        _require(
            all(type(frame[k]) is int and frame[k] > 0 for k in ("width", "height")),
            "이미지 크기가 유효하지 않습니다",
        )
        raw = read(frame["path"], "image/jpeg")
        _require(hashlib.sha256(raw).hexdigest() == digest, f"이미지 SHA 불일치: {oid}")

    response = _json(read("response_template.json", "application/json; charset=utf-8"))
    _keys(response, "schema protocol_version manifest_sha256 reviewer_id rows", "template")
    _require(
        response["schema"] == "intent_source_review_response_v1"
        and response["protocol_version"] == manifest["protocol_version"]
        and response["manifest_sha256"] == hashlib.sha256(raw_manifest).hexdigest(),
        "응답 양식과 manifest가 일치하지 않습니다",
    )
    expected_rows = [
        {
            "observation_id": f["observation_id"],
            "image_sha256": f["image_sha256"],
            "status": "unreviewed",
            "mitt": None,
            "visibility": "unknown",
            "pose": "unknown",
            "reason": "",
        }
        for f in frames
    ]
    _require(
        response["reviewer_id"] == "" and response["rows"] == expected_rows,
        "응답 양식이 빈 상태가 아니거나 이미지 목록과 다릅니다",
    )
    page = read("index.html", "text/html; charset=utf-8").decode("utf-8")
    parser = _EmbeddedData()
    parser.feed(page)
    parser.close()
    _require(
        len(parser.blocks) == 1 and parser.scripts == ["review_ui.js"],
        "HTML의 검토 자료 또는 스크립트가 다릅니다",
    )
    _require(
        _json("".join(parser.blocks[0])) == {"manifest": manifest, "response": response},
        "HTML에 포함된 자료와 manifest/빈 양식이 다릅니다",
    )
    _require(
        bool(read("review_ui.js", "text/javascript; charset=utf-8")), "화면 스크립트가 비었습니다"
    )
    return MappingProxyType(files)


def make_handler(snapshot):
    """Create a handler with no filesystem access and no directory listings."""

    class ReviewHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self._send(True)

        def do_HEAD(self):
            self._send(False)

        def _send(self, body):
            try:
                path = unquote(urlsplit(self.path).path, errors="strict")
            except ValueError:
                path = ""
            item = snapshot.get("/index.html" if path == "/" else path)
            if item is None:
                self.send_error(404)
                return
            raw, content_type = item
            self.send_response(200)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(len(raw)))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.end_headers()
            if body:
                self.wfile.write(raw)

        def log_message(self, format, *args):
            pass

    return ReviewHandler


class ReviewServer(ThreadingHTTPServer):
    # Do not permit another Windows process to reuse this listening address.
    allow_reuse_address = False


def main(argv=None):
    parser = argparse.ArgumentParser(description="검토 자료를 검사하고 이 컴퓨터에서 엽니다.")
    parser.add_argument(
        "--reviewer",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="reviewer 폴더 (기본: 이 실행 파일이 있는 폴더)",
    )
    parser.add_argument("--port", type=int, default=0, help="포트 번호 (기본 0: 빈 포트 자동 선택)")
    parser.add_argument("--open", action="store_true", help="검사 후 기본 브라우저 열기")
    parser.add_argument("--check", action="store_true", help="자료 검사만 하고 종료")
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("포트는 0부터 65535 사이여야 합니다")
    try:
        snapshot = load_snapshot(args.reviewer)
    except (OSError, ValueError) as exc:
        print(f"검토 자료 검사 실패: {exc}", file=sys.stderr)
        return 1
    print(f"검토 자료 검사 통과: 이미지 {len(snapshot) - 4}장", flush=True)
    if args.check:
        return 0
    try:
        server = ReviewServer(("127.0.0.1", args.port), make_handler(snapshot))
    except OSError as exc:
        print(
            f"검토 서버를 시작할 수 없습니다: {exc}\n"
            "다른 프로그램이 포트를 사용 중이면 --port 0으로 다시 실행하세요.",
            file=sys.stderr,
        )
        return 1
    with server:
        url = f"http://127.0.0.1:{server.server_address[1]}/"
        print(
            f"검토 주소: {url}\n이 주소는 지금 실행한 컴퓨터에서만 열립니다.\n"
            "다른 Mac/Windows에서 보려면 reviewer 폴더 전체를 그 컴퓨터로 옮겨 실행하세요.\n"
            "종료: Ctrl+C (종료 전에 화면에서 응답/초안을 파일로 저장하세요).",
            flush=True,
        )
        if args.open:
            try:
                opened = webbrowser.open(url)
            except (OSError, webbrowser.Error):
                opened = False
            if not opened:
                print("브라우저가 열리지 않으면 위 주소를 직접 여세요.", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            print("\n검토 서버를 종료합니다.", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

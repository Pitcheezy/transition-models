"""Check and serve a private review package with Python 3.10+ standard library only.

The builder copies this file byte-for-byte to launch_review.py. Hashes bind the
local package bytes; they do not authenticate a provider or validate a policy.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import os
import re
import stat
import sys
import webbrowser
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from types import MappingProxyType
from urllib.parse import unquote, urlsplit

PACKAGE_SCHEMA = "pitcheezy-private-service-review-package-v2"
REPORT_SCHEMA = "pitcheezy-service-review-v1"
MEDIA_SCHEMA = "pitcheezy-service-review-media-v1"
PROFILE = "teammate_export_20261009_v1"
MAX_JSON_BYTES = 5 * 1024 * 1024
MAX_RECEIPT_BYTES = 1024 * 1024
MAX_FILE_BYTES = 64 * 1024 * 1024
MAX_TOTAL_BYTES = 128 * 1024 * 1024
STATIC_ASSETS = {
    "index.html",
    "review.js",
    "style.css",
    "review-media.json",
    "launch_review.py",
    "START_WINDOWS.cmd",
    "START_MAC.command",
    "PRIVATE.txt",
}
CONTENT_TYPES = {
    "index.html": "text/html; charset=utf-8",
    "review.js": "text/javascript; charset=utf-8",
    "style.css": "text/css; charset=utf-8",
    "review-data.json": "application/json; charset=utf-8",
    "review-media.json": "application/json; charset=utf-8",
}


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _digest(value):
    return isinstance(value, str) and re.fullmatch(r"[a-f0-9]{64}", value) is not None


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _json(raw):
    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result, "JSON object keys must be unique.")
            result[key] = value
        return result

    def reject_constant(_value):
        raise ValueError("JSON numbers must be finite.")

    def finite_float(value):
        number = float(value)
        _require(math.isfinite(number), "JSON numbers must be finite.")
        return number

    try:
        return json.loads(
            raw.decode("utf-8-sig"),
            object_pairs_hook=pairs,
            parse_constant=reject_constant,
            parse_float=finite_float,
        )
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError):
        raise ValueError("Package JSON must contain a valid UTF-8 document.") from None


def _relative_name(name):
    _require(
        isinstance(name, str)
        and len(name) <= 240
        and re.fullmatch(r"[A-Za-z0-9_.-]+(?:/[A-Za-z0-9_.-]+)*", name),
        "Package paths must be safe relative paths.",
    )
    for part in name.split("/"):
        stem = part.split(".", 1)[0].upper()
        _require(
            part not in {".", ".."}
            and not part.endswith(".")
            and stem not in {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"}
            and not re.fullmatch(r"(?:COM|LPT)[1-9]", stem),
            "Package paths must not use traversal or device names.",
        )
    return name


def _linked(path):
    metadata = path.lstat()
    # FILE_ATTRIBUTE_REPARSE_POINT covers Windows junctions on Python 3.10 too.
    return stat.S_ISLNK(metadata.st_mode) or bool(
        getattr(metadata, "st_file_attributes", 0)
        & getattr(stat, "FILE_ATTRIBUTE_REPARSE_POINT", 0x400)
    )


class _Reader:
    def __init__(self, directory):
        root = Path(directory).absolute()
        _require(not _linked(root) and root.is_dir(), "Review directory is missing or linked.")
        self.root = root.resolve()
        self.total = 0

    def _path(self, name):
        path = self.root / _relative_name(name)
        for part in (path, *path.parents):
            if part == self.root:
                break
            _require(not _linked(part), "Linked package files or directories are not accepted.")
        _require(path.resolve().is_relative_to(self.root), "Package path leaves its directory.")
        return path

    def read(self, name, limit):
        path = self._path(name)
        before = path.stat()
        _require(stat.S_ISREG(before.st_mode), "Package input must be a regular file.")
        allowance = min(limit, MAX_TOTAL_BYTES - self.total)
        _require(0 <= before.st_size <= allowance, "Package size limit exceeded.")
        flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
        flags |= getattr(os, "O_NOFOLLOW", 0)
        descriptor = os.open(path, flags)
        with os.fdopen(descriptor, "rb") as stream:
            opened = os.fstat(stream.fileno())
            _require(
                stat.S_ISREG(opened.st_mode)
                and (opened.st_dev, opened.st_ino) == (before.st_dev, before.st_ino)
                and opened.st_size <= allowance,
                "Package file changed while opening or exceeds its size limit.",
            )
            raw = stream.read(allowance + 1)
        _require(len(raw) <= allowance, "Package size limit exceeded.")
        after = self._path(name).stat()
        _require(
            (after.st_dev, after.st_ino, after.st_size, after.st_mtime_ns)
            == (opened.st_dev, opened.st_ino, opened.st_size, opened.st_mtime_ns)
            and len(raw) == after.st_size,
            "Package file changed while reading.",
        )
        self.total += len(raw)
        return raw


def _report_keys(report, receipt):
    _require(
        isinstance(report, dict)
        and report.get("schema") == REPORT_SCHEMA
        and report.get("profile") == PROFILE,
        "Unsupported normalized report schema or profile.",
    )
    source, game = report.get("source"), report.get("game")
    _require(
        isinstance(source, dict) and source.get("sha256") == receipt["source_sha256"],
        "Report source hash does not match the receipt.",
    )
    _require(
        isinstance(game, dict)
        and type(game.get("game_pk")) is int
        and 1 <= game["game_pk"] <= 2**31 - 1,
        "Report game identity is invalid.",
    )
    pitches = report.get("pitches")
    _require(isinstance(pitches, list) and len(pitches) <= 2000, "Invalid report pitch list.")
    keys = set()
    for pitch in pitches:
        _require(isinstance(pitch, dict), "Invalid report pitch row.")
        pa, number = pitch.get("at_bat_number"), pitch.get("pitch_number")
        _require(
            type(pa) is int and 1 <= pa <= 999 and type(number) is int and 1 <= number <= 100,
            "Invalid report pitch identity.",
        )
        key = f"{game['game_pk']}:{pa}:{number}"
        _require(
            pitch.get("key") == key
            and pitch.get("pa_key") == f"{game['game_pk']}:{pa}"
            and key not in keys,
            "Report pitch keys are duplicate or inconsistent.",
        )
        keys.add(key)
    summary = report.get("summary")
    _require(
        isinstance(summary, dict)
        and type(summary.get("pitches")) is int
        and summary["pitches"] == len(keys)
        and summary == receipt.get("summary"),
        "Receipt summary does not match the report.",
    )
    return game["game_pk"], keys


def _media_files(media, game_pk, keys, receipt):
    _require(
        isinstance(media, dict)
        and media.get("schema") == MEDIA_SCHEMA
        and type(media.get("game_pk")) is int
        and media["game_pk"] == game_pk
        and media.get("source_sha256") == receipt["source_sha256"],
        "Media manifest does not match the report source and game.",
    )
    clips = media.get("clips")
    _require(isinstance(clips, list) and len(clips) <= len(keys), "Invalid media clip list.")
    seen_keys, seen_plays, files = set(), set(), {}
    for clip in clips:
        _require(isinstance(clip, dict), "Invalid media clip row.")
        key, play_id, duration = (
            clip.get("pitch_key"),
            clip.get("play_id"),
            clip.get("duration_seconds"),
        )
        _require(
            isinstance(key, str) and key in keys and key not in seen_keys,
            "Media pitch key is missing, duplicate or outside this report.",
        )
        _require(
            isinstance(play_id, str)
            and re.fullmatch(r"[A-Za-z0-9_-]{1,100}", play_id)
            and play_id not in seen_plays,
            "Media play identity is missing, duplicate or invalid.",
        )
        _require(
            type(duration) in (int, float) and 0 < duration <= 3600 and math.isfinite(duration),
            "Media duration must be a positive finite number of seconds.",
        )
        seen_keys.add(key)
        seen_plays.add(play_id)
        for field, extension, content_type in (
            ("video", ".mp4", "video/mp4"),
            ("poster", ".jpg", "image/jpeg"),
        ):
            name = _relative_name(clip.get(field))
            digest = clip.get(field + "_sha256")
            _require(
                name.startswith("media/")
                and name.endswith(extension)
                and name not in files
                and _digest(digest)
                and receipt["assets_sha256"].get(name) == digest,
                "Media path or hash does not match the receipt.",
            )
            files[name] = content_type
    return files


def load_snapshot(directory):
    """Validate the complete package and freeze only the bytes served to browsers."""
    reader = _Reader(directory)
    receipt = _json(reader.read("receipt.json", MAX_RECEIPT_BYTES))
    _require(
        isinstance(receipt, dict)
        and receipt.get("schema") == PACKAGE_SCHEMA
        and receipt.get("profile") == PROFILE
        and receipt.get("public_distribution") is False
        and receipt.get("live_validation") is False
        and _digest(receipt.get("source_sha256"))
        and _digest(receipt.get("report_sha256")),
        "Unsupported or invalid private package receipt.",
    )
    assets = receipt.get("assets_sha256")
    _require(
        isinstance(assets, dict) and STATIC_ASSETS.issubset(assets) and len(assets) <= 4008,
        "Package asset list is missing required files or exceeds the limit.",
    )
    folded_names = set()
    for name, digest in assets.items():
        _relative_name(name)
        _require(_digest(digest), "Invalid asset SHA256.")
        _require(name.casefold() not in folded_names, "Package paths collide by letter case.")
        folded_names.add(name.casefold())
    raw_report = reader.read("review-data.json", MAX_JSON_BYTES)
    _require(_sha(raw_report) == receipt["report_sha256"], "Report SHA256 mismatch.")
    game_pk, keys = _report_keys(_json(raw_report), receipt)
    raw_media = reader.read("review-media.json", MAX_JSON_BYTES)
    _require(_sha(raw_media) == assets["review-media.json"], "Media manifest SHA256 mismatch.")
    media_files = _media_files(_json(raw_media), game_pk, keys, receipt)
    _require(set(assets) == STATIC_ASSETS | media_files.keys(), "Unexpected package asset path.")
    files = {
        "/review-data.json": (raw_report, CONTENT_TYPES["review-data.json"]),
        "/review-media.json": (raw_media, CONTENT_TYPES["review-media.json"]),
    }
    for name, digest in assets.items():
        if name == "review-media.json":
            continue
        raw = reader.read(name, MAX_FILE_BYTES if name in media_files else MAX_JSON_BYTES)
        _require(bool(raw) and _sha(raw) == digest, "Package asset is empty or its SHA256 differs.")
        content_type = CONTENT_TYPES.get(name) or media_files.get(name)
        if content_type is not None:
            files["/" + name] = (raw, content_type)
    return MappingProxyType(files)


def _byte_range(value, length):
    """Return inclusive bounds for one byte range; reject multipart and invalid requests."""
    _require(isinstance(value, str) and len(value) <= 128, "Invalid byte range.")
    match = re.fullmatch(r"bytes=(\d*)-(\d*)", value.strip())
    _require(match is not None and length > 0, "Invalid byte range.")
    first, last = match.groups()
    _require(bool(first or last), "Invalid byte range.")
    if not first:
        suffix = int(last)
        _require(suffix > 0, "Invalid suffix range.")
        return max(0, length - suffix), length - 1
    start = int(first)
    stop = int(last) if last else length - 1
    _require(0 <= start < length and stop >= start, "Unsatisfiable byte range.")
    return start, min(stop, length - 1)


def make_handler(snapshot):
    """Serve immutable verified bytes only, without request-time filesystem reads."""
    snapshot = MappingProxyType(dict(snapshot))

    class ReviewHandler(BaseHTTPRequestHandler):
        def do_GET(self):
            self._send(True)

        def do_HEAD(self):
            self._send(False)

        def _send(self, body):
            try:
                parsed = urlsplit(self.path)
                path = unquote(parsed.path, errors="strict")
                if parsed.scheme or parsed.netloc or "\\" in path:
                    path = ""
            except (ValueError, UnicodeDecodeError):
                path = ""
            item = snapshot.get("/index.html" if path == "/" else path)
            if item is None:
                self.send_error(404)
                return
            raw, content_type = item
            start, stop, status_code = 0, len(raw) - 1, 200
            ranges = self.headers.get_all("Range", [])
            if ranges and content_type == "video/mp4":
                try:
                    _require(len(ranges) == 1, "Multiple ranges are not supported.")
                    start, stop = _byte_range(ranges[0], len(raw))
                    status_code = 206
                except ValueError:
                    self.send_response(416)
                    self.send_header("Content-Range", f"bytes */{len(raw)}")
                    self.send_header("Content-Length", "0")
                    self.send_header("Accept-Ranges", "bytes")
                    self.send_header("Cache-Control", "no-store")
                    self.end_headers()
                    return
            self.send_response(status_code)
            self.send_header("Content-Type", content_type)
            self.send_header("Content-Length", str(stop - start + 1))
            self.send_header("Cache-Control", "no-store")
            self.send_header("X-Content-Type-Options", "nosniff")
            self.send_header("Referrer-Policy", "no-referrer")
            if content_type == "video/mp4":
                self.send_header("Accept-Ranges", "bytes")
            if status_code == 206:
                self.send_header("Content-Range", f"bytes {start}-{stop}/{len(raw)}")
            self.end_headers()
            if body:
                try:
                    self.wfile.write(raw[start : stop + 1])
                except (BrokenPipeError, ConnectionResetError):
                    pass  # Browsers cancel the previous request while seeking.

        def log_message(self, format, *args):
            pass

    return ReviewHandler


class ReviewServer(ThreadingHTTPServer):
    allow_reuse_address = False
    daemon_threads = True


def main(argv=None):
    parser = argparse.ArgumentParser(description="비공개 검토 팩을 검사하고 이 컴퓨터에서 엽니다.")
    parser.add_argument(
        "--reviewer",
        "--directory",
        type=Path,
        default=Path(__file__).resolve().parent,
        help="검토 팩 폴더 (기본: 이 실행 파일이 있는 폴더)",
    )
    parser.add_argument("--port", type=int, default=0, help="포트 번호 (기본 0: 빈 포트 자동 선택)")
    parser.add_argument("--check", action="store_true", help="파일 검사만 하고 종료")
    parser.add_argument("--open", action="store_true", help="검사 후 기본 브라우저 열기")
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("포트는 0부터 65535 사이여야 합니다")
    try:
        snapshot = load_snapshot(args.reviewer)
    except (OSError, ValueError) as exc:
        print(f"검토 팩 검사 실패: {exc}", file=sys.stderr)
        return 1
    clips = sum(content_type == "video/mp4" for _, content_type in snapshot.values())
    print(f"검토 팩 검사 통과: 영상 {clips}개. 내부 검토 전용입니다.", flush=True)
    if args.check:
        return 0
    try:
        server = ReviewServer(("127.0.0.1", args.port), make_handler(snapshot))
    except OSError:
        print("검토 서버를 시작할 수 없습니다. --port 0으로 다시 실행하세요.", file=sys.stderr)
        return 1
    with server:
        url = f"http://127.0.0.1:{server.server_address[1]}/"
        print(
            f"검토 주소: {url}\n이 주소는 지금 실행한 컴퓨터에서만 열립니다.\n"
            "다른 컴퓨터에서는 폴더 전체를 옮긴 뒤 실행하세요. 종료: Ctrl+C.",
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

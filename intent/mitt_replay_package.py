"""Package and serve the frozen CV43 replay using only the Python standard library.

The package manifest is a consistency root, not a signature. Authenticate a transferred ZIP
against its separately obtained SHA-256 before extraction. No tracking, image decoding or OCR
is performed here, and HTTP serves only immutable, validated viewer bytes.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import lzma
import math
import os
import re
import stat
import sys
import webbrowser
import zipfile
import zlib
from pathlib import Path, PurePosixPath
from types import MappingProxyType, ModuleType

SCHEMA = "pitcheezy-private-replay-package-v1"
RECEIPT_SCHEMA = "pitcheezy-seed-gate-frame-view-receipt-v1"
COMPARISON_SCHEMA = "pitcheezy-seed-gate-frame-comparison-dev-v1"
VIEW_ASSETS = {"index.html", "review.js", "style.css", "payload.json", "ocr.json"}
ROOT_FILES = {"run_replay.py", "review_server.py", "README.txt", "manifest.json"}
MAX_FILE_BYTES = 128 * 1024 * 1024
MAX_TOTAL_BYTES = 1024 * 1024 * 1024
MAX_FILES = 10000
MAX_RELATIVE_PATH = 240
TRUST = "Manifest consistency is not authentication; verify a separately trusted ZIP SHA-256."
README = """저장된 CV43 개발 자료 재생팩

Python 3.10 이상이 필요하며 별도 패키지 설치는 필요하지 않습니다.
이 폴더에서 다음 명령으로 파일을 검사하고 엽니다.

  python -B -S run_replay.py --check
  python -B -S run_replay.py --open

브라우저가 자동으로 열리지 않으면 출력된 주소를 직접 여세요.
주소는 이 컴퓨터의 127.0.0.1과 자동 선택된 빈 포트만 사용합니다.
종료는 Ctrl+C입니다. 실행 중 디스크가 바뀌어도 검증 당시의 자료만 제공합니다.
폴더 전체를 보존하세요. 파일의 추가·누락·변조는 검사 실패로 처리합니다.

저장된 10구 개발 기록을 재생하며 추적·OCR·모델을 실행하지 않습니다.
AI 관측은 사람 정답이 아니며, 독립 정확도나 실시간 성능을 증명하지 않습니다.
MLB 이미지가 포함된 비공개 개발 자료이며 Git·공개링크에 올리지 않습니다. 기존 M3/사람검증과 별개입니다.

동봉 manifest는 파일 일관성의 기준이며 전자서명이나 발신자 인증이 아닙니다.
ZIP을 전달받았다면 별도 신뢰 경로로 받은 SHA-256과 먼저 비교하세요.
실행 코드와 manifest를 함께 바꾼 악의적 묶음을 자체 검사로 인증할 수 없습니다.
"""


def _require(condition, message):
    if not condition:
        raise ValueError(message)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _pin(value, length=64):
    _require(
        isinstance(value, str) and re.fullmatch(rf"[a-f0-9]{{{length}}}", value),
        "expected a lowercase hexadecimal pin",
    )


def _json(raw):
    def pairs(values):
        result = {}
        for name, value in values:
            _require(name not in result, "duplicate JSON key")
            result[name] = value
        return result

    def integer(value):
        _require(len(value.lstrip("-")) <= 16, "oversized JSON integer")
        number = int(value)
        _require(abs(number) <= 2**53 - 1, "inexact JSON integer")
        return number

    def floating(value):
        number = float(value)
        _require(math.isfinite(number), "nonfinite JSON number")
        return number

    def constant(_value):
        raise ValueError("nonfinite JSON constant")

    try:
        return json.loads(
            raw.decode("utf-8"),
            object_pairs_hook=pairs,
            parse_int=integer,
            parse_float=floating,
            parse_constant=constant,
        )
    except (UnicodeDecodeError, json.JSONDecodeError) as exc:
        raise ValueError("invalid UTF-8 JSON") from exc


def _encoded(value):
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")


def _safe_name(name):
    _require(
        isinstance(name, str) and name not in ("", ".") and len(name) <= MAX_RELATIVE_PATH,
        "invalid relative path",
    )
    path = PurePosixPath(name)
    _require(not path.is_absolute() and path.as_posix() == name, "noncanonical relative path")
    for part in path.parts:
        _require(
            re.fullmatch(r"[A-Za-z0-9_.-]+", part)
            and part not in (".", "..")
            and not part.endswith("."),
            "unsafe relative path",
        )
        _require(
            part.split(".")[0].upper()
            not in {
                "CON",
                "PRN",
                "AUX",
                "NUL",
                *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10)),
            },
            "reserved Windows path",
        )
    return name


def _names(names):
    _require(0 < len(names) <= MAX_FILES, "invalid file count")
    folded, components = set(), {}
    for name in names:
        _safe_name(name)
        key = name.casefold()
        _require(key not in folded, "duplicate or case-colliding path")
        folded.add(key)
        for prefix in (PurePosixPath(name), *PurePosixPath(name).parents):
            text = str(prefix)
            if text == ".":
                continue
            _require(
                components.setdefault(text.casefold(), text) == text,
                "case-colliding directory path",
            )
    for name in folded:
        _require(
            not any(str(p) in folded for p in PurePosixPath(name).parents if str(p) != "."),
            "file/directory path collision",
        )


def _linked(path):
    if path.is_symlink() or (hasattr(path, "is_junction") and path.is_junction()):
        return True
    try:
        # lstat exposes reparse points on Windows even before Path.is_junction (Python 3.12).
        return bool(getattr(path.lstat(), "st_file_attributes", 0) & 0x400)
    except FileNotFoundError:
        return False


def _tree(folder):
    root = Path(folder).absolute()
    _require(not _linked(root) and root.is_dir(), "missing or linked package directory")
    root = root.resolve()
    result, total, directories = {}, 0, set()
    pending = [root]
    while pending:
        current = pending.pop()
        with os.scandir(current) as entries:
            for entry in entries:
                path = Path(entry.path)
                _require(
                    not _linked(path) and path.resolve().is_relative_to(root),
                    "linked or escaped path",
                )
                if entry.is_dir(follow_symlinks=False):
                    directories.add(_safe_name(path.relative_to(root).as_posix()))
                    pending.append(path)
                    continue
                info = entry.stat(follow_symlinks=False)
                _require(stat.S_ISREG(info.st_mode), "only regular files are allowed")
                _require(info.st_size <= MAX_FILE_BYTES, "file exceeds package limit")
                total += info.st_size
                _require(total <= MAX_TOTAL_BYTES, "package exceeds size limit")
                name = path.relative_to(root).as_posix()
                _safe_name(name)
                result[name] = path.read_bytes()
                _require(len(result[name]) == info.st_size, "file changed while reading")
                _require(len(result) <= MAX_FILES, "too many package files")
    _names(list(result))
    expected_dirs = {
        str(p) for name in result for p in PurePosixPath(name).parents if str(p) != "."
    }
    _require(directories == expected_dirs, "extra empty directory")
    return result


def _bindings(files, records):
    _require(isinstance(records, dict) and set(files) == set(records), "file list differs")
    _names(list(records))
    for name, raw in files.items():
        record = records[name]
        _require(
            isinstance(record, dict) and set(record) == {"sha256", "bytes"}, "invalid file record"
        )
        _pin(record["sha256"])
        _require(
            type(record["bytes"]) is int and 0 <= record["bytes"] <= MAX_FILE_BYTES,
            "invalid byte count",
        )
        _require(
            record["bytes"] == len(raw) and record["sha256"] == _sha(raw), "file size/SHA differs"
        )


def _source(files, pin):
    _pin(pin)
    _require(
        "receipt.json" in files and _sha(files["receipt.json"]) == pin, "source receipt SHA differs"
    )
    receipt = _json(files["receipt.json"])
    _require(
        isinstance(receipt, dict)
        and receipt.get("schema") == RECEIPT_SCHEMA
        and receipt.get("comparison_schema") == COMPARISON_SCHEMA
        and receipt.get("input_unchanged") is True
        and receipt.get("frame_images_unchanged") is True
        and receipt.get("no_new_tracking_or_model_calls") is True
        and receipt.get("no_new_ocr_calls") is True
        and receipt.get("independent_decoded_pts_verified") is False,
        "unsupported CV43 receipt",
    )
    viewer = {name: raw for name, raw in files.items() if name != "receipt.json"}
    _bindings(viewer, receipt.get("files"))
    _require(
        all(len("viewer/" + name) <= MAX_RELATIVE_PATH for name in files),
        "source path exceeds viewer-prefixed package limit",
    )
    _require(VIEW_ASSETS <= viewer.keys(), "missing viewer assets")
    frame_names = set(viewer) - VIEW_ASSETS
    _require(
        all(
            re.fullmatch(r"frames/[1-9]\d{0,9}_[1-9]\d{0,6}_[1-9]\d{0,6}/\d+\.jpg", n, re.ASCII)
            for n in frame_names
        ),
        "unexpected CV43 viewer path",
    )
    _require(
        type(receipt.get("displayed_frames")) is int
        and receipt["displayed_frames"] == len(frame_names) > 0,
        "frame count differs",
    )
    return viewer


def _validate(files):
    _require("manifest.json" in files, "missing package manifest")
    manifest = _json(files["manifest.json"])
    _require(
        isinstance(manifest, dict)
        and set(manifest) == {"schema", "source_commit", "source_receipt_sha256", "trust", "files"},
        "invalid package manifest fields",
    )
    _require(
        manifest["schema"] == SCHEMA and manifest["trust"] == TRUST, "unsupported package manifest"
    )
    _pin(manifest["source_commit"], 40)
    _pin(manifest["source_receipt_sha256"])
    _bindings({n: raw for n, raw in files.items() if n != "manifest.json"}, manifest["files"])
    _require(
        {n for n in files if not n.startswith("viewer/")} == ROOT_FILES,
        "unexpected package root file",
    )
    source = {n.removeprefix("viewer/"): raw for n, raw in files.items() if n.startswith("viewer/")}
    return _source(source, manifest["source_receipt_sha256"])


def _snapshot(viewer):
    types = {
        ".html": "text/html; charset=utf-8",
        ".js": "text/javascript; charset=utf-8",
        ".css": "text/css; charset=utf-8",
        ".json": "application/json; charset=utf-8",
        ".jpg": "image/jpeg",
    }
    return MappingProxyType(
        {"/" + name: (raw, types[PurePosixPath(name).suffix]) for name, raw in viewer.items()}
    )


def check(package):
    """Validate every package file and return immutable viewer-only HTTP bytes."""
    return _snapshot(_validate(_tree(package)))


def _new(path, sources):
    path = Path(path).absolute()
    _require(not path.exists() and not _linked(path), "output already exists")
    for parent in path.parents:
        _require(not _linked(parent), "output has a linked parent")
    path = path.resolve()
    _require(
        not any(path == p or path.is_relative_to(p) for p in sources), "output overlaps an input"
    )
    return path


def _write(files, out):
    out.mkdir(parents=True, exist_ok=False)
    for name, raw in files.items():
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open("xb") as stream:
            stream.write(raw)


def _zip_bytes(files):
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", compression=zipfile.ZIP_DEFLATED) as archive:
        for name in sorted(files):
            info = zipfile.ZipInfo(name, date_time=(2026, 10, 27, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = zipfile.ZIP_DEFLATED
            archive.writestr(info, files[name])
    return buffer.getvalue()


def _runtime_file(path):
    _require(path.exists() and not _linked(path), "runtime file is missing or linked")
    info = path.stat()
    _require(stat.S_ISREG(info.st_mode), "runtime file must be regular")
    _require(info.st_size <= MAX_FILE_BYTES, "runtime file exceeds size limit")
    with path.open("rb") as stream:
        raw = stream.read(MAX_FILE_BYTES + 1)
    _require(len(raw) == info.st_size, "runtime file changed or exceeds size limit")
    return raw


def build(*, pack, receipt_sha256, source_commit, out, archive):
    """Copy the pinned CV43 bytes into a new folder and ZIP; never overwrite sources."""
    _pin(receipt_sha256)
    _pin(source_commit, 40)
    pack = Path(pack).absolute()
    original = _tree(pack)
    _source(original, receipt_sha256)
    pack = pack.resolve()
    out = _new(out, [pack])
    archive = _new(archive, [pack, out])
    _require(not out.is_relative_to(archive), "package and ZIP paths overlap")
    source = Path(__file__).resolve()
    helper = source.with_name("review_server.py")
    files = {"viewer/" + name: raw for name, raw in original.items()}
    files.update(
        {
            "run_replay.py": _runtime_file(source),
            "review_server.py": _runtime_file(helper),
            "README.txt": README.encode("utf-8"),
        }
    )
    manifest = {
        "schema": SCHEMA,
        "source_commit": source_commit,
        "source_receipt_sha256": receipt_sha256,
        "trust": TRUST,
        "files": {n: {"sha256": _sha(raw), "bytes": len(raw)} for n, raw in files.items()},
    }
    files["manifest.json"] = _encoded(manifest)
    _validate(files)
    zip_raw = _zip_bytes(files)
    _require(_tree(pack) == original, "source pack changed during build")
    _new(out, [pack])
    _new(archive, [pack, out])
    _write(files, out)
    archive.parent.mkdir(parents=True, exist_ok=True)
    with archive.open("xb") as stream:
        stream.write(zip_raw)
    return {
        "schema": SCHEMA,
        "source_commit": source_commit,
        "source_receipt_sha256": receipt_sha256,
        "source_files": len(original),
        "package_files": len(files),
        "manifest_sha256": _sha(files["manifest.json"]),
        "archive_sha256": _sha(zip_raw),
        "archive_bytes": len(zip_raw),
        "input_unchanged": True,
    }


def extract(*, archive, archive_sha256, out):
    """Verify a separately pinned ZIP fully before writing its files to a new directory."""
    _pin(archive_sha256)
    archive = Path(archive).absolute()
    _require(not _linked(archive) and archive.is_file(), "missing or linked ZIP")
    _require(archive.stat().st_size <= MAX_TOTAL_BYTES, "ZIP exceeds archive size limit")
    raw = archive.read_bytes()
    _require(_sha(raw) == archive_sha256, "ZIP SHA differs")
    out = _new(out, [archive.resolve()])
    try:
        with zipfile.ZipFile(io.BytesIO(raw)) as zipped:
            entries = zipped.infolist()
            _names([entry.filename for entry in entries])
            total, files = 0, {}
            for entry in entries:
                mode = entry.external_attr >> 16
                _require(entry.orig_filename == entry.filename, "truncated ZIP member path")
                _require(
                    not entry.is_dir()
                    and not entry.external_attr & 0x410
                    and stat.S_IFMT(mode) in (0, stat.S_IFREG)
                    and not entry.flag_bits & 1,
                    "ZIP has directory, link, special or encrypted entry",
                )
                _require(entry.file_size <= MAX_FILE_BYTES, "ZIP member exceeds size limit")
                total += entry.file_size
                _require(total <= MAX_TOTAL_BYTES, "ZIP exceeds expanded size limit")
                value = zipped.read(entry)  # Also verifies each member CRC before any output write.
                _require(len(value) == entry.file_size, "ZIP member length differs")
                files[entry.filename] = value
    except (
        zipfile.BadZipFile,
        RuntimeError,
        NotImplementedError,
        zlib.error,
        lzma.LZMAError,
    ) as exc:
        raise ValueError("invalid or unsupported ZIP") from exc
    _validate(files)
    _new(out, [archive.resolve()])
    _write(files, out)
    return {
        "archive_sha256": archive_sha256,
        "package_files": len(files),
        "manifest_sha256": _sha(files["manifest.json"]),
    }


def open_server(package):
    """Bind only loopback, using the already verified helper bytes and viewer snapshot."""
    files = _tree(package)
    snapshot = _snapshot(_validate(files))
    # Do not import an on-disk helper before verification or reread it after verification.
    helper = ModuleType("verified_review_server")
    exec(compile(files["review_server.py"], "verified_review_server.py", "exec"), helper.__dict__)

    class LocalHostHandler(helper.make_handler(snapshot)):
        def _send(self, body):
            hosts = self.headers.get_all("Host", [])
            port = self.server.server_address[1]
            if len(hosts) != 1 or hosts[0] not in {f"127.0.0.1:{port}", f"localhost:{port}"}:
                self.send_error(421, "Unapproved local host")
                return
            super()._send(body)

    return helper.ReviewServer(("127.0.0.1", 0), LocalHostHandler)


def main(argv=None):
    argv = list(sys.argv[1:] if argv is None else argv)
    mode = argv.pop(0) if argv and argv[0] in ("build", "extract") else "run"
    parser = argparse.ArgumentParser(description=__doc__)
    if mode == "build":
        for name in ("pack", "receipt-sha256", "source-commit", "out", "archive"):
            parser.add_argument("--" + name, required=True)
    elif mode == "extract":
        for name in ("archive", "archive-sha256", "out"):
            parser.add_argument("--" + name, required=True)
    else:
        parser.add_argument("--package", default=Path(__file__).resolve().parent, type=Path)
        group = parser.add_mutually_exclusive_group()
        group.add_argument("--check", action="store_true")
        group.add_argument("--open", action="store_true")
    args = parser.parse_args(argv)
    try:
        if mode != "run":
            print(json.dumps((build if mode == "build" else extract)(**vars(args))))
            return 0
        if args.check:
            snapshot = check(args.package)
            print(f"재생 자료 검사 통과: 제공 파일 {len(snapshot)}개", flush=True)
            return 0
        with open_server(args.package) as server:
            url = f"http://127.0.0.1:{server.server_address[1]}/"
            print(f"재생 주소: {url}\n이 컴퓨터에서만 열립니다. 종료: Ctrl+C", flush=True)
            if args.open:
                try:
                    webbrowser.open(url)
                except (OSError, webbrowser.Error):
                    print("위 주소를 브라우저에 직접 입력하세요.", flush=True)
            try:
                server.serve_forever()
            except KeyboardInterrupt:
                pass
        return 0
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(f"재생 자료 검사 실패: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

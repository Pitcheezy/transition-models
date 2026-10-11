"""Build a private portable S review with optional, identity-bound existing clips."""

import argparse
import hashlib
import json
import sys
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile, ZipInfo

sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from scripts.inspect_service_game import (  # noqa: E402
    MAX_INPUT_BYTES,
    AuditInputError,
    _local_path,
    _read_input,
)
from src.integration.service_game import (  # noqa: E402
    EXPORT_PROFILE,
    ServiceGameError,
    normalize_service_game,
)
from src.integration.service_review_server import load_snapshot  # noqa: E402

ASSETS = ("index.html", "review.js", "style.css")
MEDIA_SOURCE = ROOT / "web/pitch-studio"
MEDIA_MANIFEST = ROOT / "docs/results/service_integration_20261010/first_pa_media_binding_v1.json"
WINDOWS_START = b"""@echo off\r
setlocal\r
set PYTHONUTF8=1\r
cd /d "%~dp0"\r
where py >nul 2>&1\r
if errorlevel 1 (\r
  python launch_review.py --open\r
) else (\r
  py -3 launch_review.py --open\r
)\r
if errorlevel 1 echo Python 3.10 or newer is required. See PRIVATE.txt.\r
pause\r
"""
MAC_START = b"""#!/bin/sh
cd -- "$(dirname -- "$0")" || exit 1
if command -v python3 >/dev/null 2>&1; then
  PYTHONUTF8=1 python3 launch_review.py --open
else
  echo "Python 3.10 or newer is required. See PRIVATE.txt."
fi
printf "Press Enter to close. "
read -r reply
"""
GUIDE = """Pitcheezy 비공개 경기 검토팩

Python 3.10 이상이 필요합니다. 모델·학습 라이브러리·저장소 전체는 필요하지 않습니다.
ZIP은 먼저 폴더 전체를 압축 해제하세요. 원문 서비스 응답은 포함하지 않습니다.
정규화된 자료와 영상이 들어 있으므로 공개 사이트·공개 저장소에 올리지 마세요.

Windows: START_WINDOWS.cmd를 실행합니다.
Mac: START_MAC.command를 실행합니다. 실행 권한/연결이 없으면 터미널에서
이 폴더로 이동한 뒤 python3 launch_review.py --open 을 실행합니다.
Windows 터미널 대안: py -3 launch_review.py --open
검사만 하기: python3 launch_review.py --check

실행할 때 파일 해시와 투구 연결을 검사하고 사용 가능한 포트를 자동 선택합니다.
안내된 127.0.0.1 주소는 실행한 컴퓨터에서만 열립니다. 다른 컴퓨터에서는 이 팩을
그 컴퓨터로 옮겨 실행하세요. 서버 종료는 Ctrl+C입니다. 인터넷으로 공개하지 않습니다.
주소가 다른 프로그램과 충돌하면 --port 0을 사용하세요.

추천 → 공식 투구 클립 → 실제 결과·미트 가로 위치 순서로 봅니다.
클립이 없거나 재생에 실패해도 수동 결과 공개를 사용할 수 있습니다.
타석·투구·보고서를 바꾸면 결과를 숨기고 이전 영상은 중단합니다.
연속 중계가 아니며 별도 미트 프레임의 시각을 공식 클립에 대응하지 않습니다.

현재 자료는 경기 후 as-of 재생입니다. 구종 비중은 사건확률이 아니며 미트는
미검토 가로 추정입니다. 표시 숨김은 접근 통제나 투구 전 추론의 증명이 아닙니다.
해시는 파일 변경 검사이며 자료 제공자의 신원이나 재배포 권리를 인증하지 않습니다.
"""


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _json_bytes(value):
    return (
        json.dumps(value, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
    ).encode("utf-8")


def _destination(path):
    if path.exists() or path.is_symlink():
        raise AuditInputError("Output must not already exist.")
    if not path.parent.is_dir():
        raise AuditInputError("Output parent directory must already exist.")
    for public_root in (ROOT / "web", ROOT / "docs"):
        if path.resolve().is_relative_to(public_root.resolve()):
            raise AuditInputError("Private review data must stay outside web and docs.")


def _media(report, enabled):
    manifest = {
        "schema": "pitcheezy-service-review-media-v1",
        "game_pk": report["game"]["game_pk"],
        "source_sha256": report["source"]["sha256"],
        "clips": [],
    }
    files = {}
    if not enabled:
        return manifest, files
    curated = json.loads(MEDIA_MANIFEST.read_text(encoding="utf-8"))
    if any(curated[k] != manifest[k] for k in ("schema", "game_pk", "source_sha256")):
        raise AuditInputError("The existing clips are bound to a different source snapshot.")
    keys = {row["key"] for row in report["pitches"]}
    seen = set()
    for clip in curated["clips"]:
        if clip["pitch_key"] not in keys or clip["pitch_key"] in seen:
            raise AuditInputError("Media pitch key is missing or duplicated.")
        seen.add(clip["pitch_key"])
        for kind in ("video", "poster"):
            name = clip[kind]
            rel = PurePosixPath(name)
            if (
                not isinstance(name, str)
                or "\\" in name
                or ":" in name
                or rel.is_absolute()
                or rel.parts[:1] != ("media",)
                or any(part in (".", "..") for part in name.split("/"))
            ):
                raise AuditInputError("Unsafe local media path.")
            path = MEDIA_SOURCE / name
            if not path.resolve().is_relative_to(MEDIA_SOURCE.resolve()):
                raise AuditInputError("Media path escapes its source directory.")
            for item in (path, *path.parents):
                if item == MEDIA_SOURCE:
                    break
                if item.is_symlink() or (hasattr(item, "is_junction") and item.is_junction()):
                    raise AuditInputError("Linked media files are not supported.")
            raw = path.read_bytes()
            if _sha(raw) != clip[kind + "_sha256"]:
                raise AuditInputError("Media hash differs from the verified identity record.")
            files[name] = raw
    manifest["clips"] = curated["clips"]
    return manifest, files


def build_review(
    input_path: Path,
    output_dir: Path,
    *,
    input_kind: str,
    include_video=False,
    zip_path: Path | None = None,
) -> dict:
    """Validate inputs before making a fresh portable package; preserve old packages."""
    _destination(output_dir)
    if zip_path is not None:
        _destination(zip_path)
        if zip_path.resolve() == output_dir.resolve() or zip_path.resolve().is_relative_to(
            output_dir.resolve()
        ):
            raise AuditInputError("ZIP destination must be outside the review directory.")
    payload, digest = _read_input(input_path)
    report = normalize_service_game(
        payload, input_kind=input_kind, source_sha256=digest, profile=EXPORT_PROFILE
    )
    report_bytes = _json_bytes(report)
    if len(report_bytes) > MAX_INPUT_BYTES:
        raise AuditInputError("Normalized report exceeds the local viewer 5 MiB limit.")
    media, media_files = _media(report, include_video)
    assets = {name: (ROOT / "web/service-review" / name).read_bytes() for name in ASSETS}
    assets.update(media_files)
    assets.update(
        {
            "review-media.json": _json_bytes(media),
            "launch_review.py": (ROOT / "src/integration/service_review_server.py").read_bytes(),
            "START_WINDOWS.cmd": WINDOWS_START,
            "START_MAC.command": MAC_START,
            "PRIVATE.txt": GUIDE.encode("utf-8"),
        }
    )
    receipt = {
        "schema": "pitcheezy-private-service-review-package-v2",
        "profile": EXPORT_PROFILE,
        "input_kind": input_kind,
        "source_sha256": digest,
        "report_sha256": _sha(report_bytes),
        "assets_sha256": {name: _sha(data) for name, data in assets.items()},
        "summary": report["summary"],
        "clip_count": len(media["clips"]),
        "public_distribution": False,
        "live_validation": False,
    }
    files = assets | {"review-data.json": report_bytes, "receipt.json": _json_bytes(receipt)}
    output_dir.mkdir()
    for name, data in files.items():
        target = output_dir / name
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (output_dir / "START_MAC.command").chmod(0o755)
    load_snapshot(output_dir)
    if zip_path is not None:
        with ZipFile(zip_path, "x", compression=ZIP_DEFLATED) as archive:
            for name, data in sorted(files.items()):
                info = ZipInfo(name)
                info.create_system = 3
                info.external_attr = (0o100755 if name == "START_MAC.command" else 0o100644) << 16
                info.compress_type = ZIP_DEFLATED
                archive.writestr(info, data)
    return receipt


def main(argv: list[str] | None = None) -> int:
    """Build locally from an explicit source; never publish or send the package."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Local S raw JSON, at most 5 MiB.")
    parser.add_argument(
        "--out-dir", required=True, help="New private directory; parent must exist."
    )
    parser.add_argument("--source-kind", choices=("synthetic", "provided_export"), required=True)
    parser.add_argument(
        "--include-first-pa-video",
        action="store_true",
        help="Include only existing identity-verified clips bound to this source SHA.",
    )
    parser.add_argument(
        "--zip", dest="zip_path", help="Optional new private ZIP beside, not inside, the package."
    )
    args = parser.parse_args(argv)
    try:
        receipt = build_review(
            _local_path(args.input),
            _local_path(args.out_dir),
            input_kind=args.source_kind,
            include_video=args.include_first_pa_video,
            zip_path=_local_path(args.zip_path) if args.zip_path else None,
        )
    except (AuditInputError, ServiceGameError, ValueError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (OSError, KeyError, TypeError, RecursionError):
        print(
            "error: Could not build the private package; existing files were not replaced.",
            file=sys.stderr,
        )
        return 2
    print(json.dumps(receipt, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

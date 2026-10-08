"""Pack or verify the 14 named operational artifacts without loading any models."""

import argparse
import hashlib
import json
import re
import stat
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZIP_STORED, BadZipFile, ZipFile, ZipInfo

INVENTORY_SCHEMA = "pitcheezy_external_inventory_v1"
SCHEMA = "pitcheezy_operational_bundle_v1"
REPOSITORY = "Pitcheezy/transition-models"
MANIFEST = "bundle_manifest.json"
GUIDE = "README_KO.md"
DATA = "data/operational_20260921_v2"
RUNS = "outputs/operational_20260921"
REQUIRED_FILES = (
    f"{DATA}/dataset_manifest.json",
    f"{DATA}/feature_builder.pkl",
    f"{DATA}/run_value_model.npz",
    f"{RUNS}/evaluation/selection.json",
    f"{RUNS}/evaluation/probability_report.json",
    f"{RUNS}/evaluation/empirical.pkl",
    *(
        f"{RUNS}/mlp135_seed{seed}/{name}"
        for seed in (42, 43, 44)
        for name in ("manifest.json", "best.pt")
    ),
    f"{RUNS}/policy_nuisance_v2/manifest.json",
    f"{RUNS}/policy_nuisance_v2/propensity.txt",
)
MAX_BYTES = 64 * 1024 * 1024


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _relative(value):
    """Reject paths that would change spelling or escape on Windows or POSIX."""
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or ":" in value
        or "\x00" in value
        or PurePosixPath(value).is_absolute()
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError("Expected a portable relative POSIX path")
    return value


def _no_links(path):
    """Check every ancestor before resolving or opening a named local path."""
    path = Path(path).absolute()
    for current in (path, *path.parents):
        if current.is_symlink() or getattr(current, "is_junction", lambda: False)():
            raise ValueError("Links and junctions are not allowed")
    return path


def _read_file(path, limit=MAX_BYTES):
    path = _no_links(path)
    info = path.stat()
    if not stat.S_ISREG(info.st_mode) or info.st_size > limit:
        raise ValueError("Expected a bounded regular file")
    with path.open("rb") as handle:
        data = handle.read(limit + 1)
    if len(data) > limit:
        raise ValueError("File exceeds the bundle size limit")
    return data


def _json(data):
    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("Duplicate JSON key")
            result[key] = value
        return result

    def invalid_constant(value):
        raise ValueError("Non-finite JSON constant")

    return json.loads(data, object_pairs_hook=unique, parse_constant=invalid_constant)


def _identity(data):
    return {"bytes": len(data), "sha256": _sha(data)}


def _validate_identity(info):
    if (
        not isinstance(info, dict)
        or type(info.get("bytes")) is not int
        or not 0 <= info["bytes"] <= MAX_BYTES
        or not isinstance(info.get("sha256"), str)
        or not re.fullmatch(r"[0-9a-f]{64}", info["sha256"])
    ):
        raise ValueError("Invalid byte count or SHA256")
    return {"bytes": info["bytes"], "sha256": info["sha256"]}


def _commit(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", value):
        raise ValueError("Use a full lowercase source commit ID")
    return value


def _selection(data):
    inventory = _json(data)
    if not isinstance(inventory, dict) or inventory.get("schema") != INVENTORY_SCHEMA:
        raise ValueError("Unsupported external inventory schema")
    if not isinstance(inventory.get("artifacts"), list):
        raise ValueError("Inventory must contain artifact entries")
    selected = {}
    for row in inventory["artifacts"]:
        if not isinstance(row, dict):
            raise ValueError("Artifact entries must be objects")
        if row.get("path_alias") != "LEGACY_PROJECT":
            continue
        relative = _relative(row.get("relative_path"))
        if not relative.startswith((DATA + "/", RUNS + "/")):
            continue
        if relative not in REQUIRED_FILES or relative in selected:
            raise ValueError("Unexpected or duplicate operational artifact")
        if row.get("observed") is not True:
            raise ValueError("Every selected artifact must have been observed")
        selected[relative] = _validate_identity(row)
    if set(selected) != set(REQUIRED_FILES):
        raise ValueError("Inventory must name all 14 required operational artifacts")
    if sum(info["bytes"] for info in selected.values()) > MAX_BYTES:
        raise ValueError("Operational artifact total exceeds the bundle size limit")
    return selected


def _guide(source_commit):
    return f"""# 우리 운영 모델 비공개 전달 묶음

이 ZIP은 명시한 운영 산출물14개와 이 안내·manifest만 담습니다. 소스코드·실행파일·영상·
이미지·사람 라벨·계정정보는 포함하지 않습니다. 내부 지정 수신자에게 별도로 전달할 자료이며
공개 웹/GitHub 업로드용이 아닙니다. ZIP 작성은 전달 준비이며 전송·업로드는 하지 않습니다.

## 수신 및 확인

1. 전달자에게 ZIP의 SHA256을 별도로 받아 받은 파일과 비교합니다.
2. 우리 전체 저장소와 아래 정본 커밋을 확보합니다. 최신 전체 저장소의 stdlib 검사 도구로
   `python -B -S scripts/build_operational_bundle.py check 받은파일.zip`을 실행합니다.
3. 검사가 성공한 ZIP을 새 빈 폴더에 풉니다. 파일을 편집하거나 옛135d 모델을 섞지 않습니다.
   manifest는 파일별 상대경로·크기·SHA를 기록하며 자기 자신을 해시하지 않습니다.
   해시는 바이트 일치 확인이며 전달자 인증 서명이나 일반 재배포 권한 증명이 아닙니다.

지정한 전체 저장소: `{REPOSITORY}`
지정한 운영 소스 커밋: `{source_commit}`
이 커밋은 전달자가 명시한 실행 소스입니다. ZIP 생성기는 소스 호환성·모델 실행을 재검증하지
않습니다. H-port2 결과의 소스·환경과 대조하고, 다른 기기에서는 별도 실행 확인이 필요합니다.
H-port1의48개 소스 ZIP은 완전한 모델 런타임이 아니므로 대신 사용하면 안 됩니다.

## 실제 실행은 별도 단계

신뢰한 전달 출처와 파일 무결성을 확인한 뒤, 지정 소스의 `pyproject.toml`·`uv.lock`·
`docs/MAINTENANCE.md`를 따릅니다. 플랫폼별 PyTorch와 필요한 의존성은 별도 설치 대상입니다.
모델·pickle을 여는 것은 아래 추론 명령이며 ZIP 검사 자체는 역직렬화하지 않습니다.

전체 저장소 루트에서 `<묶음>`을 압축 해제한 폴더로 바꿉니다.

```text
uv run --frozen python scripts/57_recommend_operational.py --data-dir <묶음>/{DATA} --evaluation-dir <묶음>/{RUNS}/evaluation --nuisance-dir <묶음>/{RUNS}/policy_nuisance_v2 --runs-dir <묶음>/{RUNS} --state-json docs/results/operational_20260921/example_state.json
```

세 seed42/43/44를 모두 사용하며 선택·보정 보고서 원문을 보존합니다. 실행은
`probability_report.json` 안의 selection과 저장된 온도를 읽습니다. `selection.json`은
별도 선택 근거입니다. 원래13개 실행 의존 파일에 이 근거1개를 더한14개입니다.
새 경로는 `--runs-dir`로 지정하고 과거 경로·보정값을 JSON에서 직접 고치지 않습니다.
empirical 기준선·propensity·비용 커널도 포함합니다. 구형 Arsenal135와 호환되지 않습니다.

우리 모델의 재현 기준을 보존하는 묶음이며 팀원 모델 채택·대체 합의가 아닙니다. 구종 추천만
지원하고 목표 위치와 독립 strike/ball/foul은 제공하지 않습니다. 실점 감소는 입증되지 않았습니다.
이 ZIP을 만들었다고 Mac·새 설치·다른 기기 실행, 새 정확도·정책 효과, 완전한 배포 런타임이
검증된 것은 아닙니다. 원본 학습·평가 배열과 재학습 자료는 포함하지 않습니다.
""".encode()


def verify_archive(archive):
    """Check exact ZIP membership and bytes using only the standard library."""
    archive = _no_links(archive)
    with ZipFile(archive) as zipped:
        entries = zipped.infolist()
        expected = set(REQUIRED_FILES) | {MANIFEST, GUIDE}
        if len(entries) != len(expected) or {item.filename for item in entries} != expected:
            raise ValueError("ZIP must contain exactly 14 artifacts, manifest, and guide")
        if sum(item.file_size for item in entries) > MAX_BYTES + 256 * 1024:
            raise ValueError("ZIP expanded size exceeds the limit")
        for item in entries:
            _relative(item.filename)
            if (
                item.is_dir()
                or item.flag_bits & 1
                or item.compress_type not in {ZIP_STORED, ZIP_DEFLATED}
                or stat.S_ISLNK(item.external_attr >> 16)
            ):
                raise ValueError("ZIP contains an unsupported member")
        if zipped.getinfo(MANIFEST).file_size > 128 * 1024:
            raise ValueError("Manifest is too large")
        manifest = _json(zipped.read(MANIFEST))
        if (
            not isinstance(manifest, dict)
            or manifest.get("schema") != SCHEMA
            or manifest.get("source_repository") != REPOSITORY
            or not isinstance(manifest.get("files"), dict)
            or set(manifest["files"]) != set(REQUIRED_FILES)
        ):
            raise ValueError("Unsupported operational bundle manifest")
        _commit(manifest.get("source_commit"))
        _validate_identity(manifest.get("inventory"))
        for relative, info in manifest["files"].items():
            if _identity(zipped.read(relative)) != _validate_identity(info):
                raise ValueError("Artifact bytes or SHA256 changed")
        guide = zipped.read(GUIDE)
        if _identity(guide) != _validate_identity(manifest.get("guide")):
            raise ValueError("Guide bytes or SHA256 changed")
        if guide != _guide(manifest["source_commit"]):
            raise ValueError("Guide does not match this bundle specification")
    return manifest


def build(inventory_path, artifact_root, out, source_commit):
    """Read only the 14 allowlisted files and write one new deterministic ZIP."""
    source_commit = _commit(source_commit)
    out, artifact_root = _no_links(out), _no_links(artifact_root)
    if out.exists():
        raise FileExistsError("Use a new ZIP path; existing files are never overwritten")
    if out.suffix.lower() != ".zip" or not out.parent.is_dir() or not artifact_root.is_dir():
        raise ValueError("Use an existing artifact root and output parent, and a new .zip file")
    inventory_bytes = _read_file(inventory_path, 2 * 1024 * 1024)
    selected = _selection(inventory_bytes)
    contents = {}
    for relative, info in selected.items():
        path = _no_links(artifact_root / relative)
        if not path.resolve().is_relative_to(artifact_root.resolve()):
            raise ValueError("Artifact path escapes its root")
        data = _read_file(path, info["bytes"])
        if _identity(data) != info:
            raise ValueError("Named artifact bytes or SHA256 differ from inventory")
        contents[relative] = data
    guide = _guide(source_commit)
    manifest = {
        "schema": SCHEMA,
        "source_repository": REPOSITORY,
        "source_commit": source_commit,
        "source_commit_basis": "Explicit sender declaration; compatibility not executed by packer",
        "distribution": "private_designated_transfer_only_not_public_site",
        "inventory": {"schema": INVENTORY_SCHEMA, **_identity(inventory_bytes)},
        "files": dict(sorted(selected.items())),
        "guide": _identity(guide),
        "scope": "Exact named artifact bytes, not a complete runtime or new model validation",
    }
    contents[GUIDE] = guide
    contents[MANIFEST] = (json.dumps(manifest, ensure_ascii=False, indent=2) + "\n").encode()
    # All source inputs are verified before exclusive creation; no directory scan or model loading.
    with ZipFile(out, "x", compression=ZIP_DEFLATED, compresslevel=9) as zipped:
        for relative, data in sorted(contents.items()):
            info = ZipInfo(relative, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o600) << 16
            info.compress_type = ZIP_DEFLATED
            zipped.writestr(info, data, compresslevel=9)
    verify_archive(out)
    return {
        "files": len(selected),
        "source_commit": source_commit,
        "archive_bytes": out.stat().st_size,
        "archive_sha256": _sha(out.read_bytes()),
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    create = actions.add_parser("build")
    create.add_argument("--inventory", type=Path, required=True)
    create.add_argument("--artifact-root", type=Path, required=True)
    create.add_argument("--out", type=Path, required=True)
    create.add_argument("--source-commit", required=True)
    check = actions.add_parser("check")
    check.add_argument("archive", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "build":
            result = build(args.inventory, args.artifact_root, args.out, args.source_commit)
        else:
            manifest = verify_archive(args.archive)
            result = {
                "status": "verified",
                "files": len(manifest["files"]),
                "source_commit": manifest["source_commit"],
            }
    except (OSError, ValueError, TypeError, KeyError, BadZipFile) as exc:
        parser.exit(2, f"error: operational bundle validation failed ({type(exc).__name__}).\n")
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()

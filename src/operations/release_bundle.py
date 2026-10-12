"""Build deterministic host candidates without running builds, extracting ZIPs, or deploying."""

import hashlib
import io
import json
import re
import stat
import subprocess
from pathlib import Path, PurePosixPath
from zipfile import ZIP_STORED, BadZipFile, ZipFile, ZipInfo

SCHEMA = "pitcheezy-host-release-v1"
MANIFEST = "release-manifest.json"
MAX_FILES = 2000
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TOTAL_BYTES = 100 * 1024 * 1024
MAX_MANIFEST_BYTES = 2 * 1024 * 1024
HOST_FILES = (
    "worker.mjs",
    "gateway.mjs",
    "notice.mjs",
    "access.mjs",
    "telemetry.mjs",
    "package.json",
    "package-lock.json",
    "wrangler.example.jsonc",
    "migrations/0001_telemetry.sql",
    "client/usage-client.mjs",
    "client/widget.mjs",
    "client/widget.css",
)
PUBLIC_EXTENSIONS = {
    ".html",
    ".js",
    ".mjs",
    ".css",
    ".json",
    ".png",
    ".jpg",
    ".jpeg",
    ".svg",
    ".ico",
    ".woff",
    ".woff2",
    ".ttf",
    ".webmanifest",
    ".txt",
}
DOS_NAMES = {
    "CON",
    "PRN",
    "AUX",
    "NUL",
    *(f"COM{i}" for i in range(1, 10)),
    *(f"LPT{i}" for i in range(1, 10)),
}
HEX40 = re.compile(r"[a-f0-9]{40}\Z")
HEX64 = re.compile(r"[a-f0-9]{64}\Z")
TOKEN = re.compile(r"[A-Za-z0-9][A-Za-z0-9._+-]{0,63}\Z")
SECRET_MARKERS = re.compile(
    rb"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----|"
    rb"\bgh[pousr]_[A-Za-z0-9]{30,}\b|\bgithub_pat_[A-Za-z0-9_]{40,}\b"
)
LFS_PREFIX = b"version https://git-lfs.github.com/spec/v1"


class BundleError(ValueError):
    """An input cannot be accepted as a reviewed release candidate."""


def digest(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def canonical(value: object) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode()


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise BundleError("duplicate_json_key")
        result[key] = value
    return result


def parse_json(raw: bytes, limit: int = MAX_MANIFEST_BYTES):
    if len(raw) > limit:
        raise BundleError("json_too_large")
    try:
        return json.loads(raw.decode("utf-8"), object_pairs_hook=_unique_object)
    except (UnicodeDecodeError, json.JSONDecodeError, RecursionError) as exc:
        raise BundleError("invalid_json") from exc


def _keys(value, expected):
    return isinstance(value, dict) and set(value) == set(expected)


def safe_path(name: str) -> str:
    if not isinstance(name, str) or len(name) > 240 or not name:
        raise BundleError("invalid_path")
    parts = name.split("/")
    if len(parts) > 16:
        raise BundleError("path_too_deep")
    for part in parts:
        if (
            not re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9._-]*", part)
            or part.endswith(".")
            or part.split(".")[0].upper() in DOS_NAMES
        ):
            raise BundleError("invalid_path")
    return name


def _plain_path(path: Path):
    # Check ancestors before resolving; resolving first would hide a symlink/junction.
    path = path.absolute()
    for item in (path, *path.parents):
        if not item.exists() and not item.is_symlink():
            continue
        info = item.lstat()
        if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
            raise BundleError("linked_path")
    return path.resolve(strict=False)


def _read_regular(path: Path, limit: int) -> bytes:
    path = _plain_path(path)
    before = path.stat()
    if not stat.S_ISREG(before.st_mode) or before.st_size > limit:
        raise BundleError("not_regular_or_too_large")
    with path.open("rb") as stream:
        raw = stream.read(limit + 1)
    after = path.stat()
    if (
        len(raw) > limit
        or len(raw) != before.st_size
        or (before.st_dev, before.st_ino, before.st_mtime_ns, before.st_size)
        != (after.st_dev, after.st_ino, after.st_mtime_ns, after.st_size)
    ):
        raise BundleError("file_changed_or_too_large")
    return raw


def validate_payload(name: str, raw: bytes):
    safe_path(name)
    if not isinstance(raw, bytes) or len(raw) > MAX_FILE_BYTES:
        raise BundleError("file_too_large")
    if name.startswith("host/"):
        if name[5:] not in HOST_FILES:
            raise BundleError("unexpected_host_file")
    elif name.startswith("public/"):
        relative = name[7:]
        if (
            PurePosixPath(relative).suffix.lower() not in PUBLIC_EXTENSIONS
            or relative.split("/")[0].lower() in {"v1", "api", "node_modules"}
            or any(p.lower().startswith((".env", ".dev.vars")) for p in relative.split("/"))
            or PurePosixPath(relative).name.lower()
            in {
                "package.json",
                "package-lock.json",
                "wrangler.json",
                "wrangler.jsonc",
                "credentials.json",
            }
        ):
            raise BundleError("forbidden_public_file")
    else:
        raise BundleError("unexpected_payload_root")
    if raw.startswith(LFS_PREFIX):
        raise BundleError("lfs_pointer")
    if SECRET_MARKERS.search(raw):
        raise BundleError("possible_secret")
    # Content scan is a narrow extra guard, not proof that a build contains no secrets.


def read_frontend(directory: Path) -> dict[str, bytes]:
    root = _plain_path(directory)
    if not root.is_dir():
        raise BundleError("frontend_directory_required")
    payload = {}
    entries = 0

    def visit(folder):
        nonlocal entries
        for item in sorted(folder.iterdir()):
            entries += 1
            if entries > MAX_FILES * 2:
                raise BundleError("too_many_entries")
            relative = item.relative_to(root).as_posix()
            safe_path(relative)
            _plain_path(item)
            if item.is_dir():
                visit(item)
            else:
                name = "public/" + relative
                raw = _read_regular(item, MAX_FILE_BYTES)
                validate_payload(name, raw)
                payload[name] = raw
                if len(payload) > MAX_FILES or sum(map(len, payload.values())) > MAX_TOTAL_BYTES:
                    raise BundleError("payload_too_large")

    visit(root)
    if "public/index.html" not in payload:
        raise BundleError("frontend_index_required")
    return payload


def read_provenance(path: Path):
    """Read bounded supplier metadata without following links."""
    return validate_provenance(parse_json(_read_regular(path, 32768), 32768))


def validate_provenance(value):
    if not _keys(value, ("frontend", "contracts")):
        raise BundleError("invalid_provenance")
    front = value["frontend"]
    if (
        not _keys(front, ("repository", "commit", "build_command", "tools"))
        or front["repository"] != "SongRoute/pitcheezy"
        or not isinstance(front["commit"], str)
        or not HEX40.fullmatch(front["commit"])
        or front["build_command"] != ["npm", "run", "build:public"]
        or not _keys(front["tools"], ("node", "npm"))
        or any(not isinstance(v, str) or not TOKEN.fullmatch(v) for v in front["tools"].values())
    ):
        raise BundleError("invalid_frontend_provenance")
    contracts = value["contracts"]
    if not isinstance(contracts, list) or not 1 <= len(contracts) <= 8:
        raise BundleError("invalid_contracts")
    names = set()
    for contract in contracts:
        if (
            not _keys(contract, ("name", "version", "commit"))
            or any(
                not isinstance(contract[k], str) or not TOKEN.fullmatch(contract[k])
                for k in ("name", "version")
            )
            or not isinstance(contract["commit"], str)
            or not HEX40.fullmatch(contract["commit"])
            or contract["name"] in names
        ):
            raise BundleError("invalid_contract")
        names.add(contract["name"])
    return value


def read_host_commit(repo: Path, commit: str) -> dict[str, bytes]:
    if not isinstance(commit, str) or not HEX40.fullmatch(commit):
        raise BundleError("full_host_commit_required")
    repo = _plain_path(repo)
    # --no-replace-objects: a refs/replace entry must not swap the pinned commit's bytes.
    command = [
        "git",
        "--no-replace-objects",
        "-c",
        f"safe.directory={repo.as_posix()}",
        "-C",
        str(repo),
    ]
    try:
        if subprocess.check_output(command + ["cat-file", "-t", commit]).strip() != b"commit":
            raise BundleError("host_commit_required")
        payload = {}
        for name in HOST_FILES:
            source = f"{commit}:ops/public-host/{name}"
            size = int(subprocess.check_output(command + ["cat-file", "-s", source]))
            if size > MAX_FILE_BYTES:
                raise BundleError("file_too_large")
            raw = subprocess.check_output(command + ["cat-file", "blob", source])
            validate_payload("host/" + name, raw)
            payload["host/" + name] = raw
        return payload
    except subprocess.CalledProcessError as exc:
        raise BundleError("host_commit_files_unavailable") from exc


def _inventory(payload):
    if not 1 <= len(payload) <= MAX_FILES or sum(map(len, payload.values())) > MAX_TOTAL_BYTES:
        raise BundleError("payload_too_large")
    folded = set()
    for name, raw in payload.items():
        validate_payload(name, raw)
        if name.casefold() in folded:
            raise BundleError("case_collision")
        folded.add(name.casefold())
    for name in folded:
        if any(parent.as_posix().casefold() in folded for parent in PurePosixPath(name).parents):
            raise BundleError("path_conflict")
    expected_host = {"host/" + name for name in HOST_FILES}
    if {name for name in payload if name.startswith("host/")} != expected_host:
        raise BundleError("host_files_missing")
    if "public/index.html" not in payload:
        raise BundleError("frontend_index_required")
    return [
        {"path": name, "bytes": len(raw), "sha256": digest(raw)}
        for name, raw in sorted(payload.items())
    ]


def assemble(payload, provenance, host_commit, mode="synthetic"):
    """Return one fixed byte set for both directory and ZIP; never reopen source files."""
    if (
        not isinstance(mode, str)
        or mode not in {"synthetic", "candidate"}
        or not isinstance(host_commit, str)
        or not HEX40.fullmatch(host_commit)
    ):
        raise BundleError("invalid_release_identity")
    validate_provenance(provenance)
    manifest = {
        "schema": SCHEMA,
        "mode": mode,
        "deployable": False,
        "host": {
            "repository": "Pitcheezy/transition-models",
            "commit": host_commit,
            "provenance": "git-blob-inventory",
        },
        "frontend": {**provenance["frontend"], "provenance": "supplier-declared"},
        "contracts": provenance["contracts"],
        "files": _inventory(payload),
        "limitations": [
            "File hashes do not prove frontend build provenance or public rights.",
            "Account configuration and end-to-end deployment validation are separate.",
        ],
    }
    return {**payload, MANIFEST: canonical(manifest)}


def make_zip(files: dict[str, bytes]) -> bytes:
    buffer = io.BytesIO()
    with ZipFile(buffer, "w", compression=ZIP_STORED) as archive:
        for name, raw in sorted(files.items()):
            info = ZipInfo(name, date_time=(1980, 1, 1, 0, 0, 0))
            info.create_system = 3
            info.external_attr = (stat.S_IFREG | 0o644) << 16
            info.compress_type = ZIP_STORED
            archive.writestr(info, raw)
    return buffer.getvalue()


def verify_files(files: dict[str, bytes]) -> dict:
    if MANIFEST not in files:
        raise BundleError("manifest_missing")
    manifest = parse_json(files[MANIFEST])
    if (
        not _keys(
            manifest,
            (
                "schema",
                "mode",
                "deployable",
                "host",
                "frontend",
                "contracts",
                "files",
                "limitations",
            ),
        )
        or manifest["schema"] != SCHEMA
        or not isinstance(manifest["mode"], str)
        or manifest["mode"] not in {"synthetic", "candidate"}
        or manifest["deployable"] is not False
    ):
        raise BundleError("invalid_manifest")
    host = manifest["host"]
    if (
        not _keys(host, ("repository", "commit", "provenance"))
        or host["repository"] != "Pitcheezy/transition-models"
        or host["provenance"] != "git-blob-inventory"
        or not isinstance(host["commit"], str)
        or not HEX40.fullmatch(host["commit"])
    ):
        raise BundleError("invalid_host_identity")
    front = manifest["frontend"]
    if not isinstance(front, dict) or front.get("provenance") != "supplier-declared":
        raise BundleError("invalid_frontend_identity")
    validate_provenance(
        {
            "frontend": {k: v for k, v in front.items() if k != "provenance"},
            "contracts": manifest["contracts"],
        }
    )
    payload = {name: raw for name, raw in files.items() if name != MANIFEST}
    if canonical(manifest["files"]) != canonical(_inventory(payload)):
        raise BundleError("inventory_mismatch")
    if not isinstance(manifest["limitations"], list) or not all(
        isinstance(x, str) for x in manifest["limitations"]
    ):
        raise BundleError("invalid_limitations")
    return {
        "schema": SCHEMA,
        "mode": manifest["mode"],
        "deployable": False,
        "files": len(payload),
        "bytes": sum(map(len, payload.values())),
        "manifest_sha256": digest(files[MANIFEST]),
        "host_commit": host["commit"],
        "frontend_commit": front["commit"],
        "scope": "Package bytes only; git/build provenance, functionality and rights not verified.",
    }


def check_bundle(path: Path) -> dict:
    """Verify a bounded ZIP without extracting it or running its contents."""
    raw = _read_regular(path, MAX_TOTAL_BYTES + MAX_MANIFEST_BYTES + MAX_FILES * 1024)
    try:
        with ZipFile(io.BytesIO(raw)) as archive:
            infos = archive.infolist()
            if not 2 <= len(infos) <= MAX_FILES + 1:
                raise BundleError("entry_count")
            files = {}
            folded = set()
            total = 0
            for info in infos:
                safe_path(info.filename)
                if (
                    info.filename.casefold() in folded
                    or info.is_dir()
                    or info.flag_bits & 1
                    or info.compress_type != ZIP_STORED
                    or stat.S_IFMT(info.external_attr >> 16) != stat.S_IFREG
                ):
                    raise BundleError("unsafe_zip_entry")
                folded.add(info.filename.casefold())
                limit = MAX_MANIFEST_BYTES if info.filename == MANIFEST else MAX_FILE_BYTES
                total += info.file_size
                if info.file_size > limit or total > MAX_TOTAL_BYTES + MAX_MANIFEST_BYTES:
                    raise BundleError("zip_too_large")
                data = archive.read(info)
                if len(data) != info.file_size:
                    raise BundleError("zip_size_mismatch")
                files[info.filename] = data
    except (BadZipFile, RuntimeError, NotImplementedError) as exc:
        raise BundleError("invalid_zip") from exc
    result = verify_files(files)
    if raw != make_zip(files):
        raise BundleError("noncanonical_zip")
    result["bundle_sha256"] = digest(raw)
    return result


def write_bundle(output: Path, files: dict[str, bytes], frontend: Path):
    output = _plain_path(output)
    source = _plain_path(frontend)
    if output == source or source in output.parents:
        raise BundleError("output_inside_input")
    verify_files(files)
    bundle = make_zip(files)
    # Only create a new directory. Existing outputs and source trees are never removed or replaced.
    output.mkdir(parents=False, exist_ok=False)
    path = output / "release.zip"
    with path.open("xb") as stream:
        stream.write(bundle)
    receipt = check_bundle(path)
    (output / "receipt.json").write_bytes(canonical(receipt))
    return receipt

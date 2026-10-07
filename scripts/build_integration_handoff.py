"""Build or check a source-only handoff bound to an explicit local Git commit."""

import argparse
import hashlib
import json
import re
import subprocess
from pathlib import Path, PurePosixPath
from zipfile import ZIP_DEFLATED, ZipFile

ROOT = Path(__file__).resolve().parents[1]
CONFIG = "docs/handoff/source_files_v1.json"
MANIFEST = "bundle_manifest.json"
SCHEMA = "pitcheezy_source_handoff_v1"
REPOSITORY = "Pitcheezy/transition-models"
SUFFIXES = {
    ".py",
    ".js",
    ".cjs",
    ".html",
    ".css",
    ".md",
    ".json",
    ".jsonl",
    ".toml",
    ".lock",
    ".txt",
}
LFS_HEADER = b"version https://git-lfs.github.com/spec/v1"


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _relative(value):
    """Accept portable relative file paths without normalized-away components."""
    if (
        not isinstance(value, str)
        or not value
        or "\\" in value
        or ":" in value
        or "\x00" in value
        or PurePosixPath(value).is_absolute()
        or any(part in {"", ".", ".."} for part in value.split("/"))
    ):
        raise ValueError("File paths must be portable relative POSIX paths")
    return value


def _no_link(path):
    if path.is_symlink() or getattr(path, "is_junction", lambda: False)():
        raise ValueError("Links and junctions are not allowed")


def _git(root, *args):
    try:
        return subprocess.check_output(["git", "-C", str(root), *args], stderr=subprocess.PIPE)
    except (OSError, subprocess.CalledProcessError) as exc:
        raise ValueError("Could not read the requested local Git commit or file") from exc


def _blob(root, commit, relative):
    """Read regular Git blobs, never smudged working-tree or LFS contents."""
    _relative(relative)
    entry = _git(root, "ls-tree", "-z", commit, "--", relative).split(b"\0")
    if len(entry) != 2 or not entry[0] or entry[1]:
        raise ValueError("Selected source must be one regular Git file")
    metadata, name = entry[0].split(b"\t", 1)
    mode, kind, object_id = metadata.split()
    if mode not in {b"100644", b"100755"} or kind != b"blob":
        raise ValueError("Selected source must be a regular Git blob")
    if name.decode("utf-8") != relative:
        raise ValueError("Git source path does not match the selection")
    data = _git(root, "cat-file", "blob", object_id.decode("ascii"))
    if data.startswith(LFS_HEADER):
        raise ValueError("Git LFS pointer files are excluded from the source handoff")
    return data


def _selection(data):
    config = json.loads(data)
    if config.get("schema") != "pitcheezy_handoff_selection_v1":
        raise ValueError("Unsupported selection schema")
    if config.get("repository") != REPOSITORY:
        raise ValueError("Unexpected source repository declaration")
    rows, exclusions = config.get("files"), config.get("exclusions")
    if not isinstance(rows, list) or not rows:
        raise ValueError("Selection must contain a nonempty file list")
    if not isinstance(exclusions, list) or not all(isinstance(v, str) for v in exclusions):
        raise ValueError("Selection exclusions must be a list of strings")
    selected = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("Each selection entry must be an object")
        relative = _relative(row.get("path"))
        if relative in selected or relative == MANIFEST:
            raise ValueError("Duplicate or reserved selection path")
        if PurePosixPath(relative).suffix.lower() not in SUFFIXES:
            raise ValueError("Only allowlisted source text extensions are supported")
        if any(
            not isinstance(row.get(key), str) or not row[key] for key in ("role", "distribution")
        ):
            raise ValueError("Each source needs a role and distribution declaration")
        selected[relative] = {key: row[key] for key in ("role", "distribution")}
    if CONFIG not in selected:
        raise ValueError("The selection file must include itself")
    return selected, exclusions


def verify_bundle(bundle):
    """Verify an extracted folder without Git, models, media, or third-party packages."""
    bundle = Path(bundle)
    _no_link(bundle)
    bundle = bundle.resolve()
    manifest_path = bundle / MANIFEST
    _no_link(manifest_path)
    manifest = json.loads(manifest_path.read_bytes())
    if manifest.get("schema") != SCHEMA or manifest.get("source_repository") != REPOSITORY:
        raise ValueError("Unsupported bundle manifest")
    if not re.fullmatch(r"[0-9a-f]{40}|[0-9a-f]{64}", manifest.get("source_commit", "")):
        raise ValueError("Manifest must identify a full source commit")
    files = manifest.get("files")
    if not isinstance(files, dict) or not files or MANIFEST in files:
        raise ValueError("Invalid bundle inventory")
    for relative, info in files.items():
        _relative(relative)
        if PurePosixPath(relative).suffix.lower() not in SUFFIXES:
            raise ValueError("Bundle contains a disallowed file extension")
        if not isinstance(info, dict) or type(info.get("bytes")) is not int or info["bytes"] < 0:
            raise ValueError("Invalid file byte count")
        if not isinstance(info.get("sha256"), str) or not re.fullmatch(
            r"[0-9a-f]{64}", info["sha256"]
        ):
            raise ValueError("Invalid file SHA256")
        if any(
            not isinstance(info.get(key), str) or not info[key] for key in ("role", "distribution")
        ):
            raise ValueError("Missing source role or distribution")
    actual = set()
    for path in bundle.rglob("*"):
        _no_link(path)
        if path.is_file():
            actual.add(path.relative_to(bundle).as_posix())
        elif not path.is_dir():
            raise ValueError("Bundle contains a non-regular file")
    if actual != set(files) | {MANIFEST}:
        raise ValueError("Bundle file inventory changed")
    for relative, info in files.items():
        path = bundle / relative
        if not path.resolve().is_relative_to(bundle):
            raise ValueError("Bundle file escapes its root")
        data = path.read_bytes()
        if data.startswith(LFS_HEADER):
            raise ValueError("Git LFS pointers are not source files")
        if len(data) != info["bytes"] or _sha(data) != info["sha256"]:
            raise ValueError("Bundle file bytes or SHA256 changed")
    return manifest


def build(root, source_ref, out):
    """Export selected commit blobs to a new folder and its new sibling ZIP."""
    root, out = Path(root), Path(out)
    if not isinstance(source_ref, str) or not re.fullmatch(r"[0-9a-fA-F]{7,64}", source_ref):
        raise ValueError("Source ref must be an explicit hexadecimal commit ID")
    commit = _git(root, "rev-parse", "--verify", f"{source_ref}^{{commit}}").decode("ascii").strip()
    archive = out.with_name(f"{out.name}.zip")
    _relative(out.name)
    for path in (out, archive, out.parent):
        _no_link(path)
    if not out.parent.is_dir():
        raise ValueError("Output parent directory must already exist")
    if out.exists() or archive.exists():
        raise FileExistsError("Use a new output folder and ZIP name")
    config_bytes = _blob(root, commit, CONFIG)
    selection, exclusions = _selection(config_bytes)
    contents = {relative: _blob(root, commit, relative) for relative in selection}
    manifest = {
        "schema": SCHEMA,
        "source_commit": commit,
        "source_repository": REPOSITORY,
        "provenance_caveat": "Exact local Git blob bytes and hashes establish consistency, not source authentication or permission to redistribute. The manifest is not self-hashed.",
        "files": {
            relative: {"bytes": len(data), "sha256": _sha(data), **selection[relative]}
            for relative, data in sorted(contents.items())
        },
        "exclusions": exclusions,
    }
    # All selected inputs are checked before any output is created.
    out.mkdir()
    for relative, data in contents.items():
        target = out / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(data)
    (out / MANIFEST).write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n"
    )
    verify_bundle(out)
    with ZipFile(archive, "x", compression=ZIP_DEFLATED) as zipped:
        for relative in sorted([*contents, MANIFEST]):
            zipped.write(out / relative, f"{out.name}/{relative}")
    with ZipFile(archive) as zipped:
        for relative in [*contents, MANIFEST]:
            if zipped.read(f"{out.name}/{relative}") != (out / relative).read_bytes():
                raise ValueError("ZIP content differs from verified output")
    return {
        "bundle": str(out),
        "archive": str(archive),
        "source_commit": commit,
        "files": len(contents),
        "archive_bytes": archive.stat().st_size,
        "archive_sha256": _sha(archive.read_bytes()),
    }


def main():
    """Print compact metadata without displaying source file contents."""
    parser = argparse.ArgumentParser(description=__doc__)
    actions = parser.add_subparsers(dest="action", required=True)
    create = actions.add_parser("build")
    create.add_argument("--source-ref", required=True)
    create.add_argument("--out", required=True, type=Path)
    check = actions.add_parser("check")
    check.add_argument("bundle", type=Path)
    args = parser.parse_args()
    try:
        if args.action == "build":
            result = build(ROOT, args.source_ref, args.out)
        else:
            manifest = verify_bundle(args.bundle)
            result = {
                "status": "verified",
                "files": len(manifest["files"]),
                "source_commit": manifest["source_commit"],
            }
    except (OSError, ValueError, TypeError, KeyError) as exc:
        parser.exit(2, f"error: source handoff validation failed ({type(exc).__name__}).\n")
    print(json.dumps(result, ensure_ascii=True, indent=2))


if __name__ == "__main__":
    main()

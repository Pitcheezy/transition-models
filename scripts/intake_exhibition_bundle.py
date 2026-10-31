"""Validate a received exhibition ZIP without executing or changing partner files.

Only the nominated game's JSON is semantically inspected. Other game files are
read as bytes for integrity, including the locked evaluation game 849844.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import io
import json
import re
import stat
import zipfile
from collections import Counter
from pathlib import Path, PurePosixPath

EXPECTED_SHA256 = "af10293d5134219b7f750d00786366b93b0134c895519b939fd99a356d77a4bc"
EXPECTED_BYTES = 867682
EXPECTED_COMMIT = "fba6b2ff846dcfa9afad9ea5df4204007e0604c1"
MAX_EXPANDED_BYTES = 64 * 1024 * 1024
MAX_FILES = 256


class IntakeError(ValueError):
    """The package must not be accepted or extracted."""


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def safe_path(name: str, *, directory: bool = False) -> str:
    if directory:
        name = name.removesuffix("/")
    parts = name.split("/")
    if (not name or "\\" in name or ":" in name or name.startswith("/")
            or any(part in ("", ".", "..") for part in parts)
            or any(part.rstrip(" .") != part for part in parts)
            or any(re.match(r"^(con|prn|aux|nul|com[1-9]|lpt[1-9])(?:\.|$)",
                            part, re.I) for part in parts)
            or any(ord(char) < 32 for char in name)):
        raise IntakeError(f"unsafe archive path: {name!r}")
    return PurePosixPath(name).as_posix()


def inspect_bundle(archive: Path, *, expected_sha256: str = EXPECTED_SHA256,
                   expected_bytes: int = EXPECTED_BYTES,
                   expected_commit: str = EXPECTED_COMMIT,
                   expected_site_files: int = 28) -> tuple[dict, dict[str, bytes]]:
    if archive.stat().st_size != expected_bytes:
        raise IntakeError("ZIP byte count does not match the delivery")
    raw = archive.read_bytes()
    if len(raw) != expected_bytes or digest(raw) != expected_sha256:
        raise IntakeError("ZIP byte count or SHA-256 does not match the delivery")
    payloads: dict[str, bytes] = {}
    with zipfile.ZipFile(io.BytesIO(raw)) as bundle:
        infos = bundle.infolist()
        if len(infos) > MAX_FILES or sum(i.file_size for i in infos) > MAX_EXPANDED_BYTES:
            raise IntakeError("archive expansion limit exceeded")
        seen: set[str] = set()
        file_names = {safe_path(item.filename).casefold() for item in infos if not item.is_dir()}
        for item in infos:
            path = safe_path(item.filename, directory=item.is_dir())
            collision_key = path.casefold()
            if collision_key in seen:
                raise IntakeError(f"duplicate/case-colliding path: {path}")
            seen.add(collision_key)
            if any(parent.as_posix().casefold() in file_names for parent in PurePosixPath(path).parents if parent.as_posix() != "."):
                raise IntakeError(f"file used as directory: {path}")
            mode = item.external_attr >> 16
            if stat.S_ISLNK(mode) or (stat.S_IFMT(mode) not in (0, stat.S_IFREG, stat.S_IFDIR)):
                raise IntakeError(f"non-regular archive member: {path}")
            if not (path == "site" or path.startswith("site/")
                    or path in ("MANIFEST.tsv", "TOOLS.txt")):
                raise IntakeError(f"unexpected archive member: {path}")
            if item.flag_bits & 1:
                raise IntakeError("encrypted members are not supported")
            if not item.is_dir():
                payloads[path] = bundle.read(item)  # ZIP CRC verified by zipfile.
        if bundle.testzip() is not None:
            raise IntakeError("ZIP CRC check failed")
    if "MANIFEST.tsv" not in payloads or "TOOLS.txt" not in payloads:
        raise IntakeError("MANIFEST.tsv or TOOLS.txt is missing")
    reader = csv.DictReader(io.StringIO(payloads["MANIFEST.tsv"].decode("utf-8-sig")), delimiter="\t")
    if reader.fieldnames != ["path", "bytes", "sha256_raw", "sha256_lf_normalized"]:
        raise IntakeError("unexpected manifest columns")
    rows = list(reader)
    manifest_paths: set[str] = set()
    evidence = []
    for row in rows:
        if None in row or any(value is None for value in row.values()):
            raise IntakeError("malformed manifest row")
        path = safe_path(row["path"])
        if path in manifest_paths:
            raise IntakeError(f"duplicate manifest path: {path}")
        manifest_paths.add(path)
        content = payloads.get("site/" + path)
        if content is None:
            raise IntakeError(f"manifest member missing: {path}")
        if (str(len(content)) != row["bytes"] or digest(content) != row["sha256_raw"]
                or digest(content.replace(b"\r\n", b"\n").replace(b"\r", b"\n"))
                != row["sha256_lf_normalized"]):
            raise IntakeError(f"manifest byte/hash mismatch: {path}")
        evidence.append({"path": path, "bytes": len(content), "sha256_raw": digest(content),
                         "sha256_lf_normalized": row["sha256_lf_normalized"]})
    actual_paths = {name.removeprefix("site/") for name in payloads if name.startswith("site/")}
    if actual_paths != manifest_paths or len(actual_paths) != expected_site_files:
        raise IntakeError("site file set does not exactly match the manifest/count")
    if "index.html" not in actual_paths:
        raise IntakeError("site index.html is missing")
    manifest = json.loads(payloads["site/v1/manifest.json"])
    if manifest.get("commit") != expected_commit or manifest.get("commit_dirty") is not False:
        raise IntakeError("source commit or clean-tree assertion does not match")
    if manifest.get("contract") != "v1":
        raise IntakeError("unexpected publication contract")
    game = json.loads(payloads["site/v1/game/849843.json"])
    pitches = game["pitches"]
    keys = [p["key"] for p in pitches]
    if (len(keys) != len(set(keys))
            or any(not re.fullmatch(r"849843:[1-9]\d*:[1-9]\d*", key) for key in keys)):
        raise IntakeError("invalid or duplicate target-game pitch IDs")
    pa_keys = {p["pa_key"] for p in pitches}
    if any(p["pa_key"] != p["key"].rsplit(":", 1)[0] for p in pitches):
        raise IntakeError("pitch/plate-appearance ID mismatch")
    statuses = Counter(p["rec"]["status"] for p in pitches)
    if len(pitches) != 262 or len(pa_keys) != 71 or statuses != {"ready": 246, "unsupported": 16}:
        raise IntakeError("849843 delivery counts differ from the agreed build")
    pas = game["pas"]
    if len(pas) != 71 or {p["pa_key"] for p in pas} != pa_keys:
        raise IntakeError("plate-appearance ledger mismatch")
    dates = json.loads(payloads["site/v1/dates.json"])["dates"]
    if not isinstance(dates, list) or any(not isinstance(d, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", d) for d in dates):
        raise IntakeError("invalid date catalogue")
    available_dates = sorted(PurePosixPath(name).stem for name in actual_paths if name.startswith("v1/games/"))
    missing_dates = sorted(set(dates) - set(available_dates))
    receipt = {
        "schema": "pitcheezy-exhibition-intake-v1",
        "evidence_kind": "offline_archive_integrity",
        "zip": {"bytes": len(raw), "sha256": digest(raw), "crc": "pass"},
        "source_commit": expected_commit,
        "site_files": len(actual_paths),
        "site_bytes": sum(len(payloads["site/" + name]) for name in actual_paths),
        "manifest_raw_and_lf": "pass", "files": evidence,
        "game": {"game_pk": 849843, "pitches": len(pitches), "plate_appearances": len(pa_keys),
                 "recommendation_status": dict(statuses), "source": game.get("source"),
                 "next_present": game.get("next") is not None},
        "catalogue": {"advertised_dates": len(dates), "supplied_date_files": len(available_dates),
                      "missing_date_files": missing_dates},
        "limitations": [
            "Missing advertised date files require resolution or an agreed fixed-game entry before release.",
            "Only game 849843 was parsed semantically; locked game 849844 received byte/hash checks only.",
            "No browser, physical-device, Cloudflare, live-feed, or load test is implied by this receipt.",
            "Sender's prior BLOCK review concerns an older commit; final-build independent review remains separate.",
            "Archive data and old health timestamps are not proof of live publisher operation.",
            "No model weights, full-broadcast video, or review/PROMPT.md are included.",
        ],
        "deployment_approved": False,
    }
    return receipt, payloads


def extract_verified(payloads: dict[str, bytes], receipt: dict, output: Path) -> None:
    # Validation is complete before output exists. Never replace an existing tree.
    output.mkdir(parents=True, exist_ok=False)
    for name, content in payloads.items():
        target = output.joinpath(*PurePosixPath(name).parts)
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("xb") as stream:
            stream.write(content)
        if digest(target.read_bytes()) != digest(content):
            raise IntakeError(f"extracted file verification failed: {name}")
    with (output / "intake-receipt.json").open("x", encoding="utf-8", newline="\n") as stream:
        json.dump(receipt, stream, ensure_ascii=False, indent=2)
        stream.write("\n")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("archive", type=Path)
    parser.add_argument("--output", type=Path, help="New private output directory; existing paths are refused")
    args = parser.parse_args()
    try:
        receipt, payloads = inspect_bundle(args.archive)
        if args.output is not None:
            extract_verified(payloads, receipt, args.output)
        summary = {key: receipt[key] for key in ("zip", "source_commit", "site_files", "site_bytes", "game", "catalogue", "deployment_approved")}
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except (IntakeError, zipfile.BadZipFile, UnicodeError, KeyError, TypeError, ValueError, OSError) as exc:
        print(f"INTAKE REJECTED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

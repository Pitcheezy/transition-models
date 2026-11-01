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
LEGACY_PROFILE = "legacy-fba6b2ff"
EXHIBITION_PROFILE = "exhibition-c47fe6cb"
EXHIBITION_ROOT = "bundle-849843-main-c47fe6cb-20261101"
EXHIBITION_SHA256 = "3c3b8006b892872bfff3423e2bd6ba49ea3de17ee92fbecef07e0b076bc8da51"
EXHIBITION_BYTES = 182517
EXHIBITION_WEB_COMMIT = "c47fe6cb78479362e7250141da946814cc33bd31"
EXHIBITION_DATA_COMMIT = "cb1cfa8f759fd77adc75595316a389208c752dba"
EXHIBITION_METADATA = frozenset({
    "LOCAL-BROWSER.json", "PROVENANCE.json", "README.txt", "REPLACEMENT.txt",
    "REVIEW.txt", "SITE-CHECK.txt", "TOOLS.json", "VALIDATION.json", "verify_bundle.py",
})
EXHIBITION_SITE_FILES = frozenset({
    "assets/index-X1sSTTQ4.js", "assets/index-ks_hu7Ji.css", "favicon.svg", "index.html",
    "v1/dates.json", "v1/game/849843.json", "v1/games/2026-09-30.json",
    "v1/health.json", "v1/manifest.json", "v1/setup/849843.json",
})
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


def inspect_bundle(archive: Path, *, profile: str = LEGACY_PROFILE,
                   expected_sha256: str | None = None,
                   expected_bytes: int | None = None,
                   expected_commit: str | None = None,
                   expected_site_files: int | None = None) -> tuple[dict, dict[str, bytes]]:
    if profile not in (LEGACY_PROFILE, EXHIBITION_PROFILE):
        raise IntakeError("unknown exhibition intake profile")
    exhibition = profile == EXHIBITION_PROFILE
    if expected_sha256 is None:
        expected_sha256 = EXHIBITION_SHA256 if exhibition else EXPECTED_SHA256
    if expected_bytes is None:
        expected_bytes = EXHIBITION_BYTES if exhibition else EXPECTED_BYTES
    if expected_commit is None:
        expected_commit = EXHIBITION_WEB_COMMIT if exhibition else EXPECTED_COMMIT
    if expected_site_files is None:
        expected_site_files = len(EXHIBITION_SITE_FILES) if exhibition else 28
    allowed_files = (EXHIBITION_METADATA | {"MANIFEST.tsv"}
                     | {"site/" + name for name in EXHIBITION_SITE_FILES})
    allowed_directories = {""} | {
        parent.as_posix() for name in allowed_files for parent in PurePosixPath(name).parents
        if parent.as_posix() != "."
    }
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
        # Validate every original path before stripping the delivery's root.
        checked = []
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
            if item.flag_bits & 1:
                raise IntakeError("encrypted members are not supported")
            checked.append((item, path))
        for item, path in checked:
            if exhibition:
                if path == EXHIBITION_ROOT and item.is_dir():
                    continue
                if not path.startswith(EXHIBITION_ROOT + "/"):
                    raise IntakeError(f"unexpected archive root: {path}")
                path = path.removeprefix(EXHIBITION_ROOT + "/")
                allowed = allowed_directories if item.is_dir() else allowed_files
                if path not in allowed:
                    raise IntakeError(f"unexpected archive member: {path}")
            elif not (path == "site" or path.startswith("site/")
                      or path in ("MANIFEST.tsv", "TOOLS.txt")):
                raise IntakeError(f"unexpected archive member: {path}")
            if not item.is_dir():
                payloads[path] = bundle.read(item)  # ZIP CRC verified by zipfile.
        if bundle.testzip() is not None:
            raise IntakeError("ZIP CRC check failed")
    if exhibition and set(payloads) != allowed_files:
        raise IntakeError("exhibition bundle file set does not match the profile")
    if not exhibition and ("MANIFEST.tsv" not in payloads or "TOOLS.txt" not in payloads):
        raise IntakeError("MANIFEST.tsv or TOOLS.txt is missing")
    reader = csv.DictReader(io.StringIO(payloads["MANIFEST.tsv"].decode("utf-8-sig")), delimiter="\t")
    lf_column = "sha256_lf" if exhibition else "sha256_lf_normalized"
    if reader.fieldnames != ["path", "bytes", "sha256_raw", lf_column]:
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
        content = payloads.get(path if exhibition else "site/" + path)
        if content is None:
            raise IntakeError(f"manifest member missing: {path}")
        if (str(len(content)) != row["bytes"] or digest(content) != row["sha256_raw"]
                or digest(content.replace(b"\r\n", b"\n").replace(b"\r", b"\n"))
                != row[lf_column]):
            raise IntakeError(f"manifest byte/hash mismatch: {path}")
        evidence.append({"path": path, "bytes": len(content), "sha256_raw": digest(content),
                         "sha256_lf_normalized": row[lf_column]})
    actual_paths = {name.removeprefix("site/") for name in payloads if name.startswith("site/")}
    expected_manifest_paths = set(payloads) - {"MANIFEST.tsv"} if exhibition else actual_paths
    if expected_manifest_paths != manifest_paths or len(actual_paths) != expected_site_files:
        raise IntakeError("site file set does not exactly match the manifest/count")
    if "index.html" not in actual_paths:
        raise IntakeError("site index.html is missing")
    manifest = json.loads(payloads["site/v1/manifest.json"])
    data_commit = EXHIBITION_DATA_COMMIT if exhibition else expected_commit
    if manifest.get("commit") != data_commit or manifest.get("commit_dirty") is not False:
        raise IntakeError("source commit or clean-tree assertion does not match")
    if manifest.get("contract") != "v1":
        raise IntakeError("unexpected publication contract")
    if exhibition:
        provenance = json.loads(payloads["PROVENANCE.json"])
        tools = json.loads(payloads["TOOLS.json"])
        if (provenance.get("web_build_source_commit") != expected_commit
                or provenance.get("public_data_generation_source_commit") != data_commit
                or provenance.get("v1_manifest_commit_observed") != data_commit
                or tools.get("source_commit") != expected_commit
                or provenance.get("release_id") != EXHIBITION_ROOT):
            raise IntakeError("web/data provenance declarations do not match the profile")
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
    if exhibition:
        catalogue = json.loads(payloads["site/v1/games/2026-09-30.json"])
        catalogue_games = catalogue.get("games", [])
        if (dates != ["2026-09-30"] or manifest.get("live_dates") != dates
                or catalogue.get("date") != "2026-09-30"
                or len(catalogue_games) != 1
                or catalogue_games[0].get("game_pk") != 849843
                or catalogue_games[0].get("date_kst") != "2026-09-30"
                or game.get("game", {}).get("game_pk") != 849843
                or game.get("game", {}).get("date_kst") != "2026-09-30"):
            raise IntakeError("exhibition catalogue must contain only 849843 on 2026-09-30")
    # The app fetches exactly games/<date>.json, so only that path directly under v1/games counts as supplied.
    available_dates = sorted(d for d in set(dates) if f"v1/games/{d}.json" in actual_paths)
    missing_dates = sorted(set(dates) - set(available_dates))
    unlisted_games_files = sorted(name for name in actual_paths if name.startswith("v1/games/")
                                  and name not in {f"v1/games/{d}.json" for d in dates})
    site_evidence = [{**entry, "path": entry["path"].removeprefix("site/")}
                     for entry in evidence if entry["path"].startswith("site/")] if exhibition else evidence
    receipt = {
        "schema": "pitcheezy-exhibition-intake-v1",
        "evidence_kind": "offline_archive_integrity",
        "zip": {"bytes": len(raw), "sha256": digest(raw), "crc": "pass"},
        "source_commit": expected_commit,
        "source_commit_basis": "sender_declared_manifest_unverified",
        "declared_commit_dirty": manifest.get("commit_dirty"),
        "site_files": len(actual_paths),
        "site_bytes": sum(len(payloads["site/" + name]) for name in actual_paths),
        "manifest_raw_and_lf": "pass", "files": site_evidence,
        "game": {"game_pk": 849843, "pitches": len(pitches), "plate_appearances": len(pa_keys),
                 "recommendation_status": dict(statuses), "source": game.get("source"),
                 "next_present": game.get("next") is not None},
        "catalogue": {"advertised_dates": len(dates), "supplied_date_files": len(available_dates),
                      "missing_date_files": missing_dates, "unlisted_games_files": unlisted_games_files},
        "limitations": [
            "source_commit and the clean-tree flag are the sender's declaration in site/v1/manifest.json; no rebuild or source comparison was performed.",
            "Missing advertised date files require resolution or an agreed fixed-game entry before release.",
            "Only game 849843 was parsed semantically; locked game 849844 received byte/hash checks only.",
            "No browser, physical-device, Cloudflare, live-feed, or load test is implied by this receipt.",
            "Sender's prior BLOCK review concerns an older commit; final-build independent review remains separate.",
            "Archive data and old health timestamps are not proof of live publisher operation.",
            "No model weights, full-broadcast video, or review/PROMPT.md are included.",
        ],
        "deployment_approved": False,
    }
    if exhibition:
        receipt.update({
            "profile": profile,
            "archive_root": EXHIBITION_ROOT,
            "source_commit_basis": "sender_declared_provenance_unverified",
            "data_generation_commit": data_commit,
            "data_generation_commit_basis": "sender_declared_manifest_unverified",
            "manifest_scope": "all_bundle_files_except_MANIFEST.tsv",
            "manifest_entries": len(evidence),
            "manifest_lf_rule": "CRLF to LF, then remaining CR to LF; originals unchanged",
            "manifest_file": {"path": "MANIFEST.tsv", "bytes": len(payloads["MANIFEST.tsv"]),
                              "sha256_raw": digest(payloads["MANIFEST.tsv"])},
            "metadata_files": [entry for entry in evidence if not entry["path"].startswith("site/")],
            "limitations": [
                "Web source in PROVENANCE.json/TOOLS.json and data source in PROVENANCE.json/site/v1/manifest.json are sender declarations; no rebuild, source comparison, or provenance authentication was performed.",
                "Receipt files are site-relative; metadata_files preserves all nine metadata manifest entries separately. The archive root is stripped only after full-path safety validation.",
                "Only game 849843 and date 2026-09-30 are admitted by this profile; no other game was analysed.",
                "Received verify_bundle.py was checked as bytes only and was not executed.",
                "No browser, physical-device, Cloudflare, live-feed, or load test is implied by this receipt.",
                "Sender review and validation reports are integrity-checked evidence files, not independently reproduced results.",
                "Archive data and old health timestamps are not proof of live publisher operation.",
            ],
        })
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
    parser.add_argument("--profile", choices=(LEGACY_PROFILE, EXHIBITION_PROFILE), default=LEGACY_PROFILE,
                        help="Pinned sender format; legacy delivery remains the default")
    parser.add_argument("--output", type=Path, help="New private output directory; existing paths are refused")
    args = parser.parse_args()
    try:
        receipt, payloads = inspect_bundle(args.archive, profile=args.profile)
        if args.output is not None:
            extract_verified(payloads, receipt, args.output)
        summary = {key: receipt[key] for key in ("zip", "source_commit", "source_commit_basis", "site_files", "site_bytes", "game", "catalogue", "deployment_approved")}
        if "data_generation_commit" in receipt:
            summary["data_generation_commit"] = receipt["data_generation_commit"]
        print(json.dumps(summary, ensure_ascii=False, indent=2))
        return 0
    except (IntakeError, zipfile.BadZipFile, UnicodeError, KeyError, TypeError, ValueError, OSError) as exc:
        print(f"INTAKE REJECTED: {exc}")
        return 1


if __name__ == "__main__":
    raise SystemExit(main())

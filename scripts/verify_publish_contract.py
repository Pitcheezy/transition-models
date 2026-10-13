"""Verify a received public-publish contract pack (examples + JSON Schemas) against the expected list.

Reads only local files: hashes, JSON Schema (draft 2020-12) validation, publish envelope checks and
the host's own path/size constraints. Never fetches, never deploys, never rewrites the received files.
Run inside the project environment (needs the pinned jsonschema package, so not with python -S).
"""

import argparse
import hashlib
import json
import re
import sys
from datetime import UTC, datetime
from pathlib import Path

try:
    import jsonschema
    from referencing import Registry
except ImportError:  # pragma: no cover - the project environment pins jsonschema
    jsonschema = None

MAX_JSON_BYTES = 5 * 1024 * 1024
HOST_PATH = re.compile(
    r"^v1/(?:(?:manifest|health|dates)\.json|(?:game|setup)/[1-9][0-9]{0,11}\.json|games/[0-9]{4}-[0-9]{2}-[0-9]{2}\.json)$"
)
ISO = re.compile(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,6})?Z$")
SCHEMA_NAMES = ("dates", "games", "game", "setup", "manifest", "health")


class VerifyError(ValueError):
    """Fixed diagnostic code; received content is never interpolated."""


def _plain(path: Path) -> Path:
    # Link check runs on the unresolved absolute path: resolve() would already have followed any link.
    path = path.absolute()
    if any(part.is_symlink() for part in [path, *path.parents]):
        raise VerifyError("linked_path")
    return path.resolve()


def _read(path: Path, limit: int = MAX_JSON_BYTES) -> bytes:
    path = _plain(path)
    if not path.is_file() or path.stat().st_size > limit:
        raise VerifyError("input_not_regular_or_too_large")
    return path.read_bytes()


def digest(raw: bytes) -> str:
    return hashlib.sha256(raw).hexdigest()


def load_expected(raw: bytes) -> dict:
    try:
        expected = json.loads(raw.decode("utf-8"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise VerifyError("expected_invalid_json") from exc
    if (
        not isinstance(expected, dict)
        or expected.get("schema") != "pitcheezy-collab001-expected-files-v1"
        or not re.fullmatch(r"[a-f0-9]{40}", str(expected.get("commit", "")))
        or not isinstance(expected.get("files"), list)
        or not expected["files"]
    ):
        raise VerifyError("expected_invalid")
    for row in expected["files"]:
        if (
            not isinstance(row, dict)
            or not re.fullmatch(
                r"(examples|schema)/[A-Za-z0-9._-]+\.json", str(row.get("path", ""))
            )
            or not re.fullmatch(r"[a-f0-9]{64}", str(row.get("sha256", "")))
        ):
            raise VerifyError("expected_invalid")
        if row["path"].startswith("examples/"):
            if row.get("schema") not in SCHEMA_NAMES or not HOST_PATH.fullmatch(
                str(row.get("target", ""))
            ):
                raise VerifyError("expected_invalid")
    return expected


def _json_object(raw: bytes) -> dict:
    try:
        value = json.loads(raw.decode("utf-8", errors="strict"))
    except (UnicodeDecodeError, ValueError) as exc:
        raise VerifyError("received_invalid_json") from exc
    if not isinstance(value, dict):
        raise VerifyError("received_json_object_required")
    return value


def check_envelope(name: str, value: dict, schema_name: str) -> dict:
    """The pack says every file carries a top-level `publish`; only game/setup carry `final`."""
    publish = value.get("publish")
    report = {"present": isinstance(publish, dict)}
    if not isinstance(publish, dict):
        return {**report, "ok": False, "issue": "publish_missing"}
    issues = []
    if publish.get("contract") != "v1":
        issues.append("contract_not_v1")
    sequence = publish.get("sequence")
    if type(sequence) is not int or sequence < 0:  # bool is an int subclass and is not a sequence
        issues.append("sequence_invalid")
    if not isinstance(publish.get("published_at"), str) or not ISO.fullmatch(
        publish["published_at"]
    ):
        issues.append("published_at_invalid")
    has_final = "final" in publish
    if schema_name in ("game", "setup") and not isinstance(publish.get("final"), bool):
        issues.append("final_missing")
    if schema_name not in ("game", "setup") and has_final:
        issues.append("final_unexpected")
    return {
        **report,
        "ok": not issues,
        "issues": issues,
        "sequence": publish.get("sequence"),
        "published_at": publish.get("published_at"),
        "final": publish.get("final") if has_final else None,
    }


def verify(received: Path, expected: dict) -> dict:
    if jsonschema is None:
        raise VerifyError("jsonschema_unavailable")
    received = _plain(received)
    schemas: dict[str, dict] = {}
    contents: dict[str, bytes] = {}
    rows = []
    hash_ok = 0
    for row in expected["files"]:
        path = received / row["path"]
        try:
            raw = _read(path)
        except VerifyError as exc:
            rows.append({"path": row["path"], "status": "missing", "code": str(exc)})
            continue
        contents[row["path"]] = raw
        actual = digest(raw)
        matched = actual == row["sha256"]
        hash_ok += matched
        entry = {
            "path": row["path"],
            "bytes": len(raw),
            "sha256": actual,
            "hash_matches_pack": matched,
        }
        if row["path"].startswith("schema/"):
            try:
                schema = _json_object(raw)
            except VerifyError as exc:
                entry.update(status="invalid_schema_file", code=str(exc))
                rows.append(entry)
                continue
            name = row["path"].split("/")[-1].removesuffix(".schema.json")
            draft = schema.get("$schema")
            entry.update(
                status="schema",
                draft=draft,
                draft_2020_12=isinstance(draft, str) and "2020-12" in draft,
                schema_id=schema.get("$id"),
            )
            schemas[name] = schema
        rows.append(entry)
    for entry, row in zip(
        [r for r in rows if r["path"].startswith("examples/")],
        [r for r in expected["files"] if r["path"].startswith("examples/")],
        strict=True,
    ):
        if entry.get("status") == "missing":
            continue
        raw = contents[row["path"]]  # the bytes that were hashed, read once
        try:
            value = _json_object(raw)
        except VerifyError as exc:
            entry.update(status="invalid_example", code=str(exc))
            continue
        schema = schemas.get(row["schema"])
        if schema is None:
            entry.update(status="schema_unavailable", schema=row["schema"])
            continue
        try:
            validator_class = jsonschema.validators.validator_for(schema)
            validator_class.check_schema(schema)
            errors = sorted(
                # An explicit registry keeps untrusted $ref values offline. The
                # jsonschema default may retrieve HTTP or file URLs implicitly.
                # In-document references still resolve against this schema.
                validator_class(schema, registry=Registry()).iter_errors(value),
                key=lambda e: [str(p) for p in e.path],
            )
        except Exception:
            # The received schema is untrusted input: an unusable schema (invalid, unresolvable $ref, ...)
            # is a reported row with a fixed code, never a traceback that echoes its content.
            entry.update(
                status="schema_unusable", schema=row["schema"], code="schema_evaluation_failed"
            )
            continue
        game = value.get("game") if isinstance(value.get("game"), dict) else {}
        display = value.get("display_state") if isinstance(value.get("display_state"), dict) else {}
        rec = value.get("next", {}).get("rec", {}) if isinstance(value.get("next"), dict) else {}
        entry.update(
            status="example",
            schema=row["schema"],
            target=row["target"],
            stage=row.get("stage"),
            target_allowed_by_host=bool(HOST_PATH.fullmatch(row["target"])),
            within_host_size_limit=len(raw) <= MAX_JSON_BYTES,
            utf8_json_object=True,
            schema_errors=len(errors),
            schema_error_paths=["/" + "/".join(str(p) for p in e.path) for e in errors[:5]],
            envelope=check_envelope(row["path"], value, row["schema"]),
            game_pk=game.get("game_pk", value.get("game_pk")),
            game_status=game.get("status"),
            display_state=display.get("state"),
            display_label=display.get("label"),
            rec_status=rec.get("status") if isinstance(rec, dict) else None,
        )
    examples = [r for r in rows if r.get("status") == "example"]
    states = sorted({r["display_state"] for r in examples if r.get("display_state")})
    all_hash = hash_ok == len(expected["files"])
    all_schema = (
        bool(examples)
        and all(r["schema_errors"] == 0 for r in examples)
        and len(examples)
        == len([r for r in expected["files"] if r["path"].startswith("examples/")])
    )
    all_envelope = bool(examples) and all(r["envelope"]["ok"] for r in examples)
    all_host = bool(examples) and all(
        r["target_allowed_by_host"] and r["within_host_size_limit"] for r in examples
    )
    return {
        "schema": "pitcheezy-collab001-contract-verification-v1",
        "generated_at": datetime.now(UTC).isoformat(timespec="seconds").replace("+00:00", "Z"),
        "source_commit": expected["commit"],
        "contract": expected.get("contract"),
        "files_expected": len(expected["files"]),
        "files_hash_matched": hash_ok,
        "all_hashes_match_pack": all_hash,
        "all_examples_valid_against_schema": all_schema,
        "all_examples_have_v1_publish_envelope": all_envelope,
        "all_targets_allowed_by_host": all_host,
        "display_states_seen": states,
        "unsupported_state_example_present": "unsupported" in states,
        "known_gaps": expected.get("known_gaps", []),
        "files": rows,
        "not_verified": [
            "publisher runtime behaviour (sequence, restart, withdrawal) beyond the delivered snapshots",
            "the screen bundle rendering these files (separate browser rehearsal)",
            "live data, real hosting, MLB usage permission",
        ],
        "ok": all_hash and all_schema and all_envelope and all_host,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--received", type=Path, required=True, help="directory holding examples/ and schema/"
    )
    parser.add_argument(
        "--expected", type=Path, required=True, help="expected-files JSON (commit + sha256 list)"
    )
    parser.add_argument("--output", type=Path, help="write the receipt JSON here (new file only)")
    args = parser.parse_args(argv)
    try:
        expected = load_expected(_read(args.expected, 65536))
        report = verify(args.received, expected)
        text = json.dumps(report, ensure_ascii=False, indent=2) + "\n"
        if args.output:
            with open(
                _plain(args.output.parent) / args.output.name, "x", encoding="utf-8"
            ) as handle:
                handle.write(text)
        sys.stdout.write(text)
        return 0 if report["ok"] else 1
    except VerifyError as exc:
        print(json.dumps({"ok": False, "error": str(exc)}))
        return 2
    except OSError as exc:
        print(json.dumps({"ok": False, "error": "output_or_input_unavailable", "errno": exc.errno}))
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

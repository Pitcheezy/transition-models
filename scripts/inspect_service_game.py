"""Audit an explicitly supplied local service-game JSON export without contacting a service."""

import argparse
import hashlib
import json
import math
import os
import stat
import sys
from pathlib import Path

# This read-only audit must not create import caches beside project source files.
sys.dont_write_bytecode = True
ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.integration.service_game import (  # noqa: E402
    PROFILE,
    PROFILES,
    ServiceGameError,
    normalize_service_game,
)

MAX_INPUT_BYTES = 5 * 1024 * 1024


class AuditInputError(ValueError):
    """Carry a fixed, payload-free error message suitable for the command line."""


def _local_path(value: str) -> Path:
    """Reject remote and Windows device/alternate-stream paths before opening files."""
    portable = value.replace("\\", "/")
    if portable.startswith("//") or "://" in portable:
        raise AuditInputError("Only local filesystem paths are accepted.")
    components = portable.split("/")
    for index, component in enumerate(components):
        if index == 0 and len(component) == 2 and component[0].isalpha() and component[1] == ":":
            continue
        if ":" in component:
            raise AuditInputError("Device and alternate-stream paths are not accepted.")
        stem = component.rstrip(" .").split(".", 1)[0].upper()
        if stem in {"CON", "PRN", "AUX", "NUL", "CONIN$", "CONOUT$"} or (
            len(stem) == 4 and stem[:3] in {"COM", "LPT"} and stem[3] in "123456789"
        ):
            raise AuditInputError("Device and alternate-stream paths are not accepted.")
    return Path(value)


def _unique_object(pairs: list[tuple[str, object]]) -> dict:
    """Reject duplicate JSON object keys at every nesting level."""
    result = {}
    for key, value in pairs:
        if key in result:
            raise AuditInputError("JSON object keys must be unique.")
        result[key] = value
    return result


def _nonfinite_constant(_value: str) -> None:
    raise AuditInputError("JSON numbers must be finite.")


def _finite_float(value: str) -> float:
    number = float(value)
    if not math.isfinite(number):
        raise AuditInputError("JSON numbers must be finite.")
    return number


def _read_input(path: Path) -> tuple[object, str]:
    """Read at most the bounded original bytes from a local regular file."""
    if not stat.S_ISREG(path.stat().st_mode):
        raise AuditInputError("Input must be a regular file.")
    flags = os.O_RDONLY | getattr(os, "O_BINARY", 0) | getattr(os, "O_NONBLOCK", 0)
    descriptor = os.open(path, flags)
    with os.fdopen(descriptor, "rb") as stream:
        metadata = os.fstat(stream.fileno())
        if not stat.S_ISREG(metadata.st_mode):
            raise AuditInputError("Input must be a regular file.")
        if metadata.st_size > MAX_INPUT_BYTES:
            raise AuditInputError("Input exceeds the 5 MiB limit.")
        original = stream.read(MAX_INPUT_BYTES + 1)
    if len(original) > MAX_INPUT_BYTES:
        raise AuditInputError("Input exceeds the 5 MiB limit.")
    try:
        content = original.decode("utf-8-sig", errors="strict")
    except UnicodeDecodeError:
        raise AuditInputError("Input must be valid UTF-8 JSON.") from None
    try:
        payload = json.loads(
            content,
            object_pairs_hook=_unique_object,
            parse_constant=_nonfinite_constant,
            parse_float=_finite_float,
        )
    except json.JSONDecodeError:
        raise AuditInputError("Input must contain exactly one valid JSON document.") from None
    return payload, hashlib.sha256(original).hexdigest()


def _write_report(path: Path, input_path: Path, serialized: str) -> None:
    """Create only a new explicitly requested JSON report in an existing directory."""
    if len(serialized.encode("utf-8")) > MAX_INPUT_BYTES:
        raise AuditInputError("Normalized report exceeds the viewer 5 MiB limit.")
    if path.suffix.lower() != ".json":
        raise AuditInputError("Output must have a .json extension.")
    if path.is_symlink():
        raise AuditInputError("Output must be a new file, not a symbolic link.")
    if path.resolve() == input_path.resolve():
        raise AuditInputError("Output must differ from input.")
    if not path.parent.is_dir():
        raise AuditInputError("Output parent directory must already exist.")
    # On Windows a dangling symlink can be followed even in x mode; reject it above.
    # Exclusive creation refuses an existing file or a concurrent ordinary writer.
    with path.open("x", encoding="utf-8", newline="\n") as stream:
        stream.write(serialized)


def main(argv: list[str] | None = None) -> int:
    """Validate one explicit input and print only a compact normalized audit summary."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Local UTF-8 JSON file, at most 5 MiB.")
    parser.add_argument(
        "--profile",
        choices=PROFILES,
        default=PROFILE,
        help="Explicit contract profile; defaults to the legacy provisional STATUS interpretation.",
    )
    parser.add_argument(
        "--source-kind",
        required=True,
        choices=("synthetic", "provided_export"),
        help="Declare whether these bytes are a synthetic fixture or a provided export.",
    )
    parser.add_argument(
        "--source-revision", help="Optional reported service revision; not independently verified."
    )
    parser.add_argument(
        "--out", help="Optional new .json report in an existing directory; never overwrite."
    )
    args = parser.parse_args(argv)
    try:
        input_path = _local_path(args.input)
        output_path = _local_path(args.out) if args.out is not None else None
        payload, digest = _read_input(input_path)
        report = normalize_service_game(
            payload,
            input_kind=args.source_kind,
            source_sha256=digest,
            reported_revision=args.source_revision,
            profile=args.profile,
        )
        summary = {
            "schema": report["schema"],
            "source_sha256": digest,
            "summary": report["summary"],
            "warnings": report["warnings"],
        }
        compact = json.dumps(summary, ensure_ascii=True, allow_nan=False, separators=(",", ":"))
        if output_path is not None:
            serialized = (
                json.dumps(report, ensure_ascii=False, allow_nan=False, separators=(",", ":"))
                + "\n"
            )
            _write_report(output_path, input_path, serialized)
    except (AuditInputError, ServiceGameError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except FileExistsError:
        print("error: Output already exists; refusing to overwrite.", file=sys.stderr)
        return 2
    except OSError:
        print("error: Could not access the requested local file.", file=sys.stderr)
        return 2
    except (ValueError, RecursionError):
        print("error: Input does not satisfy the service-game review contract.", file=sys.stderr)
        return 2
    print(compact)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

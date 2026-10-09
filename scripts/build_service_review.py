"""Build a private local review of one provided S snapshot; no network or deployment."""

import argparse
import hashlib
import json
import sys
from pathlib import Path

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

ASSETS = ("index.html", "review.js", "style.css")


def build_review(input_path: Path, output_dir: Path, *, input_kind: str) -> dict:
    """Validate before creating a fresh directory and never replace an existing package."""
    if output_dir.exists() or output_dir.is_symlink():
        raise AuditInputError("Output directory must not already exist.")
    if not output_dir.parent.is_dir():
        raise AuditInputError("Output parent directory must already exist.")
    destination = output_dir.resolve()
    for public_root in (ROOT / "web", ROOT / "docs"):
        if destination.is_relative_to(public_root.resolve()):
            raise AuditInputError("Private review data must stay outside web and docs.")
    payload, digest = _read_input(input_path)
    report = normalize_service_game(
        payload, input_kind=input_kind, source_sha256=digest, profile=EXPORT_PROFILE
    )
    assets = {name: (ROOT / "web" / "service-review" / name).read_bytes() for name in ASSETS}
    report_bytes = (
        json.dumps(report, ensure_ascii=False, allow_nan=False, separators=(",", ":")) + "\n"
    ).encode("utf-8")
    if len(report_bytes) > MAX_INPUT_BYTES:
        raise AuditInputError("Normalized report exceeds the local viewer 5 MiB limit.")
    receipt = {
        "schema": "pitcheezy-private-service-review-package-v1",
        "profile": EXPORT_PROFILE,
        "input_kind": input_kind,
        "source_sha256": digest,
        "report_sha256": hashlib.sha256(report_bytes).hexdigest(),
        "assets_sha256": {name: hashlib.sha256(data).hexdigest() for name, data in assets.items()},
        "summary": report["summary"],
        "public_distribution": False,
        "live_validation": False,
    }
    output_dir.mkdir()
    for name, data in assets.items():
        (output_dir / name).write_bytes(data)
    (output_dir / "review-data.json").write_bytes(report_bytes)
    (output_dir / "receipt.json").write_text(
        json.dumps(receipt, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (output_dir / "PRIVATE.txt").write_text(
        "Internal local review only. Contains post-pitch data. Do not publish this directory.\n"
        "Display hiding is not access control or evidence of pre-pitch inference.\n"
        "Run: python -m http.server 8793 --bind 127.0.0.1 --directory <this-directory>\n",
        encoding="utf-8",
    )
    return receipt


def main(argv: list[str] | None = None) -> int:
    """Build from an explicitly declared local source and print only aggregate evidence."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Local S raw JSON, at most 5 MiB.")
    parser.add_argument(
        "--out-dir", required=True, help="New private directory; parent must exist."
    )
    parser.add_argument("--source-kind", choices=("synthetic", "provided_export"), required=True)
    args = parser.parse_args(argv)
    try:
        receipt = build_review(
            _local_path(args.input), _local_path(args.out_dir), input_kind=args.source_kind
        )
    except (AuditInputError, ServiceGameError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 2
    except (OSError, ValueError, RecursionError):
        print(
            "error: Could not build the private review package; existing files were not replaced.",
            file=sys.stderr,
        )
        return 2
    print(json.dumps(receipt, ensure_ascii=True, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

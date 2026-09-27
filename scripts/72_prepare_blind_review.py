"""Freeze A-y selection, build a reviewer-only package, or validate returned JSON."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.blind_review import (  # noqa: E402
    INPUTS,
    ROOT,
    build_package,
    canonical_hash,
    check_package,
    freeze_protocol,
    read_json,
    template_from_protocol,
    validate_response,
)

DEFAULT_PROTOCOL = ROOT / "docs/results/mlb_p0/game_747139_blind_review_protocol.json"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("freeze", "build", "check-package", "check-response"))
    parser.add_argument("--protocol", type=Path, default=DEFAULT_PROTOCOL)
    parser.add_argument("--baseline-commit", help="Required for freeze; full immutable git SHA")
    parser.add_argument(
        "--output", type=Path, default=ROOT / "outputs/blind_review/game_747139_ay_v2"
    )
    parser.add_argument("--response", type=Path)
    parser.add_argument("--require-complete", action="store_true")
    args = parser.parse_args()
    if args.command == "freeze":
        if not args.baseline_commit:
            parser.error("freeze requires --baseline-commit")
        inputs = {name: read_json(ROOT / path) for name, path in INPUTS.items()}
        protocol = freeze_protocol(inputs, args.baseline_commit)
        for name, path in INPUTS.items():
            committed = json.loads(
                subprocess.check_output(
                    ["git", "show", f"{args.baseline_commit}:{path}"], cwd=ROOT
                ).decode("utf-8")
            )
            if canonical_hash(committed) != canonical_hash(inputs[name]):
                raise ValueError(f"Working input differs from baseline commit: {path}")
        if args.protocol.exists() and read_json(args.protocol) != protocol:
            raise ValueError(
                "Protocol already exists with different content; do not revise after review"
            )
        args.protocol.parent.mkdir(parents=True, exist_ok=True)
        args.protocol.write_text(
            json.dumps(protocol, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
            encoding="utf-8",
        )
        result = {"protocol": str(args.protocol), "baseline_commit": args.baseline_commit}
    else:
        protocol = read_json(args.protocol)
        if args.command == "build":
            result = build_package(protocol, args.output)
        elif args.command == "check-package":
            result = check_package(protocol, args.output)
        else:
            if args.response is None:
                parser.error("check-response requires --response")
            result = validate_response(
                read_json(args.response), template_from_protocol(protocol), args.require_complete
            )
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

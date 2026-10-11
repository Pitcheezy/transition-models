"""Build/check/summarize manual player identity evidence, never automatic recognition accuracy."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.blind_review import canonical_hash, read_json  # noqa: E402
from src.data.player_identity import (  # noqa: E402
    ROOT,
    build_player_identity_evalset,
    bytes_hash,
    check_player_identity_evalset,
)

RESULTS = ROOT / "docs/results/mlb_p0"
DEFAULT_INPUTS = {
    "manifest": RESULTS / "game_747139_manifest.json",
    "timing": RESULTS / "game_747139_timing.json",
    "feed": ROOT / "data/raw/mlb_video/747139/feed.json",
    "review": RESULTS / "game_747139_player_identity_review_pa6.json",
}
DEFAULT_OUTPUT = RESULTS / "game_747139_player_identity_evalset_pa6.json"


def _same_file(left, right):
    return left.resolve() == right.resolve() or (
        left.exists() and right.exists() and left.samefile(right)
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("build", "check", "summary"))
    for name, default in DEFAULT_INPUTS.items():
        parser.add_argument(f"--{name}", type=Path, default=default)
    parser.add_argument(
        "--output", type=Path, help="evalset path; required for a build with custom inputs"
    )
    parser.add_argument(
        "--verify-frames",
        action="store_true",
        help="also verify local image bytes and source/time cache binding",
    )
    args = parser.parse_args()
    custom_inputs = any(
        getattr(args, name).resolve() != default.resolve()
        for name, default in DEFAULT_INPUTS.items()
    )
    if args.command == "build" and args.output is None and custom_inputs:
        parser.error("build with custom inputs requires an explicit --output")
    args.output = args.output or DEFAULT_OUTPUT
    if args.command == "build" and custom_inputs and _same_file(args.output, DEFAULT_OUTPUT):
        parser.error("custom-input builds must not overwrite the canonical PA6 evalset")
    if args.command == "build" and any(
        _same_file(args.output, path)
        for path in (*DEFAULT_INPUTS.values(), *(getattr(args, name) for name in DEFAULT_INPUTS))
    ):
        parser.error("--output must not alias any manifest, timing, feed or manual review input")
    if args.command == "summary":
        result = check_player_identity_evalset(
            read_json(args.output), verify_frames=args.verify_frames
        )
    else:
        manifest, timing, review = (
            read_json(path) for path in (args.manifest, args.timing, args.review)
        )
        rebuilt = None
        if args.feed.is_file():
            rebuilt = build_player_identity_evalset(
                manifest,
                timing,
                read_json(args.feed),
                review,
                feed_sha256=bytes_hash(args.feed.read_bytes()),
            )
        elif args.command == "build":
            parser.error(
                "build requires the frozen raw --feed file; cannot invent roster or reference IDs"
            )
        if args.command == "build":
            document = rebuilt
            result = check_player_identity_evalset(document, verify_frames=args.verify_frames)
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(
                json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
                encoding="utf-8",
            )
        else:
            document = read_json(args.output)
            result = check_player_identity_evalset(document, verify_frames=args.verify_frames)
            expected_hashes = {
                "manifest_sha256": canonical_hash(manifest),
                "timing_sha256": canonical_hash(timing),
                "review_sha256": canonical_hash(review),
            }
            if any(
                document["input_hashes"][name] != value for name, value in expected_hashes.items()
            ):
                raise ValueError(
                    "Frozen evalset differs from the tracked manifest, timing or manual review"
                )
            if rebuilt is not None and rebuilt != document:
                raise ValueError("Evalset does not match a full rebuild from frozen input files")
        if rebuilt is not None:
            result.update(validation_level="full_input_rebuild", feed_bytes_reverified=True)
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

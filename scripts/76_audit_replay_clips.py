"""Decode a bounded, private PA evidence pack. Does not classify mitts or fetch media."""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.data.replay_feasibility import build_audit  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--through-pa", type=int, default=1, choices=range(1, 6))
    parser.add_argument("--ffprobe", default="ffprobe")
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    result = build_audit(args.root, args.out, args.ffprobe, args.ffmpeg, args.through_pa)
    print(
        f"849843: examined={result['examined']} decoded={result['decoded']}; semantic review pending"
    )
    return 0 if result["examined"] == result["decoded"] else 1


if __name__ == "__main__":
    raise SystemExit(main())

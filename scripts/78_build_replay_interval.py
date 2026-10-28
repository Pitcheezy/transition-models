"""Save all decoded frames in the fixed three PA1 development intervals privately."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.replay_interval import build_intervals


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--root", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--ffprobe", required=True, type=Path)
    parser.add_argument("--ffmpeg", required=True, type=Path)
    args = parser.parse_args()
    report = build_intervals(args.root, args.out, args.ffprobe, args.ffmpeg)
    print(
        json.dumps(
            {
                "schema": report["schema"],
                "clips": len(report["records"]),
                "frames": sum(len(row["sampled_frames"]) for row in report["records"]),
            }
        )
    )


if __name__ == "__main__":
    main()

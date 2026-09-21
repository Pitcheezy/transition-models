"""Build a verified pitch/video index from local Statcast and MLB feed snapshots."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.mlb_video import write_game_manifest


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--statcast", type=Path, required=True)
    parser.add_argument("--feed", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    result = write_game_manifest(args.statcast, args.feed, args.output)
    print(json.dumps({"game_pk": result["game_pk"], "counts": result["counts"]}))
    if set(result["counts"]) != {"verified"}:
        raise SystemExit(
            "Identity audit incomplete: inspect manifest; do not use conflicted clips."
        )


if __name__ == "__main__":
    main()

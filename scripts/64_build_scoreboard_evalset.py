"""Build, check or score the scoreboard-recognition evaluation set for one game.

Usage::

    uv run --frozen python scripts/64_build_scoreboard_evalset.py build --output docs/results/mlb_p0/game_747139_scoreboard_evalset.json
    uv run --frozen python scripts/64_build_scoreboard_evalset.py check --evalset docs/results/mlb_p0/game_747139_scoreboard_evalset.json
    uv run --frozen python scripts/64_build_scoreboard_evalset.py score --evalset ... --predictions preds.json --output score.json

The set only contains pitches with human-verified timing; labels come from the identity
manifest (recorded metadata) and are never OCR output.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.scoreboard_evalset import (
    build_evalset,
    read_json,
    score_predictions,
    validate_evalset,
)

RESULTS = Path("docs/results/mlb_p0")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("build", "check", "score"))
    parser.add_argument("--manifest", type=Path, default=RESULTS / "game_747139_manifest.json")
    parser.add_argument("--sources", type=Path, default=RESULTS / "game_747139_sources.json")
    parser.add_argument("--timing", type=Path, default=RESULTS / "game_747139_timing.json")
    parser.add_argument("--evalset", type=Path)
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    manifest, sources, timing = (read_json(p) for p in (args.manifest, args.sources, args.timing))
    if args.mode == "build":
        result = build_evalset(manifest, sources, timing)
        rendered = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered + "\n", encoding="utf-8")
        print(json.dumps(result["coverage"], indent=2, ensure_ascii=False))
        return
    if not args.evalset:
        parser.error(f"{args.mode} requires --evalset")
    evalset = read_json(args.evalset)
    coverage = validate_evalset(evalset, manifest, sources, timing)
    if args.mode == "check":
        print(json.dumps(coverage, indent=2, ensure_ascii=False))
        return
    if not args.predictions:
        parser.error("score requires --predictions")
    result = score_predictions(evalset, read_json(args.predictions))
    rendered = json.dumps(result, indent=2, ensure_ascii=False, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(rendered)


if __name__ == "__main__":
    main()

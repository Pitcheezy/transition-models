"""Audit separate foul/strike/ball targets and optionally save identity-keyed Parquets."""

import argparse
import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.mlb_video import PITCH_KEYS
from src.data.pitch_observation import (
    OBSERVATION_CLASSES,
    OBSERVATION_SCHEMA,
    build_observation_targets,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--years", nargs="+", type=int, default=[2022, 2023, 2024])
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument(
        "--targets-dir", type=Path, help="Optional output directory for keyed targets"
    )
    args = parser.parse_args()
    report = {
        "schema": OBSERVATION_SCHEMA,
        "class_order": OBSERVATION_CLASSES,
        "years": {},
        "scope": "Label audit only. No new model trained; existing checkpoint unchanged.",
    }
    for year in args.years:
        frame = pd.read_parquet(
            args.raw_dir / str(year) / f"statcast_{year}.parquet",
            columns=PITCH_KEYS + ["description", "events", "game_type"],
        )
        frame = frame.loc[frame.game_type.eq("R")].reset_index(drop=True)
        targets = build_observation_targets(frame)
        report["years"][str(year)] = {
            "regular_season_rows": len(targets),
            "eligible": int(targets.target.ge(0).sum()),
            "class_counts": targets.observation.value_counts().to_dict(),
            "excluded": targets.loc[targets.target.lt(0), "exclusion_reason"]
            .value_counts()
            .to_dict(),
        }
        if args.targets_dir:
            args.targets_dir.mkdir(parents=True, exist_ok=True)
            targets.to_parquet(args.targets_dir / f"targets_{year}.parquet", index=False)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")
    if args.targets_dir:
        (args.targets_dir / "manifest.json").write_text(
            json.dumps(report, indent=2), encoding="utf-8"
        )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()

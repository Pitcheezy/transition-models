"""Build temporally separated pre-pitch datasets and observed policy-evaluation outcomes."""

import argparse
import hashlib
import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.features import CONTINUOUS_FEATURES
from src.data.operational import (
    FEATURE_SCHEMA,
    STATE_COLUMNS,
    OperationalFeatureBuilder,
    valid_states,
)
from src.data.point_data import PITCH_KEYS, identity_hash, make_point_data, validate_split_ids
from src.data.preprocess import extract_labels_10class
from src.evaluation.run_value import (
    fit_outcome_costs,
    fit_run_expectancy,
    observed_transitions,
    transition_cost,
)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    columns = list(
        dict.fromkeys(
            PITCH_KEYS
            + STATE_COLUMNS
            + CONTINUOUS_FEATURES
            + [
                "pitch_type",
                "zone",
                "batter",
                "description",
                "events",
                "game_type",
                "inning_topbot",
                "bat_score",
                "post_bat_score",
            ]
        )
    )
    raw = {}
    for year in (2022, 2023, 2024):
        frame = pd.read_parquet(
            args.raw_dir / str(year) / f"statcast_{year}.parquet", columns=columns
        )
        frame["game_date"] = pd.to_datetime(frame["game_date"])
        raw[year] = frame.loc[frame["game_type"] == "R"].reset_index(drop=True)
        print(year, "regular-season rows", len(raw[year]), flush=True)
    builder = OperationalFeatureBuilder.fit(raw[2022])
    with open(args.output_dir / "feature_builder.pkl", "wb") as file:
        pickle.dump(builder, file)
    history = observed_transitions(raw[2022])
    expectancy = fit_run_expectancy(history)
    outcome_costs = fit_outcome_costs(history, expectancy)
    np.savez(
        args.output_dir / "run_value_model.npz", expectancy=expectancy, outcome_costs=outcome_costs
    )
    periods = {
        "train": raw[2023],
        "val": raw[2024].loc[raw[2024]["game_date"].dt.month <= 5],
        "cal": raw[2024].loc[raw[2024]["game_date"].dt.month == 6],
        "test": raw[2024].loc[raw[2024]["game_date"].dt.month >= 7],
    }
    transition_frames = {year: observed_transitions(raw[year]) for year in (2023, 2024)}
    manifest = {
        "feature_schema": FEATURE_SCHEMA,
        "profile_period": "2022 regular season only",
        "selection": "2024 January-May",
        "calibration": "2024 June only",
        "test": "2024 July onward",
        "action": "pitch type, not intended location",
        "profile_sha256": hashlib.sha256(
            (args.output_dir / "feature_builder.pkl").read_bytes()
        ).hexdigest(),
        "run_expectancy_training_rows": len(history),
        "splits": {},
    }
    ids = {}
    for name, frame in periods.items():
        frame = frame.loc[valid_states(frame) & (extract_labels_10class(frame) >= 0)].reset_index(
            drop=True
        )
        x = builder.build(frame)
        data = make_point_data(frame, x)
        data["feature_schema"] = FEATURE_SCHEMA
        np.savez(args.output_dir / f"point_{name}.npz", **data)
        ids[name] = {"pitch_ids": data["pitch_ids"]}
        transitions = transition_frames[2023 if name == "train" else 2024]
        targets = transitions[PITCH_KEYS + ["state_code", "next_state", "runs", "label_10"]].copy()
        targets["run_cost"] = transition_cost(transitions, expectancy)
        metadata = frame[PITCH_KEYS + STATE_COLUMNS + ["pitch_type", "batter"]].merge(
            targets, on=PITCH_KEYS, how="left", sort=False, validate="one_to_one"
        )
        metadata.to_parquet(args.output_dir / f"metadata_{name}.parquet", index=False)
        available = builder.available_actions(frame)
        manifest["splits"][name] = {
            "n": len(frame),
            "pitch_ids_sha256": identity_hash(data["pitch_ids"]),
            "min_date": str(frame["game_date"].min()),
            "max_date": str(frame["game_date"].max()),
            "observed_run_cost_rows": int(metadata["run_cost"].notna().sum()),
            "at_least_two_supported_actions": int((available.sum(axis=1) >= 2).sum()),
        }
        print(name, json.dumps(manifest["splits"][name]), flush=True)
    validate_split_ids(ids)
    (args.output_dir / "dataset_manifest.json").write_text(
        json.dumps(manifest, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()

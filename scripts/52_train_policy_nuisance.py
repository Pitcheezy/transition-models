"""Fit independent propensity and observed run-cost nuisance models without test data."""

import argparse
import json
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.point_data import PITCH_KEYS, load_point_data
from src.evaluation.operational_metrics import fit_temperature, temperature_scale
from src.evaluation.policy_value import behavior_features
from src.inference.operational import action_indices


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=3)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    data, meta = {}, {}
    for split in ("train", "val", "cal"):
        data[split] = load_point_data(args.data_dir, split, input_dim=135)
        meta[split] = pd.read_parquet(args.data_dir / f"metadata_{split}.parquet")
        if not np.array_equal(data[split]["pitch_ids"], meta[split][PITCH_KEYS].to_numpy()):
            raise ValueError("Metadata identity mismatch")
    params = dict(
        learning_rate=0.05,
        num_leaves=31,
        max_depth=6,
        min_data_in_leaf=100,
        num_threads=args.threads,
        seed=42,
        deterministic=True,
        force_col_wise=True,
        verbosity=-1,
    )
    manifest = {
        "dataset": json.loads((args.data_dir / "dataset_manifest.json").read_text()),
        "propensity_input": "pre-state 31 + frozen profile 58; excludes action/physics/zone",
        "propensity_features": 89,
        "reward_features": 135,
        "training": "2023",
        "selection": "2024 Jan-May",
        "calibration": "June",
        "parameters": params,
        "status": "running",
    }
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    for role in ("propensity", "reward"):
        datasets = []
        for split in ("train", "val"):
            if role == "propensity":
                x = behavior_features(data[split]["vectors"])
                y = action_indices(meta[split])
            else:
                valid = meta[split]["run_cost"].notna().to_numpy()
                x = data[split]["vectors"][valid]
                y = meta[split].loc[valid, "run_cost"].to_numpy()
            datasets.append(lgb.Dataset(x, label=y, reference=datasets[0] if datasets else None))
        objective = (
            {"objective": "multiclass", "num_class": 17, "metric": "multi_logloss"}
            if role == "propensity"
            else {"objective": "regression", "metric": "l2"}
        )
        print("Training", role, flush=True)
        model = lgb.train(
            {**params, **objective},
            datasets[0],
            num_boost_round=500,
            valid_sets=[datasets[1]],
            callbacks=[lgb.early_stopping(30), lgb.log_evaluation(100)],
        )
        model.save_model(str(args.output_dir / f"{role}.txt"))
        manifest[role] = {
            "best_iteration": model.best_iteration,
            "validation_score": model.best_score["valid_0"],
        }
        if role == "propensity":
            p = model.predict(behavior_features(data["cal"]["vectors"]))
            y = action_indices(meta["cal"])
            temperature = fit_temperature(p, y)
            calibrated = temperature_scale(p, temperature)
            manifest[role].update(
                temperature=temperature,
                calibration_ce=float(-np.log(calibrated[np.arange(len(y)), y]).mean()),
            )
    manifest["status"] = "complete"
    (args.output_dir / "manifest.json").write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest, indent=2), flush=True)


if __name__ == "__main__":
    main()

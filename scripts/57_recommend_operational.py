"""Run a saved operational policy on a JSON pre-pitch state using the verified shared builder."""

import argparse
import json
import pickle
import sys
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.features import PITCH_TYPES
from src.data.operational import ACTION_TYPES, state_codes
from src.data.point_data import CLASS_NAMES
from src.evaluation.operational_metrics import temperature_scale
from src.evaluation.policy_value import behavior_features, soft_greedy
from src.inference.operational import OperationalPredictor
from src.utils.experiment_paths import resolve_selected_runs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--evaluation-dir", type=Path, required=True)
    parser.add_argument("--nuisance-dir", type=Path, required=True)
    parser.add_argument("--state-json", type=Path, required=True)
    parser.add_argument("--runs-dir", type=Path, help="Override model root after moving artifacts")
    args = parser.parse_args()
    torch.set_num_threads(1)
    report = json.loads((args.evaluation_dir / "probability_report.json").read_text())
    selected = report["selection"]["selected"]
    model = OperationalPredictor(
        args.data_dir,
        resolve_selected_runs(report["selection"], args.evaluation_dir, args.runs_dir),
        report["models"][selected]["temperature"],
        threads=1,
    )
    with open(args.evaluation_dir / "empirical.pkl", "rb") as handle:
        empirical = pickle.load(handle)
    state = json.loads(args.state_json.read_text(encoding="utf-8"))
    frame = pd.DataFrame([state])
    # Chosen action affects only the action-conditioned block, which is removed below.
    x = model.builder.build(frame, action="FF")
    nuisance = json.loads((args.nuisance_dir / "manifest.json").read_text())
    if nuisance["status"] != "complete" or nuisance["dataset"] != report["dataset"]:
        raise ValueError("Incompatible nuisance model")
    behavior = lgb.Booster(model_file=str(args.nuisance_dir / "propensity.txt"))
    prop = temperature_scale(
        behavior.predict(behavior_features(x), num_threads=1), nuisance["propensity"]["temperature"]
    )
    support = model.builder.available_actions(frame) & (
        prop[:, [PITCH_TYPES.index(a) for a in ACTION_TYPES]] >= 0.02
    )
    if support.sum() < 2:
        print(
            json.dumps(
                {"recommendation": None, "reason": "Insufficient historically supported actions"}
            )
        )
        return
    kernel = np.load(args.data_dir / "run_value_model.npz")["outcome_costs"][state_codes(frame)]
    costs, empirical_costs, probabilities = [], [], []
    for action in ACTION_TYPES:
        p = model.predict(frame, action)
        probabilities.append(p[0])
        costs.append(float((p * kernel).sum()))
        baseline = temperature_scale(
            empirical.predict(frame, action), report["models"]["empirical"]["temperature"]
        )
        empirical_costs.append(float((baseline * kernel).sum()))
    policy, choice = soft_greedy(np.array([costs]), support)
    _, empirical_choice = soft_greedy(np.array([empirical_costs]), support)
    print(
        json.dumps(
            {
                "selected_model": selected,
                "schema": model.builder.schema,
                "recommendation": ACTION_TYPES[choice[0]],
                "empirical_recommendation": ACTION_TYPES[empirical_choice[0]],
                "scope": "One-step predicted run-expectancy cost; observational validation only",
                "candidates": [
                    {
                        "action": action,
                        "supported": bool(support[0, i]),
                        "policy_probability": float(policy[0, i]),
                        "expected_cost": costs[i],
                        "probabilities": dict(
                            zip(CLASS_NAMES, probabilities[i].tolist(), strict=True)
                        ),
                    }
                    for i, action in enumerate(ACTION_TYPES)
                ],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

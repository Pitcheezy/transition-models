"""Compare frozen empirical and learned pitch-type policies on held-out logged outcomes."""

import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import lightgbm as lgb
import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.features import PITCH_TYPES
from src.data.operational import ACTION_TYPES, state_codes
from src.data.point_data import PITCH_KEYS, identity_hash, load_point_data
from src.evaluation.operational_metrics import game_interval, temperature_scale
from src.evaluation.policy_value import behavior_features, dr_scores, soft_greedy
from src.inference.operational import OperationalPredictor, action_indices
from src.utils.experiment_paths import resolve_selected_runs


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--evaluation-dir", type=Path, required=True)
    parser.add_argument("--nuisance-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--threads", type=int, default=3)
    parser.add_argument("--runs-dir", type=Path, help="Override model root after moving artifacts")
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    torch.set_num_threads(args.threads)
    probability = json.loads((args.evaluation_dir / "probability_report.json").read_text())
    selection = probability["selection"]
    name = selection["selected"]
    temperature = probability["models"][name]["temperature"]
    predictor = OperationalPredictor(
        args.data_dir,
        resolve_selected_runs(selection, args.evaluation_dir, args.runs_dir),
        temperature,
        threads=args.threads,
    )
    with open(args.evaluation_dir / "empirical.pkl", "rb") as handle:
        empirical = pickle.load(handle)
    empirical_temperature = probability["models"]["empirical"]["temperature"]
    nuisance = json.loads((args.nuisance_dir / "manifest.json").read_text())
    if nuisance["status"] != "complete" or nuisance["dataset"] != probability["dataset"]:
        raise ValueError("Nuisance dataset mismatch or incomplete training")
    behavior = lgb.Booster(model_file=str(args.nuisance_dir / "propensity.txt"))
    reward = lgb.Booster(model_file=str(args.nuisance_dir / "reward.txt"))
    data = load_point_data(args.data_dir, "test", input_dim=135)
    frame = pd.read_parquet(args.data_dir / "metadata_test.parquet")
    if not np.array_equal(data["pitch_ids"], frame[PITCH_KEYS].to_numpy()):
        raise ValueError("Policy metadata identity mismatch")
    # Verify online features against saved training/evaluation construction.
    check_rows = np.linspace(0, len(frame) - 1, 1000, dtype=int)
    np.testing.assert_array_equal(
        predictor.builder.build(frame.iloc[check_rows]), data["vectors"][check_rows]
    )
    propensities = temperature_scale(
        behavior.predict(behavior_features(data["vectors"]), num_threads=args.threads),
        nuisance["propensity"]["temperature"],
    )
    action_map = np.array([PITCH_TYPES.index(a) for a in ACTION_TYPES])
    available = predictor.builder.available_actions(frame) & (propensities[:, action_map] >= 0.02)
    eligible = frame["run_cost"].notna().to_numpy() & (available.sum(axis=1) >= 2)
    report = {
        "scope": "one pitch intervention, innings 1-8, observational continuation",
        "selected_model": name,
        "policy": "90% minimum expected cost + 10% uniform support",
        "support": "2022 pitch count >=30 and propensity >=0.02, at least 2 actions",
        "all_test_n": len(frame),
        "observed_cost_n": int(frame["run_cost"].notna().sum()),
        "eligible_n": int(eligible.sum()),
        "eligible_fraction": float(eligible.mean()),
        "online_feature_exact_match_n": len(check_rows),
        "estimators": {},
        "limitations": [
            "Conditional exchangeability is unverified; omitted batter ability, intent and game context may confound.",
            "One-step run-expectancy cost, not a season-level causal run saving.",
            "Uncertainty intervals resample games conditional on fitted policies/nuisance models.",
            "Completed 1-8 innings and overlap restriction limit generalization.",
        ],
    }
    frame = frame.loc[eligible].reset_index(drop=True)
    available, propensities = available[eligible], propensities[eligible]
    ids = data["pitch_ids"][eligible]
    report["eligible_pitch_ids_sha256"] = identity_hash(ids)
    state = state_codes(frame)
    kernel = np.load(args.data_dir / "run_value_model.npz")["outcome_costs"]
    empirical_cost, learned_cost, nuisance_q = [], [], []
    action_probabilities = []
    started = time.perf_counter()
    for action in ACTION_TYPES:
        x = predictor.builder.build(frame, action=action)
        learned_p = predictor.predict_vectors(x)
        empirical_p = temperature_scale(empirical.predict(frame, action), empirical_temperature)
        learned_cost.append((learned_p * kernel[state]).sum(axis=1))
        empirical_cost.append((empirical_p * kernel[state]).sum(axis=1))
        nuisance_q.append(reward.predict(x, num_threads=args.threads))
        action_probabilities.append(learned_p.astype(np.float32))
        print("Evaluated counterfactual action", action, flush=True)
    report["batch_counterfactual_seconds"] = time.perf_counter() - started
    costs = {"empirical": np.column_stack(empirical_cost), "learned": np.column_stack(learned_cost)}
    nuisance_q = np.column_stack(nuisance_q)
    policies, choices = {}, {}
    for label in costs:
        policies[label], choices[label] = soft_greedy(costs[label], available)
    report["recommendation_change_fraction"] = float(
        (choices["empirical"] != choices["learned"]).mean()
    )
    report["recommendation_distribution"] = {
        label: dict(
            zip(
                ACTION_TYPES, np.bincount(choice, minlength=len(ACTION_TYPES)).tolist(), strict=True
            )
        )
        for label, choice in choices.items()
    }
    logged = action_indices(frame)
    observed_action = np.array(
        [{a: i for i, a in enumerate(ACTION_TYPES)}.get(a, -1) for a in frame["pitch_type"]]
    )
    e_logged = propensities[np.arange(len(frame)), logged]
    actual_cost = frame["run_cost"].to_numpy()
    report["overlap"] = {
        "mean_propensity_mass_on_supported_actions": float(
            (propensities[:, action_map] * available).sum(1).mean()
        ),
        "mean_candidate_count": float(available.sum(1).mean()),
        "logged_action_outside_candidates_fraction": float(
            np.mean([a < 0 or not available[i, a] for i, a in enumerate(observed_action)])
        ),
        "propensity_test_ce_eligible": float(-np.log(e_logged).mean()),
    }
    all_scores = {}
    for clip in (None, 5, 10, 20):
        scores, diagnostics = {}, {}
        for label in policies:
            scores[label], diagnostics[label] = dr_scores(
                policies[label], nuisance_q, observed_action, e_logged, actual_cost, clip
            )
        delta = scores["learned"] - scores["empirical"]
        interval = game_interval(
            np.column_stack([scores["empirical"], scores["learned"], delta]) * 100, ids[:, 0]
        )
        key = "unclipped" if clip is None else f"clip_{clip}"
        report["estimators"][key] = {
            "metric_order": ["empirical_cost", "learned_cost", "learned_minus_empirical"],
            "units": "runs per 100 pitch decisions",
            "dr": interval,
            "diagnostics": diagnostics,
        }
        all_scores[key] = np.column_stack([scores["empirical"], scores["learned"]])
    report["improvement_supported_under_assumptions"] = bool(
        report["estimators"]["unclipped"]["dr"]["ci95"][2][1] < 0
    )
    # Latency includes the same builder and all nine action predictions, with warmed CPU models.
    sample = frame.iloc[[0]]
    for action in ACTION_TYPES:
        predictor.predict(sample, action)
    timings = []
    for _ in range(30):
        start = time.perf_counter()
        for action in ACTION_TYPES:
            predictor.predict(sample, action)
        timings.append((time.perf_counter() - start) * 1000)
    report["latency"] = {
        "device": "CPU",
        "threads": args.threads,
        "repetitions": 30,
        "scope": "shared feature builder plus learned prediction for nine candidate actions",
        "nine_actions_p50_ms": float(np.median(timings)),
        "nine_actions_p95_ms": float(np.quantile(timings, 0.95)),
        "concurrent_training_may_affect_measurement": True,
    }
    np.savez_compressed(
        args.output_dir / "policy_predictions.npz",
        pitch_ids=ids,
        available=available,
        empirical_cost=costs["empirical"],
        learned_cost=costs["learned"],
        nuisance_q=nuisance_q,
        propensity=propensities,
        actual_cost=actual_cost,
        empirical_choice=choices["empirical"],
        learned_choice=choices["learned"],
        probabilities=np.stack(action_probabilities, axis=1),
        **{f"dr_{key}": value for key, value in all_scores.items()},
    )
    # The first eligible states are fixed-order examples, not selected for favorable results.
    examples = []
    for i in range(min(30, len(frame))):
        values = frame.iloc[i].to_dict()
        values = {
            key: None
            if pd.isna(value)
            else str(value)
            if isinstance(value, pd.Timestamp)
            else value
            for key, value in values.items()
        }
        examples.append(
            {
                "state": values,
                "available": available[i].tolist(),
                "empirical_cost": costs["empirical"][i].tolist(),
                "learned_cost": costs["learned"][i].tolist(),
                "probabilities": np.stack(action_probabilities, axis=1)[i].tolist(),
                "empirical_choice": ACTION_TYPES[choices["empirical"][i]],
                "learned_choice": ACTION_TYPES[choices["learned"][i]],
            }
        )
    (args.output_dir / "demo_examples.json").write_text(
        json.dumps({"actions": ACTION_TYPES, "examples": examples}, indent=2)
    )
    (args.output_dir / "policy_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()

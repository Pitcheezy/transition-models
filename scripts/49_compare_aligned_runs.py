"""Compare completed runs on identical pitches, with validation-only temperature fitting."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.optimize import minimize_scalar
from scipy.special import logsumexp

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.point_data import CLASS_NAMES, identity_hash, load_point_data
from src.evaluation.point_metrics import align_predictions, probability_metrics


def temperature_scale(probs, temperature):
    """Rescale stored softmax probabilities in log space."""
    logits = np.log(np.clip(probs.astype(np.float64), 1e-12, 1)) / temperature
    return np.exp(logits - logsumexp(logits, axis=1, keepdims=True))


def fit_temperature(probs, targets):
    """Fit one scalar on validation data only."""
    logits = np.log(np.clip(probs.astype(np.float64), 1e-12, 1))

    def objective(log_temperature):
        scaled = logits / np.exp(log_temperature)
        return float((logsumexp(scaled, axis=1) - scaled[np.arange(len(targets)), targets]).mean())

    result = minimize_scalar(objective, bounds=(-2.3, 2.3), method="bounded")
    if not result.success:
        raise RuntimeError("Temperature fit failed")
    return float(np.exp(result.x))


def paired_game_bootstrap(reference, candidate_probs, repetitions=2000):
    """Bootstrap games as clusters; positive CE delta means the candidate is worse."""
    y = reference["targets"]
    reference_probs = reference["probs"]
    _, groups = np.unique(reference["pitch_ids"][:, 0], return_inverse=True)
    ce_delta = np.log(np.clip(reference_probs[np.arange(len(y)), y], 1e-12, 1)) - np.log(
        np.clip(candidate_probs[np.arange(len(y)), y], 1e-12, 1)
    )
    acc_delta = (candidate_probs.argmax(1) == y).astype(float) - (reference_probs.argmax(1) == y)
    counts = np.bincount(groups)
    sums = np.column_stack(
        [np.bincount(groups, weights=ce_delta), np.bincount(groups, weights=acc_delta)]
    )
    rng = np.random.default_rng(42)
    estimates = []
    for _ in range(repetitions):
        selected = rng.integers(0, len(counts), len(counts))
        estimates.append(sums[selected].sum(axis=0) / counts[selected].sum())
    intervals = np.quantile(estimates, [0.025, 0.975], axis=0)
    return {
        "games": len(counts),
        "repetitions": repetitions,
        "ce_delta": float(ce_delta.mean()),
        "ce_delta_95ci": intervals[:, 0].tolist(),
        "accuracy_delta": float(acc_delta.mean()),
        "accuracy_delta_95ci": intervals[:, 1].tolist(),
        "scope": "test-game sampling uncertainty; excludes training-seed uncertainty",
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--runs", nargs="+", type=Path, required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    report = {
        "scope": "Retrospective observed-pitch classification, not policy value",
        "calibration": "Scalar temperature fitted on validation (also used for early stopping); "
        "no test fitting. Independent calibration holdout remains future work.",
        "runs": {},
        "paired_differences_vs_first_run": {},
    }
    reference = None
    reference_val = None
    canonical = {}
    for split in ("val", "test"):
        point = load_point_data(args.data_dir, split)
        canonical[split] = (pd.MultiIndex.from_arrays(point["pitch_ids"].T), point["labels"])
        del point
    for path in args.runs:
        manifest = json.loads((path / "manifest.json").read_text())
        if manifest["status"] != "complete":
            raise ValueError(f"Incomplete run: {path}")
        with np.load(path / "predictions_test.npz") as file:
            test = dict(file)
        with np.load(path / "predictions_val.npz") as file:
            val = dict(file)
        for split, predictions in (("test", test), ("val", val)):
            truth_index, truth_labels = canonical[split]
            order = truth_index.get_indexer(pd.MultiIndex.from_arrays(predictions["pitch_ids"].T))
            if (
                len(order) != len(truth_labels)
                or np.any(order < 0)
                or not np.array_equal(predictions["targets"], truth_labels[order])
            ):
                raise ValueError(f"Predictions disagree with canonical {split} data: {path}")
        if reference is None:
            reference, reference_val = test, val
        aligned = align_predictions(reference, test)
        align_predictions(reference_val, val)
        temperature = fit_temperature(val["probs"], val["targets"])
        report["runs"][path.name] = {
            "manifest": manifest,
            "raw": probability_metrics(test["probs"], test["targets"]),
            "temperature": temperature,
            "temperature_scaled": probability_metrics(
                temperature_scale(test["probs"], temperature), test["targets"]
            ),
        }
        report["paired_differences_vs_first_run"][path.name] = paired_game_bootstrap(
            reference, aligned
        )
        print(path.name, report["runs"][path.name]["raw"]["top1"], temperature, flush=True)
    train_y = load_point_data(args.data_dir, "train")["labels"]
    prior = (np.bincount(train_y[train_y >= 0], minlength=10) + 1).astype(float)
    prior /= prior.sum()
    report["empirical_train_prior"] = probability_metrics(
        np.broadcast_to(prior, (len(reference["targets"]), 10)), reference["targets"]
    )
    report["test_pitch_ids_sha256"] = identity_hash(reference["pitch_ids"])
    report["class_names"] = CLASS_NAMES.tolist()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

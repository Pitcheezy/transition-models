"""Select on validation, calibrate on June, then audit held-out probabilities by identity."""

import argparse
import json
import os
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.operational import state_codes
from src.data.point_data import CLASS_NAMES, PITCH_KEYS, identity_hash
from src.evaluation.operational_metrics import (
    fit_temperature,
    game_interval,
    reliability_bins,
    score_rows,
    seed_game_interval,
    temperature_scale,
)
from src.evaluation.point_metrics import probability_metrics
from src.inference.operational import EmpiricalTransition


def canonical(directory, split):
    with np.load(directory / f"point_{split}.npz") as file:
        return file["pitch_ids"], file["labels_10"]


def verified_prediction(path, split, ids, y):
    with np.load(path / f"predictions_{split}.npz") as file:
        if (
            not np.array_equal(file["pitch_ids"], ids)
            or not np.array_equal(file["targets"], y)
            or not np.array_equal(file["class_names"], CLASS_NAMES)
        ):
            raise ValueError(f"Prediction identity/target/class mismatch: {path}/{split}")
        return file["probs"]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--runs-dir", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--observed-runs", type=Path)
    parser.add_argument("--observed-data", type=Path)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    groups = {
        f"mlp{dim}": [args.runs_dir / f"mlp{dim}_seed{seed}" for seed in (42, 43, 44)]
        for dim in (77, 135)
    }
    groups.update(
        {name: [args.runs_dir / f"{name}_seed42"] for name in ("lr77", "lgb77", "lgb135")}
    )
    for paths in groups.values():
        for path in paths:
            if json.loads((path / "manifest.json").read_text())["status"] != "complete":
                raise ValueError(f"Incomplete run {path}")
    _, train_y = canonical(args.data_dir, "train")
    train_frame = pd.read_parquet(args.data_dir / "metadata_train.parquet")
    empirical = EmpiricalTransition().fit(train_frame, train_y)
    with open(args.output_dir / "empirical.pkl", "wb") as handle:
        pickle.dump(empirical, handle)
    del train_frame, train_y
    val_ids, val_y = canonical(args.data_dir, "val")
    validation = {}
    for name, paths in groups.items():
        p = np.mean([verified_prediction(path, "val", val_ids, val_y) for path in paths], axis=0)
        validation[name] = probability_metrics(p, val_y)
    selected = min(validation, key=lambda name: validation[name]["ce"])
    selection = {
        "selected": selected,
        "criterion": "minimum uncalibrated validation CE",
        "selection_period": "2024 Jan-May",
        "calibration_period": "2024 June",
        "groups": {name: [str(p) for p in paths] for name, paths in groups.items()},
        "run_names": {name: [p.name for p in paths] for name, paths in groups.items()},
        "runs_root_relative": Path(
            os.path.relpath(args.runs_dir.resolve(), args.output_dir.resolve())
        ).as_posix(),
        "validation_ce": {name: row["ce"] for name, row in validation.items()},
    }
    (args.output_dir / "selection.json").write_text(json.dumps(selection, indent=2))
    print("Frozen selection before test metrics:", json.dumps(selection), flush=True)
    cal_ids, cal_y = canonical(args.data_dir, "cal")
    test_ids, test_y = canonical(args.data_dir, "test")
    cal_frame = pd.read_parquet(args.data_dir / "metadata_cal.parquet")
    test_frame = pd.read_parquet(args.data_dir / "metadata_test.parquet")
    if not np.array_equal(test_ids, test_frame[PITCH_KEYS].to_numpy()):
        raise ValueError("Metadata ID mismatch")
    report = {
        "selection": selection,
        "dataset": json.loads((args.data_dir / "dataset_manifest.json").read_text()),
        "models": {},
        "situations": {},
        "paired_differences": {},
        "training_seeds": {},
    }
    scaled = {}
    for name in [*groups, "empirical"]:
        if name == "empirical":
            cal = empirical.predict(cal_frame)
            test = empirical.predict(test_frame)
        else:
            cal = np.mean(
                [verified_prediction(path, "cal", cal_ids, cal_y) for path in groups[name]], axis=0
            )
            test = np.mean(
                [verified_prediction(path, "test", test_ids, test_y) for path in groups[name]],
                axis=0,
            )
        temperature = fit_temperature(cal, cal_y)
        p = temperature_scale(test, temperature)
        scaled[name] = p
        report["models"][name] = {
            "temperature": temperature,
            "raw_test": probability_metrics(test, test_y),
            "calibrated_test": probability_metrics(p, test_y),
            "scores_ci95": game_interval(score_rows(p, test_y), test_ids[:, 0]),
            "class_calibration_residual_ci95": game_interval(
                p - np.eye(10)[test_y], test_ids[:, 0]
            ),
            "class_reliability": {
                str(c): reliability_bins(p[:, i], test_y == i) for i, c in enumerate(CLASS_NAMES)
            },
        }
        np.savez_compressed(
            args.output_dir / f"{name}_test.npz",
            probs=p,
            targets=test_y,
            pitch_ids=test_ids,
            class_names=CLASS_NAMES,
        )
        print(
            name,
            "T",
            temperature,
            "CE",
            report["models"][name]["calibrated_test"]["ce"],
            flush=True,
        )
    for name in groups:
        report["paired_differences"][f"{name}_minus_empirical"] = game_interval(
            score_rows(scaled[name], test_y) - score_rows(scaled["empirical"], test_y),
            test_ids[:, 0],
        )
    report["paired_differences"]["mlp135_minus_mlp77"] = game_interval(
        score_rows(scaled["mlp135"], test_y) - score_rows(scaled["mlp77"], test_y), test_ids[:, 0]
    )
    states = state_codes(test_frame)
    strata = {
        "count": states % 12,
        "base_out": states // 12,
        "pitch_type": test_frame["pitch_type"].to_numpy(),
        "hands": (test_frame["stand"] + test_frame["p_throws"]).to_numpy(),
    }
    for category, values in strata.items():
        report["situations"][category] = {}
        for value in np.unique(values):
            mask = values == value
            if mask.sum() < 100:
                continue
            row = {"n": int(mask.sum()), "models": {}}
            for name in (selected, "empirical"):
                p, y = scaled[name][mask], test_y[mask]
                metrics = probability_metrics(p, y)
                row["models"][name] = {
                    key: metrics[key] for key in ("ce", "brier", "ece_15", "per_class")
                }
                row["models"][name]["rare_event_residual_ci95"] = game_interval(
                    p[:, 2:6] - np.eye(10)[y][:, 2:6], test_ids[mask, 0], repetitions=500
                )
            report["situations"][category][str(value)] = row
    seed_scores = {}
    for dim in (77, 135):
        rows, scores = [], []
        for seed in (42, 43, 44):
            path = args.runs_dir / f"mlp{dim}_seed{seed}"
            p = verified_prediction(path, "test", test_ids, test_y)
            rows.append(
                {
                    "seed": seed,
                    **dict(
                        zip(
                            ("ce", "brier"),
                            score_rows(p, test_y).mean(axis=0).tolist(),
                            strict=True,
                        )
                    ),
                }
            )
            scores.append(score_rows(p, test_y))
        report["training_seeds"][f"mlp{dim}"] = rows
        seed_scores[dim] = np.array(scores)
    report["training_seeds"]["raw_135_minus_77_seed_game_ci"] = seed_game_interval(
        seed_scores[135] - seed_scores[77], test_ids[:, 0]
    )
    if args.observed_runs and args.observed_data:
        ids, y = canonical(args.observed_data, "test")
        observed, scores = {}, {}
        for dim in (77, 135):
            observed[str(dim)] = []
            scores[dim] = []
            for seed in (42, 43, 44):
                path = args.observed_runs / f"mlp{dim}_ce_seed{seed}"
                p = verified_prediction(path, "test", ids, y)
                values = score_rows(p, y)
                observed[str(dim)].append(
                    {
                        "seed": seed,
                        "ce": float(values[:, 0].mean()),
                        "brier": float(values[:, 1].mean()),
                        "top1": float((p.argmax(1) == y).mean()),
                    }
                )
                scores[dim].append(values)
        observed["raw_135_minus_77_seed_game_ci"] = seed_game_interval(
            np.array(scores[135]) - np.array(scores[77]), ids[:, 0]
        )
        report["observed_features_repeat_experiment"] = observed
    report["test_pitch_ids_sha256"] = identity_hash(test_ids)
    report["class_order"] = CLASS_NAMES.tolist()
    (args.output_dir / "probability_report.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()

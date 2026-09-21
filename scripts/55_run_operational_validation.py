"""Reproduce the complete operational experiment in fresh directories on Windows/Mac/Linux."""

import argparse
import json
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.utils.pipeline import prepare_stage


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--device", default="auto", choices=["auto", "cpu", "cuda", "mps"])
    parser.add_argument("--threads", type=int, default=4)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip completed stages and preserve/restart interrupted stages",
    )
    args = parser.parse_args()
    args.data_dir = args.data_dir.resolve()
    args.run_dir = args.run_dir.resolve()
    args.raw_dir = args.raw_dir.resolve()
    if not args.resume and (args.data_dir.exists() or args.run_dir.exists()):
        parser.error(
            "Choose fresh data/run directories; completed experiments are never overwritten"
        )
    root = Path(__file__).resolve().parents[1]
    if (
        args.data_dir == args.run_dir
        or args.data_dir in args.run_dir.parents
        or args.run_dir in args.data_dir.parents
    ):
        parser.error("Data and run directories must be separate, not nested")
    if args.threads < 1:
        parser.error("threads must be positive")

    def run(*command):
        print("Running:", " ".join(map(str, command)), flush=True)
        subprocess.run([sys.executable, *map(str, command)], cwd=root, check=True)

    def stage(output, marker_name, command, required=(), expected=None, force=False):
        execute = prepare_stage(
            output,
            output / marker_name,
            required,
            resume=args.resume,
            expected=expected,
            force=force,
        )
        if execute:
            run(*command)
        if not (output / marker_name).is_file():
            raise RuntimeError(f"Stage did not produce its completion marker: {output}")
        return execute

    data_changed = stage(
        args.data_dir,
        "dataset_manifest.json",
        (
            "scripts/51_prepare_operational.py",
            "--raw-dir",
            args.raw_dir,
            "--output-dir",
            args.data_dir,
        ),
        required=(
            "feature_builder.pkl",
            "run_value_model.npz",
            *(f"point_{s}.npz" for s in ("train", "val", "cal", "test")),
            *(f"metadata_{s}.parquet" for s in ("train", "val", "cal", "test")),
        ),
    )
    dataset = json.loads((args.data_dir / "dataset_manifest.json").read_text())
    models_changed = False
    for kind, dim, seed in [
        *(("mlp", dim, seed) for dim in (77, 135) for seed in (42, 43, 44)),
        ("lr", 77, 42),
        ("lgb", 77, 42),
        ("lgb", 135, 42),
    ]:
        directory = args.run_dir / f"{kind}{dim}_seed{seed}"
        checkpoint = {"mlp": "best.pt", "lr": "model.pkl", "lgb": "model.txt"}[kind]
        trained = stage(
            directory,
            "manifest.json",
            (
                "-m",
                "src.training.point_baselines",
                "--model",
                kind,
                "--input-dim",
                dim,
                "--seed",
                seed,
                "--data-dir",
                args.data_dir,
                "--run-dir",
                directory,
                "--device",
                args.device,
                "--threads",
                args.threads,
                "--max-iter",
                1000,
                "--eval-splits",
                "val",
                "cal",
                "test",
            ),
            required=(
                checkpoint,
                "metrics.json",
                *(f"predictions_{s}.npz" for s in ("val", "cal", "test")),
            ),
            expected={
                "model": kind,
                "input_dim": dim,
                "seed": seed,
                "dataset": dataset,
                "loss": "ce",
                "class_weight": "none",
                "max_train": 0,
            },
            force=data_changed,
        )
        models_changed |= trained
    nuisance_changed = stage(
        args.run_dir / "policy_nuisance",
        "manifest.json",
        (
            "scripts/52_train_policy_nuisance.py",
            "--data-dir",
            args.data_dir,
            "--output-dir",
            args.run_dir / "policy_nuisance",
            "--threads",
            args.threads,
        ),
        required=("propensity.txt", "reward.txt"),
        expected={"dataset": dataset, "propensity_features": 89, "reward_features": 135},
        force=data_changed,
    )
    evaluation_changed = stage(
        args.run_dir / "evaluation",
        "probability_report.json",
        (
            "scripts/53_evaluate_operational.py",
            "--data-dir",
            args.data_dir,
            "--runs-dir",
            args.run_dir,
            "--output-dir",
            args.run_dir / "evaluation",
        ),
        required=("selection.json", "empirical.pkl"),
        expected={"dataset": dataset},
        force=models_changed,
    )
    policy_changed = stage(
        args.run_dir / "policy",
        "policy_report.json",
        (
            "scripts/54_evaluate_policy.py",
            "--data-dir",
            args.data_dir,
            "--evaluation-dir",
            args.run_dir / "evaluation",
            "--nuisance-dir",
            args.run_dir / "policy_nuisance",
            "--output-dir",
            args.run_dir / "policy",
            "--threads",
            args.threads,
        ),
        required=("policy_predictions.npz", "demo_examples.json"),
        force=evaluation_changed or nuisance_changed,
    )
    # The demo is cheap and independent of training; regenerate only when missing.
    if not prepare_stage(
        args.run_dir / "demo.html",
        args.run_dir / "demo.html",
        resume=args.resume,
        force=policy_changed,
    ):
        return
    run(
        "scripts/56_build_validation_demo.py",
        "--evaluation-dir",
        args.run_dir / "evaluation",
        "--policy-dir",
        args.run_dir / "policy",
        "--output",
        args.run_dir / "demo.html",
    )


if __name__ == "__main__":
    main()

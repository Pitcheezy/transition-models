"""Reproducible point baselines with aligned targets and isolated run directories."""

import argparse
import hashlib
import json
import math
import os
import pickle
import random
import subprocess
import time
import warnings
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from sklearn.exceptions import ConvergenceWarning
from sklearn.linear_model import LogisticRegression
from threadpoolctl import threadpool_limits

from src.data.point_data import CLASS_NAMES, identity_hash, load_point_data, validate_split_ids
from src.evaluation.point_metrics import probability_metrics
from src.models.otremba_mlp import OtrembaMLP
from src.utils.device import get_device
from src.utils.model_prediction import predict_mlp


def fit_mlp(data, args, manifest):
    """Train with fixed seeds, sample-weighted validation, and best checkpoint restore."""
    device = get_device() if args.device == "auto" else torch.device(args.device)
    model = OtrembaMLP(args.input_dim, 128, 10, dropout=0.2).to(device)
    x = torch.as_tensor(data["train"]["vectors"], device=device)
    y = torch.as_tensor(data["train"]["labels"], device=device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3, weight_decay=1e-5)
    scheduler = torch.optim.lr_scheduler.CosineAnnealingLR(
        optimizer, T_max=math.ceil(len(x) / args.batch_size) * args.epochs
    )
    generator_device = device if device.type != "mps" else torch.device("cpu")
    generator = torch.Generator(device=generator_device).manual_seed(args.seed)
    best, patience = float("inf"), 0
    history = []
    manifest.update(device=str(device), parameters=sum(p.numel() for p in model.parameters()))
    for epoch in range(1, args.epochs + 1):
        started = time.perf_counter()
        model.train()
        order = torch.randperm(len(x), generator=generator, device=generator_device).to(device)
        total_loss = torch.zeros((), device=device)
        for indices in order.split(args.batch_size):
            optimizer.zero_grad(set_to_none=True)
            logits = model(x[indices])
            losses = F.cross_entropy(logits, y[indices], reduction="none")
            if args.loss == "focal":
                losses = (1 - torch.exp(-losses)) ** 2 * losses
            loss = losses.mean()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
            optimizer.step()
            scheduler.step()
            total_loss += loss.detach() * len(indices)
        probs = predict_mlp(model, data["val"]["vectors"], device)
        p_true = probs[np.arange(len(probs)), data["val"]["labels"]].astype(np.float64)
        losses = -np.log(np.clip(p_true, 1e-12, 1))
        if args.loss == "focal":
            losses *= (1 - p_true) ** 2
        val_loss = float(losses.mean())
        row = {
            "epoch": epoch,
            "train_loss": float(total_loss / len(x)),
            "val_loss": val_loss,
            "seconds": time.perf_counter() - started,
        }
        history.append(row)
        print(json.dumps(row), flush=True)
        if not np.isfinite(val_loss):
            raise ValueError("Nonfinite validation loss")
        state = {
            "epoch": epoch,
            "model_state": model.state_dict(),
            "optimizer_state": optimizer.state_dict(),
            "scheduler_state": scheduler.state_dict(),
            "val_metrics": {"loss": val_loss},
            "metadata": manifest,
        }
        torch.save(state, args.run_dir / "last.pt")
        if val_loss < best:
            best, patience = val_loss, 0
            torch.save(state, args.run_dir / "best.pt")
        else:
            patience += 1
        (args.run_dir / "history.json").write_text(json.dumps(history, indent=2))
        if patience >= 5:
            break
    state = torch.load(args.run_dir / "best.pt", weights_only=False, map_location=device)
    model.load_state_dict(state["model_state"])
    manifest.update(best_epoch=state["epoch"], epochs_completed=epoch, best_val_loss=best)
    return lambda features: predict_mlp(model, features, device)


def main(model_kind: str | None = None):
    parser = argparse.ArgumentParser(description=__doc__)
    if model_kind is None:
        parser.add_argument("--model", choices=["lr", "lgb", "mlp"], required=True)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--input-dim", type=int, choices=[77, 135, 151], default=77)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--threads", type=int, default=6)
    parser.add_argument("--loss", choices=["ce", "focal"], default="ce")
    parser.add_argument(
        "--class-weight", choices=["none", "sqrt-balanced", "balanced"], default="none"
    )
    parser.add_argument("--epochs", type=int, default=30)
    parser.add_argument("--batch-size", type=int, default=256)
    parser.add_argument(
        "--max-train", type=int, default=0, help="0 uses all rows; subsampling is explicit"
    )
    parser.add_argument("--max-iter", type=int, default=500)
    parser.add_argument("--rounds", type=int, default=1000)
    parser.add_argument("--device", choices=["auto", "cpu", "cuda", "mps"], default="auto")
    parser.add_argument(
        "--eval-splits", nargs="+", choices=["val", "cal", "test"], default=["val", "test"]
    )
    args = parser.parse_args()
    args.model = model_kind or args.model
    if args.loss != "ce" and args.model != "mlp":
        parser.error("Focal loss is supported only for MLP")
    if args.class_weight != "none" and args.model == "mlp":
        parser.error("MLP class weighting is not implemented; choose CE or focal loss")
    if (
        min(args.threads, args.epochs, args.batch_size, args.max_iter, args.rounds) < 1
        or args.max_train < 0
    ):
        parser.error("Training limits must be positive (max-train may be zero)")
    args.run_dir.mkdir(parents=True, exist_ok=False)
    os.environ.setdefault("CUBLAS_WORKSPACE_CONFIG", ":4096:8")
    random.seed(args.seed)
    np.random.seed(args.seed)
    torch.manual_seed(args.seed)
    torch.set_num_threads(args.threads)
    torch.use_deterministic_algorithms(True)
    torch.backends.cudnn.benchmark = False
    data = {
        split: load_point_data(args.data_dir, split, args.input_dim)
        for split in dict.fromkeys(["train", "val", *args.eval_splits])
    }
    validate_split_ids(data)
    if args.max_train and len(data["train"]["labels"]) > args.max_train:
        indices = np.random.RandomState(args.seed).choice(
            len(data["train"]["labels"]), args.max_train, replace=False
        )
        data["train"] = {key: value[indices] for key, value in data["train"].items()}
    revision = subprocess.run(
        ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=False
    ).stdout.strip()
    manifest = {
        key: str(value) if isinstance(value, Path) else value for key, value in vars(args).items()
    }
    manifest.update(
        git_head=revision,
        torch_version=torch.__version__,
        numpy_version=np.__version__,
        class_names=CLASS_NAMES.tolist(),
        status="running",
        dataset=(
            json.loads((args.data_dir / "dataset_manifest.json").read_text())
            if (args.data_dir / "dataset_manifest.json").exists()
            else None
        ),
        source_sha256={
            str(path.relative_to(Path(__file__).resolve().parents[2])): hashlib.sha256(
                path.read_bytes()
            ).hexdigest()
            for path in (
                Path(__file__).resolve(),
                Path(__file__).resolve().parents[1] / "data/point_data.py",
                Path(__file__).resolve().parents[1] / "models/otremba_mlp.py",
            )
        },
        mlp_hyperparameters={
            "hidden_dim": 128,
            "dropout": 0.2,
            "lr": 0.001,
            "weight_decay": 0.00001,
            "gradient_clip_norm": 1.0,
            "early_stopping_patience": 5,
            "focal_gamma": 2.0,
        },
        splits={
            name: {"n": len(value["labels"]), "pitch_ids_sha256": identity_hash(value["pitch_ids"])}
            for name, value in data.items()
        },
    )
    manifest_path = args.run_dir / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    print(json.dumps(manifest), flush=True)
    started = time.perf_counter()
    x, y = data["train"]["vectors"], data["train"]["labels"]
    weights = len(y) / (10 * np.maximum(np.bincount(y, minlength=10), 1))
    if args.class_weight == "sqrt-balanced":
        weights = np.sqrt(weights)
    with threadpool_limits(limits=args.threads):
        if args.model == "mlp":
            predict = fit_mlp(data, args, manifest)
        elif args.model == "lr":
            model = LogisticRegression(
                max_iter=args.max_iter,
                random_state=args.seed,
                class_weight=None if args.class_weight == "none" else dict(enumerate(weights)),
            )
            with warnings.catch_warnings(record=True) as caught:
                warnings.simplefilter("always", ConvergenceWarning)
                model.fit(x, y)
            manifest.update(
                n_iter=model.n_iter_.tolist(), warnings=[str(w.message) for w in caught]
            )
            with open(args.run_dir / "model.pkl", "wb") as handle:
                pickle.dump(model, handle)

            def predict(features):
                result = np.zeros((len(features), 10), dtype=np.float32)
                result[:, model.classes_] = model.predict_proba(features)
                return result
        else:
            import lightgbm as lgb

            params = dict(
                objective="multiclass",
                num_class=10,
                metric="multi_logloss",
                learning_rate=0.05,
                num_leaves=63,
                max_depth=8,
                min_data_in_leaf=20,
                feature_fraction=0.8,
                bagging_fraction=0.8,
                bagging_freq=5,
                num_threads=args.threads,
                seed=args.seed,
                verbosity=-1,
                deterministic=True,
                force_col_wise=True,
            )
            train_set = lgb.Dataset(
                x, label=y, weight=None if args.class_weight == "none" else weights[y]
            )
            val_set = lgb.Dataset(
                data["val"]["vectors"], label=data["val"]["labels"], reference=train_set
            )
            model = lgb.train(
                params,
                train_set,
                num_boost_round=args.rounds,
                valid_sets=[val_set],
                callbacks=[lgb.early_stopping(20), lgb.log_evaluation(50)],
            )
            model.save_model(str(args.run_dir / "model.txt"))
            manifest.update(best_iteration=model.best_iteration, lightgbm_version=lgb.__version__)
            predict = model.predict
        manifest["training_seconds"] = time.perf_counter() - started
        metrics = {}
        for name in args.eval_splits:
            probs = np.asarray(predict(data[name]["vectors"]), dtype=np.float32)
            metrics[name] = probability_metrics(probs, data[name]["labels"])
            np.savez_compressed(
                args.run_dir / f"predictions_{name}.npz",
                probs=probs,
                targets=data[name]["labels"],
                pitch_ids=data[name]["pitch_ids"],
                class_names=CLASS_NAMES,
            )
    manifest["status"] = "complete"
    manifest_path.write_text(json.dumps(manifest, indent=2))
    (args.run_dir / "metrics.json").write_text(json.dumps(metrics, indent=2))
    print(
        json.dumps(
            {
                key: value
                for key, value in metrics[args.eval_splits[-1]].items()
                if key not in ("per_class", "confusion_matrix")
            }
        ),
        flush=True,
    )


if __name__ == "__main__":
    main()

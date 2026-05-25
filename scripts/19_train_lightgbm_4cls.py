"""Phase 9 - Model 2 (4-class): LightGBM

Single-pitch 77-dim input, 4-class output (Ball/Strike/Foul/InPlay).
1차 발표 LightGBM(58.7%)와 동일 설정으로 재현.
"""

import sys
import time
from pathlib import Path

import numpy as np
import torch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import lightgbm as lgb

from src.data.features import PitchResult4
from src.evaluation.metrics import cross_entropy, per_class_metrics, top_k_accuracy

DATA_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
CKPT_DIR = OUTPUT_DIR / "checkpoints"
CKPT_DIR.mkdir(parents=True, exist_ok=True)

CLASS_NAMES = [PitchResult4.NAMES[i] for i in range(PitchResult4.NUM_CLASSES)]


def load_point_data(split: str):
    """Load 77-dim vectors + 4-class labels from model_b_*.pt."""
    pt = torch.load(DATA_DIR / f"model_b_{split}.pt", weights_only=False)
    vectors = pt["vectors"]
    if isinstance(vectors, torch.Tensor):
        vectors = vectors.numpy()
    labels = pt["labels"]
    if isinstance(labels, torch.Tensor):
        labels = labels.numpy()
    labels = labels.astype(np.int64)
    valid = labels >= 0
    return vectors[valid].astype(np.float32), labels[valid]


def main():
    print("=" * 60)
    print("Phase 9 - Model 2 (4-class): LightGBM")
    print("=" * 60)

    print("\nLoading data...")
    X_train, y_train = load_point_data("train")
    X_val, y_val = load_point_data("val")
    X_test, y_test = load_point_data("test")
    print(f"  Train: {X_train.shape}  Val: {X_val.shape}  Test: {X_test.shape}")

    print("\nBuilding LightGBM datasets...")
    train_data = lgb.Dataset(X_train, label=y_train)
    val_data = lgb.Dataset(X_val, label=y_val, reference=train_data)

    params = {
        "objective": "multiclass",
        "num_class": PitchResult4.NUM_CLASSES,
        "metric": "multi_logloss",
        "is_unbalance": True,
        "learning_rate": 0.05,
        "num_leaves": 63,
        "max_depth": 8,
        "min_data_in_leaf": 100,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "verbose": 1,
        "num_threads": -1,
        "seed": 42,
    }

    print("\nTraining LightGBM...")
    t_start = time.time()
    booster = lgb.train(
        params,
        train_data,
        num_boost_round=1000,
        valid_sets=[train_data, val_data],
        valid_names=["train", "val"],
        callbacks=[
            lgb.early_stopping(stopping_rounds=20),
            lgb.log_evaluation(period=50),
        ],
    )
    train_time = time.time() - t_start
    print(f"Complete: {train_time:.1f}s ({train_time / 60:.1f}min)")
    print(f"Best iteration: {booster.best_iteration}")

    print("\nEvaluating on test set...")
    proba = booster.predict(X_test, num_iteration=booster.best_iteration).astype(np.float32)

    top1 = top_k_accuracy(proba, y_test, k=1)
    top3 = top_k_accuracy(proba, y_test, k=3)
    ce = cross_entropy(proba, y_test)
    pcm = per_class_metrics(proba, y_test, PitchResult4.NUM_CLASSES)

    print(f"\n  Top-1: {top1 * 100:.1f}%")
    print(f"  Top-3: {top3 * 100:.1f}%")
    print(f"  CE:    {ce:.4f}")
    print("\n  Per-class accuracy:")
    for name, acc in zip(CLASS_NAMES, pcm["per_class_accuracy"]):
        n = int((y_test == CLASS_NAMES.index(name)).sum())
        print(f"    {name:<12}: {acc * 100:.1f}%  (n={n:,})")

    print("\nSaving...")
    booster.save_model(str(CKPT_DIR / "lightgbm_4cls.txt"))
    np.savez(
        OUTPUT_DIR / "evaluation_lgb_4cls.npz",
        probs=proba,
        targets=y_test,
        top1=np.float32(top1),
        top3=np.float32(top3),
        ce=np.float32(ce),
        per_class_accuracy=pcm["per_class_accuracy"],
        confusion_matrix=pcm["confusion_matrix"],
        train_time=np.float32(train_time),
        best_iteration=np.int32(booster.best_iteration),
        model_name=np.array("LightGBM_4cls"),
        class_names=np.array(CLASS_NAMES),
    )
    print(f"[OK] {OUTPUT_DIR / 'evaluation_lgb_4cls.npz'}")


if __name__ == "__main__":
    main()

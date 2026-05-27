"""Phase 10.1 - LightGBM (10-class, 135-dim)

135-dim 입력, CUDA 가속 학습.
기존 77-dim LightGBM (13.0% 역방향 collapse) 대비 context 효과 측정.
class weight: is_unbalance=True (inverse-freq 과보정 방지).
"""

import sys
import time
from pathlib import Path

import numpy as np
import torch

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

import lightgbm as lgb

from src.data.features import PitchResult10
from src.evaluation.metrics import cross_entropy, per_class_metrics, top_k_accuracy

DATA_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
CKPT_DIR = OUTPUT_DIR / "checkpoints"
CKPT_DIR.mkdir(parents=True, exist_ok=True)

CLASS_NAMES = [PitchResult10.NAMES[i] for i in range(PitchResult10.NUM_CLASSES)]

USE_CUDA = torch.cuda.is_available()


def load_point_data(split: str):
    """135-dim vectors + 10-class labels (-1 제거)."""
    vectors = np.load(DATA_DIR / f"vectors_b3_10cls_{split}.npy")
    labels = np.load(DATA_DIR / f"labels_10_b3_{split}.npy")
    valid = labels >= 0
    return vectors[valid].astype(np.float32), labels[valid]


def main():
    print("=" * 60)
    print("Phase 10.1 - LightGBM (10-class, 135-dim)")
    print(f"CUDA: {'available (GPU)' if USE_CUDA else 'unavailable (CPU)'}")
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
        "num_class": PitchResult10.NUM_CLASSES,
        "metric": "multi_logloss",
        "is_unbalance": True,
        "learning_rate": 0.05,
        "num_leaves": 63,
        "max_depth": 8,
        "min_data_in_leaf": 20,
        "feature_fraction": 0.8,
        "bagging_fraction": 0.8,
        "bagging_freq": 5,
        "verbose": 1,
        "seed": 42,
    }

    if USE_CUDA:
        params["device"] = "cuda"
        params["num_threads"] = 0
        print("  LightGBM device=cuda 활성화")
    else:
        params["num_threads"] = -1

    print("\nTraining LightGBM (135-dim)...")
    t_start = time.time()
    try:
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
    except Exception as e:
        if USE_CUDA and "cuda" in str(e).lower():
            print(f"\n[WARN] CUDA 학습 실패: {e}\n  → CPU 폴백 재시도")
            params.pop("device", None)
            params["num_threads"] = -1
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
        else:
            raise

    train_time = time.time() - t_start
    print(f"Complete: {train_time:.1f}s ({train_time / 60:.1f}min)")
    print(f"Best iteration: {booster.best_iteration}")

    print("\nEvaluating on test set...")
    proba = booster.predict(X_test, num_iteration=booster.best_iteration).astype(np.float32)

    top1 = top_k_accuracy(proba, y_test, k=1)
    top3 = top_k_accuracy(proba, y_test, k=3)
    ce = cross_entropy(proba, y_test)
    pcm = per_class_metrics(proba, y_test, PitchResult10.NUM_CLASSES)

    print(f"\n  Top-1: {top1 * 100:.1f}%  (baseline 77d: 13.0%)")
    print(f"  Top-3: {top3 * 100:.1f}%")
    print(f"  CE:    {ce:.4f}")
    print("\n  Per-class accuracy:")
    for name, acc in zip(CLASS_NAMES, pcm["per_class_accuracy"]):
        n = int((y_test == CLASS_NAMES.index(name)).sum())
        flag = " ← collapse!" if acc < 0.05 else ""
        print(f"    {name:<12}: {acc * 100:.1f}%  (n={n:,}){flag}")

    print("\nSaving...")
    booster.save_model(str(CKPT_DIR / "lightgbm_135d_10cls.txt"))
    np.savez(
        OUTPUT_DIR / "evaluation_lgb_135d_10cls.npz",
        probs=proba,
        targets=y_test,
        top1=np.float32(top1),
        top3=np.float32(top3),
        ce=np.float32(ce),
        per_class_accuracy=pcm["per_class_accuracy"],
        confusion_matrix=pcm["confusion_matrix"],
        train_time=np.float32(train_time),
        best_iteration=np.int32(booster.best_iteration),
        model_name=np.array("LightGBM_135d_10cls"),
        class_names=np.array(CLASS_NAMES),
    )
    print(f"[OK] {OUTPUT_DIR / 'evaluation_lgb_135d_10cls.npz'}")


if __name__ == "__main__":
    main()

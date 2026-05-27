"""Phase 10.1 - LR (10-class, 135-dim)

handoff_v1 58d context (UMAP_5d + count_cluster + arsenal) 추가된 135-dim 입력.
기존 77-dim LR (41.1% collapse) 대비 context 추가 효과 측정.
"""

import pickle
import sys
import time
from pathlib import Path

import numpy as np

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from sklearn.linear_model import LogisticRegression
from sklearn.utils.class_weight import compute_class_weight

from src.data.features import PitchResult10
from src.evaluation.metrics import cross_entropy, per_class_metrics, top_k_accuracy

DATA_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
CKPT_DIR = OUTPUT_DIR / "checkpoints"
CKPT_DIR.mkdir(parents=True, exist_ok=True)

CLASS_NAMES = [PitchResult10.NAMES[i] for i in range(PitchResult10.NUM_CLASSES)]


def load_point_data(split: str):
    """135-dim vectors + 10-class labels (-1 제거)."""
    vectors = np.load(DATA_DIR / f"vectors_b3_10cls_{split}.npy")
    labels = np.load(DATA_DIR / f"labels_10_b3_{split}.npy")
    valid = labels >= 0
    return vectors[valid].astype(np.float32), labels[valid]


def main():
    print("=" * 60)
    print("Phase 10.1 - LR (10-class, 135-dim)")
    print("=" * 60)

    print("\nLoading data...")
    X_train, y_train = load_point_data("train")
    X_test, y_test = load_point_data("test")
    print(f"  Train: {X_train.shape}  Test: {X_test.shape}")
    print(f"  Classes: {np.unique(y_train)}")

    if len(X_train) > 500_000:
        print(f"\nDownsampling train: {len(X_train):,} → 500,000")
        rng = np.random.RandomState(42)
        idx = rng.choice(len(X_train), 500_000, replace=False)
        X_train, y_train = X_train[idx], y_train[idx]

    classes_arr = np.unique(y_train)
    raw_w = compute_class_weight("balanced", classes=classes_arr, y=y_train)
    sqrt_w = {int(c): float(w) for c, w in zip(classes_arr, np.sqrt(raw_w))}
    print(f"\nClass weights (sqrt-balanced): "
          + ", ".join(f"{PitchResult10.NAMES[k]}={v:.2f}" for k, v in sorted(sqrt_w.items())))

    print("\nTraining LogisticRegression (135-dim)...")
    t_start = time.time()
    model = LogisticRegression(
        solver="lbfgs",
        max_iter=500,
        C=1.0,
        class_weight=sqrt_w,
        n_jobs=-1,
        random_state=42,
        verbose=1,
    )
    model.fit(X_train, y_train)
    train_time = time.time() - t_start
    print(f"Complete: {train_time:.1f}s ({train_time / 60:.1f}min)")

    print("\nEvaluating on test set...")
    raw_proba = model.predict_proba(X_test)

    proba = np.zeros((len(X_test), PitchResult10.NUM_CLASSES), dtype=np.float32)
    for col, cls in enumerate(model.classes_):
        proba[:, int(cls)] = raw_proba[:, col]

    top1 = top_k_accuracy(proba, y_test, k=1)
    top3 = top_k_accuracy(proba, y_test, k=3)
    ce = cross_entropy(proba, y_test)
    pcm = per_class_metrics(proba, y_test, PitchResult10.NUM_CLASSES)

    print(f"\n  Top-1: {top1 * 100:.1f}%  (baseline 77d: 41.1%)")
    print(f"  Top-3: {top3 * 100:.1f}%")
    print(f"  CE:    {ce:.4f}")
    print("\n  Per-class accuracy:")
    for name, acc in zip(CLASS_NAMES, pcm["per_class_accuracy"]):
        n = int((y_test == CLASS_NAMES.index(name)).sum())
        flag = " ← collapse!" if acc < 0.05 else ""
        print(f"    {name:<12}: {acc * 100:.1f}%  (n={n:,}){flag}")

    print("\nSaving...")
    with open(CKPT_DIR / "logistic_regression_135d_10cls.pkl", "wb") as f:
        pickle.dump(model, f)

    np.savez(
        OUTPUT_DIR / "evaluation_lr_135d_10cls.npz",
        probs=proba,
        targets=y_test,
        top1=np.float32(top1),
        top3=np.float32(top3),
        ce=np.float32(ce),
        per_class_accuracy=pcm["per_class_accuracy"],
        confusion_matrix=pcm["confusion_matrix"],
        train_time=np.float32(train_time),
        model_name=np.array("LR_135d_10cls"),
        class_names=np.array(CLASS_NAMES),
    )
    print(f"[OK] {OUTPUT_DIR / 'evaluation_lr_135d_10cls.npz'}")


if __name__ == "__main__":
    main()

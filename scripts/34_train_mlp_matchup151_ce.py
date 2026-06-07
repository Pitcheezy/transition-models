"""matchup151 CE: MLP 151-dim 10-class (135d Arsenal + 16d batter context).

Extends the 135d Arsenal MLP (model_b3_135dim_10cls) by adding 16-dimensional
train-only batter context features (12 rate + 4 mean, handedness-matched).

Architecture: 151 → 128 → 128 → 10  (same depth/width as MLP135CE)
Loss: Cross-Entropy (CE) — same as the current best MDP-compatible model MLP135CE
Data: vectors_matchup151_10cls_{train,val,test}.npy  (from 33_preprocess_matchup151.py)

Baseline comparison target:
    MLP135CE:    Top-1 67.48%, CE 0.8570, Single~HR recall = 0%
    matchup151:  Does adding batter context lift Single~HR recall above 0%?

For focal loss variant: see 34b_train_mlp_matchup151_focal.py (TODO)

Usage:
    cd transition-models
    uv run python scripts/34_train_mlp_matchup151_ce.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import torch
import torch.nn.functional as F
from torch.utils.data import DataLoader

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.dataset import PitchPointDataset
from src.data.features import PitchResult10
from src.evaluation.metrics import cross_entropy, per_class_metrics, top_k_accuracy
from src.models.otremba_mlp import OtrembaMLP
from src.training.train import TrainingConfig, train
from src.utils.device import get_device

DATA_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
CKPT_DIR = OUTPUT_DIR / "checkpoints"

INPUT_DIM = 151
RUN_NAME = "model_matchup151_10cls_ce"
CLASS_NAMES = [PitchResult10.NAMES[i] for i in range(PitchResult10.NUM_CLASSES)]


def load_dataset(split: str) -> PitchPointDataset:
    vec_path = DATA_DIR / f"vectors_matchup151_10cls_{split}.npy"
    lbl_path = DATA_DIR / f"labels_10_matchup151_{split}.npy"
    for p in [vec_path, lbl_path]:
        if not p.exists():
            raise FileNotFoundError(
                f"Matchup151 data not found: {p}\n"
                "Run: uv run python scripts/33_preprocess_matchup151.py"
            )
    vectors = np.load(vec_path)
    labels = np.load(lbl_path)
    assert vectors.shape[1] == INPUT_DIM, f"Expected {INPUT_DIM}d, got {vectors.shape[1]}d"
    valid = labels >= 0
    print(f"  {split}: {vectors.shape[0]:,} total, {valid.sum():,} valid labels")
    return PitchPointDataset(vectors[valid], labels[valid])


def evaluate_on_test(model, test_loader, device):
    model.eval()
    all_probs, all_targets = [], []
    with torch.no_grad():
        for x, y in test_loader:
            x = x.to(device)
            probs = F.softmax(model(x), dim=-1).cpu().numpy()
            all_probs.append(probs)
            all_targets.append(y.numpy())
    return np.concatenate(all_probs), np.concatenate(all_targets)


def main():
    print("=" * 60)
    print("matchup151 CE: MLP 151-dim 10-class")
    print(f"  Input: {INPUT_DIM}d = 77d base + 58d arsenal + 16d batter context")
    print("=" * 60)

    print("\nLoading data...")
    train_ds = load_dataset("train")
    val_ds = load_dataset("val")
    test_ds = load_dataset("test")
    print(f"  Train: {len(train_ds):,}  Val: {len(val_ds):,}  Test: {len(test_ds):,}")

    # num_workers=0 required on Windows (multiprocessing spawn conflicts)
    train_loader = DataLoader(train_ds, batch_size=256, shuffle=True, num_workers=0)
    val_loader = DataLoader(val_ds, batch_size=256, shuffle=False, num_workers=0)
    test_loader = DataLoader(test_ds, batch_size=256, shuffle=False, num_workers=0)

    model = OtrembaMLP(input_dim=INPUT_DIM, hidden_dim=128, n_classes=PitchResult10.NUM_CLASSES, dropout=0.2)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"\nModel: OtrembaMLP({INPUT_DIM}→128→128→10)  params={n_params:,}")

    config = TrainingConfig(
        model_name="B",
        epochs=30,
        batch_size=256,
        lr=1e-3,
        weight_decay=1e-5,
        early_stopping_patience=5,
        run_name=RUN_NAME,
        use_wandb=False,
        wandb_tags=["matchup151", "mlp", "10cls", "ce", "batter_context"],
    )

    print("\nStarting training...")
    print("-" * 60)
    best_val_loss = train(model, train_loader, val_loader, config, "B")
    print(f"\nBest val loss: {best_val_loss:.4f}")

    # --- Test evaluation ---
    print("\nEvaluating on test set (best checkpoint)...")
    ckpt_path = CKPT_DIR / f"{RUN_NAME}_best.pt"
    ckpt = torch.load(ckpt_path, weights_only=False, map_location="cpu")
    best_model = OtrembaMLP(input_dim=INPUT_DIM, hidden_dim=128, n_classes=PitchResult10.NUM_CLASSES, dropout=0.2)
    best_model.load_state_dict(ckpt["model_state"])

    device = get_device()
    best_model = best_model.to(device)
    proba, y_test = evaluate_on_test(best_model, test_loader, device)

    top1 = top_k_accuracy(proba, y_test, k=1)
    top3 = top_k_accuracy(proba, y_test, k=3)
    ce = cross_entropy(proba, y_test)
    pcm = per_class_metrics(proba, y_test, PitchResult10.NUM_CLASSES)

    print(f"\n  Top-1: {top1 * 100:.2f}%")
    print(f"  Top-3: {top3 * 100:.2f}%")
    print(f"  CE:    {ce:.4f}")
    print(f"\n  Comparison baseline (same condition):")
    print(f"    MLP 135d CE (no batter): Top-1 67.48%, CE 0.8570")
    print(f"    matchup151 CE (this):    Top-1 {top1*100:.2f}%, CE {ce:.4f}")
    print("\n  Per-class accuracy (KEY: Single/Double/Triple/HomeRun above 0%?):")
    for name, acc, prec, rec, f1 in zip(
        CLASS_NAMES,
        pcm["per_class_accuracy"],
        pcm.get("per_class_precision", [float("nan")] * len(CLASS_NAMES)),
        pcm.get("per_class_recall", [float("nan")] * len(CLASS_NAMES)),
        pcm.get("per_class_f1", [float("nan")] * len(CLASS_NAMES)),
    ):
        flag = " <-- KEY" if name in ("Single", "Double", "Triple", "HomeRun") else ""
        print(f"    {name:<12}: acc={acc*100:.1f}%  rec={rec*100:.1f}%{flag}")

    np.savez(
        OUTPUT_DIR / "evaluation_matchup151_10cls_ce.npz",
        probs=proba,
        targets=y_test,
        top1=np.float32(top1),
        top3=np.float32(top3),
        ce=np.float32(ce),
        per_class_accuracy=pcm["per_class_accuracy"],
        confusion_matrix=pcm["confusion_matrix"],
        best_val_loss=np.float32(best_val_loss),
        model_name=np.array("MLP_matchup151_CE"),
        class_names=np.array(CLASS_NAMES),
    )
    print(f"\n  Saved: {OUTPUT_DIR / 'evaluation_matchup151_10cls_ce.npz'}")
    print(f"  Checkpoint: {ckpt_path}")


if __name__ == "__main__":
    main()

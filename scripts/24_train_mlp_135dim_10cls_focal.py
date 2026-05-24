"""Phase 9 - Model B v4: MLP 135-dim 10-class with Focal Loss (gamma=2).

Architecture:  135 → 128 → 128 → 10
Loss:          Focal Loss (gamma=2.0) — Single/Double/Triple/HR collapse 해결
Checkpoint:    outputs/checkpoints/model_b3_focal_135dim_10cls_best.pt
Evaluation:    outputs/evaluation_mlp_135dim_10cls_focal.npz

Baseline 비교:
  - MLP 135-dim CE (script 23):  67.5% top-1, Single~HR = 0%
  - Transformer (Model C v3):    67.2% top-1
  - 이 스크립트 목표:            Single/HR > 5%로 rl-agent RE24 계산 정확도 향상
"""

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

INPUT_DIM = 135
RUN_NAME = "model_b3_focal_135dim_10cls"
CLASS_NAMES = [PitchResult10.NAMES[i] for i in range(PitchResult10.NUM_CLASSES)]


def load_dataset(split: str) -> PitchPointDataset:
    vectors = np.load(DATA_DIR / f"vectors_b3_10cls_{split}.npy")
    labels = np.load(DATA_DIR / f"labels_10_b3_{split}.npy")
    valid = labels >= 0
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


def print_class_distribution(labels: np.ndarray) -> None:
    total = len(labels)
    for i, name in enumerate(CLASS_NAMES):
        count = (labels == i).sum()
        print(f"    {name:<12}: {count:>8,}  ({count/total*100:.2f}%)")


def main():
    print("=" * 60)
    print("Phase 9 - Model B v4: MLP 135-dim 10-class + Focal Loss")
    print("=" * 60)

    print("\nLoading data...")
    train_ds = load_dataset("train")
    val_ds = load_dataset("val")
    test_ds = load_dataset("test")
    print(f"  Train: {len(train_ds):,}  Val: {len(val_ds):,}  Test: {len(test_ds):,}")

    print("\n  Train class distribution:")
    print_class_distribution(train_ds.labels.numpy())

    train_loader = DataLoader(train_ds, batch_size=256, shuffle=True, num_workers=2, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=256, shuffle=False, num_workers=2, pin_memory=True)
    test_loader = DataLoader(test_ds, batch_size=256, shuffle=False, num_workers=2, pin_memory=True)

    model = OtrembaMLP(input_dim=INPUT_DIM, hidden_dim=128, n_classes=PitchResult10.NUM_CLASSES, dropout=0.2)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"\nModel: OtrembaMLP({INPUT_DIM}→128→128→10)  params={n_params:,}")

    config = TrainingConfig(
        model_name="B",
        epochs=30,
        batch_size=256,
        lr=1e-3,
        weight_decay=1e-5,
        early_stopping_patience=7,  # focal loss는 수렴이 느릴 수 있음
        use_focal=True,
        focal_gamma=2.0,
        run_name=RUN_NAME,
        use_wandb=False,
        wandb_tags=["phase9", "mlp", "10cls", "135dim", "focal"],
    )

    print(f"\nStarting training (focal_loss=True, gamma={config.focal_gamma})...")
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

    print(f"\n  Top-1: {top1 * 100:.1f}%")
    print(f"  Top-3: {top3 * 100:.1f}%")
    print(f"  CE:    {ce:.4f}")
    print(f"\n  비교:")
    print(f"    MLP 135-dim CE (baseline): 67.5%  (Single~HR = 0%)")
    print(f"    Transformer 87×400:        67.2%")
    print(f"    This (focal gamma=2):      {top1*100:.1f}%")
    print("\n  Per-class accuracy:")
    for name, acc in zip(CLASS_NAMES, pcm["per_class_accuracy"]):
        flag = " ← 목표" if name in ("Single", "Double", "Triple", "HomeRun") else ""
        print(f"    {name:<12}: {acc * 100:.1f}%{flag}")

    np.savez(
        OUTPUT_DIR / "evaluation_mlp_135dim_10cls_focal.npz",
        probs=proba,
        targets=y_test,
        top1=np.float32(top1),
        top3=np.float32(top3),
        ce=np.float32(ce),
        per_class_accuracy=pcm["per_class_accuracy"],
        confusion_matrix=pcm["confusion_matrix"],
        best_val_loss=np.float32(best_val_loss),
        model_name=np.array("MLP_135dim_10cls_focal"),
        class_names=np.array(CLASS_NAMES),
    )
    print(f"\n  Saved: {OUTPUT_DIR / 'evaluation_mlp_135dim_10cls_focal.npz'}")
    print(f"  Checkpoint: {ckpt_path}")
    print(f"\n  rl-agent 팀원에게 전달:")
    print(f"    체크포인트: outputs/checkpoints/{RUN_NAME}_best.pt")
    print(f"    입력 차원: {INPUT_DIM} (UMAP 5d 미보유 시 [77:82] = 0.0 처리)")
    print(f"    출력: (10,) softmax 확률 [Ball, Strike, Single, Double, Triple, HR, FieldOut, Strikeout, Walk, HBP]")


if __name__ == "__main__":
    main()

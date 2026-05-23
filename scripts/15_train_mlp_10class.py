"""Phase 9 - Model 3: MLP 10-class (Otremba architecture, output 4→10)

Single-pitch 77-dim input, 10-class output.
기존 OtrembaMLP(n_classes=10) 재사용. i.i.d. + 비선형의 한계 측정.
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

CLASS_NAMES = [PitchResult10.NAMES[i] for i in range(PitchResult10.NUM_CLASSES)]
RUN_NAME = "model_b_10cls_v1"


def load_point_dataset(split: str) -> PitchPointDataset:
    pt = torch.load(DATA_DIR / f"model_b_{split}.pt", weights_only=False)
    vectors = pt["vectors"]
    if isinstance(vectors, torch.Tensor):
        vectors = vectors.numpy()
    labels = np.load(DATA_DIR / f"labels_10_{split}.npy")
    return PitchPointDataset(vectors, labels)


def evaluate_on_test(model, test_loader, device):
    """Collect probs and targets from the test DataLoader."""
    model.eval()
    all_probs = []
    all_targets = []
    with torch.no_grad():
        for x, y in test_loader:
            x = x.to(device)
            logits = model(x)
            probs = F.softmax(logits, dim=-1).cpu().numpy()
            all_probs.append(probs)
            all_targets.append(y.numpy())
    return np.concatenate(all_probs), np.concatenate(all_targets)


def main():
    print("=" * 60)
    print("Phase 9 - Model 3: MLP 10-class")
    print("=" * 60)

    print("\nLoading data...")
    train_ds = load_point_dataset("train")
    val_ds = load_point_dataset("val")
    test_ds = load_point_dataset("test")
    print(f"  Train: {len(train_ds):,}  Val: {len(val_ds):,}  Test: {len(test_ds):,}")

    train_loader = DataLoader(train_ds, batch_size=256, shuffle=True, num_workers=2, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=256, shuffle=False, num_workers=2, pin_memory=True)
    test_loader = DataLoader(test_ds, batch_size=256, shuffle=False, num_workers=2, pin_memory=True)

    model = OtrembaMLP(input_dim=77, hidden_dim=128, n_classes=PitchResult10.NUM_CLASSES, dropout=0.2)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"\nModel: OtrembaMLP(77→128→128→10)  params={n_params:,}")

    config = TrainingConfig(
        model_name="B",
        epochs=30,
        batch_size=256,
        lr=1e-3,
        weight_decay=1e-5,
        early_stopping_patience=5,
        run_name=RUN_NAME,
        use_wandb=False,
        wandb_tags=["phase9", "mlp", "10cls"],
    )

    print("\nStarting training (no wandb)...")
    print("-" * 60)
    best_val_loss = train(model, train_loader, val_loader, config, "B")
    print(f"\nBest val loss: {best_val_loss:.4f}")

    # --- Test evaluation ---
    print("\nEvaluating on test set (best checkpoint)...")
    ckpt_path = CKPT_DIR / f"{RUN_NAME}_best.pt"
    ckpt = torch.load(ckpt_path, weights_only=False, map_location="cpu")
    best_model = OtrembaMLP(input_dim=77, hidden_dim=128, n_classes=PitchResult10.NUM_CLASSES, dropout=0.2)
    best_model.load_state_dict(ckpt["model_state"])

    device = get_device()
    best_model = best_model.to(device)
    proba, y_test = evaluate_on_test(best_model, test_loader, device)

    # Filter valid labels
    valid = y_test >= 0
    proba, y_test = proba[valid], y_test[valid]

    top1 = top_k_accuracy(proba, y_test, k=1)
    top3 = top_k_accuracy(proba, y_test, k=3)
    ce = cross_entropy(proba, y_test)
    pcm = per_class_metrics(proba, y_test, PitchResult10.NUM_CLASSES)

    print(f"\n  Top-1: {top1 * 100:.1f}%")
    print(f"  Top-3: {top3 * 100:.1f}%")
    print(f"  CE:    {ce:.4f}")
    print("\n  Per-class accuracy:")
    for name, acc in zip(CLASS_NAMES, pcm["per_class_accuracy"]):
        print(f"    {name:<12}: {acc * 100:.1f}%")

    np.savez(
        OUTPUT_DIR / "evaluation_mlp_10cls.npz",
        probs=proba,
        targets=y_test,
        top1=np.float32(top1),
        top3=np.float32(top3),
        ce=np.float32(ce),
        per_class_accuracy=pcm["per_class_accuracy"],
        confusion_matrix=pcm["confusion_matrix"],
        best_val_loss=np.float32(best_val_loss),
        model_name=np.array("MLP_10cls"),
        class_names=np.array(CLASS_NAMES),
    )
    print(f"\n✅ {OUTPUT_DIR / 'evaluation_mlp_10cls.npz'}")


if __name__ == "__main__":
    main()

"""Evaluate saved 135-dim 10-class checkpoint and save npz."""
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
from src.utils.device import get_device

DATA_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
CKPT_DIR = OUTPUT_DIR / "checkpoints"

INPUT_DIM = 135
RUN_NAME = "model_b3_135dim_10cls"
CLASS_NAMES = [PitchResult10.NAMES[i] for i in range(PitchResult10.NUM_CLASSES)]


def load_dataset(split):
    vectors = np.load(DATA_DIR / f"vectors_b3_10cls_{split}.npy")
    labels = np.load(DATA_DIR / f"labels_10_b3_{split}.npy")
    valid = labels >= 0
    return PitchPointDataset(vectors[valid], labels[valid])


def evaluate_on_test(model, loader, device):
    model.eval()
    all_probs, all_targets = [], []
    with torch.no_grad():
        for x, y in loader:
            x = x.to(device)
            all_probs.append(F.softmax(model(x), dim=-1).cpu().numpy())
            all_targets.append(y.numpy())
    return np.concatenate(all_probs), np.concatenate(all_targets)


def main():
    test_ds = load_dataset("test")
    test_loader = DataLoader(test_ds, batch_size=256, shuffle=False, num_workers=2)

    ckpt_path = CKPT_DIR / f"{RUN_NAME}_best.pt"
    ckpt = torch.load(ckpt_path, weights_only=False, map_location="cpu")
    model = OtrembaMLP(input_dim=INPUT_DIM, hidden_dim=128, n_classes=PitchResult10.NUM_CLASSES, dropout=0.2)
    model.load_state_dict(ckpt["model_state"])
    best_val_loss = float(ckpt.get("val_loss", 0.8564))

    device = get_device()
    model = model.to(device)
    proba, y_test = evaluate_on_test(model, test_loader, device)

    top1 = top_k_accuracy(proba, y_test, k=1)
    top3 = top_k_accuracy(proba, y_test, k=3)
    ce = cross_entropy(proba, y_test)
    pcm = per_class_metrics(proba, y_test, PitchResult10.NUM_CLASSES)

    print(f"Top-1: {top1 * 100:.1f}%")
    print(f"Top-3: {top3 * 100:.1f}%")
    print(f"CE:    {ce:.4f}")
    print(f"Best val loss: {best_val_loss:.4f}")
    print("\nPer-class accuracy:")
    for name, acc in zip(CLASS_NAMES, pcm["per_class_accuracy"]):
        print(f"  {name:<12}: {acc * 100:.1f}%")

    out_path = OUTPUT_DIR / "evaluation_mlp_135dim_10cls.npz"
    np.savez(
        out_path,
        probs=proba,
        targets=y_test,
        top1=np.float32(top1),
        top3=np.float32(top3),
        ce=np.float32(ce),
        per_class_accuracy=pcm["per_class_accuracy"],
        confusion_matrix=pcm["confusion_matrix"],
        best_val_loss=np.float32(best_val_loss),
        model_name=np.array("MLP_135dim_10cls"),
        class_names=np.array(CLASS_NAMES),
    )
    print(f"\nSaved: {out_path}")


if __name__ == "__main__":
    main()

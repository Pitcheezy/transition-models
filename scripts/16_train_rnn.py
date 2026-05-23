"""Phase 9 - Model 4: RNN/LSTM (10-class)

Sequence 400 pitches × 87-dim input, 10-class output.
Model C와 동일한 데이터. 단순 LSTM으로 Transformer 대비 sequence 모델 기준선 확보.
"""

import pickle
import sys
import time
from pathlib import Path

import numpy as np
import torch
import torch.nn as nn
import torch.nn.functional as F
from torch.utils.data import DataLoader

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.dataset import PitchSequenceDataset
from src.data.features import PitchResult10
from src.evaluation.metrics import cross_entropy, per_class_metrics, top_k_accuracy
from src.utils.device import get_device

DATA_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_DIR = PROJECT_ROOT / "outputs"
CKPT_DIR = OUTPUT_DIR / "checkpoints"
CKPT_DIR.mkdir(parents=True, exist_ok=True)

CLASS_NAMES = [PitchResult10.NAMES[i] for i in range(PitchResult10.NUM_CLASSES)]


class PitchRNN(nn.Module):
    """2-layer LSTM for 10-class pitch outcome prediction.

    Input:  (batch, 400, 87) pitch sequence
    Output: (batch, 10) logits
    """

    def __init__(self, input_dim: int = 87, hidden_dim: int = 256, num_layers: int = 2, num_classes: int = 10):
        super().__init__()
        self.lstm = nn.LSTM(
            input_size=input_dim,
            hidden_size=hidden_dim,
            num_layers=num_layers,
            batch_first=True,
            dropout=0.2,
        )
        self.head = nn.Linear(hidden_dim, num_classes)

    def forward(self, x: torch.Tensor) -> torch.Tensor:
        out, _ = self.lstm(x)
        return self.head(out[:, -1, :])


def load_sequence_dataset(split: str) -> PitchSequenceDataset:
    vecs = np.load(DATA_DIR / f"vectors_c_{split}.npy")
    labels = np.load(DATA_DIR / f"labels_10_{split}.npy")
    hlocs = np.load(DATA_DIR / f"hit_locs_{split}.npy")
    with open(DATA_DIR / f"indices_{split}.pkl", "rb") as f:
        indices = pickle.load(f)
    return PitchSequenceDataset(vecs, labels, hlocs, indices, seq_length=400)


def train_epoch(model, loader, optimizer, device):
    model.train()
    total_loss, total_correct, total_valid = 0.0, 0, 0
    for batch in loader:
        x = batch["sequence"].to(device)
        y = batch["pitch_result"].to(device)
        valid = y >= 0
        if not valid.any():
            continue
        optimizer.zero_grad()
        logits = model(x)
        loss = F.cross_entropy(logits[valid], y[valid])
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        total_loss += loss.item() * valid.sum().item()
        total_correct += (logits.argmax(1)[valid] == y[valid]).sum().item()
        total_valid += valid.sum().item()
    return total_loss / max(total_valid, 1), total_correct / max(total_valid, 1)


def eval_epoch(model, loader, device):
    model.eval()
    total_loss, total_correct, total_valid = 0.0, 0, 0
    with torch.no_grad():
        for batch in loader:
            x = batch["sequence"].to(device)
            y = batch["pitch_result"].to(device)
            valid = y >= 0
            if not valid.any():
                continue
            logits = model(x)
            loss = F.cross_entropy(logits[valid], y[valid])
            total_loss += loss.item() * valid.sum().item()
            total_correct += (logits.argmax(1)[valid] == y[valid]).sum().item()
            total_valid += valid.sum().item()
    return total_loss / max(total_valid, 1), total_correct / max(total_valid, 1)


def collect_test_probs(model, loader, device):
    model.eval()
    all_probs, all_targets = [], []
    with torch.no_grad():
        for batch in loader:
            x = batch["sequence"].to(device)
            y = batch["pitch_result"]
            logits = model(x)
            probs = F.softmax(logits, dim=-1).cpu().numpy()
            all_probs.append(probs)
            all_targets.append(y.numpy())
    return np.concatenate(all_probs), np.concatenate(all_targets)


def main():
    print("=" * 60)
    print("Phase 9 - Model 4: RNN/LSTM (10-class)")
    print("=" * 60)

    device = get_device()
    print(f"\nDevice: {device}")

    print("\nLoading sequence data...")
    train_ds = load_sequence_dataset("train")
    val_ds = load_sequence_dataset("val")
    test_ds = load_sequence_dataset("test")
    print(f"  Train: {len(train_ds):,}  Val: {len(val_ds):,}  Test: {len(test_ds):,}")

    num_workers = 2 if sys.platform != "win32" else 0
    train_loader = DataLoader(train_ds, batch_size=64, shuffle=True, num_workers=num_workers, pin_memory=True)
    val_loader = DataLoader(val_ds, batch_size=64, shuffle=False, num_workers=num_workers, pin_memory=True)
    test_loader = DataLoader(test_ds, batch_size=64, shuffle=False, num_workers=num_workers)

    model = PitchRNN(input_dim=87, hidden_dim=256, num_layers=2, num_classes=PitchResult10.NUM_CLASSES)
    model = model.to(device)
    n_params = sum(p.numel() for p in model.parameters())
    print(f"\nModel: PitchRNN(LSTM 2-layer, hidden=256)  params={n_params:,}")

    optimizer = torch.optim.Adam(model.parameters(), lr=1e-4, weight_decay=1e-5)

    EPOCHS = 30
    PATIENCE = 5
    best_val_loss = float("inf")
    patience_counter = 0
    best_epoch = 0
    t_train_start = time.time()

    print(f"\nStarting training (max {EPOCHS} epochs, patience={PATIENCE})...")
    print("Estimated time: 5-10 hours (RTX 4070)")
    print("-" * 60)

    for epoch in range(EPOCHS):
        t0 = time.time()
        train_loss, train_acc = train_epoch(model, train_loader, optimizer, device)
        val_loss, val_acc = eval_epoch(model, val_loader, device)
        elapsed = time.time() - t0

        print(
            f"Epoch {epoch + 1:2d}/{EPOCHS}  ({elapsed:.0f}s) "
            f"train_loss={train_loss:.4f} train_acc={train_acc * 100:.1f}%  "
            f"val_loss={val_loss:.4f} val_acc={val_acc * 100:.1f}%",
            flush=True,
        )

        if val_loss < best_val_loss:
            best_val_loss = val_loss
            best_epoch = epoch + 1
            patience_counter = 0
            torch.save(
                {
                    "epoch": epoch,
                    "model_state": model.state_dict(),
                    "val_loss": val_loss,
                    "val_acc": val_acc,
                },
                CKPT_DIR / "rnn_10cls_best.pt",
            )
            print(f"  → Best saved (val_loss={best_val_loss:.4f})")
        else:
            patience_counter += 1
            if patience_counter >= PATIENCE:
                print(f"\nEarly stopping at epoch {epoch + 1}")
                break

    total_train_time = time.time() - t_train_start
    print(f"\nTraining complete. Best val_loss={best_val_loss:.4f} at epoch {best_epoch}")
    print(f"Total train time: {total_train_time / 3600:.1f}h")

    # --- Test evaluation ---
    print("\nEvaluating best checkpoint on test set...")
    ckpt = torch.load(CKPT_DIR / "rnn_10cls_best.pt", weights_only=False, map_location="cpu")
    best_model = PitchRNN(input_dim=87, hidden_dim=256, num_layers=2, num_classes=PitchResult10.NUM_CLASSES)
    best_model.load_state_dict(ckpt["model_state"])
    best_model = best_model.to(device)

    proba, y_test = collect_test_probs(best_model, test_loader, device)
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
        OUTPUT_DIR / "evaluation_rnn_10cls.npz",
        probs=proba,
        targets=y_test,
        top1=np.float32(top1),
        top3=np.float32(top3),
        ce=np.float32(ce),
        per_class_accuracy=pcm["per_class_accuracy"],
        confusion_matrix=pcm["confusion_matrix"],
        best_val_loss=np.float32(best_val_loss),
        train_time=np.float32(total_train_time),
        model_name=np.array("RNN_LSTM"),
        class_names=np.array(CLASS_NAMES),
    )
    print(f"\n✅ {OUTPUT_DIR / 'evaluation_rnn_10cls.npz'}")


if __name__ == "__main__":
    main()

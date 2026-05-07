"""Phase 5.5: Model C (PitchTransformer) full training."""

import pickle
import sys
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.dataset import PitchSequenceDataset
from src.models.transformer import PitchTransformer
from src.training.train import TrainingConfig, train


def main():
    print("=" * 60)
    print("Phase 5.5: Model C Full Training")
    print("=" * 60)

    print("\nLoading data...")

    vecs = np.load("data/processed/vectors_c_train.npy")
    labels = np.load("data/processed/labels_10_train.npy")
    hlocs = np.load("data/processed/hit_locs_train.npy")
    with open("data/processed/indices_train.pkl", "rb") as f:
        train_indices = pickle.load(f)

    val_vecs = np.load("data/processed/vectors_c_val.npy")
    val_labels = np.load("data/processed/labels_10_val.npy")
    val_hlocs = np.load("data/processed/hit_locs_val.npy")
    with open("data/processed/indices_val.pkl", "rb") as f:
        val_indices = pickle.load(f)

    print(f"  Train vectors: {vecs.shape}")
    print(f"  Train sequences: {len(train_indices):,}")
    print(f"  Val vectors: {val_vecs.shape}")
    print(f"  Val sequences: {len(val_indices):,}")

    train_ds = PitchSequenceDataset(vecs, labels, hlocs, train_indices, 400)
    val_ds = PitchSequenceDataset(val_vecs, val_labels, val_hlocs, val_indices, 400)

    train_loader = DataLoader(
        train_ds, batch_size=32, shuffle=True,
        num_workers=2, pin_memory=True,
    )
    val_loader = DataLoader(
        val_ds, batch_size=32, shuffle=False,
        num_workers=2, pin_memory=True,
    )

    print(f"\n  Train batches: {len(train_loader):,}")
    print(f"  Val batches:   {len(val_loader):,}")

    model = PitchTransformer()
    n_params = sum(p.numel() for p in model.parameters())
    print(f"\nModel parameters: {n_params:,}")

    config = TrainingConfig(
        model_name="C",
        epochs=30,
        batch_size=32,
        lr=1e-4,
        weight_decay=1e-5,
        early_stopping_patience=5,
        run_name="model_c_full_v2",
        wandb_tags=["full", "model_c", "v2", "stride8"],
    )

    print("\nStarting training...")
    print("Estimated time: 2-3 hours")
    print("-" * 60)
    best_val = train(model, train_loader, val_loader, config, "C")

    print(f"\n{'=' * 60}")
    print(f"Training complete!")
    print(f"Best val loss: {best_val:.4f}")
    print(f"Checkpoint: outputs/checkpoints/model_c_full_v1_best.pt")
    print(f"Log:        outputs/logs/train_model_c_full_v1.log")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

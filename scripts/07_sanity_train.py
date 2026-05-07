"""Sanity training: small subset, real training loop, W&B logged."""

import pickle
import sys
from pathlib import Path

import numpy as np
import torch
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.dataset import PitchPointDataset, PitchSequenceDataset
from src.models.otremba_mlp import OtrembaMLP
from src.models.transformer import PitchTransformer
from src.training.train import TrainingConfig, train


def sanity_b():
    print("\n" + "=" * 50)
    print("Model B Sanity Training")
    print("=" * 50)

    train_data = torch.load("data/processed/model_b_train.pt", weights_only=False)
    val_data = torch.load("data/processed/model_b_val.pt", weights_only=False)

    train_ds = PitchPointDataset(train_data["vectors"][:1000], train_data["labels"][:1000])
    val_ds = PitchPointDataset(val_data["vectors"][:200], val_data["labels"][:200])

    train_loader = DataLoader(train_ds, batch_size=64, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=64)

    model = OtrembaMLP()
    config = TrainingConfig(
        model_name="B",
        epochs=5,
        batch_size=64,
        lr=1e-3,
        run_name="sanity_b",
        wandb_tags=["sanity"],
    )

    best = train(model, train_loader, val_loader, config, "B")
    print(f"Best val loss: {best:.4f}")


def sanity_c():
    print("\n" + "=" * 50)
    print("Model C Sanity Training")
    print("=" * 50)

    vecs = np.load("data/processed/vectors_c_train.npy")
    labels = np.load("data/processed/labels_10_train.npy")
    hlocs = np.load("data/processed/hit_locs_train.npy")
    with open("data/processed/indices_train.pkl", "rb") as f:
        indices = pickle.load(f)

    val_vecs = np.load("data/processed/vectors_c_val.npy")
    val_labels = np.load("data/processed/labels_10_val.npy")
    val_hlocs = np.load("data/processed/hit_locs_val.npy")
    with open("data/processed/indices_val.pkl", "rb") as f:
        val_indices = pickle.load(f)

    train_ds = PitchSequenceDataset(vecs, labels, hlocs, indices[:200], 400)
    val_ds = PitchSequenceDataset(val_vecs, val_labels, val_hlocs, val_indices[:50], 400)

    train_loader = DataLoader(train_ds, batch_size=8, shuffle=True)
    val_loader = DataLoader(val_ds, batch_size=8)

    model = PitchTransformer()
    config = TrainingConfig(
        model_name="C",
        epochs=3,
        batch_size=8,
        lr=1e-4,
        run_name="sanity_c",
        wandb_tags=["sanity"],
    )

    best = train(model, train_loader, val_loader, config, "C")
    print(f"Best val loss: {best:.4f}")


if __name__ == "__main__":
    sanity_b()
    sanity_c()

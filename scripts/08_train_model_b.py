"""Phase 5.5: Model B (OtrembaMLP) full training."""

import sys
from pathlib import Path

import torch
from torch.utils.data import DataLoader

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.dataset import PitchPointDataset
from src.models.otremba_mlp import OtrembaMLP
from src.training.train import TrainingConfig, train


def main():
    print("=" * 60)
    print("Phase 5.5: Model B Full Training")
    print("=" * 60)

    print("\nLoading data...")
    train_data = torch.load("data/processed/model_b_train.pt", weights_only=False)
    val_data = torch.load("data/processed/model_b_val.pt", weights_only=False)

    print(f"  Train: {train_data['vectors'].shape}")
    print(f"  Val:   {val_data['vectors'].shape}")

    train_ds = PitchPointDataset(train_data["vectors"], train_data["labels"])
    val_ds = PitchPointDataset(val_data["vectors"], val_data["labels"])

    train_loader = DataLoader(
        train_ds, batch_size=256, shuffle=True,
        num_workers=2, pin_memory=True,
    )
    val_loader = DataLoader(
        val_ds, batch_size=256, shuffle=False,
        num_workers=2, pin_memory=True,
    )

    print(f"  Train batches: {len(train_loader)}")
    print(f"  Val batches:   {len(val_loader)}")

    model = OtrembaMLP()
    n_params = sum(p.numel() for p in model.parameters())
    print(f"\nModel parameters: {n_params:,}")

    config = TrainingConfig(
        model_name="B",
        epochs=200,
        batch_size=256,
        lr=1e-3,
        weight_decay=1e-5,
        early_stopping_patience=10,
        run_name="model_b_full_v1",
        wandb_tags=["full", "model_b", "v1"],
    )

    print("\nStarting training...")
    print("-" * 60)
    best_val = train(model, train_loader, val_loader, config, "B")

    print(f"\n{'=' * 60}")
    print(f"Training complete!")
    print(f"Best val loss: {best_val:.4f}")
    print(f"Checkpoint: outputs/checkpoints/model_b_full_v1_best.pt")
    print(f"Log:        outputs/logs/train_model_b_full_v1.log")
    print(f"{'=' * 60}")


if __name__ == "__main__":
    main()

"""Unit tests for training loop."""

import torch
from torch.utils.data import DataLoader, TensorDataset

from src.models.otremba_mlp import OtrembaMLP
from src.training.train import (
    TrainingConfig,
    compute_loss_b,
    compute_loss_c,
    evaluate,
    train_one_epoch,
)


def _make_model_c_batch(batch_size=4, seq_len=10, device=torch.device("cpu")):
    """Helper: build a minimal Model C batch dict."""
    return {
        "sequence": torch.randn(batch_size, seq_len, 87).to(device),
        "pitch_result": torch.randint(0, 10, (batch_size,)).to(device),
        "hit_location": torch.randint(-1, 9, (batch_size,)).to(device),
    }


def test_training_config_defaults():
    cfg = TrainingConfig(model_name="B", epochs=10, batch_size=32, lr=1e-3)
    assert cfg.weight_decay == 1e-5
    assert cfg.pr_weight == 0.7
    assert cfg.hl_weight == 0.7
    assert cfg.cont_weight == 0.3
    assert cfg.early_stopping_patience == 5
    assert cfg.use_wandb is True


def test_compute_loss_b():
    model = OtrembaMLP()
    x = torch.randn(4, 77)
    y = torch.randint(0, 4, (4,))
    loss, m = compute_loss_b(model, (x, y), torch.device("cpu"))
    assert loss.requires_grad
    assert "loss" in m
    assert "accuracy" in m
    assert 0.0 <= m["accuracy"] <= 1.0


def test_train_one_epoch_b():
    model = OtrembaMLP()
    x = torch.randn(16, 77)
    y = torch.randint(0, 4, (16,))
    ds = TensorDataset(x, y)
    loader = DataLoader(ds, batch_size=4)
    optimizer = torch.optim.AdamW(model.parameters(), lr=1e-3)
    cfg = TrainingConfig(model_name="B", epochs=1, batch_size=4, lr=1e-3, use_wandb=False)
    metrics = train_one_epoch(model, loader, optimizer, None, torch.device("cpu"), cfg, "B")
    assert "loss" in metrics
    assert metrics["loss"] > 0.0


def test_evaluate_no_grad():
    model = OtrembaMLP()
    x = torch.randn(8, 77)
    y = torch.randint(0, 4, (8,))
    ds = TensorDataset(x, y)
    loader = DataLoader(ds, batch_size=4)
    cfg = TrainingConfig(model_name="B", epochs=1, batch_size=4, lr=1e-3, use_wandb=False)
    metrics = evaluate(model, loader, torch.device("cpu"), cfg, "B")
    assert "loss" in metrics
    assert "accuracy" in metrics

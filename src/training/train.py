"""Training loop with W&B integration for transition probability models."""

import time
from dataclasses import dataclass, field
from pathlib import Path

import torch
import torch.nn.functional as F
from torch.optim import AdamW
from torch.optim.lr_scheduler import CosineAnnealingLR
from torch.utils.data import DataLoader

import wandb

from src.utils.device import get_device
from src.utils.logger import get_logger


@dataclass
class TrainingConfig:
    model_name: str
    epochs: int
    batch_size: int
    lr: float
    weight_decay: float = 1e-5

    pr_weight: float = 0.7
    hl_weight: float = 0.7
    cont_weight: float = 0.3

    use_focal: bool = False   # focal loss 사용 여부 (class imbalance 대응)
    focal_gamma: float = 2.0  # focal loss gamma (2.0 권장)

    val_every: int = 1
    early_stopping_patience: int = 5

    output_dir: Path = field(default_factory=lambda: Path("outputs/checkpoints"))
    run_name: str = ""

    use_wandb: bool = True
    wandb_project: str = "transition-models"
    wandb_entity: str = "pitcheezy"
    wandb_tags: list = field(default_factory=list)


def focal_loss(logits: torch.Tensor, y: torch.Tensor, gamma: float = 2.0) -> torch.Tensor:
    """Focal loss: down-weights easy examples to focus learning on rare classes.

    FL(pt) = (1 - pt)^gamma * CE(logits, y)
    gamma=0 → standard cross-entropy, gamma=2 → standard focal loss.
    """
    ce = F.cross_entropy(logits, y, reduction="none")
    pt = torch.exp(-ce)  # softmax prob of the correct class
    return ((1 - pt) ** gamma * ce).mean()


def compute_loss_b(model, batch, device, config=None):
    """Single-task loss for Model B. Batch is (x, y) tuple."""
    x, y = batch[0].to(device), batch[1].to(device)
    logits = model(x)
    valid = y >= 0
    if not valid.any():
        return torch.tensor(0.0, device=device, requires_grad=True), {}
    use_focal = config is not None and getattr(config, "use_focal", False)
    if use_focal:
        loss = focal_loss(logits[valid], y[valid], gamma=config.focal_gamma)
    else:
        loss = F.cross_entropy(logits[valid], y[valid])
    acc = (logits.argmax(-1)[valid] == y[valid]).float().mean()
    return loss, {"loss": loss.item(), "accuracy": acc.item()}


def compute_loss_c(model, batch, device, config):
    """Multi-task loss for Model C. Batch is dict with sequence/pitch_result/hit_location."""
    seq = batch["sequence"].to(device)
    target_pr = batch["pitch_result"].to(device)
    target_hl = batch["hit_location"].to(device)

    output = model(seq)
    pr_logits = output[:, :10]
    hl_logits = output[:, 10:19]

    use_focal = getattr(config, "use_focal", False)
    gamma = getattr(config, "focal_gamma", 2.0)

    valid_pr = target_pr >= 0
    if valid_pr.any():
        loss_pr = (
            focal_loss(pr_logits[valid_pr], target_pr[valid_pr], gamma)
            if use_focal
            else F.cross_entropy(pr_logits[valid_pr], target_pr[valid_pr])
        )
    else:
        loss_pr = torch.tensor(0.0, device=device)

    valid_hl = target_hl >= 0
    if valid_hl.any():
        loss_hl = (
            focal_loss(hl_logits[valid_hl], target_hl[valid_hl], gamma)
            if use_focal
            else F.cross_entropy(hl_logits[valid_hl], target_hl[valid_hl])
        )
    else:
        loss_hl = torch.tensor(0.0, device=device)

    loss_cont = torch.tensor(0.0, device=device)  # continuous target: 추후 구현

    loss = config.pr_weight * loss_pr + config.hl_weight * loss_hl + config.cont_weight * loss_cont

    pr_acc = (
        (pr_logits.argmax(-1)[valid_pr] == target_pr[valid_pr]).float().mean()
        if valid_pr.any()
        else torch.tensor(0.0)
    )
    hl_acc = (
        (hl_logits.argmax(-1)[valid_hl] == target_hl[valid_hl]).float().mean()
        if valid_hl.any()
        else torch.tensor(0.0)
    )

    return loss, {
        "loss": loss.item(),
        "loss_pr": loss_pr.item(),
        "loss_hl": loss_hl.item(),
        "pr_accuracy": pr_acc.item(),
        "hl_accuracy": hl_acc.item(),
    }


def train_one_epoch(model, loader, optimizer, scheduler, device, config, model_type):
    """Run one training epoch and return averaged metrics dict."""
    model.train()
    metrics: dict[str, float] = {}
    n = 0
    for batch in loader:
        optimizer.zero_grad()
        if model_type == "B":
            loss, m = compute_loss_b(model, batch, device, config)
        else:
            loss, m = compute_loss_c(model, batch, device, config)
        loss.backward()
        optimizer.step()
        if scheduler is not None:
            scheduler.step()
        for k, v in m.items():
            metrics[k] = metrics.get(k, 0.0) + v
        n += 1
    return {k: v / max(n, 1) for k, v in metrics.items()}


def evaluate(model, loader, device, config, model_type):
    """Evaluate model on loader and return averaged metrics dict."""
    model.eval()
    metrics: dict[str, float] = {}
    n = 0
    with torch.no_grad():
        for batch in loader:
            if model_type == "B":
                _, m = compute_loss_b(model, batch, device, config)
            else:
                _, m = compute_loss_c(model, batch, device, config)
            for k, v in m.items():
                metrics[k] = metrics.get(k, 0.0) + v
            n += 1
    return {k: v / max(n, 1) for k, v in metrics.items()}


def save_checkpoint(model, optimizer, scheduler, epoch, val_metrics, config, is_best=False):
    """Save last checkpoint; also save best checkpoint when is_best=True."""
    config.output_dir.mkdir(parents=True, exist_ok=True)
    state = {
        "epoch": epoch,
        "model_state": model.state_dict(),
        "optimizer_state": optimizer.state_dict(),
        "scheduler_state": scheduler.state_dict() if scheduler is not None else None,
        "val_metrics": val_metrics,
    }
    torch.save(state, config.output_dir / f"{config.run_name}_last.pt")
    if is_best:
        torch.save(state, config.output_dir / f"{config.run_name}_best.pt")


def train(model, train_loader: DataLoader, val_loader: DataLoader, config: TrainingConfig, model_type: str) -> float:
    """Full training loop with W&B logging, early stopping, and checkpointing.

    Args:
        model: TransitionModel instance (OtrembaMLP or PitchTransformer).
        train_loader: DataLoader for training set.
        val_loader: DataLoader for validation set.
        config: TrainingConfig with hyperparameters and logging settings.
        model_type: "B" or "C" — selects loss function.

    Returns:
        Best validation loss achieved.
    """
    device = get_device()
    model = model.to(device)
    logger = get_logger("train", f"outputs/logs/train_{config.run_name}.log")

    optimizer = AdamW(model.parameters(), lr=config.lr, weight_decay=config.weight_decay)
    total_steps = len(train_loader) * config.epochs
    scheduler = CosineAnnealingLR(optimizer, T_max=total_steps) if total_steps > 0 else None

    if config.use_wandb:
        wandb.init(
            project=config.wandb_project,
            entity=config.wandb_entity,
            name=config.run_name,
            tags=config.wandb_tags + [f"model_{model_type}"],
            config={k: str(v) if isinstance(v, Path) else v for k, v in config.__dict__.items()},
        )

    logger.info(f"Training {config.run_name} on {device}, model_type={model_type}")
    logger.info(f"Train batches: {len(train_loader)}, Val batches: {len(val_loader)}")

    best_val = float("inf")
    patience = 0

    for epoch in range(config.epochs):
        t0 = time.time()

        train_m = train_one_epoch(model, train_loader, optimizer, scheduler, device, config, model_type)
        val_m = evaluate(model, val_loader, device, config, model_type) if epoch % config.val_every == 0 else {}

        elapsed = time.time() - t0
        lr = optimizer.param_groups[0]["lr"]

        msg = (
            f"Epoch {epoch + 1}/{config.epochs} ({elapsed:.1f}s, lr={lr:.2e})"
            f" | train_loss={train_m.get('loss', 0):.4f}"
        )
        if val_m:
            msg += f" | val_loss={val_m.get('loss', 0):.4f}"
        logger.info(msg)
        print(msg)

        if config.use_wandb:
            log = {f"train/{k}": v for k, v in train_m.items()}
            log.update({f"val/{k}": v for k, v in val_m.items()})
            log.update({"epoch": epoch, "lr": lr, "epoch_time": elapsed})
            wandb.log(log)

        if val_m:
            cur = val_m.get("loss", float("inf"))
            is_best = cur < best_val
            if is_best:
                best_val = cur
                patience = 0
            else:
                patience += 1
            save_checkpoint(model, optimizer, scheduler, epoch, val_m, config, is_best)
            if patience >= config.early_stopping_patience:
                logger.info(f"Early stopping at epoch {epoch + 1} (patience={patience})")
                break

    if config.use_wandb:
        wandb.finish()

    logger.info(f"Done. Best val loss: {best_val:.4f}")
    return best_val

"""Fixed, point-supervised CV15 development model; no detection or abstention claim.

Training accepts only images and legacy point labels from its training partition.
There is no validation input, checkpoint selection, augmentation, or early stopping.
The heatmap is a normalized training distribution, not calibrated confidence.
"""

from __future__ import annotations

# Import Arrow through src before torch (docs/H1_ARROW_CRASH_2026-09-23.md).
# isort: off
import src as _src  # noqa: F401
# isort: on

import hashlib
import math
import re
from io import BytesIO
from numbers import Integral
from pathlib import Path
from typing import Any

import numpy as np
import torch
from PIL import Image
from torch import nn
from torch.nn import functional as F

SCHEMA = "local_point_heatmap_v1"
INPUT_WIDTH = 192
INPUT_HEIGHT = 128
HEATMAP_WIDTH = 48
HEATMAP_HEIGHT = 32
SIGMA_CELLS = 1.5
SEEDS = (42, 43, 44)
EPOCHS = 20
BATCH_SIZE = 8
LEARNING_RATE = 0.001
WEIGHT_DECAY = 0.0001
THREADS = 4


class PointModelError(ValueError):
    """Reject data or provenance that does not match the frozen experiment."""


def fixed_config() -> dict[str, Any]:
    """Return a fresh, JSON-compatible description of the fixed model and training."""
    return {
        "input_size_wh": [INPUT_WIDTH, INPUT_HEIGHT],
        "input_channels": 3,
        "input_dtype": "float32",
        "input_range": [0.0, 1.0],
        "preprocessing": "Pillow RGB, BILINEAR resize, divide by 255, CHW",
        "architecture": [
            {"in": 3, "out": 16, "kernel": 3, "stride": 2, "padding": 1, "relu": True},
            {"in": 16, "out": 32, "kernel": 3, "stride": 2, "padding": 1, "relu": True},
            {"in": 32, "out": 32, "kernel": 3, "stride": 1, "padding": 1, "relu": True},
            {"in": 32, "out": 1, "kernel": 1, "stride": 1, "padding": 0, "relu": False},
        ],
        "parameter_count": 14369,
        "heatmap_size_wh": [HEATMAP_WIDTH, HEATMAP_HEIGHT],
        "lattice": "u=(column+0.5)/width; v=(row+0.5)/height",
        "gaussian_sigma_cells": SIGMA_CELLS,
        "target_distribution": "unit-mass Gaussian on the finite heatmap lattice",
        "objective": "mean spatial soft-label cross entropy",
        "coordinate_decoder": "spatial softmax expected pixel-center coordinates",
        "epochs": EPOCHS,
        "batch_size": BATCH_SIZE,
        "optimizer": "AdamW",
        "learning_rate": LEARNING_RATE,
        "weight_decay": WEIGHT_DECAY,
        "optimizer_betas": [0.9, 0.999],
        "optimizer_eps": 1e-8,
        "optimizer_foreach": False,
        "optimizer_fused": False,
        "threads": THREADS,
        "allowed_seeds": list(SEEDS),
        "shuffle": "CPU torch.Generator seeded once; randperm each epoch",
        "augmentation": None,
        "early_stopping": False,
        "checkpoint_selection": "fixed final epoch",
        "semantics": "conditional legacy manual-point regression",
        "calibrated_confidence": False,
        "verified_abstention": False,
    }


def _float_tensor(value: Any, name: str) -> torch.Tensor:
    if not isinstance(value, (np.ndarray, torch.Tensor)):
        raise PointModelError(f"{name} must be a float32 numpy array or torch tensor")
    try:
        tensor = torch.as_tensor(value)
    except (TypeError, ValueError, RuntimeError) as exc:
        raise PointModelError(f"{name} cannot be represented as a tensor") from exc
    if tensor.dtype != torch.float32 or tensor.layout != torch.strided:
        raise PointModelError(f"{name} must be a dense float32 tensor")
    return tensor


def _images(value: Any) -> torch.Tensor:
    images = _float_tensor(value, "images")
    if images.ndim != 4 or tuple(images.shape[1:]) != (3, INPUT_HEIGHT, INPUT_WIDTH):
        raise PointModelError("images must have shape [N, 3, 128, 192]")
    if len(images) == 0:
        raise PointModelError("images must contain at least one image")
    if not torch.isfinite(images).all().item():
        raise PointModelError("images must be finite")
    if (images < 0).any().item() or (images > 1).any().item():
        raise PointModelError("images must be in [0, 1]")
    return images


def _points(value: Any) -> torch.Tensor:
    points = _float_tensor(value, "normalized_points")
    if points.ndim != 2 or points.shape[1] != 2 or len(points) == 0:
        raise PointModelError("normalized_points must have shape [N, 2] with N > 0")
    if not torch.isfinite(points).all().item():
        raise PointModelError("normalized_points must be finite")
    if (points < 0).any().item() or (points > 1).any().item():
        raise PointModelError("normalized_points must be in [0, 1]; no clipping is performed")
    return points


def _logits(value: Any) -> torch.Tensor:
    logits = _float_tensor(value, "logits")
    if logits.ndim != 4 or tuple(logits.shape[1:]) != (1, HEATMAP_HEIGHT, HEATMAP_WIDTH):
        raise PointModelError("logits must have shape [N, 1, 32, 48]")
    if len(logits) == 0 or not torch.isfinite(logits).all().item():
        raise PointModelError("logits must be nonempty and finite")
    return logits


def _device(device: str) -> torch.device:
    if device not in ("cpu", "cuda"):
        raise PointModelError("device must be explicitly 'cpu' or 'cuda'")
    if device == "cuda" and not torch.cuda.is_available():
        raise PointModelError("CUDA was requested but is unavailable; no fallback is allowed")
    return torch.device(device)


def _seed(seed: int) -> int:
    if isinstance(seed, bool) or not isinstance(seed, Integral) or seed not in SEEDS:
        raise PointModelError(f"seed must be one of {SEEDS}")
    return int(seed)


def prepare_rgb_image(image: Image.Image) -> torch.Tensor:
    """Convert one already-decoded image to the fixed CPU CHW float32 representation."""
    if not isinstance(image, Image.Image) or image.width < 1 or image.height < 1:
        raise PointModelError("image must be a nonempty Pillow image")
    resized = image.convert("RGB").resize(
        (INPUT_WIDTH, INPUT_HEIGHT), resample=Image.Resampling.BILINEAR
    )
    array = np.asarray(resized, dtype=np.float32) / np.float32(255.0)
    return torch.from_numpy(np.ascontiguousarray(array.transpose(2, 0, 1)))


class TinyPointHeatmap(nn.Module):
    """Predict one spatial logit per fixed heatmap cell, without a presence head."""

    def __init__(self) -> None:
        super().__init__()
        self.layers = nn.Sequential(
            nn.Conv2d(3, 16, 3, stride=2, padding=1),
            nn.ReLU(),
            nn.Conv2d(16, 32, 3, stride=2, padding=1),
            nn.ReLU(),
            nn.Conv2d(32, 32, 3, stride=1, padding=1),
            nn.ReLU(),
            nn.Conv2d(32, 1, 1),
        )

    def forward(self, images: torch.Tensor) -> torch.Tensor:
        """Return unnormalized logits of shape [N, 1, 32, 48]."""
        if (
            not isinstance(images, torch.Tensor)
            or images.dtype != torch.float32
            or images.ndim != 4
            or tuple(images.shape[1:]) != (3, INPUT_HEIGHT, INPUT_WIDTH)
            or len(images) == 0
        ):
            raise PointModelError("model input must be float32 [N, 3, 128, 192] with N > 0")
        return self.layers(images)


def gaussian_targets(normalized_points: Any) -> torch.Tensor:
    """Build unit-mass Gaussian labels with sigma 1.5 cells on the center lattice."""
    points = _points(normalized_points)
    columns = torch.arange(HEATMAP_WIDTH, dtype=points.dtype, device=points.device) + 0.5
    rows = torch.arange(HEATMAP_HEIGHT, dtype=points.dtype, device=points.device) + 0.5
    dx = columns[None, None, :] - points[:, 0, None, None] * HEATMAP_WIDTH
    dy = rows[None, :, None] - points[:, 1, None, None] * HEATMAP_HEIGHT
    log_density = -(dx.square() + dy.square()) / (2 * SIGMA_CELLS**2)
    # log-softmax normalization also remains stable at the image boundaries.
    return F.softmax(log_density.flatten(1), dim=1).reshape(-1, 1, HEATMAP_HEIGHT, HEATMAP_WIDTH)


def softargmax_points(logits: Any) -> torch.Tensor:
    """Decode [u, v] using normalized cell centers; outputs are not confidence scores."""
    logits = _logits(logits)
    probability = F.softmax(logits.flatten(1), dim=1).reshape(-1, HEATMAP_HEIGHT, HEATMAP_WIDTH)
    columns = (
        torch.arange(HEATMAP_WIDTH, dtype=logits.dtype, device=logits.device) + 0.5
    ) / HEATMAP_WIDTH
    rows = (
        torch.arange(HEATMAP_HEIGHT, dtype=logits.dtype, device=logits.device) + 0.5
    ) / HEATMAP_HEIGHT
    u = (probability * columns[None, None, :]).sum(dim=(1, 2))
    v = (probability * rows[None, :, None]).sum(dim=(1, 2))
    return torch.stack((u, v), dim=1)


def point_loss(logits: Any, normalized_points: Any) -> torch.Tensor:
    """Return mean spatial soft-label cross entropy for training points only."""
    logits = _logits(logits)
    points = _points(normalized_points)
    if len(logits) != len(points):
        raise PointModelError("logits and normalized_points must have equal batch sizes")
    if logits.device != points.device:
        raise PointModelError("logits and normalized_points must be on the same device")
    target = gaussian_targets(points).flatten(1)
    return -(target * F.log_softmax(logits.flatten(1), dim=1)).sum(dim=1).mean()


def _runtime(device: torch.device) -> dict[str, Any]:
    return {
        "torch_version": str(torch.__version__),
        "device": device.type,
        "device_name": (
            torch.cuda.get_device_name(torch.cuda.current_device())
            if device.type == "cuda"
            else "CPU"
        ),
        "cuda_runtime": torch.version.cuda,
        "threads": torch.get_num_threads(),
        "deterministic_algorithms": torch.are_deterministic_algorithms_enabled(),
        "cudnn_deterministic": torch.backends.cudnn.deterministic,
        "cudnn_benchmark": torch.backends.cudnn.benchmark,
        "cudnn_allow_tf32": torch.backends.cudnn.allow_tf32,
    }


def train_point_model(
    train_images: Any, normalized_points: Any, *, seed: int, device: str
) -> tuple[TinyPointHeatmap, dict[str, Any]]:
    """Train exactly 20 epochs and return the final model and a CPU-only checkpoint.

    Only training images and points are accepted. Evaluation must be performed by a
    separate caller after all preregistered checkpoints have been saved and sealed.
    """
    seed = _seed(seed)
    target_device = _device(device)
    images = _images(train_images).detach().cpu().clone()
    points = _points(normalized_points).detach().cpu().clone()
    if len(images) != len(points):
        raise PointModelError("train_images and normalized_points must have equal lengths")
    torch.set_num_threads(THREADS)
    torch.manual_seed(seed)
    if target_device.type == "cuda":
        torch.cuda.manual_seed_all(seed)
    permutation_generator = torch.Generator(device="cpu").manual_seed(seed)
    was_deterministic = torch.are_deterministic_algorithms_enabled()
    was_warn_only = torch.is_deterministic_algorithms_warn_only_enabled()
    torch.use_deterministic_algorithms(True)
    try:
        with torch.backends.cudnn.flags(
            enabled=True, benchmark=False, deterministic=True, allow_tf32=False
        ):
            model = TinyPointHeatmap().to(target_device).train()
            optimizer = torch.optim.AdamW(
                model.parameters(),
                lr=LEARNING_RATE,
                weight_decay=WEIGHT_DECAY,
                betas=(0.9, 0.999),
                eps=1e-8,
                foreach=False,
                fused=False,
            )
            train_losses = []
            optimizer_steps = 0
            for _ in range(EPOCHS):
                permutation = torch.randperm(len(images), generator=permutation_generator)
                total_loss = 0.0
                for start in range(0, len(images), BATCH_SIZE):
                    indices = permutation[start : start + BATCH_SIZE]
                    batch_images = images[indices].to(target_device)
                    batch_points = points[indices].to(target_device)
                    optimizer.zero_grad(set_to_none=True)
                    loss = point_loss(model(batch_images), batch_points)
                    if not torch.isfinite(loss).item():
                        raise PointModelError("training produced nonfinite loss")
                    loss.backward()
                    optimizer.step()
                    total_loss += float(loss.detach().cpu()) * len(indices)
                    optimizer_steps += 1
                train_losses.append(total_loss / len(images))
            model.eval()
            metadata = {
                "seed": seed,
                "config": fixed_config(),
                "train_count": len(images),
                "epochs_completed": EPOCHS,
                "optimizer_steps": optimizer_steps,
                "train_losses": train_losses,
                "runtime": _runtime(target_device),
            }
            checkpoint = {
                "schema": SCHEMA,
                "metadata": metadata,
                "state_dict": {
                    name: value.detach().cpu().clone() for name, value in model.state_dict().items()
                },
            }
            return model, checkpoint
    finally:
        torch.use_deterministic_algorithms(was_deterministic, warn_only=was_warn_only)


def _checkpoint_metadata(checkpoint: Any) -> dict[str, Any]:
    if not isinstance(checkpoint, dict) or checkpoint.get("schema") != SCHEMA:
        raise PointModelError("checkpoint schema does not match CV15")
    metadata = checkpoint.get("metadata")
    if not isinstance(metadata, dict) or metadata.get("config") != fixed_config():
        raise PointModelError("checkpoint metadata does not match the fixed config")
    _seed(metadata.get("seed"))
    count = metadata.get("train_count")
    if isinstance(count, bool) or not isinstance(count, int) or count < 1:
        raise PointModelError("checkpoint train_count must be a positive integer")
    if metadata.get("epochs_completed") != EPOCHS:
        raise PointModelError("checkpoint must be from the fixed final epoch")
    if metadata.get("optimizer_steps") != EPOCHS * math.ceil(count / BATCH_SIZE):
        raise PointModelError("checkpoint optimizer_steps do not match the fixed training")
    losses = metadata.get("train_losses")
    if (
        not isinstance(losses, list)
        or len(losses) != EPOCHS
        or any(
            isinstance(loss, bool)
            or not isinstance(loss, (int, float))
            or not math.isfinite(loss)
            or loss < 0
            for loss in losses
        )
    ):
        raise PointModelError("checkpoint must record a finite loss for every epoch")
    if not isinstance(metadata.get("runtime"), dict):
        raise PointModelError("checkpoint must record training runtime metadata")
    return metadata


def load_point_model(
    checkpoint_path: str | Path, *, device: str, expected_sha256: str
) -> tuple[TinyPointHeatmap, dict[str, Any]]:
    """Load the exact SHA-256-verified checkpoint bytes without downloads or fallback."""
    target_device = _device(device)
    if (
        not isinstance(expected_sha256, str)
        or re.fullmatch(r"[a-f0-9]{64}", expected_sha256) is None
    ):
        raise PointModelError("expected_sha256 must be a full lowercase SHA-256")
    encoded = Path(checkpoint_path).read_bytes()
    if hashlib.sha256(encoded).hexdigest() != expected_sha256:
        raise PointModelError("checkpoint SHA-256 does not match the sealed artifact")
    try:
        checkpoint = torch.load(BytesIO(encoded), map_location="cpu", weights_only=True)
        metadata = _checkpoint_metadata(checkpoint)
        model = TinyPointHeatmap()
        model.load_state_dict(checkpoint["state_dict"], strict=True)
    except (KeyError, RuntimeError, TypeError, ValueError) as exc:
        raise PointModelError(f"invalid CV15 checkpoint: {exc}") from exc
    if any(not torch.isfinite(parameter).all().item() for parameter in model.parameters()):
        raise PointModelError("checkpoint parameters must be finite")
    torch.set_num_threads(THREADS)
    return model.to(target_device).eval(), metadata


def predict_points(model: TinyPointHeatmap, images: Any, *, device: str) -> torch.Tensor:
    """Return CPU float32 normalized points for every input; no learned abstention."""
    target_device = _device(device)
    images = _images(images)
    if not isinstance(model, TinyPointHeatmap):
        raise PointModelError("model must be a TinyPointHeatmap")
    actual_device = next(model.parameters()).device
    if actual_device.type != target_device.type:
        raise PointModelError("model device does not match the explicitly requested device")
    torch.set_num_threads(THREADS)
    model.eval()
    predictions = []
    with torch.inference_mode():
        for start in range(0, len(images), BATCH_SIZE):
            batch = images[start : start + BATCH_SIZE].to(target_device)
            predictions.append(softargmax_points(model(batch)).cpu())
    return torch.cat(predictions, dim=0)

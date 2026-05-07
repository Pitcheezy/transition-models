"""Evaluation loops for Model B / Model C and statistical baselines."""

from collections import Counter

import numpy as np
import torch
import torch.nn.functional as F

from src.utils.device import get_device


def evaluate_model_b(model, test_loader) -> dict:
    """Run inference on PitchPointDataset loader.

    Args:
        model: OtrembaMLP (or any model returning (batch, 4) logits).
        test_loader: DataLoader yielding (x, y) tuples.

    Returns:
        Dict with 'probs' (N, 4) and 'targets' (N,).
    """
    device = get_device()
    model = model.to(device).eval()

    all_probs, all_targets = [], []
    with torch.no_grad():
        for x, y in test_loader:
            logits = model(x.to(device))
            all_probs.append(F.softmax(logits, dim=-1).cpu().numpy())
            all_targets.append(y.numpy())

    return {
        "probs": np.concatenate(all_probs),
        "targets": np.concatenate(all_targets),
    }


def evaluate_model_c(model, test_loader) -> dict:
    """Run multi-task inference on PitchSequenceDataset loader.

    Args:
        model: PitchTransformer returning (batch, 24) logits.
        test_loader: DataLoader yielding dicts with 'sequence',
                     'pitch_result', 'hit_location'.

    Returns:
        Dict with pr_probs (N, 10), hl_probs (N, 9),
        pr_targets (N,), hl_targets (N,).
    """
    device = get_device()
    model = model.to(device).eval()

    all_pr_probs, all_hl_probs = [], []
    all_pr_targets, all_hl_targets = [], []

    with torch.no_grad():
        for batch in test_loader:
            output = model(batch["sequence"].to(device))
            all_pr_probs.append(F.softmax(output[:, :10], dim=-1).cpu().numpy())
            all_hl_probs.append(F.softmax(output[:, 10:19], dim=-1).cpu().numpy())
            all_pr_targets.append(batch["pitch_result"].numpy())
            all_hl_targets.append(batch["hit_location"].numpy())

    return {
        "pr_probs": np.concatenate(all_pr_probs),
        "hl_probs": np.concatenate(all_hl_probs),
        "pr_targets": np.concatenate(all_pr_targets),
        "hl_targets": np.concatenate(all_hl_targets),
    }


def baseline_majority(targets: np.ndarray, num_classes: int) -> np.ndarray:
    """Always predict the most frequent class (hard baseline).

    Analogous to Model A predicting the modal pitch outcome regardless of state.

    Args:
        targets: (N,) integer labels (< 0 ignored for counting).
        num_classes: K.

    Returns:
        (N, K) one-hot probability array where majority class = 1.
    """
    counts = Counter(int(v) for v in targets[targets >= 0])
    majority = counts.most_common(1)[0][0]
    probs = np.zeros((len(targets), num_classes))
    probs[:, majority] = 1.0
    return probs


def baseline_empirical(targets: np.ndarray, num_classes: int) -> np.ndarray:
    """Predict the empirical class distribution (soft baseline).

    Every sample gets the same probability vector = observed class frequencies.
    Equivalent to maximum-likelihood estimate without any features.

    Args:
        targets: (N,) integer labels (< 0 ignored for counting).
        num_classes: K.

    Returns:
        (N, K) probability array, same row repeated N times.
    """
    counts = Counter(int(v) for v in targets[targets >= 0])
    total = sum(counts.values())
    base_probs = np.zeros(num_classes)
    for k, v in counts.items():
        base_probs[k] = v / total
    return np.tile(base_probs, (len(targets), 1))

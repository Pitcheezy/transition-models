"""Evaluation metrics for transition probability models."""

import numpy as np
from sklearn.metrics import confusion_matrix


def cross_entropy(probs: np.ndarray, targets: np.ndarray, eps: float = 1e-12) -> float:
    """Average cross-entropy loss.

    Args:
        probs: (N, K) softmax probabilities.
        targets: (N,) integer class labels. Values < 0 are skipped.
        eps: clipping floor to avoid log(0).

    Returns:
        Scalar mean CE, or nan if no valid samples.
    """
    valid = targets >= 0
    if not valid.any():
        return float("nan")
    p = probs[valid]
    t = targets[valid]
    log_p = np.log(np.clip(p[np.arange(len(t)), t], eps, 1.0))
    return float(-log_p.mean())


def brier_score(probs: np.ndarray, targets: np.ndarray, num_classes: int) -> float:
    """Multi-class Brier score (lower is better).

    Brier = mean over samples of sum_k (p_k - y_k)^2,
    where y is the one-hot encoding of the true class.

    Args:
        probs: (N, K) probabilities.
        targets: (N,) integer labels (< 0 skipped).
        num_classes: K.

    Returns:
        Scalar mean Brier score, or nan if no valid samples.
    """
    valid = targets >= 0
    if not valid.any():
        return float("nan")
    p = probs[valid]
    t = targets[valid]
    one_hot = np.eye(num_classes)[t]
    return float(((p - one_hot) ** 2).sum(axis=1).mean())


def top_k_accuracy(probs: np.ndarray, targets: np.ndarray, k: int = 3) -> float:
    """Top-k accuracy: fraction of samples where true class is in top-k predictions.

    Args:
        probs: (N, K) probabilities.
        targets: (N,) integer labels (< 0 skipped).
        k: number of top predictions to consider.

    Returns:
        Scalar accuracy in [0, 1], or nan if no valid samples.
    """
    valid = targets >= 0
    if not valid.any():
        return float("nan")
    p = probs[valid]
    t = targets[valid]
    top_k_idx = np.argsort(p, axis=1)[:, -k:]
    correct = np.any(top_k_idx == t[:, None], axis=1)
    return float(correct.mean())


def per_class_metrics(probs: np.ndarray, targets: np.ndarray, num_classes: int) -> dict:
    """Per-class accuracy and confusion matrix.

    Args:
        probs: (N, K) probabilities.
        targets: (N,) integer labels (< 0 skipped).
        num_classes: K.

    Returns:
        Dict with 'confusion_matrix' (K, K) and 'per_class_accuracy' (K,).
        Returns None if no valid samples.
    """
    valid = targets >= 0
    if not valid.any():
        return None
    p = probs[valid]
    t = targets[valid]
    pred = p.argmax(axis=1)
    cm = confusion_matrix(t, pred, labels=list(range(num_classes)))
    per_class_acc = cm.diagonal() / np.maximum(cm.sum(axis=1), 1)
    return {
        "confusion_matrix": cm,
        "per_class_accuracy": per_class_acc,
    }

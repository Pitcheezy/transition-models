"""Probability metrics and identity-aware comparisons for point classifiers."""

import numpy as np
from sklearn.metrics import confusion_matrix, f1_score

from src.data.point_data import CLASS_NAMES


def calibration_error(confidence: np.ndarray, outcomes: np.ndarray, bins: int = 15) -> float:
    """Compute equal-width expected calibration error, including probabilities 0 and 1."""
    if bins < 1 or len(confidence) != len(outcomes) or not len(confidence):
        raise ValueError("Invalid calibration inputs")
    indices = np.minimum((confidence * bins).astype(int), bins - 1)
    error = 0.0
    for index in range(bins):
        mask = indices == index
        if mask.any():
            error += mask.mean() * abs(confidence[mask].mean() - outcomes[mask].mean())
    return float(error)


def probability_metrics(probs: np.ndarray, targets: np.ndarray) -> dict:
    """Report proper scores, top-label/classwise calibration, and rare-event mass."""
    probs = np.asarray(probs, dtype=np.float64)
    targets = np.asarray(targets)
    if (
        probs.shape != (len(targets), 10)
        or not len(targets)
        or not np.issubdtype(targets.dtype, np.integer)
        or np.any((targets < 0) | (targets >= 10))
    ):
        raise ValueError("Invalid probability/target shapes or classes")
    if (
        not np.isfinite(probs).all()
        or np.any((probs < 0) | (probs > 1))
        or not np.allclose(probs.sum(axis=1), 1, atol=1e-6)
    ):
        raise ValueError("Expected finite normalized probabilities")
    prediction = probs.argmax(axis=1)
    truth = np.eye(10)[targets]
    cm = confusion_matrix(targets, prediction, labels=np.arange(10))
    counts = cm.sum(axis=1)
    return {
        "n": len(targets),
        "top1": float(np.mean(prediction == targets)),
        "top3": float(
            np.mean(np.any(np.argsort(probs, axis=1)[:, -3:] == targets[:, None], axis=1))
        ),
        "ce": float(-np.log(np.clip(probs[np.arange(len(targets)), targets], 1e-12, 1)).mean()),
        "brier": float(np.square(probs - truth).sum(axis=1).mean()),
        "ece_15": calibration_error(probs.max(axis=1), prediction == targets),
        "macro_f1": float(
            f1_score(targets, prediction, labels=np.arange(10), average="macro", zero_division=0)
        ),
        "confusion_matrix": cm.tolist(),
        "per_class": {
            str(name): {
                "support": int(counts[i]),
                "recall": float(cm[i, i] / counts[i]) if counts[i] else None,
                "predicted_count": int((prediction == i).sum()),
                "mean_probability": float(probs[:, i].mean()),
                "observed_frequency": float(truth[:, i].mean()),
                "brier": float(np.square(probs[:, i] - truth[:, i]).mean()),
                "ece_15": calibration_error(probs[:, i], truth[:, i]),
            }
            for i, name in enumerate(CLASS_NAMES)
        },
    }


def align_predictions(reference: dict, candidate: dict) -> np.ndarray:
    """Align a candidate by exact pitch identity; never silently intersect cohorts."""
    for data in (reference, candidate):
        if not {"pitch_ids", "targets", "probs", "class_names"}.issubset(data):
            raise ValueError("Predictions require pitch IDs, targets, and class order")
        if not np.array_equal(data["class_names"], CLASS_NAMES):
            raise ValueError("Prediction class order mismatch")
        ids = np.asarray(data["pitch_ids"])
        if ids.shape != (len(data["targets"]), 3) or not np.issubdtype(ids.dtype, np.integer):
            raise ValueError("Invalid prediction IDs")
        if len(np.unique(ids, axis=0)) != len(ids):
            raise ValueError("Duplicate prediction IDs")
        probability_metrics(data["probs"], data["targets"])
    reference_keys = [tuple(row) for row in reference["pitch_ids"]]
    lookup = {tuple(row): i for i, row in enumerate(candidate["pitch_ids"])}
    if set(reference_keys) != set(lookup):
        raise ValueError("Prediction cohorts differ")
    order = np.array([lookup[key] for key in reference_keys])
    if not np.array_equal(reference["targets"], candidate["targets"][order]):
        raise ValueError("Targets disagree for the same pitch")
    return candidate["probs"][order]

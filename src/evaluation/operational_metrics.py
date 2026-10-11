"""Calibration and clustered uncertainty for held-out operational experiments."""

import numpy as np
from scipy.optimize import minimize_scalar
from scipy.special import logsumexp


def temperature_scale(probs, temperature):
    """Normalize log probabilities after positive scalar temperature scaling."""
    if temperature <= 0:
        raise ValueError("Temperature must be positive")
    logits = np.log(np.clip(np.asarray(probs, dtype=float), 1e-12, 1)) / temperature
    return np.exp(logits - logsumexp(logits, axis=1, keepdims=True))


def fit_temperature(probs, targets):
    """Fit a scalar using only the explicitly supplied calibration holdout."""

    def objective(log_temperature):
        scaled = temperature_scale(probs, np.exp(log_temperature))
        return -np.log(scaled[np.arange(len(targets)), targets]).mean()

    result = minimize_scalar(objective, bounds=(-2.3, 2.3), method="bounded")
    if not result.success:
        raise RuntimeError("Calibration did not converge")
    return float(np.exp(result.x))


def game_interval(values, game_ids, repetitions=2000, seed=42):
    """Bootstrap game clusters for one or more per-pitch estimands."""
    values = np.asarray(values, dtype=float)
    if values.ndim == 1:
        values = values[:, None]
    if len(values) != len(game_ids) or not np.isfinite(values).all() or not len(values):
        raise ValueError("Invalid bootstrap observations")
    _, groups = np.unique(game_ids, return_inverse=True)
    counts = np.bincount(groups)
    sums = np.column_stack([np.bincount(groups, weights=v) for v in values.T])
    rng = np.random.default_rng(seed)
    samples = np.empty((repetitions, values.shape[1]))
    for i in range(repetitions):
        selected = rng.integers(len(counts), size=len(counts))
        samples[i] = sums[selected].sum(axis=0) / counts[selected].sum()
    return {
        "mean": values.mean(axis=0).tolist(),
        "ci95": np.quantile(samples, [0.025, 0.975], axis=0).T.tolist(),
        "games": len(counts),
        "repetitions": repetitions,
    }


def score_rows(probs, y):
    """Return CE and summed multiclass Brier per pitch."""
    ce = -np.log(np.clip(probs[np.arange(len(y)), y], 1e-12, 1))
    brier = np.square(probs - np.eye(probs.shape[1])[y]).sum(axis=1)
    return np.column_stack([ce, brier])


def reliability_bins(probabilities, outcomes, bins=10):
    """Return equal-frequency class reliability bins, including actual sample sizes."""
    order = np.argsort(probabilities, kind="stable")
    return [
        {
            "n": len(ix),
            "predicted": float(probabilities[ix].mean()),
            "observed": float(outcomes[ix].mean()),
        }
        for ix in np.array_split(order, bins)
        if len(ix)
    ]


def seed_game_interval(differences, game_ids, repetitions=2000):
    """Resample paired training seeds and games; three seeds provide limited precision."""
    differences = np.asarray(differences)
    if differences.ndim != 3 or differences.shape[1] != len(game_ids):
        raise ValueError("Expected seed x pitch x metric differences")
    _, groups = np.unique(game_ids, return_inverse=True)
    counts = np.bincount(groups)
    sums = np.array(
        [[np.bincount(groups, weights=col) for col in seed.T] for seed in differences]
    )  # seed x metric x game
    rng = np.random.default_rng(42)
    samples = []
    for _ in range(repetitions):
        chosen_seeds = rng.integers(len(sums), size=len(sums))
        chosen_games = rng.integers(len(counts), size=len(counts))
        totals = sums[chosen_seeds].mean(axis=0)[:, chosen_games].sum(axis=1)
        samples.append(totals / counts[chosen_games].sum())
    return {
        "mean": differences.mean(axis=(0, 1)).tolist(),
        "ci95": np.quantile(samples, [0.025, 0.975], axis=0).T.tolist(),
        "seeds": len(sums),
        "games": len(counts),
        "repetitions": repetitions,
        "scope": "paired seed and game resampling; only three training seeds",
    }

"""One-step, overlap-restricted policy evaluation on held-out logged outcomes."""

import numpy as np


def behavior_features(vectors):
    """Remove chosen action and its estimated physical/zone features from propensity inputs."""
    if np.asarray(vectors).ndim != 2 or np.asarray(vectors).shape[1] != 135:
        raise ValueError("Propensity input requires the complete operational 135d schema")
    return np.asarray(vectors)[:, 46:135]


def soft_greedy(costs, available, exploration=0.1):
    """Mix a minimizing action with uniform exploration over exactly the supported set."""
    if costs.shape != available.shape or np.any(available.sum(axis=1) < 2):
        raise ValueError("Each policy state requires at least two available actions")
    if not 0 <= exploration <= 1 or not np.isfinite(costs).all():
        raise ValueError("Invalid policy costs or exploration")
    chosen = np.where(available, costs, np.inf).argmin(axis=1)
    probs = exploration * available / available.sum(axis=1, keepdims=True)
    probs[np.arange(len(probs)), chosen] += 1 - exploration
    return probs, chosen


def dr_scores(policy, nuisance_q, actions, propensity, rewards, clip=None):
    """Return doubly robust run-cost scores and diagnostics; actions outside support get zero."""
    n = len(rewards)
    if policy.shape != nuisance_q.shape or len(actions) != n or np.any(propensity <= 0):
        raise ValueError("Invalid off-policy evaluation arrays")
    in_range = (actions >= 0) & (actions < policy.shape[1])
    logged_pi = np.zeros(n)
    logged_q = np.zeros(n)
    rows = np.flatnonzero(in_range)
    logged_pi[rows] = policy[rows, actions[rows]]
    logged_q[rows] = nuisance_q[rows, actions[rows]]
    weights = logged_pi / propensity
    if clip is not None:
        weights = np.minimum(weights, clip)
    scores = (policy * nuisance_q).sum(axis=1) + weights * (rewards - logged_q)
    sum_weights = float(weights.sum())
    return scores, {
        "weight_mean": float(weights.mean()),
        "weight_max": float(weights.max()),
        "weight_p95": float(np.quantile(weights, 0.95)),
        "effective_sample_size": float(sum_weights**2 / np.square(weights).sum())
        if sum_weights
        else 0,
        "snips_cost": float(np.dot(weights, rewards) / sum_weights) if sum_weights else None,
        "clip": clip,
    }

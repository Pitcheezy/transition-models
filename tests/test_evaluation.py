"""Unit tests for evaluation metrics and baselines."""

import numpy as np
import pytest

from src.evaluation.evaluate import baseline_empirical, baseline_majority
from src.evaluation.metrics import (
    brier_score,
    cross_entropy,
    per_class_metrics,
    top_k_accuracy,
)


def test_cross_entropy_perfect():
    probs = np.array([[1.0, 0.0], [0.0, 1.0]])
    targets = np.array([0, 1])
    assert cross_entropy(probs, targets) < 0.01


def test_cross_entropy_uniform():
    probs = np.array([[0.5, 0.5], [0.5, 0.5]])
    targets = np.array([0, 1])
    assert abs(cross_entropy(probs, targets) - np.log(2)) < 0.01


def test_cross_entropy_invalid_targets():
    probs = np.array([[0.5, 0.5], [0.5, 0.5], [0.5, 0.5]])
    targets = np.array([-1, 0, 1])
    ce = cross_entropy(probs, targets)
    assert abs(ce - np.log(2)) < 0.01


def test_cross_entropy_all_invalid():
    probs = np.array([[0.5, 0.5]])
    targets = np.array([-1])
    assert np.isnan(cross_entropy(probs, targets))


def test_brier_score_perfect():
    probs = np.array([[1.0, 0.0], [0.0, 1.0]])
    targets = np.array([0, 1])
    assert brier_score(probs, targets, 2) < 0.01


def test_brier_score_uniform():
    probs = np.array([[0.5, 0.5], [0.5, 0.5]])
    targets = np.array([0, 1])
    # sum((0.5 - 1)^2 + (0.5 - 0)^2) = 0.5, mean = 0.5
    assert abs(brier_score(probs, targets, 2) - 0.5) < 0.01


def test_top_k_accuracy_top1():
    probs = np.array([[0.1, 0.5, 0.4], [0.6, 0.3, 0.1]])
    targets = np.array([2, 0])
    # argmax: [1, 0] vs targets [2, 0] → 1 correct
    assert abs(top_k_accuracy(probs, targets, k=1) - 0.5) < 0.001


def test_top_k_accuracy_top2():
    probs = np.array([[0.1, 0.5, 0.4], [0.6, 0.3, 0.1]])
    targets = np.array([2, 0])
    # top-2: [[1,2], [0,1]] — 2 in first row, 0 in second row → both correct
    assert abs(top_k_accuracy(probs, targets, k=2) - 1.0) < 0.001


def test_top_k_accuracy_invalid_targets():
    probs = np.array([[0.5, 0.5], [0.5, 0.5], [0.5, 0.5]])
    targets = np.array([-1, 0, 1])
    # Only 2 valid: argmax=[0,0] vs [0,1] → 1 correct out of 2
    acc = top_k_accuracy(probs, targets, k=1)
    assert abs(acc - 0.5) < 0.001


def test_baseline_majority():
    targets = np.array([0, 0, 1, 0])
    probs = baseline_majority(targets, num_classes=2)
    assert probs.shape == (4, 2)
    assert np.allclose(probs[:, 0], 1.0)
    assert np.allclose(probs[:, 1], 0.0)


def test_baseline_empirical():
    targets = np.array([0, 0, 1, 1, 2])
    probs = baseline_empirical(targets, num_classes=3)
    assert probs.shape == (5, 3)
    expected = np.array([0.4, 0.4, 0.2])
    assert np.allclose(probs[0], expected)
    assert np.allclose(probs.sum(axis=1), 1.0)


def test_per_class_metrics_shape():
    probs = np.eye(3)[[0, 1, 2, 0]]  # perfect predictions for first 3
    targets = np.array([0, 1, 2, 0])
    pcm = per_class_metrics(probs, targets, 3)
    assert pcm["confusion_matrix"].shape == (3, 3)
    assert pcm["per_class_accuracy"].shape == (3,)
    assert np.allclose(pcm["per_class_accuracy"], 1.0)


def test_per_class_metrics_mixed():
    # class 0: 2 samples predicted [0, 0] → 100%
    # class 1: 2 samples predicted [1, 0] → 50%
    probs = np.array([[1.0, 0.0], [0.0, 1.0], [0.6, 0.4], [1.0, 0.0]])
    targets = np.array([0, 1, 0, 1])
    pcm = per_class_metrics(probs, targets, 2)
    assert pcm["per_class_accuracy"][0] == 1.0
    assert pcm["per_class_accuracy"][1] == 0.5

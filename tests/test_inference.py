"""Unit tests for inference wrappers."""

import numpy as np
import pytest
from pathlib import Path

from src.inference import TransitionModelB, TransitionModelC


@pytest.fixture
def dummy_b():
    return np.random.randn(77).astype(np.float32)


@pytest.fixture
def dummy_c():
    seq = np.random.randn(400, 87).astype(np.float32)
    seq[-1, 68:87] = 0.0  # sub-token mask
    return seq


def _b_available():
    return Path(TransitionModelB.DEFAULT_CHECKPOINT).exists()


def _c_available():
    return Path(TransitionModelC.DEFAULT_CHECKPOINT).exists()


def test_model_b_load():
    if not _b_available():
        pytest.skip("Model B checkpoint not found")
    model = TransitionModelB()
    assert model.num_classes == 4
    assert len(model.classes) == 4


def test_model_b_predict_single(dummy_b):
    if not _b_available():
        pytest.skip("Model B checkpoint not found")
    model = TransitionModelB()
    probs = model.predict(dummy_b)
    assert probs.shape == (4,)
    assert np.allclose(probs.sum(), 1.0, atol=1e-5)
    assert (probs >= 0).all()


def test_model_b_predict_batch():
    if not _b_available():
        pytest.skip("Model B checkpoint not found")
    model = TransitionModelB()
    batch = np.random.randn(5, 77).astype(np.float32)
    probs = model.predict(batch)
    assert probs.shape == (5, 4)
    assert np.allclose(probs.sum(axis=1), 1.0, atol=1e-5)


def test_model_b_top_k(dummy_b):
    if not _b_available():
        pytest.skip("Model B checkpoint not found")
    model = TransitionModelB()
    top3 = model.predict_top_k(dummy_b, k=3)
    assert len(top3) == 3
    assert all("class" in item and "probability" in item for item in top3)
    p = [item["probability"] for item in top3]
    assert p == sorted(p, reverse=True)


def test_model_c_load():
    if not _c_available():
        pytest.skip("Model C checkpoint not found")
    model = TransitionModelC()
    assert len(model.pr_classes) == 10
    assert len(model.hl_classes) == 9


def test_model_c_predict_single(dummy_c):
    if not _c_available():
        pytest.skip("Model C checkpoint not found")
    model = TransitionModelC()
    result = model.predict(dummy_c)
    assert result["pitch_result"].shape == (10,)
    assert result["hit_location"].shape == (9,)
    assert np.allclose(result["pitch_result"].sum(), 1.0, atol=1e-5)
    assert np.allclose(result["hit_location"].sum(), 1.0, atol=1e-5)


def test_model_c_predict_batch():
    if not _c_available():
        pytest.skip("Model C checkpoint not found")
    model = TransitionModelC()
    batch = np.random.randn(3, 400, 87).astype(np.float32)
    batch[:, -1, 68:87] = 0.0
    result = model.predict(batch)
    assert result["pitch_result"].shape == (3, 10)
    assert result["hit_location"].shape == (3, 9)


def test_model_c_top_k(dummy_c):
    if not _c_available():
        pytest.skip("Model C checkpoint not found")
    model = TransitionModelC()
    top3 = model.predict_top_k(dummy_c, k=3)
    assert len(top3) == 3
    assert all("class" in item and "probability" in item for item in top3)
    p = [item["probability"] for item in top3]
    assert p == sorted(p, reverse=True)

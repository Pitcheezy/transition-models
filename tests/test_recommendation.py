"""Exercise policy support boundaries without requiring large local checkpoints."""

from types import SimpleNamespace

import numpy as np
import pytest

from src.inference.recommendation import OperationalRecommender


def service(supported=True):
    recommender = OperationalRecommender.__new__(OperationalRecommender)
    recommender.selected = "test_model"
    recommender.report = {"models": {"empirical": {"temperature": 1.0}}}
    recommender.nuisance = {"propensity": {"temperature": 1.0}}
    recommender.kernel = np.zeros((288, 10))
    builder = SimpleNamespace(
        cutoff="2022-12-31",
        schema="test",
        build=lambda frame, action: np.zeros((1, 135)),
        available_actions=lambda frame: np.full((1, 9), supported),
    )
    recommender.model = SimpleNamespace(
        builder=builder, predict=lambda frame, action: np.full((1, 10), 0.1)
    )
    recommender.empirical = SimpleNamespace(predict=lambda frame, action: np.full((1, 10), 0.1))
    recommender.behavior = SimpleNamespace(predict=lambda x, num_threads: np.full((1, 17), 1 / 17))
    return recommender


def state():
    return {
        "game_date": "2024-09-30",
        "pitcher": 42,
        "balls": 1,
        "strikes": 2,
        "outs_when_up": 1,
        "inning": 3,
        "stand": "R",
        "p_throws": "R",
    }


def test_supported_recommendation_has_honest_probabilities():
    result = service().predict(state())
    assert result["recommendation"] is not None
    assert sum(c["policy_probability"] for c in result["candidates"]) == pytest.approx(1)
    assert result["target_location"] is None
    assert all(c["display_probabilities"]["foul"] is None for c in result["candidates"])


def test_unsupported_repertoire_withholds_recommendation():
    result = service(False).predict(state())
    assert result["recommendation"] is None
    assert len(result["candidates"]) == 9
    assert all(c["policy_probability"] == 0 for c in result["candidates"])


def test_ninth_inning_withholds_unevaluated_costs():
    result = service().predict({**state(), "inning": 9})
    assert result["recommendation"] is None
    assert all(c["expected_cost"] is None for c in result["candidates"])


def test_no_future_profiles_for_past_prediction():
    with pytest.raises(ValueError, match="cutoff"):
        service().predict({**state(), "game_date": "2022-12-31"})

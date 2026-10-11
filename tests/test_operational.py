"""Guard the time boundary, forbidden current-pitch inputs, and run-value accounting."""

import hashlib
import json
import pickle

import numpy as np
import pandas as pd
import pytest

from src.data.features import CONTINUOUS_FEATURES
from src.data.operational import OperationalFeatureBuilder, state_codes
from src.evaluation.operational_metrics import fit_temperature, game_interval, temperature_scale
from src.evaluation.policy_value import behavior_features, dr_scores, soft_greedy
from src.evaluation.run_value import (
    fallback_transition,
    fit_run_expectancy,
    observed_transitions,
    transition_cost,
)
from src.inference.operational import EmpiricalTransition, OperationalPredictor


def history_frame():
    rows = []
    for i in range(20):
        rows.append(
            {
                **{name: 1.0 + i / 10 for name in CONTINUOUS_FEATURES},
                "pitcher": 10 + i % 2,
                "game_date": "2022-06-01",
                "balls": 1,
                "strikes": 1,
                "outs_when_up": 0,
                "inning": 3,
                "on_1b": np.nan,
                "on_2b": np.nan,
                "on_3b": np.nan,
                "stand": "R",
                "p_throws": "R",
                "pitch_type": "FF" if i % 3 else "SL",
                "zone": 5,
                "description": "ball" if i % 2 else "called_strike",
                "events": None,
            }
        )
    return pd.DataFrame(rows)


def test_operational_features_ignore_all_current_physics_locations_and_outcomes():
    history = history_frame()
    builder = OperationalFeatureBuilder.fit(history)
    decision = history.iloc[:3].copy()
    decision["game_date"] = "2024-07-01"
    expected = builder.build(decision)
    forbidden = CONTINUOUS_FEATURES + ["zone", "description", "events"]
    np.testing.assert_array_equal(builder.build(decision.drop(columns=forbidden)), expected)
    decision[CONTINUOUS_FEATURES] = 9999
    decision["zone"] = 14
    decision["events"] = "home_run"
    np.testing.assert_array_equal(builder.build(decision), expected)
    np.testing.assert_array_equal(builder.build(decision, input_dim=77), expected[:, :77])


def test_profile_future_rows_and_backdated_decisions_are_rejected():
    history = history_frame()
    builder = OperationalFeatureBuilder.fit(history)
    with pytest.raises(ValueError, match="earlier"):
        builder.build(history)
    history.loc[0, "game_date"] = "2023-01-01"
    with pytest.raises(ValueError, match="Future"):
        OperationalFeatureBuilder.fit(history)


def test_unknown_pitcher_falls_back_without_inventing_supported_actions():
    builder = OperationalFeatureBuilder.fit(history_frame())
    decision = history_frame().iloc[:1].copy()
    decision["game_date"] = "2024-07-01"
    decision["pitcher"] = 9999
    assert np.isfinite(builder.build(decision, action="FF")).all()
    assert not builder.available_actions(decision).any()


@pytest.mark.parametrize(
    "outcome,runners,runs,new_runners", [(5, 7, 4, 0), (8, 7, 1, 7), (2, 4, 1, 1)]
)
def test_baseball_fallback_advancement(outcome, runners, runs, new_runners):
    next_state, scored = fallback_transition(runners * 12, outcome)
    assert scored == runs
    assert next_state == new_runners * 12


def test_two_strike_foul_stays_and_third_out_absorbs():
    state = (2 * 8) * 12 + 2
    assert fallback_transition(state, 1) == (state, 0)
    assert fallback_transition(state, 7) == (288, 0)


def test_observed_run_costs_telescope_over_completed_half_inning():
    frame = history_frame().iloc[:4].copy()
    frame["game_pk"] = 1
    frame["at_bat_number"] = [1, 1, 2, 3]
    frame["pitch_number"] = [1, 2, 1, 1]
    frame["inning_topbot"] = "Top"
    frame["outs_when_up"] = [0, 0, 1, 2]
    frame["balls"] = [0, 1, 0, 0]
    frame["strikes"] = [0, 0, 0, 0]
    frame["description"] = ["ball", "hit_into_play", "hit_into_play", "hit_into_play"]
    frame["events"] = [None, "home_run", "field_out", "field_out"]
    frame["bat_score"] = [0, 0, 1, 1]
    frame["post_bat_score"] = [0, 1, 1, 1]
    observations = observed_transitions(frame)
    assert len(observations) == 4
    values = fit_run_expectancy(observations)
    costs = transition_cost(observations, values)
    assert costs.sum() == pytest.approx(1 - values[state_codes(frame)[0]])
    assert observations.iloc[-1]["next_state"] == 288
    frame["inning"] = 9
    assert observed_transitions(frame).empty


def test_propensity_features_exclude_chosen_action_and_its_physical_estimates():
    builder = OperationalFeatureBuilder.fit(history_frame())
    frame = history_frame().iloc[:3].copy()
    frame["game_date"] = "2024-07-01"
    a, b = builder.build(frame, "FF"), builder.build(frame, "SL")
    assert not np.array_equal(a, b)
    np.testing.assert_array_equal(behavior_features(a), behavior_features(b))
    assert behavior_features(a).shape[1] == 89
    with pytest.raises(ValueError, match="complete"):
        behavior_features(a[:, :77])


def test_empirical_probabilities_backoff_and_ignore_recorded_outcome():
    frame = history_frame()
    model = EmpiricalTransition().fit(frame, np.arange(len(frame)) % 10)
    unseen = frame.iloc[:2].copy()
    unseen["outs_when_up"] = 2
    unseen["on_1b"] = 999
    p = model.predict(unseen, "CH")
    assert (p > 0).all()
    np.testing.assert_allclose(p.sum(axis=1), 1)
    unseen["events"] = "home_run"
    np.testing.assert_array_equal(p, model.predict(unseen, "CH"))


def test_temperature_fitting_improves_overconfident_calibration():
    y = np.tile([0, 0, 0, 1], 50)
    probabilities = np.tile([0.99, 0.01], (len(y), 1))
    temperature = fit_temperature(probabilities, y)
    calibrated = temperature_scale(probabilities, temperature)
    assert temperature > 1
    np.testing.assert_allclose(calibrated.mean(axis=0), [0.75, 0.25], atol=1e-5)


def test_policy_uses_only_supported_actions_and_rejects_empty_choices():
    costs = np.array([[0.2, 0.1, -3.0]])
    available = np.array([[True, True, False]])
    policy, choice = soft_greedy(costs, available)
    np.testing.assert_allclose(policy, [[0.05, 0.95, 0]])
    assert choice[0] == 1
    with pytest.raises(ValueError, match="at least two"):
        soft_greedy(costs, np.array([[True, False, False]]))


def test_doubly_robust_estimator_recovers_randomized_policy_value_with_wrong_q():
    # Balanced randomization makes the importance correction exact for constant action rewards.
    actions = np.tile([0, 1], 500)
    rewards = np.where(actions == 0, 0.4, -0.1)
    policy = np.tile([0.2, 0.8], (len(actions), 1))
    incorrect_q = np.tile([5.0, -2.0], (len(actions), 1))
    scores, diagnostics = dr_scores(
        policy, incorrect_q, actions, np.full(len(actions), 0.5), rewards
    )
    assert scores.mean() == pytest.approx(0.2 * 0.4 + 0.8 * -0.1)
    assert diagnostics["weight_mean"] == pytest.approx(1)
    assert diagnostics["snips_cost"] == pytest.approx(0)


def test_doubly_robust_estimator_recovers_value_with_correct_q_and_wrong_propensity():
    actions = np.tile([0, 1, -1], 100)
    rewards = np.where(actions == 0, 0.4, -0.1)
    policy = np.tile([0.2, 0.8], (len(actions), 1))
    exact_q = np.tile([0.4, -0.1], (len(actions), 1))
    scores, _ = dr_scores(policy, exact_q, actions, np.full(len(actions), 0.9), rewards)
    np.testing.assert_allclose(scores, 0, atol=1e-15)


def test_clustered_interval_retains_games_as_sampling_units():
    values = np.array([1.0, 1.0, 3.0, 3.0])
    result = game_interval(values, [10, 10, 20, 20], repetitions=1000)
    assert result["games"] == 2
    assert result["mean"] == [2]
    assert result["ci95"] == [[1, 3]]


def test_operational_runtime_rejects_legacy_checkpoint_and_modified_profile(tmp_path):
    builder = OperationalFeatureBuilder.fit(history_frame())
    data, run = tmp_path / "data", tmp_path / "run"
    data.mkdir()
    run.mkdir()
    profile = pickle.dumps(builder)
    (data / "feature_builder.pkl").write_bytes(profile)
    manifest = {
        "feature_schema": builder.schema,
        "profile_sha256": hashlib.sha256(profile).hexdigest(),
    }
    (data / "dataset_manifest.json").write_text(json.dumps(manifest))
    (run / "manifest.json").write_text(json.dumps({"status": "complete", "dataset": None}))
    with pytest.raises(ValueError, match="not trained"):
        OperationalPredictor(data, [run])
    manifest["profile_sha256"] = "different-profile"
    (data / "dataset_manifest.json").write_text(json.dumps(manifest))
    with pytest.raises(ValueError, match="hash mismatch"):
        OperationalPredictor(data, [run])


def test_operational_feature_builder_requires_a_known_decision_date():
    builder = OperationalFeatureBuilder.fit(history_frame())
    frame = history_frame().iloc[:1].copy()
    frame["game_date"] = None
    with pytest.raises(ValueError, match="Missing decision date"):
        builder.build(frame)

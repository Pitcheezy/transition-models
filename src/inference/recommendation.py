"""Reusable operational recommendation service for CLI and the manual P0 UI."""

import json
import pickle
from pathlib import Path

import lightgbm as lgb
import numpy as np

from src.data.features import PITCH_TYPES
from src.data.operational import ACTION_TYPES, state_codes
from src.data.point_data import CLASS_NAMES
from src.evaluation.operational_metrics import temperature_scale
from src.evaluation.policy_value import behavior_features, soft_greedy
from src.inference.operational import OperationalPredictor
from src.inference.prepitch_contract import PrePitchState, present_legacy_probabilities
from src.utils.experiment_paths import resolve_selected_runs


class OperationalRecommender:
    """Load models once and enforce the scope of the evaluated policy."""

    def __init__(self, data_dir, evaluation_dir, nuisance_dir, runs_dir=None):
        evaluation_dir, nuisance_dir, data_dir = map(Path, (evaluation_dir, nuisance_dir, data_dir))
        self.report = json.loads((evaluation_dir / "probability_report.json").read_text())
        self.selected = self.report["selection"]["selected"]
        self.model = OperationalPredictor(
            data_dir,
            resolve_selected_runs(self.report["selection"], evaluation_dir, runs_dir),
            self.report["models"][self.selected]["temperature"],
            threads=1,
        )
        with open(evaluation_dir / "empirical.pkl", "rb") as handle:
            self.empirical = pickle.load(handle)
        self.nuisance = json.loads((nuisance_dir / "manifest.json").read_text())
        if (
            self.nuisance["status"] != "complete"
            or self.nuisance["dataset"] != self.report["dataset"]
        ):
            raise ValueError("Incompatible nuisance model")
        self.behavior = lgb.Booster(model_file=str(nuisance_dir / "propensity.txt"))
        self.kernel = np.load(data_dir / "run_value_model.npz")["outcome_costs"]

    def predict(self, payload):
        """Evaluate known states without accessing the current pitch or its outcome."""
        state = PrePitchState.from_dict(payload)
        if state.game_date <= self.model.builder.cutoff:
            raise ValueError("State must occur after the frozen historical profile cutoff")
        frame = state.to_frame()
        x = self.model.builder.build(frame, action="FF")
        prop = temperature_scale(
            self.behavior.predict(behavior_features(x), num_threads=1),
            self.nuisance["propensity"]["temperature"],
        )
        support = self.model.builder.available_actions(frame) & (
            prop[:, [PITCH_TYPES.index(a) for a in ACTION_TYPES]] >= 0.02
        )
        in_policy_scope = state.inning <= 8
        kernel = self.kernel[state_codes(frame)]
        costs, empirical_costs, candidates = [], [], []
        for i, action in enumerate(ACTION_TYPES):
            probabilities = self.model.predict(frame, action)
            cost = float((probabilities * kernel).sum())
            baseline = temperature_scale(
                self.empirical.predict(frame, action),
                self.report["models"]["empirical"]["temperature"],
            )
            costs.append(cost)
            empirical_costs.append(float((baseline * kernel).sum()))
            raw = dict(zip(CLASS_NAMES, probabilities[0].tolist(), strict=True))
            candidates.append(
                {
                    "action": action,
                    "supported": bool(support[0, i]),
                    "policy_probability": 0.0,
                    "expected_cost": cost if in_policy_scope else None,
                    "probabilities": raw,
                    **present_legacy_probabilities(raw),
                }
            )
        recommendation, empirical_recommendation, reason = None, None, None
        if not in_policy_scope:
            reason = "Policy evaluation covers innings 1-8 only; recommendation withheld."
        elif support.sum() < 2:
            reason = "Insufficient historically supported actions"
        else:
            policy, choice = soft_greedy(np.array([costs]), support)
            _, empirical_choice = soft_greedy(np.array([empirical_costs]), support)
            recommendation, empirical_recommendation = (
                ACTION_TYPES[choice[0]],
                ACTION_TYPES[empirical_choice[0]],
            )
            for i, candidate in enumerate(candidates):
                candidate["policy_probability"] = float(policy[0, i])
        return {
            "schema": "manual_recommendation_v1",
            "selected_model": self.selected,
            "feature_schema": self.model.builder.schema,
            "recommendation": recommendation,
            "empirical_recommendation": empirical_recommendation,
            "reason": reason,
            "target_location": None,
            "scope": "One-step predicted run-expectancy cost; observational validation only",
            "limitations": [
                "Target-location conditioning and batter-specific ability are not implemented.",
                "Run reduction has not been established. Scores are not win probabilities.",
                "Profiles are frozen in 2022; later players can have unsupported repertoires.",
            ],
            "candidates": candidates,
        }

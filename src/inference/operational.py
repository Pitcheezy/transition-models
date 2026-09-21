"""Versioned pre-pitch inference and a smoothed empirical probability baseline."""

import hashlib
import json
import pickle
from pathlib import Path

import numpy as np
import torch

from src.data.features import PITCH_TYPES
from src.data.operational import FEATURE_SCHEMA, state_codes
from src.evaluation.operational_metrics import temperature_scale
from src.models.otremba_mlp import OtrembaMLP
from src.utils.model_prediction import predict_mlp


def action_indices(frame, action=None):
    """Map chosen or recorded pitch types to the fixed training vocabulary."""
    choices = (
        frame["pitch_type"].to_numpy() if action is None else np.broadcast_to(action, len(frame))
    )
    lookup = {name: i for i, name in enumerate(PITCH_TYPES)}
    try:
        return np.array([lookup[value] for value in choices], dtype=int)
    except KeyError as exc:
        raise ValueError("Unknown pitch type") from exc


def empirical_keys(frame, action=None):
    """Encode state/action/hand strata from exclusively pre-pitch fields."""
    state = state_codes(frame)
    hands = (frame["stand"].to_numpy() == "L") * 2 + (frame["p_throws"].to_numpy() == "L")
    action_id = action_indices(frame, action)
    fine = (state * 17 + action_id) * 4 + hands
    coarse = ((state % 12) * 17 + action_id) * 4 + hands
    return fine, coarse, action_id * 4 + hands


class EmpiricalTransition:
    """Hierarchical count probabilities; smoothing is fixed before test evaluation."""

    def fit(self, frame, targets, strength=50.0):
        """Fit state strata with count/action/hand and action/hand backoff."""
        fine, coarse, base = empirical_keys(frame)
        prior = np.bincount(targets, minlength=10) + 1.0
        prior /= prior.sum()

        def counts(keys, size):
            return np.bincount(keys * 10 + targets, minlength=size * 10).reshape(size, 10)

        c0 = counts(base, 17 * 4)
        p0 = (c0 + strength * prior) / (c0.sum(axis=1, keepdims=True) + strength)
        c1 = counts(coarse, 12 * 17 * 4)
        p1 = (c1 + strength * p0[np.arange(len(c1)) % 68]) / (
            c1.sum(axis=1, keepdims=True) + strength
        )
        c2 = counts(fine, 288 * 17 * 4)
        self.table = (c2 + strength * p1[np.arange(len(c2)) % (12 * 68)]) / (
            c2.sum(axis=1, keepdims=True) + strength
        )
        return self

    def predict(self, frame, action=None):
        """Return strictly positive class probabilities in canonical order."""
        return self.table[empirical_keys(frame, action)[0]]


class OperationalPredictor:
    """Load only compatible profiles/checkpoints and apply the training feature builder."""

    def __init__(self, data_dir, run_dirs, temperature=1.0, device="cpu", threads=4):
        self.device = torch.device(device)
        self.temperature = temperature
        self.threads = threads
        with open(Path(data_dir) / "feature_builder.pkl", "rb") as handle:
            self.builder = pickle.load(handle)
        dataset = json.loads((Path(data_dir) / "dataset_manifest.json").read_text())
        actual_hash = hashlib.sha256(
            (Path(data_dir) / "feature_builder.pkl").read_bytes()
        ).hexdigest()
        if dataset["profile_sha256"] != actual_hash:
            raise ValueError("Operational profile file hash mismatch")
        if self.builder.schema != FEATURE_SCHEMA or dataset["feature_schema"] != FEATURE_SCHEMA:
            raise ValueError("Operational feature schema mismatch")
        self.models = []
        for directory in run_dirs:
            directory = Path(directory)
            manifest = json.loads((directory / "manifest.json").read_text())
            if (
                manifest["status"] != "complete"
                or not manifest.get("dataset")
                or manifest["dataset"]["feature_schema"] != FEATURE_SCHEMA
                or manifest["dataset"]["profile_sha256"] != dataset["profile_sha256"]
            ):
                raise ValueError("Checkpoint was not trained with these operational profiles")
            dim = manifest["input_dim"]
            if manifest["model"] == "mlp":
                model = OtrembaMLP(dim, 128, 10, dropout=0.2).to(self.device)
                checkpoint = torch.load(
                    directory / "best.pt", map_location=self.device, weights_only=False
                )
                model.load_state_dict(checkpoint["model_state"])
                model.eval()
            elif manifest["model"] == "lr":
                with open(directory / "model.pkl", "rb") as handle:
                    model = pickle.load(handle)
            else:
                import lightgbm as lgb

                model = lgb.Booster(model_file=str(directory / "model.txt"))
            self.models.append((manifest["model"], dim, model))

    def predict_vectors(self, vectors):
        """Predict an ensemble from already built operational features."""
        result = []
        for kind, dim, model in self.models:
            x = vectors[:, :dim]
            if kind == "mlp":
                probs = predict_mlp(model, x, self.device)
            elif kind == "lr":
                probs = model.predict_proba(x)
            else:
                probs = model.predict(x, num_threads=self.threads)
            result.append(probs)
        return temperature_scale(np.mean(result, axis=0), self.temperature)

    def predict(self, frame, action=None):
        """Use exactly the same feature builder as operational dataset preparation."""
        return self.predict_vectors(self.builder.build(frame, action=action))

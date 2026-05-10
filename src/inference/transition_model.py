"""Inference wrappers for transition probability models.

DQN/MDP 팀에서 쉽게 사용할 수 있는 high-level API.

Example::

    from src.inference import TransitionModelC

    model = TransitionModelC()          # 자동으로 best checkpoint 로드
    result = model.predict(sequence)    # sequence: (400, 87) numpy array
    probs = result["pitch_result"]      # (10,) 확률 벡터, 합 = 1
"""

from __future__ import annotations

from pathlib import Path
from typing import Union

import numpy as np
import torch
import torch.nn.functional as F

from src.models.otremba_mlp import OtrembaMLP
from src.models.transformer import PitchTransformer
from src.utils.device import get_device

PITCH_RESULT_CLASSES_4 = ["Ball", "Strike", "Foul", "InPlay"]

PITCH_RESULT_CLASSES_10 = [
    "Ball", "Strike", "Single", "Double", "Triple",
    "HomeRun", "FieldOut", "Strikeout", "Walk", "HitByPitch",
]

HIT_LOCATION_CLASSES = [
    "Infield_Left", "Infield_Center", "Infield_Right",
    "Outfield_Left", "Outfield_Center", "Outfield_Right",
    "Line_Left", "Line_Right", "Unknown",
]


class TransitionModelB:
    """Model B (Otremba 2022 MLP) inference wrapper.

    Input:  77-dim feature vector (or batch of them)
    Output: (4,) probability vector over [Ball, Strike, Foul, InPlay]

    Args:
        checkpoint: Path to .pt checkpoint. Defaults to DEFAULT_CHECKPOINT.
        device: torch device string. Defaults to auto-detection.
    """

    DEFAULT_CHECKPOINT = "outputs/checkpoints/model_b_full_v1_best.pt"

    def __init__(
        self,
        checkpoint: Union[str, Path, None] = None,
        device: Union[str, None] = None,
    ):
        self.checkpoint_path = Path(checkpoint or self.DEFAULT_CHECKPOINT)
        self.device = torch.device(device) if device else get_device()
        self.classes = PITCH_RESULT_CLASSES_4
        self.num_classes = 4

        ckpt = torch.load(self.checkpoint_path, weights_only=False, map_location="cpu")
        self._model = OtrembaMLP()
        self._model.load_state_dict(ckpt["model_state"])
        self._model = self._model.to(self.device).eval()

    def predict(self, x: np.ndarray) -> np.ndarray:
        """Predict pitch outcome probabilities.

        Args:
            x: (77,) single pitch feature vector, or (N, 77) batch.

        Returns:
            (4,) probabilities for single input, or (N, 4) for batch.
        """
        single = x.ndim == 1
        if single:
            x = x[np.newaxis]

        tensor = torch.from_numpy(x).float().to(self.device)
        with torch.no_grad():
            probs = F.softmax(self._model(tensor), dim=-1).cpu().numpy()

        return probs[0] if single else probs

    def predict_top_k(self, x: np.ndarray, k: int = 3) -> list[dict]:
        """Return top-k predictions sorted by probability (descending).

        Args:
            x: (77,) single pitch feature vector.
            k: number of top predictions.

        Returns:
            List of {"class": str, "probability": float} dicts.
        """
        probs = self.predict(x)  # (4,)
        if probs.ndim == 2:
            probs = probs[0]
        top_idx = np.argsort(probs)[::-1][:k]
        return [{"class": self.classes[i], "probability": float(probs[i])} for i in top_idx]


class TransitionModelC:
    """Model C (MIT Sloan 2025 Transformer) inference wrapper.

    Input:  (400, 87) pitch sequence
    Output: dict with "pitch_result" (10,) and "hit_location" (9,)

    Sub-token masking: the last pitch's outcome features (indices [68:87])
    must be zero — they represent what we're trying to predict.

    Args:
        checkpoint: Path to .pt checkpoint. Defaults to DEFAULT_CHECKPOINT.
        device: torch device string. Defaults to auto-detection.
    """

    DEFAULT_CHECKPOINT = "outputs/checkpoints/model_c_full_v2_best.pt"

    def __init__(
        self,
        checkpoint: Union[str, Path, None] = None,
        device: Union[str, None] = None,
    ):
        self.checkpoint_path = Path(checkpoint or self.DEFAULT_CHECKPOINT)
        self.device = torch.device(device) if device else get_device()
        self.pr_classes = PITCH_RESULT_CLASSES_10
        self.hl_classes = HIT_LOCATION_CLASSES

        ckpt = torch.load(self.checkpoint_path, weights_only=False, map_location="cpu")
        self._model = PitchTransformer()
        self._model.load_state_dict(ckpt["model_state"])
        self._model = self._model.to(self.device).eval()

    def predict(self, x: np.ndarray) -> dict[str, np.ndarray]:
        """Predict pitch result and hit location probabilities.

        Args:
            x: (400, 87) single sequence, or (N, 400, 87) batch.
                Last pitch outcome features x[..., -1, 68:87] must be 0.

        Returns:
            Dict with:
                "pitch_result":  (10,) or (N, 10)  — 10-class probabilities
                "hit_location":  (9,)  or (N, 9)   — 9-class probabilities (InPlay용)
        """
        single = x.ndim == 2
        if single:
            x = x[np.newaxis]

        tensor = torch.from_numpy(x).float().to(self.device)
        with torch.no_grad():
            logits = self._model(tensor)  # (N, 24)
            pr_probs = F.softmax(logits[:, :10], dim=-1).cpu().numpy()
            hl_probs = F.softmax(logits[:, 10:19], dim=-1).cpu().numpy()

        if single:
            return {"pitch_result": pr_probs[0], "hit_location": hl_probs[0]}
        return {"pitch_result": pr_probs, "hit_location": hl_probs}

    def predict_top_k(self, x: np.ndarray, k: int = 3) -> list[dict]:
        """Return top-k pitch result predictions sorted by probability.

        Args:
            x: (400, 87) single sequence.
            k: number of top predictions.

        Returns:
            List of {"class": str, "probability": float} dicts.
        """
        result = self.predict(x)
        probs = result["pitch_result"]
        if probs.ndim == 2:
            probs = probs[0]
        top_idx = np.argsort(probs)[::-1][:k]
        return [{"class": self.pr_classes[i], "probability": float(probs[i])} for i in top_idx]

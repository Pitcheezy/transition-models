"""Inference wrappers for transition probability models.

DQN/MDP 팀에서 쉽게 사용할 수 있는 high-level API.

Example (Model B — 77-dim, 4-class)::

    from src.inference import TransitionModelB
    model = TransitionModelB()
    probs = model.predict(x)   # x: (77,) → (4,) [Ball, Strike, Foul, InPlay]

Example (Model C — Transformer, 10-class)::

    from src.inference import TransitionModelC
    model = TransitionModelC()
    result = model.predict(sequence)    # sequence: (400, 87) numpy array
    probs = result["pitch_result"]      # (10,) 확률 벡터, 합 = 1

Example (TransitionModelMLP10 — MLP 135-dim, 10-class, focal loss)::

    from src.inference import TransitionModelMLP10
    model = TransitionModelMLP10()
    probs = model.predict(x)   # x: (135,) → (10,)
    # rl-agent에서 UMAP 미보유 시: x[77:82] = 0.0 (평균값으로 대체)
    # arsenal 벡터: outputs/arsenal_by_pitcher_cluster.json 참조
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


class TransitionModelMLP10:
    """MLP 135-dim 10-class inference wrapper (focal loss checkpoint).

    rl-agent 팀원을 위한 10-class 전이 모델.
    Model B의 4-class 한계(InPlay 분해 필요)를 극복하여
    Single/Double/Triple/HR/Walk/Strikeout 등 직접 예측.

    Input:  135-dim feature vector  [Ball, Strike, Foul, InPlay 확장형]
    Output: (10,) 확률 [Ball, Strike, Single, Double, Triple, HomeRun, FieldOut, Strikeout, Walk, HitByPitch]

    Feature layout (135-dim):
        [0:77]    Model B 77-dim features  (scaler.pkl 적용)
        [77:82]   UMAP 5d                  (rl-agent에서 0.0으로 채울 것)
        [82:83]   count_cluster_id          (scaler_new58.pkl 적용)
        [83:115]  arsenal_func_00..31       (scaler_new58.pkl 적용)
        [115:135] arsenal_moment_00..19     (scaler_new58.pkl 적용)

    arsenal 벡터: outputs/arsenal_by_pitcher_cluster.json 참조.

    Args:
        checkpoint: Path to .pt checkpoint. Defaults to DEFAULT_CHECKPOINT.
        device: torch device string. Defaults to auto-detection.
    """

    DEFAULT_CHECKPOINT = "outputs/checkpoints/model_b3_focal_135dim_10cls_best.pt"
    INPUT_DIM = 135

    def __init__(
        self,
        checkpoint: Union[str, Path, None] = None,
        device: Union[str, None] = None,
    ):
        self.checkpoint_path = Path(checkpoint or self.DEFAULT_CHECKPOINT)
        self.device = torch.device(device) if device else get_device()
        self.classes = PITCH_RESULT_CLASSES_10
        self.num_classes = 10

        ckpt = torch.load(self.checkpoint_path, weights_only=False, map_location="cpu")
        # dropout=0.2 로 저장된 체크포인트와 Sequential 인덱스를 맞춤
        # (eval() 시 dropout은 비활성화되므로 추론 결과에 영향 없음)
        self._model = OtrembaMLP(input_dim=self.INPUT_DIM, hidden_dim=128, n_classes=10, dropout=0.2)
        self._model.load_state_dict(ckpt["model_state"])
        self._model = self._model.to(self.device).eval()

    def predict(self, x: np.ndarray) -> np.ndarray:
        """Predict 10-class pitch outcome probabilities.

        Args:
            x: (135,) single pitch feature vector, or (N, 135) batch.
               UMAP 차원 (indices 77-81)을 모를 경우 0.0으로 채울 것.

        Returns:
            (10,) probabilities for single input, or (N, 10) for batch.
            Order: [Ball, Strike, Single, Double, Triple, HomeRun, FieldOut, Strikeout, Walk, HitByPitch]
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
            x: (135,) single pitch feature vector.
            k: number of top predictions.

        Returns:
            List of {"class": str, "probability": float} dicts.
        """
        probs = self.predict(x)
        if probs.ndim == 2:
            probs = probs[0]
        top_idx = np.argsort(probs)[::-1][:k]
        return [{"class": self.classes[i], "probability": float(probs[i])} for i in top_idx]


def build_135dim_feature(
    base_77: np.ndarray,
    arsenal_data: dict,
    pitcher_cluster: "int | None" = None,
    pitcher_id: "int | None" = None,
) -> np.ndarray:
    """Build 135-dim feature vector for TransitionModelMLP10.

    Combines the 77-dim Model B feature with 58-dim arsenal context.
    Designed for rl-agent batch inference.

    Args:
        base_77: (77,) Model B feature vector (already scaler.pkl normalized).
        arsenal_data: Parsed ``arsenal_by_pitcher_cluster.json`` dict.
        pitcher_cluster: Pitcher cluster ID (0-3). Takes priority over pitcher_id.
        pitcher_id: MLB MLBAM pitcher ID (int). Used when pitcher_cluster is None.
                    Falls back to cluster "0" if ID not in JSON.

    Returns:
        (135,) float32 feature vector.
        Indices [77:82] (UMAP 5d) are set to 0.0 — the model was trained to
        handle this as "average pitch mechanics" at inference time.

    Example::

        import json
        with open("outputs/arsenal_by_pitcher_cluster.json") as f:
            arsenal = json.load(f)

        model = TransitionModelMLP10()
        feat = build_135dim_feature(base_77, arsenal, pitcher_cluster=2)
        probs = model.predict(feat)  # (10,)
    """
    vec = np.zeros(135, dtype=np.float32)
    vec[:77] = base_77
    # [77:82] = 0.0  — UMAP unknown at inference, treated as training-data mean

    if pitcher_cluster is not None:
        cluster_id = str(pitcher_cluster)
    elif pitcher_id is not None:
        cluster_id = arsenal_data["pitcher_to_cluster"].get(str(pitcher_id), "0")
    else:
        cluster_id = "0"

    cluster = arsenal_data["clusters"][cluster_id]
    vec[82] = cluster["count_cluster_id_scaled"]
    vec[83:115] = cluster["arsenal_func_scaled"]    # 32-dim
    vec[115:135] = cluster["arsenal_moment_scaled"]  # 20-dim
    return vec

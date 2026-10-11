"""Aligned point datasets: vectors, both targets, and pitch identities travel together."""

import hashlib
from pathlib import Path

import numpy as np
import pandas as pd
import torch

from src.data.features import PitchResult10
from src.data.preprocess import extract_labels_4class, extract_labels_10class

PITCH_KEYS = ["game_pk", "at_bat_number", "pitch_number"]
CLASS_NAMES = np.array(list(PitchResult10.NAMES.values()))
SCHEMA_VERSION = 1


def pitch_ids(frame: pd.DataFrame) -> np.ndarray:
    """Return integer pitch keys, rejecting ambiguous identities."""
    keys = frame[PITCH_KEYS].to_numpy(dtype=np.float64)
    if not np.isfinite(keys).all() or not np.equal(keys, np.floor(keys)).all():
        raise ValueError("Pitch keys must be finite integers")
    result = keys.astype(np.int64)
    if pd.DataFrame(result).duplicated().any():
        raise ValueError("Duplicate pitch keys")
    return result


def identity_hash(ids: np.ndarray) -> str:
    """Hash ordered identities with a platform-independent byte representation."""
    return hashlib.sha256(np.asarray(ids, dtype="<i8").tobytes()).hexdigest()


def validate_point_data(data: dict) -> dict:
    """Reject legacy files, invalid labels, and mismatched schema components."""
    required = {"schema_version", "vectors", "labels_4", "labels_10", "pitch_ids", "class_names"}
    if not required.issubset(data):
        raise ValueError(
            "Unaligned legacy dataset. Rebuild with scripts/04_preprocess.py or "
            "scripts/48_prepare_aligned_points.py; never use sequence labels."
        )
    if int(data["schema_version"]) != SCHEMA_VERSION:
        raise ValueError("Unsupported point schema version")
    result = {key: np.asarray(value) for key, value in data.items()}
    x, ids = result["vectors"], result["pitch_ids"]
    if x.ndim != 2 or x.shape[1] not in (77, 135, 151) or not len(x):
        raise ValueError("Expected nonempty point vectors with 77, 135, or 151 columns")
    if not np.isfinite(x).all():
        raise ValueError("Nonfinite point features")
    if ids.shape != (len(x), 3) or not np.issubdtype(ids.dtype, np.integer):
        raise ValueError("Pitch ID shape/type mismatch")
    if pd.DataFrame(ids).duplicated().any():
        raise ValueError("Duplicate pitch keys")
    for key, classes in (("labels_4", 4), ("labels_10", 10)):
        y = result[key]
        if (
            y.shape != (len(x),)
            or not np.issubdtype(y.dtype, np.integer)
            or np.any((y < -1) | (y >= classes))
        ):
            raise ValueError(f"Invalid {key}")
    if not np.array_equal(result["class_names"], CLASS_NAMES):
        raise ValueError("Class order mismatch")
    return result


def make_point_data(frame: pd.DataFrame, vectors: np.ndarray) -> dict:
    """Create the whole record from one dataframe before any sequence sorting."""
    return validate_point_data(
        {
            "schema_version": SCHEMA_VERSION,
            "vectors": vectors,
            "labels_4": extract_labels_4class(frame),
            "labels_10": extract_labels_10class(frame),
            "pitch_ids": pitch_ids(frame),
            "class_names": CLASS_NAMES,
        }
    )


def load_point_data(directory: Path, split: str, input_dim: int = 77) -> dict:
    """Load only self-contained aligned artifacts, with a common valid-label mask."""
    path = directory / f"point_{split}.npz"
    if path.exists():
        with np.load(path, allow_pickle=False) as archive:
            data = validate_point_data(dict(archive))
    else:
        data = validate_point_data(
            torch.load(directory / f"model_b_{split}.pt", weights_only=False, map_location="cpu")
        )
    if input_dim > data["vectors"].shape[1]:
        raise ValueError("Requested features unavailable")
    mask = data["labels_10"] >= 0
    return {
        "vectors": np.ascontiguousarray(data["vectors"][mask, :input_dim], dtype=np.float32),
        "labels": data["labels_10"][mask],
        "pitch_ids": data["pitch_ids"][mask],
    }


def validate_split_ids(splits: dict[str, dict]) -> None:
    """Reject pitches that leak across train/validation/test."""
    ids = np.concatenate([data["pitch_ids"] for data in splits.values()])
    if pd.DataFrame(ids).duplicated().any():
        raise ValueError("Pitch identity overlap across splits")

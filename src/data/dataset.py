"""PyTorch Dataset classes for transition probability models."""

import numpy as np
import torch
from torch.utils.data import Dataset


class PitchSequenceDataset(Dataset):
    """Model C: 400-pitch sequence input, predict last pitch outcome.

    Each item returns a dict with:
        - "sequence": (seq_length, 87) float tensor (last pitch masked)
        - "pitch_result": scalar long tensor (0-9)
        - "hit_location": scalar long tensor (0-8 or -1)
    """

    def __init__(self, sequences: np.ndarray, labels_10: np.ndarray, hit_locs: np.ndarray):
        """Initialize dataset.

        Args:
            sequences: (N, seq_length, 87) masked sequences.
            labels_10: (N,) 10-class target labels.
            hit_locs: (N,) hit location labels (0-8 or -1).
        """
        self.sequences = torch.from_numpy(sequences).float()
        self.labels_10 = torch.from_numpy(labels_10).long()
        self.hit_locs = torch.from_numpy(hit_locs).long()

    def __len__(self) -> int:
        return len(self.sequences)

    def __getitem__(self, idx: int) -> dict:
        return {
            "sequence": self.sequences[idx],
            "pitch_result": self.labels_10[idx],
            "hit_location": self.hit_locs[idx],
        }


class PitchPointDataset(Dataset):
    """Model B: single pitch input, predict 4-class outcome.

    Each item returns (vector, label) tuple.
    """

    def __init__(self, vectors: np.ndarray, labels: np.ndarray):
        """Initialize dataset.

        Args:
            vectors: (N, 77) pitch feature vectors.
            labels: (N,) 4-class labels (0-3).
        """
        self.vectors = torch.from_numpy(vectors).float()
        self.labels = torch.from_numpy(labels).long()

    def __len__(self) -> int:
        return len(self.vectors)

    def __getitem__(self, idx: int) -> tuple[torch.Tensor, torch.Tensor]:
        return self.vectors[idx], self.labels[idx]

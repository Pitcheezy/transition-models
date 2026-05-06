"""PyTorch Dataset classes for transition probability models.

Model C uses lazy loading: vectors are pre-computed as (N, 87) arrays,
sequences assembled on-the-fly via numpy slicing in __getitem__.
Model B uses eager loading: vectors are small enough to hold in memory.
"""

import numpy as np
import torch
from torch.utils.data import Dataset

from src.data.features import MODEL_C_DIM, OUTCOME_END, OUTCOME_START


class PitchSequenceDataset(Dataset):
    """Model C: lazy 400-pitch sequence with O(1) numpy slicing.

    Pre-computed (N, 87) vectors are stored contiguously, sorted by
    batter then time. __getitem__ slices a 400-row window and applies
    sub-token masking to the last pitch.

    Memory: only the current batch is materialized as tensors.
    Compatible with DataLoader num_workers > 0.
    """

    def __init__(
        self,
        vectors: np.ndarray,
        labels_10: np.ndarray,
        hit_locs: np.ndarray,
        valid_indices: list[tuple[int, int]],
        seq_length: int = 400,
    ):
        """Initialize lazy-loading dataset.

        Args:
            vectors: (N, 87) pre-computed feature vectors, sorted by batter+time.
            labels_10: (N,) 10-class labels.
            hit_locs: (N,) hit location labels (0-8 or -1).
            valid_indices: List of (batter_id, global_start_idx) from build_valid_indices.
            seq_length: Window size (default 400).
        """
        self.vectors = vectors  # numpy array, can be mmap
        self.labels_10 = labels_10
        self.hit_locs = hit_locs
        self.valid_indices = valid_indices
        self.seq_length = seq_length

    def __len__(self) -> int:
        return len(self.valid_indices)

    def __getitem__(self, idx: int) -> dict:
        _, global_start = self.valid_indices[idx]
        end = global_start + self.seq_length

        # O(1) numpy slice → (400, 87) copy
        seq = self.vectors[global_start:end].copy()

        # Sub-token mask: 마지막 pitch의 outcome [68:87] = 0
        seq[-1, OUTCOME_START:OUTCOME_END] = 0.0

        # 타겟: 마지막 pitch의 라벨
        target_pr = int(self.labels_10[end - 1])
        target_hl = int(self.hit_locs[end - 1])

        return {
            "sequence": torch.from_numpy(seq).float(),
            "pitch_result": torch.tensor(target_pr, dtype=torch.long),
            "hit_location": torch.tensor(target_hl, dtype=torch.long),
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

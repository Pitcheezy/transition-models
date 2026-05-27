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


class PitchSequenceDatasetHybrid(Dataset):
    """PitchSequenceDataset + static 58-dim context at sequence endpoint.

    static_58 은 vectors_c 와 동일한 행 정렬 (sort_by_batter_and_time).
    30_align_static58_for_sequence.py 로 생성된 (N_c, 58) 배열을 사용.

    drop_missing_static=True : static_valid[end-1]=False 인 시퀀스 제외 (성능 측정용)
    drop_missing_static=False: static=0 으로 유지 (G5 fair compare용, N 동일)
    """

    def __init__(
        self,
        vectors: np.ndarray,
        static_58: np.ndarray,
        static_valid: np.ndarray,
        labels_10: np.ndarray,
        hit_locs: np.ndarray,
        valid_indices: list[tuple[int, int]],
        seq_length: int = 400,
        drop_missing_static: bool = True,
    ):
        self.vectors = vectors
        self.static_58 = static_58
        self.static_valid = static_valid
        self.labels_10 = labels_10
        self.hit_locs = hit_locs
        self.seq_length = seq_length

        if drop_missing_static:
            kept = [
                (bid, start)
                for bid, start in valid_indices
                if static_valid[start + seq_length - 1]
            ]
            self.valid_indices = kept
        else:
            self.valid_indices = list(valid_indices)

    def __len__(self) -> int:
        return len(self.valid_indices)

    def __getitem__(self, idx: int) -> dict:
        _, global_start = self.valid_indices[idx]
        end = global_start + self.seq_length

        seq = self.vectors[global_start:end].copy()
        seq[-1, OUTCOME_START:OUTCOME_END] = 0.0

        static = self.static_58[end - 1].copy()  # (58,)

        return {
            "sequence": torch.from_numpy(seq).float(),
            "static": torch.from_numpy(static).float(),
            "pitch_result": torch.tensor(int(self.labels_10[end - 1]), dtype=torch.long),
            "hit_location": torch.tensor(int(self.hit_locs[end - 1]), dtype=torch.long),
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

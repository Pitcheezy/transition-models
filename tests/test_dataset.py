"""Unit tests for src/data/dataset.py."""

import numpy as np
import torch
from torch.utils.data import DataLoader

from src.data.dataset import PitchPointDataset, PitchSequenceDataset
from src.data.features import MODEL_B_DIM, MODEL_C_DIM, OUTCOME_END, OUTCOME_START


# =============================================================================
# Helper: create lazy-style dataset for testing
# =============================================================================


def _make_lazy_dataset(n_pitches: int = 500, seq_length: int = 400):
    """Create a PitchSequenceDataset with fake data for testing."""
    vectors = np.random.randn(n_pitches, MODEL_C_DIM).astype(np.float32)
    labels_10 = np.random.randint(0, 10, size=n_pitches, dtype=np.int64)
    hit_locs = np.full(n_pitches, -1, dtype=np.int64)
    # 1 batter with n_pitches → (n_pitches - seq_length + 1) sequences
    valid_indices = [(1, start) for start in range(n_pitches - seq_length + 1)]
    return PitchSequenceDataset(vectors, labels_10, hit_locs, valid_indices, seq_length)


# =============================================================================
# PitchSequenceDataset (lazy loading)
# =============================================================================


class TestPitchSequenceDataset:
    def test_shape(self):
        ds = _make_lazy_dataset(500, 400)
        assert len(ds) == 101  # 500 - 400 + 1
        item = ds[0]
        assert item["sequence"].shape == (400, MODEL_C_DIM)
        assert item["pitch_result"].shape == ()
        assert item["hit_location"].shape == ()

    def test_dtype(self):
        ds = _make_lazy_dataset(450, 400)
        item = ds[0]
        assert item["sequence"].dtype == torch.float32
        assert item["pitch_result"].dtype == torch.int64
        assert item["hit_location"].dtype == torch.int64

    def test_subtoken_mask(self):
        """마지막 pitch의 outcome [68:87]이 0인지 확인."""
        vectors = np.ones((410, MODEL_C_DIM), dtype=np.float32)
        labels = np.zeros(410, dtype=np.int64)
        hit_locs = np.full(410, -1, dtype=np.int64)
        indices = [(1, 0), (1, 10)]
        ds = PitchSequenceDataset(vectors, labels, hit_locs, indices, seq_length=400)

        item = ds[0]
        seq = item["sequence"].numpy()
        # 마지막 pitch outcome은 0
        assert np.all(seq[-1, OUTCOME_START:OUTCOME_END] == 0.0)
        # 직전 pitch는 원본 유지 (all 1s)
        assert np.all(seq[-2, OUTCOME_START:OUTCOME_END] == 1.0)

    def test_does_not_modify_source(self):
        """__getitem__이 원본 vectors를 변경하지 않는지."""
        vectors = np.ones((400, MODEL_C_DIM), dtype=np.float32)
        labels = np.zeros(400, dtype=np.int64)
        hit_locs = np.full(400, -1, dtype=np.int64)
        ds = PitchSequenceDataset(vectors, labels, hit_locs, [(1, 0)], seq_length=400)
        _ = ds[0]
        # 원본 유지
        assert np.all(vectors[-1, OUTCOME_START:OUTCOME_END] == 1.0)

    def test_target_from_last_pitch(self):
        """타겟이 시퀀스 마지막 pitch에서 추출되는지."""
        vectors = np.zeros((400, MODEL_C_DIM), dtype=np.float32)
        labels = np.arange(400, dtype=np.int64)  # 각 pitch 다른 라벨
        hit_locs = np.full(400, -1, dtype=np.int64)
        ds = PitchSequenceDataset(vectors, labels, hit_locs, [(1, 0)], seq_length=400)
        item = ds[0]
        assert item["pitch_result"].item() == 399  # 마지막 pitch 라벨

    def test_dataloader_batches(self):
        ds = _make_lazy_dataset(500, 400)
        dl = DataLoader(ds, batch_size=8, shuffle=False)
        batch = next(iter(dl))
        assert batch["sequence"].shape == (8, 400, MODEL_C_DIM)
        assert batch["pitch_result"].shape == (8,)
        assert batch["hit_location"].shape == (8,)

    def test_dataloader_workers(self):
        """num_workers > 0에서도 작동."""
        ds = _make_lazy_dataset(500, 400)
        dl = DataLoader(ds, batch_size=4, num_workers=2)
        batch = next(iter(dl))
        assert batch["sequence"].shape == (4, 400, MODEL_C_DIM)

    def test_multiple_indices_valid(self):
        """여러 인덱스에서 모두 올바른 shape."""
        ds = _make_lazy_dataset(500, 400)
        for i in range(0, len(ds), max(1, len(ds) // 10)):
            item = ds[i]
            assert item["sequence"].shape == (400, MODEL_C_DIM)


# =============================================================================
# PitchPointDataset (unchanged)
# =============================================================================


class TestPitchPointDataset:
    def test_shape(self):
        n = 10
        vecs = np.random.randn(n, MODEL_B_DIM).astype(np.float32)
        labels = np.zeros(n, dtype=np.int64)
        ds = PitchPointDataset(vecs, labels)
        assert len(ds) == n
        vec, lbl = ds[0]
        assert vec.shape == (MODEL_B_DIM,)
        assert lbl.shape == ()

    def test_dataloader_batches(self):
        vecs = np.random.randn(20, MODEL_B_DIM).astype(np.float32)
        labels = np.arange(20, dtype=np.int64) % 4
        ds = PitchPointDataset(vecs, labels)
        dl = DataLoader(ds, batch_size=8, shuffle=False)
        batch_vec, batch_lbl = next(iter(dl))
        assert batch_vec.shape == (8, MODEL_B_DIM)
        assert batch_lbl.shape == (8,)

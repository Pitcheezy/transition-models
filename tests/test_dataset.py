"""Unit tests for src/data/dataset.py."""

import numpy as np
import torch
from torch.utils.data import DataLoader

from src.data.dataset import PitchPointDataset, PitchSequenceDataset
from src.data.features import MODEL_B_DIM, MODEL_C_DIM


class TestPitchSequenceDataset:
    def test_shape(self):
        n, seq_len = 10, 400
        seqs = np.random.randn(n, seq_len, MODEL_C_DIM).astype(np.float32)
        labels = np.zeros(n, dtype=np.int64)
        hit_locs = np.full(n, -1, dtype=np.int64)
        ds = PitchSequenceDataset(seqs, labels, hit_locs)
        assert len(ds) == n
        item = ds[0]
        assert item["sequence"].shape == (seq_len, MODEL_C_DIM)
        assert item["pitch_result"].shape == ()
        assert item["hit_location"].shape == ()

    def test_dtype(self):
        seqs = np.random.randn(5, 400, MODEL_C_DIM).astype(np.float32)
        labels = np.zeros(5, dtype=np.int64)
        hit_locs = np.full(5, -1, dtype=np.int64)
        ds = PitchSequenceDataset(seqs, labels, hit_locs)
        item = ds[0]
        assert item["sequence"].dtype == torch.float32
        assert item["pitch_result"].dtype == torch.int64

    def test_dataloader_batches(self):
        seqs = np.random.randn(20, 400, MODEL_C_DIM).astype(np.float32)
        labels = np.arange(20, dtype=np.int64) % 10
        hit_locs = np.full(20, -1, dtype=np.int64)
        ds = PitchSequenceDataset(seqs, labels, hit_locs)
        dl = DataLoader(ds, batch_size=8, shuffle=False)
        batch = next(iter(dl))
        assert batch["sequence"].shape == (8, 400, MODEL_C_DIM)
        assert batch["pitch_result"].shape == (8,)


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

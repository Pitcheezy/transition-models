"""Unit tests for src/data/preprocess.py."""

import numpy as np
import pandas as pd
import pytest

from src.data.features import (
    CONTINUOUS_FEATURES,
    MODEL_B_DIM,
    MODEL_C_DIM,
    OUTCOME_END,
    OUTCOME_START,
    PITCH_TYPES,
    PitchResult10,
)
from src.data.preprocess import (
    apply_subtoken_mask,
    build_model_b_vector,
    build_model_c_vector,
    clean_dataframe,
    derive_base_state,
    extract_labels_4class,
    make_sequences_for_batter,
)


def _make_fake_row(**overrides) -> pd.Series:
    """Create a minimal fake Statcast row for testing."""
    base = {
        "release_speed": 95.0,
        "release_pos_x": -1.5,
        "release_pos_y": 55.0,
        "release_pos_z": 6.0,
        "pfx_x": -0.5,
        "pfx_z": 1.2,
        "release_spin_rate": 2400.0,
        "plate_x": 0.1,
        "plate_z": 2.5,
        "vx0": 5.0,
        "vy0": -130.0,
        "vz0": -3.0,
        "ax": -5.0,
        "ay": 28.0,
        "az": -20.0,
        "pitch_type": "FF",
        "zone": 5,
        "balls": 1,
        "strikes": 2,
        "outs_when_up": 1,
        "on_1b": None,
        "on_2b": None,
        "on_3b": None,
        "stand": "R",
        "p_throws": "R",
        "description": "called_strike",
        "events": None,
        "hit_location": None,
        "inning": 3,
        "game_date": "2023-06-15",
    }
    base.update(overrides)
    return pd.Series(base)


def _make_fake_df(n: int = 100) -> pd.DataFrame:
    """Create a fake Statcast DataFrame for testing."""
    rng = np.random.default_rng(42)
    rows = []
    descriptions = ["called_strike", "ball", "foul", "hit_into_play", "swinging_strike"]
    for i in range(n):
        row = {f: rng.normal(80, 10) for f in CONTINUOUS_FEATURES}
        row["pitch_type"] = rng.choice(PITCH_TYPES)
        row["zone"] = rng.integers(1, 15)
        row["balls"] = rng.integers(0, 4)
        row["strikes"] = rng.integers(0, 3)
        row["outs_when_up"] = rng.integers(0, 3)
        row["on_1b"] = 12345 if rng.random() > 0.7 else None
        row["on_2b"] = 67890 if rng.random() > 0.8 else None
        row["on_3b"] = 11111 if rng.random() > 0.9 else None
        row["stand"] = rng.choice(["L", "R"])
        row["p_throws"] = rng.choice(["L", "R"])
        row["description"] = rng.choice(descriptions)
        row["events"] = None
        row["hit_location"] = None
        row["inning"] = rng.integers(1, 10)
        row["game_date"] = f"2023-06-{15 + i % 15:02d}"
        row["batter"] = 100 + (i % 3)
        row["at_bat_number"] = i // 4
        row["pitch_number"] = i % 4 + 1
        rows.append(row)
    return pd.DataFrame(rows)


# =============================================================================
# clean_dataframe
# =============================================================================


class TestCleanDataframe:
    def test_removes_deprecated_columns(self):
        df = _make_fake_df(10)
        df["tfs_deprecated"] = None
        df["sv_id"] = None
        result = clean_dataframe(df)
        assert "tfs_deprecated" not in result.columns
        assert "sv_id" not in result.columns

    def test_removes_truncated_pa(self):
        df = _make_fake_df(10)
        df.loc[0, "events"] = "truncated_pa"
        result = clean_dataframe(df)
        assert len(result) == 9

    def test_removes_null_continuous(self):
        df = _make_fake_df(10)
        df.loc[0, "release_speed"] = None
        result = clean_dataframe(df)
        assert len(result) == 9


# =============================================================================
# derive_base_state
# =============================================================================


class TestDeriveBaseState:
    def test_empty_bases(self):
        assert derive_base_state(None, None, None) == 0

    def test_loaded_bases(self):
        assert derive_base_state(1, 2, 3) == 7

    def test_first_only(self):
        assert derive_base_state(1, None, None) == 1

    def test_second_only(self):
        assert derive_base_state(None, 2, None) == 2

    def test_third_only(self):
        assert derive_base_state(None, None, 3) == 4

    def test_corners(self):
        assert derive_base_state(1, None, 3) == 5


# =============================================================================
# build_model_c_vector
# =============================================================================


class TestBuildModelCVector:
    def test_dim_87(self):
        row = _make_fake_row()
        vec = build_model_c_vector(row)
        assert vec.shape == (MODEL_C_DIM,), f"Expected (87,), got {vec.shape}"

    def test_dtype_float32(self):
        row = _make_fake_row()
        vec = build_model_c_vector(row)
        assert vec.dtype == np.float32

    def test_mask_outcome_zeros_last_19(self):
        row = _make_fake_row(
            description="hit_into_play", events="single", hit_location=6
        )
        vec_unmasked = build_model_c_vector(row, mask_outcome=False)
        vec_masked = build_model_c_vector(row, mask_outcome=True)

        # 마스크된 outcome 부분은 모두 0
        assert np.all(vec_masked[OUTCOME_START:OUTCOME_END] == 0.0)
        # 마스크 안된 버전은 outcome에 값이 있어야
        assert np.any(vec_unmasked[OUTCOME_START:OUTCOME_END] != 0.0)
        # 마스크 외 부분은 동일
        assert np.allclose(vec_masked[:OUTCOME_START], vec_unmasked[:OUTCOME_START])

    def test_pitch_type_one_hot(self):
        row = _make_fake_row(pitch_type="SL")
        vec = build_model_c_vector(row)
        pt_section = vec[15:32]  # pitch_type은 17차원
        assert pt_section.sum() == 1.0
        assert pt_section[PITCH_TYPES.index("SL")] == 1.0


# =============================================================================
# build_model_b_vector
# =============================================================================


class TestBuildModelBVector:
    def test_dim_77(self):
        row = _make_fake_row()
        vec = build_model_b_vector(row)
        assert vec.shape == (MODEL_B_DIM,), f"Expected (77,), got {vec.shape}"

    def test_inning_one_hot(self):
        row = _make_fake_row(inning=5)
        vec = build_model_b_vector(row)
        # inning은 마지막 9차원 [68:77]
        inn_section = vec[68:77]
        assert inn_section.sum() == 1.0
        assert inn_section[4] == 1.0  # 5이닝 → 인덱스 4

    def test_extra_innings_clipped(self):
        row = _make_fake_row(inning=12)
        vec = build_model_b_vector(row)
        inn_section = vec[68:77]
        assert inn_section.sum() == 1.0
        assert inn_section[8] == 1.0  # 12이닝 → 9로 클리핑 → 인덱스 8


# =============================================================================
# Sliding window + sub-token masking
# =============================================================================


class TestSlidingWindow:
    def test_makes_correct_number_of_sequences(self):
        n = 410
        vectors = np.random.randn(n, MODEL_C_DIM).astype(np.float32)
        labels = np.zeros(n, dtype=np.int64)
        hit_locs = np.full(n, -1, dtype=np.int64)
        seqs, t10, thl = make_sequences_for_batter(vectors, labels, hit_locs, seq_length=400)
        assert len(seqs) == n - 400 + 1  # 11 sequences

    def test_short_batter_returns_empty(self):
        vectors = np.random.randn(200, MODEL_C_DIM).astype(np.float32)
        labels = np.zeros(200, dtype=np.int64)
        hit_locs = np.full(200, -1, dtype=np.int64)
        seqs, _, _ = make_sequences_for_batter(vectors, labels, hit_locs, seq_length=400)
        assert len(seqs) == 0

    def test_last_pitch_masked(self):
        n = 400
        vectors = np.ones((n, MODEL_C_DIM), dtype=np.float32)
        labels = np.zeros(n, dtype=np.int64)
        hit_locs = np.full(n, -1, dtype=np.int64)
        seqs, _, _ = make_sequences_for_batter(vectors, labels, hit_locs, seq_length=400)
        seq = seqs[0]
        # 마지막 pitch의 outcome 부분은 0
        assert np.all(seq[-1, OUTCOME_START:OUTCOME_END] == 0.0)
        # 399번째 pitch (마지막 직전)는 원본 그대로
        assert np.all(seq[-2, OUTCOME_START:OUTCOME_END] == 1.0)

    def test_preserves_history(self):
        """직전 399개 pitch는 마스킹 없이 원본 유지."""
        n = 400
        vectors = np.ones((n, MODEL_C_DIM), dtype=np.float32) * 0.5
        labels = np.zeros(n, dtype=np.int64)
        hit_locs = np.full(n, -1, dtype=np.int64)
        seqs, _, _ = make_sequences_for_batter(vectors, labels, hit_locs, seq_length=400)
        seq = seqs[0]
        # 399개 history 전체가 0.5 유지
        assert np.allclose(seq[:399], 0.5)


class TestApplySubtokenMask:
    def test_zeros_outcome(self):
        seq = np.ones((400, MODEL_C_DIM), dtype=np.float32)
        masked = apply_subtoken_mask(seq)
        assert np.all(masked[-1, OUTCOME_START:OUTCOME_END] == 0.0)

    def test_does_not_modify_original(self):
        seq = np.ones((400, MODEL_C_DIM), dtype=np.float32)
        _ = apply_subtoken_mask(seq)
        assert np.all(seq[-1, OUTCOME_START:OUTCOME_END] == 1.0)  # 원본 유지

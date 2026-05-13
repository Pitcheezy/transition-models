"""Data cleaning, feature vector construction, and sequence generation.

Pipeline: raw Parquet → cleaned DataFrame → 87/77-dim vectors → sliding window sequences.
"""

import json
import pickle
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

from src.data.features import (
    CONTINUOUS_FEATURES,
    COUNTS_BALLS,
    COUNTS_STRIKES,
    HANDEDNESS,
    INNINGS,
    MODEL_B_DIM,
    MODEL_C_DIM,
    OUTCOME_END,
    OUTCOME_START,
    OUTS,
    PITCH_TYPES,
    ZONES,
    PitchResult10,
    map_hit_location,
    map_to_10class,
    map_to_4class,
)

# Deprecated 컬럼 (100% 결측)
DEPRECATED_COLS = [
    "umpire",
    "tfs_deprecated",
    "tfs_zulu_deprecated",
    "sv_id",
    "spin_dir",
    "spin_rate_deprecated",
    "break_angle_deprecated",
    "break_length_deprecated",
]


# =============================================================================
# 1. Data cleaning
# =============================================================================


def clean_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Remove deprecated columns, truncated PAs, and rows with missing core features.

    Args:
        df: Raw Statcast DataFrame.

    Returns:
        Cleaned DataFrame (fewer rows than input).
    """
    n_before = len(df)

    # Deprecated 컬럼 삭제
    df = df.drop(columns=[c for c in DEPRECATED_COLS if c in df.columns])

    # truncated_pa 제거
    df = df[df["events"] != "truncated_pa"]

    # 핵심 연속 features 결측 row 제거
    df = df.dropna(subset=CONTINUOUS_FEATURES)

    # game_date를 datetime으로
    df["game_date"] = pd.to_datetime(df["game_date"])

    return df.reset_index(drop=True)


# =============================================================================
# 2. Train/Val/Test split
# =============================================================================


def split_by_season(
    df: pd.DataFrame,
    train_years: list[int] | None = None,
) -> dict[str, pd.DataFrame]:
    """Split data by season and month.

    Train: all train_years (default [2023])
    Val:   last year in df, months 1-6
    Test:  last year in df, months 7+

    With train_years=[2022, 2023] and data covering 2022-2024:
        Train: 2022 + 2023 full seasons
        Val:   2024 months 1-6
        Test:  2024 months 7+

    Args:
        df: Cleaned DataFrame with datetime game_date.
        train_years: List of years for training. Default [2023].

    Returns:
        Dict with keys "train", "val", "test".
    """
    if train_years is None:
        train_years = [2023]

    df["_year"] = df["game_date"].dt.year
    df["_month"] = df["game_date"].dt.month

    test_year = df["_year"].max()

    train = df[df["_year"].isin(train_years)].copy()
    val = df[(df["_year"] == test_year) & (df["_month"] <= 6)].copy()
    test = df[(df["_year"] == test_year) & (df["_month"] >= 7)].copy()

    for split in [train, val, test]:
        split.drop(columns=["_year", "_month"], inplace=True)

    return {
        "train": train.reset_index(drop=True),
        "val": val.reset_index(drop=True),
        "test": test.reset_index(drop=True),
    }


# =============================================================================
# 3. Scaler / pitch type list
# =============================================================================


def fit_scaler(df: pd.DataFrame) -> StandardScaler:
    """Fit StandardScaler on training data continuous features.

    Args:
        df: Training split DataFrame.

    Returns:
        Fitted StandardScaler.
    """
    scaler = StandardScaler()
    scaler.fit(df[CONTINUOUS_FEATURES].values)
    return scaler


def determine_pitch_types(df: pd.DataFrame) -> list[str]:
    """Return the canonical pitch type list from training data.

    Uses the predefined 17 types from features.py. Any pitch_type not in
    the list is mapped to index -1 (treated as all-zeros one-hot).

    Args:
        df: Training split DataFrame.

    Returns:
        List of 17 pitch type codes.
    """
    return PITCH_TYPES


# =============================================================================
# 4. Base state helper
# =============================================================================


def derive_base_state(on_1b, on_2b, on_3b) -> int:
    """Convert base runner presence to 0-7 integer.

    Encoding: 4*bool(3B) + 2*bool(2B) + 1*bool(1B).

    Args:
        on_1b, on_2b, on_3b: Runner IDs or NaN.

    Returns:
        Integer 0-7.
    """
    b1 = 1 if pd.notna(on_1b) else 0
    b2 = 1 if pd.notna(on_2b) else 0
    b3 = 1 if pd.notna(on_3b) else 0
    return 4 * b3 + 2 * b2 + b1


# =============================================================================
# 5. Vector builders
# =============================================================================


def _one_hot(value, categories: list, allow_missing: bool = False) -> np.ndarray:
    """Create a one-hot vector."""
    vec = np.zeros(len(categories), dtype=np.float32)
    if value in categories:
        vec[categories.index(value)] = 1.0
    elif not allow_missing:
        pass  # 알 수 없는 값은 all-zeros
    return vec


def build_model_c_vector(
    row: pd.Series,
    scaler: StandardScaler | None = None,
    pitch_types: list[str] | None = None,
    mask_outcome: bool = False,
) -> np.ndarray:
    """Convert one pitch row to an 87-dim Model C feature vector.

    Layout (87 dims):
        [0:15]   continuous features (standardized)
        [15:32]  pitch_type one-hot (17)
        [32:46]  zone one-hot (14)
        [46:50]  balls one-hot (4)
        [50:53]  strikes one-hot (3)
        [53:56]  outs one-hot (3)
        [56:64]  base_state one-hot (8)
        [64:66]  stand one-hot (2)
        [66:68]  p_throws one-hot (2)
        [68:78]  pitch_result one-hot (10) — masked if mask_outcome
        [78:87]  hit_location one-hot (9) — masked if mask_outcome

    Args:
        row: Single pitch row from Statcast DataFrame.
        scaler: Fitted StandardScaler for continuous features.
        pitch_types: List of 17 pitch type codes.
        mask_outcome: If True, zero out pitch_result and hit_location.

    Returns:
        np.ndarray of shape (87,).
    """
    if pitch_types is None:
        pitch_types = PITCH_TYPES

    parts = []

    # 연속 features (15)
    cont = np.array([row[f] for f in CONTINUOUS_FEATURES], dtype=np.float32)
    if scaler is not None:
        cont = scaler.transform(cont.reshape(1, -1))[0].astype(np.float32)
    parts.append(cont)

    # pitch_type one-hot (17)
    parts.append(_one_hot(row.get("pitch_type"), pitch_types))

    # zone one-hot (14)
    zone_val = int(row["zone"]) if pd.notna(row.get("zone")) else -1
    parts.append(_one_hot(zone_val, ZONES))

    # balls one-hot (4)
    balls_val = int(row["balls"]) if pd.notna(row.get("balls")) else -1
    parts.append(_one_hot(balls_val, COUNTS_BALLS))

    # strikes one-hot (3)
    strikes_val = int(row["strikes"]) if pd.notna(row.get("strikes")) else -1
    parts.append(_one_hot(strikes_val, COUNTS_STRIKES))

    # outs one-hot (3)
    outs_val = int(row["outs_when_up"]) if pd.notna(row.get("outs_when_up")) else -1
    parts.append(_one_hot(outs_val, OUTS))

    # base_state one-hot (8)
    bs = derive_base_state(row.get("on_1b"), row.get("on_2b"), row.get("on_3b"))
    bs_vec = np.zeros(8, dtype=np.float32)
    bs_vec[bs] = 1.0
    parts.append(bs_vec)

    # stand one-hot (2)
    parts.append(_one_hot(row.get("stand"), HANDEDNESS))

    # p_throws one-hot (2)
    parts.append(_one_hot(row.get("p_throws"), HANDEDNESS))

    # pitch_result one-hot (10)
    if mask_outcome:
        parts.append(np.zeros(PitchResult10.NUM_CLASSES, dtype=np.float32))
    else:
        label_10 = map_to_10class(row.get("description"), row.get("events"))
        pr_vec = np.zeros(PitchResult10.NUM_CLASSES, dtype=np.float32)
        if label_10 is not None:
            pr_vec[label_10] = 1.0
        parts.append(pr_vec)

    # hit_location one-hot (9)
    if mask_outcome:
        parts.append(np.zeros(9, dtype=np.float32))
    else:
        hl = map_hit_location(row.get("hit_location"))
        hl_vec = np.zeros(9, dtype=np.float32)
        if hl is not None:
            hl_vec[hl] = 1.0
        parts.append(hl_vec)

    vec = np.concatenate(parts)
    assert vec.shape == (MODEL_C_DIM,), f"Expected ({MODEL_C_DIM},), got {vec.shape}"
    return vec


def build_model_b_vector(
    row: pd.Series,
    scaler: StandardScaler | None = None,
    pitch_types: list[str] | None = None,
) -> np.ndarray:
    """Convert one pitch row to a 77-dim Model B feature vector.

    Layout (77 dims):
        [0:15]   continuous features (standardized)
        [15:32]  pitch_type one-hot (17)
        [32:46]  zone one-hot (14)
        [46:50]  balls one-hot (4)
        [50:53]  strikes one-hot (3)
        [53:56]  outs one-hot (3)
        [56:64]  base_state one-hot (8)
        [64:66]  stand one-hot (2)
        [66:68]  p_throws one-hot (2)
        [68:77]  inning one-hot (9, capped at 9)

    Args:
        row: Single pitch row from Statcast DataFrame.
        scaler: Fitted StandardScaler for continuous features.
        pitch_types: List of 17 pitch type codes.

    Returns:
        np.ndarray of shape (77,).
    """
    if pitch_types is None:
        pitch_types = PITCH_TYPES

    parts = []

    # 연속 features (15)
    cont = np.array([row[f] for f in CONTINUOUS_FEATURES], dtype=np.float32)
    if scaler is not None:
        cont = scaler.transform(cont.reshape(1, -1))[0].astype(np.float32)
    parts.append(cont)

    # pitch_type one-hot (17)
    parts.append(_one_hot(row.get("pitch_type"), pitch_types))

    # zone one-hot (14)
    zone_val = int(row["zone"]) if pd.notna(row.get("zone")) else -1
    parts.append(_one_hot(zone_val, ZONES))

    # balls one-hot (4)
    balls_val = int(row["balls"]) if pd.notna(row.get("balls")) else -1
    parts.append(_one_hot(balls_val, COUNTS_BALLS))

    # strikes one-hot (3)
    strikes_val = int(row["strikes"]) if pd.notna(row.get("strikes")) else -1
    parts.append(_one_hot(strikes_val, COUNTS_STRIKES))

    # outs one-hot (3)
    outs_val = int(row["outs_when_up"]) if pd.notna(row.get("outs_when_up")) else -1
    parts.append(_one_hot(outs_val, OUTS))

    # base_state one-hot (8)
    bs = derive_base_state(row.get("on_1b"), row.get("on_2b"), row.get("on_3b"))
    bs_vec = np.zeros(8, dtype=np.float32)
    bs_vec[bs] = 1.0
    parts.append(bs_vec)

    # stand one-hot (2)
    parts.append(_one_hot(row.get("stand"), HANDEDNESS))

    # p_throws one-hot (2)
    parts.append(_one_hot(row.get("p_throws"), HANDEDNESS))

    # inning one-hot (9, 연장은 9로 클리핑)
    inning_val = min(int(row["inning"]), 9) if pd.notna(row.get("inning")) else -1
    parts.append(_one_hot(inning_val, INNINGS))

    vec = np.concatenate(parts)
    assert vec.shape == (MODEL_B_DIM,), f"Expected ({MODEL_B_DIM},), got {vec.shape}"
    return vec


# =============================================================================
# 6. Batch vector construction (vectorized for speed)
# =============================================================================


def build_vectors_batch(
    df: pd.DataFrame,
    scaler: StandardScaler | None,
    pitch_types: list[str],
    model: str = "C",
) -> np.ndarray:
    """Convert an entire DataFrame to feature vectors (vectorized).

    Args:
        df: Cleaned DataFrame.
        scaler: Fitted StandardScaler.
        pitch_types: Canonical pitch type list.
        model: "C" for 87-dim, "B" for 77-dim.

    Returns:
        np.ndarray of shape (N, 87) or (N, 77).
    """
    n = len(df)

    # === 연속 features (15) ===
    cont = df[CONTINUOUS_FEATURES].values.astype(np.float32)
    if scaler is not None:
        cont = scaler.transform(cont).astype(np.float32)

    # === pitch_type one-hot (17) ===
    pt_map = {pt: i for i, pt in enumerate(pitch_types)}
    pt_idx = df["pitch_type"].map(pt_map).fillna(-1).astype(int).values
    pt_oh = np.zeros((n, len(pitch_types)), dtype=np.float32)
    valid = pt_idx >= 0
    pt_oh[valid, pt_idx[valid]] = 1.0

    # === zone one-hot (14) ===
    zone_map = {z: i for i, z in enumerate(ZONES)}
    z_idx = df["zone"].map(zone_map).fillna(-1).astype(int).values
    z_oh = np.zeros((n, len(ZONES)), dtype=np.float32)
    valid = z_idx >= 0
    z_oh[valid, z_idx[valid]] = 1.0

    # === balls one-hot (4) ===
    b_idx = df["balls"].fillna(-1).astype(int).values
    b_oh = np.zeros((n, len(COUNTS_BALLS)), dtype=np.float32)
    valid = (b_idx >= 0) & (b_idx < len(COUNTS_BALLS))
    b_oh[valid, b_idx[valid]] = 1.0

    # === strikes one-hot (3) ===
    s_idx = df["strikes"].fillna(-1).astype(int).values
    s_oh = np.zeros((n, len(COUNTS_STRIKES)), dtype=np.float32)
    valid = (s_idx >= 0) & (s_idx < len(COUNTS_STRIKES))
    s_oh[valid, s_idx[valid]] = 1.0

    # === outs one-hot (3) ===
    o_idx = df["outs_when_up"].fillna(-1).astype(int).values
    o_oh = np.zeros((n, len(OUTS)), dtype=np.float32)
    valid = (o_idx >= 0) & (o_idx < len(OUTS))
    o_oh[valid, o_idx[valid]] = 1.0

    # === base_state one-hot (8) ===
    b1 = df["on_1b"].notna().astype(int).values
    b2 = df["on_2b"].notna().astype(int).values
    b3 = df["on_3b"].notna().astype(int).values
    bs_idx = 4 * b3 + 2 * b2 + b1
    bs_oh = np.zeros((n, 8), dtype=np.float32)
    bs_oh[np.arange(n), bs_idx] = 1.0

    # === stand one-hot (2) ===
    stand_map = {h: i for i, h in enumerate(HANDEDNESS)}
    st_idx = df["stand"].map(stand_map).fillna(-1).astype(int).values
    st_oh = np.zeros((n, len(HANDEDNESS)), dtype=np.float32)
    valid = st_idx >= 0
    st_oh[valid, st_idx[valid]] = 1.0

    # === p_throws one-hot (2) ===
    pt2_idx = df["p_throws"].map(stand_map).fillna(-1).astype(int).values
    pt2_oh = np.zeros((n, len(HANDEDNESS)), dtype=np.float32)
    valid = pt2_idx >= 0
    pt2_oh[valid, pt2_idx[valid]] = 1.0

    if model == "C":
        # === pitch_result one-hot (10) ===
        labels_10 = df.apply(
            lambda r: map_to_10class(r["description"], r["events"]), axis=1
        ).values
        pr_oh = np.zeros((n, PitchResult10.NUM_CLASSES), dtype=np.float32)
        for i, lbl in enumerate(labels_10):
            if lbl is not None:
                pr_oh[i, lbl] = 1.0

        # === hit_location one-hot (9) ===
        hl_vals = df["hit_location"].apply(map_hit_location).values
        hl_oh = np.zeros((n, 9), dtype=np.float32)
        for i, hl in enumerate(hl_vals):
            if hl is not None and not (isinstance(hl, float) and np.isnan(hl)):
                hl_oh[i, int(hl)] = 1.0

        vectors = np.concatenate(
            [cont, pt_oh, z_oh, b_oh, s_oh, o_oh, bs_oh, st_oh, pt2_oh, pr_oh, hl_oh],
            axis=1,
        )
        assert vectors.shape[1] == MODEL_C_DIM
    else:
        # === inning one-hot (9) ===
        inn_map = {inn: i for i, inn in enumerate(INNINGS)}
        inn_raw = df["inning"].fillna(1).astype(int).clip(upper=9).values
        inn_idx = np.array([inn_map.get(v, -1) for v in inn_raw])
        inn_oh = np.zeros((n, len(INNINGS)), dtype=np.float32)
        valid = inn_idx >= 0
        inn_oh[valid, inn_idx[valid]] = 1.0

        vectors = np.concatenate(
            [cont, pt_oh, z_oh, b_oh, s_oh, o_oh, bs_oh, st_oh, pt2_oh, inn_oh],
            axis=1,
        )
        assert vectors.shape[1] == MODEL_B_DIM

    return vectors


# =============================================================================
# 7. Labels extraction
# =============================================================================


def extract_labels_4class(df: pd.DataFrame) -> np.ndarray:
    """Extract 4-class labels for Model B.

    Args:
        df: Cleaned DataFrame.

    Returns:
        np.ndarray of shape (N,) with int values 0-3.
    """
    labels = df["description"].apply(map_to_4class).values
    # 매핑 불가 없어야 함 (clean_dataframe 이후)
    result = np.array([l if l is not None else -1 for l in labels], dtype=np.int64)
    return result


def extract_labels_10class(df: pd.DataFrame) -> np.ndarray:
    """Extract 10-class labels for Model C.

    Args:
        df: Cleaned DataFrame.

    Returns:
        np.ndarray of shape (N,) with int values 0-9 or -1 (unmappable).
    """
    labels = df.apply(
        lambda r: map_to_10class(r["description"], r["events"]), axis=1
    ).values
    result = np.array([l if l is not None else -1 for l in labels], dtype=np.int64)
    return result


def extract_hit_location(df: pd.DataFrame) -> np.ndarray:
    """Extract hit location labels (0-8, or -1 if not InPlay).

    Args:
        df: Cleaned DataFrame.

    Returns:
        np.ndarray of shape (N,) with int values 0-8 or -1.
    """
    locs = df["hit_location"].apply(map_hit_location).values
    result = np.array(
        [int(l) if l is not None and not (isinstance(l, float) and np.isnan(l)) else -1
         for l in locs],
        dtype=np.int64,
    )
    return result


# =============================================================================
# 8. Sliding window + sub-token masking
# =============================================================================


def make_sequences_for_batter(
    batter_vectors: np.ndarray,
    batter_labels_10: np.ndarray,
    batter_hit_locs: np.ndarray,
    seq_length: int = 400,
    stride: int = 1,
) -> tuple[list[np.ndarray], list[int], list[int]]:
    """Generate sliding window sequences from a single batter's pitch vectors.

    The last pitch in each sequence gets sub-token masking applied
    (outcome features zeroed out). The target is the original label.

    Args:
        batter_vectors: (M, 87) feature vectors, already time-sorted.
        batter_labels_10: (M,) 10-class labels.
        batter_hit_locs: (M,) hit location labels.
        seq_length: Window size (default 400).
        stride: Step between windows (default 1).

    Returns:
        Tuple of (sequences, target_labels_10, target_hit_locs).
        sequences: list of (seq_length, 87) arrays with last-pitch masking.
        target_labels_10: list of 10-class labels for the last pitch.
        target_hit_locs: list of hit location labels for the last pitch.
    """
    m = len(batter_vectors)
    if m < seq_length:
        return [], [], []

    sequences = []
    targets_10 = []
    targets_hl = []

    for start in range(0, m - seq_length + 1, stride):
        end = start + seq_length
        seq = batter_vectors[start:end].copy()

        # Sub-token masking: 마지막 pitch의 outcome features를 0 처리
        seq[-1, OUTCOME_START:OUTCOME_END] = 0.0

        sequences.append(seq)
        targets_10.append(int(batter_labels_10[end - 1]))
        targets_hl.append(int(batter_hit_locs[end - 1]))

    return sequences, targets_10, targets_hl


def apply_subtoken_mask(sequence: np.ndarray) -> np.ndarray:
    """Zero out outcome features (pitch_result + hit_location) of the last pitch.

    Args:
        sequence: (seq_length, 87) array.

    Returns:
        Masked copy of the sequence.
    """
    seq = sequence.copy()
    seq[-1, OUTCOME_START:OUTCOME_END] = 0.0
    return seq


# =============================================================================
# 9. Lazy loading helpers
# =============================================================================


def sort_by_batter_and_time(df: pd.DataFrame) -> pd.DataFrame:
    """Sort DataFrame by batter, then chronologically within each batter.

    Args:
        df: Cleaned DataFrame.

    Returns:
        Sorted DataFrame with reset index.
    """
    return df.sort_values(
        ["batter", "game_date", "at_bat_number", "pitch_number"]
    ).reset_index(drop=True)


def compute_batter_ranges(df: pd.DataFrame) -> dict[int, tuple[int, int]]:
    """Compute (start, end) index ranges for each batter in a sorted DataFrame.

    Args:
        df: DataFrame sorted by batter (via sort_by_batter_and_time).

    Returns:
        Dict mapping batter_id → (start_idx, end_idx) in the sorted array.
    """
    ranges: dict[int, tuple[int, int]] = {}
    batter_col = df["batter"].values
    n = len(batter_col)
    if n == 0:
        return ranges

    current_batter = batter_col[0]
    start = 0
    for i in range(1, n):
        if batter_col[i] != current_batter:
            ranges[int(current_batter)] = (start, i)
            current_batter = batter_col[i]
            start = i
    ranges[int(current_batter)] = (start, n)
    return ranges


def build_valid_indices(
    batter_ranges: dict[int, tuple[int, int]],
    seq_length: int = 400,
    stride: int = 1,
) -> list[tuple[int, int]]:
    """Generate (batter_id, global_start) pairs for lazy sequence loading.

    Only batters with >= seq_length pitches are included. Each index points
    to a valid starting position for a seq_length window in the sorted array.

    Args:
        batter_ranges: Dict from compute_batter_ranges.
        seq_length: Sequence length (default 400).
        stride: Step between consecutive windows (default 1).

    Returns:
        List of (batter_id, global_start_idx) tuples.
    """
    indices = []
    for batter_id, (start, end) in batter_ranges.items():
        n = end - start
        if n < seq_length:
            continue
        for offset in range(0, n - seq_length + 1, stride):
            indices.append((batter_id, start + offset))
    return indices

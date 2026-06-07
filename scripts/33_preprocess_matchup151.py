"""matchup151 preprocessing: 135-dim Arsenal MLP + 16-dim batter context = 151d.

Extends the 135d (MLP135CE) feature vector with per-batter, handedness-matched
rate/mean features from train-split Statcast data.

Feature layout (151 dims):
    [0:77]    Model B features (same as 135d)
    [77:135]  Pitcher Arsenal context (same as 135d)
    [135:151] Batter context (16d, train-only, handedness-matched):
              [135:147] rate features × 12 (swing/whiff/ball/called_strike/in_play/
                         zone/z_swing/o_swing/hit/hr/k/bb)
              [147:151] mean features × 4 (release_speed, plate_x, plate_z, spin_rate)

Join logic (DATA LEAKAGE GUARD):
    batter feature lookup is built from TRAIN years only (2022-2023).
    Each pitch selects the side matching its p_throws value:
        p_throws == "R" -> uses vs_R batter features
        p_throws == "L" -> uses vs_L batter features
    Unrecognized batters -> league-average fallback.
    This correctly conditions on pitcher handedness without leaking test outcomes.

Outputs (in data/processed/):
    vectors_matchup151_10cls_{train,val,test}.npy   (N, 151) float32
    labels_10_matchup151_{train,val,test}.npy        (N,)     int64
    scaler_batter16.pkl                              StandardScaler (fit on train only)
    matchup151_preprocessing_summary.json

Usage:
    cd transition-models
    uv run python scripts/33_preprocess_matchup151.py
"""

from __future__ import annotations

import gc
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.preprocess import (
    build_vectors_batch,
    clean_dataframe,
    extract_labels_10class,
    fit_scaler,
    split_by_season,
)

# ── Paths ─────────────────────────────────────────────────────────────────────
ROOT = Path(__file__).resolve().parent.parent
OUTPUT_DIR = ROOT / "data" / "processed"
RAW_DIR = ROOT / "data" / "raw"
BATTER_DIR = Path(r"C:\Users\zpfh1\Projects\data\data\outputs")

HANDOFF_PATH = Path(r"C:\Users\zpfh1\Projects\data\data\outputs\handoff_v1.parquet")

YEARS = [2022, 2023, 2024]
TRAIN_YEARS = [2022, 2023]

# ── Feature columns (from 21_preprocess_135dim.py) ────────────────────────────
UMAP_COLS = [f"umap_5d_{i}" for i in range(5)]
COUNT_COLS = ["count_cluster_id"]
ARSENAL_FUNC_COLS = [f"arsenal_func_{i:02d}" for i in range(32)]
ARSENAL_MOM_COLS = [f"arsenal_moment_{i:02d}" for i in range(20)]
NEW58_COLS = UMAP_COLS + COUNT_COLS + ARSENAL_FUNC_COLS + ARSENAL_MOM_COLS   # 58 dims
JOIN_KEYS = ["game_pk", "at_bat_number", "pitch_number"]

# ── Batter feature columns (16 dims per side) ─────────────────────────────────
BATTER_RATE_FEATURES = [
    "swing_rate", "whiff_rate", "ball_rate", "called_strike_rate",
    "in_play_rate", "zone_rate", "z_swing_rate", "o_swing_rate",
    "hit_rate", "hr_rate", "k_rate", "bb_rate",
]
BATTER_MEAN_FEATURES = [
    "mean_release_speed", "mean_plate_x", "mean_plate_z", "mean_release_spin_rate",
]
BATTER_FEATURE_COLS = BATTER_RATE_FEATURES + BATTER_MEAN_FEATURES   # 16 dims

MATCHUP151_DIM = 77 + 58 + len(BATTER_FEATURE_COLS)   # 151


# ── Batter lookup ──────────────────────────────────────────────────────────────

class BatterLookup:
    """Maps (batter_id, p_throws) -> 16-dim raw (pre-scale) batter feature vector.

    Built from train-split data only. Unseen batters return league average.
    Handedness matching: p_throws=R -> vs_R features, p_throws=L -> vs_L features.
    """

    def __init__(
        self,
        vs_L: dict[int, np.ndarray],
        vs_R: dict[int, np.ndarray],
        league_avg_L: np.ndarray,
        league_avg_R: np.ndarray,
    ) -> None:
        self._vs_L = vs_L
        self._vs_R = vs_R
        self._avg_L = league_avg_L
        self._avg_R = league_avg_R

    @classmethod
    def from_parquets(cls) -> "BatterLookup":
        """Load from train-only batter feature parquets."""
        vs_L_path = BATTER_DIR / "batter_features_train_only_vs_L.parquet"
        vs_R_path = BATTER_DIR / "batter_features_train_only_vs_R.parquet"
        avg_path = BATTER_DIR / "batter_features_league_avg.json"

        for p in [vs_L_path, vs_R_path, avg_path]:
            if not p.exists():
                raise FileNotFoundError(
                    f"Batter feature file not found: {p}\n"
                    "Run: cd data && uv run python scripts/04_build_batter_features_train_only.py"
                )

        with open(avg_path, encoding="utf-8") as f:
            avg_json = json.load(f)

        league_avg_L = np.array([avg_json["L"][c] for c in BATTER_FEATURE_COLS], dtype=np.float32)
        league_avg_R = np.array([avg_json["R"][c] for c in BATTER_FEATURE_COLS], dtype=np.float32)

        def _load_side(path: Path) -> dict[int, np.ndarray]:
            df = pd.read_parquet(path, columns=["batter"] + BATTER_FEATURE_COLS)
            result = {}
            for row in df.itertuples(index=False):
                batter_id = int(row.batter)
                vec = np.array([getattr(row, f) for f in BATTER_FEATURE_COLS], dtype=np.float32)
                result[batter_id] = vec
            return result

        vs_L = _load_side(vs_L_path)
        vs_R = _load_side(vs_R_path)
        print(f"  BatterLookup: {len(vs_L):,} batters (vs-L), {len(vs_R):,} batters (vs-R)")
        return cls(vs_L=vs_L, vs_R=vs_R, league_avg_L=league_avg_L, league_avg_R=league_avg_R)

    def get_batch(
        self,
        batter_ids: np.ndarray,
        p_throws: pd.Series,
    ) -> tuple[np.ndarray, int]:
        """Return (N, 16) raw batter feature matrix and fallback count."""
        N = len(batter_ids)
        out = np.empty((N, len(BATTER_FEATURE_COLS)), dtype=np.float32)
        n_fallback = 0
        for i, (bid, side) in enumerate(zip(batter_ids, p_throws)):
            bid = int(bid)
            lookup = self._vs_L if side == "L" else self._vs_R
            avg = self._avg_L if side == "L" else self._avg_R
            vec = lookup.get(bid)
            if vec is None or np.isnan(vec).any():
                out[i] = avg
                n_fallback += 1
            else:
                out[i] = vec
        return out, n_fallback


# ── Preprocessing ──────────────────────────────────────────────────────────────

_REQUIRED_COLS = [
    # for clean_dataframe
    "events", "game_date",
    # continuous features (15)
    "release_speed", "release_pos_x", "release_pos_y", "release_pos_z",
    "pfx_x", "pfx_z", "release_spin_rate", "plate_x", "plate_z",
    "vx0", "vy0", "vz0", "ax", "ay", "az",
    # for build_vectors_batch (Model B)
    "pitch_type", "zone", "balls", "strikes", "outs_when_up",
    "on_1b", "on_2b", "on_3b", "stand", "p_throws", "inning",
    # for extract_labels_10class
    "description",
    # for batter lookup + handoff join
    "batter", "game_pk", "at_bat_number", "pitch_number",
]


def load_seasons(years: list[int]) -> pd.DataFrame:
    frames = []
    for yr in years:
        p = RAW_DIR / str(yr) / f"statcast_{yr}.parquet"
        if not p.exists():
            print(f"[ERROR] 데이터 파일 없음: {p}")
            sys.exit(1)
        df = pd.read_parquet(p, columns=_REQUIRED_COLS)
        frames.append(df)
        print(f"  {yr}: {len(df):,} rows")
    return pd.concat(frames, ignore_index=True)


def load_handoff_v1() -> pd.DataFrame:
    if not HANDOFF_PATH.exists():
        print(f"[ERROR] handoff_v1.parquet 없음: {HANDOFF_PATH}")
        sys.exit(1)
    cols = JOIN_KEYS + NEW58_COLS
    df = pd.read_parquet(HANDOFF_PATH, columns=cols)
    df = df.drop_duplicates(subset=JOIN_KEYS, keep="first")
    print(f"  handoff_v1: {len(df):,} rows, {len(df.columns)} cols")
    return df


def build_new58_matrix(
    df_split: pd.DataFrame, handoff: pd.DataFrame
) -> tuple[np.ndarray, np.ndarray]:
    """Identical to 21_preprocess_135dim.py build logic."""
    merged = df_split[JOIN_KEYS].copy()
    merged = merged.merge(handoff[JOIN_KEYS + NEW58_COLS], on=JOIN_KEYS, how="left")
    new_feat = merged[NEW58_COLS].values.astype(np.float32)
    nan_mask = np.isnan(new_feat).any(axis=1)
    valid_mask = ~nan_mask
    print(f"  Arsenal join: {valid_mask.sum():,} / {len(df_split):,} matched ({nan_mask.sum():,} missing)")
    return new_feat, valid_mask


def main() -> None:
    t_start = time.time()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    print("=== 1. 원본 데이터 로드 ===")
    df_raw = load_seasons(YEARS)
    print(f"  전체: {len(df_raw):,} rows")

    df_clean = clean_dataframe(df_raw)
    print(f"  정제 후: {len(df_clean):,} rows")

    splits = split_by_season(df_clean, train_years=TRAIN_YEARS)
    for name, sdf in splits.items():
        print(f"  {name}: {len(sdf):,} rows")

    print("\n=== 2. Scaler (77d) 로드 ===")
    scaler_path = OUTPUT_DIR / "scaler.pkl"
    if scaler_path.exists():
        with open(scaler_path, "rb") as f:
            scaler = pickle.load(f)
        print("  scaler.pkl 재사용")
    else:
        scaler = fit_scaler(splits["train"])
        with open(scaler_path, "wb") as f:
            pickle.dump(scaler, f)
        print("  scaler fit + 저장")

    with open(OUTPUT_DIR / "pitch_types.json") as f:
        pitch_types = json.load(f)

    print("\n=== 3. handoff_v1 로드 (arsenal 58d) ===")
    handoff = load_handoff_v1()

    print("\n=== 4. BatterLookup 로드 (train-only) ===")
    batter_lookup = BatterLookup.from_parquets()

    summary = {
        "years": YEARS,
        "train_years": TRAIN_YEARS,
        "matchup151_dim": MATCHUP151_DIM,
        "batter_feature_cols": BATTER_FEATURE_COLS,
        "n_batter_features": len(BATTER_FEATURE_COLS),
        "data_leakage_guard": "batter features from train (2022-2023) only",
        "splits": {},
    }

    scaler_new58: StandardScaler | None = None
    scaler_batter: StandardScaler | None = None

    # Free large DataFrames no longer needed before per-split processing
    del df_raw, df_clean
    gc.collect()

    print("\n=== 5. Split별 처리 ===")
    for split_name, sdf in splits.items():
        print(f"\n--- {split_name.upper()} ---")

        # 77d base vectors
        vecs_77 = build_vectors_batch(sdf, scaler, pitch_types, model="B")
        labels_10 = extract_labels_10class(sdf)
        print(f"  77d vectors: {vecs_77.shape}")

        # Arsenal 58d join
        new58_raw, valid_mask = build_new58_matrix(sdf, handoff)

        # Apply valid_mask
        vecs_77 = vecs_77[valid_mask]
        labels_10 = labels_10[valid_mask]
        new58_raw = new58_raw[valid_mask]
        sdf_valid = sdf[valid_mask].reset_index(drop=True)
        del sdf
        gc.collect()

        # Normalise new58
        if split_name == "train":
            scaler_new58 = StandardScaler()
            valid_label10 = labels_10 >= 0
            # Fit on a contiguous sample to avoid memory fragmentation
            fit_idx = np.where(valid_label10)[0]
            scaler_new58.fit(new58_raw[fit_idx])
            del fit_idx
            with open(OUTPUT_DIR / "scaler_new58.pkl", "wb") as f:
                pickle.dump(scaler_new58, f)
            print("  scaler_new58 fit + 저장 (재확인)")
        new58_norm = scaler_new58.transform(new58_raw).astype(np.float32)
        del new58_raw
        gc.collect()

        # 135d concat (in-place build)
        vecs_135 = np.concatenate([vecs_77, new58_norm], axis=1)
        del vecs_77, new58_norm
        gc.collect()
        assert vecs_135.shape[1] == 135, f"Expected 135, got {vecs_135.shape[1]}"

        # Batter 16d lookup (handedness-matched, train-only)
        batter_ids = sdf_valid["batter"].to_numpy(dtype=np.int64) if "batter" in sdf_valid.columns else np.zeros(len(sdf_valid), dtype=np.int64)
        p_throws_col = sdf_valid["p_throws"] if "p_throws" in sdf_valid.columns else pd.Series(["R"] * len(sdf_valid))
        batter_raw, n_fallback = batter_lookup.get_batch(batter_ids, p_throws_col)
        del batter_ids, p_throws_col, sdf_valid
        gc.collect()

        fallback_pct = 100.0 * n_fallback / max(len(batter_raw), 1)
        print(f"  Batter lookup: {n_fallback:,} / {len(batter_raw):,} fallback ({fallback_pct:.1f}%)")

        # Normalise batter 16d
        if split_name == "train":
            scaler_batter = StandardScaler()
            valid_label10 = labels_10 >= 0
            fit_idx = np.where(valid_label10)[0]
            scaler_batter.fit(batter_raw[fit_idx])
            del fit_idx
            with open(OUTPUT_DIR / "scaler_batter16.pkl", "wb") as f:
                pickle.dump(scaler_batter, f)
            print("  scaler_batter16 fit + 저장")
        batter_norm = scaler_batter.transform(batter_raw).astype(np.float32)
        del batter_raw
        gc.collect()

        # 151d concat
        vecs_151 = np.concatenate([vecs_135, batter_norm], axis=1)
        del vecs_135, batter_norm
        gc.collect()
        assert vecs_151.shape[1] == MATCHUP151_DIM, f"Expected {MATCHUP151_DIM}, got {vecs_151.shape[1]}"

        # Compute stats before saving/deleting
        n_valid_labels = int((labels_10 >= 0).sum())
        label10_dist = {int(k): int(v) for k, v in zip(*np.unique(labels_10[labels_10 >= 0], return_counts=True))}

        # Save
        np.save(OUTPUT_DIR / f"vectors_matchup151_10cls_{split_name}.npy", vecs_151)
        np.save(OUTPUT_DIR / f"labels_10_matchup151_{split_name}.npy", labels_10)
        shape_saved = vecs_151.shape
        del vecs_151
        gc.collect()

        print(f"  Saved: vectors_matchup151_10cls_{split_name}.npy  shape={shape_saved}")
        print(f"  10-class valid: {n_valid_labels:,} / {len(labels_10):,}")

        summary["splits"][split_name] = {
            "n_rows_after_arsenal_join": int(valid_mask.sum()),
            "n_batter_fallback": int(n_fallback),
            "batter_fallback_pct": round(fallback_pct, 2),
            "n_label10_valid": n_valid_labels,
            "label10_dist": label10_dist,
        }

    elapsed = round(time.time() - t_start, 1)
    summary["elapsed_seconds"] = elapsed

    meta_path = OUTPUT_DIR / "matchup151_preprocessing_summary.json"
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n=== 전처리 완료: {elapsed}s ===")
    print(f"  matchup151_dim={MATCHUP151_DIM}")
    for split_name in splits:
        p = OUTPUT_DIR / f"vectors_matchup151_10cls_{split_name}.npy"
        arr = np.load(p, mmap_mode="r")
        print(f"  {p.name}: {arr.shape}")


if __name__ == "__main__":
    main()

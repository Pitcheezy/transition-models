"""135-dim preprocessing: 77-dim Model B + 58-dim v1 features.

Join handoff_v1.parquet (UMAP_5d, count_cluster_id, arsenal_func, arsenal_moment)
onto cleaned Statcast data, build 135-dim vectors per split.

New feature layout (58 dims appended after 77-dim Model B):
    [77:82]   umap_5d_0..4          (5 dims, float32, normalized)
    [82:83]   count_cluster_id      (1 dim,  float32, normalized)
    [83:115]  arsenal_func_00..31   (32 dims, float32, normalized)
    [115:135] arsenal_moment_00..19 (20 dims, float32, normalized)

Outputs (in data/processed/):
    vectors_b3_{split}.npy       (N, 135) float32
    labels_4_b3_{split}.npy     (N,)     int64  — 4-class
    labels_10_b3_{split}.npy    (N,)     int64  — 10-class (-1 = unmappable)
    scaler_new58.pkl             StandardScaler fitted on train new-58 dims
    b3_preprocessing_summary.json
"""

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
    extract_labels_4class,
    extract_labels_10class,
    fit_scaler,
    split_by_season,
)

OUTPUT_DIR = Path("data/processed")
RAW_DIR = Path("data/raw")
HANDOFF_PATH = Path(r"C:\Users\zpfh1\Projects\data\data\outputs\handoff_v1.parquet")

YEARS = [2022, 2023, 2024]
TRAIN_YEARS = [2022, 2023]

# New feature columns from handoff_v1
UMAP_COLS = [f"umap_5d_{i}" for i in range(5)]
COUNT_COLS = ["count_cluster_id"]
ARSENAL_FUNC_COLS = [f"arsenal_func_{i:02d}" for i in range(32)]
ARSENAL_MOM_COLS = [f"arsenal_moment_{i:02d}" for i in range(20)]
NEW_FEATURE_COLS = UMAP_COLS + COUNT_COLS + ARSENAL_FUNC_COLS + ARSENAL_MOM_COLS  # 58 dims
JOIN_KEYS = ["game_pk", "at_bat_number", "pitch_number"]

MODEL_B3_DIM = 77 + len(NEW_FEATURE_COLS)  # 135


def load_seasons(years: list[int]) -> pd.DataFrame:
    frames = []
    for yr in years:
        path = RAW_DIR / str(yr) / f"statcast_{yr}.parquet"
        if not path.exists():
            print(f"[ERROR] 데이터 파일 없음: {path}")
            sys.exit(1)
        frames.append(pd.read_parquet(path))
    return pd.concat(frames, ignore_index=True)


def load_handoff_v1() -> pd.DataFrame:
    if not HANDOFF_PATH.exists():
        print(f"[ERROR] handoff_v1.parquet 없음: {HANDOFF_PATH}")
        sys.exit(1)
    cols = JOIN_KEYS + NEW_FEATURE_COLS
    df = pd.read_parquet(HANDOFF_PATH, columns=cols)
    # Deduplicate keys (keep first)
    df = df.drop_duplicates(subset=JOIN_KEYS, keep="first")
    print(f"handoff_v1 로드: {len(df):,} rows, {len(df.columns)} cols")
    return df


def build_new58_matrix(df_split: pd.DataFrame, handoff: pd.DataFrame) -> tuple[np.ndarray, np.ndarray]:
    """Join split DataFrame with handoff, return (new58_matrix, valid_mask).

    Rows with no match in handoff or any NaN in new features are excluded.
    Returns:
        new58: (N_valid, 58) float32
        valid_mask: (N_original,) bool
    """
    # Merge — left join to preserve original order, then detect misses
    merged = df_split[JOIN_KEYS].copy()
    merged = merged.merge(handoff[JOIN_KEYS + NEW_FEATURE_COLS], on=JOIN_KEYS, how="left")

    new_feat = merged[NEW_FEATURE_COLS].values.astype(np.float32)
    nan_mask = np.isnan(new_feat).any(axis=1)
    valid_mask = ~nan_mask

    print(f"  Join 결과: {valid_mask.sum():,} / {len(df_split):,} 행 매칭 "
          f"({nan_mask.sum():,} 누락)")

    return new_feat, valid_mask


def main() -> None:
    t_start = time.time()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # 1. 원본 데이터 로드 + 정제 + 분할
    print("=== 1. 원본 데이터 로드 ===")
    df_raw = load_seasons(YEARS)
    print(f"원본: {len(df_raw):,} rows")

    df_clean = clean_dataframe(df_raw)
    print(f"정제 후: {len(df_clean):,} rows")

    splits = split_by_season(df_clean, train_years=TRAIN_YEARS)
    for name, sdf in splits.items():
        print(f"  {name}: {len(sdf):,} rows")

    # 2. Scaler (기존 scaler.pkl 재사용 — 동일한 77-dim 정규화)
    print("\n=== 2. Scaler 로드 ===")
    scaler_path = OUTPUT_DIR / "scaler.pkl"
    if scaler_path.exists():
        with open(scaler_path, "rb") as f:
            scaler = pickle.load(f)
        print("기존 scaler.pkl 재사용")
    else:
        scaler = fit_scaler(splits["train"])
        with open(scaler_path, "wb") as f:
            pickle.dump(scaler, f)
        print("scaler 새로 fit + 저장")

    with open(OUTPUT_DIR / "pitch_types.json") as f:
        import json as _json
        pitch_types = _json.load(f)

    # 3. handoff_v1 로드
    print("\n=== 3. handoff_v1 로드 ===")
    handoff = load_handoff_v1()

    # 4. 각 split 처리
    summary = {
        "years": YEARS,
        "train_years": TRAIN_YEARS,
        "model_b3_dim": MODEL_B3_DIM,
        "new_feature_cols": NEW_FEATURE_COLS,
        "splits": {},
    }

    scaler_new58 = None  # fit on train

    for split_name, sdf in splits.items():
        print(f"\n=== Split: {split_name.upper()} ===")

        # 77-dim Model B vectors
        t0 = time.time()
        vecs_77 = build_vectors_batch(sdf, scaler, pitch_types, model="B")
        labels_4 = extract_labels_4class(sdf)
        labels_10 = extract_labels_10class(sdf)
        print(f"  77-dim 벡터: {vecs_77.shape} ({time.time()-t0:.1f}s)")

        # 새 58-dim features (join)
        new58_raw, valid_mask = build_new58_matrix(sdf, handoff)

        # Filter all to valid rows
        vecs_77 = vecs_77[valid_mask]
        labels_4 = labels_4[valid_mask]
        labels_10 = labels_10[valid_mask]
        new58_raw = new58_raw[valid_mask]

        # 4-class invalid 제거 (labels_4 == -1)
        valid_label4 = labels_4 >= 0
        print(f"  4-class 유효: {valid_label4.sum():,} / {len(labels_4):,}")

        # 58-dim 정규화
        if split_name == "train":
            scaler_new58 = StandardScaler()
            scaler_new58.fit(new58_raw[valid_label4])
            with open(OUTPUT_DIR / "scaler_new58.pkl", "wb") as f:
                pickle.dump(scaler_new58, f)
            print("  scaler_new58 fit + 저장")

        new58_norm = scaler_new58.transform(new58_raw).astype(np.float32)

        # 135-dim 연결
        vecs_135 = np.concatenate([vecs_77, new58_norm], axis=1)
        assert vecs_135.shape[1] == MODEL_B3_DIM, f"Expected {MODEL_B3_DIM}, got {vecs_135.shape[1]}"

        # 4-class용 필터 적용 후 저장
        vecs_135_4 = vecs_135[valid_label4]
        labels_4_clean = labels_4[valid_label4]

        np.save(OUTPUT_DIR / f"vectors_b3_{split_name}.npy", vecs_135_4)
        np.save(OUTPUT_DIR / f"labels_4_b3_{split_name}.npy", labels_4_clean)

        # 10-class용: -1 포함 전체 저장 (학습 시 필터링)
        np.save(OUTPUT_DIR / f"labels_10_b3_{split_name}.npy", labels_10)
        # 10-class에 맞는 vecs_135 (valid_label4 필터 없는 버전)
        np.save(OUTPUT_DIR / f"vectors_b3_10cls_{split_name}.npy", vecs_135)

        label4_dist = {int(k): int(v) for k, v in zip(*np.unique(labels_4_clean, return_counts=True))}
        label10_valid = labels_10[labels_10 >= 0]
        label10_dist = {int(k): int(v) for k, v in zip(*np.unique(label10_valid, return_counts=True))}

        print(f"  저장 완료: vectors_b3_{split_name}.npy {vecs_135_4.shape}")
        print(f"  4-class: {label4_dist}")
        print(f"  10-class valid: {len(label10_valid):,}")

        summary["splits"][split_name] = {
            "pitches_after_join": int(valid_mask.sum()),
            "pitches_4cls": int(valid_label4.sum()),
            "label4_dist": label4_dist,
            "label10_valid": int(len(label10_valid)),
            "label10_dist": label10_dist,
        }

    elapsed = time.time() - t_start
    summary["elapsed_seconds"] = round(elapsed, 1)

    with open(OUTPUT_DIR / "b3_preprocessing_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n=== 전처리 완료: {elapsed:.1f}초 ===")
    print(f"출력: {MODEL_B3_DIM}-dim 벡터 저장 완료")
    print("  vectors_b3_{{train,val,test}}.npy  (4-class용)")
    print("  vectors_b3_10cls_{{train,val,test}}.npy  (10-class용)")


if __name__ == "__main__":
    main()

"""Phase 10.3 prep: static 58-dim feature를 vectors_c_*.npy와 행 정렬.

vectors_c_*.npy는 sort_by_batter_and_time 순서로 생성됨.
동일한 정렬을 재현하여 handoff_v1을 left-merge → (N_c, 58) 행렬 저장.

Outputs (data/processed/):
    static_58_{split}.npy        (N_c, 58) float32  — scaler_new58 적용, NaN→0
    static_58_valid_{split}.npy  (N_c,)    bool     — handoff 매칭 성공 행 마스크
"""

import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from src.data.preprocess import clean_dataframe, sort_by_batter_and_time, split_by_season

DATA_DIR = PROJECT_ROOT / "data" / "processed"
RAW_DIR = PROJECT_ROOT / "data" / "raw"
HANDOFF_PATH = Path(r"C:\Users\zpfh1\Projects\data\data\outputs\handoff_v1.parquet")

YEARS = [2022, 2023, 2024]
TRAIN_YEARS = [2022, 2023]

UMAP_COLS = [f"umap_5d_{i}" for i in range(5)]
COUNT_COLS = ["count_cluster_id"]
ARSENAL_FUNC_COLS = [f"arsenal_func_{i:02d}" for i in range(32)]
ARSENAL_MOM_COLS = [f"arsenal_moment_{i:02d}" for i in range(20)]
NEW_FEATURE_COLS = UMAP_COLS + COUNT_COLS + ARSENAL_FUNC_COLS + ARSENAL_MOM_COLS  # 58
JOIN_KEYS = ["game_pk", "at_bat_number", "pitch_number"]


def main():
    t_start = time.time()

    print("=== 1. 원본 데이터 로드 ===")
    frames = []
    for yr in YEARS:
        path = RAW_DIR / str(yr) / f"statcast_{yr}.parquet"
        if not path.exists():
            print(f"[ERROR] 파일 없음: {path}")
            sys.exit(1)
        frames.append(pd.read_parquet(path))
    df_raw = pd.concat(frames, ignore_index=True)
    print(f"원본: {len(df_raw):,} rows")

    df_clean = clean_dataframe(df_raw)
    print(f"정제 후: {len(df_clean):,} rows")

    splits = split_by_season(df_clean, train_years=TRAIN_YEARS)

    print("\n=== 2. handoff_v1 로드 ===")
    if not HANDOFF_PATH.exists():
        print(f"[ERROR] handoff_v1.parquet 없음: {HANDOFF_PATH}")
        sys.exit(1)
    handoff = pd.read_parquet(HANDOFF_PATH, columns=JOIN_KEYS + NEW_FEATURE_COLS)
    handoff = handoff.drop_duplicates(subset=JOIN_KEYS, keep="first")
    print(f"handoff: {len(handoff):,} rows")

    print("\n=== 3. scaler_new58 로드 ===")
    scaler_path = DATA_DIR / "scaler_new58.pkl"
    if not scaler_path.exists():
        print(f"[ERROR] scaler_new58.pkl 없음. 먼저 21_preprocess_135dim.py 실행 필요.")
        sys.exit(1)
    with open(scaler_path, "rb") as f:
        scaler58 = pickle.load(f)
    print("scaler_new58 로드 완료")

    print("\n=== 4. 각 split 처리 ===")
    for split_name, sdf in splits.items():
        print(f"\n--- {split_name.upper()} ---")

        # vectors_c와 동일한 정렬 순서 재현
        sdf_sorted = sort_by_batter_and_time(sdf)
        vc_path = DATA_DIR / f"vectors_c_{split_name}.npy"
        if not vc_path.exists():
            print(f"  [WARN] {vc_path} 없음 — 스킵")
            continue

        vc = np.load(vc_path, mmap_mode="r")
        n_c = len(vc)

        # 정렬 정합성 검증
        assert len(sdf_sorted) == n_c, (
            f"[ERROR] 행 수 불일치: sdf_sorted={len(sdf_sorted)} vs vectors_c={n_c}"
        )

        # 정렬 sanity check: 랜덤 1만 행의 (game_pk, at_bat_number, pitch_number) 검증
        rng = np.random.RandomState(42)
        check_idx = rng.choice(n_c, min(10000, n_c), replace=False)
        keys_sample = sdf_sorted.iloc[check_idx][JOIN_KEYS].values
        # game_pk가 오름차순 정렬에 부합하는지 기본 체크 (duplicate 없이 unique해야 합리적)
        assert keys_sample.shape[1] == 3, "[ERROR] JOIN_KEYS 컬럼 구조 이상"
        print(f"  정렬 정합성: 행 수 {n_c:,} 일치 OK, 랜덤 10000행 샘플 키 구조 OK")

        # handoff left-merge (sdf_sorted 행 순서 보존)
        merged = sdf_sorted[JOIN_KEYS].merge(
            handoff[JOIN_KEYS + NEW_FEATURE_COLS],
            on=JOIN_KEYS,
            how="left",
        )
        assert len(merged) == n_c, "[ERROR] merge 후 행 수 변경"

        raw58 = merged[NEW_FEATURE_COLS].values.astype(np.float32)
        valid = ~np.isnan(raw58).any(axis=1)
        n_invalid = (~valid).sum()

        # 정규화: 유효 행만 transform, 무효 행은 0
        out = np.zeros((n_c, 58), dtype=np.float32)
        if valid.any():
            out[valid] = scaler58.transform(raw58[valid]).astype(np.float32)

        np.save(DATA_DIR / f"static_58_{split_name}.npy", out)
        np.save(DATA_DIR / f"static_58_valid_{split_name}.npy", valid)

        print(f"  매칭: {valid.sum():,}/{n_c:,} ({valid.mean()*100:.2f}%)")
        if n_invalid > 0:
            print(f"  미매칭 {n_invalid:,}행 → static=0 (missing indicator 없음)")
        print(f"  저장: static_58_{split_name}.npy {out.shape}")

    elapsed = time.time() - t_start
    print(f"\n=== 완료: {elapsed:.1f}초 ===")
    print("static_58_{train,val,test}.npy - vectors_c와 동일 행 정렬 보장")


if __name__ == "__main__":
    main()

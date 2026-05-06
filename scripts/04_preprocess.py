"""End-to-end preprocessing: raw Parquet → preprocessed tensors.

Outputs:
    data/processed/model_c_{split}.pt  — (sequences, labels_10, hit_locs) for Model C
    data/processed/model_b_{split}.pt  — (vectors, labels_4) for Model B
    data/processed/scaler.pkl          — fitted StandardScaler
    data/processed/pitch_types.json    — canonical pitch type list
    data/processed/preprocessing_summary.json — stats
"""

import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch
from tqdm import tqdm

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.features import MODEL_B_DIM, MODEL_C_DIM, OUTCOME_END, OUTCOME_START
from src.data.preprocess import (
    build_vectors_batch,
    clean_dataframe,
    extract_hit_location,
    extract_labels_10class,
    extract_labels_4class,
    fit_scaler,
    make_sequences_for_batter,
    split_by_season,
)
from src.utils.logger import get_logger

logger = get_logger("preprocess", "outputs/logs/preprocess.log")

SEQ_LENGTH = 400
# stride=1은 메모리 초과 (train만 521K sequences × 400 × 87 × 4B ≈ 72GB)
# stride=50: 약 10K sequences, ~1.4GB — Mac Mini에서 실행 가능
# GPU 서버에서 stride를 줄여 데이터 증강 가능
STRIDE = 50
OUTPUT_DIR = Path("data/processed")


def main():
    t_start = time.time()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    # === 1. 데이터 로드 ===
    logger.info("데이터 로드 중...")
    df23 = pd.read_parquet("data/raw/2023/statcast_2023.parquet")
    df24 = pd.read_parquet("data/raw/2024/statcast_2024.parquet")
    df = pd.concat([df23, df24], ignore_index=True)
    logger.info(f"원본 데이터: {len(df):,} rows")

    # === 2. 정제 ===
    logger.info("데이터 정제 중...")
    df = clean_dataframe(df)
    logger.info(f"정제 후: {len(df):,} rows")

    # === 3. Train/Val/Test 분할 ===
    splits = split_by_season(df)
    for name, sdf in splits.items():
        logger.info(f"  {name}: {len(sdf):,} rows")

    # === 4. Scaler + pitch types (train only) ===
    logger.info("Scaler fitting (train)...")
    scaler = fit_scaler(splits["train"])
    from src.data.preprocess import determine_pitch_types

    pitch_types = determine_pitch_types(splits["train"])

    # Scaler 저장
    with open(OUTPUT_DIR / "scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)
    with open(OUTPUT_DIR / "pitch_types.json", "w") as f:
        json.dump(pitch_types, f)
    logger.info("Scaler + pitch_types 저장 완료")

    summary = {
        "raw_rows": len(df23) + len(df24),
        "cleaned_rows": sum(len(s) for s in splits.values()),
        "splits": {},
    }

    # === 5. 각 split 처리 ===
    for split_name, sdf in splits.items():
        logger.info(f"\n{'='*40} {split_name.upper()} {'='*40}")

        # --- Model B: 77차원 벡터 + 4-class 라벨 ---
        logger.info(f"[{split_name}] Model B 벡터 생성 중...")
        t0 = time.time()
        vectors_b = build_vectors_batch(sdf, scaler, pitch_types, model="B")
        labels_4 = extract_labels_4class(sdf)
        t_b = time.time() - t0
        logger.info(
            f"[{split_name}] Model B: {vectors_b.shape}, 4-class labels, {t_b:.1f}s"
        )

        # 4-class에서 -1(unmapped) 제거
        valid_mask_b = labels_4 >= 0
        vectors_b = vectors_b[valid_mask_b]
        labels_4 = labels_4[valid_mask_b]

        torch.save(
            {"vectors": vectors_b, "labels": labels_4},
            OUTPUT_DIR / f"model_b_{split_name}.pt",
        )

        # --- Model C: 87차원 벡터 → sliding window ---
        logger.info(f"[{split_name}] Model C 벡터 생성 중...")
        t0 = time.time()
        vectors_c = build_vectors_batch(sdf, scaler, pitch_types, model="C")
        labels_10 = extract_labels_10class(sdf)
        hit_locs = extract_hit_location(sdf)
        t_c = time.time() - t0
        logger.info(f"[{split_name}] Model C vectors: {vectors_c.shape}, {t_c:.1f}s")

        # 타자별 그룹핑 + 시간순 정렬 + sliding window
        logger.info(f"[{split_name}] Sliding window 생성 중 (seq={SEQ_LENGTH})...")
        t0 = time.time()

        # 정렬을 위해 원본 인덱스 사용
        sdf = sdf.copy()
        sdf["_vec_idx"] = np.arange(len(sdf))

        all_seqs = []
        all_t10 = []
        all_thl = []

        batter_groups = sdf.groupby("batter")
        for batter_id, bdf in tqdm(batter_groups, desc=f"{split_name} batters"):
            # 시간순 정렬
            bdf_sorted = bdf.sort_values(
                ["game_date", "at_bat_number", "pitch_number"]
            )
            idx = bdf_sorted["_vec_idx"].values

            batter_vecs = vectors_c[idx]
            batter_l10 = labels_10[idx]
            batter_hl = hit_locs[idx]

            seqs, t10, thl = make_sequences_for_batter(
                batter_vecs, batter_l10, batter_hl,
                seq_length=SEQ_LENGTH, stride=STRIDE,
            )
            all_seqs.extend(seqs)
            all_t10.extend(t10)
            all_thl.extend(thl)

        t_sw = time.time() - t0

        if all_seqs:
            seqs_arr = np.stack(all_seqs)
            t10_arr = np.array(all_t10, dtype=np.int64)
            thl_arr = np.array(all_thl, dtype=np.int64)
        else:
            seqs_arr = np.zeros((0, SEQ_LENGTH, MODEL_C_DIM), dtype=np.float32)
            t10_arr = np.zeros(0, dtype=np.int64)
            thl_arr = np.zeros(0, dtype=np.int64)

        logger.info(
            f"[{split_name}] Model C sequences: {seqs_arr.shape}, {t_sw:.1f}s"
        )

        torch.save(
            {"sequences": seqs_arr, "labels_10": t10_arr, "hit_locs": thl_arr},
            OUTPUT_DIR / f"model_c_{split_name}.pt",
        )

        # === Split 통계 ===
        split_stats = {
            "pitches": len(sdf),
            "model_b": {
                "vectors_shape": list(vectors_b.shape),
                "label_4_dist": {
                    int(k): int(v) for k, v in
                    zip(*np.unique(labels_4, return_counts=True))
                },
            },
            "model_c": {
                "sequences_shape": list(seqs_arr.shape),
                "n_batters_with_sequences": sum(
                    1 for _, bdf in batter_groups if len(bdf) >= SEQ_LENGTH
                ),
                "label_10_dist": {
                    int(k): int(v) for k, v in
                    zip(*np.unique(t10_arr, return_counts=True))
                } if len(t10_arr) > 0 else {},
            },
        }
        summary["splits"][split_name] = split_stats

        # Print 요약
        print(f"\n{'='*60}")
        print(f"  {split_name.upper()}")
        print(f"{'='*60}")
        print(f"  Pitches: {len(sdf):,}")
        print(f"  Model B: {vectors_b.shape}")
        print(f"    4-class dist: {split_stats['model_b']['label_4_dist']}")
        print(f"  Model C: {seqs_arr.shape}")
        print(f"    10-class dist: {split_stats['model_c']['label_10_dist']}")

    # === 6. 검증 ===
    logger.info("\n차원 검증...")
    for split_name in ["train", "val", "test"]:
        b_data = torch.load(OUTPUT_DIR / f"model_b_{split_name}.pt", weights_only=False)
        c_data = torch.load(OUTPUT_DIR / f"model_c_{split_name}.pt", weights_only=False)
        assert b_data["vectors"].shape[1] == MODEL_B_DIM, f"Model B dim mismatch: {split_name}"
        if c_data["sequences"].shape[0] > 0:
            assert c_data["sequences"].shape[1] == SEQ_LENGTH
            assert c_data["sequences"].shape[2] == MODEL_C_DIM
            # Sub-token mask 검증: 마지막 pitch의 outcome이 0인지
            sample = c_data["sequences"][0]
            assert np.all(sample[-1, OUTCOME_START:OUTCOME_END] == 0.0), \
                f"Sub-token mask failed: {split_name}"
        logger.info(f"  {split_name}: OK")

    # Split 경계 검증
    logger.info("Split 경계 검증...")
    train_dates = set(splits["train"]["game_date"].dt.date.unique())
    val_dates = set(splits["val"]["game_date"].dt.date.unique())
    test_dates = set(splits["test"]["game_date"].dt.date.unique())
    assert train_dates.isdisjoint(val_dates), "Train-Val date overlap!"
    assert train_dates.isdisjoint(test_dates), "Train-Test date overlap!"
    assert val_dates.isdisjoint(test_dates), "Val-Test date overlap!"
    logger.info("  날짜 겹침 없음 — OK")

    # === 7. 요약 저장 ===
    elapsed = time.time() - t_start
    summary["total_elapsed_seconds"] = round(elapsed, 1)

    # 파일 크기
    for f in OUTPUT_DIR.glob("*.pt"):
        summary.setdefault("file_sizes_mb", {})[f.name] = round(
            f.stat().st_size / (1024 * 1024), 1
        )

    with open(OUTPUT_DIR / "preprocessing_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n{'='*60}")
    print(f"  전처리 완료! ({elapsed:.1f}초)")
    print(f"{'='*60}")
    for f in sorted(OUTPUT_DIR.glob("*")):
        size_mb = f.stat().st_size / (1024 * 1024)
        print(f"  {f.name:40s} {size_mb:8.1f} MB")
    print()


if __name__ == "__main__":
    main()

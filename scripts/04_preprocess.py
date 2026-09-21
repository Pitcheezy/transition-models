"""End-to-end preprocessing: raw Parquet → pre-computed vectors + lazy indices.

Lazy loading approach:
    - Pre-compute (N, 87) vectors per split as .npy (memory-mappable)
    - Pre-compute labels/hit_locs as .npy
    - Save valid_indices (batter_id, global_start) as .pkl
    - Dataset.__getitem__ slices vectors in O(1) — no sequence pre-generation

Outputs:
    data/processed/vectors_c_{split}.npy   — (N, 87) Model C vectors
    data/processed/labels_10_{split}.npy   — (N,) 10-class labels
    data/processed/hit_locs_{split}.npy    — (N,) hit location labels
    data/processed/batter_ranges_{split}.pkl — batter → (start, end) mapping
    data/processed/indices_{split}.pkl     — valid sequence start positions
    data/processed/model_b_{split}.pt      — (vectors, labels) for Model B
    data/processed/scaler.pkl              — fitted StandardScaler
    data/processed/pitch_types.json        — canonical pitch type list
    data/processed/preprocessing_summary.json
"""

import argparse
import json
import pickle
import sys
import time
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.features import MODEL_B_DIM, MODEL_C_DIM, OUTCOME_END, OUTCOME_START
from src.data.point_data import make_point_data, validate_point_data
from src.data.preprocess import (
    build_valid_indices,
    build_vectors_batch,
    clean_dataframe,
    compute_batter_ranges,
    extract_hit_location,
    extract_labels_10class,
    fit_scaler,
    sort_by_batter_and_time,
    split_by_season,
)
from src.utils.logger import get_logger

logger = get_logger("preprocess", "outputs/logs/preprocess.log")

SEQ_LENGTH = 400
STRIDE = 8  # stride=1: 521K sequences (1 epoch=76min), stride=8: ~65K (8x speedup)
OUTPUT_DIR = Path("data/processed")

RAW_DIR = Path("data/raw")


def load_seasons(years: list[int]) -> pd.DataFrame:
    """Load and concatenate Parquet files for each requested year."""
    frames = []
    for yr in years:
        path = RAW_DIR / str(yr) / f"statcast_{yr}.parquet"
        if not path.exists():
            logger.error(f"데이터 파일 없음: {path}  → 먼저 다운로드하세요.")
            sys.exit(1)
        logger.info(f"  {yr} 로드: {path}")
        frames.append(pd.read_parquet(path))
    df = pd.concat(frames, ignore_index=True)
    logger.info(f"  합산: {len(df):,} rows ({len(years)} 시즌)")
    return df


def main():
    global OUTPUT_DIR, RAW_DIR
    parser = argparse.ArgumentParser(description="Preprocessing: raw Parquet → vectors + indices")
    parser.add_argument("--output-dir", type=Path, default=Path("data/aligned_preprocessed"))
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument(
        "--years",
        nargs="+",
        type=int,
        default=[2023, 2024],
        help="Seasons to process (default: 2023 2024). Last year = val/test split.",
    )
    args = parser.parse_args()
    OUTPUT_DIR, RAW_DIR = args.output_dir, args.raw_dir

    years = sorted(args.years)
    if len(years) < 2:
        logger.error("최소 2개 시즌 필요 (마지막 시즌이 val/test로 분리됩니다).")
        sys.exit(1)

    train_years = years[:-1]  # 마지막 제외 → 학습
    test_year = years[-1]  # 마지막 → val / test 분리

    logger.info(f"시즌: {years}  |  Train: {train_years}  |  Val/Test: {test_year}")

    t_start = time.time()
    OUTPUT_DIR.mkdir(parents=True, exist_ok=False)

    # === 1. 데이터 로드 ===
    logger.info("데이터 로드 중...")
    df = load_seasons(years)
    raw_row_count = len(df)
    logger.info(f"원본 데이터: {raw_row_count:,} rows")

    # === 2. 정제 ===
    logger.info("데이터 정제 중...")
    df = clean_dataframe(df)
    logger.info(f"정제 후: {len(df):,} rows")

    # === 3. Train/Val/Test 분할 ===
    splits = split_by_season(df, train_years=train_years)
    for name, sdf in splits.items():
        logger.info(f"  {name}: {len(sdf):,} rows")

    # === 4. Scaler + pitch types (train only) ===
    logger.info("Scaler fitting (train)...")
    scaler = fit_scaler(splits["train"])
    from src.data.preprocess import determine_pitch_types

    pitch_types = determine_pitch_types(splits["train"])

    with open(OUTPUT_DIR / "scaler.pkl", "wb") as f:
        pickle.dump(scaler, f)
    with open(OUTPUT_DIR / "pitch_types.json", "w") as f:
        json.dump(pitch_types, f)
    logger.info("Scaler + pitch_types 저장 완료")

    summary = {
        "years": years,
        "train_years": train_years,
        "test_year": test_year,
        "raw_rows": raw_row_count,
        "cleaned_rows": sum(len(s) for s in splits.values()),
        "seq_length": SEQ_LENGTH,
        "stride": STRIDE,
        "splits": {},
    }

    # === 5. 각 split 처리 ===
    for split_name, sdf in splits.items():
        logger.info(f"\n{'=' * 40} {split_name.upper()} {'=' * 40}")

        # --- Model B: 77차원 벡터 + 4-class 라벨 (eager, 작음) ---
        logger.info(f"[{split_name}] Model B 벡터 생성 중...")
        t0 = time.time()
        vectors_b = build_vectors_batch(sdf, scaler, pitch_types, model="B")
        point_data = make_point_data(sdf, vectors_b)
        labels_4 = point_data["labels_4"]
        t_b = time.time() - t0

        valid_mask_b = labels_4 >= 0
        vectors_b = vectors_b[valid_mask_b]
        labels_4 = labels_4[valid_mask_b]

        for key in ("vectors", "labels_4", "labels_10", "pitch_ids"):
            point_data[key] = point_data[key][valid_mask_b]
        point_data["labels"] = labels_4  # Compatibility with 4-class consumers.
        validate_point_data(point_data)
        torch.save(point_data, OUTPUT_DIR / f"model_b_{split_name}.pt")
        logger.info(f"[{split_name}] Model B: {vectors_b.shape}, {t_b:.1f}s")

        # --- Model C: 정렬 → 벡터 → 인덱스 (lazy loading) ---
        logger.info(f"[{split_name}] Model C: 타자별 정렬 중...")
        t0 = time.time()
        sdf_sorted = sort_by_batter_and_time(sdf)

        # 벡터 생성 (정렬된 순서대로)
        logger.info(f"[{split_name}] Model C: 87차원 벡터 생성 중...")
        vectors_c = build_vectors_batch(sdf_sorted, scaler, pitch_types, model="C")
        labels_10 = extract_labels_10class(sdf_sorted)
        hit_locs = extract_hit_location(sdf_sorted)
        t_vec = time.time() - t0
        logger.info(f"[{split_name}] Model C vectors: {vectors_c.shape}, {t_vec:.1f}s")

        # 타자 범위 계산
        batter_ranges = compute_batter_ranges(sdf_sorted)
        logger.info(f"[{split_name}] Batters: {len(batter_ranges)}")

        # Valid indices (stride=1)
        t0 = time.time()
        valid_indices = build_valid_indices(batter_ranges, SEQ_LENGTH, STRIDE)
        t_idx = time.time() - t0
        n_batters_qualified = sum(1 for _, (s, e) in batter_ranges.items() if e - s >= SEQ_LENGTH)
        logger.info(
            f"[{split_name}] Valid indices: {len(valid_indices):,} "
            f"(stride={STRIDE}, {n_batters_qualified} batters), {t_idx:.1f}s"
        )

        # .npy 저장 (memory-mappable)
        np.save(OUTPUT_DIR / f"vectors_c_{split_name}.npy", vectors_c)
        np.save(OUTPUT_DIR / f"labels_10_{split_name}.npy", labels_10)
        np.save(OUTPUT_DIR / f"hit_locs_{split_name}.npy", hit_locs)
        with open(OUTPUT_DIR / f"batter_ranges_{split_name}.pkl", "wb") as f:
            pickle.dump(batter_ranges, f)
        with open(OUTPUT_DIR / f"indices_{split_name}.pkl", "wb") as f:
            pickle.dump(valid_indices, f)

        # === Split 통계 ===
        split_stats = {
            "pitches": len(sdf_sorted),
            "model_b": {
                "vectors_shape": list(vectors_b.shape),
                "label_4_dist": {
                    int(k): int(v)
                    for k, v in zip(*np.unique(labels_4, return_counts=True), strict=True)
                },
            },
            "model_c": {
                "vectors_shape": list(vectors_c.shape),
                "n_sequences": len(valid_indices),
                "n_batters_qualified": n_batters_qualified,
            },
        }
        summary["splits"][split_name] = split_stats

        print(f"\n{'=' * 60}")
        print(f"  {split_name.upper()}")
        print(f"{'=' * 60}")
        print(f"  Pitches: {len(sdf_sorted):,}")
        print(f"  Model B: {vectors_b.shape}")
        print(f"    4-class: {split_stats['model_b']['label_4_dist']}")
        print(f"  Model C vectors: {vectors_c.shape}")
        print(f"    Sequences (stride={STRIDE}): {len(valid_indices):,}")
        print(f"    Qualified batters (400+): {n_batters_qualified}")

    # === 6. 검증 ===
    logger.info("\n차원 검증...")
    for split_name in ["train", "val", "test"]:
        b_data = torch.load(OUTPUT_DIR / f"model_b_{split_name}.pt", weights_only=False)
        vecs = np.load(OUTPUT_DIR / f"vectors_c_{split_name}.npy")
        assert b_data["vectors"].shape[1] == MODEL_B_DIM
        assert vecs.shape[1] == MODEL_C_DIM

        # Sub-token mask 검증: lazy dataset으로 실제 확인
        with open(OUTPUT_DIR / f"indices_{split_name}.pkl", "rb") as f:
            indices = pickle.load(f)
        if indices:
            labels = np.load(OUTPUT_DIR / f"labels_10_{split_name}.npy")
            hlocs = np.load(OUTPUT_DIR / f"hit_locs_{split_name}.npy")
            from src.data.dataset import PitchSequenceDataset

            ds = PitchSequenceDataset(vecs, labels, hlocs, indices, SEQ_LENGTH)
            item = ds[0]
            seq_np = item["sequence"].numpy()
            assert np.all(seq_np[-1, OUTCOME_START:OUTCOME_END] == 0.0), (
                f"Sub-token mask failed: {split_name}"
            )
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

    file_sizes = {}
    for f in sorted(OUTPUT_DIR.glob("*")):
        if f.name != ".gitkeep":
            file_sizes[f.name] = round(f.stat().st_size / (1024 * 1024), 1)
    summary["file_sizes_mb"] = file_sizes

    with open(OUTPUT_DIR / "preprocessing_summary.json", "w", encoding="utf-8") as f:
        json.dump(summary, f, ensure_ascii=False, indent=2)

    print(f"\n{'=' * 60}")
    print(f"  전처리 완료! ({elapsed:.1f}초)")
    print(f"{'=' * 60}")
    for name, size in sorted(file_sizes.items()):
        print(f"  {name:45s} {size:8.1f} MB")
    print()


if __name__ == "__main__":
    main()

"""Download MLB Statcast data via pybaseball and save as Parquet."""

import argparse
import json
import sys
import time
from datetime import datetime
from pathlib import Path

import pandas as pd
from tqdm import tqdm

# 프로젝트 루트를 sys.path에 추가
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.utils.logger import get_logger

logger = get_logger("download", "outputs/logs/download.log")

# 시즌 날짜 범위 (스프링트레이닝 ~ 포스트시즌 포함)
SEASON_DATES = {
    2023: ("2023-02-01", "2023-11-30"),
    2024: ("2024-02-01", "2024-11-30"),
}

# 테스트 모드 날짜 (1주일치)
TEST_DATES = {
    2023: ("2023-04-01", "2023-04-07"),
    2024: ("2024-04-01", "2024-04-07"),
}

MAX_RETRIES = 3
RETRY_DELAY = 30  # 초


def download_season(
    year: int, output_dir: Path, force: bool, test_mode: bool
) -> dict | None:
    """Download one season of Statcast data.

    Returns:
        Metadata dict on success, None on skip.
    """
    suffix = f"_test" if test_mode else ""
    season_dir = output_dir / str(year)
    season_dir.mkdir(parents=True, exist_ok=True)
    out_path = season_dir / f"statcast_{year}{suffix}.parquet"

    # 이어받기: 이미 파일 있으면 skip
    if out_path.exists() and not force:
        logger.info(f"{year}년 데이터 이미 존재, 건너뜀: {out_path}")
        # 기존 파일 메타데이터 반환
        df = pd.read_parquet(out_path)
        file_size_mb = out_path.stat().st_size / (1024 * 1024)
        return {
            "year": year,
            "test_mode": test_mode,
            "rows": len(df),
            "columns": len(df.columns),
            "file_size_mb": round(file_size_mb, 2),
            "file_path": str(out_path),
            "downloaded_at": datetime.fromtimestamp(out_path.stat().st_mtime).isoformat(),
            "skipped": True,
        }

    dates = TEST_DATES[year] if test_mode else SEASON_DATES[year]
    start_dt, end_dt = dates
    logger.info(f"{year}년 다운로드 시작: {start_dt} ~ {end_dt}")

    # pybaseball import는 여기서 (캐시 활성화 포함)
    from pybaseball import cache, statcast

    cache.enable()

    # 재시도 로직
    df = None
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            t0 = time.time()
            df = statcast(start_dt=start_dt, end_dt=end_dt)
            elapsed = time.time() - t0
            break
        except Exception as e:
            logger.warning(f"{year}년 다운로드 실패 (시도 {attempt}/{MAX_RETRIES}): {e}")
            if attempt < MAX_RETRIES:
                logger.info(f"{RETRY_DELAY}초 후 재시도...")
                time.sleep(RETRY_DELAY)
            else:
                logger.error(f"{year}년 다운로드 최종 실패. {MAX_RETRIES}회 시도 모두 실패.")
                return None

    if df is None or df.empty:
        logger.error(f"{year}년: 데이터가 비어 있습니다.")
        return None

    # Parquet 저장
    df.to_parquet(out_path, index=False)
    file_size_mb = out_path.stat().st_size / (1024 * 1024)

    logger.info(
        f"{year}년 완료: {len(df):,} pitches, {len(df.columns)} cols, "
        f"{file_size_mb:.1f} MB, {elapsed:.1f}초 소요"
    )

    return {
        "year": year,
        "test_mode": test_mode,
        "rows": len(df),
        "columns": len(df.columns),
        "file_size_mb": round(file_size_mb, 2),
        "file_path": str(out_path),
        "downloaded_at": datetime.now().isoformat(),
        "elapsed_seconds": round(elapsed, 1),
        "skipped": False,
    }


def print_test_summary(output_dir: Path, year: int) -> None:
    """Print detailed summary for test mode verification."""
    suffix = "_test"
    path = output_dir / str(year) / f"statcast_{year}{suffix}.parquet"
    if not path.exists():
        return

    df = pd.read_parquet(path)

    print("\n" + "=" * 60)
    print(f"  테스트 다운로드 검증: {year}년 (1주일치)")
    print("=" * 60)

    print(f"\n[Shape] {df.shape[0]:,} rows × {df.shape[1]} columns")

    # 첫 5행
    print(f"\n[첫 5행]")
    print(df.head().to_string())

    # 컬럼 목록
    print(f"\n[전체 컬럼 ({len(df.columns)}개)]")
    for i, col in enumerate(df.columns):
        print(f"  {i+1:3d}. {col}")

    # 결측치 비율
    null_pct = (df.isnull().sum() / len(df) * 100).sort_values(ascending=False)
    high_null = null_pct[null_pct > 0]
    print(f"\n[결측치 비율 (결측 있는 컬럼: {len(high_null)}/{len(df.columns)})]")
    for col, pct in high_null.head(20).items():
        print(f"  {col:40s} {pct:6.1f}%")
    if len(high_null) > 20:
        print(f"  ... 외 {len(high_null) - 20}개 컬럼")

    # 카테고리 변수 unique 값
    cat_cols = ["pitch_type", "events", "description", "zone", "stand", "p_throws", "type"]
    print(f"\n[카테고리 변수 unique 값]")
    for col in cat_cols:
        if col in df.columns:
            uniques = df[col].dropna().unique()
            print(f"  {col} ({len(uniques)}): {sorted(uniques)}")

    print()


def main():
    parser = argparse.ArgumentParser(description="Download MLB Statcast data")
    parser.add_argument(
        "--years", nargs="+", type=int, required=True, help="Seasons to download (e.g. 2023 2024)"
    )
    parser.add_argument("--output-dir", type=str, default="data/raw", help="Output directory")
    parser.add_argument("--force", action="store_true", help="Re-download even if file exists")
    parser.add_argument(
        "--test-mode", action="store_true", help="Download only 1 week (Apr 1-7) for testing"
    )
    args = parser.parse_args()

    output_dir = Path(args.output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    # 지원하는 시즌 확인
    for year in args.years:
        if year not in SEASON_DATES:
            logger.error(f"지원하지 않는 시즌: {year}. 지원: {list(SEASON_DATES.keys())}")
            sys.exit(1)

    mode_str = "테스트 모드 (1주일)" if args.test_mode else "전체 시즌"
    logger.info(f"Statcast 다운로드 시작: {args.years}, {mode_str}")

    results = []
    for year in tqdm(args.years, desc="시즌 다운로드"):
        meta = download_season(year, output_dir, args.force, args.test_mode)
        if meta is not None:
            results.append(meta)

    # 요약 저장
    summary_path = output_dir / "download_summary.json"
    with open(summary_path, "w", encoding="utf-8") as f:
        json.dump(results, f, ensure_ascii=False, indent=2)
    logger.info(f"다운로드 요약 저장: {summary_path}")

    # 테스트 모드 상세 출력
    if args.test_mode:
        for year in args.years:
            print_test_summary(output_dir, year)

    # 전체 요약 출력
    print("\n" + "=" * 60)
    print("  다운로드 완료 요약")
    print("=" * 60)
    for r in results:
        status = "SKIP" if r.get("skipped") else "OK"
        elapsed = r.get("elapsed_seconds", "-")
        print(
            f"  [{status}] {r['year']}: {r['rows']:>10,} pitches, "
            f"{r['columns']} cols, {r['file_size_mb']:.1f} MB, {elapsed}s"
        )
    print()


if __name__ == "__main__":
    main()

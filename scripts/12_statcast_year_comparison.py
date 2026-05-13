"""Year-by-year Statcast feature comparison.

Downloads 2-day samples (July 1-2) from 2017-2024 and checks:
- Column count and availability
- pitch_type taxonomy (FT, ST, SV presence)
- release_spin_rate distribution (Trackman vs Hawkeye)
- Continuous feature null rates
- Unknown pitch types vs our 17-type list

Usage:
    uv run python scripts/12_statcast_year_comparison.py
"""

import warnings

warnings.filterwarnings("ignore")

import numpy as np
import pandas as pd
from pybaseball import statcast

from src.data.features import CONTINUOUS_FEATURES, PITCH_TYPES

SAMPLE_DATES = {
    2017: ("2017-07-01", "2017-07-02"),
    2018: ("2018-07-01", "2018-07-02"),
    2019: ("2019-07-01", "2019-07-02"),
    2020: ("2020-08-01", "2020-08-02"),  # COVID 단축시즌
    2021: ("2021-07-01", "2021-07-02"),
    2022: ("2022-07-01", "2022-07-02"),
    2023: ("2023-07-01", "2023-07-02"),
    2024: ("2024-07-01", "2024-07-02"),
}

OUR_TYPES = set(PITCH_TYPES)


def fetch_samples() -> dict[int, pd.DataFrame]:
    samples = {}
    for yr, (s, e) in SAMPLE_DATES.items():
        try:
            df = statcast(s, e)
            samples[yr] = df
            print(f"  {yr}: {len(df):>5} rows, {len(df.columns)} cols")
        except Exception as ex:
            print(f"  {yr}: FAILED — {ex}")
    return samples


def report_pitch_types(samples: dict[int, pd.DataFrame]) -> None:
    print("\n" + "=" * 70)
    print("pitch_type 분포 (%) — FT·ST·SV 변화 추적")
    print("=" * 70)
    track_types = ["FF", "FT", "SI", "SL", "ST", "SV", "CH", "FC", "CU", "FS"]
    print(f"{'Type':<6}", end="")
    for yr in sorted(samples):
        print(f"  {yr}", end="")
    print()
    for pt in track_types:
        print(f"  {pt:<4}", end="")
        for yr in sorted(samples):
            df = samples[yr]
            total = len(df)
            cnt = (df["pitch_type"] == pt).sum()
            pct = cnt / total * 100
            print(f"  {pct:>5.1f}", end="")
        print()

    print(f"\n  {'UNKNOWN':<4}", end="")
    for yr in sorted(samples):
        df = samples[yr]
        total = len(df)
        unknown = (~df["pitch_type"].isin(OUR_TYPES) & df["pitch_type"].notna()).sum()
        pct = unknown / total * 100
        marker = " !" if pct > 1 else "  "
        print(f"  {pct:>4.1f}{marker}", end="")
    print(" ← 우리 17종에 없는 타입")


def report_spin_rate(samples: dict[int, pd.DataFrame]) -> None:
    print("\n" + "=" * 70)
    print("release_spin_rate (Trackman→Hawkeye 분포 변화)")
    print("=" * 70)
    print(f"{'Year':<6} {'mean':>8} {'std':>8} {'null%':>8}  tracking")
    for yr in sorted(samples):
        df = samples[yr]
        s = df["release_spin_rate"].dropna()
        null_pct = df["release_spin_rate"].isna().mean() * 100
        era = "Trackman" if yr <= 2019 else ("Mixed" if yr == 2020 else "Hawkeye")
        print(f"  {yr}   {s.mean():>8.1f} {s.std():>8.1f} {null_pct:>7.1f}%  {era}")


def report_null_rates(samples: dict[int, pd.DataFrame]) -> None:
    print("\n" + "=" * 70)
    print("Continuous features null% (! = 5% 초과)")
    print("=" * 70)
    print(f"  {'Feature':<22}", end="")
    for yr in sorted(samples):
        print(f"  {yr}", end="")
    print()
    for f in CONTINUOUS_FEATURES:
        print(f"  {f:<22}", end="")
        for yr in sorted(samples):
            df = samples[yr]
            pct = df[f].isna().mean() * 100 if f in df.columns else 999.0
            flag = "!" if pct > 5 else " "
            print(f"  {pct:>4.1f}{flag}", end="")
        print()


def report_column_diff(samples: dict[int, pd.DataFrame]) -> None:
    print("\n" + "=" * 70)
    print("컬럼 수 & 연도별 차이")
    print("=" * 70)
    years = sorted(samples)
    base_cols = set(samples[years[0]].columns)
    for yr in years:
        cols = set(samples[yr].columns)
        added = cols - base_cols
        removed = base_cols - cols
        print(f"  {yr}: {len(cols)} cols  |  added={sorted(added)}  removed={sorted(removed)}")
        base_cols = cols


def main() -> None:
    print("Statcast 연도별 샘플 수집 중...")
    samples = fetch_samples()

    if not samples:
        print("데이터 없음. 네트워크 확인 후 재실행.")
        return

    report_pitch_types(samples)
    report_spin_rate(samples)
    report_null_rates(samples)
    report_column_diff(samples)

    print("\n" + "=" * 70)
    print("요약 판단")
    print("=" * 70)
    for yr in sorted(samples):
        df = samples[yr]
        ft_pct = (df["pitch_type"] == "FT").mean() * 100
        st_pct = (df["pitch_type"] == "ST").mean() * 100
        unknown_pct = (~df["pitch_type"].isin(OUR_TYPES) & df["pitch_type"].notna()).mean() * 100
        spin_mean = df["release_spin_rate"].mean()
        era = "Trackman" if yr <= 2019 else ("Mixed" if yr == 2020 else "Hawkeye")
        risk = "HIGH  " if yr <= 2020 else ("MED   " if yr == 2021 else "LOW   ")
        print(
            f"  {yr} [{risk}]  FT={ft_pct:.1f}%  ST={st_pct:.1f}%"
            f"  unknown={unknown_pct:.1f}%  spin={spin_mean:.0f}  [{era}]"
        )


if __name__ == "__main__":
    main()

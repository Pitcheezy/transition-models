"""Validate feature mapping on full Statcast dataset.

Apply 4-class and 10-class mapping to all pitches and report:
- Unmapped ratio (should be near 0%)
- Class distributions
- Season-by-season comparison
"""

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.data.features import (
    PitchResult4,
    PitchResult10,
    map_hit_location,
    map_to_4class,
    map_to_10class,
)
from src.utils.logger import get_logger

logger = get_logger("mapping_validation", "outputs/logs/mapping_validation.log")


def main():
    # === 데이터 로드 ===
    logger.info("데이터 로드 시작")
    df23 = pd.read_parquet("data/raw/2023/statcast_2023.parquet")
    df24 = pd.read_parquet("data/raw/2024/statcast_2024.parquet")
    df = pd.concat([df23, df24], ignore_index=True)
    df["season"] = pd.to_datetime(df["game_date"]).dt.year
    logger.info(f"데이터 로드 완료: {len(df):,} rows")

    # === 4-class 매핑 ===
    logger.info("4-class 매핑 적용 중...")
    df["label_4class"] = df["description"].apply(map_to_4class)

    total = len(df)
    mapped_4 = df["label_4class"].notna().sum()
    unmapped_4 = total - mapped_4

    print("=" * 60)
    print("  4-CLASS MAPPING (Otremba 2022)")
    print("=" * 60)
    print(f"  Total: {total:,}")
    print(f"  Mapped: {mapped_4:,} ({mapped_4 / total * 100:.2f}%)")
    print(f"  Unmapped: {unmapped_4:,} ({unmapped_4 / total * 100:.2f}%)")
    print()

    # 클래스별 분포
    print("  Class distribution:")
    dist_4 = df["label_4class"].value_counts().sort_index()
    for cls_id, count in dist_4.items():
        name = PitchResult4.NAMES.get(int(cls_id), "?")
        print(f"    {int(cls_id)} ({name:8s}): {count:>10,} ({count / mapped_4 * 100:5.1f}%)")
    print()

    # 시즌별 비교
    print("  Season comparison (%):")
    for yr in [2023, 2024]:
        sub = df[df["season"] == yr]["label_4class"].dropna()
        pcts = sub.value_counts(normalize=True).sort_index() * 100
        vals = [f"{PitchResult4.NAMES[int(k)]}={v:.1f}" for k, v in pcts.items()]
        print(f"    {yr}: {', '.join(vals)}")
    print()

    # Unmapped description 확인
    if unmapped_4 > 0:
        unmapped_descs = df[df["label_4class"].isna()]["description"].value_counts()
        print("  Unmapped descriptions:")
        for desc, n in unmapped_descs.items():
            print(f"    {desc}: {n:,}")
        print()

    # === 10-class 매핑 ===
    logger.info("10-class 매핑 적용 중...")
    df["label_10class"] = df.apply(
        lambda r: map_to_10class(r["description"], r["events"]), axis=1
    )

    mapped_10 = df["label_10class"].notna().sum()
    unmapped_10 = total - mapped_10

    print("=" * 60)
    print("  10-CLASS MAPPING (MIT Sloan 2025)")
    print("=" * 60)
    print(f"  Total: {total:,}")
    print(f"  Mapped: {mapped_10:,} ({mapped_10 / total * 100:.2f}%)")
    print(f"  Unmapped: {unmapped_10:,} ({unmapped_10 / total * 100:.2f}%)")
    print()

    # 클래스별 분포
    print("  Class distribution:")
    dist_10 = df["label_10class"].value_counts().sort_index()
    for cls_id, count in dist_10.items():
        name = PitchResult10.NAMES.get(int(cls_id), "?")
        print(f"    {int(cls_id)} ({name:12s}): {count:>10,} ({count / mapped_10 * 100:5.1f}%)")
    print()

    # Unmapped 상세 확인
    if unmapped_10 > 0:
        unmapped_rows = df[df["label_10class"].isna()]
        print("  Unmapped breakdown:")
        # events 값 기준
        ev_counts = unmapped_rows["events"].value_counts(dropna=False)
        for ev, n in ev_counts.items():
            label = str(ev) if pd.notna(ev) else "NaN"
            print(f"    events={label}: {n:,}")
        # description 값 기준
        desc_counts = unmapped_rows["description"].value_counts(dropna=False)
        print("  Unmapped descriptions:")
        for desc, n in desc_counts.head(10).items():
            label = str(desc) if pd.notna(desc) else "NaN"
            print(f"    description={label}: {n:,}")
        print()

    # === Hit location 매핑 ===
    logger.info("Hit location 매핑 적용 중...")
    df["hit_loc_mapped"] = df["hit_location"].apply(map_hit_location)

    has_hit_loc = df["hit_loc_mapped"].notna().sum()
    print("=" * 60)
    print("  HIT LOCATION MAPPING (9-class)")
    print("=" * 60)
    print(f"  With hit_location: {has_hit_loc:,} ({has_hit_loc / total * 100:.1f}%)")
    print(f"  Null (non-InPlay): {total - has_hit_loc:,}")
    print()
    dist_hl = df["hit_loc_mapped"].dropna().value_counts().sort_index()
    for loc, count in dist_hl.items():
        print(f"    Location {int(loc)}: {count:>10,} ({count / has_hit_loc * 100:5.1f}%)")
    print()

    # === 리포트 저장 ===
    report_path = Path("outputs/logs/mapping_validation.md")
    with open(report_path, "w", encoding="utf-8") as f:
        f.write("# Feature Mapping Validation Report\n\n")
        f.write(f"Total pitches: {total:,}\n\n")
        f.write("## 4-class (Otremba 2022)\n")
        f.write(f"- Mapped: {mapped_4:,} ({mapped_4 / total * 100:.2f}%)\n")
        f.write(f"- Unmapped: {unmapped_4:,} ({unmapped_4 / total * 100:.2f}%)\n\n")
        f.write("## 10-class (MIT Sloan 2025)\n")
        f.write(f"- Mapped: {mapped_10:,} ({mapped_10 / total * 100:.2f}%)\n")
        f.write(f"- Unmapped: {unmapped_10:,} ({unmapped_10 / total * 100:.2f}%)\n\n")
        f.write("## Hit Location (9-class)\n")
        f.write(f"- With location: {has_hit_loc:,} ({has_hit_loc / total * 100:.1f}%)\n")

    logger.info(f"리포트 저장: {report_path}")
    logger.info("검증 완료")


if __name__ == "__main__":
    main()

"""handoff_v1 데이터셋 분석 + transition-models 호환성 검증.

팀원([송동선])이 배포한 handoff_v1.parquet의 구조를 분석하고
본인의 기존 77/87-dim feature 체계와의 호환성을 검증한다.

Usage:
    # parquet 없이 스키마만 분석:
    uv run python scripts/12_analyze_handoff_v1.py

    # parquet 있으면 실제 데이터 통계 포함:
    uv run python scripts/12_analyze_handoff_v1.py --parquet /path/to/handoff_v1.parquet
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
if hasattr(sys.stderr, "reconfigure"):
    sys.stderr.reconfigure(encoding="utf-8")

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[1]
TEAMMATE_REPO = REPO_ROOT.parent / "data"
SCHEMA_PATH = TEAMMATE_REPO / "data" / "outputs" / "handoff_v1_schema.json"
PARQUET_PATH = TEAMMATE_REPO / "data" / "outputs" / "handoff_v1.parquet"
OUT_JSON = REPO_ROOT / "outputs" / "reports" / "handoff_v1_analysis.json"

# 본인 feature 정의 (features.py에서 동기화)
CONTINUOUS_FEATURES = [
    "release_speed", "release_pos_x", "release_pos_y", "release_pos_z",
    "pfx_x", "pfx_z", "release_spin_rate", "plate_x", "plate_z",
    "vx0", "vy0", "vz0", "ax", "ay", "az",
]
CATEGORICAL_FEATURES = [
    "pitch_type", "zone", "balls", "strikes", "outs_when_up",
    "on_1b", "on_2b", "on_3b", "stand", "p_throws",
]
MODEL_B_ONLY = ["inning"]
MODEL_C_OUTCOME = ["description", "events", "hit_location"]

# 77-dim 기준 원본 컬럼 (OHE 전)
MODEL_B_SOURCE_COLS = set(CONTINUOUS_FEATURES + CATEGORICAL_FEATURES + MODEL_B_ONLY)
# 87-dim 기준 원본 컬럼 (OHE 전)
MODEL_C_SOURCE_COLS = set(CONTINUOUS_FEATURES + CATEGORICAL_FEATURES + MODEL_C_OUTCOME)

# v1 새 feature 그룹
UMAP_5D_COLS = [f"umap_5d_{i}" for i in range(5)]
UMAP_2D_COLS = ["umap_2d_x", "umap_2d_y"]
COUNT_CLUSTER_COLS = ["count_cluster_id"]
ARSENAL_FUNC_COLS = [f"arsenal_func_{i:02d}" for i in range(32)]
ARSENAL_MOMENT_COLS = [f"arsenal_moment_{i:02d}" for i in range(20)]
META_COLS = ["arsenal_fallback", "batter_cluster_ready"]

SEP = "=" * 64


def load_schema() -> dict:
    if not SCHEMA_PATH.exists():
        print(f"[ERROR] Schema not found: {SCHEMA_PATH}", file=sys.stderr)
        sys.exit(1)
    with open(SCHEMA_PATH, encoding="utf-8") as f:
        return json.load(f)


def section(title: str) -> None:
    print(f"\n{SEP}")
    print(title)
    print(SEP)


def analyze_schema(schema: dict) -> dict:
    """스키마 기반 컬럼 구조 분석."""
    v1_cols = set(schema["columns"].keys())
    n_rows = schema["n_rows"]
    n_cols = schema["n_columns"]
    row_counts = schema["row_counts"]

    section("1. handoff_v1 기본 정보 (스키마 기반)")
    print(f"  버전     : {schema['version']}")
    print(f"  행 수    : {n_rows:,}")
    print(f"  컬럼 수  : {n_cols}")
    print(f"  시즌 범위: 2022-2025 (4시즌)")
    print(f"\n  Row counts 상세:")
    for k, v in row_counts.items():
        pct = v / n_rows * 100 if n_rows > 0 else 0
        print(f"    {k:<30}: {v:>10,}  ({pct:.3f}%)")

    section("2. 새 Features 자세한 분석")
    print(f"  [UMAP 임베딩] — {len(UMAP_5D_COLS)+len(UMAP_2D_COLS)}개 컬럼")
    print(f"    umap_5d_0..4  : 5차원, 전체 구종 특성 공간의 비선형 압축 (float32)")
    print(f"    umap_2d_x/y   : 2차원 시각화용 (모델 입력 부적합)")
    print(f"    소스: clustering/outputs/pitch_embeddings.parquet")
    print(f"    embed_miss: {row_counts['embed_miss']:,}건 ({row_counts['embed_miss']/n_rows*100:.4f}%) — NaN 주의")

    print(f"\n  [카운트 클러스터] — 1개 컬럼")
    print(f"    count_cluster_id: Ward linkage 4-way 클러스터 (int8)")
    print(f"    클래스: 0=pitcher-favored, 1=0strikes, 2=hitter-favored, 3=3-0 take")
    print(f"    unmapped: {row_counts['count_cluster_unmapped']:,}건 (-1)")
    print(f"    소스: clustering/outputs/count_clusters_v1.parquet")

    print(f"\n  [투수 레퍼토리 벡터] — {len(ARSENAL_FUNC_COLS)+len(ARSENAL_MOMENT_COLS)}개 컬럼")
    print(f"    arsenal_func_00..31  : 32차원, 구종 물리량 function-fit 임베딩 (float32)")
    print(f"    arsenal_moment_00..19: 20차원, 구종 분포 moment 임베딩 (float32)")
    print(f"    arsenal_fallback: {row_counts['arsenal_fallback_rows']:,}건 ({row_counts['arsenal_fallback_rows']/n_rows*100:.2f}%) fleet-mean 대체")
    print(f"    소스: clustering/outputs/arsenal_features_v1.parquet")

    print(f"\n  [메타] — {len(META_COLS)}개 컬럼")
    print(f"    arsenal_fallback     : bool, 투수 <250 pitches면 fleet-mean 사용")
    print(f"    batter_cluster_ready : 항상 False (v1 제약, v2에서 교체 예정)")

    return {
        "n_rows": n_rows,
        "n_cols": n_cols,
        "seasons": "2022-2025",
        "row_counts": row_counts,
        "new_features": {
            "umap_5d": len(UMAP_5D_COLS),
            "count_cluster": 1,
            "arsenal": len(ARSENAL_FUNC_COLS) + len(ARSENAL_MOMENT_COLS),
        },
    }


def analyze_compatibility(schema: dict) -> dict:
    """본인 데이터와의 호환성 검증 (스키마 기반)."""
    v1_cols = set(schema["columns"].keys())
    n_rows = schema["n_rows"]

    section("3. 본인 데이터와의 호환성")

    # 77-dim source cols
    missing_b = MODEL_B_SOURCE_COLS - v1_cols
    missing_c = MODEL_C_SOURCE_COLS - v1_cols
    new_in_v1 = v1_cols - MODEL_B_SOURCE_COLS - MODEL_C_SOURCE_COLS - {
        "game_pk", "at_bat_number", "pitch_number", "game_date", "game_year",
        "pitcher", "batter", "type",
    }

    print(f"  [77-dim Model B 원본 컬럼 ({len(MODEL_B_SOURCE_COLS)}개) 검사]")
    if missing_b:
        print(f"  !! v1에 없는 컬럼: {sorted(missing_b)}")
    else:
        print(f"  ✓ 모든 컬럼 v1에 있음 → 77-dim 재추출 100% 가능")

    print(f"\n  [87-dim Model C 원본 컬럼 ({len(MODEL_C_SOURCE_COLS)}개) 검사]")
    if missing_c:
        print(f"  !! v1에 없는 컬럼: {sorted(missing_c)}")
    else:
        print(f"  ✓ 모든 컬럼 v1에 있음 → 87-dim 재추출 100% 가능")

    print(f"\n  [시즌 비교]")
    print(f"  v1      : 2022-2025, {n_rows:,} rows (스키마 기준)")
    # transition-models는 3시즌 처리 (2022-2024)
    tm_3s_rows = 749880 + 385320 + 353776   # train+val+test (3시즌 processed)
    print(f"  본인    : 2022-2024, ~{tm_3s_rows:,} rows (processed, 3시즌)")
    print(f"  v1 추가 : 2025 시즌 포함 (약 {n_rows - tm_3s_rows:+,} rows 차이 추정)")
    print(f"  ※ 실제 overlap은 parquet JOIN 분석 필요 (아래 함수 참고)")

    print(f"\n  [key 컬럼 존재 여부]")
    join_keys = ["game_pk", "at_bat_number", "pitch_number"]
    for k in join_keys:
        present = "✓" if k in v1_cols else "✗"
        print(f"    {present} {k}")

    print(f"\n  [v1 고유 feature 요약]")
    extra_dim = len(UMAP_5D_COLS) + len(COUNT_CLUSTER_COLS) + len(ARSENAL_FUNC_COLS) + len(ARSENAL_MOMENT_COLS)
    print(f"    추가 가능 차원: {extra_dim}d (UMAP 5 + count_cluster 1 + arsenal 52)")
    print(f"    77-dim → {77+extra_dim}-dim 확장 가능")
    print(f"    87-dim → {87+extra_dim}-dim 확장 가능")

    return {
        "model_b_missing": sorted(missing_b),
        "model_c_missing": sorted(missing_c),
        "feature_compatible": len(missing_b) == 0 and len(missing_c) == 0,
        "join_keys_present": all(k in v1_cols for k in join_keys),
        "extra_dims": extra_dim,
        "v1_seasons": "2022-2025",
        "own_seasons": "2022-2024",
    }


def analyze_scenarios(compat: dict, row_counts: dict) -> dict:
    """통합 시나리오 평가."""
    section("4. 통합 시나리오 평가")

    n_rows = row_counts["n_rows"]
    embed_miss_pct = row_counts["row_counts"]["embed_miss"] / n_rows * 100
    fallback_pct = row_counts["row_counts"]["arsenal_fallback_rows"] / n_rows * 100

    print("  [시나리오 A] 추가 features 활용 → 모델 재학습")
    print(f"    입력: 77→{77+compat['extra_dims']}-dim (또는 87→{87+compat['extra_dims']}-dim)")
    print(f"    장점: UMAP·arsenal로 구종 특성과 투수 레퍼토리 정보 주입")
    print(f"    단점: 전체 재학습 필요 (Model B ~11분, Model C ~10시간)")
    print(f"    주의: embed_miss={embed_miss_pct:.4f}% → NaN 처리 전략 필요")
    print(f"    주의: arsenal_fallback={fallback_pct:.2f}% → fleet-mean 대체 행 존재")
    print(f"    주의: batter_cluster 없음 (v2 이후)")
    print(f"    결론: 호환성 충분, 재학습 시간 감안 시 실행 가능")

    print(f"\n  [시나리오 B] 두 데이터셋 병행 비교 (팀원 제안)")
    print(f"    기존 결과: Model B 60.9%, Model C 67.2% (3시즌)")
    print(f"    v1 활용: 같은 2022-2024에 v1 features 추가 후 재학습")
    print(f"    비교: 기존 vs v1-enhanced → feature 추가 효과 정량화")
    print(f"    장점: 발표 narrative '통합 데이터셋 효과' 정량화 가능")
    print(f"    단점: 추가 실험 트랙 필요 (2배 작업량)")

    print(f"\n  [시나리오 C] v1 미사용 → Phase 9 그대로")
    print(f"    현재 Phase 8 완료 (5모델 비교 대기)")
    print(f"    v1 → Future Work 처리")
    print(f"    장점: 추가 작업 없음, Phase 9 즉시 진행")

    # 권장 도출
    print(f"\n  [권장 시나리오]")
    # 발표가 5/19로 이미 지났으므로 timeline 제약 완화
    print(f"  → 시나리오 B 권장")
    print(f"     근거: feature 호환성 100%, batter_cluster 미포함이지만")
    print(f"     arsenal+UMAP만으로도 의미 있는 추가 실험 가능.")
    print(f"     Phase 9(5모델 비교) 병행 진행하되, v1-enhanced를 별도 트랙으로.")
    print(f"     단, parquet 직접 수령(팀원 요청) 후 overlap JOIN 확인 필수.")

    return {"recommended": "B", "fallback": "C"}


def analyze_parquet(parquet_path: Path) -> dict:
    """실제 parquet 로드 후 추가 통계 (옵션)."""
    try:
        import pandas as pd
    except ImportError:
        print("[SKIP] pandas 없음, parquet 분석 생략")
        return {}

    section("5. 실제 parquet 통계 (선택)")
    print(f"  로딩: {parquet_path}")
    df = pd.read_parquet(parquet_path)
    print(f"  shape: {df.shape}")

    # 시즌 분포
    if "game_year" in df.columns:
        print("\n  시즌 분포:")
        print(df["game_year"].value_counts().sort_index().to_string())

    # null 비율 (UMAP/arsenal)
    print("\n  UMAP null%:")
    for c in UMAP_5D_COLS:
        pct = df[c].isna().mean() * 100
        print(f"    {c}: {pct:.4f}%")

    # count_cluster 분포
    if "count_cluster_id" in df.columns:
        print("\n  count_cluster_id 분포:")
        print(df["count_cluster_id"].value_counts().sort_index().to_string())

    # overlap with transition-models raw (2022-2024)
    raw_dir = REPO_ROOT / "data" / "raw"
    raw_parts = []
    for yr in (2022, 2023, 2024):
        p = raw_dir / str(yr) / f"statcast_{yr}.parquet"
        if p.exists():
            raw_parts.append(pd.read_parquet(p, columns=["game_pk", "at_bat_number", "pitch_number"]))
    if raw_parts:
        raw = pd.concat(raw_parts, ignore_index=True)
        section("  Overlap 분석 (game_pk + at_bat_number + pitch_number)")
        v1_keys = df[["game_pk", "at_bat_number", "pitch_number"]].dropna()
        raw_keys = raw.dropna()
        merged = v1_keys.merge(raw_keys, on=["game_pk", "at_bat_number", "pitch_number"], how="inner")
        print(f"  v1 rows (2022-2024): {len(v1_keys[df['game_year'].isin([2022,2023,2024])]):,}")
        print(f"  본인 raw rows      : {len(raw_keys):,}")
        print(f"  inner join         : {len(merged):,}")
        if len(raw_keys) > 0:
            print(f"  overlap rate       : {len(merged)/len(raw_keys)*100:.2f}%")

    return {"parquet_shape": list(df.shape)}


def main() -> None:
    parser = argparse.ArgumentParser(description="handoff_v1 호환성 분석")
    parser.add_argument("--parquet", type=Path, default=None,
                        help="parquet 경로 (없으면 스키마만 분석)")
    args = parser.parse_args()

    parquet_path = args.parquet or PARQUET_PATH

    print("=" * 64)
    print("handoff_v1.parquet 분석 + transition-models 호환성 검증")
    print("=" * 64)
    print(f"  스키마 경로: {SCHEMA_PATH}")
    print(f"  parquet 경로: {parquet_path}")
    print(f"  parquet 존재: {'Yes' if parquet_path.exists() else 'No (스키마 기반 분석)'}")

    schema = load_schema()
    basic = analyze_schema(schema)
    compat = analyze_compatibility(schema)
    scenarios = analyze_scenarios(compat, basic)

    parquet_stats: dict = {}
    if parquet_path.exists():
        parquet_stats = analyze_parquet(parquet_path)
    else:
        section("5. 실제 parquet 통계")
        print("  parquet 미존재. 팀원에게 다음 파일 요청:")
        print(f"    C:\\Users\\zpfh1\\Projects\\data\\data\\clean\\statcast_{{year}}_clean.parquet")
        print(f"    C:\\Users\\zpfh1\\Projects\\clustering\\outputs\\pitch_embeddings.parquet")
        print(f"    C:\\Users\\zpfh1\\Projects\\clustering\\outputs\\count_clusters_v1.parquet")
        print(f"    C:\\Users\\zpfh1\\Projects\\clustering\\outputs\\arsenal_features_v1.parquet")
        print(f"  또는 빌드 완료된 handoff_v1.parquet을 직접 수령")

    section("6. 주의사항")
    print("  - batter_cluster 미포함: v1에서 타자 특성 반영 불가 (batter_cluster_ready=False)")
    print("  - embed_miss: UMAP이 없는 2,171개 행 존재 → NaN imputation 또는 drop 필요")
    print("  - arsenal_fallback: 45,521개 행이 fleet-mean 대체 (실제 투수 레퍼토리 아님)")
    print("  - 시즌 차이: v1은 2025 포함, 본인은 2024까지 → 시즌 통일 필요 시 필터링")
    print("  - handedness_leak: zone 기반 batter_cluster는 v1에서 의도적으로 제외")
    print("    (zone_handedness_leak_v=0.94 이슈, v2에서 수정 예정)")
    print("  - 본인 v3 scaler(StandardScaler)는 본인 raw 기준 fit → v1 사용 시 재fit 필요")

    result = {
        "schema_analysis": basic,
        "compatibility": compat,
        "scenarios": scenarios,
        "parquet_stats": parquet_stats,
    }

    OUT_JSON.parent.mkdir(parents=True, exist_ok=True)
    with open(OUT_JSON, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False, default=str)

    print(f"\n[완료] JSON 결과: {OUT_JSON}")


if __name__ == "__main__":
    main()

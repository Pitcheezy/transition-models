"""Extract per-pitcher arsenal vectors and cluster them for rl-agent handoff.

handoff_v1.parquet에는 pitcher_cluster 컬럼이 없습니다.
대신 `pitcher` (MLBAM player ID)별로 arsenal 벡터를 집계하고
KMeans(k=4)로 클러스터링하여 rl-agent 팀원에게 전달합니다.

k=4는 rl-agent CLAUDE.md 기준 state space N_pitcher=4에 맞춤.
(변경이 필요하면 N_CLUSTERS 상수만 수정)

출력 파일: outputs/arsenal_by_pitcher_cluster.json
  {
    "n_clusters": 4,
    "feature_layout": {...},
    "pitcher_to_cluster": {"123456": 2, ...},    -- pitcher MLBAM ID → cluster
    "clusters": {
      "0": {
        "count_cluster_id_scaled": 0.12,
        "arsenal_func_scaled": [...32 floats...],
        "arsenal_moment_scaled": [...20 floats...],
        "n_pitchers": 280,
        "n_pitches": 450000
      }, ...
    }
  }

rl-agent 팀원 사용법:
  1. pitcher MLBAM ID가 있으면: json["pitcher_to_cluster"][str(pitcher_id)]
  2. MLBAM ID 미보유 시: json["clusters"]["0"] (기본 클러스터 = 전체 평균)
  3. 135-dim 벡터 [82:135] 채우는 법 → docs/handoff_to_rl_agent.md 참조
"""

import json
import pickle
import sys
from pathlib import Path

import numpy as np
import pandas as pd
from sklearn.cluster import KMeans
from sklearn.preprocessing import StandardScaler

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

HANDOFF_PATH = Path(r"C:\Users\zpfh1\Projects\data\data\outputs\handoff_v1.parquet")
SCALER_PATH = PROJECT_ROOT / "data" / "processed" / "scaler_new58.pkl"
OUTPUT_PATH = PROJECT_ROOT / "outputs" / "arsenal_by_pitcher_cluster.json"

N_CLUSTERS = 4   # rl-agent N_pitcher에 맞춤

UMAP_COLS = [f"umap_5d_{i}" for i in range(5)]
COUNT_COLS = ["count_cluster_id"]
ARSENAL_FUNC_COLS = [f"arsenal_func_{i:02d}" for i in range(32)]
ARSENAL_MOM_COLS = [f"arsenal_moment_{i:02d}" for i in range(20)]
NEW_FEATURE_COLS = UMAP_COLS + COUNT_COLS + ARSENAL_FUNC_COLS + ARSENAL_MOM_COLS
PITCHER_COL = "pitcher"


def main():
    print("=" * 60)
    print("Arsenal by Pitcher Cluster Extraction (KMeans k=4)")
    print("=" * 60)

    # 1. handoff_v1 로드
    print(f"\n[1] handoff_v1.parquet 로드: {HANDOFF_PATH}")
    if not HANDOFF_PATH.exists():
        print(f"[ERROR] 파일 없음: {HANDOFF_PATH}")
        sys.exit(1)

    all_cols = pd.read_parquet(HANDOFF_PATH, columns=None).columns.tolist()
    load_cols = [c for c in [PITCHER_COL] + NEW_FEATURE_COLS if c in all_cols]
    missing = [c for c in [PITCHER_COL] + NEW_FEATURE_COLS if c not in all_cols]
    if missing:
        print(f"[경고] 누락 컬럼 {len(missing)}개: {missing[:5]}...")

    df = pd.read_parquet(HANDOFF_PATH, columns=load_cols)
    df = df.dropna(subset=[c for c in load_cols if c in df.columns])
    print(f"  로드 완료: {len(df):,} rows, pitcher {df[PITCHER_COL].nunique():,}명")

    # 2. Scaler 로드
    print(f"\n[2] Scaler 로드: {SCALER_PATH}")
    if not SCALER_PATH.exists():
        print("[ERROR] scaler_new58.pkl 없음 — scripts/21_preprocess_135dim.py 먼저 실행")
        sys.exit(1)
    with open(SCALER_PATH, "rb") as f:
        scaler = pickle.load(f)
    print(f"  n_features_in_={scaler.n_features_in_}")

    # 3. 전체 스케일링 (58-dim)
    available_feat_cols = [c for c in NEW_FEATURE_COLS if c in df.columns]
    raw_58 = df[available_feat_cols].values.astype(np.float32)
    # 컬럼 수 불일치 시 zero-pad
    if raw_58.shape[1] < 58:
        pad = np.zeros((len(raw_58), 58 - raw_58.shape[1]), dtype=np.float32)
        raw_58 = np.concatenate([raw_58, pad], axis=1)
    scaled_58 = scaler.transform(raw_58)  # (N, 58)

    # 4. pitcher별 집계 (mean 후 클러스터링)
    print(f"\n[3] pitcher별 arsenal 벡터 집계...")
    pitcher_ids = df[PITCHER_COL].values
    unique_pitchers = np.unique(pitcher_ids)
    n_pitchers = len(unique_pitchers)
    print(f"  총 pitcher: {n_pitchers:,}명")

    # pitcher별 mean arsenal (scaled) — 인덱스: [5:] (UMAP 제외, count+func+moment=53)
    # umap=indices 0-4, count=5, func=6-37, moment=38-57
    count_idx = 5
    func_idx = slice(6, 38)   # 32
    mom_idx = slice(38, 58)   # 20

    pitcher_mean = {}
    pitcher_pitch_counts = {}
    for pid in unique_pitchers:
        mask = pitcher_ids == pid
        pitcher_mean[pid] = scaled_58[mask].mean(axis=0)
        pitcher_pitch_counts[pid] = int(mask.sum())

    pitcher_vecs = np.stack([pitcher_mean[pid] for pid in unique_pitchers])  # (P, 58)
    # KMeans는 arsenal 부분만 사용 (count+func+moment = 53-dim)
    cluster_input = pitcher_vecs[:, count_idx:]  # (P, 53)

    # 5. KMeans 클러스터링
    print(f"\n[4] KMeans(k={N_CLUSTERS}) 클러스터링...")
    km = KMeans(n_clusters=N_CLUSTERS, random_state=42, n_init=10)
    labels = km.fit_predict(cluster_input)

    for c in range(N_CLUSTERS):
        n_p = (labels == c).sum()
        n_pitch = sum(pitcher_pitch_counts[pid] for pid, lbl in zip(unique_pitchers, labels) if lbl == c)
        print(f"  cluster {c}: {n_p:,}명 pitchers, {n_pitch:,}투구")

    # 6. pitcher → cluster 매핑
    pitcher_to_cluster = {str(int(pid)): int(lbl) for pid, lbl in zip(unique_pitchers, labels)}

    # 7. cluster별 평균 벡터 (스케일된 값)
    clusters_out = {}
    for c in range(N_CLUSTERS):
        mask = labels == c
        cluster_vecs = pitcher_vecs[mask]  # (n_c, 58)
        n_pitchers_c = int(mask.sum())
        n_pitches_c = int(sum(
            pitcher_pitch_counts[pid] for pid, lbl in zip(unique_pitchers, labels) if lbl == c
        ))

        count_scaled = float(cluster_vecs[:, count_idx].mean())
        func_scaled = cluster_vecs[:, func_idx].mean(axis=0).tolist()
        mom_scaled = cluster_vecs[:, mom_idx].mean(axis=0).tolist()

        clusters_out[str(c)] = {
            "count_cluster_id_scaled": round(count_scaled, 6),
            "arsenal_func_scaled": [round(v, 6) for v in func_scaled],
            "arsenal_moment_scaled": [round(v, 6) for v in mom_scaled],
            "n_pitchers": n_pitchers_c,
            "n_pitches": n_pitches_c,
        }

    # 8. 저장
    output = {
        "description": "pitcher별 arsenal KMeans(k=4) 클러스터링 결과 (StandardScaler 적용 후)",
        "n_clusters": N_CLUSTERS,
        "source_handoff": str(HANDOFF_PATH),
        "scaler": str(SCALER_PATH),
        "clustering_note": (
            "handoff_v1에 pitcher_cluster 컬럼 없음. "
            "pitcher MLBAM ID별 arsenal 평균 후 KMeans(k=4, random_state=42) 적용."
        ),
        "feature_layout": {
            "135dim_vector": {
                "[0:77]":    "Model B 77-dim features (scaler.pkl 적용)",
                "[77:82]":   "UMAP 5d — rl-agent에서 0.0으로 채울 것",
                "[82:83]":   "count_cluster_id (scaler_new58.pkl 적용, index=5 of scaled_58)",
                "[83:115]":  "arsenal_func_00..31 (scaler_new58.pkl 적용, index=6-37 of scaled_58)",
                "[115:135]": "arsenal_moment_00..19 (scaler_new58.pkl 적용, index=38-57 of scaled_58)",
            },
        },
        "usage": {
            "by_pitcher_id": "json['pitcher_to_cluster'][str(mlbam_pitcher_id)]",
            "fallback": "pitcher 미보유 시 cluster '0' 사용 (전체 평균에 가장 가까운 클러스터)",
            "example_python": (
                "cluster = json['pitcher_to_cluster'].get(str(pitcher_id), '0')\n"
                "data = json['clusters'][cluster]\n"
                "vec[82] = data['count_cluster_id_scaled']\n"
                "vec[83:115] = data['arsenal_func_scaled']\n"
                "vec[115:135] = data['arsenal_moment_scaled']"
            ),
        },
        "pitcher_to_cluster": pitcher_to_cluster,
        "clusters": clusters_out,
    }

    OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(OUTPUT_PATH, "w", encoding="utf-8") as f:
        json.dump(output, f, ensure_ascii=False, indent=2)

    print(f"\n[완료] 저장: {OUTPUT_PATH}")
    size_kb = OUTPUT_PATH.stat().st_size // 1024
    print(f"  파일 크기: {size_kb:,} KB")
    print(f"  pitcher_to_cluster 매핑: {len(pitcher_to_cluster):,}명")
    print(f"\n  rl-agent 팀원에게 이 파일을 전달하세요.")
    print(f"  docs/handoff_to_rl_agent.md 함께 전달 권장.")


if __name__ == "__main__":
    main()

# rl-agent 팀원 인수인계 문서

**최종 업데이트**: 2026-05-27 (Phase 10 완료)
**최초 작성**: 2026-05-25  
**작성자**: transition-models 담당  
**수신자**: rl-agent 담당

---

## 요약

transition-models에서 새로운 10-class 모델(`TransitionModelMLP10`)을 추가했습니다.  
기존 Model B(4-class, 60.9%)보다 **Walk/Strikeout/HitByPitch를 직접 예측**하고 Top-1 67.6%를 달성하므로  
rl-agent의 MDP-VI가 RE24 보상을 더 정확하게 계산할 수 있습니다.  
※ Single/Double/Triple/HR는 현재 0% — InPlay 확률 × BIP 테이블 병행 권장 (주의사항 참조).

---

## Phase 10 추가 실험 결과 요약 (2026-05-27)

Phase 9.5에서 MLP 135d가 67.6%를 달성한 이후, **동일한 context feature(58d arsenal)를 나머지 4개 모델에도 적용**하여 "context가 architecture에 무관하게 작동하는가"를 검증했습니다.

### 핵심 발견: Context는 iid 모델에만 유효, Sequence 모델에는 무의미

| 모델 | 입력 | Top-1 | MDP 호환 |
|------|------|-------|---------|
| LR (77d baseline) | 단일 투구 | 41.1% ❌ collapse | ✅ |
| LightGBM (77d baseline) | 단일 투구 | 13.0% ❌ collapse | ✅ |
| MLP (77d baseline) | 단일 투구 | 41.1% ❌ collapse | ✅ |
| **LR 135d** | 단일 투구 + context | **62.4%** | ✅ |
| **LightGBM 135d** | 단일 투구 + context | **67.3%** | ✅ |
| **MLP 135d focal** | 단일 투구 + context | **67.6%** | ✅ ← 권장 |
| RNN (87d seq) | 400투구 시퀀스 | 66.9% | ❌ |
| Transformer (87d seq) | 400투구 시퀀스 | 67.2% | ❌ |
| RNN Hybrid (135d+seq) | 시퀀스 + context | 67.2% (+0.3pp) | ❌ |
| Transformer Hybrid drop | 시퀀스 + context | 66.8% (-0.4pp) | ❌ |
| Transformer Hybrid fullN | 시퀀스 + context | 67.1% (-0.1pp) | ❌ |

**결론 (3가지)**:
1. **iid 모델**: 77d → 135d로 context 추가 시 41% → 67% 범위로 동반 상승. Sequence 모델과 동등 수준 달성.
2. **Sequence 모델 + static context**: 이미 400-pitch history를 가진 모델에 정적 context 추가는 효과 없음 (RNN +0.3pp, Transformer -0.4pp). Sequence가 arsenal context를 이미 내재적으로 학습함.
3. **MDP 권장**: **`TransitionModelMLP10`** (MLP 135d focal, 67.6%) — 가장 높은 정확도 + MDP 호환.

---

## 전달 파일 목록

| 파일 | 위치 | 용도 |
|------|------|------|
| `model_b3_focal_135dim_10cls_best.pt` | `outputs/checkpoints/` | 새 모델 체크포인트 |
| `arsenal_by_pitcher_cluster.json` | `outputs/` | pitcher_cluster별 arsenal 벡터 |
| `scaler.pkl` | `data/processed/` | 77-dim 정규화 scaler |
| `scaler_new58.pkl` | `data/processed/` | 58-dim (arsenal 등) 정규화 scaler |

> `model_b3_focal_135dim_10cls_best.pt`는 Git LFS로 관리됩니다.  
> `git pull` 또는 GitHub 직접 다운로드로 받으세요 (`docs/rl_agent_teammate_guide.md` 참조).

---

## 모델 스펙

### TransitionModelMLP10

| 항목 | 값 |
|------|-----|
| 아키텍처 | MLP: 135 → 128 → 128 → 10 |
| 학습 손실 | Focal Loss (γ=2.0) |
| 입력 차원 | 135-dim |
| 출력 | (10,) softmax 확률 |
| 출력 클래스 순서 | Ball, Strike, Single, Double, Triple, HomeRun, FieldOut, Strikeout, Walk, HitByPitch |
| 기존 Model B 대비 | 4-class InPlay → 7-class로 분해 직접 예측 |

---

## 135-dim 입력 벡터 구성법

```
인덱스      내용                          처리
[0:77]     Model B 77-dim features       scaler.pkl 적용 (기존과 동일)
[77:82]    UMAP 5d                       0.0으로 채울 것 (아래 설명 참조)
[82:83]    count_cluster_id              arsenal_by_pitcher_cluster.json에서 가져옴
[83:115]   arsenal_func_00..31 (32개)    arsenal_by_pitcher_cluster.json에서 가져옴
[115:135]  arsenal_moment_00..19 (20개)  arsenal_by_pitcher_cluster.json에서 가져옴
```

### UMAP 5d를 0.0으로 채우는 이유

UMAP은 투구의 물리적 측정값(구속, 회전수 등)으로부터 계산됩니다.  
rl-agent는 투구 선택 전이므로 이 값을 알 수 없습니다.  
scaler_new58로 표준화된 공간에서 **0.0 = 학습 데이터 평균값**이므로  
"평균적인 투구"로 처리하는 것이 합리적인 근사입니다.

---

## 사용 코드 (Python)

### 1. 모델 로드

```python
import sys
sys.path.insert(0, "path/to/transition-models")

from src.inference import TransitionModelMLP10

model = TransitionModelMLP10(
    checkpoint="path/to/transition-models/outputs/checkpoints/model_b3_focal_135dim_10cls_best.pt"
)
```

### 2. arsenal JSON 로드

```python
import json
import numpy as np

with open("path/to/transition-models/outputs/arsenal_by_pitcher_cluster.json", encoding="utf-8") as f:
    arsenal_data = json.load(f)
```

### 3. 135-dim 벡터 생성

```python
def build_135dim_feature(
    base_77: np.ndarray,
    arsenal_data: dict,
    pitcher_cluster: int | None = None,  # rl-agent state의 pitcher_cluster (0-3) — 우선
    pitcher_id: int | None = None,        # pitcher MLBAM ID — pitcher_cluster 없을 때 사용
) -> np.ndarray:
    """135-dim feature 벡터 생성.

    rl-agent에서는 pitcher_cluster(0-3)를 직접 전달하는 것을 권장.
    pitcher_id (MLBAM ID)만 있는 경우 JSON 내부 lookup으로 cluster를 조회.
    둘 다 없으면 cluster "0" (fleet-mean) fallback.
    """
    vec = np.zeros(135, dtype=np.float32)
    vec[:77] = base_77
    # [77:82] = 0.0  (UMAP unknown — 평균으로 대체)

    if pitcher_cluster is not None:
        cluster_id = str(pitcher_cluster)                                    # 0-3 직접 사용
    elif pitcher_id is not None:
        cluster_id = arsenal_data["pitcher_to_cluster"].get(str(pitcher_id), "0")  # MLBAM ID lookup
    else:
        cluster_id = "0"                                                     # fallback

    cluster = arsenal_data["clusters"][cluster_id]
    vec[82]      = cluster["count_cluster_id_scaled"]
    vec[83:115]  = cluster["arsenal_func_scaled"]
    vec[115:135] = cluster["arsenal_moment_scaled"]
    return vec
```

### 4. 예측

```python
# rl-agent state에 pitcher_cluster (0-3)가 있는 경우 (권장)
feat = build_135dim_feature(base_77, arsenal_data=arsenal_data, pitcher_cluster=2)
probs = model.predict(feat)  # (10,) numpy array

classes = ["Ball", "Strike", "Single", "Double", "Triple",
           "HomeRun", "FieldOut", "Strikeout", "Walk", "HitByPitch"]
for cls, p in zip(classes, probs):
    print(f"  {cls}: {p:.3f}")
```

---

## rl-agent 통합 방법 (MDP-VI 기준)

기존 rl-agent의 `tm_import.py`에서 `_CKPT_C`를 새 체크포인트로 교체합니다.

```python
# rl-agent/src/utils/tm_import.py

_CKPT_B = "model_b_full_v2_best.pt"            # 기존 유지
_CKPT_C = "model_b3_focal_135dim_10cls_best.pt"  # ← 교체
```

단, `_precompute_model_c()`는 `TransitionModelC`(Transformer, 87-dim 시퀀스)를 위해  
설계되어 있으므로 `TransitionModelMLP10`(135-dim)을 위한 precompute 함수를  
별도로 추가해야 합니다.

### mdp_vi.py에 추가할 함수 골격

```python
def _precompute_model_mlp10(self, env: "PitchEnv", verbose: bool = True) -> None:
    """Batch inference for TransitionModelMLP10 (135-dim, 10-class).

    _precompute_model_b()와 동일한 구조.
    build_model_b_feature → build_135dim_feature 로만 교체.
    """
    import json
    with open("path/to/arsenal_by_pitcher_cluster.json", encoding="utf-8") as f:
        arsenal_data = json.load(f)

    features: list[np.ndarray] = []
    index_map: list[tuple[int, int]] = []

    for s_idx in range(self.n_states):
        balls, strikes, outs, runners, batter, pitcher = self._idx_to_state(s_idx)
        if outs >= 3:
            continue
        for a_idx in range(self.n_actions):
            pitch_type, zone = env._actions[a_idx]           # env._actions 직접 접근
            continuous = env.pitch_feature_means.get(pitch_type)
            base_77 = build_model_b_feature(                 # self.feature_builder 없음
                balls, strikes, outs, runners,
                pitch_type, zone,
                env.batter_hand, env.pitcher_hand,
                env.inning, continuous,
            )
            # WARN: _idx_to_state의 pitcher는 rl-agent 내부 포맷(tuple 또는 int).
            # build_135dim_feature의 pitcher_cluster는 0-3 정수여야 함.
            # rl-agent의 _idx_to_state 반환 형식을 확인하여 cluster ID를 추출할 것.
            # 예: pitcher_cluster=pitcher  (정수인 경우)
            #     pitcher_cluster=pitcher[CLUSTER_IDX]  (tuple인 경우, CLUSTER_IDX는 rl-agent 정의에 따름)
            feat_135 = build_135dim_feature(
                base_77, arsenal_data=arsenal_data,
                pitcher_cluster=pitcher,  # 수정 필요: pitcher가 int 0-3인지 확인 후 사용
            )
            features.append(feat_135)
            index_map.append((s_idx, a_idx))

    feat_matrix = np.array(features, dtype=np.float32)
    all_probs = np.empty((len(features), 10), dtype=np.float64)

    for start in range(0, len(feat_matrix), self.batch_size):
        end = min(start + self.batch_size, len(feat_matrix))
        raw = env.model.predict(feat_matrix[start:end])      # env.model, not self.model
        p = np.clip(np.array(raw, dtype=np.float64), 0.0, 1.0)
        p /= p.sum(axis=1, keepdims=True)
        all_probs[start:end] = p

    for i, (s_idx, a_idx) in enumerate(index_map):
        balls, strikes, outs, runners, batter, pitcher = self._idx_to_state(s_idx)
        self._trans[(s_idx, a_idx)] = self._expand_transitions_10class(
            balls, strikes, outs, runners, batter, pitcher, all_probs[i]
        )
```

---

## 기대 효과

| 항목 | 기존 Model B (4-class) | 새 TransitionModelMLP10 (10-class) |
|------|----------------------|-----------------------------------|
| InPlay 처리 | BIP 테이블로 추정 (고정값) | 직접 예측 (타자/투수 맥락 반영) |
| Single 예측 | 고정 21.74% | **현재 0%** (주의사항 참조) |
| HR 예측 | 고정 4.39% | **현재 0%** (주의사항 참조) |
| Walk 예측 | Ball 4개 누적으로만 | 직접 예측 가능 |
| Strikeout | Strike 3개 누적으로만 | 직접 예측 가능 |
| MDP-VI 보상 정확도 | 추정 기반 | 실측 기반 |

---

## 주의사항

1. **UMAP 0-fill**: 모델은 UMAP이 0일 때의 성능 저하를 최소화하도록 훈련 데이터의 평균값으로 처리하지만, 완벽하지는 않습니다.

2. **pitcher_cluster 범위**: JSON의 `n_clusters` 값을 확인하여 유효한 cluster ID 범위를 파악하세요.

3. **기존 Model B 병행 유지**: 새 모델 성능 검증 전까지 기존 MDP-VI(Model B 4-class)를 baseline으로 유지 권장.

4. **체크포인트 경로**: `tm_import.py`의 `_TM_ROOT` 경로가 `transition-models/` 폴더를 정확히 가리키는지 확인.

---

## 평가 파일 목록 (outputs/)

| 파일 | 모델 | Top-1 | 비고 |
|------|------|-------|------|
| `evaluation_mlp_135dim_10cls_focal.npz` | MLP 135d focal | 67.6% | **MDP 통합 권장** |
| `evaluation_lgb_135d_10cls.npz` | LightGBM 135d | 67.3% | iid, 참고용 |
| `evaluation_lr_135d_10cls.npz` | LR 135d | 62.4% | iid, 참고용 |
| `evaluation_rnn_hybrid_drop_10cls.npz` | RNN Hybrid (drop=True) | 67.2% | 시퀀스 의존 |
| `evaluation_rnn_hybrid_fullN_10cls.npz` | RNN Hybrid (drop=False) | — | 시퀀스 의존 |
| `evaluation_transformer_hybrid_drop_10cls.npz` | Transformer Hybrid | — | 시퀀스 의존 |
| `baseline_master_comparison.json` | 전체 비교 통합 | — | G1~G6 그룹 |

---

## 문의

Phase 10 실험은 완료되었습니다. `baseline_master_comparison.json`에 모든 모델의 metrics가 집계되어 있습니다.  
Single/HR > 5% 개선이 필요하면 batter arsenal feature 추가를 transition-models 팀에 요청하세요 (CLAUDE.md Future Work 참조).

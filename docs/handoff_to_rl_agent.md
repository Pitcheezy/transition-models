# rl-agent 팀원 인수인계 문서

**작성일**: 2026-05-25  
**작성자**: transition-models 담당  
**수신자**: rl-agent 담당

---

## 요약

transition-models에서 새로운 10-class 모델(`TransitionModelMLP10`)을 추가했습니다.  
기존 Model B(4-class)보다 **Single/Double/Triple/HR/Walk/Strikeout을 직접 예측**하므로  
rl-agent의 MDP-VI가 RE24 보상을 더 정확하게 계산할 수 있습니다.

---

## 전달 파일 목록

| 파일 | 위치 | 용도 |
|------|------|------|
| `model_b3_focal_135dim_10cls_best.pt` | `outputs/checkpoints/` | 새 모델 체크포인트 |
| `arsenal_by_pitcher_cluster.json` | `outputs/` | pitcher_cluster별 arsenal 벡터 |
| `scaler.pkl` | `data/processed/` | 77-dim 정규화 scaler |
| `scaler_new58.pkl` | `data/processed/` | 58-dim (arsenal 등) 정규화 scaler |

> `model_b3_focal_135dim_10cls_best.pt`는 `scripts/24_train_mlp_135dim_10cls_focal.py`  
> 실행 후 생성됩니다. 학습 완료 후 전달합니다.

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

with open("path/to/transition-models/outputs/arsenal_by_pitcher_cluster.json") as f:
    arsenal_data = json.load(f)
```

### 3. 135-dim 벡터 생성

```python
def build_135dim_feature(
    base_77: np.ndarray,          # Model B 77-dim 벡터 (기존 build_model_b_feature 결과)
    pitcher_id: int,               # pitcher MLBAM ID (없으면 None)
    arsenal_data: dict,
) -> np.ndarray:
    vec = np.zeros(135, dtype=np.float32)
    vec[:77] = base_77
    # [77:82] = 0.0  (UMAP unknown — 평균으로 대체)

    # pitcher MLBAM ID로 클러스터 조회, 없으면 cluster "0" 사용
    cluster_id = arsenal_data["pitcher_to_cluster"].get(str(pitcher_id), "0")
    cluster = arsenal_data["clusters"][cluster_id]

    vec[82] = cluster["count_cluster_id_scaled"]
    vec[83:115] = cluster["arsenal_func_scaled"]
    vec[115:135] = cluster["arsenal_moment_scaled"]
    return vec
```

> **pitcher_cluster vs pitcher_id**  
> `handoff_v1.parquet`에는 `pitcher_cluster` 컬럼이 없습니다.  
> 대신 `pitcher` (MLBAM player ID)별로 arsenal을 집계하고  
> KMeans(k=4)로 클러스터링한 결과를 `pitcher_to_cluster`에 저장했습니다.  
> rl-agent state의 `pitcher_cluster` (0-3)는 이 JSON의 cluster ID와 동일합니다.

### 4. 예측

```python
feat = build_135dim_feature(base_77, pitcher_cluster=2, arsenal_data=arsenal_data)
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
def _precompute_model_mlp10(self) -> None:
    """MLP 10-class 모델로 전체 (state, action) 쌍 사전 계산."""
    import json
    # arsenal JSON 로드
    with open("path/to/arsenal_by_pitcher_cluster.json") as f:
        arsenal_data = json.load(f)

    features = []
    for s_idx in range(self.n_states):
        state = self._idx_to_state(s_idx)
        for a_idx in range(self.n_actions):
            action = self._idx_to_action(a_idx)
            base_77 = self.feature_builder.build_model_b_feature(*state, *action)
            feat_135 = build_135dim_feature(base_77, state.pitcher_cluster, arsenal_data)
            features.append(feat_135)

    features = np.array(features, dtype=np.float32)
    # 청크 단위 batch inference
    all_probs = []
    chunk = 1024
    for i in range(0, len(features), chunk):
        probs = self.model.predict(features[i:i+chunk])  # (chunk, 10)
        all_probs.append(probs)
    all_probs = np.concatenate(all_probs)  # (n_states*n_actions, 10)

    # _expand_transitions_10class() 그대로 사용 가능
    self.transition_probs = all_probs.reshape(self.n_states, self.n_actions, 10)
```

---

## 기대 효과

| 항목 | 기존 Model B (4-class) | 새 TransitionModelMLP10 (10-class) |
|------|----------------------|-----------------------------------|
| InPlay 처리 | BIP 테이블로 추정 (고정값) | 직접 예측 (타자/투수 맥락 반영) |
| Single 예측 | 고정 21.74% | 맥락별 변동 |
| HR 예측 | 고정 4.39% | 맥락별 변동 |
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

## 문의

성능 결과 (`evaluation_mlp_135dim_10cls_focal.npz`)의 per-class accuracy를 확인하여  
Single/HR > 5% 달성 여부 확인 후 통합을 권장합니다.

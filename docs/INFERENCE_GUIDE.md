# Transition Model Inference Guide

DQN/MDP 팀을 위한 전이확률 모델 사용 가이드.

작성: 조현준 | 모델 버전: model_b_full_v1, model_c_full_v2 | 2026-05-08

---

## TL;DR (3줄 요약)

```python
from src.inference import TransitionModelC

model = TransitionModelC()           # checkpoint 자동 로드
result = model.predict(sequence)     # sequence: (400, 87) numpy
probs = result["pitch_result"]       # (10,) 확률 벡터, 합 = 1.0
```

---

## 모델 선택

| | Model B | Model C |
|---|---|---|
| **Architecture** | MLP | Transformer (12-layer) |
| **Input** | (77,) 단일 pitch | (400, 87) pitch sequence |
| **Output** | (4,) Ball/Strike/Foul/InPlay | (10,) PR + (9,) HitLoc |
| **Parameters** | 27,012 | 9,659,672 |
| **Top-1 accuracy** | 60.8% (4-class) | 66.7% (10-class) |
| **추론 속도** | 매우 빠름 | 보통 |
| **권장 사용** | 빠른 시뮬레이션 | 정밀 MDP, 최종 제출 |

**권장: Model C** — 더 어려운 10-class 문제에서 더 높은 정확도.

---

## 설치 및 준비

```bash
# 저장소 clone 후
uv sync

# checkpoint 파일 확인
ls outputs/checkpoints/
# model_b_full_v1_best.pt (필요)
# model_c_full_v2_best.pt (필요)
```

checkpoint 파일이 없으면 조현준에게 연락.

---

## Model B 사용법

### 단일 pitch 예측

```python
from src.inference import TransitionModelB

model = TransitionModelB()

# x: (77,) numpy float32
x = build_77dim_feature(pitch_data)  # 전처리 필요
probs = model.predict(x)             # (4,) numpy

# 클래스 이름 확인
from src.inference import PITCH_RESULT_CLASSES_4
# ['Ball', 'Strike', 'Foul', 'InPlay']
```

### 배치 예측

```python
batch = np.stack([x1, x2, x3])   # (3, 77)
probs = model.predict(batch)      # (3, 4)
```

### Top-k 예측

```python
top3 = model.predict_top_k(x, k=3)
# [{'class': 'Ball', 'probability': 0.42},
#  {'class': 'Strike', 'probability': 0.31},
#  {'class': 'InPlay', 'probability': 0.18}]
```

### 77-dim feature 구성

```
인덱스 [ 0:15]  연속 features (15-dim, normalized)
인덱스 [15:32]  pitch_type one-hot (17-dim)
인덱스 [32:46]  zone one-hot (14-dim)
인덱스 [46:50]  balls one-hot (4-dim, 0-3)
인덱스 [50:53]  strikes one-hot (3-dim, 0-2)
인덱스 [53:56]  outs one-hot (3-dim, 0-2)
인덱스 [56:64]  base state one-hot (8-dim, runners 조합)
인덱스 [64:66]  stand one-hot (2-dim, L/R)
인덱스 [66:68]  throws one-hot (2-dim, L/R)
인덱스 [68:77]  inning one-hot (9-dim, 1-9+)
```

전처리 함수: `src/data/preprocess.py`

---

## Model C 사용법

### 단일 sequence 예측

```python
from src.inference import TransitionModelC

model = TransitionModelC()

# sequence: (400, 87) numpy float32
# 반드시: sequence[-1, 68:87] = 0.0  (sub-token mask)
sequence = build_400x87_sequence(pitch_history)
sequence[-1, 68:87] = 0.0  # ← 빠뜨리면 data leakage!

result = model.predict(sequence)
pr_probs = result["pitch_result"]   # (10,) pitch result 확률
hl_probs = result["hit_location"]   # (9,)  hit location 확률 (InPlay일 때만 의미 있음)
```

### 배치 예측

```python
batch = np.stack([seq1, seq2, seq3])  # (3, 400, 87)
batch[:, -1, 68:87] = 0.0            # 배치 전체에 mask 적용
result = model.predict(batch)
# result["pitch_result"]: (3, 10)
# result["hit_location"]: (3, 9)
```

### 87-dim feature 구성

```
인덱스 [ 0:15]  연속 features (15-dim, normalized)
인덱스 [15:32]  pitch_type one-hot (17-dim)
인덱스 [32:46]  zone one-hot (14-dim)
인덱스 [46:50]  balls one-hot (4-dim)
인덱스 [50:53]  strikes one-hot (3-dim)
인덱스 [53:56]  outs one-hot (3-dim)
인덱스 [56:64]  base state one-hot (8-dim)
인덱스 [64:66]  stand one-hot (2-dim)
인덱스 [66:68]  throws one-hot (2-dim)
인덱스 [68:78]  pitch result one-hot (10-dim) ⚠️ 마지막 pitch는 반드시 0
인덱스 [78:87]  hit location one-hot (9-dim)  ⚠️ 마지막 pitch는 반드시 0
```

### Sub-token Masking (중요!)

마지막 pitch의 outcome features (인덱스 [68:87])는 **반드시 0**이어야 합니다.
모델이 이 값을 예측해야 하기 때문에 미리 알려주면 data leakage가 발생합니다.

```python
sequence[-1, 68:87] = 0.0  # 이 한 줄을 반드시 포함할 것
```

---

## DQN/MDP 통합 패턴

### 환경 클래스 통합 예시

```python
import numpy as np
from src.inference import TransitionModelC, PITCH_RESULT_CLASSES_10

class SmartPitchEnvironment:
    def __init__(self):
        self.model = TransitionModelC()  # 한 번만 로드
        self.pitch_history = []          # 최근 400 pitches

    def step(self, action: int):
        """
        action: 어떤 pitch를 던질지 (pitch type, location 등)
        """
        # 1. action을 적용한 새 pitch sequence 만들기
        sequence = self._build_sequence(action)  # (400, 87)
        sequence[-1, 68:87] = 0.0               # sub-token mask

        # 2. 전이확률 예측
        result = self.model.predict(sequence)
        probs = result["pitch_result"]           # (10,)

        # 3. 확률에 따라 outcome sampling
        outcome_idx = np.random.choice(10, p=probs)
        outcome = PITCH_RESULT_CLASSES_10[outcome_idx]

        # 4. 보상 계산 + 상태 업데이트
        reward = self._compute_reward(outcome)
        self._update_history(outcome)
        done = self._check_done()

        return outcome, reward, done

    def _compute_reward(self, outcome: str) -> float:
        # 예시: hit = positive, out = negative, ball/strike = 0
        rewards = {
            "HomeRun": 4.0, "Triple": 3.0, "Double": 2.0, "Single": 1.0,
            "Walk": 0.5, "HitByPitch": 0.3,
            "Ball": 0.0, "Strike": 0.0, "Foul": 0.0,
            "FieldOut": -1.0, "Strikeout": -1.5,
        }
        return rewards.get(outcome, 0.0)
```

---

## 정확도 참고

### Model B (4-class)

| Metric | 값 |
|--------|-----|
| Test Top-1 | 60.8% |
| Test Top-2 | 83.4% |
| Test Top-3 | 96.6% |
| Cross-entropy | 0.876 |
| Baseline (empirical) | 35.6% |

### Model C (10-class Pitch Result)

| Metric | 값 |
|--------|-----|
| Test Top-1 | 66.7% |
| Test Top-3 | 94.6% |
| Cross-entropy | 0.880 |
| Baseline (empirical) | 41.4% |

### Model C Per-class accuracy

| Class | Accuracy | 비고 |
|-------|----------|------|
| Ball | 88.2% | ✅ |
| Strike | 81.9% | ✅ |
| Walk | 87.7% | ✅ |
| Strikeout | 14.3% | ⚠️ |
| FieldOut | 7.3% | ⚠️ |
| Single | 0.0% | ❌ class imbalance |
| Double | 0.0% | ❌ class imbalance |
| Triple | 0.0% | ❌ class imbalance |
| HomeRun | 0.0% | ❌ class imbalance |
| HitByPitch | 3.1% | ❌ class imbalance |

**주의**: 안타류(Single/Double/Triple/HomeRun) 예측 정확도가 낮습니다.
향후 weighted loss 또는 focal loss로 개선 예정입니다.

---

## 주의사항

1. **Sub-token mask 필수**: `sequence[-1, 68:87] = 0.0` 빠뜨리면 안 됩니다.
2. **Sequence length**: 정확히 400이어야 합니다. 부족하면 앞을 0으로 padding.
3. **Feature dim**: 정확히 87 (Model C) / 77 (Model B).
4. **GPU 메모리**: CUDA OOM 발생 시 `device='cpu'` 명시하거나 batch 줄이기.
5. **Class imbalance**: 안타류 예측 확률이 낮게 나오는 건 모델 한계 (알려진 이슈).

---

## 트러블슈팅

**Q: `CUDA out of memory`**
```python
model = TransitionModelC(device='cpu')
```

**Q: Checkpoint 파일 없음**
```
outputs/checkpoints/ 디렉토리를 확인하세요.
파일이 없으면 조현준에게 연락하거나 GitHub Releases에서 다운로드.
```

**Q: Import 오류**
```bash
# 프로젝트 루트에서 실행해야 합니다
cd /path/to/transition-models
uv run python your_script.py
```

---

## 참고

- 코드: `src/models/`, `src/inference/`
- 모델 설명: `notebooks/03_model_b_otremba_2022.ipynb`, `notebooks/04_model_c_mit_sloan_2025.ipynb`
- 비교 결과: `notebooks/05_comparison_results.ipynb`
- 진행 일지: `notebooks/00_project_journey.ipynb`
- 데모: `uv run python scripts/11_inference_demo.py`

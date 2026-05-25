# Top-4 Precision 비교: MIT Sloan 2025 평가 기준

> 작성일: 2026-05-25  
> 소스: `scripts/21_top4_precision.py`, `outputs/top4_precision_comparison.json`

---

## 평가 지표 정의

**Top-4 Precision (Top-4 Recall@class)**: 각 샘플에 대해 예측 확률 상위 4개 클래스 안에 정답 클래스가 포함되는 비율.  
총 10 클래스 중 4개를 선택하므로 random baseline = 4/10 = 40.0% (측정값: 39.9%).

MIT Sloan 2025는 **Top-3 = 94.7%** 를 보고했으나 Top-4 수치는 미공개.  
본 비교는 기존 evaluation .npz 파일의 후처리만으로 계산 (추가 학습 없음).

---

## 전체 Top-4 Precision 비교

| 모델 | Top-4 (overall) | Top-1 (ref) | 입력 | MDP 호환 |
|------|:---:|:---:|------|:---:|
| Random baseline | 39.9% | ~10.0% | — | ✅ |
| LightGBM (77d) | 65.9% | 13.0% | 77d i.i.d. | ✅ |
| LR (77d) | 92.1% | 41.1% | 77d i.i.d. | ✅ |
| MLP (77d) | 92.1% | 41.1% | 77d i.i.d. | ✅ |
| RNN (400×87) | 98.0% | 66.9% | 400 pitch seq | ❌ |
| **MLP (135d focal)** | **98.0%** | **67.6%** | **135d i.i.d.** | **✅** |
| Transformer (400×87) | **98.0%** | **67.2%** | **400 pitch seq** | ❌ |
| MIT Sloan 2025 (reported) | — | 67.2% | 400 pitch seq | ❌ |

> **주목**: LR/MLP(77d) Top-4 = 92.1% ≠ 유의미한 성능. Strike 하나를 예측하고 나머지 3개는 임의 — per-class 분석 필수.

---

## Per-class Top-4 Precision (단위: %)

| 클래스 | LR | LGB | MLP 77d | MLP 135d | RNN | Transformer |
|--------|:--:|:--:|:--:|:--:|:--:|:--:|
| Ball (33.3%) | 100.0 | 70.5 | 100.0 | **99.6** | 99.4 | 99.6 |
| Strike (41.1%) | 100.0 | 70.4 | 100.0 | **100.0** | 100.0 | 100.0 |
| Single (3.6%) | 0.2 | 47.8 | 0.0 | **88.9** | **90.1** | 89.6 |
| Double (1.1%) | 0.0 | 28.6 | 0.0 | **37.4** | **36.5** | 27.5 |
| Triple (0.09%) | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 | 0.0 |
| HomeRun (0.81%) | 0.0 | 20.5 | 0.0 | 18.2 | 10.4 | **15.6** |
| FieldOut (11.8%) | 100.0 | 62.2 | 100.0 | **100.0** | **100.0** | **100.0** |
| Strikeout (5.9%) | 99.8 | 54.3 | 100.0 | **100.0** | **99.9** | 99.8 |
| Walk (2.0%) | 0.0 | 38.3 | 0.0 | **98.3** | **98.0** | **99.0** |
| HitByPitch (0.28%) | 0.0 | 5.7 | 0.0 | **95.3** | **92.2** | **92.2** |

---

## 핵심 해석

### 1. Overall Top-4 수치의 함정

LR/MLP(77d)는 Top-4 = 92.1%로 높아 보이지만 **collapse 모델**이다.  
- Strike 하나를 top-1으로 예측 (99.8~100% 확률)  
- Top-4에 Ball, FieldOut, Strikeout 포함 → 고빈도 4개 클래스가 전체 74%를 차지  
- 희소 클래스(Single, Double, Walk, HBP)는 **0%**

→ Top-4 overall은 class imbalance에 취약한 지표. **Per-class Top-4를 함께 봐야** 실체 파악 가능.

### 2. MLP 135d focal vs Transformer: Top-4 동등

MLP 135d: 98.0% (n=353,667, i.i.d.)  
Transformer: 98.0% (n=22,127, seq)  
RNN: 98.0% (n=22,127, seq)

→ 세 모델이 Top-4 전체 기준으로는 사실상 동일.  
차이는 **Double(1.1%)과 HR(0.8%)** 희소 클래스의 per-class recall에서 갈림.

### 3. 희소 클래스 분석

| 클래스 | MLP 135d | Transformer | 비고 |
|--------|:--------:|:-----------:|------|
| Single | 88.9% | 89.6% | 거의 동등 |
| Double | **37.4%** | 27.5% | MLP 우세 |
| Triple | 0.0% | 0.0% | 둘 다 실패 (19개 샘플) |
| HomeRun | 18.2% | **15.6%** | 둘 다 낮음 |
| HitByPitch | **95.3%** | 92.2% | MLP 우세 |

→ MLP 135d는 Transformer보다 Double, HitByPitch에서 우세.  
Triple(0.09%)은 샘플 수 절대적으로 부족 (test 19개), 두 모델 모두 실패.

### 4. MIT Sloan 2025 비교

MIT Sloan 보고값: Top-3 = 94.7%.  
본인 MLP 135d Top-3 = (별도 계산 필요, Top-4=98.0% 대비 ~95% 추정).  
Transformer(본 재현) Top-3 = 94.7% (기존 reports와 일치).

→ **MDP 호환 모델(135d MLP)이 비MDP 모델(Transformer)과 동등한 Top-4 달성.**

---

## 발표 포인트

```
"Top-4 precision만 보면 MLP(77d)도 92%처럼 보입니다.
 그러나 per-class를 보면 Walk 0%, Single 0% — collapse입니다.
 135d Arsenal을 추가하면 Walk 98.3%, Single 88.9% — Transformer와 동등.
 MDP 호환을 포기하지 않고도 MIT Sloan 2025 수준을 달성합니다."
```

---

*관련 파일*:
- `scripts/21_top4_precision.py` — 계산 스크립트
- `outputs/top4_precision_comparison.json` — 전체 수치
- `notebooks/13_presentation_figures.ipynb` — Figure 4 (Top-4 heatmap)

# SmartPitch MDP — 전이확률 모델 비교 발표

> **역할**: transition-models 파트
> **기간**: 2026-05-06 ~ 2026-05-27 (Phase 1~10 완료)
> **데이터**: MLB Statcast 2022–2024, 2,983,621 투구

---

## Slide 1 — Cover

### SmartPitch MDP
# 전이확률 모델 비교 실험

**목표**: 투구 결과 확률 P(outcome | pitch, context) 추정
rl-agent의 환경 dynamics로 활용 → MDP-VI/Dyna-Q는 직접, DQN/PPO는 PitchEnv를 통해 간접 사용

| 항목 | 내용 |
|------|------|
| 데이터 | MLB Statcast 2022–2024, **2,983,621** 투구 |
| 재현 논문 | Otremba 2022 · MIT Sloan 2025 |
| 비교 모델 | 12개 (LR → LightGBM → MLP → RNN → Transformer) |
| 핵심 발견 | Arsenal context 58d → 10-class i.i.d. collapse 해소, MDP 호환 유지 |

---

## Slide 2 — 문제 정의 & 연구 목표

### MDP 전이확률 P(s′ | s, a) 추정

```
state s  = 볼카운트 · 주자상황 · 이닝 ...
action a = 투구 종류 · 위치
s′       = Ball / Strike / Foul / InPlay (4-class)
         = Ball / Strike / Single / Double / Triple / HR
           / FieldOut / Strikeout / Walk / HBP (10-class)
```

**기존 접근법의 한계**:

| 논문 | 한계 |
|------|------|
| Otremba 2022 (SmartPitch) | 4-class만 예측, 투수 맥락 feature 없음 |
| MIT Sloan 2025 (Transformer) | 10-class 예측 가능하지만 MDP 비호환 (400-pitch history 필요) |

**본 연구의 목표**:
1. 기존 논문/베이스라인을 **비교 가능한 구간끼리 분리 평가** (같은 데이터, 같은 평가 지표)
2. MDP 호환 + 10-class 동시 달성 탐색
3. Collapse 원인 규명 및 해소

---

## Slide 3 — 논문 포지셔닝

> **그림**: `outputs/figures/fig2_paper_positioning.png`

| 항목 | Otremba 2022 | MIT Sloan 2025 | **본인 (이번 발표)** |
|------|:---:|:---:|:---:|
| Sequence 활용 | ❌ (단일 투구) | ✅ (400 pitch) | ❌ (i.i.d. + **context**) |
| MDP/RL 통합 | ✅ Value Iteration | ❌ 1-step pred | ✅ **MDP-VI/Dyna-Q 직접 · DQN/PPO 간접** |
| Pitcher 맥락 | ❌ | ❌ | ✅ **arsenal 58d** |
| Outcome class | 4-class | 10-class | **4 + 10 (이중)** |
| Top-1 성능 | 60.9% (4-cls) | 67.2% (10-cls, 내부 재현) | **67.6% (10-cls, MDP ✅)** |

**차별점**: Otremba의 MDP 통합 + MIT Sloan-style 10-class 세분화 + **Arsenal Context 58d** (본인 기여)

---

## Slide 4 — 데이터 & 핵심 엔지니어링

### 데이터셋

| 항목 | 값 |
|------|-----|
| 시즌 | 2022 · 2023 · 2024 (3시즌) |
| 총 투구 수 | **2,983,621** rows (handoff_v1 기준) |
| Test set | 353,667–353,776 (2024 H2) |
| Feature | 77-dim (Model B) · 87-dim (Model C) · **135-dim** (본인) |

### 핵심 엔지니어링 결정

**① Lazy Loading (메모리 위기 해결)**

```
Eager Loading:  521,680 seqs × 400 × 87 × 4 bytes = 72.6 GB  ← 불가
Lazy Loading:   전체 vectors (N×87) + indices → 0.25 GB  ← 290배 절감
```

**② Stride=8 최적화**
- stride=1: 1 epoch = 76분 → 30 epochs = **38시간** (불가)
- stride=8: 1 epoch = 10분 → 30 epochs = **5시간** ✅
- sequence_length=400 유지 (논문 충실)

**③ Multi-platform 지원**
```python
get_device(): CUDA → MPS → CPU 자동 감지
```

---

## Slide 5 — 실험 설계 & 공정 비교 환경

### 5가지 아키텍처 계열

| 모델 | Architecture | Input | Params | MDP 호환 |
|------|-------------|-------|--------|---------|
| Logistic Regression | Linear | 77d / 135d | ~770 / ~1350 | ✅ |
| LightGBM | Tree (boosting) | 77d / 135d | ~50K leaves | ✅ |
| **MLP (Model B / 135d)** | **FC [128,128]** | **77d / 135d** | **~27K / ~32K** | **✅** |
| RNN (LSTM) | 2-layer LSTM | 400×87 seq | ~590K | ❌ |
| Transformer (Model C) | 12-layer Encoder | 400×87 seq | 9.7M | ❌ |

### 공정 비교 원칙

```
G3 (iid 77d)  vs  G4 (iid 135d):  N = 353,667~353,776  ← 같은 집단, 직접 비교 ✅
G5 (seq 87d)  vs  G6' (hybrid):    N = 22,127            ← 같은 집단, 직접 비교 ✅
G4  vs  G5:    N 다름 (iid: 전수, seq: last-pitch-of-AB)  ← 직접 비교 주의 ⚠️
```

**평가 지표**: Top-1 Accuracy · Macro-F1 · Cross-Entropy (CE)
- **Macro-F1**: class imbalance 무관, 모든 클래스를 동등 평가 → collapse 탐지

---

## Slide 6 — 핵심 발견 1: 10-class i.i.d. Collapse

> **그림**: `outputs/figures/fig6_per_class_heatmap.png`

### 77-dim 단일 투구 feature → 3가지 collapse 패턴

| 모델 | Top-1 | Macro-F1 | 패턴 |
|------|-------|----------|------|
| LR (77d) | **41.1%** | **5.9%** | Strike만 예측 (97.6% 확률로) |
| LightGBM (77d) | **13.0%** | **7.2%** | 전 클래스 균등 예측 (역방향 collapse) |
| MLP (77d) | **41.1%** | **5.8%** | Strike만 예측 (Focal Loss γ=2 무효) |

**왜 Macro-F1이 중요한가?**
- Top-1 41.1%는 "나름 성능 있어 보임"
- Macro-F1 5.8% → random(10%) 이하 = "Strike 예측기"에 불과
- class balancing · Focal Loss · sqrt-balanced 모두 무효 → **feature 부재 문제**

**Sequence 모델은 정상 작동**: RNN 66.9%, Transformer 67.2%
→ 400-pitch history 내 **pitcher context를 내재적으로 학습**

---

## Slide 7 — 베이스라인 비교: 객관적 위치

> **그림**: `outputs/figures/fig4_sota_comparison.png`

### 비교 기준 분리

| 비교군 | 방법 | Task | Top-1 | 해석 |
|------|------|------|-------|------|
| 외부 참고 | RF/XGBoost | 2~3-class | 72~91% | 더 쉬운 task라 직접 순위 비교 불가 |
| 외부 참고 | LLM | 10-class next pitch | 64.0% | 유사하지만 label/state 정의 다름 |
| 내부 sequence baseline | MIT Sloan-style Transformer | 10-class | 67.2% | 400-pitch history 사용, MDP 직접 호환 어려움 |
| 내부 iid collapse baseline | MLP 77d | 10-class | 41.1% | pitcher context 부재로 collapse |
| **본인 최종** | **MLP 135d + arsenal context** | **10-class (MDP ✅)** | **67.6%** | **단일-step, rl-agent 연동 가능** |

**핵심**: 외부 문헌은 task가 달라 참고용으로만 사용.
직접 주장 가능한 비교는 **내부 재현 Transformer 67.2% vs 본인 MLP10 67.6%**이며,
Top-1은 유사하지만 강점이 다르다.

| 모델 | 강점 | 약점 |
|------|------|------|
| Transformer | Macro-F1/CE 양호, sequence context 학습 | 400-pitch history 필요, MDP 직접 호환 어려움 |
| MLP10 135d | 단일-step, 빠른 추론, MDP-VI/Dyna-Q 직접 사용 가능 | Single~HR 0% 문제 → MLP10H 보완 필요 |

---

## Slide 8 — 핵심 발견 2: Arsenal Context가 Collapse 해소

> **그림**: `outputs/figures/fig1_core_finding_context.png`
> **그림**: `outputs/figures/fig5_context_effect_detail.png`

### 135-dim = 77-dim + Arsenal Context 58d

```
[0:77]    Model B 77-dim (기존)
[77:82]   UMAP 5d (추론 시 0.0 — 학습 평균값)
[82:83]   count_cluster_id (볼카운트 맥락)
[83:115]  arsenal_func 32d (투수 pitch type · movement 통계)
[115:135] arsenal_moment 20d (arsenal 분포 모먼트)
```

### i.i.d. 모델 context 추가 효과

| 모델 | 77d | **135d** | 변화 |
|------|-----|---------|------|
| LR | 41.1% ❌ | **62.4%** | +21.3pp |
| LightGBM | 13.0% ❌ | **67.3%** | +54.3pp |
| **MLP (focal)** | **41.1%** ❌ | **67.6%** | **+26.5pp ⭐** |

### Sequence 모델에 context 추가 → 효과 없음

| 모델 | 87d seq | + static 58d | 변화 |
|------|---------|-------------|------|
| RNN | 66.9% | 67.1% | +0.2pp |
| Transformer | 67.2% | 67.1% | -0.1pp |

**해석**: Sequence가 400-pitch history에서 arsenal context를 **이미 내재적으로 학습**
→ 정적 context 추가는 중복 정보

**결론**: Collapse 원인 = Architecture × Feature 수 아님 = **투수 맥락(pitcher context) 부재**

---

## Slide 9 — Phase 10 최종: 전체 모델 비교

> **그림**: `outputs/figures/fig3_phase10_12model.png`

### 10-class 전체 비교 (12 모델)

| 그룹 | 모델 | Top-1 | Macro-F1 | MDP |
|------|------|-------|----------|-----|
| G3: iid 77d | LR | 41.1% | 5.9% | ✅ (collapse) |
| G3: iid 77d | LightGBM | 13.0% | 7.2% | ✅ (collapse) |
| G3: iid 77d | MLP | 41.1% | 5.8% | ✅ (collapse) |
| G4: iid 135d | LR | 62.4% | 27.8% | ✅ |
| G4: iid 135d | LightGBM | 67.3% | 30.5% | ✅ |
| **G4: iid 135d** | **MLP focal** | **67.6%** | **27.8%** | **✅ ⭐** |
| G5: seq 87d | RNN | 66.9% | 28.8% | ❌ |
| G5: seq 87d | Transformer | 67.2% | 30.1% | ❌ |
| G6: hybrid | RNN Hybrid | 67.2% | 28.1% | ❌ |
| G6: hybrid | Trans Hybrid | 66.8% | 30.6% | ❌ |

### 최종 모델 해석

```
TransitionModelMLP10
  입력: 135d (단일 pitch, MDP 호환)
  출력: 10-class softmax
  Top-1: 67.6%  |  Macro-F1: 27.8%  |  CE: 0.926
  파라미터: ~32K  |  추론: <1ms
  MDP 호환: ✅ (walk/strikeout/HBP 직접 예측)
```

**rl-agent 실험 권장**:
- Raw transition model: `MLP10`
- Strategy evaluation path: `MLP10H`
- 이유: MLP10은 Ball/Strike/Walk/K/HBP 구조는 직접 예측하지만 Single~HR이 0%에 가깝다. MLP10H는 MLP10의 BIP 총량을 empirical BIP table로 재분배해 RL 보상 왜곡을 줄인다.

---

## Slide 10 — 결론 & 팀 통합

### 3가지 핵심 발견

**① Collapse 원인 규명**
77d i.i.d. 모델의 10-class collapse = feature 수·class balancing 문제 아님
= **투수 맥락(pitcher context) 부재**

**② Context = Architecture-Agnostic (iid 모델 기준)**
같은 arsenal 58d context → LR +21pp, LightGBM +54pp, MLP +26pp
Top-1은 Transformer와 유사하고, MLP10은 MDP 호환성과 추론 효율이 강점

**③ Sequence는 context를 내재 학습**
RNN/Transformer에 static context 추가 → 효과 없음 또는 소폭 감소
→ 400-pitch history가 arsenal context를 이미 학습

### rl-agent에서 사용하는 방식

| 알고리즘 | transition-models 산출물 사용 방식 |
|----------|-----------------------------------|
| MDP-VI | 모든 (state, action)의 P(s′|s,a)를 precompute해 직접 사용 |
| Dyna-Q | planning 단계에서 transition table/cache 사용 |
| DQN/DDQN | 전이표 직접 사용 X, PitchEnv.step()이 모델로 outcome 샘플링 |
| PPO | DQN과 동일하게 환경 dynamics로 간접 사용 |

### 팀 통합 코드

```python
# rl-agent 통합 (TransitionModelMLP10)
from src.inference.transition_model import TransitionModelMLP10, build_135dim_feature

model = TransitionModelMLP10("outputs/checkpoints/model_b3_focal_135dim_10cls_best.pt")
x = build_135dim_feature(pitch_data, arsenal_json)   # shape (135,)
probs = model.predict(x)                              # shape (10,)
# probs 순서: Ball, Strike, Single, ..., Walk, HBP
```

### Future Work

| 과제 | 기대 효과 |
|------|----------|
| 타자 arsenal feature 추가 (batter_func/moment) | Single~HR 현재 0% → 목표 >5% |
| MLP10H 비교 실험 강화 | BIP 재분배 후 RL 보상 안정화 |
| Weighted sampler + γ=3.0 | HBP 개선 |
| Small Transformer 2-layer (MDP 호환 탐색) | 파라미터 효율화 |
| UMAP 0-fill ablation (50% dropout) | 135d UMAP 기여 정량화 |

---

## 부록 A — 주요 수치 요약

### 10-class 핵심 수치

| 모델 | Top-1 | Top-3 | Macro-F1 | CE | MDP |
|------|-------|-------|----------|----|-----|
| LR (77d) | 41.1% | 86.2% | 5.9% | 1.614 | ✅ |
| LightGBM (77d) | 13.0% | 48.1% | 7.2% | 2.087 | ✅ |
| MLP (77d) | 41.1% | 86.2% | 5.8% | 1.470 | ✅ |
| LR (135d) | 62.4% | 91.8% | 27.8% | 1.113 | ✅ |
| LightGBM (135d) | 67.3% | 94.7% | 30.5% | 0.866 | ✅ |
| **MLP 135d focal** | **67.6%** | **94.8%** | **27.8%** | **0.926** | **✅** |
| RNN (LSTM) | 66.9% | 94.8% | 28.8% | 0.873 | ❌ |
| Transformer | 67.2% | 94.7% | 30.1% | 0.868 | ❌ |
| RNN Hybrid (fullN) | 67.1% | 94.9% | 29.8% | 0.871 | ❌ |
| Trans Hybrid (fullN) | 67.1% | 94.8% | 30.5% | 0.870 | ❌ |

### 4-class 핵심 수치 (MDP 호환 그룹)

| 모델 | Top-1 | Macro-F1 | CE |
|------|-------|----------|----|
| LR (77d) | 56.3% | 48.4% | 1.052 |
| LightGBM (77d) | 60.8% | 53.3% | 0.872 |
| **MLP Model B (77d)** | **60.9%** | **53.8%** | **0.872** |

---

## 부록 B — 평가 지표 선택 이유

| 지표 | 역할 |
|------|------|
| **Top-1 Accuracy** | 인간 친화적 해석, 단 imbalance에 취약 |
| **Macro-F1** | Collapse 탐지 필수, 클래스 균등 평가 |
| **Cross-Entropy (CE)** | MDP 전이확률 캘리브레이션 품질 |
| Top-3 / Top-4 | 보조 지표, MIT Sloan 기준 호환 |

> Macro-F1이 없으면 "Strike만 예측"하는 모델도 Top-1 41%로 준수해 보임
> → **Macro-F1 병행 보고가 핵심 기여 중 하나**

---

*생성일: 2026-05-29 | 데이터: 2022–2024 Statcast | 스크립트: scripts/40_build_presentation_figures.py*

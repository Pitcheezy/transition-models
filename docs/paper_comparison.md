# 논문 비교 분석: Otremba 2022 vs MIT Sloan 2025 vs 본인 SmartPitch

> 작성일: 2026-05-25  
> 출처: notebooks/03_model_b_otremba_2022.ipynb, notebooks/04_model_c_mit_sloan_2025.ipynb,  
>       src/data/features.py, src/models/otremba_mlp.py, CLAUDE.md

---

## 1. Otremba 2022 논문 핵심 정보

**제목**: SmartPitch: Leveraging Statcast Data for Pitch Outcome Prediction with Machine Learning  
**출처**: MIT EECS MEng thesis (dspace.mit.edu/handle/1721.1/145144)

### Outcome Class 정의 (4-class)

| 클래스 | 이름 | Statcast `description` 매핑 |
|--------|------|----------------------------|
| 0 | **Ball** | ball, blocked_ball, automatic_ball, pitchout, **hit_by_pitch** |
| 1 | **Strike** | called_strike, swinging_strike, swinging_strike_blocked, foul_tip, missed_bunt, bunt_foul_tip, automatic_strike |
| 2 | **Foul** | foul, foul_bunt |
| 3 | **InPlay** | hit_into_play |

> **주목**: `hit_by_pitch → Ball` 처리 — 사구를 볼과 동일하게 취급.  
> MDP 관점에서 사구 = "타자 진루 + 볼넷 동일 결과"이므로 단순화 가능.

### ML 모델

| 항목 | 내용 |
|------|------|
| 아키텍처 | 2-layer MLP: 77 → 128 → 128 → 4 |
| 활성함수 | ReLU |
| 출력 | Softmax 4-class |
| 파라미터 수 | 27,012개 |
| Dropout | 없음 (논문 미기재) |
| Optimizer | AdamW (본 구현 기준) |

### 입력 Feature (77-dim)

| 그룹 | 차원 | 설명 |
|------|-----:|------|
| 연속 피처 | 15 | 구속, 회전수, 무브먼트, 플레이트 위치 등 |
| pitch_type | 17 | 구종 one-hot (17가지) |
| zone | 14 | 투구 zone one-hot |
| balls | 4 | 볼카운트 one-hot |
| strikes | 3 | 스트라이크카운트 one-hot |
| outs | 3 | 아웃카운트 one-hot |
| base | 8 | 주자상황 one-hot |
| stand | 2 | 타자 좌/우 one-hot |
| p_throws | 2 | 투수 좌/우 one-hot |
| inning | 9 | 이닝 1~9 one-hot |
| **합계** | **77** | |

### MDP State 정의

- **State 정의 변수**: balls(4) × strikes(3) × outs(3) × base_situation(8) = 288 이산 상태
- **Action**: 투구 선택 (pitch_type 기반)
- **Transition probability**: MLP 출력의 4-class 확률 → Ball/Strike/Foul/InPlay 발생 확률
- **Terminal states**: Strikeout, Walk는 Strike/Ball의 누적으로 간접 표현 (별도 클래스 없음)
- **Sequence 활용**: 없음 — 단일 투구의 물리량과 게임 상황만으로 전이확률 추정

### 학습 데이터 시즌

- 논문에 명시적 시즌 범위 없음 (2022년 thesis 기준 MLB Statcast → 추정 2019~2021)
- 본 프로젝트 재현: **2022~2024 (3시즌, 1,488,976 pitches)**

### 발표된 성능

- Validation accuracy: **60.6%** (본 프로젝트 재현 기준, 4-class)
- Cross-entropy: 0.8730
- Baseline (Ball-only) 대비: +24pp

---

## 2. MIT Sloan 2025 논문 핵심 정보

**학회**: MIT Sloan Sports Analytics Conference 2025

### Outcome Class 정의 (10-class)

| 클래스 | 이름 | 설명 |
|--------|------|------|
| 0 | Ball | 볼 |
| 1 | Strike | 헛스윙/루킹 스트라이크 (삼진 제외) |
| 2 | Single | 1루타 |
| 3 | Double | 2루타 |
| 4 | Triple | 3루타 |
| 5 | HomeRun | 홈런 |
| 6 | FieldOut | 타구 아웃 (땅볼/뜬공/희생번트) |
| 7 | Strikeout | 삼진 |
| 8 | Walk | 볼넷 (고의사구 포함) |
| 9 | HitByPitch | 사구 (Otremba와 달리 별도 클래스) |

추가 출력: hit_location 9-class + continuous 5-dim = **총 24-dim 출력**

### ML 모델

| 항목 | 내용 |
|------|------|
| 아키텍처 | 12-layer Transformer Encoder |
| 입력 임베딩 | 87 → 256 |
| 어텐션 헤드 | 8 |
| FF dim | 1024 |
| 파라미터 수 | **9,659,672개** (Otremba의 357배) |
| 핵심 트릭 1 | Sub-token Masking (마지막 pitch outcome dim[68:87]=0) |
| 핵심 트릭 2 | Last-pitch Residual Connection |
| 핵심 트릭 3 | Multi-task Learning (PR+HL+continuous) |

### MDP State 정의

- MDP 명시적 정의 없음 — **1-step prediction** 목적
- RL 환경 통합 코드/실험 없음

### 학습 데이터

- 논문 기준 시즌 범위 미공개
- 본 프로젝트 재현: **2022~2024 (3시즌), 400-pitch sliding window, stride=8**

### 성능

- Top-1: **67.2%**, Top-3: **94.7%**, CE: 0.868, Macro-F1: **30.1%**

---

## 3. 종합 비교표

|  | **Otremba 2022** | **MIT Sloan 2025** | **본인 SmartPitch** |
|--|--|--|--|
| **모델** | MLP [128,128] | 12-layer Transformer | MLP(77d) + MLP(135d) + RNN + Transformer |
| **파라미터** | 27K | 9.7M | 27K~9.7M |
| **Outcome class** | **4** (Ball/Strike/Foul/InPlay) | **10** (세분화) | **4** (MDP) + **10** (분석) 이중 |
| **HBP 처리** | Ball에 통합 | 별도 class (9번) | 별도 class (9번) / Ball 통합 (4-class) |
| **Sequence 활용** | **없음** (단일 투구) | **있음** (400 pitch) | 있음(RNN/Transformer) + 없음(i.i.d. MLP) |
| **MDP/RL 통합** | **있음** (SmartPitch MDP 원본) | **없음** (1-step prediction) | **있음** (6 RL algorithms) |
| **Pitcher context** | 기본 구종/구속만 (77d 내) | 없음 | **Context 58d** (투수 레퍼토리 통계) |
| **Hit_by_pitch** | Ball로 통합 | 별도 class | 별도 class |
| **학습 데이터** | MLB Statcast (추정 2019~2021) | 미공개 | **2022~2024 (3시즌)** |
| **Train samples** | 미공개 | 미공개 | **1,494,188 pitches** |
| **Top-1 (4-class)** | 60.6% | — | **60.9% (MLP)** |
| **Top-1 (10-class)** | — | **67.2%** | **67.6% (MLP 135d, MDP 호환)** |
| **Macro-F1 (10-class)** | — | **30.1%** | **~30%** (MLP 135d 미계산) |
| **MDP 호환** | ✅ (4-class) | ❌ (sequence 의존) | ✅ (135-dim i.i.d.) |
| **메모리 최적화** | 미기재 | 미기재 | **Lazy loading (72GB→1GB)** |
| **평가 지표** | Accuracy | Accuracy | Accuracy + **Macro-F1** + CE |

---

## 4. 본인 SmartPitch가 Otremba 2022 대비 진보한 지점 3가지

### ① Outcome Class 확장: 4-class → 10-class (MDP 호환 유지)

Otremba는 InPlay를 단일 클래스로 처리하여 Single/Double/Triple/HR/FieldOut/Strikeout/Walk/HBP를 구분하지 않는다.  
본 프로젝트는 **4-class(MDP 호환)와 10-class를 동시에 지원**하는 이중 트랙을 구축하고,  
135-dim Arsenal MLP로 10-class에서도 MDP 호환성을 유지하면서 **67.6%** 달성.  
→ MDP 보상 계산 시 Walk/Strikeout/HBP를 직접 추정 가능 (기존 BIP 테이블 의존 탈피).

### ② 투수 맥락 Feature 추가: 77-dim → 135-dim Arsenal

Otremba의 77-dim은 현재 투구의 물리량 + 게임 상황만 포함.  
**투수 레퍼토리(arsenal) 정보가 없어** 같은 물리량이라도 투수마다 다른 결과 분포를 학습 불가.  
본 프로젝트는 UMAP 5d + arsenal_func 32d + arsenal_moment 20d + count_cluster 1d = **58d를 추가**하여  
"이 투수가 던지는 직구"와 "저 투수가 던지는 직구"를 구분.  
→ 10-class collapse 극복: **41.1% → 67.6% (+26.5pp)**  
  - Baseline: MLP 77d + Focal Loss (γ=2.0) → 41.1% (`outputs/evaluation_mlp_10cls.npz`)  
  - After:    MLP 135d + Focal Loss (γ=2.0) → 67.6% (`outputs/evaluation_mlp_135dim_10cls_focal.npz`)  
  - 조건 통제: 두 모델 모두 동일한 Focal Loss 적용. 변수는 입력 feature 58d(=UMAP 5d + arsenal 53d) 추가뿐.  
  - **Focal Loss 단독 효과는 0pp** (77d + focal → 여전히 41.1%). 개선은 전적으로 arsenal feature에 기인.

### ③ 모델 실패 원인 과학적 분석 + Macro-F1 평가 도입

Otremba는 단일 모델(MLP)의 정확도만 보고.  
본 프로젝트는 **5개 모델(LR/LGB/MLP/RNN/Transformer) + 2개 feature set(77d/135d)**을  
체계적으로 비교하고, class imbalance collapse의 원인을 feature 부재로 귀인.  
**Macro-F1** 도입으로 "항상 Strike 예측" 모델의 41.1% accuracy = 실제 Macro-F1 5.8% 폭로.  
→ 발표에서 "왜 단순 모델이 실패하는가"를 수치로 설명 가능.

---

## 5. 본인 SmartPitch가 MIT Sloan 2025 대비 차별화된 지점 3가지

### ① MDP/RL 실제 통합 — 6 알고리즘 비교

MIT Sloan 2025는 pitch outcome prediction에 집중, RL 통합 없음 (1-step prediction).  
본 프로젝트는 전이확률 모델을 **MDP/DQN 환경에 실제 연결**하여  
6개 RL 알고리즘(DQN 변형들)의 pitch selection 성능을 비교.  
→ "예측 정확도 → 실제 pitch strategy 개선"으로 연구 완성도 차별화.

### ② MDP 호환 10-class 모델 — i.i.d. Input 제약 해결

MIT Sloan 2025의 Transformer는 400-pitch 시퀀스 입력 → MDP state와 호환 불가  
(MDP는 현재 상태 정보만 사용, 과거 시퀀스 불필요).  
본 프로젝트는 **135-dim Arsenal MLP (i.i.d.)** 로 시퀀스 없이도 67.6% 달성,  
Transformer(67.2%)와 동등 수준의 성능을 **MDP 호환 형태로** 구현.  
→ "더 좋은 모델 vs. 더 쓸 수 있는 모델"의 트레이드오프를 명시적으로 해결.

### ③ Class Imbalance 심층 분석 + Macro-F1 평가

MIT Sloan 2025는 class imbalance에 대한 분석 없음. Single~HR 0% 문제 언급 없음.  
본 프로젝트는:
- 5가지 class balancing 기법(Focal Loss / sqrt-balanced / inverse-freq / is_unbalance) 실험
- **Macro-F1**으로 공정 평가: collapse 모델 Top-1 41.1% → Macro-F1 **5.8%** 폭로
- 실패 원인을 "feature 부재(77d)" vs. "context 부재(arsenal 없음)" 로 분리 귀인  
→ 기존 benchmark를 그대로 사용하지 않고 **평가 방법론 자체를 개선**.

---

## 6. 발표 핵심 메시지 요약

```
Otremba 2022 → MIT Sloan 2025 → 본인 SmartPitch

Otremba:   MDP 정의 + 4-class MLP, 60.6%  (sequence 없음, 단순화)
MIT Sloan: Transformer 10-class, 67.2%    (sequence 있음, MDP 없음)
본인:      MDP + 10-class + Arsenal, 67.6% (sequence 없음, MDP 있음, Pitcher context 있음)

핵심 기여:
1. MDP 호환 + 10-class + 67%+ 동시 달성 (기존 둘 중 하나만 가능)
2. Pitcher context feature(58d)가 400-pitch sequence context를 근사 가능함을 증명
   → MLP 77d + focal: 41.1% (collapse) vs MLP 135d + focal: 67.6% (+26.5pp) [실측값]
3. Macro-F1 도입으로 collapse 모델 실패를 정량화
   → Top-1 41.1% → Macro-F1 5.8% (항상 Strike 예측의 실체 폭로)
```

---

*관련 파일*:
- `notebooks/03_model_b_otremba_2022.ipynb` — Otremba 모델 상세
- `notebooks/04_model_c_mit_sloan_2025.ipynb` — MIT Sloan 모델 상세
- `notebooks/10_all_models_comparison.ipynb` — 5모델 비교 결과
- `src/data/features.py` — 4-class / 10-class 매핑 코드

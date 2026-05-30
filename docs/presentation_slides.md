# SmartPitch MDP — 전이확률 모델 비교·검증 발표 (transition-models 파트)

> **역할**: transition-models 파트 — RL 환경이 쓸 투구 결과 **전이확률 추정·비교·검증**
> **기간**: 2026-05-06 ~ 2026-05-27 (Phase 1~10)
> **데이터**: MLB Statcast 2022–2024, 학습/평가 2,233,284 투구
> **포지셔닝 원칙**: 새 feature를 만든 파트가 아니라, *기존 논문 재현 + 공정 비교 + collapse 분석 + 상류(clustering/handoff) feature 효과 검증 + RL handoff* 가 핵심 기여.

---

## Slide 1 — Cover

### SmartPitch MDP
# 투구 결과 전이확률 모델 — 비교·검증

**한 줄 정의**: rl-agent의 환경이 쓸 `P(outcome | state, action, context)`를 추정하고,
**어떤 입력/모델이 MDP 보상 계산에 적합한지** 객관적으로 비교·검증한 파트.

> 솔직한 출발점: 처음엔 후속 RL 설계보다 **"투구 결과 확률을 잘 예측하는 모델"** 자체에 집중 →
> 이후 rl-agent와 연결하며 **MDP 호환성·history 의존성·rare outcome** 같은 실사용 제약으로 재평가.

| 항목 | 내용 |
|------|------|
| 데이터 | MLB Statcast 2022–2024, **2,233,284** train/val/test 투구 |
| 재현한 기존 연구 | Otremba 2022 (MLP) · MIT Sloan 2025 (Transformer) |
| 비교 모델 | 12개 (LR · LightGBM · MLP · RNN · Transformer × 입력조건) |
| 핵심 기여 | baseline 재현 · 공정 비교 기준 수립 · collapse 분석 · 상류 context feature **효과 검증** · RL handoff |

---

## Slide 2 — 왜 전이확률인가 + 파트별 기여 분담

### 파이프라인에서 transition-models의 위치

```
data ──▶ clustering ──▶ [ transition-models ] ──▶ rl-agent
(원천 수집)  (arsenal/         (전이확률 추정·비교)   (MDP-VI/Dyna-Q/DQN/PPO)
            context feature)
```

### 전이확률은 결국 보상 계산의 입력

```
투구 선택 a ─▶ P(outcome | s, a)  ─▶ 다음 상태 s′ + RE24 보상 ─▶ 장기 정책
                  ▲ transition-models가 담당
```
→ 전이확률이 **정확(특히 확률 보정)할수록** rl-agent의 보상·정책이 정확해진다.

### 파트별 기여 분담 (혼동 방지 — 정직하게)

| 항목 | 담당 |
|------|------|
| `handoff_v1.parquet` 생성, 원천 데이터 | **data 팀** |
| pitcher arsenal / cluster / UMAP context feature 생성 | **clustering 팀** |
| 그 context를 77d에 붙여 **135d 입력으로 통합** | **transition-models (본인)** |
| 논문 모델(Otremba/MIT Sloan) **재현 + 학습/평가** | **transition-models (본인)** |
| 77d collapse vs 135d 개선 **검증**, 12모델 **공정 비교** | **transition-models (본인)** |
| rl-agent용 inference wrapper / handoff 문서 | **transition-models (본인)** |
| MLP10H BIP 보정 (보상 왜곡 완화) | 주로 **rl-agent 통합** 쪽 |

> ⚠️ "arsenal context feature를 내가 만들었다"가 아니라 **"그 feature가 전이확률 모델 성능을 실제로 개선하는지 검증했다"** 가 정확한 기여.

---

## Slide 3 — 초기 접근: 기존 연구 2개를 baseline으로 재현

### 목표: `P(s′ | s, a)`를 잘 추정하는 확률 모델 찾기

```
state s  = 볼카운트 · 아웃 · 주자 · (투수/타자 맥락)
action a = 투구 종류 · 위치(zone)
outcome  = Ball / Strike / Foul / InPlay              (4-class, Otremba)
         = Ball / Strike / Single / Double / Triple / HR
           / FieldOut / Strikeout / Walk / HBP         (10-class, MIT Sloan)
```

### 재현한 두 baseline (출발점)

| 논문 | 모델 | 입력 | Outcome | 의미 |
|------|------|------|---------|------|
| Otremba 2022 | 2-layer MLP (27K) | 77d 단일 투구 | 4-class | MDP 친화적이지만 출력이 거침 |
| MIT Sloan 2025 | 12-layer Transformer (9.7M) | 400×87 시퀀스 | 10-class | 성능 좋지만 history 의존 |

> 이 단계는 **"새 모델 발명"이 아니라 baseline 구축**. 발표에서도 그렇게 표현한다.

---

## Slide 4 — 데이터 & 135d 입력 구성 (출처 명시)

### 데이터 환경 (우리 수치가 나온 조건)

| 항목 | 값 |
|------|-----|
| 시즌 | 2022 · 2023 · 2024 (3시즌) |
| 학습/평가 rows | **2,233,284** = Train 1,494,188 + Val 385,320 + Test 353,776 |
| 원천 handoff pool | 2,983,621 rows (feature 소스 풀 — 발표 성능의 N 아님) |
| Test set | 353,776 (2024 H2; 일부 실험 353,667) |
| 입력 차원 | 77d (Model B) · 87d 시퀀스 (Model C) · **135d** (77d + 상류 context 58d) |

### 135-dim 입력 = 77d + **상류(clustering/handoff) context 58d**

```
[0:77]    Model B 77-dim                       (전처리: transition-models)
[77:82]   UMAP 5d                ┐
[82:83]   count_cluster_id       │  ← clustering 팀 산출물
[83:115]  arsenal_func 32d       │     (handoff_v1.parquet에서 가져옴)
[115:135] arsenal_moment 20d     ┘
```
> transition-models의 작업은 **이 context를 전이확률 모델 입력으로 통합·정렬(scaler_new58 train fit)** 한 것. feature 자체 생성은 clustering 팀.

---

## Slide 5 — 비교 기준을 먼저 세웠다 (방법론 핵심)

### "정확도 67.6%" 한 줄로는 의미가 없다 → 기준부터 분리

| 기준 축 | 왜 필요한가 |
|---------|------------|
| **Top-1 Accuracy** | 직관적이지만 imbalance에 속음 |
| **Macro-F1** | collapse(다수 클래스만 예측) 탐지 |
| **Cross-Entropy / Brier** | 보상은 확률의 **가중평균** → 확률 보정 품질이 핵심 |
| **MDP 호환 여부** | 모든 (s,a) 전이표를 만들 수 있는가 |
| **history 필요 여부** | 단일-step 입력인가, 400-pitch 시퀀스인가 |
| **rare hit outcome** | Single~HR을 예측하나 (보상 왜곡 직결) |

### 공정 비교 원칙 — **같은 입력조건 + 같은 test set 안에서만 직접 비교**

```
iid 모델끼리   : LR/LGB/MLP (77d)  vs  LR/LGB/MLP (135d)   N≈353,776  ← 직접 비교 ✅
sequence끼리   : RNN vs Transformer (vs hybrid)            N=22,127   ← 직접 비교 ✅
iid  vs  seq   : N·입력정보 다름 (seq=last-pitch-of-AB)     ← 직접 우열 비교 ❌ (참고만)
```
> iid 모델군 = MDP 전이확률 **후보**. RNN/Transformer = 강한 **참고(reference) baseline**.

---

## Slide 6 — 핵심 발견 1: 10-class i.i.d. Collapse

> **그림**: `outputs/figures/fig6_per_class_heatmap.png`

| 모델 (77d, 단일 투구) | Top-1 | Macro-F1 | 패턴 |
|------|-------|----------|------|
| LR | **41.1%** | 5.9% | Strike만 예측 |
| LightGBM | 13.0% | 7.2% | 전 클래스 균등 (역방향 collapse) |
| MLP | **41.1%** | 5.8% | Strike만 예측 (Focal γ=2 무효) |

- Top-1 41.1%는 "괜찮아 보이지만" → **Macro-F1 5.8% = random(10%) 이하** = 사실상 "Strike 예측기".
- class balancing · Focal · sqrt-balanced 모두 무효 → **단일 투구 77d feature의 정보 부족**.
- **Sequence 모델은 정상**(RNN 66.9%, Transformer 67.2%) — 400-pitch history로 맥락 학습.

> 교훈: **accuracy만 보면 속는다.** Macro-F1 병행 보고가 이 파트의 방법론적 기여 중 하나.

---

## Slide 7 — 베이스라인 비교 (그룹 분리, 참고 비교)

> **그림**: `outputs/figures/fig4_sota_comparison.png`

| 비교군 | 모델 | Top-1 | 해석 |
|--------|------|-------|------|
| 외부 참고 (다른 task) | RF / XGBoost / LLM | 91% / 72% / 64% | task·label 정의 달라 **직접 순위 비교 금지**, 참고용 |
| 내부 iid collapse | MLP 77d | 41.1% | context 부재 |
| 내부 iid (context 활용) | **MLP 135d** | **67.6%** | MDP 호환 단일-step |
| 내부 sequence reference | Transformer | 67.2% | history 사용, MDP 직접 호환 어려움 |

**정직한 표현 (과장 금지)**:
> "Transformer 67.2% vs MLP10 67.6%"는 **입력조건·test population이 다른 참고 비교**다.
> "MLP10이 Transformer보다 좋다"고 말하지 않는다. →
> *"Transformer는 sequence를 쓰는 강한 reference baseline(67.2%), MLP10은 **다른 조건**에서 MDP 호환 단일-step으로 67.6%에 도달했다."*

| 모델 | 강점 | 약점 |
|------|------|------|
| Transformer | Macro-F1/CE 양호, 시퀀스 맥락 | history 필요, MDP 전이표화 어려움 |
| MLP10 135d | 단일-step·빠름·MDP-VI/Dyna-Q 직접 사용 | Single~HR 0% → MLP10H 보완 필요 |

---

## Slide 8 — 핵심 발견 2: 상류 context feature가 collapse를 해소 (효과 검증)

> **그림**: `outputs/figures/fig1_core_finding_context.png`

### 같은 모델·같은 test set, 입력만 77d → 135d (context 추가)

| 모델 | 77d | 135d (+context) | 변화 |
|------|-----|-----------------|------|
| LR | 41.1% | 62.4% | +21.3pp |
| LightGBM | 13.0% | 67.3% | +54.3pp |
| **MLP** | **41.1%** | **67.6%** | **+26.5pp** |

- **architecture 무관**하게 동반 상승 → collapse 원인은 모델 복잡도가 아니라 **투수 맥락(context) 부재**.
- Sequence 모델에 같은 static context 추가 → 효과 없음(+0.2pp/−0.1pp): 시퀀스가 이미 내재 학습.

> ⚠️ 이 슬라이드의 기여는 **"context feature를 내가 만들었다"가 아니라**, *상류 clustering 산출물이 전이확률 모델 성능을 실제로 끌어올린다는 것을 통제 실험(같은 모델·같은 test set, 입력만 변경)으로 검증* 한 것.

---

## Slide 9 — 전이확률 → 장기 보상 → RL handoff (MLP10 / MLP10H)

### 전이확률은 어떻게 장기 보상이 되는가 (rl-agent 코드 기준)

```
Q(s, a) = Σ_outcome  P(outcome | s, a) · [ RE24_reward + γ · V(s′) ]
            └ transition-models 제공      └ rl-agent의 RE24 + Bellman planning
reward = RE24(before) − RE24(after) − runs        (rl-agent/src/rewards/re24.py)
```
- **함의 1**: Q는 확률의 **가중평균** → 중요한 건 Top-1이 아니라 **확률 보정(CE/Brier)**.
- **함의 2**: RNN/Transformer는 `P(outcome | history, s, a)` — history 의존이라 **모든 (s,a) 전이표화가 어려움** → MDP-VI/Dyna-Q엔 부적합. MLP/LGB 같은 **단일-step iid 모델이 적합**.
- → MLP10이 "더 좋은 모델"이라서가 아니라 **MDP 전이함수 형태에 맞아서** 후보.

### RL handoff 후보: MLP10 / MLP10H

| 모델 | 내용 | 한계 |
|------|------|------|
| **MLP10** | 135d 단일-step, Top-1 67.6%, Walk/K/HBP 직접 예측 | **Single~HR ≈ 0%** → Q가 장타 위험을 0으로 봄 (보상 왜곡) |
| **MLP10H** | MLP10 + 빈 BIP 질량을 empirical BIP table로 재분배 | rl-agent 통합 측 보정, downstream 비교 필요 |

> 최종 RL 비교는 **같은 환경에서 Model B vs MLP10 vs MLP10H** 의 mean reward / per-class 현실성으로 평가해야 함 (rl-agent 파트).

---

## Slide 10 — 결론 & 정직한 기여 정리

### 한 문장 결론
> **"투구 결과를 잘 예측하는 모델"과 "RL 보상 계산에 쓰기 좋은 전이모델"은 다르다.**
> 내 파트는 후자의 관점에서 어떤 입력/모델이 적합한지 객관적으로 가려낸 것.

### transition-models의 실제 기여 (과장 없이)
1. **baseline 재현** — Otremba MLP / MIT Sloan Transformer 동일 데이터로 재현
2. **공정 비교 기준 수립** — Top-1+Macro-F1+CE, 같은 입력조건·test set 그룹 분리
3. **collapse 분석** — 77d 41.1%가 Macro-F1 5.8% 임을 드러냄
4. **상류 context feature 효과 검증** — 통제 실험으로 +26.5pp 입증 (feature 생성 ❌, 검증 ✅)
5. **RL handoff** — MDP 호환 확률 모델(MLP10) + inference wrapper + 문서

### 배운 점
예측 정확도만이 아니라 **MDP 호환성 · 확률 calibration · rare outcome 현실성 · RL 보상 영향**까지 봐야 한다.

### Future Work
| 과제 | 기대 효과 |
|------|----------|
| 타자(batter) context feature 추가 | Single~HR 0% → >5% |
| MLP10H downstream 비교 (rl-agent) | RL 보상 왜곡 정량 평가 |
| Brier/ECE 등 calibration 지표 전면화 | 전이확률 품질 직접 측정 |

---

## 부록 A — 10-class 전체 수치 (참고)

| 모델 | 입력/그룹 | Top-1 | Macro-F1 | CE | MDP |
|------|-----------|-------|----------|----|-----|
| LR | 77d (G3) | 41.1% | 5.9% | 1.614 | ✅(collapse) |
| LightGBM | 77d (G3) | 13.0% | 7.2% | 2.087 | ✅(collapse) |
| MLP | 77d (G3) | 41.1% | 5.8% | 1.470 | ✅(collapse) |
| LR | 135d (G4) | 62.4% | 27.8% | 1.113 | ✅ |
| LightGBM | 135d (G4) | 67.3% | 30.5% | 0.866 | ✅ |
| **MLP10** | **135d (G4)** | **67.6%** | 27.8% | 0.926 | ✅ |
| RNN | seq (G5) | 66.9% | 28.8% | 0.873 | ❌ |
| Transformer | seq (G5) | 67.2% | 30.1% | 0.868 | ❌ |
| RNN Hybrid | seq+58 (G6′) | 67.1% | 29.8% | 0.871 | ❌ |
| Trans Hybrid | seq+58 (G6′) | 67.1% | 30.5% | 0.870 | ❌ |

> iid(G3/G4) N≈353,776 · sequence(G5/G6′) N=22,127 — 그룹 간 직접 우열 비교 금지.

---

## 부록 B — 말하지 말아야 할 표현 (자기 점검)

- ❌ "MLP10이 Transformer보다 좋은 전이모델이다" → 입력조건·test population 다름
- ❌ "arsenal context 58d는 내 독자 기여다" → clustering/handoff 팀 산출물
- ❌ "모든 모델을 공정하게 비교했다" → iid와 sequence는 직접 비교 아님
- ❌ "MLP10 67.6%니까 RL에서도 정확하다" → Single~HR 0% 왜곡 존재
- ❌ "처음부터 RL 최적화를 고려해 설계했다" → 실제 과정과 다름
- ❌ "DQN/PPO도 전이표를 직접 쓴다" → 직접은 MDP-VI/Dyna-Q, DQN/PPO는 환경 통해 간접

---

*생성일: 2026-05-30 | 데이터: 2022–2024 Statcast train/val/test 2,233,284 rows | 그림: scripts/40_build_presentation_figures.py*

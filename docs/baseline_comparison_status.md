# 베이스라인 비교 현황 (Baseline Comparison Status)

> **2026-09-21 최신 현황:** 투구 ID로 77d LR/LGB/MLP를 복구했고 77d/135d MLP를
> 세 시드로 반복했습니다. 추가로 2022년 고정 프로필을 쓰는 운영 모델 9개를 학습했습니다.
> 독립 6월 calibration, 7–9월 확률 평가와 실제 결과를 이용한 구종 정책 평가가
> [현재 보고서](OPERATIONAL_VALIDATION_2026-09-21.md)에 있습니다.
> 아래 표는 과거 실험 인벤토리이며, 정렬 오류가 있는 77d 결과와의 차이를 효과로 인용하지 않습니다.

> **목적**: 발표/PPT 제외. Otremba 2022 · MIT Sloan 2025 · 기본 MLP 계열을 **어디까지 비교했는지**, **공정 비교가 가능한지**, **무엇을 더 해야 하는지** 한 문서에서 파악.
>
> **최종 갱신**: 2026-05-27 (Phase 10 완료)
> **관련 산출물**: `outputs/baseline_master_comparison.json` (통합 수치), `outputs/all_models_comparison_*.json`

---

## ⚡ Phase 10 업데이트 요약 (2026-05-27)

**Phase 10 완료** — scripts 26~32, 전 모델에 135d context 적용.

| 항목 | 이전 상태 | 현재 상태 |
|------|-----------|-----------|
| `17_evaluate_all_10cls.py`에 MLP 135d 추가 | ❌ | ✅ 7개 모델 추가 |
| LR 135d 10-class | ❌ | ✅ **62.4%** (41.1% → +21.3pp) |
| LightGBM 135d 10-class | ❌ | ✅ **67.3%** (13.0% → +54.3pp) |
| LR/LGB 4-class 135d | ❌ | ✅ 56.3% / 60.9% (4cls 포화 확인) |
| static58 sequence 정렬 | ❌ | ✅ `data/processed/static_58_*.npy` |
| RNN Hybrid 10-class | ❌ | ✅ **67.2%** (drop=True), **67.1%** (fullN) |
| Transformer Hybrid 10-class | ❌ | ✅ **66.8%** (drop=True), **67.1%** (fullN) |
| `baseline_master_comparison.json` | 부분 | ✅ G1~G6' 전 그룹 통합 |

**핵심 결론 (Phase 10 완료 후 수정)**:
- iid 모델: context 58d 추가 → 41% → 67%, architecture에 무관. **feature(context) 부재가 collapse 원인.**
- Sequence 모델: static context 추가 → 효과 없음 (RNN +0.3pp, Transformer -0.4pp). Sequence가 arsenal을 내재적으로 학습.
- **MDP 권장 모델**: `TransitionModelMLP10` (135d focal, **67.6%**, MDP 호환)

---

## 한 줄 요약

| 질문 | 답 |
|------|-----|
| 논문 구조 재현은 됐나? | **예** — Otremba MLP(`OtrembaMLP`), MIT Sloan Transformer(`PitchTransformer`) 코드·학습 스크립트 있음 |
| 한 표에 모든 모델이 있나? | **아니오** — 10-class는 JSON 5개 + MLP 135d는 별도 파일/문서에만 있음 |
| 숫자를 그대로 논문과 비교 가능? | **부분만** — 동일 데이터(2022–24)·동일 클래스 정의는 맞지만, **테스트 샘플 수·손실·입력 차원**이 달라 Top-1 한 줄 비교는 조건부 |
| 지금 당장 쓸 “공정 비교” | **4-class MDP 그룹**(LR/LGB/MLP 77d) · **10-class i.i.d. 그룹**(동일 353,776 pitches) · **논문 replica B vs C**(Phase 6) |

---

## 1. 비교가 나뉘는 세 트랙 (혼동 주의)

이 레포에는 “베이스라인”이 **목적별로 세 갈래**입니다. 표를 섞으면 잘못된 결론이 납니다.

```
┌─────────────────────────────────────────────────────────────────────────┐
│ Track A — Phase 6: 논문 replica (Otremba B vs MIT Sloan C)            │
│   • Model B: 77d → 4-class (Otremba 2022)                               │
│   • Model C: 400×87 seq → 10-class + multi-task (MIT Sloan 2025)        │
│   • Model A: empirical / majority (비학습)                              │
│   스크립트: 08, 09, 10  |  노트북: 02–05                               │
├─────────────────────────────────────────────────────────────────────────┤
│ Track B — Phase 9: 아키텍처 사다리 (같은 프로젝트 데이터, ablation)       │
│   • 10-class: LR → LGB → MLP(77d) → RNN → Transformer                   │
│   • 4-class:  LR → LGB → MLP(Model B)                                   │
│   스크립트: 13–20  |  JSON: all_models_comparison_10cls/4cls.json      │
├─────────────────────────────────────────────────────────────────────────┤
│ Track C — Phase 9.5: 본인 확장 (논문 밖, MDP용)                          │
│   • MLP 135d = 77d + context 58d (arsenal/UMAP/cluster)                 │
│   • 10-class focal loss 권장 모델                                       │
│   스크립트: 21_preprocess, 22–24, 21_top4_precision                     │
└─────────────────────────────────────────────────────────────────────────┘
```

**발표용으로 제외할 것**: `notebooks/13_*`, `scripts/22_build_presentation.py`, `scripts/23_build_10cls_comparison.py`, `docs/10class_comparison_script.md`

---

## 2. 모델 레지스트리 (코드 위치)

| ID | 이름 | 논문/역할 | 클래스 | 입력 | 구현 |
|----|------|-----------|--------|------|------|
| A | Empirical / Majority | Otremba식 비학습 baseline | 4 | 없음 | `src/evaluation/evaluate.py` |
| B | OtrembaMLP (Model B) | **Otremba 2022** | 4 (기본) / 10 (확장) | 77d | `src/models/otremba_mlp.py` → `OtrembaMLP` |
| B3 | MLP 135d focal | 본인 확장 (논문 아님) | 10 / 4 | 135d | 동일 `OtrembaMLP`, `input_dim=135` |
| C | PitchTransformer | **MIT Sloan 2025** | 10 + HL + cont (24d head) | 400×87 | `src/models/transformer.py` |
| — | LR / LightGBM | Phase 9 통계 baseline | 10 / 4 | 77d | `scripts/13–14`, `18–19` |
| — | PitchRNN | Phase 9 sequence baseline | 10 | 400×87 | `scripts/16_train_rnn.py` (스크립트 내 정의) |

**기본 MLP** = `OtrembaMLP` (128–128 hidden, ReLU). “아무 MLP”가 아니라 **Otremba 논문과 동일 토폴로지**입니다.

---

## 3. 어디까지 했는지 — 체크리스트

### 3.1 구현·학습

| 항목 | 상태 | 스크립트 / 노트북 | 비고 |
|------|:----:|-------------------|------|
| Otremba 4-class 학습 | ✅ | `08_train_model_b.py` | `model_b_full_v2` |
| MIT Sloan Transformer 학습 | ✅ | `09_train_model_c.py` | `model_c_full_v3` |
| Phase 6 평가 (B, C, baseline A) | ✅ | `10_evaluate_models.py` | npz: `evaluation_b_3season`, `evaluation_c_3season` |
| MLP 10-class (77d) | ✅ | `15_train_mlp_10class.py` | Focal γ=2, dropout 0.2 |
| LR / LGB 10·4-class | ✅ | `13–14`, `18–19` | |
| RNN 10-class | ✅ | `16_train_rnn.py` | |
| Phase 9 통합 JSON (5+3 모델) | ✅ | `17`, `20` | repo에 JSON **있음** |
| MLP 135d 10-class focal | ✅ | `24_train_mlp_135dim_10cls_focal.py` | 로그만 로컬; **npz/pt 없음**(gitignore 추정) |
| MLP 135d 4-class | ✅ | `22_train_mlp_135dim_4cls.py` | 4-class 통합 JSON **미포함** |
| Top-4 (MIT Sloan식 보조 지표) | ✅ | `21_top4_precision.py` | `top4_precision_comparison.json` |
| handoff v1 145d Transformer | ❌ | — | `docs/handoff_v1_analysis.md` 권장만 |
| Model A 래퍼 클래스 | ❌ | — | 평가 함수만 존재 |

### 3.2 로컬 아티팩트 (2026-05-27 기준)

`outputs/`에 **있는 것**: JSON 3개, LGB 체크포인트, 학습 로그, `arsenal_by_pitcher_cluster.json`  
**없는 것**: `evaluation_*.npz`, `model_*_best.pt` (대부분) — JSON은 과거 실행 결과를 반영한 것으로 보임. **재현하려면 학습/평가 스크립트 재실행 필요**.

---

## 4. 저장된 수치 — 통합 표

출처: `outputs/all_models_comparison_10cls.json`, `all_models_comparison_4cls.json`, `top4_precision_comparison.json`, `docs/paper_comparison.md` (MLP 135d Top-1/3/CE).

### 4.1 10-class — **i.i.d. 단일 투구** (test N ≈ **353,776**)

동일 테스트 집합에서만 Top-1/Top-3/CE를 직접 비교하세요.

| 모델 | 논문/트랙 | Top-1 | Top-3 | CE | Macro-F1 | 입력 | 비고 |
|------|-----------|------:|------:|---:|---------:|------|------|
| Logistic Regression | Phase 9 | 41.1% | 86.2% | 1.614 | 5.9% | 77d | Strike collapse |
| LightGBM | Phase 9 | 13.0% | 48.1% | 2.087 | 7.2% | 77d | class_weight 과함 |
| **MLP (77d)** | Otremba 구조 + 10출력 | 41.1% | 86.2% | 1.470 | 5.8% | 77d | **기본 MLP baseline** |
| **MLP (135d focal)** | Phase 9.5 | **67.6%** | **94.8%** | **0.926** | (미집계) | 135d | JSON 통합 **미포함** |
| Random | — | ~10% | — | — | — | — | Top-4 JSON 참고 |

### 4.2 10-class — **시퀀스** (test N ≈ **22,127**)

| 모델 | 논문/트랙 | Top-1 | Top-3 | CE | Macro-F1 | 입력 |
|------|-----------|------:|------:|---:|---------:|------|
| RNN (LSTM) | Phase 9 | 66.9% | 94.8% | 0.873 | 28.8% | 400×87 |
| **Transformer (Model C)** | **MIT Sloan 2025** | **67.2%** | **94.7%** | **0.868** | **30.1%** | 400×87 |

⚠️ **22,127 vs 353,776** — Overall Top-1을 i.i.d. MLP와 나란히 쓰면 **공정하지 않음** (시퀀스는 stride/window로 샘플 수가 적음).

### 4.3 4-class — **MDP 호환** (동일 i.i.d. test)

| 모델 | Top-1 | Top-3 | CE | Macro-F1 |
|------|------:|------:|---:|---------:|
| Logistic Regression | 56.3% | 94.5% | 1.052 | 48.4% |
| LightGBM | 60.8% | 96.6% | 0.872 | 53.3% |
| **MLP (Model B, Otremba)** | **60.9%** | **96.6%** | **0.872** | **53.8%** |

논문 Otremba 보고: validation **60.6%** (4-class) — 본 재현 **60.9%** test는 **거의 일치** (split/시즌 정의만 문서화하면 논문 대비 표기 가능).

### 4.4 Top-4 Precision (MIT Sloan 보조 지표)

| 모델 | Top-4 overall | n_samples | MDP |
|------|:-------------:|----------:|:---:|
| MLP 77d | 92.1% | 353,776 | ✅ |
| MLP 135d focal | **98.0%** | 353,667 | ✅ |
| RNN / Transformer | **98.0%** | 22,127 | ❌ |

LR/MLP 77d의 92%는 **collapse 착시** — per-class Top-4 필수 (`docs/top4_comparison.md`).

---

## 5. “정확한 비교”가 가능한가?

### 5.1 가능한 비교 (지금 구조로 타당)

1. **Otremba 4-class vs 본인 4-class 사다리**  
   - 동일 77d feature, 동일 4-class 라벨, 동일 test set → LR/LGB/**MLP 60.9%** 순위 비교 OK  
   - 논문 60.6%와의 차이는 ±0.3pp 수준으로 **재현 성공**으로 볼 수 있음  

2. **기본 MLP(77d) vs 확장 MLP(135d)** — 동일 10-class, i.i.d.  
   - 41.1% → 67.6%는 **feature ablation**으로 해석 가능 (Focal만으로는 77d가 41.1% 유지 — `paper_comparison.md`)  

3. **MIT Sloan Transformer vs RNN** — 동일 시퀀스 test (22k)  
   - 67.2% vs 66.9% → 아키텍처 비교 OK  

4. **MLP 135d vs Transformer** — 목적이 “MDP에서 시퀀스 없이 동등 성능?”이면  
   - Top-1 67.6% vs 67.2%, Top-4 98.0% vs 98.0% → **거의 동등** (단, n_samples 다름 명시 필수)  

### 5.2 불가능하거나 조건부인 비교

| 비교 | 문제 |
|------|------|
| Transformer Top-1 vs MLP 77d Top-1 | 테스트 샘플 수·입력 형태 다름 |
| LR Top-4 92% vs MLP 135d 98% | LR은 collapse; overall Top-4만 보면 오해 |
| MLP 135d vs **원 논문 MIT Sloan 숫자** | 논문은 다른 시즌/미공개 Top-4; 본인은 2022–24 Statcast 재현 |
| Otremba **10-class** vs 논문 | Otremba 원 논문은 **4-class만** — 10-class MLP는 본 프로젝트 확장 |
| handoff v1 145d Model C | **미학습** — v1 데이터와의 overlap 실험 미완 |

### 5.3 학습 조건 불일치 (공정성 체크리스트)

비교 논문/모델을 맞출 때 아래를 표 각주로 고정하는 것을 권장합니다.

| 항목 | MLP 77d 10cls | MLP 135d focal | Transformer (C) | LR 10cls | LGB 10cls |
|------|---------------|----------------|-----------------|----------|-----------|
| Loss | Focal γ=2 | Focal γ=2 | CE (multi-task) | weighted CE | inverse freq |
| Dropout | 0.2 | (스크립트 확인) | 논문 구조 | — | — |
| Epochs | 30 | 30 | 200 (early stop) | — | — |
| Class balance | Focal | Focal | CE | `balanced` | inverse freq → collapse |

→ **“모든 모델 동일 하이퍼파라미터” 비교는 아직 아님**. Phase 9는 *아키텍처 한계* 실험이 목적이었고, 135d는 *MDP용 최선* 튜닝에 가깝습니다.

---

## 6. 파일·스크립트 맵 (베이스라인만)

### 학습

| Phase | 내용 | Train |
|-------|------|-------|
| 6 | Otremba B | `scripts/08_train_model_b.py` |
| 6 | MIT Sloan C | `scripts/09_train_model_c.py` |
| 9 | LR / LGB / MLP10 / RNN | `13`–`16` |
| 9 | LR / LGB 4cls | `18`–`19` |
| 9.5 | 135d 전처리 | `scripts/21_preprocess_135dim.py` |
| 9.5 | 135d MLP 4/10 | `22`–`24` |

### 평가·집계

| 출력 | 스크립트 |
|------|----------|
| `evaluation_b_3season.npz`, `evaluation_c_3season.npz` | `10_evaluate_models.py` |
| `all_models_comparison_10cls.json` | `17_evaluate_all_10cls.py` |
| `all_models_comparison_4cls.json` | `20_evaluate_all_4cls.py` |
| `top4_precision_comparison.json` | `21_top4_precision.py` |
| `baseline_master_comparison.json` | (본 문서용 통합, 수동·스크립트 갱신) |

### 분석 노트북 (발표 제외)

| 노트북 | 용도 |
|--------|------|
| `02_model_a_baseline.ipynb` | Model A 개념 |
| `03_model_b_otremba_2022.ipynb` | Otremba 구조 |
| `04_model_c_mit_sloan_2025.ipynb` | MIT Sloan 구조 |
| `05_comparison_results.ipynb` | Phase 6 A/B/C |
| `06`–`09` | Phase 9 개별 모델 |
| `10_all_models_comparison.ipynb` | Phase 9 대시보드 |
| `11_mdp_dqn_compatibility.ipynb` | MDP 관점 (정확도 리더보드 아님) |

### 참고 문서

| 문서 | 내용 |
|------|------|
| `docs/paper_comparison.md` | Otremba vs MIT Sloan vs 135d (논문 스펙) |
| `docs/top4_comparison.md` | Top-4 per-class |
| `docs/handoff_v1_analysis.md` | v1 확장 시나리오 (baseline 유지 권장) |

---

## 7. 권장 다음 단계

### Phase 10 완료 후 남은 작업

1. ~~**아티팩트 복구**~~ ✅ 완료 — evaluation_*.npz 전부 재생성
2. ~~**`17_evaluate_all_10cls.py`에 MLP 135d 추가**~~ ✅ 완료 — 12개 모델 graceful skip 포함
3. **비교 표 3장 분리 (논문/보고서용)**  
   - 표 A: G1 vs G2 — 4-class MDP (77d vs 135d)  
   - 표 B: G3 vs G4 — 10-class i.i.d. (77d vs 135d)  
   - 표 C: G5 vs G6/G6' — 10-class sequence (87d seq vs hybrid)  
   - 각 표 footnote: `n_test`, loss, 시즌(2022–2024) 고정

4. **rl-agent 통합 테스트** (rl-agent 팀)  
   - `TransitionModelMLP10` 로드 → MDP-VI end-to-end 검증  
   - Walk/Strikeout 직접 예측 vs BIP 테이블 병행 비교  

5. **(선택) Single~HR > 5% 개선**  
   - Batter arsenal feature 추가 (“135+α dim”)  
   - `γ=3.0` + weighted sampler 조합

6. **handoff v1**  
   - Phase 10 baseline 유지, v1은 별도 트랙 (`handoff_v1_analysis.md`)

---

## 8. 빠른 실행 (재현)

```powershell
cd c:\Users\zpfh1\Projects\transition-models

# Phase 9 통합 (npz 있을 때)
python scripts/17_evaluate_all_10cls.py
python scripts/20_evaluate_all_4cls.py
python scripts/21_top4_precision.py

# Phase 6 (체크포인트 있을 때)
python scripts/10_evaluate_models.py
```

npz가 없으면 해당 스크립트는 SKIP — 먼저 `15`, `16`, `24` 등 train 스크립트 실행.

---

## 9. 결론 (의사결정용)

| 목표 | 현재 상태 | 권장 |
|------|-----------|------|
| Otremba MLP **논문 구조** 4-class 재현 | ✅ 60.9% | `paper_comparison.md` + Phase 6 npz로 보고 |
| MIT Sloan **Transformer** 10-class 재현 | ✅ 67.2% (seq test) | Track C 표에만 기재 |
| **기본 MLP** 10-class 한계 | ✅ 41.1% collapse | 77d baseline으로 명시 |
| **본인 최선 MDP 모델** | ✅ 135d 67.6% | Otremba **확장**이지 논문 baseline 아님 |
| 모든 모델 **한 표** 공정 비교 | ⚠️ 부분 | `baseline_master_comparison.json` + 표 3분할 + 135d를 `17`에 편입 |

**정확한 비교는 “트랙·테스트 집합·지표”를 맞춘 범위에서만 가능**합니다. 지금 숫자는 충분히 유용하지만, Transformer vs MLP 135d는 **동등 성능 주장 + n_samples/조건 각주**가 필수입니다.

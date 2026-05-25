# SmartPitch MDP Transition Probability Models

## Project Goal

SmartPitch MDP의 전이확률(transition probability) 추정 모델 3가지를 비교 실험한다.
동일한 MLB Statcast 데이터에 대해 학습·평가하여 정확도, 캘리브레이션, 추론 속도를 비교한다.

## Models

| ID | Name | Reference | Input | Output | Architecture |
|----|------|-----------|-------|--------|-------------|
| Model C | MIT Sloan 2025 Transformer | MIT Sloan 2025 | 87-dim × 400 sequence | 24-dim (full state transition) | 12-layer Encoder, sub-token masking |
| Model B | Otremba 2022 MLP | Otremba 2022 | 77-dim | 4-dim (Strike/Ball/Foul/InPlay) | 2-layer, 128 hidden units |
| Model A | SmartPitch MLP (wrapper) | Internal | TBD | TBD | Existing SmartPitch MLP via wrapper |

## Environment

- **Python**: 3.12 (managed by uv)
- **Package manager**: uv
- **Deep learning**: PyTorch (Mac MPS for local dev, CUDA for GPU server)
- **Experiment tracking**: W&B
- **Config**: OmegaConf + YAML (configs/)

## Code Conventions

- 한국어 주석 OK, docstring은 영어로 작성
- Formatter/Linter: ruff (line-length 100, select E/W/F/I/B/UP)
- Testing: pytest (tests/)
- Import order: stdlib → third-party → local (ruff I rule)

## Directory Structure

```
src/
  models/       # Model definitions (model_a.py, model_b.py, model_c.py)
  data/         # Dataset, feature engineering, dataloaders
  training/     # Training loops, schedulers
  evaluation/   # Metrics, calibration, comparison
  utils/        # Common helpers
configs/        # YAML config files per model/experiment
scripts/        # Standalone scripts (data prep, training, eval)
notebooks/      # Exploration notebooks
data/           # Raw/processed data (git-ignored except .gitkeep)
outputs/        # Checkpoints, logs, figures (git-ignored except .gitkeep)
references/     # Papers (git-ignored PDFs)
tests/          # pytest tests
```

## Progress Checklist

### Phase 1-2: Setup & Data Acquisition
- [x] Project scaffolding & environment setup
- [x] Sanity check (PyTorch, MPS)
- [x] Data acquisition (pybaseball / Statcast)
  - 1,534,286 pitches (2023: 774,038 / 2024: 760,248), 118 columns

### Phase 3: Data Pipeline
- [x] 3.1: Data exploration
  - 8 deprecated columns 식별, 400+ pitches 타자 586명 (sliding window 가능)
  - 시즌 간 분포 거의 동일
  - notebooks/01_data_exploration.ipynb (9셀, 한국어 주석)
- [x] 3.2: Feature mapping (4/10-class labels, hit location)
  - 4-class 매핑 100% (Ball/Strike/Foul/InPlay)
  - 10-class 매핑 99.96% (660건 truncated_pa → 전처리 시 제거)
  - Hit location 9-class: InPlay 한정 (22.7%)
  - src/data/features.py, tests/test_features.py (27 tests), scripts/03_validate_mapping.py
- [x] 3.3: Preprocessing pipeline (lazy loading)
  - 1,534,286 → 1,488,976 rows (정제 후, 3.0% 제거)
  - 87차원 Model C vector: 연속(15)+pitch_type(17)+zone(14)+balls(4)+strikes(3)+outs(3)+base(8)+stand(2)+throws(2)+result(10)+hitloc(9)
  - 77차원 Model B vector: 위 68차원 + inning(9)
  - StandardScaler (train fit), stride=8 (실용적 속도 고려, stride=1은 1 epoch=76분)
  - Sub-token masking: __getitem__에서 indices [68:87] → 0
  - Split: Train 749,880 / Val 385,320 / Test 353,776 (날짜 겹침 없음)
  - src/data/preprocess.py, scripts/04_preprocess.py
- [x] 3.4: PyTorch Dataset (lazy loading)
  - PitchSequenceDataset: O(1) numpy slice, stride=8
    - Train 65,418 / Val 25,077 / Test 22,127 sequences (stride=1 대비 8x 감소)
  - PitchPointDataset: eager (77-dim, 작음)
  - 디스크: vectors .npy + indices .pkl ≈ 1 GB (이전 3.2 GB에서 축소)
  - 77 tests all pass

### Phase 4: Model Implementation
- [x] 4.1: Common base interface (src/models/base.py)
  - TransitionModel ABC: forward, predict_proba, num_classes, model_name
- [x] 4.2: Model B — OtrembaMLP (src/models/otremba_mlp.py)
  - 77→128→128→4, ReLU, 27,012 params
  - Sanity check: loss 1.41→1.31 (10 epochs, MPS), softmax 합=1 ✓
- [x] 4.3: Model C — PitchTransformer (src/models/transformer.py)
  - 87×400 → embed(256) → 12-layer Encoder → last-token + residual → 24-dim
  - 9,659,672 params, MPS 호환, 3.3s/epoch (64 seq, batch=8)
  - Multi-task: pitch_result(10) + hit_location(9) + continuous(5)
  - Sanity check: loss 19.1→18.0, accuracy 41%→48% (5 epochs)

### Phase 5: Training ✅
- [x] 5.1: Training loop (src/training/train.py)
  - TrainingConfig dataclass, AdamW + CosineAnnealingLR (per-batch step)
- [x] 5.2: W&B integration (project=transition-models, entity=pitcheezy)
- [x] 5.3: Checkpoint management (best + last per run)
- [x] 5.4: Sanity check learning (CUDA, small subset)
- [x] 5.5: Full training ✅
  - Model B v1 (2시즌): model_b_full_v1 — best val_loss 0.8730 (epoch 10), val_acc 60.6%, 8분
  - Model C v2 (2시즌): model_c_full_v2 — best val_loss 1.8334 (epoch 29), val pr_acc 67.1%, 4시간 53분
  - Model B v2 (3시즌): model_b_full_v2 — best val_loss 0.8700 (epoch 12), val_acc 61.0%, ~11분
  - Model C v3 (3시즌): model_c_full_v3 — best val_loss 1.8190 (epoch 21), val pr_acc 67.3%, ~10시간 (RTX 4070, stride=8, 150K seqs)

### Phase 6: Evaluation & Comparison ✅
- [x] 6.1: Metrics (cross entropy, brier score, top-k precision)
  - src/evaluation/metrics.py, evaluate.py, scripts/10_evaluate_models.py
  - **2시즌** — Model B: top-1 60.8%, CE 0.876 / Model C: top-1 66.7%, CE 0.880
  - **3시즌** — Model B: top-1 60.9%, CE 0.872 / Model C: top-1 67.2%, CE 0.868
  - 13 unit tests all pass
- [x] 6.2: Per-class performance analysis
  - Model B (3시즌): Ball 91.7%, Strike 56.4%, Foul 29.6%, InPlay 38.2%
  - Model C (3시즌): Ball 87.6%, Strike 82.2%, Walk 85.6%, Strikeout 17.3%, FieldOut 10.7% / Single-HR 0%
  - evaluation_b.npz + evaluation_c.npz (2시즌), evaluation_b_3season.npz + evaluation_c_3season.npz (3시즌)
- [x] 6.3: Comparison report (3 models)
  - notebooks/05_comparison_results.ipynb (Model A baseline vs B vs C)
  - Model A 35.6% → Model B 60.8% (2시즌) / 60.9% (3시즌) → Model C 66.7% (2시즌) / 67.2% (3시즌)
- [x] 6.4: Visualization (loss curves, confusion matrices)
  - 04 노트북 결과 섹션 완성, 05 노트북 신규 작성

### Phase 7: Inference & Integration ✅
- [x] 7.1: Inference wrappers (src/inference/transition_model.py)
  - TransitionModelB: predict(x: (77,) or (N,77)) → (4,) or (N,4) numpy
  - TransitionModelC: predict(x: (400,87) or (N,400,87)) → {"pitch_result": (10,), "hit_location": (9,)}
  - predict_top_k(x, k) → [{"class": str, "probability": float}]
  - 자동 checkpoint 로드, CUDA/MPS/CPU 자동 감지
- [x] 7.2: Demo script (scripts/11_inference_demo.py)
  - Model B + Model C 예측 출력, DQN 패턴 3-step 시뮬레이션
- [x] 7.3: Documentation (docs/INFERENCE_GUIDE.md, 290 lines)
  - TL;DR 3줄, 77/87-dim feature 인덱스 표, DQN 환경 통합 코드, 트러블슈팅
- [x] 7.4: Unit tests (tests/test_inference.py, 8 tests all pass)

### 전체 테스트 검증 (2026-05-08) ✅
- 116 collected / **114 passed** / 2 skipped (MPS, Windows 정상) / 0 failed
- 실행 시간: 27.5초
- 커버리지: features, preprocess, dataset, models, transformer, training, evaluation, inference

### Phase 8: 3시즌 데이터 확장 ✅ (2026-05-14)
- [x] 2022 Statcast 데이터 다운로드 (775,330 pitches, 118 cols)
- [x] 3시즌 정합성 검증: FT=0, spin_rate 차이 10.4 RPM, 컬럼 완전 일치
- [x] sac_bunt_double_play → FIELD_OUT 매핑 추가 (2022 신규 이벤트)
- [x] preprocess.py: split_by_season(train_years) 파라미터화
- [x] 04_preprocess.py: --years argparse (train=years[:-1], val/test=last year)
- [x] Model B v2 재학습: top-1 60.8% → 60.9% (+0.1pp), CE 0.876 → 0.872
- [x] Model C v3 재학습: top-1 66.7% → 67.2% (+0.5pp), CE 0.880 → 0.868
- [x] 3시즌 evaluation 저장: evaluation_b_3season.npz, evaluation_c_3season.npz

### Phase 9: 발표 피드백 반영 — 두 그룹 비교 ✅ (2026-05-23)

**두 비교 그룹**:
- **Group 1 (10-class)**: Architecture 효과 — LR, LightGBM, MLP, RNN, Transformer
- **Group 2 (4-class MDP 호환)**: LR, LightGBM, MLP (Model B)

**스크립트**:
- [x] scripts/13_train_logistic_regression.py (10-class LR)
- [x] scripts/14_train_lightgbm.py (10-class LightGBM)
- [x] scripts/15_train_mlp_10class.py (10-class MLP)
- [x] scripts/16_train_rnn.py (10-class RNN/LSTM)
- [x] scripts/17_evaluate_all_10cls.py (10-class 종합 평가)
- [x] scripts/18_train_logistic_regression_4cls.py (4-class LR)
- [x] scripts/19_train_lightgbm_4cls.py (4-class LightGBM)
- [x] scripts/20_evaluate_all_4cls.py (4-class 종합 평가)

**학습 결과**:
- LR 10cls: Top-1 41.1% (collapse — sqrt-balanced weight 적용해도 Strike만 예측, CE 1.614)
- LightGBM 10cls: Top-1 13.0% (역방향 collapse — inverse-freq 과보정, 전 클래스 균등 예측, CE 2.087)
- MLP 10cls: Top-1 41.1% (collapse — Focal Loss γ=2.0 적용해도 Strike만 예측, CE 1.470)
- RNN 10cls: Top-1 66.9%, Top-3 94.8%, CE 0.8728 (완료)
- Transformer 10cls: Top-1 67.2% (기존 결과)
- LR 4cls: Top-1 56.3%, CE 1.0516 (balanced weights)
- LightGBM 4cls: Top-1 60.8%, CE 0.8719 (is_unbalance=True)
- MLP 4cls (Model B): Top-1 60.9%, CE 0.8723 (기존 결과)

**핵심 발견**: 77-dim 단일 투구 feature는 10-class 분류에 필요한 discriminative signal 자체가 부족.
- class balancing 미적용: Strike 다수 클래스 collapse (LR 41.1%, MLP 41.1%)
- class balancing 강적용: 반대 방향 collapse, 전 클래스 균등 예측 (LGB 13%)
- Focal Loss, sqrt-balanced 등 어떤 최적화 기법도 feature 부재를 보완 불가
- Sequence 모델(RNN 66.9%, Transformer 67.2%): pitch context로 극복
- Arsenal features(MLP 135d 67.6%): 투수 맥락 정적 feature로 극복 (Phase 9.5)

**노트북**:
- [x] notebooks/06_logistic_regression.ipynb
- [x] notebooks/07_lightgbm.ipynb
- [x] notebooks/08_mlp_10class.ipynb
- [x] notebooks/09_rnn.ipynb
- [x] notebooks/10_all_models_comparison.ipynb
- [x] notebooks/11_mdp_dqn_compatibility.ipynb
- [x] notebooks/00_project_journey.ipynb Phase 9 섹션 추가

**평가 파일**:
- outputs/evaluation_lr_10cls.npz, evaluation_lr_4cls.npz
- outputs/evaluation_lgb_10cls.npz, evaluation_lgb_4cls.npz
- outputs/evaluation_mlp_10cls.npz
- outputs/evaluation_rnn_10cls.npz
- outputs/all_models_comparison_10cls.json
- outputs/all_models_comparison_4cls.json

### Phase 9.5: MDP 호환 10-class 돌파 — 135-dim Arsenal MLP ✅ (2026-05-25)

**동기**: Sequence 모델(RNN/Transformer)은 10-class 67%+를 달성하지만 MDP state 비호환.
77-dim MLP collapse의 원인이 "feature 부족"인지 "context 부족"인지 분리 실험.
투수 arsenal 통계(pitcher repertoire embedding)를 정적 feature로 추가해 context를 근사.

**실험 설계**:
- 입력: 135-dim = 77-dim (Model B) + 5-dim UMAP (0-fill) + 53-dim arsenal
  - [77:82]: UMAP 5d → inference 시 0.0 (학습 데이터 평균값, 투구 후 측정값 미보유)
  - [82:83]: count_cluster_id (scaled)
  - [83:115]: arsenal_func 32d (pitcher pitch type distribution + movement stats)
  - [115:135]: arsenal_moment 20d (arsenal distribution moments)
- 손실: Focal Loss (γ=2.0) — Walk/Strikeout/FieldOut 희소 클래스 보정
- 아키텍처: MLP 135→128→128→10 (dropout=0.2), `TransitionModelMLP10`
- 스크립트: scripts/24_train_mlp_135dim_10cls_focal.py, scripts/25_evaluate_mlp_135dim_10cls_focal.py

**6-model 비교표** (10-class Top-1):

| 모델 | Input | Top-1 | Top-3 | MDP 호환 | 비고 |
|------|-------|-------|-------|---------|------|
| LR | 77d i.i.d. | 41.1% | 86.2% | ✅ | collapse (Strike만 예측) |
| LightGBM | 77d i.i.d. | 41.1% | 86.2% | ✅ | collapse |
| MLP (77d) | 77d i.i.d. | 41.1% | 86.2% | ✅ | collapse |
| **MLP 135d focal** | **135d i.i.d.** | **67.6%** | **—** | **✅** | **MDP 호환 최선** |
| RNN (LSTM) | 400×87 seq | 66.9% | 94.8% | ❌ | sequence 의존 |
| Transformer | 400×87 seq | 67.2% | 94.7% | ❌ | sequence 의존 |

**핵심 발견**:
1. **77-dim collapse ≠ feature 부족**: context 58d 추가만으로 41.1% → 67.6% (+26.5pp).
   Sequence 모델과 동등 수준 달성. 부족했던 것은 feature가 아니라 "투수 맥락(pitcher context)".
2. **Arsenal이 sequence context를 근사**: 400-pitch history 없이도 pitcher repertoire 통계로
   동일한 수준의 pitch outcome 분리 가능. MDP/DQN 호환성 포기 없이 달성.
3. **Single~HR은 여전히 0%**: Focal Loss로 Walk(85.9%), Strikeout(19.5%), FieldOut(7.3%) 개선됐으나
   단타~홈런은 0%. 원인: 타자 맥락(batter tendency)이 135-dim에도 없음.
   타자 arsenal에 해당하는 feature 없는 한 구조적 한계.
4. **4-class feature saturation 확인**: LR 56.3% → LightGBM 60.8% → MLP 60.9%.
   77-dim 공간에서 비선형성의 이득은 미미. 61% 천장은 feature expressiveness 한계.

**권장 MDP 모델**: `TransitionModelMLP10` (135-dim focal, 67.6%, MDP 호환)
- 기존 Model B (4-class, 60.9%)를 rl-agent 통합 시 대체 권장
- Walk/Strikeout/HitByPitch 직접 예측 가능 (BIP 테이블 의존 탈피 부분적 달성)
- Single~HR은 BIP 테이블과 병행 권장 (InPlay 확률 × 고정 비율)

**산출물**:
- outputs/checkpoints/model_b3_focal_135dim_10cls_best.pt (epoch 25, val_focal_loss 0.4505)
- outputs/evaluation_mlp_135dim_10cls_focal.npz (Top-1 67.6%, per-class accuracy)
- outputs/arsenal_by_pitcher_cluster.json (4클러스터, pitcher 2,007명 매핑)
- docs/handoff_to_rl_agent.md (rl-agent 통합 코드 골격 포함)
- docs/rl_agent_teammate_guide.md (다운로드 및 통합 단계별 가이드)
- src/inference/transition_model.py — `TransitionModelMLP10` 클래스 추가

### Future Work
- Single~HR 개선: 타자 arsenal feature (batter_func/moment) 추가 → "135+α dim"
- Weighted sampler + γ=3.0 조합으로 Single~HR > 5% 목표
- Continuous regression target 실제 구현 (현재 placeholder 0)
- Model A wrapper 구현 (실제 SmartPitch 통합)
- Ablation study (sub-token mask, last-pitch residual 효과 분리)
- Small Transformer (MDP 호환 가능성 탐색)
- Transformer embedding → MDP state 통합 (Hybrid 시스템)

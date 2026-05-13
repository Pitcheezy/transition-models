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

### Future Work
- Class imbalance 처리: weighted loss / focal loss / weighted random sampler
- Continuous regression target 실제 구현 (현재 placeholder 0)
- Model A wrapper 구현 (실제 SmartPitch 통합)
- Ablation study (sub-token mask, last-pitch residual 효과 분리)
- 발표 슬라이드 자료 작성 (notebooks/05 활용)

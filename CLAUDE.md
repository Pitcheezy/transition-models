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
  - StandardScaler (train fit), stride=1 (논문 그대로, lazy loading)
  - Sub-token masking: __getitem__에서 indices [68:87] → 0
  - Split: Train 749,880 / Val 385,320 / Test 353,776 (날짜 겹침 없음)
  - src/data/preprocess.py, scripts/04_preprocess.py
- [x] 3.4: PyTorch Dataset (lazy loading)
  - PitchSequenceDataset: O(1) numpy slice, stride=1
    - Train 521,680 / Val 199,313 / Test 175,862 sequences
  - PitchPointDataset: eager (77-dim, 작음)
  - 디스크: vectors .npy + indices .pkl ≈ 1 GB (이전 3.2 GB에서 축소)
  - 77 tests all pass

### Phase 4: Model Implementation
- [x] 4.1: Common base interface (src/models/base.py)
  - TransitionModel ABC: forward, predict_proba, num_classes, model_name
- [x] 4.2: Model B — OtrembaMLP (src/models/otremba_mlp.py)
  - 77→128→128→4, ReLU, 27,012 params
  - Sanity check: loss 1.41→1.31 (10 epochs, MPS), softmax 합=1 ✓
- [ ] 4.3: Model C (MIT Sloan 2025 Transformer)
  - 87차원 × 400 sequence input
  - 12-layer Transformer Encoder, d_model=256, 8 heads
  - Last-pitch residual connection
  - Multi-task head (10-class + 9-class + 5 continuous)
  - Multi-task loss: 0.7 × (CE_PR + CE_HL) + 0.3 × MSE_C

### Phase 5: Training
- [ ] 5.1: Training loop (src/training/train.py)
- [ ] 5.2: W&B integration
- [ ] 5.3: Checkpoint management
- [ ] 5.4: Sanity check learning (Mac MPS, small subset)
- [ ] 5.5: Full training (학교 GPU 서버 또는 게이밍 노트북)

### Phase 6: Evaluation & Comparison
- [ ] 6.1: Metrics (cross entropy, brier score, top-k precision)
- [ ] 6.2: Per-class performance analysis
- [ ] 6.3: Comparison report (3 models)
- [ ] 6.4: Visualization (loss curves, confusion matrices)

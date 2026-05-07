# transition-models

SmartPitch MDP의 전이확률(transition probability) 추정 모델 3가지를 비교하는 프로젝트.

## Models

| | Model A (SmartPitch MLP) | Model B (Otremba 2022 MLP) | Model C (MIT Sloan 2025 Transformer) |
|---|---|---|---|
| **Input** | TBD | 77-dim feature vector | 87-dim × 400 sequence |
| **Output** | TBD | 4-dim (B/S/F/InPlay) | 24-dim (10+9+5 multi-task) |
| **Architecture** | Existing MLP (wrapper) | 2-layer, 128 units, ReLU | 12-layer Encoder, sub-token masking |
| **Parameters** | TBD | 27,012 | 9,659,672 |
| **Status** | - | Implemented | Implemented |
| **Reference** | Internal | Otremba 2022 | MIT Sloan 2025 |

## Data

- **Source**: MLB Statcast (pybaseball)
- **Seasons**: 2023, 2024
- **Total pitches**: 1,534,286 (정제 후 1,488,976)
- **Split**: Train 749,880 (2023) / Val 385,320 (2024 3-6월) / Test 353,776 (2024 7월+)
- **Sequences (Model C)**: Train 521,680 / Val 199,313 / Test 175,862 (stride=1, lazy loading)

## Quick Start

```bash
# 의존성 설치
uv sync

# PyTorch + MPS 확인
uv run python scripts/00_sanity_check.py

# 데이터 다운로드 (테스트: 1주일치)
uv run python scripts/01_download_data.py --years 2024 --test-mode

# 데이터 다운로드 (전체: 2시즌, ~2시간)
uv run python scripts/01_download_data.py --years 2023 2024

# 전처리 (lazy loading 방식)
uv run python scripts/04_preprocess.py

# 테스트 실행
uv run pytest

# Model B sanity check
uv run python scripts/05_sanity_check_model_b.py

# Model C sanity check
uv run python scripts/06_sanity_check_model_c.py
```

## Project Structure

```
src/
  models/       Model definitions (base.py, otremba_mlp.py, transformer.py)
  data/         Features, preprocessing, datasets (lazy loading)
  training/     Training loops
  evaluation/   Metrics & comparison
  utils/        Logger, helpers
configs/        Experiment configs (YAML)
scripts/        Standalone scripts (download, preprocess, sanity checks)
notebooks/      Data exploration
data/           Raw/processed data (git-ignored)
outputs/        Checkpoints, logs, figures (git-ignored)
references/     Papers
tests/          91 pytest tests
```

## Daily Memo

> 팀원 데일리 메모. 날짜와 이름을 적고, 오늘 한 일/배운 것/이슈를 자유롭게 기록.

| 날짜 | 작성자 | 내용 |
|------|--------|------|
| 2025-05-05 | 조현준 | 나도 어린이라 어린이날을 즐김 |
| 2025-05-06 | 조현준 | **transition-models 프로젝트 시작 (Phase 1~3.4)**<br><br>**한 일**<br>- 졸업작품용 별도 repo `Pitcheezy/transition-models` 세팅 (uv, pyproject.toml, VS Code, Claude Code 통합)<br>- Statcast 2023-2024 데이터 다운로드 (1,534,286 pitches, 198MB Parquet)<br>- 데이터 탐색 노트북 작성 (9셀, 한국어 주석, 8 deprecated 컬럼 식별, 400+ pitches 타자 586명 확인)<br>- Feature 매핑 모듈 구현 (`src/data/features.py`): 4-class (Otremba 2022) 100% 매핑, 10-class (MIT Sloan 2025) 99.96% 매핑<br>- 전처리 파이프라인 + PyTorch Dataset 1차 구현 (`preprocess.py`, `dataset.py`)<br>- 87차원 Model C vector / 77차원 Model B vector 정의<br>- Train/Val/Test 시즌 기반 분할 (749K / 385K / 354K, 날짜 겹침 없음)<br>- Sub-token masking 구현 + 검증<br>- 단위 테스트 54개 작성 (모두 통과)<br><br>**배운 것**<br>- Statcast description vs events 컬럼의 우선순위 매핑 (events 우선, description fallback)<br>- StandardScaler는 train에만 fit하고 val/test는 transform만 적용해야 data leakage 방지<br>- Sub-token masking은 마지막 pitch의 outcome features만 0 처리해야 함 (직전 399개는 보존)<br><br>**이슈**<br>- stride=1 (논문 그대로)로 시퀀스 미리 만들면 약 521K 시퀀스 × 400 × 87 × 4B ≈ **72GB 메모리 필요** → Mac Mini OOM<br>- 임시방편으로 stride=50 사용 (시퀀스 10K개로 축소, 데이터 1/49 수준) → 다음 날 해결 예정 |
| 2025-05-07 | 조현준 | **Lazy Loading 리팩토링 + Phase 4 모델 구현 완료**<br><br>**한 일**<br>- **Lazy Loading 패턴으로 데이터 파이프라인 재구축**: 시퀀스를 미리 만들지 않고 (N, 87) 벡터를 .npy로 저장 후 `Dataset.__getitem__`에서 O(1) numpy slice로 즉석 생성<br>- 결과: stride=1 사용 가능, 시퀀스 10,668 → **521,680개 (49배)**, 디스크 3.2GB → 1GB, 메모리 72GB → 1GB<br>- Phase 4.1: `TransitionModel` ABC 인터페이스 (forward, predict_proba, num_classes, model_name)<br>- Phase 4.2: **OtrembaMLP** 구현 (77→128→128→4, 27,012 params), MPS sanity check 통과<br>- Phase 4.3: **PitchTransformer** 구현 (87×400 → embed(256) → 12-layer Encoder → last-token + last-pitch residual → 24-dim multi-task head, 9.7M params)<br>- 단위 테스트 추가 (총 91개, 모두 통과)<br>- 커밋 4개 추가 (총 10개)<br><br>**배운 것**<br>- **Lazy Loading 패턴**: 메모리 한계 우회의 표준 PyTorch 패턴. ImageNet, GPT 학습에서도 동일하게 사용. 전처리 시 가능한 데이터 변환을 미리 해두고 (.npy, memory-mappable), `__getitem__`에서는 slice만 하면 빠르고 메모리 효율적<br>- **Last-pitch residual connection**: Transformer encoder를 거치며 마지막 pitch 정보가 다른 pitches와 섞이는 걸 방지하기 위해 raw 87차원을 다시 projection해서 concat하는 트릭. 논문의 핵심 디자인<br>- 12-layer Transformer (d_model=256, 8 heads, ff=1024)는 약 9.7M params로 예상보다 큼. 본격 학습은 GPU 필요<br><br>**이슈/다음 작업**<br>- Mac MPS로는 본격 학습 비현실적 (Model C 1 epoch ≈ 30분, 30 epochs ≈ 15시간)<br>- 학습 환경 결정 완료: **HP OMEN Transcend 16 (RTX 4050/4060/4070)**으로 진행 예정<br>- 내일 학교에서 노트북 GPU 정확히 확인 (`nvidia-smi`) 후 Phase 5 (training loop + W&B + 본격 학습) 시작 |
| 2026-05-08 | 조현준 | **Phase 5 + Phase 6 완료 - 학교 RTX 4070 환경에서 본격 학습 + 평가 + 비교 노트북**<br><br>**한 일**<br>- Mac → Windows (HP OMEN Transcend 16, RTX 4070 8GB) 환경 이전: PyTorch CUDA 셋업 (pyproject.toml [tool.uv.sources]에 cu124 인덱스 추가), `get_device()` multi-platform helper 추가 (CUDA → MPS → CPU)<br>- Phase 5.1~5.4: Training loop + W&B integration + Sanity check 완료 (TrainingConfig, AdamW + CosineAnnealingLR, multi-task loss, early stopping patience=5, checkpoint best+last). 4 unit tests + 두 sanity training 통과<br>- **Model B 본격 학습**: 749K samples × max 200 epochs (early stopped epoch 20, best epoch 10), best val_loss 0.873, val_acc **60.6%** (baseline 35.6% 대비 **+25pp**), 8분 소요. W&B run: bspnzo7m<br>- 노트북 02, 03, 04 작성 (Model A baseline + Model B/C walkthrough, 한국어 markdown + matplotlib 시각화, sub-token masking 시각화 포함)<br>- **Model C 시도 1 (실패)**: stride=1로 30 epochs 시도 → 1 epoch에 76분 → 30 epochs = 38시간 예상 → KeyboardInterrupt로 중단. Epoch 1 결과 train=1.95, val=1.87 (학습 자체는 잘 됨, 시간만 문제)<br>- **Stride 최적화 (8배 단축)**: stride=1 → stride=8로 데이터 재처리 (sequences 521K → 65K), 학습 시간 38h → 5h. Architecture는 그대로 유지 (sequence_length=400)<br>- **Model C 본격 학습**: 65K sequences × 30 epochs (full, early stopping 안 됨), best val_loss 1.833 (epoch 29), val pr_acc **67.1%**, val hl_acc 37.4%, 4시간 53분 소요. W&B run: nawthn1p<br>- 한글 폰트 깨짐 수정: Windows에서 matplotlib 한글 □□□ → Malgun Gothic 폰트 명시 (03/04 노트북)<br>- 노트북 00 (project_journey) 신규 작성: Day 1 + Day 2 진행 일지 + 시각화 (메모리 비교, GPU 성능, Model B 결과, Stride 효과) + 트러블슈팅 + 회고<br>- **Phase 6 평가 (test set)**: scripts/10_evaluate_models.py로 Model B + Model C + baseline 평가 → outputs/evaluation_b.npz, evaluation_c.npz 저장<br>  - Model B test top-1: **60.8%** (CE 0.876, top-3 96.6%)<br>  - Model C test top-1 (Pitch Result, 10-class): **66.7%** (CE 0.880, top-3 94.6%) — **더 어려운 10-class에서 Model B 4-class보다 높음**<br>  - Per-class accuracy 정량 분석<br>- 노트북 04에 Model C 결과 채우기 (TODO → 실제 결과)<br>- 노트북 05 (comparison_results) 신규 작성: Model A baseline / Model B (MLP) / Model C (Transformer) 3-way 비교, top-1 / CE / per-class / confusion matrix 시각화, 논문 결과 비교 (Model B +8pp), 결론<br><br>**배운 것**<br>- **Architecture가 결정적**: Model C가 더 어려운 10-class 문제 (66.7%)에서 Model B의 4-class (60.8%)보다 더 높은 정확도. Sequence + Transformer의 효과를 정량적으로 입증<br>- **Stride trade-off**: stride=1은 메모리뿐만 아니라 **시간**도 큰 문제 (38h). stride=8은 데이터 다양성 ↑, 중복 ↓, 학습 시간 8배 ↓ — sweet spot<br>- **Class Imbalance 영향 정량적 발견**: 다수 클래스 (Ball/Strike/Walk) 80%+, 소수 클래스 (Single/Double/Triple/HomeRun) **0%** — 무처리 결정의 결과를 정량적으로 발견. 향후 weighted loss 또는 focal loss 필요<br>- **PyTorch CUDA + uv**: 첫 uv sync 시 PyTorch CPU 버전 자동 설치됨. pyproject.toml의 [tool.uv.sources] + [[tool.uv.index]]로 platform별 PyTorch 인덱스 분리하면 깔끔하게 해결<br>- **Multi-platform 추상화의 가치**: get_device() helper 하나로 Mac MPS / Windows CUDA / CPU 코드 통합. 일찍 만들어두면 환경 이전 시 큰 도움<br>- **W&B의 강력함**: 학습 진행 중에도 폰으로 loss curve 모니터링 가능. 발표 자료로 바로 사용 가능한 그래프 자동 생성<br>- **Sanity check의 가치**: 64 sequences × 5 epochs로 학습 동작 미리 검증. 본격 학습 전 자신감 확보<br><br>**이슈/다음 작업**<br>- Class imbalance 처리 (Triple/HR 0% accuracy 해결): weighted loss / focal loss / weighted random sampler 도입<br>- Continuous regression target 실제 구현 (현재 placeholder 0)<br>- Model A wrapper 구현 (실제 SmartPitch 통합)<br>- Data 확장 (2018-2022 추가 후 재학습)<br>- Ablation study (sub-token mask, last-pitch residual 효과 분리 검증)<br>- 발표 슬라이드 자료 작성 (노트북 05 활용) |

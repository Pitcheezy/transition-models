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

## Dev Log

> 팀원 일기장. 날짜와 이름을 적고, 오늘 한 일/배운 것/이슈를 자유롭게 기록.

| 날짜 | 작성자 | 내용 |
|------|--------|------|
| | | |

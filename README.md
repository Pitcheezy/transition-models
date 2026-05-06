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

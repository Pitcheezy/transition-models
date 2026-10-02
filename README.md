# transition-models

개발·검사·중단 후 재개·Mac 이관: [유지보수 안내](docs/MAINTENANCE.md).
기본 검사 명령은 `uv run --frozen python scripts/check_project.py`입니다.

> **MLB P0 — 2026-09-22:** 투구 ID 322건을 공식 경기 feed와 대조하고, 실제 운영 모델을
> 수동 입력 화면에 연결했습니다. `uv run --frozen python scripts/59_serve_manual_demo.py
> --with-example-video`로 실행한 뒤 Chrome에서 `http://127.0.0.1:8770`을 엽니다.
> 기존 운영 모델 파일이 필요합니다. 자동 영상 인식·목표 위치 추천·독립 파울 확률은 아직
> 구현 전입니다. [실행 안내와 남은 작업](docs/MLB_P0.md) ·
> [Codex/Claude 인계 기록](docs/MLB_P0_HANDOFF.md) · [입출력 규약](docs/PREPITCH_CONTRACT.md)

> **현재 결과 — 2026-09-21:** 기준선 복구와 운영 모델 9개 학습, 독립 확률 보정,
> 정책 평가, 시연을 완료했습니다. 운영 MLP의 CE는 경험적 기준선 1.2874 → 1.2743입니다.
> 다만 정책 실점 차이의 신뢰구간이 0을 포함해 **실점 개선은 입증하지 못했습니다**.
> [최종 검증 보고서](docs/OPERATIONAL_VALIDATION_2026-09-21.md) ·
> [검증 시연](docs/results/operational_20260921/demo.html) ·
> [정정한 발표 구성](docs/presentation_slides.md)

> **2026-09-21 정정:** 과거 77d 10-class 실험은 입력과 정답의 순서가 달랐습니다.
> 아래 Phase 9~10 표는 역사적 기록이며, collapse·Arsenal +26.5pp·MDP 최선 주장의 근거로
> 사용하면 안 됩니다. 같은 투구로 재학습한 77d MLP CE는 **67.67%, CE 0.8517**,
> 135d MLP CE는 **67.60%, CE 0.8546**입니다(각 seed 42, 관측된 투구 특징 사용).
> [수정·재현 결과와 운영 한계](docs/ALIGNMENT_REPAIR_2026-09-21.md)를 먼저 확인하세요.

SmartPitch MDP의 전이확률(transition probability) 추정 모델 3가지를 비교하는 프로젝트.

## Models

### Phase 6 논문 Replica (Track A)

| | Model A (Baseline) | Model B (Otremba 2022 MLP) | Model C (MIT Sloan 2025 Transformer) |
|---|---|---|---|
| **Input** | 경험적 lookup | 77-dim 단일 벡터 | 87-dim × 400 시퀀스 |
| **Output** | 4-class | 4-class (B/S/F/InPlay) | 24-dim (10+9+5 multi-task) |
| **Architecture** | Majority prior | 2-layer MLP, 128 units | 12-layer Encoder, sub-token masking |
| **Parameters** | — | 27,012 | 9,659,672 |
| **Top-1** | 35.6% | 60.9% | 67.2% |
| **Reference** | Internal | Otremba 2022 | MIT Sloan 2025 |

### Phase 9 아키텍처 사다리 (Track B) — 과거 결과, 정렬 오류로 비교 철회

| 모델 | Input | Top-1 | Macro-F1 | MDP 호환 |
|------|-------|-------|----------|---------|
| LR (77d) | 단일 77d | 41.1%† | 5.9% | ✅ |
| LightGBM (77d) | 단일 77d | 13.0%‡ | 7.2% | ✅ |
| MLP 10-class (77d) | 단일 77d | 41.1%† | 5.8% | ✅ |
| RNN (LSTM, 87d×400) | 시퀀스 | 66.9% | 28.8% | ❌ |
| Transformer (87d×400) | 시퀀스 | 67.2% | 30.1% | ❌ |

† Strike majority collapse  ‡ 역방향 collapse (균등 예측)

### Phase 9.5 (Track C) — 과거 135-dim Arsenal MLP 결과

| 모델 | Input | Top-1 | MDP 호환 | 권장 |
|------|-------|-------|---------|------|
| **TransitionModelMLP10** | **135d (77d+arsenal 58d)** | **67.6%** | 입력 형식 호환 | 과거 모델, 권장 철회 |
| LR 135d | 135d | 62.4% | ✅ | |
| LightGBM 135d | 135d | 67.3% | ✅ | |

### Phase 10 Hybrid Sequence (Track C 확장)

| 모델 | Input | Top-1 | MDP 호환 |
|------|-------|-------|---------|
| RNN Hybrid (drop) | 시퀀스 + static 58d | 67.2% | ❌ |
| Transformer Hybrid (drop) | 시퀀스 + static 58d | 66.8% | ❌ |

## Data

- **Source**: MLB Statcast (pybaseball)
- **Seasons**: 2022, 2023, 2024 (3시즌, v3 기준)
- **Total pitches**: ~2.2M (정제 후 ~1.85M)
- **Split**: Train 1,494,188 (2022+2023) / Val 385,320 (2024 3-6월) / Test 353,776 (2024 7월+)
- **Sequences (Model C)**: Train 150,957 / Val 25,077 / Test 22,127 (stride=8, lazy loading)

> v3 업데이트 상세: [docs/UPDATE_V3_3SEASON.md](docs/UPDATE_V3_3SEASON.md)

## Quick Start

```bash
# 의존성 설치
uv sync

# PyTorch + CUDA 확인
uv run python scripts/00_sanity_check.py

# 데이터 다운로드 (테스트: 1주일치)
uv run python scripts/01_download_data.py --years 2024 --test-mode

# 데이터 다운로드 (전체: 3시즌, ~3시간)
uv run python scripts/01_download_data.py --years 2022 2023 2024

# 전처리 (3시즌, lazy loading 방식)
uv run python scripts/04_preprocess.py --years 2022 2023 2024

# 테스트 실행
uv run pytest

# Model B sanity check
uv run python scripts/05_sanity_check_model_b.py

# Model C sanity check
uv run python scripts/06_sanity_check_model_c.py
```

## Inference (DQN/MDP 팀용)

### 과거 API: TransitionModelMLP10 (기존 실험 재현 전용)

아래 checkpoint는 새 운영 평가 모델이 아닙니다. 투구 전 추천에는
[운영 검증 보고서](docs/OPERATIONAL_VALIDATION_2026-09-21.md)와
`scripts/57_recommend_operational.py`를 사용하세요. 입력 차원이 135로 같아도 특징 의미가 다릅니다.

```python
import json
import numpy as np
from src.inference import TransitionModelMLP10, build_135dim_feature

model = TransitionModelMLP10()      # 자동 checkpoint 로드 (model_b3_focal_135dim_10cls_best.pt)

with open("outputs/arsenal_by_pitcher_cluster.json", encoding="utf-8") as f:
    arsenal = json.load(f)

base_77 = np.zeros(77, dtype=np.float32)          # build_model_b_feature() 결과
feat = build_135dim_feature(base_77, arsenal, pitcher_cluster=2)  # 0-3
probs = model.predict(feat)                        # (10,) — Ball/Strike/.../HitByPitch
```

rl-agent 통합 가이드: [docs/handoff_to_rl_agent.md](docs/handoff_to_rl_agent.md)

### Model C (Transformer, 시퀀스 기반)

```python
from src.inference import TransitionModelC

model = TransitionModelC()          # 자동 checkpoint 로드
result = model.predict(sequence)    # sequence: (400, 87) numpy
probs = result["pitch_result"]      # (10,) - 10-class 확률
```

자세한 사용법: [docs/INFERENCE_GUIDE.md](docs/INFERENCE_GUIDE.md)

데모 실행:

```bash
uv run python scripts/11_inference_demo.py
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
tests/          121 pytest tests (Phase 10 완료 기준)
```

## Intent (catcher setup) module v0 — branch `feature/intent-v0`

동료(Pitcheezy) 작업 지시서 [docs/INTENT_V0_WORK_ORDER.md](docs/INTENT_V0_WORK_ORDER.md)의 M0·M1 구현이다.
포수 셋업(미트 위치)은 **의도의 대리값**이며(`is_intent_proxy=true`), 포수 의도를 확인한 값이 아니다.

```bash
# M1: 경기 747139의 판단 프레임 297구 → IntentEstimate v1 JSONL (한 줄 = 한 투구)
uv run --frozen python -m intent.run --game 747139 --out intent_747139.jsonl
# 로컬 프레임 바이트까지 다시 확인하려면 (프레임이 있는 체크아웃을 지정)
uv run --frozen python -m intent.run --game 747139 --out intent_747139.jsonl --frames-root <checkout> --verify-frames
uv run --frozen python -m pytest tests/test_intent_v0.py -q
```

- 입력: 고정 수동 timing(`docs/results/mlb_p0/game_747139_timing.json`)과 점 파일
  `docs/results/mlb_p0/game_747139_intent_points_v0.json`(`method.kind=assistant_visual_estimate`:
  Claude Code 워크플로 에이전트가 2배 확대 crop 격자에서 미트 중심·홈플레이트 네 모서리를 읽어 적은 값, 셋업 미트 좌표는 사람 검토 없음).
- 출력: `docs/results/mlb_p0/game_747139_intent_v0.jsonl`과 `.run.json`(건수·소요 시간·주의 사항). 모든 줄이 `intent.schema.validate_intent_estimate`를 통과한다.
  `review_status`는 항상 `unreviewed`, `accuracy_estimate`는 측정 전이라 `null`이다.
- 좌표 홉(M2, 2026-10-01): `image_pixels` → `annotated_image_zone` v1(플레이트 **앞선**에 고정한 유사변환: u = 앞선 폭 단위 가로 위치, v = 지면선 위 높이;
  카메라 롤·타석별 배율은 M1 모서리에서 합산) → `plate_feet` v0(상수 3×3 아핀: x = −(17/12)(u−0.5), z = (17/12)·v/cos θ − d0·tan θ;
  `x_convention=statcast_plate_x_catcher_view`, 카메라 틸트 θ = 5.84°(타자석 6 ft 기준선), 공칭 미트 깊이 d0 = 2.5 ft). 측정 방법·검사·한계는
  [docs/INTENT_V0_M2_NOTES.md](docs/INTENT_V0_M2_NOTES.md), 수치는 `docs/results/mlb_p0/game_747139_intent_plate_calibration_v0.json`(`rms_error_feet`,
  `human_verified_count`) — 판독은 에이전트 시각 추정이고, 포구 프레임 19구의 공 위치는 2026-10-02 소유자가 몽타주로 확인했다(`rms_error_feet` 0.277 ft, 개발 경기 안의 값). 앞선 모서리가 없는 추정 프레임은 `image_pixels`에서 멈추고
  `blocked_by=no_image_plane_calibration`으로 남는다. `plate_feet`까지 간 줄은 `blocked_by=no_batter_zone_bounds`(서비스의 다음 좌표계 zone9에 필요한 타자 존 경계가 없음)이다.
- 계약 조정(2026-10-02, 서비스 쪽 요청): `evidence.frame_index`는 원본 영상 프레임 번호(시각으로 뽑은 프레임은 `round(frame_time × 60000/1001)`), `points.plate_feet`의 키는 Statcast와 같은 `x`/`z`, 멈춘 깊이마다 `blocked_by` 이름을 둔다. 서비스 쪽 `validate_intent_estimate`(SongRoute/pitcheezy 8771c06)로 297줄 전부 통과를 확인했다.
  ```bash
  uv run --frozen python -m intent.calibrate --game 747139   # readings json → calibration json
  ```
- 사람 라벨(M3 준비, 2026-10-02): 아래 첫 명령이 판단 프레임 40장(에이전트 추정 32 + 기권 8, 고르게 분산)을 넣은 라벨링 HTML을 `outputs/intent_label/`(git 제외)에 만든다.
  브라우저로 열어 미트 중심과 플레이트 앞선 양 끝을 클릭하고 JSON을 내려받는다. 에이전트 표시는 보이지 않는다. 두 번째 명령이 라벨을 커밋용 파일로 옮기고 에이전트 판독과 비교한다.
  ```bash
  uv run --frozen python -m intent.label_pack --game 747139 --frames-root <프레임이 있는 체크아웃> --sample 40 --out outputs/intent_label/game_747139_pack.html
  uv run --frozen python -m intent.human_labels --game 747139 --labels <내려받은 JSON>
  ```
- **영상 권리**: 프레임은 MLB.com 공개 영상에서 로컬 `outputs/frames/`에만 추출했고 저장소에는 넣지 않는다(좌표·해시만 커밋).
  프레임·crop·영상 파일을 공개 저장소나 산출물에 넣지 않으며, 대량 수집·공개 범위는 M4에서 별도로 합의한다.

## Daily Memo

> 팀원 데일리 메모. 날짜와 이름을 적고, 오늘 한 일/배운 것/이슈를 자유롭게 기록.

| 날짜 | 작성자 | 내용 |
|------|--------|------|
| 2026-05-27 | 조현준 | **Phase 10: 135-dim Context를 전 모델에 확장 + Hybrid Sequence 학습 완료**<br><br>**한 일**<br>- Phase 10.1: LR/LightGBM 135d 10-class 학습 — LR **62.4%** (+21.3pp), LightGBM **67.3%** (+54.3pp, 역방향 collapse 탈출)<br>- Phase 10.1: LR/LightGBM 135d 4-class 학습 — 56.3% / 60.9% (4-class 포화 확인, 135d 추가 효과 없음)<br>- Phase 10.2: `17_evaluate_all_10cls.py` 에 7개 신규 모델 추가 (graceful skip), `baseline_master_comparison.json` G1~G6' 통합<br>- Phase 10.3: `30_align_static58_for_sequence.py` 구현 — static_58_{train,val,test}.npy 생성 (99.9% 매칭)<br>- Phase 10.3: `PitchSequenceDatasetHybrid` 추가 (drop_missing_static 옵션), `PitchRNNHybrid` 모델 구현<br>- Phase 10.3: RNN Hybrid drop=True **67.2%** (1.5h) / drop=False **67.1%** (G5 fair compare)<br>- Phase 10.4: `PitchTransformer`에 `static_dim` 인자 추가 (역호환 유지)<br>- Phase 10.4: Transformer Hybrid drop=True **66.8%** (torch.compile Triton 우회 후 4.2h 학습) / drop=False **67.1%**<br>- 121 tests 전부 통과 확인 후 커밋·푸시 (`9bdb3b7`, LFS 86MB 포함)<br>- 논리 오류 5건 수정 커밋 (`1c10ac5`): CLAUDE.md 비교표 오기, 중복 섹션, handoff 코드 스켈레톤 버그, RNN 스크립트 Windows 안전장치, Adam→AdamW<br><br>**배운 것**<br>- **Context = Architecture-agnostic**: iid 모델에서 context 58d 추가만으로 41%→67%. 모델 복잡도보다 "투수 맥락 유무"가 10-class 분류의 결정적 인자<br>- **Sequence 모델은 static context 불필요**: RNN/Transformer는 400-pitch history로 arsenal을 이미 내재적으로 학습 → static 추가 효과 없음(+0.3pp / -0.4pp)<br>- **torch.compile + Triton on Windows**: `mode="reduce-overhead"`는 Triton 필요. `torch._dynamo.config.suppress_errors = True`로 eager fallback 강제. `try/except`는 첫 forward pass 오류를 잡지 못함<br>- **Python 함수 스코프**: `import x.y`를 함수 내부에서 쓰면 함수 전체에서 `x`가 local binding → UnboundLocalError. 모듈 레벨로 이동 필요<br><br>**이슈**<br>- Transformer Hybrid torch.compile BackendCompilerFailed → suppress_errors로 해결 (eager mode, 성능 손실 없음)<br>- Single/HR 0% 문제 미해결 (타자 arsenal feature 없음, Future Work) |
| 2026-05-25 | 조현준 | **Phase 9.5: MDP 호환 10-class 돌파 — 135-dim Arsenal MLP ✅**<br><br>**한 일**<br>- handoff_v1.parquet 분석 (`12_handoff_v1_analysis.py`, `06_handoff_v1_compat.ipynb`) — UMAP 5d, count_cluster_id, arsenal_func 32d, arsenal_moment 20d 58dim 추출, 100% 매칭<br>- `25_extract_arsenal_by_cluster.py`: pitcher 2,007명 → 4클러스터 매핑 + arsenal 벡터 추출 → `arsenal_by_pitcher_cluster.json`<br>- `21_preprocess_135dim.py`: 77d + 58d = 135d 벡터 생성, scaler_new58.pkl fit<br>- `24_train_mlp_135dim_10cls_focal.py`: MLP 135→128→128→10, Focal Loss(γ=2.0), epoch 25 → **Top-1 67.6%** (77d 41.1%에서 +26.5pp, MDP 호환!)<br>- `TransitionModelMLP10` 클래스 추가 (src/inference/transition_model.py)<br>- `build_135dim_feature()` 추가 (UMAP 0-fill, pitcher_cluster/pitcher_id lookup)<br>- docs/handoff_to_rl_agent.md, docs/rl_agent_teammate_guide.md 작성<br>- tests/test_inference.py에 MLP10·build_135dim_feature 테스트 추가<br><br>**배운 것**<br>- **77-dim collapse의 진짜 원인**: feature 수 부족이 아니라 "투수 맥락(pitcher context)" 부재. arsenal 58d로 완전히 해소<br>- **Arsenal이 시퀀스를 근사**: 400-pitch history 없이도 투수 레퍼토리 통계로 동일 분리 가능 → MDP 호환 달성<br>- **Focal Loss의 효과**: Walk 85.9%, Strikeout 19.5%, FieldOut 7.3%로 희소 클래스 개선. 단타-홈런은 타자 맥락 없어 0% 유지<br>- **UMAP 0-fill 전략**: StandardScaler 기준 0 = 학습 데이터 평균 → "평균적 투구 메카닉"으로 합리적 근사<br><br>**이슈**<br>- Single/Double/Triple/HR 여전히 0% (타자 arsenal feature 부재 — Future Work)<br>- UMAP 5d 추론 시 0-fill 영향 미정량화 (Option C ablation 미실시) |
| 2026-05-23 | 조현준 | **Phase 9: 발표 피드백 반영 — 두 그룹 비교 (10-class 아키텍처 사다리 + 4-class MDP)**<br><br>**한 일**<br>- scripts/13: LR 10-class — Top-1 41.1% (Strike majority collapse, CE 1.614)<br>- scripts/14: LightGBM 10-class — Top-1 13.0% (역방향 collapse, inverse-freq 과보정, CE 2.087)<br>- scripts/15: MLP 10-class — Top-1 41.1% (7 epoch early stop, collapse)<br>- scripts/16: RNN (LSTM 2-layer) 10-class — Top-1 66.9%, Macro-F1 28.8%, CE 0.873 (정상 학습!)<br>- scripts/18-19: LR/LightGBM 4-class — 56.3% / 60.8% (정상, 4-class 분포 균등)<br>- scripts/17,20: 통합 평가 + JSON 생성 (`all_models_comparison_10cls/4cls.json`)<br>- notebooks/06-11: 각 모델별 탐색 + 종합 비교 + MDP 호환성 분석<br><br>**배운 것**<br>- **Macro-F1의 필요성**: Top-1 41.1%는 "나름 성능 있어 보임"이지만 Macro-F1 5.8-5.9% → random classifier 이하. Strike 다수클래스만 예측하는 trivial model 탐지<br>- **10-class i.i.d. collapse 구조 분석**: (a) balancing 미적용 → Strike/Ball collapse (b) inverse-freq balancing → 반대 방향 collapse (균등 예측). 어떤 보정도 feature 부재를 극복 불가<br>- **Sequence context의 결정적 역할**: RNN 66.9% → 400-pitch history 하나만으로 41%→67% 점프. 투구 맥락 정보의 가치 정량적 입증<br>- **MDP/DQN 호환성**: sequence 모델은 pitch selection 전 필요한 400-pitch history 확보 불가 → 실시간 inference 부적합<br><br>**이슈**<br>- 10-class i.i.d. 모델 전체 collapse → 77-dim feature 자체가 single pitch에 너무 적은 context 포함 → Phase 9.5에서 해결 |
| 2026-05-14 | 조현준 | **Phase 8: 3시즌 데이터 확장 + Model B/C 재학습 완료**<br><br>**한 일**<br>- 2022 Statcast 데이터 다운로드 (775,330 pitches) 및 정합성 검증 (FT=0, spin_rate diff=10.4 RPM, 컬럼 118개 완전 일치)<br>- `sac_bunt_double_play` 이벤트 발견 (2022 신규) → FIELD_OUT 매핑 추가 + NaN guard 수정<br>- `split_by_season(train_years=[...])` 파라미터화 + `04_preprocess.py` argparse 추가<br>- Model B v2 (3시즌) 재학습: 60.8% → **60.9%**, CE 0.876 → 0.872, 11분<br>- Model C v3 (3시즌) 재학습: 66.7% → **67.2%**, CE 0.880 → 0.868, ~10시간<br>- 3시즌 evaluation 저장 (evaluation_b/c_3season.npz), 노트북 00/04/05 업데이트<br>- docs/UPDATE_V3_3SEASON.md 작성 (팀원용 업데이트 가이드)<br><br>**배운 것**<br>- Sequence model이 데이터 양 효과를 5배 더 활용 (Model C +0.5pp vs Model B +0.1pp)<br>- Strikeout/FieldOut 소수 클래스 3-4pp 향상, 그러나 Single-HR 0%는 여전 (class imbalance 한계)<br>- 데이터 확장 전 정합성 검증 (FT 여부, spin_rate 분포, 컬럼 일치)이 핵심<br><br>**이슈**<br>- Class imbalance 근본 해결 미완료 (weighted loss / focal loss 필요) |
| 2025-05-05 | 조현준 | 나도 어린이라 어린이날을 즐김 |
| 2025-05-06 | 조현준 | **transition-models 프로젝트 시작 (Phase 1~3.4)**<br><br>**한 일**<br>- 졸업작품용 별도 repo `Pitcheezy/transition-models` 세팅 (uv, pyproject.toml, VS Code, Claude Code 통합)<br>- Statcast 2023-2024 데이터 다운로드 (1,534,286 pitches, 198MB Parquet)<br>- 데이터 탐색 노트북 작성 (9셀, 한국어 주석, 8 deprecated 컬럼 식별, 400+ pitches 타자 586명 확인)<br>- Feature 매핑 모듈 구현 (`src/data/features.py`): 4-class (Otremba 2022) 100% 매핑, 10-class (MIT Sloan 2025) 99.96% 매핑<br>- 전처리 파이프라인 + PyTorch Dataset 1차 구현 (`preprocess.py`, `dataset.py`)<br>- 87차원 Model C vector / 77차원 Model B vector 정의<br>- Train/Val/Test 시즌 기반 분할 (749K / 385K / 354K, 날짜 겹침 없음)<br>- Sub-token masking 구현 + 검증<br>- 단위 테스트 54개 작성 (모두 통과)<br><br>**배운 것**<br>- Statcast description vs events 컬럼의 우선순위 매핑 (events 우선, description fallback)<br>- StandardScaler는 train에만 fit하고 val/test는 transform만 적용해야 data leakage 방지<br>- Sub-token masking은 마지막 pitch의 outcome features만 0 처리해야 함 (직전 399개는 보존)<br><br>**이슈**<br>- stride=1 (논문 그대로)로 시퀀스 미리 만들면 약 521K 시퀀스 × 400 × 87 × 4B ≈ **72GB 메모리 필요** → Mac Mini OOM<br>- 임시방편으로 stride=50 사용 (시퀀스 10K개로 축소, 데이터 1/49 수준) → 다음 날 해결 예정 |
| 2025-05-07 | 조현준 | **Lazy Loading 리팩토링 + Phase 4 모델 구현 완료**<br><br>**한 일**<br>- **Lazy Loading 패턴으로 데이터 파이프라인 재구축**: 시퀀스를 미리 만들지 않고 (N, 87) 벡터를 .npy로 저장 후 `Dataset.__getitem__`에서 O(1) numpy slice로 즉석 생성<br>- 결과: stride=1 사용 가능, 시퀀스 10,668 → **521,680개 (49배)**, 디스크 3.2GB → 1GB, 메모리 72GB → 1GB<br>- Phase 4.1: `TransitionModel` ABC 인터페이스 (forward, predict_proba, num_classes, model_name)<br>- Phase 4.2: **OtrembaMLP** 구현 (77→128→128→4, 27,012 params), MPS sanity check 통과<br>- Phase 4.3: **PitchTransformer** 구현 (87×400 → embed(256) → 12-layer Encoder → last-token + last-pitch residual → 24-dim multi-task head, 9.7M params)<br>- 단위 테스트 추가 (총 91개, 모두 통과)<br>- 커밋 4개 추가 (총 10개)<br><br>**배운 것**<br>- **Lazy Loading 패턴**: 메모리 한계 우회의 표준 PyTorch 패턴. ImageNet, GPT 학습에서도 동일하게 사용. 전처리 시 가능한 데이터 변환을 미리 해두고 (.npy, memory-mappable), `__getitem__`에서는 slice만 하면 빠르고 메모리 효율적<br>- **Last-pitch residual connection**: Transformer encoder를 거치며 마지막 pitch 정보가 다른 pitches와 섞이는 걸 방지하기 위해 raw 87차원을 다시 projection해서 concat하는 트릭. 논문의 핵심 디자인<br>- 12-layer Transformer (d_model=256, 8 heads, ff=1024)는 약 9.7M params로 예상보다 큼. 본격 학습은 GPU 필요<br><br>**이슈/다음 작업**<br>- Mac MPS로는 본격 학습 비현실적 (Model C 1 epoch ≈ 30분, 30 epochs ≈ 15시간)<br>- 학습 환경 결정 완료: **HP OMEN Transcend 16 (RTX 4050/4060/4070)**으로 진행 예정<br>- 내일 학교에서 노트북 GPU 정확히 확인 (`nvidia-smi`) 후 Phase 5 (training loop + W&B + 본격 학습) 시작 |
| 2026-05-08 | 조현준 | **Phase 5 + Phase 6 완료 - 학교 RTX 4070 환경에서 본격 학습 + 평가 + 비교 노트북**<br><br>**한 일**<br>- Mac → Windows (HP OMEN Transcend 16, RTX 4070 8GB) 환경 이전: PyTorch CUDA 셋업 (pyproject.toml [tool.uv.sources]에 cu124 인덱스 추가), `get_device()` multi-platform helper 추가 (CUDA → MPS → CPU)<br>- Phase 5.1~5.4: Training loop + W&B integration + Sanity check 완료 (TrainingConfig, AdamW + CosineAnnealingLR, multi-task loss, early stopping patience=5, checkpoint best+last). 4 unit tests + 두 sanity training 통과<br>- **Model B 본격 학습**: 749K samples × max 200 epochs (early stopped epoch 20, best epoch 10), best val_loss 0.873, val_acc **60.6%** (baseline 35.6% 대비 **+25pp**), 8분 소요. W&B run: bspnzo7m<br>- 노트북 02, 03, 04 작성 (Model A baseline + Model B/C walkthrough, 한국어 markdown + matplotlib 시각화, sub-token masking 시각화 포함)<br>- **Model C 시도 1 (실패)**: stride=1로 30 epochs 시도 → 1 epoch에 76분 → 30 epochs = 38시간 예상 → KeyboardInterrupt로 중단. Epoch 1 결과 train=1.95, val=1.87 (학습 자체는 잘 됨, 시간만 문제)<br>- **Stride 최적화 (8배 단축)**: stride=1 → stride=8로 데이터 재처리 (sequences 521K → 65K), 학습 시간 38h → 5h. Architecture는 그대로 유지 (sequence_length=400)<br>- **Model C 본격 학습**: 65K sequences × 30 epochs (full, early stopping 안 됨), best val_loss 1.833 (epoch 29), val pr_acc **67.1%**, val hl_acc 37.4%, 4시간 53분 소요. W&B run: nawthn1p<br>- 한글 폰트 깨짐 수정: Windows에서 matplotlib 한글 □□□ → Malgun Gothic 폰트 명시 (03/04 노트북)<br>- 노트북 00 (project_journey) 신규 작성: Day 1 + Day 2 진행 일지 + 시각화 (메모리 비교, GPU 성능, Model B 결과, Stride 효과) + 트러블슈팅 + 회고<br>- **Phase 6 평가 (test set)**: scripts/10_evaluate_models.py로 Model B + Model C + baseline 평가 → outputs/evaluation_b.npz, evaluation_c.npz 저장<br>  - Model B test top-1: **60.8%** (CE 0.876, top-3 96.6%)<br>  - Model C test top-1 (Pitch Result, 10-class): **66.7%** (CE 0.880, top-3 94.6%) — **더 어려운 10-class에서 Model B 4-class보다 높음**<br>  - Per-class accuracy 정량 분석<br>- 노트북 04에 Model C 결과 채우기 (TODO → 실제 결과)<br>- 노트북 05 (comparison_results) 신규 작성: Model A baseline / Model B (MLP) / Model C (Transformer) 3-way 비교, top-1 / CE / per-class / confusion matrix 시각화, 논문 결과 비교 (Model B +8pp), 결론<br><br>**배운 것**<br>- **Architecture가 결정적**: Model C가 더 어려운 10-class 문제 (66.7%)에서 Model B의 4-class (60.8%)보다 더 높은 정확도. Sequence + Transformer의 효과를 정량적으로 입증<br>- **Stride trade-off**: stride=1은 메모리뿐만 아니라 **시간**도 큰 문제 (38h). stride=8은 데이터 다양성 ↑, 중복 ↓, 학습 시간 8배 ↓ — sweet spot<br>- **Class Imbalance 영향 정량적 발견**: 다수 클래스 (Ball/Strike/Walk) 80%+, 소수 클래스 (Single/Double/Triple/HomeRun) **0%** — 무처리 결정의 결과를 정량적으로 발견. 향후 weighted loss 또는 focal loss 필요<br>- **PyTorch CUDA + uv**: 첫 uv sync 시 PyTorch CPU 버전 자동 설치됨. pyproject.toml의 [tool.uv.sources] + [[tool.uv.index]]로 platform별 PyTorch 인덱스 분리하면 깔끔하게 해결<br>- **Multi-platform 추상화의 가치**: get_device() helper 하나로 Mac MPS / Windows CUDA / CPU 코드 통합. 일찍 만들어두면 환경 이전 시 큰 도움<br>- **W&B의 강력함**: 학습 진행 중에도 폰으로 loss curve 모니터링 가능. 발표 자료로 바로 사용 가능한 그래프 자동 생성<br>- **Sanity check의 가치**: 64 sequences × 5 epochs로 학습 동작 미리 검증. 본격 학습 전 자신감 확보<br><br>**이슈/다음 작업**<br>- Class imbalance 처리 (Triple/HR 0% accuracy 해결): weighted loss / focal loss / weighted random sampler 도입<br>- Continuous regression target 실제 구현 (현재 placeholder 0)<br>- Model A wrapper 구현 (실제 SmartPitch 통합)<br>- Data 확장 (2018-2022 추가 후 재학습)<br>- Ablation study (sub-token mask, last-pitch residual 효과 분리 검증)<br>- 발표 슬라이드 자료 작성 (노트북 05 활용) |

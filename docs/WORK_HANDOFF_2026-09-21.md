# 다른 컴퓨터에서 이어갈 작업 — 2026-09-21 검토 인수인계

> **최종 상태:** Windows에서 정렬 복구, 3-seed 반복, 운영 모델 9개 학습, 독립 보정,
> 정책 평가, 문서·시연 정리를 실행했다. [최종 보고서](OPERATIONAL_VALIDATION_2026-09-21.md)를 읽는다.
> 정책 비용 차이는 −0.0862점/100회, 95% CI [−0.4046,+0.2304]로 개선 입증은 미달성이다.
> 아래 검토 기록의 “수정·재학습을 하지 않았다” 및 할 일 목록은 최초 시점 기록이다.
> 소스·작은 보고서는 Git으로 이관하고 대형 데이터·checkpoint는 별도로 보관한다.
> [유지보수·Mac 이관 안내](MAINTENANCE.md)를 따르며 옛 Windows 경로를 직접 수정할 필요는 없다.

이 파일은 transition-models 프로젝트 평가 대화의 작업용 요약이다. 대화 전체의 내보내기 파일은 아니다.
검토 당시 Git HEAD: `fc7d647`. 이 검토에서는 코드 수정이나 재학습을 하지 않았다.
확인된 문제를 재현하고 수정하는 것이 다음 작업이다. 기존 README/AGENTS.md의 연구 결론은 아래 검증 결과와 대조해야 한다.

## 새 대화에 입력할 요청

> AGENTS.md와 docs/OPERATIONAL_VALIDATION_2026-09-21.md를 읽고 완료된 작업을 중복 실행하지 마.
> 기준선 복구·운영 검증·시연은 완료됐고, 정책 실점 개선의 통계적 입증이 남아 있어.
> 새 실험은 별도 미사용 평가 데이터와 사전 계획을 확보해 설계해 줘. 기존 test에 맞춰 정책을 고르지 마.
> 같은 투구 ID에 대한 입력과 정답을 보장하는 검증을 추가하고, LR·LightGBM·MLP 기준 모델을 재학습·평가해 줘.
> 기존 체크포인트와 평가 결과는 별도 이름으로 보존하고, 사용자 변경사항을 덮어쓰지 마.
> 수정된 비교 결과로 기존 주장과 문서를 갱신한 뒤, 아래 우선순위의 나머지 작업을 진행해 줘.

## 확인된 가장 중요한 오류

- `scripts/04_preprocess.py`는 `model_b_{split}.pt`의 77차원 입력을 원래 split 행 순서로 저장한다.
- 같은 스크립트의 `labels_10_{split}.npy`는 Model C를 위해 타자·시간순으로 정렬된 정답이다.
- 다음 스크립트는 서로 다른 순서의 두 파일을 같은 행이라고 간주하고 결합한다.
  - `scripts/13_train_logistic_regression.py`
  - `scripts/14_train_lightgbm.py`
  - `scripts/15_train_mlp_10class.py`
- 따라서 배열 길이 검증만으로는 오류를 탐지할 수 없다. 행 식별자와 정렬을 함께 보존해야 한다.

현재 로컬 test 데이터에서 실제 확인한 결과:

| 검증 | 결과 |
|---|---:|
| 원본 2024 Statcast로 재생성한 Model B 입력 vs 저장 입력 | 완전히 일치 |
| 입력 행의 실제 10분류 정답 vs 기존 로더가 붙인 정답 | 247,918 / 353,776건 불일치 (70.0777%) |
| 기존 로더에서 삼진 정답인데 입력의 스트라이크 수가 2 미만 | 14,494 / 20,818건 |
| 정상 정렬된 135차원 데이터에서 같은 삼진 모순 | 0건 |

재현 방법: `data/raw/2024/statcast_2024.parquet`를 `clean_dataframe`과 `split_by_season`으로 처리한다.
test split에 `build_vectors_batch(..., model="B")`와 `extract_labels_4class >= 0` 필터를 적용하여
저장된 Model B 입력과 일치하는지 확인한다. 같은 행에서 `extract_labels_10class`로 얻은 정답과
`labels_10_test.npy`를 비교한다. 함수는 `src/data/preprocess.py`에 있다.

이 오류 때문에 다음 주장은 현재 입증되지 않았다:

- 77d 모델의 41.1% collapse는 투수 맥락 부재 때문이다.
- Arsenal 58d 추가로 26.5%p 개선했다.
- 위 비교로 아키텍처보다 맥락이 중요함을 입증했다.

135d 모델 자체의 저장된 정확도는 별도로 확인됐지만, 개선 원인은 올바른 기준 모델로 다시 검증해야 한다.
재학습 이후의 성능은 아직 알 수 없다.

## 확률 품질 재계산 결과

같은 353,667개 test 샘플의 저장된 `probs`와 `targets`에서 계산했다.
Brier는 샘플별 클래스 전체 제곱오차 합의 평균이다.
ECE는 최대 예측확률에 대한 15개 동일 폭 구간의 가중 평균 오차다. 클래스별 캘리브레이션을 대체하지 않는다.

| 모델 | Top-1 | CE (약) | Brier | ECE |
|---|---:|---:|---:|---:|
| MLP 135d Focal | 67.6439% | 0.9263 | 0.4809 | 15.0275% |
| MLP 135d CE | 67.4787% | 0.8570 | 0.4404 | 1.0279% |
| MLP 151d CE | 67.5715% | 0.8580 | 0.4398 | 0.4733% |

출처:

- `outputs/evaluation_mlp_135dim_10cls_focal.npz`
- `outputs/evaluation_mlp_135dim_10cls.npz`
- `outputs/evaluation_matchup151_10cls_ce.npz`

Focal 모델의 작은 정확도 이득만으로 전이확률용 최선이라고 할 수 없다.
검증셋에서 모델 선택·확률 보정을 수행하고 별도 평가셋으로 확인해야 한다.
기존 test를 보고 반복 튜닝한 결과는 최종 독립 검증 결과와 구분한다.

## 해석을 수정해야 하는 부분

1. **희소 클래스 recall 0%는 해당 사건의 예측확률 0을 뜻하지 않는다.**
   135d CE 모델의 홈런 recall은 0%지만 평균 홈런 확률은 약 0.7714%, 실제 발생률은 0.8056%다.
   전체 평균이 맞는다는 사실만으로 상황별 정확성까지 보장하지는 않는다.
   `docs/presentation_slides.md`의 장타 위험을 0으로 본다는 설명은 downstream 확률 처리까지 확인하고 수정해야 한다.
2. **MLP 구조 자체가 MDP 적합성을 보장하지 않는다.**
   의사결정 시점에 입력을 만들 수 있는지, 상태·행동·결과의 의미가 맞는지 검증해야 한다.
   시퀀스 모델도 상태에 이력/요약을 포함하는 설계는 가능하지만 비용이 달라진다.
3. **실제 도착 위치와 목표 코스는 다르다.**
   기존 입력은 실제 구속·회전·궤적·plate_x/plate_z/zone을 사용한다.
   투구 전에 평균값·추정값으로 대체한다면 그 동일한 생성 방식으로 평가해야 한다.
4. **타자 특징 151d 실험이 이미 존재한다.**
   `scripts/33_preprocess_matchup151.py`, `scripts/34_train_mlp_matchup151_ce.py`를 확인한다.
   저장 결과에서 Single recall은 약 0.0932%, Double/Triple/HomeRun은 0%였다.
   타자 맥락의 큰 개선 효과나 원인 설명은 아직 입증되지 않았다.
5. Transformer의 continuous loss는 `src/training/train.py`에서 0으로 처리된다.
   24차원 출력 전체가 학습된 완전한 상태 전이 예측이라는 표현은 부정확하다.

## 체크포인트로 확인한 UMAP 0-fill 민감도

다른 입력은 원래 test 값으로 유지하고, [77:82]만 0으로 바꿔 전체 test에서 다시 추론했다.
두 모델 모두 `OtrembaMLP(input_dim=135, hidden_dim=128, n_classes=10, dropout=0.2)`이며 eval 모드였다.

| 모델 | 원래 Top-1 | UMAP 0-fill Top-1 | 원래 CE | 0-fill CE |
|---|---:|---:|---:|---:|
| Focal | 67.6439% | 67.5508% | 0.92633 | 0.92797 |
| CE | 67.4787% | 67.3653% | 0.85701 | 0.85993 |

이는 UMAP만 바꾼 결과다. 물리량 평균 대체, 개별 Arsenal의 클러스터 평균 대체,
전체 handoff 특징 생성 방식까지 검증한 것은 아니다.

## 다음 작업 순서와 완료 기준

1. **기준 모델 복구**: 투구 키 `(game_pk, at_bat_number, pitch_number)`로 데이터 계약을 정하고
   77d 입력과 10분류 정답을 동일 행에서 생성한다. 실제 전처리/로더 연결을 검증하는 테스트를 추가한다.
   세 기준 모델을 재학습하고 135d와 공통 평가 행에서 비교한다.
2. **운영 조건 평가**: 사전 관측 정보, 선택 가능한 행동, 아직 모르는 실제 물리량을 구분한다.
   실제 추론 특징 생성기를 평가에도 사용한다. 상류 Arsenal 통계의 시간 범위도 확인한다.
3. **확률 중심 선정**: CE/Brier, 클래스별 캘리브레이션과 희소 사건 확률을 비교한다.
   보정은 학습과 분리된 검증 데이터에서 수행한다. 반복 seed와 경기 단위 불확실성도 확인한다.
4. **정책 효용 평가**: 경험적 확률 기준선과 학습 모델을 같은 조건에서 비교한다.
   추천 변화, 기대 실점, 추론 비용을 보여 주고 자기 모델 안에서만 평가하는 한계를 피한다.
   RL 통합 저장소의 실제 동작은 이번 검토에서 확인하지 않았다.
5. **문서·시연 갱신**: 새 실험 결과에 따라 README, AGENTS.md의 결과 주장, 발표 문서,
   handoff 문서의 권장 모델과 한계를 일관되게 정리한다.

## 환경과 파일 이관

- 원래 경로: `C:\Users\zpfh1\Projects\transition-models`
- Python 3.12, uv, PyTorch. 새 컴퓨터에서는 가상환경을 새로 만든다.
- 이 파일 외에 코드 변경이나 재학습은 아직 수행하지 않았다.
- 검토 당시 `uv run pytest -q`: **121 passed, 2 skipped**, 65.21초.
- 검토 당시 `ruff check src tests --statistics`: **32건**. 정렬 오류 검증이 스타일 수정보다 우선이다.
- 문서에 설명된 `configs/` 디렉터리는 검토 당시 없었다.
- 기존 사용자 미추적 파일: `scripts/44_draw_mlp10_architecture.py`,
  `scripts/45_draw_mlp10_paper_figure.py`, `scripts/46_draw_project_pipeline_and_roadmap.py`,
  `scripts/47_build_pipeline_roadmap_pptx.mjs`, `_INVALID_GEMINI_DUMMY/TransitionModelMLP193_v1.pth`.
  그대로 보존하고, 이름상 INVALID/DUMMY인 산출물을 검증된 성과로 취급하지 않는다.

Git clone/pull이나 앱의 Git 상태 이관만으로 대형 로컬 데이터까지 준비됐다고 가정하지 않는다.
다음 파일이 새 컴퓨터에 있는지 확인하고 없으면 별도로 복사하거나 재생성한다:

- `data/raw/2022`, `data/raw/2023`, `data/raw/2024`의 Statcast parquet
- `data/processed/`의 model_b PT, vectors/labels NPY, scaler PKL, pitch_types JSON,
  sequence indices/ranges, static58, matchup151 관련 파일
- `outputs/evaluation_*.npz`, `outputs/checkpoints/`, `outputs/arsenal_by_pitcher_cluster.json`
- 135d/151d 재전처리에 필요한 외부 `handoff_v1.parquet` 및 train-only 타자 특징 파일

외부 특징 파일 경로는 스크립트에서 `C:\Users\zpfh1\Projects\data\data\outputs`로
고정되어 있으므로 새 컴퓨터에 맞게 설정 가능하도록 정리해야 한다.
이 인수인계 파일은 로컬에 새로 작성했으며 아직 commit/push하지 않았다.

# 유지보수와 다른 컴퓨터에서 실행하기

현재 실험 결과는 [운영 검증 보고서](OPERATIONAL_VALIDATION_2026-09-21.md)에 있다.
코드 변경과 재실험을 분리하고, 완료된 결과 디렉터리는 보존한다.

## 시작하기

저장소를 받은 뒤 루트에서 실행한다. Python 3.12와 uv를 사용한다.
Mac은 LightGBM용 OpenMP가 필요하면 `brew install libomp`를 실행한다.
기존 checkpoint를 받으려면 Git LFS를 설치하고 `git lfs pull`을 실행한다.

```bash
uv sync --frozen
uv run --frozen python scripts/check_project.py
```

`pywin32`는 Windows에서만 설치된다. SciPy·PyArrow·threadpoolctl은 직접 의존성으로 선언했다.
`uv.lock`을 함께 관리하며, PyTorch는 학습에 사용한 **2.6.0**으로 고정한다.
최초 Mac CI는 기존 lock의 PyTorch 2.11.0으로 Transformer 추론 중 SIGSEGV가 발생했다.
운영체제별 PyTorch 버전 차이를 없애고 같은 테스트를 실행하도록 수정했다.
Windows/Linux는 CUDA 12.4 빌드, Mac은 PyPI 빌드이므로 GPU별 bitwise 일치를 보장하지 않는다.

검사 명령은 지원하는 새 경로의 Ruff 검사/포맷 검사와 전체 pytest를 실행한다.
대형 원본 데이터 없이 실행할 수 있다. 기존 checkpoint를 받지 않은 환경은 관련 추론 테스트를
건너뛸 수 있지만, LFS 포인터 파일만 남아 있으면 모델 로드가 실패할 수 있다.
CI는 Ubuntu와 macOS에서 LFS 파일을 받고 같은 명령을 실행한다.
2026-09-21 유지보수 보완 후 Windows 검사 결과는 **177 passed, 2 skipped**(59.44초)이며,
경로 이관·중단 결과 보존·설정 불일치 거부·하위 평가 무효화 회귀 테스트를 포함한다.
과거 연구 스크립트 전체의 스타일 위반을 한꺼번에 변경한 것은 아니다.

## 지원하는 실행 경로

| 작업 | 진입점 | 구현 |
|---|---|---|
| 과거 정렬 복구 | scripts/48_prepare_aligned_points.py | src/data/point_data.py |
| LR/LGB/MLP 학습 | python -m src.training.point_baselines | src/training/point_baselines.py |
| 운영 특징 생성 | scripts/51_prepare_operational.py | src/data/operational.py |
| 정책 평가용 보조 모델 | scripts/52_train_policy_nuisance.py | 89d 행동 확률, 135d 비용 회귀 |
| 확률 평가·모델 선택 | scripts/53_evaluate_operational.py | src/evaluation/operational_metrics.py |
| 독립 정책 평가 | scripts/54_evaluate_policy.py | src/evaluation/policy_value.py, run_value.py |
| 전체 실험 실행·재개 | scripts/55_run_operational_validation.py | src/utils/pipeline.py |
| 저장된 결과 HTML 시연 | scripts/56_build_validation_demo.py | 외부 서버 없는 단일 HTML |
| 상태 JSON에서 실제 추천 | scripts/57_recommend_operational.py | src/inference/operational.py |

13–15번은 공통 학습기의 호환 진입점이다. 44–47번은 과거 발표 그림 생성 도구이며
기존의 철회된 연구 해석을 재생성할 수 있으므로 현재 발표의 수치 근거로 쓰지 않는다.
`_INVALID_GEMINI_DUMMY/`는 무효 실험 격리 폴더이며 운영에서 불러오지 않는다.

## 긴 실험 실행과 중단 후 재개

```bash
# 처음 실행: 새 디렉터리를 사용
uv run --frozen python scripts/55_run_operational_validation.py --data-dir data/operational_new --run-dir outputs/operational_new --device auto

# 중단 뒤 같은 실험 재개
uv run --frozen python scripts/55_run_operational_validation.py --data-dir data/operational_new --run-dir outputs/operational_new --device auto --resume
```

완료 표식과 필수 산출물이 있는 단계는 건너뛴다. 모델의 seed·차원·손실·데이터 명세가
다르면 기존 완료 결과를 재사용하지 않는다. 미완료 폴더는 같은 위치에
`.interrupted-<id>`로 보존하고 그 단계를 처음부터 다시 실행한다. epoch 단위 재개는 아니다.
데이터를 다시 만들면 모델도 다시 학습하고, 모델이 다시 학습되면 확률 평가→정책→시연을
갱신한다. 교체된 완료 결과는 `.superseded-<id>`로 보존한다. 자동 삭제는 하지 않는다.

코드/특징 정의/실험 조건을 바꾼 비교 실험에는 새 디렉터리를 사용한다.
`--resume`는 동일 실험의 실행 중단 복구용이다. 이미 보관한 과거 수동 실행을 임의로
모두 이어 붙이는 옵션은 아니다. 특히 최초 2026-09-21 보조 모델은 `_v2` 경로이며,
새 실행기는 검증된 특징 수 metadata도 요구한다.

## Mac 또는 다른 경로로 결과 옮기기

Git에는 코드, 문서, 작은 검증 결과와 시연이 들어간다.
아래 데이터/학습 산출물은 기존 Git 제외 규칙에 따라 별도로 옮기거나 재생성한다.

1. `data/operational_20260921_v2/`: 전체 재평가에는 이 폴더 전체가 필요하다.
2. `outputs/operational_20260921/`: 모델별 폴더, `evaluation`, `policy_nuisance_v2`, `policy`.

추천만 실행하려면 데이터 폴더의 `feature_builder.pkl`, `dataset_manifest.json`,
`run_value_model.npz`, 선택된 MLP135 세 폴더의 `manifest.json`/`best.pt`,
`evaluation/probability_report.json`/`empirical.pkl`,
`policy_nuisance_v2/manifest.json`/`propensity.txt`면 된다.
단순 결과 시연은 Git에 들어 있는 `docs/results/operational_20260921/demo.html` 하나로 열린다.

```bash
uv run --frozen python scripts/57_recommend_operational.py --data-dir /Volumes/SSD/operational_data --evaluation-dir /Volumes/SSD/runs/evaluation --nuisance-dir /Volumes/SSD/runs/policy_nuisance_v2 --runs-dir /Volumes/SSD/runs --state-json docs/results/operational_20260921/example_state.json
```

새 선택 결과는 run 이름과 evaluation 기준 상대 경로를 저장한다. 옛 Windows 경로가 들어
있는 JSON도 run 이름을 복원해 evaluation의 형제 폴더에서 찾는다. 위치가 다르면
`--runs-dir`로 지정하므로 JSON을 손으로 고칠 필요가 없다. 프로필 hash와 schema는
계속 검사하므로 차원만 같은 다른 모델을 섞어 쓸 수 없다.

## 변경할 때 지켜야 하는 경계

- 입력·정답·투구 ID·클래스 순서를 같은 산출물로 다룬다. 행 순서를 추측하지 않는다.
- 운영 특징을 바꾸면 학습과 추론의 동일 생성기를 수정하고 schema를 새로 부여한다.
- validation, calibration, test 용도를 유지하고 test로 모델·정책 설정을 선택하지 않는다.
- 새 버그 회귀 테스트를 추가하고 `scripts/check_project.py`를 통과시킨다.
- `docs/results/`의 과거 수치/학습 당시 hash는 증거 기록이다. 코드가 바뀌었다고 덮어쓰지 않는다.
  새 실험 결과는 새 날짜·버전 디렉터리와 보고서에 추가한다.
- 기존 `src/inference/transition_model.py` API와 새 operational API는 서로 다른 특징 정의다.

의존성 변경 시 `pyproject.toml` 수정 → `uv lock` → 검사 → 두 파일을 함께 커밋한다.
원본 자료, `.env`, 캐시, 개별 PC 경로를 새 코드에 하드코딩하지 않는다.

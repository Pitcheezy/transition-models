# H-port2 — 우리 운영 모델의 최소 산출물 경로 이식 확인

2026-10-08. 우리 `feature/intent-v0@ae7db0119125782502d356288d0c5910a3417f26`의 기존
57번 CLI를 사용했다. **명시한 14개 파일을 새 경로에 복사한 뒤, 원본 경로와 이관 경로의
전체 JSON 응답 및 stdout 바이트가 완전히 일치했다.** 숫자 비교 허용오차는 0이며,
후보별 결과 확률의 최대 절대 차이도 0이다.

근거는 [실행 영수증](handoff/operational_relocation_v1.json), 복사 기준은
[기존 외부 자료 목록](handoff/external_artifacts_v1.json)이다. 로컬 영수증 원본은
`LEGACY_PROJECT/outputs/cv_independent_20261008_stage/operational_relocation_v1/receipt.json`이며
SHA256은 `be52c3a333c4f9905e4afc3721a692f72da62fae0e6bb8e7ec9fdf9dd01256c3`이다.
개인 절대경로와 stdout/stderr 원문은 같은 로컬 폴더의 `private/`에 보존했다.
커밋할 영수증에는 경로 별칭, 파일별 크기·SHA, 소스·입력 해시, 실행 환경과 검사 결과만 남긴다.

## 복사한 파일과 실행 의존

디렉터리 전체를 복사하지 않았다. 아래 **14개, 총 8,986,954바이트**만 명시적으로 복사했다.
각 파일의 원본 바이트가 외부 목록의 크기·SHA와 일치하는지 먼저 확인하고, 복사 직후와
두 실행 이후 다시 확인했다. 원본 파일과 명시한 실행 소스는 변경되지 않았다.

| 상대 경로 | 개수 | 역할 |
|---|---:|---|
| `data/operational_20260921_v2/dataset_manifest.json` | 1 | 특징 schema·고정 프로필 SHA |
| `data/operational_20260921_v2/feature_builder.pkl` | 1 | 2022년 고정 프로필·특징 생성기 |
| `data/operational_20260921_v2/run_value_model.npz` | 1 | 결과별 기대 실점 비용 |
| `outputs/operational_20260921/mlp135_seed42/{manifest.json,best.pt}` | 2 | seed42 모델과 학습 명세 |
| `outputs/operational_20260921/mlp135_seed43/{manifest.json,best.pt}` | 2 | seed43 모델과 학습 명세 |
| `outputs/operational_20260921/mlp135_seed44/{manifest.json,best.pt}` | 2 | seed44 모델과 학습 명세 |
| `outputs/operational_20260921/evaluation/probability_report.json` | 1 | 선택 모델·세 run 참조·확률 보정값 |
| `outputs/operational_20260921/evaluation/empirical.pkl` | 1 | 경험적 비교 기준선 |
| `outputs/operational_20260921/policy_nuisance_v2/manifest.json` | 1 | 데이터 호환성·행동 확률 보정값 |
| `outputs/operational_20260921/policy_nuisance_v2/propensity.txt` | 1 | 행동 확률·지원 구종 필터 |
| `outputs/operational_20260921/evaluation/selection.json` | 1 | 선택 근거 보존; 실행은 보고서 안의 `selection`을 읽음 |

직접 실행에 필요한 것은 13개이고 `selection.json`을 근거 보존용으로 추가했다.
모든 seed의 complete 상태·MLP135 정의·데이터 명세 일치, seed42/43/44 목록, 프로필 SHA,
보고서·nuisance의 데이터 명세, 별도 selection과 보고서 selection의 일치를 확인했다.

기존 `OperationalRecommender` 생성자가 이 전체 경로를 읽었다. 세 seed의 확률을 평균한 뒤
저장된 MLP 온도 `1.0022222351524148`을 적용하며, empirical 온도는
`1.0336899602754714`, propensity 온도는 `1.09794610049746`이다.
직접 `OperationalPredictor`의 기본 온도 1.0으로 대체하거나 새로 보정하지 않았다.
세 모델 실행의 근거는 확인한 선택 명세·변경 없는 생성자 소스·CLI 정상 종료의 조합이며,
별도 계측을 위해 모델을 추가 호출하지 않았다.

## 실행 방법과 결과

`CANONICAL_PROJECT`는 위 기준 커밋의 우리 전체 저장소, `CANONICAL_PYTHON`은 그 저장소의
기존 Python 실행파일이다. `LEGACY_PROJECT`는 원본 산출물 저장소,
`RELOCATED_ARTIFACTS`는 신규 출력 폴더 `operational_relocation_v1/artifacts`다.
아래 `ARTIFACT_ROOT`에 원본 별칭과 이관 별칭을 각각 대입하고 실제 로컬 경로로 치환한다.
작업 위치는 `CANONICAL_PROJECT`이며, 입력 파일과 소스·환경은 두 실행에서 같았다.

```text
<CANONICAL_PYTHON> -B <CANONICAL_PROJECT>/scripts/57_recommend_operational.py --data-dir <ARTIFACT_ROOT>/data/operational_20260921_v2 --evaluation-dir <ARTIFACT_ROOT>/outputs/operational_20260921/evaluation --nuisance-dir <ARTIFACT_ROOT>/outputs/operational_20260921/policy_nuisance_v2 --runs-dir <ARTIFACT_ROOT>/outputs/operational_20260921 --state-json <CANONICAL_PROJECT>/docs/results/operational_20260921/example_state.json
```

기존 예제는 투수621242, 2024-09-30, 8회2아웃, 3볼2스트라이크, 2루주자645277,
타자·투수 모두 우측이다. 원본 경로1회와 이관 경로1회만 실행했으며 둘 다 exit0,
stderr0바이트였다. CPU·Torch1 thread를 쓰는 기존 CLI 설정을 유지했다.

- 전체 응답의 키·타입·배열·값을 재귀 비교해 차이0, stdout 바이트도 동일했다.
- 후보9개, 후보마다 결과확률10개가 유한하고 0–1 범위였다. 확률합 검사 허용오차는
  `1e-6`이며 실제 합은 `0.9999999999999999` 또는 `1.0`이었다. 이 유효성 검사 허용오차와
  두 응답의 정확 일치 비교 허용오차0을 구분한다.
- 지원 구종은 FF·SL, 학습 모델과 empirical 추천은 모두 SL, 정책 비중 합은1이었다.
  미지원 구종 비중0, 지원 구종 중 추천, 평가 범위 내 유한 비용을 확인했다.
- `target_location`과 독립 strike/ball/foul 표시는 null을 유지했다.

환경은 Windows11 AMD64, Python3.12.12, torch2.6.0+cu124, NumPy2.4.4, pandas3.0.2,
PyArrow24.0.0, SciPy1.17.1, scikit-learn1.8.0, LightGBM4.6.0이다. 기존 환경을 사용했으며
새 설치는 하지 않았다. 프로세스 전체 경과 시간은 원본51.9733초, 이관34.3820초다.
**한 번씩 순서대로 실행한 시간이며 초기화·OS 캐시 등이 포함돼 이식 전후 속도 비교로 해석하지 않는다.**

최초 준비 시 Git revision 조회가 모델 실행 전에 실패했다. 당시 복사·모델 호출은0회였고
첫 오류의 Git stderr가 보존되지 않아 원인은 미확정이다. 정본 작업 위치에서 별도 읽기 조회가
성공한 뒤 준비를 재개했다. 모델 CLI는 원본·이관 각1회이며 실패 후 모델 재실행은 없었다.
이 준비 이력도 영수증과 로컬 기록에 남겼다.

## 확인 범위

이 결과는 **같은 Windows 컴퓨터·같은 기존 환경·기존 예제1개에서 우리 운영 모델의
명시 산출물 경로 이식이 성립했다는 확인**이다. 우리 모델을 비교·재현 기준으로 보존하는
작업이며, 팀원 모델의 채택·대체 또는 서비스 정본 합의가 아니다.

Mac/MPS·다른 컴퓨터·fresh install, 독립 설치 가능한 완전한 런타임 배포 묶음, 새 예측 정확도,
정책 효용·실점 감소, 확률 재보정, 독립 holdout 평가는 확인하지 않았다. 학습·재평가·네트워크
호출·서버 기동·공개 배포·정본 코드 수정도 하지 않았다. H-port1의 과거
`portable_runtime_verified:false` 기록은 그대로 보존하며 이 제한된 후속 근거와 구분한다.

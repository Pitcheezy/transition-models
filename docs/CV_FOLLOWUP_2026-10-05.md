# CV 후속 개발 진단 — 2026-10-05

이번 작업은 **포수 미트 관측의 신뢰도·시간 근거·재현성을 보강**한다. 팀원의 모델·추천·경기 피드·서비스·화면 구현은 제외했다. 기존 M3 측정을 다시 수행하거나 10/6 시연 JSONL을 변경하지 않았다.

## 담당 경계와 다음 방향

SongRoute/pitcheezy를 읽기 전용으로 확인한 기준은 연구 브랜치 `codex/ml-matrix-execution`의 `813ce61c0621df2559615c23075bfae08a9df78a` 및 `demo/ws-2026`의 `9c3018913780cde2d12db522c2a420a6e283db7c`다. 아래 역할은 저장소 코드·인계 문서와 사용자 확정 내용 기준이며 실제 배포 상태의 확인은 아니다.

| 담당 | 범위 | 우리 쪽 행동 |
|---|---|---|
| 팀원 | 확률 모델·프로필·정책, GUMBO 경기 상태, 추천 API, 관전 UI, 공개 전후 표시 | 재구현하지 않는다. 계약이 바뀌면 입력/출력 의미만 대조한다. |
| 본인 | 영상에서 미트 픽셀 읽기, 플레이트/카메라 변환, 기권, 관측 품질·시간·출처 | 이 문서의 진단과 로컬 도구를 유지한다. |
| 협업 경계 | pitch_id·영상 대응, IntentEstimate v1, x 방향·단위, 자료 전달 | 기존 849843 파일을 유지한다. 새 버전만 커밋·경로·SHA로 전달한다. |

팀원 근거: [UI 연결 지시](https://github.com/SongRoute/pitcheezy/blob/813ce61c0621df2559615c23075bfae08a9df78a/docs/handoffs/UI-setup-display-work-order.md), [라이브 서비스 계획](https://github.com/SongRoute/pitcheezy/blob/813ce61c0621df2559615c23075bfae08a9df78a/docs/handoffs/LIVE-service-plan.md). 본인 범위는 [M0–M4 작업 지시](INTENT_V0_WORK_ORDER.md), [새 관측 규약](CV_OBSERVATION_PROTOCOL_V1.md)을 따른다. 배치 실행기는 M4 준비 도구이며 여러 경기 자동 판독의 완성은 아니다.

## 1. 시간 근거 감사

새 [temporal_audit.py](../intent/temporal_audit.py)는 기존 points·timing·window·scan을 투구 ID로 연결한다. 압축 영상은 URL·fps·선택 프레임 번호/해시/시각까지 대조한다. 원본 이미지 바이트를 다시 보거나 새 주석을 만들지는 않았다.

| 경기 | 기존 관측 행 | AI 출력 / 기권 | 출력 프레임→릴리스 중앙값 | 릴리스 후 프레임을 포함한 제공 창 / 릴리스가 알려진 창 |
|---|---:|---:|---:|---:|
| 747139 | 297 | 233 / 64 | 4.5초 | 창 파일 없음 |
| 849843 | 39 | 27 / 12 | 약 0.05005초 | 39 / 39 |
| 849845 | 57 | 43 / 14 | 약 0.05005초 | 57 / 57 |
| 823407 | 29 | 15 / 14 | 약 0.05005초 | 28 / 28 |

422행 모두 결과의 실제 사용 가능 시점을 기록하지 않아 **투구 전 가용성은 미측정**이다. 0건이 검증됐다는 뜻이지 실시간 성공률 0%를 측정했다는 뜻이 아니다. 제공 창은 실제로 어느 프레임을 읽었는지의 로그가 아니므로, 모든 결과가 투구 후 화면을 사용했다고 단정하지 않는다. 압축 영상은 경기 전체 투구의 무작위 표본도 아니다.

기존 변환은 같은 타석의 폭과 경기 전체 앞선 roll을 모을 수 있다. 현재 프레임까지의 prefix만 쓰는 개발 비교를 추가했다. hop-1만 바꾸고 기존 hop-2는 고정했으며, 이는 새로운 인과적 실시간 파이프라인이 아니다. x 변화 절댓값 최댓값은 747139 0.05754ft(n=153), 849843 0ft(n=27), 849845 0.02151ft(n=43), 823407 0.01502ft(n=15)다. 변화가 0이어도 정보 사용 시점이 검증되는 것은 아니다.

별도 `intent_temporal_trace_v1` 검사는 실제 계측한 동일 시계의 `pitch_identity`, `setup_frame`, `camera_calibration`, `cv_output`과 의존 관계를 받는다. 각 파일 SHA, 출력의 v1 계약·pitch_id·실제 프레임 시각, 의존 setup-frame 이미지 SHA, 근거의 마지막 시각과 사용 가능 시각을 검사한다. 미측정·미래·시계 불일치·누락·순환 의존성은 통과하지 못한다. 이 프로파일에서 setup_frame은 출력 `clip_sha256`가 가리키는 이미지 바이트다. 단순 `pitch_id` JSON을 출력 대신 넣을 수 없다.

이 검사는 **선언한 계측값과 파일의 일관성 검사**다. 측정값의 진실성·시계 동기화를 독립적으로 입증하거나 기존 결과를 실시간 결과로 승격하지 않는다. 라이브 계측기·서비스 연결은 이번에 만들지 않았다.

## 2. 기권과 x 좌표 민감도

[quality_audit.py](../intent/quality_audit.py)는 기존 평가 두 경기 86장을 따로 분석한다. 기존 M3 수치를 다시 계산해 대체하지 않는다.

| 경기 | AI 표시 / 기권 | 사람 표시 / 기권 | 둘 다 표시 | 사람만 표시 |
|---|---:|---:|---:|---:|
| 849845 | 43 / 14 | 56 / 1 | 43 | 13 |
| 823407 | 15 / 14 | 28 / 1 | 15 | 13 |
| 합계(표시 여부 집계만) | 58 / 28 | 84 / 2 | 58 | 26 |

26건은 **표시 여부 불일치이며 정확성은 미판정**이다. 다음 버전에서 resting 미트도 관측할지 등의 지시를 통일하고 사람이 별도로 판정해야 한다. 이 불일치를 오류율이나 개선 가능 수치로 바꾸지 않는다.

기존 공개 x를 먼저 재현한 뒤 폭·중점·미트 위치·roll·pan·tilt·가정 깊이의 한 변수만 바꾼다. 아래는 그중 x 변화 절댓값 중앙값(ft)이다.

| 가정 변화 | 849845 (43구) | 823407 (15구) |
|---|---:|---:|
| 플레이트 폭 +5% | 0.03755 | 0.03504 |
| pan +1도 | 0.04363 | 0.04364 |
| 미트 x +1px | 0.02623 | 0.01840 |
| 가정 깊이 +1ft | 0.01207 | 0 |

이 값은 **입력 가정 변화에 대한 민감도**다. 실제 보정 오차, 물리 정확도, 신뢰구간이 아니다. 823407의 깊이 변화 0은 현행 pan=0 가정에서 나온 식의 성질이며 정확하다는 뜻이 아니다. 823407의 보정 오차는 여전히 미측정이다.

원자료: [시간 감사](results/cv_followup_20261005/temporal_audit_v1.json), [기권·민감도](results/cv_followup_20261005/quality_audit_v1.json). 소스 SHA는 보고서 및 [실행 기록](results/cv_followup_20261005/execution_v1.json)에 남긴다.

## 3. 실행·재개

저장소 루트에서 기존 Python 환경 또는 `uv run --frozen python`으로 실행한다. Windows의 기존 가상환경은 `.venv/Scripts/python.exe`다.

```bash
python -m intent.batch check --plan configs/intent_cv_followup_v1.json --run-dir outputs/cv_batch_audit_v1
python -m intent.batch run --plan configs/intent_cv_followup_v1.json --run-dir outputs/cv_batch_audit_v1
python -m intent.batch resume --plan configs/intent_cv_followup_v1.json --run-dir outputs/cv_batch_audit_v1
```

`run`은 새 디렉토리만 받는다. `resume`은 입력·소스·계획·Python 경로/버전·완료 출력 SHA를 다시 검사하고 성공 작업을 생략한다. 없기로 선언한 선택 파일이 생겨도 거절한다. 실패·중단 작업은 새로운 attempt에 쓰며 이전 로그·산출물·orphan 폴더를 보존한다. OS 잠금으로 같은 run의 중복 실행을 막는다. 순차 실행이며 외부 AI 호출·영상 다운로드는 하지 않는다.

입력이나 코드가 바뀌면 새 run-dir을 사용한다. 다른 컴퓨터에서 같은 로컬 run을 이어 쓰는 도구는 아니며 새 환경에서 새 run을 만든다. SHA는 실행 당시의 정확한 로컬 파일 바이트 기준이다. Git 줄바꿈 변환으로 달라진 소스도 새 실행으로 기록한다. 공유 보고서 JSON은 `.gitattributes`에서 바이트를 보존한다. 다른 드라이브의 새 폴더도 run-dir로 지정할 수 있다. 내부 저장소에서는 `outputs/` 아래 새 폴더만 사용한다.

`manifest.json`은 입력·명시한 의존 소스·러너 SHA와 Python 정보를, `ledger.json`은 작업 상태·attempt·출력 SHA·subprocess 경과 시간을 담는다. 실패 원인은 각 attempt의 stdout/stderr에 남는다. 경과 시간은 **이 JSON 감사 작업의 subprocess 실행 시간**이며 미트 판독 전체 시간이나 라이브 영상 지연이 아니다.

이 실행기는 신뢰하는 로컬 Python 프로그램을 위한 재개 도구이며 코드 실행 샌드박스가 아니다. 실제 사용 파일·import 의존성은 계획에 모두 선언해야 한다. 설치 패키지 전체 상태나 외부 서비스 상태는 자동 고정하지 않는다. 이 계획에는 `uv.lock`·`pyproject.toml`도 포함한다.

개별 실행:

```bash
python -m intent.temporal_audit audit --games 747139 849843 849845 823407 --out outputs/cv_followup_new/temporal.json
python -m intent.quality_audit --games 849845 823407 --out outputs/cv_followup_new/quality.json
python -m intent.temporal_audit check --trace path/to/measured_trace.json --artifact-root path/to/bound_artifacts
```

출력은 기존 파일을 덮어쓰지 않는다. trace 예시는 합성 테스트에만 있으며 현재 경기의 계측값을 가짜로 채우지 않는다.

## 4. 다음 한 단위와 유지보수

이후 CV-5에서 [기존 두 창 122장의 시점 제한 공급](CV_PREFIX_REPLAY_V1.md)을 완료했다. 바로 다음은 CV-5a, [관측 v1 규약](CV_OBSERVATION_PROTOCOL_V1.md) §8의 **실제 관측기와 계측을 연결한 한 타석 개발 리플레이**다. 기존 한 타석의 원본 영상·출처를 고정하고, 미래 프레임을 제공하지 않는 처리 기록을 준비한다. 실제 미트 관측기와 계측을 연결하기 전까지 실시간 완료로 표시하지 않는다.

CV-6의 [기권 불일치 26장 검토 자료](CV_REVIEW_QUEUE_V1.md)도 준비했지만 사람 응답은 0건이다. 다음은 같은 규약으로 실제 사람 재검토를 받고, 미열람 연속 영상·독립 라벨러·평가 manifest를 확보하는 일이다. 새 영상과 실제 사람 판정이 없으므로 독립 검증은 남아 있다. F-4i 이름 OCR 보류, 팀원 업무 제외, 기존 M3·시연 자료 고정을 유지한다.

검증 결과와 커밋은 [CHECKLIST](../CHECKLIST.md)의 CV 절 및 [인계 기록](MLB_P0_HANDOFF.md)을 기준으로 확인한다. 새 도구는 `scripts/check_project.py --cpu-only`의 lint·format·전체 pytest 대상에 포함한다.

검증: `check_project.py --cpu-only` — **742 passed, 5 skipped, 2 deselected**, Ruff check/format 90경로 통과. 새 도구 테스트 90건 포함. 기존 Pillow API deprecation 경고 2건은 남아 있다.

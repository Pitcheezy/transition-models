# Codex Cloud 인수인계 — 2026-10-11

이 문서는 transition-models의 현재 사이트 구조와 Cloud에서 재현할 수 있는 범위를 설명한다.
최신 작업 상태는 [CHECKLIST](../CHECKLIST.md) 상단이 기준이다. H-main1은
[PR #2](https://github.com/Pitcheezy/transition-models/pull/2), main 병합 커밋 `39ffcd0`으로 완료했다.
[병합·검증 기록](MAIN_INTEGRATION_20261011.md)을 읽고 시작할 때 실제 origin/main과 HEAD를 확인한다.

## 현재 실행 중인 세 화면

| 화면 | 소스와 현재 위치 | 실제로 제공하는 것 |
|---|---|---|
| 공개 Pitcheezy | `web/pitch-studio/` → OpenAI Sites, [pitcheezy.com](https://pitcheezy.com), [기본 주소](https://pitcheezy-pitch-studio.sritone723.chatgpt.site) | 정적 홈·서비스 콘셉트·기존 수신기·저장 관측 리포트 |
| 비공개 S 서비스 검토 v5 | `web/service-review/`, 노트북 `http://127.0.0.1:59154/` | 받은 S 응답의 추천 표시 → 공식 3클립 → 실제 결과/미트 가로 추정 공개 |
| 비공개 관측 재생 v9 | `web/observation-playback/`, 노트북 `http://127.0.0.1:59158/` | 기존 CV24 관측을 제한 영상 구간과 발행 시각에 맞춰 재생 |

공개 도메인은 Cloudflare DNS를 사용한다. 2026-10-11 DNS와 PowerShell 브라우저 User-Agent의 HEAD 조회에서 HTTPS 200을 재확인했다.
기록된 Sites 배포는 v9, 소스 `a3a7a6bb7bc434c6ba93ae45f12bca23c8898012`,
배포 ID `appgdep_6ac4a34611d08191bc5d9d1ae7cc93ba`다.
main 병합·push와 Sites 배포는 별도 작업이다. HTTP 200은 가용성 확인이며 배포 소스 재검증이나 모델 실행 증거가 아니다.

공개 화면의 `/service.html`에는 설명용 추천·확률·선수/벤치 평가가 있다.
`/receiver.html?demo=849843-pa1`은 기존 첫 타석 3구 경로이며,
`/report.html#analysis`와 `/report.html#validation`은 저장 관측·검증 자료다.
새 S 검토 v5를 공개 사이트의 기존 수신기와 같은 서비스로 취급하지 않는다.
[공개 화면 구성·시연 범위](INTENT_DEMO_SITE.md)를 함께 읽는다.

서비스 v5는 경기 849843의 받은 262구/71타석을 정규화한 경기 후 as-of 재생이다.
ready 246·unsupported 16·missing 0이며, 실제 missing 사례는 받지 않았다.
구종 선택 비중은 사건확률이 아니고 미트는 검토 전 가로 추정치다.
[수신 범위](SERVICE_GAME_V2_RECEIVED_20261009.md), [v5 전달 안내](handoff/README.md)를 따른다.

관측 v9는 `outputs/cv_replay_view_20261011_v9`에 있다.
기존 관측 14개 수용, 확정 미트 0개, 보수적 투구 전 시각 충족 0/3구다.
새 모델 실행·독립 평가·엄격한 전체 타석 검증이 아니다.
v9의 재생 수정은 서비스 v5 소스/영상 ZIP에 포함되지 않는다.
[CV-31 재현·한계](CV_PLAYBACK_BROWSER_REGRESSION_20261011.md),
[ZIP별 내용](handoff/FILE_GUIDE_20261011.md)을 참고한다.

## Cloud에 자동으로 따라오지 않는 것

Git checkout에는 노트북의 Git 제외 `outputs/`, 실제 S 원문, 비공개 영상팩, CV24 입력 이미지·저장 실행,
Git 제외 모델 가중치·대용량 데이터, 실행 중인 서버가 자동 복사되지 않는다.
추적된 구형 checkpoint는 Git LFS다. 포인터만 받은 상태에서 파일 존재만 확인하면 추론 검사가 실패한다.
CI는 LFS checkout을 사용하며 Cloud도 검사 전에 `git lfs pull`로 실제 바이트를 받아야 한다.
이 공개 구형 가중치를 별도 운영 schema의 Git 제외 모델 번들과 혼동하지 않는다.
특정 비공개 실행에는 합의된 별도 자료 전달과 경로 설정이 필요하다.

Cloud의 `127.0.0.1`은 그 Cloud 작업 환경을 가리킨다. 노트북의 59154/59158 서버에 연결하는 주소가 아니다.
Windows 절대 경로와 `.venv/Scripts/python.exe`를 Linux에 복사하지 않는다.
Cloud에서 띄운 개발 서버를 공개 운영 배포나 상시 웹 호스팅 완료로 기록하지 않는다.

공식 안내상 새 Cloud 작업은 게시한 환경의 준비된 파일시스템에서 별도 작업 공간을 만든다.
의존성 준비는 Install script, 서비스 시작·준비 확인은 Start skill로 기록한다.
설정 저장과 Publish/Republish를 구분하며, 재사용 설정을 바꾸면 다시 게시하고 새 작업에서 확인한다.
기존 작업은 자체 상태를 유지한다.
[OpenAI 공식 Cloud environments](https://learn.chatgpt.com/docs/environments/cloud-environments) (2026-10-11 확인).

## Linux 환경 준비와 검사

Cloud 환경에는 우리 transition-models 저장소만 선택한다.
Python 3.12, uv 0.10.4, Node.js 24를 기준으로 준비한다. 브라우저 검사의 최소 Node 버전은 20이다.
저장소 루트에서 실행하며, 의존성·브라우저 설치에는 다운로드 접근이 필요하다.
합성 검사는 API 키·W&B 로그인·팀원 서비스 자격증명을 요구하지 않는다.

~~~sh
git lfs version
git lfs pull
uv sync --frozen --python 3.12
export WANDB_MODE=offline
export PYTHONUTF8=1
export OMP_NUM_THREADS=1
export OPENBLAS_NUM_THREADS=1
export MKL_NUM_THREADS=1
uv run --frozen python scripts/check_project.py --cpu-only --test-timeout 180
~~~

이는 [.github/workflows/ci.yml](../.github/workflows/ci.yml)의 Linux CPU 경로다.
실제 환경이 느려 timeout이 발생하면 원인을 기록하고 적절한 한도를 명시해 다시 실행한다.
일반 프로젝트 검사 명령은 `uv run --frozen python scripts/check_project.py`다.
없는 모델·데이터를 합성 값으로 채워 실제 추론 통과로 만들지 않는다.

브라우저 검사는 [잠금 파일](../tests/browser/package-lock.json)의 Playwright 1.62.1을 사용한다.
다음은 저장소 루트에서 시작하며 Chromium과 WebKit 모두 검사한다.

~~~sh
export PYTHON_BIN="$PWD/.venv/bin/python"
cd tests/browser
npm ci --ignore-scripts
npx playwright install --with-deps chromium webkit
BROWSER_ENGINE=chromium npm test
BROWSER_ENGINE=webkit npm test
cd ../..
~~~

`npm test`는 합성 S 자료와 직접 만든 색상 영상을 사용한다.
서비스 검토 13개와 관측 재생 9개 회귀가 포함된다.
브라우저 설치 후 검사 자체는 임시 loopback 서버를 사용한다.
`observation-playback-private.cjs`는 별도 비공개 영상 검사이므로 Cloud 기본 검사에 추가하지 않는다.
WebKit 통과를 실제 Safari·Mac·아이폰 사용 검수로 기록하지 않는다.
[브라우저 검사 안내](../tests/browser/README.md),
[브라우저 CI](../.github/workflows/service-review-browser.yml)를 기준으로 명령을 유지한다.

## 자료 없이 검토 화면 실행하기

공개된 합성 예제만으로 새 S 검토 화면을 만들 수 있다.
아래 폴더 이름은 미사용 이름이어야 한다. 재실행할 때 새 이름으로 바꾸고 기존 팩을 덮어쓰지 않는다.

~~~sh
mkdir -p outputs
uv run --frozen python scripts/inspect_service_game.py \
  --input docs/examples/service_game_v2_export_synthetic.json \
  --source-kind synthetic --profile teammate_export_20261009_v1
uv run --frozen python scripts/build_service_review.py \
  --input docs/examples/service_game_v2_export_synthetic.json \
  --source-kind synthetic --out-dir outputs/cloud_synthetic_review_new
uv run --frozen python outputs/cloud_synthetic_review_new/launch_review.py --check
uv run --frozen python outputs/cloud_synthetic_review_new/launch_review.py --port 0
~~~

마지막 명령이 출력하는 주소를 같은 Cloud 작업의 브라우저에서 연다. 종료는 Ctrl+C다.
합성 3구는 ready/unsupported/missing 각 1개이고 실제 경기 영상은 없다.
실제 S 원문을 받은 경우에만 `--source-kind provided_export`를 사용한다.
`--include-first-pa-video`는 출처 SHA와 투구 키가 결속된 기존 클립이 있을 때만 사용한다.
가짜 자료를 비공개 원문·영상·모델 대신 넣어 실제 서비스나 연구 결과를 만들지 않는다.

공개 정적 화면의 개발 확인은 다음과 같다. 해당 checkout에 없는 미디어는 별도 누락으로 기록한다.

~~~sh
uv run --frozen python -m http.server 8786 --bind 127.0.0.1 --directory web/pitch-studio
~~~

## 다음 작업을 결정하는 조건

- I-0/I-5: 공동 정본·소스/배포 버전·역할·지원 범위 합의가 필요하다.
- I-run1: 합의된 실행 번들·가중치·데이터 manifest·lock·경로 설정이 필요하다. 저장 응답 재생으로 대신 완료하지 않는다.
- I-release1/I-device2: 실제 Mac·아이폰·사용자 경로·운영 조건 확인이 남아 있다. Mac은 현재 영상팩 전달 대기다.
- CV-6/CV-7: 독립 사람 판정과 미열람 영상·고정 평가 자료가 필요하다.
- CV-5a4/CV-5a: 시작 정의 결정 또는 엄격 조건을 만족하는 새 원본이 필요하다.
- A-y: 사용자 요청으로 보류 중이다. 재개 요청 전 배정하거나 사람 일치도 결과를 만들지 않는다.

새 기능을 임의로 추가하지 않는다. `uv run --frozen python scripts/checklist_model.py --next`로
등록 상태를 확인하고, 실행 가능한 항목이 없을 때 종료 1은 정상일 수 있다.
외부 자료가 필요한 항목은 자료 도착 후 재개한다.
구형 UMAP/Arsenal 135d와 새 운영 135d를 혼용하지 않고 독립 strike/ball/foul·목표 코스 출력을 임의로 만들지 않는다.
실점 개선은 입증되지 않았다. [운영 검증 결과](OPERATIONAL_VALIDATION_2026-09-21.md)를 먼저 읽는다.

## Cloud 작업 시작 프롬프트

~~~text
우리 transition-models 저장소에서 작업해 주세요.
AGENTS.md, CHECKLIST.md 상단, docs/CODEX_CLOUD_HANDOFF.md,
docs/OPERATIONAL_VALIDATION_2026-09-21.md를 먼저 읽고 현재 작업 범위를 확인하세요.

git status와 원격 주소를 확인하고 origin/main을 fetch하여 최신 커밋과 HEAD를 기록하세요.
H-main1 병합 커밋 39ffcd0이 실제 원격 main에 포함되는지 확인하세요. 기존 변경은 보존하고,
최신 main을 기준으로 짧은 codex/<작업명> 브랜치에서 한 작업 단위만 진행하세요.
main에 직접 push하지 말고 검증 결과를 포함한 PR로 반환하세요.
CHECKLIST.md와 관련 인수인계 문서를 작업과 같은 커밋에서 갱신하세요.

먼저 이 문서의 Linux CPU 검사와 합성 Chromium/WebKit 검사를 재현하세요.
비공개 원문·영상·가중치가 없으면 누락을 기록하고 합성 검증 범위만 보고하세요.
검사 통과를 모델/API 실제 실행, 새 정확도, 사람 검토, 실제 기기 검수로 표현하지 마세요.
Cloud localhost는 노트북의 서버가 아닙니다.

SongRoute/pitcheezy 등 팀원 저장소·프로세스·배포에는 접근하거나 변경하지 마세요.
A-y 보류와 외부 입력 조건을 유지하세요. 새 기능·공개 배포·팀원 메시지 전송은
명시적인 별도 요청이 있어야 합니다.
실행 가능한 등록 작업이 없다면 임의 작업을 만들지 말고 현재 상태와 필요한 입력을 보고하세요.
~~~

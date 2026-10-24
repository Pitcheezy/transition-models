# 로그 보존 배포 준비 — 2026-10-25

## 범위와 결론

WS-config1은 현재 켜진 Workers Logs100%·호출 기록·저장을 유지할 **오프라인 설정 검사와 배포 후보 준비**다. 실제 재배포·발행 토큰 회수·Song 화면 연결·공동시험 완료가 아니다. 사용자 우선순위는 형의 배포/접속/회수/로그 요청을 먼저 마친 뒤 동시30~50명 전시 검증이다. 용량은 미측정이다.

Wrangler4.151.0의 설치된 wrangler-dist/cli.js:181074–181080에서 observability 생략 시 배포 후 설정 PATCH에 enabled:false를 넣음을 확인했다. 기존 검사기는 이 필드를 거부하므로 기존 예제 그대로 재배포하면 현재 로그 설정을 유지할 수 없다. src/operations/host_config.py에 명시적인 로그 설정의 제한된 부분집합 검사를 추가했다. 구형 설정의 생략 호환은 유지하며, 통과는 실제 로그 유지나 배포 승인이 아니다. [검사 계약](../ops/public-host/CONFIG_CHECK.md), [공식 로그 설정](https://developers.cloudflare.com/workers/observability/logs/workers-logs/).

## 실행 근거

- 수정 전 회귀 1실패 → 집중82통과/144deselected; 관련 config+release 전체287통과(64.67초). Ruff/check/format 및 diff 검사 통과.
- 고정 release.zip을 다시 검사하고 새 비공개 후보로 추출했다. runtime5파일은 현재 신뢰한 체크아웃과 줄바꿈 정규화 후 일치한다. Song 코드나 파일을 수정하지 않았다.
- 후보는 접근 문ON, 업로드·자료읽기·이용기록·피드백OFF, 단일 합성 키/절대 만료, Logs100%/호출/저장ON, Traces/IssuesOFF다. 계정·자원·주소·자격은 공유 기록에 포함하지 않는다.
- 고정 Wrangler dry-run 종료0, bundle52.85KiB/gzip12.88KiB. 실제 배포하지 않았다. dry-run이 생성한 **빈** host/.wrangler/tmp와 host/.wrangler만 제거하고 검사기를 다시 실행해 통과했다. 내용 있는 디렉터리를 삭제하거나 목록 밖 파일 허용 규칙을 완화하지 않았다.
- [허용목록 영수증](results/ops/ws_log_config_preparation_20261025.json)에 ZIP/설정/bundle SHA를 기록했다. 후보는 로컬 비공개 폴더에만 있으며 공개 업로드하지 않는다.

재현 명령(경로는 각자의 비공개 후보 경로):

~~~text
python -m pytest tests/test_public_host_config.py tests/test_public_host_release.py -q
python -B -S scripts/check_public_host_config.py PRIVATE_CANDIDATE
node PINNED_WRANGLER deploy --dry-run --config PRIVATE_CANDIDATE/host/wrangler.deploy.json --env-file EMPTY_ENV_FILE --outdir PRIVATE_OUTPUT
~~~

재현 시 dry-run 후 후보 목록도 다시 검사한다. 검사 뒤 설정/코드가 달라지면 재검사하며, 만료 시각을 바꾸면 새 SHA를 기록한다. 실제 시험 첫 요청 이후에는 시각/키를 바꾸어 같은 시험으로 이어 붙이지 않는다.

## 실제 남은 조건

기존 관리 API 토큰은 만료된 상태다. 현재 시험 Worker의 출처를 고정한 배포에는 유효한 최소 범위 관리 자격 또는 검증 가능한 대시보드 배포 경로가 필요하다. 새로운 인증 자격의 입력·저장은 브라우저 규칙에 따라 사용자 본인이 수행한다. 발행 시험은 별도로 baseline HEAD404 → 같은 bearer 회수후401 → 업로드OFF503을 계획한다. 각1회·재시도없음·PUT/DELETE없음이며, 404는 인증/범위 통과 후 객체 부재 근거일 뿐 실제 업로드 성공은 아니다. 서버 로그와 배포 버전의 대조가 필요하다.

관람 회수 실제200→401/서버로그 증거는 별도 PR #62에 있으며, 이 브랜치는 그 이전 main에서 시작했다. 이 준비를 실제 회수로 대체하지 않는다. 다른 모델 고정 커밋 검토는 진행 전이며 결과를 후속 기록한다.

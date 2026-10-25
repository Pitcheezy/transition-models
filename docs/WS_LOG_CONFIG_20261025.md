# 로그 보존 배포 준비 — 2026-10-25

## 10/25 후속 상태

이 문서 아래의 관리 자격/배포 대기는 WS-config1 완료 당시 이력이다. 실제 본인 배포·발행 HEAD 회수와 로그3건은 [PR64 고정 기록](https://github.com/Pitcheezy/transition-models/blob/abddb240a698e91923d14ef413e36081a4af5315/docs/WS_PUBLISHER_REVOCATION_20261025.md)에서 후속 완료했다. 안내 저장 로그는12/13으로 한 건 미확인이고, 최신 Song 전달본·공동시험 GO는 여전히 대기다. 전시회 요금제·요청량은 사용자 지시로11월 보류한다.

WS-config2는 PR65가 병합된 main `e12ac00`을 PR63에 통합하는 문서 충돌 수리다. 기존 설정 검사 코드/테스트를 보존하고 회귀 검사·새 head CI를 확인한다. Cloudflare 설정·배포·자격을 변경하는 작업이 아니다. 결과와 실제 PR 병합 상태는 [CHECKLIST](../CHECKLIST.md) 및 [PR63](https://github.com/Pitcheezy/transition-models/pull/63)을 따른다.

## 범위와 결론 (당시 기록)

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

## 실제 남은 조건 (WS-config1 당시 이력)

기존 관리 API 토큰은 만료된 상태다. 현재 시험 Worker의 출처를 고정한 배포에는 유효한 최소 범위 관리 자격 또는 검증 가능한 대시보드 배포 경로가 필요하다. 새로운 인증 자격의 입력·저장은 브라우저 규칙에 따라 사용자 본인이 수행한다. 발행 시험은 별도로 baseline HEAD404 → 같은 bearer 회수후401 → 업로드OFF503을 계획한다. 각1회·재시도없음·PUT/DELETE없음이며, 404는 인증/범위 통과 후 객체 부재 근거일 뿐 실제 업로드 성공은 아니다. 서버 로그와 배포 버전의 대조가 필요하다.

관람 회수 실제200→401/서버로그 증거는 별도 PR #62에 있으며, 이 브랜치는 그 이전 main에서 시작했다. 이 준비를 실제 회수로 대체하지 않는다. 다른 모델 gpt-5.6-sol이 고정 커밋 e8b015ae97ae56301c9f5f1effdc9319f29f758b을 검토해 중요 결함 없음(PASS)을 보고했다. 독립 재실행287통과(66.48초), Ruff/diff 통과. 체크리스트8통과(Windows UTF-8 명시 후 경고 없음). 원문 Git blob SHA는 영수증에 기록했다. 이는 실제 배포 승인이나 클라우드 검증이 아니다.

## 관리 자격 준비 (WS-config1 당시 이력)

기존 관리 토큰 만료로 실제 배포를 아직 수행하지 않았다. 대시보드의 해당 Worker 전용 Editor 토큰이 우선 후보이며, 기존 R2/D1 binding을 쓰는 배포에는 별도 제품 전체 편집 권한을 처음부터 요구하지 않는다. [Workers 권한](https://developers.cloudflare.com/workers/authorization/workers/), [인증 방식](https://developers.cloudflare.com/workers/authorization/). 실제 발급 범위·만료와 assets/cron/Logs 갱신 성공은 별도 확인한다. 권한 오류가 나면 계정 전체 권한으로 자동 확대하지 않는다.

고정 Wrangler cli.js:180951–180953의 keepSecrets:true와 :169149–169151의 secret_text/secret_key keep_bindings를 확인했다. 이번 코드 배포에 secret값을 새로 공급하지 않는다. 기존 R2/D1/limiter는 설정에 명시하며 도메인/신규 자원/migration은 변경하지 않는다. [공식 deploy](https://developers.cloudflare.com/workers/wrangler/commands/workers/). 이 로컬 동작 확인도 실제 배포 후 대조를 대신하지 않는다.

## WS-config2 로컬 검증 — main 통합 후

- 통합 대상은 main `e12ac008bebc55fcfc62dea9fa0b36eddb1571d8`, 기존 PR63 head는 `1d6bfd1b782b58d0145794db438b5ab9935908c8`다. PR65 고정 head `059c8cc`의 다른 모델 검토·CI8/8 성공과 사용자 승인을 확인한 뒤 PR65만 main에 병합했다.
- 충돌은 CHECKLIST와 운영 인계 두 문서였고 양쪽 이력을 보존했다. 협업 계획/GATE-06의 PR65 병합 상태도 맞췄다. 전시회 요금제·요청량11월 보류, PR64 미병합·안내 로그12/13·새 ZIP/GO 대기를 유지한다.
- `python -m pytest tests/test_public_host_config.py tests/test_public_host_release.py tests/test_checklist_model.py -q`: **295 passed**, 70.01초. 기존 관련287검사와 체크리스트8이며 새 운영 측정이 아니다. Ruff check/format 통과.
- `src/operations/host_config.py` Git blob `f231ba22af2c13ee16ab9d67ad286309dbfe0e6a`, `tests/test_public_host_config.py` blob `a2487e9acf061b31235673819a5f9a54bf917062`는 기존 PR63과 동일하다. CONFIG_CHECK 및 기존 준비 영수증도 동일하다. 따라서 기존 다른 모델의 고정 코드 검토 범위를 바꾸지 않았다.
- 현재 구역/관련 문서의 상대 링크128개, 날짜별 이력4구역, 기존 로그 재조회/용량 요약 영수증2개의 Git blob 불변을 확인했다. Windows 체크아웃은 CRLF로 변환되어 로컬 바이트 SHA가 다르며, Git의 LF 원문 SHA는 각 기록과 일치한다. 원본 시험/배포가 달라진 것으로 해석하지 않는다.
- 같은 모델의 별도 문서 검토에서 P1/P2 없음. 이는 코드의 다른 모델 검토를 대신하는 주장이 아니다. 당시 조건 제목을 명시해 오래된 관리 토큰 대기를 현재 지시로 오독하지 않게 했다.
- 새 head CI/병합 상태는 [PR63](https://github.com/Pitcheezy/transition-models/pull/63)에서 확인한다. 이번 단위는 실제 Cloudflare 조회/변경·서비스 요청·팀원 코드 접근·새 대외 회신이 없다.

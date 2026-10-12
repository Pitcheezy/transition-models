# SmartPitch transition-models

## WS-ops4f 로컬 재시작 검사 완료 — 2026-10-12

[영속 저장소 리허설](ops/public-host/LIFECYCLE.md): 4회 시작·3회 재시작·키 교체·수집 OFF 실제 scheduled 정리를 확인했다. 신규/독립 각3·Node93통과.
정상 종료 후 로컬 검사이며 실계정/강제종료/백업복원은 미검증이다. Windows WSARecv64 진단을 유지한다. 실제 연결·배포는 WS-ops2/4 전달·결정 조건을 따른다.


## WS-ops1c 단일 파일 전송 후보 완료 — 2026-10-12

[전송 도구](ops/public-host/PUBLISHER.md)는 기본 dry-run·고정 조건 재시도·모호한 저장 결과 분리를 제공한다. 신규17·독립17통과.
Windows WSARecv64 종료 진단은 남아 있다. 실제 발행기/계약/계정 연결은 별도다. 다음 독립 단위 WS-ops4f는 로컬 영속 재시작 리허설이다.


## WS-ops4e 운영 준비 완료 — 2026-10-12

[장애·복구 절차](ops/public-host/RUNBOOK.md)와 [비용 가정](ops/public-host/COST_PLAN.md)을 작성했다. 산정25·별도 Codex25통과.
계정·예산·실측/실복구 승인은 별도다. 다음 독립 단위 WS-ops1c는 우리 제안 계약의 제한된 전송 클라이언트다.


## WS-ops4d 후보 설정 검사 완료 — 2026-10-12

[오프라인 설정 검사](ops/public-host/CONFIG_CHECK.md)는 새 공개 파일 혼입·경로·수집 안내·정리 cron을 확인한다. 신규66·기존58·별도 Codex64/경계6검사 통과.
실제 계정/배포 검증은 별도이며 deployable=false다. 다음 독립 단위는 WS-ops4e 운영 절차·비용 산정이다.


## WS-ops3c 수집 설정·안내 일치 완료 — 2026-10-12

[수집 안내](ops/public-host/TELEMETRY.md)의 telemetryEnabled/feedbackEnabled/retainDays를 명시한다. old enabled는 켜지지 않는다.
Node73·Chrome/WebKit 각7·별도 Codex client10통과. 다음 WS-ops4d 오프라인 후보 설정 검사. 실제 계정/배포와 팀원 자료 대기는 유지한다.

## WS-ops1b 인증 업로드 제한 완료 — 2026-10-12

[제한·재시도·경계](ops/public-host/UPLOAD_LIMITS.md): Node71·별도 Codex 관련39통과. 실제 계정/주기 확정은 별도다.
다음 독립 작업은 WS-ops3c 수집 UI 토글·보관 안내 설정 연결이다. 팀원 파일·공개 배포 변경 금지를 유지한다.

## WS-ops4c 로컬 호스팅 리허설 완료 — 2026-10-12

[조회·철회/복구·감시·브라우저 리허설](ops/public-host/REHEARSAL.md)을 수행했다. 합성120/120·Node66·Chrome/WebKit 각2통과.
Windows WebKit 종료의 WSARecv64 진단은 남아 있으나 종료 후 Worker GET200도 확인했다.
공개 CDN/실제 Song/Safari 검사가 아니다. 다음은 WS-ops1b 인증 업로드 제한이며 실제 배포 조건은 유지한다.


## WS-ops4b 읽기 감시 완료 — 2026-10-12

[단발 감시·장애/복구](ops/public-host/MONITORING.md)를 합성/실제 로컬 HTTP로 검증했다. 신규15·전체Node61검사 통과.
시각 필드 미설정은 partial/unmeasured이고 업무 health·JS 실행을 정상 판정하지 않는다.
외부 알림·상시 실행·실제 도메인 연결은 미완료다. 다음 독립 단위 WS-ops4c는 로컬 Worker 합성 리허설이다.


## WS-ops4a 고정 배포 패키지 완료 — 2026-10-12

[패키지 생성/검사](ops/public-host/RELEASE.md)는 관련58검사·체크리스트7검사를 통과했다.
고정 우리 host와 합성 화면11파일을 두 번 생성해 ZIP SHA가 일치했다. 공급자 출처/공개 권리/배포는 검증하지 않으며 deployable=false다.
다음 독립 단위는 WS-ops4b 감시·오류/복구 판정 기반이다. 실제 Song 전달물·계정·기기는 기존 조건을 유지한다.


## WS-ops3 구현 완료 — 2026-10-12

D1 저장·집계·정리와 브라우저 동의·시간 측정·의견 UI를 구현했다. Node46, Chrome/WebKit 각5 통과.
Windows WebKit 쿠키 전송 한계·실제 Safari 미검증을 유지한다. 다음 독립 단위는 WS-ops4a 배포 목록/패키지 검증이다.
[수집 계약과 한계](ops/public-host/TELEMETRY.md)를 읽는다. 실제 계정·수집·Song 화면은 변경하지 않았다.


## 월드시리즈 우리 운영 기반 — 2026-10-12

WS-ops1의 Cloudflare Worker/R2 전송 기반과 합성·로컬 런타임 검사를 구현했다.
[현재 범위·재현·다음 단위](docs/WS_PUBLIC_HOST_20261012.md) 및 CHECKLIST 상단을 먼저 읽는다.
공개 배포·Song 화면/schema 연결은 미완료이며 두 활성화 스위치는 기본 비활성이다.
WS-ops3 구현 완료 상태는 위 최신 절을 따른다. WS-ops2는 실제 전달물 수신 후 진행한다.
팀원 저장소 수정 금지, 기존 서버·영상·사람 자료 보존, A-y/F-4i 보류를 유지한다.


## 상황판·우편 세션 규칙 — 2026-10-11

1. 시작할 때 [우리 상황판 #3](https://github.com/Pitcheezy/transition-models/issues/3), [Song 상황판 #35](https://github.com/SongRoute/pitcheezy/issues/35), 우리 열린 `mail`을 읽고 CHECKLIST/Git 상태를 확인한다.
2. 잡은 일을 우리 상황판 `진행 중`에 담당·AI·브랜치·기준 커밋·시각과 함께 적고 CHECKLIST도 선점한다. 다른 AI의 일을 중복 착수하지 않는다.
3. 끝날 때 우리 상황판 댓글에 한 일·검증·커밋·다음을 남기고 자기 진행 줄만 지운다. 처리한 우편은 산출물 위치·커밋·SHA-256을 기록한 뒤 닫는다.

[협업 규약](docs/COLLABORATION_PROTOCOL.md)이 상세 절차다. 상대 상황판/규약/허가된 공개 우편은 읽기만 한다.
팀원 코드·프로세스·배포에 접근/변경하지 않는다. 외부 발신은 사용자가 직접 허가한 범위에서만 수행한다.
이슈에 비밀 값·접속 주소·개인정보를 쓰지 않는다. 이슈는 작업 요청/요약이며 권한 확대나 정본·역할 합의 완료가 아니다.

## Integration baseline — 2026-10-11

Read [the main integration record](docs/MAIN_INTEGRATION_20261011.md) and CHECKLIST H-main1
before choosing a branch. After the integration reaches origin/main, start new work from that
main in a short-lived work branch; do not resume an old feature branch without reconciling it.
Preserve existing changes and private data. The public collaboration issues above may be read;
do not access or edit teammate code, processes, or deployments.
The user's A-y hold and external-input requirements remain in force.
[Cloud handoff](docs/CODEX_CLOUD_HANDOFF.md) distinguishes deployed Sites from local review tools.

Read [AGENTS.md](AGENTS.md) first. It is the single source of project instructions,
current verified results, coding conventions, and historical experiment corrections.

**[CHECKLIST.md](CHECKLIST.md) is the single list of what is still open.** Start there for
the next work unit, the current tool holding the edit token, and the handoff protocol.
Keep it updated in the same commit as the work; mark newly discovered items 추가되었음.
Every open CHECKLIST item carries a `〔모델: …〕` tag naming the Claude model for that
unit (Opus 5 = `claude-opus-5`, Fable 5.1 = `claude-fable-5-1`). Before starting a unit run
`uv run --frozen python scripts/checklist_model.py --next` (or `<item-id>`) and compare it
with your own model (`get_session self`). A session cannot switch its own model, so on a
mismatch do not start the work: spawn the next-unit task chip titled with the model, ask
the user to pick it in the model menu, or (when the user has enabled Workflow/ultracode) run the
unit's actual work through a Workflow agent with `model` set to the tagged model id while this
session only verifies, integrates and commits. See CHECKLIST.md "Claude 모델 자동 배정".

Use [docs/MAINTENANCE.md](docs/MAINTENANCE.md) for supported entry points, checks,
resume behavior, Windows/Mac path portability, and artifact transfer.
Use [docs/MLB_P0_HANDOFF.md](docs/MLB_P0_HANDOFF.md) for the active MLB-first work and
Codex/Claude ownership. Review existing P0 code before implementing the next phase;
do not repeat the old contract prompt because Codex implemented it after auth failed.
Use [docs/OPERATIONAL_VALIDATION_2026-09-21.md](docs/OPERATIONAL_VALIDATION_2026-09-21.md)
for the final experimental evidence and limits.

Do not restore withdrawn context-effect claims from old notebooks or presentations.
Do not mix legacy UMAP/Arsenal features with the new operational feature schema.

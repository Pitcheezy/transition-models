# SmartPitch transition-models

## 전시 재개 기준 — 2026-11-01

PLAN.md → CHECKLIST.md 상단 → docs/COLLABORATION_PROTOCOL.md → docs/CLAUDE_EXHIBITION_RESUME.md 순서로 읽는다. 사용자는 Song 고정 빌드와 영상 전용 플레이어 방향을 채택했다. 기존 파일·worktree를 보존하며 CV/추가 경기 개발은 중단한다. 이번 실행은 우리 로컬 인수·전달팩 준비만이다. 팀원 저장소·실제 호스트·도메인 변경은 하지 않는다. 한 파일 한 수정자, 고정 변경분 다른 모델 검토를 유지한다.


## 현재 월드시리즈 운영 인계 — 2026-10-18

현재 작업·수정 권한은 [CHECKLIST 상단](CHECKLIST.md), 검증 결과·남은 입력은
[현재 운영 인계](docs/WS_OPERATIONS_HANDOFF.md)를 먼저 확인한다.
[협업 감사](docs/COLLABORATION_AUDIT_20261018.md)와 H-collab3·WS-laptop1은 이번 노트북 작업 범위이며,
두 단위의 완료 여부는 CHECKLIST를 따른다. Mac/Mac mini·팀원 코드/프로세스/배포는 접근하지 않는다.
Song 첫 연결 자료와 로컬 화면은 WS-ops2, 비공개 v4.2는 WS-partner2에서 수신·검증했다.
10/19 #38의 v5 수정/검사 보고는 접수했으나 최종 실행본·SHA·고정 검토 자료는 미수신이다.
[최종 실행본 수신 절차](docs/WS_FINAL_RUNNER_INTAKE_20261019.md)를 따르고 상대 보고와 우리 검증을 구분한다.
본인 전용 합성 클라우드 시험은 WS-stage4에서 완료했지만 실제 상태의 마지막 확인은 10/16이며 오늘은 미확인이다.
실제 Song 연결·일반 공개·상시 감시/알림·실기기는 별도다. A-y/F-4i 보류와 기존 서버/사이트/영상팩 보존을 유지한다.
아래 날짜별 기록의 브랜치·서버·다음 단위를 현재 실행 지시로 사용하지 않는다.

## 협업 v1 세션 규칙 — 2026-10-12

“각자 자기 레포에서 AI가 계속 일하고, 둘은 파일 계약과 이슈로만 만난다. 사람은 결정만 한다.”
[협업 규약](docs/COLLABORATION_PROTOCOL.md)을 따른다. 과거 역할 미합의 문구보다 우선한다.
Song은 목표·공개 계약·모델·발행기·관전 화면, 우리는 호스팅·업로드 수신·기록·피드백·감시/알림·미트 담당이다.
접점은 공개 발행 파일 v1과 업로드 API. 추가는 알림 후 진행, 삭제/의미 변경은 Song 승인 후 v2다.

1. 시작 시 양쪽 board와 열린 mail 본문/댓글, CHECKLIST/Git를 읽고 하루 한 번 확인을 유지한다.
2. 착수 전에 관련 이슈에 합격 기준을 기록하고 우리 board/CHECKLIST를 선점한다.
3. 종료 시 같은 이슈에 결과·커밋·파일 SHA·실행 명령·다음을 남기며 실제 합격한 mail만 닫는다.

계약 안의 구현/검사/문서/조사/검토/로컬 리허설은 AI가 진행한다. 계약 변경·우선순위·접근 대상·비용·
실경기 연결·대외 글은 사람 결정이며, 결정 대기는 표시하고 다음 독립 작업을 한다.
상대 코드·프로세스·배포는 접근/변경하지 않는다. 외부 발신은 사람 승인 범위 안에서만 한다.
운영 코드는 작성 AI와 **다른 모델**이 검토한다. 같은 모델의 다른 세션으로 대체하지 않는다.
합성/오프라인/실경기 증거를 구별하고 미측정은 그대로 쓴다. 비밀/접속 주소는 공개 이슈에 쓰지 않는다.
10/20까지 비공개 연락/응답 시간 결정, 10/21 이후 고장 수리만, 10/23~31 운영 규칙을 따른다.
양쪽 사람의 긴급 안내 화면 전환·양쪽 발행 중단 알림·경기별 이용/문제 기록을 준비한다.
현재 구현 여부와 다음 단위는 [협업 실행 계획](docs/WS_COLLAB_V1_ACTIONS.md)에 있다.

## Integration baseline — 2026-10-11

Read [the main integration record](docs/MAIN_INTEGRATION_20261011.md) and CHECKLIST H-main1
before choosing a branch. After the integration reaches origin/main, start new work from that
main in a short-lived work branch; do not resume an old feature branch without reconciling it.
Preserve existing changes and private data. The public collaboration issues above may be read;
do not access or edit teammate code, processes, or deployments.
The user's A-y hold and external-input requirements remain in force.
[Cloud handoff](docs/CODEX_CLOUD_HANDOFF.md) distinguishes deployed Sites from local review tools.

Read [AGENTS.md](AGENTS.md) first for project instructions, coding conventions, and
historical experiment corrections. Use CHECKLIST's top section and the operations handoff
for current task ownership and verified operating status.

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
The tag is a Claude assignment, not evidence of who authored completed work. Read the fixed
work record for actual author/reviewer models; the historical 0/16 attribution remains unknown.

Use [docs/MAINTENANCE.md](docs/MAINTENANCE.md) for supported entry points, checks,
resume behavior, Windows/Mac path portability, and artifact transfer.
Use [docs/MLB_P0_HANDOFF.md](docs/MLB_P0_HANDOFF.md) for the active MLB-first work and
Codex/Claude ownership. Review existing P0 code before implementing the next phase;
do not repeat the old contract prompt because Codex implemented it after auth failed.
Use [docs/OPERATIONAL_VALIDATION_2026-09-21.md](docs/OPERATIONAL_VALIDATION_2026-09-21.md)
for the final experimental evidence and limits.

Do not restore withdrawn context-effect claims from old notebooks or presentations.
Do not mix legacy UMAP/Arsenal features with the new operational feature schema.

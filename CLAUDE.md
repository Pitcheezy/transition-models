# SmartPitch transition-models

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

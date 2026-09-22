# SmartPitch transition-models

Read [AGENTS.md](AGENTS.md) first. It is the single source of project instructions,
current verified results, coding conventions, and historical experiment corrections.

**[CHECKLIST.md](CHECKLIST.md) is the single list of what is still open.** Start there for
the next work unit, the current tool holding the edit token, and the handoff protocol.
Keep it updated in the same commit as the work; mark newly discovered items 추가되었음.
Every open CHECKLIST item carries a `〔모델: …〕` tag naming the Claude model for that
unit (Opus 5 = `claude-opus-5`, Fable 5.1 = `claude-fable-5-1`). Before starting a unit run
`uv run --frozen python scripts/checklist_model.py --next` (or `<item-id>`) and compare it
with your own model (`get_session self`). A session cannot switch its own model, so on a
mismatch do not start the work: spawn the next-unit task chip titled with the model, or ask
the user to pick it in the model menu, then continue. See CHECKLIST.md "Claude 모델 자동 배정".

Use [docs/MAINTENANCE.md](docs/MAINTENANCE.md) for supported entry points, checks,
resume behavior, Windows/Mac path portability, and artifact transfer.
Use [docs/MLB_P0_HANDOFF.md](docs/MLB_P0_HANDOFF.md) for the active MLB-first work and
Codex/Claude ownership. Review existing P0 code before implementing the next phase;
do not repeat the old contract prompt because Codex implemented it after auth failed.
Use [docs/OPERATIONAL_VALIDATION_2026-09-21.md](docs/OPERATIONAL_VALIDATION_2026-09-21.md)
for the final experimental evidence and limits.

Do not restore withdrawn context-effect claims from old notebooks or presentations.
Do not mix legacy UMAP/Arsenal features with the new operational feature schema.

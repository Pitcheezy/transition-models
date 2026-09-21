# MLB P0 implementation and Codex / Claude handoff

## Scope

MLB first; KBO remains the later deployment target. P0 delivers identity-checked
video metadata, explicit pre-pitch input/output contracts, and a manual-input
inference UI. OCR, continuous broadcast state tracking, target-location models,
and proven policy gains remain P1 or later. Unknown probabilities must be null,
never zero or relabeled from incompatible legacy classes.

## Coordination

- One implementation owner at a time. Review a named checkpoint, then hand back.
- Read AGENTS.md and docs/OPERATIONAL_VALIDATION_2026-09-21.md before changes.
- Run relevant checks, commit each verified unit, and push this task's branch.
- Never commit raw video, credentials, local absolute paths, or model/data caches.
- Document exact commands, observed results, and unfinished items here.

## Active checkpoint

Codex: verified all 322 pitches in game 747139 against the official MLB feed and
the existing 2024 Statcast parquet (4 focused tests passed). Saved manifest:
docs/results/mlb_p0/game_747139_manifest.json. Raw source snapshots live under ignored
data/raw/mlb_video/747139. This game is already in the old test cohort; use it for
development/demo only, not as fresh validation after tuning.

The old pose_estimation downloader assigns CSV rows by list position and restricts
searches to Ohtani regular-season pitches. File names from that downloader are
unverified identities until corroborated. New code must never use positional joins.

## Next checkpoints

1. Verify all pitch identities; inspect official full-game and pitch video inputs.
2. Claude: bounded review / contract implementation after the first checkpoint.
3. Codex: integrate validated inputs with existing operational model and manual UI.
4. Run tests, inspect browser behavior, document remaining limitations, commit/push.

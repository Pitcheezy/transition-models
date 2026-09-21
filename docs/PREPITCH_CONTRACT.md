# Pre-pitch contract v1

## Inputs

`PrePitchState.from_dict` accepts only information available before the pitch.
Required: ISO `game_date`, positive MLB `pitcher` ID, `balls` 0–3, `strikes` 0–2,
`outs_when_up` 0–2, `inning` 1–30, batter `stand` and `p_throws` (`L`/`R`).
Optional: `batter`, runner IDs `on_1b/on_2b/on_3b` (null = empty base),
`inning_topbot` (`Top`/`Bot`), scores and team codes. IDs are integers, not names
or occupancy flags. Runner IDs must be distinct and cannot equal the batter.

Unknown fields, actual pitch type, velocity, location, result, fractional IDs,
NaN and coercible strings are rejected. The chosen candidate action is supplied
inside the inference service, independently of what was actually thrown.
The current model does not use batter identity, score or inning half, even though
the contract preserves these facts for the subsequent model. A state must postdate
the profile cutoff.

## Outputs and probability semantics

The existing model predicts exclusive terminal-priority events:
Ball, Strike, Single, Double, Triple, HomeRun, FieldOut, Strikeout, Walk, HitByPitch.
Strike includes nonterminal foul events; strikeouts have their own class.
Ball excludes terminal walks. FieldOut historically includes some non-out events.
These are legacy training labels, not a clean display taxonomy.

`display_probabilities.hit` = Single + Double + Triple + HomeRun: an unconditional
recorded hit on the next pitch, **not** probability of a hit conditional on contact.
`strike`, `ball`, and `foul` are null until a compatible model is trained. Null must
render as unavailable, never 0%. Exact legacy probabilities remain exposed under
`legacy_probabilities`, with explicit class meanings in the UI.

`src/data/pitch_observation.py` now defines separate eight-class observation labels:
ball, called strike, swinging strike, foul, caught foul tip, hit, in-play without a
hit, HBP. Terminal PA transitions are retained separately. Automatic calls and
catcher interference are excluded with reasons, unknown events fail closed.
The future displayed strike marginal is called + swinging + caught foul tip;
ordinary/bunt fouls remain separate. Two-strike bunt fouls can terminate a PA.
P1 still needs model training/calibration; do not rename an existing checkpoint.

## Recommendation scope

The P0 service compares nine pitch types using the validated operational builder.
It has no target-location action. Only historically supported actions enter the
recommendation. Policy costs were evaluated on completed half innings in innings
1–8; at inning 9+ the service returns probabilities but withholds recommendation
and expected cost. Future completion of an inning is not inferred from live inputs.
Probability and cost estimates do not prove an intervention would improve results.

Video manifests keep `pre_state` separate from `ground_truth`. Recorded metadata
may seed a development example, but that is explicitly a replay/manual mode,
not evidence of video recognition. Broadcast offsets and release instants remain
null until individually annotated; UTC feed timestamps are not playback offsets.
Script 63 validates separate `mlb_broadcast_timing_v1` annotations against the exact
manifest and inspected full-game source. Eight pitches currently have manual timing;
one lacks an established pre-delivery decision frame. A complete three-pitch PA is
available. These are approximate visual annotations, not automatic synchronization
or OCR labels. See `docs/MLB_BROADCAST_TIMING.md` for uncertainty and coverage.

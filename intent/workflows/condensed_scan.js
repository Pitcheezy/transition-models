export const meta = {
  name: 'intent-condensed-scan',
  description: 'Find every pitch delivery in an official MLB condensed game and read the score bug before each pitch, two independent readers per ~80 s range',
  whenToUse: 'Step 2 of intent/condensed.py: args = outputs/frames/<game>_sheets/scan_args.json',
  phases: [{ title: 'Scan', detail: 'two readers per ~80 s range of 2-fps contact sheets' }],
}

// Frozen for the M3 evaluation games (docs/results/mlb_p0/intent_eval_plan_v0.json).
// Generalised from the 849843 prototype: no broadcaster-specific layout, plus the post-pitch graphic.

const GRAPHIC = {
  type: ['object', 'null'],
  properties: { type_text: { type: ['string', 'null'] }, mph: { type: ['number', 'null'] } },
  required: ['type_text', 'mph'],
}
const PITCH = {
  type: 'object',
  properties: {
    release_t: { type: 'number' },
    release_bracket: { type: 'array', items: { type: 'number' }, minItems: 2, maxItems: 2 },
    camera_at_release: { type: 'string', enum: ['centre_field', 'other'] },
    centre_field_setup_visible: { type: 'boolean' },
    setup_t: { type: ['number', 'null'] },
    half: { type: ['string', 'null'], enum: ['top', 'bottom', null] },
    inning: { type: ['integer', 'null'] },
    outs: { type: ['integer', 'null'] },
    balls_before: { type: ['integer', 'null'] },
    strikes_before: { type: ['integer', 'null'] },
    batter_text: { type: ['string', 'null'] },
    pitcher_text: { type: ['string', 'null'] },
    pitch_count_text: { type: ['string', 'null'] },
    post_pitch_graphic: GRAPHIC,
    outcome_seen: { type: 'string' },
    confidence: { type: 'string', enum: ['high', 'medium', 'low'] },
    note: { type: 'string' },
  },
  required: ['release_t', 'release_bracket', 'camera_at_release', 'centre_field_setup_visible', 'setup_t', 'half', 'inning', 'outs', 'balls_before', 'strikes_before', 'batter_text', 'pitcher_text', 'pitch_count_text', 'post_pitch_graphic', 'outcome_seen', 'confidence', 'note'],
}
const SCHEMA = {
  type: 'object',
  properties: { range: { type: 'array', items: { type: 'number' } }, pitches: { type: 'array', items: PITCH }, note: { type: 'string' } },
  required: ['range', 'pitches', 'note'],
}

function prompt(r, reader) {
  const sheets = r.sheets.map(s => `- ${args.sheetDir}/${s}`).join('\n')
  const order = reader === 'A'
    ? 'Go through the sheets in time order.'
    : 'Go through the sheets in REVERSE time order first to get oriented, then confirm each pitch in time order; read every image yourself and never copy numbers between pitches.'
  return `You are reader ${reader}. You are scanning the official MLB condensed game of ${args.gameLabel} (${Math.round(args.duration)} s long). ${order}

The video was sampled at 2 frames per second. Each CONTACT SHEET below is a 4x4 grid of consecutive frames (left to right, top to bottom), each labelled bottom-right with its playback time t in seconds; one sheet covers 8 seconds. Full-resolution single frames are at ${args.frameDir}/scan_KKKKK.jpg where KKKKK = 2*t + 1 zero-padded to 5 digits (t = 60.5 -> scan_00122.jpg). Open single frames whenever you need to read the score bug.

Your range: t = ${r.start} to ${r.end} s.
${sheets}

Find EVERY live pitch delivery in your range (a pitch thrown to a batter, any camera). A condensed game skips most pitches, so deliveries come one or two at a time between replays and graphics; a pitch whose release falls inside your range counts even if its setup started earlier. Replays of a pitch already shown (usually without the score bug, from another angle or in slow motion) are NOT new pitches: leave them out and mention them in note.
For each pitch report:
- release_t: your best estimate of the moment the ball leaves the pitcher's hand, to the nearest 0.5 s, and release_bracket [last frame time before release, first frame time after release].
- camera_at_release: "centre_field" for the usual high camera from centre field showing pitcher, batter, catcher and umpire together; "other" for any other angle.
- centre_field_setup_visible: true if, in the centre-field view, the catcher can be seen set up behind the plate in at least one frame before release; setup_t = the time of the LAST such frame before the pitcher's arm comes forward (null if none).
- The score bug (its position and style depend on the broadcaster; find it on the first sheets): read it from a frame BEFORE the release (the count changes after the pitch): half (top = ${args.awayTeam} batting, bottom = ${args.homeTeam} batting; read the arrow or the batting team), inning, outs (filled markers), balls_before and strikes_before (the count shown before this pitch), batter_text (the batter name as shown), pitcher_text and pitch_count_text (as shown). Use null for anything you cannot read; never infer from neighbouring pitches or from baseball knowledge.
- post_pitch_graphic: many broadcasts show the pitch type and speed for a moment right after the pitch (e.g. "FOUR SEAM 98", "SLIDER 87 MPH"); give {type_text, mph} exactly as shown, or null if no such graphic appears for this pitch.
- outcome_seen: what happened (called strike, ball, swinging strike, foul, in play: ground ball/fly/hit/home run, etc.) as seen in the video.
- confidence and a short note.
Return range [${r.start}, ${r.end}] and the pitches in time order. If the range has no pitch, return an empty list and say why in note.`
}

const ranges = args.ranges
log(`${ranges.length} ranges, two readers each`)
const results = await pipeline(
  ranges,
  (r, _i, idx) => parallel([
    () => agent(prompt(r, 'A'), { label: `scan-A:${idx + 1}`, phase: 'Scan', schema: SCHEMA, effort: 'high' }),
    () => agent(prompt(r, 'B'), { label: `scan-B:${idx + 1}`, phase: 'Scan', schema: SCHEMA, effort: 'high' }),
  ]),
  (pair, r) => ({ range: [r.start, r.end], A: pair[0], B: pair[1] }),
)
log(`ranges with a missing reader: ${results.filter(x => !x || !x.A || !x.B).length}`)
return { results }

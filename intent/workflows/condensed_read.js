export const meta = {
  name: 'intent-condensed-read',
  description: 'Read the catcher setup (mitt, plate front edge), the catch, the rubber and the batter-box lines on 20-fps windows of condensed-game pitches, two independent readers',
  whenToUse: 'Step 5 of intent/condensed.py: args = outputs/frames/<game>_windows/read_args.json',
  phases: [{ title: 'Read', detail: 'two readers per chunk of three pitches' }],
}

// Frozen for the M3 evaluation games (docs/results/mlb_p0/intent_eval_plan_v0.json).
// Generalised from the 849843 prototype: the broadcaster-specific camera and plate-position hints are gone,
// the crop box and frame size come from args.

const PT = { type: ['array', 'null'], items: { type: 'number' }, minItems: 2, maxItems: 2 }
const EDGE = {
  type: ['object', 'null'],
  properties: { left_end: { type: 'array', items: { type: 'number' }, minItems: 2, maxItems: 2 }, right_end: { type: 'array', items: { type: 'number' }, minItems: 2, maxItems: 2 } },
  required: ['left_end', 'right_end'],
}
const BOX = {
  type: ['object', 'null'],
  properties: { x_used: { type: 'number' }, front_y: { type: ['number', 'null'] }, back_y: { type: ['number', 'null'] } },
  required: ['x_used', 'front_y', 'back_y'],
}
const ITEM = {
  type: 'object',
  properties: {
    at_bat_number: { type: 'integer' },
    pitch_number: { type: 'integer' },
    release_frame: { type: ['integer', 'null'] },
    live_cf_first_frame: { type: ['integer', 'null'] },
    setup_frame: { type: ['integer', 'null'] },
    setup_reason: { type: ['string', 'null'] },
    mitt_center: PT,
    mitt_visible_fraction: { type: ['string', 'null'], enum: ['full', 'partial', null] },
    setup_plate_front: EDGE,
    setup_uncertainty_pixels: { type: ['number', 'null'] },
    catch_frame: { type: ['integer', 'null'] },
    catch_reason: { type: ['string', 'null'] },
    ball_visible_in_catch_frame: { type: 'boolean' },
    pocket_center: PT,
    catch_plate_front: EDGE,
    catch_uncertainty_pixels: { type: ['number', 'null'] },
    rubber_center: PT,
    rubber_width_px: { type: ['number', 'null'] },
    left_box: BOX,
    right_box: BOX,
    note: { type: 'string' },
  },
  required: ['at_bat_number', 'pitch_number', 'release_frame', 'live_cf_first_frame', 'setup_frame', 'setup_reason', 'mitt_center', 'mitt_visible_fraction', 'setup_plate_front', 'setup_uncertainty_pixels', 'catch_frame', 'catch_reason', 'ball_visible_in_catch_frame', 'pocket_center', 'catch_plate_front', 'catch_uncertainty_pixels', 'rubber_center', 'rubber_width_px', 'left_box', 'right_box', 'note'],
}
const SCHEMA = { type: 'object', properties: { items: { type: 'array', items: ITEM } }, required: ['items'] }

function prompt(chunk, index, reader) {
  const [x0, y0, x1, y1] = args.cropBox
  const [W, H] = args.frameSize
  const list = chunk.map(p => `- PA ${p.at_bat_number} pitch ${p.pitch_number} (${p.desc}): folder ${p.dir} — strip.jpg (all frames, each labelled #frame_index and time relative to the estimated release), crop_NNNNNN.jpg (2x gridded crop of x ${x0}..${x1}, y ${y0}..${y1} for frame NNNNNN), frame_NNNNNN.jpg (full ${W}x${H} frame)`).join('\n')
  const style = reader === 'A' ? 'Work through the pitches in the listed order.' : 'Work through the pitches in REVERSE order and read every image fresh; never copy a number from another pitch or frame.'
  return `You are reader ${reader}. These are frame windows (20 frames per second; frame_index = source frame number of the video) around single pitches of ${args.gameLabel}, cut from the official MLB condensed game. ${style}

The usual pitch camera is an elevated camera in centre field looking in toward home plate (it may be set off to one side of the mound-plate line): the pitcher is in the foreground, and the catcher, umpire and batter are beyond him; the home plate is a small white pentagon on the ground in front of the catcher. Condensed-game edits often cut to this live view only a fraction of a second before the pitch; frames before the cut may be replays or other angles; ignore those.

The crops have grey grid lines every 20 original pixels and yellow lines/labels every 100; give every coordinate in ORIGINAL full-frame pixels. To read things outside the crop (the rubber on the mound, the batter's box lines), make a gridded full frame. Run from ${args.repoRoot}:
  ${args.gridModule} <folder>/frame_NNNNNN.jpg <your_tmp_dir>/g.png            (full frame, grid every 50 px)
  ${args.gridModule} <folder>/frame_NNNNNN.jpg <your_tmp_dir>/g.png x0 y0 x1 y1 2   (2x zoom of a region, grid every 20 px)
and Read the PNG. Use the Read tool on every image yourself.

For each pitch:
1. release_frame: the frame index where the ball has just left the pitcher's hand (first frame with the ball out of the hand), and live_cf_first_frame: the first frame of the live centre-field view that contains this pitch.
2. setup_frame: the LAST live centre-field frame BEFORE release in which the catcher is set and his glove (mitt) is visible, presented as the target. If there is none (the live view starts at or after release, or the glove is hidden), set null with setup_reason ("cut_after_release", "glove_hidden_by_batter", "glove_hidden_by_umpire", "not_centre_field", ...). On that frame read mitt_center [x, y] (centre of the glove), mitt_visible_fraction ("full"/"partial"), setup_plate_front (left_end and right_end of the plate's FRONT straight edge, the edge facing the pitcher/camera = the lowest straight edge of the white pentagon) and setup_uncertainty_pixels (your honest +/- for the mitt centre).
3. catch_frame: the FIRST frame in which the ball is in the glove (the glove still at the catch position; the frame before shows the ball arriving or the glove open). Null with catch_reason if the batter hit the ball, the catcher did not catch it cleanly, the view changed, or you cannot tell. On that frame: pocket_center (the ball if visible, otherwise the pocket centre), ball_visible_in_catch_frame, catch_plate_front, catch_uncertainty_pixels.
4. On the setup frame (or the nearest live centre-field frame): rubber_center [x, y] and rubber_width_px (the white pitching rubber on the mound, often partly under the pitcher's feet; null if hidden or not in frame), and for each batter's box that is visible (left_box = image-left box, right_box = image-right box): x_used (an x column where you can see both lines), front_y (the box's chalk line nearest the camera/pitcher, lower in the image) and back_y (the box's far line toward the backstop, higher in the image) at that column; null where a line is hidden.
5. note: one or two sentences (what hides what, how sure you are).
Rules: every number comes from an image you looked at; never infer positions from the pitch result or from other pitches; abstain (null + reason) instead of guessing. Return every pitch in the order listed with its at_bat_number and pitch_number.

Pitches (chunk ${index + 1}, reader ${reader}):
${list}`
}

const items = args.items
const chunks = []
for (let i = 0; i < items.length; i += args.chunk) chunks.push(items.slice(i, i + args.chunk))
log(`${items.length} pitches in ${chunks.length} chunks, two readers each`)
const reads = await pipeline(
  chunks,
  (chunk, _item, index) => parallel([
    () => agent(prompt(chunk, index, 'A'), { label: `read-A:${index + 1}`, phase: 'Read', schema: SCHEMA, effort: 'high' }),
    () => agent(prompt(chunk, index, 'B'), { label: `read-B:${index + 1}`, phase: 'Read', schema: SCHEMA, effort: 'high' }),
  ]),
  (pair, _item, index) => ({ chunk: index + 1, A: pair[0] ? pair[0].items : null, B: pair[1] ? pair[1].items : null }),
)
log(`chunks with a missing reader: ${reads.filter(r => !r || !r.A || !r.B).length}`)
return { reads }

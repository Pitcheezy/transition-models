"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { createHash } = require("node:crypto");
const timing = require("../pitch-studio/watch-timing.js");
const media = require("../pitch-studio/receiver-media.js");
const key = "849843:1:1";

// Synthetic boundary annotations exercise validation; these are not visual evidence.
const packet = () => ({ schema: "pitcheezy-watch-events-v1", game_pk: 849843, records: [{
  pitch_id: key, play_id: media[key].play_id, video_sha256: media[key].video_sha256,
  event_kind: "catch", method: "ai_frame_review", lower_seconds: 2.1, upper_seconds: 2.2,
}] });

test("valid local annotation keeps its pitch and video identity and conservatively uses the upper boundary", () => {
  const source = packet(), result = timing.validate(source, media), event = result[key];
  assert.equal(event.pitch_id, key); assert.equal(event.video_sha256, media[key].video_sha256);
  assert.equal(event.label, "포구"); assert(Object.isFrozen(event)); assert(Object.isFrozen(result));
  assert.equal(timing.reached(event, 2.1, 7), false);
  assert.equal(timing.reached(event, 2.199, 7), false);
  assert.equal(timing.reached(event, 2.2, 7), true);
  assert.equal(timing.reached(event, 3, 7), true);
  source.records[0].upper_seconds = 0;
  assert.equal(event.upper_seconds, 2.2, "the verified copy must not follow caller mutation");
});

const invalid = [
  ["different schema", p => { p.schema = "v0"; }],
  ["different game", p => { p.game_pk = 849844; }],
  ["non-array records", p => { p.records = {}; }],
  ["duplicate pitch", p => { p.records.push({ ...p.records[0] }); }],
  ["outside approved first five PAs", p => { p.records[0].pitch_id = "849843:6:1"; }],
  ["unknown pitch", p => { p.records[0].pitch_id = "849843:1:999"; }],
  ["mismatched play ID", p => { p.records[0].play_id = "another-play"; }],
  ["mismatched video bytes", p => { p.records[0].video_sha256 = "a".repeat(64); }],
  ["malformed video SHA", p => { p.records[0].video_sha256 = "abc"; }],
  ["unsupported event", p => { p.records[0].event_kind = "release"; }],
  ["prototype event key", p => { p.records[0].event_kind = "toString"; }],
  ["unsupported method", p => { p.records[0].method = "guessed"; }],
  ["negative lower bound", p => { p.records[0].lower_seconds = -0.1; }],
  ["reversed bounds", p => { p.records[0].lower_seconds = 2.3; }],
  ["zero-width bounds", p => { p.records[0].lower_seconds = 2.2; }],
  ["overwide interval", p => { p.records[0].upper_seconds = 2.351; }],
  ["string timestamp", p => { p.records[0].upper_seconds = "2.2"; }],
  ["nonfinite timestamp", p => { p.records[0].upper_seconds = Infinity; }],
  ["NaN timestamp", p => { p.records[0].lower_seconds = NaN; }],
  ["event at clip end", p => { p.records[0].lower_seconds = media[key].duration_seconds - 0.1; p.records[0].upper_seconds = media[key].duration_seconds; }],
];
for (const [label, mutate] of invalid) test(`rejects ${label} instead of inventing a display time`, () => {
  const p = packet(); mutate(p); assert.throws(() => timing.validate(p, media), TypeError);
});

test("frame-time lookup refuses absent events and unknown/short decoder duration", () => {
  const event = timing.validate(packet(), media)[key];
  for (const duration of [NaN, Infinity, 0, 2.2, "7"]) assert.equal(timing.reached(event, 3, duration), false);
  for (const time of [NaN, Infinity, -1, "3"]) assert.equal(timing.reached(event, time, 7), false);
  assert.equal(timing.reached(null, 3, 7), false);
});

test("shipped timing file is pinned byte-for-byte and every marker joins a real clip", () => {
  const bytes = fs.readFileSync(path.join(__dirname, "../pitch-studio/game-849843-timing.json"));
  const p = JSON.parse(bytes), hash = createHash("sha256").update(bytes).digest("hex");
  const rows = timing.createVerifiedTiming(p, media, hash);
  assert.equal(Object.keys(rows).length, 3);
  for (const [id, row] of Object.entries(rows)) {
    assert.equal(row.video_sha256, media[id].video_sha256);
    assert.equal(timing.reached(row, row.upper_seconds - 0.001, media[id].duration_seconds), false);
    assert.equal(timing.reached(row, row.upper_seconds, media[id].duration_seconds), true);
  }
  assert.throws(() => timing.createVerifiedTiming(p, media, "0".repeat(64)), /SHA/);
  assert.throws(() => timing.createVerifiedTiming(p, media, createHash("sha256").update(Buffer.concat([bytes, Buffer.from(" ")])).digest("hex")), /SHA/);
});

"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const fs = require("node:fs"), path = require("node:path"), crypto = require("node:crypto");
const { validate, createVerifiedMedia } = require("../../web/pitch-studio/receiver-game-media.js");
const game = require("../../web/pitch-studio/game-849843.json");
const base = require("../../web/pitch-studio/receiver-media.js");
const sha = data => crypto.createHash("sha256").update(data).digest("hex");
const gameBytes = fs.readFileSync(path.join(__dirname, "../../web/pitch-studio/game-849843.json"));
function fixture() {
  return {
    schema: "pitcheezy-static-game-media-v1", game_pk: 849843,
    game_sha256: sha(gameBytes), registry_sha256: "a".repeat(64), source_pitch_count: 262,
    records: game.pitches.map((pitch, index) => {
      const local = base[pitch.pitch_id];
      const play_id = local?.play_id ?? `00000000-0000-0000-0000-${index.toString(16).padStart(12, "0")}`;
      return {
        pitch_id: pitch.pitch_id, at_bat_number: pitch.at_bat_number, pitch_number: pitch.pitch_number,
        play_id, pitcher_id: pitch.pitcher.id, batter_id: pitch.batter.id, pitch_type: pitch.post.actual.pitch_type,
        video: `https://sporty-clips.mlb.com/video_${index}==.mp4`,
        page_url: `https://baseballsavant.mlb.com/sporty-videos?playId=${play_id}`,
        video_sha256: local?.video_sha256 ?? "b".repeat(64), bytes: 4096, duration_seconds: 8.5,
      };
    }), excluded: [],
  };
}
function excludeMismatch(packet) {
  const index = packet.records.findIndex(r => r.pitch_id === "849843:69:2");
  const [record] = packet.records.splice(index, 1);
  packet.excluded.push({ pitch_id: record.pitch_id, reason: "pitch_type_mismatch", registry_pitch_type: "SL", received_pitch_type: record.pitch_type });
}

test("matching is by pitch ID even if manifest and game arrays are reordered", () => {
  const packet = fixture(), source = structuredClone(game);
  packet.records.reverse(); source.pitches.reverse();
  const result = validate(packet, source, base);
  assert.equal(Object.keys(result.media).length, 262);
  assert.equal(result.media["849843:71:6"].play_id, packet.records[0].play_id);
  assert.equal(result.media["849843:1:1"].video, base["849843:1:1"].video);
  assert.match(result.media["849843:2:1"].video, /^https:\/\/sporty-clips\.mlb\.com\//);
  assert.equal(result.media["849843:2:1"].poster, undefined);
});
test("a conflicting actual pitch type is excluded rather than silently paired", () => {
  const packet = fixture(); excludeMismatch(packet);
  const result = validate(packet, game, base);
  assert.equal(Object.keys(result.media).length, 261);
  assert.equal(result.media["849843:69:2"], undefined);
  assert.deepEqual(result.excluded["849843:69:2"], { pitch_id: "849843:69:2", reason: "pitch_type_mismatch", registry_pitch_type: "SL", received_pitch_type: "FC" });
});
test("returned media and old observation are independent frozen copies", () => {
  const packet = fixture(), local = structuredClone(base), before = JSON.stringify(local);
  const result = validate(packet, game, local);
  assert.equal(JSON.stringify(local), before);
  local["849843:1:3"].observation.x_pixels = 0; packet.records[3].video = "bad";
  assert.equal(result.media["849843:1:3"].observation.x_pixels, 571);
  assert.throws(() => { result.media["849843:1:3"].observation.x_pixels = 0; }, TypeError);
  assert.throws(() => { result.media["849843:2:1"].video = "bad"; }, TypeError);
  assert.ok(Object.isFrozen(result) && Object.isFrozen(result.excluded));
});
for (const [name, mutate] of [
  ["missing record", d => d.records.pop()],
  ["duplicate pitch key", d => { d.records[3] = structuredClone(d.records[4]); }],
  ["duplicate official play ID", d => { d.records[3].play_id = d.records[4].play_id; d.records[3].page_url = d.records[4].page_url; }],
  ["wrong PA", d => { d.records[3].at_bat_number = 1; }],
  ["wrong pitch number", d => { d.records[3].pitch_number = 2; }],
  ["wrong pitcher", d => { d.records[3].pitcher_id = 1; }],
  ["wrong batter", d => { d.records[3].batter_id = 1; }],
  ["wrong pitch type", d => { d.records[3].pitch_type = "ZZ"; }],
  ["wrong page ID", d => { d.records[3].page_url = d.records[4].page_url; }],
  ["stale source game hash", d => { d.game_sha256 = "0".repeat(64); }],
  ["bad source registry hash", d => { d.registry_sha256 = "no hash"; }],
  ["bad duration", d => { d.records[3].duration_seconds = Infinity; }],
  ["zero duration", d => { d.records[3].duration_seconds = 0; }],
  ["bad size", d => { d.records[3].bytes = "4096"; }],
  ["bad hash", d => { d.records[3].video_sha256 = "not a hash"; }],
  ["unexpected source path field", d => { d.records[3].private_path = "D:/private.mp4"; }],
]) test(`reject ${name}`, () => {
  const packet = fixture(); mutate(packet); assert.throws(() => validate(packet, game, base), TypeError);
});
for (const video of [
  "http://sporty-clips.mlb.com/a.mp4", "https://sporty-clips.mlb.com.evil.test/a.mp4",
  "https://user:secret@sporty-clips.mlb.com/a.mp4", "https://sporty-clips.mlb.com/a.mp4?token=secret",
  "https://sporty-clips.mlb.com/a.mp4#fragment", "https://sporty-clips.mlb.com/../a.mp4",
  "https://sporty-clips.mlb.com/%61.mp4", "https://sporty-clips.mlb.com:443/a.mp4",
  "javascript:alert(1)", "file:///D:/video.mp4",
]) test(`reject unapproved video URL ${video.split(":")[0]} ${sha(video).slice(0, 6)}`, () => {
  const packet = fixture(); packet.records[3].video = video; assert.throws(() => validate(packet, game, base), TypeError);
});
for (const [name, mutate] of [
  ["unknown exclusion reason", d => { d.excluded[0].reason = "manual_override"; }],
  ["false conflict", d => { d.excluded[0].registry_pitch_type = "FC"; }],
  ["wrong received conflict", d => { d.excluded[0].received_pitch_type = "FF"; }],
  ["record and exclusion overlap", d => { d.excluded[0].pitch_id = d.records[3].pitch_id; }],
  ["unknown excluded key", d => { d.excluded[0].pitch_id = "849843:99:1"; }],
]) test(`reject ${name}`, () => {
  const packet = fixture(); excludeMismatch(packet); mutate(packet);
  assert.throws(() => validate(packet, game, base), TypeError);
});
test("base local media must match the new official identity and file hash", () => {
  for (const key of ["play_id", "video_sha256", "video", "poster", "page_url"]) {
    const local = structuredClone(base); local["849843:1:1"][key] = "different";
    assert.throws(() => validate(fixture(), game, local), TypeError);
  }
  const local = structuredClone(base); local["849843:2:1"] = local["849843:1:1"];
  assert.throws(() => validate(fixture(), game, local), TypeError);
});
test("game identity and duplicate pitch IDs cannot masquerade as a matched game", () => {
  const wrong = structuredClone(game); wrong.game.game_pk = 849844;
  assert.throws(() => validate(fixture(), wrong, base), TypeError);
  const duplicate = structuredClone(game); duplicate.pitches[3] = structuredClone(duplicate.pitches[4]);
  assert.throws(() => validate(fixture(), duplicate, base), TypeError);
});
test("unverified or changed manifest bytes never enable videos", () => {
  assert.throws(() => createVerifiedMedia(fixture(), game, "0".repeat(64), base), /바이트/);
});
test("actual shipped mapping pins all 261 clips plus the one explicit conflict", () => {
  const bytes = fs.readFileSync(path.join(__dirname, "../../web/pitch-studio/game-849843-media.json"));
  const packet = JSON.parse(bytes), result = createVerifiedMedia(packet, game, sha(bytes), base);
  assert.equal(Object.keys(result.media).length, 261);
  assert.deepEqual(Object.keys(result.excluded), ["849843:69:2"]);
  assert.equal(result.excluded["849843:69:2"].registry_pitch_type, "SL");
  assert.equal(result.excluded["849843:69:2"].received_pitch_type, "FC");
  assert.equal(result.media["849843:1:3"].video, base["849843:1:3"].video);
  assert.match(result.media["849843:71:6"].video, /^https:\/\/sporty-clips\.mlb\.com\//);
  packet.records[3].video = packet.records[4].video;
  assert.throws(() => createVerifiedMedia(packet, game, sha(Buffer.from(JSON.stringify(packet))), base), /바이트/);
});

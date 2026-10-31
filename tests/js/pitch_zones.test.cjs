"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const fs = require("node:fs"), path = require("node:path"), crypto = require("node:crypto"), vm = require("node:vm");
const { validate, createVerifiedZones, expectedSHA, expectedGameSHA } = require("../../web/pitch-studio/receiver-zones.js");
const assetPath = path.join(__dirname, "../../web/pitch-studio/game-849843-zones.json");
const gamePath = path.join(__dirname, "../../web/pitch-studio/game-849843.json");
const assetBytes = fs.readFileSync(assetPath), gameBytes = fs.readFileSync(gamePath);
const game = JSON.parse(gameBytes), packet = JSON.parse(assetBytes);
const sha = value => crypto.createHash("sha256").update(value).digest("hex");
const fixture = () => structuredClone(packet);

test("shipped zone bytes and game hash bind exactly 262 pitches and 20 batters", () => {
  assert.equal(sha(assetBytes), expectedSHA);
  assert.equal(sha(gameBytes), expectedGameSHA);
  assert.equal(packet.game_sha256, expectedGameSHA);
  const zones = createVerifiedZones(packet, game, sha(assetBytes));
  const pitches = new Map(game.pitches.map(pitch => [pitch.pitch_id, pitch]));
  assert.equal(Object.keys(zones).length, 262);
  assert.equal(new Set(packet.pitches.map(record => record.batter_id)).size, 20);
  for (const record of packet.pitches) {
    const pitch = pitches.get(record.pitch_id);
    assert.ok(pitch);
    assert.equal(record.batter_id, pitch.batter.id);
    assert.equal(record.pitcher_id, pitch.pitcher.id);
    assert.deepEqual(zones[record.pitch_id], { bottom: record.bottom_ft, top: record.top_ft, source: "statcast_record" });
  }
});

test("first three pitches retain the first batter's heights and the next batter has their own pair", () => {
  const zones = validate(packet, game);
  for (const number of [1, 2, 3]) {
    assert.deepEqual(zones[`849843:1:${number}`], { bottom: 1.616190945, top: 3.202452428, source: "statcast_record" });
  }
  assert.deepEqual(zones["849843:2:1"], { bottom: 1.57765748, top: 3.126099081, source: "statcast_record" });
  assert.notDeepEqual(zones["849843:1:1"], zones["849843:2:1"]);
});

test("joins use pitch IDs rather than sidecar or game array order", () => {
  const changed = fixture(), source = structuredClone(game);
  changed.pitches.reverse();
  source.pitches.push(source.pitches.shift());
  assert.deepEqual(validate(changed, source), validate(packet, game));
});

test("returned zone map and entries are frozen independent copies without mutating sources", () => {
  const changed = fixture(), source = structuredClone(game);
  const beforePacket = JSON.stringify(changed), beforeGame = JSON.stringify(source);
  const zones = validate(changed, source);
  assert.equal(JSON.stringify(changed), beforePacket);
  assert.equal(JSON.stringify(source), beforeGame);
  assert.equal(Object.getPrototypeOf(zones), null);
  assert.ok(Object.isFrozen(zones));
  assert.ok(Object.isFrozen(zones["849843:1:1"]));
  changed.pitches[0].bottom_ft = 0.7;
  source.pitches[0].batter.id = 1;
  assert.equal(zones["849843:1:1"].bottom, 1.616190945);
  assert.throws(() => { zones["849843:1:1"].bottom = 0.7; }, TypeError);
  assert.throws(() => { zones["849843:1:1"] = null; }, TypeError);
});

test("recorded heights do not correct the preserved 69:2 pitch-type disagreement or recommendations", () => {
  const source = structuredClone(game), before = JSON.stringify(source);
  const zones = validate(packet, source);
  assert.equal(source.pitches.find(pitch => pitch.pitch_id === "849843:69:2").post.actual.pitch_type, "FC");
  assert.deepEqual(zones["849843:69:2"], { bottom: 1.607775591, top: 3.185777559, source: "statcast_record" });
  assert.equal(JSON.stringify(source), before);
  assert.deepEqual(Object.keys(zones["849843:69:2"]), ["bottom", "top", "source"]);
});

for (const [name, mutate] of [
  ["missing pitch", d => { d.pitches.pop(); }],
  ["duplicate pitch", d => { d.pitches[1] = structuredClone(d.pitches[0]); }],
  ["unknown pitch key", d => { d.pitches[0].pitch_id = "849843:99:1"; }],
  ["prototype property as pitch key", d => { d.pitches[0].pitch_id = "__proto__"; }],
  ["incorrect batter ID", d => { d.pitches[0].batter_id = 1; }],
  ["incorrect pitcher ID", d => { d.pitches[0].pitcher_id = 1; }],
  ["string player ID", d => { d.pitches[0].batter_id = String(d.pitches[0].batter_id); }],
  ["wrong schema", d => { d.schema = "pitcheezy-strike-zones-v0"; }],
  ["wrong game", d => { d.game_pk = 123456; }],
  ["wrong game hash", d => { d.game_sha256 = "0".repeat(64); }],
  ["wrong CSV source hash", d => { d.source.statcast_sha256 = "0".repeat(64); }],
  ["wrong feed source hash", d => { d.source.feed_sha256 = "0".repeat(64); }],
  ["inferred source claim", d => { d.source.kind = "inferred"; }],
  ["wrong height unit", d => { d.units.height = "meters"; }],
  ["wrong height reference", d => { d.units.reference = "catcher_mitt"; }],
  ["wrong perspective", d => { d.units.perspective = "pitcher"; }],
  ["pre-pitch availability claim", d => { d.timing = "pre_pitch"; }],
  ["wrong source denominator", d => { d.source_pitch_count = 261; }],
  ["unexpected top-level private field", d => { d.private_path = "private"; }],
  ["unexpected per-pitch result field", d => { d.pitches[0].actual_pitch_type = "SL"; }],
  ["missing top height", d => { delete d.pitches[0].top_ft; }],
  ["null record", d => { d.pitches[0] = null; }],
]) test(`reject ${name}`, () => {
  const changed = fixture(); mutate(changed);
  assert.throws(() => validate(changed, game), TypeError);
});

for (const [name, bottom, top] of [
  ["NaN lower edge", NaN, 3.2],
  ["infinite upper edge", 1.6, Infinity],
  ["numeric string", "1.6", 3.2],
  ["boolean", true, 3.2],
  ["null", null, 3.2],
  ["lower edge below supported range", 0.49, 3.2],
  ["upper edge above supported range", 1.6, 5.01],
  ["inverted edges", 3.2, 1.6],
  ["equal edges", 1.6, 1.6],
  ["implausibly thin zone", 1.6, 1.99],
  ["implausibly tall zone", 0.5, 4.6],
]) test(`reject ${name}`, () => {
  const changed = fixture();
  changed.pitches[0].bottom_ft = bottom; changed.pitches[0].top_ft = top;
  assert.throws(() => validate(changed, game), /상·하단/);
});

for (const [name, mutate] of [
  ["wrong game identity", d => { d.game.game_pk = 123456; }],
  ["wrong game schema", d => { d.schema = "different"; }],
  ["missing game pitch", d => { d.pitches.pop(); }],
  ["duplicate game key", d => { d.pitches[1] = structuredClone(d.pitches[0]); }],
  ["wrong game pitch key", d => { d.pitches[0].pitch_id = "849843:1:99"; }],
  ["noninteger PA", d => { d.pitches[0].at_bat_number = 1.5; d.pitches[0].pitch_id = "849843:1.5:1"; }],
  ["wrong game batter", d => { d.pitches[0].batter.id = 1; }],
  ["wrong game pitcher", d => { d.pitches[0].pitcher.id = 1; }],
  ["invalid game player ID", d => { d.pitches[0].batter.id = true; }],
]) test(`reject caller's ${name}`, () => {
  const source = structuredClone(game); mutate(source);
  assert.throws(() => validate(packet, source), TypeError);
});

test("missing or changed actual byte hash prevents activation", () => {
  for (const wrong of [undefined, null, "0".repeat(64), expectedSHA.toUpperCase()]) {
    assert.throws(() => createVerifiedZones(packet, game, wrong), /바이트/);
  }
  const changed = fixture(); changed.pitches[0].bottom_ft += 0.01;
  const changedBytes = Buffer.from(JSON.stringify(changed));
  assert.notEqual(sha(changedBytes), expectedSHA);
  assert.throws(() => createVerifiedZones(changed, game, sha(changedBytes)), /바이트/);
});

test("browser global exports the same verified API without CommonJS", () => {
  const context = vm.createContext({});
  vm.runInContext(fs.readFileSync(path.join(__dirname, "../../web/pitch-studio/game-catalog.js"), "utf8"), context);
  const source = fs.readFileSync(path.join(__dirname, "../../web/pitch-studio/receiver-zones.js"), "utf8");
  vm.runInContext(source, context);
  const api = context.PitchReceiverZones;
  assert.equal(typeof api.createVerifiedZones, "function");
  assert.equal(api.expectedSHA, expectedSHA);
  assert.equal(api.expectedGameSHA, expectedGameSHA);
  const zones = api.createVerifiedZones(packet, game, sha(assetBytes));
  assert.equal(Object.keys(zones).length, 262);
  assert.equal(zones["849843:2:1"].bottom, 1.57765748);
  assert.ok(Object.isFrozen(api));
});

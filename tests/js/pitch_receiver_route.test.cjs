"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const {parse, query, FIRST} = require("../../web/pitch-studio/receiver-route.js");
const {createSession} = require("../../web/pitch-studio/receiver-fullgame.js");
const game = require("../../web/pitch-studio/game-849843.json");
test("all 262 exact pitch links round trip and restore with results hidden", () => {
  const session = createSession(game);
  for (const p of game.pitches) {
    const route = parse(query("game", p.pitch_id));
    session.reveal(true);
    session.select(route.pitchId);
    assert.equal(session.view().pitch_id, p.pitch_id);
    assert.equal(session.view().post, null);
    assert.equal(session.view().revealed, false);
  }
});
test("old first PA links become full game links without losing the selected pitch", () => {
  for (const n of [1,2,3]) {
    const r = parse(`?demo=849843-pa1&pitch=${n}`);
    assert.deepEqual(r, {mode:"game",pitchId:`849843:1:${n}`});
    assert.equal(parse(query(r.mode,r.pitchId)).pitchId,r.pitchId);
  }
  assert.equal(parse("").pitchId,FIRST);
});
test("explicit old archive and private file modes remain distinct", () => {
  assert.deepEqual(parse(query("archive","849843:1:3")),{mode:"archive",pitchId:"849843:1:3"});
  assert.deepEqual(parse(query("file",null)),{mode:"file",pitchId:null});
  assert.throws(()=>query("archive","849843:2:1"));
});
test("malformed, conflicting and different-game identities cannot select a pitch", () => {
  for (const q of ["?game=849844","?game=0849843","?game=849843&game=849843","?pitch=849844:1:1","?pitch=849843:0:1","?pitch=849843:1:0","?pitch=849843:1:101","?pitch=NaN","?pitch=","?pitch=849843:1:1&pitch=849843:2:1","?archive=first-pa&pitch=849843:2:1","?archive=other","?demo=unknown"])
    assert.throws(()=>parse(q), q);
  const session=createSession(game);
  assert.throws(()=>session.select(parse("?game=849843&pitch=849843:99:1").pitchId));
});
test("URL extras cannot reveal future outcomes or change model input", () => {
  const r = parse("?game=849843&pitch=849843:2:1&revealed=true&actual=home_run");
  const session=createSession(game); session.select(r.pitchId);
  assert.equal(session.view().post,null);
  assert.doesNotMatch(query(r.mode,r.pitchId), /revealed|actual/);
});

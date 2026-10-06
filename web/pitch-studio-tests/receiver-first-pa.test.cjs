"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const fs = require("node:fs"), path = require("node:path"), vm = require("node:vm");
const site = fs.existsSync(path.join(__dirname, "../dist")) ? path.join(__dirname, "../dist") : path.join(__dirname, "../pitch-studio");
const { validate, createSession, observation } = require(path.join(site, "receiver-contract.js"));
const demo = require(path.join(site, "receiver-demo-849843.js"));
const records = { window: {} };
vm.runInNewContext(fs.readFileSync(path.join(site, "data.js"), "utf8"), records);
test("real first PA uses original keys and unscaled pitch selection shares", () => {
  const data = validate(demo.packet);
  assert.deepEqual(data.decisions.map(d=>d.pitch_id), ["849843:1:1", "849843:1:2", "849843:1:3"]);
  assert.deepEqual(data.decisions.map(d=>d.pre.candidates[0].pitch_type), ["ST", "CH", "SI"]);
  assert.deepEqual(data.decisions.map(d=>d.pre.candidates[0].selection_probability), [.2747000042139988, .4070252755337158, .3303230709313974]);
  for(const d of data.decisions) assert(d.pre.candidates.reduce((s,c)=>s+c.selection_probability,0)<1);
  assert.equal(data.decisions[0].pre.candidates[0].zone_id, "low_middle");
});
test("first PA shows mitt only on third pitch after reveal and hides on rewind", () => {
  const session = createSession(demo.packet);
  for(let i=0;i<3;i++) {
    assert.equal(session.view().post,null);
    assert.equal(observation(session.view(),records.window.DEMO_DATA.pitches),null);
    session.reveal(true);
    const v=session.view(),mitt=observation(v,records.window.DEMO_DATA.pitches);
    assert.equal(v.pitcher.name,"Michael King"); assert.equal(v.batter.name,"Pete Crow-Armstrong");
    assert.equal(v.post.actual.pitch_type,["SI","ST","FF"][i]);
    assert.equal(mitt.status,i===2?"key_matched":"missing");
    assert.equal(mitt.x,i===2?-.05172667411468945:null);
    if(i<2) assert(session.next());
  }
  assert.equal(session.view().post.actual.result_label,"삼진");
  assert.equal(session.view().post.we.home_delta,.024007574284530042);
  assert.equal(session.next(),false); session.previous(); assert.equal(session.view().post,null);
});
test("generation provenance does not claim current backend version", () => {
  assert.equal(demo.packet.source.revision,"2eb718ef13024ad2d98d28e248388db7f8dc1bc9");
  assert.equal(demo.packet.source.exported_at,"2026-09-30T17:48:53+09:00");
  assert.match(demo.packet.source.model_id,/ARM-B P3/);
  assert.equal(demo.provenance.loaded_backend_commit,null);
  assert.equal(demo.originals.length,5);
  assert.equal(demo.packet.timeline.decisions.length,3);
  assert(!/100\.108\.|\/Users\/|serving_worktree|process_started|observer-zone-v1/.test(JSON.stringify(demo)));
});
test("only known named zones are accepted without conversion", () => {
  for(const z of ["high_left","high_middle","high_right","middle_left","middle_middle","middle_right","low_left","low_middle","low_right"]) {
    const p=structuredClone(demo.packet);p.timeline.decisions[0].pre.recommendation.candidates[0].zone_id=z;
    assert.equal(validate(p).decisions[0].pre.candidates[0].zone_id,z);
  }
  for(const z of ["outside","low_center","7","",{},10]) {
    const p=structuredClone(demo.packet);p.timeline.decisions[0].pre.recommendation.candidates[0].zone_id=z;
    assert.throws(()=>validate(p));
  }
});

"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const {validate,createSession,observation} = require("../../web/pitch-studio/receiver-fullgame.js");
const fixture = require("../../web/pitch-studio/game-849843.json");
const sample=()=>structuredClone(fixture);
test("actual archive contains 262 keyed pitches, 71 PAs, 246 recommendations and 16 unsupported",()=>{
  const s=createSession(fixture);
  assert.deepEqual(s.view().summary,{pitches:262,plate_appearances:71,ready:246,unsupported:16,missing:0});
  assert.equal(s.groups().length,71); assert.equal(s.groups().at(-1).keys.at(-1),"849843:71:6");
  assert.equal(s.view().source.revision,null); assert.equal(s.view().source.exported_at,null);
  assert.equal(s.view().source.sha256,"df606a11c6db465c054252ef8d331aeb23aa21565b4960bd586f3dcf8f62f6b7");
});
test("every pitch hides actual and setup until reveal, then exposes only same-key result",()=>{
  const s=createSession(fixture);let estimated=0,unavailable=0,missing=0;
  for(const p of fixture.pitches){
    s.select(p.pitch_id);const before=s.view();
    assert.equal(before.pitch_id,p.pitch_id);assert.equal(before.post,null);assert.equal(before.can_next,false);
    assert.deepEqual(observation(before),{status:"missing",x:null});
    assert.equal("pitches" in before,false);assert.equal("reason" in before.pre,false);
    s.reveal(true);const after=s.view();assert.deepEqual(after.post.actual,p.post.actual);
    assert.equal(after.post.we,null);
    const o=observation(after);if(o.status==="estimated") estimated++;else if(o.status==="unavailable")unavailable++;else missing++;
    assert.equal(o.x,p.post.setup?.x??null);
  }
  assert.deepEqual({estimated,unavailable,missing},{estimated:27,unavailable:12,missing:223});
});
test("PA1 to PA2, unsupported PA and last pitch navigate without retaining result",()=>{
  const s=createSession(fixture);s.select("849843:1:3");s.reveal(true);assert.equal(s.next(),true);
  assert.equal(s.view().pitch_id,"849843:2:1");assert.equal(s.view().post,null);
  s.select("849843:41:1");assert.equal(s.view().pre.status,"unsupported");assert.deepEqual(s.view().pre.candidates,[]);
  s.reveal(true);assert.ok(s.view().post.actual);s.previous();assert.equal(s.view().post,null);
  s.select("849843:71:6");s.reveal(true);assert.equal(s.next(),false);assert.equal(s.view().can_next,false);
  s.select("849843:1:1");assert.equal(s.previous(),false);assert.equal(s.view().post,null);
  assert.throws(()=>s.select("849843:99:1"));assert.throws(()=>s.reveal("true"));
});
test("input array order does not define pitch identity or playback order",()=>{
  const d=sample();d.pitches.reverse();const s=createSession(d);
  assert.equal(s.view().pitch_id,"849843:1:1");s.select("849843:71:6");s.reveal(true);
  assert.deepEqual(s.view().post.actual,fixture.pitches.at(-1).post.actual);
});
test("nullable values remain unavailable rather than zero or invented WE",()=>{
  const d=sample(),p=d.pitches[0];p.pre.candidates[0].selection_probability=null;p.pre.candidates[0].target=null;
  p.post.actual=null;p.post.setup=null; const s=createSession(d);s.reveal(true);
  assert.equal(s.view().pre.candidates[0].selection_probability,null);assert.equal(s.view().post.actual,null);
  assert.deepEqual(observation(s.view()),{status:"missing",x:null});
  const missing=sample();missing.pitches[0].pre.status="missing";missing.pitches[0].pre.candidates=[];
  assert.equal(createSession(missing).view().pre.status,"missing");
});
test("candidate selection shares are not normalized to 100 percent",()=>{
  const s=createSession(fixture),c=s.view().pre.candidates;
  assert.equal(c[0].selection_probability,0.2747000042139988);
  assert.ok(Math.abs(c.reduce((n,c)=>n+c.selection_probability,0)-0.7982791944412062)<1e-12);
});
test("caller mutations cannot alter session state or navigation",()=>{
  const d=sample(),s=createSession(d);d.pitches[0].post.actual.x=9;
  const v=s.view();v.pre.candidates[0].selection_probability=1;s.groups()[0].keys.reverse();
  assert.equal(s.groups()[0].keys[0],"849843:1:1");assert.notEqual(s.view().pre.candidates[0].selection_probability,1);
  s.reveal(true);assert.equal(s.view().post.actual.x,fixture.pitches[0].post.actual.x);
});
for(const [name,mutate] of [
  ["duplicate key",d=>d.pitches.push(structuredClone(d.pitches[0]))],
  ["duplicate index",d=>{d.pitches[1].index=0;}],
  ["wrong game key",d=>{d.pitches[0].pitch_id="849844:1:1";}],
  ["wrong PA",d=>{d.pitches[0].at_bat_number=2;}],
  ["contradictory sequence",d=>{d.pitches[0].index=9999;}],
  ["raw reason",d=>{d.pitches[0].pre.reason="private diagnostic";}],
  ["future result in pre",d=>{d.pitches[0].pre.actual=d.pitches[0].post.actual;}],
  ["PA outcome on early pitch",d=>{d.pitches[0].post.actual.event="strikeout";}],
  ["extra play text",d=>{d.pitches[0].post.actual.play_text="not allowed";}],
  ["invented WE",d=>{d.pitches[0].post.we={home_after:.9};}],
  ["invented source revision",d=>{d.source.revision="a".repeat(40);}],
  ["malformed source hash",d=>{d.source.sha256="bad";}],
  ["invalid date",d=>{d.game.date="2026-02-30";}],
  ["wrong units",d=>{d.units.position="pixels";}],
  ["unsupported with candidates",d=>{d.pitches[0].pre.status="unsupported";}],
  ["repeated candidate",d=>{d.pitches[0].pre.candidates[1].rank=1;}],
  ["negative share",d=>{d.pitches[0].pre.candidates[0].selection_probability=-.1;}],
  ["sum over one",d=>{d.pitches[0].pre.candidates[0].selection_probability=1;}],
  ["NaN coordinate",d=>{d.pitches[0].post.actual.x=NaN;}],
  ["infinite setup",d=>{d.pitches[2].post.setup.x=Infinity;}],
  ["unavailable with point",d=>{d.pitches[2].post.setup.status="unavailable";}],
  ["unmeasured claim promoted",d=>{d.claims.live_timing_verified=true;}],
]) test(`reject ${name}`,()=>{const d=sample();mutate(d);assert.throws(()=>validate(d));});

"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const { validate, createSession, observation } = require("../../web/pitch-studio/receiver-contract.js");
const fixture = require("../../web/pitch-studio/receiver-sample.js");
const sample = () => structuredClone(fixture);
const corrupt = (mutate) => { const x = sample(); mutate(x); assert.throws(() => validate(x)); };
test("top candidates retain their 75% total instead of becoming event probabilities", () => {
  const data = validate(sample());
  assert.equal(data.decisions[0].pre.candidates[0].selection_probability, .48);
  assert.equal(data.decisions[0].pre.candidates.reduce((s,c) => s+c.selection_probability, 0), .75);
  assert.equal(data.decisions[0].pre.candidates[1].target, null);
  assert.equal(data.decisions[1].pre.status, "unsupported");
  assert.equal("outcome_probabilities" in data.decisions[0].pre, false);
});
test("array reordering cannot change pitch-to-reveal binding", () => {
  const x = sample(); x.timeline.decisions.reverse(); x.reveals.reverse();
  const d = validate(x).decisions;
  assert.deepEqual(d.map(p => p.index), [14,15,16]);
  assert.equal(d[1].post.actual.x, null);
});
test("pre view withholds post, raw status, reason, and future decisions", () => {
  const x = sample(); x.timeline.decisions[0].status = "AFTER_EVENT_DIAGNOSTIC";
  x.timeline.decisions[0].pre.reason = "DO_NOT_DISPLAY";
  x.timeline.decisions[1].situation.home_score = 9;
  const s = createSession(x), v = s.view();
  assert.equal(v.post, null); assert.equal(v.can_next, false);
  assert.equal("status" in v, false); assert.equal("reason" in v.pre, false);
  assert.equal("decisions" in v, false); assert.equal(v.situation.home_score, 0);
  assert.equal(s.next(), false); assert.equal(s.view().index,14);
});
test("hide, next and rewind reset result disclosure", () => {
  const s = createSession(sample());
  s.reveal(true); assert.notEqual(s.view().post, null);
  assert.equal(s.next(), true); assert.equal(s.view().index, 15); assert.equal(s.view().post, null);
  s.reveal(true); assert.equal(s.view().post.actual.x, null);
  s.previous(); assert.equal(s.view().post, null);
  s.reveal(true); s.reveal(false); assert.equal(s.view().post, null);
  assert.throws(() => s.reveal("true"));
});
test("view objects cannot mutate internal state", () => {
  const s=createSession(sample()); const v=s.view(); v.pre.candidates[0].selection_probability=1;
  assert.equal(s.view().pre.candidates[0].selection_probability,.48);
});
for (const [name, mutate] of [
  ["raw final score", x => {x.timeline.game.final={home:9};}],
  ["raw actual result", x => {x.timeline.decisions[0].actual={x:1};}],
  ["raw WE", x => {x.timeline.decisions[0].we={};}],
  ["duplicate decision", x => x.timeline.decisions.push(x.timeline.decisions[0])],
  ["duplicate reveal", x => {x.reveals[1]=x.reveals[0];}],
  ["wrong reveal pitch key", x => {x.reveals[0].pitch_id="900001:5:2";}],
  ["other game endpoint", x => {x.reveals[0].source_endpoint="/api/watch/849843/reveal/14";}],
  ["wrong game identity", x => {x.game_pk=849843;}],
  ["wrong PA", x => {x.timeline.decisions[0].pa_id="900001:6";}],
  ["wrong index", x => {x.reveals[0].response.index=99;}],
  ["missing reveal", x => x.reveals.pop()],
  ["noninteger index", x => {x.timeline.decisions[0].index=.1;}],
  ["number as string", x => {x.timeline.decisions[0].situation.balls="1";}],
  ["illegal count", x => {x.timeline.decisions[0].situation.strikes=3;}],
  ["illegal runner mask", x => {x.timeline.decisions[0].situation.bases=8;}],
  ["renumbered pitch order", x => {x.timeline.decisions[0].pitch_number=5;}],
  ["negative probability", x => {x.timeline.decisions[0].pre.recommendation.candidates[0].detail.probability=-.1;}],
  ["overfull selection probability", x => {x.timeline.decisions[0].pre.recommendation.candidates[0].detail.probability=.9;}],
  ["nonfinite coordinate", x => {x.reveals[0].response.actual.x=Infinity;}],
  ["unsupported nonnull recommendation", x => {x.timeline.decisions[1].pre.recommendation={candidates:[]};}],
  ["unknown source field", x => {x.source.actual={};}],
  ["unknown decision identity", x => {x.timeline.decisions[0].pitch_id="wrong";}],
  ["unselected malformed PA", x => {const d=structuredClone(x.timeline.decisions[0]);d.index=99;d.pa_id="900001:6";d.at_bat_number=6;d.situation=null;x.timeline.decisions.push(d);}],
  ["arbitrary hand text", x => {x.timeline.decisions[0].pitcher.hand="after result";}],
  ["inconsistent WE arithmetic", x => {x.reveals[0].response.we.home_delta=.8;}],
  ["wrong batting WE sign", x => {x.reveals[0].response.we.batting_delta=.01;}],
]) test(`rejects ${name}`, () => corrupt(mutate));
test("null outcomes and WE remain unavailable, never zero", () => {
  const x=sample(); for (const key of Object.keys(x.reveals[0].response.we)) x.reveals[0].response.we[key]=null;
  x.reveals[0].response.actual.x=null;
  const s=createSession(x); s.reveal(true);
  assert.equal(s.view().post.actual.x,null); assert.equal(s.view().post.we.home_delta,null);
});
test("no CV coordinates before reveal or on synthetic records", () => {
  const s=createSession(sample()); const fake={"900001:5:1":{mitt_x_ft:1}};
  assert.equal(observation(s.view(),fake),null); s.reveal(true);
  assert.equal(observation(s.view(),fake).status,"synthetic");
});
test("CV key, names and pitch type must all match after reveal", () => {
  const x=sample();x.source.kind="provided_export";const s=createSession(x);s.reveal(true);
  const record={pitch_id:"900001:5:1",pitcher:"테스트 투수",batter:"테스트 타자",pitch_type:"SI",status:"estimated",mitt_x_ft:-.1};
  assert.deepEqual(observation(s.view(),{}),{status:"missing",x:null});
  const records={[record.pitch_id]:record};
  assert.deepEqual(observation(s.view(),records),{status:"key_matched",x:-.1});
  record.pitch_type="FF";assert.equal(observation(s.view(),records).status,"conflict");
  record.pitch_type="SI";record.pitcher="다른 투수";assert.equal(observation(s.view(),records).status,"conflict");
  record.pitcher="테스트 투수";record.status="unavailable";record.mitt_x_ft=null;
  assert.deepEqual(observation(s.view(),records),{status:"unavailable",x:null});
});

"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { build, marker, referenceZone, screenX, horizontalTicks, perspectiveInfo } = require("../../web/pitch-studio/receiver-location.js");
const { createSession } = require("../../web/pitch-studio/receiver-contract.js");
const fixture = require("../../web/pitch-studio/receiver-sample.js");
const supplied = require("../../web/pitch-studio/receiver-demo-849843.js");
const sample = () => structuredClone(fixture);
const view = () => createSession(sample()).view();

test("reference outline is a fixed 17-inch guide, never a batter-specific recorded zone", () => {
  const reference = referenceZone();
  assert.equal(reference.bottom, 1.5); assert.equal(reference.top, 3.5);
  assert.notEqual(reference.source, "statcast_record");
  assert(Math.abs(reference.nw * 4 - 17 / 12) < 1e-12);
  assert(Math.abs(reference.nx + reference.nw / 2 - 0.5) < 1e-12);
  assert(Math.abs(reference.ny - 0.3) < 1e-12); assert(Math.abs(reference.nh - 0.4) < 1e-12);
});

test("reference geometry does not turn hidden recorded zone or actual result into pre-pitch data", () => {
  const source = view();
  Object.defineProperty(source, "post", { get() { throw new Error("post must remain unread"); } });
  const recorded = { source: "statcast_record", bottom: 1.62, top: 3.41 };
  const before = build(source, recorded);
  assert.equal(before.zone, null); assert.equal(before.actual, null);
  assert.equal(referenceZone().bottom, 1.5);
  const session = createSession(sample()); session.reveal(true);
  const after = build(session.view(), recorded);
  assert.equal(after.zone.source, "statcast_record"); assert.equal(after.zone.bottom, 1.62);
  assert.equal(after.zone.top, 3.41); assert.equal(referenceZone().top, 3.5);
});

test("validated pre-pitch view projects recommended positions without result or probabilities", () => {
  const source = view();
  const model = build(source);
  assert.equal(model.pitch_id, "900001:5:1");
  assert.deepEqual(model.domain, { xMin: -2, xMax: 2, zMin: 0, zMax: 5 });
  assert.equal(model.revealed, false);
  assert.equal(model.actual, null);
  assert.deepEqual(model.recommendations, [
    { rank: 1, label: "싱커", x: -.4, z: 1.8, status: "plottable", nx: .4, ny: .64 },
    { rank: 2, label: "슬라이더", x: null, z: null, status: "missing", nx: null, ny: null },
  ]);
  assert.deepEqual(model.groups, [{ ranks: [1], label: "1", x: -.4, z: 1.8, nx: .4, ny: .64 }]);
  assert.equal(source.pre.candidates[0].selection_probability, .48);
  assert.doesNotMatch(JSON.stringify(model), /probability|distance|mitt|intent/);
});

test("reveal, next, previous, hide, and reset cannot retain a prior actual point", () => {
  const session = createSession(sample());
  session.reveal(true);
  assert.deepEqual(build(session.view()).actual,
    { label: "싱커", x: -.3, z: 1.9, status: "plottable", nx: .425, ny: .62 });
  assert.equal(session.next(), true);
  let model = build(session.view());
  assert.equal(model.pitch_id, "900001:5:2");
  assert.equal(model.actual, null);
  assert.deepEqual(model.recommendations, []);
  session.reveal(true);
  assert.equal(build(session.view()).actual.status, "missing");
  session.previous();
  model = build(session.view());
  assert.equal(model.pitch_id, "900001:5:1");
  assert.equal(model.actual, null);
  session.reveal(true);
  session.reveal(false);
  assert.equal(build(session.view()).actual, null);
  assert.equal(build(null), null);
  assert.equal(build(createSession(sample()).view()).actual, null);
});

test("hidden or nonboolean reveal states do not even read a leaked post object", () => {
  for (const revealed of [false, undefined, null, "true", 1]) {
    const source = view();
    source.revealed = revealed;
    Object.defineProperty(source, "post", { get() { throw new Error("post must remain unread"); } });
    const model = build(source);
    assert.equal(model.revealed, false);
    assert.equal(model.actual, null);
  }
});

test("null, missing, nonfinite, strings and booleans never become coordinate zero", () => {
  for (const invalid of [null, undefined, NaN, Infinity, -Infinity, "0", false]) {
    for (const axis of ["x", "z"]) {
      const source = view();
      source.revealed = true;
      source.pre.candidates[0].target = { x: .25, z: 2.25, [axis]: invalid };
      source.post = { actual: { pitch_label: "시험", x: .25, z: 2.25, [axis]: invalid } };
      const model = build(source);
      for (const point of [model.recommendations[0], model.actual]) {
        assert.equal(point.status, "missing");
        assert.equal(point[axis], null);
        assert.equal(point[axis === "x" ? "z" : "x"], axis === "x" ? 2.25 : .25);
        assert.equal(point.nx, null);
        assert.equal(point.ny, null);
      }
      assert.deepEqual(model.groups, []);
    }
  }
});

test("zero and the four exact domain corners are plotted in the fixed orientation", () => {
  for (const [x, z, nx, ny] of [[-2, 0, 0, 1], [-2, 5, 0, 0], [2, 0, 1, 1], [2, 5, 1, 0], [0, 0, .5, 1]]) {
    const packet = sample();
    packet.timeline.decisions[0].pre.recommendation.candidates[0].target = { x, z };
    packet.reveals[0].response.actual.x = x;
    packet.reveals[0].response.actual.z = z;
    const session = createSession(packet);
    session.reveal(true);
    const model = build(session.view());
    for (const point of [model.recommendations[0], model.actual]) {
      assert.equal(point.status, "plottable");
      assert.equal(point.x, x);
      assert.equal(point.z, z);
      assert.equal(point.nx, nx);
      assert.equal(point.ny, ny);
    }
  }
});

test("out-of-domain values remain exact and are never clamped onto the chart edge", () => {
  for (const [x, z] of [[-2.00001, 2], [2.00001, 2], [0, -.00001], [0, 5.00001], [3.125, 7.25]]) {
    const packet = sample();
    packet.timeline.decisions[0].pre.recommendation.candidates[0].target = { x, z };
    packet.reveals[0].response.actual.x = x;
    packet.reveals[0].response.actual.z = z;
    const session = createSession(packet);
    session.reveal(true);
    const model = build(session.view());
    for (const point of [model.recommendations[0], model.actual]) {
      assert.deepEqual([point.x, point.z, point.status, point.nx, point.ny], [x, z, "outside", null, null]);
    }
    assert.deepEqual(model.groups, []);
  }
});

test("coincident recommendation markers retain every rank and original candidate row", () => {
  const packet = sample();
  const candidates = packet.timeline.decisions[0].pre.recommendation.candidates;
  candidates[1].zone_id = candidates[0].zone_id;
  candidates[1].target = structuredClone(candidates[0].target);
  candidates.push({ ...structuredClone(candidates[0]), rank: 3, pitch_type: "CH", pitch_label: "체인지업",
    target: { x: -.40000001, z: 1.8 }, detail: { probability: .1 } });
  const source = createSession(packet).view();
  const model = build(source);
  assert.deepEqual(model.recommendations.map(({ rank, label }) => ({ rank, label })),
    [{ rank: 1, label: "싱커" }, { rank: 2, label: "슬라이더" }, { rank: 3, label: "체인지업" }]);
  assert.deepEqual(model.groups.map(({ ranks, label }) => ({ ranks, label })),
    [{ ranks: [1, 2], label: "1·2" }, { ranks: [3], label: "3" }]);
  assert.notEqual(model.groups[0].nx, model.groups[1].nx);
});

test("unsupported or missing recommendation status ignores accidentally retained candidates", () => {
  for (const status of ["unsupported", "missing", undefined]) {
    const source = view();
    source.pre.status = status;
    const model = build(source);
    assert.deepEqual(model.recommendations, []);
    assert.deepEqual(model.groups, []);
  }
});

test("crowded rank markers remain bounded and keep the full numeric rows", () => {
  for (const count of [3, 10, 30]) {
    const source = view();
    source.pre.candidates = Array.from({length:count}, (_, i) => ({
      ...source.pre.candidates[0], rank:i+1, target:{x:0,z:2},
    }));
    const model = build(source);
    const group = model.groups[0];
    const display = marker(group);
    assert.equal(group.ranks.length, count);
    assert.equal(model.recommendations.length, count);
    assert.equal(display.text, count === 3 ? "1·2·3" : `1+${count-1}`);
    assert.ok(display.width >= 7 * display.text.length + 10);
    assert.ok(display.width <= 59);
    assert.equal(group.nx, .5);
    assert.equal(group.ny, .6);
  }
});

test("revealed view with absent actual returns no point rather than a fabricated missing result", () => {
  for (const post of [null, undefined, {}, { actual: null }]) {
    const source = view();
    source.revealed = true;
    source.post = post;
    assert.equal(build(source).actual, null);
  }
});

test("supplied first-PA packet keeps exact per-pitch coordinates and original endpoint bindings", () => {
  const packet = structuredClone(supplied.packet);
  const endpoints = packet.reveals.map((row) => row.source_endpoint);
  packet.timeline.decisions.reverse();
  packet.reveals.reverse();
  const session = createSession(packet);
  for (let pitch = 1; pitch <= 3; pitch++) {
    const key = `849843:1:${pitch}`;
    const raw = packet.reveals.find((row) => row.pitch_id === key);
    const pre = build(session.view());
    assert.equal(pre.pitch_id, key);
    assert.equal(pre.actual, null);
    session.reveal(true);
    const model = build(session.view());
    assert.equal(model.pitch_id, key);
    assert.equal(model.actual.x, raw.response.actual.x);
    assert.equal(model.actual.z, raw.response.actual.z);
    assert.equal(model.actual.label, raw.response.actual.pitch_label);
    assert.equal(raw.source_endpoint, endpoints[pitch - 1]);
    if (pitch < 3) assert.equal(session.next(), true);
  }
});

test("model changes do not mutate validated views, and each build owns its domain and groups", () => {
  const source = view();
  const before = structuredClone(source);
  const first = build(source);
  first.domain.xMin = -99;
  first.recommendations[0].x = 99;
  first.groups[0].ranks.push(30);
  assert.deepEqual(source, before);
  const next = build(source);
  assert.equal(next.domain.xMin, -2);
  assert.equal(next.recommendations[0].x, -.4);
  assert.deepEqual(next.groups[0].ranks, [1]);
});

test("missing current identity fails instead of reusing a prior pitch", () => {
  build(view());
  for (const pitch_id of [null, undefined, "", "849843:1", "849843:1:0", 849843]) {
    const source = view();
    source.pitch_id = pitch_id;
    assert.throws(() => build(source), /투구 식별자/);
  }
  assert.equal(build(null), null);
});

test("browser UMD export needs no document or network capability", () => {
  const context = {};
  const source = fs.readFileSync(path.join(__dirname, "../../web/pitch-studio/receiver-location.js"), "utf8");
  vm.runInNewContext(source, context);
  assert.equal(typeof context.PitchReceiverLocation.build, "function");
  assert.equal(context.PitchReceiverLocation.build(null), null);
  assert.equal(context.PitchReceiverLocation.build(view()).pitch_id, "900001:5:1");
});

test("historical batter zone stays hidden until reveal and then uses exact plate width", () => {
  const v=view();
  Object.defineProperty(v,"post",{get(){throw new Error("future result");}});
  const z={bottom:1.616190945,top:3.202452428,source:"statcast_record"};
  const hidden=build(v,z);
  assert.equal(hidden.zone,null);
  assert.equal(hidden.actual,null);
  assert.deepEqual(hidden.recommendations,build(v).recommendations);
  const revealed={...view(),revealed:true};
  const result=build(revealed,z);
  assert.ok(Math.abs(result.zone.nw*4-17/12)<1e-12);
  assert.ok(Math.abs(result.zone.nh*5-(z.top-z.bottom))<1e-12);
  assert.deepEqual(result.recommendations,build(revealed).recommendations);
  assert.equal(build(v).zone,null);
  const other=build(revealed,{...z,bottom:1.5,top:3.1});
  assert.notEqual(result.zone.ny,other.zone.ny);
});
test("missing, inverted, nonfinite or out-of-view zone is never drawn as a valid boundary", () => {
  for(const z of [{bottom:2,top:1},{bottom:null,top:3},{bottom:1,top:Infinity},{bottom:-1,top:3},{bottom:1,top:6}])
    assert.throws(()=>build({...view(),revealed:true},{...z,source:"statcast_record"}));
  assert.throws(()=>build({...view(),revealed:true},{bottom:1,top:3,source:"guess"}));
});

test("849843 second pitch is right in catcher view and left in pitcher view without changing its recorded position", () => {
  const session = createSession(structuredClone(supplied.packet));
  session.reveal(true);
  assert.equal(session.next(), true);
  session.reveal(true);
  const source = session.view();
  assert.equal(source.pitch_id, "849843:1:2");
  assert.equal(source.post.actual.x, 1.282487876437138);
  assert.equal(source.post.actual.z, 1.4800826426424478);
  const catcher = build(source, null, "catcher");
  const pitcher = build(source, null, "pitcher");
  assert.ok(catcher.actual.nx > .5);
  assert.ok(pitcher.actual.nx < .5);
  assert.ok(Math.abs(catcher.actual.nx - .8206219691092845) < 1e-12);
  assert.ok(Math.abs(pitcher.actual.nx - .1793780308907155) < 1e-12);
  assert.equal(pitcher.actual.ny, catcher.actual.ny);
  assert.equal(pitcher.actual.x, source.post.actual.x);
  assert.equal(pitcher.actual.z, source.post.actual.z);
  assert.deepEqual(build(source).actual, catcher.actual);
});

test("perspective changes mirror every recommendation and grouped rank while preserving frozen inputs", () => {
  const session = createSession(structuredClone(supplied.packet));
  session.reveal(true); session.next(); session.reveal(true);
  const source = session.view(), before = structuredClone(source);
  const freeze = value => {
    if (value && typeof value === "object") {
      Object.values(value).forEach(freeze);
      Object.freeze(value);
    }
  };
  freeze(source);
  const catcher = build(source, null, "catcher"), pitcher = build(source, null, "pitcher");
  assert.equal(pitcher.recommendations.length, 3);
  assert.deepEqual(pitcher.recommendations.map(p => [p.rank, p.label, p.x, p.z, p.ny]),
    catcher.recommendations.map(p => [p.rank, p.label, p.x, p.z, p.ny]));
  for (let i = 0; i < catcher.recommendations.length; i++)
    assert.ok(Math.abs(catcher.recommendations[i].nx + pitcher.recommendations[i].nx - 1) < 1e-12);
  assert.deepEqual(pitcher.groups.map(p => [p.ranks, p.label, p.x, p.z, p.ny]),
    catcher.groups.map(p => [p.ranks, p.label, p.x, p.z, p.ny]));
  assert.deepEqual(pitcher.groups[0].ranks, [1, 3]);
  for (let i = 0; i < catcher.groups.length; i++)
    assert.ok(Math.abs(catcher.groups[i].nx + pitcher.groups[i].nx - 1) < 1e-12);
  assert.deepEqual(source, before);
  assert.deepEqual(build(source, null, "catcher"), catcher);
});

test("switching perspective never reads hidden actual or recorded-zone getters", () => {
  const source = view();
  Object.defineProperty(source, "post", { get() { throw new Error("hidden actual read"); } });
  const recorded = {};
  for (const key of ["source", "bottom", "top"])
    Object.defineProperty(recorded, key, { get() { throw new Error("hidden zone read"); } });
  for (const perspective of ["pitcher", "catcher", "pitcher"]) {
    const result = build(source, recorded, perspective);
    assert.equal(result.revealed, false);
    assert.equal(result.actual, null);
    assert.equal(result.zone, null);
    assert.equal(result.recommendations[0].status, "plottable");
  }
});

test("mirroring does not turn missing or outside coordinates into a visible edge point", () => {
  for (const [x, z, status] of [
    [null, 2, "missing"], [0, NaN, "missing"], [Infinity, 2, "missing"],
    ["0", 2, "missing"], [-2.0001, 2, "outside"], [2.0001, 2, "outside"],
    [0, -.0001, "outside"], [0, 5.0001, "outside"],
  ]) {
    const source = view();
    source.revealed = true;
    source.pre.candidates[0].target = { x, z };
    source.post = { actual: { pitch_label: "시험", x, z } };
    for (const perspective of ["catcher", "pitcher"]) {
      const result = build(source, null, perspective);
      for (const point of [result.recommendations[0], result.actual]) {
        assert.equal(point.status, status);
        assert.equal(point.nx, null);
        assert.equal(point.ny, null);
      }
      assert.deepEqual(result.groups, []);
    }
  }
});

test("recorded zone retains positive width, height and bounds in both perspectives", () => {
  const source = { ...view(), revealed: true };
  const recorded = Object.freeze({ source: "statcast_record", bottom: 1.616190945, top: 3.202452428 });
  const catcher = build(source, recorded, "catcher").zone;
  const pitcher = build(source, recorded, "pitcher").zone;
  for (const zone of [catcher, pitcher]) {
    assert.ok(zone.nw > 0 && zone.nh > 0);
    assert.ok(Math.abs(zone.nw * 4 - 17 / 12) < 1e-12);
    assert.ok(Math.abs(zone.nh * 5 - (recorded.top - recorded.bottom)) < 1e-12);
    assert.ok(Math.abs(zone.nx + zone.nw / 2 - .5) < 1e-12);
    assert.equal(zone.bottom, recorded.bottom);
    assert.equal(zone.top, recorded.top);
  }
  assert.ok(Math.abs(catcher.nx + pitcher.nx + catcher.nw - 1) < 1e-12);
  assert.equal(pitcher.nw, catcher.nw);
  assert.equal(pitcher.ny, catcher.ny);
  assert.equal(pitcher.nh, catcher.nh);
});

test("horizontal axis helpers agree with the plot and reject invalid or outside mitt positions", () => {
  assert.deepEqual(horizontalTicks(), [-2, -1, 0, 1, 2]);
  assert.deepEqual(horizontalTicks("catcher"), [-2, -1, 0, 1, 2]);
  assert.deepEqual(horizontalTicks("pitcher"), [2, 1, 0, -1, -2]);
  for (const perspective of ["catcher", "pitcher"]) {
    horizontalTicks(perspective).forEach((x, index) => assert.equal(screenX(x, perspective), index / 4));
    assert.equal(screenX(0, perspective), .5);
    for (const invalid of [null, undefined, NaN, Infinity, -Infinity, "0", false, -2.001, 2.001])
      assert.equal(screenX(invalid, perspective), null);
    const source = view();
    source.pre.candidates[0].target = { x: 1.282487876437138, z: 2 };
    assert.equal(build(source, null, perspective).recommendations[0].nx, screenX(1.282487876437138, perspective));
    const info = perspectiveInfo(perspective);
    assert.equal(typeof info.label, "string"); assert.ok(info.label.trim());
    assert.equal(typeof info.description, "string"); assert.ok(info.description.trim());
  }
  assert.equal(screenX(-1), .25);
  assert.notEqual(perspectiveInfo("catcher").label, perspectiveInfo("pitcher").label);
});

test("unknown perspectives fail explicitly instead of silently changing coordinate meaning", () => {
  for (const perspective of ["", "broadcast", "Pitcher", null, false, 1]) {
    assert.throws(() => build(view(), null, perspective));
    assert.throws(() => screenX(0, perspective));
    assert.throws(() => horizontalTicks(perspective));
    assert.throws(() => perspectiveInfo(perspective));
  }
});

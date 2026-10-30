"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const fs = require("node:fs"), path = require("node:path");
const site = fs.existsSync(path.join(__dirname, "../dist")) ? "../dist" : "../pitch-studio";
const { create } = require(path.join(__dirname, site, "receiver-sequence.js"));

function setup(options = {}) {
  const state = { enabled: true, binding: "load1:849843:1:1", pa: 1,
    pitchId: "849843:1:1", nextId: "849843:1:2", hasVideo: true, revealed: false };
  const notices = [], timers = [], advances = [], starts = [], cancelled = [];
  const controller = create({
    getState: () => ({ ...state }),
    startClip: () => { starts.push(state.pitchId); state.revealed = false; return options.play?.() ?? Promise.resolve(true); },
    advance: key => {
      advances.push(key);
      Object.assign(state, { binding: `load1:${key}`, pitchId: key, revealed: false,
        nextId: key.endsWith(":3") ? null : "849843:1:3" });
      options.afterAdvance?.(state);
    },
    onChange: value => { notices.push(value); options.onChange?.(value, controller); },
    schedule: (fn, delay) => { const timer = { fn, delay }; timers.push(timer); return timer; },
    cancel: timer => cancelled.push(timer),
  });
  const finish = () => { state.revealed = true; controller.ended(state.binding); };
  return { controller, state, notices, timers, advances, starts, cancelled, finish };
}
const flush = () => new Promise(resolve => setImmediate(resolve));

test("opt-in starts current pitch, waits five seconds, then plays only the same PA", () => {
  const s = setup();
  assert.equal(s.controller.isActive(), false);
  assert.equal(s.starts.length, 0);
  assert.equal(s.controller.start(), true);
  assert.deepEqual(s.starts, ["849843:1:1"]);
  s.finish();
  assert.equal(s.timers[0].delay, 5000);
  assert.deepEqual(s.notices.at(-1), { active: true, phase: "waiting", reason: "waiting" });
  assert.equal(s.advances.length, 0);
  s.timers[0].fn();
  assert.deepEqual(s.advances, ["849843:1:2"]);
  assert.equal(s.state.revealed, false);
  assert.equal(s.starts.at(-1), "849843:1:2");
});

test("last pitch keeps its result and stops without crossing the PA boundary", () => {
  const s = setup(); s.controller.start(); s.finish(); s.timers[0].fn();
  s.finish(); s.timers[1].fn(); s.finish();
  assert.equal(s.controller.isActive(), false);
  assert.equal(s.notices.at(-1).reason, "complete");
  assert.equal(s.state.pitchId, "849843:1:3");
  assert.equal(s.state.revealed, true);
  assert.equal(s.timers.length, 2);
});

test("duplicate ended and timer callbacks cannot skip a pitch", () => {
  const s = setup(); s.controller.start(); s.finish(); s.finish();
  assert.equal(s.timers.length, 1);
  s.timers[0].fn(); s.timers[0].fn();
  assert.deepEqual(s.advances, ["849843:1:2"]);
});

for (const reason of ["manual", "pause", "seek", "error", "hidden", "navigation"]) {
  test(`${reason} cancels automatic progression even if an old timer still fires`, () => {
    const s = setup(); s.controller.start(); s.finish(); s.controller.stop(reason);
    s.timers[0].fn();
    assert.equal(s.controller.isActive(), false);
    assert.equal(s.advances.length, 0);
    assert.equal(s.cancelled.length, 1);
    assert.equal(s.notices.at(-1).reason, reason);
  });
}

test("restart invalidates old timer and old ended binding", () => {
  const s = setup(); s.controller.start(); s.finish();
  const oldBinding = s.state.binding;
  Object.assign(s.state, { pitchId: "849843:1:2", binding: "load1:849843:1:2", nextId: "849843:1:3", revealed: false });
  s.controller.start(); s.timers[0].fn(); s.controller.ended(oldBinding);
  assert.equal(s.advances.length, 0); assert.equal(s.timers.length, 1);
  assert.equal(s.controller.isActive(), true);
});

test("unrevealed or wrong-binding ended events cannot schedule progression", () => {
  const s = setup(); s.controller.start();
  s.controller.ended(s.state.binding);
  s.state.revealed = true; s.controller.ended("load1:849843:2:1");
  assert.equal(s.timers.length, 0);
});

for (const patch of [
  { revealed: false }, { enabled: false }, { binding: "load2:849843:1:1" },
  { pitchId: "849843:2:1", pa: 2 }, { nextId: "849843:1:3" },
]) {
  test(`changed state before timer cannot advance: ${JSON.stringify(patch)}`, () => {
    const s = setup(); s.controller.start(); s.finish(); Object.assign(s.state, patch); s.timers[0].fn();
    assert.equal(s.advances.length, 0); assert.equal(s.controller.isActive(), false);
  });
}

test("missing initial or next video stops, never skips to another clip", () => {
  const s = setup(); s.state.hasVideo = false;
  assert.equal(s.controller.start(), false); assert.equal(s.starts.length, 0);
  const n = setup({ afterAdvance: state => { state.hasVideo = false; } });
  n.controller.start(); n.finish(); n.timers[0].fn();
  assert.equal(n.starts.length, 1); assert.equal(n.notices.at(-1).reason, "missing");
  assert.equal(n.state.revealed, false);
});

for (const patch of [{ pa: 2 }, { pitchId: "849843:2:1" }, { revealed: true }]) {
  test(`bad advance target does not start playback: ${JSON.stringify(patch)}`, () => {
    const s = setup({ afterAdvance: state => Object.assign(state, patch) });
    s.controller.start(); s.finish(); s.timers[0].fn();
    assert.equal(s.starts.length, 1); assert.equal(s.controller.isActive(), false);
  });
}

test("blocked or rejected play stops without a timer", async () => {
  for (const play of [() => Promise.resolve(false), () => Promise.reject(new Error("blocked")), () => { throw new Error("blocked"); }]) {
    const s = setup({ play }); s.controller.start(); await flush();
    assert.equal(s.controller.isActive(), false); assert.equal(s.notices.at(-1).reason, "blocked");
    assert.equal(s.advances.length, 0); assert.equal(s.timers.length, 0);
  }
});

test("late failed play promise cannot stop a restarted run", async () => {
  let fail, calls = 0;
  const s = setup({ play: () => ++calls === 1 ? new Promise((_, reject) => { fail = reject; }) : Promise.resolve(true) });
  s.controller.start(); s.controller.stop(); s.controller.start(); fail(new Error("late")); await flush();
  assert.equal(s.controller.isActive(), true); assert.equal(s.notices.at(-1).phase, "playing");
});

test("late false play promise after stop does not add a second stop", async () => {
  let resolve;
  const s = setup({ play: () => new Promise(done => { resolve = done; }) });
  s.controller.start(); s.controller.stop("pause"); const count = s.notices.length;
  resolve(false); await flush(); assert.equal(s.notices.length, count);
});

test("synchronous stop during notification prevents starting or scheduling", () => {
  const playing = setup({ onChange: (notice, controller) => { if (notice.phase === "playing") controller.stop(); } });
  playing.controller.start(); assert.equal(playing.starts.length, 0);
  const waiting = setup({ onChange: (notice, controller) => { if (notice.phase === "waiting") controller.stop(); } });
  waiting.controller.start(); waiting.finish(); assert.equal(waiting.timers.length, 0);
});

test("invalid input does not start playback", () => {
  for (const patch of [{ enabled: false }, { pa: NaN }, { binding: "" }, { nextId: undefined },
    { nextId: "849843:1:1" }, { nextId: "849843:2:1" }, { nextId: "849844:1:2" },
    { pitchId: "849843:2:1", pa: 1 }, { pitchId: "arbitrary" }]) {
    const s = setup(); Object.assign(s.state, patch);
    assert.equal(s.controller.start(), false); assert.equal(s.starts.length, 0);
  }
});

test("a cross-PA next ID is rejected before calling advance", () => {
  const s = setup(); s.controller.start(); s.finish();
  s.state.nextId = "849843:2:1";
  s.timers[0].fn();
  assert.equal(s.advances.length, 0);
  assert.equal(s.controller.isActive(), false);
});

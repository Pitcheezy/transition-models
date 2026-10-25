"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const vm = require("node:vm");
const { Controller, historyFor, visiblePoints, handleKey } = require("../web/track-review/review.js");

function fixture() {
  const pitch_id = "747139:3:1";
  const event = { pitch_id, frame_index: 101, frame_seconds: 10.1,
    available_frame: 101, available_seconds: 10.1, point_px: [600, 300] };
  const frames = [10, 10.1, 10.4].map((time, i) => ({
    frame_index: 100 + i, frame_seconds: time, width: 1280, height: 720,
    image: `frames/747139_3_1/${100 + i}.jpg`, sha256: "a".repeat(64),
    selection: { pitch_id, tracker_state: i === 2 ? "lost" : "tracking",
      selection_state: i === 1 ? "stationary" : i === 2 ? "unavailable" : "warming",
      reason: i === 2 ? "tracker_lost" : "waiting", current_track_point_px: i === 2 ? null : [600, 300],
      current_candidate: i === 1 ? { ...event } : null,
      last_historical_candidate: i > 0 ? { ...event } : null }
  }));
  return { schema: "pitcheezy-track-frame-view-dev-v1", time_basis: "manifest_index_timebase",
    independent_decoded_pts_verified: false,
    pitches: [{ pitch_id, play_id: "demo-1", frames }, {
      pitch_id: "747139:3:2", play_id: "demo-2", frames: frames.map((frame, i) => ({
        ...frame, frame_index: 200 + i, frame_seconds: 20 + i / 10,
        selection: { ...frame.selection, pitch_id: "747139:3:2", current_candidate: null,
          last_historical_candidate: null }
      }))
    }] };
}

function harness({ deferred = false } = {}) {
  const calls = [], views = [], timers = [];
  const controller = new Controller(fixture(), {
    loadImage: frame => deferred ? new Promise((resolve, reject) => calls.push({ frame, resolve, reject }))
      : Promise.resolve({ imageIndex: frame.frame_index }),
    onChange: view => views.push(view),
    setTimer: (callback, delay) => { timers.push({ callback, delay, cancelled: false }); return timers.length - 1; },
    clearTimer: index => { timers[index].cancelled = true; }
  });
  return { controller, calls, views, timers, last: () => views.at(-1) };
}
const flush = () => new Promise(resolve => setImmediate(resolve));

test("a slow earlier image cannot replace a later seek", async () => {
  const h = harness({ deferred: true });
  const first = h.controller.show(0), second = h.controller.seek(1);
  assert.equal(h.last().image, null);
  assert.equal(h.last().history, null);
  h.calls[1].resolve({ id: "new-image" }); await second;
  assert.equal(h.last().image.id, "new-image");
  const count = h.views.length;
  h.calls[0].resolve({ id: "old-image" }); await first;
  assert.equal(h.views.length, count);
  assert.equal(h.last().frame.frame_index, 101);
});

test("a slow historical image cannot leak after a backward seek", async () => {
  const h = harness({ deferred: true });
  const earlier = h.controller.show(2);
  h.calls[0].resolve({ id: "lost-current" }); await flush();
  assert.equal(h.calls[1].frame.frame_index, 101);
  assert.equal(h.last().historyPending, true);
  const later = h.controller.seek(0);
  assert.equal(h.last().historyPending, false);
  assert.equal(h.last().history, null);
  assert.equal(h.last().image, null);
  h.calls[2].resolve({ id: "before-event" }); await later;
  h.calls[1].resolve({ id: "history" }); await earlier;
  assert.equal(h.last().image.id, "before-event");
  assert.equal(h.last().history, null);
  assert.equal(h.last().historyPending, false);
});

test("an existing historical event stays pending until its thumbnail finishes", async () => {
  const h = harness({ deferred: true });
  const pending = h.controller.show(2);
  assert.equal(h.last().historyPending, false);
  h.calls[0].resolve({ id: "current" }); await flush();
  const loadedCurrent = h.views.filter(view => view.image);
  assert.equal(loadedCurrent.length, 1);
  assert.equal(loadedCurrent[0].historyPending, true);
  assert.equal(loadedCurrent[0].history, null);
  h.calls[1].resolve({ id: "history" }); await pending;
  assert.equal(h.last().historyPending, false);
  assert.equal(h.last().history.image.id, "history");
});

test("switching pitch clears a pending thumbnail and ignores its late failure", async () => {
  const h = harness({ deferred: true });
  const previous = h.controller.show(2);
  h.calls[0].resolve({ id: "current" }); await flush();
  assert.equal(h.last().historyPending, true);
  const next = h.controller.switchPitch(1);
  assert.equal(h.last().historyPending, false);
  h.calls[2].resolve({ id: "next-pitch" }); await next;
  h.calls[1].reject(new Error("late old history failure")); await previous;
  assert.equal(h.last().image.id, "next-pitch");
  assert.equal(h.last().historyPending, false);
  assert.equal(h.last().history, null);
  assert.equal(h.last().historyError, undefined);
});

test("current-image failure clears both panels and stops playback", async () => {
  const h = harness({ deferred: true });
  const ready = h.controller.show(1);
  h.calls[0].resolve({ id: "candidate" }); await ready;
  assert.ok(h.last().history);
  h.controller.toggle();
  const pending = h.controller.show(2);
  assert.equal(h.last().loading, true);
  assert.equal(h.last().image, null);
  assert.equal(h.last().history, null);
  h.calls[1].reject(new Error("missing frame")); await pending;
  assert.equal(h.last().playing, false);
  assert.equal(h.last().image, null);
  assert.equal(h.last().history, null);
  assert.equal(h.last().historyPending, false);
  assert.ok(h.last().error);
});

test("a failed historical thumbnail cannot keep an older thumbnail", async () => {
  const h = harness({ deferred: true });
  const pending = h.controller.show(2);
  h.calls[0].resolve({ id: "current" }); await flush();
  assert.equal(h.last().historyPending, true);
  h.calls[1].reject(new Error("missing history")); await pending;
  assert.equal(h.last().image.id, "current");
  assert.equal(h.last().history, null);
  assert.equal(h.last().historyError, true);
  assert.equal(h.last().historyPending, false);
});

test("lost rows have no current marker while history stays on its own frame", async () => {
  const h = harness();
  await h.controller.show(2);
  assert.deepEqual(visiblePoints(h.last().frame), { track: null, candidate: null });
  assert.equal(h.last().history.frame.frame_index, 101);
  assert.equal(h.last().frame.frame_index, 102);
  assert.equal(h.last().history.image.imageIndex, 101);
  // A malformed stale current point may not bypass the lost-state display guard.
  const stale = structuredClone(h.last().frame);
  stale.selection.current_track_point_px = [600, 300];
  stale.selection.current_candidate = h.last().history.event;
  assert.deepEqual(visiblePoints(stale), { track: null, candidate: null });
});

test("seeking back before an event shows only that earlier row's knowledge", async () => {
  const h = harness();
  await h.controller.show(1);
  assert.ok(h.last().history);
  await h.controller.seek(0);
  assert.equal(h.last().history, null);
  assert.equal(visiblePoints(h.last().frame).candidate, null);
});

test("future or other-pitch historical records are never rendered", () => {
  const pitch = fixture().pitches[0];
  const current = structuredClone(pitch.frames[2]);
  for (const changes of [
    { pitch_id: "747139:99:1" }, { frame_index: 999 }, { frame_seconds: 99 },
    { available_frame: 999 }, { available_seconds: 99 }, { frame_index: 98 },
    { frame_seconds: 10.1001 }
  ]) {
    const frame = structuredClone(current);
    Object.assign(frame.selection.last_historical_candidate, changes);
    assert.equal(historyFor(pitch, frame), null);
  }
});

test("current stationary marker requires a point for this exact frame", () => {
  const frame = fixture().pitches[0].frames[1];
  assert.deepEqual(visiblePoints(frame), { track: [600, 300], candidate: [600, 300] });
  for (const changes of [{ frame_index: 100 }, { frame_seconds: 10 }, { pitch_id: "another" },
    { point_px: [-1, 300] }, { point_px: [1280, 300] }, { point_px: [600, NaN] }]) {
    const altered = structuredClone(frame);
    Object.assign(altered.selection.current_candidate, changes);
    assert.equal(visiblePoints(altered).candidate, null);
  }
});

test("playback uses stored intervals then stops at the final frame without changing pitch", async () => {
  const h = harness();
  await h.controller.show(0);
  h.controller.toggle();
  assert.ok(Math.abs(h.timers[0].delay - 100) < 1e-8);
  h.timers[0].callback(); await flush();
  assert.equal(h.controller.frameIndex, 1);
  assert.ok(Math.abs(h.timers[1].delay - 300) < 1e-8);
  h.timers[1].callback(); await flush();
  assert.equal(h.controller.frameIndex, 2);
  assert.equal(h.controller.pitchIndex, 0);
  assert.equal(h.last().playing, false);
  assert.equal(h.timers.length, 2);
});

test("default browser timers never receive a Controller as their native receiver", async () => {
  const context = vm.createContext({ module: { exports: {} } });
  vm.runInContext(`
    globalThis.timerCalls = [];
    globalThis.setTimeout = function (callback, delay) {
      "use strict";
      if (this !== undefined && this !== globalThis) throw new TypeError("Illegal invocation");
      timerCalls.push({ kind: "set", delay });
      return 7;
    };
    globalThis.clearTimeout = function (id) {
      "use strict";
      if (this !== undefined && this !== globalThis) throw new TypeError("Illegal invocation");
      timerCalls.push({ kind: "clear", id });
    };
  `, context);
  vm.runInContext(fs.readFileSync(require.resolve("../web/track-review/review.js"), "utf8"), context);
  const BrowserController = context.module.exports.Controller;
  const controller = new BrowserController(fixture(), {
    loadImage: frame => Promise.resolve({ imageIndex: frame.frame_index }),
    onChange: () => {}
  });
  await controller.show(0);
  controller.toggle();
  assert.equal(context.timerCalls[0].kind, "set");
  assert.ok(Math.abs(context.timerCalls[0].delay - 100) < 1e-8);
  controller.pause();
  assert.equal(context.timerCalls[1].kind, "clear");
  assert.equal(context.timerCalls[1].id, 7);
  assert.equal(controller.playing, false);
});

test("pitch changes stop playback, cancel timers, reset the frame and clear history", async () => {
  const h = harness();
  await h.controller.show(1); h.controller.toggle();
  const pending = h.controller.switchPitch(1);
  assert.equal(h.last().playing, false);
  assert.equal(h.last().frameIndex, 0);
  assert.equal(h.last().image, null);
  assert.equal(h.last().history, null);
  assert.equal(h.timers[0].cancelled, true);
  await pending;
  assert.equal(h.last().pitch.pitch_id, "747139:3:2");
  assert.equal(h.last().history, null);
});

test("pause while loading prevents a delayed image from restarting playback", async () => {
  const h = harness({ deferred: true });
  const pending = h.controller.show(0);
  h.controller.toggle(); h.controller.pause();
  h.calls[0].resolve({ id: "current" }); await pending;
  assert.equal(h.last().playing, false);
  assert.equal(h.timers.length, 0);
});

test("arrow and space shortcuts respect form controls, editable text and modifiers", () => {
  const calls = [];
  const controller = { frameIndex: 1, seek: value => calls.push(value), toggle: () => calls.push("toggle") };
  const event = (key, target = { tagName: "DIV" }, changes = {}) => ({
    key, code: key === " " ? "Space" : key, target, preventDefault: () => calls.push("prevent"), ...changes
  });
  assert.equal(handleKey(event("ArrowRight"), controller), true);
  assert.deepEqual(calls.splice(0), [2, "prevent"]);
  assert.equal(handleKey(event("ArrowLeft"), controller), true);
  assert.deepEqual(calls.splice(0), [0, "prevent"]);
  assert.equal(handleKey(event(" "), controller), true);
  assert.deepEqual(calls.splice(0), ["toggle", "prevent"]);
  for (const tagName of ["INPUT", "SELECT", "TEXTAREA", "BUTTON"]) {
    assert.equal(handleKey(event("ArrowRight", { tagName }), controller), false);
  }
  assert.equal(handleKey(event(" ", { isContentEditable: true }), controller), false);
  assert.equal(handleKey(event("ArrowRight", undefined, { ctrlKey: true }), controller), false);
  assert.equal(handleKey(event("ArrowRight", undefined, { repeat: true }), controller), false);
  assert.deepEqual(calls, []);
});

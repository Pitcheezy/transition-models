"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { Controller, visiblePoints, historyFor, ocrView, trackingText, comparisonText, reasonText } = require("../web/track-review/review.js");

function fixture() {
  const pitch_id = "747139:3:1";
  const states = ["tracking", "reacquire_candidate", "tracking", "reacquire_search", "lost"];
  const event = { pitch_id, frame_index: 102, frame_seconds: 10.2,
    available_frame: 102, available_seconds: 10.2, point_px: [620, 300], segment_id: 1 };
  const frames = states.map((state, i) => {
    const key = { pitch_id, frame_index: 100 + i, frame_seconds: 10 + i / 10 };
    const selection = { ...key, tracker_state: i === 0 ? "tracking" : "lost",
      selection_state: i === 0 ? "warming" : "unavailable", reason: "baseline",
      current_track_point_px: i === 0 ? [600, 300] : null,
      current_candidate: null, last_historical_candidate: null };
    const track = { ...key, state, segment_id: state === "tracking" ? (i === 0 ? 0 : 1) : null,
      point_px: state === "tracking" ? [620, 300] : null,
      reacquire_candidate_px: state === "reacquire_candidate" ? [619, 299] : null, reason: state };
    return { ...key, width: 1280, height: 720, sha256: "a".repeat(64), image: `${i}.jpg`, selection,
      reacquire: { tracking: track, selection: { ...selection,
        tracker_state: state, segment_id: track.segment_id,
        current_track_point_px: track.point_px,
        selection_state: i === 2 ? "stationary" : state === "tracking" ? "warming" : "unavailable",
        current_candidate: i === 2 ? { ...event } : null,
        last_historical_candidate: i >= 2 ? { ...event } : null } } };
  });
  return { schema: "pitcheezy-track-frame-view-dev-v1",
    comparison_schema: "pitcheezy-reacquire-frame-comparison-dev-v1",
    pitches: [{ pitch_id, frames }, { pitch_id: "747139:3:2", frames: frames.map((f, i) => ({
      ...f, frame_index: 200 + i, frame_seconds: 20 + i / 10,
      selection: { ...f.selection, pitch_id: "747139:3:2" },
      reacquire: { tracking: { ...f.reacquire.tracking, pitch_id: "747139:3:2" },
        selection: { ...f.reacquire.selection, pitch_id: "747139:3:2", current_candidate: null, last_historical_candidate: null } }
    })) }] };
}
function harness(deferred = false) {
  const calls = [], views = [], timers = [];
  const controller = new Controller(fixture(), {
    loadImage: f => deferred ? new Promise((resolve, reject) => calls.push({ f, resolve, reject }))
      : Promise.resolve({ id: f.frame_index }),
    onChange: v => views.push(v), setTimer: fn => { timers.push(fn); return timers.length; }, clearTimer: () => {}
  });
  return { controller, calls, views, timers, last: () => views.at(-1) };
}
const flush = () => new Promise(resolve => setImmediate(resolve));

test("switch at the same frame shows candidate segment but never mutates baseline", async () => {
  const h = harness(); await h.controller.show(2);
  assert.equal(visiblePoints(h.last().frame).track, null);
  await h.controller.switchMode("reacquire");
  assert.equal(h.last().frameIndex, 2);
  assert.deepEqual(visiblePoints(h.last().frame), { track: [620, 300], candidate: [620, 300] });
  assert.equal(h.last().frame.selection.segment_id, 1);
  assert.equal(h.last().rawFrame.selection.tracker_state, "lost");
  await h.controller.switchMode("baseline");
  assert.equal(h.last().history, null);
  assert.equal(h.last().frameIndex, 2);
  assert.equal(visiblePoints(h.last().frame).track, null);
});

test("candidate/search/lost states do not expose tentative or stale current markers", async () => {
  const h = harness(); await h.controller.switchMode("reacquire");
  for (const i of [1, 3, 4]) {
    await h.controller.seek(i);
    assert.deepEqual(visiblePoints(h.last().frame), { track: null, candidate: null });
    const stale = structuredClone(h.last().frame);
    stale.selection.current_track_point_px = [620, 300];
    stale.selection.current_candidate = { ...stale.selection, point_px: [620, 300] };
    assert.deepEqual(visiblePoints(stale), { track: null, candidate: null });
  }
  assert.match(trackingText("reacquire_candidate"), /미확정/);
  assert.match(trackingText("reacquire_search"), /재탐색 중/);
});

test("mode switches clear pending images and history and stop playback", async () => {
  const h = harness(true); const first = h.controller.show(2);
  h.controller.toggle();
  const second = h.controller.switchMode("reacquire");
  assert.equal(h.last().playing, false);
  assert.equal(h.last().image, null); assert.equal(h.last().history, null);
  assert.match(comparisonText(h.last().rawFrame, h.last()), /비웁니다/);
  h.calls[1].resolve({ id: "candidate" }); await second;
  h.calls[0].resolve({ id: "old-baseline" }); await first;
  assert.equal(h.last().image.id, "candidate");
  assert.equal(h.last().mode, "reacquire");
});

test("a delayed candidate history cannot reappear after returning to baseline", async () => {
  const h = harness(true);
  h.controller.mode = "reacquire";
  const pending = h.controller.show(4);
  h.calls[0].resolve({ id: "lost" }); await flush();
  assert.equal(h.calls[1].f.frame_index, 102);
  const baseline = h.controller.switchMode("baseline");
  h.calls[2].resolve({ id: "baseline" }); await baseline;
  h.calls[1].resolve({ id: "old-event" }); await pending;
  assert.equal(h.last().history, null); assert.equal(h.last().mode, "baseline");
});

test("reacquisition history stays on its source frame and disappears before the event", async () => {
  const h = harness(); await h.controller.switchMode("reacquire"); await h.controller.seek(4);
  assert.equal(h.last().history.event.segment_id, 1);
  assert.equal(h.last().history.image.id, 102);
  assert.equal(h.last().frame.frame_index, 104);
  await h.controller.seek(1);
  assert.equal(h.last().history, null);
  const future = structuredClone(h.controller.pitch.frames[2]);
  future.selection = { ...future.reacquire.selection, last_historical_candidate: {
    ...future.reacquire.selection.last_historical_candidate, available_frame: 103 } };
  assert.equal(historyFor(h.controller.pitch, future), null);
});

test("stationary marker cannot belong to a different segment", async () => {
  const h = harness(); await h.controller.switchMode("reacquire"); await h.controller.seek(2);
  const frame = structuredClone(h.last().frame); frame.selection.current_candidate.segment_id = 0;
  assert.equal(visiblePoints(frame).candidate, null);
});

test("current image failure after mode switch clears all current and historical output", async () => {
  const h = harness(true); const first = h.controller.show(0);
  h.calls[0].resolve({ id: "baseline" }); await first;
  const next = h.controller.switchMode("reacquire");
  h.calls[1].reject(new Error("image missing")); await next;
  assert.equal(h.last().image, null); assert.equal(h.last().history, null);
  assert.equal(h.last().playing, false); assert.ok(h.last().error);
});

test("pitch switch retains comparison mode but clears old segment and history", async () => {
  const h = harness(); await h.controller.switchMode("reacquire"); await h.controller.seek(4);
  const next = h.controller.switchPitch(1);
  assert.equal(h.last().image, null); assert.equal(h.last().history, null);
  await next;
  assert.equal(h.last().frameIndex, 0); assert.equal(h.last().mode, "reacquire");
  assert.equal(h.last().history, null);
});

test("same-frame OCR remains unchanged by mode and is blank while loading", async () => {
  const h = harness(); await h.controller.show(2);
  const role = { raw_text: "NAME", name_text: "NAME", status: "read", reason: "read",
    temporal_relation: "not_compared", compared_to_frame: null };
  const ocr = { schema: "pitcheezy-ocr-frame-view-dev-v1", pitches: [{ pitch_id: h.last().pitch.pitch_id,
    rows: [{ pitch_id: h.last().pitch.pitch_id, frame_index: 102, frame_seconds: 10.2,
      image_sha256: "a".repeat(64), roles: { batter: role, pitcher: role } }] }] };
  const before = ocrView(ocr, h.last().pitch, h.last().frame, h.last());
  const switched = h.controller.switchMode("reacquire");
  assert.equal(ocrView(ocr, h.last().pitch, h.last().frame, h.last()).roles.batter.name, "—");
  await switched;
  assert.deepEqual(ocrView(ocr, h.last().pitch, h.last().frame, h.last()), before);
  await h.controller.switchPitch(1);
  assert.match(ocrView(ocr, h.last().pitch, h.last().frame, h.last()).status, /관측 자료 없음/);
});

test("legacy packs do not silently present baseline as reacquisition", () => {
  const data = fixture(); delete data.comparison_schema;
  const controller = new Controller(data, { loadImage: async () => ({}), onChange: () => {} });
  assert.equal(controller.hasComparison, false);
  assert.throws(() => controller.switchMode("reacquire"));
  assert.throws(() => controller.switchMode("invented"));
  const incomplete = fixture(); delete incomplete.pitches[0].frames[0].reacquire;
  assert.throws(() => new Controller(incomplete, { loadImage: async () => ({}), onChange: () => {} }));
});

test("tracking continuity cannot hide why a stationary candidate stopped", () => {
  assert.equal(reasonText({ tracking: { reason: "patch_continuity" }, selection: { reason: "motion_restart" } }),
    "추적: patch_continuity / 멈춤 판정: motion_restart");
  assert.equal(reasonText({ selection: { reason: "tracker_lost" } }), "tracker_lost");
});

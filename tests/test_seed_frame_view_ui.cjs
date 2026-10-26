"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const { Controller, visiblePoints, modeOptions, seedGateView, seedReasonText, comparisonText, ocrView } = require("../web/track-review/review.js");

const SCHEMA = "pitcheezy-seed-gate-frame-comparison-dev-v1";
const SHA = "a".repeat(64);
const POLICY = "b".repeat(64);
const key = (pitch_id, i) => ({ pitch_id, frame_index: 100 + i, frame_seconds: 10 + i / 10 });

function fixture() {
  const pitches = ["747139:3:1", "747139:3:2"].map((pitch_id, p) => {
    const event = { ...key(pitch_id, 3), available_frame: 103, available_seconds: 10.3,
      point_px: [620, 300], segment_id: 0 };
    const frames = Array.from({ length: 6 }, (_, i) => {
      const frameKey = key(pitch_id, i);
      const baselineState = i === 5 ? "lost" : "tracking";
      const selection = { ...frameKey, tracker_state: baselineState, segment_id: 0,
        selection_state: baselineState === "tracking" ? "warming" : "unavailable", reason: "baseline",
        current_track_point_px: baselineState === "tracking" ? [600, 300] : null,
        current_candidate: null, last_historical_candidate: null };
      const tracking = { ...frameKey, state: baselineState, source_sha256: SHA, reason: "baseline", segment_id: 0 };
      const seeded = p === 0 && i >= 3;
      const state = !seeded ? "unseeded" : i === 3 ? "tracking" : i === 4 ? "reacquire_candidate" : "lost";
      const support = p === 1 ? [] : [0, ...(i >= 1 ? [1] : []), ...(i >= 3 ? [3] : [])].map(j => key(pitch_id, j));
      const decision = { ...frameKey, schema: "pitcheezy-mitt-seed-gate-dev-v1", policy_sha256: POLICY,
        mitt_identity: "unverified", state: seeded ? "seeded" : p === 0 ? "collecting" : "waiting",
        reason: p === 1 ? "uncertainty_unavailable" : i === 3 ? "seed_qualified" : seeded ? "already_seeded"
          : i === 2 ? "no_saved_observation" : "collecting_support",
        support_keys: support,
        seed: p === 0 && i === 3 ? { frame_index: frameKey.frame_index, frame_seconds: frameKey.frame_seconds,
          point_px: [620, 300], support_keys: structuredClone(support) } : null };
      return { ...frameKey, width: 1280, height: 720, sha256: SHA, image: `${pitch_id}/${i}.jpg`, selection, tracking,
        seed_gate: { decision, tracking: { ...tracking, state, segment_id: state === "tracking" ? 0 : null,
          point_px: state === "tracking" ? [620, 300] : null, reacquire_candidate_px: [619, 299] },
        selection: { ...selection, tracker_state: state, selection_state: i === 3 && p === 0 ? "stationary" : "unavailable",
          current_track_point_px: state === "tracking" ? [620, 300] : null,
          current_candidate: i === 3 && p === 0 ? { ...event } : null,
          last_historical_candidate: seeded ? { ...event } : null } } };
    });
    return { pitch_id, gate_seed: { frame_index: 9999, point_px: [111, 222], summary: "FUTURE_DO_NOT_DISPLAY" }, frames };
  });
  return { schema: "pitcheezy-track-frame-view-dev-v1", comparison_schema: SCHEMA, pitches };
}

function harness({ deferred = false, data = fixture() } = {}) {
  const calls = [], views = [], timers = [];
  const controller = new Controller(data, {
    loadImage: f => deferred ? new Promise((resolve, reject) => calls.push({ f, resolve, reject })) : Promise.resolve({ id: f.frame_index }),
    onChange: view => views.push(view), setTimer: fn => { timers.push(fn); return timers.length; }, clearTimer: () => {}
  });
  return { controller, calls, views, timers, last: () => views.at(-1) };
}
const flush = () => new Promise(resolve => setImmediate(resolve));
const gate = h => seedGateView(h.last().rawFrame, h.last());
const callbacks = { loadImage: async () => ({}), onChange: () => {} };

test("comparison kind supplies distinct labels and only its own modes", () => {
  const h = harness();
  assert.deepEqual(modeOptions(SCHEMA), [
    { value: "baseline", label: "기존 재탐색" }, { value: "seed_gate", label: "초기점 게이트" }
  ]);
  assert.throws(() => h.controller.switchMode("reacquire"));
  for (const comparison_schema of [undefined, "pitcheezy-reacquire-frame-comparison-dev-v1"]) {
    const data = fixture(); data.comparison_schema = comparison_schema;
    for (const pitch of data.pitches) for (const f of pitch.frames) f.reacquire = f.seed_gate;
    const controller = new Controller(data, callbacks);
    assert.throws(() => controller.switchMode("seed_gate"));
    assert.equal(modeOptions(comparison_schema)[0].label, "기존 추적");
  }
});

test("same-frame mode switch preserves baseline, pauses and shows only confirmed tracking", async () => {
  const h = harness(); const original = structuredClone(h.controller.data);
  await h.controller.show(3); h.controller.toggle();
  const switched = h.controller.switchMode("seed_gate");
  assert.equal(h.last().playing, false); assert.equal(h.last().image, null);
  assert.deepEqual(gate(h), { visible: true, state: "—", reason: "—", support: "—" });
  await switched;
  assert.equal(h.last().frameIndex, 3);
  assert.deepEqual(visiblePoints(h.last().frame), { track: [620, 300], candidate: [620, 300] });
  assert.match(gate(h).state, /이 프레임에서 초기점 채택/);
  assert.match(comparisonText(h.last().rawFrame, h.last()), /기존 재탐색:.*초기점 게이트:/);
  await h.controller.switchMode("baseline");
  assert.equal(h.last().frameIndex, 3);
  assert.deepEqual(visiblePoints(h.last().frame), { track: [600, 300], candidate: null });
  assert.deepEqual(h.controller.data, original);
});

test("support and decision are from the displayed prefix without future seed summaries", async () => {
  const h = harness(); await h.controller.switchMode("seed_gate");
  assert.match(gate(h).support, /^1개 · 원본 번호 100 ·/);
  assert.match(gate(h).state, /아직 초기점 없음/);
  assert.doesNotMatch(JSON.stringify(gate(h)), /9999|FUTURE_DO_NOT_DISPLAY|111|222/);
  await h.controller.seek(2);
  assert.equal(gate(h).reason, "이 프레임에는 저장된 AI 관측이 없습니다 (no_saved_observation)");
  assert.match(gate(h).support, /^2개 · 원본 번호 100, 101 ·/);
  await h.controller.seek(5);
  assert.match(gate(h).state, /현재 추적 성공을 뜻하지 않음/);
  await h.controller.seek(0);
  assert.match(gate(h).state, /아직 초기점 없음/);
  assert.equal(h.last().history, null);
});

test("unseeded, tentative and lost frames never draw seed or stale point coordinates", async () => {
  const h = harness(); await h.controller.switchMode("seed_gate");
  for (const i of [0, 1, 2, 4, 5]) {
    await h.controller.seek(i);
    const frame = structuredClone(h.last().frame);
    frame.selection.current_track_point_px = [620, 300];
    frame.selection.current_candidate = { ...frame.selection, point_px: [620, 300] };
    assert.deepEqual(visiblePoints(frame), { track: null, candidate: null });
  }
});

test("a pitch without a qualified seed remains navigable with explicit reasons", async () => {
  const h = harness(); await h.controller.switchMode("seed_gate"); await h.controller.seek(5);
  const switched = h.controller.switchPitch(1);
  assert.equal(h.last().image, null); assert.equal(h.last().history, null);
  assert.equal(gate(h).state, "—");
  await switched;
  assert.equal(h.controller.pitch.frames.length, 6);
  for (let i = 0; i < 6; i++) {
    await h.controller.seek(i);
    assert.equal(gate(h).reason, "좌표의 불확실도 값이 없어 보류했습니다 (uncertainty_unavailable)");
    assert.match(gate(h).state, /보류/); assert.match(gate(h).support, /^0개/);
    assert.deepEqual(visiblePoints(h.last().frame), { track: null, candidate: null });
    assert.equal(h.last().history, null);
  }
});

test("delayed current and historical loads cannot restore an earlier mode", async () => {
  const h = harness({ deferred: true });
  const oldCurrent = h.controller.show(0);
  const current = h.controller.switchMode("seed_gate");
  h.calls[1].resolve({ id: "gate" }); await current;
  h.calls[0].resolve({ id: "baseline-old" }); await oldCurrent;
  assert.equal(h.last().image.id, "gate");
  const historical = h.controller.seek(5);
  h.calls[2].resolve({ id: "gate-lost" }); await flush();
  assert.equal(h.calls[3].f.frame_index, 103);
  const baseline = h.controller.switchMode("baseline");
  assert.equal(gate(h).state, "—");
  h.calls[4].resolve({ id: "baseline" }); await baseline;
  h.calls[3].resolve({ id: "gate-old-history" }); await historical;
  assert.equal(h.last().mode, "baseline"); assert.equal(h.last().history, null);
  assert.equal(h.last().image.id, "baseline");
});

test("image failure clears gate decisions alongside current and historical displays", async () => {
  const h = harness({ deferred: true });
  const pending = h.controller.switchMode("seed_gate");
  h.calls[0].reject(new Error("missing image")); await pending;
  assert.ok(h.last().error); assert.equal(h.last().image, null); assert.equal(h.last().history, null);
  assert.deepEqual(gate(h), { visible: true, state: "—", reason: "—", support: "—" });
});

test("gate comparison shares exact same-frame OCR and never fills missing-pitch observations", async () => {
  const h = harness(); await h.controller.show(3);
  const role = { raw_text: "NAME", name_text: "NAME", status: "read", reason: "saved",
    temporal_relation: "not_compared", compared_to_frame: null };
  const ocr = { schema: "pitcheezy-ocr-frame-view-dev-v1", pitches: [{ pitch_id: h.last().pitch.pitch_id,
    rows: [{ ...key(h.last().pitch.pitch_id, 3), image_sha256: SHA, roles: { batter: role, pitcher: role } }] }] };
  const before = ocrView(ocr, h.last().pitch, h.last().frame, h.last());
  const pending = h.controller.switchMode("seed_gate");
  assert.equal(ocrView(ocr, h.last().pitch, h.last().frame, h.last()).roles.batter.name, "—");
  await pending;
  assert.deepEqual(ocrView(ocr, h.last().pitch, h.last().frame, h.last()), before);
  await h.controller.switchPitch(1);
  assert.match(ocrView(ocr, h.last().pitch, h.last().frame, h.last()).status, /관측 자료 없음/);
});

test("seed gate rows and baseline must bind pitch, frame, time and source image", () => {
  for (const path of ["selection", "tracking", "seed_gate.selection", "seed_gate.tracking", "seed_gate.decision"]) {
    for (const change of [{ pitch_id: "747139:99:1" }, { frame_index: 999 }, { frame_seconds: 99 }]) {
      const data = fixture(); let target = data.pitches[0].frames[0];
      for (const part of path.split(".")) target = target[part];
      Object.assign(target, change);
      assert.throws(() => new Controller(data, callbacks), `${path}: ${JSON.stringify(change)}`);
    }
  }
  for (const mode of ["baseline", "seed_gate"]) {
    const data = fixture(); const f = data.pitches[0].frames[0];
    (mode === "baseline" ? f.tracking : f.seed_gate.tracking).source_sha256 = "c".repeat(64);
    assert.throws(() => new Controller(data, callbacks));
  }
});

test("invalid decisions, future support and foreign-pitch support fail closed", () => {
  const changes = [
    { schema: "other" }, { state: "unknown" }, { reason: null }, { policy_sha256: "short" },
    { mitt_identity: "verified" }, { support_keys: null }, { support_keys: [] },
    { support_keys: [key("747139:3:1", 1)] },
    { support_keys: [key("747139:3:2", 0)] },
    { support_keys: [{ ...key("747139:3:1", 0), frame_seconds: 9 }] },
    { support_keys: [key("747139:3:1", 0), key("747139:3:1", 0)] },
    { state: "waiting" }, { seed: undefined }, { reason: "seed_qualified" }, { reason: "already_seeded" }
  ];
  for (const change of changes) {
    const data = fixture(); Object.assign(data.pitches[0].frames[0].seed_gate.decision, change);
    assert.throws(() => new Controller(data, callbacks), JSON.stringify(change));
  }
});

test("seed events cannot backdate, use a future point or diverge from support", () => {
  for (const change of [{ frame_index: 102 }, { frame_seconds: 10.4 }, { point_px: [1280, 300] },
    { point_px: [600, NaN] }, { support_keys: [] }, { support_keys: [key("747139:3:2", 0)] }]) {
    const data = fixture(); Object.assign(data.pitches[0].frames[3].seed_gate.decision.seed, change);
    assert.throws(() => new Controller(data, callbacks));
  }
  const stale = fixture(); stale.pitches[0].frames[3].seed_gate.decision.seed = null;
  assert.throws(() => new Controller(stale, callbacks));
  const future = fixture(); future.pitches[0].frames[0].seed_gate.tracking.state = "tracking";
  future.pitches[0].frames[0].seed_gate.selection.tracker_state = "tracking";
  assert.throws(() => new Controller(future, callbacks));
  const disagreement = fixture(); disagreement.pitches[0].frames[3].seed_gate.selection.tracker_state = "unseeded";
  assert.throws(() => new Controller(disagreement, callbacks));
});

test("unsupported dimensions are rejected and non-seed comparison hides the gate panel", async () => {
  const invalid = fixture(); invalid.pitches[0].frames[0].width = 640;
  assert.throws(() => new Controller(invalid, callbacks));
  const h = harness(); await h.controller.show(0);
  for (const comparisonMode of [null, "reacquire"]) {
    assert.deepEqual(seedGateView(h.last().rawFrame, { ...h.last(), comparisonMode }),
      { visible: false, state: "—", reason: "—", support: "—" });
  }
});

test("all saved gate reasons keep their code with a Korean explanation and unknown text stays literal", () => {
  const reasons = ["already_seeded", "gap_expired", "no_saved_observation", "view_not_live_centre_field",
    "catcher_not_set", "mitt_not_full", "occluded", "pitcher_not_before_delivery", "no_centre",
    "uncertainty_unavailable", "uncertainty_exceeds_limit", "gap_restart", "collecting_support",
    "movement_restart", "seed_qualified"];
  for (const reason of reasons) {
    const text = seedReasonText(reason);
    assert.match(text, /[가-힣]/);
    assert.ok(text.endsWith(` (${reason})`));
  }
  for (const reason of ["future_reason", "constructor", "__proto__", "<img src=x onerror=alert(1)>"]) {
    assert.equal(seedReasonText(reason), reason);
  }
});

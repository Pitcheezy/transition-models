"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const { Controller, ocrFor, ocrView } = require("../web/track-review/review.js");

const PITCH = "747139:3:1";
const SHA = "a".repeat(64);

function frames(pitchId, base) {
  return [0, 1, 2, 3].map(i => ({
    frame_index: base + 6 * i, frame_seconds: (base + 6 * i) * 1001 / 60000,
    width: 1280, height: 720, image: `frames/${pitchId.replace(/:/g, "_")}/${base + 6 * i}.jpg`,
    sha256: SHA.replace(/a/g, String(i)),
    selection: { pitch_id: pitchId, tracker_state: "unseeded", selection_state: "unavailable",
      reason: "no_seed", current_track_point_px: null, current_candidate: null,
      event: null, last_historical_candidate: null }
  }));
}

function trackData() {
  return { schema: "pitcheezy-track-frame-view-dev-v1", time_basis: "manifest_index_timebase",
    independent_decoded_pts_verified: false,
    pitches: [{ pitch_id: PITCH, play_id: "p1", frames: frames(PITCH, 600) },
      { pitch_id: "747139:3:2", play_id: "p2", frames: frames("747139:3:2", 720) }] };
}

function role(name, { status, reason, relation = "not_compared", compared = null } = {}) {
  const resolved = status || (name ? "read" : "abstain");
  return { raw_text: name ? `3.${name}` : "", name_text: resolved === "read" ? name : null, lineup_order: null,
    status: resolved, reason: reason || (resolved === "read" ? "literal_name" : "name_panel_absent"),
    temporal_relation: relation, compared_to_frame: compared };
}

function ocrData(data) {
  const f = data.pitches[0].frames;
  const batters = [
    role("VLTNLUS"),
    role("VIENTOS", { relation: "literal_changed", compared: f[0].frame_index }),
    role(null),
    role(null, { status: "error", reason: "engine_error:RuntimeError" })
  ];
  return { schema: "pitcheezy-ocr-frame-view-dev-v1", time_basis: "manifest_index_timebase",
    independent_decoded_pts_verified: false,
    pitches: [{ pitch_id: PITCH, rows: f.map((frame, i) => ({ pitch_id: PITCH, frame_index: frame.frame_index,
      frame_seconds: frame.frame_seconds, image_sha256: frame.sha256,
      roles: { pitcher: role(null, { reason: "possible_truncated_name" }), batter: batters[i] } })) }],
    pitches_without_observations: ["747139:3:2"] };
}

const loaded = { loading: false, error: null };
const blank = { raw: "—", name: "—", state: "—", relation: "—" };

test("exact four-key join returns one row or an explicit non-match", () => {
  const data = trackData(), ocr = ocrData(data), pitch = data.pitches[0];
  assert.equal(ocrFor(ocr, pitch, pitch.frames[1]).kind, "row");
  assert.equal(ocrFor(ocr, pitch, pitch.frames[1]).row.roles.batter.name_text, "VIENTOS");
  for (const changes of [{ frame_index: 999 }, { frame_seconds: pitch.frames[1].frame_seconds + 1e-9 }, { sha256: "b".repeat(64) }]) {
    assert.equal(ocrFor(ocr, pitch, { ...pitch.frames[1], ...changes }).kind, "mismatch");
  }
  assert.equal(ocrFor(ocr, data.pitches[1], data.pitches[1].frames[0]).kind, "none");
  assert.equal(ocrFor(null, pitch, pitch.frames[0]).kind, "unavailable");
  assert.equal(ocrFor({ schema: "other", pitches: [] }, pitch, pitch.frames[0]).kind, "unsupported");
  const duplicated = structuredClone(ocr);
  duplicated.pitches[0].rows.push(structuredClone(duplicated.pitches[0].rows[1]));
  assert.equal(ocrFor(duplicated, pitch, pitch.frames[1]).kind, "mismatch");
  const twice = structuredClone(ocr);
  twice.pitches.push(structuredClone(twice.pitches[0]));
  assert.equal(ocrFor(twice, pitch, pitch.frames[1]).kind, "mismatch");
  const malformed = structuredClone(ocr);
  malformed.pitches[0].rows[1].roles.batter.status = "guessed";
  assert.equal(ocrFor(malformed, pitch, pitch.frames[1]).kind, "mismatch");
  const nameless = structuredClone(ocr);
  nameless.pitches[0].rows[1].roles.batter.name_text = "";
  assert.equal(ocrFor(nameless, pitch, pitch.frames[1]).kind, "mismatch");
});

test("read, abstain, engine error, no data and mismatch are shown differently", () => {
  const data = trackData(), ocr = ocrData(data), pitch = data.pitches[0], f = pitch.frames;
  const read = ocrView(ocr, pitch, f[1], loaded);
  assert.match(read.status, /저장 관측 · 원본 번호 606/);
  assert.equal(read.roles.batter.raw, "3.VIENTOS");
  assert.equal(read.roles.batter.name, "VIENTOS");
  assert.equal(read.roles.batter.state, "읽음 · literal_name");
  assert.match(read.roles.batter.relation, /문자열 다름 · 비교 원본 번호 600 · 선수 교체 근거 아님/);
  assert.equal(read.roles.pitcher.state, "기권 · possible_truncated_name");
  assert.equal(read.roles.pitcher.raw, "(빈 문자열)");
  assert.equal(read.roles.pitcher.name, "—");
  const abstain = ocrView(ocr, pitch, f[2], loaded);
  assert.equal(abstain.roles.batter.state, "기권 · name_panel_absent");
  assert.equal(abstain.roles.batter.name, "—");
  const error = ocrView(ocr, pitch, f[3], loaded);
  assert.equal(error.roles.batter.state, "엔진 오류 · engine_error:RuntimeError");
  const none = ocrView(ocr, data.pitches[1], data.pitches[1].frames[0], loaded);
  assert.match(none.status, /관측 자료 없음/);
  assert.deepEqual(none.roles, { pitcher: blank, batter: blank });
  const mismatch = ocrView(ocr, pitch, { ...f[1], sha256: "b".repeat(64) }, loaded);
  assert.match(mismatch.status, /관측 불일치/);
  assert.deepEqual(mismatch.roles, { pitcher: blank, batter: blank });
  assert.match(ocrView(null, pitch, f[0], loaded).status, /OCR 관측 자료가 없습니다/);
});

test("names never persist from an earlier frame, and VLTNLUS is shown as saved", () => {
  const data = trackData(), ocr = ocrData(data), pitch = data.pitches[0], f = pitch.frames;
  assert.equal(ocrView(ocr, pitch, f[0], loaded).roles.batter.name, "VLTNLUS");
  const sequence = [1, 2, 3, 1, 0].map(i => ocrView(ocr, pitch, f[i], loaded).roles.batter.name);
  assert.deepEqual(sequence, ["VIENTOS", "—", "—", "VIENTOS", "VLTNLUS"]);
  const text = JSON.stringify(ocrView(ocr, pitch, f[0], loaded));
  assert.ok(!text.includes("VIENTOS"));
});

test("loading and failed images blank the OCR panel regardless of saved rows", () => {
  const data = trackData(), ocr = ocrData(data), pitch = data.pitches[0];
  const loading = ocrView(ocr, pitch, pitch.frames[1], { loading: true, error: null });
  assert.equal(loading.status, "이미지 준비 중 · 표시 비움");
  assert.deepEqual(loading.roles, { pitcher: blank, batter: blank });
  const failed = ocrView(ocr, pitch, pitch.frames[1], { loading: false, error: "이미지를 불러오지 못했습니다." });
  assert.equal(failed.status, "표시 없음");
  assert.deepEqual(failed.roles, { pitcher: blank, batter: blank });
});

test("a slow earlier image never re-surfaces an older frame's OCR after seeking or switching", async () => {
  const data = trackData(), ocr = ocrData(data);
  const calls = [], rendered = [];
  const controller = new Controller(data, {
    loadImage: frame => new Promise((resolve, reject) => calls.push({ frame, resolve, reject })),
    onChange: view => rendered.push(ocrView(ocr, view.pitch, view.frame, view)),
    setTimer: () => 0, clearTimer: () => {}
  });
  const first = controller.show(1), second = controller.seek(2);
  assert.equal(rendered.at(-1).status, "이미지 준비 중 · 표시 비움");
  calls[1].resolve({ id: "frame-2" }); await second;
  assert.equal(rendered.at(-1).roles.batter.state, "기권 · name_panel_absent");
  const count = rendered.length;
  calls[0].resolve({ id: "frame-1" }); await first;
  assert.equal(rendered.length, count);
  const switched = controller.switchPitch(1);
  assert.equal(rendered.at(-1).status, "이미지 준비 중 · 표시 비움");
  calls[2].resolve({ id: "other-pitch" }); await switched;
  assert.match(rendered.at(-1).status, /관측 자료 없음/);
  const back = controller.switchPitch(0);
  calls[3].reject(new Error("missing frame")); await back;
  assert.equal(rendered.at(-1).status, "표시 없음");
  assert.deepEqual(rendered.at(-1).roles.batter, blank);
});

test("hostile saved strings pass through as plain text values only", () => {
  const data = trackData(), ocr = ocrData(data), pitch = data.pitches[0];
  const hostile = "</script><img src=x onerror=alert(1)>";
  ocr.pitches[0].rows[0].roles.batter.raw_text = hostile;
  ocr.pitches[0].rows[0].roles.batter.name_text = hostile;
  const view = ocrView(ocr, pitch, pitch.frames[0], loaded);
  assert.equal(view.roles.batter.raw, hostile);
  assert.equal(view.roles.batter.name, hostile);
  const source = fs.readFileSync(require.resolve("../web/track-review/review.js"), "utf8");
  assert.ok(!/innerHTML|outerHTML|insertAdjacentHTML|document\.write|\beval\(|new Function/.test(source));
  assert.ok(/get\(`ocr-\$\{role\}-\$\{field\}`\)\.textContent/.test(source));
});

test("OCR comparison relation and referenced frame must agree", () => {
  const data = trackData(), pitch = data.pitches[0], frame = pitch.frames[1];
  for (const change of [
    { temporal_relation: "literal_same", compared_to_frame: null },
    { temporal_relation: "literal_changed", compared_to_frame: null },
    { temporal_relation: "not_compared", compared_to_frame: 600 }
  ]) {
    const ocr = ocrData(data); Object.assign(ocr.pitches[0].rows[1].roles.batter, change);
    assert.equal(ocrFor(ocr, pitch, frame).kind, "mismatch");
    assert.deepEqual(ocrView(ocr, pitch, frame, loaded).roles, { pitcher: blank, batter: blank });
  }
});

test("abstained and errored OCR roles cannot claim a temporal comparison", () => {
  const data = trackData(), pitch = data.pitches[0];
  for (const [index, relation] of [[2, "literal_same"], [3, "literal_changed"]]) {
    const ocr = ocrData(data);
    Object.assign(ocr.pitches[0].rows[index].roles.batter, { temporal_relation: relation, compared_to_frame: 600 });
    assert.equal(ocrFor(ocr, pitch, pitch.frames[index]).kind, "mismatch");
  }
});

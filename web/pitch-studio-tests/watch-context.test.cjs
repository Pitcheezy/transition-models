"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const context = require("../pitch-studio/watch-context.js");

function pitch(index, overrides = {}) {
  const pa = overrides.at_bat_number ?? 1;
  const number = overrides.pitch_number ?? index + 1;
  return {
    index, pitch_id: `123:${pa}:${number}`, at_bat_number: pa, pitch_number: number,
    pitcher: { id: 10, name: "같은 이름", hand: "R" },
    batter: { id: 20, name: "타자", hand: "L" },
    situation: { inning: 1, half: "Top", balls: 0, strikes: 0, outs: 0, bases: 0, home_score: 0, away_score: 0 },
    pre: { candidates: [{ pitch_type: "SL", selection_probability: 0.9 }] },
    post: { actual: { pitch_type: "FF", pitch_label: "포심", speed_mph: 90, description: "ball" } },
    ...overrides,
  };
}
function forbid(row, field = "post") {
  Object.defineProperty(row, field, { configurable: true, get() { throw new Error(`Forbidden read: ${row.pitch_id}.${field}`); } });
  return row;
}
function actual(code, speed, description = "ball", label = code) {
  return { actual: { pitch_type: code, pitch_label: label, speed_mph: speed, description } };
}
function deepFreeze(value) {
  if (value && typeof value === "object") {
    Object.values(value).forEach(deepFreeze);
    Object.freeze(value);
  }
  return value;
}
const all = { pitcher: "all", batter: "all", count: "all" };

test("browser UMD exposes the same factory without CommonJS", () => {
  const sandbox = {};
  vm.runInNewContext(fs.readFileSync(path.join(__dirname, "../pitch-studio/watch-context.js"), "utf8"), sandbox);
  assert.equal(typeof sandbox.PitchWatchContext.create, "function");
  assert.equal(sandbox.PitchWatchContext.create([]).prior("none").total, 0);
});

test("metadata paths never inspect any post or recommendation field", () => {
  const rows = [pitch(0), pitch(1, { situation: { inning: 2, half: "Bot", balls: 3, strikes: 2, outs: 1, bases: 5 } })];
  rows.forEach(row => { forbid(row); forbid(row, "pre"); });
  const model = context.create(rows);
  assert.deepEqual(model.options().counts, [{ value: "0-0", label: "0볼 0스트라이크" }, { value: "3-2", label: "3볼 2스트라이크" }]);
  assert.deepEqual(model.matchingKeys(all), rows.map(row => row.pitch_id));
  assert.equal(model.situation(rows[1].pitch_id), "2회 말 · 3볼 2스트라이크 · 1아웃 · 주자 1루·3루");
  assert.equal(model.situation(rows[0].pitch_id), "1회 초 · 0볼 0스트라이크 · 0아웃 · 주자 없음");
  assert.deepEqual(model.prior(rows[0].pitch_id), { total: 0, speedCount: 0, averageMph: null, types: [] });
  assert.deepEqual(model.ribbon(rows[0].pitch_id, false).map(row => row.kind), ["hidden", "hidden"]);
});

test("options identify players by ID despite duplicate names and sort counts numerically", () => {
  const rows = [pitch(0, { situation: { balls: 3, strikes: 2 } }),
    pitch(1, { pitcher: { id: 11, name: "같은 이름" }, batter: { id: 21, name: "타자" }, situation: { balls: 0, strikes: 2 } }),
    pitch(2, { situation: { balls: 0, strikes: 1 } }), pitch(3)];
  const model = context.create(rows), options = model.options();
  assert.deepEqual(options.pitchers, [{ id: "10", name: "같은 이름" }, { id: "11", name: "같은 이름" }]);
  assert.deepEqual(options.batters.map(p => p.id), ["20", "21"]);
  assert.deepEqual(options.counts.map(c => c.value), ["0-0", "0-1", "0-2", "3-2"]);
  options.pitchers[0].name = "changed"; options.counts.length = 0;
  assert.equal(model.options().pitchers[0].name, "같은 이름");
  assert.equal(model.options().counts.length, 4);
});

test("filters combine with AND and return chronological keys, including empty combinations", () => {
  const rows = [pitch(0), pitch(1, { batter: { id: 21, name: "다른 타자" } }),
    pitch(2, { pitcher: { id: 11, name: "다른 투수" }, situation: { balls: 1, strikes: 2 } })];
  const model = context.create(rows);
  assert.deepEqual(model.matchingKeys(all), rows.map(p => p.pitch_id));
  assert.deepEqual(model.matchingKeys({ pitcher: "10", batter: "21", count: "0-0" }), [rows[1].pitch_id]);
  assert.deepEqual(model.matchingKeys({ pitcher: "11", batter: "20", count: "1-2" }), [rows[2].pitch_id]);
  assert.deepEqual(model.matchingKeys({ pitcher: "11", batter: "21", count: "all" }), []);
  assert.deepEqual(model.matchingKeys({ ...all, count: "1-2" }), [rows[2].pitch_id]);
});

test("invalid filters fail closed rather than silently broadening results", () => {
  const model = context.create([pitch(0)]);
  for (const filters of [undefined, null, [], {}, { ...all, pitcher: 10 }, { ...all, pitcher: "010" },
    { ...all, batter: "20 " }, { ...all, count: "0:0" }, { ...all, count: "4-2" },
    { ...all, pitcher: "missing" }, { ...all, result: "ball" }, { ...all, count: undefined }]) {
    assert.deepEqual(model.matchingKeys(filters), []);
  }
});

test("prior joins a returning pitcher by ID, excludes other IDs and never reads selected or future post", () => {
  const rows = [pitch(0, { post: actual("FF", 90) }),
    forbid(pitch(1, { pitcher: { id: 11, name: "같은 이름" } })),
    pitch(2, { post: actual("SL", 80) }), forbid(pitch(3)), forbid(pitch(4))];
  rows.forEach(row => forbid(row, "pre"));
  const result = context.create(rows).prior(rows[3].pitch_id);
  assert.equal(result.total, 2); assert.equal(result.speedCount, 2); assert.equal(result.averageMph, 85);
  assert.deepEqual(result.types.map(t => [t.code, t.count, t.share]), [["FF", 1, 0.5], ["SL", 1, 0.5]]);
});

test("prior keeps missing and unknown types in the denominator and averages finite actual speeds including zero", () => {
  const rows = [pitch(0, { post: { actual: null } }), pitch(1, { post: actual(null, 0) }),
    pitch(2, { post: actual("unknown", null) }), pitch(3, { post: actual("FF", 100) }),
    pitch(4, { post: actual("FF", NaN) }), pitch(5, { post: actual("SL", Infinity) }),
    pitch(6, { post: actual("SL", "80") }), pitch(7)];
  const result = context.create(rows).prior(rows[7].pitch_id);
  assert.equal(result.total, 7); assert.equal(result.speedCount, 2); assert.equal(result.averageMph, 50);
  assert.deepEqual(result.types, [
    { code: "unknown", label: "구종 미제공", count: 3, share: 3 / 7, averageMph: 0, speedCount: 1 },
    { code: "FF", label: "FF", count: 2, share: 2 / 7, averageMph: 100, speedCount: 1 },
    { code: "SL", label: "SL", count: 2, share: 2 / 7, averageMph: null, speedCount: 0 },
  ]);
});

test("past missing post stays explicit and all-missing speed averages stay null", () => {
  const rows = [pitch(0, { post: null }), pitch(1, { post: actual("FF", null) }), pitch(2)];
  const result = context.create(rows).prior(rows[2].pitch_id);
  assert.equal(result.total, 2); assert.equal(result.averageMph, null); assert.equal(result.speedCount, 0);
  assert.equal(result.types.reduce((n, type) => n + type.count, 0), 2);
  assert.equal(result.types.find(type => type.code === "unknown").share, 0.5);
});

test("ribbon reads only previous results in the same PA and current only after strict true", () => {
  const rows = [forbid(pitch(0, { at_bat_number: 1, pitch_number: 1 })),
    pitch(1, { at_bat_number: 2, pitch_number: 1, post: actual("FF", 90, "called_strike") }),
    forbid(pitch(2, { at_bat_number: 2, pitch_number: 2 })),
    forbid(pitch(3, { at_bat_number: 2, pitch_number: 3 })),
    forbid(pitch(4, { at_bat_number: 3, pitch_number: 1 }))];
  const model = context.create(rows);
  for (const ready of [false, undefined, 1, "true"]) {
    assert.deepEqual(model.ribbon(rows[2].pitch_id, ready), [
      { key: rows[1].pitch_id, pitchNumber: 1, label: "스트라이크", kind: "strike", isCurrent: false },
      { key: rows[2].pitch_id, pitchNumber: 2, label: "결과 숨김", kind: "hidden", isCurrent: true },
      { key: rows[3].pitch_id, pitchNumber: 3, label: "결과 숨김", kind: "hidden", isCurrent: false },
    ]);
  }
  Object.defineProperty(rows[2], "post", { value: actual("SL", 80, "foul"), configurable: true });
  assert.deepEqual(model.ribbon(rows[2].pitch_id, true).map(row => row.kind), ["strike", "foul", "hidden"]);
});

test("ribbon uses recorded description only, retaining missing or unrecognized outcomes as unknown", () => {
  const cases = [["blocked_ball", "ball"], ["swinging_strike_blocked", "strike"], ["foul_tip", "strike"],
    ["foul", "foul"], ["hit_into_play", "inplay"], ["new_result", "unknown"], [null, "unknown"]];
  const rows = cases.map(([description], index) => pitch(index, { post: actual("FF", 90, description) }));
  rows.push(pitch(7, { post: { actual: null } }));
  const ribbon = context.create(rows).ribbon(rows[7].pitch_id, true);
  assert.deepEqual(ribbon.map(row => row.kind), [...cases.map(c => c[1]), "unknown"]);
});

test("unknown keys and empty games return explicit empty state without touching post", () => {
  for (const rows of [[], [forbid(pitch(0))]]) {
    const model = context.create(rows);
    assert.deepEqual(model.prior("missing"), { total: 0, speedCount: 0, averageMph: null, types: [] });
    assert.deepEqual(model.ribbon("missing", true), []);
    assert.equal(model.situation("missing"), "상황 정보 없음");
  }
});

test("the module does not mutate input and fresh result objects cannot alter later calls", () => {
  const rows = [pitch(2), pitch(0), pitch(1)];
  const before = JSON.stringify(rows);
  deepFreeze(rows);
  const model = context.create(rows);
  model.options(); model.matchingKeys(all); model.situation(rows[0].pitch_id);
  const first = model.prior(rows[0].pitch_id); first.types[0].count = 999;
  const ribbon = model.ribbon(rows[0].pitch_id, true); ribbon[0].kind = "changed";
  assert.equal(model.prior(rows[0].pitch_id).types[0].count, 2);
  assert.equal(model.ribbon(rows[0].pitch_id, true)[0].kind, "ball");
  assert.equal(JSON.stringify(rows), before);
  assert.deepEqual(model.matchingKeys(all), ["123:1:1", "123:1:2", "123:1:3"]);
});

test("ambiguous duplicate keys and non-arrays are rejected", () => {
  assert.throws(() => context.create([pitch(0), pitch(0)]), /중복/);
  assert.throws(() => context.create(null), TypeError);
});

test('automatic balls are shown as records but excluded from actual pitch-type history',()=>{
  const rows=[pitch(0),pitch(1,{post:actual(null,null,'automatic_ball',null)}),pitch(2)];
  const model=context.create(rows);
  assert.equal(model.prior(rows[2].pitch_id).total,1);
  assert.equal(model.prior(rows[2].pitch_id).types[0].share,1);
  assert.equal(model.ribbon(rows[1].pitch_id,false)[1].label,'결과 숨김');
  assert.equal(model.ribbon(rows[1].pitch_id,true)[1].label,'자동 볼');
});

test("hit by pitch is named in the ribbon once disclosed and hidden before", () => {
  const rows = [pitch(0), pitch(1, { post: actual("SL", 80.3, "hit_by_pitch", "슬라이더") })];
  const view = context.create(rows);
  const shown = view.ribbon(rows[1].pitch_id, true).find(chip => chip.isCurrent);
  assert.equal(shown.kind, "hbp");
  assert.equal(shown.label, "몸에 맞는 공");
  const hidden = view.ribbon(rows[1].pitch_id, false).find(chip => chip.isCurrent);
  assert.equal(hidden.kind, "hidden");
});

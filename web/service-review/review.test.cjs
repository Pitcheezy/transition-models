"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const api = require("./review.js");
function fixture() {
  const makePitch = (pa, number, recStatus = "ready") => ({ index: pa * 10 + number,
    key: `123:${pa}:${number}`, pa_key: `123:${pa}`, at_bat_number: pa, pitch_number: number,
    pre: { situation: { inning: 1, half: "Top", balls: 0, strikes: 0, outs: 0, bases: 0, home_score: 0, away_score: 0 },
      pitcher: { id: 1, name: "Synthetic Pitcher", hand: "R" }, batter: { id: 2, name: "Synthetic Batter", side: "L" },
      recommendation: { status: recStatus, provenance: "asof_replay", reason: null,
        candidates: recStatus === "ready" ? [{ rank: 1, pitch_type: "FF", pitch_label: "Fastball",
          selection_probability: 0, target: { x: 0, z: 2.5 }, zone_label: "middle" },
        { rank: 2, pitch_type: "CH", pitch_label: "Changeup", selection_probability: null, target: null, zone_label: null }] : [] } },
    post: { actual: { pitch_type: "SECRET_ACTUAL", pitch_label: "SECRET_ACTUAL_LABEL", x: 0, z: 0,
      speed_mph: 0, result_label: "SECRET_RESULT", play_text: "SECRET_PLAY", setup_status: "estimated", setup_x_ft: 0 } }
  });
  return { schema: api.SCHEMA, profile: api.PROFILE, game: { game_pk: 123, kst_date: "2026-10-09", away_team: "A", home_team: "B" },
    source: { input_kind: "synthetic", upstream_kind: "archive", sha256: "a".repeat(64) },
    zone_bounds: { bottom: 1.5, top: 3.5 }, pitches: [makePitch(1, 1), makePitch(1, 2), makePitch(2, 1, "unsupported"), makePitch(2, 2, "missing")] };
}
test("strict report schema/profile excludes raw/provisional responses", () => {
  for (const mutation of [r => { r.schema = "pitcheezy-service-game-v2"; }, r => { r.profile = "teammate_status_20261007_provisional_v1"; }]) {
    const r = fixture(); mutation(r); assert.throws(() => api.viewFor(r, "123:1:1"));
  }
});
test("unexpected nested post-pitch fields in pre containers cannot bypass reveal", () => {
  for (const field of ["actual", "post", "result", "we", "catcher_setup", "setup_x_ft", "setup_status"]) {
    const report = fixture();
    report.pitches[0].pre.recommendation.extra = [{ [field]: "SECRET" }];
    assert.throws(() => api.viewFor(report, "123:1:1"));
  }
});
test("hidden view and plot do not contain actual values, actual point or setup", () => {
  const report = fixture(), view = api.viewFor(report, "123:1:1");
  assert.equal(view.actual, null);
  assert.equal(JSON.stringify(view).includes("SECRET"), false);
  assert.equal(JSON.stringify(view).includes("setup_"), false);
  assert.equal(api.plotModel(report, view).points.length, 1);
  assert.equal(api.plotModel(report, view).setup, null);
});
test("explicit reveal preserves actual zero and setup x=0 without making up a height", () => {
  const report = fixture(), view = api.viewFor(report, "123:1:1", true), plot = api.plotModel(report, view);
  assert.equal(view.actual.pitch_type, "SECRET_ACTUAL");
  assert.deepEqual(plot.setup, { x: 0, clipped: false });
  assert.equal(plot.points.at(-1).x, 0); assert.equal(plot.points.at(-1).z, 0);
  assert.equal(Object.hasOwn(plot.setup, "z"), false);
});
test("navigation to another or the same pitch and PA resets the reveal gate", () => {
  const initial = api.initialState(fixture());
  assert.equal(initial.key, "123:1:1"); assert.equal(initial.revealed, false);
  const shown = api.reveal(initial);
  for (const key of ["123:1:1", "123:1:2"]) assert.equal(api.selectPitch(shown, key).revealed, false);
  assert.deepEqual([api.selectPA(shown, "123:2").key, api.selectPA(shown, "123:2").revealed], ["123:2:1", false]);
  assert.equal(api.initialState(fixture()).revealed, false);
  assert.throws(() => api.selectPitch(shown, "bad"));
});
test("views are defensive copies and selection weights are not renormalized", () => {
  const report = fixture(); report.pitches[0].pre.recommendation.candidates[0].selection_probability = .21;
  const view = api.viewFor(report, "123:1:1", true);
  assert.equal(view.pre.recommendation.candidates[0].selection_probability, .21);
  view.actual.x = 9; view.pre.situation.balls = 3;
  assert.equal(report.pitches[0].post.actual.x, 0); assert.equal(report.pitches[0].pre.situation.balls, 0);
});
test("unsupported and missing recommendations remain separate with no phantom candidates", () => {
  const report = fixture();
  for (const [key, status] of [["123:2:1", "unsupported"], ["123:2:2", "missing"]]) {
    const view = api.viewFor(report, key);
    assert.equal(view.pre.recommendation.status, status); assert.deepEqual(api.plotModel(report, view).points, []);
  }
});
test("null values stay absent; unverified or unavailable setup never produces a point", () => {
  const report = fixture(), a = report.pitches[0].post.actual;
  for (const status of ["unavailable", "unverified", undefined]) {
    a.setup_status = status;
    assert.equal(api.plotModel(report, api.viewFor(report, "123:1:1", true)).setup, null);
  }
  a.setup_status = "estimated"; a.setup_x_ft = null; a.x = null;
  assert.equal(api.plotModel(report, api.viewFor(report, "123:1:1", true)).setup, null);
  assert.equal(api.plotModel(report, api.viewFor(report, "123:1:1", true)).points.length, 1);
  report.pitches[0].post.actual = null;
  assert.equal(api.viewFor(report, "123:1:1", true).actual, null);
});
test("setup absence, abstention, and estimated but missing x have distinct explanations", () => {
  const report = fixture(), actual = report.pitches[0].post.actual;
  assert.equal(api.setupSummary(api.viewFor(report, "123:1:1")).status, "hidden");
  for (const [status, x, expected, message] of [[null, null, "not_supplied", "영상 추정 행 없음"],
    ["unavailable", null, "unavailable", "영상은 있으나 추정 기권"],
    ["estimated", null, "coordinate_missing", "가로 좌표 미제공"], ["estimated", 0, "estimated", ""]]) {
    actual.setup_status = status; actual.setup_x_ft = x;
    assert.deepEqual(api.setupSummary(api.viewFor(report, "123:1:1", true)), { status: expected, message });
  }
});
test("coincident recommendations preserve their coordinates and every rank in one marker", () => {
  const report = fixture(), candidates = report.pitches[0].pre.recommendation.candidates;
  candidates.push({ ...candidates[0], rank: 3, pitch_type: "SL", pitch_label: "Slider" });
  const hidden = api.plotModel(report, api.viewFor(report, "123:1:1"));
  assert.equal(hidden.points.length, 1);
  assert.deepEqual(hidden.points[0].ranks, [1, 3]); assert.equal(hidden.points[0].label, "1·3");
  assert.equal(hidden.points[0].x, 0); assert.equal(hidden.points[0].z, 2.5);
  report.pitches[0].post.actual.z = 2.5;
  const shown = api.plotModel(report, api.viewFor(report, "123:1:1", true));
  assert.equal(shown.points.length, 2); assert.equal(shown.points[1].kind, "actual");
  assert.equal(shown.points[1].overlapsCandidate, true); assert.deepEqual(shown.points[0], hidden.points[0]);
});
test("fixed chart bounds do not move after reveal and outliers are explicitly clipped", () => {
  const report = fixture(); report.pitches[0].post.actual.x = 10;
  report.pitches[0].post.actual.setup_x_ft = -3;
  const hidden = api.plotModel(report, api.viewFor(report, "123:1:1"));
  const shown = api.plotModel(report, api.viewFor(report, "123:1:1", true));
  assert.deepEqual(hidden.bounds, shown.bounds);
  assert.equal(shown.points.at(-1).clipped, true); assert.equal(shown.setup.clipped, true);
});
test("chart grid uses the supplied service width and three-column target centers", () => {
  const report = fixture(), model = api.plotModel(report, api.viewFor(report, "123:1:1"));
  assert.equal(model.zone.left, -.83); assert.equal(model.zone.right, .83);
  assert.equal(model.zone.bottom, 1.5); assert.equal(model.zone.top, 3.5);
  for (const [actual, expected] of model.zone.columnCenters.map((v, i) => [v, [-.5533333333333333, 0, .5533333333333333][i]])) {
    assert.ok(Math.abs(actual - expected) < 1e-12);
  }
  assert.ok(Math.abs(model.zone.verticalDividers[0] + .27666666666666667) < 1e-12);
  assert.ok(Math.abs(model.zone.verticalDividers[1] - .27666666666666667) < 1e-12);
});
test("invalid boundaries, NaN coordinates, duplicates and loose reveal flags reject", () => {
  for (const mutate of [r => { r.zone_bounds.top = r.zone_bounds.bottom; },
    r => { r.pitches[0].post.actual.x = NaN; }, r => { r.pitches[0].pre.situation.balls = 9; },
    r => { r.pitches[0].pre.recommendation.candidates[0].target.x = Infinity; },
    r => { r.pitches.push(r.pitches[0]); }]) {
    const report = fixture(); mutate(report); assert.throws(() => api.validateReport(report));
  }
  assert.throws(() => api.viewFor(fixture(), "123:1:1", "true"));
  assert.throws(() => api.viewFor(fixture(), "absent"));
});
test("last selected file wins when earlier asynchronous reads finish late", async () => {
  let finishFirst, visible = null, clears = 0;
  const load = api.createLoadCoordinator({ clear: () => { visible = null; clears++; }, commit: r => { visible = r; }, fail: error => { throw error; } });
  const first = load(() => new Promise(resolve => { finishFirst = resolve; }));
  const newer = fixture(); newer.game.game_pk = 456;
  for (const pitch of newer.pitches) {
    pitch.pa_key = `456:${pitch.at_bat_number}`;
    pitch.key = `${pitch.pa_key}:${pitch.pitch_number}`;
  }
  await load(async () => newer); finishFirst(fixture()); await first;
  assert.equal(visible, newer); assert.equal(clears, 2);
});
test("new failed selection clears old report and late success cannot restore it", async () => {
  let finishOld, visible = fixture(), errorMessage;
  const load = api.createLoadCoordinator({ clear: () => { visible = null; }, commit: r => { visible = r; }, fail: e => { errorMessage = e.message; } });
  const pending = load(() => new Promise(resolve => { finishOld = resolve; }));
  await load(async () => { throw new Error("bad file"); }); finishOld(fixture()); await pending;
  assert.equal(visible, null); assert.equal(errorMessage, "bad file");
});
test("local parser enforces byte limit and readable UTF-8 JSON", () => {
  const valid = new TextEncoder().encode(JSON.stringify(fixture()));
  assert.equal(api.parseBytes(valid).profile, api.PROFILE);
  assert.throws(() => api.parseBytes(new Uint8Array(api.MAX_BYTES + 1)));
  assert.throws(() => api.parseBytes(new Uint8Array([255])));
  assert.throws(() => api.parseBytes(new TextEncoder().encode("not JSON")));
});

function mediaFixture() {
  return { schema: api.MEDIA_SCHEMA, game_pk: 123, source_sha256: "a".repeat(64), clips: [
    { pitch_key: "123:1:1", play_id: "00000000-0000-0000-0000-000000000001",
      video: "media/pitch-123-1-1-official.mp4", poster: "media/pitch-123-1-1-official.jpg",
      video_sha256: "b".repeat(64), poster_sha256: "c".repeat(64), duration_seconds: 6.999 },
    { pitch_key: "123:1:2", play_id: "00000000-0000-0000-0000-000000000002",
      video: "media/pitch-123-1-2-official.mp4", poster: "media/pitch-123-1-2-official.jpg",
      video_sha256: "d".repeat(64), poster_sha256: "e".repeat(64), duration_seconds: 7.13 }
  ] };
}
function mediaHarness() {
  const log = { clears: 0, statuses: [], reveals: [] };
  const controller = api.createMediaController({ clear: () => { log.clears++; },
    status: event => { log.statuses.push(event); }, reveal: event => { log.reveals.push(event); } });
  return { controller, log };
}
test("media binds only exact game, source hash, and an existing pitch key", () => {
  const report = fixture(), manifest = mediaFixture();
  assert.equal(api.mediaBinding(report, "123:1:1", manifest).clip.play_id, manifest.clips[0].play_id);
  assert.equal(api.mediaBinding(report, "123:2:1", manifest).clip, null);
  assert.equal(api.mediaBinding(report, "123:9:9", manifest).clip, null);
  assert.equal(api.mediaBinding(report, "123:1:1", null).clip, null);
  report.source.sha256 = "f".repeat(64);
  assert.equal(api.mediaBinding(report, "123:1:1", manifest).clip, null);
  report.source.sha256 = manifest.source_sha256; report.game.game_pk = 456;
  assert.equal(api.mediaBinding(report, "123:1:1", manifest).clip, null);
});
test("media manifest rejects remote, blob, traversal, encoded and ambiguous paths", () => {
  for (const path of ["https://example.com/v.mp4", "//example.com/v.mp4", "blob:local", "/media/v.mp4",
    "media/../v.mp4", "media/%2e%2e/v.mp4", "media\\v.mp4", "media/v.mp4?q=1", "media/v.mp4#fragment",
    "media/sub/v.mp4", "media/a b.mp4", "data:video/mp4;base64,AAA"]) {
    const manifest = mediaFixture(); manifest.clips[0].video = path;
    assert.throws(() => api.validateMediaManifest(manifest), path);
  }
  const manifest = mediaFixture(); manifest.clips[0].poster = "https://example.com/p.jpg";
  assert.throws(() => api.validateMediaManifest(manifest));
});
test("media manifest rejects wrong schema, bad identities, hashes and durations", () => {
  for (const mutate of [m => { m.schema = "raw-video-list"; }, m => { m.source_sha256 = "bad"; },
    m => { m.clips[0].video_sha256 = "bad"; }, m => { m.clips[0].poster_sha256 = "bad"; },
    m => { m.clips[0].pitch_key = "456:1:1"; }, m => { m.clips[0].play_id = "not-a-uuid"; },
    m => { m.clips[0].duration_seconds = NaN; }, m => { m.clips[0].duration_seconds = 0; },
    m => { m.clips.push(m.clips[0]); }, m => { m.clips[1].play_id = m.clips[0].play_id; }]) {
    const manifest = mediaFixture(); mutate(manifest); assert.throws(() => api.validateMediaManifest(manifest));
  }
});
test("clip binding is copied and cannot mutate the manifest", () => {
  const manifest = mediaFixture(), binding = api.mediaBinding(fixture(), "123:1:1", manifest);
  binding.clip.video = "changed";
  assert.equal(manifest.clips[0].video, "media/pitch-123-1-1-official.mp4");
});
test("only a played current clip may reveal its own result once", () => {
  const { controller, log } = mediaHarness();
  const selection = controller.select(fixture(), "123:1:1", mediaFixture());
  assert.equal(controller.signal(selection.token, "ended"), false); assert.equal(log.reveals.length, 0);
  assert.equal(controller.signal(selection.token, "play"), true);
  assert.equal(controller.signal(selection.token, "ended"), true);
  assert.deepEqual(log.reveals, [{ key: "123:1:1", gamePk: 123, sourceSha256: "a".repeat(64) }]);
  assert.equal(controller.signal(selection.token, "ended"), false); assert.equal(log.reveals.length, 1);
});
test("pitch navigation, same-pitch reselection and PA changes invalidate late media events", () => {
  for (const nextKey of ["123:1:1", "123:1:2", "123:2:1"]) {
    const { controller, log } = mediaHarness();
    const old = controller.select(fixture(), "123:1:1", mediaFixture());
    controller.signal(old.token, "play");
    const next = controller.select(fixture(), nextKey, mediaFixture()), count = log.statuses.length;
    assert.notEqual(old.token, next.token); assert.equal(log.clears, 2);
    for (const event of ["ended", "error", "play", "pause"]) assert.equal(controller.signal(old.token, event), false);
    assert.equal(log.statuses.length, count); assert.equal(log.reveals.length, 0);
  }
});
test("new report load including failure immediately clears media and blocks old reveal", async () => {
  const { controller, log } = mediaHarness(), old = controller.select(fixture(), "123:1:1", mediaFixture());
  controller.signal(old.token, "play");
  const load = api.createLoadCoordinator({ clear: () => controller.reset(), commit: () => assert.fail("invalid report"), fail: () => {} });
  await load(async () => { throw new Error("invalid replacement"); });
  assert.equal(log.clears, 2); assert.equal(controller.signal(old.token, "ended"), false);
  assert.equal(log.reveals.length, 0);
});
test("missing or source-mismatched media never blocks manual result reveal", () => {
  for (const manifest of [null, { ...mediaFixture(), source_sha256: "f".repeat(64) }]) {
    const state = api.initialState(fixture()), { controller, log } = mediaHarness();
    const selection = controller.select(state.report, state.key, manifest);
    assert.equal(selection.clip, null); assert.equal(controller.signal(selection.token, "ended"), false);
    assert.equal(api.reveal(state).revealed, true); assert.equal(log.reveals.length, 0);
  }
});
test("play rejection has a recoverable error and cannot reveal; retry has a new session", async () => {
  const { controller, log } = mediaHarness();
  const first = controller.select(fixture(), "123:1:1", mediaFixture());
  await controller.requestPlay(first.token, async () => { throw new DOMException("play not allowed", "NotAllowedError"); });
  assert.equal(log.statuses.at(-1).phase, "error");
  assert.equal(controller.signal(first.token, "ended"), false); assert.equal(log.reveals.length, 0);
  const retry = controller.select(fixture(), "123:1:1", mediaFixture());
  assert.notEqual(retry.token, first.token);
  await controller.requestPlay(retry.token, async () => {});
  controller.signal(retry.token, "ended"); assert.equal(log.reveals.length, 1);
});
test("late play promise resolution or rejection cannot affect a new selected clip", async () => {
  for (const rejected of [false, true]) {
    const { controller, log } = mediaHarness();
    let finish;
    const first = controller.select(fixture(), "123:1:1", mediaFixture());
    const pending = controller.requestPlay(first.token, () => new Promise((resolve, reject) => { finish = rejected ? reject : resolve; }));
    controller.select(fixture(), "123:1:2", mediaFixture());
    const count = log.statuses.length;
    finish(rejected ? new Error("late playback failure") : undefined);
    assert.equal(await pending, false); assert.equal(log.statuses.length, count); assert.equal(log.reveals.length, 0);
  }
});
test("native media failure after play blocks ended until an explicit retry", () => {
  const { controller, log } = mediaHarness(), selection = controller.select(fixture(), "123:1:1", mediaFixture());
  controller.signal(selection.token, "play"); controller.signal(selection.token, "error");
  assert.equal(controller.signal(selection.token, "ended"), false);
  assert.equal(controller.signal(selection.token, "play"), false);
  assert.equal(log.reveals.length, 0); assert.equal(log.statuses.at(-1).phase, "error");
});
test("normal pause AbortError preserves native resume and ended result reveal", async () => {
  const { controller, log } = mediaHarness(), selection = controller.select(fixture(), "123:1:1", mediaFixture());
  let interrupt;
  const pending = controller.requestPlay(selection.token, () => new Promise((_resolve, reject) => { interrupt = reject; }));
  controller.signal(selection.token, "play"); controller.signal(selection.token, "pause");
  interrupt(new DOMException("The play request was interrupted by pause", "AbortError"));
  await pending;
  assert.equal(log.statuses.at(-1).phase, "paused");
  assert.equal(log.statuses.some(event => event.phase === "error"), false);
  assert.equal(controller.signal(selection.token, "play"), true);
  assert.equal(controller.signal(selection.token, "ended"), true);
  assert.equal(log.reveals.length, 1);
});
test("late normal interruption cannot pause the newly selected clip", async () => {
  const { controller, log } = mediaHarness(), first = controller.select(fixture(), "123:1:1", mediaFixture());
  let interrupt;
  const pending = controller.requestPlay(first.token, () => new Promise((_resolve, reject) => { interrupt = reject; }));
  const next = controller.select(fixture(), "123:1:2", mediaFixture());
  controller.signal(next.token, "play");
  const count = log.statuses.length;
  interrupt(new DOMException("Detached player interrupted", "AbortError"));
  assert.equal(await pending, false); assert.equal(log.statuses.length, count);
  assert.equal(log.statuses.at(-1).phase, "playing");
  controller.signal(next.token, "ended"); assert.equal(log.reveals[0].key, "123:1:2");
});

for (const [name, mutate] of [
  ["game", report => { report.game.game_pk = 456; }],
  ["pitch number", report => { report.pitches[0].pitch_number = 99; }],
  ["plate appearance number", report => { report.pitches[0].at_bat_number = 9; }],
  ["pitch key", report => { report.pitches[0].key = "123:9:9"; }],
  ["plate appearance key", report => { report.pitches[0].pa_key = "123:9"; }],
  ["padded pitch key", report => { report.pitches[0].key = "123:01:1"; }],
  ["foreign plate appearance key", report => { report.pitches[0].pa_key = "456:1"; }]
]) {
  test(`uploaded report rejects inconsistent ${name} before selecting or binding media`, () => {
    const report = fixture(); mutate(report);
    assert.throws(() => api.validateReport(report), /식별자/);
    assert.throws(() => api.initialState(report), /식별자/);
  });
}

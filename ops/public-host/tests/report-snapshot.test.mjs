import test from "node:test";
import assert from "node:assert/strict";
import { buildReport } from "../report.mjs";

const NOW = Date.parse("2026-10-13T06:00:00Z");
const SOURCE_HASH = "b".repeat(64);
const session = (extra = {}) => ({ utc_day: "2026-10-12", game_pk: 123,
  sessions: 2, active_ms: 90000, mean_active_ms: 45000, ...extra });
const feedback = (extra = {}) => ({ utc_day: "2026-10-12", game_pk: 123,
  rating: "helpful", reason: "none", responses: 1, ...extra });
const summary = (sessions = [], feedback = [], extra = {}) => ({
  schema: "pitcheezy-usage-summary-v1", timezone: "UTC", from_day: "2026-10-12",
  to_day: "2026-10-12", generated_at: new Date(NOW).toISOString(), sessions, feedback,
  limits: "Opt-in browser sessions, not unique people; browser-reported active time.", ...extra,
});
const snapshot = (usage_summary = summary(), extra = {}) => ({
  schema: "pitcheezy-usage-snapshot-v1", source_sha256: SOURCE_HASH,
  coverage: "unverified", aggregation: "utc_day", usage_summary, ...extra,
});
const collection = (telemetry_enabled = true, feedback_enabled = true) => ({
  telemetry_enabled, feedback_enabled, consent_note: "synthetic fixture", retain_days: 30,
});
const input = (usage_summary = snapshot(), extra = {}) => ({
  schema: "pitcheezy-game-report-input-v1", game_pk: 123, evidence: "synthetic",
  window: { from: "2026-10-12T00:00:00Z", to: "2026-10-12T23:59:59Z" },
  collection: collection(), usage_summary, monitor_state: null, notice_audit: null,
  alert_state: null, actions: [], sources: { host_commit: "a".repeat(40),
    frontend_commit: null, contract_version: null, release_manifest_sha256: null },
  commands: [], unmeasured: [], notes: "", ...extra,
});
const report = (usage = snapshot(), extra = {}) => buildReport(input(usage, extra), { now: NOW });
const assertNullCounts = usage => {
  assert.equal(usage.sessions, null);
  assert.equal(usage.active_ms, null);
  assert.equal(usage.feedback, null);
};
const assertSnapshotCaveats = result => {
  assert.match(result.markdown, /UTC 날짜 전체/);
  assert.match(result.markdown, /수집·보존 누락/);
  assert.ok(result.json.unmeasured.some(value => /시각|시간|datetime/.test(value)),
    "exact report-window totals must remain explicitly unmeasured");
  assert.equal(result.json.usage.summary_covers_window, false);
};

test("WS-report2: the complete envelope retains only validated provenance in operator JSON", () => {
  const source = snapshot(summary([session()], [feedback()]));
  const supplied = input(source), before = structuredClone(supplied);
  const result = buildReport(supplied, { now: NOW });
  assert.deepEqual(supplied, before, "building a report must not strip or mutate the envelope");
  assert.deepEqual(result.json.usage_snapshot, {
    schema: "pitcheezy-usage-snapshot-v1", source_sha256: SOURCE_HASH,
    coverage: "unverified", aggregation: "utc_day", generated_at: "2026-10-13T06:00:00.000Z",
    from_day: "2026-10-12", to_day: "2026-10-12",
  });
  assert.equal(result.json.usage.status, "partial_data");
  assert.equal(result.json.usage.sessions, 2);
  assert.equal(result.json.usage.active_ms, 90000);
  assert.deepEqual(result.json.usage.feedback, [
    { utc_day: "2026-10-12", rating: "helpful", reason: "none", responses: 1 },
  ]);
  assert.equal(result.json.posted, false);
  assert.equal(result.json.approval_required, true);
  assert.ok(!result.markdown.includes(SOURCE_HASH), "private source provenance is not issue-draft copy");
  assert.doesNotMatch(JSON.stringify(result), /session_id|feedback_id|snapshot\.sqlite/);
  assertSnapshotCaveats(result);
});

test("WS-report2: empty and irrelevant retained rows are no data, never measured zero", () => {
  const cases = [summary(), summary([session({ game_pk: 999 })], [feedback({ game_pk: 999 })]),
    summary([session({ utc_day: "2026-10-11" })], [feedback({ utc_day: "2026-10-11" })],
      { from_day: "2026-10-11", to_day: "2026-10-12" })];
  for (const retained of cases) {
    const result = report(snapshot(retained));
    assert.equal(result.json.usage.status, "no_data");
    assertNullCounts(result.json.usage);
    assert.doesNotMatch(result.markdown, /자료 없음이 아니라 0세션/);
    assertSnapshotCaveats(result);
  }
});

test("WS-report2: an enabled channel with no retained rows stays null beside observed data", () => {
  const sessionsOnly = report(snapshot(summary([session()])));
  assert.equal(sessionsOnly.json.usage.status, "partial_data");
  assert.equal(sessionsOnly.json.usage.sessions, 2);
  assert.equal(sessionsOnly.json.usage.active_ms, 90000);
  assert.equal(sessionsOnly.json.usage.feedback, null);
  const feedbackOnly = report(snapshot(summary([], [feedback()])));
  assert.equal(feedbackOnly.json.usage.status, "partial_data");
  assert.equal(feedbackOnly.json.usage.sessions, null);
  assert.equal(feedbackOnly.json.usage.active_ms, null);
  assert.equal(feedbackOnly.json.usage.feedback[0].responses, 1);
  for (const result of [sessionsOnly, feedbackOnly]) assertSnapshotCaveats(result);
});

test("WS-report2: collection flags suppress retained OFF-channel data and preserve unknown counts", () => {
  for (const telemetry of [false, true]) {
    for (const feedbackEnabled of [false, true]) {
      const result = report(snapshot(summary([session()], [feedback()])), {
        collection: collection(telemetry, feedbackEnabled),
      });
      assert.equal(result.json.usage.status, telemetry || feedbackEnabled ? "partial_data" : "collection_off");
      assert.equal(result.json.usage.sessions, telemetry ? 2 : null);
      assert.equal(result.json.usage.active_ms, telemetry ? 90000 : null);
      if (feedbackEnabled) assert.equal(result.json.usage.feedback[0].responses, 1);
      else assert.equal(result.json.usage.feedback, null);
      assert.equal(result.json.usage_snapshot.coverage, "unverified");
      assert.notEqual(result.json.usage.summary_covers_window, true);
    }
  }
  for (const [retained, flags] of [
    [summary([session()]), collection(false, true)],
    [summary([], [feedback()]), collection(true, false)],
  ]) {
    const result = report(snapshot(retained), { collection: flags });
    assert.equal(result.json.usage.status, "no_data", "OFF-channel rows are not enabled observations");
    assertNullCounts(result.json.usage);
  }
});

test("WS-report2: a one-hour window retains full-day aggregates without claiming hour totals", () => {
  const window = { from: "2026-10-12T08:00:00Z", to: "2026-10-12T09:00:00Z" };
  const result = report(snapshot(summary([session()], [feedback()])), { window });
  assert.deepEqual(result.json.window, window);
  assert.equal(result.json.usage.sessions, 2);
  assert.equal(result.json.usage.active_ms, 90000);
  assert.equal(result.json.usage.status, "partial_data");
  assertSnapshotCaveats(result);
});

test("WS-report2: crossing midnight retains each UTC date and excludes other games and dates", () => {
  const retained = summary([
    session({ utc_day: "2026-10-11", sessions: 50 }), session(),
    session({ utc_day: "2026-10-13", sessions: 3, active_ms: 30000, mean_active_ms: 10000 }),
    session({ game_pk: 999, sessions: 70 }),
  ], [feedback({ utc_day: "2026-10-11", responses: 50 }), feedback(),
    feedback({ utc_day: "2026-10-13", responses: 2 }), feedback({ game_pk: 999, responses: 70 })],
  { from_day: "2026-10-11", to_day: "2026-10-13" });
  const result = report(snapshot(retained), {
    window: { from: "2026-10-12T23:30:00Z", to: "2026-10-13T00:30:00Z" },
  });
  assert.equal(result.json.usage.sessions, 5);
  assert.equal(result.json.usage.active_ms, 120000);
  assert.deepEqual(result.json.usage.feedback, [
    { utc_day: "2026-10-12", rating: "helpful", reason: "none", responses: 1 },
    { utc_day: "2026-10-13", rating: "helpful", reason: "none", responses: 2 },
  ]);
  assertSnapshotCaveats(result);
});

test("WS-report2: partial date overlap retains evidence while absent overlap remains unknown", () => {
  const retained = snapshot(summary([session()], [feedback()]));
  const result = report(retained, {
    window: { from: "2026-10-11T08:00:00Z", to: "2026-10-13T08:00:00Z" },
  });
  assert.equal(result.json.usage.status, "partial_data");
  assert.equal(result.json.usage.sessions, 2);
  assertSnapshotCaveats(result);
  const outside = report(retained, {
    window: { from: "2026-10-13T08:00:00Z", to: "2026-10-13T09:00:00Z" },
  });
  assert.equal(outside.json.usage.status, "no_data");
  assertNullCounts(outside.json.usage);
  assertSnapshotCaveats(outside);
});

test("WS-report2: invalid snapshot provenance and unsupported envelope keys are refused", () => {
  for (const change of [
    { source_sha256: "b".repeat(63) }, { source_sha256: "B".repeat(64) },
    { source_sha256: 123 }, { source_sha256: "g".repeat(64) },
    { coverage: "complete" }, { coverage: null }, { aggregation: "exact_window" },
    { aggregation: null }, { source_path: "private-snapshot.sqlite" },
  ]) assert.throws(() => report(snapshot(summary(), change)), { code: "invalid_usage_snapshot" });
  const missing = snapshot();
  delete missing.source_sha256;
  assert.throws(() => report(missing), { code: "invalid_usage_snapshot" });
});

test("WS-report2: nested summaries must have the exact supported shape and real generation times", () => {
  const missing = summary();
  delete missing.generated_at;
  for (const nested of [null, [], snapshot(), missing, summary([], [], { raw_path: "private.sqlite" })]) {
    assert.throws(() => report(snapshot(nested)), { code: "invalid_usage_snapshot" });
  }
  for (const generated_at of [null, 123, "", "2026-02-31T06:00:00Z", "2026-10-12T24:00:00Z",
    "2026-10-12T23:59:60Z", "2026-10-12T06:00:00+00:00", "2026-10-12T06:00:00.1234Z"]) {
    assert.throws(() => report(snapshot(summary([], [], { generated_at }))), { code: "invalid_usage_snapshot" });
  }
  for (const generated_at of ["2026-10-13T06:00:00Z", "2026-10-13T06:00:00.1Z",
    "2026-10-13T06:00:00.12Z", "2026-10-13T06:00:00.123Z"]) {
    assert.equal(report(snapshot(summary([], [], { generated_at }))).json.usage_snapshot.generated_at, generated_at);
  }
});

test("WS-report2: nested rows retain existing validation before aggregation or channel suppression", () => {
  const badSummaries = [
    summary([session({ sessions: 0 })]), summary([], [feedback({ responses: 0 })]),
    summary([session({ active_ms: -1 })]), summary([session({ sessions: "2" })]),
    summary([session({ utc_day: "2026-02-31" })]), summary([session({ utc_day: "2026-10-11" })]),
    summary([session(), session()]), summary([], [feedback(), feedback()]),
    summary([], [feedback({ reason: "private text" })]), summary([], [feedback({ responses: -1 })]),
    summary([session({ active_ms: Number.MAX_SAFE_INTEGER }), session({ game_pk: 999 })]),
    summary([], [], { timezone: "Asia/Seoul" }), summary([], [], { from_day: "2026-02-31" }),
    summary([], [], { from_day: "2026-10-13", to_day: "2026-10-12" }),
  ];
  for (const retained of badSummaries) {
    for (const flags of [collection(), collection(false, false)]) {
      assert.throws(() => report(snapshot(retained), { collection: flags }), { code: "invalid_usage_summary" });
    }
  }
});

test("WS-report2: plain summary inputs keep their legacy zero, counted and feedback-only results", () => {
  const zero = report(summary());
  assert.equal(zero.json.usage.status, "zero_rows");
  assert.equal(zero.json.usage.sessions, 0);
  assert.equal(zero.json.usage.active_ms, 0);
  assert.deepEqual(zero.json.usage.feedback, []);
  assert.equal(zero.json.usage.summary_covers_window, true);
  assert.equal(Object.hasOwn(zero.json, "usage_snapshot"), false);
  const counted = report(summary([session()], [feedback()]));
  assert.equal(counted.json.usage.status, "counted");
  assert.equal(counted.json.usage.sessions, 2);
  assert.deepEqual(counted.json.usage.feedback, [{ rating: "helpful", reason: "none", responses: 1 }]);
  const feedbackOnly = report(summary([], [feedback()]), { collection: collection(false, true) });
  assert.equal(feedbackOnly.json.usage.status, "feedback_only");
  assert.equal(feedbackOnly.json.usage.sessions, null);
  assert.equal(feedbackOnly.json.usage.active_ms, null);
  assert.equal(feedbackOnly.json.usage.feedback[0].responses, 1);
});
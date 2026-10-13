import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import { validateReportInput, usageSection, problemsSection, buildReport, EVIDENCE } from "../report.mjs";

const sha = text => createHash("sha256").update(text).digest("hex");
const NOW = Date.parse("2026-10-13T06:00:00Z");
const base = (extra = {}) => ({
  schema: "pitcheezy-game-report-input-v1", game_pk: 123, evidence: "synthetic",
  window: { from: "2026-10-12T00:00:00Z", to: "2026-10-12T23:59:59Z" },
  collection: { telemetry_enabled: true, feedback_enabled: true, consent_note: "opt-in 체크박스, 위젯 미삽입 화면은 누락", retain_days: 30 },
  usage_summary: null, monitor_state: null, notice_audit: null, alert_state: null, actions: [],
  sources: { host_commit: "a".repeat(40), frontend_commit: null, contract_version: "public-file-v1-draft-v0", release_manifest_sha256: null },
  commands: ["node ops/public-host/monitor-cli.mjs --config <운영 설정> --state <상태>"], unmeasured: [], notes: "", ...extra,
});
const summary = (rows, feedback = []) => ({ schema: "pitcheezy-usage-summary-v1", timezone: "UTC", from_day: "2026-10-12", to_day: "2026-10-12",
  generated_at: new Date(NOW).toISOString(), sessions: rows, feedback, limits: "synthetic" });

test("input validation refuses wrong shapes, windows, labels and secret-like content", () => {
  validateReportInput(base());
  for (const [bad, code] of [
    [base({ evidence: "real" }), "invalid_game_or_evidence"], [base({ game_pk: 0 }), "invalid_game_or_evidence"],
    [base({ window: { from: "2026-10-12T00:00:00Z", to: "2026-10-11T00:00:00Z" } }), "invalid_window"],
    [base({ window: { from: "2026-10-01T00:00:00Z", to: "2026-10-30T00:00:00Z" } }), "invalid_window"],
    [base({ collection: { telemetry_enabled: "true", feedback_enabled: false, consent_note: "", retain_days: null } }), "invalid_collection"],
    [base({ usage_summary: { schema: "other" } }), "invalid_usage_summary"],
    [base({ monitor_state: { events: [{ id: "x", kind: "opened", at_ms: 1, issues: [] }] } }), "invalid_monitor_state"],
    [base({ notice_audit: [{ schema: "nope" }] }), "invalid_notice_audit"],
    [base({ alert_state: { schema: "pitcheezy-host-alert-state-v1", deliveries: {}, pending: [], mock_only: false } }), "invalid_alert_state"],
    [base({ actions: [{ at: "2026-10-12T01:00:00Z", by: "ops a", what: "x" }] }), "invalid_actions"],
    [base({ sources: { host_commit: "short", frontend_commit: null, contract_version: null, release_manifest_sha256: null } }), "invalid_sources"],
    [base({ notes: "see https://host.example.test" }), "secret_or_address_like_content"],
    [base({ collection: { telemetry_enabled: true, feedback_enabled: true, consent_note: "Bearer " + "x".repeat(50), retain_days: 30 } }), "secret_or_address_like_content"],
    [base({ unmeasured: ["https://host.example.test/v1"] }), "secret_or_address_like_content"],
    [base({ sources: { host_commit: "a".repeat(40), frontend_commit: null, contract_version: "k".repeat(44), release_manifest_sha256: null } }), "secret_or_address_like_content"],
    [base({ actions: [{ at: "2026-10-12T01:00:00Z", by: "ops-a", what: "token " + "a".repeat(43) }] }), "secret_or_address_like_content"],
    [base({ notice_audit: [{ schema: "pitcheezy-notice-audit-v1", id: "x", at: "2026-10-12T10:01:00Z", active: true, message_id: "maintenance", operator: "ops-a", reason: "https://host.example.test", operator_token_prefix: "abc", revision: 1, etag_before: null, etag_after: null }] }), "secret_or_address_like_content"],
    [base({ commands: ["curl -H 'Authorization: Bearer abc'"] }), "secret_or_address_like_content"],
    [base({ extra: 1 }), "invalid_input"],
  ]) assert.throws(() => validateReportInput(bad), new RegExp(code), code);
});

test("usage distinguishes collection off, no data, zero rows and counted sessions", () => {
  assert.equal(usageSection(base({ collection: { telemetry_enabled: false, feedback_enabled: false, consent_note: "", retain_days: null } })).status, "collection_off");
  assert.equal(usageSection(base()).status, "no_data");
  const zero = usageSection(base({ usage_summary: summary([{ utc_day: "2026-10-12", game_pk: 999, sessions: 5, active_ms: 1000, mean_active_ms: 200 }]) }));
  assert.equal(zero.status, "zero_rows"); assert.equal(zero.sessions, 0);
  const counted = usageSection(base({ usage_summary: summary(
    [{ utc_day: "2026-10-12", game_pk: 123, sessions: 2, active_ms: 90000, mean_active_ms: 45000 },
     { utc_day: "2026-10-11", game_pk: 123, sessions: 9, active_ms: 9, mean_active_ms: 1 }],
    [{ utc_day: "2026-10-12", game_pk: 123, rating: "helpful", reason: "none", responses: 2 }]) }));
  assert.equal(counted.status, "counted"); assert.equal(counted.sessions, 2); assert.equal(counted.active_ms, 90000);
  assert.deepEqual(counted.feedback, [{ rating: "helpful", reason: "none", responses: 2 }]);
  assert.match(counted.statement, /사람 수/);
  assert.equal(counted.summary_covers_window, true);
});

test("a channel that was OFF is unmeasured (null), never 0, even when the other channel has rows", () => {
  const rows = [{ utc_day: "2026-10-12", game_pk: 123, sessions: 2, active_ms: 90000, mean_active_ms: 45000 }];
  const fb = [{ utc_day: "2026-10-12", game_pk: 123, rating: "helpful", reason: "none", responses: 2 }];
  const feedbackOnly = usageSection(base({ collection: { telemetry_enabled: false, feedback_enabled: true, consent_note: "", retain_days: 30 }, usage_summary: summary(rows, fb) }));
  assert.equal(feedbackOnly.status, "feedback_only"); assert.equal(feedbackOnly.sessions, null); assert.equal(feedbackOnly.active_ms, null);
  assert.deepEqual(feedbackOnly.feedback, [{ rating: "helpful", reason: "none", responses: 2 }]);
  assert.match(feedbackOnly.statement, /미측정/);
  const noFeedbackRows = usageSection(base({ collection: { telemetry_enabled: false, feedback_enabled: true, consent_note: "", retain_days: 30 }, usage_summary: summary(rows, []) }));
  assert.equal(noFeedbackRows.status, "feedback_only"); assert.equal(noFeedbackRows.sessions, null); assert.deepEqual(noFeedbackRows.feedback, []);
  const telemetryOnly = usageSection(base({ collection: { telemetry_enabled: true, feedback_enabled: false, consent_note: "", retain_days: 30 }, usage_summary: summary(rows, fb) }));
  assert.equal(telemetryOnly.status, "counted"); assert.equal(telemetryOnly.sessions, 2); assert.equal(telemetryOnly.feedback, null);
  const md = buildReport(base({ collection: { telemetry_enabled: false, feedback_enabled: true, consent_note: "", retain_days: 30 }, usage_summary: summary(rows, fb) }), { now: NOW });
  assert.match(md.markdown, /## 미측정\n- 이용자 수·활성 시간/);
  assert.equal(md.json.usage.sessions, null);
  const zero = buildReport(base({ usage_summary: summary([{ utc_day: "2026-10-12", game_pk: 999, sessions: 5, active_ms: 1000, mean_active_ms: 200 }]) }), { now: NOW });
  assert.doesNotMatch(zero.markdown, /## 미측정\n- 이용자 수·활성 시간/, "zero rows is a measurement, not unmeasured");
  // A summary whose day range does not reach the window is "no data", not zero sessions.
  const outside = { ...summary([]), from_day: "2026-10-01", to_day: "2026-10-05" };
  const uncovered = usageSection(base({ usage_summary: outside }));
  assert.equal(uncovered.status, "no_data"); assert.equal(uncovered.sessions, null); assert.equal(uncovered.summary_covers_window, false);
});

test("problems collect monitor events, notice changes and mock alert counts inside the window only", () => {
  const ev = (kind, at, issues = []) => ({ id: sha(kind + at), kind, at_ms: Date.parse(at), issues });
  const input = base({
    monitor_state: { events: [ev("opened", "2026-10-12T10:00:00Z", ["freshness_stale"]), ev("recovered", "2026-10-12T10:05:00Z"), ev("opened", "2026-10-13T10:00:00Z", ["page_http_error"])],
      incident: ev("opened", "2026-10-13T10:00:00Z", ["page_http_error"]), dropped_events: 1 },
    notice_audit: [{ schema: "pitcheezy-notice-audit-v1", id: "x", at: "2026-10-12T10:01:00Z", active: true, message_id: "maintenance", operator: "ops-a", reason: "drill", operator_token_prefix: "abc", revision: 1, etag_before: null, etag_after: '"x"' },
      { schema: "pitcheezy-notice-audit-v1", id: "y", at: "2026-10-14T10:01:00Z", active: false, message_id: "maintenance", operator: "ops-a", reason: "late", operator_token_prefix: "abc", revision: 2, etag_before: '"x"', etag_after: '"y"' }],
    alert_state: { schema: "pitcheezy-host-alert-state-v1", mock_only: true, pending: [], deliveries: {
      [sha("a") + ":opened:song"]: { status: "acknowledged", attempts: 1, last_attempt_ms: Date.parse("2026-10-12T10:02:00Z"), acknowledged_by_transport: true },
      [sha("a") + ":opened:ours"]: { status: "undelivered", attempts: 3, last_attempt_ms: Date.parse("2026-10-12T10:02:00Z"), acknowledged_by_transport: false },
      [sha("b") + ":opened:song"]: { status: "acknowledged", attempts: 1, last_attempt_ms: NOW, acknowledged_by_transport: true },
      [sha("b") + ":opened:ours"]: { status: "undelivered", attempts: 3, last_attempt_ms: NOW, acknowledged_by_transport: false } } },
  });
  const p = problemsSection(input);
  assert.equal(p.monitor_events.length, 2);
  assert.equal(p.notice_changes.length, 1);
  assert.deepEqual(p.alerts, { acknowledged_by_mock: 1, undelivered: 1, abandoned: 0, waiting_unattempted: 0, pending: 0, delivery_confirmed: false }, "alert attempts outside the window are not counted");
  assert.equal(p.incident_still_open, true);
  assert.equal(p.dropped_monitor_events, 1);
});

test("markdown draft carries every required section, labels and the no-posting notice", () => {
  const { markdown, json } = buildReport(base({ evidence: "offline_replay", actions: [{ at: "2026-10-12T11:00:00Z", by: "ops-a", what: "안내 ON 후 OFF" }],
    unmeasured: ["실제 CDN 지연"], notes: "합성 리허설" }), { now: NOW });
  for (const section of ["## 기본", "## 이용 기록", "## 문제와 조치", "### 조치", "## 소스·해시·명령", "## 미측정", "## 비고"]) assert.ok(markdown.includes(section), section);
  assert.ok(markdown.includes(EVIDENCE.offline_replay));
  assert.ok(markdown.includes("자료 없음"));
  assert.ok(markdown.includes("0명이 아님"));
  assert.ok(markdown.includes("자동 게시 없음"));
  assert.ok(markdown.includes("이용자 수·활성 시간"));
  assert.equal(json.posted, false); assert.equal(json.approval_required, true);
  assert.equal(json.usage.status, "no_data");
  assert.doesNotMatch(markdown, /https?:\/\//);
});

test("monitor coverage of the window decides whether 'no events' is a measurement", () => {
  const ev = { id: sha("x"), kind: "opened", at_ms: Date.parse("2026-10-12T10:00:00Z"), issues: ["freshness_stale"] };
  const state = last => ({ events: [], incident: null, dropped_events: 0, ...(last === "absent" ? {} : { last_observed_ms: last }) });
  const cases = [
    [state(Date.parse("2026-10-13T00:00:30Z")), "covers_end", /감시 이벤트 없음\(관측한 동안/, false],
    [state(Date.parse("2026-10-12T15:00:00Z")), "stopped_in_window", /감시 마지막 관측 2026-10-12T15:00:00.000Z\(집계 기간 끝 전\)/, "감시 마지막 관측 이후의 장애 유무"],
    [state(Date.parse("2026-10-10T00:00:00Z")), "before_window", /감시가 집계 기간에 관측하지 않았다/, "장애 유무·지속 시간"],
    [state(null), "never", /마지막 관측 없음/, "장애 유무·지속 시간"],
    [state("absent"), "unknown", /마지막 관측 시각이 없어/, "감시 실행 범위"],
  ];
  for (const [monitor_state, coverage, line, unmeasured] of cases) {
    const r = buildReport(base({ monitor_state }), { now: NOW });
    assert.equal(r.json.problems.monitor_coverage, coverage);
    assert.match(r.markdown, line, coverage);
    if (unmeasured) assert.ok(r.json.unmeasured.includes(unmeasured), coverage);
    else assert.equal(r.json.unmeasured.some(u => /장애|감시/.test(u)), false);
  }
  const before = buildReport(base({ monitor_state: { ...state(Date.parse("2026-10-10T00:00:00Z")), events: [ev] } }), { now: NOW });
  assert.doesNotMatch(before.markdown, /감시 이벤트 없음/, "a monitor that did not run cannot report 'no events'");
  assert.throws(() => validateReportInput(base({ monitor_state: { ...state(1), last_observed_ms: -1 } })), /invalid_monitor_state/);
});

test("CLI writes markdown and JSON once, refuses overwrite and invalid input", async () => {
  const dir = await mkdtemp(join(tmpdir(), "pitcheezy-report-"));
  const run = promisify(execFile);
  const cli = fileURLToPath(new URL("../report-cli.mjs", import.meta.url));
  await writeFile(join(dir, "input.json"), JSON.stringify(base()));
  const first = JSON.parse((await run(process.execPath, [cli, "--input", join(dir, "input.json"), "--output-dir", dir])).stdout);
  assert.equal(first.posted, false); assert.equal(first.usage_status, "no_data");
  const md = await readFile(join(dir, first.markdown), "utf8");
  assert.match(md, /^# \[경기별 운영 기록 초안\] 경기 123/);
  await assert.rejects(run(process.execPath, [cli, "--input", join(dir, "input.json"), "--output-dir", dir]), e => e.code === 2 && /EEXIST/.test(e.stderr));
  // A lone existing .json refuses the run before the .md is written (no orphan draft).
  const other = await mkdtemp(join(tmpdir(), "pitcheezy-report-"));
  await writeFile(join(other, first.json), "{}");
  await assert.rejects(run(process.execPath, [cli, "--input", join(dir, "input.json"), "--output-dir", other]), e => e.code === 2 && /EEXIST/.test(e.stderr));
  await assert.rejects(readFile(join(other, first.markdown)), e => e.code === "ENOENT");
  await writeFile(join(dir, "bad.json"), JSON.stringify(base({ evidence: "real" })));
  await assert.rejects(run(process.execPath, [cli, "--input", join(dir, "bad.json"), "--output-dir", dir]), e => e.code === 2 && /invalid_game_or_evidence/.test(e.stderr));
});

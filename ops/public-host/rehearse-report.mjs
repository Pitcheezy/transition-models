/** Per-game report rehearsal (WS-report1): real local D1 usage summary + monitor/notice/alert artefacts -> draft. Synthetic only. */
import { readFile, writeFile, mkdtemp, mkdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import { parseArgs } from "node:util";
import { createHash, randomUUID } from "node:crypto";
import { Miniflare } from "miniflare";
import { saveMeasurement, summarizeTelemetry } from "./telemetry.mjs";
import { initialState, advanceState } from "./monitor.mjs";
import { initialAlertState, mockTransport, dispatchAlerts } from "./alerts.mjs";
import { buildReport } from "./report.mjs";
import { runReport } from "./report-cli.mjs";
const hash = value => createHash("sha256").update(value).digest("hex");
function need(value, code) { if (!value) throw new Error(code); }

async function sourceReceipt() {
  const values = {};
  for (const name of ["telemetry.mjs", "monitor.mjs", "alerts.mjs", "report.mjs", "report-cli.mjs", "rehearse-report.mjs", "migrations/0001_telemetry.sql"]) {
    values[name] = hash(await readFile(new URL(name, import.meta.url)));
  }
  return values;
}

export async function runReportRehearsal() {
  const start = performance.now();
  const report = { schema: "pitcheezy-local-report-rehearsal-v1", synthetic: true, posted: false, approval_required: true,
    environment: { node: process.version, platform: process.platform, arch: process.arch },
    source_sha256: await sourceReceipt(), cases: [], passed: false };
  let mf, dir;
  try {
    // 1. Real local D1 with the committed migration; two opt-in synthetic sessions and one feedback for game 123 on 2026-10-12.
    mf = new Miniflare({ modules: true, scriptPath: fileURLToPath(new URL("./worker.mjs", import.meta.url)),
      compatibilityDate: "2026-07-30", d1Databases: ["TELEMETRY_DB"], bindings: {} });
    await mf.ready;
    const db = await mf.getD1Database("TELEMETRY_DB");
    const sql = await readFile(new URL("./migrations/0001_telemetry.sql", import.meta.url), "utf8");
    await db.batch(sql.split(";").map(x => x.trim()).filter(Boolean).map(x => db.prepare(x)));
    const now = Date.parse("2026-10-12T12:00:00Z"); const opts = { days: 30, limit: 100 };
    for (const active of [30000, 60000]) {
      const s = { v: 1, consent: true, session_id: randomUUID(), game_pk: 123, sequence: 0, active_ms: 0 };
      await saveMeasurement(db, s, "session", now, opts);
      await saveMeasurement(db, { ...s, sequence: 1, active_ms: active }, "session", now + active, opts);
    }
    await saveMeasurement(db, { v: 1, consent: true, feedback_id: randomUUID(), game_pk: 123, rating: "helpful", reason: "none" }, "feedback", now, opts);
    const summary = await summarizeTelemetry(db, "2026-10-12", "2026-10-12", now + 120000);
    need(summary.sessions.length === 1 && summary.sessions[0].sessions === 2, "summary_rows");
    // 2. Monitor + alerts through the real state machines.
    const mconfig = { schema: "pitcheezy-host-monitor-v1", origin: "https://public-host.example.invalid", allow_loopback_http: false, timeout_ms: 5000,
      max_body_bytes: 1048576, timestamp_pointer: "/synthetic/at", timestamp_format: "rfc3339", max_age_seconds: 120, clock_skew_seconds: 30, page_sha256: null };
    let mstate = initialState(mconfig);
    const probe = (status, issues, at) => ({ schema: "pitcheezy-host-probe-v1", config_sha256: mstate.config_sha256, observed_at_ms: at, status, issues, page: {}, health: {} });
    for (const [status, issues, at] of [["available", [], now], ["failed", ["freshness_stale"], now + 60000], ["failed", ["freshness_stale"], now + 120000],
      ["available", [], now + 180000], ["available", [], now + 240000]]) mstate = advanceState(mstate, probe(status, issues, at), mconfig).state;
    need(mstate.events.length === 2, "monitor_events");
    const alerts = await dispatchAlerts(initialAlertState(), mstate, { schema: "pitcheezy-host-alerts-v1", transport: "mock",
      recipients: [{ id: "song", label: "Song side" }, { id: "ours", label: "our side" }], max_attempts: 3, remind_after_minutes: 0 }, mockTransport(), { now: now + 300000 });
    const notice = [{ schema: "pitcheezy-notice-audit-v1", id: randomUUID(), at: new Date(now + 90000).toISOString(), active: true, message_id: "data_hold",
      operator: "ops-a", reason: "synthetic drill", operator_token_prefix: "0123456789ab", revision: 1, etag_before: null, etag_after: '"a"' },
      { schema: "pitcheezy-notice-audit-v1", id: randomUUID(), at: new Date(now + 200000).toISOString(), active: false, message_id: "data_hold",
      operator: "ops-b", reason: "synthetic recovery", operator_token_prefix: "0123456789ab", revision: 2, etag_before: '"a"', etag_after: '"b"' }];
    const input = (extra = {}) => ({ schema: "pitcheezy-game-report-input-v1", game_pk: 123, evidence: "synthetic",
      window: { from: "2026-10-12T00:00:00Z", to: "2026-10-12T23:59:59Z" },
      collection: { telemetry_enabled: true, feedback_enabled: true, consent_note: "opt-in 위젯 체크, 합성 세션 2개", retain_days: 30 },
      usage_summary: summary, monitor_state: { events: mstate.events, incident: mstate.incident, dropped_events: mstate.dropped_events },
      notice_audit: notice, alert_state: alerts.state,
      actions: [{ at: new Date(now + 90000).toISOString(), by: "ops-a", what: "안내 ON(합성 리허설)" }, { at: new Date(now + 200000).toISOString(), by: "ops-b", what: "안내 OFF" }],
      sources: { host_commit: "0".repeat(40), frontend_commit: null, contract_version: "public-file-v1 draft v0", release_manifest_sha256: null },
      commands: ["node ops/public-host/rehearse-report.mjs"], unmeasured: ["실경기 지연", "실제 CDN"], notes: "합성 리허설 초안", ...extra });
    dir = await mkdtemp(join(tmpdir(), "pitcheezy-report-rehearsal-"));
    const cases = [
      ["counted", input()],
      ["zero_rows", input({ game_pk: 456 })],
      ["no_data", input({ usage_summary: null })],
      ["collection_off", input({ usage_summary: null, collection: { telemetry_enabled: false, feedback_enabled: false, consent_note: "수집 OFF", retain_days: null } })],
    ];
    for (const [expected, value] of cases) {
      const built = buildReport(value, { now: now + 400000 });
      need(built.json.usage.status === expected, "usage_" + expected);
      const caseDir = join(dir, expected);
      await mkdir(caseDir);
      await writeFile(join(caseDir, "input.json"), JSON.stringify(value));
      const result = await runReport(join(caseDir, "input.json"), caseDir, { now: now + 400000 });
      need(result.posted === false, "posted");
      const md = await readFile(join(caseDir, result.markdown), "utf8");
      need(md.includes("자동 게시 없음") && md.includes("합성 자료"), "labels");
      report.cases.push({ case: expected, usage_status: built.json.usage.status, sessions: built.json.usage.sessions, active_ms: built.json.usage.active_ms,
        monitor_events: built.json.problems.monitor_events.length, notice_changes: built.json.problems.notice_changes.length,
        alerts: built.json.problems.alerts, markdown_sha256: hash(md), markdown_bytes: Buffer.byteLength(md) });
    }
    need(report.cases[0].sessions === 2 && report.cases[0].active_ms === 90000 && report.cases[0].monitor_events === 2 && report.cases[0].notice_changes === 2, "counted_case");
    need(report.cases[1].sessions === 0 && report.cases[2].sessions === null && report.cases[3].sessions === null, "distinct_statuses");
    report.passed = true;
  } catch (error) {
    report.failure = /^[a-z_]+$/.test(error.message) ? error.message : "phase_failed";
  } finally {
    if (mf) await mf.dispose().catch(() => {});
    if (dir) await rm(dir, { recursive: true, force: true }).catch(() => {});
  }
  report.total_ms = Math.round(performance.now() - start);
  return report;
}

export async function main(args) {
  try {
    const { values } = parseArgs({ args, options: { output: { type: "string" } } });
    const report = await runReportRehearsal();
    const text = JSON.stringify(report, null, 2) + "\n";
    if (values.output) await writeFile(values.output, text, { flag: "wx", mode: 0o600 });
    process.stdout.write(text);
    return report.passed ? 0 : 1;
  } catch { process.stderr.write('{"ok":false,"code":"rehearsal_arguments_or_output_error"}\n'); return 2; }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await main(process.argv.slice(2));
}

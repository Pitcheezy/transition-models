/** Alert-path rehearsal (WS-alert1): synthetic monitor sequences through the mock transport. No network, no contacts. */
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import { parseArgs } from "node:util";
import { createHash } from "node:crypto";
import { initialState, advanceState } from "./monitor.mjs";
import { initialAlertState, mockTransport, dispatchAlerts, classifyEvent } from "./alerts.mjs";
const hash = value => createHash("sha256").update(value).digest("hex");
function need(value, code) { if (!value) throw new Error(code); }

async function sourceReceipt() {
  const values = {};
  for (const name of ["monitor.mjs", "alerts.mjs", "alerts-cli.mjs", "rehearse-alerts.mjs", "examples/alerts.example.json"]) {
    values[name] = hash(await readFile(new URL(name, import.meta.url)));
  }
  return values;
}

const CONFIG = { schema: "pitcheezy-host-alerts-v1", transport: "mock",
  recipients: [{ id: "song", label: "Song side" }, { id: "ours", label: "our side" }], max_attempts: 3, remind_after_minutes: 30 };
const MCONFIG = { schema: "pitcheezy-host-monitor-v1", origin: "https://public-host.example.invalid", allow_loopback_http: false,
  timeout_ms: 5000, max_body_bytes: 1048576, timestamp_pointer: "/synthetic/at", timestamp_format: "rfc3339",
  max_age_seconds: 120, clock_skew_seconds: 30, page_sha256: null };

/** Plays a sequence of synthetic probe outcomes through the real monitor state machine and the dispatcher. */
async function scenario(name, steps, { failBeforeSuccess = {} } = {}) {
  const base = Date.parse("2026-10-13T00:00:00Z");
  let mstate = initialState(MCONFIG);
  let astate = initialAlertState();
  const transport = mockTransport({ failBeforeSuccess });
  const timeline = [];
  let clock = base;
  for (const step of steps) {
    clock += step.advance_ms ?? 60000;
    const report = { schema: "pitcheezy-host-probe-v1", config_sha256: mstate.config_sha256, observed_at_ms: clock,
      status: step.issues.length ? "failed" : "available", issues: step.issues, page: {}, health: {} };
    const advanced = advanceState(mstate, report, MCONFIG);
    mstate = advanced.state;
    const { state, receipt } = await dispatchAlerts(astate, mstate, CONFIG, transport, { now: clock });
    astate = state;
    timeline.push({ t_min: (clock - base) / 60000, issues: step.issues, monitor_event: advanced.event?.kind ?? null,
      category: advanced.event ? classifyEvent(advanced.event) : null, acknowledged: receipt.acknowledged.length,
      failed: receipt.failed.length, suppressed: receipt.suppressed.length, reminders: receipt.reminders.length, pending: state.pending.length });
  }
  return { name, timeline, messages: transport.sent.map(m => ({ recipient: m.recipient, category: m.category, kind: m.event_kind, reminder: m.reminder, first_responder: m.first_responder })),
    final_state: { deliveries: Object.keys(astate.deliveries).length, pending: astate.pending.length } };
}

export async function runAlertRehearsal() {
  const start = performance.now();
  const report = { schema: "pitcheezy-local-alert-rehearsal-v1", synthetic: true, transport: "mock",
    delivery_confirmed: false, real_contacts: false, channel_decided: false,
    environment: { node: process.version, platform: process.platform, arch: process.arch },
    source_sha256: await sourceReceipt(), scenarios: [], passed: false };
  try {
    const stale = ["freshness_stale"]; const host = ["page_http_error", "health_http_error"]; const ok = [];
    const a = await scenario("publish_stalled_then_recovery", [
      { issues: ok }, { issues: stale }, { issues: stale }, { issues: stale }, { issues: stale, advance_ms: 31 * 60000 }, { issues: ok }, { issues: ok }, { issues: ok }]);
    need(a.messages.filter(m => m.category === "publish_stalled" && m.reminder === 0).length === 2, "a_open");
    need(a.messages.every(m => m.category !== "publish_stalled" || m.first_responder === "song"), "a_responder");
    need(a.messages.filter(m => m.reminder === 1).length === 2, "a_reminder");
    need(a.messages.filter(m => m.category === "recovered").length === 2, "a_recovered");
    need(a.timeline.reduce((n, t) => n + t.suppressed, 0) > 0, "a_suppressed");
    const b = await scenario("host_error_with_transport_retry", [
      { issues: ok }, { issues: host }, { issues: host }, { issues: host }, { issues: host }, { issues: ok }, { issues: ok }], { failBeforeSuccess: { ours: 2 } });
    need(b.messages.filter(m => m.category === "host_error").length === 2, "b_open");
    need(b.messages.find(m => m.category === "host_error").first_responder === "ours", "b_responder");
    need(b.timeline.filter(t => t.failed > 0).length === 2 && b.final_state.pending === 0, "b_retry");
    const c = await scenario("notice_then_access_gate_are_informational", [
      { issues: ok }, { issues: ["page_notice_active", "health_notice_active"] }, { issues: ["page_notice_active", "health_notice_active"] }, { issues: ok }, { issues: ok },
      { issues: ["page_access_required", "health_access_required"] }, { issues: ["page_access_required", "health_access_required"] }]);
    need(c.messages.filter(m => m.category === "notice_active").every(m => m.first_responder === "none"), "c_notice");
    need(c.messages.some(m => m.category === "access_gate"), "c_access");
    const d = await scenario("mixed_causes_go_to_both", [{ issues: ok }, { issues: [...stale, ...host] }, { issues: [...stale, ...host] }]);
    need(d.messages.length === 2 && d.messages.every(m => m.category === "unclassified" && m.first_responder === "both"), "d_both");
    const e = await scenario("permanent_transport_failure_is_recorded_not_hidden", [{ issues: ok }, { issues: stale }, { issues: stale }, { issues: stale }, { issues: stale }, { issues: stale }],
      { failBeforeSuccess: { song: 99, ours: 99 } });
    need(e.messages.length === 0 && e.final_state.pending === 0 && e.timeline.filter(t => t.failed > 0).length === 3, "e_exhausted");
    report.scenarios = [a, b, c, d, e];
    report.passed = true;
  } catch (error) {
    report.failure = /^[a-z_]+$/.test(error.message) ? error.message : "phase_failed";
  }
  report.total_ms = Math.round(performance.now() - start);
  return report;
}

export async function main(args) {
  try {
    const { values } = parseArgs({ args, options: { output: { type: "string" } } });
    const report = await runAlertRehearsal();
    const text = JSON.stringify(report, null, 2) + "\n";
    if (values.output) await writeFile(values.output, text, { flag: "wx", mode: 0o600 });
    process.stdout.write(text);
    return report.passed ? 0 : 1;
  } catch { process.stderr.write('{"ok":false,"code":"rehearsal_arguments_or_output_error"}\n'); return 2; }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await main(process.argv.slice(2));
}

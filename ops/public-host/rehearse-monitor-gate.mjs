/**
 * Local rehearsal for WS-monitor2: publish monitoring while the viewer access gate is on.
 * Ephemeral loopback Miniflare only; the monitor code stays in this process and never reaches the receipt.
 */
import { readFile, writeFile, stat } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import { parseArgs } from "node:util";
import { createRequire } from "node:module";
import { randomBytes } from "node:crypto";
import { startLocalHost, hash, boundedCleanup } from "./rehearsal/local-host.mjs";
import { probe, initialState, advanceState } from "./monitor.mjs";
import { classifyEvent, dispatchAlerts, initialAlertState, mockTransport } from "./alerts.mjs";
const require = createRequire(import.meta.url);
function need(value, code) { if (!value) throw new Error(code); }

async function sourceReceipt() {
  const files = ["worker.mjs", "gateway.mjs", "access.mjs", "notice.mjs", "monitor.mjs", "monitor-cli.mjs", "alerts.mjs",
    "rehearsal/local-host.mjs", "rehearse-monitor-gate.mjs", "package-lock.json"];
  const values = {};
  for (const name of files) values[name] = hash(await readFile(new URL(name, import.meta.url)));
  return values;
}
const summary = r => ({ status: r.status, issues: r.issues, access_session: r.access_session,
  access_gate_active: r.access_gate_active, notice_active: r.notice_active,
  freshness: r.health?.freshness?.status ?? null, page: r.page.status, health: r.health.status });

export async function runMonitorGateRehearsal() {
  const controller = new AbortController();
  const deadline = setTimeout(() => controller.abort(), 60000);
  const start = performance.now();
  let host, phase = "start", report;
  const completed = [];
  try {
    report = { schema: "pitcheezy-local-monitor-gate-rehearsal-v1", target: "ephemeral-loopback-miniflare",
      synthetic: true, real_codes: false, alerts_transport: "mock (no delivery)",
      environment: { node: process.version, platform: process.platform, arch: process.arch,
        miniflare: require("miniflare/package.json").version },
      source_sha256: await sourceReceipt(), completed_phases: completed, passed: false,
      note: "The monitor logs in through the viewer route with a dedicated code from an environment variable; the code and cookie are never recorded." };
    const viewerCode = randomBytes(12).toString("base64url"), monitorCode = randomBytes(12).toString("base64url");
    host = await startLocalHost({ signal: controller.signal, access: { sessionSeconds: 3600, codes: [viewerCode, monitorCode] } });
    const cfg = { schema: "pitcheezy-host-monitor-v1", origin: host.origin, allow_loopback_http: true, timeout_ms: 3000,
      max_body_bytes: 65536, timestamp_pointer: "/synthetic/at", timestamp_format: "rfc3339", max_age_seconds: 120,
      clock_skew_seconds: 30, page_sha256: null, access_code_env: "PZ_MONITOR_ACCESS_CODE" };
    let etag = null;
    const publish = async at => {
      const r = await host.publish("/v1/health.json", JSON.stringify({ synthetic: { at } }), etag);
      need(r.status === 200, "publish_failed"); etag = r.headers.get("ETag"); await r.arrayBuffer();
    };
    const run = (code = monitorCode, c = cfg) => probe(c, { accessCode: code });

    phase = "gate_without_monitor_code";
    await publish(new Date().toISOString());
    const { access_code_env: _ignored, ...legacy } = cfg;
    const blind = await probe(legacy);
    need(blind.issues.join() === "page_access_required,health_access_required", "blind_issues");
    report.gate_without_monitor_code = { ...summary(blind), classification: "access_gate (info): freshness not measurable" };
    completed.push(phase);

    phase = "gate_with_monitor_code_fresh";
    const fresh = await run();
    need(fresh.status === "available" && fresh.access_session === "established", "fresh_not_available");
    report.gate_with_monitor_code_fresh = summary(fresh);
    completed.push(phase);

    phase = "publication_stops";
    await publish(new Date(Date.now() - 600000).toISOString());
    let state = initialState(cfg), event = null;
    const stale = [];
    for (let i = 0; i < 2; i++) {
      const r = await run(); stale.push(summary(r));
      ({ state, event } = advanceState(state, r, cfg));
    }
    need(event?.kind === "opened" && event.issues.join() === "freshness_stale", "incident_not_opened");
    const transport = mockTransport();
    const alerts = await dispatchAlerts(initialAlertState(), state, { schema: "pitcheezy-host-alerts-v1", transport: "mock",
      recipients: [{ id: "song", label: "Song side" }, { id: "ours", label: "our side" }], max_attempts: 3, remind_after_minutes: 0 }, transport);
    need(transport.sent.length === 2 && transport.sent.every(m => m.category === "publish_stalled" && m.first_responder === "song"), "alert_category");
    report.publication_stops = { probes: stale, incident_opened_after: 2, incident_issues: event.issues,
      alert: { category: "publish_stalled", first_responder: "song", mock_acknowledged: alerts.receipt.acknowledged.length, delivery_confirmed: false } };
    completed.push(phase);

    phase = "publication_resumes";
    await publish(new Date().toISOString());
    for (let i = 0; i < 2; i++) ({ state, event } = advanceState(state, await run(), cfg));
    need(event?.kind === "recovered", "not_recovered");
    report.publication_resumes = { recovered_after: 2 };
    completed.push(phase);

    phase = "wrong_monitor_code";
    const wrong = await run(randomBytes(12).toString("base64url"));
    need(wrong.issues.join() === "access_login_denied" && wrong.page.status === "skipped", "wrong_code");
    report.wrong_monitor_code = { ...summary(wrong), classification: classifyEvent({ id: "0".repeat(64), kind: "opened", at_ms: Date.now(), issues: wrong.issues }) };
    completed.push(phase);

    phase = "notice_with_monitor_session";
    const on = await host.setNotice({ active: true, operator: "ops-a", reason: "synthetic drill", message_id: "maintenance" });
    need(on.status === 200, "notice_on"); const noticeTag = on.headers.get("ETag"); await on.arrayBuffer();
    const notice = await run();
    need(notice.notice_active === true && notice.access_session === "established", "notice_not_distinguished");
    report.notice_with_monitor_session = { ...summary(notice), classification: classifyEvent({ id: "1".repeat(64), kind: "opened", at_ms: Date.now(), issues: notice.issues }) };
    const off = await host.setNotice({ active: false, operator: "ops-a", reason: "synthetic recovery", message_id: "maintenance" }, noticeTag);
    need(off.status === 200, "notice_off"); await off.arrayBuffer();
    completed.push(phase);

    phase = "secrets_absent";
    const text = JSON.stringify(report);
    need(!text.includes(monitorCode) && !text.includes(viewerCode) && !/pz_viewer=/.test(text), "secret_in_receipt");
    completed.push(phase);
    report.passed = true;
  } catch (error) {
    report ??= { schema: "pitcheezy-local-monitor-gate-rehearsal-v1", synthetic: true, passed: false };
    if (error.cleanup) report.cleanup = error.cleanup;
    report.failure = { phase, code: controller.signal.aborted ? "deadline" : /^[a-z_/.0-9: -]+$/i.test(error.message) ? error.message : "phase_failed" };
  } finally {
    controller.abort(); clearTimeout(deadline);
    if (host) report.cleanup = await boundedCleanup(() => host.dispose());
    if (report?.cleanup && report.cleanup.status !== "complete") { report.passed = false; report.failure = { phase: "cleanup", code: report.cleanup.code }; }
  }
  report.total_ms = Math.round(performance.now() - start);
  return report;
}

export async function main(args) {
  try {
    const { values } = parseArgs({ args, options: { output: { type: "string" } } });
    if (values.output) {
      const exists = await stat(values.output).then(() => true, e => { if (e.code === "ENOENT") return false; throw e; });
      need(!exists, "output_exists");
    }
    const report = await runMonitorGateRehearsal();
    const text = JSON.stringify(report, null, 2) + "\n";
    if (values.output) await writeFile(values.output, text, { flag: "wx", mode: 0o600 });
    process.stdout.write(text);
    return report.passed ? 0 : 1;
  } catch { process.stderr.write('{"ok":false,"code":"rehearsal_arguments_or_output_error"}\n'); return 2; }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await main(process.argv.slice(2));
}

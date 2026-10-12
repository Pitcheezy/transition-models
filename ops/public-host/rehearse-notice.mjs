/** Local emergency-notice rehearsal (WS-safe1). Ephemeral loopback Miniflare only; no account, no Song files. */
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import { parseArgs } from "node:util";
import { createRequire } from "node:module";
import { startLocalHost, hash, boundedCleanup } from "./rehearsal/local-host.mjs";
import { probe } from "./monitor.mjs";
const require = createRequire(import.meta.url);
function need(value, code) { if (!value) throw new Error(code); }

async function sourceReceipt() {
  const files = ["worker.mjs", "gateway.mjs", "notice.mjs", "monitor.mjs", "telemetry.mjs",
    "rehearsal/local-host.mjs", "rehearse-notice.mjs", "package-lock.json"];
  const values = {};
  for (const name of files) values[name] = hash(await readFile(new URL(name, import.meta.url)));
  return values;
}

/** Polls a route until the notice header appears or disappears; returns elapsed ms and attempts. */
async function waitForNotice(get, route, expected, deadlineMs) {
  const start = performance.now();
  let attempts = 0;
  while (performance.now() - start < deadlineMs) {
    attempts++;
    const r = await get(route);
    await r.arrayBuffer();
    const active = r.status === 503 && r.headers.get("X-Pitcheezy-Notice") !== null;
    if (active === expected) return { elapsed_ms: Math.round((performance.now() - start) * 100) / 100, attempts };
    await new Promise(r => setTimeout(r, 25));
  }
  need(false, "switch_timeout");
}

export async function runNoticeRehearsal() {
  const controller = new AbortController();
  const deadline = setTimeout(() => controller.abort(), 60000);
  const start = performance.now();
  let host, phase = "start", report;
  const completed = [];
  try {
    report = { schema: "pitcheezy-local-notice-rehearsal-v1", target: "ephemeral-loopback-miniflare",
      synthetic: true, public_wording_approved: false, song_screen_verified: false, real_operator_tokens: false,
      environment: { node: process.version, platform: process.platform, arch: process.arch,
        miniflare: require("miniflare/package.json").version },
      source_sha256: await sourceReceipt(), completed_phases: completed, passed: false,
      note: "Switch latency is loopback and single-isolate; production propagation across isolates/colos is unmeasured." };
    host = await startLocalHost({ signal: controller.signal, notice: true });
    report.startup_ms = Math.round(performance.now() - start);
    const get = (path, init = {}) => fetch(host.origin + path, { ...init, redirect: "error",
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(5000)]), cache: "no-store" });
    const consume = async (response, status, code) => { need(response.status === status, code); const t = response.headers.get("ETag"); await response.arrayBuffer(); return t; };
    const game = "/v1/game/123.json";
    const body = JSON.stringify({ synthetic: true, synthetic_version: 1 });
    await consume(await host.publish(game, body), 200, "publish_failed");
    phase = "baseline";
    const baseline = {};
    for (const [route, init] of [["/", {}], ["/fixture.mjs", {}], [game, {}], [game, { method: "HEAD" }]]) {
      const r = await get(route, init); await r.arrayBuffer();
      baseline[(init.method || "GET") + " " + route] = r.status;
      need(r.status === 200, "baseline_" + route);
    }
    report.baseline = baseline;
    completed.push("baseline");

    phase = "switch_on";
    // Warm the per-isolate memo right before the change so the measurement includes the cache window.
    await (await get("/")).arrayBuffer();
    const t0 = performance.now();
    const turned = await host.setNotice({ active: true, operator: "rehearsal-a", reason: "synthetic drill", message_id: "maintenance" });
    const adminMs = Math.round((performance.now() - t0) * 100) / 100;
    const etag = await consume(turned, 200, "switch_on_failed");
    const latency = await waitForNotice(get, "/", true, 10000);
    report.switch_on = { admin_request_ms: adminMs, first_notice_response_after_admin_ok_ms: latency.elapsed_ms,
      polls_until_notice: latency.attempts, memo_window_ms: 2000 };
    completed.push("switch_on");

    phase = "notice_matrix";
    const matrix = {};
    const routes = [["GET", "/"], ["HEAD", "/"], ["GET", "/index.html"], ["GET", "/fixture.mjs"], ["GET", game], ["HEAD", game],
      ["GET", "/v1/health.json"], ["OPTIONS", game], ["POST", "/_telemetry/session"]];
    for (const [method, route] of routes) {
      const init = { method, ...(method === "POST" ? { body: "{}", headers: { "Content-Type": "application/json" } } : {}) };
      const r = await get(route, init);
      const text = await r.text();
      matrix[method + " " + route] = { status: r.status, content_type: r.headers.get("Content-Type"),
        cache_control: r.headers.get("Cache-Control"), notice: r.headers.get("X-Pitcheezy-Notice"),
        body_bytes: Buffer.byteLength(text), html: /<!doctype html>/i.test(text), json_error: (() => { try { return JSON.parse(text).error ?? null; } catch { return null; } })() };
      if (method === "OPTIONS") need(r.status === 204, "options_" + route);
      else { need(r.status === 503 && r.headers.get("X-Pitcheezy-Notice") === "maintenance" && r.headers.get("Cache-Control") === "no-store", "notice_" + method + "_" + route); }
      need(!text.includes("synthetic drill") && !text.includes("rehearsal-a"), "reason_leaked");
    }
    const upload = await host.publish("/v1/health.json", JSON.stringify({ synthetic: true, synthetic_publish: { at: new Date().toISOString() } }));
    await consume(upload, 200, "upload_blocked_during_notice");
    report.notice_matrix = matrix; report.upload_during_notice = "accepted";
    const monitored = await probe({ schema: "pitcheezy-host-monitor-v1", origin: host.origin, allow_loopback_http: true,
      timeout_ms: 5000, max_body_bytes: 1048576, timestamp_pointer: "/synthetic_publish/at", timestamp_format: "rfc3339",
      max_age_seconds: 120, clock_skew_seconds: 30, page_sha256: null });
    need(monitored.status === "failed" && monitored.notice_active === true, "monitor_classification");
    report.monitor_during_notice = { status: monitored.status, notice_active: monitored.notice_active, issues: monitored.issues };
    completed.push("notice_matrix");

    phase = "switch_off";
    await (await get("/")).arrayBuffer();
    const t1 = performance.now();
    const recovered = await host.setNotice({ active: false, operator: "rehearsal-b", reason: "synthetic recovery", message_id: "maintenance" }, etag);
    const offAdminMs = Math.round((performance.now() - t1) * 100) / 100;
    await consume(recovered, 200, "switch_off_failed");
    const back = await waitForNotice(get, "/", false, 10000);
    report.switch_off = { admin_request_ms: offAdminMs, first_normal_response_after_admin_ok_ms: back.elapsed_ms, polls_until_normal: back.attempts };
    const restored = await get(game);
    need(restored.status === 200 && await restored.text() === body, "data_not_restored");
    const stale = await host.setNotice({ active: true, operator: "rehearsal-a", reason: "stale retry", message_id: "maintenance" }, etag);
    await consume(stale, 412, "stale_switch_accepted");
    const view = await host.noticeState();
    need(view.status === 200, "state_read_failed");
    const parsed = await view.json();
    need(parsed.state.active === false && parsed.audit.length === 2, "audit_count");
    report.audit_entries = parsed.audit.map(a => ({ at: a.at, active: a.active, operator: a.operator, revision: a.revision, operator_token_prefix: a.operator_token_prefix }));
    completed.push("switch_off");
    report.passed = true;
  } catch (error) {
    report ??= { schema: "pitcheezy-local-notice-rehearsal-v1", synthetic: true, passed: false };
    if (error.cleanup) report.cleanup = error.cleanup;
    report.failure = { phase, code: controller.signal.aborted ? "deadline" : /^[a-z_/.0-9-]+$/i.test(error.message) ? error.message : "phase_failed" };
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
    const report = await runNoticeRehearsal();
    const text = JSON.stringify(report, null, 2) + "\n";
    if (values.output) await writeFile(values.output, text, { flag: "wx", mode: 0o600 });
    process.stdout.write(text);
    return report.passed ? 0 : 1;
  } catch { process.stderr.write('{"ok":false,"code":"rehearsal_arguments_or_output_error"}\n'); return 2; }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await main(process.argv.slice(2));
}

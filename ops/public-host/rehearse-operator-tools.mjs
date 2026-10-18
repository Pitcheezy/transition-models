/** Isolated operator drill: actual CLIs, synthetic credentials and a new loopback Worker only. */
import { Miniflare } from "miniflare";
import { spawn } from "node:child_process";
import { randomBytes } from "node:crypto";
import { mkdtemp, readFile, writeFile, lstat, realpath, rm, readdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { parseArgs } from "node:util";
import { setTimeout as delay } from "node:timers/promises";
import { plainPath } from "./monitor-cli.mjs";
import { hash, fixtureHtml, waitForReady, boundedCleanup } from "./rehearsal/local-host.mjs";
const require = createRequire(import.meta.url);
const ROOT = fileURLToPath(new URL("./", import.meta.url));
const PREFIX = "pitcheezy-operator-drill-";
const KEY = "/v1/health.json";
const need = (value, code) => { if (!value) throw new Error(code); };
const exists = path => lstat(path).then(() => true, error => { if (error.code === "ENOENT") return false; throw error; });

/** Children get only OS necessities and their own synthetic credential, never inherited account settings. */
export function childEnvironment(directory, credential = {}, environment = process.env) {
  const allowed = new Set(["PATH", "PATHEXT", "SYSTEMROOT", "WINDIR", "COMSPEC", "PROCESSOR_ARCHITECTURE", "NUMBER_OF_PROCESSORS"]);
  const result = Object.fromEntries(Object.entries(environment).filter(([key]) => allowed.has(key.toUpperCase())));
  return { ...result, TEMP: directory, TMP: directory, NO_COLOR: "1", ...credential };
}

/** Bound a child wait; a missing close event is unconfirmed, never treated as successful shutdown. */
export async function collectChild(child, { signal, timeoutMs = 25000, stopGraceMs = 5000 } = {}) {
  return new Promise((resolveResult, reject) => {
    let stdout = "", stderr = "", interrupted = false, grace;
    const stop = () => {
      if (interrupted) return;
      interrupted = true;
      try { child.kill(); } catch { /* The close event remains the evidence. */ }
      grace = setTimeout(() => {
        clearTimeout(timer); signal?.removeEventListener("abort", stop);
        child.unref(); child.stdout.destroy(); child.stderr.destroy();
        reject(new Error("cli_close_unconfirmed"));
      }, stopGraceMs);
    };
    const timer = setTimeout(stop, timeoutMs);
    signal?.addEventListener("abort", stop, { once: true });
    const finish = () => { clearTimeout(timer); clearTimeout(grace); signal?.removeEventListener("abort", stop); };
    child.stdout.on("data", data => { if (interrupted) return; stdout += data.toString(); if (Buffer.byteLength(stdout) > 262144) stop(); });
    child.stderr.on("data", data => { if (interrupted) return; stderr += data.toString(); if (Buffer.byteLength(stderr) > 262144) stop(); });
    child.once("error", () => {
      if (!child.pid) { finish(); reject(new Error("cli_start_failed")); }
      else stop();
    });
    child.once("close", (code, childSignal) => { finish();
      if (interrupted || childSignal) reject(new Error("cli_interrupted"));
      else resolveResult({ code, stdout, stderr }); });
    if (signal?.aborted) stop();
  });
}
/** Delete only the exact directory created by this invocation, after its runtime and children close. */
export async function removeOwnedDirectory(directory, parent, expectedName) {
  const root = await realpath(parent), target = await realpath(directory), entry = await lstat(directory);
  need(!entry.isSymbolicLink() && entry.isDirectory() && dirname(target) === root &&
    basename(target) === expectedName && expectedName.startsWith(PREFIX) && expectedName.length > PREFIX.length,
  "unsafe_cleanup_path");
  await rm(target, { recursive: true, force: false, maxRetries: 3, retryDelay: 100 });
}

async function sourceReceipt() {
  const result = {};
  for (const name of ["worker.mjs", "gateway.mjs", "access.mjs", "notice.mjs", "telemetry.mjs",
    "publisher.mjs", "publisher-cli.mjs", "notice-client.mjs", "notice-cli.mjs", "monitor.mjs",
    "monitor-cli.mjs", "monitor-runner.mjs", "monitor-runner-cli.mjs", "alerts.mjs", "alerts-cli.mjs",
    "owned-files.mjs", "rehearsal/local-host.mjs", "rehearse-operator-tools.mjs", "package-lock.json"])
    result[name] = hash(await readFile(join(ROOT, name)));
  return result;
}

/** onPhase is an in-process test hook; the command accepts no target, port, credential or runtime options. */
export async function runOperatorToolsRehearsal({ onPhase = () => {} } = {}) {
  const started = performance.now(), controller = new AbortController();
  const deadline = setTimeout(() => controller.abort(), 60000);
  const report = { schema: "pitcheezy-operator-tools-rehearsal-v1", synthetic: true,
    target: "new-loopback-miniflare", passed: false, cloud_verified: false, song_publisher_verified: false,
    actual_ctrl_c_verified: false, delivery_confirmed: false, http_requests: null,
    http_request_budget_verified: false, expiry_evidence: "past-expiry configuration after local restart; live deadline crossing unmeasured",
    limits: { overall_request_window_ms: 60000, child_process_ms: 25000, synthetic_payload_bytes: 2048 },
    environment: { node: process.version, platform: process.platform, arch: process.arch,
      miniflare: require("miniflare/package.json").version },
    completed_phases: [], cli_invocations: [], cleanup: { runtimes: [], children: "not_started", temporary_storage: "not_created" } };
  let directory, parent, mf, origin, phase = "startup", fileNumber = 0, safeToRemove = true;
  const children = new Set(), forbidden = [], inputs = [];
  const publisherToken = randomBytes(32).toString("base64url"), noticeToken = randomBytes(32).toString("base64url");
  const accessCode = randomBytes(12).toString("base64url"), sessionSecret = randomBytes(32).toString("base64url");
  forbidden.push(publisherToken, noticeToken, accessCode, sessionSecret);
  const mark = name => { report.completed_phases.push(name); onPhase(name); };
  const privateOutput = value => !forbidden.some(secret => secret && value.includes(secret)) && !value.includes("pz_viewer=");
  const writeInput = async (name, value) => {
    const path = join(directory, `${++fileNumber}-${name}.json`), text = JSON.stringify(value);
    await writeFile(path, text, { flag: "wx", mode: 0o600 }); inputs.push([path, hash(text)]); return path;
  };
  const stopRuntime = async () => {
    if (!mf) return;
    const current = mf; mf = null;
    const result = await boundedCleanup(() => current.dispose()); report.cleanup.runtimes.push(result);
    if (result.status !== "complete") { safeToRemove = false; throw new Error("runtime_cleanup_incomplete"); }
  };
  const startRuntime = async expired => {
    controller.signal.throwIfAborted();
    need(!mf && safeToRemove, "runtime_still_running");
    mf = new Miniflare({ host: "127.0.0.1", port: 0, modules: true, modulesRoot: ROOT,
      scriptPath: join(ROOT, "worker.mjs"), compatibilityDate: "2026-07-30",
      r2Buckets: { PUBLISH_BUCKET: "operator-drill-r2" }, r2Persist: join(directory, "r2"),
      ratelimits: { PUBLISH_LIMITER: { namespace_id: "1002", simple: { limit: 60, period: 60 } } },
      bindings: { DATA_READ_ENABLED: "true", UPLOAD_ENABLED: "true", TELEMETRY_ENABLED: "false", FEEDBACK_ENABLED: "false",
        PUBLISH_TOKEN_SHA256: hash(publisherToken), PUBLISH_KEY_SCOPE: KEY.slice(1),
        PUBLISH_EXPIRES_AT: expired ? "2001-01-01T00:00:00.000Z" : new Date(Date.now() + 120000).toISOString(),
        NOTICE_TOKEN_SHA256: hash(noticeToken), ACCESS_GATE_ENABLED: "true", ACCESS_CODE_SHA256: hash(accessCode),
        ACCESS_SESSION_SECRET: sessionSecret, ACCESS_SESSION_SECONDS: "3600" },
      serviceBindings: { ASSETS: () => new Response(fixtureHtml, { headers: { "Content-Type": "text/html; charset=utf-8" } }) } });
    origin = (await waitForReady(mf.ready, controller.signal)).origin;
    const url = new URL(origin); need(url.protocol === "http:" && url.hostname === "127.0.0.1", "loopback_required");
    forbidden.push(origin);
  };
  const cli = async (kind, args, credential = {}) => {
    controller.signal.throwIfAborted();
    const script = { publisher: "publisher-cli.mjs", notice: "notice-cli.mjs", monitor: "monitor-runner-cli.mjs" }[kind];
    need(script, "invalid_cli");
    const child = spawn(process.execPath, [join(ROOT, script), ...args], {
      cwd: directory, env: childEnvironment(directory, credential), shell: false, windowsHide: true, stdio: ["ignore", "pipe", "pipe"] });
    children.add(child); child.once("close", () => children.delete(child));
    const result = await collectChild(child, { signal: controller.signal });
    need(privateOutput(result.stdout + result.stderr), "cli_private_output");
    need(result.stderr === "", "cli_stderr");
    let receipt;
    try { receipt = kind === "monitor" ? JSON.parse(result.stdout.trim().split("\n").at(-1)) : JSON.parse(result.stdout); }
    catch { throw new Error("cli_invalid_output"); }
    report.cli_invocations.push({ tool: kind, exit_code: result.code,
      ...(kind === "monitor" ? { mode: receipt.mode, attempts: receipt.attempts, available: receipt.available,
        failed: receipt.failed, mock_messages: receipt.mock_messages, stop_reason: receipt.stop_reason } : { outcome: receipt.outcome }) });
    return { ...result, receipt };
  };
  const request = async (path, init = {}) => {
    need(path.startsWith("/") && !path.startsWith("//"), "local_path_required");
    const response = await fetch(origin + path, { ...init, redirect: "manual",
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(5000)]) });
    return { status: response.status, headers: response.headers, text: await response.text() };
  };
  const login = async () => {
    const result = await request("/_access/v1/session", { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code: accessCode }) });
    need(result.status === 200, "viewer_login_failed"); const cookie = result.headers.get("Set-Cookie")?.split(";", 1)[0];
    need(cookie?.startsWith("pz_viewer="), "viewer_cookie_missing"); forbidden.push(cookie); return cookie;
  };
  const payload = version => ({ synthetic: true, synthetic_version: version, at: new Date().toISOString() });
  const uploadPlan = async (method, condition = null, value = null, path = KEY) => {
    const source = value === null ? null : await writeInput("payload", value);
    if (source) need((await lstat(source)).size <= 2048, "synthetic_payload_too_large");
    return writeInput("publish-plan", { schema: "pitcheezy-upload-plan-v1", origin, allow_loopback_http: true,
      method, path, condition, source_file: source ? basename(source) : null, sha256: source ? hash(await readFile(source)) : null });
  };
  const publish = async (method, condition = null, value = null, path = KEY) => cli("publisher",
    ["--plan", await uploadPlan(method, condition, value, path), "--execute"], { PITCHEEZY_PUBLISH_TOKEN: publisherToken });
  const noticePlan = (method, condition = null, active = null) => writeInput("notice-plan", {
    schema: "pitcheezy-notice-plan-v1", origin, allow_loopback_http: true, method, condition,
    change: active === null ? null : { active, operator: "synthetic-operator", reason: "isolated synthetic drill", message_id: "maintenance" } });
  const inspectNotice = async () => {
    const snapshot = join(directory, `${++fileNumber}-notice-snapshot.json`);
    const result = await cli("notice", ["--plan", await noticePlan("GET"), "--execute", "--snapshot", snapshot], { PITCHEEZY_NOTICE_TOKEN: noticeToken });
    need(result.code === 0 && result.receipt.outcome === "observed", "notice_inspect_failed");
    return JSON.parse(await readFile(snapshot, "utf8"));
  };
  const noticeChange = async (condition, active) => {
    const result = await cli("notice", ["--plan", await noticePlan("PUT", condition, active), "--execute"], { PITCHEEZY_NOTICE_TOKEN: noticeToken });
    need(result.code === 0 && result.receipt.outcome === "applied", "notice_change_failed");
  };
  try {
    report.source_sha256 = await sourceReceipt();
    parent = await realpath(tmpdir()); directory = await mkdtemp(join(parent, PREFIX)); forbidden.push(directory);
    report.cleanup.temporary_storage = "created";
    await startRuntime(false); mark("startup");
    const config = await writeInput("monitor-config", { schema: "pitcheezy-host-monitor-v1", origin,
      allow_loopback_http: true, timeout_ms: 2000, max_body_bytes: 65536, timestamp_pointer: "/at", timestamp_format: "rfc3339",
      max_age_seconds: 120, clock_skew_seconds: 30, page_sha256: hash(fixtureHtml), access_code_env: "PZ_OPERATOR_DRILL_CODE" });
    const alertConfig = await writeInput("alert-config", { schema: "pitcheezy-host-alerts-v1", transport: "mock",
      recipients: [{ id: "song", label: "Synthetic Song" }, { id: "ours", label: "Synthetic ours" }], max_attempts: 3, remind_after_minutes: 0 });
    const state = join(directory, "monitor-state.json"), alertState = join(directory, "alert-state.json");
    const monitor = async (runs, execute = true) => cli("monitor", ["--config", config, "--state", state,
      "--mock-alert-config", alertConfig, "--mock-alert-state", alertState,
      ...(execute ? ["--execute", "--max-runs", String(runs), "--max-duration-ms", "10000", "--interval-ms", "1000"] : [])],
    execute ? { PZ_OPERATOR_DRILL_CODE: accessCode } : {});
    const stateValue = async () => JSON.parse(await readFile(state, "utf8"));
    phase = "dry_runs";
    const dryPublisher = await cli("publisher", ["--plan", await uploadPlan("PUT", { if_none_match: "*" }, payload(1))]);
    const absentSnapshot = join(directory, "dry-snapshot.json");
    const dryNotice = await cli("notice", ["--plan", await noticePlan("GET"), "--snapshot", absentSnapshot]);
    const dryMonitor = await monitor(1, false);
    need(dryPublisher.code === 0 && dryPublisher.receipt.outcome === "dry_run" && dryNotice.code === 0 &&
      dryNotice.receipt.outcome === "dry_run" && dryMonitor.code === 0 && dryMonitor.receipt.mode === "dry_run", "dry_run_failed");
    need(!await exists(state) && !await exists(alertState) && !await exists(absentSnapshot) &&
      !(await readdir(directory)).some(name => name.endsWith(".lock")), "dry_run_wrote_state");
    mark(phase);
    phase = "gate_and_publish";
    need((await request("/")).status === 401 && (await request(KEY)).status === 401, "gate_not_required");
    const created = await publish("PUT", { if_none_match: "*" }, payload(1));
    need(created.code === 0 && created.receipt.outcome === "stored", "create_failed");
    const head = await publish("HEAD"); need(head.code === 0 && head.receipt.outcome === "observed", "head_failed");
    const updatedBody = payload(2);
    const update = await publish("PUT", { if_match: created.receipt.etag }, updatedBody);
    need(update.code === 0 && update.receipt.outcome === "stored" && update.receipt.etag !== created.receipt.etag, "update_failed");
    const conflict = await publish("PUT", { if_match: created.receipt.etag }, payload(3));
    need(conflict.code === 1 && conflict.receipt.outcome === "conflict", "conflict_not_rejected");
    const deleted = await publish("DELETE", { if_match: update.receipt.etag });
    need(deleted.code === 0 && deleted.receipt.outcome === "stored" && deleted.receipt.deleted === true, "withdraw_failed");
    const tombstone = await publish("HEAD");
    need(tombstone.code === 0 && tombstone.receipt.deleted === true && tombstone.receipt.etag === deleted.receipt.etag, "tombstone_head_failed");
    const viewerCookie = await login();
    need((await request(KEY, { headers: { Cookie: viewerCookie } })).status === 404 &&
      (await request(KEY, { method: "HEAD", headers: { Cookie: viewerCookie } })).status === 404, "withdraw_not_hidden");
    const restored = await publish("PUT", { if_match: tombstone.receipt.etag }, updatedBody);
    need(restored.code === 0 && restored.receipt.outcome === "stored" && restored.receipt.etag !== update.receipt.etag, "restore_failed");
    const restoredRead = await request(KEY, { headers: { Cookie: viewerCookie } });
    need(restoredRead.status === 200 && restoredRead.text === JSON.stringify(updatedBody), "restored_bytes_mismatch");
    report.withdraw_restore_verified = true;
    const healthy = await monitor(1); need(healthy.code === 0 && healthy.receipt.available === 1, "healthy_monitor_failed");
    need((await stateValue()).report.access_session === "established", "monitor_not_authenticated"); mark(phase);
    phase = "stale_and_recovery";
    const stale = await publish("PUT", { if_match: restored.receipt.etag }, { ...payload(4), at: new Date(Date.now() - 600000).toISOString() });
    need(stale.code === 0, "stale_publish_failed");
    const failed = await monitor(2); const opened = await stateValue();
    need(failed.code === 1 && failed.receipt.failed === 2 && failed.receipt.mock_messages === 2 &&
      opened.state.events.at(-1)?.kind === "opened" && opened.report.issues.join() === "freshness_stale", "stale_incident_failed");
    const finalBody = payload(5);
    const fresh = await publish("PUT", { if_match: stale.receipt.etag }, finalBody); need(fresh.code === 0, "fresh_publish_failed");
    const recovered = await monitor(2); const history = await stateValue();
    need(recovered.code === 1 && recovered.receipt.available === 2 && recovered.receipt.mock_messages === 2 &&
      history.state.incident === null && history.state.events.map(x => x.kind).join() === "opened,recovered", "recovery_history_failed");
    report.monitor_history = history.state.events.map(x => x.kind); report.recovery_exit_code = recovered.code; mark(phase);
    phase = "notice_on_off";
    const initial = await inspectNotice(); need(initial.observed.active === false, "notice_initial_state");
    await noticeChange(initial.condition, true);
    // The production notice memo is two seconds; wait inside the global abortable budget before probing.
    await delay(2100, null, { signal: controller.signal });
    const noticeMonitor = await monitor(2); const noticeState = await stateValue();
    need(noticeMonitor.code === 1 && noticeState.report.notice_active === true && noticeState.report.access_session === "established", "notice_not_classified");
    const active = await inspectNotice(); need(active.observed.active === true, "notice_not_active");
    await noticeChange(active.condition, false);
    await delay(2100, null, { signal: controller.signal });
    const noticeRecovered = await monitor(2); const finalNotice = await inspectNotice();
    need(noticeRecovered.code === 1 && noticeRecovered.receipt.available === 2 && finalNotice.observed.active === false &&
      (await stateValue()).state.incident === null, "notice_recovery_failed"); mark(phase);
    phase = "out_of_scope";
    let cookie = await login();
    const before = await request(KEY, { headers: { Cookie: cookie } });
    need(before.status === 200 && before.text === JSON.stringify(finalBody), "final_bytes_mismatch");
    for (const method of ["PUT", "DELETE", "HEAD"]) {
      const result = await publish(method, method === "PUT" ? { if_none_match: "*" } : method === "DELETE" ? { if_match: fresh.receipt.etag } : null,
        method === "PUT" ? payload(6) : null, "/v1/game/123.json");
      need(result.code === 1 && result.receipt.outcome === "rejected" && result.receipt.attempts[0]?.status === 403, "scope_not_rejected");
    }
    const after = await request(KEY, { headers: { Cookie: cookie } });
    need(after.text === before.text && after.headers.get("ETag") === before.headers.get("ETag") &&
      (await request("/v1/game/123.json", { headers: { Cookie: cookie } })).status === 404, "scope_changed_state"); mark(phase);
    phase = "expired_restart";
    await stopRuntime(); await startRuntime(true); cookie = await login();
    const expiredBefore = await request(KEY, { headers: { Cookie: cookie } });
    need(expiredBefore.status === 200 && expiredBefore.text === before.text && expiredBefore.headers.get("ETag") === before.headers.get("ETag"), "restart_changed_state");
    for (const method of ["PUT", "DELETE", "HEAD"]) {
      const result = await publish(method, method === "HEAD" ? null : { if_match: fresh.receipt.etag }, method === "PUT" ? payload(7) : null);
      need(result.code === 1 && result.receipt.outcome === "rejected" && result.receipt.attempts[0]?.status === 403, "expiry_not_rejected");
    }
    const expiredAfter = await request(KEY, { headers: { Cookie: cookie } });
    need(expiredAfter.text === expiredBefore.text && expiredAfter.headers.get("ETag") === expiredBefore.headers.get("ETag"), "expiry_changed_state");
    need((await inspectNotice()).observed.active === false, "expiry_changed_notice"); mark(phase);
    phase = "preservation_and_redaction";
    for (const [path, digest] of inputs) need(hash(await readFile(path)) === digest, "input_changed");
    for (const name of await readdir(directory)) {
      if (name.endsWith(".json")) {
        const text = await readFile(join(directory, name), "utf8");
        need(![publisherToken, noticeToken, accessCode, sessionSecret].some(secret => text.includes(secret)) &&
          !text.includes("pz_viewer="), "secret_saved_to_file");
      }
    }
    need(!(await readdir(directory)).some(name => name.endsWith(".lock")), "lock_remaining");
    need(privateOutput(JSON.stringify(report)), "receipt_private_output");
    report.input_files_preserved = inputs.length; report.secrets_absent_from_cli_and_receipt = true; mark(phase);
    report.passed = true;
  } catch {
    report.failure = { phase, code: controller.signal.aborted ? "deadline" : "phase_failed" };
  } finally {
    controller.abort(); clearTimeout(deadline);
    const childCleanup = await boundedCleanup(async () => {
      await Promise.all([...children].map(child => new Promise(resolveChild => {
        child.once("close", resolveChild);
        try { child.kill(); } catch { /* Cleanup stays unconfirmed until close. */ }
      })));
    });
    report.cleanup.children = childCleanup.status;
    if (childCleanup.status !== "complete") safeToRemove = false;
    try { await stopRuntime(); } catch { safeToRemove = false; }
    if (directory && safeToRemove) {
      try { await removeOwnedDirectory(directory, parent, basename(directory)); report.cleanup.temporary_storage = "removed"; }
      catch { report.cleanup.temporary_storage = "retained"; safeToRemove = false; }
    } else if (directory) report.cleanup.temporary_storage = "retained";
    if (!safeToRemove) { report.passed = false; report.failure = { phase: "cleanup", code: "cleanup_unconfirmed" }; }
  }
  report.elapsed_ms = Math.round(performance.now() - started);
  report.cli_invocation_count = report.cli_invocations.length;
  return report;
}

/** Preflight a new receipt path before starting any process or runtime. */
export async function main(args, { run = runOperatorToolsRehearsal, output = text => process.stdout.write(text),
  errorOutput = text => process.stderr.write(text) } = {}) {
  try {
    const { values } = parseArgs({ args, strict: true, allowPositionals: false, options: { output: { type: "string" } } });
    let destination;
    if (values.output !== undefined) {
      need(values.output.length > 0, "output_required"); destination = await plainPath(values.output);
      need(!await exists(destination) && (await lstat(dirname(destination))).isDirectory(), "output_must_be_new");
    }
    const report = await run(); const text = JSON.stringify(report, null, 2) + "\n";
    if (destination) await writeFile(destination, text, { flag: "wx", mode: 0o600 });
    output(text); return report.passed ? 0 : 1;
  } catch { errorOutput('{"ok":false,"code":"operator_rehearsal_arguments_or_output_error"}\n'); return 2; }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) process.exitCode = await main(process.argv.slice(2));

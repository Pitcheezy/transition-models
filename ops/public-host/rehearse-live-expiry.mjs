/** One fresh loopback Worker, one synthetic key, measured HTTP and a real clock deadline. */
import { Miniflare } from "miniflare";
import { randomBytes } from "node:crypto";
import { mkdtemp, readFile, writeFile, lstat, realpath } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { parseArgs } from "node:util";
import { setTimeout as delay } from "node:timers/promises";
import { plainPath } from "./monitor-cli.mjs";
import { removeOwnedDirectory } from "./rehearse-operator-tools.mjs";
import { hash, fixtureHtml, waitForReady, boundedCleanup } from "./rehearsal/local-host.mjs";
const require = createRequire(import.meta.url);
const ROOT = fileURLToPath(new URL("./", import.meta.url));
const KEY = "/v1/game/123.json", REQUEST_LIMIT = 18, BODY_LIMIT = 2048;
const REQUEST_WINDOW = 100000, TOTAL_WINDOW = 120000, EXPIRY_DELAY = 20000;
const need = (value, code) => { if (!value) throw new Error(code); };
const exists = path => lstat(path).then(() => true, error => { if (error.code === "ENOENT") return false; throw error; });

/** Every attempted HTTP request counts, including login, reads and rejected requests. No retries. */
export function createMeasuredRequests(transport, { elapsed, rows = [] } = {}) {
  let stopped = false;
  return async (label, path, init, expected) => {
    need(!stopped, "request_sequence_stopped");
    try {
      need(rows.length < REQUEST_LIMIT, "request_budget_exhausted");
      need(elapsed() < REQUEST_WINDOW, "request_deadline");
      const bodyBytes = init.body === undefined ? 0 : Buffer.byteLength(init.body);
      need(bodyBytes <= BODY_LIMIT, "body_budget_exhausted");
      const row = { label, method: init.method || "GET", sent_ms: Math.round(elapsed()), body_bytes: bodyBytes, status: null };
      rows.push(row);
      const result = await transport(path, init);
      row.status = result.status; row.finished_ms = Math.round(elapsed());
      need(result.status === expected, "unexpected_http_status");
      return result;
    } catch { stopped = true; throw new Error("measured_request_failed"); }
  };
}

/** No target, credential or clock override. The command never uses a saved environment or account. */
export async function runLiveExpiryRehearsal() {
  const started = performance.now(), elapsed = () => performance.now() - started;
  const controller = new AbortController(), timer = setTimeout(() => controller.abort(), REQUEST_WINDOW);
  const token = randomBytes(32).toString("base64url"), code = randomBytes(12).toString("base64url");
  const secret = randomBytes(32).toString("base64url"), forbidden = [token, code, secret];
  const report = { schema: "pitcheezy-live-expiry-rehearsal-v1", synthetic: true, passed: false,
    target: "new-loopback-miniflare", runtime_count: 0, clock_mocked: false, runtime_restarted: false,
    cloud_verified: false, song_publisher_verified: false, credential_revocation_verified: false,
    delivery_confirmed: false, single_data_key: true, access_gate_enabled: true,
    telemetry_enabled: false, feedback_enabled: false,
    limits: { http_requests: REQUEST_LIMIT, body_bytes: BODY_LIMIT, request_window_ms: REQUEST_WINDOW, total_ms: TOTAL_WINDOW },
    environment: { node: process.version, platform: process.platform, arch: process.arch,
      miniflare: require("miniflare/package.json").version },
    requests: [], completed_phases: [], cleanup: { runtime: "not_started", temporary_storage: "not_created" } };
  let directory, parent, mf, origin, phase = "startup", cookie;
  const send = createMeasuredRequests(async (path, init) => {
    need(path.startsWith("/") && !path.startsWith("//"), "local_path_required");
    const response = await fetch(origin + path, { ...init, redirect: "manual",
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(5000)]) });
    return { status: response.status, headers: response.headers, text: await response.text() };
  }, { elapsed, rows: report.requests });
  const mark = value => { report.completed_phases.push(value); };
  const publicRead = (label, expected = 200, method = "GET") => send(label, KEY, { method, headers: { Cookie: cookie } }, expected);
  const publish = (label, method, expected, body, etag) => send(label, "/_publish" + KEY, {
    method, ...(body === undefined ? {} : { body }), headers: { Authorization: "Bearer " + token,
      ...(body === undefined ? {} : { "Content-Type": "application/json", "X-Content-SHA256": hash(body) }),
      ...(method === "HEAD" ? {} : etag ? { "If-Match": etag } : { "If-None-Match": "*" }) },
  }, expected);
  const etagOf = value => { const etag = value.headers.get("ETag"); need(/^"[a-f0-9]{32}"$/.test(etag || ""), "etag_missing"); return etag; };
  const body1 = JSON.stringify({ synthetic: true, synthetic_version: 1 });
  const body2 = JSON.stringify({ synthetic: true, synthetic_version: 2 });
  try {
    report.source_sha256 = {};
    for (const name of ["worker.mjs", "gateway.mjs", "access.mjs", "notice.mjs", "telemetry.mjs", "monitor-cli.mjs",
      "rehearsal/local-host.mjs", "rehearse-operator-tools.mjs", "rehearse-live-expiry.mjs", "package-lock.json"])
      report.source_sha256[name] = hash(await readFile(join(ROOT, name)));
    parent = await realpath(tmpdir()); directory = await mkdtemp(join(parent, "pitcheezy-operator-drill-expiry-"));
    forbidden.push(directory); report.cleanup.temporary_storage = "created";
    const expiresAt = Date.now() + EXPIRY_DELAY;
    report.expiry_utc = new Date(expiresAt).toISOString();
    mf = new Miniflare({ host: "127.0.0.1", port: 0, modules: true, modulesRoot: ROOT,
      scriptPath: join(ROOT, "worker.mjs"), compatibilityDate: "2026-07-30",
      r2Buckets: { PUBLISH_BUCKET: "live-expiry-r2" }, r2Persist: join(directory, "r2"),
      ratelimits: { PUBLISH_LIMITER: { namespace_id: "1002", simple: { limit: 60, period: 60 } } },
      bindings: { DATA_READ_ENABLED: "true", UPLOAD_ENABLED: "true", TELEMETRY_ENABLED: "false", FEEDBACK_ENABLED: "false",
        PUBLISH_TOKEN_SHA256: hash(token), PUBLISH_KEY_SCOPE: KEY.slice(1), PUBLISH_EXPIRES_AT: report.expiry_utc,
        ACCESS_GATE_ENABLED: "true", ACCESS_CODE_SHA256: hash(code), ACCESS_SESSION_SECRET: secret, ACCESS_SESSION_SECONDS: "3600" },
      serviceBindings: { ASSETS: () => new Response(fixtureHtml, { headers: { "Content-Type": "text/html; charset=utf-8" } }) } });
    report.runtime_count = 1; report.cleanup.runtime = "started";
    origin = (await waitForReady(mf.ready, controller.signal)).origin;
    need(new URL(origin).hostname === "127.0.0.1" && new URL(origin).protocol === "http:", "loopback_required");
    forbidden.push(origin);
    need(Date.now() < expiresAt - 5000, "startup_too_late"); mark("startup");
    phase = "before_expiry";
    await send("unauthenticated_read", KEY, {}, 401);
    const login = await send("viewer_login", "/_access/v1/session", { method: "POST",
      headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }) }, 200);
    cookie = login.headers.get("Set-Cookie")?.split(";", 1)[0];
    need(cookie?.startsWith("pz_viewer="), "viewer_cookie_missing"); forbidden.push(cookie);
    await publish("unused_key_head", "HEAD", 404);
    const created = await publish("create", "PUT", 200, body1);
    const head = await publish("created_head", "HEAD", 200);
    need(etagOf(head) === etagOf(created), "created_head_mismatch");
    const firstRead = await publicRead("created_read");
    need(firstRead.text === body1 && etagOf(firstRead) === etagOf(created), "created_bytes_mismatch");
    const updated = await publish("conditional_update", "PUT", 200, body2, etagOf(created));
    const updateRead = await publicRead("updated_read");
    need(updateRead.text === body2 && etagOf(updateRead) === etagOf(updated) && etagOf(updated) !== etagOf(created), "updated_bytes_mismatch");
    const withdrawn = await publish("conditional_withdraw", "DELETE", 200, undefined, etagOf(updated));
    await publicRead("withdrawn_read", 404);
    const tombstone = await publish("tombstone_head", "HEAD", 200);
    need(tombstone.headers.get("X-Publish-Deleted") === "true" && etagOf(tombstone) === etagOf(withdrawn), "tombstone_mismatch");
    const restored = await publish("conditional_restore", "PUT", 200, body2, etagOf(tombstone));
    const before = await publicRead("restored_read");
    need(before.text === body2 && etagOf(before) === etagOf(restored) && etagOf(restored) !== etagOf(updated), "restore_mismatch");
    need(Date.now() < expiresAt, "pre_expiry_sequence_late");
    report.last_pre_expiry_utc = new Date().toISOString(); report.withdraw_restore_verified = true; mark(phase);
    phase = "real_clock_wait";
    await delay(Math.max(0, expiresAt - Date.now() + 100), null, { signal: controller.signal });
    need(Date.now() >= expiresAt, "expiry_not_reached"); report.first_post_expiry_utc = new Date().toISOString(); mark(phase);
    phase = "after_expiry";
    const rejectedPut = await publish("expired_put", "PUT", 403, body1, etagOf(restored));
    const rejectedDelete = await publish("expired_delete", "DELETE", 403, undefined, etagOf(restored));
    const rejectedHead = await publish("expired_head", "HEAD", 403);
    need(JSON.parse(rejectedPut.text).error === "upload_expired" && JSON.parse(rejectedDelete.text).error === "upload_expired" &&
      rejectedHead.text === "", "expiry_reason_mismatch");
    const after = await publicRead("preserved_read"), afterHead = await publicRead("preserved_head", 200, "HEAD");
    need(after.text === before.text && etagOf(after) === etagOf(before) && etagOf(afterHead) === etagOf(before), "expiry_changed_state");
    report.payload_sha256_before = hash(before.text); report.payload_sha256_after = hash(after.text);
    report.bytes_and_etag_preserved = true; report.live_deadline_crossing_verified = true; mark(phase);
    need(report.requests.length === REQUEST_LIMIT, "unexpected_request_count");
    need(!forbidden.some(value => JSON.stringify(report).includes(value)) && !JSON.stringify(report).includes("pz_viewer="), "receipt_private_output");
    report.passed = true;
  } catch {
    report.failure = { phase, code: controller.signal.aborted ? "request_deadline" : "phase_failed" };
  } finally {
    controller.abort(); clearTimeout(timer);
    const cleanup = mf ? await boundedCleanup(() => mf.dispose()) : { status: "not_started" };
    report.cleanup.runtime = cleanup.status;
    if (directory && ["complete", "not_started"].includes(cleanup.status)) {
      try { await removeOwnedDirectory(directory, parent, basename(directory)); report.cleanup.temporary_storage = "removed"; }
      catch { report.cleanup.temporary_storage = "retained"; }
    } else if (directory) report.cleanup.temporary_storage = "retained";
    if (cleanup.status !== "complete" || report.cleanup.temporary_storage !== "removed") {
      report.passed = false; report.failure = { phase: "cleanup", code: "cleanup_unconfirmed" };
    }
  }
  report.elapsed_ms = Math.round(elapsed()); report.http_requests = report.requests.length;
  report.maximum_body_bytes = Math.max(0, ...report.requests.map(row => row.body_bytes));
  report.request_budget_verified = report.passed && report.http_requests <= REQUEST_LIMIT && report.maximum_body_bytes <= BODY_LIMIT;
  report.total_budget_verified = report.elapsed_ms <= TOTAL_WINDOW;
  if (!report.total_budget_verified) { report.passed = false; report.failure = { phase: "overall", code: "total_deadline" }; }
  return report;
}

/** Destination preflight precedes all runtime work; receipts never overwrite an existing file. */
export async function main(args, { run = runLiveExpiryRehearsal, output = text => process.stdout.write(text),
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
  } catch { errorOutput('{"ok":false,"code":"live_expiry_arguments_or_output_error"}\n'); return 2; }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) process.exitCode = await main(process.argv.slice(2));
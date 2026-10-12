/** Isolated local persistence rehearsal; no account, deployment or external target. */
import { Miniflare } from "miniflare";
import { randomBytes, randomUUID } from "node:crypto";
import { mkdtemp, readFile, writeFile, realpath, lstat, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { createRequire } from "node:module";
import { parseArgs } from "node:util";
import { saveMeasurement } from "./telemetry.mjs";
import { transmit } from "./publisher.mjs";
import { hash, waitForReady, boundedCleanup } from "./rehearsal/local-host.mjs";
const require = createRequire(import.meta.url);
const need = (value, code) => { if (!value) throw new Error(code); };
const DAY = 86400000;
const PREFIX = "pitcheezy-lifecycle-";
const uiOrigin = "https://ui.example.test";
const game = "/v1/game/123.json", hidden = "/v1/game/124.json";
const body = '{"synthetic":true,"version":1}';
const nextBody = '{"synthetic":true,"version":2}';

/** Only the caller's exact, freshly-created direct temp child may be removed. */
export async function removeOwnedSandbox(directory, parent, expectedName) {
  const root = await realpath(parent);
  const entry = await lstat(directory);
  const target = await realpath(directory);
  need(!entry.isSymbolicLink() && entry.isDirectory() &&
    dirname(target) === root && basename(target) === expectedName &&
    expectedName.startsWith(PREFIX) && expectedName.length > PREFIX.length, "unsafe_cleanup_path");
  await rm(target, { recursive: true, force: false, maxRetries: 3, retryDelay: 100 });
}
async function sourceReceipt() {
  const result = {};
  for (const name of ["worker.mjs", "gateway.mjs", "telemetry.mjs", "publisher.mjs",
    "rehearsal/local-host.mjs", "rehearse-lifecycle.mjs", "migrations/0001_telemetry.sql", "package-lock.json"]) {
    result[name] = hash(await readFile(new URL(name, import.meta.url)));
  }
  return result;
}
export async function runLifecycleRehearsal() {
  const report = { schema: "pitcheezy-local-lifecycle-v1", synthetic: true,
    target: "new-local-persistent-miniflare", passed: false,
    public_deployment_verified: false, crash_recovery_verified: false,
    cloud_backup_restore_verified: false, production_cron_verified: false,
    environment: { node: process.version, platform: process.platform, arch: process.arch,
      miniflare: require("miniflare/package.json").version },
    source_sha256: await sourceReceipt(), completed_phases: [], shutdowns: [],
    temporary_storage: "not_created" };
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 90000);
  let directory, parent, mf, origin, phase = "start", safeToRemove = true;
  const mark = (name, evidence) => report.completed_phases.push({ name, ...evidence });
  const stop = async () => {
    if (!mf) return;
    const current = mf; mf = null;
    const cleanup = await boundedCleanup(() => current.dispose());
    report.shutdowns.push(cleanup);
    if (cleanup.status !== "complete") { safeToRemove = false; throw new Error("runtime_cleanup_incomplete"); }
  };
  const start = async (token, collect, upload) => {
    controller.signal.throwIfAborted();
    need(!mf && safeToRemove, "previous_runtime_not_closed");
    mf = new Miniflare({
      modules: true, modulesRoot: fileURLToPath(new URL("./", import.meta.url)),
      scriptPath: fileURLToPath(new URL("./worker.mjs", import.meta.url)),
      compatibilityDate: "2026-07-30", host: "127.0.0.1", port: 0,
      r2Buckets: { PUBLISH_BUCKET: "lifecycle-r2" }, r2Persist: join(directory, "r2"),
      d1Databases: { TELEMETRY_DB: "lifecycle-d1" }, d1Persist: join(directory, "d1"),
      unsafeTriggerHandlers: true, // local Miniflare only; never deployment configuration
      ratelimits: {
        PUBLISH_LIMITER: { namespace_id: "1002", simple: { limit: 60, period: 60 } },
        TELEMETRY_LIMITER: { namespace_id: "1001", simple: { limit: 60, period: 60 } },
      },
      bindings: { DATA_READ_ENABLED: "true", UPLOAD_ENABLED: String(upload),
        PUBLISH_TOKEN_SHA256: hash(token), TELEMETRY_ENABLED: String(collect), FEEDBACK_ENABLED: String(collect),
        COLLECTION_ORIGIN: uiOrigin, TELEMETRY_RETAIN_DAYS: "30",
        SESSION_WRITES_PER_DAY: "3", FEEDBACK_ROWS_PER_DAY: "2",
        TELEMETRY_RATE_SECRET: randomBytes(32).toString("base64url") },
    });
    origin = (await waitForReady(mf.ready, controller.signal)).origin;
    need(new URL(origin).hostname === "127.0.0.1" && new URL(origin).protocol === "http:", "local_target_required");
    return waitForReady(mf.getD1Database("TELEMETRY_DB"), controller.signal);
  };
  const request = async (path, init = {}) => {
    controller.signal.throwIfAborted();
    const response = await fetch(origin + path, { ...init, redirect: "error",
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(5000)]) });
    const text = await response.text();
    return { status: response.status, etag: response.headers.get("ETag"), text };
  };
  const send = (token, path, method, etag = null, text = body) => {
    controller.signal.throwIfAborted();
    const input = method === "PUT" ? Buffer.from(text) : null;
    return transmit({ schema: "pitcheezy-upload-plan-v1", origin, allow_loopback_http: true,
      path, method, condition: method === "HEAD" ? null :
        etag ? { if_match: etag } : { if_none_match: "*" },
      source_file: input ? "synthetic.json" : null, sha256: input ? hash(input) : null },
    input, token, { maxAttempts: 1, timeoutMs: 5000, totalMs: 5000,
      fetchImpl: (url, init) => fetch(url, { ...init,
        signal: AbortSignal.any([controller.signal, init.signal]) }) });
  };
  const post = (kind, value) => request("/_telemetry/" + kind, { method: "POST",
    headers: { "Content-Type": "application/json", Origin: uiOrigin, "CF-Connecting-IP": "192.0.2.1" },
    body: JSON.stringify(value) });
  const session = () => ({ v: 1, consent: true, session_id: randomUUID(),
    game_pk: 123, sequence: 0, active_ms: 0 });
  const feedback = () => ({ v: 1, consent: true, feedback_id: randomUUID(),
    game_pk: 123, rating: "helpful", reason: "none" });
  const snapshot = async db => {
    const values = await waitForReady(db.batch([
      db.prepare("SELECT * FROM usage_sessions ORDER BY session_id"),
      db.prepare("SELECT * FROM feedback ORDER BY feedback_id"),
      db.prepare("SELECT utc_day,kind,used FROM telemetry_budget ORDER BY utc_day,kind"),
    ]), controller.signal);
    return { sessions: values[0].results.length, feedback: values[1].results.length,
      records_sha256: hash(JSON.stringify([values[0].results, values[1].results])),
      budget: values[2].results };
  };
  const same = (a, b) => JSON.stringify(a) === JSON.stringify(b);
  const work = async () => {
    parent = await realpath(tmpdir());
    directory = await mkdtemp(join(parent, PREFIX));
    report.temporary_storage = "created";
    const oldToken = randomBytes(32).toString("base64url"), newToken = randomBytes(32).toString("base64url");
    let db = await start(oldToken, true, true);
    const sql = await readFile(new URL("./migrations/0001_telemetry.sql", import.meta.url), "utf8");
    await waitForReady(db.batch(sql.split(";").map(x => x.trim()).filter(Boolean).map(x => db.prepare(x))), controller.signal);
    phase = "seed";
    const first = await send(oldToken, game, "PUT");
    need(first.outcome === "stored", "seed_publish");
    const temporary = await send(oldToken, hidden, "PUT");
    need(temporary.outcome === "stored", "seed_hidden");
    const tombstone = await send(oldToken, hidden, "DELETE", temporary.etag);
    need(tombstone.outcome === "stored", "seed_tombstone");
    const s = session(), f = feedback();
    need((await post("session", s)).status === 200 && (await post("feedback", f)).status === 200, "seed_collection");
    Object.assign(s, { sequence: 1, active_ms: 500 });
    need((await post("session", s)).status === 200, "seed_session_progress");
    const now = Date.now(), today = new Date(now).toISOString().slice(0, 10);
    const expiredSession = session(), expiredFeedback = feedback();
    await waitForReady(saveMeasurement(db, expiredSession, "session", now - 2 * DAY, { days: 1, limit: 2 }), controller.signal);
    await waitForReady(saveMeasurement(db, expiredFeedback, "feedback", now - 2 * DAY, { days: 1, limit: 2 }), controller.signal);
    const seeded = await snapshot(db);
    need(seeded.sessions === 2 && seeded.feedback === 2 && seeded.budget.length === 4 &&
      seeded.budget.every(x => x.used === (x.utc_day === today && x.kind === "session" ? 2 : 1)), "seed_rows");
    mark("seed", { public_sha256: hash(body), ...seeded });
    await stop();
    phase = "restart_and_rotate";
    db = await start(newToken, true, true);
    const restored = await request(game);
    need(restored.status === 200 && restored.text === body && restored.etag === first.etag, "r2_restart");
    const stillHidden = await request(hidden);
    const hiddenMetadata = await send(newToken, hidden, "HEAD");
    need(stillHidden.status === 404 && hiddenMetadata.outcome === "observed" &&
      hiddenMetadata.deleted === true && hiddenMetadata.etag === tombstone.etag, "tombstone_restart");
    need(same(await snapshot(db), seeded), "d1_restart");
    for (const method of ["PUT", "DELETE", "HEAD"]) {
      const denied = await send(oldToken, game, method, method === "HEAD" ? null : first.etag);
      need(denied.outcome === "rejected" && denied.attempts[0].status === 401, "old_token_accepted");
    }
    need((await request(game)).text === body, "rotation_mutated_data");
    need((await post("session", s)).status === 200 && (await post("feedback", f)).status === 200, "retry_failed");
    need(same(await snapshot(db), seeded), "duplicate_consumed_budget");
    const s2 = session(), f2 = feedback();
    need((await post("session", s2)).status === 200 && (await post("feedback", f2)).status === 200, "budget_second");
    need((await post("session", session())).status === 429 && (await post("feedback", feedback())).status === 429, "budget_reset_after_restart");
    const changed = await send(newToken, game, "PUT", first.etag, nextBody);
    need(changed.outcome === "stored" && changed.etag !== first.etag, "new_token_failed");
    need((await send(newToken, game, "DELETE", first.etag)).outcome === "conflict", "stale_etag_accepted");
    mark("restart_and_rotate", { public_bytes_and_etag_preserved: true, tombstone_preserved: true,
      old_token_denied_methods: ["PUT", "DELETE", "HEAD"], duplicate_budget_unchanged: true,
      current_day_session_limit: 3, current_day_feedback_limit: 2, stale_delete_status: 412 });
    const beforeOff = await snapshot(db);
    await stop();
    phase = "collection_off_scheduled";
    db = await start(newToken, false, false);
    need(same(await snapshot(db), beforeOff), "second_d1_restart");
    need((await request(game)).text === nextBody, "second_r2_restart");
    need((await post("session", session())).status === 503 &&
      (await post("feedback", feedback())).status === 503, "collection_not_closed");
    const closed = await send(newToken, game, "PUT", changed.etag, body);
    need(closed.attempts[0].status === 503, "upload_not_closed");
    need(same(await snapshot(db), beforeOff), "disabled_changed_rows");
    need(new Date().toISOString().slice(0, 10) === today, "utc_day_changed_retry");
    const scheduled = await request("/cdn-cgi/handler/scheduled?cron=17%203%20*%20*%20*&format=json");
    need(scheduled.status === 200 && JSON.parse(scheduled.text).outcome === "ok", "scheduled_failed");
    const after = await snapshot(db);
    need(after.sessions === 2 && after.feedback === 2 && after.budget.length === 2 &&
      after.budget.every(x => x.utc_day === today && x.used === (x.kind === "session" ? 3 : 2)), "selective_cleanup_failed");
    const surviving = await waitForReady(db.batch([
      db.prepare("SELECT session_id FROM usage_sessions ORDER BY session_id"),
      db.prepare("SELECT feedback_id FROM feedback ORDER BY feedback_id"),
    ]), controller.signal);
    need(same(surviving[0].results.map(x => x.session_id), [s.session_id, s2.session_id].sort()) &&
      same(surviving[1].results.map(x => x.feedback_id), [f.feedback_id, f2.feedback_id].sort()), "wrong_surviving_rows");
    const scheduledAgain = await request("/cdn-cgi/handler/scheduled?cron=17%203%20*%20*%20*&format=json");
    need(scheduledAgain.status === 200 && same(await snapshot(db), after), "cleanup_not_idempotent");
    mark("collection_off_scheduled", { denied_session_and_feedback_status: 503, denied_upload_status: 503,
      scheduled_outcome: "ok", repeat_cleanup_unchanged: true, before: beforeOff, after });
    await stop();
    phase = "cleanup_persisted";
    db = await start(newToken, false, false);
    need(same(await snapshot(db), after), "cleanup_not_persisted");
    const final = await request(game);
    need(final.status === 200 && final.text === nextBody && final.etag === changed.etag, "final_public_data");
    need((await request(hidden)).status === 404, "final_tombstone");
    mark("cleanup_persisted", { public_sha256: hash(nextBody), ...after });
  };
  try {
    // Await the control flow itself: an outer race could resume it after cleanup.
    await work();
    report.passed = true;
  } catch {
    report.failure = { phase, code: controller.signal.aborted ? "deadline" : "phase_failed" };
  } finally {
    clearTimeout(timer);
    try { await stop(); } catch { report.passed = false; }
    if (directory) {
      if (safeToRemove) {
        try {
          await removeOwnedSandbox(directory, parent, basename(directory));
          report.temporary_storage = "removed";
        } catch { report.temporary_storage = "retained"; report.passed = false; }
      } else report.temporary_storage = "retained";
    }
  }
  return report;
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const { values } = parseArgs({ options: { output: { type: "string" } }, strict: true });
    const report = await runLifecycleRehearsal();
    const text = JSON.stringify(report, null, 2) + "\n";
    if (values.output) await writeFile(values.output, text, { encoding: "utf8", flag: "wx" });
    else process.stdout.write(text);
    process.exitCode = report.passed ? 0 : 1;
  } catch {
    process.stderr.write("lifecycle_rehearsal_failed\n");
    process.exitCode = 2;
  }
}

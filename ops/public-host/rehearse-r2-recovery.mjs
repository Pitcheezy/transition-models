/** Synthetic raw-object recovery rehearsal. No remote target, credentials or backup input. */
import { createHash, randomBytes } from "node:crypto";
import { readFile, writeFile } from "node:fs/promises";
import { createRequire } from "node:module";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { Miniflare } from "miniflare";
import { boundedCleanup } from "./rehearsal/local-host.mjs";
import { NOTICE_ROUTE, NOTICE_STATE_KEY } from "./notice.mjs";

const require = createRequire(import.meta.url);
const hash = bytes => createHash("sha256").update(bytes).digest("hex");
const need = (value, code) => { if (!value) throw new Error(code); };
const GAME = "/v1/game/123.json";
const KEY = GAME.slice(1);
const BODY = '{"synthetic":true,"synthetic_version":1}';

async function sourceHashes() {
  const names = ["rehearse-r2-recovery.mjs", "worker.mjs", "gateway.mjs", "notice.mjs",
    "telemetry.mjs", "rehearsal/local-host.mjs", "package-lock.json"];
  return Object.fromEntries(await Promise.all(names.map(async name =>
    [name, hash(await readFile(new URL(name, import.meta.url)))])));
}

/** Only creates two disposable Miniflare runtimes; no existing storage is accepted. */
export async function runR2RecoveryRehearsal() {
  const controller = new AbortController();
  const deadline = setTimeout(() => controller.abort(), 60000);
  const report = { schema: "pitcheezy-local-r2-recovery-v1", synthetic: true, passed: false,
    target: "two-ephemeral-miniflare-runtimes", public_resume_authorized: false,
    cloud_restore_verified: false, whole_bucket_restore_verified: false, crash_recovery_verified: false,
    rto_ms: null, rpo_records: null,
    environment: { node: process.version, platform: process.platform, arch: process.arch,
      miniflare: require("miniflare/package.json").version },
    source_sha256: {}, evidence: { object_restore: "selected-synthetic-bytes-and-metadata",
      notice_cache: "admin-get-invalidates-local-memo", external_recovery_evidence_required: true },
    cases: [], cleanup: [] };
  let current = null, phase = "source_hashes";
  const bounded = async (work, code, timeoutMs = 5000) => {
    controller.signal.throwIfAborted();
    let timer, abort;
    try {
      return await Promise.race([Promise.resolve().then(work), new Promise((_, reject) => {
        timer = setTimeout(() => reject(new Error(code)), timeoutMs);
        abort = () => reject(new Error("deadline"));
        controller.signal.addEventListener("abort", abort, { once: true });
      })]);
    } finally { clearTimeout(timer); controller.signal.removeEventListener("abort", abort); }
  };
  const close = async () => {
    if (!current) return true;
    const instance = current;
    current = null; // Never retry disposal concurrently after an unconfirmed shutdown.
    const cleanup = await boundedCleanup(() => instance.dispose());
    report.cleanup.push(cleanup);
    if (cleanup.status !== "complete") return false;
    return true;
  };
  const start = async enabled => {
    const publishToken = randomBytes(32).toString("base64url");
    const noticeToken = randomBytes(32).toString("base64url");
    current = new Miniflare({
      modules: true, modulesRoot: fileURLToPath(new URL("./", import.meta.url)),
      scriptPath: fileURLToPath(new URL("worker.mjs", import.meta.url)), compatibilityDate: "2026-07-30",
      host: "127.0.0.1", port: 0, r2Buckets: ["PUBLISH_BUCKET"],
      ratelimits: { PUBLISH_LIMITER: { namespace_id: "1002", simple: { limit: 60, period: 60 } } },
      bindings: { DATA_READ_ENABLED: String(enabled), UPLOAD_ENABLED: String(enabled),
        PUBLISH_TOKEN_SHA256: hash(publishToken), NOTICE_TOKEN_SHA256: hash(noticeToken) },
      serviceBindings: { ASSETS: () => new Response("<!doctype html><html>synthetic recovery fixture</html>",
        { headers: { "Content-Type": "text/html" } }) },
    });
    const mf = current;
    await bounded(() => mf.ready, "runtime_start_timeout", 20000);
    const bucket = await bounded(() => mf.getR2Bucket("PUBLISH_BUCKET"), "bucket_timeout");
    const call = (path, init = {}) => bounded(async () => {
      const response = await mf.dispatchFetch("http://localhost" + path, init);
      return { status: response.status, etag: response.headers.get("ETag"),
        notice: response.headers.get("X-Pitcheezy-Notice"), text: await response.text() };
    }, "request_timeout");
    const publish = (etag = null) => call("/_publish" + GAME, { method: "PUT", body: BODY,
      headers: { Authorization: "Bearer " + publishToken, "Content-Type": "application/json",
        "X-Content-SHA256": hash(BODY), ...(etag ? { "If-Match": etag } : { "If-None-Match": "*" }) } });
    const withdraw = etag => call("/_publish" + GAME, { method: "DELETE",
      headers: { Authorization: "Bearer " + publishToken, "If-Match": etag } });
    const notice = (active, etag = null) => call(NOTICE_ROUTE, { method: "PUT",
      headers: { Authorization: "Bearer " + noticeToken, "Content-Type": "application/json",
        ...(etag ? { "If-Match": etag } : { "If-None-Match": "*" }) },
      body: JSON.stringify({ active, operator: "synthetic-operator", reason: "local recovery drill", message_id: "data_hold" }) });
    const state = async () => {
      const r = await call(NOTICE_ROUTE, { headers: { Authorization: "Bearer " + noticeToken } });
      need(r.status === 200, "notice_read_failed");
      return JSON.parse(r.text);
    };
    const snapshot = key => bounded(async () => {
      const obj = await bucket.get(key);
      need(obj !== null, "snapshot_missing");
      return { bytes: new Uint8Array(await obj.arrayBuffer()), customMetadata: { ...obj.customMetadata },
        httpMetadata: { ...obj.httpMetadata } };
    }, "snapshot_timeout");
    const restore = (key, snap, metadata = true) => bounded(() => bucket.put(key, snap.bytes,
      metadata ? { customMetadata: snap.customMetadata, httpMetadata: snap.httpMetadata } : {}), "restore_timeout");
    return { call, publish, withdraw, notice, state, snapshot, restore,
      removeNotice: () => bounded(() => bucket.delete(NOTICE_STATE_KEY), "remove_timeout") };
  };
  const mark = (name, observed) => report.cases.push({ name, ...observed });
  try {
    report.source_sha256 = await sourceHashes();
    phase = "normal_api_restore";
    const open = await start(true);
    const original = await open.publish(); need(original.status === 200, "initial_publish_failed");
    const oldLive = await open.snapshot(KEY);
    const removed = await open.withdraw(original.etag); need(removed.status === 200, "withdraw_failed");
    const oldTombstone = await open.snapshot(KEY);
    need((await open.call(GAME)).status === 404, "withdraw_not_hidden");
    const restored = await open.publish(removed.etag);
    const stale = await open.withdraw(original.etag);
    need(restored.status === 200 && restored.etag !== original.etag && stale.status === 412, "normal_restore_condition");
    mark(phase, { new_etag: true, stale_delete_status: stale.status });

    phase = "raw_live_rollback";
    need((await open.withdraw(restored.etag)).status === 200, "second_withdraw_failed");
    await open.restore(KEY, oldLive);
    const rollback = await open.call(GAME);
    const oldDelete = await open.withdraw(original.etag);
    need(rollback.status === 200 && rollback.text === BODY && rollback.etag === original.etag && oldDelete.status === 200, "raw_live_expectation");
    mark(phase, { public_status: rollback.status, original_etag_returned: true, old_delete_status: oldDelete.status,
      withdrawn_content_returned: true });

    phase = "raw_tombstone_rollback";
    const corrected = await open.publish(oldDelete.etag); need(corrected.status === 200, "corrected_publish_failed");
    await open.restore(KEY, oldTombstone);
    const hidden = await open.call(GAME), conflict = await open.publish(corrected.etag);
    need(hidden.status === 404 && conflict.status === 412, "raw_tombstone_expectation");
    mark(phase, { public_status: hidden.status, latest_writer_status: conflict.status });

    phase = "missing_metadata";
    await open.restore(KEY, oldLive, false);
    const invalid = await open.call(GAME);
    need(invalid.status === 503 && JSON.parse(invalid.text).error === "invalid_stored_record", "missing_metadata_expectation");
    mark(phase, { public_status: invalid.status, rejected: true });
    await open.restore(KEY, oldLive);

    phase = "raw_notice_off_rollback";
    const off = await open.notice(false); need(off.status === 200, "initial_off_failed");
    const oldOff = await open.snapshot(NOTICE_STATE_KEY);
    const on = await open.notice(true, off.etag); need(on.status === 200, "notice_on_failed");
    need((await open.call("/")).status === 503 && (await open.call(GAME)).status === 503, "notice_not_blocking");
    await open.restore(NOTICE_STATE_KEY, oldOff);
    // The authenticated GET invalidates this isolate's memo. This is not a cross-colo latency measurement.
    const view = await open.state();
    const page = await open.call("/"), data = await open.call(GAME);
    need(view.state.active === false && view.audit_unavailable === false && view.audit.length === 2 &&
      page.status === 200 && data.status === 200, "raw_notice_expectation");
    mark(phase, { active: view.state.active, audit_unavailable: view.audit_unavailable,
      page_status: page.status, public_status: data.status, newer_audit_retained: view.audit.length === 2 });

    phase = "notice_key_absent";
    const again = await open.notice(true, view.state.etag); need(again.status === 200, "notice_reenable_failed");
    await open.removeNotice();
    const absent = await open.state();
    const absentPage = await open.call("/");
    need(absent.state.active === false && absent.state.revision === 0 && absentPage.status === 200, "absent_notice_expectation");
    mark(phase, { active: false, revision: 0, page_status: absentPage.status });

    phase = "normal_api_notice_reasserted";
    const finalOn = await open.notice(true); need(finalOn.status === 200, "final_notice_failed");
    const finalView = await open.state(), finalPage = await open.call("/"), finalData = await open.call(GAME);
    need(finalView.state.active === true && finalView.audit_unavailable === false && finalPage.status === 503 && finalData.status === 503, "final_notice_expectation");
    mark(phase, { active: true, audit_unavailable: false, page_status: finalPage.status, public_status: finalData.status,
      public_resume_authorized: false });
    need(await close(), "first_runtime_cleanup_failed");

    phase = "external_gates_survive_raw_restore";
    const closed = await start(false);
    await closed.restore(KEY, oldLive);
    await closed.restore(NOTICE_STATE_KEY, oldOff);
    await closed.state();
    const closedRead = await closed.call(GAME), closedWrite = await closed.publish(original.etag), asset = await closed.call("/");
    need(closedRead.status === 503 && JSON.parse(closedRead.text).error === "publication_not_enabled" &&
      closedWrite.status === 503 && JSON.parse(closedWrite.text).error === "upload_not_configured" && asset.status === 200, "external_gate_expectation");
    mark(phase, { public_status: closedRead.status, upload_status: closedWrite.status, page_status: asset.status,
      whole_site_blocked: false });

    phase = "closed_runtime_notice_reasserted";
    const closedView = await closed.state();
    need((await closed.notice(true, closedView.state.etag)).status === 200, "closed_notice_failed");
    const heldPage = await closed.call("/"), heldData = await closed.call(GAME);
    need(heldPage.status === 503 && heldData.status === 503 && heldPage.notice === "data_hold", "closed_final_notice_expectation");
    mark(phase, { active: true, page_status: heldPage.status, public_status: heldData.status, public_resume_authorized: false });
    report.passed = true;
  } catch {
    report.failure = { phase, code: controller.signal.aborted ? "deadline" : "phase_failed" };
  } finally {
    controller.abort(); clearTimeout(deadline);
    // Do not start another runtime after an unconfirmed shutdown, or claim it was disposed.
    if (current) {
      const cleanup = await boundedCleanup(() => current.dispose());
      report.cleanup.push(cleanup);
      if (cleanup.status !== "complete") report.failure = { phase: "cleanup", code: cleanup.code };
    }
    if (report.cleanup.length !== 2 || report.cleanup.some(c => c.status !== "complete")) report.passed = false;
  }
  return report;
}

export async function main(args) {
  try {
    const { values } = parseArgs({ args, options: { output: { type: "string" } }, allowPositionals: false });
    if (Object.hasOwn(values, "output") && !values.output) throw new Error("empty_output");
    const report = await runR2RecoveryRehearsal();
    const text = JSON.stringify(report, null, 2) + "\n";
    if (values.output) await writeFile(values.output, text, { flag: "wx", mode: 0o600 });
    else process.stdout.write(text);
    return report.passed ? 0 : 1;
  } catch { process.stderr.write("r2_recovery_rehearsal_failed\n"); return 2; }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) process.exitCode = await main(process.argv.slice(2));

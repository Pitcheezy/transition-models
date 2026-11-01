/** Stage3: one approved, finite HEAD6 + first-create PUT6 run. No cleanup API or automatic retry. */
import { createHash } from "node:crypto";
import { mkdir, open, lstat } from "node:fs/promises";
import { dirname, isAbsolute, relative, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { plainPath } from "./monitor-cli.mjs";
import { MAX_JSON_BYTES } from "./gateway.mjs";
import { dryRun, transmit } from "./publisher.mjs";

export const KEYS = Object.freeze([
  "/v1/setup/849843.json", "/v1/game/849843.json", "/v1/games/2026-09-30.json",
  "/v1/dates.json", "/v1/manifest.json", "/v1/health.json",
]);
const HASH = /^[a-f0-9]{64}$/;
const UUID = /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
const TOKEN = /^[A-Za-z0-9_-]{43,128}$/;
const RAY = /^[a-f0-9]{16,32}(?:-[A-Z0-9]{3,10})?$/i;
const TIMEOUT_MS = 5000, CLEANUP_RESERVE_MS = 30000, MAX_WINDOW_MS = 600000;
const cleanup = "Operator must switch upload OFF and rotate the temporary publisher digest; this runner does neither.";
const sha = bytes => createHash("sha256").update(bytes).digest("hex");
const exact = (obj, keys) => obj && typeof obj === "object" && !Array.isArray(obj) && Object.keys(obj).sort().join(",") === [...keys].sort().join(",");
export class Stage3Error extends Error { constructor(code) { super(code); this.code = code; } }
const need = (condition, code) => { if (!condition) throw new Stage3Error(code); };
const codeOf = error => error instanceof Stage3Error ? error.code : "local_io_or_execution_error";

async function readFixed(filePath, limit) {
  need(typeof filePath === "string" && isAbsolute(filePath), "absolute_input_path_required");
  const path = await plainPath(filePath);
  const info = await lstat(path);
  need(info.isFile() && info.size > 0 && info.size <= limit, "input_size_or_type_invalid");
  const file = await open(path, "r");
  try {
    const before = await file.stat();
    need(before.isFile() && before.size > 0 && before.size <= limit, "input_size_or_type_invalid");
    const bytes = Buffer.alloc(before.size + 1);
    let offset = 0;
    while (offset < bytes.length) {
      const { bytesRead } = await file.read(bytes, offset, bytes.length - offset, null);
      if (!bytesRead) break;
      offset += bytesRead;
    }
    const after = await file.stat();
    await plainPath(path);
    need(offset === before.size && before.size === after.size && before.mtimeMs === after.mtimeMs, "input_changed");
    return bytes.subarray(0, offset);
  } finally { await file.close(); }
}
function parseJson(bytes) {
  try { return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)); }
  catch { throw new Stage3Error("invalid_json"); }
}
function utc(value) {
  need(typeof value === "string" && /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d\.\d{3}Z$/.test(value), "window_utc_invalid");
  const millis = Date.parse(value);
  need(Number.isFinite(millis) && new Date(millis).toISOString() === value, "window_utc_invalid");
  return millis;
}
function windowFor(manifest, execute, now, remaining = 12) {
  if (!execute && manifest.window_start_utc === null && manifest.close_by_utc === null) return;
  const start = utc(manifest.window_start_utc), end = utc(manifest.close_by_utc);
  need(end > start && end - start <= MAX_WINDOW_MS, "window_duration_invalid");
  if (execute) {
    need(manifest.approved === true, "execution_not_approved");
    need(Number.isFinite(now) && now >= start && end - now >= remaining * TIMEOUT_MS + CLEANUP_RESERVE_MS, "window_not_active_or_insufficient");
  }
}

export async function prepareStage3(manifestPath, manifestSha256, { execute = false, now = Date.now() } = {}) {
  need(HASH.test(manifestSha256 || ""), "manifest_sha_required");
  const bytes = await readFixed(manifestPath, 65536);
  need(sha(bytes) === manifestSha256, "manifest_sha_mismatch");
  const manifest = parseJson(bytes);
  need(exact(manifest, ["schema", "run_id", "origin", "expected_deployment_version", "approved", "window_start_utc", "close_by_utc", "request_limit", "operations"]), "manifest_fields_invalid");
  need(manifest.schema === "pitcheezy-stage3-upload-run-v1" && /^[A-Za-z0-9_-]{1,64}$/.test(manifest.run_id || ""), "manifest_identity_invalid");
  need(typeof manifest.approved === "boolean" && UUID.test(manifest.expected_deployment_version || ""), "manifest_approval_or_version_invalid");
  let origin;
  try { origin = new URL(manifest.origin); } catch { throw new Stage3Error("origin_invalid"); }
  need(typeof manifest.origin === "string" && origin.protocol === "https:" && origin.origin === manifest.origin && !origin.username && !origin.password, "origin_invalid");
  need(manifest.request_limit === 12 && Array.isArray(manifest.operations) && manifest.operations.length === 12, "request_limit_invalid");
  if (execute) need(manifest.approved === true, "execution_not_approved");
  windowFor(manifest, execute, now);
  const prepared = [];
  const files = new Set();
  for (const [i, operation] of manifest.operations.entries()) {
    need(exact(operation, ["plan_file", "plan_sha256", "expected_status", "expected_outcome"]), "operation_fields_invalid");
    need(HASH.test(operation.plan_sha256 || ""), "plan_sha_invalid");
    const planBytes = await readFixed(operation.plan_file, 16384);
    const file = resolve(operation.plan_file);
    need(!files.has(file.toLowerCase()), "duplicate_plan_file");
    files.add(file.toLowerCase());
    need(sha(planBytes) === operation.plan_sha256, "plan_sha_mismatch");
    const plan = parseJson(planBytes);
    const method = i < 6 ? "HEAD" : "PUT";
    need(plan.method === method && plan.path === KEYS[i % 6], "operation_order_or_key_invalid");
    need(plan.origin === manifest.origin && plan.allow_loopback_http === false, "plan_origin_mismatch");
    need(operation.expected_status === (method === "HEAD" ? 404 : 200) && operation.expected_outcome === (method === "HEAD" ? "missing" : "stored"), "expected_result_invalid");
    let payload = null;
    if (method === "PUT") {
      need(exact(plan.condition, ["if_none_match"]) && plan.condition.if_none_match === "*", "first_create_required");
      need(typeof plan.source_file === "string" && /^[A-Za-z0-9_.\/-]+\.json$/.test(plan.source_file) && !plan.source_file.startsWith("/") && plan.source_file.split("/").every(part => part && part !== "." && part !== ".."), "source_path_invalid");
      const root = dirname(file), source = resolve(root, plan.source_file), rel = relative(root, source);
      need(rel && !rel.startsWith("..") && !isAbsolute(rel), "source_outside_plan_folder");
      payload = new Uint8Array(await readFixed(source, MAX_JSON_BYTES));
    }
    // Validates the exact publisher plan, original byte SHA, object JSON and condition before any request.
    dryRun(plan, payload);
    prepared.push({ plan, payload, expected_status: operation.expected_status, expected_outcome: operation.expected_outcome });
  }
  return { manifest, bytes, manifestSha256, prepared };
}

async function writeExclusive(path, value) {
  const handle = await open(await plainPath(path), "wx", 0o600);
  try { await handle.writeFile(Buffer.isBuffer(value) ? value : JSON.stringify(value, null, 2) + "\n", "utf8"); await handle.sync(); }
  finally { await handle.close(); }
}

export async function runStage3({ manifestPath, manifestSha256, out, execute = false, token = null },
  { fetchImpl = fetch, now = Date.now, writeRecord = writeExclusive } = {}) {
  const frozen = await prepareStage3(manifestPath, manifestSha256, { execute, now: now() });
  const { manifest, prepared } = frozen;
  if (!execute) return { schema: "pitcheezy-stage3-upload-result-v1", outcome: "dry_run", prepared_operations: 12, attempted_requests: 0, cleanup_required: false };
  need(TOKEN.test(token || ""), "token_missing_or_invalid");
  need(typeof out === "string" && isAbsolute(out), "absolute_output_path_required");
  const output = await plainPath(out);
  try { await mkdir(output); } catch { throw new Stage3Error("output_exists_or_unavailable"); }
  let attempted = 0, completed = 0;
  const result = (outcome, code = null) => ({
    schema: "pitcheezy-stage3-upload-result-v1", outcome, code,
    prepared_operations: 12, attempted_requests: attempted, completed_operations: completed,
    cleanup_required: true, cleanup, data_readback_verified: false,
  });
  try {
    await writeRecord(resolve(output, "started.private.json"), {
      run_id: manifest.run_id, manifest_sha256: manifestSha256, started_utc: new Date(now()).toISOString(),
      expected_deployment_version: manifest.expected_deployment_version,
      version_basis: "operator_management_pin_not_http_or_server_log_proof", request_limit: 12,
    });
    await writeRecord(resolve(output, "manifest.private.json"), frozen.bytes);
    for (const [i, operation] of prepared.entries()) {
      windowFor(manifest, true, now(), 12 - i);
      const sequence = i + 1, prefix = `request-${String(sequence).padStart(2, "0")}`;
      const started = new Date(now()).toISOString();
      await writeRecord(resolve(output, prefix + ".pending.private.json"), {
        sequence, method: operation.plan.method, path: operation.plan.path, started_utc: started,
        expected_status: operation.expected_status, expected_outcome: operation.expected_outcome,
      });
      let exchange = null, calls = 0;
      const recordingFetch = async (url, init) => {
        need(calls === 0 && attempted < 12, "request_budget_exhausted");
        need(url === manifest.origin + "/_publish" + operation.plan.path && init.method === operation.plan.method && init.redirect === "error", "transport_target_changed");
        windowFor(manifest, true, now(), 12 - i);
        ++calls; ++attempted;
        const sent = new Date(now()).toISOString();
        exchange = { started_utc: sent, headers_received_utc: null, status: null, ray: null };
        try {
          const response = await fetchImpl(url, init);
          const ray = response.headers.get("CF-Ray");
          exchange = { started_utc: sent, headers_received_utc: new Date(now()).toISOString(), status: response.status,
            ray: ray && RAY.test(ray) ? ray : null };
          return response;
        } catch {
          exchange = { started_utc: sent, headers_received_utc: null, status: null, ray: null, transport_error: true };
          throw new Stage3Error("transport_failed");
        }
      };
      const receipt = await transmit(operation.plan, operation.payload, token, {
        maxAttempts: 1, timeoutMs: TIMEOUT_MS, totalMs: TIMEOUT_MS, backoffMs: 0, fetchImpl: recordingFetch,
      });
      const row = { sequence, method: operation.plan.method, path: operation.plan.path,
        started_utc: started, finished_utc: new Date(now()).toISOString(), exchange,
        expected_deployment_version: manifest.expected_deployment_version,
        version_basis: "operator_management_pin_not_http_or_server_log_proof", receipt };
      await writeRecord(resolve(output, prefix + ".completed.private.json"), row);
      need(calls === 1 && receipt.attempts.length === 1 && exchange?.status === operation.expected_status && receipt.outcome === operation.expected_outcome, "unexpected_response_stop");
      if (operation.plan.method === "PUT") need(receipt.current_sha256 === operation.plan.sha256, "returned_sha_mismatch");
      ++completed;
    }
    const summary = result("uploaded_pending_operator_close");
    await writeRecord(resolve(output, "result.private.json"), summary);
    return summary;
  } catch (error) {
    const summary = result("STOPPED", codeOf(error));
    try { await writeRecord(resolve(output, "result.private.json"), summary); } catch { summary.journal_write_failed = true; }
    return summary;
  }
}

export async function main(args, { environment = process.env, stdout = process.stdout, stderr = process.stderr, ...dependencies } = {}) {
  try {
    const { values } = parseArgs({ args, options: {
      manifest: { type: "string" }, "manifest-sha256": { type: "string" }, out: { type: "string" }, execute: { type: "boolean", default: false },
    } });
    need(values.manifest && values["manifest-sha256"], "manifest_and_sha_required");
    const result = await runStage3({ manifestPath: values.manifest, manifestSha256: values["manifest-sha256"],
      out: values.out, execute: values.execute, token: values.execute ? environment.PITCHEEZY_PUBLISH_TOKEN : null }, dependencies);
    stdout.write(JSON.stringify(result, null, 2) + "\n");
    return result.outcome === "STOPPED" ? 3 : 0;
  } catch (error) {
    stderr.write(JSON.stringify({ ok: false, code: codeOf(error), cleanup: "If upload was opened by the operator, close it and rotate the temporary digest. Do not retry an uncertain run." }) + "\n");
    return 2;
  }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) process.exitCode = await main(process.argv.slice(2));
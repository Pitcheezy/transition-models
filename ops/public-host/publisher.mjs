/** Our proposed single-file transport client. No baseball contract or publisher ledger. */
import { createHash } from "node:crypto";
import { performance } from "node:perf_hooks";
import { permittedKey, MAX_JSON_BYTES } from "./gateway.mjs";

const HASH = /^[a-f0-9]{64}$/;
const ETAG = /^"[a-f0-9]{32}"$/;
const TOKEN = /^[A-Za-z0-9_-]{43,128}$/;
const sha = bytes => createHash("sha256").update(bytes).digest("hex");
const EMPTY_SHA = sha(new Uint8Array());
const exact = (o, keys) => o && typeof o === "object" && !Array.isArray(o) &&
  Object.keys(o).sort().join(",") === [...keys].sort().join(",");
export class PublisherError extends Error { constructor(code) { super(code); this.code = code; } }
const refuse = code => { throw new PublisherError(code); };

export function prepare(plan, input = null) {
  if (!exact(plan, ["schema", "origin", "allow_loopback_http", "method", "path",
      "condition", "source_file", "sha256"]) || plan.schema !== "pitcheezy-upload-plan-v1") {
    refuse("invalid_plan");
  }
  let url;
  try { url = new URL(plan.origin); } catch { refuse("invalid_origin"); }
  if (typeof plan.origin !== "string" || url.origin !== plan.origin ||
      url.username || url.password || url.search || url.hash ||
      typeof plan.allow_loopback_http !== "boolean") refuse("invalid_origin");
  if (url.protocol !== "https:" && !(plan.allow_loopback_http && url.protocol === "http:" &&
      ["127.0.0.1", "[::1]"].includes(url.hostname))) refuse("https_or_explicit_loopback_required");
  if (typeof plan.path !== "string" || !permittedKey(plan.path) ||
      !["PUT", "DELETE", "HEAD"].includes(plan.method)) refuse("invalid_target");
  let condition = {};
  if (plan.method === "HEAD") {
    if (plan.condition !== null) refuse("head_condition_must_be_null");
  } else if (exact(plan.condition, ["if_match"]) && typeof plan.condition.if_match === "string" && ETAG.test(plan.condition.if_match)) {
    condition = { "If-Match": plan.condition.if_match };
  } else if (plan.method === "PUT" && exact(plan.condition, ["if_none_match"]) &&
      plan.condition.if_none_match === "*") condition = { "If-None-Match": "*" };
  else refuse("explicit_precondition_required");
  let body = null;
  let digest = plan.method === "DELETE" ? EMPTY_SHA : null;
  if (plan.method === "PUT") {
    if (typeof plan.source_file !== "string" || plan.source_file.length > 256 ||
        !/^[A-Za-z0-9_.\/-]+\.json$/.test(plan.source_file) ||
        plan.source_file.startsWith("/") ||
        plan.source_file.split("/").some(p => !p || p === "." || p === "..") ||
        typeof plan.sha256 !== "string" || !HASH.test(plan.sha256)) refuse("invalid_source");
    if (!(input instanceof Uint8Array) || !input.byteLength || input.byteLength > MAX_JSON_BYTES) {
      refuse("invalid_body_size");
    }
    body = new Uint8Array(input); // fixed private snapshot, never re-read on retry
    digest = sha(body);
    if (digest !== plan.sha256) refuse("source_sha_mismatch");
    let value;
    try { value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(body)); }
    catch { refuse("invalid_json"); }
    if (!value || typeof value !== "object" || Array.isArray(value)) refuse("json_object_required");
  } else if (plan.source_file !== null || plan.sha256 !== null || input !== null) {
    refuse("unexpected_body");
  }
  return { origin: plan.origin, path: plan.path, method: plan.method, condition, body, digest };
}

export function dryRun(plan, input = null) {
  const p = prepare(plan, input);
  return { schema: "pitcheezy-upload-receipt-v1", outcome: "dry_run", attempted: false,
    path: p.path, method: p.method, bytes: p.body?.byteLength ?? 0, sha256: p.digest,
    schema_validated: false, attempts: [] };
}

async function responseBody(response, signal) {
  if (!/^application\/json(?:\s*;\s*charset=utf-8)?$/i.test(response.headers.get("Content-Type") || "")) {
    refuse("invalid_success_response");
  }
  const reader = response.body?.getReader();
  if (!reader) refuse("invalid_success_response");
  const onAbort = () => { void reader.cancel().catch(() => {}); };
  signal.addEventListener("abort", onAbort, { once: true });
  if (signal.aborted) onAbort();
  let size = 0; const chunks = [];
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > 2048) { void reader.cancel().catch(() => {}); refuse("invalid_success_response"); }
      chunks.push(value);
    }
  } finally { signal.removeEventListener("abort", onAbort); reader.releaseLock(); }
  try { return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks))); }
  catch { refuse("invalid_success_response"); }
}

async function request(p, token, fetchImpl, timeoutMs) {
  const controller = new AbortController();
  let response; let timer; let completed = false;
  const work = (async () => {
    response = await fetchImpl(p.origin + "/_publish" + p.path, {
      method: p.method, redirect: "error", credentials: "omit", cache: "no-store",
      signal: controller.signal,
      headers: { Authorization: "Bearer " + token, ...p.condition,
        ...(p.method === "PUT" ? { "Content-Type": "application/json", "X-Content-SHA256": p.digest } : {}) },
      ...(p.body ? { body: new Uint8Array(p.body) } : {}),
    });
    if (response.status !== 200) return { status: response.status, retry: response.headers.get("Retry-After") };
    const etag = response.headers.get("ETag");
    if (!ETAG.test(etag || "")) refuse("invalid_success_response");
    if (p.method === "HEAD") {
      const deleted = response.headers.get("X-Publish-Deleted");
      const digest = response.headers.get("X-Content-SHA256");
      if (!["true", "false"].includes(deleted) || !HASH.test(digest || "") ||
          (deleted === "true" && digest !== EMPTY_SHA)) refuse("invalid_success_response");
      return { status: 200, etag, deleted: deleted === "true", sha256: digest, metadata_only: true };
    }
    const body = await responseBody(response, controller.signal);
    if (!exact(body, ["stored", "deleted", "sha256", "schema_validated"]) ||
        body.stored !== true || body.deleted !== (p.method === "DELETE") ||
        body.sha256 !== p.digest || body.schema_validated !== false) refuse("invalid_success_response");
    return { status: 200, etag, deleted: body.deleted, sha256: body.sha256 };
  })();
  try {
    const result = await Promise.race([work, new Promise((_, reject) => {
      timer = setTimeout(() => { controller.abort(); reject(new PublisherError("request_timeout")); }, timeoutMs);
    })]);
    completed = true;
    return result;
  } finally {
    clearTimeout(timer);
    if (!completed) controller.abort();
    if (response?.body && !response.bodyUsed && !response.body.locked) void response.body.cancel().catch(() => {});
  }
}

export async function transmit(plan, input, token, options = {}) {
  const p = prepare(plan, input);
  if (typeof token !== "string" || !TOKEN.test(token)) refuse("token_missing_or_invalid");
  const { fetchImpl = fetch, timeoutMs = 5000, totalMs = 20000, maxAttempts = 3,
    backoffMs = 500 } = options;
  if (!Number.isInteger(timeoutMs) || timeoutMs < 10 || timeoutMs > 5000 ||
      !Number.isInteger(totalMs) || totalMs < timeoutMs || totalMs > 20000 ||
      !Number.isInteger(maxAttempts) || maxAttempts < 1 || maxAttempts > 3 ||
      !Number.isInteger(backoffMs) || backoffMs < 0 || backoffMs > 1000) refuse("invalid_limits");
  const start = performance.now(), deadline = start + totalMs, attempts = [];
  let uncertain = false;
  const finish = (outcome, extra = {}) => ({
    schema: "pitcheezy-upload-receipt-v1", outcome, attempted: attempts.length > 0,
    path: p.path, method: p.method, sha256: p.digest, schema_validated: false,
    elapsed_ms: Math.ceil(performance.now() - start), attempts, ...extra,
  });
  for (let i = 0; i < maxAttempts; i++) {
    const remaining = deadline - performance.now();
    if (remaining <= 0) break;
    let result;
    try {
      result = await request(p, token, fetchImpl, Math.min(timeoutMs, remaining));
      attempts.push({ number: i + 1, status: result.status });
    } catch (error) {
      attempts.push({ number: i + 1, error: error instanceof PublisherError ? error.code : "network_error" });
      if (p.method !== "HEAD") uncertain = true;
      if (error instanceof PublisherError && error.code === "invalid_success_response") {
        return finish(p.method === "HEAD" ? "invalid_response" : "unknown");
      }
      result = { status: null, retry: null };
    }
    if (result.status === 200) return finish(p.method === "HEAD" ? "observed" : "stored",
      { etag: result.etag, deleted: result.deleted, current_sha256: result.sha256,
        ...(p.method === "HEAD" ? { metadata_only: true } : {}) });
    if (p.method === "HEAD" && result.status === 404) return finish("missing");
    if (result.status === 412) return finish(uncertain ? "conflict_or_already_applied" : "conflict");
    if (result.status !== null && result.status >= 500 && p.method !== "HEAD") uncertain = true;
    const retryable = result.status === null || result.status === 429 ||
      (result.status >= 500 && result.status <= 599);
    if (!retryable) {
      // Only documented pre-storage rejections establish that this attempt did not write.
      const definiteRejection = [400, 401, 403, 404, 405, 413, 415, 422, 428].includes(result.status);
      if (p.method === "HEAD" && result.status >= 200 && result.status < 300) return finish("invalid_response");
      return finish(uncertain || (p.method !== "HEAD" && !definiteRejection) ? "unknown" : "rejected");
    }
    let delay = backoffMs * 2 ** i;
    if (result.retry !== null) {
      if (!/^[0-9]{1,6}$/.test(result.retry || "")) return finish(uncertain ? "unknown" : "deferred");
      delay = Math.max(delay, Number(result.retry) * 1000);
    } else if (result.status === 429) return finish(uncertain ? "unknown" : "deferred", { retry_after_seconds: null });
    if (i === maxAttempts - 1) break;
    if (delay + 1 >= deadline - performance.now()) return finish(uncertain ? "unknown" : "deferred",
      { retry_after_seconds: Math.ceil(delay / 1000) });
    await new Promise(resolve => setTimeout(resolve, delay));
  }
  return finish(uncertain ? "unknown" : p.method === "HEAD" ? "unavailable" : "deferred");
}

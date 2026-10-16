/** Explicit notice operator transport. No automatic retries, credentials on disk, or cloud setup. */
import { NOTICE_ROUTE, NOTICE_MESSAGES } from "./notice.mjs";

const ETAG = /^"[a-f0-9]{32}"$/;
const TOKEN = /^[A-Za-z0-9_-]{43,128}$/;
const MAX_RESPONSE_BYTES = 65536;
const exact = (v, keys) => v !== null && typeof v === "object" && !Array.isArray(v) &&
  Object.keys(v).length === keys.length && keys.every(k => Object.hasOwn(v, k));
const integer = n => Number.isSafeInteger(n) && n >= 0;
const timestamp = v => typeof v === "string" && Number.isFinite(Date.parse(v)) &&
  /^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?(?:Z|[+-]\d\d:\d\d)$/.test(v);
export class NoticeClientError extends Error { constructor(code) { super(code); this.code = code; } }
const refuse = code => { throw new NoticeClientError(code); };

/** Validate and copy a human-reviewable plan; no environment or network access. */
export function prepareNotice(plan) {
  if (!exact(plan, ["schema", "origin", "allow_loopback_http", "method", "condition", "change"]) ||
      plan.schema !== "pitcheezy-notice-plan-v1") refuse("invalid_plan");
  let url;
  try { url = new URL(plan.origin); } catch { refuse("invalid_origin"); }
  if (typeof plan.origin !== "string" || url.origin !== plan.origin || url.username || url.password ||
      url.search || url.hash || typeof plan.allow_loopback_http !== "boolean") refuse("invalid_origin");
  if (url.protocol !== "https:" && !(plan.allow_loopback_http && url.protocol === "http:" &&
      ["127.0.0.1", "[::1]"].includes(url.hostname))) refuse("https_or_explicit_loopback_required");
  if (!["GET", "HEAD", "PUT"].includes(plan.method)) refuse("invalid_method");
  let condition = {}, body = null, change = null;
  if (plan.method === "PUT") {
    if (exact(plan.condition, ["if_match"]) && typeof plan.condition.if_match === "string" && ETAG.test(plan.condition.if_match)) {
      condition = { "If-Match": plan.condition.if_match };
    } else if (exact(plan.condition, ["if_none_match"]) && plan.condition.if_none_match === "*") {
      condition = { "If-None-Match": "*" };
    } else refuse("explicit_precondition_required");
    const v = plan.change;
    if (!exact(v, ["active", "operator", "reason", "message_id"]) || typeof v.active !== "boolean" ||
        typeof v.operator !== "string" || !/^[A-Za-z0-9._-]{1,64}$/.test(v.operator) ||
        typeof v.reason !== "string" || v.reason.length < 1 || v.reason.length > 500 || /[\p{Cc}]/u.test(v.reason) ||
        typeof v.message_id !== "string" || !Object.hasOwn(NOTICE_MESSAGES, v.message_id)) refuse("invalid_change");
    change = { active: v.active, operator: v.operator, reason: v.reason, message_id: v.message_id };
    body = JSON.stringify(change);
    if (Buffer.byteLength(body) > 2048) refuse("request_too_large");
  } else if (plan.condition !== null || plan.change !== null) refuse("unexpected_change_or_condition");
  return { origin: plan.origin, method: plan.method, condition, change, body };
}

function baseReceipt(p, outcome, attempted = false) {
  return { schema: "pitcheezy-notice-receipt-v1", method: p.method, outcome, attempted,
    requests: attempted ? 1 : 0, retries: 0, ...(p.change ? { requested_active: p.change.active,
      requested_message_id: p.change.message_id, body_bytes: Buffer.byteLength(p.body) } : {}) };
}
export function noticeDryRun(plan) { return baseReceipt(prepareNotice(plan), "dry_run"); }

async function jsonBody(response, signal) {
  if (!/^application\/json(?:\s*;\s*charset=utf-8)?$/i.test(response.headers.get("Content-Type") || "")) refuse("invalid_response");
  const declared = response.headers.get("Content-Length");
  if (declared !== null && (!/^\d+$/.test(declared) || Number(declared) > MAX_RESPONSE_BYTES)) refuse("response_too_large");
  const reader = response.body?.getReader();
  if (!reader) refuse("invalid_response");
  const cancel = () => { void reader.cancel().catch(() => {}); };
  signal.addEventListener("abort", cancel, { once: true });
  const chunks = []; let size = 0;
  try {
    while (true) {
      signal.throwIfAborted();
      const { done, value } = await reader.read();
      signal.throwIfAborted();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_RESPONSE_BYTES) { cancel(); refuse("response_too_large"); }
      chunks.push(value);
    }
  } finally { signal.removeEventListener("abort", cancel); reader.releaseLock(); }
  if (declared !== null && Number(declared) !== size) refuse("invalid_response");
  try { return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(Buffer.concat(chunks))); }
  catch { refuse("invalid_response"); }
}

function protectedHeaders(response) {
  const cache = (response.headers.get("Cache-Control") || "").toLowerCase().split(",").map(x => x.trim());
  const etag = response.headers.get("ETag");
  if (!cache.includes("no-store") || (etag !== null && (!ETAG.test(etag) || !cache.includes("no-transform")))) refuse("invalid_response");
  return etag;
}
function readState(value, etag) {
  if (!exact(value, ["state", "audit", "audit_truncated", "audit_unavailable", "messages"]) ||
      !Array.isArray(value.audit) || value.audit.length > 20 || typeof value.audit_truncated !== "boolean" ||
      typeof value.audit_unavailable !== "boolean") refuse("invalid_response");
  const s = value.state;
  if (!exact(s, ["active", "message_id", "revision", "since", "etag"]) || typeof s.active !== "boolean" ||
      !integer(s.revision) || s.etag !== etag) refuse("invalid_response");
  if (s.revision === 0) {
    if (s.active || s.message_id !== null || s.since !== null || etag !== null) refuse("invalid_response");
  } else if (!etag || typeof s.message_id !== "string" || !Object.hasOwn(NOTICE_MESSAGES, s.message_id) ||
      (s.active ? !timestamp(s.since) : s.since !== null)) refuse("invalid_response");
  if (s.revision > 0 && !value.audit_unavailable && !value.audit.some(a => a &&
      a.schema === "pitcheezy-notice-audit-v1" && a.revision === s.revision && a.etag_after === etag)) refuse("invalid_response");
  return { active: s.active, message_id: s.message_id, revision: s.revision,
    audit_unavailable: value.audit_unavailable, audit_truncated: value.audit_truncated };
}
function writeAck(value, p, etag) {
  const keys = ["active", "message_id", "revision", "since", "change_id", "audit_recorded"];
  if (value && Object.hasOwn(value, "audit_error")) keys.push("audit_error");
  if (!etag || !exact(value, keys) || value.active !== p.change.active || value.message_id !== p.change.message_id ||
      !integer(value.revision) || value.revision < 1 ||
      (value.active ? !timestamp(value.since) : value.since !== null) ||
      typeof value.change_id !== "string" || !/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(value.change_id) ||
      typeof value.audit_recorded !== "boolean" || (Object.hasOwn(value, "audit_error") &&
        (value.audit_recorded || value.audit_error !== "audit_write_failed"))) refuse("invalid_response");
  return { active: value.active, message_id: value.message_id, revision: value.revision, audit_recorded: value.audit_recorded };
}

/** One request only. The snapshot is private output; only receipt is suitable for console logging. */
export async function executeNotice(plan, token, { fetchImpl = fetch, timeoutMs = 5000 } = {}) {
  const p = prepareNotice(plan);
  if (typeof token !== "string" || !TOKEN.test(token)) refuse("notice_token_unavailable_or_invalid");
  if (!Number.isInteger(timeoutMs) || timeoutMs < 50 || timeoutMs > 30000) refuse("invalid_timeout");
  const controller = new AbortController();
  let timer, status = null;
  const isWrite = p.method === "PUT";
  const finish = (outcome, extra = {}, snapshot = null) => ({ receipt: {
    ...baseReceipt(p, outcome, true), ...(status !== null ? { http_status: status } : {}), ...extra }, snapshot });
  const perform = async () => {
    const response = await fetchImpl(p.origin + NOTICE_ROUTE, { method: p.method,
      headers: { Authorization: "Bearer " + token, ...p.condition,
        ...(isWrite ? { "Content-Type": "application/json" } : {}) },
      body: p.body, signal: controller.signal, redirect: "manual", credentials: "omit", referrerPolicy: "no-referrer", cache: "no-store" });
    status = response.status;
    if (status !== 200) {
      void response.body?.cancel().catch(() => {});
      if (status === 412 && isWrite) return finish("conflict");
      if (status === 429) return finish("deferred");
      if ([400, 401, 403, 404, 405, 413, 415, 422, 428].includes(status)) return finish("rejected");
      return finish(isWrite ? "unknown" : "unavailable", { code: status >= 300 && status < 400 ? "redirect_not_followed" : "unexpected_status" });
    }
    const etag = protectedHeaders(response);
    let observed;
    if (p.method === "HEAD") observed = { metadata_only: true, audit_status: "unmeasured" };
    else {
      const value = await jsonBody(response, controller.signal);
      observed = isWrite ? writeAck(value, p, etag) : readState(value, etag);
    }
    if (isWrite) return finish(observed.audit_recorded ? "applied" : "applied_audit_missing", observed);
    const snapshot = { schema: "pitcheezy-notice-snapshot-v1", origin: p.origin, method: p.method,
      observed_at: new Date().toISOString(), condition: etag ? { if_match: etag } : { if_none_match: "*" }, observed };
    return finish(observed.audit_unavailable ? "observed_audit_unavailable" : "observed", observed, snapshot);
  };
  try {
    return await Promise.race([perform(), new Promise((_, reject) => {
      timer = setTimeout(() => { controller.abort(); reject(new NoticeClientError("request_timeout")); }, timeoutMs);
    })]);
  } catch (error) {
    return finish(isWrite ? "unknown" : error instanceof NoticeClientError && error.code !== "request_timeout" ? "invalid_response" : "unavailable",
      { code: error instanceof NoticeClientError ? error.code : controller.signal.aborted ? "request_timeout" : "network_error" });
  } finally { clearTimeout(timer); controller.abort(); }
}

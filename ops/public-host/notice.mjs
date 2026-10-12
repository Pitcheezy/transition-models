/**
 * Emergency notice switch (WS-safe1). Our host-side state only; no Song screen, model or publisher code.
 * The switch is a private R2 object changed through an authenticated admin route. Nothing here deletes
 * data a browser already downloaded, and the placeholder texts are development copy awaiting approval.
 */
const encoder = new TextEncoder();
const SHA256 = /^[a-f0-9]{64}$/;
const ETAG = /^"[a-f0-9]{32}"$/;
export const NOTICE_ROUTE = "/_notice/v1/state";
export const NOTICE_STATE_KEY = "_notice/state.json";
export const NOTICE_AUDIT_PREFIX = "_notice/audit/";
export const NOTICE_CACHE_MS = 2000; // Per-isolate memo; bounds switch latency per isolate, not globally.
export const NOTICE_HEADER = "X-Pitcheezy-Notice";
const STATE_SCHEMA = "pitcheezy-notice-state-v1";
const AUDIT_SCHEMA = "pitcheezy-notice-audit-v1";
const MAX_BODY = 2048;
const MAX_AUDIT_LIST = 20;
/** Development placeholder copy. The public wording is a human decision (WS-human1); ids are stable. */
export const NOTICE_MESSAGES = Object.freeze({
  maintenance: "개발용 안내 문구(승인 전): 서비스 점검 중입니다. 잠시 후 다시 확인해 주세요.",
  data_hold: "개발용 안내 문구(승인 전): 자료 확인 중이라 화면을 잠시 내렸습니다.",
});
export class NoticeError extends Error {
  constructor(status, code, headers = {}) { super(code); this.status = status; this.headers = headers; }
}
const fail = (status, code, headers) => { throw new NoticeError(status, code, headers); };
const object = v => v !== null && typeof v === "object" && !Array.isArray(v);
const exact = (v, keys) => object(v) && Object.keys(v).length === keys.length && keys.every(k => Object.hasOwn(v, k));
const sha256 = async bytes => Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
  b => b.toString(16).padStart(2, "0")).join("");

/** Parses NOTICE_TOKEN_SHA256: 1..8 comma-separated digests, one per authorised operator. */
export function noticeDigests(env) {
  const raw = typeof env.NOTICE_TOKEN_SHA256 === "string" ? env.NOTICE_TOKEN_SHA256 : "";
  if (!raw) return null;
  const digests = raw.split(",").map(x => x.trim());
  if (digests.length > 8 || digests.some(d => !SHA256.test(d)) || new Set(digests).size !== digests.length) return null;
  return digests;
}

function validateState(value) {
  if (!exact(value, ["schema", "active", "message_id", "revision", "since", "updated_at", "last_change_id"]) ||
      value.schema !== STATE_SCHEMA || typeof value.active !== "boolean" ||
      !Object.hasOwn(NOTICE_MESSAGES, value.message_id) || !Number.isSafeInteger(value.revision) || value.revision < 1 ||
      !(value.since === null || typeof value.since === "string") || typeof value.updated_at !== "string" ||
      typeof value.last_change_id !== "string") fail(503, "notice_state_invalid");
  return value;
}

const memo = new WeakMap();
export function invalidateNotice(bucket) { if (bucket) memo.delete(bucket); }

/**
 * Current switch state. Fails closed when the switch storage exists but cannot be read or is malformed.
 * A deployment without PUBLISH_BUCKET has no switch at all (the release config check requires the
 * binding, so this only happens in isolated unit fixtures); data routes already answer 503 there.
 */
export async function currentNotice(env, now = Date.now()) {
  const bucket = env.PUBLISH_BUCKET;
  if (!bucket) return { active: false, message_id: null, revision: 0, since: null, etag: null, storage: "absent" };
  const cached = memo.get(bucket);
  if (cached && now - cached.at < NOTICE_CACHE_MS && now >= cached.at) return cached.value;
  const obj = await bucket.get(NOTICE_STATE_KEY);
  let value;
  if (!obj) value = { active: false, message_id: null, revision: 0, since: null, etag: null };
  else {
    if (obj.customMetadata?.kind !== "notice-state-v1") fail(503, "notice_state_invalid");
    let parsed;
    try { parsed = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(await obj.arrayBuffer())); }
    catch { fail(503, "notice_state_invalid"); }
    const state = validateState(parsed);
    value = { active: state.active, message_id: state.message_id, revision: state.revision, since: state.since, etag: obj.httpEtag };
  }
  memo.set(bucket, { at: now, value });
  return value;
}

async function authorize(request, env) {
  const digests = noticeDigests(env);
  if (!digests) fail(503, "notice_control_not_configured");
  const token = /^Bearer ([A-Za-z0-9_-]{43,128})$/.exec(request.headers.get("Authorization") || "")?.[1];
  if (!token) fail(401, "unauthorized");
  const actual = await sha256(encoder.encode(token));
  let matched = null;
  for (const digest of digests) {
    let difference = 0;
    for (let i = 0; i < actual.length; i++) difference |= actual.charCodeAt(i) ^ digest.charCodeAt(i);
    if (difference === 0) matched = digest;
  }
  if (!matched) fail(401, "unauthorized");
  return matched.slice(0, 12); // Operator identity for the audit record; the raw token is never stored.
}

async function enforceLimit(env) {
  let result;
  try {
    if (typeof env.PUBLISH_LIMITER?.limit !== "function") throw new Error();
    result = await env.PUBLISH_LIMITER.limit({ key: "notice" }); // Separate pool from the publisher key.
  } catch { fail(503, "notice_limiter_unavailable"); }
  if (!result || typeof result !== "object" || typeof result.success !== "boolean") fail(503, "notice_limiter_unavailable");
  if (result.success === false) fail(429, "notice_rate_limited", { "Retry-After": "60" });
}

async function readBody(request) {
  if (!/^application\/json(?:\s*;\s*charset=utf-8)?$/i.test(request.headers.get("Content-Type") || "") ||
      request.headers.has("Content-Encoding")) fail(415, "json_required");
  const length = request.headers.get("Content-Length");
  if (length !== null && (!/^[0-9]+$/.test(length) || Number(length) > MAX_BODY)) fail(413, "body_too_large");
  const reader = request.body?.getReader();
  if (!reader) fail(400, "empty_body");
  const chunks = []; let size = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > MAX_BODY) { await reader.cancel(); fail(413, "body_too_large"); }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  if (length !== null && Number(length) !== size) fail(400, "length_mismatch");
  const bytes = new Uint8Array(size); let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  let value;
  try { value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)); } catch { fail(400, "invalid_json"); }
  if (!exact(value, ["active", "operator", "reason", "message_id"]) || typeof value.active !== "boolean" ||
      typeof value.operator !== "string" || !/^[A-Za-z0-9._-]{1,64}$/.test(value.operator) ||
      typeof value.reason !== "string" || value.reason.length < 1 || value.reason.length > 500 ||
      /[\p{Cc}]/u.test(value.reason) || !Object.hasOwn(NOTICE_MESSAGES, value.message_id)) fail(400, "invalid_notice_change");
  return value;
}

function precondition(request) {
  const match = request.headers.get("If-Match");
  const none = request.headers.get("If-None-Match");
  if (match && !none && ETAG.test(match)) return new Headers({ "If-Match": match });
  if (!match && none === "*") return new Headers({ "If-None-Match": "*" });
  fail(428, "single_write_precondition_required");
}

function reply(request, status, body, extra = {}) {
  const headers = new Headers({
    "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store",
    "CDN-Cache-Control": "no-store", "Date": new Date().toUTCString(), "Age": "0",
    "X-Content-Type-Options": "nosniff", ...extra,
  });
  return new Response(request.method === "HEAD" ? null : JSON.stringify(body), { status, headers });
}

async function listAudit(bucket) {
  if (typeof bucket.list !== "function") return { entries: [], truncated: true, unavailable: true };
  const listed = await bucket.list({ prefix: NOTICE_AUDIT_PREFIX, limit: 1000 });
  const keys = (listed?.objects || []).map(o => o.key).sort();
  const tail = keys.slice(-MAX_AUDIT_LIST);
  const entries = [];
  for (const key of tail) {
    const obj = await bucket.get(key);
    if (!obj) continue;
    try {
      const value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(await obj.arrayBuffer()));
      if (object(value) && value.schema === AUDIT_SCHEMA) entries.push(value);
    } catch { entries.push({ schema: AUDIT_SCHEMA, key, unreadable: true }); }
  }
  return { entries, truncated: Boolean(listed?.truncated) || keys.length > MAX_AUDIT_LIST, unavailable: false };
}

/** Admin route: GET/HEAD current state + recent audit, PUT a change. Never affected by the notice itself. */
export async function handleNotice(request, env) {
  const url = new URL(request.url);
  try {
    if (url.pathname !== NOTICE_ROUTE || url.search) return reply(request, 404, { error: "not_found" });
    const operatorId = await authorize(request, env);
    if (!["GET", "HEAD", "PUT"].includes(request.method)) {
      return reply(request, 405, { error: "method_not_allowed" }, { Allow: "GET, HEAD, PUT" });
    }
    await enforceLimit(env);
    const bucket = env.PUBLISH_BUCKET;
    if (!bucket || typeof bucket.put !== "function") fail(503, "storage_not_configured");
    if (request.method !== "PUT") {
      invalidateNotice(bucket); // Operators read the stored truth, not the memo.
      const state = await currentNotice(env);
      const audit = await listAudit(bucket);
      return reply(request, 200, { state, audit: audit.entries, audit_truncated: audit.truncated,
        audit_unavailable: audit.unavailable, messages: NOTICE_MESSAGES }, state.etag ? { ETag: state.etag } : {});
    }
    const onlyIf = precondition(request);
    const change = await readBody(request);
    invalidateNotice(bucket);
    const before = await currentNotice(env);
    const now = new Date();
    const id = crypto.randomUUID();
    const next = {
      schema: STATE_SCHEMA, active: change.active, message_id: change.message_id,
      revision: before.revision + 1,
      since: change.active ? (before.active ? before.since : now.toISOString()) : null,
      updated_at: now.toISOString(), last_change_id: id,
    };
    const bytes = encoder.encode(JSON.stringify(next));
    const stored = await bucket.put(NOTICE_STATE_KEY, bytes, {
      onlyIf, sha256: await sha256(bytes),
      httpMetadata: { contentType: "application/json; charset=utf-8", cacheControl: "no-store" },
      customMetadata: { kind: "notice-state-v1", revision: String(next.revision) },
    });
    invalidateNotice(bucket);
    if (!stored) fail(412, "write_conflict");
    const audit = {
      schema: AUDIT_SCHEMA, id, at: now.toISOString(), active: change.active, message_id: change.message_id,
      operator: change.operator, reason: change.reason, operator_token_prefix: operatorId,
      revision: next.revision, etag_before: before.etag, etag_after: stored.httpEtag,
    };
    const auditBytes = encoder.encode(JSON.stringify(audit));
    const auditKey = NOTICE_AUDIT_PREFIX + now.toISOString().replace(/[-:.]/g, "") + "-" + id + ".json";
    const auditStored = await bucket.put(auditKey, auditBytes, {
      onlyIf: new Headers({ "If-None-Match": "*" }), sha256: await sha256(auditBytes),
      httpMetadata: { contentType: "application/json; charset=utf-8", cacheControl: "no-store" },
      customMetadata: { kind: "notice-audit-v1" },
    });
    return reply(request, 200, {
      active: next.active, message_id: next.message_id, revision: next.revision, since: next.since,
      change_id: id, audit_recorded: Boolean(auditStored),
    }, { ETag: stored.httpEtag });
  } catch (error) {
    const known = error instanceof NoticeError;
    return reply(request, known ? error.status : 503, { error: known ? error.message : "storage_unavailable" },
      known ? error.headers : {});
  }
}

/** Public notice bodies. No scripts, no external assets, no internal reason or operator. */
export function noticeHtml(messageId) {
  const text = NOTICE_MESSAGES[messageId] || NOTICE_MESSAGES.maintenance;
  const escape = s => s.replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  return '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">' +
    '<meta name="robots" content="noindex,nofollow"><title>안내</title>' +
    '<style>body{font-family:system-ui,sans-serif;margin:0;padding:24px 16px;color:#1b1b1b;background:#fafafa}' +
    'main{max-width:36rem;margin:0 auto}h1{font-size:1.25rem}p{line-height:1.5}small{color:#555}</style></head>' +
    '<body><main data-notice-id="' + escape(messageId) + '"><h1>안내</h1><p>' + escape(text) + '</p>' +
    '<p><small>개발용 안내 화면입니다. 실제 공개 문구와 전환은 담당자가 결정합니다.</small></p></main></body></html>';
}
export function noticeJson(messageId) {
  return { error: "service_notice", notice: { id: messageId, message: NOTICE_MESSAGES[messageId] || NOTICE_MESSAGES.maintenance } };
}

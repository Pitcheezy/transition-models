import { handleTelemetry } from "./telemetry.mjs";
import { currentNotice, handleNotice, noticeHtml, noticeJson, NOTICE_HEADER } from "./notice.mjs";
/**
 * File transport candidate for COLLAB-001. No baseball-schema validation here.
 * Both gates default closed. Only a reviewed publisher may supply public data.
 */
export const MAX_JSON_BYTES = 5 * 1024 * 1024; // Provisional, measure actual export before launch.
const SHA256 = /^[a-f0-9]{64}$/;
const ETAG = /^"[a-f0-9]{32}"$/; // Single-part R2 objects written by this gateway only.
const encoder = new TextEncoder();
const RECORD_FORMAT = "pitcheezy-host-record-v1";
const RECORD_PREFIX = RECORD_FORMAT + ":";
const RECORD_HEADER_BYTES = encoder.encode(RECORD_PREFIX + "0".repeat(36) + "\n").length;

class HttpError extends Error {
  constructor(status, code, headers = {}) { super(code); this.status = status; this.headers = headers; }
}

export function permittedKey(pathname) {
  if (/^\/v1\/(manifest|health|dates)\.json$/.test(pathname)) return pathname.slice(1);
  if (/^\/v1\/(game|setup)\/[1-9][0-9]{0,11}\.json$/.test(pathname)) return pathname.slice(1);
  const date = /^\/v1\/games\/([0-9]{4}-[0-9]{2}-[0-9]{2})\.json$/.exec(pathname)?.[1];
  if (date) {
    const parsed = new Date(date + "T00:00:00Z");
    if (Number.isFinite(parsed.getTime()) && parsed.toISOString().slice(0, 10) === date) {
      return pathname.slice(1);
    }
  }
  return null;
}

export async function sha256(bytes) {
  return Array.from(new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
    byte => byte.toString(16).padStart(2, "0")).join("");
}

function response(request, env, status, body = null, extra = {}, publicRead = false) {
  const headers = new Headers({
    "Content-Type": "application/json; charset=utf-8",
    "Cache-Control": "no-store",
    "CDN-Cache-Control": "no-store",
    "Date": new Date().toUTCString(),
    "Age": "0",
    "X-Content-Type-Options": "nosniff",
    ...extra,
  });
  if (publicRead) {
    headers.set("Vary", "Origin");
    // No wildcard/credential support. Keep same origin unless one exact UI origin is agreed.
    const origin = request.headers.get("Origin");
    if (origin && env.READ_ORIGIN && origin === env.READ_ORIGIN) {
      headers.set("Access-Control-Allow-Origin", origin);
      headers.set("Access-Control-Expose-Headers", "Date, Age, ETag");
      headers.set("Access-Control-Allow-Methods", "GET, HEAD, OPTIONS");
    }
  }
  return new Response(request.method === "HEAD" ? null : body, { status, headers });
}

function json(request, env, status, value, extra = {}, publicRead = false) {
  return response(request, env, status, JSON.stringify(value), extra, publicRead);
}

async function authorize(request, env) {
  if (env.UPLOAD_ENABLED !== "true" || !SHA256.test(env.PUBLISH_TOKEN_SHA256 || "")) {
    throw new HttpError(503, "upload_not_configured");
  }
  const token = /^Bearer ([A-Za-z0-9_-]{43,128})$/.exec(request.headers.get("Authorization") || "")?.[1];
  if (!token) throw new HttpError(401, "unauthorized");
  const actual = await sha256(encoder.encode(token));
  // Compare fixed-length digests; never store/log the raw bearer token.
  let difference = 0;
  for (let i = 0; i < actual.length; i++) difference |= actual.charCodeAt(i) ^ env.PUBLISH_TOKEN_SHA256.charCodeAt(i);
  if (difference !== 0) throw new HttpError(401, "unauthorized");
}


async function enforceUploadLimit(env) {
  let result;
  try {
    if (typeof env.PUBLISH_LIMITER?.limit !== "function") throw new Error();
    // One authenticated publisher pool: changing method/path/IP cannot bypass it.
    // Namespace must be separate from telemetry and other deployment environments.
    result = await env.PUBLISH_LIMITER.limit({ key: "publisher" });
  } catch { throw new HttpError(503, "upload_limiter_unavailable"); }
  if (!result || typeof result !== "object" || typeof result.success !== "boolean") {
    throw new HttpError(503, "upload_limiter_unavailable");
  }
  if (result.success === false) {
    throw new HttpError(429, "upload_rate_limited", { "Retry-After": "60" });
  }
}

function precondition(request, deletion) {
  const match = request.headers.get("If-Match");
  const none = request.headers.get("If-None-Match");
  if (match && !none && ETAG.test(match)) return new Headers({ "If-Match": match });
  if (!deletion && !match && none === "*") return new Headers({ "If-None-Match": "*" });
  throw new HttpError(428, "single_write_precondition_required");
}

async function readLimited(request) {
  const length = request.headers.get("Content-Length");
  if (length !== null && (!/^[0-9]+$/.test(length) || Number(length) > MAX_JSON_BYTES)) {
    throw new HttpError(413, "file_too_large");
  }
  if (request.headers.has("Content-Encoding")) throw new HttpError(415, "encoded_body_not_supported");
  const reader = request.body?.getReader();
  if (!reader) throw new HttpError(400, "empty_body");
  const chunks = [];
  let total = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      total += value.byteLength;
      if (total > MAX_JSON_BYTES) {
        await reader.cancel();
        throw new HttpError(413, "file_too_large");
      }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  const bytes = new Uint8Array(total);
  let offset = 0;
  for (const chunk of chunks) { bytes.set(chunk, offset); offset += chunk.byteLength; }
  if (length !== null && Number(length) !== total) throw new HttpError(400, "length_mismatch");
  return bytes;
}

async function upload(request, env, key) {
  await authorize(request, env);
  if (!["PUT", "DELETE", "HEAD"].includes(request.method)) {
    return json(request, env, 405, { error: "method_not_allowed" }, { Allow: "PUT, DELETE, HEAD" });
  }
  await enforceUploadLimit(env);
  if (!env.PUBLISH_BUCKET) throw new HttpError(503, "storage_not_configured");
  if (request.method === "HEAD") {
    const obj = await env.PUBLISH_BUCKET.head(key);
    if (!obj) return response(request, env, 404);
    return response(request, env, 200, null, {
      ETag: obj.httpEtag,
      "X-Publish-Deleted": obj.customMetadata?.deleted === "true" ? "true" : "false",
      ...(obj.customMetadata?.sha256 ? { "X-Content-SHA256": obj.customMetadata.sha256 } : {}),
    });
  }
  const deleting = request.method === "DELETE";
  const onlyIf = precondition(request, deleting);
  let bytes;
  let digest;
  if (deleting) {
    // R2 delete has no conditional option. A conditional tombstone prevents a stale
    // withdrawal racing a newer upload; public GET/HEAD must treat it as absent.
    bytes = new Uint8Array();
    digest = await sha256(bytes);
  } else {
    if (!/^application\/json(?:\s*;\s*charset=utf-8)?$/i.test(request.headers.get("Content-Type") || "")) {
      throw new HttpError(415, "json_required");
    }
    digest = request.headers.get("X-Content-SHA256");
    if (!SHA256.test(digest || "")) throw new HttpError(400, "sha256_required");
    bytes = await readLimited(request);
    if (await sha256(bytes) !== digest) throw new HttpError(422, "checksum_mismatch");
    let value;
    try { value = JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)); }
    catch { throw new HttpError(400, "invalid_json"); }
    if (value === null || typeof value !== "object" || Array.isArray(value)) {
      throw new HttpError(400, "json_object_required");
    }
    // Deliberately no guessed publish fields, sequence rules, or outcome conversions.
  }
  // R2 ETags depend on content. A unique private header prevents ABA when an
  // identical JSON body is restored: an earlier delete/update token stays stale.
  // Public GET strips this header; the publisher's JSON bytes remain unchanged.
  const header = encoder.encode(RECORD_PREFIX + crypto.randomUUID() + "\n");
  const record = new Uint8Array(header.length + bytes.length);
  record.set(header); record.set(bytes, header.length);
  const obj = await env.PUBLISH_BUCKET.put(key, record, {
    onlyIf,
    sha256: await sha256(record),
    httpMetadata: { contentType: "application/octet-stream", cacheControl: "no-store" },
    customMetadata: {
      recordFormat: RECORD_FORMAT, payloadBytes: String(bytes.length),
      deleted: deleting ? "true" : "false", sha256: digest,
    },
  });
  if (!obj) throw new HttpError(412, "write_conflict");
  return json(request, env, 200, {
    stored: true, deleted: deleting, sha256: digest, schema_validated: false,
  }, { ETag: obj.httpEtag });
}

async function read(request, env, key) {
  if (!["GET", "HEAD", "OPTIONS"].includes(request.method)) {
    return json(request, env, 405, { error: "read_only" }, { Allow: "GET, HEAD, OPTIONS" }, true);
  }
  if (env.DATA_READ_ENABLED !== "true") throw new HttpError(503, "publication_not_enabled");
  if (!env.PUBLISH_BUCKET) throw new HttpError(503, "storage_not_configured");
  if (request.method === "OPTIONS") return response(request, env, 204, null, {}, true);
  const obj = request.method === "HEAD" ? await env.PUBLISH_BUCKET.head(key) : await env.PUBLISH_BUCKET.get(key);
  if (!obj || obj.customMetadata?.deleted === "true") {
    return json(request, env, 404, { error: "not_found" }, {}, true);
  }
  const meta = obj.customMetadata || {};
  const length = Number(meta.payloadBytes);
  if (meta.recordFormat !== RECORD_FORMAT || !/^[0-9]+$/.test(meta.payloadBytes || "") ||
      !SHA256.test(meta.sha256 || "") || length > MAX_JSON_BYTES ||
      obj.size !== length + RECORD_HEADER_BYTES) throw new HttpError(503, "invalid_stored_record");
  let payload = null;
  if (request.method === "GET") {
    const record = new Uint8Array(await obj.arrayBuffer());
    const header = new TextDecoder().decode(record.slice(0, RECORD_HEADER_BYTES));
    payload = record.slice(RECORD_HEADER_BYTES);
    if (!/^pitcheezy-host-record-v1:[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}\n$/.test(header) ||
        payload.length !== length || await sha256(payload) !== meta.sha256) {
      throw new HttpError(503, "invalid_stored_record");
    }
  }
  // R2 binding bypasses edge cache: Age=0 is this origin response's cache age,
  // NOT file freshness. The client must also inspect the original publication time.
  return response(request, env, 200, payload, {
    ETag: obj.httpEtag, "Content-Length": String(length),
  }, true);
}

/**
 * Emergency notice (WS-safe1): while the switch is on, every viewer-facing route answers 503 with the
 * pre-registered development notice and no-store. Uploads and the admin route stay reachable so the
 * publisher keeps writing and an operator can turn the notice off. Data already downloaded by a
 * browser is not recalled.
 */
function noticeResponse(request, env, notice, kind) {
  const extra = { "Retry-After": "60", [NOTICE_HEADER]: notice.message_id, "X-Robots-Tag": "noindex" };
  if (kind === "page") {
    const headers = new Headers({
      "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store", "CDN-Cache-Control": "no-store",
      "Date": new Date().toUTCString(), "Age": "0", "X-Content-Type-Options": "nosniff", ...extra,
    });
    return new Response(request.method === "HEAD" ? null : noticeHtml(notice.message_id), { status: 503, headers });
  }
  if (kind === "public" && request.method === "OPTIONS") return response(request, env, 204, null, {}, true);
  return json(request, env, 503, noticeJson(notice.message_id), extra, kind === "public");
}

export default {
  async fetch(request, env) {
    const url = new URL(request.url);
    const uploadRoute = url.pathname === "/_publish" || url.pathname.startsWith("/_publish/");
    const publicRoute = url.pathname === "/v1" || url.pathname.startsWith("/v1/");
    const telemetryRoute = url.pathname === "/_telemetry" || url.pathname.startsWith("/_telemetry/");
    try {
      // This foundation uses ASCII asset paths. Do not let encoded API prefixes reach SPA fallback.
      if (url.pathname.includes("%")) return json(request, env, 404, { error: "not_found" });
      if (url.pathname === "/_notice" || url.pathname.startsWith("/_notice/")) return await handleNotice(request, env);
      if (!uploadRoute) {
        // Fails closed: an unreadable switch state is a 503, never a silently served screen.
        const notice = await currentNotice(env);
        if (notice.active) {
          return noticeResponse(request, env, notice, publicRoute ? "public" : telemetryRoute ? "telemetry" : "page");
        }
      }
      if (telemetryRoute) return await handleTelemetry(request, env);
      if (uploadRoute || publicRoute) {
        const path = uploadRoute ? url.pathname.slice("/_publish".length) : url.pathname;
        const key = permittedKey(path);
        if (!key || (uploadRoute && url.search)) {
          return json(request, env, 404, { error: "not_found" }, {}, publicRoute);
        }
        return await (uploadRoute ? upload(request, env, key) : read(request, env, key));
      }
      // Never turn unknown API/private paths into the SPA's index.html.
      if (url.pathname === "/api" || url.pathname.startsWith("/api/") ||
          url.pathname.startsWith("/_") || url.pathname.split("/").some(s => s.startsWith("."))) {
        return json(request, env, 404, { error: "not_found" });
      }
      if (!["GET", "HEAD"].includes(request.method)) {
        return json(request, env, 405, { error: "method_not_allowed" }, { Allow: "GET, HEAD" });
      }
      return env.ASSETS ? await env.ASSETS.fetch(request) :
        json(request, env, 503, { error: "frontend_not_installed" });
    } catch (error) {
      // Do not reflect input, credentials, storage paths, or provider exception messages.
      const known = error instanceof HttpError || (error && typeof error.status === "number" && typeof error.message === "string" && /^[a-z_]{1,64}$/.test(error.message));
      return json(request, env, known ? error.status : 503,
        { error: known ? error.message : "storage_unavailable" },
        known ? error.headers || {} : {}, publicRoute);
    }
  },
};

/**
 * Viewer access gate (WS-access1). Our host-side gate only: a shared access code opens a stateless,
 * HMAC-signed browser session; without it every viewer-facing route answers 401. Separate from the
 * publisher token (/_publish) and the notice operator token (/_notice). An access gate is not an MLB
 * usage permission and a session is not a person identity. Codes, digests and secrets never appear in
 * responses, logs or receipts.
 */
const encoder = new TextEncoder();
const SHA256 = /^[a-f0-9]{64}$/;
const SECRET = /^[A-Za-z0-9_-]{43,128}$/;
// v2: issue time and expiry are both signed so the lifetime rule below does not depend on the current time.
const COOKIE_VALUE = /^v2\.([1-9][0-9]{0,15})\.([1-9][0-9]{0,15})\.([a-f0-9]{8})\.([a-f0-9]{16})\.([a-f0-9]{64})$/;
/** Tolerated difference between edge clocks for a cookie issued "in the future". */
export const ISSUE_CLOCK_SKEW_MS = 60000;
const MAX_BODY = 1024;
export const ACCESS_ROUTE = "/_access/v1/session";
export const ACCESS_HEADER = "X-Pitcheezy-Access";
export const MAX_SESSION_SECONDS = 604800;
export class AccessError extends Error {
  constructor(status, code, headers = {}) { super(code); this.status = status; this.headers = headers; }
}
const fail = (status, code, headers) => { throw new AccessError(status, code, headers); };
const hex = bytes => Array.from(new Uint8Array(bytes), b => b.toString(16).padStart(2, "0")).join("");
const sha256 = async bytes => hex(await crypto.subtle.digest("SHA-256", bytes));
const constantEqual = (a, b) => {
  if (typeof a !== "string" || typeof b !== "string" || a.length !== b.length) return false;
  let difference = 0;
  for (let i = 0; i < a.length; i++) difference |= a.charCodeAt(i) ^ b.charCodeAt(i);
  return difference === 0;
};

/** Returns null when the gate is off; a config object when on; throws 503 when on but misconfigured. */
export function accessConfig(env) {
  if (env.ACCESS_GATE_ENABLED !== "true") return null;
  const raw = typeof env.ACCESS_CODE_SHA256 === "string" ? env.ACCESS_CODE_SHA256 : "";
  const digests = raw ? raw.split(",").map(x => x.trim()) : [];
  const seconds = typeof env.ACCESS_SESSION_SECONDS === "string" && /^[1-9][0-9]{0,8}$/.test(env.ACCESS_SESSION_SECONDS) ?
    Number(env.ACCESS_SESSION_SECONDS) : NaN;
  if (digests.length < 1 || digests.length > 8 || digests.some(d => !SHA256.test(d)) ||
      new Set(digests).size !== digests.length || !SECRET.test(env.ACCESS_SESSION_SECRET || "") ||
      !Number.isSafeInteger(seconds) || seconds > MAX_SESSION_SECONDS) {
    fail(503, "access_not_configured");
  }
  return { digests, secret: env.ACCESS_SESSION_SECRET, seconds };
}

export function cookieName(url) { return url.protocol === "https:" ? "__Host-pz_viewer" : "pz_viewer"; }
/** Plain http is tolerated only on loopback (local rehearsal); anywhere else the session must be Secure. */
export function transportAllowed(url) {
  return url.protocol === "https:" || (url.protocol === "http:" && ["127.0.0.1", "[::1]", "localhost"].includes(url.hostname));
}

async function hmac(secret, text) {
  const key = await crypto.subtle.importKey("raw", encoder.encode(secret), { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  return hex(await crypto.subtle.sign("HMAC", key, encoder.encode(text)));
}

async function mint(config, digest, now) {
  const issued = now;
  const expires = issued + config.seconds * 1000;
  const prefix = digest.slice(0, 8);
  const nonce = hex(crypto.getRandomValues(new Uint8Array(8)));
  const mac = await hmac(config.secret, `v2|${issued}|${expires}|${prefix}|${nonce}`);
  return { value: `v2.${issued}.${expires}.${prefix}.${nonce}.${mac}`, issued, expires };
}

function readCookie(request, name) {
  const header = request.headers.get("Cookie");
  if (!header) return null;
  for (const part of header.split(";")) {
    const index = part.indexOf("=");
    if (index < 0) continue;
    if (part.slice(0, index).trim() === name) return part.slice(index + 1).trim();
  }
  return null;
}

/**
 * Valid session => { issued, expires }; otherwise null. Never throws on malformed cookies.
 * Lifetime rule (WS-access2): the cookie's whole signed lifetime (expires - issued) must fit the CURRENT
 * ACCESS_SESSION_SECONDS. This does not depend on the current time, so a cookie rejected after the setting
 * was shortened stays rejected at every later moment; comparing only the remaining lifetime let it come back.
 */
export async function verifySession(request, env, config, url, now = Date.now()) {
  const value = readCookie(request, cookieName(url));
  const match = value ? COOKIE_VALUE.exec(value) : null;
  if (!match) return null;
  const [, issuedText, expiresText, prefix, nonce, mac] = match;
  const issued = Number(issuedText), expires = Number(expiresText);
  if (!Number.isSafeInteger(issued) || !Number.isSafeInteger(expires) || expires <= issued) return null;
  if (expires - issued > config.seconds * 1000) return null;
  if (issued > now + ISSUE_CLOCK_SKEW_MS || expires <= now) return null;
  // Removing a code from the list revokes every session opened with it.
  if (!config.digests.some(d => d.slice(0, 8) === prefix)) return null;
  const expected = await hmac(config.secret, `v2|${issued}|${expires}|${prefix}|${nonce}`);
  return constantEqual(expected, mac) ? { issued, expires } : null;
}

function setCookie(url, value, maxAge) {
  const secure = url.protocol === "https:" ? "; Secure" : "";
  return `${cookieName(url)}=${value}; Path=/; Max-Age=${maxAge}; HttpOnly; SameSite=Strict${secure}`;
}

function sameOrigin(request, url) {
  const site = request.headers.get("Sec-Fetch-Site");
  if (site !== null && !["same-origin", "none"].includes(site)) fail(403, "origin_not_allowed");
  const origin = request.headers.get("Origin");
  if (origin !== null && origin !== url.origin) fail(403, "origin_not_allowed");
}

async function enforceLimit(request, env, config, now) {
  // CF-Connecting-IP is set by Cloudflare at the edge. Without it (local runtime) a shared pool applies.
  const ip = request.headers.get("CF-Connecting-IP");
  const identity = ip && ip.length <= 64 && /^[a-fA-F0-9:.]+$/.test(ip) ? ip : "unknown";
  const day = new Date(now).toISOString().slice(0, 10);
  const key = "access:" + (await hmac(config.secret, `limit|${day}|${identity}`)).slice(0, 32);
  let result;
  try {
    if (typeof env.PUBLISH_LIMITER?.limit !== "function") throw new Error();
    result = await env.PUBLISH_LIMITER.limit({ key });
  } catch { fail(503, "access_limiter_unavailable"); }
  if (!result || typeof result !== "object" || typeof result.success !== "boolean") fail(503, "access_limiter_unavailable");
  if (result.success === false) fail(429, "access_rate_limited", { "Retry-After": "60" });
}

async function readCode(request) {
  const type = (request.headers.get("Content-Type") || "").toLowerCase();
  const json = /^application\/json(?:\s*;\s*charset=utf-8)?$/.test(type);
  const form = /^application\/x-www-form-urlencoded(?:\s*;\s*charset=utf-8)?$/.test(type);
  if ((!json && !form) || request.headers.has("Content-Encoding")) fail(415, "unsupported_body");
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
  let text;
  try { text = new TextDecoder("utf-8", { fatal: true }).decode(bytes); } catch { fail(400, "invalid_body"); }
  let code;
  if (json) {
    let value;
    try { value = JSON.parse(text); } catch { fail(400, "invalid_body"); }
    if (!value || typeof value !== "object" || Array.isArray(value) || Object.keys(value).length !== 1) fail(400, "invalid_body");
    code = value.code;
  } else {
    const params = new URLSearchParams(text);
    if ([...params.keys()].length !== 1 || !params.has("code")) fail(400, "invalid_body");
    code = params.get("code");
  }
  if (typeof code !== "string" || code.length < 8 || code.length > 128 || /[\p{Cc}\s]/u.test(code)) fail(400, "invalid_body");
  return { code, form };
}

async function matchCode(config, code) {
  const digest = await sha256(encoder.encode(code));
  let matched = null;
  for (const candidate of config.digests) if (constantEqual(candidate, digest)) matched = candidate;
  return matched;
}

function reply(request, status, body, extra = {}) {
  const headers = new Headers({
    "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store",
    "CDN-Cache-Control": "no-store", "Date": new Date().toUTCString(), "Age": "0",
    "X-Content-Type-Options": "nosniff", ...extra,
  });
  return new Response(request.method === "HEAD" || status === 204 ? null : JSON.stringify(body), { status, headers });
}

/** Development login page. The wording is a placeholder awaiting approval; no scripts, no external assets. */
export function loginHtml(message = null) {
  const escape = s => s.replace(/[&<>"']/g, c => ({ "&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#39;" }[c]));
  return '<!doctype html><html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width">' +
    '<meta name="robots" content="noindex,nofollow"><title>접속 코드</title>' +
    '<style>body{font-family:system-ui,sans-serif;margin:0;padding:24px 16px;color:#1b1b1b;background:#fafafa}' +
    'main{max-width:24rem;margin:0 auto}label{display:block;margin:12px 0 4px}input,button{font:inherit;padding:8px;width:100%;box-sizing:border-box}' +
    'button{margin-top:12px}p[role=alert]{color:#8a1c1c}small{color:#555}</style></head><body><main data-access-gate="on">' +
    '<h1>접속 코드</h1><p>개발용 입력 화면(승인 전 문구): 초대받은 분만 볼 수 있습니다.</p>' +
    (message ? '<p role="alert">' + escape(message) + "</p>" : "") +
    '<form method="post" action="' + ACCESS_ROUTE + '"><label for="code">접속 코드</label>' +
    '<input id="code" name="code" type="password" autocomplete="off" required minlength="8" maxlength="128">' +
    '<button type="submit">들어가기</button></form>' +
    '<p><small>접속 제한은 이용 허가가 아니며, 이 입력은 개인을 식별하지 않습니다.</small></p></main></body></html>';
}

function page(request, status, html, extra = {}) {
  const headers = new Headers({
    "Content-Type": "text/html; charset=utf-8", "Cache-Control": "no-store", "CDN-Cache-Control": "no-store",
    "Date": new Date().toUTCString(), "Age": "0", "X-Content-Type-Options": "nosniff", "X-Robots-Tag": "noindex", ...extra,
  });
  return new Response(request.method === "HEAD" ? null : html, { status, headers });
}

/** Session route: GET/HEAD state, POST code (JSON or form), DELETE logout. Not gated itself. */
export async function handleAccess(request, env, now = Date.now()) {
  const url = new URL(request.url);
  try {
    if (url.pathname !== ACCESS_ROUTE || url.search) return reply(request, 404, { error: "not_found" });
    const config = accessConfig(env);
    if (!config) return reply(request, 404, { error: "not_found" });
    if (!transportAllowed(url)) fail(503, "https_required");
    if (["GET", "HEAD"].includes(request.method)) {
      const session = await verifySession(request, env, config, url, now);
      return reply(request, 200, { authenticated: session !== null,
        expires_at: session ? new Date(session.expires).toISOString() : null }, { Vary: "Cookie" });
    }
    if (request.method === "DELETE") {
      sameOrigin(request, url);
      return reply(request, 204, null, { "Set-Cookie": setCookie(url, "", 0) });
    }
    if (request.method !== "POST") return reply(request, 405, { error: "method_not_allowed" }, { Allow: "GET, HEAD, POST, DELETE" });
    sameOrigin(request, url);
    await enforceLimit(request, env, config, now);
    const { code, form } = await readCode(request);
    const matched = await matchCode(config, code);
    if (!matched) {
      if (form) return page(request, 401, loginHtml("접속 코드가 맞지 않습니다."), { [ACCESS_HEADER]: "denied" });
      return reply(request, 401, { error: "access_denied" }, { [ACCESS_HEADER]: "denied" });
    }
    const session = await mint(config, matched, now);
    const cookie = setCookie(url, session.value, config.seconds);
    if (form) {
      return new Response(null, { status: 303, headers: { Location: "/", "Set-Cookie": cookie, "Cache-Control": "no-store" } });
    }
    return reply(request, 200, { authenticated: true, expires_at: new Date(session.expires).toISOString() }, { "Set-Cookie": cookie });
  } catch (error) {
    const known = error instanceof AccessError;
    return reply(request, known ? error.status : 503, { error: known ? error.message : "access_unavailable" }, known ? error.headers : {});
  }
}

/**
 * Gate decision for viewer routes. Returns { gated: false } when off, { gated: true, session } when the
 * cookie is valid, and throws AccessError(401, "access_required") otherwise. Misconfiguration throws 503.
 */
export async function requireViewer(request, env, url, now = Date.now()) {
  const config = accessConfig(env);
  if (!config) return { gated: false, session: null };
  const session = await verifySession(request, env, config, url, now);
  if (!session) fail(401, "access_required", { [ACCESS_HEADER]: "required", Vary: "Cookie" });
  return { gated: true, session };
}

/** Authenticated asset bytes must not be shared by intermediaries: private caching only, keyed on the cookie. */
export function privatizeHeaders(headers) {
  const next = new Headers(headers);
  const current = next.get("Cache-Control") || "";
  const maxAge = /max-age=(\d+)/.exec(current)?.[1];
  next.set("Cache-Control", maxAge ? `private, max-age=${maxAge}` : "private, no-store");
  next.delete("CDN-Cache-Control");
  next.append("Vary", "Cookie");
  return next;
}

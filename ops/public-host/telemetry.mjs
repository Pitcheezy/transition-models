/** Opt-in first-party measurement candidate. No account, raw IP, URL or free text is stored. */
const encoder = new TextEncoder();
const UUID = /^[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89ab][a-f0-9]{3}-[a-f0-9]{12}$/;
const DAY = 86400000;
export const MAX_ACTIVE_MS = 8 * 60 * 60 * 1000;
const MAX_BODY = 1024;
const RATE_RETRY_SECONDS = 60;
export class TelemetryError extends Error {
  constructor(status, code) { super(code); this.status = status; }
}
function fail(status, code) { throw new TelemetryError(status, code); }
const exactKeys = (value, keys) => value && typeof value === "object" && !Array.isArray(value) &&
  Object.keys(value).length === keys.length && keys.every(k => Object.hasOwn(value, k));
export function validateMeasurement(value, kind) {
  const keys = kind === "session" ?
    ["v", "consent", "session_id", "game_pk", "sequence", "active_ms"] :
    ["v", "consent", "feedback_id", "game_pk", "rating", "reason"];
  if (!exactKeys(value, keys) || value.v !== 1 || value.consent !== true ||
      !Number.isSafeInteger(value.game_pk) || value.game_pk < 0 || value.game_pk > 999999999999) {
    fail(400, "invalid_measurement");
  }
  if (kind === "session") {
    if (!UUID.test(value.session_id) || !Number.isSafeInteger(value.sequence) ||
        value.sequence < 0 || value.sequence > 10000 ||
        !Number.isSafeInteger(value.active_ms) || value.active_ms < 0 ||
        value.active_ms > MAX_ACTIVE_MS || (value.sequence === 0 && value.active_ms !== 0)) {
      fail(400, "invalid_session");
    }
  } else if (!UUID.test(value.feedback_id) ||
      !["helpful", "unclear", "problem"].includes(value.rating) ||
      !["none", "recommendation", "explanation", "delay", "display", "other"].includes(value.reason)) {
    fail(400, "invalid_feedback");
  }
  return value;
}
function setting(env, key, max) {
  if (!/^[1-9][0-9]*$/.test(env[key] || "") || Number(env[key]) > max) fail(503, "collection_not_configured");
  return Number(env[key]);
}
function config(env, kind) {
  if (env[kind === "session" ? "TELEMETRY_ENABLED" : "FEEDBACK_ENABLED"] !== "true") {
    fail(503, "collection_disabled");
  }
  if (!env.TELEMETRY_DB || !env.TELEMETRY_LIMITER || !/^[A-Za-z0-9_-]{43,128}$/.test(env.TELEMETRY_RATE_SECRET || "")) {
    fail(503, "collection_not_configured");
  }
  let origin;
  try { origin = new URL(env.COLLECTION_ORIGIN); } catch { fail(503, "collection_not_configured"); }
  if (origin.protocol !== "https:" || origin.origin !== env.COLLECTION_ORIGIN) fail(503, "collection_not_configured");
  return {
    origin: origin.origin, days: setting(env, "TELEMETRY_RETAIN_DAYS", 90),
    limit: setting(env, kind === "session" ? "SESSION_WRITES_PER_DAY" : "FEEDBACK_ROWS_PER_DAY", 1000000),
  };
}
function reply(status, body, extra = {}) {
  return new Response(JSON.stringify(body), { status, headers: {
    "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store",
    "CDN-Cache-Control": "no-store", "X-Content-Type-Options": "nosniff", ...extra,
  } });
}
async function bodyJson(request) {
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
  try { return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes)); }
  catch { fail(400, "invalid_json"); }
}
async function rateLimit(request, env, day) {
  // Cloudflare supplies/overwrites this header at the edge. Do not trust an unprotected proxy.
  const ip = request.headers.get("CF-Connecting-IP");
  if (!ip || ip.length > 64 || !/^[a-fA-F0-9:.]+$/.test(ip)) fail(503, "edge_identity_unavailable");
  const key = await crypto.subtle.importKey("raw", encoder.encode(env.TELEMETRY_RATE_SECRET),
    { name: "HMAC", hash: "SHA-256" }, false, ["sign"]);
  const signature = await crypto.subtle.sign("HMAC", key, encoder.encode(day + ":" + ip));
  const digest = Array.from(new Uint8Array(signature), b => b.toString(16).padStart(2, "0")).join("");
  const decision = await env.TELEMETRY_LIMITER.limit({ key: digest });
  if (decision?.success === false) fail(429, "rate_limited");
  if (decision?.success !== true) fail(503, "collection_unavailable");
}
export async function saveMeasurement(db, value, kind, now, options) {
  const day = new Date(now).toISOString().slice(0, 10);
  const expiry = now + options.days * DAY;
  const stmt = (sql, ...params) => db.prepare(sql).bind(...params);
  const setup = stmt("INSERT INTO telemetry_budget(utc_day,kind,used) VALUES(?,?,0) ON CONFLICT DO NOTHING", day, kind);
  const budget = "COALESCE((SELECT used FROM telemetry_budget WHERE utc_day=? AND kind=?),0) < ?";
  let write; let lookup;
  if (kind === "session") {
    // Each accepted new state consumes one budget unit. Duplicate/stale retries consume none.
    write = stmt(`INSERT INTO usage_sessions
      (session_id,game_pk,utc_day,sequence,active_ms,created_ms,updated_ms,expires_ms)
      SELECT ?,?,?,0,0,?,?,? WHERE ?=0 AND ${budget}
      ON CONFLICT(session_id) DO NOTHING`,
      value.session_id,value.game_pk,day,now,now,expiry,value.sequence,day,kind,options.limit);
    lookup = stmt("SELECT * FROM usage_sessions WHERE session_id=?", value.session_id);
  } else {
    write = stmt(`INSERT INTO feedback
      (feedback_id,game_pk,utc_day,rating,reason,created_ms,expires_ms)
      SELECT ?,?,?,?,?,?,? WHERE ${budget} ON CONFLICT(feedback_id) DO NOTHING`,
      value.feedback_id,value.game_pk,day,value.rating,value.reason,now,expiry,day,kind,options.limit);
    lookup = stmt("SELECT * FROM feedback WHERE feedback_id=?", value.feedback_id);
  }
  const increment = () => stmt("UPDATE telemetry_budget SET used=used+changes() WHERE utc_day=? AND kind=?", day, kind);
  const statements = [setup,write,increment()];
  if (kind === "session") {
    statements.push(stmt(`UPDATE usage_sessions SET sequence=?,active_ms=?,updated_ms=?
      WHERE session_id=? AND game_pk=? AND utc_day=? AND expires_ms>?
      AND sequence<? AND active_ms<=? AND ?<=MIN(?,?-created_ms+1000)
      AND ${budget}`,
      value.sequence,value.active_ms,now,value.session_id,value.game_pk,day,now,
      value.sequence,value.active_ms,value.active_ms,MAX_ACTIVE_MS,now,day,kind,options.limit), increment());
  }
  statements.push(lookup, stmt("SELECT used FROM telemetry_budget WHERE utc_day=? AND kind=?", day, kind));
  // D1 batch executes sequentially in one transaction: no check-then-write quota race.
  const results = await db.batch(statements);
  const row = results.at(-2).results[0];
  const used = results.at(-1).results[0]?.used ?? 0;
  if (!row) fail(used >= options.limit ? 429 : 409, used >= options.limit ? "daily_limit" : "session_start_required");
  if (row.game_pk !== value.game_pk || row.utc_day !== day || row.expires_ms <= now) fail(409, "identity_conflict");
  if (kind === "feedback") {
    if (row.rating !== value.rating || row.reason !== value.reason) fail(409, "identity_conflict");
  } else if (row.sequence < value.sequence || row.active_ms < value.active_ms) {
    fail(used >= options.limit ? 429 : 409, used >= options.limit ? "daily_limit" : "invalid_session_update");
  } else if (row.sequence === value.sequence && row.active_ms !== value.active_ms) {
    fail(409, "identity_conflict");
  }
  return { accepted: true }; // Never expose another request's stored content or counts.
}
export async function handleTelemetry(request, env) {
  const url = new URL(request.url);
  const kind = /^\/_telemetry\/(session|feedback)$/.exec(url.pathname)?.[1];
  if (!kind || url.search) return reply(404, { error: "not_found" });
  if (request.method !== "POST") return reply(405, { error: "method_not_allowed" }, { Allow: "POST" });
  try {
    const options = config(env, kind);
    if (request.headers.get("Origin") !== options.origin ||
        !["same-origin", null].includes(request.headers.get("Sec-Fetch-Site"))) fail(403, "origin_not_allowed");
    if (request.headers.get("DNT") === "1" || request.headers.get("Sec-GPC") === "1") fail(403, "collection_opt_out");
    await rateLimit(request, env, new Date().toISOString().slice(0, 10));
    const value = validateMeasurement(await bodyJson(request), kind);
    return reply(200, await saveMeasurement(env.TELEMETRY_DB, value, kind, Date.now(), options));
  } catch (error) {
    const status = error instanceof TelemetryError ? error.status : 503;
    return reply(status, { error: error instanceof TelemetryError ? error.message : "collection_unavailable" },
      status === 429 ? { "Retry-After": String(RATE_RETRY_SECONDS) } : {});
  }
}
export async function cleanupTelemetry(env, now = Date.now()) {
  // Cleanup must continue after collection has been turned off.
  if (!env.TELEMETRY_DB) return;
  const db = env.TELEMETRY_DB;
  const day = new Date(now).toISOString().slice(0, 10);
  await db.batch([
    db.prepare("DELETE FROM usage_sessions WHERE expires_ms<=?").bind(now),
    db.prepare("DELETE FROM feedback WHERE expires_ms<=?").bind(now),
    db.prepare("DELETE FROM telemetry_budget WHERE utc_day<?").bind(day),
  ]);
}
export async function summarizeTelemetry(db, fromDay, toDay, now = Date.now()) {
  const valid = s => typeof s === "string" && /^\d{4}-\d{2}-\d{2}$/.test(s) &&
    Number.isFinite(Date.parse(s + "T00:00:00Z")) && new Date(s + "T00:00:00Z").toISOString().slice(0,10) === s;
  if (!valid(fromDay) || !valid(toDay) || fromDay > toDay ||
      Date.parse(toDay)-Date.parse(fromDay) > 90*DAY) throw new Error("invalid_report_range");
  const [sessions, feedback] = await db.batch([
    db.prepare(`SELECT utc_day,game_pk,COUNT(*) AS sessions,SUM(active_ms) AS active_ms,
      ROUND(AVG(active_ms),0) AS mean_active_ms FROM usage_sessions
      WHERE utc_day>=? AND utc_day<=? AND expires_ms>? GROUP BY utc_day,game_pk ORDER BY utc_day,game_pk`).bind(fromDay,toDay,now),
    db.prepare(`SELECT utc_day,game_pk,rating,reason,COUNT(*) AS responses FROM feedback
      WHERE utc_day>=? AND utc_day<=? AND expires_ms>? GROUP BY utc_day,game_pk,rating,reason
      ORDER BY utc_day,game_pk,rating,reason`).bind(fromDay,toDay,now),
  ]);
  return { schema: "pitcheezy-usage-summary-v1", timezone: "UTC", from_day: fromDay, to_day: toDay,
    generated_at: new Date(now).toISOString(), sessions: sessions.results, feedback: feedback.results,
    limits: "Opt-in browser sessions, not unique people; browser-reported active time, not verified attention." };
}

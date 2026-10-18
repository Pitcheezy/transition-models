/**
 * One-shot availability/freshness probe. No publisher calls or alerts sent.
 * Config is OUR monitor configuration, not a Song health-file schema.
 * WS-monitor2: when the viewer access gate is on, an optional monitor access code (read from the
 * environment variable named by `access_code_env`, never from the config file) opens a viewer session
 * through the same login route a viewer uses. No bypass route or extra credential type exists; the code
 * and the session cookie stay in memory and never reach the report, state, output or logs.
 */
import { createHash } from "node:crypto";
const sha = text => createHash("sha256").update(text).digest("hex");
const own = (o, k) => Object.prototype.hasOwnProperty.call(o, k);
const object = v => v !== null && typeof v === "object" && !Array.isArray(v);
const exact = (v, keys) => object(v) && Object.keys(v).sort().join(",") === [...keys].sort().join(",");
const int = (v, min, max) => Number.isSafeInteger(v) && v >= min && v <= max;
const STATES = new Set(["available", "partial", "failed"]);
export class MonitorError extends Error { constructor(code) { super(code); this.code = code; } }
function refuse(code) { throw new MonitorError(code); }

export const ACCESS_ROUTE = "/_access/v1/session";
const GATE_LOGIN_ANSWERS = new Set(["access_login_denied", "access_login_rate_limited", "access_login_invalid_cookie"]);
const GATE_READ_ANSWERS = new Set(["access_required", "access_session_rejected", "access_gate_without_login"]);
const ENV_NAME = /^[A-Z][A-Z0-9_]{2,63}$/;

export function validateConfig(config) {
  const keys = ["schema", "origin", "allow_loopback_http", "timeout_ms", "max_body_bytes",
    "timestamp_pointer", "timestamp_format", "max_age_seconds", "clock_skew_seconds",
    "page_sha256"];
  // Optional (WS-monitor2): the NAME of an environment variable holding a monitor access code.
  if (object(config) && own(config, "access_code_env")) keys.push("access_code_env");
  const publisherChecks = object(config) && (own(config, "health_contract") || own(config, "active_game_ids"));
  if (publisherChecks) keys.push("health_contract", "active_game_ids");
  if (!exact(config, keys) || config.schema !== "pitcheezy-host-monitor-v1") refuse("invalid_config");
  if (publisherChecks && (config.health_contract !== "pitcheezy-publish-health-v1" ||
      config.timestamp_pointer !== "/published_at" || !Array.isArray(config.active_game_ids) ||
      config.active_game_ids.length > 32 || !config.active_game_ids.every(id => int(id, 1, 999999999999)) ||
      new Set(config.active_game_ids).size !== config.active_game_ids.length)) refuse("invalid_health_contract_config");
  if (own(config, "access_code_env") && !(config.access_code_env === null ||
      (typeof config.access_code_env === "string" && ENV_NAME.test(config.access_code_env)))) refuse("invalid_access_code_env");
  let url;
  try { url = new URL(config.origin); } catch { refuse("invalid_origin"); }
  if (typeof config.origin !== "string" || url.origin !== config.origin ||
      url.username || url.password || url.search || url.hash ||
      typeof config.allow_loopback_http !== "boolean") refuse("invalid_origin");
  const loopback = url.hostname === "127.0.0.1" || url.hostname === "[::1]";
  if (url.protocol !== "https:" && !(config.allow_loopback_http && loopback && url.protocol === "http:")) {
    refuse("https_or_explicit_loopback_required");
  }
  if (!int(config.timeout_ms, 100, 30000) || !int(config.max_body_bytes, 64, 5 * 1024 * 1024) ||
      !int(config.max_age_seconds, 1, 86400) || !int(config.clock_skew_seconds, 0, 300) ||
      config.timestamp_format !== "rfc3339" ||
      !(config.page_sha256 === null || (typeof config.page_sha256 === "string" && /^[a-f0-9]{64}$/.test(config.page_sha256)))) {
    refuse("invalid_limits");
  }
  const p = config.timestamp_pointer;
  if (p !== null && (typeof p !== "string" || !p.startsWith("/") || p.length > 256 ||
      p.split("/").length > 17 || /~(?![01])/.test(p))) refuse("invalid_pointer");
  return config;
}

export function configFingerprint(config) {
  validateConfig(config);
  return sha(JSON.stringify(Object.fromEntries(Object.entries(config).sort(([a], [b]) => a.localeCompare(b)))));
}

function lookup(document, pointer) {
  let value = document;
  for (const encoded of pointer.slice(1).split("/")) {
    const key = encoded.replaceAll("~1", "/").replaceAll("~0", "~");
    if ((!object(value) && !Array.isArray(value)) || !own(value, key)) return undefined;
    if (Array.isArray(value) && !/^(0|[1-9][0-9]*)$/.test(key)) return undefined;
    value = value[key];
  }
  return value;
}

function timestamp(value) {
  if (typeof value !== "string" || value.length > 40) return NaN;
  const m = /^(\d{4})-(\d{2})-(\d{2})T(\d{2}):(\d{2}):(\d{2})(?:\.\d{1,6})?(Z|[+-]\d{2}:\d{2})$/.exec(value);
  if (!m) return NaN;
  const [y, mo, d, h, mi, se] = m.slice(1, 7).map(Number);
  if (y < 2000 || mo < 1 || mo > 12 || d < 1 ||
      d > new Date(Date.UTC(y, mo, 0)).getUTCDate() || h > 23 || mi > 59 || se > 59) return NaN;
  if (m[7] !== "Z" && (Number(m[7].slice(1, 3)) > 23 || Number(m[7].slice(4)) > 59)) return NaN;
  return Date.parse(value);
}

export function evaluateFreshness(document, config, nowMs) {
  if (config.timestamp_pointer === null) return { status: "unmeasured", age_seconds: null };
  const raw = lookup(document, config.timestamp_pointer);
  if (raw === undefined) return { status: "missing", age_seconds: null };
  const at = timestamp(raw);
  if (!Number.isFinite(at)) return { status: "invalid", age_seconds: null };
  const age = (nowMs - at) / 1000;
  if (age < -config.clock_skew_seconds) return { status: "future", age_seconds: Math.floor(age) };
  return { status: age > config.max_age_seconds ? "stale" : "fresh", age_seconds: Math.max(0, Math.floor(age)) };
}

/**
 * Optional, narrowly scoped checks for the delivered public-health v1 contract.
 * game_checks is optional: an absent active row means unconfirmed, not a malformed publisher.
 * Never reads game files or derives active games from historical game_checks entries.
 */
export function evaluatePublisherHealth(document, config, nowMs) {
  if (!own(config, "health_contract")) return null;
  const issues = new Set(), games = [];
  const sequenceValid = int(document.sequence, 0, Number.MAX_SAFE_INTEGER);
  const checksPresent = own(document, "game_checks");
  const checksValid = checksPresent && object(document.game_checks);
  if (document.schema !== config.health_contract || !sequenceValid || (checksPresent && !checksValid)) {
    issues.add("health_contract_invalid");
  }
  for (const game of config.active_game_ids) {
    const entry = { game_pk: game, status: "unconfirmed", code: "game_check_missing" };
    games.push(entry);
    if (!checksValid || !own(document.game_checks, String(game))) continue;
    const row = document.game_checks[String(game)];
    if (!object(row) || !int(row.sequence_checked, 0, Number.MAX_SAFE_INTEGER) ||
        !(row.file_sequence === null || int(row.file_sequence, 0, Number.MAX_SAFE_INTEGER)) ||
        typeof row.feed_ok !== "boolean" || !sequenceValid || row.sequence_checked > document.sequence ||
        (row.file_sequence !== null && row.file_sequence > row.sequence_checked)) {
      entry.status = "failed"; entry.code = "game_check_invalid";
      issues.add("game_check_invalid"); continue;
    }
    const freshness = evaluateFreshness(row, { ...config, timestamp_pointer: "/checked_at" }, nowMs);
    Object.assign(entry, { freshness, sequence_checked: row.sequence_checked,
      file_sequence: row.file_sequence, feed_ok: row.feed_ok });
    if (freshness.status !== "fresh") {
      entry.status = "failed"; entry.code = freshness.status === "stale" ? "game_check_stale" : "game_check_invalid";
      issues.add(entry.code);
    }
    if (!row.feed_ok) {
      entry.status = "failed"; entry.code = "game_check_feed_failed"; issues.add("game_check_feed_failed");
    }
    if (entry.status === "failed") continue;
    entry.status = row.file_sequence === null ? "unconfirmed" : "confirmed";
    entry.code = row.file_sequence === null ? "game_file_withdrawn" : null;
  }
  const freshness = evaluateFreshness(document, config, nowMs);
  return { contract: config.health_contract, scope: "configured_active_games_only",
    status: issues.size || freshness.status !== "fresh" ? "failed" :
      games.some(g => g.status === "unconfirmed") ? "unconfirmed" : "confirmed",
    sequence: sequenceValid ? document.sequence : null, issues: [...issues], games };
}

function timingHeaders(headers, nowMs, skew) {
  const date = headers.get("Date");
  const age = headers.get("Age");
  if (!date || !Number.isFinite(Date.parse(date)) || new Date(date).toUTCString() !== date) return "date_invalid";
  if (age === null || !/^(0|[1-9][0-9]{0,8})$/.test(age)) return "age_invalid";
  // Age describes cache residence, not publisher freshness. Do not substitute it for publish time.
  if (Math.abs(Date.parse(date) + Number(age) * 1000 - nowMs) > skew * 1000 + 1000) return "clock_mismatch";
  return "valid";
}

/** Same shape the gate accepts; checked before any request so a bad value never leaves the process. */
export function validAccessCode(code) {
  return typeof code === "string" && code.length >= 8 && code.length <= 128 && !/[\p{Cc}\s]/u.test(code);
}

/**
 * Opens a viewer session through the public login route. Returns { session: "established", cookie } or
 * { session: "gate_off", cookie: null } (the route is hidden while the gate is off); throws a fixed code.
 */
export async function accessLogin(config, code, fetchImpl) {
  const controller = new AbortController();
  let timer;
  const work = async () => {
    let response;
    try {
      response = await fetchImpl(config.origin + ACCESS_ROUTE, {
        method: "POST", redirect: "manual", credentials: "omit", referrerPolicy: "no-referrer", cache: "no-store",
        signal: controller.signal, headers: { "Content-Type": "application/json", Accept: "application/json" },
        body: JSON.stringify({ code }),
      });
    } catch { refuse("access_login_network_error"); }
    response.body?.cancel().catch(() => {}); // the session travels in Set-Cookie; the body is not needed
    if (response.status === 404) return { session: "gate_off", cookie: null };
    if (response.status === 401) refuse("access_login_denied");
    if (response.status === 429) refuse("access_login_rate_limited");
    if (response.status === 503) refuse("access_login_unavailable");
    if (response.status !== 200) refuse("access_login_http_error");
    const lines = typeof response.headers.getSetCookie === "function" ? response.headers.getSetCookie() :
      [response.headers.get("Set-Cookie")].filter(Boolean);
    const name = new URL(config.origin).protocol === "https:" ? "__Host-pz_viewer" : "pz_viewer";
    for (const line of lines) {
      const pair = line.split(";")[0];
      const index = pair.indexOf("=");
      if (index > 0 && pair.slice(0, index) === name && /^[A-Za-z0-9._-]{1,512}$/.test(pair.slice(index + 1))) {
        return { session: "established", cookie: pair };
      }
    }
    refuse("access_login_invalid_cookie");
  };
  try {
    return await Promise.race([
      work(),
      new Promise((_, reject) => { timer = setTimeout(() => {
        controller.abort(); reject(new MonitorError("access_login_timeout"));
      }, config.timeout_ms); }),
    ]);
  } catch (error) {
    if (error instanceof MonitorError) throw error;
    refuse("access_login_error");
  } finally { clearTimeout(timer); controller.abort(); }
}

async function fetchBounded(url, config, fetchImpl, cookie = null, accessConfigured = false) {
  const controller = new AbortController();
  let timer;
  const work = async () => {
    let response;
    try {
      response = await fetchImpl(url, {
        method: "GET", redirect: "manual", credentials: "omit",
        referrerPolicy: "no-referrer", cache: "no-store", signal: controller.signal,
        headers: { Accept: url.endsWith(".json") ? "application/json" : "text/html", ...(cookie ? { Cookie: cookie } : {}) },
      });
    } catch { refuse("network_error"); }
    if (response.status !== 200) {
      response.body?.cancel().catch(() => {});
      // An intentional notice (WS-safe1) is still unavailable to viewers, but it must not be mistaken
      // for a publisher or storage outage: the host marks it with a header, never by body text.
      const notice = response.headers.get("X-Pitcheezy-Notice");
      if (response.status === 503 && notice && /^[a-z_]{1,40}$/.test(notice)) refuse("notice_active");
      // The viewer access gate (WS-access1) answers 401 to a probe without a session by design; with a
      // session from our own login (WS-monitor2) the same answer means the gate refused that session.
      // A configured monitor that found no login route (404 = "gate off") yet meets the gate is inconsistent:
      // that is ours to investigate, never the info-only "gate seen without a monitor code".
      if (response.status === 401 && response.headers.get("X-Pitcheezy-Access") === "required") {
        refuse(cookie ? "access_session_rejected" : accessConfigured ? "access_gate_without_login" : "access_required");
      }
      refuse(response.status >= 300 && response.status < 400 ? "redirect" :
        response.status === 404 ? "missing" : "http_error");
    }
    const declared = response.headers.get("Content-Length");
    if (declared !== null && (!/^[0-9]+$/.test(declared) || Number(declared) > config.max_body_bytes)) {
      controller.abort(); refuse("body_too_large");
    }
    const reader = response.body?.getReader();
    if (!reader) refuse("empty_body");
    const chunks = [];
    let length = 0;
    try {
      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        length += value.byteLength;
        if (length > config.max_body_bytes) { controller.abort(); refuse("body_too_large"); }
        chunks.push(Buffer.from(value));
      }
    } finally { reader.releaseLock(); }
    return { headers: response.headers, bytes: Buffer.concat(chunks) };
  };
  try {
    return await Promise.race([
      work(),
      new Promise((_, reject) => { timer = setTimeout(() => {
        controller.abort(); reject(new MonitorError("timeout"));
      }, config.timeout_ms); }),
    ]);
  } catch (error) {
    if (error instanceof MonitorError) throw error;
    refuse("body_error");
  } finally { clearTimeout(timer); controller.abort(); }
}

export async function probe(config, { fetchImpl = fetch, now = () => Date.now(), accessCode = null } = {}) {
  validateConfig(config);
  const accessConfigured = typeof config.access_code_env === "string";
  if (accessConfigured && !validAccessCode(accessCode)) refuse(accessCode ? "access_code_invalid" : "access_code_unavailable");
  const started = now();
  let access = { session: accessConfigured ? null : "not_configured", cookie: null, code: null };
  if (accessConfigured) {
    try { access = { ...(await accessLogin(config, accessCode, fetchImpl)), code: null }; }
    catch (error) { access = { session: "login_failed", cookie: null, code: error instanceof MonitorError ? error.code : "access_login_error" }; }
  }
  const check = async (path, kind) => {
    const begin = performance.now();
    // Without a session nothing behind the gate can be read; do not mislabel that as a page outage.
    if (access.session === "login_failed") return { status: "skipped", code: "access_login_failed", elapsed_ms: 0 };
    try {
      const result = await fetchBounded(config.origin + path, config, fetchImpl, access.cookie, accessConfigured);
      const mime = result.headers.get("Content-Type")?.split(";")[0].trim().toLowerCase();
      const expected = kind === "page" ? "text/html" : "application/json";
      if (mime !== expected) refuse("content_type");
      let text;
      try { text = new TextDecoder("utf-8", { fatal: true }).decode(result.bytes); }
      catch { refuse("invalid_utf8"); }
      if (kind === "page") {
        if (!/<!doctype\s+html[\s>]/i.test(text) || !/<html[\s>]/i.test(text)) refuse("not_html_document");
        if (config.page_sha256 !== null && sha(result.bytes) !== config.page_sha256) refuse("page_hash_mismatch");
        return { status: "ok", code: null, elapsed_ms: Math.round(performance.now() - begin) };
      }
      let document;
      try { document = JSON.parse(text); } catch { refuse("invalid_json"); }
      if (!object(document)) refuse("invalid_json_object");
      const end = now();
      const headerStatus = timingHeaders(result.headers, end, config.clock_skew_seconds);
      const freshness = evaluateFreshness(document, config, end);
      const publisher = evaluatePublisherHealth(document, config, end);
      return { status: "ok", code: null, headers: headerStatus, freshness,
        ...(publisher ? { publisher } : {}), elapsed_ms: Math.round(performance.now() - begin) };
    } catch (error) {
      return { status: "error", code: error instanceof MonitorError ? error.code : "probe_error",
        elapsed_ms: Math.round(performance.now() - begin) };
    }
  };
  const [page, health] = await Promise.all([check("/", "page"), check("/v1/health.json", "health")]);
  const end = now();
  if (!Number.isSafeInteger(started) || !Number.isSafeInteger(end) || end < started) refuse("clock_error");
  const issues = [];
  if (access.session === "login_failed") issues.push(access.code);
  if (page.status === "error") issues.push("page_" + page.code);
  if (health.status === "error") issues.push("health_" + health.code);
  else if (health.status === "ok") {
    if (health.headers !== "valid") issues.push("health_" + health.headers);
    if (!["fresh", "unmeasured"].includes(health.freshness.status)) issues.push("freshness_" + health.freshness.status);
    // At most four fixed publisher categories, deduplicated across up to 32 games.
    // Together with page/header/freshness this stays below the existing eight-issue state bound.
    if (health.publisher) issues.push(...health.publisher.issues);
  }
  const status = issues.length ? "failed" :
    health.freshness.status === "unmeasured" || health.publisher?.status === "unconfirmed" ? "partial" : "available";
  return {
    schema: "pitcheezy-host-probe-v1", config_sha256: configFingerprint(config),
    observed_at_ms: end, status, issues, page, health,
    // Viewer-facing unavailability caused by the operator notice, distinguished from outages for routing.
    notice_active: page.code === "notice_active" || health.code === "notice_active",
    // True only when this probe saw the gate itself answer: a session opened, a login answered by the gate
    // (refused, rate-limited, or 200 without a usable cookie), or a read refused by the gate. Network errors,
    // timeouts and other HTTP answers prove nothing about the gate and leave it false.
    access_gate_active: access.session === "established" || GATE_LOGIN_ANSWERS.has(access.code) ||
      [page.code, health.code].some(code => GATE_READ_ANSWERS.has(code)),
    // not_configured | established | gate_off | login_failed. Never the code or the cookie.
    access_session: access.session,
    // This is the publisher's reported checks, not independent validation of the MLB feed/model.
    semantic_health: health.publisher ? ({ confirmed: "publisher_checks_passed",
      unconfirmed: "publisher_checks_incomplete", failed: "publisher_checks_failed" })[health.publisher.status] : "unmeasured",
    javascript_execution: "unmeasured",
  };
}

export function initialState(config) {
  return { schema: "pitcheezy-host-monitor-state-v1", config_sha256: configFingerprint(config),
    last_observed_ms: null, failures: 0, successes: 0, incident: null, events: [], dropped_events: 0 };
}

export function validateState(state, config) {
  if (!exact(state, ["schema", "config_sha256", "last_observed_ms", "failures", "successes",
    "incident", "events", "dropped_events"]) || state.schema !== "pitcheezy-host-monitor-state-v1" ||
    !/^[a-f0-9]{64}$/.test(state.config_sha256) ||
    !(state.last_observed_ms === null || int(state.last_observed_ms, 0, Number.MAX_SAFE_INTEGER)) ||
    !int(state.failures, 0, 2) || !int(state.successes, 0, 2) ||
    !int(state.dropped_events, 0, Number.MAX_SAFE_INTEGER) || !Array.isArray(state.events) ||
    state.events.length > 100) refuse("state_invalid");
  if (state.config_sha256 !== configFingerprint(config)) refuse("config_changed_use_new_state");
  const eventValid = e => exact(e, ["id", "kind", "at_ms", "issues"]) &&
    typeof e.id === "string" && /^[a-f0-9]{64}$/.test(e.id) &&
    ["opened", "recovered"].includes(e.kind) && int(e.at_ms, 0, Number.MAX_SAFE_INTEGER) &&
    Array.isArray(e.issues) && e.issues.length <= 8 &&
    e.issues.every(x => typeof x === "string" && /^[a-z_]{1,80}$/.test(x));
  if (!state.events.every(eventValid) || !(state.incident === null ||
    (eventValid(state.incident) && state.incident.kind === "opened"))) refuse("state_invalid");
  return state;
}

export function advanceState(state, report, config) {
  validateState(state, config);
  if (!object(report) || report.schema !== "pitcheezy-host-probe-v1" ||
      report.config_sha256 !== state.config_sha256 || !STATES.has(report.status) ||
      !int(report.observed_at_ms, 0, Number.MAX_SAFE_INTEGER)) refuse("invalid_report");
  if (state.last_observed_ms !== null && report.observed_at_ms <= state.last_observed_ms) refuse("clock_error");
  const next = structuredClone(state);
  next.last_observed_ms = report.observed_at_ms;
  let event = null;
  if (report.status === "failed") {
    next.failures = Math.min(2, next.failures + 1); next.successes = 0;
    if (!next.incident && next.failures === 2) {
      event = { id: sha(state.config_sha256 + ":" + report.observed_at_ms), kind: "opened",
        at_ms: report.observed_at_ms, issues: [...report.issues] };
      next.incident = event;
    }
  } else if (report.status === "partial" && report.health?.publisher?.status === "unconfirmed") {
    // Missing/withdrawn active-game evidence cannot resolve an already recorded incident.
    // Break consecutive counts but retain the incident; legacy timestamp-only partial is unchanged.
    next.successes = 0; next.failures = 0;
  } else {
    next.successes = Math.min(2, next.successes + 1); next.failures = 0;
    if (next.incident && next.successes === 2) {
      event = { id: next.incident.id, kind: "recovered", at_ms: report.observed_at_ms, issues: [] };
      next.incident = null;
    }
  }
  if (event) {
    next.events.push(event);
    if (next.events.length > 100) { next.events.shift(); next.dropped_events += 1; }
  }
  validateState(next, config);
  return { state: next, event };
}

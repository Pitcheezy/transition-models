/**
 * One-shot availability/freshness probe. No publisher calls, credentials, or alerts sent.
 * Config is OUR monitor configuration, not a Song health-file schema.
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

export function validateConfig(config) {
  const keys = ["schema", "origin", "allow_loopback_http", "timeout_ms", "max_body_bytes",
    "timestamp_pointer", "timestamp_format", "max_age_seconds", "clock_skew_seconds",
    "page_sha256"];
  if (!exact(config, keys) || config.schema !== "pitcheezy-host-monitor-v1") refuse("invalid_config");
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

function timingHeaders(headers, nowMs, skew) {
  const date = headers.get("Date");
  const age = headers.get("Age");
  if (!date || !Number.isFinite(Date.parse(date)) || new Date(date).toUTCString() !== date) return "date_invalid";
  if (age === null || !/^(0|[1-9][0-9]{0,8})$/.test(age)) return "age_invalid";
  // Age describes cache residence, not publisher freshness. Do not substitute it for publish time.
  if (Math.abs(Date.parse(date) + Number(age) * 1000 - nowMs) > skew * 1000 + 1000) return "clock_mismatch";
  return "valid";
}

async function fetchBounded(url, config, fetchImpl) {
  const controller = new AbortController();
  let timer;
  const work = async () => {
    let response;
    try {
      response = await fetchImpl(url, {
        method: "GET", redirect: "manual", credentials: "omit",
        referrerPolicy: "no-referrer", cache: "no-store", signal: controller.signal,
        headers: { Accept: url.endsWith(".json") ? "application/json" : "text/html" },
      });
    } catch { refuse("network_error"); }
    if (response.status !== 200) {
      response.body?.cancel().catch(() => {});
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

export async function probe(config, { fetchImpl = fetch, now = () => Date.now() } = {}) {
  validateConfig(config);
  const started = now();
  const check = async (path, kind) => {
    const begin = performance.now();
    try {
      const result = await fetchBounded(config.origin + path, config, fetchImpl);
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
      return { status: "ok", code: null, headers: headerStatus, freshness,
        elapsed_ms: Math.round(performance.now() - begin) };
    } catch (error) {
      return { status: "error", code: error instanceof MonitorError ? error.code : "probe_error",
        elapsed_ms: Math.round(performance.now() - begin) };
    }
  };
  const [page, health] = await Promise.all([check("/", "page"), check("/v1/health.json", "health")]);
  const end = now();
  if (!Number.isSafeInteger(started) || !Number.isSafeInteger(end) || end < started) refuse("clock_error");
  const issues = [];
  if (page.status !== "ok") issues.push("page_" + page.code);
  if (health.status !== "ok") issues.push("health_" + health.code);
  else {
    if (health.headers !== "valid") issues.push("health_" + health.headers);
    if (!["fresh", "unmeasured"].includes(health.freshness.status)) issues.push("freshness_" + health.freshness.status);
  }
  const status = issues.length ? "failed" :
    health.freshness.status === "unmeasured" ? "partial" : "available";
  return {
    schema: "pitcheezy-host-probe-v1", config_sha256: configFingerprint(config),
    observed_at_ms: end, status, issues, page, health,
    semantic_health: "unmeasured", javascript_execution: "unmeasured",
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

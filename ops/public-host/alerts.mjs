/**
 * Two-recipient alert candidate (WS-alert1). Consumes monitor events (monitor.mjs state) and hands each
 * one to both sides through a transport adapter. Only a mock transport exists here: a mock "ok" is a
 * local acknowledgement, never a confirmed delivery to a person. Contacts, channels and sending approval
 * are human decisions (WS-human1); this module stores no addresses.
 */
const object = v => v !== null && typeof v === "object" && !Array.isArray(v);
const exact = (v, keys) => object(v) && Object.keys(v).sort().join(",") === [...keys].sort().join(",");
const int = (v, min, max) => Number.isSafeInteger(v) && v >= min && v <= max;
export class AlertError extends Error { constructor(code) { super(code); this.code = code; } }
const refuse = code => { throw new AlertError(code); };

export const RECIPIENTS = Object.freeze(["song", "ours"]);
/** Categories that ask someone to act. A change of an open incident INTO one of these is announced (WS-alert2). */
export const ACTIONABLE = Object.freeze(new Set(["publish_stalled", "host_error", "unclassified"]));
export const PRUNE_AFTER_DAYS = 30;
/** Which side looks first. Mac/publisher causes -> Song, hosting causes -> ours, mixed/unknown -> both. */
export const CATEGORIES = Object.freeze({
  publish_stalled: { first_responder: "song", severity: "incident" },
  host_error: { first_responder: "ours", severity: "incident" },
  unclassified: { first_responder: "both", severity: "incident" },
  notice_active: { first_responder: "none", severity: "info" },
  access_gate: { first_responder: "none", severity: "info" },
  recovered: { first_responder: "none", severity: "info" },
});
const PUBLISHER_ISSUES = new Set(["freshness_stale", "freshness_future", "freshness_missing", "freshness_invalid",
  "health_missing", "health_invalid_json", "health_invalid_json_object", "health_invalid_utf8"]);
const HOST_ISSUES = new Set(["page_http_error", "page_network_error", "page_timeout", "page_redirect", "page_missing",
  "page_body_too_large", "page_body_error", "page_empty_body", "page_content_type", "page_not_html_document",
  "page_page_hash_mismatch", "page_invalid_utf8", "page_probe_error", "health_http_error", "health_network_error",
  "health_timeout", "health_redirect", "health_body_too_large", "health_body_error", "health_empty_body",
  "health_content_type", "health_probe_error", "health_date_invalid", "health_age_invalid", "health_clock_mismatch",
  // WS-monitor2: our monitor could not open or keep a viewer session; our side (gate/monitor code) looks first.
  "access_login_denied", "access_login_rate_limited", "access_login_unavailable", "access_login_http_error",
  "access_login_network_error", "access_login_timeout", "access_login_invalid_cookie", "access_login_error",
  "page_access_session_rejected", "health_access_session_rejected",
  "page_access_gate_without_login", "health_access_gate_without_login"]);

/** Maps a monitor event (opened/recovered with issues) to an alert category. Pure; no I/O. */
export function classifyEvent(event) {
  if (!exact(event, ["id", "kind", "at_ms", "issues"]) || !["opened", "recovered"].includes(event.kind) ||
      typeof event.id !== "string" || !/^[a-f0-9]{64}$/.test(event.id) || !int(event.at_ms, 0, Number.MAX_SAFE_INTEGER) ||
      !Array.isArray(event.issues) || event.issues.length > 8 || !event.issues.every(i => typeof i === "string" && /^[a-z_]{1,80}$/.test(i))) refuse("invalid_event");
  if (event.kind === "recovered") return "recovered";
  const issues = new Set(event.issues);
  if (issues.size === 0) return "unclassified";
  if ([...issues].every(i => i.endsWith("_notice_active"))) return "notice_active";
  if ([...issues].every(i => i.endsWith("_access_required"))) return "access_gate";
  const publisher = [...issues].some(i => PUBLISHER_ISSUES.has(i));
  const host = [...issues].some(i => HOST_ISSUES.has(i));
  if (publisher && !host) return "publish_stalled";
  if (host && !publisher) return "host_error";
  return "unclassified";
}

export function validateAlertConfig(config) {
  if (!exact(config, ["schema", "transport", "recipients", "max_attempts", "remind_after_minutes"]) ||
      config.schema !== "pitcheezy-host-alerts-v1") refuse("invalid_config");
  if (!["mock"].includes(config.transport)) refuse("unsupported_transport");
  if (!Array.isArray(config.recipients) || config.recipients.length !== 2 ||
      config.recipients.map(r => r?.id).sort().join(",") !== "ours,song" ||
      !config.recipients.every(r => exact(r, ["id", "label"]) && typeof r.label === "string" &&
        /^[A-Za-z0-9 _.-]{1,40}$/.test(r.label))) refuse("invalid_recipients");
  if (!int(config.max_attempts, 1, 5) || !int(config.remind_after_minutes, 0, 1440)) refuse("invalid_limits");
  return config;
}

const STATE_V1 = "pitcheezy-host-alert-state-v1";
const STATE_V2 = "pitcheezy-host-alert-state-v2";
export const STATE_SCHEMA = "pitcheezy-host-alert-state-v3";
export const MAX_DELIVERY_ROWS = 4096;
export const MAX_ALERT_STATE_BYTES = 8 * 1024 * 1024;
export const MAX_ALERT_STATE_READ_BYTES = MAX_ALERT_STATE_BYTES;
export const MAX_V1_STATE_BYTES = 1024 * 1024;
export const MAX_PENDING_DELIVERIES = 2048;
const MAX_MONITOR_EVENTS = 100;
const DELIVERY_KEY = /^([a-f0-9]{64}):(opened|recovered|reminder:[0-9]{1,6}|reclassified:[0-9]{1,4}:[a-z_]{1,40}):(song|ours)$/;
const CATEGORY_NAMES = new Set(Object.keys(CATEGORIES));
const ISSUE = i => typeof i === "string" && /^[a-z_]{1,80}$/.test(i);
const MAX_INCIDENT_MEMORY = 16;
const MAX_V1_PENDING = 200;
// The monitor retains 100 events for two recipients; v2 also queues the current
// re-classification and reminder for both recipients.
const MAX_V2_PENDING = MAX_V1_PENDING + 2 * RECIPIENTS.length;

export function initialAlertState() {
  return { schema: STATE_SCHEMA, deliveries: {}, pending: [], mock_only: true, incidents: {},
    history_pruned_through_ms: null, history_complete_from_ms: null, last_dispatch_ms: null };
}
const incidentValid = v => exact(v, ["opened_category", "announced", "announced_issues", "seq", "candidate", "candidate_runs", "previous", "last_report_ms"]) &&
  (v.previous === null || CATEGORY_NAMES.has(v.previous)) &&
  CATEGORY_NAMES.has(v.opened_category) && CATEGORY_NAMES.has(v.announced) && Array.isArray(v.announced_issues) &&
  v.announced_issues.length <= 8 && v.announced_issues.every(ISSUE) && int(v.seq, 0, 9999) &&
  (v.candidate === null || CATEGORY_NAMES.has(v.candidate)) && int(v.candidate_runs, 0, 2) &&
  (v.last_report_ms === null || int(v.last_report_ms, 0, Number.MAX_SAFE_INTEGER));

/** Reads v1/v2 histories without claiming their earlier retention coverage, and returns a v3 state. */
export function validateAlertState(state) {
  const common = ["schema", "deliveries", "pending", "mock_only"];
  const v1 = exact(state, common) && state.schema === STATE_V1;
  const v2 = exact(state, [...common, "incidents"]) && state.schema === STATE_V2;
  const v3 = exact(state, [...common, "incidents", "history_pruned_through_ms", "history_complete_from_ms", "last_dispatch_ms"]) &&
    state.schema === STATE_SCHEMA;
  if ((!v1 && !v2 && !v3) || !object(state.deliveries) || !Array.isArray(state.pending) || state.mock_only !== true) refuse("state_invalid");
  if (v3 && ![state.history_pruned_through_ms, state.history_complete_from_ms, state.last_dispatch_ms]
    .every(ms => ms === null || int(ms, 0, Number.MAX_SAFE_INTEGER))) refuse("state_invalid");
  const statuses = v1 ? ["acknowledged", "undelivered"] : ["acknowledged", "undelivered", "abandoned"];
  for (const [key, row] of Object.entries(state.deliveries)) {
    if (!DELIVERY_KEY.test(key) || (v1 && key.includes(":reclassified:")) ||
        !exact(row, ["status", "attempts", "last_attempt_ms", "acknowledged_by_transport"]) ||
        !statuses.includes(row.status) || !int(row.attempts, 0, 100) ||
        !int(row.last_attempt_ms, 0, Number.MAX_SAFE_INTEGER) || typeof row.acknowledged_by_transport !== "boolean") refuse("state_invalid");
  }
  if (state.pending.length > (v1 ? MAX_V1_PENDING : v2 ? MAX_V2_PENDING : MAX_PENDING_DELIVERIES)) refuse("state_invalid");
  const pending = state.pending.map(canonicalPending);
  if (new Set(pending.map(p => p.key)).size !== pending.length ||
      pending.some(p => !state.deliveries[p.key])) refuse("state_invalid");
  if (!v1 && (!object(state.incidents) || Object.keys(state.incidents).length > MAX_INCIDENT_MEMORY ||
      !Object.entries(state.incidents).every(([id, v]) => /^[a-f0-9]{64}$/.test(id) && incidentValid(v)))) refuse("state_invalid");
  return v3 ? { ...state, pending } : { schema: STATE_SCHEMA, deliveries: state.deliveries, pending, mock_only: true,
    incidents: v1 ? {} : state.incidents, history_pruned_through_ms: null, history_complete_from_ms: null, last_dispatch_ms: null };
}

/** Every persisted output must be readable by the next invocation. */
export function serializeAlertState(state, { maxBytes = MAX_ALERT_STATE_BYTES } = {}) {
  const serialized = JSON.stringify(state, null, 2) + "\n";
  if (new TextEncoder().encode(serialized).byteLength > maxBytes) refuse("state_capacity_exceeded");
  return serialized;
}

function compactAlertState(state, { listed, openId, config, now, receipt }) {
  const protectedKeys = new Set(state.pending.map(p => p.key));
  // Retain a recovery's opening outcome even after the monitor evicts both events.
  for (const item of state.pending) {
    const [, id, kind, recipient] = DELIVERY_KEY.exec(item.key);
    if (kind === "recovered") protectedKeys.add(`${id}:opened:${recipient}`);
  }
  const latestReminders = new Map();
  for (const [k, row] of Object.entries(state.deliveries)) {
    // Preserve unresolved delivery evidence even if its monitor event has been
    // evicted. Legacy rows whose message was already lost cannot be reconstructed.
    if (row.status === "undelivered" && row.attempts < config.max_attempts) protectedKeys.add(k);
    const [, id, kind, recipient] = DELIVERY_KEY.exec(k);
    if (["opened", "recovered"].includes(kind) && listed.has(`${id}:${kind}`)) protectedKeys.add(k);
    if (id === openId && kind.startsWith(`reclassified:${state.incidents[openId]?.seq}:`)) protectedKeys.add(k);
    if (id === openId && kind.startsWith("reminder:")) {
      const slot = Number(kind.slice(9));
      if (!latestReminders.has(recipient) || slot > latestReminders.get(recipient).slot) latestReminders.set(recipient, { key: k, slot });
    }
  }
  for (const { key } of latestReminders.values()) protectedKeys.add(key);
  const drop = k => {
    const row = state.deliveries[k];
    state.history_pruned_through_ms = Math.max(state.history_pruned_through_ms ?? 0, row.last_attempt_ms);
    delete state.deliveries[k]; receipt.pruned++;
  };
  for (const [k, row] of Object.entries(state.deliveries)) {
    const settled = row.status === "acknowledged" || row.status === "abandoned" || row.attempts >= config.max_attempts;
    if (!protectedKeys.has(k) && settled && now - row.last_attempt_ms > PRUNE_AFTER_DAYS * 86400000) drop(k);
  }
  const oldest = Object.entries(state.deliveries).filter(([k]) => !protectedKeys.has(k))
    .sort(([ka, a], [kb, b]) => a.last_attempt_ms - b.last_attempt_ms || ka.localeCompare(kb));
  let index = 0;
  const excess = Math.max(0, Object.keys(state.deliveries).length - MAX_DELIVERY_ROWS);
  for (; index < excess && index < oldest.length; index++) drop(oldest[index][0]);
  // Normally the row bound is sufficient. Large valid pending messages may
  // need extra history removed; pending items and deduplication anchors stay.
  while (true) {
    try { serializeAlertState(state); break; }
    catch (error) {
      if (error.code !== "state_capacity_exceeded" || index >= oldest.length) throw error;
      const bytes = new TextEncoder().encode(JSON.stringify(state, null, 2) + "\n").byteLength;
      let removed = 0;
      while (index < oldest.length && removed < bytes - MAX_ALERT_STATE_BYTES) {
        const [k, row] = oldest[index++];
        removed += new TextEncoder().encode(JSON.stringify({ [k]: row }, null, 2)).byteLength;
        drop(k);
      }
    }
  }
  if (Object.keys(state.deliveries).length > MAX_DELIVERY_ROWS) refuse("state_capacity_exceeded");
}

/**
 * Message text uses placeholders awaiting human-approved wording; it never includes URLs, tokens or addresses.
 * `observed_at` is when the incident opened; `cause_observed_at`/`issues` describe the cause being announced
 * (they differ for re-classifications and reminders after a re-classification).
 */
export function buildMessage(event, category, recipient, { reminder = 0, reclassifiedFrom = null, causeIssues = null, causeObservedMs = null, kind = null, announcement = null } = {}) {
  const meta = CATEGORIES[category];
  const issues = causeIssues ?? event.issues;
  const responsibility = meta.first_responder === "both" ? "양쪽이 함께 조사"
    : meta.first_responder === "song" ? "Song 쪽(맥미니/발행기) 우선 조사, 우리 쪽은 호스팅 상태 확인"
    : meta.first_responder === "ours" ? "우리 쪽(호스팅) 우선 조사, Song 쪽은 발행기 상태 확인"
    : "조치 불필요(정보)";
  const eventKind = kind ?? event.kind;
  return {
    schema: "pitcheezy-host-alert-message-v2", recipient, category, severity: meta.severity,
    first_responder: meta.first_responder, incident_id: event.id, event_kind: eventKind, reminder,
    observed_at: new Date(event.at_ms).toISOString(),
    cause_observed_at: causeObservedMs === null ? null : new Date(causeObservedMs).toISOString(),
    issues: [...issues], reclassified_from: reclassifiedFrom, announcement,
    text: `[개발용 문구] ${category} (${eventKind}${reminder ? ", 재알림 " + reminder : ""}${reclassifiedFrom ? ", 원인 재분류: " + reclassifiedFrom + " → " + category : ""}): ${responsibility}. issues=${issues.join(",") || "none"}`,
    delivery_confirmed: false,
  };
}

/** Validate identity and bounded source fields, then regenerate text instead of trusting stored transport payloads. */
function canonicalPending(item) {
  if (!exact(item, ["key", "message"]) || typeof item.key !== "string" || !DELIVERY_KEY.test(item.key) || !object(item.message)) refuse("state_invalid");
  const [, id, kind, recipient] = DELIVERY_KEY.exec(item.key), m = item.message;
  const at = typeof m.observed_at === "string" && m.observed_at.length <= 30 ? Date.parse(m.observed_at) : NaN;
  if (!["pitcheezy-host-alert-message-v1", "pitcheezy-host-alert-message-v2"].includes(m.schema) ||
      m.incident_id !== id || m.recipient !== recipient || !Number.isSafeInteger(at) || at < 0 ||
      !Array.isArray(m.issues) || m.issues.length > 8 || !m.issues.every(ISSUE) || !CATEGORY_NAMES.has(m.category)) refuse("state_invalid");
  const event = { id, kind: kind === "recovered" ? "recovered" : "opened", at_ms: at, issues: [...m.issues] };
  let options = {};
  if (["opened", "recovered"].includes(kind)) {
    if (m.event_kind !== kind || (m.reminder ?? 0) !== 0 || classifyEvent(event) !== m.category) refuse("state_invalid");
  } else if (kind.startsWith("reminder:")) {
    const reminder = Number(kind.slice(9));
    if (m.event_kind !== "opened" || !int(reminder, 1, 999999) || m.reminder !== reminder) refuse("state_invalid");
    options = { reminder, causeIssues: m.issues };
  } else {
    const [, number, category] = kind.split(":");
    const announcement = Number(number), causeAt = typeof m.cause_observed_at === "string" && m.cause_observed_at.length <= 30 ? Date.parse(m.cause_observed_at) : NaN;
    if (m.event_kind !== "reclassified" || !int(announcement, 1, 9999) || m.announcement !== announcement ||
        m.category !== category || !ACTIONABLE.has(category) || !CATEGORY_NAMES.has(m.reclassified_from) ||
        !Number.isSafeInteger(causeAt) || causeAt < at) refuse("state_invalid");
    options = { kind: "reclassified", announcement, reclassifiedFrom: m.reclassified_from, causeIssues: m.issues, causeObservedMs: causeAt };
  }
  return { key: item.key, message: buildMessage(event, m.category, recipient, options) };
}

/** Mock transport: records messages, can be told to fail N times per recipient. Never contacts anything. */
export function mockTransport({ failBeforeSuccess = {} } = {}) {
  const sent = []; const remaining = { ...failBeforeSuccess };
  return {
    name: "mock", sent,
    async deliver(message) {
      if ((remaining[message.recipient] || 0) > 0) { remaining[message.recipient]--; return { ok: false, code: "mock_transport_failure" }; }
      sent.push(message); return { ok: true, code: "mock_acknowledged" };
    },
  };
}

/**
 * Processes monitor events not yet handled and returns a bounded v3 alert state plus a receipt.
 * - opened/recovered: deduplicated per (incident id, kind, recipient), retried from durable pending even after monitor eviction.
 * - WS-alert2 re-classification: the monitor keeps the issues of the run that opened an incident; later runs only
 *   appear in record.report. With `latestReport` (the run the state last recorded) the dispatcher tracks the
 *   cause of the open incident with the monitor's own two-run rule. When a new ACTIONABLE category holds for two
 *   recorded runs and differs from what both sides were last told, both get a numbered re-classification
 *   (`reclassified:<n>:<category>`), so a return to an earlier cause is announced too. Informational causes
 *   (notice, access gate) never replace an announced cause. Re-classifications are retried from the stored
 *   queue regardless of the current cause and are settled as "abandoned" when the incident closes.
 * - reminders: once per window for a still-open incident, naming the last announced cause (never a downgrade).
 * - order: recovery, re-classification and reminders wait for that recipient's "opened" alert while it is still retrying.
 * Mock acknowledgement is recorded as such, never as delivery.
 */
export async function dispatchAlerts(state, monitorState, config, transport, { now = Date.now(), latestReport = null } = {}) {
  const base = validateAlertState(state); validateAlertConfig(config);
  if (!int(now, 0, Number.MAX_SAFE_INTEGER) || (base.last_dispatch_ms !== null && now < base.last_dispatch_ms)) refuse("clock_error");
  if (!object(monitorState) || !Array.isArray(monitorState.events) || monitorState.events.length > MAX_MONITOR_EVENTS) refuse("invalid_monitor_state");
  if (transport?.name !== config.transport || typeof transport.deliver !== "function") refuse("transport_mismatch");
  const next = structuredClone(base);
  next.history_complete_from_ms ??= now;
  next.last_dispatch_ms = now;
  const receipt = { attempted: [], acknowledged: [], failed: [], suppressed: [], reminders: [], reclassified: [],
    deferred: [], abandoned: [], invalid_events: 0, incident_invalid: false, unrecoverable_events: [] };
  const queue = [], queued = new Set();
  const enqueue = item => { if (!queued.has(item.key)) { queued.add(item.key); queue.push(item); } };
  const key = (id, kind, recipient) => `${id}:${kind}:${recipient}`;
  const settled = row => row.status === "acknowledged" || row.status === "abandoned" || row.attempts >= config.max_attempts;
  // Previously persisted events are authoritative and remain retryable after monitor eviction.
  for (const item of base.pending) {
    const [, , kind] = DELIVERY_KEY.exec(item.key), row = next.deliveries[item.key];
    if (["opened", "recovered"].includes(kind) && !settled(row)) enqueue(item);
  }
  for (const event of monitorState.events) {
    let category;
    try { category = classifyEvent(event); } catch { receipt.invalid_events++; continue; } // one bad record never blocks the rest
    for (const recipient of RECIPIENTS) {
      const k = key(event.id, event.kind, recipient);
      const row = next.deliveries[k];
      if (row && settled(row)) { receipt.suppressed.push(k); continue; }
      enqueue({ key: k, message: buildMessage(event, category, recipient) });
    }
  }
  const open = monitorState.incident ?? null;
  let openedCategory = null;
  if (open) { try { openedCategory = classifyEvent(open); } catch { receipt.incident_invalid = true; } }
  const openId = openedCategory ? open.id : null;
  // Incidents that are no longer open: drop their memory and settle their reminders/re-classifications.
  for (const id of Object.keys(next.incidents)) if (id !== openId) delete next.incidents[id];
  const settleAbandoned = (k, row) => { row.status = "abandoned"; receipt.abandoned.push(k); };
  for (const [k, row] of Object.entries(next.deliveries)) {
    const [, id, kind] = DELIVERY_KEY.exec(k);
    if (id !== openId && /^(reminder|reclassified):/.test(kind) && !settled(row)) settleAbandoned(k, row);
  }
  let incident = null;
  if (openId) {
    incident = next.incidents[openId] ??= { opened_category: openedCategory, announced: openedCategory,
      announced_issues: [...open.issues], seq: 0, candidate: null, candidate_runs: 0, previous: null, last_report_ms: null };
    const sameRun = object(latestReport) && Number.isSafeInteger(latestReport.observed_at_ms) &&
      latestReport.observed_at_ms === monitorState.last_observed_ms && latestReport.observed_at_ms >= open.at_ms;
    // Each recorded run is counted once, even if this CLI runs twice on the same monitor record.
    if (sameRun && latestReport.observed_at_ms !== incident.last_report_ms) {
      incident.last_report_ms = latestReport.observed_at_ms;
      let cause = null, issues = null;
      if (latestReport.status === "failed" && Array.isArray(latestReport.issues) && latestReport.issues.length >= 1 &&
          latestReport.issues.length <= 8 && latestReport.issues.every(ISSUE)) {
        issues = [...latestReport.issues];
        try { cause = classifyEvent({ id: open.id, kind: "opened", at_ms: open.at_ms, issues }); } catch { cause = null; }
      }
      const previous = incident.previous;
      incident.previous = cause;
      if (cause === null) { incident.candidate = null; incident.candidate_runs = 0; }
      else { incident.candidate_runs = cause === incident.candidate ? Math.min(2, incident.candidate_runs + 1) : 1; incident.candidate = cause; }
      let target = null;
      if (incident.candidate_runs === 2 && ACTIONABLE.has(incident.candidate) && incident.candidate !== incident.announced) {
        target = incident.candidate;
      } else if (!ACTIONABLE.has(incident.announced) && ACTIONABLE.has(cause) && ACTIONABLE.has(previous)) {
        // Announced as informational, but two consecutive runs needed action (their causes alternate):
        // escalate rather than keep saying "no action needed". Mixed causes go to both sides.
        target = cause === previous ? cause : "unclassified";
      }
      if (target) {
        const from = incident.announced;
        incident.seq += 1; incident.announced = target; incident.announced_issues = issues;
        // A newer announcement supersedes every older one still waiting for any recipient, so a late retry can
        // never arrive after it and leave a recipient with an outdated cause.
        for (const [k, row] of Object.entries(next.deliveries)) {
          const [, id, kind] = DELIVERY_KEY.exec(k);
          if (id === openId && kind.startsWith("reclassified:") && !settled(row)) settleAbandoned(k, row);
        }
        for (const recipient of RECIPIENTS) {
          const k = key(openId, `reclassified:${incident.seq}:${target}`, recipient);
          enqueue({ key: k, message: buildMessage(open, target, recipient, { reclassifiedFrom: from,
            causeIssues: issues, causeObservedMs: latestReport.observed_at_ms, kind: "reclassified", announcement: incident.seq }) });
          receipt.reclassified.push(k);
        }
      }
    }
    // Earlier re-classifications that have not been acknowledged are retried from the stored queue, whatever the
    // current cause is (opened/recovered were restored before the monitor snapshot).
    for (const item of base.pending) {
      const [, id, kind] = DELIVERY_KEY.exec(item.key);
      const row = next.deliveries[item.key];
      if (id === openId && kind.startsWith(`reclassified:${incident.seq}:`) && row && !settled(row) && !queued.has(item.key)) enqueue(item);
    }
    if (config.remind_after_minutes > 0) {
      const slot = Math.floor((now - open.at_ms) / (config.remind_after_minutes * 60000));
      for (const [k, row] of Object.entries(next.deliveries)) {
        const [, id, kind] = DELIVERY_KEY.exec(k);
        if (id === openId && kind.startsWith("reminder:") && Number(kind.slice(9)) < slot && !settled(row)) settleAbandoned(k, row);
      }
      if (slot >= 1) {
        for (const recipient of RECIPIENTS) {
          const k = key(openId, `reminder:${slot}`, recipient);
          const row = next.deliveries[k];
          if (row && settled(row)) continue;
          enqueue({ key: k, message: buildMessage(open, incident.announced, recipient, { reminder: slot,
            causeIssues: incident.announced_issues }) });
          receipt.reminders.push(k);
        }
      }
    }
  }
  const listed = new Set(monitorState.events.filter(e => object(e) && typeof e.id === "string").map(e => `${e.id}:${e.kind}`));
  receipt.pruned = 0;
  const byKey = new Map(queue.map(item => [item.key, item])), ordered = [], orderedKeys = new Set();
  const append = item => { if (item && !orderedKeys.has(item.key)) { orderedKeys.add(item.key); ordered.push(item); } };
  for (const item of queue) {
    const [, id, kind, recipient] = DELIVERY_KEY.exec(item.key);
    if (kind !== "opened") {
      const openingKey = key(id, "opened", recipient), opening = next.deliveries[openingKey];
      if (opening && !settled(opening) && !byKey.has(openingKey)) refuse("pending_opening_unavailable");
      append(byKey.get(openingKey));
    }
    append(item);
  }
  if (ordered.length > MAX_PENDING_DELIVERIES) refuse("pending_capacity_exceeded");
  for (const [k, row] of Object.entries(next.deliveries)) {
    const [, id, kind] = DELIVERY_KEY.exec(k);
    if (["opened", "recovered"].includes(kind) && !settled(row) && !byKey.has(k) && !listed.has(`${id}:${kind}`)) receipt.unrecoverable_events.push(k);
  }
  // Reserve all potentially pending rows and serialized messages before transport calls.
  // Valid fresh traffic fits: at most 200 new events per invocation, five opening
  // attempts, then at most five recovery attempts (four intervening waits).
  next.pending = ordered;
  for (const item of ordered) next.deliveries[item.key] ??= { status: "undelivered", attempts: 0, last_attempt_ms: now, acknowledged_by_transport: false };
  compactAlertState(next, { listed, openId, config, now, receipt });
  next.pending = [];
  for (const item of ordered) {
    const [, id, kind, recipient] = DELIVERY_KEY.exec(item.key);
    if (kind === "recovered" || (id === openId && /^(reminder|reclassified):/.test(kind))) {
      const opened = next.deliveries[key(id, "opened", recipient)];
      if (opened && opened.status !== "acknowledged" && !settled(opened)) {
        // That recipient has not received the opening alert yet; keep the order (it is retried first next run).
        if (!next.deliveries[item.key]) next.deliveries[item.key] = { status: "undelivered", attempts: 0, last_attempt_ms: now, acknowledged_by_transport: false };
        next.pending.push(item); receipt.deferred.push(item.key); continue;
      }
    }
    const row = next.deliveries[item.key] || { status: "undelivered", attempts: 0, last_attempt_ms: 0, acknowledged_by_transport: false };
    let result;
    try { result = await transport.deliver(item.message); } catch { result = { ok: false, code: "transport_threw" }; }
    row.attempts += 1; row.last_attempt_ms = now;
    receipt.attempted.push(item.key);
    if (result?.ok === true) { row.status = "acknowledged"; row.acknowledged_by_transport = true; receipt.acknowledged.push(item.key); }
    else {
      row.status = "undelivered";
      receipt.failed.push({ key: item.key, code: typeof result?.code === "string" ? result.code : "transport_failure", attempts: row.attempts });
      if (row.attempts < config.max_attempts) next.pending.push(item);
    }
    next.deliveries[item.key] = row;
  }
  compactAlertState(next, { listed, openId, config, now, receipt });
  validateAlertState(next);
  return { state: next, receipt };
}

/**
 * Rollback aid: converts a v2/v3 state into a WS-alert1 (v1) state that the previous code accepts WITHOUT re-sending
 * retained deduplication history. v1 cannot represent retention coverage and must be reported as unknown.
 * Re-classification rows and pending items are dropped (v1 has no such kind) and "abandoned" rows become
 * undelivered with attempts = maxAttempts, which v1 treats as settled. Starting v1 from an empty file instead would
 * re-send every opened/recovered event the monitor still lists (up to 100 events, both recipients).
 */
export function toV1State(state, maxAttempts) {
  const v2 = validateAlertState(state);
  if (!int(maxAttempts, 1, 5)) refuse("invalid_limits");
  const deliveries = {};
  for (const [k, row] of Object.entries(v2.deliveries)) {
    if (k.includes(":reclassified:")) continue;
    deliveries[k] = row.status === "abandoned" ? { ...row, status: "undelivered", attempts: Math.max(row.attempts, maxAttempts) } : { ...row };
  }
  // Refuse rather than truncate a queue the old state format cannot hold. Even a
  // small copy cannot make old v1 code retry events after the monitor evicts them;
  // v1 dispatch reconstructs events from the monitor, not the stored pending payload.
  const pending = v2.pending.filter(p => !p.key.includes(":reclassified:"));
  if (pending.length > MAX_V1_PENDING) refuse("v1_pending_capacity_exceeded");
  const legacy = { schema: STATE_V1, deliveries, pending, mock_only: true };
  serializeAlertState(legacy, { maxBytes: MAX_V1_STATE_BYTES });
  return legacy;
}


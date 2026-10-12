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
  "health_content_type", "health_probe_error", "health_date_invalid", "health_age_invalid", "health_clock_mismatch"]);

/** Maps a monitor event (opened/recovered with issues) to an alert category. Pure; no I/O. */
export function classifyEvent(event) {
  if (!exact(event, ["id", "kind", "at_ms", "issues"]) || !["opened", "recovered"].includes(event.kind) ||
      typeof event.id !== "string" || !/^[a-f0-9]{64}$/.test(event.id) || !int(event.at_ms, 0, Number.MAX_SAFE_INTEGER) ||
      !Array.isArray(event.issues) || !event.issues.every(i => typeof i === "string" && /^[a-z_]{1,80}$/.test(i))) refuse("invalid_event");
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

export function initialAlertState() {
  return { schema: "pitcheezy-host-alert-state-v1", deliveries: {}, pending: [], mock_only: true };
}
export function validateAlertState(state) {
  if (!exact(state, ["schema", "deliveries", "pending", "mock_only"]) || state.schema !== "pitcheezy-host-alert-state-v1" ||
      !object(state.deliveries) || !Array.isArray(state.pending) || state.mock_only !== true) refuse("state_invalid");
  for (const [key, row] of Object.entries(state.deliveries)) {
    if (!/^[a-f0-9]{64}:(opened|recovered|reminder:[0-9]+):(song|ours)$/.test(key) ||
        !exact(row, ["status", "attempts", "last_attempt_ms", "acknowledged_by_transport"]) ||
        !["acknowledged", "undelivered"].includes(row.status) || !int(row.attempts, 0, 100) ||
        !int(row.last_attempt_ms, 0, Number.MAX_SAFE_INTEGER) || typeof row.acknowledged_by_transport !== "boolean") refuse("state_invalid");
  }
  if (state.pending.length > 200 || !state.pending.every(p => exact(p, ["key", "message"]) && typeof p.key === "string" && object(p.message))) refuse("state_invalid");
  return state;
}

/** Message text uses placeholders awaiting human-approved wording; it never includes URLs, tokens or addresses. */
export function buildMessage(event, category, recipient, { reminder = 0 } = {}) {
  const meta = CATEGORIES[category];
  const responsibility = meta.first_responder === "both" ? "양쪽이 함께 조사"
    : meta.first_responder === "song" ? "Song 쪽(맥미니/발행기) 우선 조사, 우리 쪽은 호스팅 상태 확인"
    : meta.first_responder === "ours" ? "우리 쪽(호스팅) 우선 조사, Song 쪽은 발행기 상태 확인"
    : "조치 불필요(정보)";
  return {
    schema: "pitcheezy-host-alert-message-v1", recipient, category, severity: meta.severity,
    first_responder: meta.first_responder, incident_id: event.id, event_kind: event.kind, reminder,
    observed_at: new Date(event.at_ms).toISOString(), issues: [...event.issues],
    text: `[개발용 문구] ${category} (${event.kind}${reminder ? ", 재알림 " + reminder : ""}): ${responsibility}. issues=${event.issues.join(",") || "none"}`,
    delivery_confirmed: false,
  };
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
 * Processes monitor events not yet handled. Returns a new alert state plus a receipt. Deduplicates per
 * (incident id, kind, recipient); retries failed deliveries up to max_attempts across runs; optional
 * reminders for incidents still open. Mock acknowledgement is recorded as such, never as delivery.
 */
export async function dispatchAlerts(state, monitorState, config, transport, { now = Date.now() } = {}) {
  validateAlertState(state); validateAlertConfig(config);
  if (!object(monitorState) || !Array.isArray(monitorState.events)) refuse("invalid_monitor_state");
  if (transport?.name !== config.transport || typeof transport.deliver !== "function") refuse("transport_mismatch");
  const next = structuredClone(state);
  const receipt = { attempted: [], acknowledged: [], failed: [], suppressed: [], reminders: [] };
  const queue = [];
  const key = (event, kind, recipient) => `${event.id}:${kind}:${recipient}`;
  for (const event of monitorState.events) {
    const category = classifyEvent(event);
    for (const recipient of RECIPIENTS) {
      const k = key(event, event.kind, recipient);
      const row = next.deliveries[k];
      if (row?.status === "acknowledged") { receipt.suppressed.push(k); continue; }
      if (row && row.attempts >= config.max_attempts) { receipt.suppressed.push(k); continue; }
      queue.push({ key: k, message: buildMessage(event, category, recipient) });
    }
  }
  // Reminder for an incident that is still open, at most once per remind window.
  const open = monitorState.incident;
  if (open && config.remind_after_minutes > 0) {
    const category = classifyEvent(open);
    const slot = Math.floor((now - open.at_ms) / (config.remind_after_minutes * 60000));
    if (slot >= 1) {
      for (const recipient of RECIPIENTS) {
        const k = key(open, `reminder:${slot}`, recipient);
        const row = next.deliveries[k];
        // A failed reminder is retried like any other delivery until max_attempts; an acknowledged one is not repeated.
        if (row && (row.status === "acknowledged" || row.attempts >= config.max_attempts)) continue;
        queue.push({ key: k, message: buildMessage(open, category, recipient, { reminder: slot }) });
        receipt.reminders.push(k);
      }
    }
  }
  // Bounded state: rows that are settled (acknowledged or out of attempts) and older than the retention window are dropped.
  const retainMs = PRUNE_AFTER_DAYS * 86400000;
  receipt.pruned = 0;
  for (const [k, row] of Object.entries(next.deliveries)) {
    const settled = row.status === "acknowledged" || row.attempts >= config.max_attempts;
    if (settled && now - row.last_attempt_ms > retainMs) { delete next.deliveries[k]; receipt.pruned++; }
  }
  next.pending = [];
  for (const item of queue) {
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
  validateAlertState(next);
  return { state: next, receipt };
}

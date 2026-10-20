/**
 * Per-game operations report draft (WS-report1). Pure builder: turns operator-supplied inputs (usage
 * summary, monitor state, notice audit, alert state, actions, sources, commands) into a Markdown issue
 * draft plus a JSON record. It never posts anywhere, never counts "no data" as zero viewers, and labels
 * synthetic / offline replay / live evidence separately. Wording is development copy awaiting approval.
 */
import { isIP } from "node:net";

const object = v => v !== null && typeof v === "object" && !Array.isArray(v);
const exact = (v, keys) => object(v) && Object.keys(v).sort().join(",") === [...keys].sort().join(",");
const int = (v, min, max) => Number.isSafeInteger(v) && v >= min && v <= max;
const text = (v, max) => typeof v === "string" && v.length <= max && !/\p{Cc}/u.test(v.replace(/[\n\t]/g, ""));
const iso = v => typeof v === "string" && /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(?:\.\d{1,3})?Z$/.test(v) &&
  Number.isFinite(Date.parse(v)) && new Date(v).toISOString().slice(0, 19) === v.slice(0, 19);
const day = v => typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v) &&
  Number.isFinite(Date.parse(v + "T00:00:00Z")) && new Date(v + "T00:00:00Z").toISOString().slice(0, 10) === v;
const HEX40 = /^[a-f0-9]{40}$/, HEX64 = /^[a-f0-9]{64}$/;
export class ReportError extends Error { constructor(code) { super(code); this.code = code; } }
const refuse = code => { throw new ReportError(code); };
export const EVIDENCE = Object.freeze({ synthetic: "합성 자료", offline_replay: "오프라인 재생", live: "실경기" });

/** Shared row validation; legacy summary semantics remain unchanged. */
export function validateUsageSummary(s) {
  if (s !== null && (!object(s) || s.schema !== "pitcheezy-usage-summary-v1" || s.timezone !== "UTC" ||
      !Array.isArray(s.sessions) || !Array.isArray(s.feedback) || !day(s.from_day) || !day(s.to_day) ||
      s.from_day > s.to_day)) refuse("invalid_usage_summary");
  if (s !== null) {
    const inSummary = value => day(value) && value >= s.from_day && value <= s.to_day;
    const sessionGroups = new Set(), feedbackGroups = new Set();
    let totalActive = 0;
    for (const row of s.sessions) {
      if (!exact(row, ["utc_day", "game_pk", "sessions", "active_ms", "mean_active_ms"]) ||
          !int(row.sessions, 0, 1e9) || !int(row.game_pk, 0, 999999999999) || !inSummary(row.utc_day) ||
          !int(row.active_ms, 0, Number.MAX_SAFE_INTEGER) || !int(row.mean_active_ms, 0, Number.MAX_SAFE_INTEGER)) refuse("invalid_usage_summary");
      const key = `${row.utc_day}:${row.game_pk}`;
      totalActive += row.active_ms;
      if (sessionGroups.has(key) || !Number.isSafeInteger(totalActive)) refuse("invalid_usage_summary");
      sessionGroups.add(key);
    }
    for (const row of s.feedback) {
      if (!exact(row, ["utc_day", "game_pk", "rating", "reason", "responses"]) ||
          !int(row.responses, 0, 1e9) || !int(row.game_pk, 0, 999999999999) || !inSummary(row.utc_day) ||
          !["helpful", "unclear", "problem"].includes(row.rating) ||
          !["none", "recommendation", "explanation", "delay", "display", "other"].includes(row.reason)) refuse("invalid_usage_summary");
      const key = `${row.utc_day}:${row.game_pk}:${row.rating}:${row.reason}`;
      if (feedbackGroups.has(key)) refuse("invalid_usage_summary");
      feedbackGroups.add(key);
    }
  }
  return s;
}
const isSnapshot = value => object(value) && value.schema === "pitcheezy-usage-snapshot-v1";
const usageSummary = value => isSnapshot(value) ? value.usage_summary : value;
function validateUsageInput(value) {
  if (!isSnapshot(value)) return validateUsageSummary(value);
  if (!exact(value, ["schema", "source_sha256", "coverage", "aggregation", "usage_summary"]) ||
      typeof value.source_sha256 !== "string" || !HEX64.test(value.source_sha256) ||
      value.coverage !== "unverified" || value.aggregation !== "utc_day") refuse("invalid_usage_snapshot");
  const s = value.usage_summary;
  if (!exact(s, ["schema", "timezone", "from_day", "to_day", "generated_at", "sessions", "feedback", "limits"]) ||
      s.schema !== "pitcheezy-usage-summary-v1" || !iso(s.generated_at) ||
      new Date(s.generated_at).toISOString().slice(0, 19) !== s.generated_at.slice(0, 19) ||
      !text(s.limits, 500)) refuse("invalid_usage_snapshot");
  validateUsageSummary(s);
  // Actual GROUP BY output has positive counts. An invented zero-count group is not observed evidence.
  if (s.sessions.some(r => r.sessions === 0) || s.feedback.some(r => r.responses === 0)) refuse("invalid_usage_summary");
  return s;
}

export function validateReportInput(input) {
  const keys = ["schema", "game_pk", "evidence", "window", "collection", "usage_summary", "monitor_state",
    "notice_audit", "alert_state", "actions", "sources", "commands", "unmeasured", "notes"];
  if (object(input) && Object.hasOwn(input, "notice_audit_meta")) keys.push("notice_audit_meta");
  if (!exact(input, keys) ||
      input.schema !== "pitcheezy-game-report-input-v1") refuse("invalid_input");
  if (!int(input.game_pk, 1, 999999999999) || !Object.hasOwn(EVIDENCE, input.evidence)) refuse("invalid_game_or_evidence");
  if (!exact(input.window, ["from", "to"]) || !iso(input.window.from) || !iso(input.window.to) ||
      Date.parse(input.window.to) < Date.parse(input.window.from) ||
      Date.parse(input.window.to) - Date.parse(input.window.from) > 14 * 86400000) refuse("invalid_window");
  const c = input.collection;
  if (!exact(c, ["telemetry_enabled", "feedback_enabled", "consent_note", "retain_days"]) ||
      typeof c.telemetry_enabled !== "boolean" || typeof c.feedback_enabled !== "boolean" ||
      !text(c.consent_note, 500) || !(c.retain_days === null || int(c.retain_days, 1, 90))) refuse("invalid_collection");
  validateUsageInput(input.usage_summary);
  const m = input.monitor_state;
  if (m !== null && (!object(m) || !Array.isArray(m.events) || !int(m.dropped_events ?? 0, 0, Number.MAX_SAFE_INTEGER) ||
      !(m.last_observed_ms === undefined || m.last_observed_ms === null || int(m.last_observed_ms, 0, Number.MAX_SAFE_INTEGER)) ||
      !m.events.every(e => exact(e, ["id", "kind", "at_ms", "issues"]) && HEX64.test(e.id) && ["opened", "recovered"].includes(e.kind) &&
        int(e.at_ms, 0, Number.MAX_SAFE_INTEGER) && Array.isArray(e.issues) && e.issues.every(i => typeof i === "string" && /^[a-z_]{1,80}$/.test(i))))) refuse("invalid_monitor_state");
  const n = input.notice_audit;
  if (n !== null && (!Array.isArray(n) || n.length > 200 || !n.every(a => object(a) && a.schema === "pitcheezy-notice-audit-v1" &&
      iso(a.at) && typeof a.active === "boolean" && text(a.operator || "", 64) && text(a.reason || "", 500) && typeof a.message_id === "string"))) refuse("invalid_notice_audit");
  if (Object.hasOwn(input, "notice_audit_meta") && (!exact(input.notice_audit_meta, ["audit_unavailable", "audit_truncated"]) ||
      typeof input.notice_audit_meta.audit_unavailable !== "boolean" || typeof input.notice_audit_meta.audit_truncated !== "boolean")) refuse("invalid_notice_audit_meta");
  const a = input.alert_state;
  if (a !== null && (!object(a) || !["pitcheezy-host-alert-state-v1", "pitcheezy-host-alert-state-v2", "pitcheezy-host-alert-state-v3"].includes(a.schema) ||
      !object(a.deliveries) || a.mock_only !== true)) refuse("invalid_alert_state");
  if (a !== null) {
    // Validate only the fields this report consumes; minimal legacy states remain supported.
    const statuses = a.schema === "pitcheezy-host-alert-state-v1" ?
      ["acknowledged", "undelivered"] : ["acknowledged", "undelivered", "abandoned"];
    if ((a.pending != null && !Array.isArray(a.pending)) || !Object.values(a.deliveries).every(row =>
      object(row) && statuses.includes(row.status) && int(row.attempts, 0, 100) &&
      int(row.last_attempt_ms, 0, Number.MAX_SAFE_INTEGER))) refuse("invalid_alert_state");
  }
  if (a?.schema === "pitcheezy-host-alert-state-v3" &&
      !["history_pruned_through_ms", "history_complete_from_ms", "last_dispatch_ms"].every(k =>
        a[k] === null || int(a[k], 0, Number.MAX_SAFE_INTEGER))) refuse("invalid_alert_state");
  if (!Array.isArray(input.actions) || input.actions.length > 100 ||
      !input.actions.every(x => exact(x, ["at", "by", "what"]) && iso(x.at) && /^[A-Za-z0-9._-]{1,64}$/.test(x.by) && text(x.what, 500))) refuse("invalid_actions");
  const src = input.sources;
  if (!exact(src, ["host_commit", "frontend_commit", "contract_version", "release_manifest_sha256"]) ||
      !HEX40.test(src.host_commit) || !(src.frontend_commit === null || HEX40.test(src.frontend_commit)) ||
      !(src.contract_version === null || text(src.contract_version, 64)) ||
      !(src.release_manifest_sha256 === null || HEX64.test(src.release_manifest_sha256))) refuse("invalid_sources");
  if (!Array.isArray(input.commands) || input.commands.length > 50 || !input.commands.every(x => text(x, 300) && !/\n/.test(x))) refuse("invalid_commands");
  if (!Array.isArray(input.unmeasured) || input.unmeasured.length > 50 || !input.unmeasured.every(x => text(x, 200))) refuse("invalid_unmeasured");
  if (!text(input.notes, 2000)) refuse("invalid_notes");
  // Secrets, addresses and tokens never belong in an issue draft: every free-text field that can reach the draft is scanned.
  if (privateContent(freeText(input))) refuse("secret_or_address_like_content");
  return input;
}

/** Reject recognizable contact/access details before producing either public draft artifact.
 * This is a conservative shape check, not complete PII detection or permission to publish.
 */
function privateContent(value) {
  if (/\b[A-Za-z][A-Za-z0-9+.-]*:\/\/|Bearer |[A-Za-z0-9_-]{43,}/.test(value)) return true;
  if (/[\p{L}\p{N}.!#$%&'*+/=?^_`{|}~-]+@(?:[\p{L}\p{N}](?:[\p{L}\p{N}-]*[\p{L}\p{N}])?\.)+[\p{L}]{2,63}\b/u.test(value)) return true;
  // Drive-rooted Windows and UNC paths; repo-relative commands stay usable.
  if (/\b[A-Za-z]:[\\/]|\\\\[^\\\s]+\\[^\\\s]+|(?<![:/])\/\/[^/\s]+\/[^/\s]+/.test(value)) return true;
  // Known personal home roots, including shell-expanded forms. API paths such as /v1 remain valid.
  if (/(?:^|[\s"'`(=])(?:\/(?:Users|home|root)(?:\/|(?=$|[\s"'`)]))|~(?:[A-Za-z0-9._-]+)?\/)/.test(value)) return true;
  // Parse address candidates rather than treating version numbers/times as IP addresses.
  const ipv4 = value.match(/(?<![A-Za-z0-9_.])(?:[0-9]{1,3}\.){3}[0-9]{1,3}(?![A-Za-z0-9_.])/g) || [];
  const ipv6 = value.match(/(?<![A-Za-z0-9_.:])(?:[A-Fa-f0-9]{0,4}:){2,}[A-Fa-f0-9:.]*(?:%[A-Za-z0-9_.-]+)?(?![A-Za-z0-9_.:])/g) || [];
  return ipv4.some(v => isIP(v) === 4) || ipv6.some(v => isIP(v) === 6);
}

function freeText(input) {
  const audit = input.notice_audit || [];
  const feedback = usageSummary(input.usage_summary)?.feedback || [];
  return [input.notes, ...input.commands, ...input.actions.flatMap(x => [x.by, x.what]), input.collection.consent_note,
    ...input.unmeasured, input.sources.contract_version || "", ...audit.flatMap(a => [a.operator || "", a.reason || "", a.message_id]),
    ...feedback.map(r => `${r.rating} ${r.reason}`)].join(" ");
}

/**
 * "no data" (collection off, no summary, or no observations in an incomplete summary) is distinct from
 * "zero sessions in the window". Incomplete summaries with observations retain partial totals and a warning.
 * Session counts exist only while telemetry was ON; feedback counts only
 * while feedback was ON. A count for a channel that was OFF is null (unmeasured), never 0.
 */
export function usageSection(input) {
  const c = input.collection;
  const days = new Set();
  for (let t = Date.parse(input.window.from); t <= Date.parse(input.window.to); t += 86400000) days.add(new Date(t).toISOString().slice(0, 10));
  days.add(input.window.to.slice(0, 10));
  if (!c.telemetry_enabled && !c.feedback_enabled) {
    return { status: "collection_off", sessions: null, active_ms: null, feedback: null, summary_covers_window: null,
      statement: "수집 OFF — 이용자 수·활성 시간·피드백은 **미측정**이다(0명이 아님)." };
  }
  const snapshot = isSnapshot(input.usage_summary);
  const s = usageSummary(input.usage_summary);
  if (s === null) {
    return { status: "no_data", sessions: null, active_ms: null, feedback: null, summary_covers_window: null,
      statement: "집계 자료 없음(요약 미수신) — 이용자 수는 **미측정**이다(0명이 아님)." };
  }
  const sorted = [...days].sort();
  const covers = s.from_day <= sorted[0] && s.to_day >= sorted[sorted.length - 1];
  const rows = c.telemetry_enabled ? s.sessions.filter(r => r.game_pk === input.game_pk && days.has(r.utc_day)) : [];
  const fb = c.feedback_enabled ? s.feedback.filter(r => r.game_pk === input.game_pk && days.has(r.utc_day)) : [];
  const feedback = c.feedback_enabled ? fb.map(r => ({ rating: r.rating, reason: r.reason, responses: r.responses })) : null;
  const responses = fb.reduce((n, r) => n + r.responses, 0);
  if (snapshot) {
    const caveat = `요약 범위 ${s.from_day} ~ ${s.to_day}의 보존 행 중 보고 기간과 겹치는 UTC 날짜 전체의 합계다. ` +
      "보고서의 정확한 시각 구간 집계가 아니며 수집·보존 누락은 미확인이다. ";
    if (rows.length === 0 && fb.length === 0) {
      return { status: "no_data", sessions: null, active_ms: null, feedback: null, summary_covers_window: false,
        statement: caveat + "활성 수집 채널의 해당 경기 보존 행이 없다 — 이용량은 **미측정**이다(0명이 아님)." };
    }
    const sessions = rows.length ? rows.reduce((n, r) => n + r.sessions, 0) : null;
    const active = rows.length ? rows.reduce((n, r) => n + r.active_ms, 0) : null;
    const keptFeedback = fb.length ? fb.map(r => ({ utc_day: r.utc_day, rating: r.rating, reason: r.reason, responses: r.responses })) : null;
    const sessionNote = sessions === null ? "세션·활성 시간은 **미측정**이다(수집 OFF 또는 보존 행 없음). " :
      `보존된 opt-in 브라우저 세션 ${sessions}개, 활성 시간 합계 ${Math.round(active / 60000)}분(전체 이용량·사람 수가 아님). `;
    const feedbackNote = keptFeedback === null ? "피드백은 **미측정**이다(수집 OFF 또는 보존 행 없음)." : `보존된 피드백 응답 ${responses}건.`;
    return { status: "partial_data", sessions, active_ms: active, feedback: keptFeedback, summary_covers_window: false,
      statement: caveat + sessionNote + feedbackNote };
  }
  if (!covers && rows.length === 0 && fb.length === 0) {
    return { status: "no_data", sessions: null, active_ms: null, feedback: null, summary_covers_window: false,
      statement: "집계 자료가 집계 기간을 덮지 않는다(요약 범위 밖) — 이용자 수는 **미측정**이다(0명이 아님)." };
  }
  const partialNote = covers ? "" : `부분 집계: 요약 범위 ${s.from_day} ~ ${s.to_day}(UTC 날짜)의 기록만 포함한다. 요약 범위 밖은 **미측정**이다. `;
  if (!c.telemetry_enabled) {
    return { status: covers ? "feedback_only" : "partial_data", sessions: null, active_ms: null, feedback, summary_covers_window: covers,
      statement: partialNote + `통계 수집 OFF — 이용자 수·활성 시간은 **미측정**이다(0명이 아님). 피드백 수집 ON: 응답 ${responses}건.` };
  }
  const sessions = rows.reduce((n, r) => n + r.sessions, 0);
  const active = rows.reduce((n, r) => n + r.active_ms, 0);
  const feedbackNote = c.feedback_enabled ? "" : " 피드백 수집 OFF(미측정).";
  if (rows.length === 0 && fb.length === 0) {
    return { status: "zero_rows", sessions: 0, active_ms: 0, feedback: c.feedback_enabled ? [] : null, summary_covers_window: covers,
      statement: "수집 ON이었으나 집계 기간·이 경기의 opt-in 세션 행이 0개다(자료 없음이 아니라 0세션)." + feedbackNote };
  }
  return { status: covers ? "counted" : "partial_data", sessions, active_ms: active, feedback, summary_covers_window: covers,
    statement: partialNote + `opt-in 브라우저 세션 ${sessions}개, 브라우저가 보고한 활성 시간 합계 ${Math.round(active / 60000)}분(사람 수·검증된 주의 시간이 아님).` + feedbackNote };
}

function withinWindow(ms, input) { return ms >= Date.parse(input.window.from) && ms <= Date.parse(input.window.to); }

export function problemsSection(input) {
  const monitor = (input.monitor_state?.events || []).filter(e => withinWindow(e.at_ms, input))
    .map(e => ({ at: new Date(e.at_ms).toISOString(), kind: e.kind, issues: [...e.issues], incident_id: e.id.slice(0, 12) }));
  const notice = (input.notice_audit || []).filter(a => withinWindow(Date.parse(a.at), input))
    .map(a => ({ at: a.at, active: a.active, message_id: a.message_id, operator: a.operator, reason: a.reason }));
  // Delivery rows accumulate across games; only attempts made inside this window belong to this report. Pending is current state.
  const deliveries = Object.values(input.alert_state?.deliveries || {}).filter(d => withinWindow(d.last_attempt_ms, input));
  const a = input.alert_state;
  // This checks retention bounds, not an attempt ledger: retries replace each row's last-attempt timestamp.
  const alertCoverage = a?.schema !== "pitcheezy-host-alert-state-v3" ? "unknown" :
    a.history_complete_from_ms !== null && a.last_dispatch_ms !== null &&
    Date.parse(input.window.from) >= a.history_complete_from_ms &&
    (a.history_pruned_through_ms === null || Date.parse(input.window.from) > a.history_pruned_through_ms) &&
    Date.parse(input.window.to) <= a.last_dispatch_ms ? "complete" : "partial";
  const alerts = input.alert_state === null ? null : {
    acknowledged_by_mock: deliveries.filter(d => d.status === "acknowledged").length,
    undelivered: deliveries.filter(d => d.status === "undelivered" && d.attempts > 0).length,
    // WS-alert2: a reminder/re-classification settled without delivery (incident closed, reminder window passed,
    // or superseded by a newer re-classification). Rows only queued behind an opening alert (0 attempts) are separate.
    abandoned: deliveries.filter(d => d.status === "abandoned").length,
    waiting_unattempted: deliveries.filter(d => d.status === "undelivered" && d.attempts === 0).length,
    pending: (input.alert_state.pending || []).length, delivery_confirmed: false, history_coverage: alertCoverage,
  };
  const incident_still_open = Boolean(input.monitor_state?.incident);
  const dropped = input.monitor_state?.dropped_events ?? 0;
  // The last observation proves a single sample, not coverage before it. Events remain positive evidence.
  const last = input.monitor_state?.last_observed_ms;
  const coverage = input.monitor_state === null ? "absent" : last === undefined ? "unknown" : last === null ? "never" :
    last < Date.parse(input.window.from) ? "before_window" : last < Date.parse(input.window.to) ? "stopped_in_window" :
      last === Date.parse(input.window.to) ? "at_window_end" : "after_window";
  const noticeMeta = input.notice_audit_meta;
  const noticeCoverage = input.notice_audit === null ? "absent" : !noticeMeta ? "unknown" :
    noticeMeta.audit_unavailable ? "unavailable" : noticeMeta.audit_truncated ? "truncated" : "available";
  return { monitor_events: monitor, notice_changes: notice, alerts, incident_still_open, dropped_monitor_events: dropped,
    monitor_available: input.monitor_state !== null, monitor_coverage: coverage,
    monitor_last_observed: Number.isSafeInteger(last) ? new Date(last).toISOString() : null,
    notice_available: input.notice_audit !== null, notice_audit_coverage: noticeCoverage };
}

export function buildReport(input, { now = Date.now() } = {}) {
  validateReportInput(input);
  const usage = usageSection(input);
  const problems = problemsSection(input);
  const label = EVIDENCE[input.evidence];
  const lines = [];
  lines.push(`# [경기별 운영 기록 초안] 경기 ${input.game_pk} — ${label}`, "");
  lines.push("> 개발용 초안 문구. 사람 승인 전에는 게시하지 않는다(자동 게시 없음). 작성 시각 " + new Date(now).toISOString() + " (UTC).", "");
  lines.push("## 기본", `- 경기 ID: ${input.game_pk}`, `- 집계 기간(UTC): ${input.window.from} ~ ${input.window.to}`,
    `- 증거 종류: **${label}** (${input.evidence})`, "");
  lines.push("## 이용 기록", `- 상태: \`${usage.status}\``, `- ${usage.statement}`,
    `- 통계 수집 ${input.collection.telemetry_enabled ? "ON" : "OFF"} / 피드백 수집 ${input.collection.feedback_enabled ? "ON" : "OFF"} / 보관일 ${input.collection.retain_days ?? "미설정"}`,
    `- 동의·누락 범위: ${input.collection.consent_note || "(기재 없음)"}`);
  if (usage.feedback && usage.feedback.length) {
    lines.push("- 피드백:"); for (const f of usage.feedback) lines.push(`  - ${f.utc_day ? f.utc_day + " UTC " : ""}${f.rating}/${f.reason}: ${f.responses}건`);
  }
  lines.push("- 세션은 opt-in 브라우저 단위이며 사람 수가 아니다. 활성 시간은 브라우저 보고값이다.", "");
  lines.push("## 문제와 조치");
  const coverage = problems.monitor_coverage;
  if (!problems.monitor_available) lines.push("- 감시 기록 없음(감시 상태 파일 미제공) — 장애 유무 **미측정**.");
  else if (coverage === "never" || coverage === "before_window") {
    lines.push(`- 감시가 집계 기간에 관측하지 않았다(마지막 관측 ${problems.monitor_last_observed ?? "없음"}) — 기간 중 장애 유무 **미측정**(감시 미실행 가능).`);
  } else {
    if (coverage === "stopped_in_window") lines.push(`- 감시 마지막 관측 ${problems.monitor_last_observed}(집계 기간 끝 전) — 그 이후는 **미측정**.`);
    if (coverage === "at_window_end") lines.push(`- 감시 마지막 관측 ${problems.monitor_last_observed}은 집계 기간 끝의 한 관측이다.`);
    if (coverage === "after_window") lines.push(`- 감시 마지막 관측 ${problems.monitor_last_observed}은 집계 기간 뒤다. ` +
      (problems.monitor_events.length ? "기간 안의 기록된 이벤트는 아래에 제시한다." : "이 시각만으로 기간 중 관측 여부를 확인할 수 없다."));
    if (coverage === "unknown") lines.push("- 감시 상태에 마지막 관측 시각이 없어 기간을 덮었는지 확인할 수 없다.");
    if (problems.monitor_events.length === 0) lines.push("- 제공된 감시 기록에 집계 기간 내 open/복구 이벤트가 없다(기간 전체 무장애를 뜻하지 않음)." + (problems.incident_still_open ? " 단, 기간 밖에서 열린 장애가 아직 열려 있다." : ""));
    else for (const e of problems.monitor_events) lines.push(`- ${e.at} 감시 ${e.kind} (${e.incident_id}…): ${e.issues.join(", ") || "-"}`);
    lines.push("- 기록된 관측·이벤트 외의 관측 간격과 누락 여부는 확인할 수 없다. 기간 전체의 장애 유무·지속 시간은 **미측정**이다.");
  }
  if (problems.dropped_monitor_events > 0) lines.push(`- 감시 기록이 ${problems.dropped_monitor_events}건 잘렸다(최근 100건만 보존).`);
  if (!problems.notice_available) lines.push("- 안내 화면 전환 기록 없음(감사 기록 미제공).");
  else if (problems.notice_changes.length === 0) lines.push("- 제공된 감사 기록에 집계 기간 내 안내 전환 기록이 없다(전환이 없었다는 보장은 아님).");
  else for (const n of problems.notice_changes) lines.push(`- ${n.at} 안내 ${n.active ? "ON" : "OFF"} (${n.message_id}) by ${n.operator}: ${n.reason}`);
  if (problems.notice_audit_coverage === "unavailable") lines.push("- 안내 감사 일부를 확인할 수 없거나 현재 상태 버전의 감사 증거가 누락됐다 — 안내 전환 기록의 완전성 **미측정**.");
  else if (problems.notice_audit_coverage === "truncated") lines.push("- 안내 감사는 최근 일부만 제공됐다 — 안내 전환 기록의 완전성 **미측정**.");
  else if (problems.notice_audit_coverage === "unknown") lines.push("- 안내 감사의 조회 상태·잘림 정보가 없다 — 안내 전환 기록의 완전성 **미측정**.");
  if (problems.alerts === null) lines.push("- 알림 기록 없음(알림 상태 파일 미제공).");
  else {
    lines.push(`- 알림(모의 transport, 보존된 최종 시도 행 기준): 모의 확인 ${problems.alerts.acknowledged_by_mock}건, 미전달 ${problems.alerts.undelivered}건, 전달 전 정리(장애 종료·재알림 창 경과·새 재분류로 대체) ${problems.alerts.abandoned}건, 순서 대기 ${problems.alerts.waiting_unattempted}건, 현재 대기 ${problems.alerts.pending}건 — 실제 전달 확인 아님.`);
    if (problems.alerts.history_coverage !== "complete") lines.push("- 알림 보존 범위가 집계 기간을 덮는지 확인되지 않거나 잘린 이력과 겹친다 — 보존된 행만 집계했으며 기간 전체합계는 **미측정**.");
    lines.push("- 재시도는 행의 최종 시각·상태를 갱신한다. 위 숫자는 모든 전송 시도의 횟수나 과거 시점의 상태 합계가 아니다.");
  }
  lines.push("", "### 조치");
  if (input.actions.length === 0) lines.push("- 기록된 조치 없음.");
  else for (const a of input.actions) lines.push(`- ${a.at} ${a.by}: ${a.what}`);
  lines.push("", "## 소스·해시·명령", `- 호스트 커밋: \`${input.sources.host_commit}\``,
    `- 화면 커밋: ${input.sources.frontend_commit ? "`" + input.sources.frontend_commit + "`" : "미기재"}`,
    `- 계약 버전: ${input.sources.contract_version ?? "미기재"}`,
    `- 배포 manifest SHA-256: ${input.sources.release_manifest_sha256 ? "`" + input.sources.release_manifest_sha256 + "`" : "미기재"}`);
  if (input.commands.length) { lines.push("- 실행 명령:"); for (const c of input.commands) lines.push("  - `" + c.replace(/`/g, "'") + "`"); }
  lines.push("", "## 미측정");
  const unmeasured = [...input.unmeasured];
  if (usage.sessions === null) unmeasured.unshift("이용자 수·활성 시간");
  if (usage.feedback === null && usage.status !== "collection_off") unmeasured.push("피드백 응답");
  if (isSnapshot(input.usage_summary)) {
    unmeasured.push("수집·보존 누락과 기간 전체 이용량(스냅샷의 남아 있는 행만 확인)",
      "정확한 보고 시각 구간의 이용량(UTC 날짜 전체 합계만 제공)");
  } else if (usage.status === "partial_data") unmeasured.push("요약 범위 밖의 이용 기록·피드백(부분 집계)");
  if (!problems.monitor_available || ["never", "before_window"].includes(problems.monitor_coverage)) unmeasured.push("장애 유무·지속 시간");
  else {
    unmeasured.push("기간 전체의 장애 유무·지속 시간(기록된 관측·이벤트 외의 관측 간격·누락 미확인)");
    if (problems.monitor_coverage === "stopped_in_window") unmeasured.push("감시 마지막 관측 이후의 장애 유무");
    if (problems.monitor_coverage === "unknown") unmeasured.push("감시 실행 범위");
  }
  if (problems.notice_audit_coverage !== "available") unmeasured.push("안내 전환 기록의 완전성");
  if (problems.alerts && problems.alerts.history_coverage !== "complete") unmeasured.push("알림 기간 전체합계(보존된 최종 시도 행만 집계)");
  if (unmeasured.length === 0) lines.push("- (기재 없음)"); else for (const u of unmeasured) lines.push(`- ${u}`);
  lines.push("", "## 비고", input.notes || "(없음)", "", "---",
    "게시 범위·문구는 사람의 발신 승인을 따른다. 이 초안은 11월 전시 근거로 보존하되 실경기가 아닌 자료는 그 라벨을 유지한다.");
  const json = { schema: "pitcheezy-game-report-v1", generated_at: new Date(now).toISOString(), game_pk: input.game_pk,
    evidence: input.evidence, evidence_label: label, window: input.window, usage, problems, actions: input.actions,
    sources: input.sources, commands: input.commands, unmeasured, posted: false, approval_required: true };
  if (isSnapshot(input.usage_summary)) {
    const v = input.usage_summary, s = v.usage_summary;
    // Explicit allowlist: the operator JSON keeps provenance, not raw input, paths, IDs or free-form limits.
    json.usage_snapshot = { schema: v.schema, source_sha256: v.source_sha256, coverage: v.coverage,
      aggregation: v.aggregation, from_day: s.from_day, to_day: s.to_day, generated_at: s.generated_at };
  }
  return { markdown: lines.join("\n") + "\n", json };
}

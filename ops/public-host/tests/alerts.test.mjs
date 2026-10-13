import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, readFile, writeFile, unlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import { classifyEvent, validateAlertConfig, initialAlertState, validateAlertState, buildMessage, mockTransport, dispatchAlerts, PRUNE_AFTER_DAYS, toV1State, MAX_DELIVERY_ROWS, MAX_ALERT_STATE_BYTES, serializeAlertState } from "../alerts.mjs";
import { runAlertsOnce, downgradeState } from "../alerts-cli.mjs";
import { initialState, advanceState } from "../monitor.mjs";

const NOW = Date.parse("2026-10-13T03:00:00Z");
const sha = text => createHash("sha256").update(text).digest("hex");
const config = (extra = {}) => ({ schema: "pitcheezy-host-alerts-v1", transport: "mock",
  recipients: [{ id: "song", label: "Song side" }, { id: "ours", label: "our side" }], max_attempts: 3, remind_after_minutes: 0, ...extra });
const event = (kind, issues, at = NOW, id = sha(kind + issues.join(","))) => ({ id, kind, at_ms: at, issues });
const monitor = (events, incident = null) => ({ events, incident });

test("classification routes publisher causes to Song first, host causes to us first, mixed to both", () => {
  assert.equal(classifyEvent(event("opened", ["freshness_stale"])), "publish_stalled");
  assert.equal(classifyEvent(event("opened", ["health_missing"])), "publish_stalled");
  assert.equal(classifyEvent(event("opened", ["page_http_error", "health_http_error"])), "host_error");
  assert.equal(classifyEvent(event("opened", ["health_network_error"])), "host_error");
  assert.equal(classifyEvent(event("opened", ["freshness_stale", "page_http_error"])), "unclassified");
  assert.equal(classifyEvent(event("opened", ["page_notice_active", "health_notice_active"])), "notice_active");
  assert.equal(classifyEvent(event("opened", ["page_access_required", "health_access_required"])), "access_gate");
  assert.equal(classifyEvent(event("opened", ["something_new"])), "unclassified");
  assert.equal(classifyEvent(event("recovered", [])), "recovered");
  assert.throws(() => classifyEvent({ id: "x", kind: "opened", at_ms: NOW, issues: [] }), /invalid_event/);
  assert.throws(() => classifyEvent(event("exploded", [])), /invalid_event/);
});

test("config and state validation reject unsupported transports, wrong recipients and bad limits", () => {
  validateAlertConfig(config());
  for (const bad of [config({ transport: "email" }), config({ recipients: [{ id: "song", label: "x" }] }),
    config({ recipients: [{ id: "song", label: "a" }, { id: "song", label: "b" }] }),
    config({ recipients: [{ id: "song", label: "a", address: "x@y" }, { id: "ours", label: "b" }] }),
    config({ max_attempts: 0 }), config({ max_attempts: 6 }), config({ remind_after_minutes: -1 }), config({ extra: 1 })]) {
    assert.throws(() => validateAlertConfig(bad), /invalid_config|unsupported_transport|invalid_recipients|invalid_limits/);
  }
  validateAlertState(initialAlertState());
  assert.throws(() => validateAlertState({ ...initialAlertState(), mock_only: false }), /state_invalid/);
  assert.throws(() => validateAlertState({ ...initialAlertState(), deliveries: { bad: {} } }), /state_invalid/);
});

test("each monitor event reaches both recipients once; repeats are suppressed; recovery is informational", async () => {
  const transport = mockTransport();
  const opened = event("opened", ["freshness_stale"]);
  let state = initialAlertState();
  let result = await dispatchAlerts(state, monitor([opened], opened), config(), transport, { now: NOW });
  state = result.state;
  assert.deepEqual(result.receipt.acknowledged.sort(), [opened.id + ":opened:ours", opened.id + ":opened:song"]);
  assert.equal(transport.sent.length, 2);
  assert.deepEqual(transport.sent.map(m => m.recipient).sort(), ["ours", "song"]);
  assert.equal(transport.sent[0].first_responder, "song");
  assert.equal(transport.sent[0].delivery_confirmed, false);
  assert.equal(state.deliveries[opened.id + ":opened:song"].acknowledged_by_transport, true);
  result = await dispatchAlerts(state, monitor([opened], opened), config(), transport, { now: NOW + 60000 });
  assert.equal(result.receipt.attempted.length, 0);
  assert.equal(result.receipt.suppressed.length, 2);
  assert.equal(transport.sent.length, 2);
  const recovered = { ...opened, kind: "recovered", at_ms: NOW + 120000, issues: [] };
  result = await dispatchAlerts(result.state, monitor([opened, recovered], null), config(), transport, { now: NOW + 120000 });
  assert.equal(result.receipt.acknowledged.length, 2);
  assert.equal(transport.sent.at(-1).category, "recovered");
  assert.equal(transport.sent.at(-1).severity, "info");
  assert.equal(transport.sent.length, 4);
});

test("delivery failures retry across runs up to max_attempts, then stay recorded as undelivered", async () => {
  const transport = mockTransport({ failBeforeSuccess: { ours: 2 } });
  const opened = event("opened", ["page_http_error"]);
  let { state, receipt } = await dispatchAlerts(initialAlertState(), monitor([opened], opened), config(), transport, { now: NOW });
  assert.deepEqual(receipt.acknowledged, [opened.id + ":opened:song"]);
  assert.equal(receipt.failed.length, 1); assert.equal(receipt.failed[0].code, "mock_transport_failure");
  assert.equal(state.pending.length, 1);
  ({ state, receipt } = await dispatchAlerts(state, monitor([opened], opened), config(), transport, { now: NOW + 1000 }));
  assert.equal(receipt.failed.length, 1); assert.equal(state.deliveries[opened.id + ":opened:ours"].attempts, 2);
  ({ state, receipt } = await dispatchAlerts(state, monitor([opened], opened), config(), transport, { now: NOW + 2000 }));
  assert.deepEqual(receipt.acknowledged, [opened.id + ":opened:ours"]);
  assert.equal(state.pending.length, 0);
  assert.equal(transport.sent.map(m => m.recipient).join(","), "song,ours");
  const broken = { name: "mock", deliver: async () => { throw new Error("secret transport detail"); } };
  let s = initialAlertState();
  for (let i = 0; i < 4; i++) ({ state: s } = await dispatchAlerts(s, monitor([opened], opened), config(), broken, { now: NOW + i }));
  assert.equal(s.deliveries[opened.id + ":opened:song"].attempts, 3);
  assert.equal(s.deliveries[opened.id + ":opened:song"].status, "undelivered");
  assert.equal(s.pending.length, 0, "exhausted attempts are not queued forever");
  assert.doesNotMatch(JSON.stringify(s), /secret transport detail/);
});

test("reminders for a still-open incident fire once per window and stop after recovery", async () => {
  const transport = mockTransport();
  const opened = event("opened", ["freshness_stale"]);
  let { state } = await dispatchAlerts(initialAlertState(), monitor([opened], opened), config({ remind_after_minutes: 30 }), transport, { now: NOW });
  ({ state } = await dispatchAlerts(state, monitor([opened], opened), config({ remind_after_minutes: 30 }), transport, { now: NOW + 29 * 60000 }));
  assert.equal(transport.sent.length, 2);
  let result = await dispatchAlerts(state, monitor([opened], opened), config({ remind_after_minutes: 30 }), transport, { now: NOW + 31 * 60000 });
  assert.equal(result.receipt.reminders.length, 2);
  assert.equal(transport.sent.length, 4);
  assert.equal(transport.sent.at(-1).reminder, 1);
  result = await dispatchAlerts(result.state, monitor([opened], opened), config({ remind_after_minutes: 30 }), transport, { now: NOW + 45 * 60000 });
  assert.equal(transport.sent.length, 4, "same window is not repeated");
  const recovered = { ...opened, kind: "recovered", at_ms: NOW + 50 * 60000, issues: [] };
  result = await dispatchAlerts(result.state, monitor([opened, recovered], null), config({ remind_after_minutes: 30 }), transport, { now: NOW + 90 * 60000 });
  assert.equal(result.receipt.reminders.length, 0);
  assert.equal(transport.sent.at(-1).category, "recovered");
});

test("a failed reminder is retried in the same window until max_attempts; settled old rows are pruned", async () => {
  const sent = []; let failReminderOnce = true;
  const transport = { name: "mock", sent, async deliver(m) {
    if (m.reminder && failReminderOnce) { failReminderOnce = false; return { ok: false, code: "mock_transport_failure" }; }
    sent.push(m); return { ok: true, code: "mock_acknowledged" };
  } };
  const opened = event("opened", ["freshness_stale"]);
  const cfg = config({ remind_after_minutes: 30 });
  let { state } = await dispatchAlerts(initialAlertState(), monitor([opened], opened), cfg, transport, { now: NOW });
  let result = await dispatchAlerts(state, monitor([opened], opened), cfg, transport, { now: NOW + 31 * 60000 });
  assert.equal(result.receipt.failed.length, 1);
  assert.equal(result.state.deliveries[opened.id + ":reminder:1:song"].status, "undelivered");
  result = await dispatchAlerts(result.state, monitor([opened], opened), cfg, transport, { now: NOW + 32 * 60000 });
  assert.deepEqual(result.receipt.reminders, [opened.id + ":reminder:1:song"], "only the failed reminder is retried");
  assert.equal(result.state.deliveries[opened.id + ":reminder:1:song"].status, "acknowledged");
  assert.equal(result.state.deliveries[opened.id + ":reminder:1:song"].attempts, 2);
  result = await dispatchAlerts(result.state, monitor([opened], opened), cfg, transport, { now: NOW + 33 * 60000 });
  assert.equal(result.receipt.reminders.length, 0, "an acknowledged reminder is not repeated");
  // Pruning: settled rows older than the retention window disappear; live or retryable rows stay.
  const old = NOW - (PRUNE_AFTER_DAYS + 1) * 86400000;
  const seeded = { ...initialAlertState(), deliveries: {
    [sha("old") + ":opened:song"]: { status: "acknowledged", attempts: 1, last_attempt_ms: old, acknowledged_by_transport: true },
    [sha("old") + ":opened:ours"]: { status: "undelivered", attempts: 3, last_attempt_ms: old, acknowledged_by_transport: false },
    [sha("retry") + ":opened:ours"]: { status: "undelivered", attempts: 1, last_attempt_ms: old, acknowledged_by_transport: false },
    [sha("recent") + ":opened:song"]: { status: "acknowledged", attempts: 1, last_attempt_ms: NOW - 1000, acknowledged_by_transport: true },
  } };
  const pruned = await dispatchAlerts(seeded, monitor([]), config(), mockTransport(), { now: NOW });
  assert.equal(pruned.receipt.pruned, 2);
  assert.deepEqual(Object.keys(pruned.state.deliveries).sort(), [sha("recent") + ":opened:song", sha("retry") + ":opened:ours"].sort());
});

test("messages carry categories and placeholder wording only, never addresses, origins or tokens", () => {
  const m = buildMessage(event("opened", ["health_http_error"]), "host_error", "ours");
  assert.equal(m.first_responder, "ours");
  assert.match(m.text, /^\[개발용 문구\]/);
  assert.doesNotMatch(JSON.stringify(m), /https?:\/\/|@|Bearer|token/i);
});

test("real monitor state transitions feed the dispatcher end to end", async () => {
  const mconfig = { schema: "pitcheezy-host-monitor-v1", origin: "https://public.example.test", allow_loopback_http: false,
    timeout_ms: 200, max_body_bytes: 4096, timestamp_pointer: "/synthetic/at", timestamp_format: "rfc3339",
    max_age_seconds: 120, clock_skew_seconds: 30, page_sha256: null };
  let mstate = initialState(mconfig);
  const report = (status, issues, at) => ({ schema: "pitcheezy-host-probe-v1", config_sha256: mstate.config_sha256,
    observed_at_ms: at, status, issues, page: {}, health: {} });
  mstate = advanceState(mstate, report("failed", ["freshness_stale"], NOW), mconfig).state;
  mstate = advanceState(mstate, report("failed", ["freshness_stale"], NOW + 1000), mconfig).state;
  assert.ok(mstate.incident);
  const transport = mockTransport();
  const { state, receipt } = await dispatchAlerts(initialAlertState(), mstate, config(), transport, { now: NOW + 2000 });
  assert.equal(receipt.acknowledged.length, 2);
  assert.equal(transport.sent[0].category, "publish_stalled");
  mstate = advanceState(mstate, report("available", [], NOW + 3000), mconfig).state;
  mstate = advanceState(mstate, report("available", [], NOW + 4000), mconfig).state;
  const after = await dispatchAlerts(state, mstate, config(), transport, { now: NOW + 5000 });
  assert.equal(after.receipt.acknowledged.length, 2);
  assert.equal(transport.sent.at(-1).category, "recovered");
});

test("CLI runs once over a monitor state file with a mock transport and refuses other transports", async () => {
  const dir = await mkdtemp(join(tmpdir(), "pitcheezy-alerts-"));
  const opened = event("opened", ["freshness_stale"]);
  await writeFile(join(dir, "monitor.json"), JSON.stringify({ state: { events: [opened], incident: opened }, report: {} }));
  await writeFile(join(dir, "alerts.json"), JSON.stringify(config()));
  const run = promisify(execFile);
  const cli = fileURLToPath(new URL("../alerts-cli.mjs", import.meta.url));
  const first = await run(process.execPath, [cli, "--monitor-state", join(dir, "monitor.json"), "--config", join(dir, "alerts.json"), "--state", join(dir, "alert-state.json")]);
  const out = JSON.parse(first.stdout);
  assert.equal(out.receipt.acknowledged.length, 2);
  assert.equal(out.delivery_confirmed, false);
  assert.equal(out.transport, "mock");
  const saved = JSON.parse(await readFile(join(dir, "alert-state.json"), "utf8"));
  assert.equal(Object.keys(saved.deliveries).length, 2);
  const second = await run(process.execPath, [cli, "--monitor-state", join(dir, "monitor.json"), "--config", join(dir, "alerts.json"), "--state", join(dir, "alert-state.json")]);
  assert.equal(JSON.parse(second.stdout).receipt.suppressed.length, 2);
  // A lock file held by another run refuses this one before any delivery or state write.
  await writeFile(join(dir, "alert-state.json.lock"), "");
  await assert.rejects(run(process.execPath, [cli, "--monitor-state", join(dir, "monitor.json"), "--config", join(dir, "alerts.json"), "--state", join(dir, "alert-state.json")]),
    e => e.code === 2 && /already_running_or_stale_lock/.test(e.stderr));
  await unlink(join(dir, "alert-state.json.lock"));
  const third = await run(process.execPath, [cli, "--monitor-state", join(dir, "monitor.json"), "--config", join(dir, "alerts.json"), "--state", join(dir, "alert-state.json")]);
  assert.equal(JSON.parse(third.stdout).receipt.suppressed.length, 2);
  await assert.rejects(readFile(join(dir, "alert-state.json.lock")), e => e.code === "ENOENT", "the lock is released after the run");
  await writeFile(join(dir, "bad.json"), JSON.stringify(config({ transport: "email" })));
  await assert.rejects(run(process.execPath, [cli, "--monitor-state", join(dir, "monitor.json"), "--config", join(dir, "bad.json"), "--state", join(dir, "other-state.json")]),
    e => e.code === 2 && /unsupported_transport/.test(e.stderr));
});

// WS-alert2: re-classification of an open incident (two-run rule, numbered announcements, no downgrade in reminders).
const MCFG = { schema: "pitcheezy-host-monitor-v1", origin: "https://public.example.test", allow_loopback_http: false,
  timeout_ms: 200, max_body_bytes: 4096, timestamp_pointer: "/synthetic/at", timestamp_format: "rfc3339",
  max_age_seconds: 120, clock_skew_seconds: 30, page_sha256: null };
const NOTICE = ["page_notice_active", "health_notice_active"], STALE = ["freshness_stale"], HOST = ["page_http_error", "health_http_error"];
const LOGIN = ["access_login_rate_limited"];
/** Plays probe outcomes through the REAL monitor state machine and the dispatcher, one dispatch per recorded run. */
async function play(steps, { cfg = config(), transport = mockTransport(), stepMs = 60000 } = {}) {
  let mstate = initialState(MCFG), astate = initialAlertState(), clock = NOW;
  const receipts = [];
  for (const issues of steps) {
    clock += stepMs;
    const report = { schema: "pitcheezy-host-probe-v1", config_sha256: mstate.config_sha256, observed_at_ms: clock,
      status: issues.length ? "failed" : "available", issues, page: {}, health: {} };
    mstate = advanceState(mstate, report, MCFG).state;
    const r = await dispatchAlerts(astate, mstate, cfg, transport, { now: clock, latestReport: report });
    astate = r.state; receipts.push(r.receipt);
  }
  return { transport, receipts, mstate, astate, clock };
}
const rows = t => t.sent.map(m => [m.recipient, m.event_kind, m.category, m.first_responder, m.reclassified_from]);

test("an incident opened under the notice is re-announced to both sides once publishing has stalled for two runs", async () => {
  const { transport, receipts } = await play([[], NOTICE, NOTICE, STALE, STALE, STALE]);
  assert.deepEqual(rows(transport), [
    ["song", "opened", "notice_active", "none", null], ["ours", "opened", "notice_active", "none", null],
    ["song", "reclassified", "publish_stalled", "song", "notice_active"], ["ours", "reclassified", "publish_stalled", "song", "notice_active"]]);
  assert.equal(receipts[3].reclassified.length, 0, "one stale run is not enough");
  assert.equal(receipts[4].reclassified.length, 2);
  const m = transport.sent[2];
  assert.match(m.text, /원인 재분류: notice_active → publish_stalled/);
  assert.deepEqual(m.issues, STALE); assert.notEqual(m.cause_observed_at, m.observed_at);
  assert.equal(m.schema, "pitcheezy-host-alert-message-v2");
});

test("a one-run blip never re-routes; a sustained change and the return to the earlier cause are both announced", async () => {
  const blip = await play([[], STALE, STALE, LOGIN, STALE, HOST, STALE, STALE]);
  assert.deepEqual(blip.transport.sent.map(m => m.category), ["publish_stalled", "publish_stalled"], "single-run blips are silent");
  const flip = await play([[], STALE, STALE, HOST, HOST, STALE, STALE]);
  assert.deepEqual(rows(flip.transport).slice(2), [
    ["song", "reclassified", "host_error", "ours", "publish_stalled"], ["ours", "reclassified", "host_error", "ours", "publish_stalled"],
    ["song", "reclassified", "publish_stalled", "song", "host_error"], ["ours", "reclassified", "publish_stalled", "song", "host_error"]]);
  assert.ok(flip.receipts[6].reclassified.every(k => k.includes(":reclassified:2:publish_stalled:")), "announcements are numbered");
});

test("a transient monitor login failure that opened the incident does not keep a later stall on our side", async () => {
  const { transport } = await play([[], LOGIN, LOGIN, STALE, STALE]);
  assert.deepEqual(transport.sent.map(m => [m.category, m.first_responder]),
    [["host_error", "ours"], ["host_error", "ours"], ["publish_stalled", "song"], ["publish_stalled", "song"]]);
});

test("informational causes never replace an announced cause; reminders keep the last announced cause", async () => {
  const cfg = config({ remind_after_minutes: 3 });
  // Stall, then someone switches the notice on (health becomes unmeasurable): reminders stay publish_stalled / Song.
  const a = await play([[], STALE, STALE, NOTICE, NOTICE, NOTICE, NOTICE, NOTICE, NOTICE], { cfg });
  const remindersA = a.transport.sent.filter(m => m.reminder > 0);
  assert.ok(remindersA.length >= 2);
  assert.ok(remindersA.every(m => m.category === "publish_stalled" && m.first_responder === "song" && m.severity === "incident"));
  assert.equal(a.transport.sent.filter(m => m.event_kind === "reclassified").length, 0);
  // Opened under the notice, re-announced as a stall, then one passing run at a window boundary: still publish_stalled.
  const b = await play([[], NOTICE, NOTICE, STALE, STALE, [], STALE, STALE, STALE], { cfg });
  const remindersB = b.transport.sent.filter(m => m.reminder > 0);
  assert.ok(remindersB.length >= 1);
  assert.ok(remindersB.every(m => m.category === "publish_stalled"), JSON.stringify(remindersB.map(m => m.category)));
});

test("a failed re-classification is retried while the incident stays open, whatever the current cause; closing settles it", async () => {
  const transport = mockTransport({ failBeforeSuccess: {} });
  let failSong = true;
  const flaky = { name: "mock", sent: transport.sent, async deliver(m) {
    if (failSong && m.recipient === "song" && m.event_kind === "reclassified") return { ok: false, code: "mock_transport_failure" };
    return transport.deliver(m);
  } };
  let r = await play([[], NOTICE, NOTICE, STALE, STALE, NOTICE], { transport: flaky });
  const key = r.receipts[4].reclassified.find(k => k.endsWith(":song"));
  assert.equal(r.astate.deliveries[key].status, "undelivered");
  assert.equal(r.astate.deliveries[key].attempts, 2, "retried on the next run although the current cause is the notice again");
  failSong = false;
  const mstate = r.mstate;
  const third = await dispatchAlerts(r.astate, mstate, config(), flaky, { now: r.clock + 1 });
  assert.equal(third.state.deliveries[key].status, "acknowledged");
  // Same failure, but the incident closes before delivery: the row is settled as abandoned (and later pruned).
  failSong = true;
  r = await play([[], NOTICE, NOTICE, STALE, STALE, [], []], { transport: flaky });
  const k2 = r.receipts[4].reclassified.find(k => k.endsWith(":song"));
  assert.equal(r.astate.deliveries[k2].status, "abandoned");
  assert.equal(r.astate.pending.length, 0);
  assert.deepEqual(r.astate.incidents, {}, "closed incidents leave no memory");
  const later = await dispatchAlerts(r.astate, r.mstate, config(), mockTransport(), { now: r.clock + (PRUNE_AFTER_DAYS + 1) * 86400000 });
  assert.equal(later.state.deliveries[k2], undefined, "settled abandoned rows are pruned");
});

test("a recipient whose opening alert is still retrying gets the re-classification after it, not before", async () => {
  let songFailures = 1;
  const transport = mockTransport();
  const flaky = { name: "mock", sent: transport.sent, async deliver(m) {
    if (m.recipient === "song" && m.event_kind === "opened" && songFailures > 0) { songFailures--; return { ok: false, code: "mock_transport_failure" }; }
    return transport.deliver(m);
  } };
  // The incident opens and is re-classified in quick succession while Song's opening alert keeps failing once.
  songFailures = 3;
  const { receipts } = await play([[], NOTICE, NOTICE, STALE, STALE, STALE, STALE], { transport: flaky, cfg: config({ max_attempts: 5 }) });
  assert.ok(receipts.some(r => r.deferred.some(k => k.endsWith(":song"))), "deferred while the opening alert retried");
  const song = transport.sent.filter(m => m.recipient === "song").map(m => m.event_kind);
  assert.deepEqual(song, ["opened", "reclassified"], "Song hears the opening before the re-classification");
});

test("malformed monitor records are skipped without blocking other alerts; the same report is counted once", async () => {
  const good = event("opened", ["page_http_error"]);
  const bad = { id: "not-a-hash", kind: "opened", at_ms: NOW, issues: [] };
  const r = await dispatchAlerts(initialAlertState(), { events: [bad, good], incident: { ...good, issues: ["Bad Issue"] } }, config(), mockTransport(), { now: NOW });
  assert.equal(r.receipt.invalid_events, 1); assert.equal(r.receipt.incident_invalid, true);
  assert.equal(r.receipt.acknowledged.length, 2, "the valid event still reached both sides");
  // Running the CLI twice on the same monitor record must not count one run as two.
  let mstate = initialState(MCFG), clock = NOW, report;
  for (const issues of [[], NOTICE, NOTICE, STALE]) {
    clock += 60000;
    report = { schema: "pitcheezy-host-probe-v1", config_sha256: mstate.config_sha256, observed_at_ms: clock,
      status: issues.length ? "failed" : "available", issues, page: {}, health: {} };
    mstate = advanceState(mstate, report, MCFG).state;
  }
  let a = initialAlertState();
  for (let i = 0; i < 3; i++) ({ state: a } = await dispatchAlerts(a, mstate, config(), mockTransport(), { now: clock, latestReport: report }));
  assert.equal(a.incidents[mstate.incident.id].candidate_runs, 1);
  assert.equal(Object.keys(a.deliveries).some(k => k.includes(":reclassified:")), false);
});

test("v1 alert state files are upgraded; v3 keys and statuses are validated", async () => {
  const v1 = { schema: "pitcheezy-host-alert-state-v1", deliveries: { [sha("o") + ":opened:song"]: { status: "acknowledged", attempts: 1, last_attempt_ms: NOW, acknowledged_by_transport: true } },
    pending: [], mock_only: true };
  const up = validateAlertState(v1);
  assert.equal(up.schema, "pitcheezy-host-alert-state-v3"); assert.deepEqual(up.incidents, {});
  assert.throws(() => validateAlertState({ ...v1, deliveries: { [sha("o") + ":opened:song"]: { status: "abandoned", attempts: 0, last_attempt_ms: NOW, acknowledged_by_transport: false } } }), /state_invalid/);
  const v2 = initialAlertState();
  for (const bad of [sha("x") + ":reclassified:publish_stalled:song", sha("x") + ":reclassified:1:Bad-Name:song", sha("x") + ":reminder:1:song:extra"]) {
    assert.throws(() => validateAlertState({ ...v2, deliveries: { [bad]: { status: "acknowledged", attempts: 1, last_attempt_ms: NOW, acknowledged_by_transport: true } } }), /state_invalid/, bad);
  }
  validateAlertState({ ...v2, deliveries: { [sha("x") + ":reclassified:3:host_error:ours"]: { status: "abandoned", attempts: 1, last_attempt_ms: NOW, acknowledged_by_transport: false } } });
  assert.throws(() => validateAlertState({ ...v2, incidents: { [sha("x")]: { opened_category: "nope" } } }), /state_invalid/);
});

test("the CLI forwards the latest report and writes a v3 state", async () => {
  const dir = await mkdtemp(join(tmpdir(), "pitcheezy-alerts-reclass-"));
  let mstate = initialState(MCFG), clock = Date.now() - 600000, report;
  const run = promisify(execFile);
  const cli = fileURLToPath(new URL("../alerts-cli.mjs", import.meta.url));
  await writeFile(join(dir, "alerts.json"), JSON.stringify(config()));
  const messages = [];
  for (const issues of [[], NOTICE, NOTICE, STALE, STALE]) {
    clock += 60000;
    report = { schema: "pitcheezy-host-probe-v1", config_sha256: mstate.config_sha256, observed_at_ms: clock,
      status: issues.length ? "failed" : "available", issues, page: {}, health: {} };
    mstate = advanceState(mstate, report, MCFG).state;
    await writeFile(join(dir, "monitor.json"), JSON.stringify({ state: mstate, report }));
    const out = JSON.parse((await run(process.execPath, [cli, "--monitor-state", join(dir, "monitor.json"), "--config", join(dir, "alerts.json"), "--state", join(dir, "state.json")])).stdout);
    messages.push(...out.mock_messages.map(m => [m.event_kind, m.category]));
  }
  assert.deepEqual(messages, [["opened", "notice_active"], ["opened", "notice_active"], ["reclassified", "publish_stalled"], ["reclassified", "publish_stalled"]]);
  assert.equal(JSON.parse(await readFile(join(dir, "state.json"), "utf8")).schema, "pitcheezy-host-alert-state-v3");
});

test("a newer re-classification supersedes an older one still retrying; each recipient ends on the current cause", async () => {
  // Song's channel fails every re-classification during runs 4-6, then recovers.
  let run = 0;
  const transport = mockTransport();
  const flaky = { name: "mock", sent: transport.sent, async deliver(m) {
    if (m.recipient === "song" && m.event_kind === "reclassified" && run < 7) return { ok: false, code: "mock_transport_failure" };
    return transport.deliver(m);
  } };
  let mstate = initialState(MCFG), astate = initialAlertState(), clock = NOW;
  for (const issues of [[], STALE, STALE, HOST, HOST, STALE, STALE, STALE]) {
    run++; clock += 60000;
    const report = { schema: "pitcheezy-host-probe-v1", config_sha256: mstate.config_sha256, observed_at_ms: clock,
      status: issues.length ? "failed" : "available", issues, page: {}, health: {} };
    mstate = advanceState(mstate, report, MCFG).state;
    ({ state: astate } = await dispatchAlerts(astate, mstate, config(), flaky, { now: clock, latestReport: report }));
  }
  const song = transport.sent.filter(m => m.recipient === "song");
  assert.equal(song.at(-1).category, "publish_stalled", "Song's latest message names the current cause");
  assert.equal(song.some(m => m.event_kind === "reclassified" && m.category === "host_error"), false, "the superseded announcement is never delivered late");
  const old = Object.entries(astate.deliveries).find(([k]) => k.includes(":reclassified:1:host_error:song"));
  assert.equal(old[1].status, "abandoned");
  assert.equal(transport.sent.filter(m => m.event_kind === "reclassified").every(m => Number.isInteger(m.announcement)), true);
});

test("an incident announced as informational escalates when two consecutive runs need action, even if their causes alternate", async () => {
  const { transport } = await play([[], NOTICE, NOTICE, STALE, HOST, STALE, HOST, STALE]);
  const reclassified = transport.sent.filter(m => m.event_kind === "reclassified");
  assert.deepEqual(reclassified.map(m => [m.recipient, m.category, m.first_responder]), [["song", "unclassified", "both"], ["ours", "unclassified", "both"]]);
  // Once an actionable cause is announced, a one-run blip still does not re-route (the alternation rule only lifts informational ones).
  const blip = await play([[], STALE, STALE, LOGIN, STALE, STALE]);
  assert.equal(blip.transport.sent.filter(m => m.event_kind === "reclassified").length, 0);
});

test("pruning never forgets opened/recovered rows whose events the monitor still lists (no re-send after 30 days)", async () => {
  const { transport, mstate, astate, clock } = await play([[], STALE, STALE, [], []]);
  assert.deepEqual(transport.sent.map(m => m.event_kind), ["opened", "opened", "recovered", "recovered"]);
  const later = mockTransport();
  const r = await dispatchAlerts(astate, mstate, config(), later, { now: clock + (PRUNE_AFTER_DAYS + 5) * 86400000 });
  assert.equal(later.sent.length, 0, "old events still listed by the monitor are not alerted again");
  assert.equal(r.receipt.pruned, 0);
  const gone = await dispatchAlerts(r.state, { ...mstate, events: [] }, config(), mockTransport(), { now: clock + (PRUNE_AFTER_DAYS + 5) * 86400000 });
  assert.equal(gone.receipt.pruned, 4, "rows are pruned once the monitor no longer lists their events");
});

test("rollback aid: a v3 state converts to a v1 state that keeps the dedup history", async () => {
  const cfg = config();
  const flaky = mockTransport({ failBeforeSuccess: { song: 0 } });
  const { astate, mstate } = await play([[], NOTICE, NOTICE, STALE, STALE, [], []], { transport: flaky });
  const v1 = toV1State(astate, cfg.max_attempts);
  assert.equal(v1.schema, "pitcheezy-host-alert-state-v1");
  assert.equal(Object.keys(v1).sort().join(","), "deliveries,mock_only,pending,schema");
  assert.equal(Object.keys(v1.deliveries).some(k => k.includes(":reclassified:")), false);
  assert.ok(Object.values(v1.deliveries).every(r => ["acknowledged", "undelivered"].includes(r.status)));
  // The previous dispatcher logic (dedup on opened/recovered) would send nothing new from this history:
  const replay = await dispatchAlerts(v1, mstate, cfg, mockTransport(), { now: NOW + 3600000 });
  assert.equal(replay.receipt.attempted.length, 0);
  const dir = await mkdtemp(join(tmpdir(), "pitcheezy-alerts-downgrade-"));
  await writeFile(join(dir, "alerts.json"), JSON.stringify(cfg));
  await writeFile(join(dir, "state.json"), JSON.stringify(astate));
  const run = promisify(execFile);
  const cli = fileURLToPath(new URL("../alerts-cli.mjs", import.meta.url));
  const out = JSON.parse((await run(process.execPath, [cli, "--config", join(dir, "alerts.json"), "--state", join(dir, "state.json"), "--downgrade-to-v1", join(dir, "v1.json")])).stdout);
  assert.equal(out.schema, "pitcheezy-host-alerts-downgrade-v1");
  assert.equal(JSON.parse(await readFile(join(dir, "v1.json"), "utf8")).schema, "pitcheezy-host-alert-state-v1");
  assert.equal(JSON.parse(await readFile(join(dir, "state.json"), "utf8")).schema, "pitcheezy-host-alert-state-v3", "the source is unchanged");
  await assert.rejects(run(process.execPath, [cli, "--config", join(dir, "alerts.json"), "--state", join(dir, "state.json"), "--downgrade-to-v1", join(dir, "v1.json")]),
    e => e.code === 2, "never overwrites an existing file");
});



test("recovery waits for each recipient's opening retry and remains the last message after closure", async () => {
  const sent = []; let openingAttempts = 0;
  const transport = { name: "mock", sent, async deliver(message) {
    if (message.recipient === "song" && message.event_kind === "opened" && ++openingAttempts <= 3) return { ok: false };
    sent.push(message); return { ok: true };
  } };
  const result = await play([STALE, STALE, [], [], []], { cfg: config({ max_attempts: 5 }), transport });
  assert.equal(result.mstate.incident, null);
  assert.deepEqual(sent.filter(m => m.recipient === "song").map(m => m.event_kind), ["opened", "recovered"]);
  assert.deepEqual(sent.filter(m => m.recipient === "ours").map(m => m.event_kind), ["opened", "recovered"]);
  assert.equal(result.receipts[3].deferred.some(k => k.endsWith(":recovered:song")), true);
  assert.equal(result.receipts[3].acknowledged.some(k => k.endsWith(":recovered:ours")), true,
    "one recipient's opening retries do not hold back the other recipient's recovery");
  assert.equal(result.astate.pending.length, 0);
});

test("an exhausted opening retry allows that recipient's recovery without waiting forever", async () => {
  const sent = []; let openingAttempts = 0;
  const transport = { name: "mock", sent, async deliver(message) {
    if (message.recipient === "song" && message.event_kind === "opened") { openingAttempts++; return { ok: false }; }
    sent.push(message); return { ok: true };
  } };
  const result = await play([STALE, STALE, [], [], []], { cfg: config({ max_attempts: 3 }), transport });
  assert.equal(openingAttempts, 3);
  assert.deepEqual(sent.filter(m => m.recipient === "song").map(m => m.event_kind), ["recovered"]);
  assert.equal(result.receipts[3].acknowledged.some(k => k.endsWith(":recovered:song")), true);
  assert.equal(result.astate.pending.length, 0);
});


test("a full monitor backlog keeps event, re-classification and reminder retries within the v3 bound", async () => {
  let mstate = initialState(MCFG), clock = NOW, latestReport;
  const record = issues => {
    clock += 60000;
    latestReport = { schema: "pitcheezy-host-probe-v1", config_sha256: mstate.config_sha256,
      observed_at_ms: clock, status: issues.length ? "failed" : "available", issues, page: {}, health: {} };
    mstate = advanceState(mstate, latestReport, MCFG).state;
  };
  // Start alerting after the monitor has already filled its bounded 100-event history.
  for (let i = 0; i < 50; i++) { record(STALE); record(STALE); record([]); record([]); }
  record(NOTICE); record(NOTICE);
  assert.equal(mstate.events.length, 100);
  const cfg = config({ max_attempts: 5, remind_after_minutes: 1 });
  const broken = { name: "mock", deliver: async () => ({ ok: false }) };
  let { state } = await dispatchAlerts(initialAlertState(), mstate, cfg, broken, { now: clock, latestReport });
  assert.equal(state.pending.length, 200);
  record(STALE);
  ({ state } = await dispatchAlerts(state, mstate, cfg, broken, { now: clock, latestReport }));
  assert.equal(state.pending.length, 202);
  record(STALE);
  ({ state } = await dispatchAlerts(state, mstate, cfg, broken, { now: clock, latestReport }));
  assert.equal(state.pending.length, 204);
  validateAlertState(state);
  const legacy = toV1State(state, cfg.max_attempts);
  assert.ok(legacy.pending.length <= 200, "rollback still satisfies the original v1 pending limit");
  validateAlertState(legacy);
  for (let i = 0; i < MAX_DELIVERY_ROWS + 20; i++) state.deliveries[`${sha("old-history-" + i)}:opened:song`] = {
    status: "acknowledged", attempts: 1, last_attempt_ms: NOW, acknowledged_by_transport: true,
  };
  const required = state.pending.map(p => p.key);
  ({ state } = await dispatchAlerts(state, mstate, cfg, broken, { now: clock, latestReport }));
  assert.equal(Object.keys(state.deliveries).length, MAX_DELIVERY_ROWS);
  assert.ok(required.every(k => state.pending.some(p => p.key === k)), "compaction preserves every pending retry");
  assert.equal(state.history_pruned_through_ms, NOW);
  const recovered = await dispatchAlerts(state, mstate, cfg, mockTransport(), { now: clock, latestReport });
  assert.equal(recovered.state.pending.length, 0);
  assert.equal(recovered.receipt.acknowledged.length, 204, "every retained event and current announcement is retried");
});


test("repeated CLI saves compact history and remain readable on the following invocation", async () => {
  const dir = await mkdtemp(join(tmpdir(), "pitcheezy-alerts-bounded-"));
  const cfg = config({ remind_after_minutes: 1 });
  const opened = event("opened", STALE);
  const paths = ["monitor.json", "config.json", "state.json"].map(name => join(dir, name));
  await writeFile(paths[0], JSON.stringify({ state: monitor([opened], opened), report: {} }));
  await writeFile(paths[1], JSON.stringify(cfg));
  // Cross the history bound using real reads, atomic saves and the next CLI invocation.
  for (let minute = 0; minute <= 520; minute++) {
    const result = await runAlertsOnce(...paths, { now: NOW + minute * 60000 });
    assert.equal(result.mock_messages.length, 2, "opening then each new reminder is delivered once per recipient");
  }
  const saved = await readFile(paths[2], "utf8"), state = JSON.parse(saved);
  assert.ok(Buffer.byteLength(saved) <= MAX_ALERT_STATE_BYTES);
  assert.equal(Object.keys(state.deliveries).length, MAX_DELIVERY_ROWS);
  assert.ok(state.history_pruned_through_ms > NOW);
  assert.equal(state.history_complete_from_ms, NOW);
  assert.equal(state.last_dispatch_ms, NOW + 520 * 60000);
  assert.ok(state.deliveries[`${opened.id}:opened:song`], "listed opening remains a deduplication anchor");
  const repeat = await runAlertsOnce(...paths, { now: NOW + 520 * 60000 });
  assert.equal(repeat.mock_messages.length, 0, "compaction does not resend the current reminder or opening");
});

test("an oversized legacy v2 file is compacted, rolled back and upgraded without replaying retained history", async () => {
  const dir = await mkdtemp(join(tmpdir(), "pitcheezy-alerts-legacy-size-"));
  const cfg = config({ remind_after_minutes: 1 });
  const opened = event("opened", STALE);
  const first = await dispatchAlerts(initialAlertState(), monitor([opened], opened), cfg, mockTransport(), { now: NOW });
  const { history_complete_from_ms, history_pruned_through_ms, last_dispatch_ms, ...legacy } = first.state;
  legacy.schema = "pitcheezy-host-alert-state-v2";
  for (let minute = 1; minute <= 2300; minute++) for (const recipient of ["song", "ours"]) {
    legacy.deliveries[`${opened.id}:reminder:${minute}:${recipient}`] = {
      status: "acknowledged", attempts: 1, last_attempt_ms: NOW + minute * 60000, acknowledged_by_transport: true,
    };
  }
  const orphanKey = `${sha("orphan-retry")}:opened:song`;
  legacy.deliveries[orphanKey] = { status: "undelivered", attempts: 1, last_attempt_ms: NOW, acknowledged_by_transport: false };
  const configPath = join(dir, "config.json"), monitorPath = join(dir, "monitor.json"), statePath = join(dir, "state.json");
  const oversized = JSON.stringify(legacy, null, 2) + "\n";
  assert.ok(Buffer.byteLength(oversized) > MAX_ALERT_STATE_BYTES, "reproduces the old self-locking file size");
  await writeFile(configPath, JSON.stringify(cfg));
  await writeFile(monitorPath, JSON.stringify({ state: monitor([opened], opened), report: {} }));
  await writeFile(statePath, oversized);
  const now = NOW + 2300 * 60000;
  const compacted = await runAlertsOnce(monitorPath, configPath, statePath, { now });
  assert.equal(compacted.mock_messages.length, 0, "retained history is not replayed while migrating");
  const saved = await readFile(statePath, "utf8"), state = JSON.parse(saved);
  assert.equal(state.schema, "pitcheezy-host-alert-state-v3");
  assert.ok(Buffer.byteLength(saved) <= MAX_ALERT_STATE_BYTES);
  assert.equal(Object.keys(state.deliveries).length, MAX_DELIVERY_ROWS);
  assert.equal(state.history_complete_from_ms, now, "legacy retention before this run is unknown");
  assert.deepEqual(state.deliveries[orphanKey], legacy.deliveries[orphanKey], "compaction preserves unresolved orphan evidence");
  assert.ok(state.history_pruned_through_ms > NOW);
  assert.equal((await runAlertsOnce(monitorPath, configPath, statePath, { now })).mock_messages.length, 0);
  const output = join(dir, "v1.json");
  const rollback = await downgradeState(configPath, statePath, output);
  assert.equal(rollback.history_coverage, "unknown", "v1 cannot carry coverage metadata");
  const v1 = JSON.parse(await readFile(output, "utf8"));
  assert.equal(v1.schema, "pitcheezy-host-alert-state-v1");
  const upgraded = validateAlertState(v1);
  assert.equal(upgraded.history_complete_from_ms, null, "round-tripping never invents legacy completeness");
  assert.equal((await runAlertsOnce(monitorPath, configPath, output, { now })).mock_messages.length, 0);
  assert.equal((await runAlertsOnce(monitorPath, configPath, output, { now: now + 60000 })).mock_messages.length, 2);
});

test("output capacity is checked before creating a rollback file and clocks cannot replay pruned history", async () => {
  const dir = await mkdtemp(join(tmpdir(), "pitcheezy-alerts-write-limit-"));
  const source = initialAlertState();
  source.pending.push({ key: `${sha("large")}:opened:song`, message: { value: "x".repeat(MAX_ALERT_STATE_BYTES) } });
  assert.throws(() => serializeAlertState(source), /state_capacity_exceeded/);
  await writeFile(join(dir, "config.json"), JSON.stringify(config()));
  await writeFile(join(dir, "source.json"), JSON.stringify(source));
  await assert.rejects(downgradeState(join(dir, "config.json"), join(dir, "source.json"), join(dir, "v1.json")), /state_capacity_exceeded/);
  await assert.rejects(readFile(join(dir, "v1.json")), e => e.code === "ENOENT");
  const { state } = await dispatchAlerts(initialAlertState(), monitor([]), config(), mockTransport(), { now: NOW });
  await assert.rejects(dispatchAlerts(state, monitor([]), config(), mockTransport(), { now: NOW - 1 }), /clock_error/);
});

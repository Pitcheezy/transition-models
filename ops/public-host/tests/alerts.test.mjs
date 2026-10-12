import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, readFile, writeFile, unlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import { classifyEvent, validateAlertConfig, initialAlertState, validateAlertState, buildMessage, mockTransport, dispatchAlerts, PRUNE_AFTER_DAYS } from "../alerts.mjs";
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

import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, readFile, readdir, realpath, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import { initialAlertState, dispatchAlerts, mockTransport } from "../alerts.mjs";
import { runAlertsOnce } from "../alerts-cli.mjs";
import { initialState, advanceState } from "../monitor.mjs";

const NOW = Date.parse("2026-10-15T00:00:00Z");
const RETRY_AT = NOW + 31 * 60000;
const opened = { id: createHash("sha256").update("ws-alert3-synthetic-incident").digest("hex"),
  kind: "opened", at_ms: NOW, issues: ["freshness_stale"] };
const config = () => ({ schema: "pitcheezy-host-alerts-v1", transport: "mock",
  recipients: [{ id: "song", label: "Song side" }, { id: "ours", label: "our side" }],
  max_attempts: 3, remind_after_minutes: 30 });
const record = (incident = opened) => ({ state: { events: [opened], incident }, report: {} });
const cli = fileURLToPath(new URL("../alerts-cli.mjs", import.meta.url));
const run = promisify(execFile);

async function pendingReminders() {
  const monitor = record().state;
  const first = await dispatchAlerts(initialAlertState(), monitor, config(), mockTransport(), { now: NOW });
  const second = await dispatchAlerts(first.state, monitor, config(),
    { name: "mock", deliver: async () => ({ ok: false }) }, { now: RETRY_AT });
  assert.equal(second.state.pending.length, 2);
  assert.equal(Object.keys(second.state.incidents).length, 1);
  return JSON.stringify(second.state, null, 2) + "\n";
}

async function files(monitorRecord, stateText = null, cfg = config()) {
  // Resolve platform temp-directory aliases so the existing no-symlink input rule is respected.
  const dir = await realpath(await mkdtemp(join(tmpdir(), "pitcheezy-alert-input-")));
  const paths = ["monitor.json", "config.json", "state.json"].map(name => join(dir, name));
  await writeFile(paths[0], JSON.stringify(monitorRecord));
  await writeFile(paths[1], JSON.stringify(cfg));
  if (stateText !== null) await writeFile(paths[2], stateText);
  return { dir, paths };
}
const cliArgs = paths => [cli, "--monitor-state", paths[0], "--config", paths[1], "--state", paths[2]];
const invalidInput = error => error.code === "invalid_monitor_state";

const invalidIncidents = [
  ["missing", () => ({ state: { events: [] } })],
  ["false", () => record(false)],
  ["zero", () => record(0)],
  ["empty string", () => record("")],
  ["empty object", () => record({})],
  ["array", () => record([])],
  ["recovered event", () => record({ ...opened, kind: "recovered", issues: [] })],
  ["bad event identity", () => record({ ...opened, id: "not-a-hash" })],
  ["bad event issue", () => record({ ...opened, issues: ["Bad Issue"] })],
];

const invalidEnvelopes = [
  ["null envelope", () => null],
  ["array envelope", () => []],
  ["missing state", () => ({ report: {} })],
  ["null state", () => ({ state: null })],
  ["array state", () => ({ state: [] })],
  ["string state", () => ({ state: "wrong file" })],
  ["missing events", () => ({ state: { incident: null } })],
  ["null events", () => ({ state: { events: null, incident: null } })],
  ["object events", () => ({ state: { events: {}, incident: null } })],
  ["oversized events", () => ({ state: { events: Array(101).fill(opened), incident: null } })],
];

test("missing or malformed incident input never discards persisted reminder retries", async () => {
  const original = await pendingReminders();
  for (const [label, make] of invalidIncidents) {
    const { dir, paths } = await files(make(), original);
    const before = (await readdir(dir)).sort();
    await assert.rejects(runAlertsOnce(...paths, { now: RETRY_AT + 1 }), invalidInput, label);
    assert.equal(await readFile(paths[2], "utf8"), original, label + ": persisted retries are unchanged");
    assert.deepEqual((await readdir(dir)).sort(), before, label + ": no lock or temporary file");
  }
});

test("invalid monitor envelopes and event containers preserve the entire existing alert state", async () => {
  const original = await pendingReminders();
  for (const [label, make] of invalidEnvelopes) {
    const { dir, paths } = await files(make(), original);
    await assert.rejects(runAlertsOnce(...paths, { now: RETRY_AT + 1 }), invalidInput, label);
    assert.equal(await readFile(paths[2], "utf8"), original, label);
    assert.deepEqual((await readdir(dir)).sort(), ["config.json", "monitor.json", "state.json"], label);
  }
});

test("invalid monitor inputs cannot initialize a new alert state", async () => {
  for (const [label, make] of [...invalidIncidents, ...invalidEnvelopes]) {
    const { dir, paths } = await files(make());
    await assert.rejects(runAlertsOnce(...paths, { now: RETRY_AT + 1 }), invalidInput, label);
    assert.deepEqual((await readdir(dir)).sort(), ["config.json", "monitor.json"], label);
  }
});

test("a valid explicit null incident still settles reminders and processes recovery", async () => {
  const original = await pendingReminders();
  const recovered = { ...opened, kind: "recovered", at_ms: RETRY_AT + 1, issues: [] };
  const { paths } = await files({ state: { events: [opened, recovered], incident: null }, report: {} }, original);
  const result = await runAlertsOnce(...paths, { now: RETRY_AT + 2 });
  assert.equal(result.receipt.abandoned.length, 2);
  assert.equal(result.pending, 0);
  assert.equal(result.receipt.incident_invalid, false);
  assert.deepEqual(result.mock_messages.map(message => [message.recipient, message.event_kind]),
    [["song", "recovered"], ["ours", "recovered"]]);
  const saved = JSON.parse(await readFile(paths[2], "utf8"));
  assert.equal(Object.keys(saved.incidents).length, 0);
  assert.equal(saved.pending.length, 0);
});

test("valid open incident retries both saved reminders with absent or empty report", async () => {
  const original = await pendingReminders();
  for (const includeReport of [false, true]) {
    const monitor = record();
    if (!includeReport) delete monitor.report;
    const { paths } = await files(monitor, original);
    const result = await runAlertsOnce(...paths, { now: RETRY_AT + 1 });
    assert.equal(result.receipt.abandoned.length, 0);
    assert.equal(result.pending, 0);
    assert.deepEqual(result.mock_messages.map(message => [message.recipient, message.reminder]),
      [["song", 1], ["ours", 1]]);
    const saved = JSON.parse(await readFile(paths[2], "utf8"));
    assert.equal(Object.keys(saved.incidents).length, 1);
    assert.equal(saved.pending.length, 0);
  }
});

test("full real monitor state-machine records remain accepted", async () => {
  const monitorConfig = { schema: "pitcheezy-host-monitor-v1", origin: "https://synthetic.example.invalid",
    allow_loopback_http: false, timeout_ms: 200, max_body_bytes: 4096,
    timestamp_pointer: null, timestamp_format: "rfc3339", max_age_seconds: 120,
    clock_skew_seconds: 30, page_sha256: null };
  let state = initialState(monitorConfig), report;
  for (const at of [NOW, NOW + 1]) {
    report = { schema: "pitcheezy-host-probe-v1", config_sha256: state.config_sha256,
      observed_at_ms: at, status: "failed", issues: ["freshness_stale"], page: {}, health: {} };
    state = advanceState(state, report, monitorConfig).state;
  }
  const { paths } = await files({ state, report });
  const result = await runAlertsOnce(...paths, { now: NOW + 2 });
  assert.equal(result.mock_messages.length, 2);
  assert.equal(result.receipt.invalid_events, 0);
  assert.equal(result.receipt.incident_invalid, false);
});

test("individual invalid events still allow good events and return CLI exit one", async () => {
  const bad = { ...opened, id: "bad-event" };
  const cfg = { ...config(), remind_after_minutes: 0 };
  const { paths } = await files({ state: { events: [bad, opened], incident: opened }, report: {} }, null, cfg);
  await assert.rejects(run(process.execPath, cliArgs(paths)), error => {
    assert.equal(error.code, 1);
    const result = JSON.parse(error.stdout);
    assert.equal(result.receipt.invalid_events, 1);
    assert.equal(result.receipt.incident_invalid, false);
    assert.equal(result.mock_messages.length, 2);
    assert.equal(result.delivery_confirmed, false);
    return true;
  });
  const saved = JSON.parse(await readFile(paths[2], "utf8"));
  assert.equal(Object.keys(saved.deliveries).length, 2);
});

test("actual CLI refuses missing incident with exit two and leaves existing pending bytes intact", async () => {
  const original = await pendingReminders();
  const { dir, paths } = await files({ state: { events: [] } }, original);
  await assert.rejects(run(process.execPath, cliArgs(paths)), error => {
    assert.equal(error.code, 2);
    assert.deepEqual(JSON.parse(error.stderr), { ok: false, code: "invalid_monitor_state" });
    assert.equal(error.stdout, "");
    return true;
  });
  assert.equal(await readFile(paths[2], "utf8"), original);
  assert.deepEqual((await readdir(dir)).sort(), ["config.json", "monitor.json", "state.json"]);
});

test("invalid monitor input refuses before touching a lock held by another invocation", async () => {
  const original = await pendingReminders();
  const { dir, paths } = await files(record(false), original);
  await writeFile(paths[2] + ".lock", "synthetic-other-run");
  await assert.rejects(runAlertsOnce(...paths, { now: RETRY_AT + 1 }), invalidInput);
  assert.equal(await readFile(paths[2] + ".lock", "utf8"), "synthetic-other-run");
  assert.equal(await readFile(paths[2], "utf8"), original);
  assert.deepEqual((await readdir(dir)).sort(), ["config.json", "monitor.json", "state.json", "state.json.lock"]);
});

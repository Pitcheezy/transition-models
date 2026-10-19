import test from "node:test";
import assert from "node:assert/strict";
import { readFile, readdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import { initialAlertState, validateAlertState, classifyEvent, buildMessage, dispatchAlerts, mockTransport } from "../alerts.mjs";
import { runAlertsOnce } from "../alerts-cli.mjs";
import { createTestDirectory } from "./helpers/owned-temp.mjs";
const NOW = Date.parse("2026-10-19T00:00:00.000Z"), MAX_DATE = 8640000000000000;
const opened = { id: "a".repeat(64), kind: "opened", at_ms: NOW, issues: ["freshness_stale"] };
const config = { schema: "pitcheezy-host-alerts-v1", transport: "mock", recipients: [{ id: "song", label: "Song" }, { id: "ours", label: "Ours" }], max_attempts: 3, remind_after_minutes: 0 };
const monitor = (events = [], incident = null, last_observed_ms = NOW) => ({ events, incident, last_observed_ms });
const run = promisify(execFile), cli = fileURLToPath(new URL("../alerts-cli.mjs", import.meta.url));
const args = p => [cli, "--monitor-state", p[0], "--config", p[1], "--state", p[2]];
async function pending(event = opened) {
  return (await dispatchAlerts(initialAlertState(), monitor([event], event, event.at_ms), config,
    mockTransport({ failBeforeSuccess: { song: 1, ours: 1 } }), { now: event.at_ms })).state;
}
function version(state, schema) {
  const s = structuredClone(state); s.schema = `pitcheezy-host-alert-state-v${schema}`;
  if (schema < 3) for (const f of ["history_pruned_through_ms", "history_complete_from_ms", "last_dispatch_ms"]) delete s[f];
  if (schema === 1) {
    delete s.incidents;
    for (const p of s.pending) { p.message.schema = "pitcheezy-host-alert-message-v1";
      for (const f of ["cause_observed_at", "reclassified_from", "announcement"]) delete p.message[f]; }
  }
  return s;
}
async function files(t, record, state) {
  const dir = await createTestDirectory(t), paths = ["monitor.json", "config.json", "state.json"].map(x => join(dir, x));
  await writeFile(paths[0], JSON.stringify(record)); await writeFile(paths[1], JSON.stringify(config));
  if (state !== undefined) await writeFile(paths[2], JSON.stringify(state));
  return { dir, paths };
}

test("unrenderable event dates are skipped while later valid events reach both recipients", async () => {
  const bad = [MAX_DATE + 1, Number.MAX_SAFE_INTEGER].map((at_ms, i) => ({ ...opened, id: String(i + 1).repeat(64), at_ms }));
  const transport = mockTransport();
  const r = await dispatchAlerts(initialAlertState(), monitor([...bad, opened]), config, transport, { now: NOW });
  assert.equal(r.receipt.invalid_events, 2);
  assert.deepEqual(transport.sent.map(m => [m.incident_id, m.recipient]), [[opened.id, "song"], [opened.id, "ours"]]);
  for (const e of bad) {
    assert.throws(() => classifyEvent(e), { code: "invalid_event" });
    assert.throws(() => buildMessage(e, "publish_stalled", "song"), { code: "invalid_event" });
  }
  assert.throws(() => buildMessage(opened, "publish_stalled", "song", { causeObservedMs: Number.MAX_SAFE_INTEGER }), { code: "invalid_event" });
});

test("generated ISO epoch, leap-day and expanded-year dates remain retryable in v1/v2/v3", async () => {
  for (const at_ms of [0, Date.parse("2024-02-29T00:00:00.123Z"), Date.parse("+010000-01-01T00:00:00.000Z"), MAX_DATE]) {
    const e = { ...opened, at_ms }, original = await pending(e);
    assert.equal(classifyEvent(e), "publish_stalled");
    for (const schema of [1, 2, 3]) {
      const transport = mockTransport();
      const r = await dispatchAlerts(version(original, schema), monitor(), config, transport, { now: Number.MAX_SAFE_INTEGER });
      assert.equal(r.state.schema, "pitcheezy-host-alert-state-v3"); assert.equal(transport.sent.length, 2);
      assert.ok(transport.sent.every(m => m.observed_at === new Date(at_ms).toISOString()));
      assert.equal(r.state.last_dispatch_ms, Number.MAX_SAFE_INTEGER, "arithmetic clock remains safe-integer bounded");
    }
  }
});

test("impossible or noncanonical pending dates refuse before transport without rewriting source", async () => {
  const original = await pending();
  const bad = ["2026-02-30T00:00:00.000Z", "2026-04-31T00:00:00.000Z", "2026-10-19T24:00:00.000Z",
    "2026-10-19T00:00:00Z", "10/19/2026", "+275760-09-13T00:00:00.001Z"];
  for (const schema of [1, 2, 3]) for (const at of bad) {
    const state = version(original, schema); state.pending[0].message.observed_at = at;
    const before = JSON.stringify(state), transport = mockTransport();
    await assert.rejects(dispatchAlerts(state, monitor(), config, transport, { now: NOW }), { code: "state_invalid" });
    assert.equal(transport.sent.length, 0); assert.equal(JSON.stringify(state), before);
  }
});

test("reclassification cause dates must be canonical and not precede the incident", () => {
  const e = { ...opened, at_ms: Date.parse("2026-02-01T00:00:00.000Z") }, state = initialAlertState();
  const key = `${e.id}:reclassified:1:host_error:song`;
  state.deliveries[key] = { status: "undelivered", attempts: 1, last_attempt_ms: NOW, acknowledged_by_transport: false };
  state.pending = [{ key, message: buildMessage(e, "host_error", "song", { kind: "reclassified", announcement: 1,
    reclassifiedFrom: "publish_stalled", causeObservedMs: NOW, causeIssues: ["page_http_error"] }) }];
  validateAlertState(state);
  for (const schema of [2, 3]) for (const at of ["2026-02-30T00:00:00.000Z", "2026-10-19T24:00:00.000Z", "2026-10-19T00:00:00Z", "2026-01-31T00:00:00.000Z"]) {
    const bad = version(state, schema); bad.pending[0].message.cause_observed_at = at;
    assert.throws(() => validateAlertState(bad), { code: "state_invalid" });
  }
  state.pending[0].message.cause_observed_at = new Date(MAX_DATE).toISOString();
  assert.equal(validateAlertState(state).pending[0].message.cause_observed_at, new Date(MAX_DATE).toISOString());
});

test("nonrenderable latest-report dates do not advance reclassification or crash dispatch", async () => {
  let state = (await dispatchAlerts(initialAlertState(), monitor([opened], opened), config, mockTransport(), { now: NOW,
    latestReport: { observed_at_ms: NOW, status: "failed", issues: opened.issues } })).state;
  for (const at of [MAX_DATE + 1, Number.MAX_SAFE_INTEGER]) {
    const transport = mockTransport();
    const r = await dispatchAlerts(state, monitor([], opened, at), config, transport, { now: at,
      latestReport: { observed_at_ms: at, status: "failed", issues: ["page_http_error"] } });
    assert.equal(r.state.incidents[opened.id].last_report_ms, NOW);
    assert.equal(r.state.incidents[opened.id].announced, "publish_stalled");
    assert.deepEqual(r.receipt.reclassified, []); assert.equal(transport.sent.length, 0); state = r.state;
  }
});

test("CLI skips an impossible event, saves valid deliveries and exits one", async t => {
  const bad = { ...opened, id: "b".repeat(64), at_ms: Number.MAX_SAFE_INTEGER };
  const { paths } = await files(t, { state: monitor([bad, opened], opened), report: {} });
  await assert.rejects(run(process.execPath, args(paths)), error => {
    assert.equal(error.code, 1); assert.equal(error.stderr, ""); const r = JSON.parse(error.stdout);
    assert.equal(r.receipt.invalid_events, 1); assert.equal(r.mock_messages.length, 2); return true;
  });
  assert.equal(Object.keys(JSON.parse(await readFile(paths[2], "utf8")).deliveries).length, 2);
});

test("CLI rejects an impossible open incident before taking a lock or changing retries", async t => {
  const bad = { ...opened, at_ms: Number.MAX_SAFE_INTEGER };
  const { dir, paths } = await files(t, { state: monitor([], bad), report: {} }, await pending());
  const before = await readFile(paths[2], "utf8"); await writeFile(paths[2] + ".lock", "unrelated-owner");
  const names = (await readdir(dir)).sort();
  await assert.rejects(runAlertsOnce(...paths, { now: NOW }), { code: "invalid_monitor_state" });
  assert.equal(await readFile(paths[2], "utf8"), before); assert.equal(await readFile(paths[2] + ".lock", "utf8"), "unrelated-owner");
  assert.deepEqual((await readdir(dir)).sort(), names);
});

test("CLI rejects impossible saved retry dates without output, replacing state or retaining locks", async t => {
  const state = await pending(); state.pending[0].message.observed_at = "2026-02-30T00:00:00.000Z";
  const { dir, paths } = await files(t, { state: monitor(), report: {} }, state);
  const before = await readFile(paths[2], "utf8"), names = (await readdir(dir)).sort();
  await assert.rejects(run(process.execPath, args(paths)), error => {
    assert.equal(error.code, 2); assert.equal(error.stdout, "");
    assert.deepEqual(JSON.parse(error.stderr), { ok: false, code: "state_invalid" }); return true;
  });
  assert.equal(await readFile(paths[2], "utf8"), before); assert.deepEqual((await readdir(dir)).sort(), names);
});

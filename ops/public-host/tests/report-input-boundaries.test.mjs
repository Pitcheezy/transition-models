import test from "node:test";
import assert from "node:assert/strict";
import { readFile, readdir, writeFile } from "node:fs/promises";
import { join } from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import { buildReport } from "../report.mjs";
import { createTestDirectory } from "./helpers/owned-temp.mjs";

const FROM = "2026-10-12T00:00:00Z", TO = "2026-10-12T23:59:59Z";
const START = Date.parse(FROM), END = Date.parse(TO), NOW = END + 1000;
const input = (extra = {}) => ({
  schema: "pitcheezy-game-report-input-v1", game_pk: 123, evidence: "synthetic",
  window: { from: FROM, to: TO },
  collection: { telemetry_enabled: false, feedback_enabled: false, consent_note: "synthetic", retain_days: 30 },
  usage_summary: null, monitor_state: null, notice_audit: null, alert_state: null, actions: [],
  sources: { host_commit: "a".repeat(40), frontend_commit: null, contract_version: null, release_manifest_sha256: null },
  commands: [], unmeasured: [], notes: "", ...extra,
});
const report = value => buildReport(value, { now: NOW });
const delivery = (extra = {}) => ({ status: "acknowledged", attempts: 1,
  last_attempt_ms: START + 1000, acknowledged_by_transport: true, ...extra });
const alerts = (version = 3, deliveries = { retained: delivery() }, extra = {}) => ({
  schema: `pitcheezy-host-alert-state-v${version}`, mock_only: true, deliveries, pending: [],
  ...(version === 3 ? { history_complete_from_ms: START, history_pruned_through_ms: null, last_dispatch_ms: END } : {}),
  ...extra,
});
const timestampCase = (field, at) => {
  if (field.startsWith("window.")) return input({ window: { from: at, to: at } });
  if (field === "actions") return input({ actions: [{ at, by: "ops", what: "synthetic action" }] });
  if (field === "notice_audit") return input({ notice_audit: [{ schema: "pitcheezy-notice-audit-v1",
    at, active: true, operator: "ops", reason: "synthetic notice", message_id: "maintenance" }] });
  return input({ usage_summary: { schema: "pitcheezy-usage-snapshot-v1", source_sha256: "b".repeat(64),
    coverage: "unverified", aggregation: "utc_day", usage_summary: { schema: "pitcheezy-usage-summary-v1",
      timezone: "UTC", from_day: "2026-10-12", to_day: "2026-10-12", generated_at: at,
      sessions: [], feedback: [], limits: "synthetic" } } });
};

for (const [field, code] of [["window.from", "invalid_window"], ["window.to", "invalid_window"],
  ["actions", "invalid_actions"], ["notice_audit", "invalid_notice_audit"],
  ["snapshot.generated_at", "invalid_usage_snapshot"]]) {
  test(`report rejects normalized calendar timestamps in ${field}`, () => {
    for (const at of ["2026-02-29T00:00:00Z", "2026-02-30T00:00:00.1Z",
      "2026-04-31T00:00:00.123Z", "2026-10-12T24:00:00Z"]) {
      const value = timestampCase(field, at);
      if (field === "window.from") value.window.to = new Date(at).toISOString();
      if (field === "window.to") value.window.from = new Date(at).toISOString();
      assert.throws(() => report(value), { code }, `${field}: ${at}`);
    }
  });
}

test("valid leap dates, accepted year range and timestamp precision remain unchanged", () => {
  for (const at of ["0000-02-29T00:00:00Z", "0099-01-01T00:00:00.1Z", "9999-12-31T23:59:59.999Z",
    "2024-02-29T23:59:59Z", "2024-02-29T23:59:59.1Z", "2024-02-29T23:59:59.12Z", "2024-02-29T23:59:59.123Z"]) {
    const value = timestampCase("window.from", at);
    const result = report(value);
    assert.deepEqual(result.json.window, { from: at, to: at });
    for (const field of ["actions", "notice_audit", "snapshot.generated_at"]) {
      assert.doesNotThrow(() => report(timestampCase(field, at)), `${field}: ${at}`);
    }
  }
});

test("malformed delivery rows cannot disappear as zero-count complete history", () => {
  const badRows = [null, [], true, "row", {}, delivery({ status: "unknown" }), delivery({ status: null })];
  for (const attempts of [undefined, null, "1", -1, 0.5, 101, NaN, Infinity]) badRows.push(delivery({ attempts }));
  for (const last_attempt_ms of [undefined, null, "not-a-timestamp", String(START), -1, 0.5,
    NaN, Infinity, Number.MAX_SAFE_INTEGER + 1]) badRows.push(delivery({ last_attempt_ms }));
  for (const row of badRows) {
    assert.throws(() => report(input({ alert_state: alerts(3, { retained: row }) })),
      { code: "invalid_alert_state" });
  }
  assert.throws(() => report(input({ alert_state: alerts(1, { retained: delivery({ status: "abandoned" }) }) })),
    { code: "invalid_alert_state" });
});

test("supplied pending containers must be arrays while omitted and null remain compatible", () => {
  for (const pending of ["pending", {}, 0, false]) {
    assert.throws(() => report(input({ alert_state: alerts(3, {}, { pending }) })), { code: "invalid_alert_state" });
  }
  for (const version of [1, 2, 3]) for (const pending of [undefined, null, [], [{ legacy: "payload" }]]) {
    const state = alerts(version, {}, { pending });
    if (pending === undefined) delete state.pending;
    assert.equal(report(input({ alert_state: state })).json.problems.alerts.pending, pending?.length ?? 0);
  }
});

test("minimal legacy and v3 rows retain counts, extra fields and unattempted waiting evidence", () => {
  for (const version of [1, 2, 3]) {
    const rows = {
      acknowledged: { status: "acknowledged", attempts: 100, last_attempt_ms: START + 1, extra: "retained" },
      undelivered: delivery({ status: "undelivered", attempts: 1 }),
      waiting: delivery({ status: "undelivered", attempts: 0 }),
      before: delivery({ last_attempt_ms: 0 }), after: delivery({ last_attempt_ms: Number.MAX_SAFE_INTEGER }),
      ...(version > 1 ? { abandoned: delivery({ status: "abandoned", attempts: 0 }) } : {}),
    };
    const state = alerts(version, rows, { extra: "ignored state metadata" });
    const frozen = structuredClone(state);
    const result = report(input({ alert_state: state }));
    assert.deepEqual(result.json.problems.alerts, {
      acknowledged_by_mock: 1, undelivered: 1, abandoned: version > 1 ? 1 : 0, waiting_unattempted: 1,
      pending: 0, delivery_confirmed: false, history_coverage: version === 3 ? "complete" : "unknown",
    });
    assert.deepEqual(state, frozen, "report validation never rewrites source state");
    assert.equal(Object.hasOwn(state, "incidents"), false, "minimal historical report input stays valid");
  }
});

test("valid v3 retained counts keep complete and partial coverage semantics", () => {
  for (const [change, coverage] of [[{}, "complete"], [{ history_complete_from_ms: START + 1 }, "partial"],
    [{ history_pruned_through_ms: START }, "partial"], [{ history_pruned_through_ms: START - 1 }, "complete"],
    [{ last_dispatch_ms: END - 1 }, "partial"], [{ last_dispatch_ms: null }, "partial"]]) {
    const result = report(input({ alert_state: alerts(3, undefined, change) }));
    assert.equal(result.json.problems.alerts.acknowledged_by_mock, 1);
    assert.equal(result.json.problems.alerts.history_coverage, coverage);
  }
});

test("CLI rejects bad timestamps and alert rows before creating reports or locks", async t => {
  const directory = await createTestDirectory(t);
  const source = join(directory, "input.json"), stored = join(directory, "stored-report.json");
  const cli = fileURLToPath(new URL("../report-cli.mjs", import.meta.url));
  const execute = promisify(execFile);
  const sentinel = "unrelated stored report must remain unchanged\n";
  await writeFile(stored, sentinel);
  const cases = [
    [timestampCase("window.from", "2026-02-30T00:00:00Z"), "invalid_window"],
    [input({ alert_state: alerts(3, { retained: delivery({ last_attempt_ms: "not-a-timestamp" }) }) }), "invalid_alert_state"],
  ];
  for (const [value, code] of cases) {
    const original = JSON.stringify(value) + "\n";
    await writeFile(source, original);
    const before = (await readdir(directory)).sort();
    await assert.rejects(execute(process.execPath, [cli, "--input", source, "--output-dir", directory],
      { windowsHide: true, timeout: 10000 }), error => {
      assert.equal(error.code, 2); assert.equal(error.stdout, "");
      assert.deepEqual(JSON.parse(error.stderr), { ok: false, code });
      return true;
    });
    assert.deepEqual((await readdir(directory)).sort(), before, "no draft or lock created");
    assert.equal(await readFile(source, "utf8"), original);
    assert.equal(await readFile(stored, "utf8"), sentinel);
  }
});

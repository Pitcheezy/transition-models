import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, writeFile, readFile, readdir, rm, access } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { EventEmitter, once } from "node:events";
import { createServer } from "node:http";
import { runBounded, validateRunnerOptions, interruptibleSleep } from "../monitor-runner.mjs";
import { main } from "../monitor-runner-cli.mjs";
import { configFingerprint } from "../monitor.mjs";

const config = extra => ({ schema: "pitcheezy-host-monitor-v1", origin: "https://private.example.invalid",
  allow_loopback_http: false, timeout_ms: 100, max_body_bytes: 1024,
  timestamp_pointer: "/at", timestamp_format: "rfc3339", max_age_seconds: 120,
  clock_skew_seconds: 30, page_sha256: null, ...extra });
const alertConfig = { schema: "pitcheezy-host-alerts-v1", transport: "mock",
  recipients: [{ id: "song", label: "Song" }, { id: "ours", label: "ours" }], max_attempts: 3, remind_after_minutes: 30 };
async function fixture(t, extra = {}) {
  const dir = await mkdtemp(join(tmpdir(), "pz-monitor-runner-"));
  t.after(() => rm(dir, { recursive: true, force: true }));
  const c = config(extra);
  const options = { configPath: join(dir, "config.json"), statePath: join(dir, "state.json"),
    execute: true, maxRuns: 3, maxDurationMs: 10000, intervalMs: 1000 };
  await writeFile(options.configPath, JSON.stringify(c));
  return { dir, c, options };
}
function clock() {
  let time = 0;
  return { monotonic: () => time, sleep: async ms => { time += ms; }, advance: ms => { time += ms; } };
}
function result(c, status = "available", time = 1, incident = false) {
  return { report: { schema: "pitcheezy-host-probe-v1", config_sha256: configFingerprint(c),
    observed_at_ms: time, status, issues: [] }, incident_open: incident };
}
async function withAlerts(f) {
  f.options.alertConfigPath = join(f.dir, "alerts-config.json");
  f.options.alertStatePath = join(f.dir, "alerts-state.json");
  await writeFile(f.options.alertConfigPath, JSON.stringify(alertConfig));
}
const okAlert = () => ({ mock_messages: [{}, {}], receipt: { failed: [], invalid_events: 0,
  incident_invalid: false, unrecoverable_events: [] } });

test("default dry-run reads config only and creates no lock, state, request or alerts", async t => {
  const f = await fixture(t); await withAlerts(f);
  const before = await readdir(f.dir);
  let calls = 0;
  const r = await runBounded({ ...f.options, execute: false }, { monitor: () => calls++, alerts: () => calls++ });
  assert.equal(r.mode, "dry_run"); assert.equal(r.attempts, 0); assert.equal(r.exit_code, 0);
  assert.equal(calls, 0); assert.deepEqual(await readdir(f.dir), before);
  assert.doesNotMatch(JSON.stringify(r), /private\.example|config\.json|state\.json|https:/);
});

test("count, duration, interval, boolean and path limits refuse invalid inputs", async t => {
  const { options } = await fixture(t);
  for (const bad of [{ maxRuns: 0 }, { maxRuns: 1001 }, { maxDurationMs: 86400001 },
    { maxDurationMs: 999 }, { intervalMs: 999 }, { intervalMs: 3600001 }, { execute: "yes" },
    { maxRuns: 1.2 }, { statePath: "" }, { alertConfigPath: "only-one" }]) {
    assert.throws(() => validateRunnerOptions({ ...options, ...bad }));
  }
  assert.equal(validateRunnerOptions({ configPath: "c", statePath: "s" }).execute, false);
});

test("mixed failure, partial and later success retain all outcomes and nonzero exit", async t => {
  const { options, c } = await fixture(t); const statuses = ["failed", "partial", "available"];
  let n = 0; const rows = [];
  const r = await runBounded(options, { ...clock(), monitor: async () => result(c, statuses[n++]), emit: row => rows.push(row) });
  assert.equal(r.attempts, 3); assert.equal(r.failed, 1); assert.equal(r.partial, 1); assert.equal(r.available, 1);
  assert.equal(r.exit_code, 1); assert.equal(r.stop_reason, "count_limit"); assert.equal(rows.length, 3);
  assert.equal(r.elapsed_ms, 2000);
});

test("partial and unresolved incident remain non-green even with available samples", async t => {
  const { options, c } = await fixture(t);
  const partial = await runBounded({ ...options, maxRuns: 1 }, { ...clock(), monitor: async () => result(c, "partial") });
  assert.equal(partial.exit_code, 3);
  const pending = await runBounded({ ...options, maxRuns: 1 }, { ...clock(), monitor: async () => result(c, "available", 1, true) });
  assert.equal(pending.incident_open_samples, 1); assert.equal(pending.exit_code, 1);
});

test("duration prevents starting a probe without its timeout budget and never catches up", async t => {
  const { options, c } = await fixture(t); const timer = clock(); let n = 0;
  const r = await runBounded({ ...options, maxRuns: 10, maxDurationMs: 2400 }, { ...timer,
    monitor: async () => { n++; timer.advance(200); return result(c); } });
  assert.equal(n, 2); assert.equal(r.stop_reason, "duration_limit"); assert.equal(r.elapsed_ms, 1400);
  const noBudget = await runBounded({ ...options, maxDurationMs: 1000 }, { ...clock(),
    monitor: async () => { throw new Error("should not run"); } });
  // One 100ms probe fits here; its mock failure is correctly a monitor error.
  assert.equal(noBudget.monitor_errors, 1);
  await writeFile(options.configPath, JSON.stringify(config({ timeout_ms: 1000, access_code_env: "PZ_TEST_CODE" })));
  const zero = await runBounded({ ...options, maxDurationMs: 1000 }, { ...clock(), monitor: async () => { throw new Error("no"); } });
  assert.equal(zero.attempts, 0); assert.equal(zero.stop_reason, "duration_limit"); assert.equal(zero.exit_code, 2);
});

test("monotonic clock reversal stops without fresh success", async t => {
  const { options, c } = await fixture(t); let now = 5;
  const r = await runBounded(options, { monotonic: () => now, monitor: async () => { now = 1; return result(c); } });
  assert.equal(r.monitor_errors, 1); assert.equal(r.exit_code, 2); assert.equal(r.last_error, "runner_clock_error");
});

test("runner holds its lock for the whole loop, removes it and permits restart", async t => {
  const { options, c } = await fixture(t); let nested;
  const r = await runBounded({ ...options, maxRuns: 1 }, { ...clock(), monitor: async () => {
    nested = await runBounded(options, { ...clock(), monitor: async () => assert.fail("overlap") });
    return result(c);
  } });
  assert.equal(r.exit_code, 0); assert.equal(nested.last_error, "runner_already_running_or_stale_lock");
  await assert.rejects(access(options.statePath + ".runner.lock"));
  const restart = await runBounded({ ...options, maxRuns: 1 }, { ...clock(), monitor: async () => result(c) });
  assert.equal(restart.exit_code, 0);
});

test("stale lock is preserved, never automatically removed", async t => {
  const { options } = await fixture(t); await writeFile(options.statePath + ".runner.lock", "operator check required");
  const r = await runBounded(options, { ...clock(), monitor: () => assert.fail("blocked") });
  assert.equal(r.exit_code, 2); assert.equal(await readFile(options.statePath + ".runner.lock", "utf8"), "operator check required");
});

test("config changes stop before the next probe and do not alert from saved success", async t => {
  const f = await fixture(t); await withAlerts(f); let alerts = 0;
  const r = await runBounded(f.options, { ...clock(), monitor: async () => {
    await writeFile(f.options.configPath, JSON.stringify(config({ max_age_seconds: 121 })));
    return result(f.c);
  }, alerts: async () => { alerts++; return okAlert(); } });
  assert.equal(r.monitor_errors, 1); assert.equal(r.last_error, "runner_config_changed");
  assert.equal(r.attempts, 1); assert.equal(alerts, 0);
});

test("monitor errors preserve old files and skip alerts with fixed, secret-free code", async t => {
  const f = await fixture(t); await withAlerts(f); await writeFile(f.options.statePath, "old-state");
  let alerts = 0;
  const r = await runBounded(f.options, { ...clock(), monitor: async () => { throw new Error("secret https://private.example/a?key=token"); },
    alerts: async () => { alerts++; return okAlert(); } });
  assert.equal(alerts, 0); assert.equal(r.exit_code, 2); assert.equal(r.last_error, "runner_io_error");
  assert.equal(await readFile(f.options.statePath, "utf8"), "old-state");
  assert.doesNotMatch(JSON.stringify(r), /secret|https:|token/);
});

test("bad config fingerprint from probe cannot count as success or trigger alerts", async t => {
  const f = await fixture(t); await withAlerts(f);
  const r = await runBounded(f.options, { ...clock(), monitor: async () => result(config({ max_age_seconds: 121 })),
    alerts: () => assert.fail("stale alert") });
  assert.equal(r.available, 0); assert.equal(r.last_error, "runner_report_changed"); assert.equal(r.exit_code, 2);
});

test("mock dispatch receives only the exact fresh report under the writer lock", async t => {
  const f = await fixture(t); await withAlerts(f); let n = 0;
  const r = await runBounded(f.options, { ...clock(), monitor: async () => {
    const v = result(f.c, "failed", ++n); await writeFile(f.options.statePath, JSON.stringify({ report: v.report })); return v;
  }, alerts: async () => { await access(f.options.statePath + ".lock"); return okAlert(); } });
  assert.equal(r.mock_alert_runs, 3); assert.equal(r.mock_messages, 6); assert.equal(r.delivery_confirmed, false);
  assert.equal(r.failed, 3); assert.equal(r.exit_code, 1);
  await assert.rejects(access(f.options.statePath + ".lock"));
});

test("intervening state writer or alert config change prevents dispatch", async t => {
  const f = await fixture(t); await withAlerts(f);
  const r = await runBounded(f.options, { ...clock(), monitor: async () => {
    await writeFile(f.options.statePath, JSON.stringify({ report: result(f.c, "available", 99).report })); return result(f.c);
  }, alerts: () => assert.fail("changed report") });
  assert.equal(r.alert_errors, 1); assert.equal(r.last_error, "runner_report_changed");
  const changed = await runBounded(f.options, { ...clock(), monitor: async () => {
    await writeFile(f.options.alertConfigPath, JSON.stringify({ ...alertConfig, remind_after_minutes: 31 })); return result(f.c);
  }, alerts: () => assert.fail("changed config") });
  assert.equal(changed.last_error, "runner_alert_config_changed");
});

test("mock delivery failure is cumulative error, not healthy exit", async t => {
  const f = await fixture(t); await withAlerts(f);
  const r = await runBounded(f.options, { ...clock(), monitor: async () => {
    const v = result(f.c); await writeFile(f.options.statePath, JSON.stringify({ report: v.report })); return v;
  }, alerts: async () => ({ ...okAlert(), receipt: { ...okAlert().receipt, failed: [{}] } }) });
  assert.equal(r.alert_errors, 1); assert.equal(r.exit_code, 2); assert.equal(r.attempts, 1);
});

test("path overlap refuses config/state/lock aliasing before writes", async t => {
  const f = await fixture(t);
  await assert.rejects(runBounded({ ...f.options, statePath: f.options.configPath }), { code: "runner_paths_overlap" });
  await withAlerts(f);
  await assert.rejects(runBounded({ ...f.options, alertStatePath: f.options.statePath + ".lock" }), { code: "runner_paths_overlap" });
});

test("abort during sleep stops promptly with preserved samples and cleaned locks", async t => {
  const f = await fixture(t); const controller = new AbortController(); let n = 0;
  const r = await runBounded(f.options, { ...clock(), signal: controller.signal, monitor: async () => { n++; return result(f.c); },
    sleep: async () => controller.abort() });
  assert.equal(n, 1); assert.equal(r.stop_reason, "interrupted"); assert.equal(r.exit_code, 130);
  await assert.rejects(access(f.options.statePath + ".runner.lock"));
  const before = performance.now(); const stop = new AbortController();
  const wait = interruptibleSleep(60000, stop.signal); stop.abort(); await wait;
  assert.ok(performance.now() - before < 1000);
});

test("CLI requires explicit execute limits and removes SIGINT/SIGTERM handlers", async t => {
  const f = await fixture(t); const signals = new EventEmitter(); let err = ""; let out = "";
  const base = ["--config", f.options.configPath, "--state", f.options.statePath];
  assert.equal(await main([...base, "--execute"], { signals, errorOutput: s => { err += s; } }), 2);
  assert.match(err, /execute_requires_explicit_limits/);
  for (const name of ["SIGINT", "SIGTERM"]) {
    const code = await main([...base, "--execute", "--max-runs", "2", "--max-duration-ms", "10000", "--interval-ms", "1000"], {
      signals, output: s => { out += s; }, run: (o, deps) => runBounded(o, { ...deps, ...clock(),
        monitor: async () => { signals.emit(name); return result(f.c); } }) });
    assert.equal(code, 130); assert.equal(signals.listenerCount("SIGINT"), 0); assert.equal(signals.listenerCount("SIGTERM"), 0);
  }
  assert.doesNotMatch(out, /private\.example|config\.json|https:/);
});

test("real one-shot local HTTP history resumes across runs, including mock opened/recovered", async t => {
  let bad = true; let requests = 0;
  const server = createServer((req, res) => {
    requests++; res.setHeader("Age", "0");
    if (bad) { res.writeHead(503); res.end("synthetic outage"); return; }
    res.setHeader("Content-Type", req.url === "/" ? "text/html" : "application/json");
    res.end(req.url === "/" ? "<!doctype html><html><title>synthetic</title></html>" : JSON.stringify({ at: new Date().toISOString() }));
  });
  server.listen(0, "127.0.0.1"); await once(server, "listening");
  t.after(() => new Promise(resolve => server.close(resolve)));
  const f = await fixture(t, { origin: `http://127.0.0.1:${server.address().port}`, allow_loopback_http: true, timeout_ms: 1000 });
  await withAlerts(f); const timer = clock();
  const deps = { ...timer, sleep: async ms => { timer.advance(ms); await new Promise(resolve => setTimeout(resolve, 3)); } };
  const first = await runBounded({ ...f.options, maxRuns: 2 }, deps);
  assert.equal(first.failed, 2); assert.equal(first.mock_messages, 2); assert.equal(first.exit_code, 1);
  const open = JSON.parse(await readFile(f.options.statePath)); assert.equal(open.state.events.length, 1);
  bad = false; await new Promise(resolve => setTimeout(resolve, 3));
  const second = await runBounded({ ...f.options, maxRuns: 2 }, deps);
  assert.equal(second.available, 2); assert.equal(second.mock_messages, 2);
  assert.equal(second.exit_code, 1); // first available sample still had an open incident
  const recovered = JSON.parse(await readFile(f.options.statePath));
  assert.equal(recovered.state.incident, null); assert.deepEqual(recovered.state.events.map(e => e.kind), ["opened", "recovered"]);
  assert.equal(requests, 8);
});

test("existing corrupt monitor state is preserved and never used for mock dispatch", async t => {
  const f = await fixture(t); await withAlerts(f); await writeFile(f.options.statePath, "{bad state");
  const r = await runBounded(f.options, { ...clock() });
  assert.equal(r.last_error, "input_invalid_json"); assert.equal(r.mock_alert_runs, 0); assert.equal(r.exit_code, 2);
  assert.equal(await readFile(f.options.statePath, "utf8"), "{bad state");
});

test("non-mock transport is rejected before probe, state or runner lock creation", async t => {
  const f = await fixture(t); await withAlerts(f);
  await writeFile(f.options.alertConfigPath, JSON.stringify({ ...alertConfig, transport: "smtp" }));
  const before = await readdir(f.dir);
  await assert.rejects(runBounded(f.options, { monitor: () => assert.fail("no request") }), { code: "unsupported_transport" });
  assert.deepEqual(await readdir(f.dir), before);
});

test("already-aborted run performs no probe or alert and does not leave locks", async t => {
  const f = await fixture(t); await withAlerts(f); const controller = new AbortController(); controller.abort();
  const r = await runBounded(f.options, { ...clock(), signal: controller.signal,
    monitor: () => assert.fail("no probe"), alerts: () => assert.fail("no alert") });
  assert.equal(r.attempts, 0); assert.equal(r.stop_reason, "interrupted"); assert.equal(r.exit_code, 130);
  await assert.rejects(access(f.options.statePath + ".runner.lock"));
});

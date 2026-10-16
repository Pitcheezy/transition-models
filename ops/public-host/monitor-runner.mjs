/** Bounded, foreground orchestration of the existing one-shot monitor and mock alerts. */
import { open, unlink } from "node:fs/promises";
import { performance } from "node:perf_hooks";
import { MonitorError, validateConfig, configFingerprint } from "./monitor.mjs";
import { AlertError, validateAlertConfig } from "./alerts.mjs";
import { readJson, plainPath, runOnce } from "./monitor-cli.mjs";
import { runAlertsOnce } from "./alerts-cli.mjs";

export class RunnerError extends Error { constructor(code) { super(code); this.code = code; } }
const fail = code => { throw new RunnerError(code); };
const int = (v, min, max) => Number.isSafeInteger(v) && v >= min && v <= max;
const SAFE_CODES = new Set(["config_changed_use_new_state", "clock_error", "state_invalid", "invalid_report",
  "already_running_or_stale_lock", "linked_path", "input_not_regular_or_too_large", "input_changed_or_too_large",
  "input_invalid_json", "access_code_unavailable", "access_code_invalid", "unsupported_transport",
  "runner_already_running_or_stale_lock", "runner_config_changed", "runner_report_changed",
  "runner_clock_error", "runner_cleanup_failed", "runner_alert_config_changed"]);
const codeOf = error => SAFE_CODES.has(error?.code) ? error.code :
  error instanceof AlertError ? "alert_error" : error instanceof MonitorError ? "monitor_error" : "runner_io_error";

export function validateRunnerOptions(options) {
  const o = { execute: false, maxRuns: 3, maxDurationMs: 60000, intervalMs: 15000, ...options };
  if (typeof o.execute !== "boolean" || !int(o.maxRuns, 1, 1000) ||
      !int(o.maxDurationMs, 1000, 86400000) || !int(o.intervalMs, 1000, 3600000)) fail("invalid_runner_limits");
  if (typeof o.configPath !== "string" || !o.configPath || typeof o.statePath !== "string" || !o.statePath) fail("runner_paths_required");
  if (Boolean(o.alertConfigPath) !== Boolean(o.alertStatePath) ||
      (o.alertConfigPath && (typeof o.alertConfigPath !== "string" || typeof o.alertStatePath !== "string"))) fail("runner_alert_paths_required");
  return o;
}

/** Resolves promptly on shutdown; never leaves a live timer or signal listener behind. */
export function interruptibleSleep(ms, signal) {
  if (signal?.aborted) return Promise.resolve();
  return new Promise(resolve => {
    let timer;
    const finish = () => { clearTimeout(timer); signal?.removeEventListener("abort", finish); resolve(); };
    timer = setTimeout(finish, ms);
    signal?.addEventListener("abort", finish, { once: true });
  });
}

async function exclusive(path, work, conflictCode) {
  let lock;
  try { lock = await open(await plainPath(path), "wx", 0o600); }
  catch (error) { if (error.code === "EEXIST") fail(conflictCode); throw error; }
  try { return await work(); }
  finally {
    let clean = true;
    try { await lock.close(); } catch { clean = false; }
    try { await unlink(path); } catch { clean = false; }
    if (!clean) fail("runner_cleanup_failed");
  }
}

/** Run-local counters never reset when a later sample recovers. Monitor/alert histories remain authoritative. */
export async function runBounded(options, dependencies = {}) {
  const o = validateRunnerOptions(options);
  const deps = { monotonic: () => performance.now(), sleep: interruptibleSleep, monitor: runOnce,
    alerts: runAlertsOnce, emit: () => {}, ...dependencies };
  const signal = dependencies.signal;
  const config = validateConfig(await readJson(o.configPath, 16384));
  const fingerprint = configFingerprint(config);
  const configPath = await plainPath(o.configPath);
  const statePath = await plainPath(o.statePath);
  let alertConfig = null;
  const paths = [configPath, statePath, statePath + ".lock", statePath + ".runner.lock"];
  if (o.alertConfigPath) {
    o.alertConfigPath = await plainPath(o.alertConfigPath);
    o.alertStatePath = await plainPath(o.alertStatePath);
    paths.push(o.alertConfigPath, o.alertStatePath, o.alertStatePath + ".lock");
    alertConfig = validateAlertConfig(await readJson(o.alertConfigPath, 16384));
  }
  // Aliasing config/state/lock paths can overwrite inputs or deadlock the one-shot implementation.
  const normalized = paths.map(p => process.platform === "win32" ? p.toLowerCase() : p);
  if (new Set(normalized).size !== normalized.length) fail("runner_paths_overlap");
  const worstProbeMs = config.timeout_ms * (typeof config.access_code_env === "string" ? 2 : 1);
  const summary = { schema: "pitcheezy-host-monitor-runner-v1", mode: o.execute ? "execute" : "dry_run",
    config_sha256: fingerprint, max_runs: o.maxRuns, max_duration_ms: o.maxDurationMs, interval_ms: o.intervalMs,
    max_probe_ms: worstProbeMs, mock_alerts: Boolean(alertConfig), delivery_confirmed: false,
    attempts: 0, available: 0, partial: 0, failed: 0, incident_open_samples: 0,
    monitor_errors: 0, alert_errors: 0, mock_alert_runs: 0, mock_messages: 0,
    elapsed_ms: 0, stop_reason: o.execute ? null : "dry_run", last_error: null, exit_code: 0 };
  if (!o.execute) return summary; // No lock, write, environment access, or network request.
  let previousMono = deps.monotonic();
  const started = previousMono;
  const elapsed = () => {
    const now = deps.monotonic();
    if (!Number.isFinite(now) || now < previousMono) fail("runner_clock_error");
    previousMono = now;
    summary.elapsed_ms = Math.ceil(now - started);
    return summary.elapsed_ms;
  };
  const recordError = (error, kind = "monitor") => {
    summary[kind + "_errors"] += 1;
    summary.last_error = codeOf(error);
    summary.stop_reason = "error";
  };
  try {
    await exclusive(statePath + ".runner.lock", async () => {
      while (summary.attempts < o.maxRuns) {
        if (signal?.aborted) { summary.stop_reason = "interrupted"; break; }
        if (o.maxDurationMs - elapsed() < worstProbeMs) { summary.stop_reason = "duration_limit"; break; }
        let result;
        try {
          if (configFingerprint(validateConfig(await readJson(configPath, 16384))) !== fingerprint) fail("runner_config_changed");
          summary.attempts += 1;
          result = await deps.monitor(configPath, statePath);
          if (result?.report?.config_sha256 !== fingerprint ||
              !["available", "partial", "failed"].includes(result.report.status)) fail("runner_report_changed");
          summary[result.report.status] += 1;
          if (result.incident_open) summary.incident_open_samples += 1;
          if (configFingerprint(validateConfig(await readJson(configPath, 16384))) !== fingerprint) fail("runner_config_changed");
        } catch (error) { recordError(error); break; }
        if (alertConfig && !signal?.aborted) {
          try {
            const current = validateAlertConfig(await readJson(o.alertConfigPath, 16384));
            if (JSON.stringify(current) !== JSON.stringify(alertConfig)) fail("runner_alert_config_changed");
            // Share the existing one-shot writer's lock while checking and dispatching this exact report.
            // Never dispatch an old success after a failed probe or an intervening one-shot execution.
            const alert = await exclusive(statePath + ".lock", async () => {
              const stored = await readJson(statePath, 131072);
              if (JSON.stringify(stored?.report) !== JSON.stringify(result.report)) fail("runner_report_changed");
              return deps.alerts(statePath, o.alertConfigPath, o.alertStatePath);
            }, "already_running_or_stale_lock");
            summary.mock_alert_runs += 1;
            summary.mock_messages += alert.mock_messages.length;
            if (alert.receipt.failed.length || alert.receipt.invalid_events || alert.receipt.incident_invalid ||
                alert.receipt.unrecoverable_events.length) throw new AlertError("mock_alert_incomplete");
          } catch (error) { recordError(error, "alert"); break; }
        }
        // Fixed-size, fixed-code progress; no report body, contact labels, URL, cookie, or exception text.
        deps.emit({ sample: summary.attempts, status: result.report.status, incident_open: Boolean(result.incident_open) });
        if (signal?.aborted) { summary.stop_reason = "interrupted"; break; }
        if (summary.attempts >= o.maxRuns) { summary.stop_reason = "count_limit"; break; }
        const remaining = o.maxDurationMs - elapsed();
        if (remaining < o.intervalMs + worstProbeMs) { summary.stop_reason = "duration_limit"; break; }
        await deps.sleep(o.intervalMs, signal); // Delay after completion: never overlaps or catches up with a burst.
      }
    }, "runner_already_running_or_stale_lock");
    elapsed();
  } catch (error) { recordError(error); }
  summary.exit_code = summary.monitor_errors || summary.alert_errors ? 2 :
    summary.failed || summary.incident_open_samples ? 1 : summary.partial ? 3 :
    summary.stop_reason === "interrupted" ? 130 : summary.attempts === 0 ? 2 : 0;
  return summary;
}

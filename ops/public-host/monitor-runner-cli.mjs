/** Foreground bounded monitor. Dry-run unless --execute is explicitly supplied. */
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { RunnerError, runBounded } from "./monitor-runner.mjs";

const number = value => value === undefined ? undefined : /^(0|[1-9][0-9]{0,8})$/.test(value) ? Number(value) : NaN;
export async function main(args, { output = text => process.stdout.write(text),
  errorOutput = text => process.stderr.write(text), signals = process, run = runBounded } = {}) {
  const controller = new AbortController();
  const stop = () => controller.abort();
  let attached = false;
  try {
    const { values } = parseArgs({ args, options: { config: { type: "string" }, state: { type: "string" },
      execute: { type: "boolean", default: false }, "max-runs": { type: "string" },
      "max-duration-ms": { type: "string" }, "interval-ms": { type: "string" },
      "mock-alert-config": { type: "string" }, "mock-alert-state": { type: "string" } } });
    if (values.execute && ["max-runs", "max-duration-ms", "interval-ms"].some(key => values[key] === undefined)) {
      throw new RunnerError("execute_requires_explicit_limits");
    }
    const options = { configPath: values.config, statePath: values.state, execute: values.execute,
      alertConfigPath: values["mock-alert-config"], alertStatePath: values["mock-alert-state"] };
    for (const [flag, key] of [["max-runs", "maxRuns"], ["max-duration-ms", "maxDurationMs"], ["interval-ms", "intervalMs"]]) {
      if (values[flag] !== undefined) options[key] = number(values[flag]);
    }
    signals.on("SIGINT", stop); signals.on("SIGTERM", stop); attached = true;
    const summary = await run(options, { signal: controller.signal,
      emit: row => output(JSON.stringify({ schema: "pitcheezy-host-monitor-runner-progress-v1", ...row }) + "\n") });
    output(JSON.stringify(summary) + "\n");
    return summary.exit_code;
  } catch (error) {
    const safe = new Set(["execute_requires_explicit_limits", "invalid_runner_limits", "runner_paths_required",
      "runner_alert_paths_required", "runner_paths_overlap"]);
    errorOutput(JSON.stringify({ ok: false, code: safe.has(error?.code) ? error.code : "runner_setup_error" }) + "\n");
    return 2;
  } finally {
    if (attached) { signals.removeListener("SIGINT", stop); signals.removeListener("SIGTERM", stop); }
  }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await main(process.argv.slice(2));
}

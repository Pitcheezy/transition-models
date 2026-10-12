/** One invocation: read a monitor state file, hand new events to both recipients through the mock transport. */
import { open, lstat, rename, unlink } from "node:fs/promises";
import { resolve, dirname, basename } from "node:path";
import { randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { AlertError, validateAlertConfig, initialAlertState, validateAlertState, mockTransport, dispatchAlerts } from "./alerts.mjs";
import { readJson, plainPath } from "./monitor-cli.mjs";

export async function runAlertsOnce(monitorStatePath, configPath, statePath, { now = Date.now() } = {}) {
  const config = validateAlertConfig(await readJson(configPath, 16384));
  const record = await readJson(monitorStatePath, 131072);
  if (!record || typeof record !== "object" || !record.state) throw new AlertError("invalid_monitor_state");
  const path = await plainPath(statePath);
  // One run at a time per state file: overlapping runs would double-deliver and overwrite each other's attempts.
  const lockPath = path + ".lock";
  let lock;
  try { lock = await open(lockPath, "wx", 0o600); }
  catch (e) { if (e.code === "EEXIST") throw new AlertError("already_running_or_stale_lock"); throw e; }
  try {
    let state;
    try { state = validateAlertState(await readJson(path, 1048576)); }
    catch (e) { if (e.code !== "ENOENT") throw e; state = initialAlertState(); }
    if (config.transport !== "mock") throw new AlertError("unsupported_transport");
    const transport = mockTransport();
    const { state: next, receipt } = await dispatchAlerts(state, record.state, config, transport, { now });
    const tempPath = resolve(dirname(path), "." + basename(path) + "." + randomUUID() + ".tmp");
    const file = await open(tempPath, "wx", 0o600);
    try {
      await file.writeFile(JSON.stringify(next, null, 2) + "\n", "utf8");
      await file.sync();
    } finally { await file.close(); }
    try { await rename(tempPath, path); } catch (e) { await unlink(tempPath).catch(() => {}); throw e; }
    return { schema: "pitcheezy-host-alerts-run-v1", transport: config.transport, delivery_confirmed: false,
      mock_messages: transport.sent, receipt, pending: next.pending.length };
  } finally {
    await lock.close();
    await unlink(lockPath).catch(() => {});
  }
}

export async function main(args) {
  try {
    const { values } = parseArgs({ args, options: { "monitor-state": { type: "string" }, config: { type: "string" }, state: { type: "string" } } });
    if (!values["monitor-state"] || !values.config || !values.state) throw new AlertError("arguments_required");
    const result = await runAlertsOnce(values["monitor-state"], values.config, values.state);
    process.stdout.write(JSON.stringify(result, null, 2) + "\n");
    return result.receipt.failed.length ? 1 : 0;
  } catch (error) {
    process.stderr.write(JSON.stringify({ ok: false, code: error instanceof AlertError ? error.code : (error?.code && typeof error.code === "string" ? error.code : "alerts_io_or_argument_error") }) + "\n");
    return 2;
  }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await main(process.argv.slice(2));
}

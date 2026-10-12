/** One invocation, one local record. Does not install a scheduler or send notifications. */
import { open, lstat, rename, unlink } from "node:fs/promises";
import { resolve, dirname, basename } from "node:path";
import { randomUUID } from "node:crypto";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { MonitorError, validateConfig, initialState, validateState, probe, advanceState } from "./monitor.mjs";

export async function plainPath(value) {
  const path = resolve(value);
  for (let p = path; ; p = dirname(p)) {
    let st;
    try { st = await lstat(p); } catch (e) { if (e.code !== "ENOENT") throw e; }
    if (st?.isSymbolicLink()) throw new MonitorError("linked_path");
    if (dirname(p) === p) break;
  }
  return path;
}
export async function readJson(path, limit) {
  path = await plainPath(path);
  const info = await lstat(path);
  if (!info.isFile() || info.size > limit) throw new MonitorError("input_not_regular_or_too_large");
  const file = await open(path, "r");
  try {
    const before = await file.stat();
    if (!before.isFile() || before.size > limit) throw new MonitorError("input_not_regular_or_too_large");
    const buffer = Buffer.alloc(limit + 1);
    let offset = 0;
    while (offset < buffer.length) {
      const { bytesRead } = await file.read(buffer, offset, buffer.length - offset, null);
      if (!bytesRead) break;
      offset += bytesRead;
    }
    const after = await file.stat();
    if (offset > limit || offset !== before.size || before.mtimeMs !== after.mtimeMs || before.size !== after.size) {
      throw new MonitorError("input_changed_or_too_large");
    }
    try { return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(buffer.subarray(0, offset))); }
    catch { throw new MonitorError("input_invalid_json"); }
  } finally { await file.close(); }
}

export async function runOnce(configPath, statePath) {
  const path = await plainPath(statePath);
  const lockPath = path + ".lock";
  let lock;
  try { lock = await open(lockPath, "wx", 0o600); }
  catch (e) { if (e.code === "EEXIST") throw new MonitorError("already_running_or_stale_lock"); throw e; }
  const tempPath = resolve(dirname(path), "." + basename(path) + "." + randomUUID() + ".tmp");
  let tempCreated = false;
  try {
    const config = validateConfig(await readJson(configPath, 16384));
    let state;
    try {
      const record = await readJson(path, 131072);
      if (!record || Object.keys(record).sort().join(",") !== "report,state") throw new MonitorError("state_invalid");
      state = validateState(record.state, config);
    } catch (e) {
      if (e.code !== "ENOENT") throw e;
      state = initialState(config);
    }
    const report = await probe(config);
    const next = advanceState(state, report, config);
    const file = await open(tempPath, "wx", 0o600);
    tempCreated = true;
    try {
      await file.writeFile(JSON.stringify({ state: next.state, report }, null, 2) + "\n", "utf8");
      await file.sync();
    } finally { await file.close(); }
    await plainPath(path);
    await rename(tempPath, path);
    tempCreated = false;
    return { report, event: next.event, incident_open: next.state.incident !== null,
      recorded_events: next.state.events.length, dropped_events: next.state.dropped_events };
  } finally {
    if (tempCreated) await unlink(tempPath).catch(() => {});
    await lock.close();
    await unlink(lockPath);
  }
}

export async function main(args) {
  try {
    const { values } = parseArgs({ args, options: { config: { type: "string" }, state: { type: "string" } } });
    if (!values.config || !values.state) throw new MonitorError("config_and_state_required");
    const result = await runOnce(values.config, values.state);
    process.stdout.write(JSON.stringify(result, null, 2) + "\n");
    return result.report.status === "failed" || result.incident_open ? 1 :
      result.report.status === "partial" ? 3 : 0;
  } catch (error) {
    process.stderr.write(JSON.stringify({ ok: false,
      code: error instanceof MonitorError ? error.code : "monitor_io_or_argument_error" }) + "\n");
    return 2;
  }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await main(process.argv.slice(2));
}

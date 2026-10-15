/** Writes a per-game report draft (Markdown + JSON) from an input file. Never posts; refuses to overwrite. */
import { lstat } from "node:fs/promises";
import { writeNew, rollback } from "./owned-files.mjs";
import { randomUUID } from "node:crypto";
import { resolve, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { ReportError, buildReport } from "./report.mjs";
import { readJson, plainPath } from "./monitor-cli.mjs";

async function absent(path) {
  try { await lstat(path); } catch (e) { if (e.code === "ENOENT") return; throw e; }
  const error = new Error("EEXIST"); error.code = "EEXIST"; throw error;
}

export async function runReport(inputPath, outputDir, { now = Date.now() } = {}) {
  const input = await readJson(inputPath, 1024 * 1024);
  const { markdown, json } = buildReport(input, { now });
  const dir = await plainPath(outputDir);
  const base = `game_${json.game_pk}_${json.window.from.slice(0, 10)}_report`;
  const mdPath = join(dir, base + ".md"), jsonPath = join(dir, base + ".json");
  const lockPath = join(dir, "." + base + ".lock");
  const owned = [], locks = [];
  let acquired = false;
  try {
    try { await writeNew(lockPath, "pitcheezy-report-lock-v1 " + randomUUID() + "\n", locks); acquired = true; }
    catch (error) {
      if (error.code === "EEXIST" && locks.length === 0) throw new ReportError("already_running_or_stale_lock");
      throw error;
    }
    for (const path of [mdPath, jsonPath]) await absent(path);
    await writeNew(mdPath, markdown, owned);
    await writeNew(jsonPath, JSON.stringify(json, null, 2) + "\n", owned);
    return { schema: "pitcheezy-game-report-run-v1", markdown: base + ".md", json: base + ".json", posted: false,
      approval_required: true, usage_status: json.usage.status, evidence: json.evidence };
  } catch (error) {
    if (!await rollback(owned)) throw new ReportError("report_rollback_incomplete");
    throw error;
  } finally {
    // Also cleans a partially written lock; a lock we did not create is never removed.
    if ((acquired || locks.length) && !await rollback(locks)) throw new ReportError("report_lock_cleanup_incomplete");
  }
}

export async function main(args) {
  try {
    const { values } = parseArgs({ args, options: { input: { type: "string" }, "output-dir": { type: "string" } } });
    if (!values.input || !values["output-dir"]) throw new ReportError("arguments_required");
    const result = await runReport(values.input, values["output-dir"]);
    process.stdout.write(JSON.stringify(result, null, 2) + "\n");
    return 0;
  } catch (error) {
    const code = error instanceof ReportError ? error.code : typeof error?.code === "string" ? error.code : "report_io_or_argument_error";
    process.stderr.write(JSON.stringify({ ok: false, code }) + "\n");
    return 2;
  }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await main(process.argv.slice(2));
}

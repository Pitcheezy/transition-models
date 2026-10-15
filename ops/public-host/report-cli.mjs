/** Writes a per-game report draft (Markdown + JSON) from an input file. Never posts; refuses to overwrite. */
import { open, lstat, unlink } from "node:fs/promises";
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

async function writeNew(path, content, owned) {
  const file = await open(path, "wx", 0o600);
  const entry = { path, identity: null, namedIdentity: null, expected: Buffer.from(content, "utf8") };
  owned.push(entry); // Track creation before any stat/write/sync can fail.
  try {
    entry.identity = await file.stat({ bigint: true });
    entry.namedIdentity = await lstat(path, { bigint: true });
    await file.writeFile(content, "utf8");
    await file.sync();
  } finally { await file.close(); }
}

async function removeOwned(entry) {
  let file;
  try {
    const named = await lstat(entry.path, { bigint: true });
    if (!entry.identity || !entry.namedIdentity || !named.isFile() || named.isSymbolicLink() ||
        named.dev !== entry.namedIdentity.dev || named.ino !== entry.namedIdentity.ino ||
        named.ino !== entry.identity.ino || named.size > BigInt(entry.expected.length)) return false;
    file = await open(entry.path, "r");
    // Windows can report different dev values for named and handle stats.
    // Compare each API with its own creation identity; bigint keeps large inode IDs exact.
    const opened = await file.stat({ bigint: true });
    if (opened.dev !== entry.identity.dev || opened.ino !== entry.identity.ino || opened.size !== named.size) return false;
    // A failed write may have produced only a prefix. Never remove unexpected replacement contents.
    const bytes = Buffer.alloc(entry.expected.length + 1);
    let offset = 0;
    while (offset < bytes.length) {
      const { bytesRead } = await file.read(bytes, offset, bytes.length - offset, null);
      if (!bytesRead) break;
      offset += bytesRead;
    }
    if (BigInt(offset) !== opened.size || !bytes.subarray(0, offset).equals(entry.expected.subarray(0, offset))) return false;
    await file.close(); file = null;
    const current = await lstat(entry.path, { bigint: true });
    if (current.isSymbolicLink() || current.dev !== named.dev || current.ino !== named.ino ||
        current.size !== named.size || current.mtimeNs !== named.mtimeNs || current.ctimeNs !== named.ctimeNs) return false;
    await unlink(entry.path);
    return true;
  } catch (error) {
    return error.code === "ENOENT"; // Already absent is safe; other cleanup failures need operator attention.
  } finally { if (file) await file.close().catch(() => {}); }
}
async function rollback(owned) {
  let complete = true;
  for (const entry of [...owned].reverse()) if (!await removeOwned(entry)) complete = false;
  return complete;
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

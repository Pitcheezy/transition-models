/** Offline private summary export. Writes one new file, never posts or connects to a service. */
import { open, lstat, unlink } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { createHash } from "node:crypto";
import { plainPath } from "./monitor-cli.mjs";
import { exportUsage, UsageExportError } from "./export-usage.mjs";

export async function runExport(snapshotPath, outputPath, fromDay, toDay, options = {}) {
  const output = await plainPath(outputPath), source = await plainPath(snapshotPath);
  // Conservative on every OS: macOS volumes can also be case-insensitive.
  const pathKey = value => value.normalize("NFC").toLowerCase();
  if (pathKey(output) === pathKey(source) || ["-wal", "-shm", "-journal"].some(s => pathKey(output) === pathKey(source + s))) throw new UsageExportError("output_conflicts_with_source");
  try { await lstat(output); throw new UsageExportError("output_exists"); }
  catch (e) { if (e.code !== "ENOENT") throw e; }
  const summary = await exportUsage(source, fromDay, toDay, options);
  const bytes = Buffer.from(JSON.stringify(summary, null, 2) + "\n");
  await plainPath(output);
  let file, created = false;
  try {
    file = await open(output, "wx", 0o600); created = true;
    await file.writeFile(bytes); await file.sync();
  } catch (e) {
    await file?.close(); file = undefined;
    if (created) await unlink(output).catch(() => {});
    throw e;
  } finally { await file?.close(); }
  return { ok: true, schema: summary.schema, from_day: fromDay, to_day: toDay, coverage: "unverified",
    source_sha256: summary.source_sha256, output_sha256: createHash("sha256").update(bytes).digest("hex"),
    session_groups: summary.usage_summary.sessions.length, feedback_groups: summary.usage_summary.feedback.length };
}
export async function main(args) {
  try {
    const { values } = parseArgs({ args, options: { snapshot: { type: "string" }, output: { type: "string" },
      "from-day": { type: "string" }, "to-day": { type: "string" } } });
    if (!values.snapshot || !values.output || !values["from-day"] || !values["to-day"]) throw new UsageExportError("snapshot_output_and_days_required");
    // Current time is intentional: the CLI cannot resurrect expired rows by choosing a past cutoff.
    const receipt = await runExport(values.snapshot, values.output, values["from-day"], values["to-day"]);
    process.stdout.write(JSON.stringify(receipt, null, 2) + "\n"); return 0;
  } catch (e) {
    process.stderr.write(JSON.stringify({ ok: false, code: e instanceof UsageExportError ? e.code :
      e?.code === "linked_path" ? "linked_path" : "usage_export_io_or_argument_error" }) + "\n"); return 2;
  }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) process.exitCode = await main(process.argv.slice(2));

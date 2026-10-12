/** Writes a per-game report draft (Markdown + JSON) from an input file. Never posts; refuses to overwrite. */
import { open } from "node:fs/promises";
import { resolve, join } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { ReportError, buildReport } from "./report.mjs";
import { readJson, plainPath } from "./monitor-cli.mjs";

async function writeNew(path, content) {
  const file = await open(path, "wx", 0o600);
  try { await file.writeFile(content, "utf8"); await file.sync(); } finally { await file.close(); }
}

export async function runReport(inputPath, outputDir, { now = Date.now() } = {}) {
  const input = await readJson(inputPath, 1024 * 1024);
  const { markdown, json } = buildReport(input, { now });
  const dir = await plainPath(outputDir);
  const base = `game_${json.game_pk}_${json.window.from.slice(0, 10)}_report`;
  const mdPath = join(dir, base + ".md"), jsonPath = join(dir, base + ".json");
  await writeNew(mdPath, markdown);
  await writeNew(jsonPath, JSON.stringify(json, null, 2) + "\n");
  return { schema: "pitcheezy-game-report-run-v1", markdown: base + ".md", json: base + ".json", posted: false,
    approval_required: true, usage_status: json.usage.status, evidence: json.evidence };
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

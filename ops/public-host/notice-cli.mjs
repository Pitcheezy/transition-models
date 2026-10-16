/** Private plan in, redacted receipt out. Network requires --execute; secrets are environment-only. */
import { lstat } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { plainPath, readJson } from "./monitor-cli.mjs";
import { writeNew, rollback } from "./owned-files.mjs";
import { NoticeClientError, noticeDryRun, executeNotice } from "./notice-client.mjs";

export async function main(args, environment = process.env, { stdout = process.stdout, stderr = process.stderr, fetchImpl = fetch } = {}) {
  try {
    const { values } = parseArgs({ args, options: { plan: { type: "string" },
      execute: { type: "boolean", default: false }, snapshot: { type: "string" } } });
    if (!values.plan) throw new NoticeClientError("plan_required");
    const planPath = await plainPath(values.plan);
    const plan = await readJson(planPath, 16384);
    const dry = noticeDryRun(plan);
    let output;
    if (values.snapshot) {
      if (plan.method === "PUT") throw new NoticeClientError("snapshot_requires_read_plan");
      output = await plainPath(values.snapshot);
      if (output === planPath) throw new NoticeClientError("snapshot_must_be_new");
      try { await lstat(output); throw new NoticeClientError("snapshot_must_be_new"); }
      catch (error) { if (error.code !== "ENOENT") throw error; }
    }
    if (!values.execute) { stdout.write(JSON.stringify(dry, null, 2) + "\n"); return 0; }
    const { receipt, snapshot } = await executeNotice(plan, environment.PITCHEEZY_NOTICE_TOKEN, { fetchImpl });
    if (output && snapshot) {
      const owned = [];
      try { await writeNew(output, JSON.stringify(snapshot, null, 2) + "\n", owned); owned.length = 0; }
      finally { if (!await rollback(owned)) throw new NoticeClientError("snapshot_cleanup_incomplete"); }
    }
    stdout.write(JSON.stringify({ ...receipt, snapshot_saved: Boolean(output && snapshot) }, null, 2) + "\n");
    return ["observed", "applied"].includes(receipt.outcome) ? 0 :
      ["observed_audit_unavailable", "applied_audit_missing", "unknown", "conflict", "deferred", "unavailable"].includes(receipt.outcome) ? 3 : 1;
  } catch (error) {
    stderr.write(JSON.stringify({ ok: false, code: error instanceof NoticeClientError ? error.code : "notice_input_or_output_error" }) + "\n");
    return 2;
  }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await main(process.argv.slice(2));
}

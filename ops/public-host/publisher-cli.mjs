/** Explicit operator invocation. Default is a local dry run; no watcher or scheduler. */
import { open } from "node:fs/promises";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { plainPath, readJson } from "./monitor-cli.mjs";
import { MAX_JSON_BYTES } from "./gateway.mjs";
import { PublisherError, dryRun, transmit } from "./publisher.mjs";

async function readPayload(planPath, plan) {
  if (plan?.method !== "PUT") return null;
  const relative = plan.source_file;
  if (typeof relative !== "string" || relative.length > 256 ||
      !/^[A-Za-z0-9_.\/-]+\.json$/.test(relative) || relative.startsWith("/") ||
      relative.split("/").some(p => !p || p === "." || p === "..")) {
    throw new PublisherError("invalid_source");
  }
  const file = await open(await plainPath(resolve(dirname(planPath), relative)), "r");
  try {
    const before = await file.stat();
    if (!before.isFile() || before.size < 1 || before.size > MAX_JSON_BYTES) {
      throw new PublisherError("invalid_body_size");
    }
    const buffer = Buffer.alloc(before.size + 1);
    let offset = 0;
    while (offset < buffer.length) {
      const result = await file.read(buffer, offset, buffer.length - offset, null);
      if (!result.bytesRead) break;
      offset += result.bytesRead;
    }
    const after = await file.stat();
    if (offset !== before.size || before.size !== after.size || before.mtimeMs !== after.mtimeMs) {
      throw new PublisherError("source_changed");
    }
    return new Uint8Array(buffer.subarray(0, offset));
  } finally { await file.close(); }
}

export async function main(args, environment = process.env) {
  try {
    const { values } = parseArgs({ args, options: {
      plan: { type: "string" }, execute: { type: "boolean", default: false },
    } });
    if (!values.plan) throw new PublisherError("plan_required");
    const planPath = await plainPath(values.plan);
    const plan = await readJson(planPath, 16384);
    const bytes = await readPayload(planPath, plan);
    const dry = dryRun(plan, bytes);
    const receipt = values.execute ?
      await transmit(plan, bytes, environment.PITCHEEZY_PUBLISH_TOKEN) : dry;
    process.stdout.write(JSON.stringify(receipt, null, 2) + "\n");
    return ["dry_run", "stored", "observed", "missing"].includes(receipt.outcome) ? 0 :
      ["unknown", "conflict_or_already_applied", "deferred", "unavailable"].includes(receipt.outcome) ? 3 : 1;
  } catch (error) {
    process.stderr.write(JSON.stringify({ ok: false,
      code: error instanceof PublisherError ? error.code : "publisher_input_or_argument_error" }) + "\n");
    return 2;
  }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await main(process.argv.slice(2));
}

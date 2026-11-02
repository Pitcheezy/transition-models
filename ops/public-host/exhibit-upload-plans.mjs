/**
 * EXHIBIT-host1 ③: one publisher-cli plan (pitcheezy-upload-plan-v1) per v1 data file of the received site, into a NEW
 * private folder. Default: PUT plans (first-create, If-None-Match: *) together with a byte copy of each file, in the
 * rehearsal's upload order (setup, game, games, dates, manifest, health). --head instead emits HEAD plans only
 * (condition/source_file/sha256 null, no byte copies) to learn which keys already exist and their ETag before any PUT.
 * --if-match "v1/health.json=<quoted 32-hex ETag>" (repeatable) makes that key's PUT plan replace the existing record
 * with {"if_match": ETag} instead of a first-create condition; unknown keys and malformed ETags are refused.
 * Without --origin the plans carry a non-URL placeholder so that even a dry run refuses them until the user fills the
 * real https origin. Partner files are read only; nothing is sent.
 */
import { lstat, mkdir, readFile, writeFile } from "node:fs/promises";
import { dirname, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { prepareSite, EXHIBIT_GAME, hash } from "./exhibit-site.mjs"; // no Miniflare: runs without ops/public-host/node_modules
import { parseOrigin } from "./verify-exhibit-remote.mjs";

export const SCHEMA = "pitcheezy-exhibit-upload-plans-v1";
export const ORIGIN_PLACEHOLDER = "REPLACE_WITH_HTTPS_ORIGIN";
export const ETAG = /^"[a-f0-9]{32}"$/;
const UPLOAD_ORDER = ["setup", "game", "games", "dates", "manifest", "health"];
const fail = (code, path = null) => { throw Object.assign(new Error(code), path ? { path } : {}); };
const need = (value, code, path = null) => { if (!value) fail(code, path); };

export function planFileName(index, key, kind = "plan") {
  need(["plan", "head"].includes(kind), "plan_kind_invalid");
  return `${kind}-${String(index + 1).padStart(2, "0")}-${key.replace(/[^A-Za-z0-9]+/g, "-")}.json`;
}

/**
 * --if-match values "<data key>=<quoted 32-hex ETag>" → Map(key → ETag). The ETag must be the publisher's quoted form
 * (as HEAD returns it); the key must be one of the site's data keys and may appear once. Arbitrary input is never echoed.
 */
export function parseIfMatch(values, dataKeys) {
  const map = new Map();
  for (const value of values ?? []) {
    need(typeof value === "string" && value.length <= 512, "if_match_invalid");
    const at = value.indexOf("=");
    need(at > 0, "if_match_invalid");
    const key = value.slice(0, at), etag = value.slice(at + 1);
    need(ETAG.test(etag), "if_match_invalid");
    need(dataKeys.includes(key), "if_match_unknown_key");
    need(!map.has(key), "if_match_duplicate_key", key);
    map.set(key, etag);
  }
  return map;
}

export async function writeUploadPlans({ prepared, out, origin = null, allowLoopback = false, game = EXHIBIT_GAME, head = false, ifMatch = [] }) {
  const { intake, files, classified } = prepared;
  const target = origin === null ? { origin: ORIGIN_PLACEHOLDER, kind: "placeholder" } : parseOrigin(origin, { allowLoopback });
  const replace = parseIfMatch(ifMatch, classified.data);
  need(!(head && replace.size > 0), "head_excludes_if_match");
  await mkdir(out).catch(() => fail("output_not_creatable"));
  const order = [];
  for (const [index, key] of classified.data.entries()) {
    const source = files.get(key);
    const common = { schema: "pitcheezy-upload-plan-v1", origin: target.origin, allow_loopback_http: target.kind === "loopback_http" };
    if (head) {
      const plan = { ...common, method: "HEAD", path: "/" + key, condition: null, source_file: null, sha256: null };
      const name = planFileName(index, key, "head");
      await writeFile(join(out, name), JSON.stringify(plan, null, 2) + "\n", { flag: "wx" });
      order.push({ plan: name, method: "HEAD", path: plan.path, expected_sha256: source.sha256 });
      continue;
    }
    const copy = join(out, ...key.split("/"));
    await mkdir(dirname(copy), { recursive: true });
    await writeFile(copy, source.bytes, { flag: "wx" });
    const back = await readFile(copy);
    need(back.length === source.bytes.length && hash(back) === source.sha256, "copy_mismatch", key);
    const condition = replace.has(key) ? { if_match: replace.get(key) } : { if_none_match: "*" };
    const plan = { ...common, method: "PUT", path: "/" + key, condition, source_file: key, sha256: source.sha256 };
    const name = planFileName(index, key);
    await writeFile(join(out, name), JSON.stringify(plan, null, 2) + "\n", { flag: "wx" });
    order.push({ plan: name, method: "PUT", condition: replace.has(key) ? "if_match" : "if_none_match", path: plan.path, source_file: key, bytes: source.bytes.length, sha256: source.sha256 });
  }
  const index = { schema: SCHEMA, mode: head ? "head" : "put", source_commit: intake.source_commit, exhibit_game: String(game), origin_kind: target.kind, origin_recorded: false,
    count: order.length, if_match_keys: [...replace.keys()], upload_order: UPLOAD_ORDER, plans: order,
    run: `node ops/public-host/publisher-cli.mjs --plan <folder>/<plan>            # dry run (default)`,
    execute: `node ops/public-host/publisher-cli.mjs --plan <folder>/<plan> --execute   # one ${head ? "HEAD" : "file"}, token only via PITCHEEZY_PUBLISH_TOKEN`,
    notes: [
      head ? "Each plan is a HEAD (condition null, no body): outcome observed = the key exists (etag and current_sha256 in the receipt), missing = not stored. Nothing is written."
        : "Each plan without if_match is a first-create PUT (If-None-Match: *); a 412 means the key already exists and must be inspected (HEAD plan), not overwritten.",
      ...(replace.size > 0 ? ["Plans with if_match replace an existing record only while its ETag still equals the HEAD result; a 412 means it changed since the HEAD."] : []),
      target.kind === "placeholder" ? "origin is a placeholder: replace it in every plan with the real https origin before any run." : "origin is set; it is not repeated here.",
      head ? "This folder holds no partner bytes, only the keys. Keep it private anyway; do not commit or attach it."
        : "Keep this folder private; it holds the partner's data bytes. Do not commit or attach it.",
    ] };
  await writeFile(join(out, "index.json"), JSON.stringify(index, null, 2) + "\n", { flag: "wx" });
  return index;
}

export async function main(args) {
  try {
    const { values } = parseArgs({ args, options: { site: { type: "string" }, receipt: { type: "string" }, out: { type: "string" }, origin: { type: "string" },
      game: { type: "string", default: EXHIBIT_GAME }, "expect-data": { type: "string", default: "24" }, "allow-loopback": { type: "boolean", default: false },
      head: { type: "boolean", default: false }, "if-match": { type: "string", multiple: true, default: [] } } });
    need(values.site && values.receipt && values.out, "arguments_required");
    need(/^[1-9][0-9]{0,3}$/.test(values["expect-data"]), "expect_data_invalid");
    if (values.origin !== undefined) parseOrigin(values.origin, { allowLoopback: values["allow-loopback"] });
    for (const value of values["if-match"]) need(/^[A-Za-z0-9_./-]{1,200}="[a-f0-9]{32}"$/.test(value), "if_match_invalid");
    need(!(values.head && values["if-match"].length > 0), "head_excludes_if_match");
    const out = resolve(values.out);
    need(!(await lstat(out).then(() => true, () => false)), "output_exists");
    const prepared = await prepareSite({ site: values.site, receipt: values.receipt, expectData: Number(values["expect-data"]), game: values.game });
    const index = await writeUploadPlans({ prepared, out, origin: values.origin ?? null, allowLoopback: values["allow-loopback"], game: values.game,
      head: values.head, ifMatch: values["if-match"] });
    process.stdout.write(JSON.stringify(index, null, 2) + "\n");
    return 0;
  } catch (error) {
    const code = /^[a-z_]{1,64}$/.test(error?.message || "") ? error.message : "upload_plans_input_or_output_error";
    process.stderr.write(JSON.stringify({ ok: false, code, ...(error?.path ? { path: error.path } : {}) }) + "\n");
    return 2;
  }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await main(process.argv.slice(2));
}

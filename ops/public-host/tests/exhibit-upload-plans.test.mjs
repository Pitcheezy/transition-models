// Upload-plan generator on the SYNTHETIC 4+6 build; plans are checked with the real publisher dry run (no network).
import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile, readFile, readdir, rm, realpath, lstat } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { hash } from "../exhibit-site.mjs";
import { main as publisherMain } from "../publisher-cli.mjs";
import { dryRun } from "../publisher.mjs";
import { main, planFileName, parseIfMatch, ORIGIN_PLACEHOLDER } from "../exhibit-upload-plans.mjs";

function miniBuild() {
  return {
    "index.html": "<!doctype html><title>synthetic</title>", "favicon.svg": '<svg xmlns="http://www.w3.org/2000/svg"/>',
    "assets/index-syn1.js": "export {};", "assets/index-syn1.css": "body{margin:0}",
    "v1/manifest.json": JSON.stringify({ synthetic: true }), "v1/health.json": JSON.stringify({ synthetic: true, sequence: 1 }),
    "v1/dates.json": JSON.stringify({ synthetic: true, dates: ["2026-01-01"] }), "v1/games/2026-01-01.json": JSON.stringify({ synthetic: true, games: [1] }),
    "v1/game/1.json": JSON.stringify({ synthetic: true, game_pk: 1 }), "v1/setup/1.json": JSON.stringify({ synthetic: true, game_pk: 1 }),
  };
}
async function fixture(t) {
  const build = miniBuild();
  const dir = await mkdtemp(join(await realpath(tmpdir()), "pitcheezy-plans-test-"));
  t.after(() => rm(dir, { recursive: true, force: true }));
  const site = join(dir, "site");
  for (const [path, text] of Object.entries(build)) {
    const full = join(site, ...path.split("/"));
    await mkdir(dirname(full), { recursive: true });
    await writeFile(full, text);
  }
  const receiptPath = join(dir, "intake-receipt.json");
  await writeFile(receiptPath, JSON.stringify({ schema: "pitcheezy-exhibition-intake-v1", evidence_kind: "offline_archive_integrity", source_commit: "a".repeat(40),
    zip: { bytes: 1, sha256: "b".repeat(64) }, catalogue: { advertised_dates: 1, supplied_date_files: 1, missing_date_files: [] },
    files: Object.entries(build).map(([path, text]) => ({ path, bytes: Buffer.byteLength(text), sha256_raw: hash(text) })) }));
  return { dir, site, receiptPath, build };
}
async function capture(stream, run) {
  const chunks = []; const original = stream.write;
  stream.write = chunk => { chunks.push(String(chunk)); return true; };
  try { return { code: await run(), text: chunks.join("") }; } finally { stream.write = original; }
}
const ORDER = ["v1/setup/1.json", "v1/game/1.json", "v1/games/2026-01-01.json", "v1/dates.json", "v1/manifest.json", "v1/health.json"];
const base = (fx, out) => ["--site", fx.site, "--receipt", fx.receiptPath, "--out", out, "--expect-data", "6", "--game", "1"];

test("placeholder origin: 6 plans in upload order, byte copies, and the publisher refuses even a dry run until the origin is filled", async (t) => {
  const fx = await fixture(t);
  const out = join(fx.dir, "plans");
  const run = await capture(process.stdout, () => main(base(fx, out)));
  const index = JSON.parse(run.text);
  assert.equal(run.code, 0);
  assert.equal(index.schema, "pitcheezy-exhibit-upload-plans-v1");
  assert.equal(index.count, 6); assert.equal(index.origin_kind, "placeholder"); assert.equal(index.origin_recorded, false);
  assert.equal(index.exhibit_game, "1"); assert.equal(index.source_commit, "a".repeat(40));
  assert.deepEqual(index.plans.map(p => p.source_file), ORDER);
  assert.deepEqual(index.plans.map(p => p.plan), ORDER.map((key, i) => planFileName(i, key)));
  assert.equal(index.plans[0].plan, "plan-01-v1-setup-1-json.json");
  for (const row of index.plans) {
    const copied = await readFile(join(out, ...row.source_file.split("/")));
    assert.equal(copied.toString(), fx.build[row.source_file], row.source_file);
    assert.equal(row.sha256, hash(copied)); assert.equal(row.bytes, copied.length);
    const plan = JSON.parse(await readFile(join(out, row.plan), "utf8"));
    assert.deepEqual(plan, { schema: "pitcheezy-upload-plan-v1", origin: ORIGIN_PLACEHOLDER, allow_loopback_http: false, method: "PUT", path: row.path,
      condition: { if_none_match: "*" }, source_file: row.source_file, sha256: row.sha256 });
    assert.throws(() => dryRun(plan, copied), /invalid_origin/, "placeholder is not a URL: nothing can run with it");
  }
  assert.deepEqual(JSON.parse(await readFile(join(out, "index.json"), "utf8")).plans, index.plans);
  assert.equal((await readdir(out)).length, 6 + 2, "6 plans, index.json, v1/");
  // Partner site untouched; existing output refused.
  assert.equal(await readFile(join(fx.site, "v1", "health.json"), "utf8"), fx.build["v1/health.json"]);
  const again = await capture(process.stderr, () => main(base(fx, out)));
  assert.equal(again.code, 2); assert.match(again.text, /output_exists/);
});

test("explicit origins: https accepted (no network), loopback http only with --allow-loopback, every plan passes the real publisher dry run", async (t) => {
  const fx = await fixture(t);
  const https = join(fx.dir, "plans-https");
  const ok = await capture(process.stdout, () => main([...base(fx, https), "--origin", "https://host.invalid"]));
  assert.equal(ok.code, 0);
  assert.equal(JSON.parse(ok.text).origin_kind, "https");
  const plan = JSON.parse(await readFile(join(https, planFileName(0, ORDER[0])), "utf8"));
  assert.equal(plan.origin, "https://host.invalid"); assert.equal(plan.allow_loopback_http, false);
  assert.doesNotMatch(ok.text, /host\.invalid/, "the index never repeats the origin");
  const refused = await capture(process.stderr, () => main([...base(fx, join(fx.dir, "plans-http")), "--origin", "http://host.invalid", "--allow-loopback"]));
  assert.equal(refused.code, 2); assert.match(refused.text, /origin_https_required/);
  const noFlag = await capture(process.stderr, () => main([...base(fx, join(fx.dir, "plans-http2")), "--origin", "http://127.0.0.1:9"]));
  assert.equal(noFlag.code, 2); assert.match(noFlag.text, /origin_https_required/);
  assert.deepEqual((await readdir(fx.dir)).filter(n => ["plans-http", "plans-http2"].includes(n)), [], "refusals create no folder");
  const loop = join(fx.dir, "plans-loop");
  const loopRun = await capture(process.stdout, () => main([...base(fx, loop), "--origin", "http://127.0.0.1:9", "--allow-loopback"]));
  assert.equal(loopRun.code, 0);
  for (const [i, key] of ORDER.entries()) {
    const path = join(loop, planFileName(i, key));
    assert.equal(JSON.parse(await readFile(path, "utf8")).allow_loopback_http, true);
    const dry = await capture(process.stdout, () => publisherMain(["--plan", path], {}));
    const receipt = JSON.parse(dry.text);
    assert.equal(dry.code, 0, key);
    assert.deepEqual([receipt.outcome, receipt.attempted, receipt.method, receipt.path, receipt.sha256], ["dry_run", false, "PUT", "/" + key, hash(fx.build[key])]);
  }
  for (const [i, key] of ORDER.entries()) {
    assert.equal(JSON.parse(await readFile(join(loop, planFileName(i, key)), "utf8")).condition.if_none_match, "*", "default stays first-create");
  }
  assert.deepEqual(JSON.parse(loopRun.text).if_match_keys, []); assert.equal(JSON.parse(loopRun.text).mode, "put");
});

const ETAG_OK = '"' + "0123456789abcdef".repeat(2) + '"';

test("--head: HEAD-only plans (condition/source_file/sha256 null, no byte copies) under the same origin rules, every one passes the publisher dry run", async (t) => {
  const fx = await fixture(t);
  const heads = join(fx.dir, "heads");
  const run = await capture(process.stdout, () => main([...base(fx, heads), "--origin", "http://127.0.0.1:9", "--allow-loopback", "--head"]));
  const index = JSON.parse(run.text);
  assert.equal(run.code, 0, run.text);
  assert.equal(index.mode, "head"); assert.equal(index.count, 6); assert.equal(index.origin_kind, "loopback_http"); assert.equal(index.origin_recorded, false);
  assert.deepEqual(index.plans.map(p => p.plan), ORDER.map((key, i) => planFileName(i, key, "head")));
  assert.equal(index.plans[0].plan, "head-01-v1-setup-1-json.json");
  assert.deepEqual(index.plans.map(p => [p.method, p.path, p.expected_sha256]), ORDER.map(key => ["HEAD", "/" + key, hash(fx.build[key])]));
  assert.deepEqual((await readdir(heads)).sort(), [...ORDER.map((key, i) => planFileName(i, key, "head")), "index.json"].sort(), "no v1/ byte copies in a HEAD folder");
  assert.equal(await lstat(join(heads, "v1")).then(() => true, () => false), false);
  for (const [i, key] of ORDER.entries()) {
    const path = join(heads, planFileName(i, key, "head"));
    const plan = JSON.parse(await readFile(path, "utf8"));
    assert.deepEqual(plan, { schema: "pitcheezy-upload-plan-v1", origin: "http://127.0.0.1:9", allow_loopback_http: true, method: "HEAD", path: "/" + key, condition: null, source_file: null, sha256: null });
    const dry = await capture(process.stdout, () => publisherMain(["--plan", path], {}));
    const receipt = JSON.parse(dry.text);
    assert.equal(dry.code, 0, key + " " + dry.text);
    assert.deepEqual([receipt.outcome, receipt.attempted, receipt.method, receipt.path, receipt.bytes, receipt.sha256], ["dry_run", false, "HEAD", "/" + key, 0, null]);
  }
  assert.ok(index.notes.some(n => n.includes("observed") && n.includes("missing")));
  // https origin and the placeholder work the same way for HEAD plans; the placeholder still refuses a dry run.
  const https = await capture(process.stdout, () => main([...base(fx, join(fx.dir, "heads-https")), "--origin", "https://host.invalid", "--head"]));
  assert.equal(https.code, 0); assert.doesNotMatch(https.text, /host\.invalid/);
  const placeholder = await capture(process.stdout, () => main([...base(fx, join(fx.dir, "heads-placeholder")), "--head"]));
  assert.equal(placeholder.code, 0);
  const first = JSON.parse(await readFile(join(fx.dir, "heads-placeholder", planFileName(0, ORDER[0], "head")), "utf8"));
  assert.equal(first.origin, ORIGIN_PLACEHOLDER);
  assert.throws(() => dryRun(first, null), /invalid_origin/);
  // --head together with --if-match is a contradiction and is refused before anything is written.
  const both = await capture(process.stderr, () => main([...base(fx, join(fx.dir, "heads-both")), "--head", "--if-match", `v1/health.json=${ETAG_OK}`]));
  assert.equal(both.code, 2); assert.match(both.text, /head_excludes_if_match/);
  assert.equal((await readdir(fx.dir)).includes("heads-both"), false);
});

test("--if-match: that key's PUT plan carries exactly {\"if_match\": ETag} and passes the dry run; the other keys stay first-create; malformed ETags, unknown and repeated keys are refused", async (t) => {
  const fx = await fixture(t);
  const out = join(fx.dir, "plans-ifmatch");
  const ok = await capture(process.stdout, () => main([...base(fx, out), "--origin", "https://host.invalid", "--if-match", `v1/health.json=${ETAG_OK}`]));
  const index = JSON.parse(ok.text);
  assert.equal(ok.code, 0, ok.text);
  assert.equal(index.mode, "put"); assert.deepEqual(index.if_match_keys, ["v1/health.json"]);
  assert.deepEqual(index.plans.map(p => p.condition), ["if_none_match", "if_none_match", "if_none_match", "if_none_match", "if_none_match", "if_match"]);
  assert.doesNotMatch(ok.text, /0123456789abcdef/, "the index names the key, not the ETag");
  const health = JSON.parse(await readFile(join(out, planFileName(5, "v1/health.json")), "utf8"));
  assert.deepEqual(health, { schema: "pitcheezy-upload-plan-v1", origin: "https://host.invalid", allow_loopback_http: false, method: "PUT", path: "/v1/health.json",
    condition: { if_match: ETAG_OK }, source_file: "v1/health.json", sha256: hash(fx.build["v1/health.json"]) });
  const copied = await readFile(join(out, "v1", "health.json"));
  assert.equal(copied.toString(), fx.build["v1/health.json"]);
  assert.equal(dryRun(health, copied).outcome, "dry_run", "the real publisher accepts the if_match precondition");
  for (const [i, key] of ORDER.entries()) {
    if (key === "v1/health.json") continue;
    assert.deepEqual(JSON.parse(await readFile(join(out, planFileName(i, key)), "utf8")).condition, { if_none_match: "*" }, key);
  }
  assert.ok(index.notes.some(n => n.includes("if_match") && n.includes("412")));
  // Two keys at once, order independent.
  const two = await capture(process.stdout, () => main([...base(fx, join(fx.dir, "plans-two")), "--if-match", `v1/manifest.json=${ETAG_OK}`, "--if-match", `v1/setup/1.json=${ETAG_OK}`]));
  assert.equal(two.code, 0); assert.deepEqual(JSON.parse(two.text).if_match_keys.sort(), ["v1/manifest.json", "v1/setup/1.json"]);
  // Refusals: exit 2, coded, no output folder.
  const cases = [
    [[`v1/health.json=0123456789abcdef0123456789abcdef`], /if_match_invalid/, "unquoted"],
    [[`v1/health.json="0123456789ABCDEF0123456789ABCDEF"`], /if_match_invalid/, "uppercase hex"],
    [[`v1/health.json="0123456789abcdef"`], /if_match_invalid/, "16 hex"],
    [[`v1/health.json="0123456789abcdef0123456789abcdef0"`], /if_match_invalid/, "33 hex"],
    [[`v1/health.json=W/"0123456789abcdef0123456789abcdef"`], /if_match_invalid/, "weak etag"],
    [[`v1/health.json`], /if_match_invalid/, "no ="],
    [[`=${ETAG_OK}`], /if_match_invalid/, "empty key"],
    [[`v1/nope.json=${ETAG_OK}`], /if_match_unknown_key/, "key not in the site"],
    [[`v1/game/2.json=${ETAG_OK}`], /if_match_unknown_key/, "permitted-looking key the site does not have"],
    [[`index.html=${ETAG_OK}`], /if_match_unknown_key/, "static file is not a data key"],
    [[`v1/health.json=${ETAG_OK}`, `v1/health.json=${ETAG_OK}`], /if_match_duplicate_key/, "repeated key"],
  ];
  for (const [i, [values, code, label]] of cases.entries()) {
    const target = join(fx.dir, `refused-${i}`);
    const refused = await capture(process.stderr, () => main([...base(fx, target), ...values.flatMap(v => ["--if-match", v])]));
    assert.equal(refused.code, 2, label); assert.match(refused.text, code, label);
    assert.doesNotMatch(refused.text, /nope|ABCDEF|W\//, "arbitrary input is not echoed: " + label);
    assert.equal(await lstat(target).then(() => true, () => false), false, "no folder on refusal: " + label);
  }
  assert.throws(() => parseIfMatch([`v1/health.json=${ETAG_OK}`], ["v1/manifest.json"]), /if_match_unknown_key/);
  assert.deepEqual([...parseIfMatch([`v1/health.json=${ETAG_OK}`], ["v1/health.json"])], [["v1/health.json", ETAG_OK]]);
  assert.deepEqual([...parseIfMatch([], ["v1/health.json"])], []);
});

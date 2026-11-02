import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { mkdtemp, mkdir, readFile, writeFile, readdir, rm, realpath, symlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { KEYS, prepareStage3, runStage3, main } from "../exhibit-stage3-upload.mjs";

const NOW = Date.parse("2026-11-02T00:00:00.000Z");
const TOKEN = "t".repeat(43), VERSION = "12345678-1234-1234-1234-123456789abc";
const sha = value => createHash("sha256").update(value).digest("hex");
const iso = value => new Date(value).toISOString();
const etag = '"' + "a".repeat(32) + '"';
const ray = "0123456789abcdef-ICN";
async function fixture(t) {
  const dir = await mkdtemp(join(await realpath(tmpdir()), "pitcheezy-stage3-test-"));
  t.after(() => rm(dir, { recursive: true, force: true }));
  const manifest = { schema: "pitcheezy-stage3-upload-run-v1", run_id: "synthetic-test", origin: "https://host.invalid",
    expected_deployment_version: VERSION, approved: true, window_start_utc: iso(NOW - 1000), close_by_utc: iso(NOW + 300000), request_limit: 12, operations: [] };
  const plans = [];
  for (let i = 0; i < 12; ++i) {
    const method = i < 6 ? "HEAD" : "PUT";
    const source = KEYS[i % 6].slice(1);
    const payload = Buffer.from(JSON.stringify({ synthetic: true, key: source }));
    const plan = { schema: "pitcheezy-upload-plan-v1", origin: manifest.origin, allow_loopback_http: false,
      method, path: KEYS[i % 6], condition: method === "HEAD" ? null : { if_none_match: "*" },
      source_file: method === "HEAD" ? null : source, sha256: method === "HEAD" ? null : sha(payload) };
    const planPath = join(dir, `plan-${i}.json`);
    if (method === "PUT") { await mkdir(dirname(join(dir, source)), { recursive: true }); await writeFile(join(dir, source), payload); }
    await writeFile(planPath, JSON.stringify(plan));
    manifest.operations.push({ plan_file: planPath, plan_sha256: sha(JSON.stringify(plan)), expected_status: method === "HEAD" ? 404 : 200, expected_outcome: method === "HEAD" ? "missing" : "stored" });
    plans.push(plan);
  }
  const manifestPath = join(dir, "manifest.json"), out = join(dir, "run");
  const fx = { dir, manifestPath, out, manifest, plans };
  fx.save = async () => { const bytes = JSON.stringify(manifest); await writeFile(manifestPath, bytes); fx.manifestSha256 = sha(bytes); };
  fx.savePlan = async i => { const bytes = JSON.stringify(plans[i]); await writeFile(manifest.operations[i].plan_file, bytes); manifest.operations[i].plan_sha256 = sha(bytes); await fx.save(); };
  fx.options = () => ({ manifestPath, manifestSha256: fx.manifestSha256, out, execute: true, token: TOKEN });
  await fx.save();
  return fx;
}
function transport(fx, change = null) {
  const calls = [];
  const fetchImpl = async (url, init) => {
    const index = calls.length;
    calls.push({ url, method: init.method, headers: init.headers, body: init.body });
    assert.equal(url, fx.manifest.origin + "/_publish" + fx.plans[index].path);
    assert.equal(init.redirect, "error");
    if (change) { const replacement = await change(index, init); if (replacement) return replacement; }
    if (init.method === "HEAD") return new Response(null, { status: 404, headers: { "CF-Ray": ray } });
    return new Response(JSON.stringify({ stored: true, deleted: false, sha256: fx.plans[index].sha256, schema_validated: false }),
      { status: 200, headers: { "Content-Type": "application/json", ETag: etag, "CF-Ray": ray } });
  };
  return { calls, fetchImpl, now: () => NOW };
}
async function noNetwork(fx, pattern) {
  let calls = 0;
  await assert.rejects(runStage3(fx.options(), { now: () => NOW, fetchImpl: async () => { calls++; throw new Error("unexpected request"); } }), pattern);
  assert.equal(calls, 0);
  assert.equal((await readdir(fx.dir)).includes("run"), false);
}

test("fixed 12 succeeds in order, first-create bytes and private UTC/Ray journal; stdout summary has no credential or origin", async t => {
  const fx = await fixture(t), transportMock = transport(fx);
  const result = await runStage3(fx.options(), transportMock);
  assert.equal(result.outcome, "uploaded_pending_operator_close");
  assert.equal(result.attempted_requests, 12); assert.equal(result.completed_operations, 12);
  assert.equal(result.cleanup_required, true); assert.equal(result.data_readback_verified, false);
  assert.deepEqual(transportMock.calls.map(c => c.method), [...Array(6).fill("HEAD"), ...Array(6).fill("PUT")]);
  for (const call of transportMock.calls.slice(6)) assert.equal(call.headers["If-None-Match"], "*");
  const files = await readdir(fx.out);
  assert.equal(files.length, 27);
  assert.equal(sha(await readFile(join(fx.out, "manifest.private.json"))), fx.manifestSha256);
  const row = JSON.parse(await readFile(join(fx.out, "request-12.completed.private.json"), "utf8"));
  assert.equal(row.exchange.ray, ray); assert.equal(row.exchange.status, 200);
  assert.equal(row.expected_deployment_version, VERSION);
  assert.match(row.version_basis, /not_http/);
  for (const file of files) assert.equal((await readFile(join(fx.out, file), "utf8")).includes(TOKEN), false);
  assert.equal(JSON.stringify(result).includes("host.invalid"), false);
  assert.equal(JSON.stringify(result).includes(ray), false);
  assert.equal(JSON.stringify(result).includes(TOKEN), false);
});

test("dry run accepts unapproved null window without token, requests or output directory", async t => {
  const fx = await fixture(t);
  fx.manifest.approved = false; fx.manifest.window_start_utc = null; fx.manifest.close_by_utc = null; await fx.save();
  const run = await runStage3({ ...fx.options(), execute: false, token: null }, { fetchImpl: () => assert.fail("network"), now: () => NOW });
  assert.equal(run.outcome, "dry_run"); assert.equal(run.attempted_requests, 0);
  assert.equal((await readdir(fx.dir)).includes("run"), false);
});

test("HEAD existing key stops before any PUT, even though publisher observed would be CLI exit zero", async t => {
  const fx = await fixture(t), mock = transport(fx, async index => index === 2 ? new Response(null, { status: 200,
    headers: { ETag: etag, "X-Publish-Deleted": "false", "X-Content-SHA256": "b".repeat(64), "CF-Ray": ray } }) : null);
  const result = await runStage3(fx.options(), mock);
  assert.equal(result.outcome, "STOPPED"); assert.equal(mock.calls.length, 3);
  assert.equal(result.completed_operations, 2); assert.equal(mock.calls.some(c => c.method === "PUT"), false);
});

test("late PUT body corruption is rejected before first HEAD", async t => {
  const fx = await fixture(t);
  await writeFile(join(fx.dir, fx.plans[11].source_file), '{"changed":true}');
  await noNetwork(fx, /source_sha_mismatch/);
});

test("changed manifest or plan pin, wrong origin/key/order, expiry, approval and excessive window refuse without requests", async t => {
  const cases = [
    [fx => { fx.manifestSha256 = "0".repeat(64); }, /manifest_sha_mismatch/, false],
    [fx => { fx.manifest.operations[11].plan_sha256 = "0".repeat(64); }, /plan_sha_mismatch/],
    [async fx => { fx.plans[11].origin = "https://wrong.invalid"; await fx.savePlan(11); }, /plan_origin_mismatch/],
    [async fx => { fx.plans[0].path = "/v1/game/2.json"; await fx.savePlan(0); }, /operation_order_or_key_invalid/],
    [fx => { fx.manifest.approved = false; }, /execution_not_approved/],
    [fx => { fx.manifest.close_by_utc = iso(NOW - 1); }, /window_not_active_or_insufficient/],
    [fx => { fx.manifest.close_by_utc = iso(NOW + 600000); }, /window_duration_invalid/],
    [fx => { fx.manifest.window_start_utc = iso(NOW + 1000); }, /window_not_active_or_insufficient/],
    [fx => { fx.manifest.close_by_utc = iso(NOW + 89999); }, /window_not_active_or_insufficient/],
    [async fx => { fx.plans[11].source_file = "../outside.json"; await fx.savePlan(11); }, /source_path_invalid/],
    [async fx => { fx.plans[6].condition = { if_match: etag }; await fx.savePlan(6); }, /first_create_required/],
  ];
  for (const [mutate, pattern, save = true] of cases) {
    const fx = await fixture(t); await mutate(fx); if (save) await fx.save(); await noNetwork(fx, pattern);
  }
});

test("503 and 429 each consume exactly one attempt; no publisher retry", async t => {
  for (const status of [503, 429]) {
    const fx = await fixture(t), mock = transport(fx, async () => new Response(null, { status, headers: { "CF-Ray": ray, "Retry-After": "0" } }));
    const result = await runStage3(fx.options(), mock);
    assert.equal(result.outcome, "STOPPED"); assert.equal(mock.calls.length, 1);
    assert.equal(result.attempted_requests, 1);
  }
});

test("network exception is not retried and request journal contains no exception contents", async t => {
  const fx = await fixture(t); let calls = 0;
  const result = await runStage3(fx.options(), { now: () => NOW, fetchImpl: async () => { calls++; throw new Error(TOKEN); } });
  assert.equal(result.outcome, "STOPPED"); assert.equal(calls, 1);
  const row = await readFile(join(fx.out, "request-01.completed.private.json"), "utf8");
  assert.equal(row.includes(TOKEN), false);
  assert.equal(JSON.parse(row).exchange.transport_error, true);
});

test("request timeout stops once; no retry after abort", async t => {
  const fx = await fixture(t); let calls = 0;
  const result = await runStage3(fx.options(), { now: () => NOW, fetchImpl: async (_url, init) => {
    calls++;
    return new Promise((_resolve, reject) => init.signal.addEventListener("abort", () => reject(new Error("aborted")), { once: true }));
  } });
  assert.equal(result.outcome, "STOPPED"); assert.equal(calls, 1);
  assert.equal(result.attempted_requests, 1);
});

test("partial PUT failure preserves successful rows and stops without remaining writes or cleanup HTTP", async t => {
  const fx = await fixture(t), mock = transport(fx, async index => index === 8 ? new Response(null, { status: 412, headers: { "CF-Ray": ray } }) : null);
  const result = await runStage3(fx.options(), mock);
  assert.equal(result.outcome, "STOPPED"); assert.equal(mock.calls.length, 9);
  assert.equal(result.completed_operations, 8); assert.equal(result.cleanup_required, true);
  assert.ok((await readdir(fx.out)).includes("request-08.completed.private.json"));
  assert.equal((await readdir(fx.out)).includes("request-10.pending.private.json"), false);
});

test("same output folder refuses rerun before a request", async t => {
  const fx = await fixture(t), mock = transport(fx);
  await runStage3(fx.options(), mock);
  await assert.rejects(runStage3(fx.options(), mock), /output_exists_or_unavailable/);
  assert.equal(mock.calls.length, 12);
});

test("pending or completed journal failure prevents subsequent requests", async t => {
  for (const failSuffix of ["request-01.pending.private.json", "request-01.completed.private.json"]) {
    const fx = await fixture(t), mock = transport(fx);
    const result = await runStage3(fx.options(), { ...mock, writeRecord: async (path, value) => {
      if (path.endsWith(failSuffix)) throw new Error("disk unavailable");
      await writeFile(path, JSON.stringify(value), { flag: "wx" });
    } });
    assert.equal(result.outcome, "STOPPED");
    assert.equal(mock.calls.length, failSuffix.includes("pending") ? 0 : 1);
  }
});

test("window consumed by journal work prevents send and stops subsequent operations", async t => {
  const fx = await fixture(t); let clock = NOW;
  const mock = transport(fx);
  const result = await runStage3(fx.options(), { ...mock, now: () => clock, writeRecord: async (path, value) => {
    await writeFile(path, JSON.stringify(value), { flag: "wx" });
    if (path.endsWith("request-01.pending.private.json")) clock += 250000;
  } });
  assert.equal(result.outcome, "STOPPED"); assert.equal(mock.calls.length, 0);
});

test("CLI only executes with flag and environment token; default output is sanitized", async t => {
  const fx = await fixture(t); let text = "", requests = 0;
  const sink = { write: chunk => { text += chunk; } };
  const code = await main(["--manifest", fx.manifestPath, "--manifest-sha256", fx.manifestSha256], {
    environment: { PITCHEEZY_PUBLISH_TOKEN: TOKEN }, stdout: sink, stderr: sink, now: () => NOW,
    fetchImpl: async () => { requests++; throw new Error("unexpected"); },
  });
  assert.equal(code, 0); assert.equal(requests, 0); assert.match(text, /dry_run/);
  assert.equal(text.includes(TOKEN), false); assert.equal(text.includes("host.invalid"), false);
});

test("symlinked source is refused where symlink creation is permitted", async t => {
  const fx = await fixture(t), source = join(fx.dir, fx.plans[11].source_file), copy = join(fx.dir, "source-copy.json");
  await writeFile(copy, await readFile(source)); await rm(source);
  try { await symlink(copy, source); }
  catch (error) { if (error.code === "EPERM") { t.skip("symlink permission unavailable"); return; } throw error; }
  await noNetwork(fx, /linked_path/);
});

test("incorrect returned PUT digest stops at that write without retry", async t => {
  const fx = await fixture(t), mock = transport(fx, async index => index === 6 ? new Response(JSON.stringify({
    stored: true, deleted: false, sha256: "c".repeat(64), schema_validated: false,
  }), { status: 200, headers: { "Content-Type": "application/json", ETag: etag, "CF-Ray": ray } }) : null);
  const result = await runStage3(fx.options(), mock);
  assert.equal(result.outcome, "STOPPED"); assert.equal(mock.calls.length, 7);
  assert.equal(result.completed_operations, 6); assert.equal(result.cleanup_required, true);
});

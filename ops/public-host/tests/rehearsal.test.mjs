import test from "node:test";
import assert from "node:assert/strict";
import { runLocalRehearsal, validateWorkload, syntheticBody, summarizeLoad, checkRead } from "../rehearse-local.mjs";
import { hash, waitForReady, boundedCleanup } from "../rehearsal/local-host.mjs";
import { main as firstConnectionMain } from "../rehearse-first-connection.mjs";
import { writeFile, readFile } from "node:fs/promises";
import { join } from "node:path";
import { createTestDirectory } from "./helpers/owned-temp.mjs";

test("workload caps prevent accidental external or unbounded load", () => {
  for (const bad of [
    { requests: 0 }, { requests: 1001 }, { concurrency: 17 }, { concurrency: 0 },
    { payload_bytes: 200 }, { payload_bytes: 1048577 }, { requests: 1000, payload_bytes: 1048576 },
    { origin: "https://some-server.test" }, { requests: "120" },
  ]) assert.throws(() => validateWorkload(bad), /invalid_workload/);
  assert.equal(Buffer.byteLength(syntheticBody(32768)), 32768);
});

test("latency only covers successful requests; empty percentiles are null", () => {
  const r = summarizeLoad([2, 3, 100], ["read_integrity"], 200, 2, validateWorkload({ requests: 4 }));
  assert.equal(r.attempted, 4); assert.equal(r.successful, 3); assert.equal(r.failed, 1);
  assert.equal(r.p50_ms, 3); assert.equal(r.p95_ms, 100);
  const empty = summarizeLoad([], ["read_status"], 10, 1, validateWorkload({ requests: 1 }));
  assert.equal(empty.p50_ms, null); assert.equal(empty.p95_ms, null);
});

test("body corruption and wrong cache metadata fail the read verifier", async () => {
  const expected = hash("synthetic");
  const response = (body = "synthetic", h = {}) => new Response(body, { headers: {
    Date: new Date().toUTCString(), Age: "0", "Cache-Control": "no-store", ...h,
  } });
  await checkRead(response(), expected, 9);
  for (const cache of ["no-store, no-transform", "no-transform, NO-STORE"]) {
    await checkRead(response("synthetic", { "Cache-Control": cache }), expected, 9);
  }
  for (const cache of ["no-transform", "max-age=300, no-transform", "x-no-store", "no-store=1"]) {
    await assert.rejects(checkRead(response("synthetic", { "Cache-Control": cache }), expected, 9), /read_cache/);
  }
  await assert.rejects(checkRead(response("synthetiC"), expected, 9), /read_integrity/);
  await assert.rejects(checkRead(response("synthetic", { Age: "2" }), expected, 9), /read_age/);
  await assert.rejects(checkRead(response("synthetic", { "Cache-Control": "max-age=300" }), expected, 9), /read_cache/);
});

test("actual isolated Worker/R2: bounded reads, conflicting writes, withdrawal and monitor recovery", { timeout: 30000 }, async () => {
  const report = await runLocalRehearsal({ requests: 24, concurrency: 4, payload_bytes: 1024 });
  assert.equal(report.passed, true, JSON.stringify(report));
  assert.equal(report.public_capacity_verified, false);
  assert.equal(report.song_contract_verified, false);
  assert.equal(report.cleanup.status, "complete");
  assert.equal(report.load.successful, 24);
  assert.equal(report.load.failed, 0);
  assert.ok(report.load.maximum_in_flight <= 4);
  assert.deepEqual(report.completed_phases, ["warmup", "read_load", "concurrent_conflict", "withdraw_restore", "freshness_incident"]);
  assert.deepEqual(report.monitor_observations.map(x => x.event), [null, null, "opened", null, "recovered"]);
  assert.match(report.source_sha256["package-lock.json"], /^[a-f0-9]{64}$/);
  assert.doesNotMatch(JSON.stringify(report), /127\.0\.0\.1|Bearer |PUBLISH_TOKEN/);
});

test("startup abort and cleanup failures are bounded and never reported as success", async () => {
  const controller = new AbortController();
  const ready = waitForReady(new Promise(() => {}), controller.signal);
  controller.abort();
  await assert.rejects(ready, /runtime_start_aborted/);
  assert.equal((await boundedCleanup(() => Promise.resolve())).status, "complete");
  assert.equal((await boundedCleanup(() => { throw new Error("secret"); })).code, "runtime_cleanup_failed");
  const begin = performance.now();
  const result = await boundedCleanup(() => new Promise(() => {}), 25);
  assert.equal(result.status, "unconfirmed");
  assert.equal(result.code, "runtime_cleanup_timeout");
  assert.ok(performance.now() - begin < 2000);
});

test("first-connection rehearsal refuses an existing receipt path before running", async (t) => {
  const dir = await createTestDirectory(t);
  const receipt = join(dir, "receipt.json");
  await writeFile(receipt, "keep");
  const errors = []; const original = process.stderr.write;
  process.stderr.write = chunk => { errors.push(String(chunk)); return true; };
  let code;
  try { code = await firstConnectionMain(["--examples", dir, "--dist", dir, "--output", receipt]); }
  finally { process.stderr.write = original; }
  assert.equal(code, 2, "refused as an argument error, not as a failed rehearsal");
  assert.equal(await readFile(receipt, "utf8"), "keep");
  assert.match(errors.join(""), /rehearsal_arguments_or_output_error/);
});

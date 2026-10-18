import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, writeFile, readFile, rm, realpath } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, dirname, basename } from "node:path";
import { createMeasuredRequests, main, runLiveExpiryRehearsal } from "../rehearse-live-expiry.mjs";

async function sandbox(t) {
  const parent = await realpath(tmpdir()), directory = await mkdtemp(join(parent, "live-expiry-test-"));
  t.after(async () => {
    assert.equal(dirname(await realpath(directory)), parent); assert.ok(basename(directory).startsWith("live-expiry-test-"));
    await rm(directory, { recursive: true, force: false });
  });
  return directory;
}

test("all 18 attempted requests count, including expected 401/403/404; a nineteenth never reaches transport", async () => {
  const rows = []; let calls = 0;
  const statuses = [401, 200, 404, 200, 200, 200, 200, 200, 200, 404, 200, 200, 200, 403, 403, 403, 200, 200];
  const send = createMeasuredRequests(async () => ({ status: statuses[calls++] }), { elapsed: () => 0, rows });
  for (const expected of statuses) await send("synthetic", "/v1/game/123.json", { method: "HEAD" }, expected);
  await assert.rejects(send("over_budget", "/v1/game/123.json", {}, 200), /measured_request_failed/);
  assert.equal(calls, 18); assert.equal(rows.length, 18); assert.equal(rows.filter(row => row.status === 403).length, 3);
});

test("UTF-8 body bytes and elapsed deadline fail closed before transport, with no subsequent attempt", async () => {
  for (const [body, elapsed] of [["가".repeat(683), 0], ["{}", 100000]]) {
    let calls = 0; const rows = [];
    const send = createMeasuredRequests(async () => { calls++; return { status: 200 }; }, { elapsed: () => elapsed, rows });
    await assert.rejects(send("invalid_budget", "/v1/game/123.json", { body }, 200), /measured_request_failed/);
    await assert.rejects(send("later", "/v1/game/123.json", {}, 200), /request_sequence_stopped/);
    assert.equal(calls, 0); assert.equal(rows.length, 0);
  }
});

test("unexpected HTTP state and uncertain transport are counted once and prohibit later writes", async () => {
  for (const uncertain of [false, true]) {
    let calls = 0; const rows = [];
    const send = createMeasuredRequests(async () => { calls++; if (uncertain) throw new Error("private-origin-and-token"); return { status: 412 }; },
      { elapsed: () => 10, rows });
    await assert.rejects(send("create", "/v1/game/123.json", { method: "PUT", body: "{}" }, 200), /measured_request_failed/);
    await assert.rejects(send("retry_forbidden", "/v1/game/123.json", { method: "PUT", body: "{}" }, 200), /request_sequence_stopped/);
    assert.equal(calls, 1); assert.equal(rows.length, 1); assert.equal(rows[0].status, uncertain ? null : 412);
    assert.doesNotMatch(JSON.stringify(rows), /private|token|origin/);
  }
});

test("external targets, secrets, ports, clock overrides and positional arguments refuse before runtime", async () => {
  let runs = 0;
  for (const args of [["--origin", "https://private.example"], ["--token", "private"], ["--port", "1234"],
    ["--expires-at", "2030-01-01"], ["--clock", "0"], ["unexpected"], ["--output", ""]]) {
    let out = "", err = "";
    assert.equal(await main(args, { run: () => { runs++; assert.fail(); }, output: value => { out += value; }, errorOutput: value => { err += value; } }), 2);
    assert.equal(out, ""); assert.doesNotMatch(err, /private|https|1234|2030/);
  }
  assert.equal(runs, 0);
});

test("existing output and missing parent stop before runtime; a destination race never overwrites", async t => {
  const directory = await sandbox(t), existing = join(directory, "existing.json"), race = join(directory, "race.json");
  await writeFile(existing, "keep"); let runs = 0;
  for (const path of [existing, join(directory, "missing", "receipt.json")]) {
    assert.equal(await main(["--output", path], { run: () => { runs++; assert.fail(); }, output: () => {}, errorOutput: () => {} }), 2);
  }
  assert.equal(runs, 0); assert.equal(await readFile(existing, "utf8"), "keep");
  assert.equal(await main(["--output", race], { run: async () => { await writeFile(race, "other writer"); return { passed: true }; },
    output: () => {}, errorOutput: () => {} }), 2);
  assert.equal(await readFile(race, "utf8"), "other writer");
});

test("one real Worker crosses its real deadline within the measured budget and preserves restored bytes", { timeout: 125000 }, async () => {
  const report = await runLiveExpiryRehearsal();
  assert.equal(report.passed, true, JSON.stringify(report));
  assert.deepEqual(report.completed_phases, ["startup", "before_expiry", "real_clock_wait", "after_expiry"]);
  assert.equal(report.runtime_count, 1); assert.equal(report.runtime_restarted, false); assert.equal(report.clock_mocked, false);
  assert.equal(report.http_requests, 18); assert.equal(report.requests.length, 18); assert.ok(report.maximum_body_bytes <= 2048);
  assert.equal(report.request_budget_verified, true); assert.equal(report.total_budget_verified, true); assert.ok(report.elapsed_ms <= 120000);
  assert.ok(Date.parse(report.last_pre_expiry_utc) < Date.parse(report.expiry_utc));
  assert.ok(Date.parse(report.first_post_expiry_utc) >= Date.parse(report.expiry_utc));
  assert.equal(report.withdraw_restore_verified, true); assert.equal(report.live_deadline_crossing_verified, true);
  assert.equal(report.bytes_and_etag_preserved, true); assert.equal(report.payload_sha256_before, report.payload_sha256_after);
  assert.deepEqual(report.requests.slice(-5).map(row => row.status), [403, 403, 403, 200, 200]);
  assert.equal(report.cleanup.runtime, "complete"); assert.equal(report.cleanup.temporary_storage, "removed");
  assert.equal(report.cloud_verified, false); assert.equal(report.song_publisher_verified, false); assert.equal(report.credential_revocation_verified, false);
  assert.equal(report.delivery_confirmed, false); assert.equal(report.access_gate_enabled, true); assert.equal(report.telemetry_enabled, false);
  assert.equal(report.feedback_enabled, false); assert.doesNotMatch(JSON.stringify(report), /127\.0\.0\.1|pz_viewer=|pitcheezy-operator-drill-|https?:\/\//);
});
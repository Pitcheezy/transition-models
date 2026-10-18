import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile, writeFile, rm, realpath, access } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join } from "node:path";
import { EventEmitter } from "node:events";
import { PassThrough } from "node:stream";
import { childEnvironment, collectChild, main, removeOwnedDirectory, runOperatorToolsRehearsal } from "../rehearse-operator-tools.mjs";

async function sandbox(t) {
  const parent = await realpath(tmpdir()); const directory = await mkdtemp(join(parent, "operator-drill-test-"));
  t.after(async () => {
    assert.equal(dirname(await realpath(directory)), parent);
    assert.ok(basename(directory).startsWith("operator-drill-test-"));
    await rm(directory, { recursive: true, force: false });
  });
  return directory;
}

test("child environment excludes inherited account, proxy, preload and publisher secrets", () => {
  const actual = childEnvironment("temporary", { PITCHEEZY_NOTICE_TOKEN: "synthetic-only" }, {
    Path: "required-os-path", SYSTEMROOT: "system", CLOUDFLARE_API_TOKEN: "private", HTTP_PROXY: "private",
    NODE_OPTIONS: "--require private", PITCHEEZY_PUBLISH_TOKEN: "private", PZ_OPERATOR_DRILL_CODE: "private", HOME: "private" });
  assert.equal(actual.Path, "required-os-path"); assert.equal(actual.SYSTEMROOT, "system");
  assert.equal(actual.TEMP, "temporary"); assert.equal(actual.PITCHEEZY_NOTICE_TOKEN, "synthetic-only");
  assert.equal(JSON.stringify(actual).includes("private"), false);
});

test("arbitrary destination, credentials, ports and positional arguments refuse before any runtime", async () => {
  let runs = 0;
  for (const args of [["--origin", "https://private.example"], ["--token", "private-secret"], ["--port", "1234"], ["unexpected"], ["--output", ""]]) {
    let out = "", err = "";
    const code = await main(args, { run: () => { runs++; assert.fail("no runtime"); }, output: text => { out += text; }, errorOutput: text => { err += text; } });
    assert.equal(code, 2); assert.equal(out, ""); assert.doesNotMatch(err, /private|https|1234/);
  }
  assert.equal(runs, 0);
});

test("existing output and missing parent refuse before runtime; original output remains intact", async t => {
  const directory = await sandbox(t), file = join(directory, "receipt.json"); await writeFile(file, "keep");
  let runs = 0;
  for (const path of [file, join(directory, "missing", "receipt.json")]) {
    assert.equal(await main(["--output", path], { run: () => { runs++; assert.fail("no runtime"); }, output: () => {}, errorOutput: () => {} }), 2);
  }
  assert.equal(runs, 0); assert.equal(await readFile(file, "utf8"), "keep");
});

test("receipt destination race preserves the other writer's file", async t => {
  const directory = await sandbox(t), file = join(directory, "receipt.json");
  const code = await main(["--output", file], { run: async () => { await writeFile(file, "other writer"); return { passed: true }; }, output: () => {}, errorOutput: () => {} });
  assert.equal(code, 2); assert.equal(await readFile(file, "utf8"), "other writer");
});

test("cleanup refuses an unowned directory even when it has a matching parent", async t => {
  const directory = await sandbox(t), file = join(directory, "keep.json"); await writeFile(file, "keep");
  await assert.rejects(removeOwnedDirectory(directory, dirname(directory), basename(directory)), /unsafe_cleanup_path/);
  await access(file);
});

test("failure after actual runtime startup cleans only this run and redacts the exception", { timeout: 20000 }, async () => {
  const report = await runOperatorToolsRehearsal({ onPhase: phase => { if (phase === "startup") throw new Error("private-token-and-location"); } });
  assert.equal(report.passed, false); assert.deepEqual(report.completed_phases, ["startup"]);
  assert.equal(report.cli_invocation_count, 0); assert.equal(report.cleanup.children, "complete");
  assert.equal(report.cleanup.temporary_storage, "removed");
  assert.ok(report.cleanup.runtimes.every(value => value.status === "complete"));
  assert.equal(JSON.stringify(report).includes("private-token-and-location"), false);
});

test("actual three CLI processes compose against scoped Worker/R2 and preserve failure history", { timeout: 90000 }, async () => {
  const report = await runOperatorToolsRehearsal();
  assert.equal(report.passed, true, JSON.stringify(report));
  assert.deepEqual(report.completed_phases, ["startup", "dry_runs", "gate_and_publish", "stale_and_recovery",
    "notice_on_off", "out_of_scope", "expired_restart", "preservation_and_redaction"]);
  assert.equal(report.withdraw_restore_verified, true);
  assert.deepEqual(report.monitor_history, ["opened", "recovered"]); assert.equal(report.recovery_exit_code, 1);
  assert.ok(report.cli_invocations.some(value => value.outcome === "conflict"));
  assert.equal(report.cli_invocations.filter(value => value.outcome === "rejected").length, 6);
  assert.ok(report.cli_invocations.some(value => value.tool === "notice" && value.outcome === "applied"));
  assert.equal(report.cli_invocation_count, report.cli_invocations.length);
  assert.equal(report.http_requests, null); assert.equal(report.http_request_budget_verified, false);
  assert.equal(report.delivery_confirmed, false); assert.equal(report.actual_ctrl_c_verified, false);
  assert.equal(report.cleanup.children, "complete"); assert.equal(report.cleanup.temporary_storage, "removed");
  assert.equal(report.cleanup.runtimes.length, 2); assert.ok(report.cleanup.runtimes.every(value => value.status === "complete"));
  assert.doesNotMatch(JSON.stringify(report), /127\.0\.0\.1|pz_viewer=|pitcheezy-operator-drill-|https?:\/\//);
  assert.ok(report.input_files_preserved > 0); assert.equal(report.secrets_absent_from_cli_and_receipt, true);
});

test("a child that ignores kill is bounded and never reported as a confirmed close", { timeout: 2000 }, async () => {
  const child = new EventEmitter(); child.pid = 123;
  child.stdout = new PassThrough(); child.stderr = new PassThrough();
  let kills = 0, unrefs = 0;
  child.kill = () => { kills++; return false; }; child.unref = () => { unrefs++; };
  await assert.rejects(collectChild(child, { timeoutMs: 10, stopGraceMs: 10 }), /cli_close_unconfirmed/);
  assert.equal(kills, 1); assert.equal(unrefs, 1); assert.equal(child.stdout.destroyed, true);
  assert.equal(child.stderr.destroyed, true);
});
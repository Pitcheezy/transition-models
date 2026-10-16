import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, writeFile, readFile, readdir, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import { main } from "../notice-cli.mjs";

const TOKEN = "synthetic-notice-cli-test-token-not-a-real-credential";
const ETAG = '"' + "c".repeat(32) + '"';
const plan = (extra = {}) => ({ schema: "pitcheezy-notice-plan-v1", origin: "https://private.example.test",
  allow_loopback_http: false, method: "GET", condition: null, change: null, ...extra });
const change = { active: false, operator: "private-operator", reason: "private-reason", message_id: "maintenance" };
const inspectResponse = () => new Response(JSON.stringify({ state: { active: false, message_id: "maintenance", revision: 2, since: null, etag: ETAG },
  audit: [{ schema: "pitcheezy-notice-audit-v1", revision: 2, etag_after: ETAG, reason: change.reason }],
  audit_truncated: false, audit_unavailable: false, messages: {} }), { headers: { "Content-Type": "application/json", ETag: ETAG,
    "Cache-Control": "no-store, no-transform" } });
async function temp(fn) {
  const dir = await mkdtemp(join(tmpdir(), "pz-notice-cli-"));
  try { await fn(dir); } finally { await rm(dir, { recursive: true, force: true }); }
}
async function invoke(args, environment = {}, fetchImpl = () => { assert.fail("network forbidden"); }) {
  let stdout = "", stderr = "";
  const exit = await main(args, environment, { fetchImpl, stdout: { write: s => { stdout += s; } }, stderr: { write: s => { stderr += s; } } });
  for (const secret of [TOKEN, "private.example.test", change.reason, change.operator, "c".repeat(12)]) {
    assert.equal((stdout + stderr).includes(secret), false, secret);
  }
  return { exit, stdout, stderr, receipt: stdout ? JSON.parse(stdout) : null };
}

test("CLI defaults to offline dry-run and does not create the optional snapshot", async () => temp(async dir => {
  const input = join(dir, "plan.json"), output = join(dir, "snapshot.json");
  await writeFile(input, JSON.stringify(plan()));
  const r = await invoke(["--plan", input, "--snapshot", output]);
  assert.equal(r.exit, 0); assert.equal(r.receipt.outcome, "dry_run"); assert.deepEqual(await readdir(dir), ["plan.json"]);
}));

test("explicit GET writes a new private snapshot but only redacted facts to stdout", async () => temp(async dir => {
  const input = join(dir, "plan.json"), output = join(dir, "snapshot.json"); await writeFile(input, JSON.stringify(plan()));
  const before = await readFile(input);
  const r = await invoke(["--plan", input, "--execute", "--snapshot", output], { PITCHEEZY_NOTICE_TOKEN: TOKEN }, inspectResponse);
  assert.equal(r.exit, 0); assert.equal(r.receipt.snapshot_saved, true); assert.equal(r.receipt.revision, 2);
  const snapshot = JSON.parse(await readFile(output, "utf8")); assert.deepEqual(snapshot.condition, { if_match: ETAG });
  assert.equal(snapshot.origin, plan().origin); assert.equal(JSON.stringify(snapshot).includes(change.reason), false);
  assert.deepEqual(await readFile(input), before);
  const refusal = await invoke(["--plan", input, "--execute", "--snapshot", output]);
  assert.equal(refusal.exit, 2); assert.match(refusal.stderr, /snapshot_must_be_new/);
}));

test("invalid plans, missing token, secret arguments and input/output collision refuse without requests", async () => temp(async dir => {
  const input = join(dir, "plan.json"); await writeFile(input, JSON.stringify(plan()));
  for (const args of [["--plan", input, "--token", TOKEN], ["--plan", input, "--execute"],
    ["--plan", input, "--execute", "--snapshot", input]]) {
    const r = await invoke(args); assert.equal(r.exit, 2);
  }
  await writeFile(input, JSON.stringify({ ...plan(), token: TOKEN }));
  assert.equal((await invoke(["--plan", input])).exit, 2);
  assert.deepEqual(await readdir(dir), ["plan.json"]);
}));

test("PUT cannot use snapshot output and unknown/conflict/audit missing never exit as success", async () => temp(async dir => {
  const input = join(dir, "plan.json"); await writeFile(input, JSON.stringify(plan({ method: "PUT", condition: { if_match: ETAG }, change })));
  assert.equal((await invoke(["--plan", input, "--snapshot", join(dir, "snapshot.json")])).exit, 2);
  for (const fetchImpl of [async () => { throw new Error(TOKEN); }, async () => new Response(null, { status: 412 }),
    async () => new Response(JSON.stringify({ active: false, message_id: "maintenance", revision: 3, since: null,
      change_id: "12345678-abcd-abcd-abcd-123456789012", audit_recorded: false }),
    { headers: { "Content-Type": "application/json", ETag: ETAG, "Cache-Control": "no-store, no-transform" } })]) {
    let count = 0;
    const r = await invoke(["--plan", input, "--execute"], { PITCHEEZY_NOTICE_TOKEN: TOKEN }, (...args) => { count++; return fetchImpl(...args); });
    assert.equal(r.exit, 3); assert.equal(count, 1);
  }
}));

test("actual CLI process keeps dry-run offline, rejects token flags, and sanitizes malformed inputs", async () => temp(async dir => {
  const input = join(dir, "plan.json"); await writeFile(input, JSON.stringify(plan()));
  const cli = fileURLToPath(new URL("../notice-cli.mjs", import.meta.url));
  const execute = promisify(execFile);
  const result = await execute(process.execPath, [cli, "--plan", input], { timeout: 5000 });
  assert.equal(JSON.parse(result.stdout).outcome, "dry_run"); assert.equal(result.stderr, "");
  try { await execute(process.execPath, [cli, "--plan", input, "--token", TOKEN], { timeout: 5000 }); assert.fail("must reject"); }
  catch (error) { assert.equal(error.code, 2); assert.equal((error.stdout + error.stderr).includes(TOKEN), false); }
  await writeFile(input, "not json " + TOKEN);
  try { await execute(process.execPath, [cli, "--plan", input], { timeout: 5000 }); assert.fail("must reject"); }
  catch (error) { assert.equal(error.code, 2); assert.equal((error.stdout + error.stderr).includes(TOKEN), false); }
}));

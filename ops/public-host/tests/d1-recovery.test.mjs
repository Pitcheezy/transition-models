import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, writeFile, readFile, unlink, rmdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import { runD1RecoveryRehearsal } from "../rehearse-d1-recovery.mjs";

const execute = promisify(execFile);
const cli = fileURLToPath(new URL("../rehearse-d1-recovery.mjs", import.meta.url));
let receipt;
const rehearsal = () => receipt ??= runD1RecoveryRehearsal();

// This is a real isolated SQLite run, not a mock of an expected inspection object.
test("local recovery inspection distinguishes old records, rewound budgets and malformed copies", { timeout: 110000 }, async () => {
  const r = await rehearsal();
  assert.equal(r.schema, "pitcheezy-local-d1-recovery-v1");
  assert.equal(r.passed, true, JSON.stringify(r));
  assert.equal(r.original_unchanged, true);
  assert.equal(r.normal_duplicate_insert_rejected, true);
  assert.equal(r.temporary_storage, "removed");
  assert.deepEqual(r.cases.map(c => c.name), [
    "normal", "restored_older", "cleaned_copy", "missing_budget_evidence",
    "missing_index", "wrong_index", "schema_mismatch", "null_identity",
    "duplicate_identity", "invalid_budget",
  ]);
  const cases = Object.fromEntries(r.cases.map(c => [c.name, c.inspection]));
  assert.equal(cases.normal.structure, "ok");
  assert.equal(cases.normal.integrity, "ok");
  assert.deepEqual(cases.normal.retained, { sessions: 1, feedback: 1 });
  assert.deepEqual(cases.normal.expired, { sessions: 0, feedback: 0 });
  assert.equal(cases.normal.budget.state, "not_below_evidence");
  assert.deepEqual(cases.normal.budget.observed, { session: 2, feedback: 1 });
  assert.deepEqual(cases.normal.budget.floor, { session: 2, feedback: 1 });
  assert.deepEqual(cases.restored_older.retained, { sessions: 1, feedback: 1 });
  assert.deepEqual(cases.restored_older.expired, { sessions: 1, feedback: 1 });
  assert.equal(cases.restored_older.budget.state, "rewound");
  assert.deepEqual(cases.restored_older.budget.observed, { session: 2, feedback: 1 });
  assert.deepEqual(cases.restored_older.budget.floor, { session: 5, feedback: 3 });
  assert.deepEqual(cases.cleaned_copy.expired, { sessions: 0, feedback: 0 });
  assert.deepEqual(cases.cleaned_copy.retained, { sessions: 1, feedback: 1 });
  assert.equal(cases.cleaned_copy.budget.state, "rewound", "deleting expired records cannot repair a rewound daily budget");
  assert.equal(cases.missing_budget_evidence.budget.state, "missing_evidence");
  assert.equal(cases.missing_budget_evidence.budget.floor, null);
  for (const name of ["missing_index", "wrong_index", "schema_mismatch", "duplicate_identity"]) {
    assert.equal(cases[name].structure, "invalid", name);
    assert.equal(cases[name].integrity, "not_checked", name);
    assert.equal(cases[name].budget.state, "not_checked", name);
    assert.ok(cases[name].findings.length > 0, name);
  }
  for (const name of ["null_identity", "invalid_budget"]) {
    assert.equal(cases[name].structure, "ok", name);
    assert.equal(cases[name].integrity, "invalid", name);
    assert.ok(cases[name].findings.length > 0, name);
  }
  for (const c of r.cases) {
    assert.equal(c.source_unchanged, true, c.name);
    assert.equal(c.read_only_enforced, true, c.name);
    assert.ok(Array.isArray(c.inspection.findings), c.name);
  }
});

test("inspection never authorizes collection or claims cloud recovery, and receipts omit private data", { timeout: 110000 }, async () => {
  const r = await rehearsal();
  assert.equal(r.synthetic, true);
  assert.equal(r.collection_resume_authorized, false);
  assert.equal(r.cloud_restore_verified, false);
  assert.equal(r.crash_recovery_verified, false);
  assert.equal(r.rto_ms, null);
  assert.equal(r.rpo_records, null);
  for (const c of r.cases) assert.equal(c.inspection.collection_resume_authorized, false, c.name);
  assert.doesNotMatch(JSON.stringify(r), /127\.0\.0\.1|Bearer |session_id|feedback_id|PUBLISH_TOKEN|(?:C:|[A-Z]:)\\\\|\/Users\//);
});

test("recovery CLI refuses external targets and input databases before running", async () => {
  for (const args of [
    ["--origin", "https://never-contact.example"],
    ["--database", "never-open.sqlite"],
    ["--snapshot", "never-open.sqlite"],
  ]) {
    await assert.rejects(execute(process.execPath, [cli, ...args], { timeout: 5000 }),
      error => error.code === 2 && error.stdout === "" && error.stderr === "d1_recovery_rehearsal_failed\n");
  }
});

test("recovery CLI refuses to replace an existing output file", { timeout: 110000 }, async () => {
  const directory = await mkdtemp(join(tmpdir(), "pitcheezy-recovery-test-"));
  const output = join(directory, "keep.json");
  const sentinel = "existing private evidence must survive\n";
  try {
    await writeFile(output, sentinel, { flag: "wx" });
    await assert.rejects(execute(process.execPath, [cli, "--output", output], { timeout: 100000 }),
      error => error.code === 2 && error.stdout === "" && error.stderr.endsWith("d1_recovery_rehearsal_failed\n"));
    assert.equal(await readFile(output, "utf8"), sentinel);
  } finally {
    await unlink(output);
    await rmdir(directory);
  }
});

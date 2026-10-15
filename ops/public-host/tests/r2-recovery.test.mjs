import test from "node:test";
import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import { runR2RecoveryRehearsal } from "../rehearse-r2-recovery.mjs";

const execute = promisify(execFile);
const cli = fileURLToPath(new URL("../rehearse-r2-recovery.mjs", import.meta.url));
let receipt;
const rehearsal = () => receipt ??= runR2RecoveryRehearsal();

test("isolated R2 raw restore replays old tokens and notice state while external gates remain closed", { timeout: 80000 }, async () => {
  const r = await rehearsal();
  assert.equal(r.passed, true, JSON.stringify(r));
  assert.deepEqual(r.cleanup, [{ status: "complete" }, { status: "complete" }]);
  assert.deepEqual(r.cases.map(c => c.name), ["normal_api_restore", "raw_live_rollback", "raw_tombstone_rollback",
    "missing_metadata", "raw_notice_off_rollback", "notice_key_absent", "normal_api_notice_reasserted",
    "external_gates_survive_raw_restore", "closed_runtime_notice_reasserted"]);
  const c = Object.fromEntries(r.cases.map(row => [row.name, row]));
  assert.equal(c.normal_api_restore.stale_delete_status, 412);
  assert.equal(c.raw_live_rollback.original_etag_returned, true);
  assert.equal(c.raw_live_rollback.old_delete_status, 200);
  assert.equal(c.raw_tombstone_rollback.public_status, 404);
  assert.equal(c.raw_tombstone_rollback.latest_writer_status, 412);
  assert.equal(c.missing_metadata.public_status, 503);
  assert.equal(c.raw_notice_off_rollback.audit_unavailable, false);
  assert.equal(c.raw_notice_off_rollback.newer_audit_retained, true);
  assert.equal(c.raw_notice_off_rollback.active, false);
  assert.equal(c.raw_notice_off_rollback.page_status, 200);
  assert.equal(c.notice_key_absent.revision, 0);
  assert.equal(c.external_gates_survive_raw_restore.public_status, 503);
  assert.equal(c.external_gates_survive_raw_restore.upload_status, 503);
  assert.equal(c.external_gates_survive_raw_restore.page_status, 200);
  assert.equal(c.external_gates_survive_raw_restore.whole_site_blocked, false);
  for (const name of ["normal_api_notice_reasserted", "closed_runtime_notice_reasserted"]) {
    assert.equal(c[name].active, true);
    assert.equal(c[name].page_status, 503);
    assert.equal(c[name].public_resume_authorized, false);
  }
});

test("receipt omits ephemeral secrets and never certifies account restore or public resumption", { timeout: 80000 }, async () => {
  const r = await rehearsal();
  assert.equal(r.schema, "pitcheezy-local-r2-recovery-v1");
  assert.equal(r.synthetic, true);
  for (const key of ["public_resume_authorized", "cloud_restore_verified", "whole_bucket_restore_verified", "crash_recovery_verified"]) assert.equal(r[key], false);
  assert.equal(r.rto_ms, null); assert.equal(r.rpo_records, null);
  assert.equal(r.evidence.external_recovery_evidence_required, true);
  assert.equal(Object.keys(r.source_sha256).length, 7);
  for (const value of Object.values(r.source_sha256)) assert.match(value, /^[a-f0-9]{64}$/);
  assert.doesNotMatch(JSON.stringify(r), /127\.0\.0\.1|localhost|Bearer |https?:\/\/|PUBLISH_TOKEN|NOTICE_TOKEN|[A-Z]:\\|\/Users\//);
});

test("recovery CLI rejects external targets, source backups and positional paths before runtime startup", async () => {
  for (const args of [["--origin", "https://never-contact.example"], ["--snapshot", "never-open"], ["--bucket", "never-open"], ["unexpected-path"]]) {
    await assert.rejects(execute(process.execPath, [cli, ...args], { timeout: 5000 }),
      error => error.code === 2 && error.stdout === "" && error.stderr === "r2_recovery_rehearsal_failed\n");
  }
});

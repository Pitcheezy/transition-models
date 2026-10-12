import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile, readFile, symlink, unlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, basename, dirname } from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { fileURLToPath } from "node:url";
import { runLifecycleRehearsal, removeOwnedSandbox } from "../rehearse-lifecycle.mjs";

test("persistent local R2/D1 survives restart, key rotation, OFF cleanup and another restart", { timeout: 110000 }, async () => {
  const r = await runLifecycleRehearsal();
  assert.equal(r.passed, true, JSON.stringify(r));
  assert.deepEqual(r.completed_phases.map(x => x.name),
    ["seed", "restart_and_rotate", "collection_off_scheduled", "cleanup_persisted"]);
  assert.equal(r.shutdowns.length, 4);
  assert.ok(r.shutdowns.every(x => x.status === "complete"));
  assert.equal(r.temporary_storage, "removed");
  assert.equal(r.cloud_backup_restore_verified, false);
  assert.equal(r.crash_recovery_verified, false);
  assert.equal(r.production_cron_verified, false);
  assert.equal(r.completed_phases[2].before.sessions, 3);
  assert.equal(r.completed_phases[2].after.sessions, 2);
  assert.equal(r.completed_phases[2].scheduled_outcome, "ok");
  assert.equal(r.completed_phases[2].repeat_cleanup_unchanged, true);
  assert.doesNotMatch(JSON.stringify(r), /127\.0\.0\.1|Bearer |session_id|feedback_id|PUBLISH_TOKEN_SHA256/);
});

test("sandbox removal refuses mismatched, nested and linked targets and preserves files", async () => {
  const root = await mkdtemp(join(tmpdir(), "pitcheezy-lifecycle-"));
  const other = await mkdtemp(join(tmpdir(), "pitcheezy-lifecycle-"));
  const nested = join(root, "pitcheezy-lifecycle-nested");
  const link = join(root, "pitcheezy-lifecycle-link");
  try {
    await mkdir(nested);
    await writeFile(join(root, "sentinel.txt"), "keep");
    await writeFile(join(other, "sentinel.txt"), "keep other");
    await assert.rejects(removeOwnedSandbox(root, tmpdir(), "pitcheezy-lifecycle-wrong"), /unsafe_cleanup_path/);
    await assert.rejects(removeOwnedSandbox(root, dirname(tmpdir()), basename(root)), /unsafe_cleanup_path/);
    await assert.rejects(removeOwnedSandbox(nested, tmpdir(), basename(nested)), /unsafe_cleanup_path/);
    await symlink(other, link, process.platform === "win32" ? "junction" : "dir");
    await assert.rejects(removeOwnedSandbox(link, tmpdir(), basename(other)), /unsafe_cleanup_path/);
    assert.equal(await readFile(join(root, "sentinel.txt"), "utf8"), "keep");
    assert.equal(await readFile(join(other, "sentinel.txt"), "utf8"), "keep other");
    await unlink(link);
  } finally {
    await removeOwnedSandbox(root, tmpdir(), basename(root));
    await removeOwnedSandbox(other, tmpdir(), basename(other));
  }
});

test("lifecycle CLI refuses external-target arguments before running", async () => {
  await assert.rejects(
    promisify(execFile)(process.execPath,
      [fileURLToPath(new URL("../rehearse-lifecycle.mjs", import.meta.url)), "--origin", "https://never-contact.example"],
      { timeout: 5000 }),
    error => error.code === 2 && error.stdout === "" && error.stderr === "lifecycle_rehearsal_failed\n",
  );
});

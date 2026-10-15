import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import fsp from "node:fs/promises";
import { syncBuiltinESMExports } from "node:module";
import { tmpdir } from "node:os";
import { basename, dirname, join, resolve } from "node:path";
import { runAlertsOnce } from "../alerts-cli.mjs";
import { initialAlertState, serializeAlertState, validateAlertState } from "../alerts.mjs";

const NOW = Date.parse("2026-10-15T06:00:00Z");
const event = { id: "a".repeat(64), kind: "opened", at_ms: NOW, issues: ["freshness_stale"] };
const monitorBytes = JSON.stringify({ state: { events: [event], incident: event }, report: {} });
const configBytes = JSON.stringify({ schema: "pitcheezy-host-alerts-v1", transport: "mock",
  recipients: [{ id: "song", label: "Synthetic A" }, { id: "ours", label: "Synthetic B" }],
  max_attempts: 3, remind_after_minutes: 0 });
const ioError = () => Object.assign(new Error("synthetic I/O failure"), { code: "EIO" });
const isTemp = (f, path) => dirname(resolve(String(path))) === f.dir &&
  basename(String(path)).startsWith(".state.json.") && String(path).endsWith(".tmp");

async function fixture(work) {
  const dir = await fsp.mkdtemp(join(tmpdir(), "pitcheezy-alert-write-test-"));
  const f = { dir, monitor: join(dir, "monitor.json"), config: join(dir, "config.json"),
    state: join(dir, "state.json"), original: serializeAlertState(initialAlertState()) };
  await fsp.writeFile(f.monitor, monitorBytes, { flag: "wx" });
  await fsp.writeFile(f.config, configBytes, { flag: "wx" });
  await fsp.writeFile(f.state, f.original, { flag: "wx" });
  try { await work(f); }
  finally {
    assert.equal(await fsp.readFile(f.monitor, "utf8"), monitorBytes);
    assert.equal(await fsp.readFile(f.config, "utf8"), configBytes);
    // Only regular files under this exact newly-created directory are removed.
    for (const entry of await fsp.readdir(dir, { withFileTypes: true })) {
      assert.equal(entry.isFile(), true, "unexpected cleanup target");
      await fsp.unlink(join(dir, entry.name));
    }
    await fsp.rmdir(dir);
  }
}
async function patchedFs(make, work) {
  const original = { open: fs.promises.open, rename: fs.promises.rename, unlink: fs.promises.unlink };
  Object.assign(fs.promises, make(original)); syncBuiltinESMExports();
  try { return await work(); }
  finally { Object.assign(fs.promises, original); syncBuiltinESMExports(); }
}
function wrap(handle, method, replacement) {
  return new Proxy(handle, { get(target, key) {
    if (key === method) return (...args) => replacement(target, ...args);
    const value = Reflect.get(target, key, target);
    return typeof value === "function" ? value.bind(target) : value;
  } });
}
const run = f => runAlertsOnce(f.monitor, f.config, f.state, { now: NOW });
const temps = async f => (await fsp.readdir(f.dir)).filter(name => isTemp(f, join(f.dir, name)));
async function priorStateAndNoLock(f) {
  assert.equal(await fsp.readFile(f.state, "utf8"), f.original, "failed save must preserve previous state");
  await assert.rejects(fsp.lstat(f.state + ".lock"), { code: "ENOENT" });
}
async function successfulSave(f) {
  const result = await run(f);
  assert.equal(result.schema, "pitcheezy-host-alerts-run-v1");
  assert.equal(result.transport, "mock"); assert.equal(result.delivery_confirmed, false);
  assert.equal(result.mock_messages.length, 2);
  const state = validateAlertState(JSON.parse(await fsp.readFile(f.state, "utf8")));
  assert.equal(state.schema, "pitcheezy-host-alert-state-v3");
  assert.equal(Object.keys(state.deliveries).length, 2);
  await assert.rejects(fsp.lstat(f.state + ".lock"), { code: "ENOENT" });
  return result;
}

for (const operation of ["open", "writeFile", "sync", "rename"]) {
  test(`alerts temporary ${operation} failure cleans owned bytes, preserves state and permits retry`, { concurrency: false }, async () => {
    await fixture(async f => {
      let injected = false;
      await patchedFs(original => ({
        open: async (path, ...args) => {
          if (!isTemp(f, path) || args[0] !== "wx" || operation === "rename" || injected) return original.open(path, ...args);
          if (operation === "open") { injected = true; throw ioError(); }
          const handle = await original.open(path, ...args);
          return wrap(handle, operation, async (target, ...callArgs) => {
            injected = true;
            if (operation === "writeFile") await target.writeFile(callArgs[0].slice(0, 40), "utf8");
            throw ioError();
          });
        },
        rename: async (from, to) => {
          if (operation === "rename" && isTemp(f, from)) { injected = true; throw ioError(); }
          return original.rename(from, to);
        },
      }), async () => { await assert.rejects(run(f), { code: "EIO" }); });
      assert.equal(injected, true);
      await priorStateAndNoLock(f); assert.deepEqual(await temps(f), []);
      await successfulSave(f); assert.deepEqual(await temps(f), []);
    });
  });
}

test("an externally pre-created temporary file survives wx refusal and a later retry", { concurrency: false }, async () => {
  await fixture(async f => {
    const external = "other writer's temporary evidence\n";
    let externalPath;
    await patchedFs(original => ({ open: async (path, ...args) => {
      if (isTemp(f, path) && args[0] === "wx" && !externalPath) {
        externalPath = String(path);
        const file = await original.open(path, "wx", 0o600);
        try { await file.writeFile(external, "utf8"); } finally { await file.close(); }
      }
      return original.open(path, ...args);
    } }), async () => { await assert.rejects(run(f), { code: "EEXIST" }); });
    assert.ok(externalPath);
    await priorStateAndNoLock(f);
    assert.equal(await fsp.readFile(externalPath, "utf8"), external);
    await successfulSave(f);
    assert.equal(await fsp.readFile(externalPath, "utf8"), external);
    assert.deepEqual(await temps(f), [basename(externalPath)]);
  });
});

test("an externally replaced temporary file is preserved and cleanup is explicitly incomplete", { concurrency: false }, async () => {
  await fixture(async f => {
    const external = "replacement owned by another writer\n";
    let replacedPath, heldOriginal;
    try {
      await patchedFs(original => ({ open: async (path, ...args) => {
        const handle = await original.open(path, ...args);
        if (!isTemp(f, path) || args[0] !== "wx" || replacedPath) return handle;
        return wrap(handle, "sync", async target => {
          replacedPath = String(path);
          // Hold the old inode to prevent identifier recycling while replacing its directory entry.
          heldOriginal = await original.open(path, "r");
          await original.unlink(path);
          const other = await original.open(path, "wx", 0o600);
          try { await other.writeFile(external, "utf8"); } finally { await other.close(); }
          throw ioError();
        });
      } }), async () => { await assert.rejects(run(f), { code: "alerts_temp_cleanup_incomplete" }); });
      assert.ok(replacedPath);
      await priorStateAndNoLock(f);
      assert.equal(await fsp.readFile(replacedPath, "utf8"), external);
      assert.deepEqual(await temps(f), [basename(replacedPath)]);
    } finally { await heldOriginal?.close(); }
  });
});

test("cleanup unlink failure is visible, preserves the previous state and still releases the lock", { concurrency: false }, async () => {
  await fixture(async f => {
    let wrotePartial = false, cleanupDenied = false;
    await patchedFs(original => ({
      open: async (path, ...args) => {
        const handle = await original.open(path, ...args);
        if (!isTemp(f, path) || args[0] !== "wx") return handle;
        return wrap(handle, "writeFile", async (target, content) => {
          await target.writeFile(content.slice(0, 40), "utf8"); wrotePartial = true; throw ioError();
        });
      },
      unlink: async path => {
        if (isTemp(f, path)) { cleanupDenied = true; throw Object.assign(new Error("synthetic cleanup refusal"), { code: "EPERM" }); }
        return original.unlink(path);
      },
    }), async () => { await assert.rejects(run(f), { code: "alerts_temp_cleanup_incomplete" }); });
    assert.equal(wrotePartial, true); assert.equal(cleanupDenied, true);
    await priorStateAndNoLock(f); assert.equal((await temps(f)).length, 1);
    await successfulSave(f);
    assert.equal((await temps(f)).length, 1, "a fresh run does not delete an unidentified old temporary file");
  });
});

test("successful alert persistence leaves no temporary file and suppresses repeat mock delivery", { concurrency: false }, async () => {
  await fixture(async f => {
    await successfulSave(f); assert.deepEqual(await temps(f), []);
    const repeated = await run(f);
    assert.equal(repeated.mock_messages.length, 0);
    assert.equal(repeated.receipt.suppressed.length, 2);
    assert.deepEqual(await temps(f), []);
    await assert.rejects(fsp.lstat(f.state + ".lock"), { code: "ENOENT" });
  });
});

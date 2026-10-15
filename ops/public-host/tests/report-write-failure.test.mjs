import test from "node:test";
import assert from "node:assert/strict";
import fs from "node:fs";
import fsp from "node:fs/promises";
import { syncBuiltinESMExports } from "node:module";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { runReport } from "../report-cli.mjs";

const NOW = Date.parse("2026-10-15T06:00:00Z");
const BASE = "game_123_2026-10-12_report";
const rawInput = JSON.stringify({
  schema: "pitcheezy-game-report-input-v1", game_pk: 123, evidence: "synthetic",
  window: { from: "2026-10-12T00:00:00Z", to: "2026-10-12T23:59:59Z" },
  collection: { telemetry_enabled: false, feedback_enabled: false, consent_note: "synthetic", retain_days: 30 },
  usage_summary: null, monitor_state: null, notice_audit: null, alert_state: null, actions: [],
  sources: { host_commit: "a".repeat(40), frontend_commit: null, contract_version: "public-file-v1-draft-v0", release_manifest_sha256: null },
  commands: [], unmeasured: [], notes: "synthetic write failure regression",
});
const ioFailure = () => Object.assign(new Error("synthetic write failure"), { code: "EIO" });

async function fixture(work) {
  const dir = await fsp.mkdtemp(join(tmpdir(), "pitcheezy-report-write-test-"));
  const input = join(dir, "input.json"), md = join(dir, BASE + ".md"), json = join(dir, BASE + ".json");
  const lock = join(dir, "." + BASE + ".lock");
  await fsp.writeFile(input, rawInput, { flag: "wx" });
  try { await work({ dir, input, md, json, lock }); }
  finally {
    assert.equal(await fsp.readFile(input, "utf8"), rawInput, "source input must remain unchanged");
    // Remove only regular files in this exact newly-created directory; no recursive cleanup.
    for (const entry of await fsp.readdir(dir, { withFileTypes: true })) {
      assert.equal(entry.isFile(), true, "unexpected cleanup target");
      await fsp.unlink(join(dir, entry.name));
    }
    await fsp.rmdir(dir);
  }
}
async function patchedOpen(make, work) {
  const original = fs.promises.open;
  fs.promises.open = make(original);
  syncBuiltinESMExports();
  try { return await work(); }
  finally { fs.promises.open = original; syncBuiltinESMExports(); }
}
async function absent(path) {
  await assert.rejects(fsp.lstat(path), { code: "ENOENT" });
}
async function completeRetry(f) {
  const result = await runReport(f.input, f.dir, { now: NOW });
  assert.equal(result.schema, "pitcheezy-game-report-run-v1");
  assert.equal(result.markdown, BASE + ".md");
  assert.equal(result.json, BASE + ".json");
  assert.equal(result.posted, false);
  assert.equal(result.approval_required, true);
  assert.equal(result.evidence, "synthetic");
  assert.match(await fsp.readFile(f.md, "utf8"), /##/);
  assert.equal(JSON.parse(await fsp.readFile(f.json, "utf8")).game_pk, 123);
  await absent(f.lock);
}

for (const extension of ["md", "json"]) {
  for (const operation of ["open", "writeFile", "sync"]) {
    test(`report ${extension} ${operation} failure removes owned partial files and permits retry`, { concurrency: false }, async () => {
      await fixture(async f => {
        let injected = false;
        await patchedOpen(original => async (path, ...args) => {
          if (String(path) !== f[extension] || args[0] !== "wx" || injected) return original(path, ...args);
          injected = true;
          if (operation === "open") throw ioFailure();
          const handle = await original(path, ...args);
          return new Proxy(handle, { get(target, property) {
            if (property === operation) return async (...methodArgs) => {
              if (operation === "writeFile") await target.writeFile(methodArgs[0].slice(0, 17), "utf8");
              throw ioFailure();
            };
            const value = Reflect.get(target, property, target);
            return typeof value === "function" ? value.bind(target) : value;
          } });
        }, async () => {
          await assert.rejects(runReport(f.input, f.dir, { now: NOW }), { code: "EIO" });
        });
        assert.equal(injected, true, "fault injection must hit the intended file operation");
        await absent(f.md); await absent(f.json); await absent(f.lock);
        await completeRetry(f);
      });
    });
  }
}

test("external JSON created after preflight is preserved and our Markdown is rolled back", { concurrency: false }, async () => {
  await fixture(async f => {
    const external = "outside writer owns this JSON\n";
    let injected = false;
    await patchedOpen(original => async (path, ...args) => {
      if (String(path) === f.json && args[0] === "wx" && !injected) {
        injected = true;
        const other = await original(path, "wx", 0o600);
        try { await other.writeFile(external, "utf8"); } finally { await other.close(); }
      }
      return original(path, ...args);
    }, async () => {
      await assert.rejects(runReport(f.input, f.dir, { now: NOW }), { code: "EEXIST" });
    });
    assert.equal(injected, true);
    assert.equal(await fsp.readFile(f.json, "utf8"), external);
    await absent(f.md); await absent(f.lock);
  });
});

test("an existing pair lock is refused before creating outputs and is never replaced", { concurrency: false }, async () => {
  await fixture(async f => {
    const external = "existing operator lock\n";
    await fsp.writeFile(f.lock, external, { flag: "wx" });
    await assert.rejects(runReport(f.input, f.dir, { now: NOW }), { code: "already_running_or_stale_lock" });
    await absent(f.md); await absent(f.json);
    assert.equal(await fsp.readFile(f.lock, "utf8"), external);
  });
});

test("two cooperative report writers cannot create a mixed output pair", { concurrency: false }, async () => {
  await fixture(async f => {
    let count = 0, release;
    const blocked = new Promise(resolve => { release = resolve; });
    let outcomes;
    await patchedOpen(original => async (path, ...args) => {
      if (String(path) !== f.lock || args[0] !== "wx") return original(path, ...args);
      count++;
      if (count === 1) {
        const file = await original(path, ...args);
        // Hold the first acquired lock until the second writer reaches acquisition.
        await blocked;
        return file;
      }
      try { return await original(path, ...args); } finally { release(); }
    }, async () => {
      // Bound a failed/missing lock implementation so the regression cannot hang the suite.
      const timeout = setTimeout(release, 3000);
      try {
        outcomes = await Promise.allSettled([
          runReport(f.input, f.dir, { now: NOW }), runReport(f.input, f.dir, { now: NOW }),
        ]);
      } finally { clearTimeout(timeout); release(); }
    });
    assert.equal(count, 2);
    assert.equal(outcomes.filter(x => x.status === "fulfilled").length, 1);
    assert.equal(outcomes.find(x => x.status === "rejected").reason.code, "already_running_or_stale_lock");
    assert.match(await fsp.readFile(f.md, "utf8"), /##/);
    assert.equal(JSON.parse(await fsp.readFile(f.json, "utf8")).game_pk, 123);
    await absent(f.lock);
  });
});

test("rollback preserves an externally replaced file and reports incomplete cleanup", { concurrency: false }, async () => {
  await fixture(async f => {
    const external = "replacement evidence belongs to another writer\n";
    let injected = false, heldOriginal;
    try {
      await patchedOpen(original => async (path, ...args) => {
        if (String(path) === f.json && args[0] === "wx" && !injected) {
          injected = true;
          // Keep the old inode alive to avoid an OS recycling it for the replacement.
          heldOriginal = await original(f.md, "r");
          await fsp.unlink(f.md);
          const other = await original(f.md, "wx", 0o600);
          try { await other.writeFile(external, "utf8"); } finally { await other.close(); }
          throw ioFailure();
        }
        return original(path, ...args);
      }, async () => {
        await assert.rejects(runReport(f.input, f.dir, { now: NOW }), { code: "report_rollback_incomplete" });
      });
      assert.equal(injected, true);
      assert.equal(await fsp.readFile(f.md, "utf8"), external);
      await absent(f.json);
    } finally { await heldOriginal?.close(); }
  });
});

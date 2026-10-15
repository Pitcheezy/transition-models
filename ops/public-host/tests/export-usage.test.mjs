import test from "node:test";
import assert from "node:assert/strict";
import { DatabaseSync } from "node:sqlite";
import { mkdtemp, readFile, writeFile, readdir, rm, symlink } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { fileURLToPath } from "node:url";
import { createHash } from "node:crypto";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { Miniflare } from "miniflare";
import { exportUsage } from "../export-usage.mjs";
import { runExport } from "../export-usage-cli.mjs";
import { summarizeTelemetry } from "../telemetry.mjs";
import { buildReport } from "../report.mjs";

const run = promisify(execFile), NOW = Date.parse("2026-10-13T06:00:00Z"), DAY = 86400000;
const CREATED = Date.parse("2026-10-12T00:00:00Z");
const migration = await readFile(new URL("../migrations/0001_telemetry.sql", import.meta.url), "utf8");
const hash = bytes => createHash("sha256").update(bytes).digest("hex");
const session = (id, game = 123, active = 60000, created = CREATED, expires = CREATED + 30 * DAY) =>
  [id, game, new Date(created).toISOString().slice(0, 10), 1, active, created, created + 120000, expires];
const feedback = (id, game = 123, expires = CREATED + 30 * DAY, created = CREATED) => [id, game, new Date(created).toISOString().slice(0, 10), "helpful", "none", created, expires];
const sessions = [session("private-session-1"), session("private-session-2", 123, 30000),
  session("private-session-other", 456), session("private-session-prior", 123, 60000, CREATED - DAY),
  session("private-session-expired", 123, 60000, NOW - DAY, NOW)];
const feedbacks = [feedback("private-feedback-1"), feedback("private-feedback-2"), feedback("private-feedback-other", 456),
  feedback("private-feedback-expired", 123, NOW, NOW - DAY)];
async function fixture(t, { empty = false, sql = "" } = {}) {
  const dir = await mkdtemp(join(tmpdir(), "pitcheezy-usage-test-")), path = join(dir, "snapshot.sqlite");
  t.after(() => rm(dir, { recursive: true, force: true }));
  const db = new DatabaseSync(path);
  try {
    db.exec(migration);
    if (!empty) {
      for (const r of sessions) db.prepare("INSERT INTO usage_sessions VALUES(?,?,?,?,?,?,?,?)").run(...r);
      for (const r of feedbacks) db.prepare("INSERT INTO feedback VALUES(?,?,?,?,?,?,?)").run(...r);
    }
    if (sql) db.exec(sql);
  } finally { db.close(); }
  return { dir, path };
}
const read = path => exportUsage(path, "2026-10-12", "2026-10-12", { now: NOW });
const reportInput = summary => ({ schema: "pitcheezy-game-report-input-v1", game_pk: 123, evidence: "synthetic",
  window: { from: "2026-10-12T08:00:00Z", to: "2026-10-12T10:00:00Z" },
  collection: { telemetry_enabled: true, feedback_enabled: true, consent_note: "synthetic", retain_days: 30 },
  usage_summary: summary, monitor_state: null, notice_audit: null, alert_state: null, actions: [],
  sources: { host_commit: "a".repeat(40), frontend_commit: null, contract_version: null, release_manifest_sha256: null },
  commands: [], unmeasured: [], notes: "" });

test("SQLite snapshot equals real local D1 aggregation and leaves source bytes/directory untouched", async t => {
  const { dir, path } = await fixture(t), before = await readFile(path), names = await readdir(dir);
  const result = await read(path);
  const mf = new Miniflare({ modules: true, script: "export default {fetch(){return new Response('test')}}",
    compatibilityDate: "2026-07-30", d1Databases: ["DB"] });
  t.after(() => mf.dispose());
  await mf.ready;
  const db = await mf.getD1Database("DB");
  await db.batch(migration.split(";").map(s => s.trim()).filter(Boolean).map(s => db.prepare(s)));
  await db.batch([...sessions.map(r => db.prepare("INSERT INTO usage_sessions VALUES(?,?,?,?,?,?,?,?)").bind(...r)),
    ...feedbacks.map(r => db.prepare("INSERT INTO feedback VALUES(?,?,?,?,?,?,?)").bind(...r))]);
  const expected = await summarizeTelemetry(db, "2026-10-12", "2026-10-12", NOW);
  assert.deepEqual(JSON.parse(JSON.stringify(result.usage_summary)), expected);
  assert.equal(result.usage_summary.sessions[0].sessions, 2); assert.equal(result.usage_summary.sessions[0].active_ms, 90000);
  assert.equal(result.usage_summary.feedback[0].responses, 2);
  assert.equal(result.source_sha256, hash(before));
  assert.deepEqual(await readFile(path), before); assert.deepEqual(await readdir(dir), names);
  assert.doesNotMatch(JSON.stringify(result), /private-session|private-feedback|session_id|feedback_id|snapshot\.sqlite/);
});

test("export has an explicit incomplete-coverage envelope; legacy report cannot mistake it for complete totals", async t => {
  const { dir, path } = await fixture(t), output = join(dir, "summary.json");
  const receipt = await runExport(path, output, "2026-10-12", "2026-10-12", { now: NOW });
  const bytes = await readFile(output), result = JSON.parse(bytes);
  assert.equal(receipt.output_sha256, hash(bytes)); assert.equal(receipt.coverage, "unverified");
  assert.equal(result.schema, "pitcheezy-usage-snapshot-v1");
  assert.equal(result.aggregation, "utc_day");
  assert.equal(result.usage_summary.sessions[0].sessions, 2);
  assert.throws(() => buildReport(reportInput(result)), /invalid_usage_summary/);
});

test("empty and fully expired snapshots retain unknown coverage and cannot become zero viewers in legacy report", async t => {
  for (const options of [{ empty: true }, { now: CREATED + 31 * DAY }]) {
    const { path } = await fixture(t, options), result = await exportUsage(path, "2026-10-12", "2026-10-12", { now: options.now ?? NOW });
    assert.deepEqual(result.usage_summary.sessions, []); assert.deepEqual(result.usage_summary.feedback, []);
    assert.equal(result.coverage, "unverified");
    assert.throws(() => buildReport(reportInput(result)), /invalid_usage_summary/);
  }
});

test("UTC boundaries and expiry cutoff are identical to collection semantics", async t => {
  const { path } = await fixture(t);
  const before = await exportUsage(path, "2026-10-11", "2026-10-11", { now: NOW });
  assert.equal(before.usage_summary.sessions[0].sessions, 1); assert.deepEqual(before.usage_summary.feedback, []);
  const early = await exportUsage(path, "2026-10-12", "2026-10-12", { now: NOW - 1 });
  assert.equal(early.usage_summary.sessions[0].sessions, 3); assert.equal((await read(path)).usage_summary.sessions[0].sessions, 2);
});

test("missing, invalid format, wrong schema and views are refused without creating a source", async t => {
  const { path, dir } = await fixture(t, { empty: true });
  await assert.rejects(read(join(dir, "missing.sqlite")), /snapshot_missing/);
  await writeFile(join(dir, "text.sqlite"), "sensitive text ".repeat(20));
  await assert.rejects(read(join(dir, "text.sqlite")), /snapshot_not_standalone_sqlite/);
  for (const sql of ["DROP TABLE feedback", "ALTER TABLE feedback ADD COLUMN extra TEXT",
    "DROP TABLE feedback; CREATE VIEW feedback AS SELECT 1 AS game_pk",
    "ALTER TABLE usage_sessions ADD COLUMN extra TEXT GENERATED ALWAYS AS ('x') VIRTUAL",
    "DROP TABLE usage_sessions; CREATE TABLE usage_sessions(session_id TEXT,game_pk INTEGER NOT NULL,utc_day TEXT NOT NULL,sequence INTEGER NOT NULL,active_ms INTEGER NOT NULL,created_ms INTEGER NOT NULL,updated_ms INTEGER NOT NULL,expires_ms INTEGER NOT NULL,PRIMARY KEY(session_id,sequence))"]) {
    const f = await fixture(t, { empty: true, sql });
    await assert.rejects(read(f.path), /snapshot_schema_mismatch/);
  }
  assert.equal((await readdir(dir)).includes("missing.sqlite"), false);
  assert.deepEqual((await read(path)).usage_summary.sessions, []);
});

test("malformed and unsafe rows are refused even outside requested dates or already expired", async t => {
  for (const sql of [
    "UPDATE usage_sessions SET session_id=NULL", "UPDATE feedback SET feedback_id=NULL",
    "UPDATE usage_sessions SET active_ms=-1", "UPDATE usage_sessions SET active_ms=1.5",
    "UPDATE usage_sessions SET game_pk='secret-value'", "UPDATE usage_sessions SET utc_day='2026-02-31'",
    "UPDATE usage_sessions SET utc_day='2026-10-11'", "UPDATE usage_sessions SET sequence=0",
    "UPDATE usage_sessions SET created_ms=9007199254740993", "UPDATE usage_sessions SET updated_ms=created_ms-1",
    `UPDATE usage_sessions SET expires_ms=created_ms+${91 * DAY}`,
    `UPDATE feedback SET expires_ms=created_ms+${DAY + 1}`,
    "UPDATE feedback SET reason='private free text'", "UPDATE feedback SET expires_ms=created_ms",
    "UPDATE usage_sessions SET active_ms=-1 WHERE session_id='private-session-expired'",
    "UPDATE usage_sessions SET active_ms=-1 WHERE session_id='private-session-prior'",
  ]) {
    const { path } = await fixture(t, { sql });
    await assert.rejects(read(path), /snapshot_invalid_row|snapshot_unreadable_or_invalid/, sql);
  }
});

test("journal sidecars and WAL header are refused, with no checkpoint or mutation", async t => {
  for (const suffix of ["-wal", "-shm", "-journal"]) {
    const { path } = await fixture(t);
    await writeFile(path + suffix, "private sidecar"); const before = await readFile(path);
    await assert.rejects(read(path), /snapshot_has_sidecar/); assert.deepEqual(await readFile(path), before);
    assert.equal(await readFile(path + suffix, "utf8"), "private sidecar");
  }
  const { path } = await fixture(t, { sql: "PRAGMA journal_mode=WAL" }), before = await readFile(path);
  await assert.rejects(read(path), /snapshot_not_standalone_sqlite/); assert.deepEqual(await readFile(path), before);
});

test("range validation rejects bad dates, reversed dates and oversized ranges", async t => {
  const { path } = await fixture(t);
  for (const [from, to] of [["2026-02-31", "2026-03-01"], ["2026-10-13", "2026-10-12"],
    ["2026-01-01", "2026-10-12"], ["not-a-day", "2026-10-12"]]) {
    await assert.rejects(exportUsage(path, from, to, { now: NOW }), /invalid_report_range/);
  }
});

test("output refuses overwrites, source names and SQLite sidecar destinations", async t => {
  const { path, dir } = await fixture(t), output = join(dir, "existing.json");
  await writeFile(output, "keep"); const before = await readFile(path);
  await assert.rejects(runExport(path, output, "2026-10-12", "2026-10-12", { now: NOW }), /output_exists/);
  for (const dest of [path, ...["-wal", "-shm", "-journal"].map(s => path + s)]) {
    await assert.rejects(runExport(path, dest, "2026-10-12", "2026-10-12", { now: NOW }), /output_conflicts_with_source/);
  }
  await assert.rejects(runExport(path, path.toUpperCase() + "-WAL", "2026-10-12", "2026-10-12", { now: NOW }), /output_conflicts_with_source/);
  assert.equal(await readFile(output, "utf8"), "keep"); assert.deepEqual(await readFile(path), before);
});

test("symlinked snapshot is rejected when OS permits creating symlinks", async t => {
  const { path, dir } = await fixture(t), link = join(dir, "link.sqlite");
  try { await symlink(path, link); } catch (e) { if (["EPERM", "EACCES"].includes(e.code)) { t.skip("OS denies test symlink creation"); return; } throw e; }
  await assert.rejects(read(link), /linked_path/);
});

test("CLI emits safe receipt, rejects past-clock override and hides raw SQLite errors and paths", async t => {
  const { path, dir } = await fixture(t, { empty: true }), output = join(dir, "cli.json");
  const cli = fileURLToPath(new URL("../export-usage-cli.mjs", import.meta.url));
  const args = [cli, "--snapshot", path, "--output", output, "--from-day", "2026-10-12", "--to-day", "2026-10-12"];
  const good = await run(process.execPath, args);
  assert.equal(JSON.parse(good.stdout).ok, true); assert.equal(JSON.parse(await readFile(output)).coverage, "unverified");
  for (const a of [[...args, "--as-of", "2026-10-12"], [cli, "--snapshot", join(dir, "secret.sqlite"), "--output", join(dir, "new.json"), "--from-day", "2026-10-12", "--to-day", "2026-10-12"]]) {
    await assert.rejects(run(process.execPath, a), e => {
      assert.equal(e.code, 2); assert.doesNotMatch(e.stderr, /secret\.sqlite|pitcheezy-usage-test-/); return true;
    });
  }
});

/** Synthetic SQLite recovery rehearsal. No external database or remote restore input. */
import { createHash, randomUUID } from "node:crypto";
import { constants } from "node:fs";
import { copyFile, mkdtemp, readFile, writeFile } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { cleanupTelemetry, validateMeasurement } from "./telemetry.mjs";
import { removeOwnedSandbox } from "./rehearse-lifecycle.mjs";

const DAY = 86400000;
const NOW = Date.parse("2026-10-15T12:00:00Z"); // Fixed synthetic clock, never a live incident.
const TODAY = "2026-10-15";
const tables = ["usage_sessions", "feedback", "telemetry_budget"];
const sha = bytes => createHash("sha256").update(bytes).digest("hex");
const need = (value, code) => { if (!value) throw new Error(code); };
const integer = (v, lo = 0, hi = Number.MAX_SAFE_INTEGER) => Number.isSafeInteger(v) && v >= lo && v <= hi;
const validDay = v => typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v) &&
  Number.isFinite(Date.parse(v)) && new Date(v).toISOString().slice(0, 10) === v;

function schemaOf(db) {
  // Compare the fixture to the repository migration, including key/index definitions and extra objects.
  return JSON.stringify({
    objects: db.prepare("SELECT type,name,tbl_name,sql FROM sqlite_schema WHERE name NOT LIKE 'sqlite_%' ORDER BY type,name").all(),
    columns: tables.map(name => db.prepare(`PRAGMA table_xinfo(${name})`).all()),
  });
}
function inspect(db, expectedSchema, floor) {
  const result = { structure: "invalid", integrity: "not_checked", expired: null, retained: null,
    budget: { state: "not_checked", observed: null, floor: null }, findings: [],
    collection_resume_authorized: false };
  db.exec("PRAGMA query_only=ON; PRAGMA trusted_schema=OFF; BEGIN");
  try {
    if (schemaOf(db) !== expectedSchema) { result.findings.push("schema_mismatch"); return result; }
    result.structure = "ok";
    if (db.prepare("PRAGMA quick_check").get().quick_check !== "ok") {
      result.integrity = "invalid"; result.findings.push("database_integrity"); return result;
    }
    const common = r => validDay(r.utc_day) && integer(r.created_ms, 0, 8640000000000000) &&
      integer(r.expires_ms, 0, 8640000000000000) &&
      integer(r.expires_ms - r.created_ms, DAY, 90 * DAY) && (r.expires_ms - r.created_ms) % DAY === 0 &&
      new Date(r.created_ms).toISOString().slice(0, 10) === r.utc_day;
    try {
      for (const r of db.prepare("SELECT * FROM usage_sessions").iterate()) {
        validateMeasurement({ v: 1, consent: true, session_id: r.session_id, game_pk: r.game_pk,
          sequence: r.sequence, active_ms: r.active_ms }, "session");
        need(common(r) && integer(r.updated_ms, r.created_ms, r.expires_ms - 1) &&
          new Date(r.updated_ms).toISOString().slice(0, 10) === r.utc_day &&
          r.active_ms <= r.updated_ms - r.created_ms + 1000, "invalid_session_row");
      }
      for (const r of db.prepare("SELECT * FROM feedback").iterate()) {
        validateMeasurement({ v: 1, consent: true, feedback_id: r.feedback_id, game_pk: r.game_pk,
          rating: r.rating, reason: r.reason }, "feedback");
        need(common(r), "invalid_feedback_row");
      }
      for (const r of db.prepare("SELECT utc_day,kind,used FROM telemetry_budget").iterate()) {
        need(validDay(r.utc_day) && ["session", "feedback"].includes(r.kind) && integer(r.used), "invalid_budget_row");
      }
    } catch {
      result.integrity = "invalid"; result.findings.push("invalid_row"); return result;
    }
    result.integrity = "ok";
    const count = (table, comparison) => db.prepare(`SELECT COUNT(*) AS n FROM ${table} WHERE expires_ms${comparison}?`).get(NOW).n;
    result.expired = { sessions: count("usage_sessions", "<="), feedback: count("feedback", "<=") };
    result.retained = { sessions: count("usage_sessions", ">"), feedback: count("feedback", ">") };
    if (result.expired.sessions + result.expired.feedback > 0) result.findings.push("expired_rows_returned");
    const observed = { session: 0, feedback: 0 };
    for (const r of db.prepare("SELECT kind,used FROM telemetry_budget WHERE utc_day=?").all(TODAY)) observed[r.kind] = r.used;
    if (floor === null) {
      result.budget = { state: "missing_evidence", observed, floor: null };
      result.findings.push("budget_evidence_missing");
    } else {
      const rewound = observed.session < floor.session || observed.feedback < floor.feedback;
      result.budget = { state: rewound ? "rewound" : "not_below_evidence", observed, floor: { ...floor } };
      if (rewound) result.findings.push("budget_rewound");
    }
    return result;
  } finally { db.exec("COMMIT"); }
}
function sqliteAdapter(db) {
  return {
    prepare(sql) { return { bind: (...args) => ({ sql, args }) }; },
    async batch(statements) {
      db.exec("BEGIN");
      try { const result = statements.map(s => db.prepare(s.sql).run(...s.args)); db.exec("COMMIT"); return result; }
      catch (e) { db.exec("ROLLBACK"); throw e; }
    },
  };
}
function seed(db, includeExpiring) {
  const session = db.prepare("INSERT INTO usage_sessions VALUES(?,?,?,?,?,?,?,?)");
  const feedback = db.prepare("INSERT INTO feedback VALUES(?,?,?,?,?,?,?)");
  const add = (created, ttl) => {
    const day = new Date(created).toISOString().slice(0, 10);
    session.run(randomUUID(), 123, day, 1, 30000, created, created + 30000, created + ttl);
    feedback.run(randomUUID(), 123, day, "helpful", "none", created, created + ttl);
  };
  add(NOW - 3 * 3600000, 30 * DAY);
  if (includeExpiring) add(NOW - DAY - 3600000, DAY);
  db.exec("INSERT INTO telemetry_budget VALUES('2026-10-15','session',2),('2026-10-15','feedback',1),('2026-10-14','session',1)");
}
async function hashes() {
  const result = {};
  for (const name of ["rehearse-d1-recovery.mjs", "rehearse-lifecycle.mjs", "telemetry.mjs", "migrations/0001_telemetry.sql"])
    result[name] = sha(await readFile(new URL(name, import.meta.url)));
  return result;
}

/** Create, restore and inspect only disposable synthetic fixtures; never accepts a database path. */
export async function runD1RecoveryRehearsal() {
  const { DatabaseSync } = await import("node:sqlite");
  const report = { schema: "pitcheezy-local-d1-recovery-v1", synthetic: true, passed: false,
    target: "new-local-sqlite-fixtures", synthetic_clock: new Date(NOW).toISOString(),
    collection_resume_authorized: false, cloud_restore_verified: false, crash_recovery_verified: false,
    rto_ms: null, rpo_records: null, original_unchanged: false, normal_duplicate_insert_rejected: false,
    temporary_storage: "not_created", environment: { node: process.version, platform: process.platform, arch: process.arch },
    source_sha256: await hashes(), cases: [] };
  let directory, phase = "create";
  try {
    directory = await mkdtemp(join(tmpdir(), "pitcheezy-lifecycle-d1-recovery-"));
    report.temporary_storage = "created";
    const migration = await readFile(new URL("migrations/0001_telemetry.sql", import.meta.url), "utf8");
    const normal = join(directory, "normal.sqlite"), live = join(directory, "live.sqlite"), backup = join(directory, "backup.sqlite");
    let expectedSchema;
    for (const [path, expiring] of [[normal, false], [live, true]]) {
      const db = new DatabaseSync(path, { allowExtension: false });
      try {
        db.exec(migration); expectedSchema = schemaOf(db); seed(db, expiring);
        if (!expiring) {
          try { db.exec("INSERT INTO usage_sessions SELECT * FROM usage_sessions LIMIT 1"); }
          catch (e) { report.normal_duplicate_insert_rejected = e.errcode === 1555; }
          need(report.normal_duplicate_insert_rejected, "duplicate_not_rejected");
        }
      } finally { db.close(); }
    }
    // Backup is a closed rollback-journal DB; subsequent live changes do not modify it.
    await copyFile(live, backup, constants.COPYFILE_EXCL);
    const backupHash = sha(await readFile(backup));
    need(backupHash === sha(await readFile(live)), "backup_copy_mismatch");
    const liveDb = new DatabaseSync(live, { allowExtension: false });
    let incidentFloor;
    try {
      liveDb.exec("UPDATE telemetry_budget SET used=CASE kind WHEN 'session' THEN 5 ELSE 3 END WHERE utc_day='2026-10-15'");
      await cleanupTelemetry({ TELEMETRY_DB: sqliteAdapter(liveDb), TELEMETRY_ENABLED: "false", FEEDBACK_ENABLED: "false" }, NOW);
      incidentFloor = Object.fromEntries(liveDb.prepare("SELECT kind,used FROM telemetry_budget WHERE utc_day=?").all(TODAY).map(r => [r.kind, r.used]));
    } finally { liveDb.close(); }
    const liveHash = sha(await readFile(live));
    const examine = async (name, path, floor) => {
      phase = name;
      const before = sha(await readFile(path));
      const db = new DatabaseSync(path, { readOnly: true, allowExtension: false });
      let readOnly = false, inspection;
      try {
        try { db.exec("CREATE TABLE recovery_write_probe(value INTEGER)"); }
        catch (e) { readOnly = e.errcode === 8; }
        need(readOnly, "read_only_not_enforced");
        inspection = inspect(db, expectedSchema, floor);
      } finally { db.close(); }
      const unchanged = before === sha(await readFile(path));
      need(unchanged, "inspection_changed_source");
      report.cases.push({ name, inspection, source_unchanged: unchanged, read_only_enforced: readOnly });
      return inspection;
    };
    const normalResult = await examine("normal", normal, { session: 2, feedback: 1 });
    need(normalResult.findings.length === 0, "normal_failed");
    for (const name of ["restored_older", "cleaned_copy", "missing_budget_evidence", "missing_index", "wrong_index", "schema_mismatch", "null_identity", "duplicate_identity", "invalid_budget"]) {
      const path = join(directory, name + ".sqlite");
      await copyFile(backup, path, constants.COPYFILE_EXCL);
      need(sha(await readFile(path)) === backupHash, "restored_copy_mismatch");
      if (!["restored_older", "missing_budget_evidence"].includes(name)) {
        const db = new DatabaseSync(path, { allowExtension: false });
        try {
          if (name === "cleaned_copy") await cleanupTelemetry({ TELEMETRY_DB: sqliteAdapter(db), TELEMETRY_ENABLED: "false", FEEDBACK_ENABLED: "false" }, NOW);
          if (name === "missing_index") db.exec("DROP INDEX sessions_expiry");
          if (name === "wrong_index") db.exec("DROP INDEX sessions_expiry; CREATE INDEX sessions_expiry ON usage_sessions(created_ms)");
          if (name === "schema_mismatch") db.exec("ALTER TABLE telemetry_budget ADD COLUMN unexpected TEXT");
          if (name === "null_identity") db.exec("INSERT INTO usage_sessions SELECT NULL,game_pk,utc_day,sequence,active_ms,created_ms,updated_ms,expires_ms FROM usage_sessions");
          if (name === "duplicate_identity") db.exec("CREATE TABLE duplicate_copy AS SELECT * FROM usage_sessions; INSERT INTO duplicate_copy SELECT * FROM usage_sessions; DROP TABLE usage_sessions; ALTER TABLE duplicate_copy RENAME TO usage_sessions");
          if (name === "invalid_budget") db.exec("UPDATE telemetry_budget SET used=-1 WHERE kind='session'");
        } finally { db.close(); }
      }
      const result = await examine(name, path, name === "missing_budget_evidence" ? null : incidentFloor);
      if (name === "restored_older") need(result.expired.sessions === 1 && result.expired.feedback === 1 && result.budget.state === "rewound", "restore_hazards_not_detected");
      else if (name === "cleaned_copy") need(result.expired.sessions === 0 && result.expired.feedback === 0 && result.budget.state === "rewound", "cleanup_hid_budget_hazard");
      else if (name === "missing_budget_evidence") need(result.budget.state === "missing_evidence", "missing_floor_not_detected");
      else if (["null_identity", "invalid_budget"].includes(name)) need(result.integrity === "invalid", "invalid_row_not_detected");
      else need(result.structure === "invalid", "invalid_schema_not_detected");
    }
    report.original_unchanged = backupHash === sha(await readFile(backup)) && liveHash === sha(await readFile(live));
    need(report.original_unchanged, "original_changed");
    report.passed = true;
  } catch {
    report.failure = { phase, code: "rehearsal_failed" }; // Never echo SQL, paths, IDs or values.
  } finally {
    if (directory) {
      try { await removeOwnedSandbox(directory, tmpdir(), basename(directory)); report.temporary_storage = "removed"; }
      catch { report.temporary_storage = "retained"; report.passed = false; }
    }
  }
  return report;
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  try {
    const { values, positionals } = parseArgs({ options: { output: { type: "string" } }, strict: true, allowPositionals: false });
    need(positionals.length === 0, "unexpected_input");
    const report = await runD1RecoveryRehearsal();
    const text = JSON.stringify(report, null, 2) + "\n";
    if (values.output) await writeFile(values.output, text, { encoding: "utf8", flag: "wx", mode: 0o600 });
    else process.stdout.write(text);
    process.exitCode = report.passed ? 0 : 1;
  } catch {
    process.stderr.write("d1_recovery_rehearsal_failed\n");
    process.exitCode = 2;
  }
}

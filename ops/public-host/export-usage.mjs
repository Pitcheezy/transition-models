/** Private, offline SQLite snapshot aggregation. No remote database access or source writes. */
import { DatabaseSync } from "node:sqlite";
import { open, lstat } from "node:fs/promises";
import { createHash } from "node:crypto";
import { plainPath } from "./monitor-cli.mjs";
import { summarizeTelemetry, MAX_ACTIVE_MS } from "./telemetry.mjs";
import { validateReportInput } from "./report.mjs";

const MAX_BYTES = 512 * 1024 * 1024, MAX_ROWS = 2_000_000, DAY = 86400000;
const integer = (v, min, max) => Number.isSafeInteger(v) && v >= min && v <= max;
const day = v => typeof v === "string" && /^\d{4}-\d{2}-\d{2}$/.test(v) &&
  Number.isFinite(Date.parse(v + "T00:00:00Z")) && new Date(v + "T00:00:00Z").toISOString().slice(0, 10) === v;
export class UsageExportError extends Error { constructor(code) { super(code); this.code = code; } }
const refuse = code => { throw new UsageExportError(code); };
const columns = {
  usage_sessions: { session_id: "TEXT", game_pk: "INTEGER", utc_day: "TEXT", sequence: "INTEGER",
    active_ms: "INTEGER", created_ms: "INTEGER", updated_ms: "INTEGER", expires_ms: "INTEGER" },
  feedback: { feedback_id: "TEXT", game_pk: "INTEGER", utc_day: "TEXT", rating: "TEXT", reason: "TEXT",
    created_ms: "INTEGER", expires_ms: "INTEGER" },
};

async function noSidecars(path) {
  for (const suffix of ["-wal", "-shm", "-journal"]) {
    try { await lstat(path + suffix); } catch (e) { if (e.code === "ENOENT") continue; throw e; }
    refuse("snapshot_has_sidecar");
  }
}
async function fingerprint(path) {
  await plainPath(path);
  await noSidecars(path);
  const file = await open(path, "r");
  try {
    const before = await file.stat();
    if (!before.isFile() || before.size < 100 || before.size > MAX_BYTES) refuse("snapshot_size_or_type");
    const hash = createHash("sha256"), buffer = Buffer.alloc(512 * 1024);
    let total = 0;
    while (true) {
      const { bytesRead } = await file.read(buffer, 0, buffer.length, null);
      if (!bytesRead) break;
      if (total === 0 && (buffer.subarray(0, 16).toString("binary") !== "SQLite format 3\0" ||
          buffer[18] !== 1 || buffer[19] !== 1)) refuse("snapshot_not_standalone_sqlite");
      total += bytesRead;
      if (total > MAX_BYTES) refuse("snapshot_size_or_type");
      hash.update(buffer.subarray(0, bytesRead));
    }
    const after = await file.stat();
    if (total !== before.size || before.size !== after.size || before.mtimeMs !== after.mtimeMs ||
        before.ctimeMs !== after.ctimeMs) refuse("snapshot_changed");
    return { sha256: hash.digest("hex"), size: before.size, dev: before.dev, ino: before.ino,
      mtime: before.mtimeMs, ctime: before.ctimeMs };
  } finally { await file.close(); }
}
function validateTables(db) {
  for (const [table, expected] of Object.entries(columns)) {
    const def = db.prepare("SELECT type,sql FROM sqlite_schema WHERE name=?").get(table);
    if (def?.type !== "table" || !/^CREATE TABLE\b/i.test(def.sql || "")) refuse("snapshot_schema_mismatch");
    const info = db.prepare(`PRAGMA table_xinfo(${table})`).all(); // table is a fixed constant above.
    if (info.length !== Object.keys(expected).length ||
        !info.every(r => r.hidden === 0 && Object.hasOwn(expected, r.name) && r.type.toUpperCase() === expected[r.name])) refuse("snapshot_schema_mismatch");
    const id = table === "feedback" ? "feedback_id" : "session_id";
    if (info.filter(r => r.pk > 0).length !== 1 || !info.some(r => r.name === id && r.pk === 1) ||
        !info.every(r => r.name === id || r.notnull === 1)) refuse("snapshot_schema_mismatch");
    // SQLite TEXT PRIMARY KEY can still admit NULL; do not let anonymous/empty IDs inflate counts.
    if (db.prepare(`SELECT EXISTS(SELECT 1 FROM ${table} WHERE ${id} IS NULL OR typeof(${id})!='text' OR length(${id})=0) AS bad`).get().bad) refuse("snapshot_invalid_row");
    const count = db.prepare(`SELECT COUNT(*) AS n FROM ${table}`).get().n;
    if (!integer(count, 0, MAX_ROWS)) refuse("snapshot_too_many_rows");
  }
}
function validateRows(db) {
  // Do not load IDs. Scan even expired/out-of-range rows so malformed data cannot disappear in SQL filters.
  const common = r => integer(r.game_pk, 0, 999999999999) && day(r.utc_day) &&
    integer(r.created_ms, 0, 8640000000000000) && integer(r.expires_ms, 0, 8640000000000000) &&
    integer(r.expires_ms - r.created_ms, DAY, 90 * DAY) && (r.expires_ms - r.created_ms) % DAY === 0 && new Date(r.created_ms).toISOString().slice(0, 10) === r.utc_day;
  for (const r of db.prepare("SELECT game_pk,utc_day,sequence,active_ms,created_ms,updated_ms,expires_ms FROM usage_sessions").iterate()) {
    if (!common(r) || !integer(r.sequence, 0, 10000) || !integer(r.active_ms, 0, MAX_ACTIVE_MS) ||
        !integer(r.updated_ms, r.created_ms, r.expires_ms - 1) ||
        new Date(r.updated_ms).toISOString().slice(0, 10) !== r.utc_day ||
        r.active_ms > r.updated_ms - r.created_ms + 1000 || (r.sequence === 0 && r.active_ms !== 0)) refuse("snapshot_invalid_row");
  }
  for (const r of db.prepare("SELECT game_pk,utc_day,rating,reason,created_ms,expires_ms FROM feedback").iterate()) {
    if (!common(r) || !["helpful", "unclear", "problem"].includes(r.rating) ||
        !["none", "recommendation", "explanation", "delay", "display", "other"].includes(r.reason)) refuse("snapshot_invalid_row");
  }
}

export async function exportUsage(snapshotPath, fromDay, toDay, { now = Date.now() } = {}) {
  if (!day(fromDay) || !day(toDay) || fromDay > toDay || Date.parse(toDay) - Date.parse(fromDay) > 90 * DAY ||
      !integer(now, 0, 8640000000000000)) refuse("invalid_report_range");
  let db;
  try {
    const path = await plainPath(snapshotPath);
    const before = await fingerprint(path);
    db = new DatabaseSync(path, { readOnly: true, allowExtension: false, timeout: 1000 });
    db.exec("PRAGMA query_only=ON; PRAGMA trusted_schema=OFF; BEGIN");
    validateTables(db);
    validateRows(db);
    // summarizeTelemetry owns both SQL statements; one read transaction covers validation and both aggregates.
    const adapter = {
      prepare(sql) { return { bind: (...args) => ({ sql, args }) }; },
      async batch(statements) { return statements.map(s => ({ results: db.prepare(s.sql).all(...s.args) })); },
    };
    const summary = await summarizeTelemetry(adapter, fromDay, toDay, now);
    db.exec("COMMIT");
    db.close(); db = undefined;
    const after = await fingerprint(path);
    if (JSON.stringify(before) !== JSON.stringify(after)) refuse("snapshot_changed");
    // Reuse existing aggregate validation without modifying the report builder. This is validation,
    // not an evidence report; the enclosing snapshot deliberately refuses legacy report consumption.
    validateReportInput({ schema: "pitcheezy-game-report-input-v1", game_pk: 1, evidence: "synthetic",
      window: { from: fromDay + "T00:00:00Z", to: fromDay + "T23:59:59Z" },
      collection: { telemetry_enabled: false, feedback_enabled: false, consent_note: "", retain_days: null },
      usage_summary: summary, monitor_state: null, notice_audit: null, alert_state: null, actions: [],
      sources: { host_commit: "0".repeat(40), frontend_commit: null, contract_version: null, release_manifest_sha256: null },
      commands: [], unmeasured: [], notes: "" });
    const result = { schema: "pitcheezy-usage-snapshot-v1", source_sha256: before.sha256,
      coverage: "unverified", aggregation: "utc_day", usage_summary: summary };
    if (Buffer.byteLength(JSON.stringify(result, null, 2)) > 900_000) refuse("summary_too_large");
    return result;
  } catch (e) {
    if (e instanceof UsageExportError) throw e;
    if (e?.code === "linked_path") refuse("linked_path");
    if (e?.code === "ENOENT") refuse("snapshot_missing");
    if (e?.code === "invalid_usage_summary") refuse("snapshot_invalid_aggregate");
    refuse("snapshot_unreadable_or_invalid"); // Never return SQLite text, source paths or stored values.
  } finally { db?.close(); }
}

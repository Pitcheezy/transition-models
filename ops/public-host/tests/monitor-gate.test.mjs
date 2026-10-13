// WS-monitor2: publish monitoring while the viewer access gate is on. Synthetic codes only; the code and the
// session cookie must never reach a report, state, stdout or stderr.
import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, writeFile, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join } from "node:path";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import { validateConfig, probe, initialState, advanceState, accessLogin, ACCESS_ROUTE } from "../monitor.mjs";
import { classifyEvent, dispatchAlerts, initialAlertState, mockTransport } from "../alerts.mjs";
import { startLocalHost, boundedCleanup } from "../rehearsal/local-host.mjs";

const NOW = Date.parse("2026-10-13T03:00:00Z");
const CODE = "synthetic-monitor-code-0001";
const COOKIE = "__Host-pz_viewer=v2.1.2.abcdef01.0123456789abcdef." + "a".repeat(64);
const config = (extra = {}) => ({
  schema: "pitcheezy-host-monitor-v1", origin: "https://public.example.test", allow_loopback_http: false,
  timeout_ms: 300, max_body_bytes: 4096, timestamp_pointer: "/synthetic/at", timestamp_format: "rfc3339",
  max_age_seconds: 120, clock_skew_seconds: 30, page_sha256: null, access_code_env: "PZ_MONITOR_ACCESS_CODE", ...extra,
});
const html = "<!doctype html><html><title>Synthetic monitor</title></html>";
function fakeHost({ login = { status: 200, cookie: COOKIE }, read = "ok", at = new Date(NOW).toISOString() } = {}) {
  const calls = [];
  const fetchImpl = async (url, init) => {
    const path = new URL(url).pathname;
    calls.push({ path, method: init.method, credentials: init.credentials, redirect: init.redirect, cookie: init.headers?.Cookie ?? null, body: init.body ?? null });
    if (path === ACCESS_ROUTE) {
      if (login === "throw") throw new Error("CODE " + CODE + " leaked?");
      if (login === "hang") return await new Promise(() => {});
      const headers = new Headers({ "Content-Type": "application/json" });
      if (login.cookie) headers.append("Set-Cookie", login.cookie + "; Path=/; Max-Age=3600; HttpOnly; SameSite=Strict; Secure");
      return new Response("{}", { status: login.status, headers });
    }
    if (read === "rejected") return new Response('{"error":"access_required"}', { status: 401, headers: { "X-Pitcheezy-Access": "required", "Content-Type": "application/json" } });
    if (path === "/") return new Response(html, { headers: { "Content-Type": "text/html" } });
    return new Response(JSON.stringify({ synthetic: { at } }), { headers: { "Content-Type": "application/json", Date: new Date(NOW).toUTCString(), Age: "0" } });
  };
  return { calls, fetchImpl };
}
const secretFree = value => { const text = JSON.stringify(value); assert.doesNotMatch(text, new RegExp(CODE)); assert.doesNotMatch(text, /pz_viewer|v2\.1\.2\./); };

test("access_code_env is optional, names an environment variable, and never holds the code itself", () => {
  const { access_code_env: _ignored, ...legacy } = config();
  assert.equal(validateConfig(legacy).access_code_env, undefined, "existing configs stay valid");
  assert.equal(validateConfig(config({ access_code_env: null })).access_code_env, null);
  for (const bad of ["pz_lower", "AB", "1ABC", "PZ-CODE", 7, true, CODE]) {
    assert.throws(() => validateConfig(config({ access_code_env: bad })), /invalid_access_code_env/, String(bad));
  }
});

test("a configured gate login is required before any request; invalid or missing codes stop the probe", async () => {
  for (const [code, expected] of [[null, "access_code_unavailable"], ["", "access_code_unavailable"], ["short", "access_code_invalid"], ["has space 12345", "access_code_invalid"]]) {
    const host = fakeHost();
    await assert.rejects(probe(config(), { fetchImpl: host.fetchImpl, now: () => NOW, accessCode: code }), new RegExp(expected));
    assert.equal(host.calls.length, 0, "no request leaves the process");
  }
});

test("login through the viewer route, then every read carries that session; nothing secret is reported", async () => {
  const host = fakeHost();
  const report = await probe(config(), { fetchImpl: host.fetchImpl, now: () => NOW, accessCode: CODE });
  assert.equal(report.status, "available"); assert.deepEqual(report.issues, []);
  assert.equal(report.access_session, "established"); assert.equal(report.access_gate_active, true);
  const [login, ...reads] = host.calls;
  assert.deepEqual([login.path, login.method, login.credentials, login.redirect, login.body], [ACCESS_ROUTE, "POST", "omit", "manual", JSON.stringify({ code: CODE })]);
  assert.equal(reads.length, 2);
  for (const read of reads) { assert.equal(read.cookie, COOKIE.split(";")[0]); assert.equal(read.method, "GET"); assert.equal(read.body, null); }
  secretFree(report);
});

test("gate off (route hidden) keeps reading without a session; a missing config key keeps the old behaviour", async () => {
  const off = fakeHost({ login: { status: 404 } });
  const report = await probe(config(), { fetchImpl: off.fetchImpl, now: () => NOW, accessCode: CODE });
  assert.equal(report.status, "available"); assert.equal(report.access_session, "gate_off"); assert.equal(report.access_gate_active, false);
  assert.deepEqual(off.calls.slice(1).map(c => c.cookie), [null, null]);
  const { access_code_env: _ignored, ...legacy } = config();
  const plain = fakeHost();
  const r2 = await probe(legacy, { fetchImpl: plain.fetchImpl, now: () => NOW, accessCode: CODE });
  assert.equal(r2.access_session, "not_configured");
  assert.equal(plain.calls.some(c => c.path === ACCESS_ROUTE), false, "a code is never sent unless configured");
});

test("login failures are fixed codes on our side; reads are skipped instead of being reported as page outages", async () => {
  const cases = [
    [{ status: 401 }, "access_login_denied"], [{ status: 429 }, "access_login_rate_limited"], [{ status: 503 }, "access_login_unavailable"],
    [{ status: 500 }, "access_login_http_error"], [{ status: 200 }, "access_login_invalid_cookie"],
    [{ status: 200, cookie: "pz_viewer=wrong-name-for-https" }, "access_login_invalid_cookie"], ["throw", "access_login_network_error"], ["hang", "access_login_timeout"],
  ];
  for (const [login, code] of cases) {
    const host = fakeHost({ login });
    const report = await probe(config(), { fetchImpl: host.fetchImpl, now: () => NOW, accessCode: CODE });
    assert.equal(report.status, "failed", code); assert.deepEqual(report.issues, [code]);
    assert.equal(report.access_session, "login_failed");
    assert.deepEqual([report.page.status, report.health.status], ["skipped", "skipped"]);
    assert.equal(host.calls.length, 1, "no read without a session");
    assert.equal(classifyEvent({ id: "a".repeat(64), kind: "opened", at_ms: NOW, issues: report.issues }), "host_error");
    secretFree(report);
  }
});

test("a session refused right after login is ours to investigate, distinct from a gate seen without a session", async () => {
  const host = fakeHost({ read: "rejected" });
  const report = await probe(config(), { fetchImpl: host.fetchImpl, now: () => NOW, accessCode: CODE });
  assert.deepEqual(report.issues, ["page_access_session_rejected", "health_access_session_rejected"]);
  assert.equal(classifyEvent({ id: "b".repeat(64), kind: "opened", at_ms: NOW, issues: report.issues }), "host_error");
  assert.equal(classifyEvent({ id: "c".repeat(64), kind: "opened", at_ms: NOW, issues: ["page_access_required", "health_access_required"] }), "access_gate");
});

test("a login-route 404 followed by gated reads is ours to investigate, not the info-only gate case", async () => {
  const host = fakeHost({ login: { status: 404 }, read: "rejected" });
  const report = await probe(config(), { fetchImpl: host.fetchImpl, now: () => NOW, accessCode: CODE });
  assert.equal(report.access_session, "gate_off");
  assert.deepEqual(report.issues, ["page_access_gate_without_login", "health_access_gate_without_login"]);
  assert.equal(report.access_gate_active, true, "the reads were refused by the gate");
  assert.equal(classifyEvent({ id: "e".repeat(64), kind: "opened", at_ms: NOW, issues: report.issues }), "host_error");
});

test("access_gate_active is set only when the gate itself answered", async () => {
  const expect = { access_login_denied: true, access_login_rate_limited: true, access_login_invalid_cookie: true,
    access_login_unavailable: false, access_login_http_error: false, access_login_network_error: false, access_login_timeout: false };
  const logins = { access_login_denied: { status: 401 }, access_login_rate_limited: { status: 429 }, access_login_invalid_cookie: { status: 200 },
    access_login_unavailable: { status: 503 }, access_login_http_error: { status: 500 }, access_login_network_error: "throw", access_login_timeout: "hang" };
  for (const [code, login] of Object.entries(logins)) {
    const report = await probe(config(), { fetchImpl: fakeHost({ login }).fetchImpl, now: () => NOW, accessCode: CODE });
    assert.deepEqual(report.issues, [code]);
    assert.equal(report.access_gate_active, expect[code], code);
  }
  const off = await probe(config(), { fetchImpl: fakeHost({ login: { status: 404 } }).fetchImpl, now: () => NOW, accessCode: CODE });
  assert.equal(off.access_gate_active, false);
});

test("accessLogin uses the https cookie name only for https origins", async () => {
  const host = fakeHost({ login: { status: 200, cookie: "pz_viewer=abc" } });
  const loopback = config({ origin: "http://127.0.0.1:9", allow_loopback_http: true });
  assert.deepEqual(await accessLogin(loopback, CODE, host.fetchImpl), { session: "established", cookie: "pz_viewer=abc" });
});

// ---- real local Worker ---------------------------------------------------------------------------
const runtimeConfig = (origin, extra = {}) => config({ origin, allow_loopback_http: true, timeout_ms: 3000, max_body_bytes: 65536, ...extra });
async function publishHealth(host, at, etag = null) {
  const r = await host.publish("/v1/health.json", JSON.stringify({ synthetic: { at } }), etag);
  assert.equal(r.status, 200, await r.clone().text());
  const tag = r.headers.get("ETag"); await r.arrayBuffer(); return tag;
}

test("actual local Worker with the gate on: fresh, stale -> incident -> publish_stalled alert, recovery, wrong code, no code, notice", { timeout: 60000 }, async () => {
  const monitorCode = "synthetic-monitor-only-code-77";
  const host = await startLocalHost({ access: { sessionSeconds: 3600, codes: ["synthetic-viewer-code-0042", monitorCode] } });
  try {
    let etag = await publishHealth(host, new Date().toISOString());
    const cfg = runtimeConfig(host.origin);
    const run = async (c = cfg, code = monitorCode) => probe(c, { accessCode: code });
    const fresh = await run();
    assert.equal(fresh.status, "available", JSON.stringify(fresh.issues)); assert.equal(fresh.access_session, "established");
    secretFree(fresh); assert.doesNotMatch(JSON.stringify(fresh), new RegExp(monitorCode));
    const { access_code_env: _ignored, ...legacy } = cfg;
    const blind = await probe(legacy);
    assert.deepEqual(blind.issues, ["page_access_required", "health_access_required"], "without a code the gate hides freshness");
    const wrong = await run(cfg, "synthetic-not-a-listed-code");
    assert.deepEqual(wrong.issues, ["access_login_denied"]);
    // Publishing stops: the health file ages past max_age_seconds. Two failed probes open one incident.
    etag = await publishHealth(host, new Date(Date.now() - 600000).toISOString(), etag);
    let state = initialState(cfg);
    let event = null;
    for (let i = 0; i < 2; i++) {
      const report = await run();
      assert.deepEqual(report.issues, ["freshness_stale"], "the gated host is still measured");
      ({ state, event } = advanceState(state, report, cfg));
    }
    assert.equal(event.kind, "opened"); assert.deepEqual(event.issues, ["freshness_stale"]);
    const transport = mockTransport();
    const { receipt } = await dispatchAlerts(initialAlertState(), state, { schema: "pitcheezy-host-alerts-v1", transport: "mock",
      recipients: [{ id: "song", label: "Song side" }, { id: "ours", label: "our side" }], max_attempts: 3, remind_after_minutes: 0 }, transport);
    assert.equal(receipt.acknowledged.length, 2);
    assert.deepEqual(transport.sent.map(m => [m.recipient, m.category, m.first_responder]), [["song", "publish_stalled", "song"], ["ours", "publish_stalled", "song"]]);
    etag = await publishHealth(host, new Date().toISOString(), etag);
    for (let i = 0; i < 2; i++) ({ state, event } = advanceState(state, await run(), cfg));
    assert.equal(event.kind, "recovered");
    // An operator notice is still reported as a notice (not an outage) while the monitor holds a session.
    const on = await host.setNotice({ active: true, operator: "ops-a", reason: "synthetic drill", message_id: "maintenance" });
    assert.equal(on.status, 200); const noticeTag = on.headers.get("ETag"); await on.arrayBuffer();
    const notice = await run();
    assert.equal(notice.access_session, "established"); assert.equal(notice.notice_active, true);
    assert.equal(classifyEvent({ id: "d".repeat(64), kind: "opened", at_ms: Date.now(), issues: notice.issues }), "notice_active");
    const off = await host.setNotice({ active: false, operator: "ops-a", reason: "synthetic recovery", message_id: "maintenance" }, noticeTag);
    assert.equal(off.status, 200); await off.arrayBuffer();
  } finally { await boundedCleanup(() => host.dispose()); }
});

function cli(args, env) {
  return new Promise(resolve => {
    const child = spawn(process.execPath, [fileURLToPath(new URL("../monitor-cli.mjs", import.meta.url)), ...args],
      { env: { PATH: process.env.PATH, SystemRoot: process.env.SystemRoot, ...env } });
    let out = "", err = "";
    child.stdout.on("data", d => { out += d; }); child.stderr.on("data", d => { err += d; });
    child.on("close", code => resolve({ code, out, err }));
  });
}

test("monitor CLI reads the code only from the named environment variable and never prints it", { timeout: 60000 }, async () => {
  const monitorCode = "synthetic-monitor-only-code-88";
  const host = await startLocalHost({ access: { sessionSeconds: 3600, codes: [monitorCode] } });
  const root = await mkdtemp(join(tmpdir(), "pitcheezy-monitor-gate-"));
  try {
    await publishHealth(host, new Date().toISOString());
    const cfgPath = join(root, "monitor.json"), statePath = join(root, "state.json");
    await writeFile(cfgPath, JSON.stringify(runtimeConfig(host.origin)));
    const missing = await cli(["--config", cfgPath, "--state", statePath], {});
    assert.equal(missing.code, 2); assert.match(missing.err, /access_code_unavailable/);
    await assert.rejects(readFile(statePath), e => e.code === "ENOENT", "no state written without a code");
    const ok = await cli(["--config", cfgPath, "--state", statePath], { PZ_MONITOR_ACCESS_CODE: monitorCode });
    assert.equal(ok.code, 0, ok.err);
    const result = JSON.parse(ok.out);
    assert.equal(result.report.status, "available"); assert.equal(result.report.access_session, "established");
    const saved = await readFile(statePath, "utf8");
    for (const text of [ok.out, ok.err, saved, missing.out, missing.err]) {
      assert.doesNotMatch(text, new RegExp(monitorCode)); assert.doesNotMatch(text, /pz_viewer=/);
    }
  } finally {
    await rm(root, { recursive: true, force: true });
    await boundedCleanup(() => host.dispose());
  }
});

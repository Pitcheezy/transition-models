import test from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { once } from "node:events";
import { mkdtemp, writeFile, readFile, rm, access } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, dirname } from "node:path";
import { createHash } from "node:crypto";
import { spawn } from "node:child_process";
import { fileURLToPath } from "node:url";
import {
  validateConfig, evaluateFreshness, probe, initialState, advanceState, validateState,
} from "../monitor.mjs";

const NOW = Date.parse("2026-10-12T03:00:00Z");
const ISO = new Date(NOW).toISOString();
const config = (extra = {}) => ({
  schema: "pitcheezy-host-monitor-v1", origin: "https://public.example.test",
  allow_loopback_http: false, timeout_ms: 200, max_body_bytes: 4096,
  timestamp_pointer: "/synthetic/at", timestamp_format: "rfc3339",
  max_age_seconds: 120, clock_skew_seconds: 30, page_sha256: null, ...extra,
});
const html = "<!doctype html><html><title>Synthetic monitor</title></html>";
const goodHealth = () => ({ synthetic: { at: ISO } });
const headers = (extra = {}) => ({ "Content-Type": "application/json", Date: new Date(NOW).toUTCString(), Age: "0", ...extra });
const fake = ({ body = goodHealth(), extraHeaders = {}, page = html, pageStatus = 200, healthStatus = 200 } = {}) =>
  async (url, options) => {
    assert.equal(options.redirect, "manual");
    assert.equal(options.credentials, "omit");
    assert.equal(options.referrerPolicy, "no-referrer");
    assert.equal(options.method, "GET");
    return url.endsWith(".json") ?
      new Response(typeof body === "string" ? body : JSON.stringify(body), { status: healthStatus, headers: headers(extraHeaders) }) :
      new Response(page, { status: pageStatus, headers: { "Content-Type": "text/html" } });
  };
const run = (c = config(), options = {}) => probe(c, { now: () => NOW, fetchImpl: fake(options) });

test("fresh transport is not a semantic health or JavaScript execution claim", async () => {
  const result = await run();
  assert.equal(result.status, "available");
  assert.equal(result.health.freshness.status, "fresh");
  assert.equal(result.semantic_health, "unmeasured");
  assert.equal(result.javascript_execution, "unmeasured");
  assert.doesNotMatch(JSON.stringify(result), /public\.example|Synthetic monitor/);
});

test("freshness missing configuration is partial, not green", async () => {
  const result = await run(config({ timestamp_pointer: null }));
  assert.equal(result.status, "partial");
  assert.equal(result.health.freshness.status, "unmeasured");
});

test("configured publication clock distinguishes stale, future, missing, invalid, and boundary", async () => {
  for (const [body, status] of [
    [{ synthetic: { at: new Date(NOW - 121000).toISOString() } }, "stale"],
    [{ synthetic: { at: new Date(NOW + 31000).toISOString() } }, "future"],
    [{ synthetic: {} }, "missing"],
    [{ synthetic: { at: NOW } }, "invalid"],
    [{ synthetic: { at: "2026-02-30T00:00:00Z" } }, "invalid"],
    [{ synthetic: { at: "2026-10-12T03:00:00" } }, "invalid"],
    [{ synthetic: { at: new Date(NOW - 120000).toISOString() } }, "fresh"],
    [{ synthetic: { at: "2026-10-12T12:00:00+09:00" } }, "fresh"],
  ]) {
    assert.equal((await run(config(), { body })).health.freshness.status, status);
  }
});

test("pointer escapes and own properties work without traversing inherited values", () => {
  const c = config({ timestamp_pointer: "/a~1b/~0time" });
  assert.equal(evaluateFreshness({ "a/b": { "~time": ISO } }, c, NOW).status, "fresh");
  assert.equal(evaluateFreshness({}, config({ timestamp_pointer: "/constructor" }), NOW).status, "missing");
});

test("headers are tested separately from publication time", async () => {
  for (const [h, expected] of [[{ Age: "bad" }, "age_invalid"], [{ Date: "bad" }, "date_invalid"],
    [{ Age: "99999" }, "clock_mismatch"]]) {
    const r = await run(config(), { extraHeaders: h });
    assert.equal(r.health.headers, expected);
    assert.equal(r.status, "failed");
    assert.equal(r.health.freshness.status, "fresh");
  }
  const stale = await run(config(), { body: { synthetic: { at: "2026-10-11T03:00:00Z" } } });
  assert.equal(stale.health.headers, "valid");
  assert.equal(stale.health.freshness.status, "stale");
});

test("invalid origins, bounds, secrets in URL and deep pointers fail before requests", () => {
  for (const extra of [
    { origin: "http://example.test" }, { origin: "https://u:p@example.test" },
    { origin: "https://example.test/?key=secret" }, { origin: "https://example.test/#x" },
    { origin: "https://example.test/path" }, { origin: null },
    { timeout_ms: 0 }, { max_body_bytes: 6e6 }, { timestamp_pointer: "/" + "a/".repeat(20) },
    { timestamp_pointer: "/a~2b" }, { timestamp_format: "guess" }, { extra: "x" },
    { origin: "http://localhost:1234", allow_loopback_http: true },
  ]) assert.throws(() => validateConfig(config(extra)));
  assert.doesNotThrow(() => validateConfig(config({ origin: "http://127.0.0.1:1234", allow_loopback_http: true })));
});

test("HTTP, MIME, JSON and page content/hash failures are safe fixed codes", async () => {
  for (const [options, expected] of [
    [{ healthStatus: 404 }, "health_missing"],
    [{ healthStatus: 503 }, "health_http_error"],
    [{ healthStatus: 302 }, "health_redirect"],
    [{ body: "<secret>" }, "health_invalid_json"],
    [{ body: [] }, "health_invalid_json_object"],
    [{ extraHeaders: { "Content-Type": "text/plain" } }, "health_content_type"],
    [{ page: "error page" }, "page_not_html_document"],
  ]) assert.ok((await run(config(), options)).issues.includes(expected));
  const sha = createHash("sha256").update(html).digest("hex");
  assert.equal((await run(config({ page_sha256: sha }))).status, "available");
  assert.ok((await run(config({ page_sha256: "0".repeat(64) }))).issues.includes("page_page_hash_mismatch"));
});

test("stream cap rejects body even when length header is absent or false", async () => {
  for (const declared of [null, "20", "100000"]) {
    const fetchImpl = async url => {
      if (!url.endsWith(".json")) return fake()(url, { redirect: "manual", credentials: "omit", referrerPolicy: "no-referrer", method: "GET" });
      const h = headers();
      if (declared !== null) h["Content-Length"] = declared;
      return new Response("x".repeat(5000), { headers: h });
    };
    const r = await probe(config(), { fetchImpl, now: () => NOW });
    assert.equal(r.health.code, "body_too_large");
  }
});

test("whole-body timeout, including headers-only response, cannot hang a probe", async () => {
  const begin = performance.now();
  const fetchImpl = async () => new Response(new ReadableStream({ start() {} }), { headers: headers() });
  const result = await probe(config({ timeout_ms: 100 }), { fetchImpl, now: () => NOW });
  assert.equal(result.health.code, "timeout");
  assert.ok(performance.now() - begin < 2000);
});

test("fetch refusal does not leak exception text", async () => {
  const r = await probe(config(), { fetchImpl: async () => { throw new Error("TOKEN: should-not-leak"); }, now: () => NOW });
  assert.equal(r.health.code, "network_error");
  assert.doesNotMatch(JSON.stringify(r), /TOKEN|should-not-leak/);
});

test("two recorded failures open one incident and two recoveries close it", async () => {
  const c = config();
  const good = await run(c);
  const bad = await run(c, { healthStatus: 503 });
  let state = initialState(c);
  const events = [];
  for (const [i, report] of [good, bad, bad, bad, good, good, good].entries()) {
    const next = advanceState(state, { ...report, observed_at_ms: NOW + i * 1000 }, c);
    state = next.state;
    if (next.event) events.push(next.event);
  }
  assert.deepEqual(events.map(e => e.kind), ["opened", "recovered"]);
  assert.equal(events[0].id, events[1].id);
  assert.equal(state.incident, null);
  assert.equal(state.events.length, 2);
});

test("damaged state, configuration change and backward time do not erase incidents", async () => {
  const c = config();
  const bad = await run(c, { healthStatus: 503 });
  let state = advanceState(initialState(c), bad, c).state;
  state = advanceState(state, { ...bad, observed_at_ms: NOW + 1 }, c).state;
  const snapshot = JSON.stringify(state);
  assert.throws(() => validateState({ ...state, failures: 99 }, c), /state_invalid/);
  assert.throws(() => validateState(state, config({ max_age_seconds: 300 })), /config_changed/);
  assert.throws(() => advanceState(state, bad, c), /clock_error/);
  assert.equal(JSON.stringify(state), snapshot);
});

test("state event history is bounded and reports discarded count", async () => {
  const c = config();
  const bad = await run(c, { healthStatus: 503 });
  const good = await run(c);
  let state = initialState(c);
  for (let i = 0; i < 208; i++) state = advanceState(state,
    { ...(i % 4 < 2 ? bad : good), observed_at_ms: NOW + i }, c).state;
  assert.equal(state.events.length, 100);
  assert.equal(state.dropped_events, 4);
});

function command(args) {
  return new Promise((resolve, reject) => {
    const child = spawn(process.execPath, [fileURLToPath(new URL("../monitor-cli.mjs", import.meta.url)), ...args], { windowsHide: true });
    let out = "", err = "";
    child.stdout.on("data", x => out += x);
    child.stderr.on("data", x => err += x);
    child.on("error", reject);
    child.on("close", code => resolve({ code, out, err }));
  });
}

test("real loopback CLI records, locks, preserves state on errors and detects recovery", async () => {
  const root = await mkdtemp(join(tmpdir(), "pitcheezy-monitor-"));
  let broken = false, requests = 0;
  const server = createServer((req, res) => {
    requests++;
    if (req.url === "/") { res.setHeader("Content-Type", "text/html"); res.end(html); return; }
    res.setHeader("Content-Type", "application/json"); res.setHeader("Age", "0");
    if (broken) { res.statusCode = 503; res.end('{"synthetic":true}'); return; }
    res.end(JSON.stringify({ synthetic: { at: new Date().toISOString() } }));
  }).listen(0, "127.0.0.1");
  try {
    await once(server, "listening");
    const c = config({ origin: "http://127.0.0.1:" + server.address().port, allow_loopback_http: true, timeout_ms: 2000 });
    const cfg = join(root, "config.json"), state = join(root, "state.json");
    await writeFile(cfg, JSON.stringify(c));
    const args = ["--config", cfg, "--state", state];
    let r = await command(args);
    assert.equal(r.code, 0, r.err);
    broken = true;
    assert.equal((await command(args)).code, 1);
    r = await command(args);
    assert.equal(JSON.parse(r.out).event.kind, "opened");
    const saved = await readFile(state, "utf8");
    const calls = requests;
    await writeFile(state + ".lock", "synthetic lock");
    r = await command(args);
    assert.equal(r.code, 2);
    assert.match(r.err, /already_running/);
    assert.equal(requests, calls);
    assert.equal(await readFile(state, "utf8"), saved);
    await rm(state + ".lock");
    await writeFile(cfg, JSON.stringify({ ...c, max_age_seconds: 500 }));
    r = await command(args);
    assert.match(r.err, /config_changed/);
    assert.equal(requests, calls);
    await writeFile(cfg, JSON.stringify(c));
    broken = false;
    assert.equal((await command(args)).code, 1); // one success cannot close the open incident
    r = await command(args);
    assert.equal(r.code, 0);
    assert.equal(JSON.parse(r.out).event.kind, "recovered");
    await assert.rejects(access(state + ".lock"));
    assert.doesNotMatch(r.out + r.err, /127\.0\.0\.1|TOKEN|Synthetic monitor/);
    await writeFile(state, "{damaged");
    r = await command(args);
    assert.equal(r.code, 2);
    assert.match(r.err, /input_invalid_json/);
    assert.equal(await readFile(state, "utf8"), "{damaged");
  } finally {
    server.closeAllConnections();
    await new Promise(resolve => server.close(resolve));
    assert.equal(dirname(resolve(root)), resolve(tmpdir()));
    assert.ok(resolve(root).startsWith(join(resolve(tmpdir()), "pitcheezy-monitor-")));
    await rm(root, { recursive: true, force: true }); // exact mkdtemp-created test directory only
  }
});

test("JSON Pointer supports regular array indices only", () => {
  const body = { samples: [{ at: ISO }] };
  assert.equal(evaluateFreshness(body, config({ timestamp_pointer: "/samples/0/at" }), NOW).status, "fresh");
  assert.equal(evaluateFreshness(body, config({ timestamp_pointer: "/samples/00/at" }), NOW).status, "missing");
  assert.equal(evaluateFreshness(body, config({ timestamp_pointer: "/samples/length" }), NOW).status, "missing");
});

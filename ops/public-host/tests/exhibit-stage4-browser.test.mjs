import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile, readdir, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { browserRequestPath, Stage4BrowserLedger, summarizeNormalBrowserRows } from "../exhibit-stage4-browser.mjs";

const ORIGIN = "https://synthetic.invalid";
const VERSION = "12345678-1234-1234-1234-123456789abc";
async function fixture(t, limit = 4) {
  const parent = await mkdtemp(join(tmpdir(), "pz-stage4-browser-"));
  t.after(() => rm(parent, { recursive: true, force: true }));
  const ledger = new Stage4BrowserLedger({ origin: ORIGIN, outDir: join(parent, "new"), maxRequests: limit, versionPin: VERSION });
  await ledger.initialize(); return ledger;
}

test("exact game/asset paths allow reads; other hosts, credentials, query data and mutations are refused", () => {
  for (const path of ["/", "/?game=849843", "/v1/game/849843.json", "/assets/index-X1sSTTQ4.js", "/favicon.svg"])
    assert.equal(browserRequestPath(ORIGIN, ORIGIN + path, "GET"), path);
  for (const [url, method] of [
    ["https://other.invalid/", "GET"], ["https://secret@synthetic.invalid/", "GET"],
    [ORIGIN + "/?game=849844", "GET"], [ORIGIN + "/v1/game/849843.json?key=secret", "GET"],
    [ORIGIN + "/v1/game/849844.json", "GET"], [ORIGIN + "/v1/game/849843.json", "PUT"],
    [ORIGIN + "/_notice/v1/state", "PUT"], [ORIGIN + "/_publish/v1/health.json", "HEAD"],
    [ORIGIN + "/?game=849843#secret", "GET"], [ORIGIN + "/_access/v1/session", "GET"],
  ]) assert.equal(browserRequestPath(ORIGIN, url, method), null);
  assert.equal(browserRequestPath(ORIGIN, ORIGIN + "/_access/v1/session", "POST"), "/_access/v1/session");
});

test("normal cap reserves exactly one logout even after budget stop", async t => {
  const ledger = await fixture(t, 3);
  await ledger.begin(ORIGIN + "/", "GET");
  await ledger.begin(ORIGIN + "/v1/health.json", "GET");
  await assert.rejects(ledger.begin(ORIGIN + "/", "GET"), /budget_or_stop/);
  const logout = await ledger.begin(ORIGIN + "/_access/v1/session", "DELETE", { logout: true });
  assert.equal(logout.number, 3);
  await assert.rejects(ledger.begin(ORIGIN + "/_access/v1/session", "DELETE", { logout: true }));
  assert.equal(ledger.snapshot().requests, 3);
});

test("reserved slot cannot be used as ordinary DELETE or arbitrary cleanup GET", async t => {
  const ledger = await fixture(t);
  await assert.rejects(ledger.begin(ORIGIN + "/_access/v1/session", "DELETE"));
  await assert.rejects(ledger.begin(ORIGIN + "/", "GET", { logout: true }));
  assert.equal(ledger.snapshot().requests, 0);
});

test("a started record exists before dispatch; completed records contain only safe selected values", async t => {
  const ledger = await fixture(t);
  const row = await ledger.begin(ORIGIN + "/?game=849843", "GET");
  const before = JSON.parse(await readFile(ledger.file(row, "started"), "utf8"));
  assert.equal(before.state, "started"); assert.equal(before.status, undefined);
  await ledger.finish(row, { status: 200, ray: "0123456789abcdef-HKG", headers: { cookie: "secret" }, body: "secret" });
  const after = JSON.parse(await readFile(ledger.file(row, "completed"), "utf8"));
  assert.equal(after.status, 200); assert.equal(after.cf_ray, "0123456789abcdef-HKG");
  assert.equal(after.version_evidence, "management_pin_not_server_event_proof");
  const all = (await Promise.all((await readdir(ledger.outDir)).map(file => readFile(join(ledger.outDir, file), "utf8")))).join("");
  assert.equal(all.includes("secret"), false); assert.equal(all.includes(ORIGIN), false);
});

test("concurrent begin calls cannot exceed cap or share record numbers", async t => {
  const ledger = await fixture(t, 4);
  const settled = await Promise.allSettled(Array.from({ length: 12 }, () => ledger.begin(ORIGIN + "/v1/health.json", "GET")));
  assert.equal(settled.filter(r => r.status === "fulfilled").length, 3);
  assert.deepEqual(ledger.rows.map(r => r.number), [1, 2, 3]);
});

test("unknown transport result stays failed and stops new reads but permits logout", async t => {
  const ledger = await fixture(t);
  const row = await ledger.begin(ORIGIN + "/v1/health.json", "GET");
  await ledger.finish(row, { failed: true, ray: "malicious cookie=secret" });
  await assert.rejects(ledger.begin(ORIGIN + "/", "GET"), /transport_failed/);
  assert.equal(row.cf_ray, null);
  await ledger.begin(ORIGIN + "/_access/v1/session", "DELETE", { logout: true });
  assert.equal(ledger.snapshot().incomplete_or_failed, 2);
});

test("automatic redirects are stopped even when redirect target is allowed", async t => {
  const ledger = await fixture(t);
  await assert.rejects(ledger.begin(ORIGIN + "/", "GET", { redirected: true }), /unexpected_browser_request/);
  assert.equal(ledger.snapshot().requests, 0);
});

test("existing output refuses repeat run; invalid origin and enlarged budgets fail before setup", async t => {
  const ledger = await fixture(t);
  await assert.rejects(ledger.initialize(), /EEXIST/);
  assert.throws(() => new Stage4BrowserLedger({ origin: "http://synthetic.invalid", outDir: ledger.outDir, versionPin: VERSION }), /invalid_origin/);
  assert.throws(() => new Stage4BrowserLedger({ origin: ORIGIN, outDir: ledger.outDir, maxRequests: 181, versionPin: VERSION }), /invalid_budget/);
});

test("normal polling requires completed game and health observations inside the sampling window", () => {
  const rows = [
    { number: 1, method: "GET", path: "/v1/game/849843.json", state: "completed", status: 200 },
    { number: 2, method: "GET", path: "/v1/health.json", state: "completed", status: 200 },
    { number: 3, method: "GET", path: "/v1/game/849843.json", state: "completed", status: 304 },
  ];
  assert.equal(summarizeNormalBrowserRows(rows, 1, 3).passed, true);
  const measured = summarizeNormalBrowserRows(rows, 2, 3);
  assert.equal(measured.passed, true); assert.equal(measured.requests, 2);
  assert.deepEqual(measured.status_counts, { 200: 1, 304: 1 });
  assert.equal(summarizeNormalBrowserRows(rows, 4, 4).passed, false);
  assert.equal(summarizeNormalBrowserRows(rows, 3, 3).passed, false);
});

test("normal polling rejects failed/incomplete transport, notice/error responses, and redirects", () => {
  const baseline = [
    { number: 1, method: "GET", path: "/v1/game/849843.json", state: "completed", status: 200 },
    { number: 2, method: "GET", path: "/v1/health.json", state: "completed", status: 200 },
  ];
  for (const status of [301, 401, 404, 500, 503, null]) {
    const result = summarizeNormalBrowserRows([...baseline, { number: 3, method: "GET", path: "/v1/manifest.json", state: "completed", status }], 1, 3);
    assert.equal(result.passed, false); assert.equal(result.unexpected_http, 1);
  }
  for (const state of ["started", "transport_failed"]) {
    const result = summarizeNormalBrowserRows([...baseline, { number: 3, method: "GET", path: "/v1/health.json", state }], 1, 3);
    assert.equal(result.passed, false); assert.equal(result.incomplete_or_failed, 1);
  }
});

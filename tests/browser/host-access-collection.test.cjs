"use strict";
// WS-access3: viewer access gate x opt-in collection in a real local environment: an https loopback Worker
// (Miniflare's built-in development certificate), real local D1 with the telemetry migration, an edge stand-in that sets
// CF-Connecting-IP, and OUR widget/usage client. Synthetic game and ephemeral codes only; no Song code.
const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const playwright = require("playwright");
const ROOT = path.resolve(__dirname, "../..");
const ENGINE = process.env.BROWSER_ENGINE || "chromium";
const RECEIPT = process.env.PZ_ACCESS_COLLECTION_RECEIPT || null;
const OPTIONS = { telemetryEnabled: true, feedbackEnabled: true, retainDays: 30, gamePk: 123 };
const SHORT_SESSION_SECONDS = 4;
let local, gated, shortGated, open, browser;
const cases = [];

before(async () => {
  local = await import(pathToFileURL(path.join(ROOT, "ops/public-host/rehearsal/local-host.mjs")).href);
  gated = await local.startLocalHost({ access: { sessionSeconds: 3600 }, collection: true });
  shortGated = await local.startLocalHost({ access: { sessionSeconds: SHORT_SESSION_SECONDS }, collection: true });
  open = await local.startLocalHost({ collection: true });
  browser = await playwright[ENGINE].launch({ headless: true,
    ...(process.env.BROWSER_CHANNEL ? { channel: process.env.BROWSER_CHANNEL } : {}) });
});
after(async () => {
  await browser?.close();
  for (const host of [gated, shortGated, open]) await host?.dispose().catch(() => {});
  if (RECEIPT) {
    fs.writeFileSync(RECEIPT, JSON.stringify({
      schema: "pitcheezy-access-collection-check-v1", engine: ENGINE, evidence: "synthetic local runtime",
      environment: "https loopback Miniflare Worker (built-in development certificate), local D1 with migrations/0001_telemetry.sql, edge stand-in for CF-Connecting-IP",
      not_checked: ["real Cloudflare edge and certificate", "real Safari/mobile", "real viewers or real games"], cases,
    }, null, 2) + "\n", { flag: "wx" });
  }
});

async function openPage(host) {
  const context = await browser.newContext({ ignoreHTTPSErrors: true, viewport: { width: 375, height: 760 } });
  const page = await context.newPage();
  const failures = []; page.on("pageerror", e => failures.push(e.message));
  const sent = [];
  const pending = new Map();
  // Status comes from the response event: the client deliberately does not read refused bodies, so a
  // "finished" event may never fire for a 401.
  page.on("request", request => {
    const url = new URL(request.url());
    if (!url.pathname.startsWith("/_telemetry/")) return;
    const entry = { path: url.pathname, done: false };
    sent.push(entry); pending.set(request, entry);
    entry.headers = request.allHeaders().then(headers => {
      entry.cookie = /(^|;\s*)(__Host-)?pz_viewer=/.test(headers.cookie || "");
      entry.other_cookie = /private_cookie=/.test(headers.cookie || "");
    });
  });
  page.on("response", async response => {
    const entry = pending.get(response.request());
    if (!entry) return;
    await entry.headers;
    Object.assign(entry, { status: response.status(), access: response.headers()["x-pitcheezy-access"] || null, done: true });
  });
  page.on("requestfailed", async request => {
    const entry = pending.get(request);
    if (!entry || entry.done) return;
    await entry.headers;
    Object.assign(entry, { failed: true, done: true });
  });
  await page.clock.install({ time: new Date("2026-10-13T12:00:00Z") });
  await page.clock.pauseAt(new Date("2026-10-13T12:01:00Z"));
  const settled = async count => {
    for (let i = 0; i < 100 && !(sent.length >= count && sent.every(e => e.done)); i++) await new Promise(r => setTimeout(r, 50));
    assert.ok(sent.length >= count && sent.every(e => e.done), `expected ${count} finished collection requests, saw ${sent.length}`);
  };
  const quiet = async () => { await new Promise(r => setTimeout(r, 300)); return sent.length; };
  return { context, page, failures, sent, settled, quiet };
}
async function login(page, host) {
  const locked = await page.goto(host.origin + "/collect.html");
  assert.equal(locked.status(), 401);
  await page.fill("#code", host.accessCodes[0]);
  await Promise.all([page.waitForURL(host.origin + "/"), page.getByRole("button", { name: "들어가기" }).click()]);
  await enter(page, host);
}
async function enter(page, host) {
  const response = await page.goto(host.origin + "/collect.html");
  assert.equal(response.status(), 200);
  await page.waitForFunction(() => window.collectReady === true);
}
const mount = (page, extra = {}) => page.evaluate(o => window.mount(o), { ...OPTIONS, ...extra });
const usageStatus = page => page.locator(".pitcheezy-usage-widget [role=status]").nth(0).textContent();
const feedbackStatus = page => page.locator(".pitcheezy-usage-widget [role=status]").nth(1).textContent();
const delta = (after, before) => Object.fromEntries(Object.keys(after).map(k => [k, after[k] - before[k]]));
const tick = (page, ms = 30000) => page.clock.fastForward(ms);
// The server accepts active time only up to the real time since the session started (+1 s), so a pulse that
// must be stored lets the same amount of real time pass, then flushes through the widget's visibility handler.
async function pulse(page, ms) {
  await new Promise(r => setTimeout(r, ms + 400));
  await page.clock.fastForward(ms);
  await page.evaluate(() => document.dispatchEvent(new Event("visibilitychange")));
}
async function consent(page) {
  await page.getByRole("checkbox", { name: "방문 통계 참여" }).check();
}
async function waitStatus(page, prefix) {
  await page.waitForFunction(p => document.querySelectorAll(".pitcheezy-usage-widget [role=status]")[0]?.textContent.startsWith(p), prefix);
}

test("without a viewer session the collection routes refuse before storage and spend no budget", { timeout: 30000 }, async () => {
  const before = await gated.collectionCounts();
  const body = JSON.stringify({ v: 1, consent: true, session_id: crypto.randomUUID(), game_pk: 123, sequence: 0, active_ms: 0 });
  for (const cookie of [null, "__Host-pz_viewer=v2.1.2.0123abcd.0123456789abcdef." + "0".repeat(64), "pz_viewer=garbage"]) {
    for (const route of ["/_telemetry/session", "/_telemetry/feedback"]) {
      const r = await gated.request(route, { method: "POST", body,
        headers: { "Content-Type": "application/json", Origin: gated.origin, ...(cookie ? { Cookie: cookie } : {}) } });
      assert.equal(r.status, 401, route); assert.equal(r.headers.get("X-Pitcheezy-Access"), "required");
      assert.deepEqual(await r.json(), { error: "access_required" });
    }
  }
  const d = delta(await gated.collectionCounts(), before);
  assert.deepEqual(d, { sessions: 0, feedback: 0, budget_used: 0 });
  cases.push({ case: "no_session_direct_post", status: 401, d1_delta: d });
});

test("logged-in viewer: nothing before consent, feedback without consent, consent stores with the session cookie, withdrawal stops", { timeout: 90000 }, async () => {
  const before = await gated.collectionCounts();
  const { context, page, failures, sent, settled, quiet } = await openPage(gated);
  try {
    await login(page, gated);
    await mount(page, { accessGate: true });
    assert.match(await page.locator(".pitcheezy-usage-widget").textContent(), /이 사이트의 쿠키\(접속 확인용 포함\)가 함께 전송됩니다/);
    await tick(page, 60000); assert.equal(await quiet(), 0, "no consent: no collection request");
    await page.getByRole("button", { name: "도움이 돼요", exact: true }).click();
    await page.getByText("의견을 받았습니다. 감사합니다.", { exact: true }).waitFor();
    await settled(1);
    assert.deepEqual([sent[0].path, sent[0].status, sent[0].cookie], ["/_telemetry/feedback", 200, true]);
    await consent(page); await waitStatus(page, "참여 중");
    await settled(2);
    assert.deepEqual([sent[1].path, sent[1].status, sent[1].cookie], ["/_telemetry/session", 200, true]);
    await pulse(page, 2000); await settled(3);
    assert.deepEqual([sent[2].path, sent[2].status, sent[2].cookie], ["/_telemetry/session", 200, true]);
    const rows = await gated.sessionRows();
    const mine = rows.at(-1);
    assert.equal(mine.sequence, 1); assert.equal(mine.active_ms, 2000); assert.equal(mine.game_pk, 123);
    await page.getByRole("checkbox", { name: "방문 통계 참여" }).uncheck();
    await waitStatus(page, "참여하지");
    await tick(page, 120000); assert.equal(await quiet(), 3, "withdrawn: no further requests");
    assert.equal(await page.evaluate(() => document.cookie), "", "the session cookie is HttpOnly");
    const d = delta(await gated.collectionCounts(), before);
    assert.deepEqual(d, { sessions: 1, feedback: 1, budget_used: 3 }, "the daily budget counts writes: feedback, session start, one update");
    assert.deepEqual(failures, []);
    cases.push({ case: "login_no_consent_feedback_consent_withdraw", requests: sent.map(({ path: p, status, cookie }) => ({ path: p, status, cookie })), d1_delta: d });
  } finally { await context.close(); }
});

test("after logout: session and feedback are refused as access_required and not stored; re-entry does not carry consent", { timeout: 90000 }, async () => {
  const before = await gated.collectionCounts();
  const { context, page, failures, sent, settled, quiet } = await openPage(gated);
  try {
    await login(page, gated);
    await mount(page, { accessGate: true });
    await consent(page); await waitStatus(page, "참여 중"); await settled(1);
    const firstSession = (await gated.sessionRows()).at(-1).session_id;
    const loggedOut = await page.evaluate(() => fetch("/_access/v1/session", { method: "DELETE", credentials: "same-origin" }).then(r => r.status));
    assert.equal(loggedOut, 204);
    await tick(page); await settled(2);
    assert.deepEqual([sent[1].status, sent[1].access, sent[1].cookie], [401, "required", false]);
    await waitStatus(page, "접속이 끝나");
    assert.equal(await page.getByRole("checkbox", { name: "방문 통계 참여" }).isChecked(), false, "participation ends: the box is unchecked");
    for (let i = 0; i < 5; i++) await tick(page, 300000);
    assert.equal(await quiet(), 2, "no retry storm against the gate");
    await page.getByRole("button", { name: "설명이 어려워요" }).click();
    await page.getByText("접속이 끝나 의견이 저장되지 않았습니다.", { exact: false }).waitFor();
    await settled(3);
    assert.deepEqual([sent[2].path, sent[2].status], ["/_telemetry/feedback", 401]);
    assert.equal(await page.getByRole("button", { name: "도움이 돼요", exact: true }).isDisabled(), false, "a certain refusal leaves every rating available");
    const afterLogout = delta(await gated.collectionCounts(), before);
    assert.deepEqual(afterLogout, { sessions: 1, feedback: 0, budget_used: 1 }, "only the session started before logout was stored");
    // Re-entry: the page reloads into the login screen; consent is in memory only and is not carried over.
    await login(page, gated);
    await mount(page, { accessGate: true });
    assert.equal(await page.getByRole("checkbox", { name: "방문 통계 참여" }).isChecked(), false);
    await tick(page, 60000); assert.equal(await quiet(), 3, "no collection until consent is given again");
    await consent(page); await waitStatus(page, "참여 중"); await settled(4);
    assert.equal(sent[3].status, 200);
    const rows = await gated.sessionRows();
    assert.notEqual(rows.at(-1).session_id, firstSession, "re-consent starts a new session");
    const d = delta(await gated.collectionCounts(), before);
    assert.deepEqual(d, { sessions: 2, feedback: 0, budget_used: 2 });
    assert.deepEqual(failures, []);
    cases.push({ case: "logout_refusal_relogin_reconsent", requests: sent.map(({ path: p, status, cookie }) => ({ path: p, status, cookie })), d1_delta: d });
  } finally { await context.close(); }
});

test("an expiring session stops collection as access_required; nothing is stored after expiry", { timeout: 90000 }, async () => {
  const before = await shortGated.collectionCounts();
  const { context, page, failures, sent, settled, quiet } = await openPage(shortGated);
  try {
    await login(page, shortGated);
    await mount(page, { accessGate: true });
    await consent(page); await waitStatus(page, "참여 중"); await settled(1);
    assert.equal(sent[0].status, 200);
    await new Promise(r => setTimeout(r, SHORT_SESSION_SECONDS * 1000 + 600)); // real time: the server and browser clocks expire it
    await tick(page); await settled(2);
    assert.deepEqual([sent[1].status, sent[1].access], [401, "required"]);
    await waitStatus(page, "접속이 끝나");
    assert.equal(await page.getByRole("checkbox", { name: "방문 통계 참여" }).isChecked(), false);
    await page.evaluate(() => window.widget.setGame(456));
    await tick(page, 60000); assert.equal(await quiet(), 2, "a game change does not restart participation after a refusal");
    await page.getByRole("button", { name: "도움이 돼요", exact: true }).click();
    await page.getByText("접속이 끝나 의견이 저장되지 않았습니다.", { exact: false }).waitFor();
    await tick(page, 300000); assert.equal(await quiet(), 3);
    const d = delta(await shortGated.collectionCounts(), before);
    assert.deepEqual(d, { sessions: 1, feedback: 0, budget_used: 1 });
    assert.deepEqual(failures, []);
    cases.push({ case: "session_expiry_mid_collection", session_seconds: SHORT_SESSION_SECONDS, requests: sent.map(({ path: p, status, cookie }) => ({ path: p, status, cookie })), d1_delta: d });
  } finally { await context.close(); }
});

test("gate off: credentials stay omitted (no cookies travel) and collection works as before", { timeout: 60000 }, async t => {
  const before = await open.collectionCounts();
  const { context, page, failures, sent, settled } = await openPage(open);
  try {
    await context.addCookies([{ name: "private_cookie", value: "must-not-send", url: open.origin }]);
    await enter(page, open);
    await mount(page, { accessGate: false });
    assert.doesNotMatch(await page.locator(".pitcheezy-usage-widget").textContent(), /접속 확인용 쿠키/);
    await consent(page); await waitStatus(page, "참여 중"); await settled(1);
    assert.equal(sent[0].status, 200);
    if (ENGINE === "webkit" && sent[0].other_cookie) {
      t.diagnostic("Known local WebKit transport limitation: credentials omit requested but cookie arrived; the server stores no headers. Physical Safari pending.");
    } else assert.equal(sent[0].other_cookie, false);
    const d = delta(await open.collectionCounts(), before);
    assert.deepEqual(d, { sessions: 1, feedback: 0, budget_used: 1 });
    assert.deepEqual(failures, []);
    cases.push({ case: "gate_off_credentials_omit", other_cookie_sent: sent[0].other_cookie, d1_delta: d });
  } finally { await context.close(); }
});

test("misconfiguration (gate on, client accessGate false) surfaces as access_required instead of a silent delay", { timeout: 60000 }, async t => {
  const before = await gated.collectionCounts();
  const { context, page, failures, sent, settled } = await openPage(gated);
  try {
    await login(page, gated);
    await mount(page, { accessGate: false });
    await consent(page); await settled(1);
    if (ENGINE === "webkit" && sent[0].cookie) {
      t.diagnostic("Known local WebKit transport limitation: credentials omit requested but the session cookie arrived, so the gate accepted it.");
      cases.push({ case: "client_server_mismatch", engine_note: "webkit sent cookie despite omit", status: sent[0].status });
      return;
    }
    assert.deepEqual([sent[0].status, sent[0].access, sent[0].cookie], [401, "required", false]);
    await waitStatus(page, "접속이 끝나");
    const d = delta(await gated.collectionCounts(), before);
    assert.deepEqual(d, { sessions: 0, feedback: 0, budget_used: 0 });
    assert.deepEqual(failures, []);
    cases.push({ case: "client_server_mismatch", status: sent[0].status, widget: "access_required", d1_delta: d,
      note: "the offline config check refuses this pairing (client_server_settings_mismatch)" });
  } finally { await context.close(); }
});

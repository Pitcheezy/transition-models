"use strict";
// WS-access1: viewer access gate against the real local Worker. Synthetic fixture page and ephemeral codes only.
const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const playwright = require("playwright");
const ROOT = path.resolve(__dirname, "../..");
const ENGINE = process.env.BROWSER_ENGINE || "chromium";
let host, shortHost, browser, local;
before(async () => {
  local = await import(pathToFileURL(path.join(ROOT, "ops/public-host/rehearsal/local-host.mjs")).href);
  host = await local.startLocalHost({ access: { sessionSeconds: 3600 } });
  const published = await host.publish("/v1/game/123.json", JSON.stringify({ synthetic: true, synthetic_version: 1 }));
  assert.equal(published.status, 200); await published.arrayBuffer();
  browser = await playwright[ENGINE].launch({ headless: true,
    ...(process.env.BROWSER_CHANNEL ? { channel: process.env.BROWSER_CHANNEL } : {}) });
});
after(async () => {
  await browser?.close();
  try { await shortHost?.dispose(); } finally { await host?.dispose(); }
});
async function read(page, expect) {
  const button = page.getByRole("button", { name: "합성 파일 다시 읽기" });
  await button.focus(); await page.keyboard.press("Enter");
  await page.waitForFunction(text => document.querySelector("#state")?.textContent === text, expect);
}
test("gate asks for a code, rejects a wrong one, opens a private session and locks again after logout", { timeout: 60000 }, async () => {
  const context = await browser.newContext({ viewport: { width: 375, height: 740 } });
  try {
    const page = await context.newPage(); const failures = [];
    page.on("pageerror", e => failures.push(e.message));
    const locked = await page.goto(host.origin);
    assert.equal(locked.status(), 401);
    assert.equal(await page.title(), "접속 코드");
    assert.equal(await page.evaluate(() => document.scripts.length), 0);
    for (const route of ["/fixture.mjs", "/v1/game/123.json"]) {
      const r = await page.request.get(host.origin + route);
      assert.equal(r.status(), 401, route);
      assert.equal(r.headers()["x-pitcheezy-access"], "required");
      assert.equal(r.headers()["cache-control"], "no-store");
    }
    await page.fill("#code", "synthetic-wrong-code-000");
    await page.getByRole("button", { name: "들어가기" }).click();
    await page.waitForLoadState("domcontentloaded");
    assert.equal(await page.locator("p[role=alert]").textContent(), "접속 코드가 맞지 않습니다.");
    assert.deepEqual(await context.cookies(), []);
    await page.fill("#code", host.accessCodes[0]);
    await page.getByRole("button", { name: "들어가기" }).click();
    await page.waitForURL(host.origin + "/");
    await page.waitForFunction(() => window.fixtureReady === true);
    const cookies = await context.cookies();
    assert.equal(cookies.length, 1);
    assert.equal(cookies[0].name, "pz_viewer");
    assert.equal(cookies[0].httpOnly, true);
    assert.equal(cookies[0].sameSite, "Strict");
    assert.equal(cookies[0].path, "/");
    assert.equal(await page.evaluate(() => document.cookie), "", "HttpOnly cookie is invisible to scripts");
    await read(page, "합성 v1");
    const asset = await page.request.get(host.origin + "/fixture.mjs");
    assert.equal(asset.status(), 200);
    assert.match(asset.headers()["cache-control"], /^private/);
    const data = await page.request.get(host.origin + "/v1/game/123.json");
    assert.equal(data.status(), 200);
    assert.equal(local.hash(await data.body()), local.hash(JSON.stringify({ synthetic: true, synthetic_version: 1 })));
    assert.equal(await page.evaluate(() => Object.keys(window).some(k => /code|token|secret/i.test(k))), false);
    const logout = await page.request.delete(host.origin + "/_access/v1/session");
    assert.equal(logout.status(), 204);
    assert.deepEqual(await context.cookies(), []);
    const relocked = await page.reload();
    assert.equal(relocked.status(), 401);
    assert.equal(await page.title(), "접속 코드");
    assert.deepEqual(failures, []);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  } finally { await context.close(); }
});
test("a short session expires on its own and the screen locks on the next navigation", { timeout: 60000 }, async () => {
  shortHost = await local.startLocalHost({ access: { sessionSeconds: 1 } });
  const context = await browser.newContext();
  try {
    const page = await context.newPage();
    await page.goto(shortHost.origin);
    await page.fill("#code", shortHost.accessCodes[0]);
    await page.getByRole("button", { name: "들어가기" }).click();
    await page.waitForURL(shortHost.origin + "/");
    assert.equal((await context.cookies()).length, 1);
    await page.waitForTimeout(1300);
    const expired = await page.reload();
    assert.equal(expired.status(), 401);
    assert.equal(await page.title(), "접속 코드");
  } finally { await context.close(); }
});

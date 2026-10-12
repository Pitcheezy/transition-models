"use strict";
const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const playwright = require("playwright");
const ROOT = path.resolve(__dirname, "../..");
const ENGINE = process.env.BROWSER_ENGINE || "chromium";
let host, browser, hash;
before(async () => {
  const local = await import(pathToFileURL(path.join(ROOT, "ops/public-host/rehearsal/local-host.mjs")).href);
  hash = local.hash; host = await local.startLocalHost();
  browser = await playwright[ENGINE].launch({ headless: true,
    ...(process.env.BROWSER_CHANNEL ? { channel: process.env.BROWSER_CHANNEL } : {}) });
});
after(async () => {
  await browser?.close();
  try {
    // A closing browser can reset keep-alive sockets on Windows; the Worker must still answer.
    if (host) {
      const alive = await fetch(host.origin, { signal: AbortSignal.timeout(5000) });
      assert.equal(alive.status, 200);
      await alive.arrayBuffer();
    }
  } finally { await host?.dispose(); }
});
async function write(body, tag) {
  const r = await host.publish("/v1/game/123.json", body, tag);
  assert.equal(r.status, 200);
  await r.arrayBuffer(); return r.headers.get("ETag");
}
test("real local Worker: keyboard reads new versions, withdrawal and same-body restore", async () => {
  const context = await browser.newContext({ viewport: { width: 375, height: 740 } });
  try {
    const page = await context.newPage(); const failures = [];
    page.on("pageerror", e => failures.push(e.message));
    await page.goto(host.origin);
    await page.waitForFunction(() => window.fixtureReady === true);
    const button = page.getByRole("button", { name: "합성 파일 다시 읽기" });
    const state = page.locator("#state");
    async function read(expect) {
      await button.focus(); await page.keyboard.press("Enter");
      await page.waitForFunction(text => document.querySelector("#state").textContent === text, expect);
      assert.equal(await state.textContent(), expect);
    }
    await read("파일 없음");
    const first = JSON.stringify({ synthetic: true, synthetic_version: 1 });
    let tag = await write(first);
    await read("합성 v1");
    const second = JSON.stringify({ synthetic: true, synthetic_version: 2 });
    tag = await write(second, tag);
    await read("합성 v2");
    const del = await host.withdraw("/v1/game/123.json", tag);
    assert.equal(del.status, 200); await del.arrayBuffer();
    await read("파일 없음");
    const restored = await write(second, del.headers.get("ETag"));
    assert.notEqual(restored, tag);
    await read("합성 v2");
    const r = await page.request.get(host.origin + "/v1/game/123.json");
    assert.equal(hash(await r.body()), hash(second));
    assert.equal(r.headers()["age"], "0");
    assert.deepEqual(failures, []);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  } finally { await context.close(); }
});
test("data and private paths return actual 404 instead of synthetic HTML", async () => {
  const context = await browser.newContext();
  try {
    const page = await context.newPage(); await page.goto(host.origin);
    for (const route of ["/v1/game/999.json", "/api/private", "/v1%2fgame/123.json"]) {
      const r = await page.request.get(host.origin + route);
      assert.equal(r.status(), 404);
      assert.match(r.headers()["content-type"], /^application\/json/);
      assert.doesNotMatch(await r.text(), /<!doctype/i);
    }
  } finally { await context.close(); }
});

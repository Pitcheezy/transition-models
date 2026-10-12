"use strict";
// WS-safe1: emergency notice switch against the real local Worker. Synthetic fixture page only; no Song screen.
const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const { pathToFileURL } = require("node:url");
const playwright = require("playwright");
const ROOT = path.resolve(__dirname, "../..");
const ENGINE = process.env.BROWSER_ENGINE || "chromium";
let host, browser;
const change = async (active, etag, operator = "browser-drill") => {
  const r = await host.setNotice({ active, operator, reason: "synthetic browser drill", message_id: "maintenance" }, etag);
  const text = await r.text();
  assert.equal(r.status, 200, text);
  return r.headers.get("ETag");
};
// Leaves no notice behind even when an earlier scenario failed midway.
const ensureOff = async () => {
  const view = await host.noticeState();
  const parsed = await view.json();
  if (parsed.state.active) await change(false, parsed.state.etag, "browser-cleanup");
};
before(async () => {
  const local = await import(pathToFileURL(path.join(ROOT, "ops/public-host/rehearsal/local-host.mjs")).href);
  host = await local.startLocalHost({ notice: true });
  const published = await host.publish("/v1/game/123.json", JSON.stringify({ synthetic: true, synthetic_version: 1 }));
  assert.equal(published.status, 200); await published.arrayBuffer();
  browser = await playwright[ENGINE].launch({ headless: true,
    ...(process.env.BROWSER_CHANNEL ? { channel: process.env.BROWSER_CHANNEL } : {}) });
});
after(async () => {
  await browser?.close();
  try {
    if (host) {
      const alive = await fetch(host.origin + "/v1/game/123.json", { signal: AbortSignal.timeout(5000) });
      assert.equal(alive.status, 200); await alive.arrayBuffer();
    }
  } finally { await host?.dispose(); }
});
async function read(page, expect) {
  const button = page.getByRole("button", { name: "합성 파일 다시 읽기" });
  await button.focus(); await page.keyboard.press("Enter");
  await page.waitForFunction(text => document.querySelector("#state")?.textContent === text, expect);
}
test("open screen, reload, direct files, back navigation and recovery around the notice switch", { timeout: 60000 }, async (t) => {
  const context = await browser.newContext({ viewport: { width: 375, height: 740 } });
  try {
    const page = await context.newPage(); const failures = [];
    page.on("pageerror", e => failures.push(e.message));
    const first = await page.goto(host.origin);
    assert.equal(first.status(), 200);
    await page.waitForFunction(() => window.fixtureReady === true);
    await read(page, "합성 v1");
    // Operator turns the notice on while the viewer's screen stays open.
    const etag = await change(true, null);
    await read(page, "안내 중: maintenance");
    // Direct file, data and HEAD access from the same browser context.
    for (const route of ["/fixture.mjs", "/index.html", "/anything/else"]) {
      const r = await page.request.get(host.origin + route);
      assert.equal(r.status(), 503, route);
      assert.match(r.headers()["content-type"], /^text\/html/);
      assert.equal(r.headers()["cache-control"], "no-store");
      assert.equal(r.headers()["x-pitcheezy-notice"], "maintenance");
      assert.match(await r.text(), /개발용 안내 문구/);
    }
    const data = await page.request.get(host.origin + "/v1/game/123.json");
    assert.equal(data.status(), 503);
    assert.equal((await data.json()).error, "service_notice");
    const head = await page.request.head(host.origin + "/v1/game/123.json");
    assert.equal(head.status(), 503);
    assert.equal(await head.text(), "");
    // Reload of the open screen shows the notice document itself.
    const reloaded = await page.reload();
    assert.equal(reloaded.status(), 503);
    assert.equal(await page.title(), "안내");
    assert.equal(await page.locator("main[data-notice-id]").getAttribute("data-notice-id"), "maintenance");
    assert.equal(await page.evaluate(() => document.scripts.length), 0);
    assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
    // History: navigate to a second entry, then back. A restored old DOM must receive the notice on its next read.
    const second = await page.goto(host.origin + "/index.html");
    assert.equal(second.status(), 503);
    await page.goBack();
    await page.waitForLoadState("domcontentloaded");
    const noticeVisible = await page.locator("main[data-notice-id]").count();
    if (noticeVisible > 0) t.diagnostic("back navigation re-requested the document: notice shown");
    else {
      t.diagnostic("back navigation restored the previous document from history/bfcache: next read must show the notice");
      await page.waitForFunction(() => window.fixtureReady === true);
      await read(page, "안내 중: maintenance");
    }
    await page.goForward();
    await page.waitForLoadState("domcontentloaded");
    assert.equal(await page.locator("main[data-notice-id]").count(), 1);
    // Recovery: operator turns the notice off; the viewer reloads and reads normally again.
    await change(false, etag, "browser-recovery");
    const restored = await page.goto(host.origin);
    assert.equal(restored.status(), 200);
    await page.waitForFunction(() => window.fixtureReady === true);
    await read(page, "합성 v1");
    assert.deepEqual(failures, []);
  } finally { await ensureOff(); await context.close(); }
});
test("operator token never reaches the browser and the switch key is not a public file", async () => {
  await ensureOff();
  const context = await browser.newContext();
  try {
    const page = await context.newPage(); await page.goto(host.origin);
    assert.equal(await page.evaluate(() => Object.keys(window).some(k => /token/i.test(k))), false);
    for (const route of ["/v1/_notice/state.json", "/_notice/v1/state", "/_notice"]) {
      const r = await page.request.get(host.origin + route);
      assert.ok([401, 404].includes(r.status()), route + " " + r.status());
      assert.doesNotMatch(await r.text(), /<!doctype/i);
    }
  } finally { await context.close(); }
});

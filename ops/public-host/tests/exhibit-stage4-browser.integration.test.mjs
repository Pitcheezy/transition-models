// Opt-in real Chrome + our real gateway in ephemeral loopback Miniflare.
// The front end below is explicitly SYNTHETIC; no partner build, Cloudflare account or external service is used.
import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readdir, readFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { createRequire } from "node:module";
import { fileURLToPath } from "node:url";
import { startLocalHost } from "../rehearsal/local-host.mjs";
import { makeAssets } from "../exhibit-site.mjs";
import { openStage4Browser } from "../exhibit-stage4-browser.mjs";

const VERSION = "12345678-1234-1234-1234-123456789abc";
const require = createRequire(import.meta.url);
const fixtureJs = `
let busy=false;
function ready(){document.querySelector('#root').innerHTML='<p>SYNTHETIC lifecycle fixture</p><div class="sv-reclist">실제 투구 · 1구 · Pete Crow-Armstrong</div><button class="sv-atbat-toggle">Synthetic</button><svg width="10" height="10"></svg>';}
function held(){document.querySelector('#root').innerHTML='<p>서비스 점검 중이에요. 잠시 후 다시 확인해 주세요.</p>';}
async function tick(){if(busy)return;busy=true;try{
  const health=await fetch('/v1/health.json',{cache:'no-store'});await health.arrayBuffer();
  if(health.status===503&&health.headers.has('X-Pitcheezy-Notice')){held();return;}
  if(health.status!==200)return;
  const response=await fetch('/v1/game/849843.json',{cache:'no-store'});await response.arrayBuffer();
  if(response.status===503&&response.headers.has('X-Pitcheezy-Notice'))held();
  else if(response.status===200)ready();
  // General errors deliberately keep the previous held view: this tests the harness lifecycle only.
}finally{busy=false;}}
tick();setInterval(tick,1000);
`;

test("synthetic loopback lifecycle: auth, real polling, local notice, intercepted error, same-document restore and logout", {
  skip: process.env.PITCHEEZY_STAGE4_BROWSER_INTEGRATION !== "1", timeout: 60000,
}, async t => {
  const parent = await mkdtemp(join(tmpdir(), "pz-stage4-browser-integration-"));
  let host, browser, session, currentEtag = null;
  t.after(async () => {
    if (session) await session.close().catch(() => {});
    if (browser) await browser.close();
    if (host) await host.dispose();
    await rm(parent, { recursive: true, force: true });
  });
  const source = {
    "index.html": '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>SYNTHETIC stage4 lifecycle</title><link rel="stylesheet" href="/assets/index-ks_hu7Ji.css"><link rel="icon" href="/favicon.svg"><div id="root"></div><script type="module" src="/assets/index-X1sSTTQ4.js"></script></html>',
    "assets/index-X1sSTTQ4.js": fixtureJs,
    "assets/index-ks_hu7Ji.css": "body{margin:0}svg{display:block}",
    "favicon.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 10 10"/>',
  };
  const files = new Map(Object.entries(source).map(([path, text]) => [path, { bytes: Buffer.from(text) }]));
  host = await startLocalHost({ notice: true, access: {}, assets: makeAssets(files, [...files.keys()]) });
  assert.equal(new URL(host.origin).hostname, "127.0.0.1");
  for (const path of ["/v1/health.json", "/v1/game/849843.json"]) {
    const put = await host.publish(path, JSON.stringify({ synthetic: true }));
    await put.arrayBuffer(); assert.equal(put.status, 200);
  }
  const modulePath = process.env.PLAYWRIGHT_MODULE || fileURLToPath(new URL("../../../tests/browser/node_modules/playwright", import.meta.url));
  browser = await require(modulePath).chromium.launch({ headless: true, channel: "chrome" });
  session = await openStage4Browser({ browser, origin: host.origin, accessCode: host.accessCodes[0],
    outDir: join(parent, "browser"), versionPin: VERSION, allowLoopback: true });
  const normal = await session.sampleNormal(2200);
  assert.equal(normal.passed, true); assert.ok(normal.game_reads > 0); assert.ok(normal.health_reads > 0);
  async function notice(active) {
    const result = await host.setNotice({ active, operator: "synthetic-stage4", reason: "local lifecycle test", message_id: "maintenance" }, currentEtag);
    currentEtag = result.headers.get("ETag"); await result.arrayBuffer(); assert.equal(result.status, 200);
  }
  await notice(true);
  await session.waitHidden(10000);
  session.setSyntheticGameError(true);
  await session.waitSyntheticGameError(10000);
  await session.assertHidden();
  session.setSyntheticGameError(false);
  await notice(false);
  const restored = await session.waitRestored(10000);
  assert.equal(restored.passed, true);
  const result = await session.close();
  assert.equal(result.fatal, null); assert.equal(result.logged_out, true);
  assert.equal(result.incomplete_or_failed, 0); assert.ok(result.synthetic_responses >= 1);
  assert.ok(result.requests <= 180); assert.equal(result.real_phone, false);
  const logDir = join(parent, "browser");
  const rows = await Promise.all((await readdir(logDir)).filter(path => /^request-\d+\.completed/.test(path))
    .map(async path => JSON.parse(await readFile(join(logDir, path), "utf8"))));
  assert.equal(rows.filter(row => row.method === "POST" && row.path === "/_access/v1/session" && row.status === 200).length, 1);
  assert.equal(rows.filter(row => row.method === "DELETE" && row.path === "/_access/v1/session" && row.status === 204).length, 1);
  const text = (await Promise.all((await readdir(logDir)).map(path => readFile(join(logDir, path), "utf8")))).join("");
  assert.equal(text.includes(host.accessCodes[0]), false); assert.equal(text.includes(host.origin), false);
});

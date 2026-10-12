"use strict";
// WS-ops2: Song's built public screen (pinned commit, read-only build) reading Song's delivered examples through OUR local Worker.
// Needs two local directories that are not in this repository; without them every check is skipped and reported as skipped.
//   PZ_FIRST_CONNECTION_EXAMPLES = directory holding examples/ and schema/ from svc/ws-publisher@d5a1dd9
//   PZ_FIRST_CONNECTION_DIST     = apps/observer/web/dist-public built from svc/ws-static-web@ef4e4df (static mode)
//   PZ_FIRST_CONNECTION_RECEIPT  = optional path for a JSON receipt (new file only)
// Phase A uploads the untouched examples (pack hashes). Their 2026-10-05 publish times make the screen show "갱신 지연",
// which is the publish-stop signal. Phase B uploads time-shifted copies (publish time = now) so the state labels are
// visible; the pack allows this as a separate test artefact and the receipt records the shifted hashes.
const { test, before, after } = require("node:test");
const assert = require("node:assert/strict");
const path = require("node:path");
const fs = require("node:fs");
const { pathToFileURL } = require("node:url");
const playwright = require("playwright");
const ROOT = path.resolve(__dirname, "../..");
const ENGINE = process.env.BROWSER_ENGINE || "chromium";
const EXAMPLES = process.env.PZ_FIRST_CONNECTION_EXAMPLES;
const DIST = process.env.PZ_FIRST_CONNECTION_DIST;
const RECEIPT = process.env.PZ_FIRST_CONNECTION_RECEIPT;
const READY = Boolean(EXAMPLES && DIST && fs.existsSync(EXAMPLES) && fs.existsSync(DIST));
const SKIP = !READY && "set PZ_FIRST_CONNECTION_EXAMPLES and PZ_FIRST_CONNECTION_DIST";
let host, browser, mod;
const receipt = { schema: "pitcheezy-first-connection-screen-receipt-v1", engine: ENGINE, synthetic: true, live_data: false,
  examples_commit: "d5a1dd98003672235cc50509391fd4c41b28be32", screen_commit: "ef4e4df2f0547331459f9d952c5d76e1090f11e8",
  checks: [], shifted_artifacts: [], api_requests: [], v1_requests: [] };
function saveReceipt() {
  if (!RECEIPT) return;
  try { fs.writeFileSync(RECEIPT, JSON.stringify(receipt, null, 2) + "\n", { flag: "wx" }); }
  catch (error) { receipt.receipt_error = error.code || "write_failed"; }
}
before(async () => {
  if (!READY) return;
  mod = await import(pathToFileURL(path.join(ROOT, "ops/public-host/rehearse-first-connection.mjs")).href);
  host = await mod.startFirstConnectionHost({ examples: EXAMPLES, dist: DIST });
  for (const file of ["examples/manifest-live.json", "examples/dates.json", "examples/games-live.json", "examples/games-archive.json",
    "examples/game-pregame.json", "examples/game-final-archive.json", "examples/setup.json", "examples/health-live.json"]) await host.upload(file);
  browser = await playwright[ENGINE].launch({ headless: true, ...(process.env.BROWSER_CHANNEL ? { channel: process.env.BROWSER_CHANNEL } : {}) });
});
after(async () => {
  try { await browser?.close(); } finally { saveReceipt(); await host?.dispose(); }
});
const record = (name, ok, detail = {}) => { receipt.checks.push({ name, ok, ...detail }); assert.ok(ok, name + " " + JSON.stringify(detail)); };
function watch(page) {
  page.on("request", r => {
    const u = new URL(r.url());
    if (u.pathname.startsWith("/api")) receipt.api_requests.push(u.pathname);
    if (u.pathname.startsWith("/v1")) receipt.v1_requests.push(u.pathname);
  });
}
async function open(context, query) {
  const page = await context.newPage();
  watch(page);
  const response = await page.goto(host.origin + "/" + query, { waitUntil: "domcontentloaded" });
  return { page, status: response.status() };
}
const hasText = (page, text) => page.evaluate(t => document.body.innerText.includes(t), text);
async function waitText(page, text, timeout = 20000) {
  await page.waitForFunction(t => document.body.innerText.includes(t), text, { timeout });
}
const now = () => new Date().toISOString().replace(/\.\d{3}Z$/, "Z");

test("phase A: untouched examples render the list cards and the publish-stop notice; only v1 files are requested", { skip: SKIP, timeout: 60000 }, async () => {
  const context = await browser.newContext({ viewport: { width: 375, height: 740 } });
  try {
    const { page, status } = await open(context, "?date=2026-10-05");
    record("list_page_served", status === 200, { status });
    await waitText(page, "LIVE"); await waitText(page, "Club");
    record("live_card_visible", true, { date: "2026-10-05", game_pk: 900200 });
    await waitText(page, "갱신 지연");
    record("stale_notice_with_original_publish_times", true, { note: "examples carry 2026-10-05 publish times; the screen flags the stopped publication" });
    const archive = await open(context, "?date=2026-09-30");
    await waitText(archive.page, "Club");
    record("archive_card_visible", true, { date: "2026-09-30", game_pk: 900101 });
    const game = await open(context, "?game=900200");
    await waitText(game.page, "예정"); await waitText(game.page, "갱신 지연");
    record("pregame_original_shows_scheduled_and_stale", true);
    record("no_api_requests_phase_a", receipt.api_requests.length === 0, { count: receipt.api_requests.length });
    record("v1_files_requested", ["/v1/dates.json", "/v1/manifest.json", "/v1/games/2026-10-05.json", "/v1/health.json", "/v1/game/900200.json"].every(p => receipt.v1_requests.includes(p)),
      { seen: [...new Set(receipt.v1_requests)] });
  } finally { await context.close(); }
});

test("phase B: time-shifted copies show each state label in order, then a stopped publication turns into 갱신 지연", { skip: SKIP, timeout: 180000 }, async () => {
  const context = await browser.newContext({ viewport: { width: 375, height: 740 } });
  try {
    const refresh = async (file) => {
      const health = await host.uploadShifted("examples/health-live.json", now());
      const game = await host.uploadShifted(file, now());
      receipt.shifted_artifacts.push({ example: file, target: game.target, shifted_sha256: game.shifted_sha256, original_sha256: game.original_sha256, published_at: game.published_at });
      receipt.shifted_artifacts.push({ example: "examples/health-live.json", target: health.target, shifted_sha256: health.shifted_sha256, original_sha256: health.original_sha256, published_at: health.published_at });
    };
    await refresh("examples/game-pregame.json");
    const { page, status } = await open(context, "?game=900200");
    record("game_page_served", status === 200, { status });
    await waitText(page, "경기 전", 30000);
    record("state_pregame", !(await hasText(page, "갱신 지연")), { label: "경기 전" });
    const sequence = [["examples/game-live.json", "다음 공 추천", "recommended"], ["examples/game-live-unconfirmed.json", "확인 중", "unconfirmed"],
      ["examples/game-disconnected.json", "연결 끊김", "disconnected"], ["examples/game-between-innings.json", "공수 교대", "waiting"]];
    for (const [file, label, state] of sequence) {
      await refresh(file);
      const started = Date.now();
      await waitText(page, label, 40000);
      record("state_" + state, true, { label, seconds_until_shown: Math.round((Date.now() - started) / 100) / 10 });
    }
    // Stop refreshing while the game is still live: the screen must flag the stopped publication on its own (threshold is provisional).
    const started = Date.now();
    await waitText(page, "갱신 지연", 90000);
    record("stopped_publication_flagged_while_live", true, { seconds_until_flagged: Math.round((Date.now() - started) / 100) / 10, note: "threshold VITE_PUBLISH_STALE_S=30 is provisional per the pack" });
    await refresh("examples/game-final.json");
    const finalStarted = Date.now();
    await waitText(page, "경기가 끝났어요", 40000);
    record("state_final", true, { label: "경기가 끝났어요", seconds_until_shown: Math.round((Date.now() - finalStarted) / 100) / 10 });
    await page.waitForTimeout(5000);
    receipt.checks.push({ name: "stale_notice_after_final", ok: true, observed: await hasText(page, "갱신 지연"), note: "a finished game needs no further publication; observed only" });
    record("no_api_requests_phase_b", receipt.api_requests.length === 0, { count: receipt.api_requests.length });
    record("fits_mobile_width", await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth));
  } finally { await context.close(); }
});

test("phase C: the archive game shows 경기 종료, setup is never requested, and a withdrawn file is gone for the screen", { skip: SKIP, timeout: 60000 }, async () => {
  const context = await browser.newContext();
  try {
    const requested = [];
    const page = await context.newPage();
    watch(page);
    page.on("request", r => requested.push(new URL(r.url()).pathname));
    await page.goto(host.origin + "/?game=900101", { waitUntil: "domcontentloaded" });
    await waitText(page, "종료", 30000);
    record("archive_game_final_visible", true, { label: "종료" });
    await page.waitForTimeout(3000);
    record("setup_file_not_requested", !requested.some(p => p.startsWith("/v1/setup/")), { v1: [...new Set(requested.filter(p => p.startsWith("/v1/")))] });
    await host.withdraw("v1/game/900101.json");
    const r = await page.request.get(host.origin + "/v1/game/900101.json");
    record("withdrawn_file_404_for_screen_fetch", r.status() === 404, { status: r.status() });
    record("no_api_requests_phase_c", receipt.api_requests.length === 0, { count: receipt.api_requests.length });
  } finally { await context.close(); }
});

/**
 * EXHIBIT-host1 local rehearsal: the received exhibition build installed the way OUR host contract requires.
 * The 4 static front-end files go through the ASSETS binding; the v1 data files go through the authenticated
 * /_publish route (stored as pitcheezy-host-record-v1) and are read back through the public /v1 route of our
 * real gateway, in an ephemeral loopback Miniflare. Not Cloudflare, no real domain, no network beyond 127.0.0.1.
 * Partner files are read only; a failure on our gateway is recorded, never patched. Game files are moved as bytes.
 */
import { readFile, lstat, mkdir, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { createRequire } from "node:module";
import { startLocalHost, boundedCleanup } from "./rehearsal/local-host.mjs";
import { NOTICE_CACHE_MS, NOTICE_HEADER } from "./notice.mjs";
import { ACCESS_HEADER } from "./access.mjs";
// Receipt validation, byte check, classification and the ASSETS emulation live in exhibit-site.mjs (no Miniflare import)
// so the deploy-day tools can run without ops/public-host/node_modules; they are re-exported here unchanged.
import { validateIntakeReceipt, verifySite, classifySite, makeAssets, prepareSite, EXHIBIT_GAME, CONTENT_TYPES, hash } from "./exhibit-site.mjs";
export { validateIntakeReceipt, verifySite, classifySite, makeAssets, prepareSite, EXHIBIT_GAME, hash };

const require = createRequire(import.meta.url);
const fail = (code, path = null) => { throw Object.assign(new Error(code), path ? { path } : {}); };
const need = (value, code, path = null) => { if (!value) fail(code, path); };
const sleep = ms => new Promise(r => setTimeout(r, ms));
export const SCHEMA = "pitcheezy-exhibit-host-local-v1";
const FIRST_PITCH_TEXT = "실제 투구 · 1구 · Pete Crow-Armstrong";
const NOTICE_TEXT = "자료를 확인하고 있어요";
const VIEWPORTS = [[1440, 900], [390, 844]];
const NOTICE_WAIT_MS = 10000; // Node-side switch latency bound (memo window is NOTICE_CACHE_MS).
const BROWSER_WAIT_MS = 40000; // The partner app polls about every 10 s.

async function sourceReceipt() {
  const files = ["worker.mjs", "gateway.mjs", "notice.mjs", "access.mjs", "telemetry.mjs",
    "rehearsal/local-host.mjs", "exhibit-site.mjs", "rehearse-exhibit-host.mjs", "package-lock.json"];
  const values = {};
  for (const name of files) values[name] = hash(await readFile(new URL(name, import.meta.url)));
  return values;
}

async function waitUntil(condition, timeoutMs, intervalMs) {
  const start = performance.now();
  while (true) {
    if (await condition()) return Math.round(performance.now() - start);
    if (performance.now() - start >= timeoutMs) return null;
    await sleep(intervalMs);
  }
}

export async function runExhibitHostRehearsal({ site, receipt, out, browser = false, access = false, playwright = null,
  expectData = null, game = EXHIBIT_GAME, deadlineMs = 600000, prepared = null } = {}) {
  const controller = new AbortController();
  const deadline = setTimeout(() => controller.abort(), deadlineMs);
  const start = performance.now();
  const checks = [];
  const check = (name, passed, detail = undefined) => { checks.push({ name, passed: Boolean(passed), ...(detail === undefined ? {} : { detail }) }); return Boolean(passed); };
  let host = null, chrome = null, phase = "prepare", noticeEtag = null, report;
  try {
    const { intake, files, classified } = prepared || await prepareSite({ site, receipt, expectData, game });
    const missingDate = intake.catalogue.missing_date_files[0] ?? null;
    report = {
      schema: SCHEMA, evidence_kind: "loopback_miniflare_our_gateway", target: "ephemeral-loopback-miniflare",
      source_commit: intake.source_commit, intake_zip_sha256: intake.zip?.sha256 ?? null, exhibit_game: String(game),
      environment: { node: process.version, platform: process.platform, arch: process.arch, miniflare: require("miniflare/package.json").version, browser: null },
      gateway_sha256: await sourceReceipt(),
      counts: { site_files: files.size, static: classified.static.length, data: classified.data.length,
        site_bytes: [...files.values()].reduce((n, f) => n + f.bytes.length, 0) },
      install: { static: "ASSETS binding (emulated static assets, SPA fallback)", data: "/_publish PUT, If-None-Match: *, pitcheezy-host-record-v1",
        upload_order: ["setup", "game", "games", "dates", "manifest", "health"] },
      files: [], static_emulation: {}, negative: {}, notice: {}, browser: null, access: null,
      checks, passed: false, pass: 0, fail: 0,
      limitations: [
        "Loopback Miniflare/workerd with our real worker/gateway/notice/access code; not Cloudflare, no CDN, no TLS, no real domain, no edge cache.",
        "ASSETS is emulated in Node (exact path, '/' => index.html, HTML-accepting miss => index.html); Cloudflare asset headers/redirects are not emulated.",
        "Browser checks are headless installed Chrome at two viewports; no physical phones or Safari.",
        "Date files the build advertises but does not include stay missing (404 observed, not corrected).",
        "Partner files were read only and uploaded as bytes; game files were not analysed (849844 is evaluation-locked).",
        "Notice wording is the unapproved development placeholder; the public wording is a human decision.",
        "Loopback http uses the unprefixed viewer cookie without Secure; production https uses __Host- and Secure.",
      ],
    };
    // Phase: host with the partner front end installed as static assets.
    phase = "start";
    host = await startLocalHost({ signal: controller.signal, notice: true, access: access ? {} : null, assets: makeAssets(files, classified.static) });
    report.startup_ms = Math.round(performance.now() - start);
    let nodeCookie = null;
    if (access) {
      const opened = await host.login(host.accessCodes[0]);
      check("access:node_json_login", opened.status === 200 && /^pz_viewer=v3\./.test(opened.headers.get("Set-Cookie") || ""), { status: opened.status });
      nodeCookie = (opened.headers.get("Set-Cookie") || "").split(";")[0]; await opened.arrayBuffer();
    }
    const get = (path, init = {}, { cookie = nodeCookie } = {}) => fetch(host.origin + path, {
      ...init, redirect: "manual", cache: "no-store", signal: AbortSignal.any([controller.signal, AbortSignal.timeout(15000)]),
      headers: { ...(cookie ? { Cookie: cookie } : {}), ...(init.headers || {}) },
    });
    const body = async r => Buffer.from(await r.arrayBuffer());

    // Phase: upload the data files through our real authenticated route, then read every path back.
    phase = "upload";
    const rows = new Map();
    for (const key of classified.data) {
      const { bytes, sha256 } = files.get(key);
      const put = await host.publish("/" + key, bytes);
      const text = await put.text();
      let echoed = null; try { echoed = JSON.parse(text); } catch { echoed = null; }
      const row = { path: key, kind: "data", bytes: bytes.length, sha256, upload_status: put.status,
        etag_returned: put.headers.get("ETag") !== null, stored_echo_sha256_equal: echoed?.stored === true && echoed?.sha256 === sha256,
        readback_status: null, readback_equal: null };
      rows.set(key, row); report.files.push(row);
      check("upload:" + key, put.status === 200 && row.etag_returned && row.stored_echo_sha256_equal, { status: put.status });
    }
    phase = "readback";
    for (const key of classified.data) {
      const row = rows.get(key);
      const r = await get("/" + key);
      const got = await body(r);
      row.readback_status = r.status; row.readback_equal = r.status === 200 && hash(got) === row.sha256 && got.length === row.bytes;
      row.readback_content_type = r.headers.get("Content-Type"); row.readback_etag_present = r.headers.get("ETag") !== null;
      check("readback:" + key, row.readback_equal && r.headers.get("Cache-Control") === "no-store, no-transform" && row.readback_etag_present,
        { status: r.status, bytes: got.length });
    }
    for (const path of classified.static) {
      const { bytes, sha256 } = files.get(path);
      const r = await get("/" + path);
      const got = await body(r);
      const row = { path, kind: "static", bytes: bytes.length, sha256, upload_status: null, readback_status: r.status,
        readback_equal: r.status === 200 && hash(got) === sha256, readback_content_type: r.headers.get("Content-Type") };
      report.files.push(row);
      check("static:" + path, row.readback_equal && (r.headers.get("Content-Type") || "").startsWith(CONTENT_TYPES[path === "index.html" ? "html" : path === "favicon.svg" ? "svg" : path.endsWith(".js") ? "js" : "css"].split(";")[0]),
        { status: r.status, content_type: row.readback_content_type });
    }
    const root = await get("/"); const rootBytes = await body(root);
    check("static:root_is_index", root.status === 200 && hash(rootBytes) === files.get("index.html").sha256, { status: root.status });
    const spa = await get("/some/app/route", { headers: { Accept: "text/html,application/xhtml+xml" } }); const spaBytes = await body(spa);
    const miss = await get("/missing-asset.png", { headers: { Accept: "image/avif,image/webp,*/*" } }); await miss.arrayBuffer();
    const nav = await get("/?game=" + game, { headers: { Accept: "text/html" } }); const navBytes = await body(nav);
    report.static_emulation = { root_status: root.status, spa_fallback_status: spa.status, unknown_asset_status: miss.status, query_entry_status: nav.status,
      note: "Node emulation of Cloudflare static assets; the gateway blocks /api, /_*, dotted segments and /v1 before ASSETS." };
    check("static:spa_fallback_serves_index", spa.status === 200 && hash(spaBytes) === files.get("index.html").sha256);
    check("static:unknown_asset_404", miss.status === 404);
    check("static:query_entry_serves_index", nav.status === 200 && hash(navBytes) === files.get("index.html").sha256);

    // Phase: negative checks on our gateway with the partner data installed.
    phase = "negative";
    const absent = await get("/v1/game/999999.json"); await absent.arrayBuffer();
    report.negative.unknown_game_status = absent.status;
    check("negative:unknown_game_404", absent.status === 404);
    if (missingDate) {
      const date = await get(`/v1/games/${missingDate}.json`); await date.arrayBuffer();
      report.negative.missing_advertised_date = { date: missingDate, status: date.status };
      check("negative:missing_advertised_date_404", date.status === 404);
    } else report.negative.missing_advertised_date = { date: null, status: null, note: "receipt lists no missing date files" };
    const manifest = files.get("v1/manifest.json");
    const unauth = await fetch(host.origin + "/_publish/v1/manifest.json", { method: "PUT", body: manifest.bytes, redirect: "error",
      headers: { "Content-Type": "application/json", "X-Content-SHA256": manifest.sha256, "If-None-Match": "*" }, signal: AbortSignal.timeout(15000) });
    await unauth.arrayBuffer();
    report.negative.unauthenticated_put_status = unauth.status;
    check("negative:unauthenticated_put_401", unauth.status === 401);
    const again = await host.publish("/v1/manifest.json", manifest.bytes); await again.arrayBuffer();
    report.negative.repeat_create_status = again.status;
    check("negative:repeat_create_412", again.status === 412);
    const after = await get("/v1/manifest.json"); const afterBytes = await body(after);
    check("negative:repeat_create_keeps_bytes", after.status === 200 && hash(afterBytes) === manifest.sha256);
    if (access) {
      const locked = await get("/v1/manifest.json", {}, { cookie: null }); await locked.arrayBuffer();
      const lockedPage = await get("/", {}, { cookie: null }); const lockedHtml = await lockedPage.text();
      report.negative.without_cookie = { data_status: locked.status, page_status: lockedPage.status, access_header: locked.headers.get(ACCESS_HEADER) };
      check("access:node_data_without_cookie_401", locked.status === 401 && locked.headers.get(ACCESS_HEADER) === "required");
      check("access:node_page_without_cookie_login", lockedPage.status === 401 && lockedHtml.includes('data-access-gate="on"'));
      const wrong = await host.login("synthetic-wrong-code-0000"); await wrong.arrayBuffer();
      check("access:node_wrong_code_401", wrong.status === 401 && wrong.headers.get("Set-Cookie") === null);
    }

    // Phase: real notice switch through /_notice, observed on the game file and the page.
    phase = "notice";
    const gamePath = `/v1/game/${game}.json`;
    const noticeActive = async path => { const r = await get(path); await r.arrayBuffer(); return r.status === 503 && r.headers.get(NOTICE_HEADER) !== null; };
    await (await get(gamePath)).arrayBuffer(); // Warm the per-isolate memo so the latency includes the cache window.
    const on = await host.setNotice({ active: true, operator: "local-rehearsal", reason: "EXHIBIT-host1 local rehearsal", message_id: "data_hold" }, noticeEtag);
    noticeEtag = on.headers.get("ETag"); await on.arrayBuffer();
    check("notice:switch_on_200", on.status === 200 && noticeEtag !== null, { status: on.status });
    const onMs = await waitUntil(() => noticeActive(gamePath), NOTICE_WAIT_MS, 100);
    const gameOn = await get(gamePath); const gameOnText = await gameOn.text();
    const pageOn = await get("/"); const pageOnText = await pageOn.text();
    report.notice.on = { game_status: gameOn.status, game_notice_header: gameOn.headers.get(NOTICE_HEADER), page_status: pageOn.status,
      page_content_type: pageOn.headers.get("Content-Type"), page_notice_header: pageOn.headers.get(NOTICE_HEADER), first_503_after_ms: onMs, memo_window_ms: NOTICE_CACHE_MS };
    check("notice:game_503_with_header", gameOn.status === 503 && gameOn.headers.get(NOTICE_HEADER) === "data_hold" && (() => { try { return JSON.parse(gameOnText).error === "service_notice"; } catch { return false; } })());
    check("notice:page_503_html", pageOn.status === 503 && (pageOn.headers.get("Content-Type") || "").startsWith("text/html") && pageOnText.includes('data-notice-id="data_hold"'));
    check("notice:reason_not_leaked", !gameOnText.includes("local rehearsal") && !pageOnText.includes("local rehearsal") && !gameOnText.includes("local-rehearsal"));
    const off = await host.setNotice({ active: false, operator: "local-rehearsal", reason: "EXHIBIT-host1 local rehearsal", message_id: "data_hold" }, noticeEtag);
    noticeEtag = off.headers.get("ETag"); await off.arrayBuffer();
    check("notice:switch_off_200", off.status === 200 && noticeEtag !== null, { status: off.status });
    const offMs = await waitUntil(async () => !(await noticeActive(gamePath)), NOTICE_WAIT_MS, 100);
    const gameOff = await get(gamePath); const gameOffBytes = await body(gameOff);
    const pageOff = await get("/"); const pageOffBytes = await body(pageOff);
    report.notice.off = { game_status: gameOff.status, page_status: pageOff.status, first_200_after_ms: offMs };
    check("notice:game_200_bytes_restored", gameOff.status === 200 && hash(gameOffBytes) === files.get(`v1/game/${game}.json`).sha256);
    check("notice:page_200_restored", pageOff.status === 200 && hash(pageOffBytes) === files.get("index.html").sha256);

    // Phase: the partner app in installed Chrome against our gateway (optional).
    if (browser) {
      phase = "browser";
      const modulePath = playwright || process.env.PLAYWRIGHT_MODULE || "playwright";
      const pw = require(modulePath);
      chrome = await pw.chromium.launch({ headless: true, channel: "chrome" });
      report.environment.browser = "installed Chrome headless " + chrome.version() + " via Playwright " + require(modulePath.replace(/\\/g, "/") + "/package.json").version;
      report.browser = { viewports: [], notice: {}, missing_date_observation: null };
      if (access) report.access = { browser: [] };
      const views = [];
      for (const [width, height] of VIEWPORTS) {
        const label = `${width}x${height}`;
        const context = await chrome.newContext({ viewport: { width, height } });
        const page = await context.newPage();
        const view = { label, page, context, errors: [], blocked: [], responses: [] };
        page.on("pageerror", e => view.errors.push(String(e?.message || e).slice(0, 300)));
        page.on("response", r => { const u = new URL(r.url()); if (u.origin === host.origin && view.responses.length < 400) view.responses.push({ path: u.pathname, query: u.search || null, status: r.status() }); });
        await page.route("**/*", route => {
          const origin = new URL(route.request().url()).origin;
          if (origin === host.origin) return route.continue();
          if (view.blocked.length < 50) view.blocked.push(origin);
          return route.abort();
        });
        if (access) {
          // Gate first: '/' must be the login page, then the code goes through the real form (never printed or stored).
          const first = await page.goto(host.origin + "/", { waitUntil: "load" });
          const loginShown = (await page.locator('main[data-access-gate="on"]').count()) === 1;
          await page.screenshot({ path: join(out, `access-login-${label}.png`), fullPage: true });
          check(`access:${label}:root_401_login_page`, first?.status() === 401 && loginShown, { status: first?.status() ?? null });
          await page.fill("#code", host.accessCodes[0]);
          // The 401 page already sits at "/", so wait for the GET "/" that follows the form's 303, not for the URL.
          await Promise.all([
            page.waitForResponse(r => r.url() === host.origin + "/" && r.request().method() === "GET", { timeout: 15000 }),
            page.click('button[type="submit"]'),
          ]);
          await page.waitForLoadState("load");
          const landed = view.responses.filter(r => r.path === "/").map(r => r.status);
          const appRoot = (await page.locator("#root").count()) === 1 && (await page.locator('main[data-access-gate="on"]').count()) === 0;
          const cookies = (await context.cookies(host.origin)).filter(c => c.name === "pz_viewer").map(c => ({ name: c.name, httpOnly: c.httpOnly, sameSite: c.sameSite, path: c.path }));
          check(`access:${label}:form_login_lands_on_app`, appRoot && landed.includes(200) && cookies.length === 1, { root_statuses: landed, cookie: cookies[0] ?? null });
          report.access.browser.push({ viewport: label, login_page_status: first?.status() ?? null, root_statuses_after_login: landed, cookie: cookies[0] ?? null });
        }
        const entry = await page.goto(host.origin + "/?game=" + game, { waitUntil: "load" });
        const reclist = await page.locator(".sv-reclist").waitFor({ timeout: 20000 }).then(() => true, () => false);
        const text = reclist ? await page.locator("body").innerText() : "";
        const overflow = await page.evaluate(() => document.documentElement.scrollWidth > window.innerWidth);
        await page.screenshot({ path: join(out, `game-${game}-${label}.png`), fullPage: true });
        check(`browser:${label}:reclist_rendered`, reclist, { entry_status: entry?.status() ?? null });
        check(`browser:${label}:first_pitch_text`, text.includes(FIRST_PITCH_TEXT));
        check(`browser:${label}:no_horizontal_overflow`, !overflow);
        const gameReads = view.responses.filter(r => r.path === gamePath).map(r => r.status);
        check(`browser:${label}:game_file_read_200`, gameReads.includes(200), { statuses: gameReads });
        await page.evaluate(() => { window.__pzRehearsalMarker = "set"; });
        view.record = { viewport: label, entry_status: entry?.status() ?? null, reclist_rendered: reclist, first_pitch_text: text.includes(FIRST_PITCH_TEXT),
          horizontal_overflow: overflow, game_file_statuses: gameReads, blocked_external_origins: [...new Set(view.blocked)] };
        views.push(view);
      }
      // Real switch ON: the app must hide the recommendation list and show its notice text without reload.
      const onB = await host.setNotice({ active: true, operator: "local-rehearsal", reason: "EXHIBIT-host1 browser rehearsal", message_id: "data_hold" }, noticeEtag);
      noticeEtag = onB.headers.get("ETag"); await onB.arrayBuffer();
      check("browser:notice_switch_on_200", onB.status === 200 && noticeEtag !== null, { status: onB.status });
      const t0 = performance.now();
      for (const view of views) {
        const ms = await waitUntil(async () => (await view.page.locator(".sv-reclist").count()) === 0 && (await view.page.locator("body").innerText()).includes(NOTICE_TEXT), BROWSER_WAIT_MS, 500);
        await view.page.screenshot({ path: join(out, `notice-${view.label}.png`), fullPage: true });
        const hidden = (await view.page.locator(".sv-reclist").count()) === 0 && (await view.page.locator(".sv-atbat-toggle").count()) === 0 && (await view.page.locator("svg").count()) === 0;
        view.record.notice_on = { hidden_after_ms: ms === null ? null : Math.round(performance.now() - t0), reclist_hidden: hidden, notice_text_shown: ms !== null };
        check(`browser:${view.label}:notice_hides_and_shows_text`, ms !== null && hidden, { waited_ms: ms });
      }
      const offB = await host.setNotice({ active: false, operator: "local-rehearsal", reason: "EXHIBIT-host1 browser rehearsal", message_id: "data_hold" }, noticeEtag);
      noticeEtag = offB.headers.get("ETag"); await offB.arrayBuffer();
      check("browser:notice_switch_off_200", offB.status === 200 && noticeEtag !== null, { status: offB.status });
      const t1 = performance.now();
      for (const view of views) {
        const ms = await waitUntil(async () => (await view.page.locator(".sv-reclist").count()) > 0, BROWSER_WAIT_MS, 500);
        const restoredText = ms === null ? "" : await view.page.locator("body").innerText();
        const sameDocument = await view.page.evaluate(() => window.__pzRehearsalMarker === "set");
        await view.page.screenshot({ path: join(out, `restored-${view.label}.png`), fullPage: true });
        view.record.notice_off = { restored_after_ms: ms === null ? null : Math.round(performance.now() - t1), same_document: sameDocument, first_pitch_text: restoredText.includes(FIRST_PITCH_TEXT) };
        check(`browser:${view.label}:restored_without_reload`, ms !== null && sameDocument && restoredText.includes(FIRST_PITCH_TEXT), { waited_ms: ms });
        check(`browser:${view.label}:no_page_errors`, view.errors.length === 0, view.errors.slice(0, 5));
        view.record.page_errors = view.errors.slice(0, 10);
        report.browser.viewports.push(view.record);
      }
      report.browser.notice = { message_id: "data_hold", wait_bound_ms: BROWSER_WAIT_MS, poll_note: "the partner app polls about every 10 s; real time, no clock mocking" };
      // Observation only: what the app shows for an advertised date whose file the build does not include.
      if (missingDate) {
        const page = await views[0].context.newPage();
        const seen = [];
        page.on("response", r => { const u = new URL(r.url()); if (u.origin === host.origin && seen.length < 400) seen.push({ path: u.pathname, status: r.status() }); });
        await page.route("**/*", route => new URL(route.request().url()).origin === host.origin ? route.continue() : route.abort());
        await page.goto(host.origin + "/?date=" + missingDate, { waitUntil: "load" });
        await waitUntil(() => seen.some(r => r.path === `/v1/games/${missingDate}.json`), 10000, 250);
        await page.waitForTimeout(2000);
        const excerpt = (await page.locator("body").innerText()).replace(/\s+/g, " ").trim().slice(0, 400);
        await page.screenshot({ path: join(out, `missing-date-${missingDate}.png`), fullPage: true });
        report.browser.missing_date_observation = { date: missingDate, games_file_status: seen.find(r => r.path === `/v1/games/${missingDate}.json`)?.status ?? null,
          text_excerpt: excerpt, note: "observation, not pass/fail; the build's date list is unchanged" };
        await page.close();
      }
      for (const view of views) await view.context.close();
    } else if (access) {
      // No browser: the real form login is exercised from Node only.
      const form = await host.login(host.accessCodes[0], { form: true }); await form.arrayBuffer();
      report.access = { browser: null, node_form_login: { status: form.status, location: form.headers.get("Location") } };
      check("access:node_form_login_303", form.status === 303 && form.headers.get("Location") === "/");
    }
    phase = "done";
  } catch (error) {
    report ??= { schema: SCHEMA, evidence_kind: "loopback_miniflare_our_gateway", checks, passed: false };
    if (error?.cleanup) report.cleanup = error.cleanup;
    const coded = /^[a-z_]{1,64}$/.test(error?.message || "");
    // Loopback addresses, bearer values and cookies never belong in a receipt; runtime messages are scrubbed and truncated.
    const scrub = text => String(text).replace(/https?:\/\/127\.0\.0\.1:\d+/g, "<origin>").replace(/Bearer [A-Za-z0-9_-]+/g, "Bearer <redacted>").replace(/pz_viewer=[^;\s]+/g, "pz_viewer=<redacted>").slice(0, 300);
    report.failure = { phase, code: controller.signal.aborted ? "deadline" : coded ? error.message : "phase_failed",
      ...(error?.path ? { path: error.path } : {}), ...(coded ? {} : { message: scrub(error?.message || error) }) };
  } finally {
    controller.abort(); clearTimeout(deadline);
    if (chrome) report.browser_cleanup = await boundedCleanup(() => chrome.close(), 15000);
    if (host) report.cleanup = await boundedCleanup(() => host.dispose());
  }
  report.pass = checks.filter(c => c.passed).length;
  report.fail = checks.filter(c => !c.passed).length;
  report.passed = !report.failure && report.fail === 0 && checks.length > 0 && (!host || report.cleanup?.status === "complete") &&
    (!chrome || report.browser_cleanup?.status === "complete");
  if (report.cleanup && report.cleanup.status !== "complete") report.failure ??= { phase: "cleanup", code: report.cleanup.code };
  report.total_ms = Math.round(performance.now() - start);
  return report;
}

export async function main(args) {
  let values;
  try {
    ({ values } = parseArgs({ args, options: { site: { type: "string" }, receipt: { type: "string" }, out: { type: "string" },
      browser: { type: "boolean", default: false }, access: { type: "boolean", default: false }, playwright: { type: "string" },
      "expect-data": { type: "string", default: "24" }, game: { type: "string", default: EXHIBIT_GAME } } }));
    need(values.site && values.receipt && values.out, "arguments_required");
    need(/^[1-9][0-9]{0,3}$/.test(values["expect-data"]), "expect_data_invalid");
    const out = resolve(values.out);
    need(!(await lstat(out).then(() => true, () => false)), "output_exists");
    // Inputs are verified and classified before the output folder or any runtime exists.
    const prepared = await prepareSite({ site: values.site, receipt: values.receipt, expectData: Number(values["expect-data"]), game: values.game });
    await mkdir(out).catch(() => fail("output_not_creatable"));
    values.prepared = prepared;
  } catch (error) {
    const code = /^[a-z_]{1,64}$/.test(error?.message || "") ? error.message : "rehearsal_arguments_or_input_error";
    process.stderr.write(JSON.stringify({ ok: false, code, ...(error?.path ? { path: error.path } : {}) }) + "\n");
    return 2;
  }
  const report = await runExhibitHostRehearsal({ site: values.site, receipt: values.receipt, out: resolve(values.out), browser: values.browser,
    access: values.access, playwright: values.playwright || null, expectData: Number(values["expect-data"]), game: values.game, prepared: values.prepared });
  try { await writeFile(join(resolve(values.out), "receipt.json"), JSON.stringify(report, null, 2) + "\n", { flag: "wx" }); report.receipt_written = true; }
  catch { report.receipt_written = false; }
  process.stdout.write(JSON.stringify(report, null, 2) + "\n");
  return report.passed && report.receipt_written ? 0 : 1;
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await main(process.argv.slice(2));
}

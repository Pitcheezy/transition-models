/** One-tab, bounded exhibition observation. No upload, notice mutation, deployment or CLI. */
import { mkdir, writeFile } from "node:fs/promises";
import { join, resolve } from "node:path";
import { randomUUID } from "node:crypto";

const SESSION = "/_access/v1/session";
const GAME = "/v1/game/849843.json";
const READ_PATHS = new Set(["/", "/favicon.svg", "/assets/index-X1sSTTQ4.js", "/assets/index-ks_hu7Ji.css",
  "/collection-settings.json", "/v1/manifest.json", "/v1/health.json", "/v1/dates.json",
  "/v1/games/2026-09-30.json", GAME, "/v1/setup/849843.json"]);
const fail = code => { throw new Error(code); };
const utc = () => new Date().toISOString();

export function browserRequestPath(origin, address, method) {
  let u; try { u = new URL(address); } catch { return null; }
  if (u.origin !== origin || u.username || u.password || u.hash) return null;
  if (u.pathname === SESSION) return !u.search && ["POST", "DELETE"].includes(method) ? SESSION : null;
  if (!["GET", "HEAD"].includes(method) || !READ_PATHS.has(u.pathname)) return null;
  if (u.search && !(u.pathname === "/" && u.search === "?game=849843")) return null;
  return u.pathname + u.search;
}

/** Only completed requests sent inside the normal observation window count as polling evidence. */
export function summarizeNormalBrowserRows(rows, firstNumber, lastNumber) {
  const selected = rows.filter(row => row.number >= firstNumber && row.number <= lastNumber);
  const complete = selected.filter(row => row.state === "completed");
  const acceptable = row => [200, 304].includes(row.status);
  const goodReads = path => complete.filter(row => row.method === "GET" && row.path === path && acceptable(row)).length;
  const gameReads = goodReads(GAME), healthReads = goodReads("/v1/health.json");
  const statusCounts = {};
  for (const row of complete) statusCounts[String(row.status)] = (statusCounts[String(row.status)] || 0) + 1;
  return { requests: selected.length, completed: complete.length,
    incomplete_or_failed: selected.length - complete.length,
    unexpected_http: complete.filter(row => !acceptable(row)).length,
    game_reads: gameReads, health_reads: healthReads, status_counts: statusCounts,
    passed: selected.length > 0 && complete.length === selected.length && complete.every(acceptable) && gameReads > 0 && healthReads > 0 };
}

/** Private request ledger: credential values, bodies, headers and raw exceptions are never saved. */
export class Stage4BrowserLedger {
  constructor({ origin, outDir, maxRequests = 180, versionPin }) {
    let u; try { u = new URL(origin); } catch { fail("invalid_origin"); }
    if (u.protocol !== "https:" || u.origin !== origin || u.username || u.password) fail("invalid_origin");
    if (!Number.isSafeInteger(maxRequests) || maxRequests < 2 || maxRequests > 180) fail("invalid_budget");
    if (!/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(versionPin || "")) fail("invalid_version_pin");
    this.origin = origin; this.outDir = resolve(outDir); this.limit = maxRequests; this.versionPin = versionPin;
    this.rows = []; this.synthetic = 0; this.blocked = 0; this.fatal = null; this.logoutReservedUsed = false;
  }
  async initialize() {
    await mkdir(this.outDir); // existing output refuses a duplicate run
    await writeFile(join(this.outDir, "browser-started.private.json"), JSON.stringify({ started_at: utc(),
      limit: this.limit, version_pin: this.versionPin, pin_kind: "management_pin_not_server_event_proof" }) + "\n", { flag: "wx", flush: true });
  }
  async begin(address, method, { logout = false, redirected = false } = {}) {
    const path = browserRequestPath(this.origin, address, method);
    if (redirected || !path || (logout && !(path === SESSION && method === "DELETE"))) {
      this.blocked++; this.fatal ??= "unexpected_browser_request"; fail(this.fatal);
    }
    if ((!logout && this.fatal) || (!logout && method === "DELETE") ||
      (logout && this.logoutReservedUsed) || this.rows.length >= (logout ? this.limit : this.limit - 1)) {
      this.blocked++; this.fatal ??= "browser_request_budget_or_stop"; fail(this.fatal);
    }
    if (logout) this.logoutReservedUsed = true;
    const row = { number: this.rows.length + 1, method, path, started_at: utc(), state: "started",
      version_pin: this.versionPin, version_evidence: "management_pin_not_server_event_proof" };
    this.rows.push(row);
    try { await writeFile(this.file(row, "started"), JSON.stringify(row) + "\n", { flag: "wx", flush: true }); }
    catch { this.fatal = "browser_ledger_write_failed"; fail(this.fatal); }
    return row;
  }
  file(row, suffix) { return join(this.outDir, `request-${String(row.number).padStart(3, "0")}.${suffix}.private.json`); }
  async finish(row, { status = null, ray = null, failed = false } = {}) {
    if (row.state !== "started") return;
    row.state = failed ? "transport_failed" : "completed"; row.finished_at = utc();
    row.status = Number.isInteger(status) && status >= 100 && status <= 599 ? status : null;
    row.cf_ray = typeof ray === "string" && /^[a-f0-9]{16,32}-[A-Z]{3}$/i.test(ray) ? ray : null;
    if (failed) this.fatal ??= "browser_transport_failed";
    try { await writeFile(this.file(row, "completed"), JSON.stringify(row) + "\n", { flag: "wx", flush: true }); }
    catch { this.fatal = "browser_ledger_write_failed"; fail(this.fatal); }
  }
  snapshot() {
    return { requests: this.rows.length, limit: this.limit, reserve_for_logout: 1,
      completed: this.rows.filter(r => r.state === "completed").length,
      incomplete_or_failed: this.rows.filter(r => r.state !== "completed").length,
      blocked: this.blocked, synthetic_responses: this.synthetic, fatal: this.fatal,
      version_pin: this.versionPin, version_evidence: "management_pin_not_server_event_proof" };
  }
}

export async function openStage4Browser({ browser, origin, accessCode, outDir, maxRequests = 180, versionPin }) {
  if (typeof accessCode !== "string" || !/^[^\s\p{Cc}]{8,128}$/u.test(accessCode)) fail("invalid_access_code");
  const ledger = new Stage4BrowserLedger({ origin, outDir, maxRequests, versionPin });
  await ledger.initialize();
  let context, page, loggedIn = false, authAttempted = false, closing = false, closed = false, synthetic = false;
  let marker = null, syntheticBaseline = 0; const tickets = new WeakMap(); const pending = new Set(); const measurements = [];
  const noteTask = promise => {
    pending.add(promise);
    promise.catch(() => { ledger.fatal ??= "browser_observer_failed"; }).finally(() => pending.delete(promise));
  };
  const check = () => { if (ledger.fatal) fail(ledger.fatal); };
  const snapshot = () => ({ ...ledger.snapshot(), viewport: { width: 390, height: 844 },
    real_phone: false, logged_out: closed && !loggedIn && !authAttempted, measurements: [...measurements],
    cache_note: "Playwright routing disables browser HTTP cache; this is instrumented single-tab traffic, not capacity or unrestricted-browser proof." });
  const flush = async () => { await Promise.allSettled([...pending]); };
  const close = async () => {
    if (closed) return snapshot(); closing = true; synthetic = false;
    if (page && authAttempted && !page.isClosed()) {
      try {
        const status = await page.evaluate(async path => {
          const r = await fetch(path, { method: "DELETE", credentials: "same-origin", redirect: "manual", signal: AbortSignal.timeout(15000) });
          await r.arrayBuffer(); return r.status;
        }, SESSION);
        if (status === 204) { loggedIn = false; authAttempted = false; }
        else ledger.fatal ??= "browser_logout_failed";
      } catch { ledger.fatal ??= "browser_logout_failed"; }
    }
    if (page && !page.isClosed()) {
      const until = performance.now() + 5000;
      while (ledger.rows.some(row => row.state === "started") && performance.now() < until)
        await page.waitForTimeout(100).catch(() => {});
    }
    if (context) await context.close().catch(() => { ledger.fatal ??= "browser_close_failed"; });
    await flush(); closed = true;
    await writeFile(join(ledger.outDir, "browser-final.private.json"), JSON.stringify(snapshot(), null, 2) + "\n", { flag: "wx", flush: true });
    return snapshot();
  };
  const hidden = async () => page.evaluate(expectedMarker => ({
    hidden: document.querySelectorAll(".sv-reclist,.sv-atbat-toggle,svg").length === 0,
    notice: document.body.innerText.includes("자료를 확인하고 있어요"),
    same_document: window.__pzStage4Marker === expectedMarker,
  }), marker);
  const waitFor = async (label, test, timeoutMs = 120000) => {
    if (!Number.isInteger(timeoutMs) || timeoutMs < 1 || timeoutMs > 120000) fail("invalid_observation_wait");
    const begin = performance.now(), began = utc();
    while (performance.now() - begin <= timeoutMs) {
      check(); if (await test()) {
        const row = { phase: label, started_at: began, observed_at: utc(), elapsed_ms: Math.round(performance.now() - begin), passed: true };
        measurements.push(row); return row;
      }
      await page.waitForTimeout(500); // DOM observation only, no extra HTTP probe
    }
    measurements.push({ phase: label, started_at: began, elapsed_ms: Math.round(performance.now() - begin), passed: false });
    fail("browser_observation_timeout");
  };
  const assertReady = async () => {
    await waitFor("ready", async () => (await page.locator(".sv-reclist").count()) > 0, 20000);
    const result = await page.evaluate(() => ({ first_pitch: document.body.innerText.includes("실제 투구 · 1구 · Pete Crow-Armstrong"),
      overflow: document.documentElement.scrollWidth > window.innerWidth, gate: !!document.querySelector('[data-access-gate="on"]') }));
    if (!result.first_pitch || result.overflow || result.gate) fail("browser_initial_view_failed");
    return result;
  };
  try {
    context = await browser.newContext({ viewport: { width: 390, height: 844 }, serviceWorkers: "block" });
    context.on("page", extra => { if (page && extra !== page) { ledger.fatal ??= "unexpected_extra_tab"; void extra.close().catch(() => {}); } });
    context.on("requestfinished", request => {
      const row = tickets.get(request); if (!row) return;
      noteTask((async () => { const response = await request.response();
        await ledger.finish(row, { status: response?.status(), ray: await response?.headerValue("cf-ray"), failed: !response }); })());
    });
    context.on("requestfailed", request => { const row = tickets.get(request); if (row) noteTask(ledger.finish(row, { failed: true })); });
    await context.route("**/*", async route => {
      const request = route.request(), method = request.method();
      const path = browserRequestPath(origin, request.url(), method);
      try {
        if (synthetic && path === GAME && method === "GET") {
          ledger.synthetic++;
          await writeFile(join(ledger.outDir, `synthetic-${String(ledger.synthetic).padStart(3, "0")}.private.json`),
            JSON.stringify({ observed_at: utc(), method, path, status: 500, evidence_kind: "browser_intercepted_synthetic_response", remote_request: false }) + "\n", { flag: "wx", flush: true });
          await route.fulfill({ status: 500, contentType: "application/json", body: '{"error":"synthetic_stage4_error"}', headers: { "Cache-Control": "no-store" } });
          return;
        }
        if (closing && !(method === "DELETE" && path === SESSION)) { await route.abort(); return; }
        const row = await ledger.begin(request.url(), method, { logout: closing && method === "DELETE", redirected: !!request.redirectedFrom() });
        tickets.set(request, row); await route.continue();
      } catch { ledger.fatal ??= "browser_route_failed"; await route.abort().catch(() => {}); }
    });
    page = await context.newPage();
    page.on("pageerror", () => { ledger.fatal ??= "browser_page_error"; });
    page.setDefaultTimeout(15000);
    const gate = await page.goto(origin + "/", { waitUntil: "load", timeout: 20000 });
    if (gate?.status() !== 401) fail("browser_gate_not_401");
    authAttempted = true;
    const auth = await page.evaluate(async ({ path, code }) => {
      const response = await fetch(path, { method: "POST", credentials: "same-origin", redirect: "manual", signal: AbortSignal.timeout(15000),
        headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }) });
      const status = response.status; await response.arrayBuffer(); return status;
    }, { path: SESSION, code: accessCode });
    if (auth !== 200) fail("browser_login_failed"); loggedIn = true;
    const entry = await page.goto(origin + "/?game=849843", { waitUntil: "load", timeout: 20000 });
    if (entry?.status() !== 200) fail("browser_entry_failed");
    await assertReady(); marker = randomUUID();
    await page.evaluate(value => { window.__pzStage4Marker = value; }, marker);
  } catch (error) {
    await close().catch(() => {});
    fail(/^[a-z_]+$/.test(error?.message || "") ? error.message : "browser_open_failed");
  }
  return {
    assertReady, snapshot, close,
    waitHidden: timeout => waitFor("notice_hidden", async () => { const v = await hidden(); return v.hidden && v.notice && v.same_document; }, timeout),
    waitRestored: timeout => waitFor("notice_restored", async () => (await page.locator(".sv-reclist").count()) > 0 &&
      await page.evaluate(expected => window.__pzStage4Marker === expected && document.body.innerText.includes("실제 투구 · 1구 · Pete Crow-Armstrong"), marker), timeout),
    setSyntheticGameError: value => { if (typeof value !== "boolean") fail("invalid_synthetic_mode"); synthetic = value; syntheticBaseline = ledger.synthetic; },
    waitSyntheticGameError: async timeout => {
      await waitFor("synthetic_error_received", async () => ledger.synthetic > syntheticBaseline, timeout);
      await page.waitForTimeout(1000); check();
      const result = await hidden();
      if (!result.hidden || !result.same_document) fail("browser_stale_content_visible");
      measurements.push({ phase: "synthetic_error_keeps_hidden", observed_at: utc(), passed: true, evidence_kind: "browser_intercepted_synthetic_response" });
      return result;
    },
    assertHidden: async () => { check(); const result = await hidden(); if (!result.hidden || !result.same_document) fail("browser_stale_content_visible"); return result; },
    sampleNormal: async (durationMs = 600000) => {
      if (!Number.isInteger(durationMs) || durationMs < 1 || durationMs > 600000) fail("invalid_sample_duration");
      const begin = performance.now(), started = utc(), count = ledger.rows.length;
      let uiValid = true;
      while (performance.now() - begin < durationMs) {
        check();
        uiValid = await page.evaluate(expected => document.visibilityState === "visible" && window.__pzStage4Marker === expected &&
          !!document.querySelector(".sv-reclist") && !document.querySelector('[data-access-gate="on"]'), marker);
        const responses = summarizeNormalBrowserRows(ledger.rows, count + 1, ledger.rows.length);
        if (!uiValid || responses.unexpected_http > 0) break;
        await page.waitForTimeout(Math.max(1, Math.min(500, durationMs - (performance.now() - begin))));
      }
      check();
      const lastNumber = ledger.rows.length, finished = utc(), measuredMs = Math.round(performance.now() - begin);
      // Let already-issued responses finish without counting later requests as part of this window.
      const until = performance.now() + 5000;
      while (ledger.rows.some(row => row.number > count && row.number <= lastNumber && row.state === "started") && performance.now() < until)
        await page.waitForTimeout(100);
      await flush(); check();
      const traffic = summarizeNormalBrowserRows(ledger.rows, count + 1, lastNumber);
      const row = { phase: "normal_polling", started_at: started, finished_at: finished, duration_ms: measuredMs,
        ...traffic, ui_visible_and_ready: uiValid, real_time: true, passed: uiValid && measuredMs >= durationMs && traffic.passed };
      measurements.push(row);
      if (!row.passed) fail("browser_normal_polling_failed");
      return row;
    },
  };
}

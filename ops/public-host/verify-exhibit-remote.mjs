/**
 * EXHIBIT-host1 ③: READ-ONLY verification of a deployed host against the intake receipt and the extracted site.
 * GET/HEAD only, plus at most one viewer login whose cookie stays in memory. Never uploads, never touches the notice
 * switch, never follows a redirect, never records the origin, the code or the cookie. The receipt says what the host
 * answered and whether the bytes equal the partner's; it cannot prove who uploaded them, what the CDN holds, or what a
 * browser renders. Loopback http is accepted only with --allow-loopback (tests).
 */
import { lstat, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs } from "node:util";
import { prepareSite, EXHIBIT_GAME, hash } from "./exhibit-site.mjs"; // no Miniflare: runs without ops/public-host/node_modules
import { NOTICE_HEADER } from "./notice.mjs";
import { ACCESS_HEADER, ACCESS_ROUTE } from "./access.mjs";

export const SCHEMA = "pitcheezy-exhibit-remote-verify-v1";
export const REQUEST_TIMEOUT_MS = 15000;
export const TOTAL_DEADLINE_MS = 300000;
const MAX_BODY_BYTES = 8 * 1024 * 1024;
const DATA_CACHE_CONTROL = "no-store, no-transform";
const MIME = { html: /^text\/html\b/, svg: /^image\/svg\+xml\b/, js: /^(?:text|application)\/(?:x-)?(?:java|ecma)script\b/, css: /^text\/css\b/ };
const fail = (code, path = null) => { throw Object.assign(new Error(code), path ? { path } : {}); };
const need = (value, code, path = null) => { if (!value) fail(code, path); };
const kindOf = path => path === "index.html" ? "html" : path === "favicon.svg" ? "svg" : path.endsWith(".js") ? "js" : "css";

/** Exact https origin: no path, query, fragment or userinfo. http is only http://127.0.0.1[:port] with allowLoopback. */
export function parseOrigin(value, { allowLoopback = false } = {}) {
  need(typeof value === "string" && value.length > 0 && value.length <= 2048, "origin_invalid");
  let url;
  try { url = new URL(value); } catch { fail("origin_invalid"); }
  need(url.origin === value && !url.username && !url.password && url.pathname === "/" && !url.search && !url.hash, "origin_invalid");
  if (url.protocol === "https:") return { origin: url.origin, kind: "https" };
  need(allowLoopback && url.protocol === "http:" && url.hostname === "127.0.0.1", "origin_https_required");
  return { origin: url.origin, kind: "loopback_http" };
}

async function readBounded(response, limit) {
  if (!response.body) return Buffer.alloc(0);
  const reader = response.body.getReader();
  const chunks = [];
  let size = 0;
  try {
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      size += value.byteLength;
      if (size > limit) { await reader.cancel().catch(() => {}); fail("body_too_large"); }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  return Buffer.concat(chunks);
}

export async function verifyExhibitRemote({ target, prepared, game = EXHIBIT_GAME, noticeCheck = false, accessCode = null } = {}) {
  const { origin } = target;
  const controller = new AbortController();
  const deadline = setTimeout(() => controller.abort(), TOTAL_DEADLINE_MS);
  const start = performance.now();
  const checks = [];
  const check = (name, passed, detail = undefined) => { checks.push({ name, passed: Boolean(passed), ...(detail === undefined ? {} : { detail }) }); return Boolean(passed); };
  const { intake, files, classified } = prepared;
  const report = {
    schema: SCHEMA, evidence_kind: "remote_http_read_only", target: { kind: target.kind, origin_recorded: false },
    source_commit: intake.source_commit, intake_zip_sha256: intake.zip?.sha256 ?? null, exhibit_game: String(game),
    started_at: new Date().toISOString(), environment: { node: process.version, platform: process.platform, arch: process.arch },
    counts: { site_files: files.size, static: classified.static.length, data: classified.data.length, requests: 0, pass: 0, fail: 0 },
    access: { env_present: accessCode !== null, access_used: false, login_status: null, session_cookie_received: false },
    notice: { checked: noticeCheck, active: null, header: null }, files: [], entry: {}, negative: {}, head: {}, cdn: {},
    checks, passed: false, pass: 0, fail: 0,
    limitations: [
      "Read-only HTTP from this machine: GET/HEAD and at most one viewer login. Nothing was uploaded, switched, deleted or logged out.",
      "Byte equality with the intake receipt shows what the host answers now; it does not prove who uploaded the files, when, or that no other key exists.",
      "CDN/edge is noted from headers only (Age, CF-Cache-Status). Our gateway sends no-store, so cached variants are not expected but not disproved.",
      "No browser: rendering, polling and the app's notice behaviour are not observed (rehearse-exhibit-host.mjs --browser covers them locally).",
      "Redirects are never followed. Only /index.html -> / (Cloudflare static assets html_handling) counts as a pass, and only because / itself is compared.",
      "The origin, the viewer code and the session cookie are not recorded; the receipt names no host.",
      "Notice state is observed from the public manifest response (503 + notice header) only; the operator route is not read.",
      "With the access gate on and no PITCHEEZY_ACCESS_CODE every viewer path answers 401 and the run fails by design.",
    ],
  };
  let session = null;
  const locationKind = value => {
    if (value === null) return null;
    try { const u = new URL(value, origin); return u.origin === origin ? u.pathname + u.search : "<other-origin>"; } catch { return "<unparseable>"; }
  };
  const send = async (method, path, { headers = {}, cookie = session, body = undefined } = {}) => {
    const row = { method, path, status: null, redirect: false, error: null, bytes: null, headers: null };
    let response;
    report.counts.requests += 1;
    try {
      response = await fetch(origin + path, { method, redirect: "manual", cache: "no-store", body,
        headers: { ...(cookie ? { Cookie: cookie } : {}), ...headers },
        signal: AbortSignal.any([controller.signal, AbortSignal.timeout(REQUEST_TIMEOUT_MS)]) });
      row.status = response.status;
      row.redirect = response.status >= 300 && response.status < 400;
      const h = response.headers;
      row.headers = { content_type: h.get("Content-Type"), cache_control: h.get("Cache-Control"), etag_present: h.get("ETag") !== null,
        age: h.get("Age"), cf_cache_status: h.get("CF-Cache-Status"), notice: h.get(NOTICE_HEADER), access: h.get(ACCESS_HEADER), location: locationKind(h.get("Location")) };
      const bytes = await readBounded(response, MAX_BODY_BYTES);
      row.bytes = bytes.length;
      return { row, bytes, response };
    } catch (error) {
      row.error = controller.signal.aborted ? "deadline" : /^[a-z_]{1,64}$/.test(error?.message || "") ? error.message :
        ["TimeoutError", "AbortError"].includes(error?.name) ? "timeout" : "network_error";
      if (response?.body && !response.bodyUsed && !response.body.locked) void response.body.cancel().catch(() => {});
      return { row, bytes: Buffer.alloc(0), response };
    }
  };
  const equalTo = (row, bytes, source) => row.status === 200 && !row.redirect && bytes.length === source.bytes.length && hash(bytes) === source.sha256;
  try {
    if (accessCode !== null) {
      // JSON login like local-host.mjs; the cookie value lives in this closure only.
      const { row, response } = await send("POST", ACCESS_ROUTE, { headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code: accessCode }), cookie: null });
      const setCookie = response?.headers.get("Set-Cookie") || "";
      const pair = setCookie.split(";")[0];
      report.access.login_status = row.status;
      report.access.session_cookie_received = /^(__Host-)?pz_viewer=v3\./.test(pair);
      if (row.status === 200 && report.access.session_cookie_received) { session = pair; report.access.access_used = true; }
      check("access:login_200_with_session_cookie", report.access.access_used, { status: row.status, error: row.error });
    }
    if (noticeCheck) {
      const { row } = await send("GET", "/v1/manifest.json");
      report.notice = { checked: true, active: row.status === 503 && row.headers?.notice !== null && row.headers?.notice !== undefined,
        header: row.headers?.notice ?? null, status: row.status };
    }
    for (const key of classified.data) {
      const source = files.get(key);
      const { row, bytes } = await send("GET", "/" + key);
      const equal = equalTo(row, bytes, source);
      const entry = { path: key, kind: "data", bytes: source.bytes.length, sha256: source.sha256, status: row.status, equal, redirect: row.redirect, error: row.error,
        cache_control: row.headers?.cache_control ?? null, etag_present: row.headers?.etag_present ?? false, content_type: row.headers?.content_type ?? null,
        age: row.headers?.age ?? null, cf_cache_status: row.headers?.cf_cache_status ?? null, notice: row.headers?.notice ?? null, access: row.headers?.access ?? null };
      entry.passed = check("data:" + key, equal && entry.cache_control === DATA_CACHE_CONTROL && entry.etag_present, { status: row.status, bytes: row.bytes, error: row.error });
      report.files.push(entry);
    }
    for (const path of classified.static) {
      const source = files.get(path);
      const { row, bytes } = await send("GET", "/" + path);
      const equal = equalTo(row, bytes, source);
      const mimeOk = MIME[kindOf(path)].test(row.headers?.content_type || "");
      // Cloudflare static assets answer /index.html with a redirect to /; "/" is compared below, the redirect is not followed.
      const indexRedirect = path === "index.html" && row.redirect && row.headers?.location === "/";
      const entry = { path, kind: "static", bytes: source.bytes.length, sha256: source.sha256, status: row.status, equal, redirect: row.redirect, error: row.error,
        content_type: row.headers?.content_type ?? null, cache_control: row.headers?.cache_control ?? null, age: row.headers?.age ?? null,
        cf_cache_status: row.headers?.cf_cache_status ?? null, ...(indexRedirect ? { note: "redirected_to_root" } : {}) };
      entry.passed = check("static:" + path, (equal && mimeOk) || indexRedirect, { status: row.status, content_type: entry.content_type, error: row.error });
      report.files.push(entry);
    }
    const index = files.get("index.html");
    const root = await send("GET", "/", { headers: { Accept: "text/html,application/xhtml+xml" } });
    report.entry.root = { status: root.row.status, equal_index: equalTo(root.row, root.bytes, index), redirect: root.row.redirect, error: root.row.error,
      content_type: root.row.headers?.content_type ?? null, cache_control: root.row.headers?.cache_control ?? null };
    check("entry:root_is_index", report.entry.root.equal_index && MIME.html.test(report.entry.root.content_type || ""), { status: root.row.status });
    const query = await send("GET", "/?game=" + game, { headers: { Accept: "text/html,application/xhtml+xml" } });
    report.entry.query = { status: query.row.status, equal_index: equalTo(query.row, query.bytes, index), redirect: query.row.redirect, error: query.row.error };
    check("entry:query_game_is_index", report.entry.query.equal_index, { status: query.row.status });

    const absent = await send("GET", "/v1/game/999999.json");
    report.negative.unknown_game = { status: absent.row.status, redirect: absent.row.redirect, error: absent.row.error };
    check("negative:unknown_game_404", absent.row.status === 404 && !absent.row.redirect);
    const missingDate = intake.catalogue.missing_date_files[0] ?? null;
    if (missingDate) {
      const date = await send("GET", `/v1/games/${missingDate}.json`);
      report.negative.missing_advertised_date = { date: missingDate, status: date.row.status, redirect: date.row.redirect, error: date.row.error };
      check("negative:missing_advertised_date_404", date.row.status === 404 && !date.row.redirect);
    } else report.negative.missing_advertised_date = { date: null, status: null, note: "receipt lists no missing date files" };

    const head = await send("HEAD", "/v1/manifest.json");
    report.head.manifest = { status: head.row.status, bytes: head.row.bytes, etag_present: head.row.headers?.etag_present ?? false,
      cache_control: head.row.headers?.cache_control ?? null, redirect: head.row.redirect, error: head.row.error };
    check("head:manifest_200_no_body_etag", head.row.status === 200 && head.row.bytes === 0 && report.head.manifest.etag_present && report.head.manifest.cache_control === DATA_CACHE_CONTROL);

    const rows = report.files;
    report.cdn = { age_values: [...new Set(rows.map(r => r.age).filter(v => v !== null))], cf_cache_status_values: [...new Set(rows.map(r => r.cf_cache_status).filter(v => v !== null))],
      redirects: rows.filter(r => r.redirect).length, note: "header observations only; no cache purge, no edge inspection" };
    check("transport:no_unexpected_redirect", rows.every(r => !r.redirect || r.note === "redirected_to_root") && !root.row.redirect && !query.row.redirect);
  } catch (error) {
    const coded = /^[a-z_]{1,64}$/.test(error?.message || "");
    report.failure = { code: controller.signal.aborted ? "deadline" : coded ? error.message : "verification_failed", ...(error?.path ? { path: error.path } : {}) };
  } finally {
    controller.abort(); clearTimeout(deadline);
  }
  report.pass = checks.filter(c => c.passed).length;
  report.fail = checks.filter(c => !c.passed).length;
  report.counts.pass = report.pass; report.counts.fail = report.fail;
  report.passed = !report.failure && report.fail === 0 && checks.length > 0;
  report.total_ms = Math.round(performance.now() - start);
  return report;
}

/** The origin never appears in the receipt, even inside an unexpected header value. */
export function serialize(report, origin) {
  return JSON.stringify(report, null, 2).split(origin).join("<origin>") + "\n";
}

export async function main(args, environment = process.env) {
  let values, target, prepared, accessCode = null;
  try {
    ({ values } = parseArgs({ args, options: { origin: { type: "string" }, site: { type: "string" }, receipt: { type: "string" }, out: { type: "string" },
      game: { type: "string", default: EXHIBIT_GAME }, "expect-data": { type: "string", default: "24" },
      "notice-check": { type: "boolean", default: false }, "allow-loopback": { type: "boolean", default: false } } }));
    need(values.origin && values.site && values.receipt && values.out, "arguments_required");
    // The target is judged before any file is read and long before any request is sent.
    target = parseOrigin(values.origin, { allowLoopback: values["allow-loopback"] });
    need(/^[1-9][0-9]{0,3}$/.test(values["expect-data"]), "expect_data_invalid");
    const out = resolve(values.out);
    need(!(await lstat(out).then(() => true, () => false)), "output_exists");
    if (environment.PITCHEEZY_ACCESS_CODE !== undefined) {
      // A code read from a file with Get-Content -Raw / $(cat) may carry a trailing CR/LF; surrounding whitespace is not part of the code.
      accessCode = typeof environment.PITCHEEZY_ACCESS_CODE === "string" ? environment.PITCHEEZY_ACCESS_CODE.trim() : environment.PITCHEEZY_ACCESS_CODE;
      need(typeof accessCode === "string" && /^[^\s\p{Cc}]{8,128}$/u.test(accessCode), "access_code_invalid");
    }
    prepared = await prepareSite({ site: values.site, receipt: values.receipt, expectData: Number(values["expect-data"]), game: values.game });
  } catch (error) {
    const code = /^[a-z_]{1,64}$/.test(error?.message || "") ? error.message : "verify_arguments_or_input_error";
    process.stderr.write(JSON.stringify({ ok: false, code, ...(error?.path ? { path: error.path } : {}) }) + "\n");
    return 2;
  }
  const report = await verifyExhibitRemote({ target, prepared, game: values.game, noticeCheck: values["notice-check"], accessCode });
  try { await writeFile(resolve(values.out), serialize(report, target.origin), { flag: "wx" }); report.receipt_written = true; }
  catch { report.receipt_written = false; }
  process.stdout.write(serialize(report, target.origin));
  return report.passed && report.receipt_written ? 0 : 1;
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await main(process.argv.slice(2));
}

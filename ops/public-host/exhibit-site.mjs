/**
 * EXHIBIT-host1: the received exhibition build as OUR host contract sees it, with no runtime attached.
 * Reads the intake receipt, checks every site file byte-for-byte against it, and classifies the files into the
 * 4 static front-end files (ASSETS) and the v1 data files (/_publish). Imports only node: modules and our own
 * gateway/notice/access code, so the deploy-day tools (verify-exhibit-remote.mjs, exhibit-upload-plans.mjs) run from a
 * checkout without ops/public-host/node_modules (no Miniflare). rehearse-exhibit-host.mjs re-exports everything here.
 * Partner files are read only.
 */
import { createHash } from "node:crypto";
import { readFile, readdir, lstat } from "node:fs/promises";
import { join, resolve, relative } from "node:path";
import { permittedKey } from "./gateway.mjs";

const fail = (code, path = null) => { throw Object.assign(new Error(code), path ? { path } : {}); };
const need = (value, code, path = null) => { if (!value) fail(code, path); };
export const INTAKE_SCHEMA = "pitcheezy-exhibition-intake-v1";
export const EXHIBIT_GAME = "849843";
const BUNDLE = /^assets\/index-[A-Za-z0-9_-]+\.(js|css)$/;
export const CONTENT_TYPES = { html: "text/html; charset=utf-8", svg: "image/svg+xml", js: "text/javascript; charset=utf-8", css: "text/css; charset=utf-8" };
export const CORE_DATA = ["v1/manifest.json", "v1/health.json", "v1/dates.json"];

/** SHA-256 hex of a string or byte buffer (same function as rehearsal/local-host.mjs, without its Miniflare import). */
export const hash = value => createHash("sha256").update(value).digest("hex");

/** The intake receipt is the only authority for which bytes the partner sent; refuse anything malformed. */
export function validateIntakeReceipt(value) {
  need(value && typeof value === "object" && !Array.isArray(value) && value.schema === INTAKE_SCHEMA, "intake_receipt_schema");
  need(typeof value.source_commit === "string" && /^[a-f0-9]{40}$/.test(value.source_commit), "intake_receipt_commit");
  need(Array.isArray(value.files) && value.files.length > 0, "intake_receipt_files");
  const seen = new Set();
  for (const file of value.files) {
    need(file && typeof file.path === "string" &&
      /^[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}(\/[A-Za-z0-9_][A-Za-z0-9_.-]{0,99}){0,7}$/.test(file.path) &&
      !/(^|\/)\.\.?(\/|$)/.test(file.path) && !seen.has(file.path), "intake_receipt_path");
    need(Number.isSafeInteger(file.bytes) && file.bytes >= 0 && /^[a-f0-9]{64}$/.test(file.sha256_raw || ""), "intake_receipt_entry", file.path);
    seen.add(file.path);
  }
  const missing = value.catalogue?.missing_date_files;
  need(Array.isArray(missing) && missing.every(d => typeof d === "string" && /^\d{4}-\d{2}-\d{2}$/.test(d)), "intake_receipt_catalogue");
  return value;
}

async function walk(root, dir, out) {
  for (const entry of await readdir(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    const rel = relative(root, full).split("\\").join("/");
    if (entry.isSymbolicLink()) fail("site_symlink_refused", rel);
    if (entry.isDirectory()) await walk(root, full, out);
    else if (entry.isFile()) out.push(rel);
    else fail("site_entry_refused", rel);
  }
  return out;
}

/** Every file under the site must be in the receipt with the same byte count and raw SHA-256, and vice versa. */
export async function verifySite(siteDir, receipt) {
  const root = resolve(siteDir);
  need((await lstat(root)).isDirectory(), "site_not_directory");
  const expected = new Map(receipt.files.map(f => [f.path, f]));
  const actual = (await walk(root, root, [])).sort();
  for (const path of actual) need(expected.has(path), "site_extra_file", path);
  for (const path of expected.keys()) need(actual.includes(path), "site_missing_file", path);
  const files = new Map();
  for (const path of actual) {
    const bytes = await readFile(join(root, ...path.split("/")));
    const row = expected.get(path);
    need(bytes.length === row.bytes, "site_bytes_mismatch", path);
    const sha256 = hash(bytes);
    need(sha256 === row.sha256_raw, "site_sha256_mismatch", path);
    files.set(path, { bytes, sha256 });
  }
  return files;
}

/**
 * static = exactly index.html, favicon.svg, one assets/index-*.js, one assets/index-*.css;
 * data = every v1/ file our gateway permits as a public key. Anything else, or a count mismatch, is refused.
 * Data keys come back in upload order: setup, game, games, dates, manifest, health last.
 */
export function classifySite(paths, { expectData = null, game = EXHIBIT_GAME } = {}) {
  need(/^[1-9][0-9]{0,11}$/.test(String(game)), "exhibit_game_invalid");
  need(expectData === null || (Number.isSafeInteger(expectData) && expectData >= 1), "expect_data_invalid");
  const statics = { html: [], favicon: [], js: [], css: [] };
  const data = [];
  for (const path of paths) {
    if (path === "index.html") statics.html.push(path);
    else if (path === "favicon.svg") statics.favicon.push(path);
    else if (BUNDLE.test(path)) statics[path.endsWith(".js") ? "js" : "css"].push(path);
    else if (path.startsWith("v1/")) { need(permittedKey("/" + path) === path, "data_key_not_permitted", path); data.push(path); }
    else fail("file_unclassified", path);
  }
  need(statics.html.length === 1, "static_index_missing");
  need(statics.favicon.length === 1, "static_favicon_missing");
  need(statics.js.length === 1, "static_js_count");
  need(statics.css.length === 1, "static_css_count");
  for (const core of CORE_DATA) need(data.includes(core), "data_core_missing", core);
  need(data.includes(`v1/game/${game}.json`), "exhibit_game_missing", `v1/game/${game}.json`);
  if (expectData !== null) need(data.length === expectData, "data_count_mismatch");
  const rank = k => k.startsWith("v1/setup/") ? 0 : k.startsWith("v1/game/") ? 1 : k.startsWith("v1/games/") ? 2 :
    k === "v1/dates.json" ? 3 : k === "v1/manifest.json" ? 4 : 5;
  data.sort((a, b) => rank(a) - rank(b) || (a < b ? -1 : a > b ? 1 : 0));
  return { static: [statics.html[0], statics.favicon[0], statics.js[0], statics.css[0]], data };
}

/**
 * Emulates Cloudflare static assets with not_found_handling "single-page-application": exact paths serve raw bytes
 * with their Content-Type, "/" serves index.html, and an unmatched GET/HEAD that accepts text/html gets index.html
 * (200). Everything else is 404. Real asset headers (ETag, Cache-Control, redirects for /index.html) are not emulated.
 */
export function makeAssets(files, staticPaths) {
  const served = new Map();
  for (const path of staticPaths) {
    const kind = path === "index.html" ? "html" : path === "favicon.svg" ? "svg" : path.endsWith(".js") ? "js" : "css";
    served.set("/" + path, { bytes: files.get(path).bytes, type: CONTENT_TYPES[kind] });
  }
  return request => {
    const url = new URL(request.url);
    if (!["GET", "HEAD"].includes(request.method)) return new Response(null, { status: 405, headers: { Allow: "GET, HEAD" } });
    let file = served.get(url.pathname === "/" ? "/index.html" : url.pathname);
    if (!file && /(^|,)\s*text\/html\b/.test(request.headers.get("Accept") || "")) file = served.get("/index.html");
    if (!file) return new Response("not found", { status: 404, headers: { "Content-Type": "text/plain; charset=utf-8" } });
    return new Response(request.method === "HEAD" ? null : file.bytes, { status: 200, headers: { "Content-Type": file.type } });
  };
}

/** Reads the inputs and refuses before any runtime starts. Returns what a run needs. */
export async function prepareSite({ site, receipt, expectData = null, game = EXHIBIT_GAME }) {
  need(typeof site === "string" && site && typeof receipt === "string" && receipt, "arguments_required");
  let parsed;
  try { parsed = JSON.parse(await readFile(receipt, "utf8")); } catch { fail("intake_receipt_unreadable"); }
  const intake = validateIntakeReceipt(parsed);
  const files = await verifySite(site, intake);
  const classified = classifySite([...files.keys()], { expectData, game });
  return { intake, files, classified };
}

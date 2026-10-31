// EXHIBIT-host1 remote verifier against a loopback host with a tiny SYNTHETIC 4+6 build. Never the partner's files.
import test from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { mkdtemp, mkdir, writeFile, readFile, rm, readdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { prepareSite, makeAssets } from "../rehearse-exhibit-host.mjs";
import { startLocalHost, hash } from "../rehearsal/local-host.mjs";
import { main, parseOrigin } from "../verify-exhibit-remote.mjs";

function miniBuild() {
  return {
    "index.html": '<!doctype html><html lang="ko"><meta charset="utf-8"><title>synthetic</title><link rel="stylesheet" href="./assets/index-syn1.css"><div id="root"></div><script type="module" src="./assets/index-syn1.js"></script></html>',
    "favicon.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"/>',
    "assets/index-syn1.js": 'fetch("./v1/manifest.json",{cache:"no-store"});',
    "assets/index-syn1.css": "body{margin:0}",
    "v1/manifest.json": JSON.stringify({ synthetic: true, schema: "synthetic-manifest" }),
    "v1/health.json": JSON.stringify({ synthetic: true, sequence: 1 }),
    "v1/dates.json": JSON.stringify({ synthetic: true, dates: ["2026-01-01", "2026-01-02"] }),
    "v1/games/2026-01-01.json": JSON.stringify({ synthetic: true, games: [1] }),
    "v1/game/1.json": JSON.stringify({ synthetic: true, game_pk: 1, pitches: [], padding: "x".repeat(5000) }),
    "v1/setup/1.json": JSON.stringify({ synthetic: true, game_pk: 1 }),
  };
}
function receiptFor(build) {
  return { schema: "pitcheezy-exhibition-intake-v1", evidence_kind: "offline_archive_integrity", source_commit: "a".repeat(40),
    zip: { bytes: 1, sha256: "b".repeat(64) }, catalogue: { advertised_dates: 2, supplied_date_files: 1, missing_date_files: ["2026-01-02"] },
    files: Object.entries(build).map(([path, text]) => ({ path, bytes: Buffer.byteLength(text), sha256_raw: hash(text) })) };
}
async function fixture(t, build = miniBuild()) {
  const dir = await mkdtemp(join(tmpdir(), "pitcheezy-remote-test-"));
  t.after(() => rm(dir, { recursive: true, force: true }));
  const site = join(dir, "site");
  for (const [path, text] of Object.entries(build)) {
    const full = join(site, ...path.split("/"));
    await mkdir(dirname(full), { recursive: true });
    await writeFile(full, text);
  }
  const receiptPath = join(dir, "intake-receipt.json");
  await writeFile(receiptPath, JSON.stringify(receiptFor(build)));
  return { dir, site, receiptPath, build };
}
/** Our real gateway in loopback Miniflare with the synthetic build installed the host-contract way (ASSETS + /_publish). */
async function hostWithSite(t, { access = null, overrides = {} } = {}) {
  const fx = await fixture(t);
  const prepared = await prepareSite({ site: fx.site, receipt: fx.receiptPath, expectData: 6, game: "1" });
  const host = await startLocalHost({ notice: true, access, assets: makeAssets(prepared.files, prepared.classified.static) });
  t.after(() => host.dispose());
  for (const key of prepared.classified.data) {
    const put = await host.publish("/" + key, overrides[key] ?? prepared.files.get(key).bytes);
    await put.arrayBuffer();
    assert.equal(put.status, 200, key);
  }
  return { ...fx, host, prepared };
}
async function capture(stream, run) {
  const chunks = []; const original = stream.write;
  stream.write = chunk => { chunks.push(String(chunk)); return true; };
  try { return { code: await run(), text: chunks.join("") }; } finally { stream.write = original; }
}
const args = (origin, fx, out, extra = []) => ["--origin", origin, "--site", fx.site, "--receipt", fx.receiptPath, "--out", out, "--expect-data", "6", "--game", "1", "--allow-loopback", ...extra];
const noLeak = text => assert.doesNotMatch(text, /127\.0\.0\.1|Bearer |pz_viewer=|PUBLISH_TOKEN|accessCodes/);

test("origin rules: https exact origin only; loopback http only with the flag; refusals happen before any file is read", async (t) => {
  assert.deepEqual(parseOrigin("https://host.invalid"), { origin: "https://host.invalid", kind: "https" });
  assert.deepEqual(parseOrigin("http://127.0.0.1:8080", { allowLoopback: true }), { origin: "http://127.0.0.1:8080", kind: "loopback_http" });
  for (const [value, code, options] of [
    ["http://host.invalid", /origin_https_required/, {}],
    ["http://host.invalid", /origin_https_required/, { allowLoopback: true }],
    ["http://127.0.0.1:1", /origin_https_required/, {}],
    ["http://localhost:1", /origin_https_required/, { allowLoopback: true }],
    ["https://host.invalid/", /origin_invalid/, {}],
    ["https://host.invalid/path", /origin_invalid/, {}],
    ["https://host.invalid?x=1", /origin_invalid/, {}],
    ["https://user:pw@host.invalid", /origin_invalid/, {}],
    ["host.invalid", /origin_invalid/, {}],
    ["", /origin_invalid/, {}],
  ]) assert.throws(() => parseOrigin(value, options), code, value);
  const fx = await fixture(t);
  const out = join(fx.dir, "never.json");
  const refused = await capture(process.stderr, () => main(["--origin", "http://host.invalid", "--site", fx.site, "--receipt", fx.receiptPath, "--out", out, "--expect-data", "6", "--game", "1"]));
  assert.equal(refused.code, 2);
  assert.match(refused.text, /origin_https_required/);
  const flagged = await capture(process.stderr, () => main(["--origin", "http://host.invalid", "--site", fx.site, "--receipt", fx.receiptPath, "--out", out, "--expect-data", "6", "--game", "1", "--allow-loopback"]));
  assert.equal(flagged.code, 2);
  assert.match(flagged.text, /origin_https_required/);
  const missing = await capture(process.stderr, () => main(["--origin", "https://host.invalid"]));
  assert.equal(missing.code, 2);
  assert.match(missing.text, /arguments_required/);
  const badCode = await capture(process.stderr, () => main(["--origin", "https://host.invalid", "--site", fx.site, "--receipt", fx.receiptPath, "--out", out], { PITCHEEZY_ACCESS_CODE: "short" }));
  assert.equal(badCode.code, 2);
  assert.match(badCode.text, /access_code_invalid/);
  assert.equal((await readdir(fx.dir)).includes("never.json"), false, "no receipt on refusal");
});

test("all pass: every data key and static path byte-identical, 404s, HEAD, receipt file, nothing sensitive printed", { timeout: 50000 }, async (t) => {
  const fx = await hostWithSite(t);
  const out = join(fx.dir, "remote.json");
  const run = await capture(process.stdout, () => main(args(fx.host.origin, fx, out, ["--notice-check"]), {}));
  const report = JSON.parse(run.text);
  assert.equal(run.code, 0, JSON.stringify(report.checks.filter(c => !c.passed)) + JSON.stringify(report.failure ?? null));
  assert.equal(report.passed, true);
  assert.equal(report.schema, "pitcheezy-exhibit-remote-verify-v1");
  assert.equal(report.evidence_kind, "remote_http_read_only");
  assert.deepEqual(report.target, { kind: "loopback_http", origin_recorded: false });
  assert.equal(report.source_commit, "a".repeat(40));
  assert.equal(report.counts.data, 6); assert.equal(report.counts.static, 4); assert.equal(report.counts.site_files, 10);
  assert.equal(report.counts.requests, 6 + 4 + 2 + 2 + 1 + 1, "data, statics, root+query, two 404s, HEAD, notice observation");
  assert.equal(report.fail, 0);
  assert.ok(report.pass >= 16, String(report.pass));
  const data = report.files.filter(f => f.kind === "data");
  assert.deepEqual(data.map(f => f.path), ["v1/setup/1.json", "v1/game/1.json", "v1/games/2026-01-01.json", "v1/dates.json", "v1/manifest.json", "v1/health.json"]);
  for (const row of data) {
    assert.equal(row.status, 200, row.path); assert.equal(row.equal, true, row.path); assert.equal(row.passed, true, row.path);
    assert.equal(row.cache_control, "no-store, no-transform", row.path); assert.equal(row.etag_present, true, row.path);
    assert.equal(row.sha256, hash(fx.build[row.path]), row.path); assert.equal(row.redirect, false);
  }
  for (const row of report.files.filter(f => f.kind === "static")) { assert.equal(row.equal, true, row.path); assert.equal(row.passed, true, row.path); }
  assert.equal(report.entry.root.equal_index, true); assert.equal(report.entry.query.equal_index, true);
  assert.deepEqual([report.negative.unknown_game.status, report.negative.missing_advertised_date.status], [404, 404]);
  assert.equal(report.negative.missing_advertised_date.date, "2026-01-02");
  assert.deepEqual([report.head.manifest.status, report.head.manifest.bytes, report.head.manifest.etag_present], [200, 0, true]);
  assert.deepEqual(report.notice, { checked: true, active: false, header: null, status: 200 });
  assert.deepEqual(report.access, { env_present: false, access_used: false, login_status: null, session_cookie_received: false });
  assert.deepEqual(report.cdn.age_values, ["0"]); assert.equal(report.cdn.redirects, 0);
  assert.equal(report.receipt_written, true);
  noLeak(run.text);
  const written = JSON.parse(await readFile(out, "utf8"));
  assert.equal(written.passed, true); assert.equal(written.pass, report.pass);
  noLeak(await readFile(out, "utf8"));
  // An existing --out is refused before any request.
  const again = await capture(process.stderr, () => main(args(fx.host.origin, fx, out), {}));
  assert.equal(again.code, 2); assert.match(again.text, /output_exists/);
});

test("a changed byte on one key fails that row only and exits 1; the receipt still records everything", { timeout: 50000 }, async (t) => {
  const changed = Buffer.from(JSON.stringify({ synthetic: true, sequence: 2 })); // same length, different bytes
  const fx = await hostWithSite(t, { overrides: { "v1/health.json": changed } });
  const out = join(fx.dir, "remote.json");
  const run = await capture(process.stdout, () => main(args(fx.host.origin, fx, out), {}));
  const report = JSON.parse(run.text);
  assert.equal(run.code, 1);
  assert.equal(report.passed, false);
  const health = report.files.find(f => f.path === "v1/health.json");
  assert.equal(health.status, 200); assert.equal(health.equal, false); assert.equal(health.passed, false);
  assert.equal(health.sha256, hash(fx.build["v1/health.json"]), "the receipt keeps the SOURCE sha, never the served one");
  assert.deepEqual(report.checks.filter(c => !c.passed).map(c => c.name), ["data:v1/health.json"]);
  assert.equal(report.fail, 1);
  assert.equal(report.receipt_written, true);
  assert.equal(JSON.parse(await readFile(out, "utf8")).passed, false);
  noLeak(run.text);
});

test("access gate: PITCHEEZY_ACCESS_CODE logs in once and the run passes; without it every viewer path is 401 and the run fails", { timeout: 50000 }, async (t) => {
  const fx = await hostWithSite(t, { access: {} });
  const out = join(fx.dir, "remote-access.json");
  process.env.PITCHEEZY_ACCESS_CODE = fx.host.accessCodes[0];
  let run;
  try { run = await capture(process.stdout, () => main(args(fx.host.origin, fx, out))); }
  finally { delete process.env.PITCHEEZY_ACCESS_CODE; }
  const report = JSON.parse(run.text);
  assert.equal(run.code, 0, JSON.stringify(report.checks.filter(c => !c.passed)));
  assert.deepEqual(report.access, { env_present: true, access_used: true, login_status: 200, session_cookie_received: true });
  assert.equal(report.counts.requests, 1 + 6 + 4 + 2 + 2 + 1);
  assert.ok(report.checks.some(c => c.name === "access:login_200_with_session_cookie" && c.passed));
  noLeak(run.text);
  assert.equal(run.text.includes(fx.host.accessCodes[0]), false, "code never printed");
  assert.equal((await readFile(out, "utf8")).includes(fx.host.accessCodes[0]), false);
  // A code read from a file with Get-Content -Raw / $(cat) may end in CR LF: surrounding whitespace is trimmed, the login still succeeds.
  const crlf = await capture(process.stdout, () => main(args(fx.host.origin, fx, join(fx.dir, "remote-crlf.json")), { PITCHEEZY_ACCESS_CODE: fx.host.accessCodes[0] + "\r\n" }));
  const crlfReport = JSON.parse(crlf.text);
  assert.equal(crlf.code, 0, JSON.stringify(crlfReport.checks.filter(c => !c.passed)));
  assert.deepEqual(crlfReport.access, { env_present: true, access_used: true, login_status: 200, session_cookie_received: true });
  const padded = await capture(process.stdout, () => main(args(fx.host.origin, fx, join(fx.dir, "remote-padded.json")), { PITCHEEZY_ACCESS_CODE: "  \t" + fx.host.accessCodes[0] + " \n" }));
  assert.equal(padded.code, 0);
  // Inner whitespace is still part of the value and still refused before any request.
  const inner = await capture(process.stderr, () => main(args(fx.host.origin, fx, join(fx.dir, "never-inner.json")), { PITCHEEZY_ACCESS_CODE: " bad code value \r\n" }));
  assert.equal(inner.code, 2); assert.match(inner.text, /access_code_invalid/);
  assert.equal((await readdir(fx.dir)).includes("never-inner.json"), false);
  // Same host, no code: the gate answers 401 everywhere and the verifier reports it instead of guessing.
  const locked = await capture(process.stdout, () => main(args(fx.host.origin, fx, join(fx.dir, "remote-locked.json")), {}));
  const lockedReport = JSON.parse(locked.text);
  assert.equal(locked.code, 1);
  assert.equal(lockedReport.access.access_used, false);
  assert.ok(lockedReport.files.every(f => f.status === 401 && f.passed === false));
  assert.equal(lockedReport.files[0].access, "required");
  assert.equal(lockedReport.entry.root.status, 401);
  noLeak(locked.text);
});

/** Plain Node server standing in for a host that redirects: either everything (fails) or only /index.html -> / (Cloudflare assets). */
async function redirectServer(t, build, mode) {
  const index = Buffer.from(build["index.html"]);
  const server = createServer((request, response) => {
    const url = new URL(request.url, "http://127.0.0.1");
    const path = url.pathname;
    const send = (status, body, headers) => { response.writeHead(status, headers); response.end(request.method === "HEAD" ? undefined : body); };
    if (mode === "all" || (path === "/index.html")) return send(mode === "all" ? 302 : 307, "", { Location: mode === "all" ? "https://elsewhere.invalid/" : "/" });
    if (path === "/" ) return send(200, index, { "Content-Type": "text/html; charset=utf-8" });
    if (path === "/favicon.svg") return send(200, build["favicon.svg"], { "Content-Type": "image/svg+xml" });
    if (path.startsWith("/assets/") && build[path.slice(1)]) return send(200, build[path.slice(1)], { "Content-Type": path.endsWith(".js") ? "application/javascript" : "text/css; charset=utf-8" });
    if (path.startsWith("/v1/") && build[path.slice(1)]) return send(200, build[path.slice(1)], { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store, no-transform", ETag: '"' + hash(build[path.slice(1)]).slice(0, 32) + '"', Age: "0" });
    return send(404, '{"error":"not_found"}', { "Content-Type": "application/json; charset=utf-8", "Cache-Control": "no-store" });
  });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  t.after(() => new Promise(resolve => server.close(resolve)));
  return "http://127.0.0.1:" + server.address().port;
}

test("redirects are never followed: a redirecting host fails; only /index.html -> / is tolerated when / serves the bytes", { timeout: 30000 }, async (t) => {
  const fx = await fixture(t);
  const all = await redirectServer(t, fx.build, "all");
  const failed = await capture(process.stdout, () => main(args(all, fx, join(fx.dir, "redirect-all.json")), {}));
  const failedReport = JSON.parse(failed.text);
  assert.equal(failed.code, 1);
  assert.ok(failedReport.files.every(f => f.redirect === true && f.passed === false));
  assert.equal(failedReport.cdn.redirects, 10);
  assert.doesNotMatch(failed.text, /elsewhere\.invalid/, "foreign Location values are not copied into the receipt");
  const indexOnly = await redirectServer(t, fx.build, "index");
  const ok = await capture(process.stdout, () => main(args(indexOnly, fx, join(fx.dir, "redirect-index.json")), {}));
  const okReport = JSON.parse(ok.text);
  assert.equal(ok.code, 0, JSON.stringify(okReport.checks.filter(c => !c.passed)));
  const index = okReport.files.find(f => f.path === "index.html");
  assert.deepEqual([index.status, index.redirect, index.note, index.passed, index.equal], [307, true, "redirected_to_root", true, false]);
  assert.equal(okReport.entry.root.equal_index, true);
  assert.equal(okReport.files.find(f => f.path === "assets/index-syn1.js").passed, true, "application/javascript is a JavaScript MIME type");
  noLeak(ok.text);
});

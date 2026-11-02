// EXHIBIT-host1 rehearsal checks on tiny SYNTHETIC builds generated here. Never the partner's files.
import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, mkdir, writeFile, readFile, rm, appendFile, readdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, dirname } from "node:path";
import { classifySite, verifySite, validateIntakeReceipt, prepareSite, makeAssets, runExhibitHostRehearsal, main } from "../rehearse-exhibit-host.mjs";
import { hash } from "../rehearsal/local-host.mjs";

const GOOD = ["index.html", "favicon.svg", "assets/index-syn1.js", "assets/index-syn1.css",
  "v1/manifest.json", "v1/health.json", "v1/dates.json", "v1/games/2026-01-01.json", "v1/game/1.json", "v1/setup/1.json"];
const OPTIONS = { expectData: 6, game: "1" };

/** A fake front end that only fetches ./v1/manifest.json relative to the page, like the partner app does. */
function miniBuild() {
  return {
    "index.html": '<!doctype html><html lang="ko"><meta charset="utf-8"><title>synthetic</title><link rel="stylesheet" href="./assets/index-syn1.css"><div id="root"></div><script type="module" src="./assets/index-syn1.js"></script></html>',
    "favicon.svg": '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1 1"/>',
    "assets/index-syn1.js": 'fetch("./v1/manifest.json",{cache:"no-store"}).then(r=>{document.querySelector("#root").textContent="synthetic "+r.status;});',
    "assets/index-syn1.css": "body{margin:0}",
    "v1/manifest.json": JSON.stringify({ synthetic: true, schema: "synthetic-manifest" }),
    "v1/health.json": JSON.stringify({ synthetic: true, sequence: 1 }),
    "v1/dates.json": JSON.stringify({ synthetic: true, dates: ["2026-01-01", "2026-01-02"] }),
    "v1/games/2026-01-01.json": JSON.stringify({ synthetic: true, games: [1] }),
    "v1/game/1.json": JSON.stringify({ synthetic: true, game_pk: 1, pitches: [], padding: "x".repeat(5000) }),
    "v1/setup/1.json": JSON.stringify({ synthetic: true, game_pk: 1 }),
  };
}
function receiptFor(build, extra = {}) {
  return { schema: "pitcheezy-exhibition-intake-v1", evidence_kind: "offline_archive_integrity", source_commit: "a".repeat(40),
    zip: { bytes: 1, sha256: "b".repeat(64) }, catalogue: { advertised_dates: 2, supplied_date_files: 1, missing_date_files: ["2026-01-02"] },
    files: Object.entries(build).map(([path, text]) => ({ path, bytes: Buffer.byteLength(text), sha256_raw: hash(text) })), ...extra };
}
async function writeBuild(root, build) {
  for (const [path, text] of Object.entries(build)) {
    const full = join(root, ...path.split("/"));
    await mkdir(dirname(full), { recursive: true });
    await writeFile(full, text);
  }
}
async function fixture(t, build = miniBuild(), receipt = receiptFor(build)) {
  const dir = await mkdtemp(join(tmpdir(), "pitcheezy-exhibit-test-"));
  t.after(() => rm(dir, { recursive: true, force: true }));
  const site = join(dir, "site");
  await writeBuild(site, build);
  const receiptPath = join(dir, "intake-receipt.json");
  await writeFile(receiptPath, JSON.stringify(receipt));
  return { dir, site, receiptPath, build };
}
async function capture(stream, run) {
  const chunks = []; const original = stream.write;
  stream.write = chunk => { chunks.push(String(chunk)); return true; };
  try { return { code: await run(), text: chunks.join("") }; } finally { stream.write = original; }
}

test("classification: exactly 4 static files plus permitted v1 keys, in upload order", () => {
  const result = classifySite(GOOD, OPTIONS);
  assert.deepEqual(result.static, ["index.html", "favicon.svg", "assets/index-syn1.js", "assets/index-syn1.css"]);
  assert.deepEqual(result.data, ["v1/setup/1.json", "v1/game/1.json", "v1/games/2026-01-01.json", "v1/dates.json", "v1/manifest.json", "v1/health.json"]);
  assert.equal(classifySite(GOOD, { game: "1" }).data.length, 6, "no expected count means no count check");
});

test("classification refuses extra, missing, renamed, unpermitted files and wrong counts", () => {
  const without = path => GOOD.filter(p => p !== path);
  const cases = [
    [[...GOOD, "README.md"], /file_unclassified/],
    [[...GOOD, "assets/vendor-abc.js"], /file_unclassified/],
    [[...GOOD, "robots.txt"], /file_unclassified/],
    [without("favicon.svg"), /static_favicon_missing/],
    [without("index.html"), /static_index_missing/],
    [[...without("index.html"), "index.htm"], /file_unclassified/],
    [[...without("assets/index-syn1.js"), "assets/main-syn1.js"], /file_unclassified/],
    [[...GOOD, "assets/index-syn2.js"], /static_js_count/],
    [[...GOOD, "assets/index-syn2.css"], /static_css_count/],
    [without("assets/index-syn1.css"), /static_css_count/],
    [[...GOOD, "v1/game/abc.json"], /data_key_not_permitted/],
    [[...GOOD, "v1/games/2026-02-30.json"], /data_key_not_permitted/],
    [[...GOOD, "v1/extra.json"], /data_key_not_permitted/],
    [[...GOOD, "v1/game/01.json"], /data_key_not_permitted/],
    [without("v1/dates.json"), /data_core_missing/],
    [without("v1/health.json"), /data_core_missing/],
    [[...GOOD, "v1/game/2.json"], /data_count_mismatch/],
    [without("v1/games/2026-01-01.json"), /data_count_mismatch/],
  ];
  for (const [paths, code] of cases) assert.throws(() => classifySite(paths, OPTIONS), code, paths.join(","));
  assert.throws(() => classifySite(GOOD, { ...OPTIONS, game: "2" }), /exhibit_game_missing/);
  assert.throws(() => classifySite(GOOD, { ...OPTIONS, game: "x" }), /exhibit_game_invalid/);
  assert.throws(() => classifySite(GOOD, { ...OPTIONS, expectData: 0 }), /expect_data_invalid/);
  const error = (() => { try { classifySite([...GOOD, "v1/extra.json"], OPTIONS); } catch (e) { return e; } })();
  assert.equal(error.path, "v1/extra.json", "refusals name the offending path");
});

test("intake receipt validation refuses malformed receipts", () => {
  const good = receiptFor(miniBuild());
  validateIntakeReceipt(good);
  assert.throws(() => validateIntakeReceipt({ ...good, schema: "other" }), /intake_receipt_schema/);
  assert.throws(() => validateIntakeReceipt({ ...good, source_commit: "short" }), /intake_receipt_commit/);
  assert.throws(() => validateIntakeReceipt({ ...good, files: [] }), /intake_receipt_files/);
  assert.throws(() => validateIntakeReceipt({ ...good, files: [...good.files, good.files[0]] }), /intake_receipt_path/);
  assert.throws(() => validateIntakeReceipt({ ...good, files: [{ path: "../x.json", bytes: 1, sha256_raw: "a".repeat(64) }] }), /intake_receipt_path/);
  assert.throws(() => validateIntakeReceipt({ ...good, files: [{ path: "v1/x.json", bytes: 1, sha256_raw: "nope" }] }), /intake_receipt_entry/);
  assert.throws(() => validateIntakeReceipt({ ...good, catalogue: {} }), /intake_receipt_catalogue/);
});

test("site verification refuses any byte, hash, extra or missing file against the receipt", async (t) => {
  const { site, receiptPath, build } = await fixture(t);
  const receipt = JSON.parse(await readFile(receiptPath, "utf8"));
  const files = await verifySite(site, receipt);
  assert.equal(files.size, 10);
  assert.equal(files.get("v1/game/1.json").sha256, hash(build["v1/game/1.json"]));
  // Same length, different bytes.
  const flipped = build["v1/health.json"].replace("1", "2");
  await writeFile(join(site, "v1", "health.json"), flipped);
  await assert.rejects(verifySite(site, receipt), /site_sha256_mismatch/);
  await writeFile(join(site, "v1", "health.json"), build["v1/health.json"]);
  await appendFile(join(site, "favicon.svg"), "\n");
  await assert.rejects(verifySite(site, receipt), /site_bytes_mismatch/);
  await writeFile(join(site, "favicon.svg"), build["favicon.svg"]);
  await writeFile(join(site, "extra.txt"), "x");
  await assert.rejects(verifySite(site, receipt), /site_extra_file/);
  await rm(join(site, "extra.txt"));
  await rm(join(site, "v1", "setup", "1.json"));
  await assert.rejects(verifySite(site, receipt), /site_missing_file/);
  await writeFile(join(site, "v1", "setup", "1.json"), build["v1/setup/1.json"]);
  await verifySite(site, receipt);
  // prepareSite also applies the classification count.
  await assert.rejects(prepareSite({ site, receipt: receiptPath, expectData: 7, game: "1" }), /data_count_mismatch/);
  const prepared = await prepareSite({ site, receipt: receiptPath, ...OPTIONS });
  assert.equal(prepared.classified.data.length, 6);
});

test("emulated ASSETS: exact paths, root and SPA fallback, 404 otherwise", async (t) => {
  const { site, receiptPath } = await fixture(t);
  const { files, classified } = await prepareSite({ site, receipt: receiptPath, ...OPTIONS });
  const assets = makeAssets(files, classified.static);
  const get = (path, headers = {}, method = "GET") => assets(new Request("http://127.0.0.1" + path, { method, headers }));
  assert.equal((await get("/")).status, 200);
  assert.equal((await get("/")).headers.get("Content-Type"), "text/html; charset=utf-8");
  assert.equal(await (await get("/")).text(), files.get("index.html").bytes.toString());
  assert.equal((await get("/assets/index-syn1.js")).headers.get("Content-Type"), "text/javascript; charset=utf-8");
  assert.equal((await get("/assets/index-syn1.css")).headers.get("Content-Type"), "text/css; charset=utf-8");
  assert.equal((await get("/favicon.svg")).headers.get("Content-Type"), "image/svg+xml");
  assert.equal((await get("/deep/route", { Accept: "text/html,*/*" })).status, 200);
  assert.equal((await get("/deep/route", { Accept: "*/*" })).status, 404);
  assert.equal((await get("/missing.png", { Accept: "image/webp,*/*" })).status, 404);
  assert.equal((await get("/v1/manifest.json")).status, 404, "data never comes from assets");
  assert.equal((await get("/", {}, "HEAD")).body, null);
  assert.equal((await get("/", {}, "POST")).status, 405);
});

test("CLI refuses an existing --out and unreadable inputs before anything starts", async (t) => {
  const { dir, site, receiptPath } = await fixture(t);
  const out = join(dir, "out-existing");
  await mkdir(out);
  const existing = await capture(process.stderr, () => main(["--site", site, "--receipt", receiptPath, "--out", out, "--expect-data", "6", "--game", "1"]));
  assert.equal(existing.code, 2);
  assert.match(existing.text, /output_exists/);
  assert.deepEqual(await readdir(out), [], "existing output folder untouched");
  const fresh = join(dir, "out-fresh");
  const unreadable = await capture(process.stderr, () => main(["--site", site, "--receipt", join(dir, "nope.json"), "--out", fresh]));
  assert.equal(unreadable.code, 2);
  assert.match(unreadable.text, /intake_receipt_unreadable/);
  const wrongCount = await capture(process.stderr, () => main(["--site", site, "--receipt", receiptPath, "--out", fresh, "--game", "1"]));
  assert.equal(wrongCount.code, 2, "default --expect-data is the real build's 24");
  assert.match(wrongCount.text, /data_count_mismatch/);
  const missingArgs = await capture(process.stderr, () => main(["--site", site]));
  assert.equal(missingArgs.code, 2);
  assert.match(missingArgs.text, /arguments_required/);
  assert.equal(await readdir(dir).then(list => list.includes("out-fresh")), false, "no output folder on refusal");
});

test("synthetic end to end on our gateway: upload => byte-identical readback, 503/200 notice cycle, receipt file", { timeout: 55000 }, async (t) => {
  const { dir, site, receiptPath, build } = await fixture(t);
  const out = join(dir, "out");
  const run = await capture(process.stdout, () => main(["--site", site, "--receipt", receiptPath, "--out", out, "--expect-data", "6", "--game", "1"]));
  const report = JSON.parse(run.text);
  assert.equal(run.code, 0, JSON.stringify(report.checks.filter(c => !c.passed)) + JSON.stringify(report.failure ?? null));
  assert.equal(report.passed, true);
  assert.equal(report.schema, "pitcheezy-exhibit-host-local-v1");
  assert.equal(report.evidence_kind, "loopback_miniflare_our_gateway");
  assert.equal(report.source_commit, "a".repeat(40));
  assert.deepEqual(report.counts, { site_files: 10, static: 4, data: 6, site_bytes: Object.values(build).reduce((n, s) => n + Buffer.byteLength(s), 0) });
  assert.equal(report.fail, 0);
  assert.ok(report.pass >= 30);
  const data = report.files.filter(f => f.kind === "data");
  assert.equal(data.length, 6);
  assert.deepEqual(data.map(f => f.path), ["v1/setup/1.json", "v1/game/1.json", "v1/games/2026-01-01.json", "v1/dates.json", "v1/manifest.json", "v1/health.json"]);
  for (const row of data) {
    assert.equal(row.upload_status, 200, row.path); assert.equal(row.etag_returned, true, row.path);
    assert.equal(row.readback_status, 200, row.path); assert.equal(row.readback_equal, true, row.path);
    assert.equal(row.sha256, hash(build[row.path]), row.path);
  }
  for (const row of report.files.filter(f => f.kind === "static")) { assert.equal(row.readback_equal, true, row.path); assert.equal(row.upload_status, null); }
  assert.deepEqual([report.negative.unknown_game_status, report.negative.missing_advertised_date.status, report.negative.unauthenticated_put_status, report.negative.repeat_create_status], [404, 404, 401, 412]);
  assert.equal(report.negative.missing_advertised_date.date, "2026-01-02");
  assert.equal(report.notice.on.game_status, 503); assert.equal(report.notice.on.game_notice_header, "data_hold"); assert.equal(report.notice.on.page_status, 503);
  assert.equal(report.notice.off.game_status, 200); assert.equal(report.notice.off.page_status, 200);
  assert.ok(report.notice.on.first_503_after_ms !== null && report.notice.on.first_503_after_ms <= 10000);
  assert.equal(report.static_emulation.spa_fallback_status, 200); assert.equal(report.static_emulation.unknown_asset_status, 404);
  assert.equal(report.browser, null); assert.equal(report.access, null);
  assert.equal(report.cleanup.status, "complete");
  assert.equal(report.receipt_written, true);
  for (const name of ["worker.mjs", "gateway.mjs", "notice.mjs", "access.mjs", "telemetry.mjs"]) {
    assert.equal(report.gateway_sha256[name], hash(await readFile(new URL("../" + name, import.meta.url))));
  }
  assert.doesNotMatch(run.text, /127\.0\.0\.1|Bearer |pz_viewer=|PUBLISH_TOKEN|accessCodes/);
  const written = JSON.parse(await readFile(join(out, "receipt.json"), "utf8"));
  assert.equal(written.passed, true); assert.equal(written.pass, report.pass);
  assert.deepEqual(await readdir(out), ["receipt.json"], "no browser => receipt only");
});

test("a failing gateway readback is reported, not patched", { timeout: 55000 }, async (t) => {
  // The receipt and site agree, but a data file is not a JSON object: our gateway refuses it (400) and the
  // rehearsal must record the failure instead of altering or skipping the partner file.
  const build = { ...miniBuild(), "v1/setup/1.json": "[1,2,3]" };
  const { dir, site, receiptPath } = await fixture(t, build);
  const report = await runExhibitHostRehearsal({ site, receipt: receiptPath, out: join(dir, "out"), ...OPTIONS });
  assert.equal(report.passed, false);
  const row = report.files.find(f => f.path === "v1/setup/1.json");
  assert.equal(row.upload_status, 400); assert.equal(row.readback_status, 404); assert.equal(row.readback_equal, false);
  assert.ok(report.checks.some(c => c.name === "upload:v1/setup/1.json" && c.passed === false));
  assert.ok(report.checks.filter(c => c.name.startsWith("readback:") && c.passed).length === 5, "other files still read back");
  assert.equal(report.cleanup.status, "complete");
  assert.equal(await readFile(join(site, "v1", "setup", "1.json"), "utf8"), "[1,2,3]", "partner file untouched");
});

import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readdir, readFile, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { hash, classifySite } from "../exhibit-site.mjs";
import { runStage4Read } from "../exhibit-stage4-read.mjs";

const ORIGIN = "https://private-read.example.test", VERSION = "12345678-abcd-abcd-abcd-123456789012";
const CODE = "synthetic-stage4-access-CANARY", COOKIE = "__Host-pz_viewer=v3.123.456." + "a".repeat(64) + "." + "b".repeat(16) + "." + "c".repeat(64);
const EXCLUDED = ["/v1/game/849844.json", "/v1/setup/849844.json", "/v1/games/2026-10-01.json"];
function prepared() {
  const build = { "index.html": "<!doctype html><title>synthetic</title>", "favicon.svg": "<svg/>",
    "assets/index-test.js": "console.log('synthetic');", "assets/index-test.css": "body{}",
    "v1/setup/849843.json": '{}', "v1/game/849843.json": '{}', "v1/games/2026-09-30.json": '{}',
    "v1/dates.json": '{}', "v1/manifest.json": '{}', "v1/health.json": '{}' };
  const files = new Map(Object.entries(build).map(([path, text]) => { const bytes = Buffer.from(text); return [path, { bytes, sha256: hash(bytes) }]; }));
  return { files, classified: classifySite([...files.keys()], { expectData: 6 }),
    intake: { schema: "pitcheezy-exhibition-intake-v1", profile: "exhibition-c47fe6cb",
      source_commit: "c47fe6cb78479362e7250141da946814cc33bd31", data_generation_commit: "cb1cfa8f759fd77adc75595316a389208c752dba",
      catalogue: { advertised_dates: 1, missing_date_files: [] },
      files: [...files].map(([path, source]) => ({ path, bytes: source.bytes.length, sha256_raw: source.sha256 })) } };
}
async function fixture(t, override = null) {
  const root = await mkdtemp(join(tmpdir(), "pz-stage4-read-")); t.after(() => rm(root, { recursive: true, force: true }));
  const input = prepared(), calls = [], collectionBytes = Buffer.from('{"telemetry_enabled":false,"feedback_enabled":false}');
  const fetchImpl = async (url, init) => {
    const path = new URL(url).pathname + new URL(url).search, method = init.method ?? "GET";
    calls.push({ path, method });
    const altered = override ? await override({ path, method, init, calls }) : undefined;
    if (altered !== undefined) return altered;
    const headers = { "CF-Ray": "a123456789abcdef-ABC" };
    if (method === "DELETE") { assert.equal(init.headers.Cookie, COOKIE); return new Response(null, { status: 204, headers }); }
    if (method === "POST") {
      assert.equal(JSON.parse(init.body).code, CODE);
      return new Response('{"authenticated":true}', { headers: { ...headers, "Set-Cookie": COOKIE + "; Path=/; Secure; HttpOnly", "Content-Type": "application/json" } });
    }
    if (path.startsWith("/_publish/")) return new Response(null, { status: 503, headers });
    if (!new Headers(init.headers).has("Cookie")) return new Response("access required", { status: 401, headers: { ...headers, "X-Pitcheezy-Access": "required" } });
    assert.equal(new Headers(init.headers).get("Cookie"), COOKIE);
    if (EXCLUDED.includes(path) || path === "/v1/game/999999.json") return new Response("missing", { status: 404, headers });
    if (path === "/index.html") return new Response(null, { status: 307, headers: { ...headers, Location: "/" } });
    if (path === "/collection-settings.json") return new Response(collectionBytes, { headers });
    const key = path === "/" || path === "/?game=849843" ? "index.html" : path.slice(1);
    const source = input.files.get(key); assert.ok(source, path);
    const kind = key === "index.html" ? "text/html" : key.endsWith(".svg") ? "image/svg+xml" : key.endsWith(".js") ? "text/javascript" : key.endsWith(".css") ? "text/css" : "application/json";
    return new Response(method === "HEAD" ? null : source.bytes, { headers: { ...headers, "Content-Type": kind, ETag: '"abc"', "Cache-Control": "no-store, no-transform" } });
  };
  return { root, calls, input, collectionBytes,
    run: extra => runStage4Read({ target: { origin: ORIGIN }, prepared: input, accessCode: CODE, collectionBytes,
      outDir: join(root, "journal"), versionPin: VERSION, fetchImpl, ...extra }) };
}
async function journalText(root) { const out = join(root, "journal"); return (await Promise.all((await readdir(out)).map(n => readFile(join(out, n), "utf8")))).join("\n"); }

test("normal c47 acceptance is exactly 24 requests with 19 verifier checks and final logout", async t => {
  const fx = await fixture(t); const result = await fx.run();
  assert.equal(result.passed, true, JSON.stringify(result)); assert.equal(result.verifier_pass, 19);
  assert.equal(result.transport.attempted_requests, 24); assert.equal(result.transport.normal_requests, 23); assert.equal(result.transport.cleanup_requests, 1);
  assert.equal(fx.calls.length, 24); assert.deepEqual(fx.calls.slice(0, 4).map(c => c.path), ["/", "/favicon.svg", "/v1/manifest.json", "/_publish/v1/health.json"]);
  assert.equal(fx.calls.at(-1).method, "DELETE"); assert.equal(result.logout, "confirmed_204");
  for (const text of [JSON.stringify(result), await journalText(fx.root)]) for (const secret of [ORIGIN, CODE, COOKIE]) assert.equal(text.includes(secret), false);
});

test("unexpected authenticated status stops subsequent reads and spends only reserved logout", async t => {
  const fx = await fixture(t, ({ path, init }) => path === "/v1/setup/849843.json" && new Headers(init.headers).has("Cookie") ? new Response("bad", { status: 503 }) : undefined);
  const result = await fx.run(); assert.equal(result.passed, false); assert.equal(result.logout, "confirmed_204");
  assert.equal(fx.calls.length, 7); assert.equal(fx.calls.at(-1).method, "DELETE");
  assert.equal(fx.calls.filter(c => c.path === "/v1/game/849843.json").length, 0);
});

test("wrong bytes halt immediately despite verifier continuing its logical report, then logout", async t => {
  const fx = await fixture(t, ({ path }) => path === "/v1/setup/849843.json" ? new Response("changed", { headers: { ETag: '"abc"', "Cache-Control": "no-store, no-transform" } }) : undefined);
  const result = await fx.run(); assert.equal(result.passed, false); assert.equal(fx.calls.length, 7); assert.equal(result.logout, "confirmed_204");
  assert.equal(result.transport.failure, "remote_bytes_mismatch");
});

test("initial gate failure performs no login and no logout", async t => {
  const fx = await fixture(t, () => new Response("ungated", { status: 200 }));
  const result = await fx.run(); assert.equal(result.passed, false); assert.equal(fx.calls.length, 1); assert.equal(result.logout, "not_needed");
});

test("network exception never leaks credentials and reserved logout still executes", async t => {
  const fx = await fixture(t, ({ path }) => { if (path === "/v1/setup/849843.json") throw new Error(CODE + COOKIE + ORIGIN); });
  const result = await fx.run(); assert.equal(result.passed, false); assert.equal(result.logout, "confirmed_204"); assert.equal(fx.calls.length, 7);
  for (const text of [JSON.stringify(result), await journalText(fx.root)]) for (const secret of [ORIGIN, CODE, COOKIE]) assert.equal(text.includes(secret), false);
});

test("removed evaluation body is cancelled without parsing while its authenticated status is checked", async t => {
  let cancelled = 0;
  const fx = await fixture(t, ({ path }) => {
    if (!EXCLUDED.includes(path)) return;
    const stream = new ReadableStream({ start(controller) { controller.enqueue(new TextEncoder().encode("DO-NOT-INSPECT")); }, cancel() { cancelled++; } });
    return new Response(stream, { status: 404 });
  });
  const result = await fx.run(); assert.equal(result.passed, true); assert.equal(cancelled, 3);
});

test("collection mismatch still performs final logout, with no repeated verification", async t => {
  const fx = await fixture(t, ({ path }) => path === "/collection-settings.json" ? new Response("wrong") : undefined);
  const result = await fx.run(); assert.equal(result.passed, false); assert.equal(result.collection_matched, false);
  assert.equal(result.logout, "confirmed_204"); assert.equal(fx.calls.length, 24);
});

test("logout failure is not retried and prevents success", async t => {
  const fx = await fixture(t, ({ method }) => method === "DELETE" ? new Response("bad", { status: 503 }) : undefined);
  const result = await fx.run(); assert.equal(result.passed, false); assert.equal(result.logout, "unconfirmed"); assert.equal(fx.calls.length, 24);
  assert.equal(fx.calls.filter(c => c.method === "DELETE").length, 1);
});

test("missing cookie halts at login and cannot claim a logged-out session", async t => {
  const fx = await fixture(t, ({ method }) => method === "POST" ? new Response("{}") : undefined);
  const result = await fx.run(); assert.equal(result.passed, false); assert.equal(result.logout, "not_needed"); assert.equal(fx.calls.length, 5);
});

test("wrong candidate, changed local bytes or catalogue mismatch reject before dispatch", async t => {
  for (const mutate of [p => { p.intake.source_commit = "a".repeat(40); }, p => { p.intake.profile = "legacy"; },
    p => { p.files.get("v1/health.json").bytes = Buffer.from("changed"); }, p => { p.intake.catalogue.missing_date_files = ["2026-10-01"]; },
    p => { p.files.delete("favicon.svg"); }]) {
    const fx = await fixture(t); mutate(fx.input); await assert.rejects(fx.run()); assert.equal(fx.calls.length, 0);
    assert.equal((await readdir(fx.root)).length, 0);
  }
});

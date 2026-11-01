import test from "node:test";
import assert from "node:assert/strict";
import { mkdtemp, readFile, readdir, mkdir, rm } from "node:fs/promises";
import { join } from "node:path";
import { tmpdir } from "node:os";
import { createStage4Transport } from "../exhibit-stage4-transport.mjs";

const ORIGIN = "https://private-stage4.example.test", VERSION = "12345678-abcd-abcd-abcd-123456789012";
const RAY = "a123456789abcdef-ABC", CANARY = "PRIVATE-CREDENTIAL-NEVER-PERSIST-4567";
async function fixture(t, extra = {}) {
  const root = await mkdtemp(join(tmpdir(), "pz-stage4-transport-"));
  t.after(() => rm(root, { recursive: true, force: true }));
  const outDir = join(root, "journal");
  const options = { origin: ORIGIN, outDir, versionPin: VERSION, limit: 3, reserve: 1,
    allowed: [{ method: "GET", path: "/" }, { method: "DELETE", path: "/_access/v1/session" }],
    fetchImpl: async () => new Response("ok", { headers: { "CF-Ray": RAY } }), ...extra };
  return { root, outDir, options, transport: await createStage4Transport(options) };
}
async function filesText(out) { return (await Promise.all((await readdir(out)).filter(n => n.endsWith(".json")).map(n => readFile(join(out, n), "utf8")))).join("\n"); }

test("starts are durable before dispatch; headers only, UTC/Ray/version are recorded without credentials", async t => {
  let out, calls = 0;
  const fx = await fixture(t, { fetchImpl: async (url, init) => {
    calls++;
    const started = JSON.parse(await readFile(join(out, "request-001.started.private.json"), "utf8"));
    assert.equal(started.outcome, "pending"); assert.match(started.started_utc, /Z$/);
    assert.equal(init.redirect, "manual"); assert.equal(init.cache, "no-store");
    assert.equal(init.headers.Authorization, "Bearer " + CANARY);
    return new Response(CANARY, { headers: { "CF-Ray": RAY, "Set-Cookie": CANARY, ETag: '"internal-only"' } });
  } }); out = fx.outDir;
  const response = await fx.transport.fetch(ORIGIN + "/", { headers: { Authorization: "Bearer " + CANARY }, body: undefined }, { statuses: [200] });
  assert.equal(response.headers.get("ETag"), '"internal-only"'); assert.equal(await response.text(), CANARY);
  const row = JSON.parse(await readFile(join(out, "request-001.completed.private.json"), "utf8"));
  assert.equal(row.status, 200); assert.equal(row.ray, RAY); assert.equal(row.expected_deployment_version, VERSION);
  assert.equal(row.outcome, "response_headers_received"); assert.equal(calls, 1);
  assert.doesNotMatch(await filesText(out), new RegExp(CANARY + "|" + ORIGIN.replaceAll(".", "\\.")));
});

test("hard normal cap preserves exactly the reserved logout and prevents any extra dispatch", async t => {
  let calls = 0;
  const { transport } = await fixture(t, { fetchImpl: async (_, init) => { calls++; return new Response(init.method === "DELETE" ? null : "ok", { status: init.method === "DELETE" ? 204 : 200 }); } });
  await transport.fetch(ORIGIN + "/"); await transport.fetch(ORIGIN + "/");
  await assert.rejects(transport.fetch(ORIGIN + "/"), /request_budget_exhausted/);
  await transport.cleanupFetch(ORIGIN + "/_access/v1/session", { method: "DELETE" }, { statuses: [204] });
  await assert.rejects(transport.cleanupFetch(ORIGIN + "/_access/v1/session", { method: "DELETE" }), /request_budget_exhausted/);
  assert.equal(calls, 3); assert.equal(transport.summary().cleanup_requests, 1);
});

test("transport errors remain unknown, halt normal traffic, allow cleanup and never persist exception text", async t => {
  let calls = 0;
  const { outDir, transport } = await fixture(t, { fetchImpl: async (_, init) => {
    calls++; if (init.method === "GET") throw new Error(CANARY); return new Response(null, { status: 204 });
  } });
  await assert.rejects(transport.fetch(ORIGIN + "/"), /transport_or_journal_failed/);
  await assert.rejects(transport.fetch(ORIGIN + "/"), /transport_halted/);
  await transport.cleanupFetch(ORIGIN + "/_access/v1/session", { method: "DELETE" }, { statuses: [204] });
  assert.equal(calls, 2);
  const row = JSON.parse(await readFile(join(outDir, "request-001.completed.private.json"), "utf8"));
  assert.equal(row.outcome, "unknown"); assert.equal(row.status, null); assert.doesNotMatch(await filesText(outDir), new RegExp(CANARY));
});

for (const suffix of ["https://other.example.test/", ORIGIN + "/missing", ORIGIN + "/?token=secret", ORIGIN + "/a/../", ORIGIN + "/#secret", ORIGIN + "/%2e%2e/"]) {
  test("unapproved or normalized-away target is refused: " + suffix.replace(ORIGIN, "<origin>"), async t => {
    let calls = 0;
    const { transport } = await fixture(t, { fetchImpl: async () => { calls++; return new Response("ok"); } });
    await assert.rejects(transport.fetch(suffix)); assert.equal(calls, 0);
  });
}

test("unexpected method or status halts without retry; arbitrary Ray header is discarded", async t => {
  let calls = 0;
  const { transport, outDir } = await fixture(t, { fetchImpl: async () => { calls++; return new Response("bad", { status: 503, headers: { "CF-Ray": CANARY } }); } });
  await assert.rejects(transport.fetch(ORIGIN + "/", {}, { statuses: [200] }), /unexpected_status/);
  await assert.rejects(transport.fetch(ORIGIN + "/"), /transport_halted/);
  assert.equal(calls, 1); assert.doesNotMatch(await filesText(outDir), new RegExp(CANARY));
  const second = await fixture(t);
  await assert.rejects(second.transport.fetch(ORIGIN + "/", { method: "PUT" }), /operation_refused/);
  assert.equal(second.transport.summary().attempted_requests, 0);
});

test("only explicitly allowed relative root redirect is returned, never followed", async t => {
  for (const location of ["/", ORIGIN + "/", "https://other.example.test/", "/?secret=x"]) {
    let calls = 0;
    const { transport } = await fixture(t, { fetchImpl: async (_, init) => {
      calls++; assert.equal(init.redirect, "manual"); return new Response(null, { status: 307, headers: { Location: location } });
    } });
    const result = transport.fetch(ORIGIN + "/", {}, { statuses: [307], redirectTo: "/" });
    if (location === "/") assert.equal((await result).status, 307); else await assert.rejects(result, /redirect_refused/);
    assert.equal(calls, 1);
  }
});

test("existing output is refused; in-flight dispatch blocks concurrent request", async t => {
  let release;
  const { options, transport } = await fixture(t, { fetchImpl: () => new Promise(resolve => { release = () => resolve(new Response("ok")); }) });
  await assert.rejects(createStage4Transport(options));
  const first = transport.fetch(ORIGIN + "/");
  while (!release) await new Promise(r => setTimeout(r, 1));
  await assert.rejects(transport.fetch(ORIGIN + "/"), /parallel_request_refused/);
  release(); await first; assert.equal(transport.summary().attempted_requests, 1);
});

test("completion journal failure leaves a started record and does not dispatch another normal request", async t => {
  let out, calls = 0;
  const fx = await fixture(t, { fetchImpl: async () => {
    calls++; await mkdir(join(out, "request-001.completed.private.json")); return new Response("ok");
  } }); out = fx.outDir;
  await assert.rejects(fx.transport.fetch(ORIGIN + "/"));
  await assert.rejects(fx.transport.fetch(ORIGIN + "/"), /transport_halted/);
  assert.equal(calls, 1); assert.equal(fx.transport.summary().pending_possible, true);
  assert.equal(JSON.parse(await readFile(join(out, "request-001.started.private.json"), "utf8")).outcome, "pending");
});

test("failed pre-send journal cannot consume the logout sequence or dispatch normal traffic", async t => {
  let calls = 0;
  const { outDir, transport } = await fixture(t, { fetchImpl: async () => { calls++; return new Response(null, { status: 204 }); } });
  await mkdir(join(outDir, "request-001.started.private.json"));
  await assert.rejects(transport.fetch(ORIGIN + "/"));
  assert.equal(calls, 0);
  await transport.cleanupFetch(ORIGIN + "/_access/v1/session", { method: "DELETE" }, { statuses: [204] });
  assert.equal(calls, 1);
  assert.equal(JSON.parse(await readFile(join(outDir, "request-002.completed.private.json"), "utf8")).status, 204);
});

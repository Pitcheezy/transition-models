import test from "node:test";
import assert from "node:assert/strict";
import { createServer } from "node:http";
import { createHash } from "node:crypto";
import { mkdtemp, writeFile, readFile, rm } from "node:fs/promises";
import { tmpdir } from "node:os";
import { join, resolve, dirname, basename } from "node:path";
import { fileURLToPath } from "node:url";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { Miniflare } from "miniflare";
import { prepare, dryRun, transmit, PublisherError } from "../publisher.mjs";

const token = "synthetic-publisher-test-token-with-no-account-permissions";
const hash = bytes => createHash("sha256").update(bytes).digest("hex");
const bytes = Buffer.from('{ "synthetic": true }\n');
const etag = '"' + "a".repeat(32) + '"';
const tag2 = '"' + "b".repeat(32) + '"';
const makePlan = (changes = {}) => ({
  schema: "pitcheezy-upload-plan-v1", origin: "https://upload.example.test",
  allow_loopback_http: false, method: "PUT", path: "/v1/game/123.json",
  condition: { if_none_match: "*" }, source_file: "public-example.json", sha256: hash(bytes), ...changes,
});
const success = (p = makePlan(), input = bytes) => new Response(JSON.stringify({
  stored: true, deleted: p.method === "DELETE",
  sha256: p.method === "DELETE" ? hash(new Uint8Array()) : hash(input), schema_validated: false,
}), { headers: { "Content-Type": "application/json", ETag: etag } });

async function local(handler) {
  const sockets = new Set();
  const server = createServer(handler);
  server.on("connection", socket => { sockets.add(socket); socket.on("close", () => sockets.delete(socket)); });
  await new Promise(resolve => server.listen(0, "127.0.0.1", resolve));
  return { origin: "http://127.0.0.1:" + server.address().port,
    close: async () => {
      for (const socket of sockets) socket.destroy();
      await new Promise(resolve => server.close(resolve));
    } };
}
const drain = async request => { const chunks = []; for await (const chunk of request) chunks.push(chunk); return Buffer.concat(chunks); };

test("default dry-run validates exact source bytes without network or credentials", () => {
  const result = dryRun(makePlan(), bytes);
  assert.equal(result.outcome, "dry_run");
  assert.equal(result.attempted, false);
  assert.equal(result.sha256, hash(bytes));
  assert.equal(result.schema_validated, false);
  assert.ok(!JSON.stringify(result).includes("upload.example.test"));
  assert.throws(() => dryRun(makePlan(), Buffer.from("{}")), /source_sha_mismatch/);
});

test("invalid origins, preconditions and source identities are refused before fetch", async () => {
  const cases = [
    { origin: "http://example.test" }, { origin: "https://secret@example.test" },
    { origin: "https://example.test/" }, { origin: "https://example.test?secret=1" },
    { origin: "https://example.test#token" }, { path: "/v1%2fgame/123.json" },
    { path: "/v1/game/../health.json" }, { condition: null },
    { condition: { if_match: "*" } }, { source_file: "../private.json" },
    { method: "POST" }, { method: "DELETE", source_file: null, sha256: null },
  ];
  let calls = 0;
  for (const item of cases) await assert.rejects(
    transmit(makePlan(item), bytes, token, { fetchImpl: () => { calls++; throw Error(); } }),
    PublisherError
  );
  assert.equal(calls, 0);
});

test("conditional success and HEAD metadata are distinct", async () => {
  const result = await transmit(makePlan(), bytes, token, { fetchImpl: async (_url, init) => {
    assert.equal(init.redirect, "error");
    assert.equal(init.credentials, "omit");
    assert.equal(init.headers["If-None-Match"], "*");
    assert.equal(init.headers["X-Content-SHA256"], hash(bytes));
    return success();
  } });
  assert.equal(result.outcome, "stored");
  assert.equal(result.etag, etag);
  const head = makePlan({ method: "HEAD", condition: null, source_file: null, sha256: null });
  const observed = await transmit(head, null, token, { fetchImpl: async () => new Response(null,
    { headers: { ETag: etag, "X-Publish-Deleted": "false", "X-Content-SHA256": hash(bytes) } }) });
  assert.equal(observed.outcome, "observed");
  assert.equal(observed.metadata_only, true);
  assert.equal((await transmit(head, null, token, { fetchImpl: async () => new Response(null, { status: 404 }) })).outcome, "missing");
});

test("every retry keeps one private body snapshot and original conditional write", async () => {
  const input = new Uint8Array(bytes); const seen = []; let call = 0;
  const result = await transmit(makePlan(), input, token, { backoffMs: 0,
    fetchImpl: async (_url, init) => {
      seen.push({ body: Buffer.from(init.body).toString(), condition: init.headers["If-None-Match"] });
      input.fill(120); init.body.fill(121);
      return ++call === 1 ? new Response(null, { status: 503 }) : success();
    } });
  assert.equal(result.outcome, "stored");
  assert.deepEqual(seen, Array(2).fill({ body: bytes.toString(), condition: "*" }));
});

test("uncertain write then conflict is not falsely called failed or successful", async () => {
  let n = 0;
  const result = await transmit(makePlan(), bytes, token, { backoffMs: 0,
    fetchImpl: async () => ++n === 1 ? new Response(null, { status: 503 }) : new Response(null, { status: 412 }) });
  assert.equal(result.outcome, "conflict_or_already_applied");
  assert.equal(n, 2);
  const clean = await transmit(makePlan(), bytes, token, { fetchImpl: async () => new Response(null, { status: 412 }) });
  assert.equal(clean.outcome, "conflict");
});

test("401/403/428 and validation failures are never retried", async () => {
  for (const status of [400, 401, 403, 413, 415, 422, 428]) {
    let n = 0;
    const receipt = await transmit(makePlan(), bytes, token, { fetchImpl: async () => {
      n++; return new Response("private source error", { status });
    } });
    assert.equal(receipt.outcome, "rejected");
    assert.equal(n, 1);
    assert.ok(!JSON.stringify(receipt).includes("private source error"));
  }
});

test("exhausted transient errors preserve possible storage", async () => {
  for (const fetchImpl of [async () => { throw Error("secret URL and token"); },
    async () => new Response(null, { status: 503 })]) {
    const r = await transmit(makePlan(), bytes, token, { fetchImpl, backoffMs: 0 });
    assert.equal(r.outcome, "unknown"); assert.equal(r.attempts.length, 3);
    assert.ok(!JSON.stringify(r).includes("secret"));
  }
});

test("malformed, oversized or wrongly certified success is unknown without blind retry", async () => {
  for (const response of [
    new Response("invalid", { headers: { ETag: etag, "Content-Type": "application/json" } }),
    new Response("x".repeat(2049), { headers: { ETag: etag, "Content-Type": "application/json" } }),
    new Response(JSON.stringify({ stored: true, deleted: false, sha256: hash(bytes), schema_validated: true }),
      { headers: { ETag: etag, "Content-Type": "application/json" } }),
    new Response("{}", { headers: { ETag: "weak", "Content-Type": "application/json" } }),
  ]) {
    let calls = 0;
    const r = await transmit(makePlan(), bytes, token, { fetchImpl: async () => { calls++; return response; } });
    assert.equal(r.outcome, "unknown"); assert.equal(calls, 1);
  }
});

test("real slow partial 200 is timed out; retry sends same bytes and old condition", async () => {
  const received = []; let n = 0;
  const server = await local(async (req, res) => {
    received.push({ body: (await drain(req)).toString(), condition: req.headers["if-none-match"] });
    if (++n === 1) {
      res.writeHead(200, { "Content-Type": "application/json", ETag: etag });
      res.write('{"stored":');
    } else { res.writeHead(412); res.end(); }
  });
  try {
    const r = await transmit(makePlan({ origin: server.origin, allow_loopback_http: true }), bytes, token,
      { timeoutMs: 150, totalMs: 1500, backoffMs: 0 });
    assert.equal(r.outcome, "conflict_or_already_applied");
    assert.deepEqual(received, Array(2).fill({ body: bytes.toString(), condition: "*" }));
  } finally { await server.close(); }
});

test("real long Retry-After is deferred within total window", async () => {
  let calls = 0;
  const server = await local(async (req, res) => {
    await drain(req); calls++; res.writeHead(429, { "Retry-After": "60" }); res.end();
  });
  try {
    const r = await transmit(makePlan({ origin: server.origin, allow_loopback_http: true }), bytes, token,
      { timeoutMs: 1000, totalMs: 2000 });
    assert.equal(r.outcome, "deferred"); assert.equal(r.retry_after_seconds, 60); assert.equal(calls, 1);
    assert.ok(r.elapsed_ms < 2000);
  } finally { await server.close(); }
});

test("zero Retry-After can retry without switching condition", async () => {
  let calls = 0;
  const r = await transmit(makePlan(), bytes, token, { backoffMs: 0, fetchImpl: async () =>
    ++calls === 1 ? new Response(null, { status: 429, headers: { "Retry-After": "0" } }) : success() });
  assert.equal(r.outcome, "stored"); assert.equal(calls, 2);
});

test("real redirect never forwards publisher token to another server", async () => {
  let reached = 0;
  const target = await local((req, res) => { reached++; res.end(); });
  const source = await local(async (req, res) => { await drain(req); res.writeHead(307, { Location: target.origin }); res.end(); });
  try {
    const r = await transmit(makePlan({ origin: source.origin, allow_loopback_http: true }), bytes, token,
      { backoffMs: 0, maxAttempts: 1 });
    assert.equal(r.outcome, "unknown"); assert.equal(reached, 0);
  } finally { await source.close(); await target.close(); }
});

test("real Worker creates, inspects, withdraws and restores with distinct ETags", { timeout: 30000 }, async () => {
  const mf = new Miniflare({
    modules: true, modulesRoot: fileURLToPath(new URL("../", import.meta.url)),
    scriptPath: fileURLToPath(new URL("../worker.mjs", import.meta.url)), compatibilityDate: "2026-07-30",
    r2Buckets: ["PUBLISH_BUCKET"],
    ratelimits: { PUBLISH_LIMITER: { namespace_id: "1002", simple: { limit: 60, period: 60 } } },
    bindings: { DATA_READ_ENABLED: "true", UPLOAD_ENABLED: "true", PUBLISH_TOKEN_SHA256: hash(token) },
  });
  try {
    await mf.ready;
    const options = { fetchImpl: (url, init) => mf.dispatchFetch(url, init), backoffMs: 0 };
    const created = await transmit(makePlan(), bytes, token, options);
    assert.equal(created.outcome, "stored");
    const headPlan = makePlan({ method: "HEAD", condition: null, source_file: null, sha256: null });
    const head = await transmit(headPlan, null, token, options);
    assert.equal(head.current_sha256, hash(bytes));
    const delPlan = makePlan({ method: "DELETE", condition: { if_match: created.etag }, source_file: null, sha256: null });
    const deleted = await transmit(delPlan, null, token, options);
    assert.equal(deleted.outcome, "stored"); assert.equal(deleted.sha256, hash(new Uint8Array()));
    assert.equal((await mf.dispatchFetch("http://localhost/v1/game/123.json")).status, 404);
    const restored = await transmit(makePlan({ condition: { if_match: deleted.etag } }), bytes, token, options);
    assert.equal(restored.outcome, "stored"); assert.notEqual(restored.etag, created.etag);
    assert.equal((await transmit(delPlan, null, token, options)).outcome, "conflict");
    assert.equal(await (await mf.dispatchFetch("http://localhost/v1/game/123.json")).text(), bytes.toString());
  } finally { await mf.dispose(); }
});

test("CLI dry-run needs no token; explicit loopback execute stores once and leaves inputs intact", async () => {
  const dir = await mkdtemp(join(tmpdir(), "pitcheezy-publisher-test-"));
  const sourceFile = join(dir, "public-example.json"), planFile = join(dir, "plan.json");
  const cli = fileURLToPath(new URL("../publisher-cli.mjs", import.meta.url));
  const run = promisify(execFile);
  let requests = 0;
  const server = await local(async (req, res) => {
    requests++; const raw = await drain(req); assert.deepEqual(raw, bytes);
    res.writeHead(200, { "Content-Type": "application/json", ETag: tag2 });
    res.end(JSON.stringify({ stored: true, deleted: false, sha256: hash(raw), schema_validated: false }));
  });
  try {
    await writeFile(sourceFile, bytes);
    await writeFile(planFile, JSON.stringify(makePlan({ origin: server.origin, allow_loopback_http: true })));
    const frozen = await readFile(planFile);
    const args = [cli, "--plan", planFile];
    const dry = await run(process.execPath, args, { env: { ...process.env, PITCHEEZY_PUBLISH_TOKEN: "invalid" } });
    assert.equal(JSON.parse(dry.stdout).outcome, "dry_run"); assert.equal(requests, 0);
    const sent = await run(process.execPath, [...args, "--execute"], { env: { ...process.env, PITCHEEZY_PUBLISH_TOKEN: token } });
    assert.equal(JSON.parse(sent.stdout).outcome, "stored"); assert.equal(requests, 1);
    assert.ok(!sent.stdout.includes(token) && !sent.stdout.includes(server.origin));
    assert.deepEqual(await readFile(planFile), frozen); assert.deepEqual(await readFile(sourceFile), bytes);
  } finally { await server.close();
    assert.equal(dirname(resolve(dir)), resolve(tmpdir()));
    assert.ok(basename(dir).startsWith("pitcheezy-publisher-test-"));
    await rm(dir, { recursive: true, force: true }); }
});


test("checked-in plan is a portable no-network dry run", async () => {
  const run = promisify(execFile);
  const cli = fileURLToPath(new URL("../publisher-cli.mjs", import.meta.url));
  const plan = fileURLToPath(new URL("../examples/publish-plan.json", import.meta.url));
  const result = await run(process.execPath, [cli, "--plan", plan], {
    env: { ...process.env, PITCHEEZY_PUBLISH_TOKEN: "not-valid-and-not-needed" },
  });
  const receipt = JSON.parse(result.stdout);
  assert.equal(receipt.outcome, "dry_run"); assert.equal(receipt.attempted, false);
});

test("total deadline also bounds repeated servers that never return headers", async () => {
  let calls = 0;
  const server = await local(async request => { await drain(request); calls++; });
  try {
    const r = await transmit(makePlan({ origin: server.origin, allow_loopback_http: true }), bytes, token,
      { timeoutMs: 85, totalMs: 120, backoffMs: 0 });
    assert.equal(r.outcome, "unknown"); assert.ok(calls <= 3);
    assert.ok(r.elapsed_ms >= 100 && r.elapsed_ms < 1500);
  } finally { await server.close(); }
});


test("unverified 2xx, redirect and remote timeout preserve possible writes without retry", async () => {
  for (const method of ["PUT", "DELETE"]) for (const status of [201, 202, 204, 206, 301, 302, 408, 499]) {
    let calls = 0;
    const p = method === "PUT" ? makePlan() : makePlan({ method, condition: { if_match: etag }, source_file: null, sha256: null });
    const r = await transmit(p, method === "PUT" ? bytes : null, token, { fetchImpl: async () => {
      calls++; return new Response(null, { status });
    } });
    assert.equal(r.outcome, "unknown", method + ":" + status); assert.equal(calls, 1);
  }
});

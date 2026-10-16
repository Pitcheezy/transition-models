import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { Miniflare } from "miniflare";
import worker from "../gateway.mjs";

const TOKEN = "synthetic-scoped-publisher-token-not-a-real-credential";
const OPERATOR = "synthetic-scoped-notice-token-not-a-real-credential";
const KEY = "v1/health.json";
const EXPIRY = "2030-01-01T00:00:00.000Z";
const DEADLINE = Date.parse(EXPIRY);
const body = '{"synthetic":true}';
const digest = bytes => createHash("sha256").update(bytes).digest("hex");
const scope = () => ({ PUBLISH_KEY_SCOPE: KEY, PUBLISH_EXPIRES_AT: EXPIRY });

class Bucket {
  objects = new Map(); reads = 0; writes = 0;
  snapshot(key) {
    const v = this.objects.get(key);
    return v ? { ...v, arrayBuffer: async () => v.bytes.slice().buffer } : null;
  }
  async get(key) { this.reads++; return this.snapshot(key); }
  async head(key) { this.reads++; return this.snapshot(key); }
  async list({ prefix }) { return { objects: [...this.objects.keys()].filter(k => k.startsWith(prefix)).map(key => ({ key })), truncated: false }; }
  async put(key, bytes, options) {
    this.writes++;
    const current = this.objects.get(key);
    const match = options.onlyIf.get("If-Match"), none = options.onlyIf.get("If-None-Match");
    if (match && current?.httpEtag !== match || none === "*" && current) return null;
    assert.equal(options.sha256, digest(bytes));
    const value = { bytes: bytes.slice(), size: bytes.byteLength, customMetadata: { ...options.customMetadata },
      httpEtag: '"' + createHash("md5").update(bytes).digest("hex") + '"' };
    this.objects.set(key, value); return this.snapshot(key);
  }
}
function fixture(extra = {}) {
  const env = { UPLOAD_ENABLED: "true", DATA_READ_ENABLED: "true", PUBLISH_TOKEN_SHA256: digest(TOKEN),
    NOTICE_TOKEN_SHA256: digest(OPERATOR), PUBLISH_BUCKET: new Bucket(),
    PUBLISH_LIMITER: { limit: async () => ({ success: true }) },
    ASSETS: { fetch: async () => new Response("synthetic page") }, ...extra };
  const call = (path, init = {}) => worker.fetch(new Request("https://synthetic.example.test" + path, init), env);
  return { env, call };
}
function request(method, key = KEY, condition = null) {
  return new Request("https://synthetic.example.test/_publish/" + key, { method,
    ...(method === "PUT" ? { body } : {}), headers: { Authorization: "Bearer " + TOKEN,
      ...(method === "PUT" ? { "Content-Type": "application/json", "X-Content-SHA256": digest(body) } : {}),
      ...(condition || (method === "PUT" ? { "If-None-Match": "*" } : method === "DELETE" ? { "If-Match": '"' + "0".repeat(32) + '"' } : {})) } });
}
async function assertBlocked(env, status, code, key = KEY) {
  let limitCalls = 0, bodyReads = 0;
  env.PUBLISH_LIMITER = { limit: async () => { limitCalls++; return { success: true }; } };
  for (const method of ["PUT", "DELETE", "HEAD"]) {
    const req = request(method, key);
    Object.defineProperty(req, "body", { get() { bodyReads++; throw new Error("body must remain unread"); } });
    const response = await worker.fetch(req, env);
    assert.equal(response.status, status, method);
    assert.equal(await response.text(), method === "HEAD" ? "" : JSON.stringify({ error: code }));
    assert.equal(response.headers.get("Cache-Control"), "no-store");
  }
  assert.equal(limitCalls, 0); assert.equal(bodyReads, 0);
  assert.equal(env.PUBLISH_BUCKET.reads, 0); assert.equal(env.PUBLISH_BUCKET.writes, 0);
}

test("both optional fields absent preserve legacy multi-key PUT, private HEAD and DELETE", async () => {
  const { env } = fixture();
  for (const key of [KEY, "v1/game/123.json"]) {
    const saved = await worker.fetch(request("PUT", key), env); assert.equal(saved.status, 200);
    assert.equal((await worker.fetch(request("HEAD", key), env)).status, 200);
    assert.equal((await worker.fetch(request("DELETE", key, { "If-Match": saved.headers.get("ETag") }), env)).status, 200);
  }
});

test("partial and explicitly empty optional pairs fail closed before limiter, body or storage", async () => {
  for (const extra of [{ PUBLISH_KEY_SCOPE: KEY }, { PUBLISH_EXPIRES_AT: EXPIRY },
    { PUBLISH_KEY_SCOPE: undefined, PUBLISH_EXPIRES_AT: undefined },
    { PUBLISH_KEY_SCOPE: "", PUBLISH_EXPIRES_AT: "" },
    ...[null, false, 1, [], {}].flatMap(v => [{ ...scope(), PUBLISH_KEY_SCOPE: v }, { ...scope(), PUBLISH_EXPIRES_AT: v }])]) {
    await assertBlocked(fixture(extra).env, 503, "upload_scope_not_configured");
  }
});

test("scope is one exact existing allowed storage key, not a prefix, list, URL or encoded path", async () => {
  for (const value of ["/v1/health.json", "v1/", "v1/*", "v1/health.json,v1/dates.json", "v1/health.json?x=1",
    "https://synthetic.example.test/v1/health.json", "v1/%68ealth.json", "v1/game/../health.json", "v1/game/01.json",
    "v1/games/2026-02-30.json", "v1/games/0000-01-01.json", "_notice/state.json"]) {
    await assertBlocked(fixture({ ...scope(), PUBLISH_KEY_SCOPE: value }).env, 503, "upload_scope_not_configured");
  }
});

test("expiry accepts only a real year-one-or-later UTC .sssZ calendar value", async () => {
  for (const value of ["", "2030-01-01T00:00:00Z", "2030-01-01T00:00:00.000+00:00", "2030-01-01",
    "2030-02-30T00:00:00.000Z", "2030-02-29T00:00:00.000Z", "2030-04-31T00:00:00.000Z",
    "2030-01-01T24:00:00.000Z", "0000-01-01T00:00:00.000Z", "2030-01-01T00:00:00.000Z "]) {
    await assertBlocked(fixture({ ...scope(), PUBLISH_EXPIRES_AT: value }).env, 503, "upload_scope_not_configured");
  }
  // A structurally valid old timestamp is expired, not misconfigured.
  await assertBlocked(fixture({ ...scope(), PUBLISH_EXPIRES_AT: "0001-01-01T00:00:00.000Z" }).env, 403, "upload_expired");
  assert.equal((await worker.fetch(request("PUT"), fixture({ ...scope(), PUBLISH_EXPIRES_AT: "2032-02-29T23:59:59.999Z" }).env)).status, 200);
});

test("same credential cannot write, delete or inspect another otherwise-permitted key", async () => {
  for (const key of ["v1/dates.json", "v1/game/123.json", "v1/setup/123.json", "v1/games/2026-10-17.json"])
    await assertBlocked(fixture(scope()).env, 403, "upload_scope_forbidden", key);
});

test("the exact deadline is closed while the preceding millisecond remains usable", async t => {
  let now = DEADLINE - 1; t.mock.method(Date, "now", () => now);
  const { env } = fixture(scope());
  const saved = await worker.fetch(request("PUT"), env); assert.equal(saved.status, 200);
  assert.equal((await worker.fetch(request("HEAD"), env)).status, 200);
  const writes = env.PUBLISH_BUCKET.writes, reads = env.PUBLISH_BUCKET.reads;
  now = DEADLINE;
  for (const method of ["PUT", "DELETE", "HEAD"]) {
    const r = await worker.fetch(request(method, KEY, { "If-Match": saved.headers.get("ETag") }), env);
    assert.equal(r.status, 403);
  }
  assert.equal(env.PUBLISH_BUCKET.writes, writes); assert.equal(env.PUBLISH_BUCKET.reads, reads);
});

test("expiry while awaiting the limiter blocks all body and private storage reads", async t => {
  let now; t.mock.method(Date, "now", () => now);
  for (const method of ["PUT", "DELETE", "HEAD"]) {
    now = DEADLINE - 1; const { env } = fixture(scope()); let bodies = 0;
    env.PUBLISH_LIMITER = { limit: async () => { now = DEADLINE; return { success: true }; } };
    const req = request(method);
    Object.defineProperty(req, "body", { get() { bodies++; throw new Error("must not read body"); } });
    assert.equal((await worker.fetch(req, env)).status, 403);
    assert.equal(bodies, 0); assert.equal(env.PUBLISH_BUCKET.reads, 0); assert.equal(env.PUBLISH_BUCKET.writes, 0);
  }
});

test("a PUT whose body completes after expiry never reaches conditional storage", async t => {
  let now = DEADLINE - 1; t.mock.method(Date, "now", () => now);
  const { env } = fixture(scope()); const req = request("PUT"); let reads = 0;
  Object.defineProperty(req, "body", { get: () => ({ getReader: () => ({
    read: async () => { now = DEADLINE; reads++; return reads === 1 ? { done: false, value: new TextEncoder().encode(body) } : { done: true }; },
    releaseLock() {}, cancel: async () => {},
  }) }) });
  const r = await worker.fetch(req, env); assert.equal(r.status, 403);
  assert.equal((await r.json()).error, "upload_expired"); assert.equal(reads, 2); assert.equal(env.PUBLISH_BUCKET.writes, 0);
});

test("PUT and DELETE recheck expiry after the last asynchronous record digest", async t => {
  let now, calls; t.mock.method(Date, "now", () => now);
  const original = crypto.subtle.digest.bind(crypto.subtle);
  t.mock.method(crypto.subtle, "digest", async (...args) => {
    const value = await original(...args); calls++;
    if (calls === 3) now = DEADLINE; // auth digest, payload/empty digest, final private record digest
    return value;
  });
  for (const method of ["PUT", "DELETE"]) {
    now = DEADLINE - 1; calls = 0; const { env } = fixture(scope());
    const r = await worker.fetch(request(method), env);
    assert.equal(calls, 3); assert.equal(r.status, 403); assert.equal(env.PUBLISH_BUCKET.writes, 0);
  }
});

test("valid scoped writes retain checksum, conflict, tombstone, restore and strong ETag semantics", async () => {
  const { env, call } = fixture(scope());
  const saved = await worker.fetch(request("PUT"), env); assert.equal(saved.status, 200);
  const first = saved.headers.get("ETag"); assert.match(first, /^"[a-f0-9]{32}"$/);
  assert.equal(saved.headers.get("Cache-Control"), "no-store, no-transform");
  assert.equal((await worker.fetch(request("PUT"), env)).status, 412);
  const deleted = await worker.fetch(request("DELETE", KEY, { "If-Match": first }), env); assert.equal(deleted.status, 200);
  assert.equal((await call("/" + KEY)).status, 404);
  const restored = await worker.fetch(request("PUT", KEY, { "If-Match": deleted.headers.get("ETag") }), env); assert.equal(restored.status, 200);
  assert.notEqual(restored.headers.get("ETag"), first);
  assert.equal((await worker.fetch(request("DELETE", KEY, { "If-Match": first }), env)).status, 412);
  assert.equal(await (await call("/" + KEY)).text(), body);
});

test("invalid or expired upload restrictions do not control public viewers or the notice operator", async () => {
  for (const extra of [{ PUBLISH_KEY_SCOPE: "invalid" }, { ...scope(), PUBLISH_EXPIRES_AT: "2001-01-01T00:00:00.000Z" }]) {
    const { env, call } = fixture(); assert.equal((await worker.fetch(request("PUT"), env)).status, 200);
    Object.assign(env, extra);
    assert.equal((await call("/")).status, 200); assert.equal(await (await call("/" + KEY)).text(), body);
    assert.equal((await call("/" + KEY, { method: "HEAD" })).status, 200);
    const control = { Authorization: "Bearer " + OPERATOR };
    assert.equal((await call("/_notice/v1/state", { headers: control })).status, 200);
    const on = await call("/_notice/v1/state", { method: "PUT", headers: { ...control,
      "Content-Type": "application/json", "If-None-Match": "*" },
      body: JSON.stringify({ active: true, operator: "test", reason: "synthetic drill", message_id: "maintenance" }) });
    assert.equal(on.status, 200); assert.equal((await call("/")).status, 503);
  }
});

test("actual loopback Worker/R2 enforces exact scope and expiry without changing public bytes", { timeout: 30000 }, async () => {
  for (const expiry of [EXPIRY, "2001-01-01T00:00:00.000Z"]) {
    const mf = new Miniflare({ host: "127.0.0.1", port: 0, modules: true,
      scriptPath: fileURLToPath(new URL("../worker.mjs", import.meta.url)), compatibilityDate: "2026-07-30",
      r2Buckets: ["PUBLISH_BUCKET"], ratelimits: { PUBLISH_LIMITER: { namespace_id: "1002", simple: { limit: 60, period: 60 } } },
      bindings: { UPLOAD_ENABLED: "true", DATA_READ_ENABLED: "true", PUBLISH_TOKEN_SHA256: digest(TOKEN),
        PUBLISH_KEY_SCOPE: KEY, PUBLISH_EXPIRES_AT: expiry } });
    try {
      const origin = (await mf.ready).origin; assert.equal(new URL(origin).hostname, "127.0.0.1");
      const send = (method, key = KEY, condition = null) => {
        const req = request(method, key, condition);
        return fetch(origin + "/_publish/" + key, { method, headers: req.headers, ...(method === "PUT" ? { body } : {}), redirect: "manual" });
      };
      if (expiry === EXPIRY) {
        const saved = await send("PUT"); assert.equal(saved.status, 200);
        assert.equal((await send("HEAD")).status, 200);
        for (const method of ["PUT", "DELETE", "HEAD"]) assert.equal((await send(method, "v1/dates.json")).status, 403);
        assert.equal(await (await fetch(origin + "/" + KEY)).text(), body);
        const deleted = await send("DELETE", KEY, { "If-Match": saved.headers.get("ETag") }); assert.equal(deleted.status, 200);
        assert.equal((await fetch(origin + "/" + KEY)).status, 404);
      } else {
        for (const method of ["PUT", "DELETE", "HEAD"]) assert.equal((await send(method)).status, 403);
        assert.equal((await fetch(origin + "/" + KEY)).status, 404);
      }
    } finally { await mf.dispose(); }
  }
});

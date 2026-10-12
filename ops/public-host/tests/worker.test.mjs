import { readFileSync } from "node:fs";
import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import worker, { MAX_JSON_BYTES, permittedKey, sha256 } from "../gateway.mjs";

// Synthetic-only credentials and payloads, never an account secret or Song schema fixture.
const TOKEN = "synthetic-only-token-for-unit-tests-not-a-real-credential";
const digest = body => createHash("sha256").update(body).digest("hex");
const path = "/v1/game/123.json";

class Bucket {
  objects = new Map();
  writes = 0;
  snapshot(key) {
    const stored = this.objects.get(key);
    if (!stored) return null;
    return { ...stored, body: stored.bytes.slice(), arrayBuffer: async () => stored.bytes.slice().buffer, customMetadata: { ...stored.customMetadata } };
  }
  async get(key) { return this.snapshot(key); }
  async head(key) { return this.snapshot(key); }
  async put(key, bytes, options = {}) {
    assert.ok(options.onlyIf instanceof Headers, "writes must have atomic storage conditions");
    const current = this.objects.get(key);
    const match = options.onlyIf.get("If-Match");
    if (match && (!current || current.httpEtag !== match)) return null;
    if (options.onlyIf.get("If-None-Match") === "*" && current) return null;
    assert.equal(digest(bytes), options.sha256);
    const httpEtag = '"' + createHash("md5").update(bytes).digest("hex") + '"';
    this.objects.set(key, {
      httpEtag, size: bytes.length, bytes: bytes.slice(),
      customMetadata: { ...options.customMetadata },
    });
    this.writes++;
    return this.snapshot(key);
  }
}

async function fixture() {
  const env = {
    DATA_READ_ENABLED: "true", UPLOAD_ENABLED: "true",
    PUBLISH_TOKEN_SHA256: await sha256(new TextEncoder().encode(TOKEN)),
    PUBLISH_BUCKET: new Bucket(),
    PUBLISH_LIMITER: { limit: async () => ({ success: true }) },
    READ_ORIGIN: "https://ui.example.test",
    ASSETS: { fetch: async () => new Response("frontend", { headers: { "Content-Type": "text/html" } }) },
  };
  const call = (route, init = {}) => worker.fetch(new Request("https://host.example.test" + route, init), env);
  const put = (body = '{"synthetic":true}', condition = { "If-None-Match": "*" }, more = {}) => call("/_publish" + path, {
    method: "PUT", body, headers: {
      Authorization: "Bearer " + TOKEN, "Content-Type": "application/json",
      "X-Content-SHA256": digest(body), ...condition, ...more,
    },
  });
  const del = etag => call("/_publish" + path, {
    method: "DELETE", headers: { Authorization: "Bearer " + TOKEN, "If-Match": etag },
  });
  return { env, call, put, del };
}

test("date and file allowlist rejects temporary, private, encoded and impossible paths", () => {
  for (const valid of ["/v1/health.json", "/v1/manifest.json", "/v1/dates.json", path,
    "/v1/setup/123.json", "/v1/games/2024-02-29.json"]) assert.ok(permittedKey(valid), valid);
  for (const invalid of ["/v1/game/0.json", "/v1/game/-1.json", "/v1/game/01.json",
    "/v1/game/1.5.json", "/v1/games/2026-02-29.json", "/v1/games/2026-04-31.json",
    "/v1/games/2026-13-01.json", "/v1/.tmp", "/v1/game/123.mp4", "/v1%2fgame/123.json",
    "/v1/game/%31.json", "/v1/game/../manifest.json", "/v1/game/123.json/extra",
    "/v1/game/123.json.bak", "/v1/setup.json"]) assert.equal(permittedKey(invalid), null, invalid);
});

test("default env cannot publish or upload", async () => {
  const { env, call, put } = await fixture();
  delete env.DATA_READ_ENABLED;
  assert.equal((await call(path)).status, 503);
  delete env.UPLOAD_ENABLED;
  assert.equal((await put()).status, 503);
  assert.equal(env.PUBLISH_BUCKET.writes, 0);
});

test("gates accept only explicit true string", async () => {
  const { env, call, put } = await fixture();
  for (const value of [true, 1, "TRUE", "", "false"]) {
    env.DATA_READ_ENABLED = env.UPLOAD_ENABLED = value;
    assert.equal((await call(path)).status, 503);
    assert.equal((await put()).status, 503);
  }
});

test("upload token missing, invalid or wrong cannot mutate storage", async () => {
  const { env, put } = await fixture();
  for (const token of ["", "Bearer short", "Bearer " + "x".repeat(64), "Basic abc", "bearer " + TOKEN]) {
    assert.equal((await put(undefined, undefined, { Authorization: token })).status, 401);
  }
  assert.equal(env.PUBLISH_BUCKET.writes, 0);
});

test("invalid configured digest fails closed", async () => {
  const { env, put } = await fixture();
  env.PUBLISH_TOKEN_SHA256 = "not-a-sha";
  assert.equal((await put()).status, 503);
});

test("create, exact-byte read and HEAD provide Date Age and no-store", async () => {
  const { call, put } = await fixture();
  const body = '{ "synthetic": true, "label": "합성", "value": null }\n';
  const saved = await put(body);
  assert.equal(saved.status, 200);
  assert.equal((await saved.json()).schema_validated, false);
  const read = await call(path);
  assert.equal(await read.text(), body);
  assert.equal(read.headers.get("ETag"), saved.headers.get("ETag"));
  assert.equal(read.headers.get("Content-Length"), String(Buffer.byteLength(body)));
  assert.equal(read.headers.get("Age"), "0");
  assert.equal(read.headers.get("Cache-Control"), "no-store");
  assert.equal(read.headers.get("CDN-Cache-Control"), "no-store");
  assert.ok(Math.abs(Date.parse(read.headers.get("Date")) - Date.now()) < 2000);
  const head = await call(path, { method: "HEAD" });
  assert.equal(head.status, 200);
  assert.equal(await head.text(), "");
  assert.equal(head.headers.get("Content-Length"), String(Buffer.byteLength(body)));
});

test("cache validators do not turn changed or deleted objects into stale 304 responses", async () => {
  const { call, put, del } = await fixture();
  const first = await put();
  const tag = first.headers.get("ETag");
  assert.equal((await call(path, { headers: { "If-None-Match": tag } })).status, 200);
  await del(tag);
  assert.equal((await call(path, { headers: { "If-None-Match": tag } })).status, 404);
});

test("reserved API paths cannot fall through to SPA including 404 and HEAD", async () => {
  const { call } = await fixture();
  for (const route of [path, "/v1", "/v1/missing.json", "/v1/game/123.mp4",
    "/v1%2fgame/123.json", "/%76%31/game/123.json", "/%5fpublish/v1/game/123.json",
    "/_publish", "/_publish/.tmp", "/api/service/games/123", "/api", "/.env"]) {
    for (const method of ["GET", "HEAD"]) {
      const result = await call(route, { method });
      assert.equal(result.status, 404, route);
      assert.equal(result.headers.get("Content-Type"), "application/json; charset=utf-8");
      if (method === "HEAD") assert.equal(await result.text(), "");
    }
  }
  assert.equal(await (await call("/game?game=123")).text(), "frontend");
});

test("public route never mutates and upload route never serves bodies", async () => {
  const { call, put } = await fixture();
  await put();
  for (const method of ["PUT", "POST", "DELETE", "PATCH"]) {
    assert.equal((await call(path, { method })).status, 405);
  }
  assert.equal((await call("/_publish" + path, {
    headers: { Authorization: "Bearer " + TOKEN },
  })).status, 405);
});

test("cross-origin public reads expose clock headers only to configured exact origin", async () => {
  const { call } = await fixture();
  const good = await call(path, { headers: { Origin: "https://ui.example.test" } });
  assert.equal(good.headers.get("Access-Control-Allow-Origin"), "https://ui.example.test");
  assert.equal(good.headers.get("Access-Control-Expose-Headers"), "Date, Age, ETag");
  for (const origin of ["https://evil.test", "null", "https://ui.example.test.evil.test"]) {
    assert.equal((await call(path, { headers: { Origin: origin } })).headers.get("Access-Control-Allow-Origin"), null);
  }
  const options = await call(path, { method: "OPTIONS", headers: { Origin: "https://ui.example.test" } });
  assert.equal(options.status, 204);
  assert.equal(options.headers.get("Access-Control-Allow-Credentials"), null);
});

test("upload forbids URL credentials via query and has no CORS", async () => {
  const { call, put } = await fixture();
  const bad = await call("/_publish" + path + "?token=not-a-real-token", { method: "PUT" });
  assert.equal(bad.status, 404);
  const result = await put(undefined, undefined, { Origin: "https://ui.example.test" });
  assert.equal(result.headers.get("Access-Control-Allow-Origin"), null);
});

test("conditional create cannot overwrite existing content", async () => {
  const { put, call } = await fixture();
  await put();
  assert.equal((await put('{"synthetic":"replacement"}')).status, 412);
  assert.equal(await (await call(path)).text(), '{"synthetic":true}');
});

test("conditional update accepts current ETag and rejects stale retry", async () => {
  const { put, call } = await fixture();
  const first = await put();
  const old = first.headers.get("ETag");
  const updated = await put('{"synthetic":2}', { "If-Match": old });
  assert.equal(updated.status, 200);
  assert.equal((await put('{"synthetic":3}', { "If-Match": old })).status, 412);
  assert.equal(await (await call(path)).text(), '{"synthetic":2}');
});

test("two concurrent conditional writers cannot both replace one version", async () => {
  const { put } = await fixture();
  const tag = (await put()).headers.get("ETag");
  const results = await Promise.all([
    put('{"synthetic":2}', { "If-Match": tag }),
    put('{"synthetic":3}', { "If-Match": tag }),
  ]);
  assert.deepEqual(results.map(x => x.status).sort(), [200, 412]);
});

test("write requires exactly one supported precondition", async () => {
  const { put } = await fixture();
  for (const headers of [{}, { "If-Match": "*" }, { "If-Match": 'W/"' + "a".repeat(32) + '"' },
    { "If-Match": '"bad"' }, { "If-None-Match": '"bad"' },
    { "If-Match": '"' + "a".repeat(32) + '", "' + "b".repeat(32) + '"' },
    { "If-Match": '"' + "a".repeat(32) + '"', "If-None-Match": "*" }]) {
    assert.equal((await put(undefined, headers)).status, 428);
  }
});

test("conditional deletion hides body from GET and HEAD immediately", async () => {
  const { put, del, call, env } = await fixture();
  const original = (await put()).headers.get("ETag");
  const removed = await del(original);
  assert.equal(removed.status, 200);
  assert.equal((await call(path)).status, 404);
  assert.equal((await call(path, { method: "HEAD" })).status, 404);
  assert.equal(env.PUBLISH_BUCKET.objects.get(path.slice(1)).customMetadata.deleted, "true");
  const metadata = await call("/_publish" + path, {
    method: "HEAD", headers: { Authorization: "Bearer " + TOKEN },
  });
  assert.equal(metadata.headers.get("X-Publish-Deleted"), "true");
  assert.equal(metadata.headers.get("ETag"), removed.headers.get("ETag"));
  assert.equal(await metadata.text(), "");
});

test("restore needs tombstone ETag; stale withdrawal cannot delete restored data", async () => {
  const { put, del, call } = await fixture();
  const first = (await put()).headers.get("ETag");
  const removed = (await del(first)).headers.get("ETag");
  assert.notEqual(removed, first);
  assert.equal((await put()).status, 412);
  assert.equal((await put('{"synthetic":2}', { "If-Match": removed })).status, 200);
  assert.equal((await del(first)).status, 412);
  assert.equal((await del(removed)).status, 412);
  assert.equal(await (await call(path)).text(), '{"synthetic":2}');
});

test("delete needs current object condition, never unguarded storage delete", async () => {
  const { call, del } = await fixture();
  assert.equal((await del('"' + "0".repeat(32) + '"')).status, 412);
  assert.equal((await call("/_publish" + path, {
    method: "DELETE", headers: { Authorization: "Bearer " + TOKEN, "If-None-Match": "*" },
  })).status, 428);
});

test("wrong checksum, invalid JSON and wrong root shape cannot store", async () => {
  const { env, put } = await fixture();
  assert.equal((await put(undefined, undefined, { "X-Content-SHA256": "a".repeat(64) })).status, 422);
  assert.equal((await put(undefined, undefined, { "X-Content-SHA256": "" })).status, 400);
  for (const body of ["{", "", "null", "[]", "1", '"string"']) assert.equal((await put(body)).status, 400, body);
  assert.equal(env.PUBLISH_BUCKET.writes, 0);
});

test("non-UTF8 and encoded bodies are rejected", async () => {
  const { put } = await fixture();
  assert.equal((await put(new Uint8Array([123, 34, 97, 34, 58, 34, 255, 34, 125]))).status, 400);
  assert.equal((await put(undefined, undefined, { "Content-Encoding": "gzip" })).status, 415);
  assert.equal((await put(undefined, undefined, { "Content-Type": "text/plain" })).status, 415);
});

test("declared oversize and streaming oversize cannot store", async () => {
  const { env, put } = await fixture();
  assert.equal((await put(undefined, undefined, { "Content-Length": String(MAX_JSON_BYTES + 1) })).status, 413);
  assert.equal((await put('{"large":"' + "a".repeat(MAX_JSON_BYTES) + '"}')).status, 413);
  assert.equal(env.PUBLISH_BUCKET.writes, 0);
});

test("mismatched declared length is rejected", async () => {
  const { put } = await fixture();
  assert.equal((await put(undefined, undefined, { "Content-Length": "1" })).status, 400);
});

test("storage failures are sanitized and never leak exception details", async () => {
  const { env, call, put } = await fixture();
  env.PUBLISH_BUCKET.get = env.PUBLISH_BUCKET.put = async () => { throw new Error("sensitive-provider-path"); };
  for (const result of [await call(path), await put()]) {
    assert.equal(result.status, 503);
    assert.equal(await result.text(), '{"error":"storage_unavailable"}');
  }
});

test("missing bucket and frontend report unavailable without guessing content", async () => {
  const { env, call, put } = await fixture();
  delete env.PUBLISH_BUCKET;
  assert.equal((await call(path)).status, 503);
  assert.equal((await put()).status, 503);
  delete env.ASSETS;
  assert.equal((await call("/game")).status, 503);
});

test("oversize object inserted outside this gateway is not served", async () => {
  const { env, call } = await fixture();
  env.PUBLISH_BUCKET.get = async () => ({ size: MAX_JSON_BYTES + 1 });
  assert.equal((await call(path)).status, 503);
});


test("identical restoration cannot revive an old write or withdrawal token (ABA)", async () => {
  const { put, del, call } = await fixture();
  const original = (await put()).headers.get("ETag");
  const removed = (await del(original)).headers.get("ETag");
  const restored = await put(undefined, { "If-Match": removed });
  assert.equal(restored.status, 200);
  assert.notEqual(restored.headers.get("ETag"), original);
  assert.equal((await del(original)).status, 412);
  assert.equal((await put('{"synthetic":"old-retry"}', { "If-Match": original })).status, 412);
  assert.equal(await (await call(path)).text(), '{"synthetic":true}');
});

test("private storage format and integrity are checked before serving", async () => {
  const { env, put, call } = await fixture();
  await put();
  const obj = env.PUBLISH_BUCKET.objects.get(path.slice(1));
  obj.bytes[obj.bytes.length - 2] ^= 1;
  assert.equal((await call(path)).status, 503);
  delete obj.customMetadata.recordFormat;
  assert.equal((await call(path, { method: "HEAD" })).status, 503);
});


test("example config keeps both gates closed and routes through Worker before assets", () => {
  const config = JSON.parse(readFileSync(new URL("../wrangler.example.jsonc", import.meta.url), "utf8"));
  assert.equal(config.vars.DATA_READ_ENABLED, "false");
  assert.equal(config.vars.UPLOAD_ENABLED, "false");
  assert.equal(config.assets.run_worker_first, true);
  assert.equal(config.workers_dev, false);
  assert.equal(config.preview_urls, false);
  assert.equal(config.vars.PUBLISH_TOKEN_SHA256, undefined);
});

test("authenticated requests share one limit across files and methods", async () => {
  const { env, call, put } = await fixture(); const keys = [];
  env.PUBLISH_LIMITER = { limit: async ({ key }) => { keys.push(key); return { success: true }; } };
  assert.equal((await put()).status, 200);
  assert.equal((await call("/_publish/v1/health.json", { method: "HEAD", headers: { Authorization: "Bearer " + TOKEN } })).status, 404);
  assert.equal((await call("/_publish/v1/setup/456.json", { method: "DELETE", headers: { Authorization: "Bearer " + TOKEN } })).status, 428);
  assert.deepEqual(keys, ["publisher", "publisher", "publisher"]);
});

test("rate rejection and unavailable limiter never read request body or storage", async () => {
  const variants = [
    [undefined, 503], [{}, 503], [{ limit: 1 }, 503],
    ...[null, {}, "yes", { success: "true" }, { success: 1 }, { success: false }].map(x => [
      { limit: async () => x }, x?.success === false ? 429 : 503]),
    [{ limit: async () => { throw new Error("provider secret"); } }, 503],
  ];
  for (const [limiter, status] of variants) {
    const { env } = await fixture(); env.PUBLISH_LIMITER = limiter;
    let storage = 0, bodyReads = 0;
    env.PUBLISH_BUCKET = { get: () => { storage++; }, head: () => { storage++; }, put: () => { storage++; } };
    for (const method of ["PUT", "DELETE", "HEAD"]) {
      const request = new Request("https://host.example.test/_publish" + path, {
        method, ...(method === "PUT" ? { body: "{}" } : {}),
        headers: { Authorization: "Bearer " + TOKEN },
      });
      Object.defineProperty(request, "body", { get() { bodyReads++; throw Error("body must stay unread"); } });
      const response = await worker.fetch(request, env);
      assert.equal(response.status, status);
      assert.equal(response.headers.get("Retry-After"), status === 429 ? "60" : null);
      assert.equal(response.headers.get("Cache-Control"), "no-store");
      assert.equal(await response.text(), method === "HEAD" ? "" :
        JSON.stringify({ error: status === 429 ? "upload_rate_limited" : "upload_limiter_unavailable" }));
    }
    assert.equal(storage, 0); assert.equal(bodyReads, 0);
  }
});

test("disabled, unauthorized and disallowed requests do not consume publisher quota", async () => {
  const { env, call, put } = await fixture(); let count = 0;
  env.PUBLISH_LIMITER = { limit: async () => { count++; return { success: true }; } };
  assert.equal((await put(undefined, undefined, { Authorization: "wrong" })).status, 401);
  assert.equal((await call("/_publish" + path, { method: "POST", headers: { Authorization: "Bearer " + TOKEN } })).status, 405);
  assert.equal((await call("/_publish/v1/private.json", { method: "HEAD", headers: { Authorization: "Bearer " + TOKEN } })).status, 404);
  assert.equal((await call(path)).status, 404);
  assert.equal((await call(path, { method: "HEAD" })).status, 404);
  env.UPLOAD_ENABLED = "false"; assert.equal((await put()).status, 503);
  assert.equal(count, 0);
});

test("example limiter is separate and explicit; retries remain conditional", async () => {
  const c = JSON.parse(readFileSync(new URL("../wrangler.example.jsonc", import.meta.url), "utf8"));
  const upload = c.ratelimits.find(x => x.name === "PUBLISH_LIMITER");
  assert.deepEqual(upload.simple, { limit: 60, period: 60 });
  assert.notEqual(upload.namespace_id, c.ratelimits.find(x => x.name === "TELEMETRY_LIMITER").namespace_id);
  const { env, put, call } = await fixture();
  const created = await put(); const old = created.headers.get("ETag");
  env.PUBLISH_LIMITER = { limit: async () => ({ success: false }) };
  assert.equal((await put('{"synthetic":2}', { "If-Match": old })).status, 429);
  env.PUBLISH_LIMITER = { limit: async () => ({ success: true }) };
  assert.equal((await put('{"synthetic":3}', { "If-Match": old })).status, 200);
  assert.equal((await put('{"synthetic":2}', { "If-Match": old })).status, 412);
  assert.equal(await (await call(path)).text(), '{"synthetic":3}');
});

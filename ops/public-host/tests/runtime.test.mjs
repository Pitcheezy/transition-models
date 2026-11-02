import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { Miniflare } from "miniflare";

const token = "synthetic-local-runtime-token-not-a-real-account-credential";
const hash = bytes => createHash("sha256").update(bytes).digest("hex");

function assertProtectedEtag(response) {
  assert.match(response.headers.get("ETag"), /^"[a-f0-9]{32}"$/);
  assert.equal(response.headers.get("Cache-Control"), "no-store, no-transform");
  assert.equal(response.headers.get("CDN-Cache-Control"), "no-store");
}

test("actual local Worker/R2 runtime: publish, conditional updates, withdrawal and restore", async () => {
  const mf = new Miniflare({
    modules: true, scriptPath: fileURLToPath(new URL("../worker.mjs", import.meta.url)),
    compatibilityDate: "2026-07-30", r2Buckets: ["PUBLISH_BUCKET"],
    ratelimits: { PUBLISH_LIMITER: { namespace_id: "1002", simple: { limit: 60, period: 60 } } },
    bindings: {
      DATA_READ_ENABLED: "true", UPLOAD_ENABLED: "true", PUBLISH_TOKEN_SHA256: hash(token),
      READ_ORIGIN: "https://ui.example.test",
    },
  });
  try {
    await mf.ready;
    const call = (route, init) => mf.dispatchFetch("http://localhost" + route, init);
    const route = "/v1/game/123.json";
    const privateHead = async (status, etag = null, deleted = null) => {
      const started = Date.now();
      const response = await call("/_publish" + route, { method: "HEAD", headers: { Authorization: "Bearer " + token } });
      const finished = Date.now();
      assert.equal(response.status, status);
      assert.equal(response.headers.get("Cache-Control"), etag ? "no-store, no-transform" : "no-store");
      assert.equal(response.headers.get("CDN-Cache-Control"), "no-store");
      assert.equal(response.headers.get("Age"), "0");
      const date = Date.parse(response.headers.get("Date"));
      assert.ok(Number.isFinite(date) && date >= Math.floor(started / 1000) * 1000 && date <= finished);
      assert.equal(response.headers.get("ETag"), etag);
      assert.equal(response.headers.get("X-Publish-Deleted"), deleted);
      assert.equal(await response.text(), "");
    };
    const put = (body, condition) => call("/_publish" + route, {
      method: "PUT", body, headers: {
        Authorization: "Bearer " + token, "Content-Type": "application/json",
        "X-Content-SHA256": hash(body), ...condition,
      },
    });
    const del = etag => call("/_publish" + route, {
      method: "DELETE", headers: { Authorization: "Bearer " + token, "If-Match": etag },
    });
    const body = '{ "synthetic": true, "label": "테스트" }\n';
    let first;
    let tombstone;
    { // missing JSON is 404, reserved encoded paths never serve SPA
      await privateHead(404);
      for (const p of [route, "/v1%2fgame/123.json", "/%76%31/game/123.json"]) {
        assert.equal((await call(p)).status, 404);
      }
    }
    { // R2 checksum and conditional create work with private record
      const saved = await put(body, { "If-None-Match": "*" });
      assert.equal(saved.status, 200, await saved.clone().text());
      assertProtectedEtag(saved);
      first = saved.headers.get("ETag");
      await privateHead(200, first, "false");
      assert.match(first, /^"[a-f0-9]{32}"$/);
      assert.equal((await put(body, { "If-None-Match": "*" })).status, 412);
      const bucket = await mf.getR2Bucket("PUBLISH_BUCKET");
      const record = await bucket.get(route.slice(1));
      assert.match(await record.text(), /^pitcheezy-host-record-v1:/);
      assert.equal(record.customMetadata.sha256, hash(body));
    }
    { // reader returns exactly original bytes, origin Date/Age and payload HEAD size; a held ETag answers 304
      const response = await call(route, { headers: { Origin: "https://ui.example.test" } });
      assert.equal(await response.text(), body);
      const conditional = await call(route, { headers: { "If-None-Match": response.headers.get("ETag") } });
      assert.equal(conditional.status, 304);
      assertProtectedEtag(conditional);
      assert.equal(await conditional.text(), "");
      assert.equal(response.headers.get("Age"), "0");
      assertProtectedEtag(response);
      assert.ok(Number.isFinite(Date.parse(response.headers.get("Date"))));
      assert.equal(response.headers.get("Access-Control-Expose-Headers"), "Date, Age, ETag");
      const head = await call(route, { method: "HEAD" });
      assertProtectedEtag(head);
      assert.equal(await head.text(), "");
      assert.equal(head.headers.get("Content-Length"), String(Buffer.byteLength(body)));
    }
    { // conditional tombstone withdraws immediately
      const response = await del(first);
      assert.equal(response.status, 200);
      assertProtectedEtag(response);
      tombstone = response.headers.get("ETag");
      assert.notEqual(tombstone, first);
      // Deleted private metadata is HEAD 200 while its public route is HEAD 404.
      await privateHead(200, tombstone, "true");
      assert.equal((await call(route)).status, 404);
      assert.equal((await call(route, { method: "HEAD" })).status, 404);
      assert.equal((await del(first)).status, 412);
    }
    { // identical restore does not revive stale deletion (real R2 ETag)
      const restored = await put(body, { "If-Match": tombstone });
      assert.equal(restored.status, 200);
      assertProtectedEtag(restored);
      assert.notEqual(restored.headers.get("ETag"), first);
      assert.notEqual(restored.headers.get("ETag"), tombstone);
      await privateHead(200, restored.headers.get("ETag"), "false");
      assert.equal((await del(first)).status, 412);
      assert.equal(await (await call(route)).text(), body);
    }
    { // real R2 allows only one concurrent update with the same precondition
      const tag = (await call(route, { method: "HEAD" })).headers.get("ETag");
      const attempts = await Promise.all([
        put('{"synthetic":2}', { "If-Match": tag }),
        put('{"synthetic":3}', { "If-Match": tag }),
      ]);
      assert.deepEqual(attempts.map(x => x.status).sort(), [200, 412]);
    }
    { // unauthorized write never stores
      assert.equal((await call("/_publish/v1/health.json", { method: "PUT", body: "{}" })).status, 401);
      assert.equal((await call("/v1/health.json")).status, 404);
    }
  } finally {
    await mf.dispose();
  }
});

test("actual rate binding blocks authenticated storage calls while public reads continue", { timeout: 30000 }, async () => {
  const mf = new Miniflare({
    modules: true, modulesRoot: fileURLToPath(new URL("../", import.meta.url)),
    scriptPath: fileURLToPath(new URL("../worker.mjs", import.meta.url)),
    compatibilityDate: "2026-07-30", r2Buckets: ["PUBLISH_BUCKET"],
    ratelimits: { PUBLISH_LIMITER: { namespace_id: "1002", simple: { limit: 2, period: 60 } } },
    bindings: { DATA_READ_ENABLED: "true", UPLOAD_ENABLED: "true", PUBLISH_TOKEN_SHA256: hash(token) },
  });
  try {
    await mf.ready;
    const body = '{"synthetic":true}';
    const call = (path, init) => mf.dispatchFetch("http://localhost" + path, init);
    const response = await call("/_publish/v1/game/123.json", { method: "PUT", body,
      headers: { Authorization: "Bearer " + token, "Content-Type": "application/json",
        "X-Content-SHA256": hash(body), "If-None-Match": "*" } });
    assert.equal(response.status, 200);
    const tag = response.headers.get("ETag");
    const head = await call("/_publish/v1/game/123.json", { method: "HEAD", headers: { Authorization: "Bearer " + token } });
    assert.equal(head.status, 200);
    for (const [path, method] of [["/v1/game/123.json","DELETE"],["/v1/health.json","HEAD"],["/v1/setup/456.json","PUT"]]) {
      const blocked = await call("/_publish" + path, { method, headers: { Authorization: "Bearer " + token, "If-Match": tag } });
      assert.equal(blocked.status, 429);
      assert.equal(blocked.headers.get("Retry-After"), "60");
      await blocked.arrayBuffer();
    }
    const publicRead = await call("/v1/game/123.json");
    assert.equal(publicRead.status, 200); assert.equal(await publicRead.text(), body);
    assert.equal(publicRead.headers.get("ETag"), tag);
  } finally { await mf.dispose(); }
});

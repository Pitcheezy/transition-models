import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { Miniflare } from "miniflare";

const token = "synthetic-local-runtime-token-not-a-real-account-credential";
const hash = bytes => createHash("sha256").update(bytes).digest("hex");

test("actual local Worker/R2 runtime: publish, conditional updates, withdrawal and restore", async () => {
  const mf = new Miniflare({
    modules: true, scriptPath: fileURLToPath(new URL("../worker.mjs", import.meta.url)),
    compatibilityDate: "2026-07-30", r2Buckets: ["PUBLISH_BUCKET"],
    bindings: {
      DATA_READ_ENABLED: "true", UPLOAD_ENABLED: "true", PUBLISH_TOKEN_SHA256: hash(token),
      READ_ORIGIN: "https://ui.example.test",
    },
  });
  try {
    await mf.ready;
    const call = (route, init) => mf.dispatchFetch("http://localhost" + route, init);
    const route = "/v1/game/123.json";
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
      for (const p of [route, "/v1%2fgame/123.json", "/%76%31/game/123.json"]) {
        assert.equal((await call(p)).status, 404);
      }
    }
    { // R2 checksum and conditional create work with private record
      const saved = await put(body, { "If-None-Match": "*" });
      assert.equal(saved.status, 200, await saved.clone().text());
      first = saved.headers.get("ETag");
      assert.match(first, /^"[a-f0-9]{32}"$/);
      assert.equal((await put(body, { "If-None-Match": "*" })).status, 412);
      const bucket = await mf.getR2Bucket("PUBLISH_BUCKET");
      const record = await bucket.get(route.slice(1));
      assert.match(await record.text(), /^pitcheezy-host-record-v1:/);
      assert.equal(record.customMetadata.sha256, hash(body));
    }
    { // reader returns exactly original bytes, origin Date/Age and payload HEAD size
      const response = await call(route, { headers: { Origin: "https://ui.example.test" } });
      assert.equal(await response.text(), body);
      assert.equal(response.headers.get("Age"), "0");
      assert.equal(response.headers.get("Cache-Control"), "no-store");
      assert.ok(Number.isFinite(Date.parse(response.headers.get("Date"))));
      assert.equal(response.headers.get("Access-Control-Expose-Headers"), "Date, Age, ETag");
      const head = await call(route, { method: "HEAD" });
      assert.equal(await head.text(), "");
      assert.equal(head.headers.get("Content-Length"), String(Buffer.byteLength(body)));
    }
    { // conditional tombstone withdraws immediately
      const response = await del(first);
      assert.equal(response.status, 200);
      tombstone = response.headers.get("ETag");
      assert.equal((await call(route)).status, 404);
      assert.equal((await call(route, { method: "HEAD" })).status, 404);
      assert.equal((await del(first)).status, 412);
    }
    { // identical restore does not revive stale deletion (real R2 ETag)
      const restored = await put(body, { "If-Match": tombstone });
      assert.equal(restored.status, 200);
      assert.notEqual(restored.headers.get("ETag"), first);
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

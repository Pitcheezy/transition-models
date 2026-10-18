import test from "node:test";
import assert from "node:assert/strict";
import { startLocalHost, boundedCleanup, hash } from "../rehearsal/local-host.mjs";

test("transport preserves free-text receipt reasons without changing recommendation meaning", { timeout: 30000 }, async () => {
  const host = await startLocalHost({ notice: false, signal: AbortSignal.timeout(20000) });
  try {
    let etag = null;
    for (const reason of ["held_last_accepted", "future_synthetic_reason"]) {
      // OUR synthetic body. A stored observation is not a newly recorded recommendation.
      const body = JSON.stringify({ synthetic: true,
        receipt: { status: "received", corrected: true, reason },
        rec: { pairing: { status: "none", rule: "no_recorded_recommendation" } } });
      const put = await host.publish("/v1/game/123.json", body, etag);
      assert.equal(put.status, 200); etag = put.headers.get("ETag");
      await put.arrayBuffer();
      const read = await fetch(host.origin + "/v1/game/123.json", { signal: AbortSignal.timeout(5000) });
      assert.equal(read.status, 200);
      const actual = await read.text();
      assert.equal(actual, body); assert.equal(hash(actual), hash(body));
      assert.equal(read.headers.get("ETag"), etag);
      assert.equal(JSON.parse(actual).rec.pairing.status, "none");
    }
  } finally {
    assert.equal((await boundedCleanup(() => host.dispose())).status, "complete");
  }
});

import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { Miniflare } from "miniflare";
import worker from "../gateway.mjs";
import { currentNotice, invalidateNotice, noticeDigests, NOTICE_CACHE_MS, NOTICE_MESSAGES, NOTICE_ROUTE, NOTICE_STATE_KEY } from "../notice.mjs";
import { probe, initialState, advanceState } from "../monitor.mjs";

// Synthetic-only credentials. Never an account secret or a Song file.
const PUBLISH_TOKEN = "synthetic-only-publish-token-for-unit-tests-not-a-credential";
const OPERATOR_A = "synthetic-only-notice-token-operator-a-not-a-credential-xx";
const OPERATOR_B = "synthetic-only-notice-token-operator-b-not-a-credential-xx";
const digest = body => createHash("sha256").update(body).digest("hex");
const game = "/v1/game/123.json";

class Bucket {
  objects = new Map();
  writes = 0;
  reads = 0;
  snapshot(key) {
    const stored = this.objects.get(key);
    if (!stored) return null;
    return { ...stored, body: stored.bytes.slice(), arrayBuffer: async () => stored.bytes.slice().buffer, customMetadata: { ...stored.customMetadata } };
  }
  async get(key) { this.reads++; return this.snapshot(key); }
  async head(key) { return this.snapshot(key); }
  async list({ prefix = "", limit = 1000 } = {}) {
    const keys = [...this.objects.keys()].filter(k => k.startsWith(prefix)).sort();
    return { objects: keys.slice(0, limit).map(key => ({ key })), truncated: keys.length > limit };
  }
  async put(key, bytes, options = {}) {
    assert.ok(options.onlyIf instanceof Headers, "writes must have atomic storage conditions");
    const current = this.objects.get(key);
    const match = options.onlyIf.get("If-Match");
    if (match && (!current || current.httpEtag !== match)) return null;
    if (options.onlyIf.get("If-None-Match") === "*" && current) return null;
    assert.equal(digest(bytes), options.sha256);
    const httpEtag = '"' + createHash("md5").update(bytes).digest("hex") + '"';
    this.objects.set(key, { httpEtag, size: bytes.length, bytes: bytes.slice(), customMetadata: { ...options.customMetadata } });
    this.writes++;
    return this.snapshot(key);
  }
}

async function fixture({ notice = true } = {}) {
  const env = {
    DATA_READ_ENABLED: "true", UPLOAD_ENABLED: "true",
    PUBLISH_TOKEN_SHA256: digest(PUBLISH_TOKEN),
    ...(notice ? { NOTICE_TOKEN_SHA256: digest(OPERATOR_A) + "," + digest(OPERATOR_B) } : {}),
    PUBLISH_BUCKET: new Bucket(),
    PUBLISH_LIMITER: { limit: async () => ({ success: true }) },
    READ_ORIGIN: "https://ui.example.test",
    ASSETS: { fetch: async () => new Response("<!doctype html><html>frontend</html>", { headers: { "Content-Type": "text/html" } }) },
  };
  const call = (route, init = {}) => worker.fetch(new Request("https://host.example.test" + route, init), env);
  const publish = (body = '{"synthetic":true}') => call("/_publish" + game, {
    method: "PUT", body, headers: {
      Authorization: "Bearer " + PUBLISH_TOKEN, "Content-Type": "application/json",
      "X-Content-SHA256": digest(body), "If-None-Match": "*",
    },
  });
  const change = (body, condition = { "If-None-Match": "*" }, token = OPERATOR_A, more = {}) => call(NOTICE_ROUTE, {
    method: "PUT", body: JSON.stringify(body), headers: {
      Authorization: "Bearer " + token, "Content-Type": "application/json", ...condition, ...more,
    },
  });
  const on = (condition, token) => change({ active: true, operator: "ops-a", reason: "synthetic drill", message_id: "maintenance" }, condition, token);
  const off = (condition, token) => change({ active: false, operator: "ops-a", reason: "synthetic recovery", message_id: "maintenance" }, condition, token);
  return { env, call, publish, change, on, off };
}

function assertProtectedEtag(response) {
  assert.match(response.headers.get("ETag"), /^"[a-f0-9]{32}"$/);
  assert.equal(response.headers.get("Cache-Control"), "no-store, no-transform");
  assert.equal(response.headers.get("CDN-Cache-Control"), "no-store");
}

test("switch control is closed by default and never reachable from public routes", async () => {
  const { env, call, on } = await fixture({ notice: false });
  assert.equal((await on()).status, 503);
  assert.equal(await (await on()).text(), '{"error":"notice_control_not_configured"}');
  for (const bad of ["", "a", digest("x").slice(0, 63), digest("x") + ",", digest("x") + "," + digest("x")]) {
    env.NOTICE_TOKEN_SHA256 = bad;
    assert.equal(noticeDigests(env), null, bad);
    assert.equal((await on()).status, 503);
  }
  env.NOTICE_TOKEN_SHA256 = Array.from({ length: 9 }, (_, i) => digest("t" + i)).join(",");
  assert.equal(noticeDigests(env), null);
  env.NOTICE_TOKEN_SHA256 = digest(OPERATOR_A);
  assert.equal((await call("/v1/_notice/state.json")).status, 404);
  assert.equal((await call("/_publish/_notice/v1/state", { method: "PUT", headers: { Authorization: "Bearer " + PUBLISH_TOKEN } })).status, 404);
  assert.equal(env.PUBLISH_BUCKET.writes, 0);
});

test("wrong, missing or publisher tokens cannot change the switch; limiter and preconditions apply", async () => {
  const { env, call, on, change } = await fixture();
  for (const token of ["", "Bearer short", "Bearer " + PUBLISH_TOKEN, "Basic abc"]) {
    const r = await call(NOTICE_ROUTE, { method: "PUT", body: "{}", headers: { Authorization: token, "Content-Type": "application/json", "If-None-Match": "*" } });
    assert.equal(r.status, 401);
  }
  assert.equal((await call(NOTICE_ROUTE, { method: "DELETE", headers: { Authorization: "Bearer " + OPERATOR_A } })).status, 405);
  assert.equal((await call(NOTICE_ROUTE + "?x=1", { headers: { Authorization: "Bearer " + OPERATOR_A } })).status, 404);
  assert.equal((await on({})).status, 428);
  for (const body of [{}, { active: "true", operator: "a", reason: "r", message_id: "maintenance" },
    { active: true, operator: "", reason: "r", message_id: "maintenance" },
    { active: true, operator: "a b", reason: "r", message_id: "maintenance" },
    { active: true, operator: "a", reason: "", message_id: "maintenance" },
    { active: true, operator: "a", reason: "x".repeat(501), message_id: "maintenance" },
    { active: true, operator: "a", reason: "line\nbreak", message_id: "maintenance" },
    { active: true, operator: "a", reason: "r", message_id: "<script>" },
    { active: true, operator: "a", reason: "r", message_id: "maintenance", extra: 1 }]) {
    assert.equal((await change(body)).status, 400, JSON.stringify(body));
  }
  const keys = [];
  env.PUBLISH_LIMITER = { limit: async ({ key }) => { keys.push(key); return { success: false }; } };
  assert.equal((await on()).status, 429);
  assert.deepEqual(keys, ["notice"]);
  env.PUBLISH_LIMITER = { limit: async () => ({ success: "yes" }) };
  assert.equal((await on()).status, 503);
  assert.equal(env.PUBLISH_BUCKET.writes, 0);
});

test("turning the notice on replaces page, asset, data and telemetry answers but not uploads or control", async () => {
  const { env, call, publish, on, off } = await fixture();
  assert.equal((await publish()).status, 200);
  assert.equal(await (await call("/")).text(), "<!doctype html><html>frontend</html>");
  const turned = await on();
  assert.equal(turned.status, 200, await turned.clone().text());
  assertProtectedEtag(turned);
  const state = await turned.json();
  assert.equal(state.active, true); assert.equal(state.revision, 1); assert.equal(state.audit_recorded, true);
  const etag = turned.headers.get("ETag");
  assert.match(etag, /^"[a-f0-9]{32}"$/);
  for (const route of ["/", "/index.html", "/assets/app.js", "/game?game=123"]) {
    for (const method of ["GET", "HEAD"]) {
      const r = await call(route, { method });
      assert.equal(r.status, 503, route);
      assert.equal(r.headers.get("Content-Type"), "text/html; charset=utf-8");
      assert.equal(r.headers.get("Cache-Control"), "no-store");
      assert.equal(r.headers.get("CDN-Cache-Control"), "no-store");
      assert.equal(r.headers.get("Retry-After"), "60");
      assert.equal(r.headers.get("X-Pitcheezy-Notice"), "maintenance");
      assert.equal(r.headers.get("X-Robots-Tag"), "noindex");
      const text = await r.text();
      if (method === "HEAD") assert.equal(text, "");
      else {
        assert.match(text, /<!doctype html>/);
        assert.ok(text.includes(NOTICE_MESSAGES.maintenance));
        assert.doesNotMatch(text, /synthetic drill|ops-a|<script/);
      }
    }
  }
  for (const route of [game, "/v1/health.json", "/v1/missing.json", "/v1/game/123.mp4"]) {
    const r = await call(route, { headers: { Origin: "https://ui.example.test" } });
    assert.equal(r.status, 503, route);
    assert.equal(r.headers.get("Content-Type"), "application/json; charset=utf-8");
    assert.equal(r.headers.get("Cache-Control"), "no-store");
    assert.equal(r.headers.get("Access-Control-Allow-Origin"), "https://ui.example.test");
    assert.equal(r.headers.get("X-Pitcheezy-Notice"), "maintenance");
    const body = await r.json();
    assert.equal(body.error, "service_notice");
    assert.equal(body.notice.id, "maintenance");
    assert.equal(JSON.stringify(body).includes("synthetic drill"), false);
  }
  assert.equal((await call(game, { method: "OPTIONS", headers: { Origin: "https://ui.example.test" } })).status, 204);
  const telemetry = await call("/_telemetry/session", { method: "POST", body: "{}", headers: { "Content-Type": "application/json" } });
  assert.equal(telemetry.status, 503);
  assert.equal((await telemetry.json()).error, "service_notice");
  // Upload path and operator path keep working while the notice is on.
  const head = await call("/_publish" + game, { method: "HEAD", headers: { Authorization: "Bearer " + PUBLISH_TOKEN } });
  assert.equal(head.status, 200);
  const read = await call(NOTICE_ROUTE, { headers: { Authorization: "Bearer " + OPERATOR_A } });
  assert.equal(read.status, 200);
  assertProtectedEtag(read);
  const controlHead = await call(NOTICE_ROUTE, { method: "HEAD", headers: { Authorization: "Bearer " + OPERATOR_A } });
  assert.equal(controlHead.status, 200);
  assertProtectedEtag(controlHead);
  const view = await read.json();
  assert.equal(view.state.active, true);
  assert.equal(view.audit.length, 1);
  assert.equal(view.audit[0].operator, "ops-a");
  assert.equal(view.audit[0].reason, "synthetic drill");
  assert.equal(view.audit[0].operator_token_prefix, digest(OPERATOR_A).slice(0, 12));
  assert.equal(view.audit[0].etag_before, null);
  assert.equal(view.audit[0].etag_after, etag);
  // Recovery requires the current ETag; a stale operator loses.
  assert.equal((await off({ "If-None-Match": "*" }, OPERATOR_B)).status, 412);
  assert.equal((await off({ "If-Match": '"' + "0".repeat(32) + '"' }, OPERATOR_B)).status, 412);
  const recovered = await off({ "If-Match": etag }, OPERATOR_B);
  assert.equal(recovered.status, 200);
  assertProtectedEtag(recovered);
  assert.equal((await recovered.json()).active, false);
  assert.equal(await (await call("/")).text(), "<!doctype html><html>frontend</html>");
  assert.equal(await (await call(game)).text(), '{"synthetic":true}');
  const after = await (await call(NOTICE_ROUTE, { headers: { Authorization: "Bearer " + OPERATOR_B } })).json();
  assert.equal(after.audit.length, 2);
  assert.equal(after.audit[1].operator_token_prefix, digest(OPERATOR_B).slice(0, 12));
  assert.equal(after.state.revision, 2);
  assert.equal(after.state.since, null);
});

test("two operators racing on one state version: exactly one write wins", async () => {
  const { on, off } = await fixture();
  const etag = (await on()).headers.get("ETag");
  const results = await Promise.all([off({ "If-Match": etag }), off({ "If-Match": etag }, OPERATOR_B)]);
  assert.deepEqual(results.map(r => r.status).sort(), [200, 412]);
});

test("switch reads are memoised per bucket and fail closed on a malformed state object", async () => {
  const { env, call, on } = await fixture();
  let now = Date.parse("2026-10-13T00:00:00Z");
  const bucket = env.PUBLISH_BUCKET;
  invalidateNotice(bucket);
  bucket.reads = 0;
  await currentNotice(env, now); await currentNotice(env, now + NOTICE_CACHE_MS - 1);
  assert.equal(bucket.reads, 1);
  await currentNotice(env, now + NOTICE_CACHE_MS);
  assert.equal(bucket.reads, 2);
  assert.equal((await on()).status, 200);
  const other = new Bucket();
  assert.equal((await currentNotice({ PUBLISH_BUCKET: other })).active, false);
  assert.equal((await currentNotice({})).storage, "absent");
  bucket.objects.get(NOTICE_STATE_KEY).bytes = new TextEncoder().encode('{"schema":"wrong"}');
  invalidateNotice(bucket);
  for (const route of ["/", game, "/_telemetry/session"]) {
    const r = await call(route, route.startsWith("/_telemetry") ? { method: "POST", body: "{}", headers: { "Content-Type": "application/json" } } : {});
    assert.equal(r.status, 503, route);
    assert.equal((await r.json()).error, "notice_state_invalid");
  }
  bucket.get = async () => { throw new Error("sensitive-provider-path"); };
  invalidateNotice(bucket);
  const failed = await call("/");
  assert.equal(failed.status, 503);
  assert.equal(await failed.text(), '{"error":"storage_unavailable"}');
});

test("monitor records an active notice as viewer unavailability distinct from outages", async () => {
  const config = {
    schema: "pitcheezy-host-monitor-v1", origin: "https://public.example.test", allow_loopback_http: false,
    timeout_ms: 200, max_body_bytes: 4096, timestamp_pointer: null, timestamp_format: "rfc3339",
    max_age_seconds: 120, clock_skew_seconds: 30, page_sha256: null,
  };
  const now = Date.parse("2026-10-13T00:00:00Z");
  const fetchImpl = async () => new Response('{"error":"service_notice"}', { status: 503, headers: {
    "Content-Type": "application/json", "X-Pitcheezy-Notice": "maintenance", "Cache-Control": "no-store" } });
  let clock = now;
  const report = await probe(config, { fetchImpl, now: () => clock });
  assert.equal(report.status, "failed");
  assert.equal(report.notice_active, true);
  assert.deepEqual(report.issues, ["page_notice_active", "health_notice_active"]);
  assert.doesNotMatch(JSON.stringify(report), /개발용|service_notice/);
  let state = initialState(config);
  state = advanceState(state, report, config).state;
  clock += 1000;
  const second = advanceState(state, await probe(config, { fetchImpl, now: () => clock }), config);
  assert.equal(second.event.kind, "opened");
  assert.deepEqual(second.event.issues, ["page_notice_active", "health_notice_active"]);
  const outage = await probe(config, { fetchImpl: async () => new Response("down", { status: 503 }), now: () => clock + 1000 });
  assert.equal(outage.notice_active, false);
  assert.deepEqual(outage.issues, ["page_http_error", "health_http_error"]);
});

test("actual local Worker/R2 runtime: notice switch changes every viewer route and recovers", { timeout: 30000 }, async () => {
  const mf = new Miniflare({
    modules: true, modulesRoot: fileURLToPath(new URL("../", import.meta.url)),
    scriptPath: fileURLToPath(new URL("../worker.mjs", import.meta.url)),
    compatibilityDate: "2026-07-30", r2Buckets: ["PUBLISH_BUCKET"],
    ratelimits: { PUBLISH_LIMITER: { namespace_id: "1002", simple: { limit: 60, period: 60 } } },
    bindings: { DATA_READ_ENABLED: "true", UPLOAD_ENABLED: "true", PUBLISH_TOKEN_SHA256: digest(PUBLISH_TOKEN),
      NOTICE_TOKEN_SHA256: digest(OPERATOR_A) },
    serviceBindings: { ASSETS: () => new Response("<!doctype html><html>frontend</html>", { headers: { "Content-Type": "text/html" } }) },
  });
  try {
    await mf.ready;
    const call = (route, init) => mf.dispatchFetch("http://localhost" + route, init);
    const body = '{"synthetic":true}';
    const saved = await call("/_publish" + game, { method: "PUT", body, headers: {
      Authorization: "Bearer " + PUBLISH_TOKEN, "Content-Type": "application/json", "X-Content-SHA256": digest(body), "If-None-Match": "*" } });
    assert.equal(saved.status, 200); await saved.arrayBuffer();
    assert.equal(await (await call(game)).text(), body);
    const turned = await call(NOTICE_ROUTE, { method: "PUT", headers: {
      Authorization: "Bearer " + OPERATOR_A, "Content-Type": "application/json", "If-None-Match": "*" },
      body: JSON.stringify({ active: true, operator: "ops-a", reason: "runtime drill", message_id: "data_hold" }) });
    assert.equal(turned.status, 200, await turned.clone().text());
    assertProtectedEtag(turned);
    const etag = turned.headers.get("ETag"); await turned.arrayBuffer();
    const bucket = await mf.getR2Bucket("PUBLISH_BUCKET");
    const stored = await bucket.get(NOTICE_STATE_KEY);
    assert.equal(stored.customMetadata.kind, "notice-state-v1");
    const listed = await bucket.list({ prefix: "_notice/audit/" });
    assert.equal(listed.objects.length, 1);
    // The switch key is never publishable or readable through public or upload routes.
    assert.equal((await call("/v1/_notice/state.json")).status, 503);
    assert.equal((await call("/_publish/v1/_notice/state.json", { method: "HEAD", headers: { Authorization: "Bearer " + PUBLISH_TOKEN } })).status, 404);
    for (const route of ["/", "/anything.js"]) {
      const r = await call(route);
      assert.equal(r.status, 503); assert.equal(r.headers.get("X-Pitcheezy-Notice"), "data_hold");
      assert.match(await r.text(), /개발용 안내 문구/);
    }
    const data = await call(game);
    assert.equal(data.status, 503); assert.equal((await data.json()).error, "service_notice");
    const head = await call("/_publish" + game, { method: "HEAD", headers: { Authorization: "Bearer " + PUBLISH_TOKEN } });
    assert.equal(head.status, 200); await head.arrayBuffer();
    const recovered = await call(NOTICE_ROUTE, { method: "PUT", headers: {
      Authorization: "Bearer " + OPERATOR_A, "Content-Type": "application/json", "If-Match": etag },
      body: JSON.stringify({ active: false, operator: "ops-a", reason: "runtime recovery", message_id: "data_hold" }) });
    assert.equal(recovered.status, 200); await recovered.arrayBuffer();
    assert.equal(await (await call(game)).text(), body);
    assert.equal((await call("/")).status, 200);
    const view = await call(NOTICE_ROUTE, { headers: { Authorization: "Bearer " + OPERATOR_A } });
    assertProtectedEtag(view);
    const parsed = await view.json();
    assert.equal(parsed.state.active, false); assert.equal(parsed.audit.length, 2);
  } finally { await mf.dispose(); }
});

test("audit view shows the newest 20 entries even when the bucket lists them in several pages", async () => {
  class PagedBucket extends Bucket {
    async list({ prefix = "", cursor } = {}) {
      const keys = [...this.objects.keys()].filter(k => k.startsWith(prefix)).sort();
      const start = cursor ? Number(cursor) : 0;
      const page = keys.slice(start, start + 7);
      const truncated = start + 7 < keys.length;
      return { objects: page.map(key => ({ key })), truncated, ...(truncated ? { cursor: String(start + 7) } : {}) };
    }
  }
  const { env, call } = await fixture();
  env.PUBLISH_BUCKET = new PagedBucket();
  for (let i = 0; i < 30; i++) {
    const at = new Date(Date.UTC(2026, 9, 13, 0, i)).toISOString();
    const bytes = new TextEncoder().encode(JSON.stringify({ schema: "pitcheezy-notice-audit-v1", id: "synthetic-" + i, at, active: i % 2 === 0,
      message_id: "maintenance", operator: "ops-a", reason: "paged " + i, operator_token_prefix: "0".repeat(12), revision: i + 1, etag_before: null, etag_after: null }));
    await env.PUBLISH_BUCKET.put("_notice/audit/" + at.replace(/[-:.]/g, "") + "-synthetic-" + i + ".json", bytes,
      { onlyIf: new Headers({ "If-None-Match": "*" }), sha256: digest(bytes), customMetadata: { kind: "notice-audit-v1" } });
  }
  const view = await call(NOTICE_ROUTE, { headers: { Authorization: "Bearer " + OPERATOR_A } });
  assert.equal(view.status, 200);
  const parsed = await view.json();
  assert.equal(parsed.audit.length, 20);
  assert.equal(parsed.audit_truncated, true);
  assert.equal(parsed.audit[0].reason, "paged 10", "the oldest shown entry is the 11th, not the first page's tail");
  assert.equal(parsed.audit.at(-1).reason, "paged 29", "the newest entry is shown");
});

test("a failed audit write after a committed switch is reported, not mistaken for a failed switch", async () => {
  const { env, call } = await fixture();
  const bucket = env.PUBLISH_BUCKET;
  const originalPut = bucket.put.bind(bucket);
  bucket.put = async (key, bytes, options) => {
    if (key.startsWith("_notice/audit/")) throw new Error("synthetic audit storage failure");
    return originalPut(key, bytes, options);
  };
  const turned = await call(NOTICE_ROUTE, { method: "PUT", headers: {
    Authorization: "Bearer " + OPERATOR_A, "Content-Type": "application/json", "If-None-Match": "*" },
    body: JSON.stringify({ active: true, operator: "ops-a", reason: "audit failure drill", message_id: "maintenance" }) });
  assert.equal(turned.status, 200);
  const body = await turned.json();
  assert.equal(body.active, true); assert.equal(body.audit_recorded, false); assert.equal(body.audit_error, "audit_write_failed");
  assert.doesNotMatch(JSON.stringify(body), /synthetic audit storage failure/);
  assert.equal((await call("/")).status, 503, "the switch itself is on");
});

test("WS-review2: a later GET still identifies a missing audit for the committed notice revision", async () => {
  const { env, call, on, off } = await fixture();
  const first = await on();
  const before = await (await call(NOTICE_ROUTE, { headers: { Authorization: "Bearer " + OPERATOR_A } })).json();
  assert.equal(before.audit_unavailable, false);
  const put = env.PUBLISH_BUCKET.put.bind(env.PUBLISH_BUCKET);
  env.PUBLISH_BUCKET.put = async (key, bytes, options) => {
    if (key.startsWith("_notice/audit/")) throw new Error("synthetic failed audit for revision 2");
    return put(key, bytes, options);
  };
  const changed = await off({ "If-Match": first.headers.get("ETag") });
  assert.equal((await changed.json()).audit_recorded, false);
  const after = await (await call(NOTICE_ROUTE, { headers: { Authorization: "Bearer " + OPERATOR_A } })).json();
  assert.equal(after.state.active, false);
  assert.equal(after.state.revision, 2);
  assert.equal(after.audit.length, 1, "the earlier successful audit remains available");
  assert.equal(after.audit_unavailable, true, "the current revision has no audit, despite a working list call");
});

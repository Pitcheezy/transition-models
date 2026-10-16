import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { fileURLToPath } from "node:url";
import { Miniflare } from "miniflare";
import { prepareNotice, noticeDryRun, executeNotice } from "../notice-client.mjs";

const TOKEN = "synthetic-notice-client-test-token-not-a-real-credential";
const ETAG = '"' + "a".repeat(32) + '"';
const AT = "2026-10-17T00:00:00.000Z";
const change = { active: true, operator: "private-operator", reason: "private-reason-do-not-print", message_id: "maintenance" };
const plan = (extra = {}) => ({ schema: "pitcheezy-notice-plan-v1", origin: "https://private.example.test",
  allow_loopback_http: false, method: "GET", condition: null, change: null, ...extra });
const writePlan = (extra = {}) => plan({ method: "PUT", condition: { if_none_match: "*" }, change, ...extra });
const response = (value, extra = {}) => new Response(JSON.stringify(value), { headers: {
  "Content-Type": "application/json", "Cache-Control": "no-store, no-transform", ETag: ETAG, ...extra } });
const state = (extra = {}) => ({ state: { active: true, message_id: "maintenance", revision: 1, since: AT, etag: ETAG },
  audit: [{ schema: "pitcheezy-notice-audit-v1", revision: 1, etag_after: ETAG,
    reason: change.reason, operator_token_prefix: "a".repeat(12) }], audit_truncated: false,
  audit_unavailable: false, messages: { maintenance: "private-server-copy" }, ...extra });
const ack = (extra = {}) => ({ active: true, message_id: "maintenance", revision: 1, since: AT,
  change_id: "12345678-abcd-abcd-abcd-123456789012", audit_recorded: true, ...extra });
function privateFree(receipt) {
  const text = JSON.stringify(receipt);
  for (const value of [TOKEN, "private.example.test", change.operator, change.reason, "a".repeat(12), "private-server-copy"])
    assert.equal(text.includes(value), false, value);
}

test("plans reject implicit writes, unsupported targets, secrets and invalid change shapes before I/O", () => {
  for (const value of [null, {}, plan({ token: TOKEN }), plan({ method: "DELETE" }), plan({ change }),
    writePlan({ condition: null }), writePlan({ condition: { if_match: 'W/' + ETAG } }),
    writePlan({ condition: { if_match: ETAG, if_none_match: "*" } }),
    writePlan({ change: { ...change, active: "true" } }), writePlan({ change: { ...change, operator: "has space" } }),
    writePlan({ change: { ...change, reason: "line\nbreak" } }), writePlan({ change: { ...change, reason: "x".repeat(501) } }),
    writePlan({ change: { ...change, message_id: "unapproved" } })]) assert.throws(() => prepareNotice(value));
  for (const origin of ["http://private.example.test", "https://private.example.test/path", "https://u:p@private.example.test",
    "https://private.example.test?secret=hidden", "https://private.example.test#fragment", "https://private.example.test/"])
    assert.throws(() => prepareNotice(plan({ origin })));
  assert.throws(() => prepareNotice(plan({ origin: "http://localhost:1234", allow_loopback_http: true })));
  assert.equal(prepareNotice(plan({ origin: "http://127.0.0.1:1234", allow_loopback_http: true })).origin, "http://127.0.0.1:1234");
  assert.equal(prepareNotice(writePlan({ condition: { if_match: ETAG } })).condition["If-Match"], ETAG);
});

test("dry run is a redacted review receipt without reading credentials or sending requests", () => {
  const r = noticeDryRun(writePlan());
  assert.equal(r.outcome, "dry_run"); assert.equal(r.attempted, false); assert.equal(r.requests, 0);
  assert.equal(r.requested_active, true); assert.equal(r.requested_message_id, "maintenance"); privateFree(r);
});

test("GET preserves a private fixed condition while its public receipt excludes all sensitive response fields", async () => {
  let calls = 0;
  const result = await executeNotice(plan(), TOKEN, { fetchImpl: async (url, init) => {
    calls++; assert.equal(url, plan().origin + "/_notice/v1/state"); assert.equal(init.redirect, "manual");
    assert.equal(init.credentials, "omit"); assert.equal(init.headers.Authorization, "Bearer " + TOKEN);
    return response(state());
  } });
  assert.equal(calls, 1); assert.equal(result.receipt.outcome, "observed");
  assert.deepEqual(result.snapshot.condition, { if_match: ETAG }); assert.equal(result.snapshot.observed.active, true);
  assert.equal(JSON.stringify(result.snapshot).includes(change.reason), false); privateFree(result.receipt);
});

test("missing initial state gives an explicit create condition; HEAD remains metadata-only", async () => {
  const empty = state({ state: { active: false, message_id: null, revision: 0, since: null, etag: null }, audit: [] });
  const result = await executeNotice(plan(), TOKEN, { fetchImpl: async () => response(empty, { ETag: undefined }) });
  // Headers stringify undefined, so absence must actually be represented by deleting the header.
  assert.equal(result.receipt.outcome, "invalid_response");
  const fetchImpl = async () => { const r = response(empty); r.headers.delete("ETag"); return r; };
  const missing = await executeNotice(plan(), TOKEN, { fetchImpl });
  assert.equal(missing.receipt.outcome, "observed"); assert.deepEqual(missing.snapshot.condition, { if_none_match: "*" });
  const head = await executeNotice(plan({ method: "HEAD" }), TOKEN,
    { fetchImpl: async () => new Response(null, { headers: { ETag: ETAG, "Cache-Control": "no-store, no-transform" } }) });
  assert.equal(head.receipt.metadata_only, true); assert.equal(head.receipt.audit_status, "unmeasured");
  assert.deepEqual(head.snapshot.condition, { if_match: ETAG });
});

test("PUT uses only the reviewed condition and distinguishes state success from audit failure", async () => {
  for (const audit of [true, false]) {
    let calls = 0;
    const result = await executeNotice(writePlan({ condition: { if_match: ETAG } }), TOKEN, { fetchImpl: async (_, init) => {
      calls++; assert.deepEqual(init.headers["If-Match"], ETAG); assert.equal(init.headers["If-None-Match"], undefined);
      assert.deepEqual(JSON.parse(init.body), change); return response(ack({ audit_recorded: audit, ...(audit ? {} : { audit_error: "audit_write_failed" }) }));
    } });
    assert.equal(calls, 1); assert.equal(result.receipt.outcome, audit ? "applied" : "applied_audit_missing");
    assert.equal(result.receipt.audit_recorded, audit); assert.equal(result.snapshot, null); privateFree(result.receipt);
  }
  const missingAudit = await executeNotice(plan(), TOKEN, { fetchImpl: async () => response(state({ audit: [], audit_unavailable: true })) });
  assert.equal(missingAudit.receipt.outcome, "observed_audit_unavailable");
  assert.equal(missingAudit.receipt.active, true);
});

test("conflict, throttle and definite rejection never refetch or retry", async () => {
  for (const [status, outcome] of [[412, "conflict"], [429, "deferred"], [401, "rejected"], [428, "rejected"]]) {
    let calls = 0;
    const result = await executeNotice(writePlan(), TOKEN, { fetchImpl: async () => {
      calls++; return new Response("private-error-body", { status, headers: { "Retry-After": "0" } });
    } });
    assert.equal(calls, 1); assert.equal(result.receipt.outcome, outcome); assert.equal(result.receipt.retries, 0); privateFree(result.receipt);
  }
});

test("lost, redirected, 5xx and corrupt write acknowledgements remain unknown without blind writes", async () => {
  for (const fetchImpl of [async () => { throw new Error(TOKEN + plan().origin); },
    async () => new Response(null, { status: 302, headers: { Location: "https://other.example.test" } }),
    async () => new Response("private", { status: 503 }), async () => response(ack({ active: false })),
    async () => response(ack(), { ETag: "W/" + ETAG }), async () => response(ack(), { "Cache-Control": "max-age=100" })]) {
    let calls = 0;
    const result = await executeNotice(writePlan(), TOKEN, { fetchImpl: (...args) => { calls++; return fetchImpl(...args); } });
    assert.equal(calls, 1); assert.equal(result.receipt.outcome, "unknown"); privateFree(result.receipt);
  }
});

test("read validation refuses inconsistent ETags, unproved audit, wrong MIME, UTF8 and oversized bodies", async () => {
  for (const fetchImpl of [async () => response(state({ state: { ...state().state, etag: '"' + "b".repeat(32) + '"' } })),
    async () => response(state({ audit: [] })), async () => response(state({ state: { ...state().state, message_id: ["maintenance"] } })), async () => response(state(), { "Content-Type": "text/html" }),
    async () => response(state(), { "Content-Length": "70000" }),
    async () => new Response(new Uint8Array([0xff]), { headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } }),
    async () => new Response("x".repeat(65537), { headers: { "Content-Type": "application/json", "Cache-Control": "no-store" } })]) {
    const result = await executeNotice(plan(), TOKEN, { fetchImpl });
    assert.equal(result.receipt.outcome, "invalid_response"); assert.equal(result.snapshot, null); privateFree(result.receipt);
  }
});

test("GET and PUT require the server's exact UTC ISO timestamp without calendar normalization", async () => {
  for (const since of ["2026-02-30T00:00:00Z", "2026-02-30T00:00:00.000Z", "2026-02-29T00:00:00.000Z",
    "2026-04-31T00:00:00.000Z", "2026-10-17T24:00:00.000Z", "2026-10-17T09:00:00.000+09:00"]) {
    const read = await executeNotice(plan(), TOKEN,
      { fetchImpl: async () => response(state({ state: { ...state().state, since } })) });
    assert.equal(read.receipt.outcome, "invalid_response", since); assert.equal(read.snapshot, null);
    const write = await executeNotice(writePlan(), TOKEN, { fetchImpl: async () => response(ack({ since })) });
    assert.equal(write.receipt.outcome, "unknown", since); assert.equal(write.receipt.code, "invalid_response");
  }
  for (const since of [AT, "2024-02-29T23:59:59.123Z"]) {
    const read = await executeNotice(plan(), TOKEN,
      { fetchImpl: async () => response(state({ state: { ...state().state, since } })) });
    assert.equal(read.receipt.outcome, "observed", since);
    const write = await executeNotice(writePlan(), TOKEN, { fetchImpl: async () => response(ack({ since })) });
    assert.equal(write.receipt.outcome, "applied", since);
  }
});

test("timeout covers both fetch and a headers-only body, with one request and no secret error output", async () => {
  for (const fetchImpl of [async () => new Promise(() => {}), async () => new Response(new ReadableStream({ start() {} }),
    { headers: { "Content-Type": "application/json", "Cache-Control": "no-store, no-transform", ETag: ETAG } })]) {
    for (const p of [plan(), writePlan()]) {
      const before = Date.now(); const r = await executeNotice(p, TOKEN, { fetchImpl, timeoutMs: 50 });
      assert.ok(Date.now() - before < 1000); assert.equal(r.receipt.outcome, p.method === "PUT" ? "unknown" : "unavailable");
      assert.equal(r.receipt.code, "request_timeout"); assert.equal(r.receipt.requests, 1); privateFree(r.receipt);
    }
  }
});

test("missing token and invalid limits refuse before calling fetch", async () => {
  const fetchImpl = () => { assert.fail("request forbidden"); };
  for (const token of [undefined, "", "short", TOKEN + "\n"]) await assert.rejects(executeNotice(plan(), token, { fetchImpl }), /notice_token/);
  await assert.rejects(executeNotice(plan(), TOKEN, { fetchImpl, timeoutMs: 0 }), /invalid_timeout/);
});

test("actual loopback Worker and R2: inspect, conditionally enable, conflict, inspect and disable", { timeout: 30000 }, async () => {
  const mf = new Miniflare({ host: "127.0.0.1", port: 0, modules: true,
    scriptPath: fileURLToPath(new URL("../worker.mjs", import.meta.url)), compatibilityDate: "2026-07-30",
    r2Buckets: ["PUBLISH_BUCKET"], ratelimits: { PUBLISH_LIMITER: { namespace_id: "1002", simple: { limit: 60, period: 60 } } },
    bindings: { NOTICE_TOKEN_SHA256: createHash("sha256").update(TOKEN).digest("hex") },
    serviceBindings: { ASSETS: () => new Response("<!doctype html><html>synthetic</html>") } });
  try {
    const origin = (await mf.ready).origin; assert.equal(new URL(origin).hostname, "127.0.0.1");
    const p = plan({ origin, allow_loopback_http: true });
    const initial = await executeNotice(p, TOKEN); assert.equal(initial.receipt.revision, 0);
    const onPlan = { ...p, method: "PUT", condition: initial.snapshot.condition, change };
    const on = await executeNotice(onPlan, TOKEN); assert.equal(on.receipt.outcome, "applied");
    assert.equal((await fetch(origin)).status, 503);
    const conflict = await executeNotice(onPlan, TOKEN); assert.equal(conflict.receipt.outcome, "conflict");
    const current = await executeNotice(p, TOKEN); assert.equal(current.receipt.active, true); assert.equal(current.receipt.audit_unavailable, false);
    const off = await executeNotice({ ...onPlan, condition: current.snapshot.condition, change: { ...change, active: false } }, TOKEN);
    assert.equal(off.receipt.outcome, "applied"); assert.equal(off.receipt.revision, 2);
    const after = await executeNotice(p, TOKEN); assert.equal(after.receipt.active, false); assert.equal(after.receipt.audit_unavailable, false);
    assert.equal((await fetch(origin)).status, 200);
    // A real accepted write followed by a lost acknowledgement is not safe to repeat.
    let lostRequests = 0;
    const lost = await executeNotice({ ...onPlan, condition: after.snapshot.condition }, TOKEN, { fetchImpl: async (...args) => {
      lostRequests++; const accepted = await fetch(...args); assert.equal(accepted.status, 200);
      await accepted.arrayBuffer(); throw new Error("synthetic loss after actual stored write");
    } });
    assert.equal(lost.receipt.outcome, "unknown"); assert.equal(lostRequests, 1);
    const stored = await executeNotice(p, TOKEN); assert.equal(stored.receipt.active, true); assert.equal(stored.receipt.revision, 3);
    const recovered = await executeNotice({ ...onPlan, condition: stored.snapshot.condition, change: { ...change, active: false } }, TOKEN);
    assert.equal(recovered.receipt.outcome, "applied"); assert.equal(recovered.receipt.revision, 4);
  } finally { await mf.dispose(); }
});

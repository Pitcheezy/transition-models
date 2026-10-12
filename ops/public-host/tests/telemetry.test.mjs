import test from "node:test";
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import gateway from "../gateway.mjs";
import { validateMeasurement, MAX_ACTIVE_MS } from "../telemetry.mjs";
const origin = "https://ui.example.test";
const session = () => ({ v: 1, consent: true, session_id: randomUUID(), game_pk: 123, sequence: 0, active_ms: 0 });
const feedback = () => ({ v: 1, consent: true, feedback_id: randomUUID(), game_pk: 123, rating: "helpful", reason: "none" });
function env() { return {
  TELEMETRY_ENABLED: "true", FEEDBACK_ENABLED: "true", COLLECTION_ORIGIN: origin,
  TELEMETRY_RETAIN_DAYS: "30", SESSION_WRITES_PER_DAY: "20", FEEDBACK_ROWS_PER_DAY: "10",
  TELEMETRY_RATE_SECRET: "synthetic-rate-key-only-not-a-real-credential-12345",
  TELEMETRY_LIMITER: { limit: async () => ({ success: true }) }, TELEMETRY_DB: {},
}; }
const call = (environment, options = {}) => gateway.fetch(new Request(origin + (options.path || "/_telemetry/session"), {
  method: options.method || "POST", ...(options.method === "GET" ? {} : { body: options.body ?? JSON.stringify(session()) }),
  headers: { "Content-Type": "application/json", Origin: origin, "CF-Connecting-IP": "192.0.2.1", ...options.headers },
}), environment);
test("strict measurement schemas reject identifiers, text, URLs and invalid ranges", () => {
  assert.deepEqual(validateMeasurement(session(), "session").game_pk, 123);
  assert.equal(validateMeasurement(feedback(), "feedback").rating, "helpful");
  for (const patch of [
    { consent: false }, { consent: 1 }, { ip: "192.0.2.1" }, { url: "/game/123" },
    { game_pk: "123" }, { game_pk: -1 }, { session_id: "user@example.test" },
    { sequence: 1.5 }, { active_ms: 1 }, { sequence: 1, active_ms: MAX_ACTIVE_MS + 1 },
  ]) assert.throws(() => validateMeasurement({ ...session(), ...patch }, "session"));
  assert.throws(() => validateMeasurement({ ...feedback(), text: "hello" }, "feedback"));
  assert.throws(() => validateMeasurement({ ...feedback(), rating: "five" }, "feedback"));
  assert.throws(() => validateMeasurement({ ...feedback(), reason: "free-form" }, "feedback"));
});
test("collection is closed by default and missing configuration fails closed", async () => {
  assert.equal((await call({})).status, 503);
  for (const name of ["TELEMETRY_DB","TELEMETRY_LIMITER","TELEMETRY_RATE_SECRET","COLLECTION_ORIGIN","TELEMETRY_RETAIN_DAYS"]) {
    const e=env(); delete e[name]; assert.equal((await call(e)).status, 503, name);
  }
  for (const patch of [{ TELEMETRY_ENABLED: true },{ COLLECTION_ORIGIN: origin+"/path" },
    { TELEMETRY_RETAIN_DAYS:"91" },{ SESSION_WRITES_PER_DAY:"1e6" }]) {
    assert.equal((await call({...env(),...patch})).status, 503);
  }
});
test("wrong/missing browser origin and opt-outs never write or call limiter", async () => {
  const e=env(); e.TELEMETRY_LIMITER.limit = () => { throw new Error("must not call"); };
  for (const headers of [{ Origin:"https://other.example.test" },{ Origin:"null" },
    { "Sec-Fetch-Site":"cross-site" },{ DNT:"1" },{ "Sec-GPC":"1" }]) {
    assert.equal((await call(e,{headers})).status,403);
  }
});
test("no public reads, preflight, query data, encoded path or SPA fallback", async () => {
  const e=env(); e.ASSETS={fetch:()=>new Response("SPA")};
  assert.equal((await call(e,{method:"GET"})).status,405);
  assert.equal((await call(e,{method:"OPTIONS"})).status,405);
  for (const path of ["/_telemetry","/_telemetry/export","/_telemetry/session?x=1","/%5ftelemetry/session"]) {
    assert.equal((await call(e,{path})).status,404);
  }
});
test("bounded JSON streaming, MIME, UTF8, unknown fields and encodings", async () => {
  for (const [options,status] of [
    [{body:"x".repeat(1025)},413], [{body:"{}"},400], [{body:"null"},400],
    [{headers:{"Content-Type":"text/plain"}},415], [{headers:{"Content-Encoding":"gzip"}},415],
    [{body:new Uint8Array([255,254])},400], [{body:"{"},400],
    [{headers:{"Content-Length":"2000"}},413], [{headers:{"Content-Length":"1"}},400],
  ]) assert.equal((await call(env(),options)).status,status);
});
test("rate keys conceal raw edge IP and opt-out never weakens the limit", async () => {
  const e=env(); let seen;
  e.TELEMETRY_LIMITER.limit=async ({key})=>{seen=key;return{success:false};};
  const r=await call(e);
  assert.equal(r.status,429); assert.match(seen,/^[0-9a-f]{64}$/);
  assert.equal(r.headers.get("Retry-After"),"60");
  assert.equal(r.headers.get("Access-Control-Allow-Origin"),null);
  assert.equal(r.headers.get("Cache-Control"),"no-store");
  assert.equal((await call(e,{headers:{"CF-Connecting-IP":""}})).status,503);
});
test("provider failures do not reflect exception text or credentials", async () => {
  const e=env(); e.TELEMETRY_LIMITER.limit=()=>{throw new Error("private database provider secret");};
  const r=await call(e); assert.equal(r.status,503);
  assert.deepEqual(await r.json(),{error:"collection_unavailable"});
});
test("configuration has distinct opt-in gates, private D1 and cleanup schedule", () => {
  const c=JSON.parse(readFileSync(new URL("../wrangler.example.jsonc",import.meta.url),"utf8"));
  assert.equal(c.vars.TELEMETRY_ENABLED,"false"); assert.equal(c.vars.FEEDBACK_ENABLED,"false");
  assert.equal(c.vars.TELEMETRY_RATE_SECRET,undefined);
  assert.equal(c.d1_databases[0].binding,"TELEMETRY_DB");
  assert.ok(c.triggers.crons.length);
});

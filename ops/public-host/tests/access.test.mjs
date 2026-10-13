import test from "node:test";
import assert from "node:assert/strict";
import { createHash, createHmac } from "node:crypto";
import { fileURLToPath } from "node:url";
import { Miniflare } from "miniflare";
import worker from "../gateway.mjs";
import { accessConfig, verifySession, transportAllowed, handleAccess, requireViewer, ACCESS_ROUTE, MAX_SESSION_SECONDS, ISSUE_CLOCK_SKEW_MS } from "../access.mjs";
import { NOTICE_ROUTE } from "../notice.mjs";
import { probe } from "../monitor.mjs";

// Synthetic-only values. Never real viewer codes, secrets, account credentials or Song files.
const PUBLISH_TOKEN = "synthetic-only-publish-token-for-unit-tests-not-a-credential";
const OPERATOR = "synthetic-only-notice-token-operator-a-not-a-credential-xx";
const CODE_A = "synthetic-code-A-not-real-1234";
const CODE_B = "synthetic-code-B-not-real-5678";
const SECRET = "synthetic-session-secret-not-a-real-value-0123456789abcdef";
const digest = body => createHash("sha256").update(body).digest("hex");
const game = "/v1/game/123.json";

class Bucket {
  objects = new Map();
  snapshot(key) {
    const stored = this.objects.get(key);
    if (!stored) return null;
    return { ...stored, arrayBuffer: async () => stored.bytes.slice().buffer, customMetadata: { ...stored.customMetadata } };
  }
  async get(key) { return this.snapshot(key); }
  async head(key) { return this.snapshot(key); }
  async list({ prefix = "" } = {}) { return { objects: [...this.objects.keys()].filter(k => k.startsWith(prefix)).sort().map(key => ({ key })), truncated: false }; }
  async put(key, bytes, options = {}) {
    const current = this.objects.get(key);
    const match = options.onlyIf.get("If-Match");
    if (match && (!current || current.httpEtag !== match)) return null;
    if (options.onlyIf.get("If-None-Match") === "*" && current) return null;
    const httpEtag = '"' + createHash("md5").update(bytes).digest("hex") + '"';
    this.objects.set(key, { httpEtag, size: bytes.length, bytes: bytes.slice(), customMetadata: { ...options.customMetadata } });
    return this.snapshot(key);
  }
}

function fixture({ gate = true, origin = "https://host.example.test" } = {}) {
  const env = {
    DATA_READ_ENABLED: "true", UPLOAD_ENABLED: "true", PUBLISH_TOKEN_SHA256: digest(PUBLISH_TOKEN),
    NOTICE_TOKEN_SHA256: digest(OPERATOR), PUBLISH_BUCKET: new Bucket(),
    PUBLISH_LIMITER: { limit: async () => ({ success: true }) }, READ_ORIGIN: "",
    ASSETS: { fetch: async () => new Response("<!doctype html><html>frontend</html>", { headers: {
      "Content-Type": "text/html", "Cache-Control": "public, max-age=300", ETag: '"asset"' } }) },
    ...(gate ? { ACCESS_GATE_ENABLED: "true", ACCESS_CODE_SHA256: digest(CODE_A) + "," + digest(CODE_B),
      ACCESS_SESSION_SECRET: SECRET, ACCESS_SESSION_SECONDS: "3600" } : {}),
  };
  const call = (route, init = {}) => worker.fetch(new Request(origin + route, init), env);
  const login = (code, { form = false, headers = {} } = {}) => call(ACCESS_ROUTE, {
    method: "POST", headers: { "Content-Type": form ? "application/x-www-form-urlencoded" : "application/json", ...headers },
    body: form ? new URLSearchParams({ code }).toString() : JSON.stringify({ code }),
  });
  const cookieOf = response => (response.headers.get("Set-Cookie") || "").split(";")[0];
  const publish = (body = '{"synthetic":true}') => call("/_publish" + game, { method: "PUT", body, headers: {
    Authorization: "Bearer " + PUBLISH_TOKEN, "Content-Type": "application/json", "X-Content-SHA256": digest(body), "If-None-Match": "*" } });
  return { env, call, login, cookieOf, publish };
}

test("gate is off by default and the session route is hidden while it is off", async () => {
  const { env, call, publish } = fixture({ gate: false });
  assert.equal(accessConfig(env), null);
  assert.equal((await publish()).status, 200);
  assert.equal(await (await call("/")).text(), "<!doctype html><html>frontend</html>");
  assert.equal((await call("/")).headers.get("Cache-Control"), "public, max-age=300");
  assert.equal(await (await call(game)).text(), '{"synthetic":true}');
  assert.equal((await call(ACCESS_ROUTE)).status, 404);
  for (const value of [true, 1, "TRUE", "", "false"]) {
    env.ACCESS_GATE_ENABLED = value;
    assert.equal((await call("/")).status, 200);
  }
});

test("gate on with missing or malformed secrets fails closed everywhere viewer-facing", async () => {
  for (const broken of [
    { ACCESS_CODE_SHA256: undefined }, { ACCESS_CODE_SHA256: "" }, { ACCESS_CODE_SHA256: "abc" },
    { ACCESS_CODE_SHA256: digest("x") + "," + digest("x") }, { ACCESS_CODE_SHA256: Array.from({ length: 9 }, (_, i) => digest("c" + i)).join(",") },
    { ACCESS_SESSION_SECRET: undefined }, { ACCESS_SESSION_SECRET: "short" }, { ACCESS_SESSION_SECONDS: "0" },
    { ACCESS_SESSION_SECONDS: String(MAX_SESSION_SECONDS + 1) }, { ACCESS_SESSION_SECONDS: 3600 },
  ]) {
    const { env, call, login, publish } = fixture();
    Object.assign(env, broken);
    for (const route of ["/", "/assets/app.js", game]) {
      const r = await call(route);
      assert.equal(r.status, 503, JSON.stringify(broken) + " " + route);
      assert.equal((await r.json()).error, "access_not_configured");
      assert.equal(r.headers.get("X-Pitcheezy-Access"), "misconfigured");
    }
    assert.equal((await login(CODE_A)).status, 503);
    assert.equal((await publish()).status, 200, "uploads are independent of the viewer gate");
  }
});

test("without a session every viewer route is 401 while uploads, notice control and preflight work", async () => {
  const { call, publish } = fixture();
  assert.equal((await publish()).status, 200);
  for (const route of ["/", "/index.html", "/assets/app.js", "/game?game=123"]) {
    for (const method of ["GET", "HEAD"]) {
      const r = await call(route, { method });
      assert.equal(r.status, 401, route);
      assert.equal(r.headers.get("Content-Type"), "text/html; charset=utf-8");
      assert.equal(r.headers.get("Cache-Control"), "no-store");
      assert.equal(r.headers.get("X-Pitcheezy-Access"), "required");
      assert.equal(r.headers.get("Vary"), "Cookie");
      assert.equal(r.headers.get("X-Robots-Tag"), "noindex");
      const text = await r.text();
      if (method === "HEAD") assert.equal(text, "");
      else { assert.match(text, /<form method="post" action="\/_access\/v1\/session">/); assert.doesNotMatch(text, /<script/); }
    }
  }
  for (const route of [game, "/v1/health.json", "/v1/missing.json"]) {
    const r = await call(route);
    assert.equal(r.status, 401, route);
    assert.equal(r.headers.get("Content-Type"), "application/json; charset=utf-8");
    assert.deepEqual(await r.json(), { error: "access_required" });
  }
  assert.equal((await call(game, { method: "OPTIONS" })).status, 204);
  const telemetry = await call("/_telemetry/session", { method: "POST", body: "{}", headers: { "Content-Type": "application/json" } });
  assert.equal(telemetry.status, 401);
  assert.equal((await call("/_publish" + game, { method: "HEAD", headers: { Authorization: "Bearer " + PUBLISH_TOKEN } })).status, 200);
  assert.equal((await call(NOTICE_ROUTE, { headers: { Authorization: "Bearer " + OPERATOR } })).status, 200);
  assert.equal((await call(ACCESS_ROUTE)).status, 200);
  assert.deepEqual(await (await call(ACCESS_ROUTE)).json(), { authenticated: false, expires_at: null });
});

test("login rejects wrong, malformed, cross-site and over-limit attempts without issuing a cookie", async () => {
  const { env, call, login } = fixture();
  const wrong = await login("synthetic-wrong-code-000");
  assert.equal(wrong.status, 401);
  assert.equal(wrong.headers.get("Set-Cookie"), null);
  assert.equal(wrong.headers.get("X-Pitcheezy-Access"), "denied");
  assert.deepEqual(await wrong.json(), { error: "access_denied" });
  const wrongForm = await login("synthetic-wrong-code-000", { form: true });
  assert.equal(wrongForm.status, 401);
  assert.match(await wrongForm.text(), /접속 코드가 맞지 않습니다/);
  for (const [body, type, status] of [["short", "application/json", 400], ['{"code":"synthetic-code-A-not-real-1234","x":1}', "application/json", 400],
    ['{"code":123456789}', "application/json", 400], ["code=has%20space%20inside", "application/x-www-form-urlencoded", 400],
    ["code=synthetic-code-A-not-real-1234&other=1", "application/x-www-form-urlencoded", 400],
    ['{"code":"synthetic-code-A-not-real-1234"}', "text/plain", 415]]) {
    const r = await call(ACCESS_ROUTE, { method: "POST", headers: { "Content-Type": type }, body: body.startsWith("{") || body.includes("=") ? body : JSON.stringify({ code: body }) });
    assert.equal(r.status, status, body);
    assert.equal(r.headers.get("Set-Cookie"), null);
  }
  for (const headers of [{ "Sec-Fetch-Site": "cross-site" }, { "Sec-Fetch-Site": "same-site" }, { Origin: "https://evil.test" }]) {
    assert.equal((await login(CODE_A, { headers })).status, 403, JSON.stringify(headers));
  }
  assert.equal((await call(ACCESS_ROUTE, { method: "DELETE", headers: { Origin: "https://evil.test" } })).status, 403);
  const keys = [];
  env.PUBLISH_LIMITER = { limit: async ({ key }) => { keys.push(key); return { success: true }; } };
  await login(CODE_A, { headers: { "CF-Connecting-IP": "192.0.2.1" } });
  await login(CODE_A, { headers: { "CF-Connecting-IP": "192.0.2.2" } });
  await login(CODE_A);
  assert.equal(keys.length, 3);
  assert.ok(keys.every(k => /^access:[a-f0-9]{32}$/.test(k)));
  assert.equal(new Set(keys).size, 3);
  assert.ok(!keys.some(k => k.includes("192.0.2")));
  env.PUBLISH_LIMITER = { limit: async () => ({ success: false }) };
  const limited = await login(CODE_A);
  assert.equal(limited.status, 429); assert.equal(limited.headers.get("Retry-After"), "60");
  env.PUBLISH_LIMITER = { limit: async () => ({ success: "yes" }) };
  assert.equal((await login(CODE_A)).status, 503);
});

test("a correct code opens a strict, private session that unlocks screen, data and collection", async () => {
  const { env, call, login, cookieOf, publish } = fixture();
  await publish();
  const opened = await login(CODE_A, { headers: { "Sec-Fetch-Site": "same-origin", Origin: "https://host.example.test" } });
  assert.equal(opened.status, 200);
  const set = opened.headers.get("Set-Cookie");
  assert.match(set, /^__Host-pz_viewer=v2\.[1-9][0-9]*\.[1-9][0-9]*\.[a-f0-9]{8}\.[a-f0-9]{16}\.[a-f0-9]{64}; Path=\/; Max-Age=3600; HttpOnly; SameSite=Strict; Secure$/);
  const body = await opened.json();
  assert.equal(body.authenticated, true);
  assert.ok(Date.parse(body.expires_at) > Date.now());
  const cookie = cookieOf(opened);
  const screen = await call("/", { headers: { Cookie: cookie } });
  assert.equal(screen.status, 200);
  assert.equal(await screen.text(), "<!doctype html><html>frontend</html>");
  assert.equal(screen.headers.get("Cache-Control"), "private, max-age=300");
  assert.equal(screen.headers.get("Vary"), "Cookie");
  assert.equal(screen.headers.get("ETag"), '"asset"');
  assert.equal(await (await call(game, { headers: { Cookie: cookie } })).text(), '{"synthetic":true}');
  const telemetry = await call("/_telemetry/session", { method: "POST", body: "{}", headers: { "Content-Type": "application/json", Cookie: cookie } });
  assert.equal((await telemetry.json()).error, "collection_disabled", "reached the telemetry handler");
  assert.equal((await (await call(ACCESS_ROUTE, { headers: { Cookie: cookie } })).json()).authenticated, true);
  const form = await login(CODE_B, { form: true });
  assert.equal(form.status, 303);
  assert.equal(form.headers.get("Location"), "/");
  assert.match(form.headers.get("Set-Cookie"), /^__Host-pz_viewer=v2\./);
  // No secret material in any response.
  for (const r of [opened, screen, form]) {
    const text = JSON.stringify([...r.headers]) + (r.bodyUsed ? "" : await r.clone().text());
    for (const secret of [CODE_A, CODE_B, SECRET, digest(CODE_A), digest(CODE_B)]) assert.equal(text.includes(secret), false);
  }
  assert.equal(env.PUBLISH_BUCKET.objects.has("_notice/state.json"), false);
});

test("expiry, tampering, code removal, secret rotation and logout all end the session", async () => {
  const { env, call, login, cookieOf } = fixture();
  const cookie = cookieOf(await login(CODE_A));
  const request = (c = cookie) => new Request("https://host.example.test/", { headers: { Cookie: c } });
  const url = new URL("https://host.example.test/");
  const config = accessConfig(env);
  assert.ok(await verifySession(request(), env, config, url));
  assert.equal(await verifySession(request(), env, config, url, Date.now() + 3600 * 1000 + 1), null);
  const [name, value] = cookie.split("=");
  const parts = value.split(".");
  assert.equal(parts.length, 6, "v2.<issued>.<expires>.<prefix>.<nonce>.<mac>");
  const tamperedMac = [...parts.slice(0, 5), parts[5].replace(/^./, c => (c === "a" ? "b" : "a"))].join(".");
  const tamperedExpiry = [parts[0], parts[1], String(Number(parts[2]) + 60000), ...parts.slice(3)].join(".");
  const tamperedIssued = [parts[0], String(Number(parts[1]) - 60000), ...parts.slice(2)].join(".");
  for (const bad of [tamperedMac, tamperedExpiry, tamperedIssued, "v1.1.2.3.4", "v2.1.2.3.4.5", "", "garbage"]) {
    assert.equal(await verifySession(request(name + "=" + bad), env, config, url), null, bad);
    assert.equal((await call("/", { headers: { Cookie: name + "=" + bad } })).status, 401);
  }
  assert.equal((await call("/", { headers: { Cookie: "other=1; " + cookie } })).status, 200);
  env.ACCESS_CODE_SHA256 = digest(CODE_B); // code A removed -> its sessions are revoked
  assert.equal((await call("/", { headers: { Cookie: cookie } })).status, 401);
  const viaB = cookieOf(await login(CODE_B));
  assert.equal((await call("/", { headers: { Cookie: viaB } })).status, 200);
  env.ACCESS_SESSION_SECRET = "rotated-synthetic-session-secret-not-a-real-value-0123456789";
  assert.equal((await call("/", { headers: { Cookie: viaB } })).status, 401);
  const fresh = cookieOf(await login(CODE_B));
  assert.equal((await call("/", { headers: { Cookie: fresh } })).status, 200);
  env.ACCESS_SESSION_SECONDS = "60"; // shortening the setting ends sessions minted for longer
  assert.equal((await call("/", { headers: { Cookie: fresh } })).status, 401);
  env.ACCESS_SESSION_SECONDS = "3600";
  assert.equal((await call("/", { headers: { Cookie: fresh } })).status, 200);
  const logout = await call(ACCESS_ROUTE, { method: "DELETE", headers: { Cookie: fresh, "Sec-Fetch-Site": "same-origin" } });
  assert.equal(logout.status, 204);
  assert.match(logout.headers.get("Set-Cookie"), /^__Host-pz_viewer=; Path=\/; Max-Age=0; HttpOnly; SameSite=Strict; Secure$/);
});

// WS-access2: shortening ACCESS_SESSION_SECONDS must never let an already rejected cookie become valid later.
const T0 = Date.parse("2026-10-13T12:00:00Z");
const gateEnv = (seconds, code = CODE_A) => ({ ACCESS_GATE_ENABLED: "true", ACCESS_CODE_SHA256: digest(code), ACCESS_SESSION_SECRET: SECRET,
  ACCESS_SESSION_SECONDS: String(seconds), PUBLISH_LIMITER: { limit: async () => ({ success: true }) } });
async function mintAt(env, now, code = CODE_A) {
  const r = await handleAccess(new Request("https://host.example.test" + ACCESS_ROUTE, { method: "POST",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code }) }), env, now);
  assert.equal(r.status, 200);
  return r.headers.get("Set-Cookie").split(";")[0];
}
async function validAt(env, cookie, now) {
  const url = new URL("https://host.example.test/");
  try { await requireViewer(new Request(url, { headers: { Cookie: cookie } }), env, url, now); return true; }
  catch (e) { if (e.message !== "access_required") throw e; return false; }
}
const signed = (issued, expires, code = CODE_A, version = "v2") => {
  const prefix = digest(code).slice(0, 8), nonce = "0123456789abcdef";
  const text = version === "v2" ? `v2|${issued}|${expires}|${prefix}|${nonce}` : `v1|${expires}|${prefix}|${nonce}`;
  const mac = createHmac("sha256", SECRET).update(text).digest("hex");
  return "__Host-pz_viewer=" + (version === "v2" ? `v2.${issued}.${expires}.${prefix}.${nonce}.${mac}` : `v1.${expires}.${prefix}.${nonce}.${mac}`);
};

test("shortening the session length rejects longer cookies at every later minute; it never resurrects them", async () => {
  const env = gateEnv(7200);
  const cookie = await mintAt(env, T0);
  assert.equal(await validAt(env, cookie, T0 + 10 * 60000), true);
  env.ACCESS_SESSION_SECONDS = "1800";
  const resurrected = [];
  for (let minute = 0; minute <= 180; minute++) if (await validAt(env, cookie, T0 + minute * 60000)) resurrected.push(minute);
  assert.deepEqual(resurrected, [], "main 9c99a5d accepted this cookie again at minutes 91-119");
  // A cookie minted under the short setting behaves normally under it.
  const short = await mintAt(env, T0 + 100 * 60000);
  assert.equal(await validAt(env, short, T0 + 100 * 60000), true);
  assert.equal(await validAt(env, short, T0 + 129 * 60000), true);
  assert.equal(await validAt(env, short, T0 + 130 * 60000), false, "expires at issue + 1800 s");
});

test("extending the session length keeps existing sessions until their own expiry; equal lengths stay valid", async () => {
  const env = gateEnv(1800);
  const cookie = await mintAt(env, T0);
  env.ACCESS_SESSION_SECONDS = "7200";
  assert.equal(await validAt(env, cookie, T0 + 29 * 60000), true);
  assert.equal(await validAt(env, cookie, T0 + 30 * 60000), false, "the signed expiry still ends it");
  env.ACCESS_SESSION_SECONDS = "1800";
  assert.equal(await validAt(env, cookie, T0 + 5 * 60000), true, "lifetime equal to the setting is allowed");
  env.ACCESS_SESSION_SECONDS = "1799";
  for (const minute of [0, 5, 29]) assert.equal(await validAt(env, cookie, T0 + minute * 60000), false);
});

test("legacy v1, forged lifetimes and future issue times are refused even with a valid signature", async () => {
  const env = gateEnv(3600);
  // A correctly signed v1 cookie (pre-WS-access2 format) is not accepted: it carries no issue time.
  assert.equal(await validAt(env, signed(null, T0 + 1800000, CODE_A, "v1"), T0), false);
  assert.equal(await validAt(env, signed(T0, T0 + 1800000), T0 + 1000), true, "control: a well-formed v2 cookie");
  assert.equal(await validAt(env, signed(T0, T0 + 3600000 + 1), T0 + 1000), false, "lifetime above the setting");
  assert.equal(await validAt(env, signed(T0, T0), T0 - 1), false, "expiry not after issue");
  assert.equal(await validAt(env, signed(T0 + 1000, T0), T0 - 5000), false, "expiry before issue");
  assert.equal(await validAt(env, signed(T0 + ISSUE_CLOCK_SKEW_MS, T0 + ISSUE_CLOCK_SKEW_MS + 60000), T0), true, "skew tolerance");
  assert.equal(await validAt(env, signed(T0 + ISSUE_CLOCK_SKEW_MS + 1, T0 + ISSUE_CLOCK_SKEW_MS + 60000), T0), false, "issued in the future");
  assert.equal(await validAt(env, signed(T0, T0 + 1800000, CODE_B), T0 + 1000), false, "code not in the list");
});

test("plain http loopback uses an unprefixed cookie without Secure; notice takes precedence over the gate", async () => {
  const { call, login, cookieOf } = fixture({ origin: "http://127.0.0.1:8787" });
  const opened = await login(CODE_A);
  assert.match(opened.headers.get("Set-Cookie"), /^pz_viewer=v2\..*; HttpOnly; SameSite=Strict$/);
  assert.equal((await call("/", { headers: { Cookie: cookieOf(opened) } })).status, 200);
  const on = await call(NOTICE_ROUTE, { method: "PUT", headers: { Authorization: "Bearer " + OPERATOR, "Content-Type": "application/json", "If-None-Match": "*" },
    body: JSON.stringify({ active: true, operator: "ops-a", reason: "drill", message_id: "maintenance" }) });
  assert.equal(on.status, 200);
  const r = await call("/");
  assert.equal(r.status, 503);
  assert.equal(r.headers.get("X-Pitcheezy-Notice"), "maintenance");
  assert.equal((await call(ACCESS_ROUTE)).status, 200, "session route stays reachable during a notice");
});

test("sessions are never minted over plain http away from loopback", async () => {
  assert.equal(transportAllowed(new URL("https://host.example.test/")), true);
  assert.equal(transportAllowed(new URL("http://127.0.0.1:8787/")), true);
  assert.equal(transportAllowed(new URL("http://localhost:8787/")), true);
  assert.equal(transportAllowed(new URL("http://host.example.test/")), false);
  assert.equal(transportAllowed(new URL("http://10.0.0.5/")), false);
  const { call, login } = fixture({ origin: "http://host.example.test" });
  const opened = await login(CODE_A);
  assert.equal(opened.status, 503);
  assert.equal((await opened.json()).error, "https_required");
  assert.equal(opened.headers.get("Set-Cookie"), null);
  assert.equal((await call("/")).status, 401, "the gate stays closed");
});

test("monitor records a gated host as access_required, not as an outage", async () => {
  const config = { schema: "pitcheezy-host-monitor-v1", origin: "https://public.example.test", allow_loopback_http: false,
    timeout_ms: 200, max_body_bytes: 4096, timestamp_pointer: null, timestamp_format: "rfc3339", max_age_seconds: 120,
    clock_skew_seconds: 30, page_sha256: null };
  const fetchImpl = async () => new Response('{"error":"access_required"}', { status: 401, headers: {
    "Content-Type": "application/json", "X-Pitcheezy-Access": "required", "Cache-Control": "no-store" } });
  const report = await probe(config, { fetchImpl, now: () => Date.parse("2026-10-13T00:00:00Z") });
  assert.equal(report.status, "failed");
  assert.equal(report.access_gate_active, true);
  assert.equal(report.notice_active, false);
  assert.deepEqual(report.issues, ["page_access_required", "health_access_required"]);
});

test("actual local Worker runtime: gate, login, cookie round trip, logout and form redirect", { timeout: 30000 }, async () => {
  const mf = new Miniflare({
    modules: true, modulesRoot: fileURLToPath(new URL("../", import.meta.url)),
    scriptPath: fileURLToPath(new URL("../worker.mjs", import.meta.url)),
    compatibilityDate: "2026-07-30", r2Buckets: ["PUBLISH_BUCKET"],
    ratelimits: { PUBLISH_LIMITER: { namespace_id: "1002", simple: { limit: 60, period: 60 } } },
    bindings: { DATA_READ_ENABLED: "true", UPLOAD_ENABLED: "true", PUBLISH_TOKEN_SHA256: digest(PUBLISH_TOKEN),
      ACCESS_GATE_ENABLED: "true", ACCESS_CODE_SHA256: digest(CODE_A), ACCESS_SESSION_SECRET: SECRET, ACCESS_SESSION_SECONDS: "60" },
    serviceBindings: { ASSETS: () => new Response("<!doctype html><html>frontend</html>", { headers: { "Content-Type": "text/html", "Cache-Control": "public, max-age=60" } }) },
  });
  try {
    await mf.ready;
    const call = (route, init) => mf.dispatchFetch("http://localhost" + route, init);
    const body = '{"synthetic":true}';
    const saved = await call("/_publish" + game, { method: "PUT", body, headers: { Authorization: "Bearer " + PUBLISH_TOKEN,
      "Content-Type": "application/json", "X-Content-SHA256": digest(body), "If-None-Match": "*" } });
    assert.equal(saved.status, 200); await saved.arrayBuffer();
    const locked = await call("/");
    assert.equal(locked.status, 401); assert.match(await locked.text(), /접속 코드/);
    assert.equal((await call(game)).status, 401);
    const denied = await call(ACCESS_ROUTE, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code: "synthetic-wrong-code-000" }) });
    assert.equal(denied.status, 401); await denied.arrayBuffer();
    const opened = await call(ACCESS_ROUTE, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code: CODE_A }) });
    assert.equal(opened.status, 200, await opened.clone().text());
    const cookie = opened.headers.get("Set-Cookie").split(";")[0];
    assert.match(cookie, /^pz_viewer=v2\./);
    await opened.arrayBuffer();
    const screen = await call("/", { headers: { Cookie: cookie } });
    assert.equal(screen.status, 200); assert.equal(screen.headers.get("Cache-Control"), "private, max-age=60"); await screen.arrayBuffer();
    const data = await call(game, { headers: { Cookie: cookie } });
    assert.equal(await data.text(), body);
    const form = await call(ACCESS_ROUTE, { method: "POST", redirect: "manual", headers: { "Content-Type": "application/x-www-form-urlencoded" }, body: "code=" + encodeURIComponent(CODE_A) });
    assert.equal(form.status, 303); assert.equal(form.headers.get("Location"), "/"); await form.arrayBuffer();
    const logout = await call(ACCESS_ROUTE, { method: "DELETE", headers: { Cookie: cookie } });
    assert.equal(logout.status, 204); assert.match(logout.headers.get("Set-Cookie"), /Max-Age=0/); await logout.arrayBuffer();
    assert.equal((await call("/")).status, 401);
    // WS-access2 on the real runtime. main 9c99a5d compared only the remaining lifetime, so a cookie refused right
    // after shortening became valid again once its remaining lifetime fell below the new setting. Mint a 6 s cookie,
    // restart with 3 s, and check both right away and inside that window (about 3.8 s after minting).
    const restart = seconds => mf.setOptions({
      modules: true, modulesRoot: fileURLToPath(new URL("../", import.meta.url)),
      scriptPath: fileURLToPath(new URL("../worker.mjs", import.meta.url)),
      compatibilityDate: "2026-07-30", r2Buckets: ["PUBLISH_BUCKET"],
      ratelimits: { PUBLISH_LIMITER: { namespace_id: "1002", simple: { limit: 60, period: 60 } } },
      bindings: { DATA_READ_ENABLED: "true", UPLOAD_ENABLED: "true", PUBLISH_TOKEN_SHA256: digest(PUBLISH_TOKEN),
        ACCESS_GATE_ENABLED: "true", ACCESS_CODE_SHA256: digest(CODE_A), ACCESS_SESSION_SECRET: SECRET, ACCESS_SESSION_SECONDS: String(seconds) },
      serviceBindings: { ASSETS: () => new Response("<!doctype html><html>frontend</html>", { headers: { "Content-Type": "text/html" } }) },
    });
    const loginNow = async () => {
      const r = await call(ACCESS_ROUTE, { method: "POST", headers: { "Content-Type": "application/json" }, body: JSON.stringify({ code: CODE_A }) });
      assert.equal(r.status, 200); const c = r.headers.get("Set-Cookie").split(";")[0]; await r.arrayBuffer(); return c;
    };
    await restart(6);
    const mintedAt = Date.now();
    const sixSecond = await loginNow();
    const before = await call("/", { headers: { Cookie: sixSecond } });
    assert.equal(before.status, 200); await before.arrayBuffer();
    await restart(3);
    const refused = await call("/", { headers: { Cookie: sixSecond } });
    assert.equal(refused.status, 401, "a 6 s cookie does not fit a 3 s setting"); await refused.arrayBuffer();
    await new Promise(r => setTimeout(r, Math.max(0, mintedAt + 3800 - Date.now())));
    assert.ok(Date.now() < mintedAt + 5600, "the check must run before the cookie's own expiry to be meaningful");
    const stillRefused = await call("/", { headers: { Cookie: sixSecond } });
    assert.equal(stillRefused.status, 401, "remaining lifetime is now below 3 s: main accepted here, the fix must not"); await stillRefused.arrayBuffer();
    const shortCookie = await loginNow();
    const ok = await call("/", { headers: { Cookie: shortCookie } });
    assert.equal(ok.status, 200); await ok.arrayBuffer();
  } finally { await mf.dispose(); }
});

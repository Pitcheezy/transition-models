/** Isolated local rehearsal only. This helper accepts no external target or account. */
import { Miniflare } from "miniflare";
import { createHash, randomBytes } from "node:crypto";
import { readFile } from "node:fs/promises";
import https from "node:https";
import net from "node:net";
import { fileURLToPath } from "node:url";

export const fixtureHtml = '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>합성 호스트 리허설</title><h1>합성 운영 리허설</h1><p>실제 경기·추천·성능 자료가 아닙니다.</p><button id="refresh">합성 파일 다시 읽기</button><output id="state" aria-live="polite">아직 읽지 않음</output><script type="module" src="/fixture.mjs"></script></html>';
const fixtureJs = 'let current;document.querySelector("#refresh").addEventListener("click",async()=>{current?.abort();const c=new AbortController();current=c;const timer=setTimeout(()=>c.abort(),3000);const out=document.querySelector("#state");out.textContent="읽는 중";try{const r=await fetch("/v1/game/123.json",{signal:c.signal,cache:"no-store",credentials:"same-origin"});if(current!==c)return;if(r.status===404){out.textContent="파일 없음";return;}if(r.status===401&&r.headers.get("X-Pitcheezy-Access")){out.textContent="접속 필요";return;}if(r.status===503&&r.headers.get("X-Pitcheezy-Notice")){const n=await r.json();if(current!==c)return;out.textContent=n.error==="service_notice"?"안내 중: "+n.notice.id:"읽기 실패";return;}if(!r.ok)throw Error();const x=await r.json();if(current!==c)return;if(x.synthetic!==true||!Number.isInteger(x.synthetic_version))throw Error();out.textContent="합성 v"+x.synthetic_version;}catch{if(current===c)out.textContent="읽기 실패";}finally{clearTimeout(timer);}});window.fixtureReady=true;';
export const hash = value => createHash("sha256").update(value).digest("hex");

/** Bound runtime waits; a timed-out shutdown is reported as unconfirmed, never as success. */
export async function waitForReady(ready, signal) {
  if (!signal) return ready;
  signal.throwIfAborted();
  let abort;
  try {
    return await Promise.race([ready, new Promise((_, reject) => {
      abort = () => reject(new Error("runtime_start_aborted"));
      signal.addEventListener("abort", abort, { once: true });
    })]);
  } finally { signal.removeEventListener("abort", abort); }
}
export async function boundedCleanup(dispose, timeoutMs = 5000) {
  let timer;
  try {
    return await Promise.race([
      Promise.resolve().then(dispose).then(() => ({ status: "complete" }),
        () => ({ status: "failed", code: "runtime_cleanup_failed" })),
      new Promise(resolve => { timer = setTimeout(() =>
        resolve({ status: "unconfirmed", code: "runtime_cleanup_timeout" }), timeoutMs); }),
    ]);
  } finally { clearTimeout(timer); }
}

/** Page for the collection checks (WS-access3): mounts OUR widget with options chosen by the test. */
export const collectHtml = '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>합성 수집 검사</title><link rel="stylesheet" href="/widget.css"><h1>합성 경기 관전</h1><p>가짜 경기와 합성 기록만 사용합니다.</p><div id="slot"></div><script type="module">import{mountUsageWidget}from"/widget.mjs";window.mount=o=>{window.widget?.destroy();window.widget=mountUsageWidget(document.querySelector("#slot"),o);};window.collectReady=true;</script></html>';
// Local stand-in for the Cloudflare edge, used only by the opt-in collection mode (the app Worker code is unchanged):
// the real edge overwrites any client-sent CF-Connecting-IP with the peer address, and it decouples the client
// connection from the Worker, so a Worker answering before reading the body (gate 401) never resets the client.
// The local TLS server would otherwise drop such early response bodies, so the stand-in reads the body first.
const edgeShim = 'export default{async fetch(request,env){const headers=new Headers(request.headers);headers.set("CF-Connecting-IP","127.0.0.1");' +
  'const body=["GET","HEAD"].includes(request.method)?null:await request.arrayBuffer();' +
  'return env.APP.fetch(new Request(request.url,{method:request.method,headers,body,redirect:"manual"}));}};';
/**
 * Node-side request to the ephemeral loopback https runtime. Miniflare's `https: true` serves its built-in
 * development certificate (fixed, its key ships in the package), so verification is disabled here; the helper
 * refuses every target except https://127.0.0.1. Redirects are never followed.
 */
export function localHttps(target, init = {}) {
  return new Promise((resolve, reject) => {
    const url = new URL(target);
    if (url.protocol !== "https:" || url.hostname !== "127.0.0.1") { reject(new Error("local_target_required")); return; }
    const headers = Object.fromEntries(new Headers(init.headers || {}));
    const body = init.body === undefined || init.body === null ? null : Buffer.from(init.body);
    if (body) headers["content-length"] = String(body.length);
    const method = init.method || "GET";
    const request = https.request({ hostname: url.hostname, port: url.port, path: url.pathname + url.search, method, headers,
      rejectUnauthorized: false, timeout: 5000 }, response => {
      const chunks = [];
      response.on("data", chunk => chunks.push(chunk));
      response.on("error", reject);
      response.on("end", () => {
        const out = new Headers();
        for (const [key, value] of Object.entries(response.headers)) {
          if (Array.isArray(value)) for (const v of value) out.append(key, v);
          else if (value !== undefined) out.set(key, value);
        }
        const empty = method === "HEAD" || [204, 205, 304].includes(response.statusCode);
        resolve(new Response(empty ? null : Buffer.concat(chunks), { status: response.statusCode, headers: out }));
      });
    });
    request.on("timeout", () => request.destroy(new Error("local_request_timeout")));
    request.on("error", reject);
    if (body) request.write(body);
    request.end();
  });
}

async function freeLoopbackPort() {
  return await new Promise((resolve, reject) => {
    const server = net.createServer();
    server.once("error", reject);
    server.listen(0, "127.0.0.1", () => { const { port } = server.address(); server.close(() => resolve(port)); });
  });
}

/**
 * Options: notice (operator switch), access ({codes?, sessionSeconds?}) for the viewer gate, and
 * collection (true or {}) for the opt-in collection mode: local https with Miniflare's built-in development certificate,
 * real D1 with the telemetry migration, telemetry and feedback ON, the edge stand-in above, and the
 * widget files served as assets. Collection needs https because COLLECTION_ORIGIN is https-only.
 */
export async function startLocalHost({ signal, notice = true, access = null, collection = null, assets = null } = {}) {
  const token = randomBytes(32).toString("base64url");
  // Separate ephemeral operator token for the emergency notice switch (never the publisher token).
  const noticeToken = randomBytes(32).toString("base64url");
  // Optional viewer access gate: ephemeral codes and a separate session secret, never written to receipts.
  const accessCodes = access ? (access.codes || [randomBytes(12).toString("base64url")]) : [];
  const accessSecret = randomBytes(32).toString("base64url");
  const accessBindings = access ? {
    ACCESS_GATE_ENABLED: "true", ACCESS_CODE_SHA256: accessCodes.map(hash).join(","),
    ACCESS_SESSION_SECRET: accessSecret, ACCESS_SESSION_SECONDS: String(access.sessionSeconds || 3600),
  } : {};
  const collectionMode = collection !== null && collection !== false;
  const port = collectionMode ? await freeLoopbackPort() : 0;
  const plannedOrigin = collectionMode ? `https://127.0.0.1:${port}` : null;
  const client = collectionMode ? Object.fromEntries(await Promise.all(["usage-client.mjs", "widget.mjs", "widget.css"].map(async name =>
    [name, await readFile(new URL("../client/" + name, import.meta.url), "utf8")]))) : {};
  const collectionBindings = collectionMode ? {
    TELEMETRY_ENABLED: "true", FEEDBACK_ENABLED: "true", COLLECTION_ORIGIN: plannedOrigin, TELEMETRY_RETAIN_DAYS: "30",
    SESSION_WRITES_PER_DAY: "1000", FEEDBACK_ROWS_PER_DAY: "1000", TELEMETRY_RATE_SECRET: randomBytes(32).toString("base64url"),
  } : {};
  const app = {
    modules: true, modulesRoot: fileURLToPath(new URL("../", import.meta.url)), scriptPath: fileURLToPath(new URL("../worker.mjs", import.meta.url)),
    compatibilityDate: "2026-07-30",
    r2Buckets: ["PUBLISH_BUCKET"],
    ratelimits: { PUBLISH_LIMITER: { namespace_id: "1002", simple: { limit: 60, period: 60 } },
      ...(collectionMode ? { TELEMETRY_LIMITER: { namespace_id: "1001", simple: { limit: 60, period: 60 } } } : {}) },
    ...(collectionMode ? { d1Databases: ["TELEMETRY_DB"] } : {}),
    bindings: { DATA_READ_ENABLED: "true", UPLOAD_ENABLED: "true", PUBLISH_TOKEN_SHA256: hash(token),
      ...(notice ? { NOTICE_TOKEN_SHA256: hash(noticeToken) } : {}), ...accessBindings, ...collectionBindings },
    serviceBindings: {
      // `assets` lets a rehearsal install a real front end (EXHIBIT-host1); the fixture stays the default.
      ASSETS: assets || (request => {
        const path = new URL(request.url).pathname;
        if (path === "/") return new Response(fixtureHtml, { headers: { "Content-Type": "text/html; charset=utf-8" } });
        if (path === "/fixture.mjs") return new Response(fixtureJs, { headers: { "Content-Type": "text/javascript" } });
        if (collectionMode && path === "/collect.html") return new Response(collectHtml, { headers: { "Content-Type": "text/html; charset=utf-8" } });
        if (collectionMode && ["/usage-client.mjs", "/widget.mjs", "/widget.css"].includes(path)) {
          return new Response(client[path.slice(1)], { headers: { "Content-Type": path.endsWith(".css") ? "text/css" : "text/javascript" } });
        }
        return new Response("not found", { status: 404 });
      }),
    },
  };
  const mf = new Miniflare(collectionMode ? {
    host: "127.0.0.1", port, https: true,
    workers: [
      { name: "edge", modules: true, script: edgeShim, compatibilityDate: "2026-07-30", serviceBindings: { APP: "app" } },
      { name: "app", ...app },
    ],
  } : { ...app, host: "127.0.0.1", port: 0 });
  try {
    const origin = (await waitForReady(mf.ready, signal)).origin;
    const url = new URL(origin);
    if (url.hostname !== "127.0.0.1" || url.protocol !== (collectionMode ? "https:" : "http:") || (collectionMode && origin !== plannedOrigin)) {
      throw new Error("local_target_required");
    }
    let db = null;
    if (collectionMode) {
      db = await mf.getD1Database("TELEMETRY_DB", "app");
      const sql = await readFile(new URL("../migrations/0001_telemetry.sql", import.meta.url), "utf8");
      await db.batch(sql.split(";").map(x => x.trim()).filter(Boolean).map(x => db.prepare(x)));
    }
    // Collection mode serves a self-signed loopback certificate; Node-side helpers use localHttps for it.
    const send = collectionMode ? localHttps : fetch;
    // Auth stays inside this ephemeral helper; never returned in a receipt.
    const mutate = (path, init) => send(origin + "/_publish" + path, {
      ...init, redirect: "error", signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(5000)]) : AbortSignal.timeout(5000),
      headers: { Authorization: "Bearer " + token, ...init.headers },
    });
    const admin = (init) => send(origin + "/_notice/v1/state", {
      ...init, redirect: "error", signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(5000)]) : AbortSignal.timeout(5000),
      headers: { Authorization: "Bearer " + noticeToken, ...init.headers },
    });
    return {
      origin,
      publish: (path, body, etag = null) => mutate(path, {
        method: "PUT", body, headers: {
          "Content-Type": "application/json", "X-Content-SHA256": hash(body),
          ...(etag ? { "If-Match": etag } : { "If-None-Match": "*" }),
        },
      }),
      withdraw: (path, etag) => mutate(path, { method: "DELETE", headers: { "If-Match": etag } }),
      /** Operator switch: change = { active, operator, reason, message_id }; etag of the current state or null. */
      setNotice: (change, etag = null) => admin({
        method: "PUT", body: JSON.stringify(change), headers: {
          "Content-Type": "application/json", ...(etag ? { "If-Match": etag } : { "If-None-Match": "*" }),
        },
      }),
      noticeState: () => admin({ method: "GET" }),
      /** Test-only: the ephemeral viewer codes (never put them into receipts, HTML or logs). */
      accessCodes,
      /** Viewer login from Node; returns the response (Set-Cookie header carries the session). */
      login: (code, { form = false, headers = {} } = {}) => send(origin + "/_access/v1/session", {
        method: "POST", redirect: "manual", signal: AbortSignal.timeout(5000),
        headers: { "Content-Type": form ? "application/x-www-form-urlencoded" : "application/json", ...headers },
        body: form ? new URLSearchParams({ code }).toString() : JSON.stringify({ code }),
      }),
      /** Collection mode only: stored row counts and the daily budget, read straight from local D1. */
      collectionCounts: async () => {
        if (!db) throw new Error("collection_mode_required");
        const row = await db.prepare("SELECT (SELECT COUNT(*) FROM usage_sessions) AS sessions, (SELECT COUNT(*) FROM feedback) AS feedback, " +
          "(SELECT COALESCE(SUM(used),0) FROM telemetry_budget) AS budget_used").first();
        return { sessions: row.sessions, feedback: row.feedback, budget_used: row.budget_used };
      },
      sessionRows: async () => {
        if (!db) throw new Error("collection_mode_required");
        return (await db.prepare("SELECT session_id, game_pk, sequence, active_ms FROM usage_sessions ORDER BY created_ms").all()).results;
      },
      /** Raw request from Node through the runtime entry (edge stand-in included in collection mode). */
      request: (path, init = {}) => send(origin + path, { redirect: "manual", ...init }),
      dispose: () => mf.dispose(),
    };
  } catch {
    const cleanup = await boundedCleanup(() => mf.dispose());
    throw Object.assign(new Error("local_start_failed"), { cleanup });
  }
}

/** Isolated local rehearsal only. This helper accepts no external target or account. */
import { Miniflare } from "miniflare";
import { createHash, randomBytes } from "node:crypto";
import { fileURLToPath } from "node:url";

export const fixtureHtml = '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>합성 호스트 리허설</title><h1>합성 운영 리허설</h1><p>실제 경기·추천·성능 자료가 아닙니다.</p><button id="refresh">합성 파일 다시 읽기</button><output id="state" aria-live="polite">아직 읽지 않음</output><script type="module" src="/fixture.mjs"></script></html>';
const fixtureJs = 'let current;document.querySelector("#refresh").addEventListener("click",async()=>{current?.abort();const c=new AbortController();current=c;const timer=setTimeout(()=>c.abort(),3000);const out=document.querySelector("#state");out.textContent="읽는 중";try{const r=await fetch("/v1/game/123.json",{signal:c.signal,cache:"no-store",credentials:"omit"});if(current!==c)return;if(r.status===404){out.textContent="파일 없음";return;}if(!r.ok)throw Error();const x=await r.json();if(current!==c)return;if(x.synthetic!==true||!Number.isInteger(x.synthetic_version))throw Error();out.textContent="합성 v"+x.synthetic_version;}catch{if(current===c)out.textContent="읽기 실패";}finally{clearTimeout(timer);}});window.fixtureReady=true;';
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

export async function startLocalHost({ signal } = {}) {
  const token = randomBytes(32).toString("base64url");
  const mf = new Miniflare({
    modules: true, modulesRoot: fileURLToPath(new URL("../", import.meta.url)), scriptPath: fileURLToPath(new URL("../worker.mjs", import.meta.url)),
    compatibilityDate: "2026-07-30", host: "127.0.0.1", port: 0,
    r2Buckets: ["PUBLISH_BUCKET"],
    bindings: { DATA_READ_ENABLED: "true", UPLOAD_ENABLED: "true", PUBLISH_TOKEN_SHA256: hash(token) },
    serviceBindings: {
      ASSETS: request => {
        const path = new URL(request.url).pathname;
        if (path === "/") return new Response(fixtureHtml, { headers: { "Content-Type": "text/html; charset=utf-8" } });
        if (path === "/fixture.mjs") return new Response(fixtureJs, { headers: { "Content-Type": "text/javascript" } });
        return new Response("not found", { status: 404 });
      },
    },
  });
  try {
    const origin = (await waitForReady(mf.ready, signal)).origin;
    const url = new URL(origin);
    if (url.protocol !== "http:" || url.hostname !== "127.0.0.1") throw new Error("local_target_required");
    // Auth stays inside this ephemeral helper; never returned in a receipt.
    const mutate = (path, init) => fetch(origin + "/_publish" + path, {
      ...init, redirect: "error", signal: signal ? AbortSignal.any([signal, AbortSignal.timeout(5000)]) : AbortSignal.timeout(5000),
      headers: { Authorization: "Bearer " + token, ...init.headers },
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
      dispose: () => mf.dispose(),
    };
  } catch {
    const cleanup = await boundedCleanup(() => mf.dispose());
    throw Object.assign(new Error("local_start_failed"), { cleanup });
  }
}

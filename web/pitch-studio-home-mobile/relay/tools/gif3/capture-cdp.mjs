// capture-cdp.mjs — headless Chrome + CDP recorder (no npm deps; Node 22+ global WebSocket).
// usage: node capture-cdp.mjs <plan.json>
// plan: { name, url, width, height, dpr, readyJs, prime:[{js, waitMs}], recordMs, actions:[{at, js}], finalJs, outDir, port, chrome,
//         virtual: true|false  — true(기본): 페이지의 rAF·setTimeout·setInterval·performance.now·Date.now를 가상 시계로 바꿔 프레임마다 FRAME_MS씩 진행시키고
//                                 Page.captureScreenshot으로 그 프레임을 찍는다(기계 속도와 무관한 결정적 녹화). false: 실시간 screencast(이전 방식). }
import { spawn, spawnSync } from "node:child_process";
import { mkdirSync, writeFileSync, rmSync, readFileSync } from "node:fs";
import { setTimeout as sleep } from "node:timers/promises";
import path from "node:path";

const plan = JSON.parse(readFileSync(process.argv[2], "utf8"));
const CHROME = plan.chrome || "C:/Program Files/Google/Chrome/Application/chrome.exe";
const PORT = plan.port || 9333;
const VIRTUAL = plan.virtual !== false;
const FRAME_MS = plan.frameMs || 1000 / 30;
const outDir = path.resolve(plan.outDir);
rmSync(outDir, { recursive: true, force: true }); mkdirSync(outDir, { recursive: true });
const profile = path.resolve(path.dirname(outDir), "profile-" + plan.name);
rmSync(profile, { recursive: true, force: true });

const chrome = spawn(CHROME, [
  "--headless=new", `--remote-debugging-port=${PORT}`, `--user-data-dir=${profile}`,
  "--no-first-run", "--no-default-browser-check", "--enable-unsafe-swiftshader", "--use-angle=swiftshader",
  "--ignore-gpu-blocklist", "--hide-scrollbars", "--window-size=900,1300", "--disable-background-timer-throttling",
  "--disable-renderer-backgrounding", "--disable-backgrounding-occluded-windows", "--autoplay-policy=no-user-gesture-required",
  "--disable-features=CalculateNativeWinOcclusion", "about:blank",
], { stdio: ["ignore", "ignore", "pipe"] });
let chromeErr = ""; chrome.stderr.on("data", (d) => { chromeErr += d; });
const shutdown = (code) => { try { spawnSync("taskkill", ["/PID", String(chrome.pid), "/T", "/F"], { stdio: "ignore" }); } catch {} process.exit(code); };

async function targets() {
  for (let i = 0; i < 100; i++) {
    try { const r = await fetch(`http://127.0.0.1:${PORT}/json`); if (r.ok) return await r.json(); } catch {}
    await sleep(100);
  }
  throw new Error("chrome devtools not reachable\n" + chromeErr.slice(-2000));
}
try {
const list = await targets();
const page = list.find((t) => t.type === "page");
if (!page) throw new Error("no page target: " + JSON.stringify(list));

const ws = new WebSocket(page.webSocketDebuggerUrl);
await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });
let nextId = 1; const pending = new Map(); const handlers = new Map();
ws.onmessage = (ev) => {
  const m = JSON.parse(ev.data);
  if (m.id && pending.has(m.id)) { const { res, rej } = pending.get(m.id); pending.delete(m.id); m.error ? rej(new Error(JSON.stringify(m.error))) : res(m.result); }
  else if (m.method && handlers.has(m.method)) handlers.get(m.method)(m.params);
};
const send = (method, params = {}) => new Promise((res, rej) => { const id = nextId++; pending.set(id, { res, rej }); ws.send(JSON.stringify({ id, method, params })); });
const evaluate = async (js, awaitPromise = true) => { const r = await send("Runtime.evaluate", { expression: js, returnByValue: true, awaitPromise }); if (r.exceptionDetails) throw new Error("page js error: " + JSON.stringify(r.exceptionDetails).slice(0, 500)); return r.result.value; };

await send("Page.enable"); await send("Runtime.enable");
await send("Emulation.setDeviceMetricsOverride", { width: plan.width || 375, height: plan.height || 812, deviceScaleFactor: plan.dpr || 2, mobile: true });
if (plan.userAgent) await send("Emulation.setUserAgentOverride", { userAgent: plan.userAgent });
if (VIRTUAL) {
  // 가상 시계: 페이지 안의 시간 API를 바꿔 치기. 프레임마다 __vt.step(ms)로만 흐른다. (timeweb 방식) 네트워크·Promise·MutationObserver는 그대로 실시간.
  await send("Page.addScriptToEvaluateOnNewDocument", { source: `(() => {
    let now = 0; const t0 = Date.now(); let rid = 0, tid = 0; const rafs = new Map(), timers = new Map();
    const RealDate = Date;
    performance.now = () => now;
    Date.now = () => t0 + now;
    window.Date = new Proxy(RealDate, { construct(T, args) { return args.length ? new T(...args) : new T(t0 + now); }, apply() { return new T(t0 + now).toString(); } });
    window.Date.now = () => t0 + now; window.Date.UTC = RealDate.UTC; window.Date.parse = RealDate.parse;
    window.requestAnimationFrame = (cb) => { const i = ++rid; rafs.set(i, cb); return i; };
    window.cancelAnimationFrame = (i) => { rafs.delete(i); };
    window.setTimeout = (fn, ms = 0, ...a) => { const i = ++tid; timers.set(i, { at: now + Math.max(0, Number(ms) || 0), fn, a }); return i; };
    window.setInterval = (fn, ms = 0, ...a) => { const i = ++tid; const every = Math.max(1, Number(ms) || 1); timers.set(i, { at: now + every, fn, a, every }); return i; };
    window.clearTimeout = window.clearInterval = (i) => { timers.delete(i); };
    window.__vt = {
      now: () => now,
      step(ms) {
        const target = now + ms;
        for (let guard = 0; guard < 10000; guard++) {
          let k = null, t = null; for (const [kk, tt] of timers) if (tt.at <= target && (t === null || tt.at < t.at)) { k = kk; t = tt; }
          if (t === null) break; now = Math.max(now, t.at); if (t.every) t.at += t.every; else timers.delete(k);
          try { typeof t.fn === "function" ? t.fn(...t.a) : (0, eval)(String(t.fn)); } catch (e) { console.error("vt timer", e && e.message); }
        }
        now = target; const cbs = [...rafs.values()]; rafs.clear();
        for (const cb of cbs) { try { cb(now); } catch (e) { console.error("vt raf", e && e.message); } }
        return now;
      },
    };
  })();` });
}
const consoleLog = []; handlers.set("Runtime.consoleAPICalled", (p) => consoleLog.push(`${p.type}: ${p.args.map((a) => a.value ?? a.description ?? "").join(" ")}`.slice(0, 300)));
handlers.set("Runtime.exceptionThrown", (p) => consoleLog.push("exception: " + JSON.stringify(p.exceptionDetails).slice(0, 300)));

const loaded = new Promise((res) => handlers.set("Page.loadEventFired", res));
await send("Page.navigate", { url: plan.url });
await Promise.race([loaded, sleep(30000)]);

// 가상 시간 한 걸음 + 실제 잠깐 대기(fetch·Promise가 흐르게)
const vstep = async (ms) => { if (VIRTUAL) await evaluate(`__vt.step(${ms})`, false); else await sleep(ms); };
const vwait = async (ms) => { for (let d = 0; d < ms; d += FRAME_MS) { await vstep(FRAME_MS); if (VIRTUAL) await sleep(3); } };

// readiness poll
const t0 = Date.now(); let ready = false;
while (Date.now() - t0 < (plan.readyTimeoutMs || 90000)) {
  try { if (await evaluate(plan.readyJs || "true")) { ready = true; break; } } catch (e) { /* page still booting */ }
  await vstep(FRAME_MS * 2); await sleep(40);
}
if (!ready) console.error("not ready; console:", consoleLog.slice(-10));
console.error(`[${plan.name}] ready after ${Date.now() - t0} ms${VIRTUAL ? " (virtual clock)" : ""}`);

for (const step of plan.prime || []) { if (step.js) await evaluate(step.js); if (step.waitMs) await vwait(step.waitMs); }

const frames = []; let fi = 0; const marks = [];
const actions = [...(plan.actions || [])].sort((a, b) => a.at - b.at);
if (VIRTUAL) {
  const n = Math.ceil(plan.recordMs / FRAME_MS); let ai = 0;
  for (let i = 0; i <= n; i++) {
    const t = i * FRAME_MS;
    while (ai < actions.length && actions[ai].at <= t) { let result = null; try { result = await evaluate(actions[ai].js); } catch (e) { result = "ERR " + e.message.slice(0, 200); } marks.push({ at: Math.round(t), planned: actions[ai].at, label: actions[ai].label || "", result }); ai++; await sleep(3); }
    await vstep(FRAME_MS); await sleep(2);
    const shot = await send("Page.captureScreenshot", { format: "jpeg", quality: plan.quality || 85 });
    const file = `f${String(fi++).padStart(5, "0")}.jpg`; writeFileSync(path.join(outDir, file), Buffer.from(shot.data, "base64"));
    frames.push({ t: Math.round(t), file });
  }
} else {
  let recStart = 0;
  handlers.set("Page.screencastFrame", (p) => {
    const t = performance.now() - recStart; const file = `f${String(fi++).padStart(5, "0")}.jpg`;
    writeFileSync(path.join(outDir, file), Buffer.from(p.data, "base64")); frames.push({ t: Math.round(t), file, ts: p.metadata.timestamp });
    send("Page.screencastFrameAck", { sessionId: p.sessionId }).catch(() => {});
  });
  await send("Page.startScreencast", { format: "jpeg", quality: plan.quality || 82, maxWidth: (plan.width || 375) * (plan.dpr || 2), maxHeight: (plan.height || 812) * (plan.dpr || 2), everyNthFrame: 1 });
  recStart = performance.now();
  for (const a of actions) {
    const wait = a.at - (performance.now() - recStart); if (wait > 0) await sleep(wait);
    const at = Math.round(performance.now() - recStart); let result = null; try { result = await evaluate(a.js); } catch (e) { result = "ERR " + e.message.slice(0, 200); }
    marks.push({ at, planned: a.at, label: a.label || "", result });
  }
  const rest = plan.recordMs - (performance.now() - recStart); if (rest > 0) await sleep(rest);
  await send("Page.stopScreencast"); await sleep(200);
}
let finalState = null; try { finalState = plan.finalJs ? await evaluate(plan.finalJs) : null; } catch (e) { finalState = "ERR " + e.message; }
writeFileSync(path.join(outDir, "index.json"), JSON.stringify({ plan: plan.name, url: plan.url, width: plan.width, height: plan.height, dpr: plan.dpr, virtual: VIRTUAL, frameMs: FRAME_MS, frames, marks, finalState, console: consoleLog.slice(-40) }, null, 1));
console.error(`[${plan.name}] frames ${frames.length}, span ${frames.length ? frames[frames.length - 1].t : 0} ms, marks ${JSON.stringify(marks)}`);
try { ws.close(); } catch {}
shutdown(0);
} catch (e) { console.error("capture failed:", e && e.message); shutdown(1); }

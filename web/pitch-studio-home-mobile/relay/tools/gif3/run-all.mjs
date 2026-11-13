// run-all.mjs — build capture plans for v0/v1/v2(/v2pz) and run capture-cdp.mjs for each, sequentially.
// usage: node run-all.mjs [v0 v1 v2 v2pz]
import { writeFileSync } from "node:fs";
import { spawnSync } from "node:child_process";
import path from "node:path";

const here = path.dirname(new URL(import.meta.url).pathname.replace(/^\/([A-Za-z]:)/, "$1"));
const STEP_AT = [600, 4600, 8600, 12600];          // ms from record start: idx 8, 9, 10, 11
const RECORD_MS = 16600;
const STEPS = [8, 9, 10, 11];

const relayReady = "!!(window.PZRelay && window.PZRelay.state3D && window.PZRelay.state3D().attached && window.PZRelay.state3D().idleLoop)";
const relayPrime = (i) => `(() => { const b = document.querySelector('.prow[data-index="${i}"]'); if (!b) return 'no prow'; b.click(); return 'sel ' + ${i}; })()`;
const relayStep = (i) => `(() => { const b = document.querySelector('.prow[data-index="${i}"]'); if (!b) return 'no prow'; b.click(); const s = window.PZRelay.state3D(); return JSON.stringify({ i: ${i}, kind: s.kind, k: s.k }); })()`;
const relayFinal = "JSON.stringify(window.PZRelay.state3D())";

const v0Ready = "!!document.querySelector('.sv-atbat-toggle')";
const v0Prime = `(async () => {
  const q = (s) => document.querySelector(s); const ms = async () => { for (let i = 0; i < 4; i++) await new Promise((r) => queueMicrotask(r)); }; // 가상 시계 녹화에서도 풀리게 setTimeout 대신 마이크로태스크(React 동기 갱신은 마이크로태스크에서 끝난다)
  const tg = q('.sv-atbat-toggle'); if (tg && tg.getAttribute('aria-expanded') !== 'true') { tg.click(); await ms(80); }
  const row = [...document.querySelectorAll('.sv-pitch-row')].find((b) => (b.getAttribute('aria-label') || '').startsWith('1구')); if (!row) return 'no row';
  row.click(); await ms(80);
  for (let i = 0; i < 7; i++) { const nx = q('button[aria-label="다음 공"]'); if (!nx) return 'no next at ' + i; nx.click(); await ms(40); }
  const cl = [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === '닫기' || b.getAttribute('aria-label') === '닫기'); if (!cl) return 'no close';
  cl.click(); await ms(80);
  return (q('.sv-actual-line') || {}).textContent || document.title;
})()`;
const v0Step = `(async () => {
  const q = (s) => document.querySelector(s); const mt = () => new Promise((r) => queueMicrotask(r));
  const row = q('.sv-pitch-row[aria-pressed="true"]'); if (!row) return 'no pressed row';
  row.click(); await mt(); await mt(); await mt();
  const nx = q('button[aria-label="다음 공"]'); if (!nx) return 'no next'; nx.click(); await mt(); await mt(); await mt();
  const cl = [...document.querySelectorAll('button')].find((b) => b.textContent.trim() === '닫기' || b.getAttribute('aria-label') === '닫기'); if (!cl) return 'no close (sheet?)';
  cl.click(); await mt(); await mt(); await mt();
  return (q('.sv-actual-line') || {}).textContent || 'ok';
})()`;
const v0Final = "JSON.stringify({ actual: (document.querySelector('.sv-actual-line')||{}).textContent, sheet: !!document.querySelector('button[aria-label=\"다음 공\"]') })";

const DEMO = "http://127.0.0.1:8790/relay/batter3d/assets/demo-test/";
const plans = {
  v0: { url: "http://127.0.0.1:8798/?game=849843", readyJs: v0Ready, prime: [{ js: v0Prime, waitMs: 900 }], stepJs: () => v0Step, finalJs: v0Final },
  v3s: { url: "http://127.0.0.1:8800/?game=849843", readyJs: "!!(window.PZSongSkin && window.PZSongSkin.status().attached && document.querySelector('.sv-atbat-toggle'))", prime: [{ js: v0Prime, waitMs: 1500 }], stepJs: () => v0Step, finalJs: "JSON.stringify(window.PZSongSkin.status())" },
  v1: { url: DEMO + "pitcheezy-relay-v1-demo.html", readyJs: relayReady, prime: [{ js: relayPrime(7), waitMs: 4200 }], stepJs: relayStep, finalJs: relayFinal },
  v2: { url: DEMO + "pitcheezy-relay-v2-demo.html", readyJs: relayReady, prime: [{ js: relayPrime(7), waitMs: 4200 }], stepJs: relayStep, finalJs: relayFinal },
  v2pz: { url: DEMO + "pitcheezy-relay-v2-demo.html?palette=pz", readyJs: relayReady, prime: [{ js: relayPrime(7), waitMs: 4200 }], stepJs: relayStep, finalJs: relayFinal },
};

const wanted = process.argv.slice(2).length ? process.argv.slice(2) : ["v0", "v1", "v2", "v2pz", "v3s"];
for (const name of wanted) {
  const p = plans[name]; if (!p) { console.error("unknown plan", name); continue; }
  const plan = {
    name, url: p.url, width: 375, height: 812, dpr: 2, quality: 85,
    readyJs: p.readyJs, prime: p.prime, recordMs: RECORD_MS,
    actions: STEPS.map((i, n) => ({ at: STEP_AT[n], label: "step" + i, js: p.stepJs(i) })),
    finalJs: p.finalJs, outDir: path.join(here, "frames", name), port: 9333,
  };
  const file = path.join(here, `plan-${name}.json`);
  writeFileSync(file, JSON.stringify(plan, null, 1));
  console.error(`=== ${name}`);
  const r = spawnSync(process.execPath, [path.join(here, "capture-cdp.mjs"), file], { stdio: "inherit" });
  if (r.status !== 0) console.error(`!!! ${name} exited ${r.status}`);
}

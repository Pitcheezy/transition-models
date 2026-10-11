"use strict";

// Generated colors and invented clocks only. No private video, saved runs, models or labels.
const assert = require("node:assert/strict");
const { before, after, test: nodeTest } = require("node:test");
const { spawn } = require("node:child_process");
const { once } = require("node:events");
const { createHash } = require("node:crypto");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const playwright = require("playwright");
const test = (name, fn) => nodeTest(name, { timeout: 30000 }, fn);
const ROOT = path.resolve(__dirname, "../..");
const TEMP_PREFIX = "pitcheezy-observation-browser-";
const PYTHON = process.env.PYTHON_BIN || (process.platform === "win32" ? "python" : "python3");
const ENGINE = process.env.BROWSER_ENGINE || "chromium";
const WAIT = 10000, LOW = 2, HIGH = 6;
const SEEK_TOLERANCE = 1 / 15 + .025; // one generated fixture frame plus media-clock settlement
let directory, browser, server, origin, serverOutput = "";
const digest = bytes => createHash("sha256").update(bytes).digest("hex");

async function buildSyntheticPack() {
  const fixtures = path.join(__dirname, "fixtures");
  const media = await fs.readFile(path.join(fixtures, "observation-colors-8s.mp4"));
  const data = {
    schema: "intent_observation_playback_v1",
    media: { path: "media/clip.mp4", sha256: digest(media), source_offset_seconds_exact: "100", clip_end_seconds_exact: "8" },
    scope: { game_pk: 900123, pa: 1, start_source_seconds_exact: "102", end_source_seconds_exact: "106", full_pa_verified: false, live_availability_verified: false, human_label: false },
    observations: [
      { index: 0, cutoff_seconds_exact: "512/5", frame_seconds_exact: "511/5", publication_seconds_exact: "103", status: "accepted", observation_status: "unknown", candidate_status: "candidate", reference_pitch_id: "900123:1:1", image_path: "frames/000.jpg" },
      { index: 1, cutoff_seconds_exact: "522/5", frame_seconds_exact: "521/5", publication_seconds_exact: "105", status: "accepted", observation_status: "unavailable", candidate_status: "no_candidate", reference_pitch_id: "900123:1:2", image_path: "frames/001.jpg" },
      { index: 2, cutoff_seconds_exact: "529/5", frame_seconds_exact: null, publication_seconds_exact: null, status: "error", observation_status: "unavailable", candidate_status: "error", reference_pitch_id: null, image_path: null },
    ],
    references: [
      { pitch_id: "900123:1:1", decision_seconds_exact: "102", decision_upper_seconds_exact: "1021/10", release_lower_seconds_exact: "104", release_upper_seconds_exact: "1041/10", conservative_temporal_ready: true, nominal_start_temporal_ready: true, usable_mitt: false },
      { pitch_id: "900123:1:2", decision_seconds_exact: "104", decision_upper_seconds_exact: "1041/10", release_lower_seconds_exact: "106", release_upper_seconds_exact: "1061/10", conservative_temporal_ready: true, nominal_start_temporal_ready: true, usable_mitt: false },
    ],
    summary: { planned_observations: 3, interval_observations: 3, outside_interval_observations: 0, accepted: 2, errors: 1, not_attempted: 0, verified_mitt: 0, conservative_ready_pitches: 2 },
  };
  const assets = new Map([
    ["media/clip.mp4", media],
    ["frames/000.jpg", await fs.readFile(path.join(fixtures, "observation-red.jpg"))],
    ["frames/001.jpg", await fs.readFile(path.join(fixtures, "observation-blue.jpg"))],
    ["replay-data.json", Buffer.from(JSON.stringify(data))],
    ["PRIVATE.txt", Buffer.from("SYNTHETIC BROWSER TEST: generated colors; invented observations; no baseball evidence.\n")],
  ]);
  for (const name of ["index.html", "playback.js", "style.css"])
    assets.set(name, await fs.readFile(path.join(ROOT, "web/observation-playback", name)));
  const artifacts = {};
  for (const [name, bytes] of assets) {
    const file = path.join(directory, name);
    await fs.mkdir(path.dirname(file), { recursive: true });
    await fs.writeFile(file, bytes);
    artifacts[name] = { sha256: digest(bytes), bytes: bytes.length };
  }
  // Synthetic bindings exercise the package schema, not provenance of a real saved run.
  const input_evidence_sha256 = Object.fromEntries([
    "saved_run_inventory", "capture_receipt_sha256", "source_framemd5_sha256", "clip_framemd5_sha256",
    "clip_media_sha256", "timing", "manifest", "sources", "deadline_report",
  ].map(key => [key, digest(Buffer.from(`synthetic:${key}`))]));
  await fs.writeFile(path.join(directory, "manifest.json"), JSON.stringify({
    schema: "intent_observation_playback_package_v1", private: true,
    input_files_unchanged: true, input_evidence_sha256, artifacts,
  }));
}

async function stopServer() {
  if (!server || server.exitCode !== null || server.signalCode !== null) return;
  const stopped = once(server, "exit");
  server.stdin.end("stop\n");
  let timer;
  await Promise.race([stopped, new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error("Observation server did not exit")), 5000);
  })]).finally(() => clearTimeout(timer));
}
async function removeOwnTemp() {
  if (!directory) return;
  const actual = await fs.realpath(directory), tempRoot = await fs.realpath(os.tmpdir());
  assert.equal(path.dirname(actual), tempRoot, "Refuse cleanup outside OS temp directory");
  assert.ok(path.basename(actual).startsWith(TEMP_PREFIX), "Refuse unrelated cleanup");
  await fs.rm(actual, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 });
}

before(async () => {
  assert.ok(["chromium", "webkit"].includes(ENGINE));
  assert.ok(!process.env.BROWSER_EXECUTABLE || ENGINE === "chromium");
  directory = await fs.mkdtemp(path.join(os.tmpdir(), TEMP_PREFIX));
  await buildSyntheticPack();
  // Gracefully stop the real Python process, including Windows venv redirectors.
  const bootstrap = [
    "import _thread, runpy, sys, threading",
    "def stop():", "    sys.stdin.readline()", "    _thread.interrupt_main()",
    "threading.Thread(target=stop, daemon=True).start()",
    "sys.argv = ['intent.observation_playback_server', *sys.argv[1:]]",
    "runpy.run_module('intent.observation_playback_server', run_name='__main__')",
  ].join("\n");
  server = spawn(PYTHON, ["-B", "-S", "-X", "utf8", "-u", "-c", bootstrap,
    "--directory", directory, "--port", "0"], {
    cwd: ROOT, env: { ...process.env, PYTHONUTF8: "1" }, windowsHide: true,
    stdio: ["pipe", "pipe", "pipe"],
  });
  server.stderr.setEncoding("utf8"); server.stderr.on("data", chunk => { serverOutput += chunk; });
  server.stdout.setEncoding("utf8");
  origin = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error(`Server start timed out: ${serverOutput}`)), WAIT);
    const failed = error => { clearTimeout(timer); reject(error); };
    server.once("error", failed);
    server.once("exit", code => failed(new Error(`Server exited before ready: ${code} ${serverOutput}`)));
    server.stdout.on("data", chunk => {
      serverOutput += chunk;
      const match = serverOutput.match(/http:\/\/127\.0\.0\.1:\d+\//);
      if (match) { clearTimeout(timer); resolve(match[0]); }
    });
  });
  browser = await playwright[ENGINE].launch({ headless: true,
    ...(process.env.BROWSER_EXECUTABLE ? { executablePath: process.env.BROWSER_EXECUTABLE } : {}) });
  console.log(`Synthetic observation replay: ${ENGINE} ${browser.version()}`);
}, { timeout: 60000 });
after(async () => {
  try { if (browser) await browser.close(); }
  finally { try { await stopServer(); } finally { await removeOwnTemp(); } }
});

async function withPage(t, viewport = { width: 1280, height: 900 }) {
  const context = await browser.newContext({ viewport });
  const unexpected = [], errors = [];
  await context.route("**/*", async route => {
    const request = route.request(), url = new URL(request.url());
    if (url.origin !== new URL(origin).origin || !["GET", "HEAD"].includes(request.method())) {
      unexpected.push(`${request.method()} ${url.origin}${url.pathname}`);
      return route.abort();
    }
    return route.continue();
  });
  const page = await context.newPage(); page.setDefaultTimeout(WAIT);
  page.on("pageerror", error => errors.push(error.message));
  page.on("request", request => {
    const url = new URL(request.url());
    if (url.origin !== new URL(origin).origin || !["GET", "HEAD"].includes(request.method()))
      unexpected.push(`${request.method()} ${url.origin}${url.pathname}`);
  });
  t.after(async () => {
    await context.close();
    assert.deepEqual(unexpected, [], "Never send external requests or uploads");
    assert.deepEqual(errors, [], "No unhandled browser errors");
  });
  return page;
}
async function open(page) {
  await page.goto(origin, { waitUntil: "domcontentloaded" });
  try {
    await page.waitForFunction(({ low, tolerance }) => {
      const v = document.getElementById("video");
      return v.readyState >= 2 && !v.seeking && Math.abs(v.currentTime - low) < tolerance;
    }, { low: LOW, tolerance: SEEK_TOLERANCE });
  } catch (error) {
    const media = await page.locator("#video").evaluate(v => ({ time: v.currentTime,
      seeking: v.seeking, ready: v.readyState, network: v.networkState,
      error: v.error && { code: v.error.code, message: v.error.message } }));
    throw new Error(`Initial scope seek failed: ${JSON.stringify(media)}`, { cause: error });
  }
  assert.equal(await page.locator("#error").isVisible(), false);
}
async function seek(page, seconds) {
  await page.locator("#video").evaluate((v, time) => { v.pause(); v.currentTime = time; }, seconds);
  await page.waitForFunction(({ time, tolerance }) => {
    const v = document.getElementById("video");
    return !v.seeking && Math.abs(v.currentTime - time) < tolerance;
  }, { time: seconds, tolerance: SEEK_TOLERANCE });
}
async function frame(page, relative) {
  await page.waitForFunction(expected => {
    const img = document.getElementById("frame");
    return !img.hidden && img.getAttribute("src") === expected && img.complete && img.naturalWidth === 64;
  }, relative);
}

test("native media play at the scope end restarts and advances inside the interval", async t => {
  const page = await withPage(t); await open(page); await seek(page, HIGH);
  // Native controls, keyboard/media actions and play() all enter the media play event.
  await page.locator("#video").evaluate(v => v.play());
  await page.waitForFunction(low => {
    const v = document.getElementById("video");
    return !v.paused && v.currentTime > low + .15 && v.currentTime < low + 1.5;
  }, LOW, { timeout: 2500 });
  assert.equal(await page.locator("#frame").isHidden(), true);
});

test("real media plays and the immutable server supports bounded Range seeks", async t => {
  const page = await withPage(t); await open(page);
  const response = await page.request.get(`${origin}media/clip.mp4`, { headers: { Range: "bytes=0-15" } });
  assert.equal(response.status(), 206);
  assert.equal((await response.body()).length, 16);
  assert.match(response.headers()["content-range"], /^bytes 0-15\/\d+$/);
  await page.locator("#toggle").click();
  await page.waitForFunction(() => document.getElementById("video").currentTime > 2.3);
  await page.locator("#toggle").click();
  assert.equal(await page.locator("#video").evaluate(v => v.paused), true);
  await seek(page, 4.5);
  assert.match(await page.locator("#active").textContent(), /900123:1:2/);
});

test("publication exposes its own frame and reverse seeking hides future observations", async t => {
  const page = await withPage(t); await open(page); await seek(page, 2.8);
  assert.equal(await page.locator("#frame").isHidden(), true);
  assert.match(await page.locator("#rows tr").nth(0).textContent(), /발행 전/);
  await seek(page, 3.1); await frame(page, "frames/000.jpg");
  assert.match(await page.locator("#observation").textContent(), /관측 #1/);
  await seek(page, 2.8);
  assert.equal(await page.locator("#frame").isHidden(), true);
  assert.equal(await page.locator("#frame").getAttribute("src"), null);
  assert.match(await page.locator("#observation").textContent(), /아직/);
});

test("changing observations hides the old bitmap while its replacement is loading", async t => {
  const page = await withPage(t); await open(page); await seek(page, 3.1); await frame(page, "frames/000.jpg");
  let release, received;
  const held = new Promise(resolve => { release = resolve; });
  const seen = new Promise(resolve => { received = resolve; });
  await page.route("**/frames/001.jpg", async route => { received(); await held; await route.continue(); });
  try {
    await seek(page, 5.1); await seen;
    assert.equal(await page.locator("#frame").isHidden(), true);
    assert.match(await page.locator("#observation").textContent(), /관측 #2/);
    release(); await frame(page, "frames/001.jpg");
  } finally { release(); }
});

test("scope-end playback stops and custom replay clears future output", async t => {
  const page = await withPage(t); await open(page); await seek(page, 5.8);
  await page.locator("#toggle").click();
  await page.waitForFunction(({ high, tolerance }) => {
    const v = document.getElementById("video"); return v.paused && !v.seeking && Math.abs(v.currentTime - high) < tolerance;
  }, { high: HIGH, tolerance: SEEK_TOLERANCE });
  await page.locator("#toggle").click();
  await page.waitForFunction(() => { const v = document.getElementById("video"); return !v.paused && v.currentTime < 2.8; });
  assert.equal(await page.locator("#frame").isHidden(), true);
  await page.locator("#toggle").click();
  await page.getByRole("button", { name: "2구 판단 참조", exact: true }).click();
  await page.waitForFunction(tolerance => Math.abs(document.getElementById("video").currentTime - 4) < tolerance, SEEK_TOLERANCE);
  await page.locator("#restart").click();
  await page.waitForFunction(tolerance => Math.abs(document.getElementById("video").currentTime - 2) < tolerance, SEEK_TOLERANCE);
});

for (const [name, pattern, message, needsSeek] of [
  ["missing replay data", "**/replay-data.json", /기록 파일/, false],
  ["missing historical input frame", "**/frames/000.jpg", /입력 프레임을 읽을 수 없습니다/, true],
]) test(`${name} fails visibly and stops the player`, async t => {
  const page = await withPage(t);
  await page.route(pattern, route => route.fulfill({ status: 404, contentType: "text/plain", body: "Synthetic missing fixture" }));
  if (needsSeek) { await open(page); await seek(page, 3.1); }
  else await page.goto(origin, { waitUntil: "domcontentloaded" });
  await page.locator("#error").waitFor({ state: "visible" });
  assert.match(await page.locator("#error").textContent(), message);
  assert.equal(await page.locator("#app").isVisible(), false);
  assert.equal(await page.locator("#video").evaluate(v => v.paused), true);
});

test("missing video fails visibly through an actual server 404", async t => {
  const page = await withPage(t); await open(page);
  // Windows WebKit media loading bypasses Playwright route interception. Use an
  // actual missing loopback resource; never synthesize an error event or read private media.
  await page.locator("#video").evaluate(v => { v.src = "media/synthetic-missing.mp4"; v.load(); });
  await page.locator("#error").waitFor({ state: "visible" });
  assert.match(await page.locator("#error").textContent(), /영상을 읽을 수 없습니다/);
  assert.equal(await page.locator("#app").isVisible(), false);
  assert.equal(await page.locator("#video").evaluate(v => v.paused), true);
});

test("320px layout keeps the page bounded and retains uncertainty and error counts", async t => {
  const page = await withPage(t, { width: 320, height: 740 }); await open(page);
  assert.equal(await page.evaluate(() => document.documentElement.scrollWidth <= innerWidth), true);
  assert.equal(await page.locator("#rows tr").count(), 3);
  assert.match(await page.locator("#summary").textContent(), /0확정 미트/);
  await seek(page, 5.9); await frame(page, "frames/001.jpg");
  assert.match(await page.locator("#rows tr").nth(2).textContent(), /저장 실행: 실행 오류/);
  assert.match(await page.locator("footer").textContent(), /검증한 결과가 아닙니다/);
});

"use strict";

// Every pitch and uploaded report in this suite is invented. No private artifact is read.
const assert = require("node:assert/strict");
const { before, after, test: nodeTest } = require("node:test");
const test = (name, fn) => nodeTest(name, { timeout: 30000 }, fn);
const { execFileSync, spawn } = require("node:child_process");
const { once } = require("node:events");
const fs = require("node:fs/promises");
const os = require("node:os");
const path = require("node:path");
const playwright = require("playwright");

const ROOT = path.resolve(__dirname, "../..");
const TEMP_PREFIX = "pitcheezy-browser-";
const PYTHON = process.env.PYTHON_BIN || (process.platform === "win32" ? "python" : "python3");
const ENGINE = process.env.BROWSER_ENGINE || "chromium";
const WAIT = 10000;
let directory, browser, server, origin, report, serverOutput = "";
const copy = value => JSON.parse(JSON.stringify(value));

function runPython(args) {
  return execFileSync(PYTHON, ["-B", ...args], {
    cwd: ROOT, env: { ...process.env, PYTHONUTF8: "1" }, encoding: "utf8", timeout: 30000, windowsHide: true,
  });
}

async function stopServer() {
  if (!server || server.exitCode !== null || server.signalCode !== null) return;
  const stopped = once(server, "exit");
  server.stdin.end("stop\n");
  let timer;
  await Promise.race([stopped, new Promise((_, reject) => {
    timer = setTimeout(() => reject(new Error("Test server did not exit")), 5000);
  })]).finally(() => clearTimeout(timer));
}

async function removeOwnTemp() {
  if (!directory) return;
  const actual = await fs.realpath(directory);
  const tempRoot = await fs.realpath(os.tmpdir());
  assert.equal(path.dirname(actual), tempRoot, "Refuse cleanup outside the OS temp directory");
  assert.ok(path.basename(actual).startsWith(TEMP_PREFIX), "Refuse cleanup of an unrelated folder");
  assert.equal(actual, await fs.realpath(directory));
  await fs.rm(actual, { recursive: true, force: true, maxRetries: 5, retryDelay: 100 });
}

before(async () => {
  assert.ok(["chromium", "webkit"].includes(ENGINE), "BROWSER_ENGINE must be chromium or webkit");
  assert.ok(!process.env.BROWSER_EXECUTABLE || ENGINE === "chromium",
    "BROWSER_EXECUTABLE is supported only for chromium");
  directory = await fs.mkdtemp(path.join(os.tmpdir(), TEMP_PREFIX));
  const source = JSON.parse(await fs.readFile(path.join(ROOT,
    "docs/examples/service_game_v2_export_synthetic.json"), "utf8"));
  const ready = source.pitches.find(pitch => pitch.rec.status === "ready");
  const second = copy(ready);
  second.index += 1;
  second.pitch_number = 2;
  second.key = `${second.pa_key}:2`;
  second.situation_before.balls = 1;
  second.actual.description = "Synthetic second-pitch observation";
  source.pitches.push(second);
  const input = path.join(directory, "synthetic-input.json");
  const pack = path.join(directory, "review");
  await fs.writeFile(input, JSON.stringify(source));
  runPython(["scripts/build_service_review.py", "--input", input, "--source-kind", "synthetic",
    "--out-dir", pack]);
  report = JSON.parse(await fs.readFile(path.join(pack, "review-data.json"), "utf8"));
  assert.equal(report.source.input_kind, "synthetic");
  assert.equal(report.pitches[0].pitch_number, 1);
  assert.equal(report.pitches[1].pitch_number, 2);
  // Windows venv Python may be a redirector: terminate the actual runtime through
  // stdin + KeyboardInterrupt instead of killing its parent and orphaning the server.
  const bootstrap = [
    "import _thread, runpy, sys, threading",
    "def stop():",
    "    sys.stdin.readline()",
    "    _thread.interrupt_main()",
    "threading.Thread(target=stop, daemon=True).start()",
    "sys.argv = sys.argv[1:]",
    "runpy.run_path(sys.argv[0], run_name='__main__')",
  ].join("\n");
  server = spawn(PYTHON, ["-I", "-S", "-B", "-X", "utf8", "-u", "-c", bootstrap,
    path.join(pack, "launch_review.py"), "--port", "0"], {
    cwd: ROOT, env: { ...process.env, PYTHONUTF8: "1" }, windowsHide: true,
    stdio: ["pipe", "pipe", "pipe"],
  });
  server.stderr.setEncoding("utf8");
  server.stderr.on("data", chunk => { serverOutput += chunk; });
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
  console.log(`Synthetic browser regression: ${ENGINE} ${browser.version()}`);
}, { timeout: 60000 });

after(async () => {
  try { if (browser) await browser.close(); }
  finally { try { await stopServer(); } finally { await removeOwnTemp(); } }
});

async function withPage(t, options = {}) {
  const context = await browser.newContext({ viewport: options.viewport || { width: 1280, height: 900 } });
  const unexpected = [], pageErrors = [];
  await context.route("**/*", async route => {
    const request = route.request();
    const url = new URL(request.url());
    if (url.origin !== new URL(origin).origin || !["GET", "HEAD"].includes(request.method())) {
      unexpected.push(`${request.method()} ${url.origin}${url.pathname}`);
      return route.abort();
    }
    return route.continue();
  });
  const page = await context.newPage();
  page.setDefaultTimeout(WAIT);
  page.on("pageerror", error => pageErrors.push(error.message));
  page.on("request", request => {
    const url = new URL(request.url());
    if (url.origin !== new URL(origin).origin || !["GET", "HEAD"].includes(request.method()))
      unexpected.push(`${request.method()} ${url.origin}${url.pathname}`);
  });
  t.after(async () => {
    await context.close();
    assert.deepEqual(unexpected, [], "Browser must never send non-loopback requests or uploads");
    assert.deepEqual(pageErrors, [], "No unhandled browser errors");
  });
  return page;
}

async function loaded(page) {
  await page.locator("#report-content").waitFor({ state: "visible" });
  await page.waitForFunction(() => !document.getElementById("load-status").classList.contains("error"));
}
async function open(page) {
  await page.goto(origin, { waitUntil: "domcontentloaded" });
  await loaded(page);
}
async function upload(page, value, name = "synthetic-report.json") {
  await page.locator("#report-file").setInputFiles({ name, mimeType: "application/json",
    buffer: Buffer.isBuffer(value) ? value : Buffer.from(JSON.stringify(value)) });
}
async function hiddenResult(page) {
  assert.equal(await page.locator("#actual-content").textContent(), "");
  assert.equal(await page.locator("#setup-rail").textContent(), "");
  assert.equal(await page.locator("#reveal-button").isDisabled(), false);
}
async function focused(page) {
  return page.evaluate(() => ({ id: document.activeElement.id,
    text: document.activeElement.textContent.trim().slice(0, 100), pressed: document.activeElement.getAttribute("aria-pressed") }));
}

function alternateReport() {
  const other = copy(report), game = 900002;
  other.game.game_pk = game;
  other.game.home_team = "Synthetic Replacement Home";
  other.source.sha256 = "b".repeat(64);
  if (other.cutoff && other.cutoff.pitch_key)
    other.cutoff.pitch_key = other.cutoff.pitch_key.replace(/^\d+:/, `${game}:`);
  for (const pitch of other.pitches) {
    pitch.pa_key = `${game}:${pitch.at_bat_number}`;
    pitch.key = `${pitch.pa_key}:${pitch.pitch_number}`;
  }
  return other;
}

test("initial result is hidden; reveal, pitch and PA selection reset correctly", async t => {
  const page = await withPage(t);
  await open(page);
  await hiddenResult(page);
  assert.match(await page.locator("#source-badges").textContent(), /합성 자료/);
  await page.locator("#reveal-button").click();
  assert.match(await page.locator("#actual-content").textContent(), /Synthetic ball/);
  assert.match(await page.locator("#setup-rail").textContent(), /미검토/);
  await page.getByRole("button", { name: "2구", exact: true }).click();
  await hiddenResult(page);
  await page.locator("#reveal-button").click();
  await page.locator("#pa-select").selectOption("900001:3");
  await hiddenResult(page);
  assert.match(await page.locator("#candidate-list").textContent(), /지원되지 않습니다/);
  await page.locator("#pa-select").selectOption("900001:4");
  assert.match(await page.locator("#candidate-list").textContent(), /제공되지 않았습니다/);
  assert.equal(await page.locator("video").count(), 0);
});

const invalidInputs = [
  ["invalid JSON", () => Buffer.from("{invalid")],
  ["file above 5 MiB", () => Buffer.alloc(5 * 1024 * 1024 + 1, 32)],
  ["pitch identity mismatch", () => { const value = copy(report); value.pitches[0].key = "900001:2:99"; return value; }],
  ["unsupported position units", () => { const value = copy(report); value.units.actual_x_z = "meters"; return value; }],
  ["selection shares above 100 percent", () => { const value = copy(report); const c = value.pitches[0].pre.recommendation.candidates; c[0].selection_probability = .8; c[1].selection_probability = .8; return value; }],
  ["duplicate pitch type", () => { const value = copy(report); const c = value.pitches[0].pre.recommendation.candidates; c[1].pitch_type = c[0].pitch_type; return value; }],
];
for (const [name, value] of invalidInputs) test(`${name} is rejected and a valid file recovers`, async t => {
  const page = await withPage(t);
  await open(page);
  await page.locator("#reveal-button").click();
  await upload(page, value(), "invalid.json");
  await page.locator("#load-status.error").waitFor();
  assert.equal(await page.locator("#report-content").isVisible(), false);
  assert.equal(await page.locator("#actual-content").textContent(), "");
  assert.equal(await page.locator("#setup-rail").textContent(), "");
  await upload(page, report);
  await loaded(page);
  await hiddenResult(page);
  assert.match(await page.locator("#game-meta").textContent(), /900001/);
});

test("replacing an already revealed report shows only the new game and hides its result", async t => {
  const page = await withPage(t);
  await open(page);
  await page.locator("#reveal-button").click();
  await upload(page, alternateReport());
  await loaded(page);
  assert.match(await page.locator("#game-meta").textContent(), /900002/);
  assert.match(await page.locator("#game-title").textContent(), /Synthetic Replacement Home/);
  await hiddenResult(page);
});

test("late default fetch cannot overwrite the report explicitly chosen by the user", async t => {
  const page = await withPage(t);
  let release;
  const held = new Promise(resolve => { release = resolve; });
  let intercepted;
  const seen = new Promise(resolve => { intercepted = resolve; });
  await page.route("**/review-data.json", async route => {
    intercepted();
    await held;
    await route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(report) });
  });
  try {
    await page.goto(origin, { waitUntil: "domcontentloaded" });
    await seen;
    await upload(page, alternateReport());
    await loaded(page);
    assert.match(await page.locator("#game-meta").textContent(), /900002/);
    const response = page.waitForResponse(url => url.url().endsWith("/review-data.json"));
    release();
    await (await response).finished();
    // Wait through two render opportunities after response completion.
    await page.evaluate(() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve))));
    assert.match(await page.locator("#game-meta").textContent(), /900002/);
    await hiddenResult(page);
  } finally { release(); }
});

for (const key of ["Enter", "Space"]) test(`${key} selects pitch 2 and retains the same logical button focus`, async t => {
  const page = await withPage(t);
  await open(page);
  const second = page.getByRole("button", { name: "2구", exact: true });
  await second.focus();
  await second.press(key);
  assert.match(await page.locator("#pitch-heading").textContent(), /2번째/);
  assert.deepEqual(await focused(page), { id: "", text: "2구", pressed: "true" });
  await hiddenResult(page);
  // A render caused by result reveal must retain the currently focused pitch button.
  await page.locator("#reveal-button").evaluate(button => button.click());
  assert.deepEqual(await focused(page), { id: "", text: "2구", pressed: "true" });
});

test("a render does not steal focus from an element outside pitch controls", async t => {
  const page = await withPage(t);
  await open(page);
  await page.locator(".brand").focus();
  await page.locator("#reveal-button").evaluate(button => button.click());
  assert.equal(await page.locator(".brand").evaluate(element => element === document.activeElement), true);
  await page.locator("#pa-select").focus();
  await page.locator("#pa-select").selectOption("900001:3");
  assert.equal((await focused(page)).id, "pa-select");
});

test("320px viewport has no horizontal document overflow before or after reveal", async t => {
  const page = await withPage(t, { viewport: { width: 320, height: 800 } });
  await open(page);
  for (const stage of ["before reveal", "after reveal"]) {
    if (stage === "after reveal") await page.locator("#reveal-button").click();
    const widths = await page.evaluate(() => ({ viewport: document.documentElement.clientWidth,
      document: document.documentElement.scrollWidth, body: document.body.scrollWidth }));
    assert.ok(widths.document <= widths.viewport && widths.body <= widths.viewport,
      `${stage}: horizontal overflow ${JSON.stringify(widths)}`);
  }
});

function syntheticEvidence() {
  const pitches = report.pitches.slice(0, 2);
  const clips = pitches.map((pitch, index) => ({
    pitch_key: pitch.key, play_id: "00000000-0000-0000-0000-00000000000" + (index + 1),
    video: "media/synthetic-" + (index + 1) + ".mp4", poster: "media/synthetic-" + (index + 1) + ".jpg",
    video_sha256: String(index + 1).repeat(64), poster_sha256: "c".repeat(64), duration_seconds: 5
  }));
  return {
    media: { schema: "pitcheezy-service-review-media-v1", game_pk: report.game.game_pk,
      source_sha256: report.source.sha256, clips },
    evidence: { schema: "pitcheezy-service-review-evidence-v1", game_pk: report.game.game_pk,
      source_sha256: report.source.sha256, entries: clips.map((clip, index) => ({
        pitch_key: clip.pitch_key, play_id: clip.play_id, clip_sha256: clip.video_sha256,
        image: "evidence/synthetic-" + (index + 1) + ".png", image_sha256: "e".repeat(64),
        frame_pts: 138000, clip_first_pts: 3000, release_lower_bound_pts: 228000,
        time_base: "1/90000", clip_seconds: 1.5, status: index ? "abstained" : "candidate",
        reason: index ? "Synthetic occlusion; no accepted point." : "Synthetic candidate; no confirmed point."
      })) }
  };
}

async function evidencePage(t, mutate, brokenImage = false) {
  const page = await withPage(t), data = syntheticEvidence(), requests = [];
  if (mutate) mutate(data.evidence);
  await page.route("**/review-media.json", route =>
    route.fulfill({ json: data.media }));
  await page.route("**/review-evidence.json", route =>
    route.fulfill({ json: data.evidence }));
  await page.route("**/media/synthetic-*", route =>
    route.fulfill({ status: 404, body: "Synthetic test: playback is not under test." }));
  await page.route("**/evidence/*.png", route => {
    requests.push(new URL(route.request().url()).pathname);
    return brokenImage ? route.fulfill({ status: 404, body: "Synthetic missing image." }) :
      route.fulfill({ contentType: "image/png", body: Buffer.from(
        "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mP8/x8AAwMCAO+j5RkAAAAASUVORK5CYII=", "base64") });
  });
  await page.goto(origin, { waitUntil: "networkidle" });
  await loaded(page);
  return { page, requests };
}

async function evidenceHidden(page) {
  assert.equal(await page.locator("#evidence-panel").isVisible(), false);
  assert.equal(await page.locator("#evidence-content").textContent(), "");
  assert.equal(await page.locator("#evidence-content img").count(), 0);
}

async function evidenceImageLoaded(page) {
  await page.waitForFunction(() => {
    const image = document.querySelector("#evidence-content img");
    return image && image.complete && image.naturalWidth > 0;
  });
}

test("optional synthetic evidence reveals after results; next pitch, stale image errors and PA changes stay isolated", async t => {
  const { page, requests } = await evidencePage(t);
  await evidenceHidden(page);
  assert.deepEqual(requests, []);
  await page.locator("#reveal-button").click();
  await evidenceImageLoaded(page);
  assert.match(await page.locator("#evidence-content").textContent(), /Synthetic candidate/);
  const oldImage = await page.locator("#evidence-content img").elementHandle();
  await page.locator("#next-pitch").click();
  await evidenceHidden(page);
  await hiddenResult(page);
  await page.locator("#reveal-button").click();
  await evidenceImageLoaded(page);
  assert.match(await page.locator("#evidence-content").textContent(), /Synthetic occlusion/);
  await oldImage.evaluate(image => image.dispatchEvent(new Event("error")));
  assert.match(await page.locator("#evidence-content").textContent(), /Synthetic occlusion/);
  assert.equal(await page.locator("#evidence-content img").getAttribute("src"), "evidence/synthetic-2.png");
  const anotherPA = report.pitches.find(pitch => pitch.pa_key !== report.pitches[0].pa_key).pa_key;
  await page.locator("#pa-select").selectOption(anotherPA);
  await evidenceHidden(page);
  await page.locator("#reveal-button").click();
  assert.equal(await page.locator("#evidence-content img").count(), 0);
});

test("invalid synthetic sidecars fail closed without blocking report reveal", async t => {
  for (const mutate of [
    evidence => { evidence.entries[0].frame_pts = evidence.entries[0].release_lower_bound_pts; evidence.entries[0].clip_seconds = 2.5; },
    evidence => { evidence.entries[0].image = "evidence/../unexpected.png"; },
    evidence => { evidence.source_sha256 = "f".repeat(64); }
  ]) {
    const { page, requests } = await evidencePage(t, mutate);
    await evidenceHidden(page);
    await page.locator("#reveal-button").click();
    assert.notEqual(await page.locator("#actual-content").textContent(), "");
    assert.equal(await page.locator("#evidence-content img").count(), 0);
    assert.deepEqual(requests, []);
  }
});

test("failed report replacement clears displayed synthetic evidence and valid recovery starts hidden", async t => {
  const { page } = await evidencePage(t);
  await page.locator("#reveal-button").click();
  await evidenceImageLoaded(page);
  await upload(page, Buffer.from("not-json"));
  await page.waitForFunction(() => document.getElementById("load-status").classList.contains("error"));
  await evidenceHidden(page);
  assert.equal(await page.locator("#actual-content").textContent(), "");
  await upload(page, report);
  await loaded(page);
  await evidenceHidden(page);
  await hiddenResult(page);
});

test("unreadable synthetic evidence image removes the image and keeps the result available", async t => {
  const { page } = await evidencePage(t, null, true);
  await page.locator("#reveal-button").click();
  await page.waitForFunction(() => document.getElementById("evidence-content").textContent.includes("읽지 못했습니다"));
  assert.equal(await page.locator("#evidence-content img").count(), 0);
  assert.notEqual(await page.locator("#actual-content").textContent(), "");
  assert.equal(await page.locator("#next-pitch").isDisabled(), false);
});

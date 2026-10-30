"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const { webcrypto } = require("node:crypto");
const site = path.join(__dirname, "../pitch-studio");
const html = fs.readFileSync(path.join(site, "watch.html"), "utf8");
const game = JSON.parse(fs.readFileSync(path.join(site, "game-849843.json")));

function element(tag = "div") {
  let ownText = "", value = "";
  const classes = new Set(), attributes = new Map(), listeners = new Map();
  const e = { tagName: tag.toUpperCase(), children: [], style: { setProperty(name, value) { this[name] = String(value); } }, hidden: false, disabled: false,
    complete: true, naturalWidth: 1280, checked: false, dataset: {},
    classList: { toggle(name, force) { const on = force ?? !classes.has(name); on ? classes.add(name) : classes.delete(name); return on; }, contains: name => classes.has(name) },
    append(child) { this.children.push(child); },
    replaceChildren(...items) { ownText = ""; this.children = items; },
    setAttribute(name, val) { attributes.set(name, String(val)); },
    getAttribute(name) { return attributes.get(name) ?? null; },
    removeAttribute(name) { attributes.delete(name); },
    addEventListener(name, fn) { if (!listeners.has(name)) listeners.set(name, []); listeners.get(name).push(fn); },
    emit(name) { for (const fn of [...(listeners.get(name) || [])]) fn({ target: e, type: name }); },
  };
  Object.defineProperties(e, {
    textContent: { get() { return ownText + this.children.map(c => c.textContent).join(""); }, set(text) { ownText = String(text); this.children = []; } },
    value: { get: () => value, set: v => { value = String(v); } },
    className: { get: () => [...classes].join(" "), set: v => { classes.clear(); for (const c of String(v).split(/\s+/)) if (c) classes.add(c); } },
  });
  return e;
}

async function settle(predicate = () => true) {
  for (let i = 0; i < 200; i++) {
    await new Promise(resolve => setImmediate(resolve));
    if (predicate()) { await new Promise(resolve => setImmediate(resolve)); return; }
  }
  throw new Error("Watch initialization did not settle");
}

async function setup({ search = "?game=849843", missing = [], corrupt = [], scope = "game", frameCallbacks = false,
  stalled = {}, raw = {}, waitForReady = true } = {}) {
  const elements = new Map();
  for (const match of html.matchAll(/<([a-z][a-z0-9-]*)\b([^>]*\bid="([^"]+)"[^>]*)>/gi)) {
    const e = element(match[1]); e.hidden = /\bhidden\b/.test(match[2]); e.disabled = /\bdisabled\b/.test(match[2]);
    e.checked = /\bchecked\b/.test(match[2]);
    elements.set(match[3], e);
  }
  const get = id => { const e = elements.get(id); if (!e) throw new Error(`Missing HTML element: ${id}`); return e; };
  get("watch-play-scope").value = scope;
  get("watch-rate").value = "1";
  for (const id of ["watch-filter-pitcher", "watch-filter-batter", "watch-filter-count"]) if (elements.has(id)) get(id).value = "all";
  const video = get("pitch-video");
  Object.assign(video, { paused: true, ended: false, currentTime: 0, duration: 7, error: null,
    muted: true, seeking: false, readyState: 4, playbackRate: 1,
    pause() { const wasPlaying = !this.paused; this.paused = true; if (wasPlaying) this.emit("pause"); },
    load() { this.currentTime = 0; this.ended = false; this.error = null; this.emit("emptied"); },
    play() { this.paused = false; this.ended = false; this.emit("play"); this.emit("playing"); return Promise.resolve(); },
  });
  const frames = new Map(), cancelledFrames = [];
  let frameId = 0;
  if (frameCallbacks) Object.assign(video, {
    requestVideoFrameCallback(fn) { const id = ++frameId; frames.set(id, fn); return id; },
    cancelVideoFrameCallback(id) { if (frames.has(id)) cancelledFrames.push(frames.get(id)); frames.delete(id); },
  });
  const document = Object.assign(element(), { hidden: false, getElementById: get,
    createElement: tag => element(tag), createElementNS: (_, tag) => element(tag) });
  const reloads = [], window = element(), location = { search, pathname: "/watch.html", reload: () => reloads.push(true) };
  const historyCalls = [];
  const history = Object.fromEntries(["pushState", "replaceState"].map(method => [method, (_, title, url) => {
    const next = new URL(url, "https://example.test"); location.search = next.search; location.pathname = next.pathname;
    historyCalls.push({ method, url });
  }]));
  const timers = new Map(), cancelledTimers = [], requests = [], signals = new Map(), held = new Map(), bodyFiles = new WeakMap();
  const hold = (file, value) => new Promise(resolve => held.set(file, () => resolve(value)));
  let timerId = 0;
  const context = vm.createContext({ document, location, history, console, AbortController, TextDecoder, URLSearchParams,
    crypto: { subtle: { digest: async (algorithm, bytes) => {
      const digest = await webcrypto.subtle.digest(algorithm, bytes), file = bodyFiles.get(bytes);
      return stalled[file] === "digest" ? hold(file, digest) : digest;
    } } },
    setTimeout: (fn, delay) => { const id = ++timerId; timers.set(id, { fn, delay }); return id; },
    clearTimeout: id => { if (timers.has(id)) cancelledTimers.push(timers.get(id)); timers.delete(id); },
    fetch: async (name, options) => {
      const file = String(name).split("?")[0]; requests.push(file);
      signals.set(file, options.signal);
      if (missing.includes(file) || !fs.existsSync(path.join(site, file))) return { ok: false };
      let bytes = raw[file] === undefined ? fs.readFileSync(path.join(site, file)) : Buffer.from(raw[file]);
      if (corrupt.includes(file)) bytes = Buffer.concat([bytes, Buffer.from(" ")]);
      const response = { ok: true, arrayBuffer: async () => {
        const body = bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength); bodyFiles.set(body, file);
        return stalled[file] === "body" ? hold(file, body) : body;
      } };
      return stalled[file] === "headers" ? hold(file, response) : response;
    },
  });
  context.window = context;
  context.addEventListener = window.addEventListener.bind(window);
  for (const file of ["receiver-fullgame.js", "receiver-game-media.js", "receiver-zones.js", "receiver-location.js", "receiver-media.js", "receiver-video.js", "receiver-sequence.js", "watch-timing.js", "watch-context.js", "watch.js"])
    vm.runInContext(fs.readFileSync(path.join(site, file), "utf8"), context, { filename: file });
  if (waitForReady) await settle(() => /저장 경기 262구|다시 시작해 주세요/.test(get("watch-load-status").textContent));
  else await settle();
  const click = async id => { assert.equal(get(id).disabled, false, `${id} must be enabled`); get(id).emit("click"); await settle(); };
  const select = async (id, value) => { assert.equal(get(id).disabled, false, `${id} must be enabled`); get(id).value = value; get(id).emit("change"); await settle(); };
  const end = async () => { video.currentTime = video.duration; video.ended = true; video.paused = true; video.emit("pause"); video.emit("ended"); await settle(); };
  const fireTimer = async () => { assert.equal(timers.size, 1); const [id, entry] = timers.entries().next().value; timers.delete(id); entry.fn(); await settle(); return entry; };
  const shapes = cls => get("watch-location").children.filter(c => c.getAttribute("class") === cls);
  const showFrame = async mediaTime => {
    assert.equal(frames.size, 1, "one presented-frame callback must be pending");
    const [id, fn] = frames.entries().next().value; frames.delete(id); fn(0, { mediaTime }); await settle();
  };
  const finishSeek = async () => { video.seeking = false; video.emit("seeked"); await settle(); };
  const check = async (id, value) => { assert.equal(get(id).disabled, false, `${id} must be enabled`); get(id).checked = value; get(id).emit("change"); await settle(); };
  const clickElement = async button => { assert(button); assert.equal(button.disabled, false); button.emit("click"); await settle(); };
  const expireRequests = async () => {
    const active = [...timers].filter(([, entry]) => entry.delay === 10000);
    assert(active.length > 0, "an asset deadline must be pending");
    for (const [id, entry] of active) { timers.delete(id); entry.fn(); }
    await settle(); return active.length;
  };
  const finishAsset = async file => { assert(held.has(file)); held.get(file)(); held.delete(file); await settle(); };
  return { get, video, document, window, location, requests, timers, cancelledTimers, historyCalls, click, select, end, fireTimer, shapes, frames, cancelledFrames, showFrame, finishSeek, check, clickElement, reloads, signals, held, expireRequests, finishAsset };
}

test("initial state joins the exact pitch, candidates and video but hides actual result and recorded zone", async () => {
  const s = await setup();
  assert.match(s.get("watch-identity").textContent, /849843:1:1/);
  assert.equal(s.get("watch-candidates").children.length, 3);
  assert.match(s.get("watch-back-analysis").href, /pitch=849843%3A1%3A1/);
  assert.match(s.video.getAttribute("src"), /1-1-official\.mp4$/);
  assert.equal(s.shapes("strike-zone").length, 0); assert.equal(s.shapes("location-actual").length, 0);
  assert.equal(s.shapes("reference-zone").length, 1);
  assert.match(s.get("watch-zone-note").textContent, /참고/);
  assert.equal(s.get("watch-result").classList.contains("is-revealed"), false);
  assert.equal(s.get("watch-start").disabled, false);
  assert.equal(s.get("watch-pa").disabled, false); assert.equal(s.get("watch-pitch").disabled, false);
});

test("video end reveals only the current pitch result and recorded geometry", async () => {
  const s = await setup(); await s.click("play-pitch-video");
  assert.equal(s.shapes("location-actual").length, 0);
  await s.end();
  const actual = game.pitches[0].post.actual;
  assert(s.get("watch-result").textContent.includes(actual.result_label));
  assert.equal(s.get("watch-result").hidden, false);
  assert.equal(s.get("watch-result").classList.contains("is-revealed"), true);
  assert.equal(s.shapes("strike-zone").length, 1); assert.equal(s.shapes("location-actual").length, 1);
  assert.equal(s.shapes("reference-zone").length, 0);
});

test("native seek after disclosure hides the actual and zone without rewinding the user's position", async () => {
  const s = await setup(); await s.click("play-pitch-video"); await s.end();
  s.video.currentTime = 2.5; s.video.ended = false; s.video.emit("seeking"); await settle();
  assert.equal(s.video.currentTime, 2.5);
  assert.equal(s.shapes("location-actual").length, 0); assert.equal(s.shapes("strike-zone").length, 0);
  assert.equal(s.get("watch-result").classList.contains("is-revealed"), false);
});

test("native replay after the result hides post-pitch data", async () => {
  const s = await setup(); await s.click("play-pitch-video"); await s.end();
  s.video.currentTime = 0; await s.video.play(); await settle();
  assert.equal(s.shapes("location-actual").length, 0); assert.equal(s.shapes("strike-zone").length, 0);
  assert.equal(s.get("watch-result").classList.contains("is-revealed"), false);
});

test("manual pitch selection resets results, video and analysis link; an old ended callback cannot reveal", async () => {
  const s = await setup(); await s.click("play-pitch-video"); await s.end();
  await s.select("watch-pitch", "849843:1:2");
  assert.match(s.video.getAttribute("src"), /1-2-official\.mp4$/); assert.equal(s.video.currentTime, 0);
  assert.match(s.get("watch-identity").textContent, /849843:1:2/);
  assert.match(s.get("watch-back-analysis").href, /pitch=849843%3A1%3A2/);
  s.video.ended = true; s.video.emit("ended");
  assert.equal(s.get("watch-result").classList.contains("is-revealed"), false);
  assert.equal(s.shapes("location-actual").length, 0);
});

test("excluded 69:2 has no playable clip and never fabricates actual data", async () => {
  const s = await setup({ search: "?game=849843&pitch=849843%3A69%3A2" });
  assert.equal(s.get("watch-start").disabled, true);
  assert.equal(s.video.getAttribute("src"), null);
  assert.match(s.get("pitch-video-missing").textContent, /구종 기록이 달라/);
  assert.equal(s.shapes("location-actual").length, 0);
});

for (const search of ["?game=849844", "?game=849843&pitch=849843%3A999%3A1", "?game=849843&game=849843"]) {
  test(`invalid route fails closed: ${search}`, async () => {
    const s = await setup({ search });
    assert.equal(s.get("watch-start").disabled, true); assert.equal(s.video.getAttribute("src"), null);
    assert.equal(s.get("watch-candidates").children.length, 0); assert.equal(s.get("watch-location").children.length, 0);
    assert.match(s.get("watch-phase").textContent, /실패/);
  });
}

for (const fault of ["missing", "corrupt"]) {
  test(`${fault} media manifest retains recommendation but disables playback`, async () => {
    const s = await setup({ [fault]: ["game-849843-media.json"] });
    assert.equal(s.get("watch-start").disabled, true); assert.equal(s.video.getAttribute("src"), null);
    assert.equal(s.get("watch-candidates").children.length, 3); assert.equal(s.shapes("location-actual").length, 0);
  });
}

test("missing recorded zone keeps only the labelled reference outline while result and video remain available", async () => {
  const s = await setup({ missing: ["game-849843-zones.json"] });
  await s.click("play-pitch-video"); await s.end();
  assert.equal(s.shapes("location-actual").length, 1); assert.equal(s.shapes("strike-zone").length, 0);
  assert.equal(s.shapes("reference-zone").length, 1);
  assert.match(s.get("watch-zone-note").textContent, /미연결/);
});

test("game playback crosses the PA boundary only after the result delay and hides old actual", async () => {
  const s = await setup({ search: "?game=849843&pitch=849843%3A1%3A3" });
  await s.click("watch-start"); await s.end();
  assert.match(s.get("watch-identity").textContent, /849843:1:3/);
  assert.equal(s.timers.values().next().value.delay, 5000);
  await s.fireTimer();
  assert.match(s.get("watch-identity").textContent, /849843:2:1/);
  assert.equal(s.video.paused, false); assert.equal(s.shapes("location-actual").length, 0);
  assert.equal(s.get("watch-result").classList.contains("is-revealed"), false);
});

test("PA-only mode stops at the final pitch", async () => {
  const s = await setup({ search: "?game=849843&pitch=849843%3A1%3A3", scope: "pa" });
  await s.click("watch-start"); await s.end();
  assert.equal(s.timers.size, 0); assert.equal(s.get("watch-stop").disabled, true);
  assert.match(s.get("watch-sequence-status").textContent, /현재 타석 관전을 마쳤/);
  assert.match(s.get("watch-identity").textContent, /849843:1:3/);
});

test("game continuation stops on excluded 69:2 instead of silently skipping", async () => {
  const s = await setup({ search: "?game=849843&pitch=849843%3A69%3A1" });
  await s.click("watch-start"); await s.end(); await s.fireTimer();
  assert.match(s.get("watch-identity").textContent, /849843:69:2/);
  assert.equal(s.get("watch-start").disabled, true); assert.equal(s.get("watch-stop").disabled, true);
  assert.equal(s.video.getAttribute("src"), null); assert.equal(s.timers.size, 0);
  assert.match(s.get("watch-sequence-status").textContent, /영상이 없는 투구/);
});

test("stop during result delay invalidates a stale timer even if it still fires", async () => {
  const s = await setup(); await s.click("watch-start"); await s.end();
  const stale = s.timers.values().next().value;
  await s.click("watch-stop"); assert.equal(s.timers.size, 0);
  stale.fn(); await settle();
  assert.match(s.get("watch-identity").textContent, /849843:1:1/);
  assert.equal(s.get("watch-stop").disabled, true);
});

test("history restoration switches the pitch and clears result state", async () => {
  const s = await setup(); await s.click("play-pitch-video"); await s.end();
  s.location.search = "?game=849843&pitch=849843%3A2%3A1"; s.window.emit("popstate"); await settle();
  assert.match(s.get("watch-identity").textContent, /849843:2:1/);
  assert.equal(s.shapes("location-actual").length, 0); assert.equal(s.video.paused, true);
});

test("video error and page hiding stop progression without revealing results", async () => {
  for (const cause of ["error", "hidden"]) {
    const s = await setup(); await s.click("watch-start");
    if (cause === "error") { s.video.error = { code: 4 }; s.video.emit("error"); }
    else { s.document.hidden = true; s.document.emit("visibilitychange"); }
    await settle();
    assert.equal(s.get("watch-stop").disabled, true); assert.equal(s.timers.size, 0);
    assert.equal(s.get("watch-result").classList.contains("is-revealed"), false);
  }
});

test("invalid history after a disclosed result clears every prior result and drawing", async () => {
  const s = await setup(); await s.click("play-pitch-video"); await s.end();
  s.location.search = "?game=849844"; s.window.emit("popstate"); await settle();
  assert.equal(s.get("watch-result").textContent, ""); assert.equal(s.get("watch-location").children.length, 0);
  assert.equal(s.video.getAttribute("src"), null); assert.equal(s.get("watch-start").disabled, true);
});

const firstTiming = () => JSON.parse(fs.readFileSync(path.join(site, "game-849843-timing.json"))).records.find(r => r.pitch_id === "849843:1:1");
const hiddenResult = s => {
  assert.equal(s.get("watch-result").classList.contains("is-revealed"), false);
  assert.equal(s.get("watch-result").textContent.includes(game.pitches[0].post.actual.result_label), false);
};

test("timeupdate fallback reveals location at the verified upper boundary, but result only at end", async () => {
  const s = await setup(), event = firstTiming();
  assert.equal(s.get("watch-event-marker").hidden, false);
  await s.click("watch-toggle");
  s.video.currentTime = event.upper_seconds - 0.001; s.video.emit("timeupdate");
  assert.equal(s.shapes("location-actual").length, 0);
  s.video.currentTime = event.upper_seconds; s.video.emit("timeupdate");
  assert.equal(s.shapes("location-actual").length, 1); assert.equal(s.shapes("strike-zone").length, 1);
  hiddenResult(s); assert.equal(s.video.currentTime, event.upper_seconds);
  assert.equal(s.get("watch-location").getAttribute("aria-label").includes(`실제 ${game.pitches[0].post.actual.pitch_label}:`), false,
    "actual pitch type must stay undisclosed in accessible text as well as the result panel");
  await s.end();
  assert.equal(s.get("watch-result").classList.contains("is-revealed"), true);
  assert(s.get("watch-result").textContent.includes(game.pitches[0].post.actual.result_label));
});

test("presented frame time, not the advancing media clock, controls arrival when rVFC is available", async () => {
  const s = await setup({ frameCallbacks: true }), event = firstTiming();
  await s.click("watch-toggle");
  s.video.currentTime = event.upper_seconds + 0.5;
  s.video.emit("timeupdate"); assert.equal(s.shapes("location-actual").length, 0);
  await s.showFrame(event.upper_seconds - 0.001); assert.equal(s.shapes("location-actual").length, 0);
  await s.showFrame(event.upper_seconds); assert.equal(s.shapes("location-actual").length, 1);
  hiddenResult(s);
});

test("paused or actively seeking time updates cannot reveal an arrival", async () => {
  const s = await setup(), event = firstTiming();
  s.video.currentTime = event.upper_seconds + 0.1; s.video.emit("timeupdate");
  assert.equal(s.shapes("location-actual").length, 0);
  await s.click("watch-toggle"); s.video.seeking = true; s.video.emit("seeking"); s.video.emit("timeupdate");
  assert.equal(s.shapes("location-actual").length, 0);
  await s.finishSeek(); assert.equal(s.shapes("location-actual").length, 1); hiddenResult(s);
});

test("settled seek after the marker shows only location, and seeking before it hides location without rewinding", async () => {
  const s = await setup(), event = firstTiming(); await s.click("watch-toggle"); await s.end();
  for (const after of [true, false]) {
    const target = event.upper_seconds + (after ? 0.1 : -0.1);
    s.video.ended = false; s.video.currentTime = target; s.video.seeking = true; s.video.emit("seeking");
    assert.equal(s.shapes("location-actual").length, 0); hiddenResult(s);
    await s.finishSeek();
    assert.equal(s.video.currentTime, target);
    assert.equal(s.shapes("location-actual").length, after ? 1 : 0);
    assert.equal(s.shapes("strike-zone").length, after ? 1 : 0); hiddenResult(s);
  }
});

test("cancelled frame callback from the previous pitch cannot reveal the newly selected pitch", async () => {
  const s = await setup({ frameCallbacks: true }); await s.click("watch-toggle");
  const stale = s.frames.values().next().value;
  await s.select("watch-pitch", "849843:1:2"); await s.click("watch-toggle");
  stale(0, { mediaTime: 6 }); await settle();
  assert.equal(s.shapes("location-actual").length, 0); hiddenResult(s);
  assert.equal(s.frames.size, 1, "the current pitch still owns one frame callback");
});

test("unannotated PA2 uses end-of-clip fallback for both location and outcome", async () => {
  const s = await setup({ search: "?game=849843&pitch=849843%3A2%3A1" });
  assert.equal(s.get("watch-event-marker").hidden, true);
  assert.match(s.get("watch-event-label").textContent, /미확인/);
  await s.click("watch-toggle"); s.video.currentTime = s.video.duration - 0.01; s.video.emit("timeupdate");
  assert.equal(s.shapes("location-actual").length, 0);
  await s.end(); assert.equal(s.shapes("location-actual").length, 1);
  assert.equal(s.get("watch-result").classList.contains("is-revealed"), true);
});

for (const fault of ["missing", "corrupt"]) test(`${fault} timing never blocks video or falls back to an unverified event`, async () => {
  const s = await setup({ [fault]: ["game-849843-timing.json"] });
  assert.equal(s.get("watch-toggle").disabled, false); assert.equal(s.get("watch-event-marker").hidden, true);
  await s.click("watch-toggle"); s.video.currentTime = s.video.duration - 0.01; s.video.emit("timeupdate");
  assert.equal(s.shapes("location-actual").length, 0); hiddenResult(s);
  await s.end(); assert.equal(s.shapes("location-actual").length, 1);
});

test("custom play/pause preserves playback position; replay after end clears prior result", async () => {
  const s = await setup();
  await s.click("watch-toggle"); assert.equal(s.video.paused, false);
  s.video.currentTime = 1.25; await s.click("watch-toggle");
  assert.equal(s.video.paused, true); assert.equal(s.video.currentTime, 1.25);
  assert.equal(s.get("watch-toggle").getAttribute("aria-label"), "재생");
  await s.click("watch-toggle"); assert.equal(s.video.currentTime, 1.25);
  await s.end(); await s.click("watch-toggle");
  assert.equal(s.video.currentTime, 0); assert.equal(s.video.paused, false);
  assert.equal(s.shapes("location-actual").length, 0); hiddenResult(s);
});

test("scrub uses clip-relative thousandths and updates progress; +-3 second controls clamp to clip", async () => {
  const s = await setup(); await s.click("watch-start");
  s.get("watch-scrub").value = 500; s.get("watch-scrub").emit("input");
  assert.equal(s.video.currentTime, 3.5); assert.equal(s.get("watch-stop").disabled, true);
  assert.equal(s.get("watch-scrub").style["--progress"], "50%");
  assert.match(s.get("watch-scrub").getAttribute("aria-valuetext"), /0:03 \/ 0:07/);
  assert.equal(s.shapes("location-actual").length, 0);
  await s.click("watch-back"); assert.equal(s.video.currentTime, 0.5);
  await s.click("watch-back"); assert.equal(s.video.currentTime, 0);
  await s.click("watch-forward"); assert.equal(s.video.currentTime, 3);
  await s.click("watch-forward"); assert.equal(s.video.currentTime, 6);
  await s.click("watch-forward"); assert.equal(s.video.currentTime, 7);
  hiddenResult(s);
});

test("allowed rates and mute state work independently of pitch result disclosure", async () => {
  const s = await setup();
  for (const rate of [0.5, 0.75, 1, 1.25]) {
    await s.select("watch-rate", rate); assert.equal(s.video.playbackRate, rate);
  }
  for (const rate of [0, 2, "NaN"]) {
    await s.select("watch-rate", rate); assert.equal(s.video.playbackRate, 1.25);
  }
  assert.equal(s.video.muted, true); await s.click("watch-mute");
  assert.equal(s.video.muted, false); assert.equal(s.get("watch-mute").getAttribute("aria-pressed"), "false");
  await s.click("watch-mute"); assert.equal(s.video.muted, true);
  assert.equal(s.get("watch-mute").getAttribute("aria-pressed"), "true"); hiddenResult(s);
});

test("decoder errors hide arrival and keep a custom retry available; excluded media disables transport", async () => {
  const s = await setup(); await s.click("watch-toggle");
  s.video.error = { code: 4 }; s.video.emit("error");
  assert.equal(s.get("watch-scrub").disabled, true); assert.equal(s.get("watch-toggle").disabled, false);
  await s.click("watch-toggle"); assert.equal(s.video.error, null); assert.equal(s.video.paused, false);
  hiddenResult(s);
  s.location.search = "?game=849843&pitch=849843%3A69%3A2"; s.window.emit("popstate"); await settle();
  assert.equal(s.get("watch-transport").hidden, true); assert.equal(s.get("watch-toggle").disabled, true);
  assert.equal(s.get("watch-event-marker").hidden, true); assert.equal(s.get("watch-scrub").value, "0");
});

test("arrival alone never advances the game; the result countdown starts only on ended", async () => {
  const s = await setup(), event = firstTiming(); await s.click("watch-start");
  s.video.currentTime = event.upper_seconds; s.video.emit("timeupdate");
  assert.equal(s.shapes("location-actual").length, 1); assert.equal(s.timers.size, 0); hiddenResult(s);
  await s.end(); assert.equal(s.timers.size, 1); assert.equal(s.timers.values().next().value.delay, 5000);
});

test("game progress previews a different pitch without seeking the currently loaded clip", async () => {
  const s = await setup(); await s.click("watch-start");
  s.video.currentTime = 1.25;
  const videoBefore = s.video.getAttribute("src"), identityBefore = s.get("watch-identity").textContent;
  const previewBefore = s.get("watch-game-position").textContent;
  s.get("watch-game-scrub").value = "4"; s.get("watch-game-scrub").emit("input");
  assert.equal(s.video.paused, true); assert.equal(s.get("watch-stop").disabled, true);
  assert.equal(s.video.currentTime, 1.25); assert.equal(s.video.getAttribute("src"), videoBefore);
  assert.equal(s.get("watch-identity").textContent, identityBefore);
  assert.notEqual(s.get("watch-game-position").textContent, previewBefore);
  assert.equal(s.timers.size, 0);
});

test("committing game progress selects the exact pitch and resets the clip without autoplay or old results", async () => {
  const s = await setup(); await s.click("watch-toggle"); await s.end();
  await s.select("watch-game-scrub", "4");
  const target = game.pitches[3].pitch_id;
  assert.equal(target, "849843:2:1");
  assert(s.get("watch-identity").textContent.includes(target));
  assert.equal(s.get("watch-game-scrub").value, "4");
  assert.equal(s.video.currentTime, 0); assert.equal(s.video.paused, true);
  assert.equal(s.shapes("location-actual").length, 0); assert.equal(s.timers.size, 0);
  assert.equal(s.get("watch-result").classList.contains("is-revealed"), false);
  assert.equal(new URLSearchParams(s.location.search).get("pitch"), target);
});

test("game progress can select the excluded clip and final pitch without silently skipping either", async () => {
  const s = await setup();
  const excludedPosition = game.pitches.findIndex(row => row.pitch_id === "849843:69:2") + 1;
  await s.select("watch-game-scrub", excludedPosition);
  assert(s.get("watch-identity").textContent.includes("849843:69:2"));
  assert.equal(s.video.getAttribute("src"), null); assert.equal(s.get("watch-start").disabled, true);
  await s.select("watch-game-scrub", game.pitches.length);
  assert(s.get("watch-identity").textContent.includes(game.pitches.at(-1).pitch_id));
  assert.equal(s.get("watch-game-scrub").value, "262");
  assert.equal(s.get("watch-next").disabled, true); assert.equal(s.video.paused, true);
});

test("invalid game-progress values cannot select or disclose another pitch", async () => {
  const s = await setup();
  for (const value of [0, -1, 263, 1.5, "NaN"]) {
    await s.select("watch-game-scrub", value);
    assert(s.get("watch-identity").textContent.includes("849843:1:1"));
    assert.equal(s.video.currentTime, 0); assert.equal(s.shapes("location-actual").length, 0);
  }
});

test("previous/next and restored URL keep game progress on the selected pitch", async () => {
  const s = await setup();
  assert.equal(s.get("watch-game-scrub").value, "1");
  await s.click("watch-next"); assert.equal(s.get("watch-game-scrub").value, "2");
  await s.click("watch-prev"); assert.equal(s.get("watch-game-scrub").value, "1");
  s.location.search = "?game=849843&pitch=849843%3A2%3A1"; s.window.emit("popstate"); await settle();
  assert.equal(s.get("watch-game-scrub").value, "4");
});

const descendants = root => root.children.flatMap(child => [child, ...descendants(child)]);
const pitchButtons = root => descendants(root).filter(item => item.tagName === "BUTTON" && item.getAttribute("data-pitch-id"));
const pitchButton = (s, container, key) => pitchButtons(s.get(container)).find(button => button.getAttribute("data-pitch-id") === key);
const selectedKey = s => new URLSearchParams(s.location.search).get("pitch");

test("PA ribbon reveals past pitches but withholds current and future outcomes until clip end", async () => {
  const s = await setup(), event = firstTiming();
  assert.deepEqual(pitchButtons(s.get("watch-ribbon")).map(button => button.getAttribute("data-pitch-id")),
    game.pitches.slice(0, 3).map(row => row.pitch_id));
  for (const row of game.pitches.slice(0, 3)) assert.match(pitchButton(s, "watch-ribbon", row.pitch_id).textContent, /결과 숨김/);
  await s.click("watch-toggle"); s.video.currentTime = event.upper_seconds; s.video.emit("timeupdate");
  assert.match(pitchButton(s, "watch-ribbon", "849843:1:1").textContent, /결과 숨김/);
  await s.end(); assert.match(pitchButton(s, "watch-ribbon", "849843:1:1").textContent, /스트라이크/);
  await s.clickElement(pitchButton(s, "watch-ribbon", "849843:1:2"));
  assert.match(pitchButton(s, "watch-ribbon", "849843:1:1").textContent, /스트라이크/);
  assert.match(pitchButton(s, "watch-ribbon", "849843:1:2").textContent, /결과 숨김/);
  assert.match(pitchButton(s, "watch-ribbon", "849843:1:3").textContent, /결과 숨김/);
  assert.equal(selectedKey(s), "849843:1:2"); assert.equal(s.video.paused, true); assert.equal(s.video.currentTime, 0);
  assert.equal(s.shapes("location-actual").length, 0);
  await s.clickElement(pitchButton(s, "watch-ribbon", "849843:1:1"));
  for (const button of pitchButtons(s.get("watch-ribbon"))) assert.match(button.textContent, /결과 숨김/);
});

test("ribbon follows the selected PA and situation text changes with the selected pre-pitch state", async () => {
  const s = await setup(); const firstLine = s.get("watch-situation-line").textContent;
  assert(firstLine.length > 0); assert.equal(firstLine.includes("루킹 스트라이크"), false);
  await s.select("watch-pa", "2");
  assert.deepEqual(pitchButtons(s.get("watch-ribbon")).map(button => button.getAttribute("data-pitch-id")),
    game.pitches.filter(row => row.at_bat_number === 2).map(row => row.pitch_id));
  const row = game.pitches.find(row => row.situation.bases !== 0 && row.situation.balls > 0);
  await s.select("watch-game-scrub", game.pitches.indexOf(row) + 1);
  assert.notEqual(s.get("watch-situation-line").textContent, firstLine);
  assert.doesNotMatch(s.get("watch-situation-line").textContent, /mph|파울|헛스윙|홈런|타구 결과/);
  assert.equal(selectedKey(s), row.pitch_id);
});

test("filter results paginate the actual pitch IDs and expose metadata, never outcome or actual pitch type", async () => {
  const s = await setup();
  const ids = () => pitchButtons(s.get("watch-filter-results")).map(button => button.getAttribute("data-pitch-id"));
  assert.deepEqual(ids(), game.pitches.slice(0, 12).map(row => row.pitch_id));
  assert.equal(s.get("watch-filter-prev").disabled, true);
  assert.doesNotMatch(s.get("watch-filter-results").textContent, /루킹|헛스윙|삼진|파울|안타|포심|싱커|mph/);
  assert.match(pitchButtons(s.get("watch-filter-results"))[0].textContent, /0볼 0스트라이크/);
  await s.click("watch-filter-next");
  assert.deepEqual(ids(), game.pitches.slice(12, 24).map(row => row.pitch_id));
  assert.equal(selectedKey(s), "849843:1:1");
  await s.click("watch-filter-prev"); assert.deepEqual(ids(), game.pitches.slice(0, 12).map(row => row.pitch_id));
});

test("changing filters pauses continuation without selecting a different pitch; clicking a result binds exact ID", async () => {
  const s = await setup(); await s.click("watch-start"); s.video.currentTime = 1.25;
  const beforeSource = s.video.getAttribute("src");
  const pitcher = game.pitches[0].pitcher.id, batter = game.pitches[0].batter.id;
  await s.select("watch-filter-pitcher", pitcher);
  assert.equal(s.video.paused, true); assert.equal(s.video.currentTime, 1.25); assert.equal(s.video.getAttribute("src"), beforeSource);
  assert.equal(s.get("watch-stop").disabled, true); assert.equal(selectedKey(s), "849843:1:1");
  await s.select("watch-filter-batter", batter); await s.select("watch-filter-count", "0-0");
  const expected = game.pitches.filter(row => row.pitcher.id === pitcher && row.batter.id === batter && row.situation.balls === 0 && row.situation.strikes === 0);
  assert.deepEqual(pitchButtons(s.get("watch-filter-results")).map(button => button.getAttribute("data-pitch-id")), expected.slice(0, 12).map(row => row.pitch_id));
  const target = expected.at(-1); assert.notEqual(target.pitch_id, "849843:1:1");
  await s.clickElement(pitchButton(s, "watch-filter-results", target.pitch_id));
  assert.equal(selectedKey(s), target.pitch_id); assert.equal(s.video.currentTime, 0); assert.equal(s.video.paused, true);
  assert.equal(s.shapes("location-actual").length, 0); assert.equal(s.get("watch-result").classList.contains("is-revealed"), false);
  await s.click("watch-filter-clear");
  for (const id of ["watch-filter-pitcher", "watch-filter-batter", "watch-filter-count"]) assert.equal(s.get(id).value, "all");
  assert.equal(pitchButtons(s.get("watch-filter-results")).length, 12); assert.equal(selectedKey(s), target.pitch_id);
});

test("an impossible pitcher/batter pair produces an explicit empty filter without changing current data", async () => {
  const s = await setup();
  await s.select("watch-filter-pitcher", game.pitches[0].pitcher.id);
  const opposingPitcherFirst = game.pitches.find(row => row.pitcher.id !== game.pitches[0].pitcher.id);
  await s.select("watch-filter-batter", opposingPitcherFirst.batter.id);
  assert.equal(pitchButtons(s.get("watch-filter-results")).length, 0);
  assert.match(s.get("watch-filter-status").textContent, /0|없/);
  assert.equal(s.get("watch-filter-next").disabled, true); assert.equal(s.get("watch-filter-prev").disabled, true);
  assert.equal(selectedKey(s), "849843:1:1"); assert.equal(s.get("watch-candidates").children.length, 3);
});

test("pitcher history excludes other pitchers, current pitch, and future pitches even after the result is disclosed", async () => {
  const s = await setup();
  assert.match(s.get("watch-history-summary").textContent, /0구|0 구|표본\s*0|없/);
  const opposingPitcherFirst = game.pitches.find(row => row.pitcher.id !== game.pitches[0].pitcher.id);
  await s.select("watch-game-scrub", game.pitches.indexOf(opposingPitcherFirst) + 1);
  assert.match(s.get("watch-history-summary").textContent, /0구|0 구|표본\s*0|없/);
  const current = game.pitches.find(row => row.at_bat_number === 2 && row.pitch_number === 1);
  await s.select("watch-game-scrub", game.pitches.indexOf(current) + 1);
  assert.match(s.get("watch-history-summary").textContent, /3구|3 구|표본\s*3/);
  const historyBefore = s.get("watch-history-list").textContent;
  for (const row of game.pitches.slice(0, 3)) assert(historyBefore.includes(row.post.actual.pitch_label));
  assert.match(historyBefore, /96\.3/); assert.match(historyBefore, /86\.4/); assert.match(historyBefore, /97\.6/);
  assert.match(historyBefore, /mph/);
  await s.click("watch-toggle"); await s.end();
  assert.equal(s.get("watch-history-list").textContent, historyBefore);
  await s.click("watch-next"); assert.match(s.get("watch-history-summary").textContent, /4구|4 구|표본\s*4/);
});

test("recommendation and actual layer toggles preserve playback and candidate text without leaking hidden actuals", async () => {
  const s = await setup();
  assert.equal(s.get("watch-show-recommendations").checked, true);
  assert.equal(s.get("watch-show-actual").checked, true); assert.equal(s.get("watch-show-mitt").checked, false);
  await s.click("watch-start"); s.video.currentTime = 1.25;
  const candidates = s.get("watch-candidates").textContent;
  await s.check("watch-show-recommendations", false);
  assert.equal(s.shapes("location-recommended").length, 0); assert.equal(s.get("watch-candidates").textContent, candidates);
  assert.equal(s.video.paused, false); assert.equal(s.video.currentTime, 1.25); assert.equal(s.get("watch-stop").disabled, false);
  await s.check("watch-show-recommendations", true); assert(s.shapes("location-recommended").length > 0);
  await s.check("watch-show-actual", false); await s.check("watch-show-actual", true);
  assert.equal(s.shapes("location-actual").length, 0); hiddenResult(s);
  await s.end(); const result = s.get("watch-result").textContent, time = s.video.currentTime;
  await s.check("watch-show-actual", false);
  assert.equal(s.shapes("location-actual").length, 0); assert.equal(s.shapes("location-actual-halo").length, 0);
  assert.match(s.get("watch-coordinate-note").textContent, /숨김|꺼짐/);
  assert.equal(s.get("watch-result").textContent, result); assert.equal(s.video.currentTime, time);
  assert.equal(s.get("watch-result").classList.contains("is-revealed"), true);
  await s.check("watch-show-actual", true); assert.equal(s.shapes("location-actual").length, 1);
});

test("mitt x is never exposed at arrival; only ended enables its separate horizontal observation", async () => {
  const s = await setup({ search: "?game=849843&pitch=849843%3A1%3A3" });
  assert.equal(s.get("watch-mitt-panel").hidden, true); await s.check("watch-show-mitt", true);
  assert.equal(s.get("watch-mitt-axis").hidden, true);
  assert.doesNotMatch(s.get("watch-mitt-value").textContent, /-0\.05/);
  const event = JSON.parse(fs.readFileSync(path.join(site, "game-849843-timing.json"))).records.find(row => row.pitch_id === "849843:1:3");
  await s.click("watch-toggle"); s.video.currentTime = event.upper_seconds; s.video.emit("timeupdate");
  assert.equal(s.shapes("location-actual").length, 1); assert.equal(s.get("watch-mitt-axis").hidden, true);
  assert.doesNotMatch(s.get("watch-mitt-value").textContent, /-0\.05/);
  await s.end();
  assert.equal(s.get("watch-mitt-panel").hidden, false); assert.equal(s.get("watch-mitt-axis").hidden, false);
  assert.match(s.get("watch-mitt-value").textContent, /-0\.05/); assert.match(s.get("watch-mitt-value").textContent, /ft/);
  assert.match(s.get("watch-mitt-status").textContent, /추정|미검토/);
  assert.equal(descendants(s.get("watch-location")).includes(s.get("watch-mitt-dot")), false);
  assert.equal(s.get("pitch-observation-image").hidden, true);
  s.video.currentTime = 1; s.video.ended = false; s.video.emit("seeking"); await s.finishSeek();
  assert.equal(s.get("watch-mitt-axis").hidden, true);
  assert.doesNotMatch(s.get("watch-mitt-value").textContent, /-0\.05/);
});

test("missing and unavailable mitt observations never reuse an earlier estimated dot", async () => {
  const s = await setup({ search: "?game=849843&pitch=849843%3A1%3A3" });
  await s.check("watch-show-mitt", true); await s.click("watch-toggle"); await s.end();
  assert.equal(s.get("watch-mitt-axis").hidden, false);
  for (const [key, status] of [["849843:1:1", /없|미제공|연결/], ["849843:2:5", /불가|기권|사용할 수 없|미제공/]]) {
    await s.select("watch-game-scrub", game.pitches.findIndex(row => row.pitch_id === key) + 1);
    assert.equal(s.get("watch-mitt-axis").hidden, true);
    await s.click("watch-toggle"); await s.end();
    assert.match(s.get("watch-mitt-status").textContent, status);
    assert.equal(s.get("watch-mitt-axis").hidden, true);
    assert.doesNotMatch(s.get("watch-mitt-value").textContent, /-0\.05/);
  }
});

test("a failed route clears all new context and cannot restore prior data through layer toggles", async () => {
  const s = await setup({ search: "?game=849843&pitch=849843%3A1%3A3" });
  await s.check("watch-show-mitt", true); await s.click("watch-toggle"); await s.end();
  s.location.search = "?game=849844"; s.window.emit("popstate"); await settle();
  assert.equal(s.get("watch-ribbon").children.length, 0); assert.equal(s.get("watch-filter-results").children.length, 0);
  assert.equal(s.get("watch-history-list").children.length, 0); assert.equal(s.get("watch-situation-line").textContent, "");
  assert.equal(s.get("watch-history-summary").textContent, "");
  assert.equal(s.get("watch-mitt-axis").hidden, true);
  assert.doesNotMatch(s.get("watch-mitt-value").textContent, /-0\.05/);
  for (const id of ["watch-show-recommendations", "watch-show-actual", "watch-show-mitt"]) { s.get(id).checked = true; s.get(id).emit("change"); }
  assert.equal(s.get("watch-location").children.length, 0); assert.equal(s.get("watch-mitt-axis").hidden, true);
});

test("successful loading cancels all request deadlines and keeps retry hidden", async () => {
  const s = await setup();
  assert.equal(s.timers.size, 0); assert.equal(s.get("watch-retry").hidden, true);
  assert.equal(s.reloads.length, 0); assert.equal(s.requests.length, 4);
  assert.match(s.get("watch-load-status").textContent, /저장 경기 262구/);
});

for (const fault of ["missing", "corrupt", "malformed"]) {
  test(`${fault} core data fails closed with a friendly message and a user-initiated retry`, async () => {
    const s = await setup(fault === "malformed" ? { raw: { "game-849843.json": '{"synthetic-private-marker" nope' } }
      : { [fault]: ["game-849843.json"] });
    assert.equal(s.get("watch-start").disabled, true); assert.equal(s.get("watch-pa").disabled, true);
    assert.equal(s.video.getAttribute("src"), null); assert.equal(s.get("watch-candidates").children.length, 0);
    assert.equal(s.get("watch-location").children.length, 0); assert.equal(s.get("watch-retry").hidden, false);
    assert.match(s.get("watch-load-status").textContent, /자료 다시 불러오기/);
    assert.doesNotMatch(s.get("watch-load-status").textContent, /synthetic-private-marker|SyntaxError|JSON|SHA|TypeError/);
    assert.equal(s.requests.length, 1); assert.equal(s.timers.size, 0); assert.equal(s.reloads.length, 0);
    await s.click("watch-retry"); assert.equal(s.reloads.length, 1);
    assert.equal(s.requests.length, 1, "retry asks the browser to reload; it does not launch an uncontrolled request loop");
  });
}

for (const stage of ["headers", "body", "digest"]) {
  test(`core ${stage} stall expires in one bounded deadline and a late response cannot restore the page`, async () => {
    const s = await setup({ stalled: { "game-849843.json": stage }, waitForReady: false });
    await settle(() => s.held.has("game-849843.json"));
    assert.equal(s.timers.size, 1); assert.equal(s.get("watch-start").disabled, true);
    await s.expireRequests(); await settle(() => !s.get("watch-retry").hidden);
    assert.equal(s.signals.get("game-849843.json").aborted, true);
    assert.equal(s.get("watch-candidates").children.length, 0); assert.equal(s.timers.size, 0);
    await s.finishAsset("game-849843.json");
    assert.equal(s.get("watch-candidates").children.length, 0); assert.equal(s.get("watch-pa").disabled, true);
    assert.equal(s.requests.length, 1); assert.equal(s.reloads.length, 0);
  });
}

test("stalled optional video mapping does not hide the verified game, change a user's selection, or load a late unchecked clip", async () => {
  const s = await setup({ stalled: { "game-849843-media.json": "body" }, waitForReady: false });
  await settle(() => s.held.has("game-849843-media.json") && s.timers.size === 1);
  assert.match(s.get("watch-identity").textContent, /849843:1:1/);
  assert.equal(s.get("watch-candidates").children.length, 3); assert.equal(s.get("watch-pa").disabled, false);
  assert.equal(s.get("watch-start").disabled, true); assert.match(s.get("watch-load-status").textContent, /확인 중/);
  await s.select("watch-pitch", "849843:1:3");
  await s.expireRequests(); await settle(() => /저장 경기 262구/.test(s.get("watch-load-status").textContent));
  assert.equal(selectedKey(s), "849843:1:3"); assert.equal(s.get("watch-candidates").children.length, 3);
  assert.equal(s.get("watch-start").disabled, true); assert.equal(s.get("watch-retry").hidden, false);
  assert.equal(s.signals.get("game-849843-media.json").aborted, true);
  await s.finishAsset("game-849843-media.json");
  assert.equal(s.video.getAttribute("src"), null); assert.equal(s.get("watch-start").disabled, true);
  assert.equal(s.shapes("location-actual").length, 0); assert.equal(s.timers.size, 0);
  await s.click("watch-retry"); assert.equal(s.reloads.length, 1); assert.equal(selectedKey(s), "849843:1:3");
});

test("a stalled zone request falls back to the labelled reference while verified video and results remain usable", async () => {
  const s = await setup({ stalled: { "game-849843-zones.json": "headers" }, waitForReady: false });
  await settle(() => s.held.has("game-849843-zones.json") && s.timers.size === 1);
  await s.expireRequests(); await settle(() => /저장 경기 262구/.test(s.get("watch-load-status").textContent));
  assert.equal(s.get("watch-start").disabled, false); assert.equal(s.get("watch-retry").hidden, false);
  assert.match(s.get("watch-zone-note").textContent, /참고/);
  await s.click("watch-toggle"); await s.end();
  assert.equal(s.shapes("location-actual").length, 1); assert.equal(s.shapes("strike-zone").length, 0);
  assert.equal(s.shapes("reference-zone").length, 1);
  await s.finishAsset("game-849843-zones.json"); assert.equal(s.shapes("strike-zone").length, 0);
});

test("optional loading cannot revive stale data after an invalid route clears the verified game", async () => {
  const s = await setup({ stalled: { "game-849843-timing.json": "body" }, waitForReady: false });
  await settle(() => s.held.has("game-849843-timing.json") && s.timers.size === 1);
  s.location.search = "?game=849844"; s.window.emit("popstate"); await settle();
  assert.equal(s.get("watch-candidates").children.length, 0); assert.equal(s.get("watch-retry").hidden, false);
  await s.finishAsset("game-849843-timing.json"); await settle(() => s.timers.size === 0);
  assert.equal(s.get("watch-candidates").children.length, 0); assert.equal(s.get("watch-start").disabled, true);
  assert.equal(s.video.getAttribute("src"), null); assert.equal(s.get("watch-history-list").children.length, 0);
  assert.match(s.get("watch-load-status").textContent, /확인하지 못/);
});

test("a history change during core loading selects the current URL, not the stale initial pitch", async () => {
  const s = await setup({ stalled: { "game-849843.json": "headers" }, waitForReady: false });
  await settle(() => s.held.has("game-849843.json"));
  s.location.search = "?game=849843&pitch=849843%3A2%3A1"; s.window.emit("popstate");
  await s.finishAsset("game-849843.json");
  await settle(() => /저장 경기 262구/.test(s.get("watch-load-status").textContent));
  assert.equal(selectedKey(s), "849843:2:1"); assert.match(s.get("watch-identity").textContent, /849843:2:1/);
  assert.equal(s.shapes("location-actual").length, 0); assert.equal(s.video.paused, true);
});

test("an invalid history change during core loading cannot display a valid but stale game", async () => {
  const s = await setup({ stalled: { "game-849843.json": "headers" }, waitForReady: false });
  await settle(() => s.held.has("game-849843.json"));
  s.location.search = "?game=849844"; s.window.emit("popstate");
  await s.finishAsset("game-849843.json"); await settle(() => !s.get("watch-retry").hidden);
  assert.equal(s.requests.length, 1); assert.equal(s.get("watch-candidates").children.length, 0);
  assert.equal(s.video.getAttribute("src"), null); assert.equal(s.get("watch-start").disabled, true);
});

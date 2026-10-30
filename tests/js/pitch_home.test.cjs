"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../../web/pitch-studio/home.js"), "utf8");

function setup({ reduced = false, blocked = false, pending = false, unsupported = false, networkState = 1 } = {}) {
  const elements = {};
  for (const id of ["hero-video", "hero-still", "hero-play", "film-mode", "source"]) {
    elements[id] = {
      hidden: false, textContent: "", listeners: {},
      addEventListener(event, callback) { this.listeners[event] = callback; },
      emit(event) { this.listeners[event]?.(); },
    };
  }
  const film = elements["hero-video"];
  Object.assign(film, {
    paused: true, error: null, calls: 0, loads: 0, networkState,
    querySelector() { return elements.source; },
    load() { this.error = null; this.loads++; },
    play() {
      this.calls++;
      if (blocked || unsupported) return Promise.reject(Object.assign(new Error("play rejected"), {name: blocked ? "NotAllowedError" : "NotSupportedError"}));
      if (pending) return new Promise((resolve, reject) => { this.rejectPending = reject; });
      this.paused = false;
      this.emit("playing");
      return Promise.resolve();
    },
    pause() { this.paused = true; this.emit("pause"); },
  });
  const listeners = {};
  const location = { hash: "", replaced: null, replace(value) { this.replaced = value; } };
  vm.runInNewContext(source, {
    document: { getElementById: (id) => elements[id] },
    matchMedia: () => ({ matches: reduced }),
    location,
    window: { addEventListener(event, callback) { listeners[event] = callback; } },
  });
  return { elements, film, location, listeners, allow: () => { blocked = false; unsupported = false; } };
}
const flush = () => new Promise((resolve) => setImmediate(resolve));

test("legacy analysis links open the full game, including later hash changes", () => {
  const { location, listeners } = setup({ reduced: true });
  location.hash = "#analysis";
  listeners.hashchange();
  assert.equal(location.replaced, "watch.html?game=849843");
  location.hash = "#validation";
  listeners.hashchange();
  assert.equal(location.replaced, "report.html#validation");
});

test("blocked autoplay leaves a working user-initiated retry", async () => {
  const { elements: e, film, allow } = setup({ blocked: true });
  await flush();
  assert.match(e["film-mode"].textContent, /재생 버튼/);
  assert.equal(e["hero-play"].hidden, false);
  assert.equal(e["hero-still"].hidden, film.paused ? false : true);
  allow();
  e["hero-play"].emit("click");
  await flush();
  assert.equal(film.paused, false);
  assert.match(e["hero-play"].textContent, /일시정지/);
});

test("late autoplay rejection cannot replace the explicit media error", async () => {
  const { elements:e, film } = setup({pending:true});
  film.emit("error");
  film.rejectPending(new Error("AbortError"));
  await flush();
  assert.match(e["film-mode"].textContent,/영상 연결/);
  assert.equal(e["hero-still"].hidden,false);
});

test("missing source before script load and unsupported play recover with an explicit reload", async () => {
  const {elements:e, film, allow} = setup({unsupported:true, networkState:3});
  await flush();
  assert.equal(film.loads,1);
  assert.match(e["film-mode"].textContent,/영상 연결/);
  assert.equal(e["hero-still"].hidden,false);
  allow();
  e["hero-play"].emit("click");
  await flush();
  assert.equal(film.loads,2);
  assert.equal(film.paused,false);
});

test("media and source failures retain the still and reload on explicit retry", async () => {
  for (const target of ["hero-video", "source"]) {
    const { elements: e, film } = setup();
    e[target].emit("error");
    assert.equal(film.paused, true);
    assert.equal(e["hero-still"].hidden, false);
    assert.match(e["film-mode"].textContent, /영상 연결/);
    e["hero-play"].emit("click");
    await flush();
    assert.equal(film.loads, 1);
    assert.equal(film.paused, false);
    assert.equal(e["hero-still"].hidden, film.paused ? false : true);
  }
});

test("reduced motion starts still and permits explicit replay", async () => {
  const { elements: e, film } = setup({ reduced: true });
  assert.equal(film.calls, 0);
  assert.equal(e["hero-still"].hidden, false);
  e["hero-play"].emit("click");
  await flush();
  assert.equal(film.calls, 1);
  assert.equal(e["hero-still"].hidden, film.paused ? false : true);
});

test("pause and resume retain the video rather than an unrelated still", async () => {
  const { elements: e, film } = setup();
  await flush();
  e["hero-play"].emit("click");
  assert.equal(film.paused, true);
  assert.match(e["hero-play"].textContent, /영상 재생/);
  e["hero-play"].emit("click");
  await flush();
  assert.equal(film.paused, false);
  assert.equal(e["hero-still"].hidden, film.paused ? false : true);
});

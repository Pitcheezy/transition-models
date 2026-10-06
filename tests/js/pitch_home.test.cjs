"use strict";
const { test } = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs");
const path = require("node:path");
const vm = require("node:vm");
const source = fs.readFileSync(path.join(__dirname, "../../web/pitch-studio/home.js"), "utf8");

function setup({ reduced = false, blocked = false, pending = false } = {}) {
  const elements = {};
  for (const id of ["hero-video", "hero-still", "hero-marker", "hero-toggle", "hero-play", "film-mode", "source"]) {
    elements[id] = {
      hidden: false, textContent: "", listeners: {},
      addEventListener(event, callback) { this.listeners[event] = callback; },
      emit(event) { this.listeners[event]?.(); },
    };
  }
  const film = elements["hero-video"];
  Object.assign(film, {
    paused: true, error: null, calls: 0, loads: 0,
    querySelector() { return elements.source; },
    load() { this.error = null; this.loads++; },
    play() {
      this.calls++;
      if (blocked) return Promise.reject(new Error("NotAllowedError"));
      if (pending) return new Promise((resolve, reject) => { this.rejectPending = reject; });
      this.paused = false;
      this.emit("playing");
      return Promise.resolve();
    },
    pause() { this.paused = true; this.emit("pause"); },
  });
  vm.runInNewContext(source, {
    document: { getElementById: (id) => elements[id] },
    matchMedia: () => ({ matches: reduced }),
    location: { hash: "", replace() {} },
  });
  return { elements, film, allow: () => { blocked = false; } };
}
const flush = () => new Promise((resolve) => setImmediate(resolve));

test("blocked autoplay leaves a working user-initiated retry", async () => {
  const { elements: e, film, allow } = setup({ blocked: true });
  await flush();
  assert.match(e["film-mode"].textContent, /재생 버튼/);
  assert.equal(e["hero-play"].hidden, false);
  assert.equal(e["hero-marker"].hidden, true);
  allow();
  e["hero-play"].emit("click");
  await flush();
  assert.equal(film.paused, false);
  assert.match(e["hero-play"].textContent, /일시정지/);
});

test("still observation pauses video; replay hides its marker", async () => {
  const { elements: e, film } = setup();
  e["hero-toggle"].emit("click");
  assert.equal(film.paused, true);
  assert.equal(film.hidden, true);
  assert.equal(e["hero-marker"].hidden, false);
  e["hero-toggle"].emit("click");
  await flush();
  assert.equal(film.paused, false);
  assert.equal(e["hero-marker"].hidden, true);
  assert.equal(e["hero-still"].hidden, true);
});

test("late autoplay rejection cannot replace the still-frame explanation", async () => {
  const { elements: e, film } = setup({ pending: true });
  e["hero-toggle"].emit("click");
  film.rejectPending(new Error("AbortError"));
  await flush();
  assert.match(e["film-mode"].textContent, /정지 프레임/);
  assert.equal(e["hero-marker"].hidden, false);
});

test("media and source failures retain the still and reload on explicit retry", async () => {
  for (const target of ["hero-video", "source"]) {
    const { elements: e, film } = setup();
    e[target].emit("error");
    assert.equal(film.paused, true);
    assert.equal(e["hero-still"].hidden, false);
    assert.match(e["film-mode"].textContent, /재생 불가/);
    e["hero-toggle"].emit("click");
    await flush();
    assert.equal(film.loads, 1);
    assert.equal(film.paused, false);
    assert.equal(e["hero-marker"].hidden, true);
  }
});

test("reduced motion starts still and permits explicit replay", async () => {
  const { elements: e, film } = setup({ reduced: true });
  assert.equal(film.calls, 0);
  assert.equal(e["hero-marker"].hidden, false);
  e["hero-toggle"].emit("click");
  await flush();
  assert.equal(film.calls, 1);
  assert.equal(e["hero-marker"].hidden, true);
});

test("pause and resume controls follow media state without showing a marker", async () => {
  const { elements: e, film } = setup();
  await flush();
  e["hero-play"].emit("click");
  assert.equal(film.paused, true);
  assert.match(e["hero-play"].textContent, /영상 재생/);
  e["hero-play"].emit("click");
  await flush();
  assert.equal(film.paused, false);
  assert.equal(e["hero-marker"].hidden, true);
});

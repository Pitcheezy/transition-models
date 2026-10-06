"use strict";
const test = require("node:test");
const assert = require("node:assert/strict");
const fs = require("node:fs"), path = require("node:path");
const site = fs.existsSync(path.join(__dirname, "../dist")) ? "../dist" : "../pitch-studio";
const { create } = require(path.join(__dirname, site, "receiver-video.js"));
function setup() {
  const callbacks = {}, attrs = {};
  const video = {
    paused: true, ended: false, currentTime: 0, hidden: false, error: null,
    addEventListener: (name, fn) => { callbacks[name] = fn; },
    getAttribute: (name) => attrs[name],
    setAttribute: (name, value) => { attrs[name] = value; },
    removeAttribute: (name) => { delete attrs[name]; },
    pause() { this.paused = true; callbacks.pause?.(); },
    load() { this.ended = false; this.currentTime = 0; this.error = null; },
    play() { this.paused = false; callbacks.play(); return Promise.resolve(); },
  };
  let click;
  const elements = { video, section: {}, frame: {}, missing: {}, status: {}, fallback: {},
    play: { addEventListener: (_, fn) => { click = fn; } } };
  const reveals = [];
  const controller = create(elements, (binding) => reveals.push(binding));
  const update = (pitch = 3, revealed = false, context = 1, enabled = true) =>
    controller.update({ context, pitch_id: `849843:1:${pitch}`, revealed, enabled });
  return { elements, video, callbacks, reveals, update, click: () => click(), controller };
}
test("only the verified third pitch of the built-in demo gets a video", () => {
  const s = setup();
  for (const pitch of [1, 2]) { s.update(pitch); assert(s.elements.frame.hidden); assert(!s.video.getAttribute("src")); }
  s.update(); assert(!s.elements.frame.hidden); assert.match(s.video.getAttribute("src"), /1-3\.mp4$/);
  s.update(3, false, 1, false); assert(s.elements.section.hidden); assert(!s.video.getAttribute("src"));
});
test("playing does not reveal results; completed playback does", async () => {
  const s = setup(); s.update(); await s.click();
  assert.equal(s.reveals.length, 0);
  s.video.ended = true; s.callbacks.ended();
  assert.deepEqual(s.reveals, ["1:849843:1:3"]);
  s.callbacks.ended(); assert.equal(s.reveals.length, 1);
});
test("rewind or new input pauses and clears the previous final frame", async () => {
  const s = setup(); s.update(); await s.click(); s.video.currentTime = 3;
  s.update(2); assert(s.video.paused); assert.equal(s.video.currentTime, 0);
  s.video.ended = true; s.callbacks.ended(); assert.equal(s.reveals.length, 0);
  s.update(3, false, 2); s.callbacks.ended(); assert.equal(s.reveals.length, 0);
});
test("hiding a revealed third pitch returns video to its beginning", async () => {
  const s = setup(); s.update(); await s.click(); s.update(3, true);
  s.video.currentTime = 3; s.update(3, false);
  assert(s.video.paused); assert.equal(s.video.currentTime, 0); assert.equal(s.reveals.length, 0);
});
test("late play rejection cannot overwrite a newer pitch's message", async () => {
  const s = setup(); s.update(); let reject;
  s.video.play = () => new Promise((_, fail) => { reject = fail; });
  const pending = s.click(); s.update(1);
  const message = s.elements.status.textContent; reject(new Error("late")); await pending;
  assert.equal(s.elements.status.textContent, message); assert.equal(s.reveals.length, 0);
});
test("playback failure gives a retry without revealing results", async () => {
  const s = setup(); s.update(); s.video.play = () => Promise.reject(new Error("blocked"));
  await s.click(); assert.match(s.elements.status.textContent, /다시/); assert.equal(s.reveals.length, 0);
});
test("media errors show the verified still and retry restores video", async () => {
  const s = setup(); s.update(); s.video.error = { code: 4 }; s.callbacks.error();
  assert(s.video.hidden); assert(!s.elements.fallback.hidden); assert.equal(s.reveals.length, 0);
  await s.click(); assert(!s.video.hidden); assert(s.elements.fallback.hidden);
});
test("clearing the packet discards pending playback and disclosure", async () => {
  const s = setup(); s.update(); await s.click(); s.controller.update(null);
  s.video.ended = true; s.callbacks.ended();
  assert(s.elements.section.hidden); assert(s.video.paused); assert.equal(s.reveals.length, 0);
});

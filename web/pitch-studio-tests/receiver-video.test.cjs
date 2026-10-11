"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const fs = require("node:fs"), path = require("node:path"), crypto = require("node:crypto");
const site = fs.existsSync(path.join(__dirname, "../dist")) ? "../dist" : "../pitch-studio";
const { create } = require(path.join(__dirname, site, "receiver-video.js"));
const media = require(path.join(__dirname, site, "receiver-media.js"));
function element() {
  const callbacks = {}, attrs = {};
  return { callbacks, style: {}, hidden: false, complete: true, naturalWidth: 1280,
    addEventListener: (name, fn) => { callbacks[name] = fn; },
    getAttribute: (name) => attrs[name], setAttribute: (name,value) => { attrs[name]=value; },
    removeAttribute: (name) => { delete attrs[name]; } };
}
function setup() {
  const video = Object.assign(element(), {
    paused: true, ended: false, currentTime: 0, error: null,
    pause() { this.paused = true; this.callbacks.pause?.(); },
    load() { this.ended = false; this.currentTime = 0; this.error = null; },
    play() { this.paused = false; this.callbacks.play(); return Promise.resolve(); },
  });
  const elements = {video};
  for(const name of ["section","frame","missing","status","fallback","play","inspect","observationImage","marker","observationNote","sourceLink"]) elements[name]=element();
  const reveals = [];
  const controller = create(elements, binding => reveals.push(binding), media);
  const update = (pitch=3, revealed=false, context=1, enabled=true, observationAllowed=true) =>
    controller.update({context,pitch_id:`849843:1:${pitch}`,revealed,enabled,observationAllowed});
  return {elements,video,callbacks:video.callbacks,reveals,update,controller,click:()=>elements.play.callbacks.click(),inspect:()=>elements.inspect.callbacks.click()};
}

test("all three exact clips and posters match their recorded hashes",()=>{
  assert.deepEqual(Object.keys(media),["849843:1:1","849843:1:2","849843:1:3"]);
  for(const [id,record] of Object.entries(media)) {
    assert.equal(id,record.pitch_id);
    for(const kind of ["video","poster"]) {
      const actual=crypto.createHash("sha256").update(fs.readFileSync(path.join(__dirname,site,record[kind]))).digest("hex");
      assert.equal(actual,record[`${kind}_sha256`]);
    }
    assert.equal(new URL(record.page_url).searchParams.get("playId"),record.play_id);
  }
  assert.equal(media["849843:1:1"].observation,undefined);
  assert.equal(media["849843:1:2"].observation,undefined);
  assert.equal(media["849843:1:3"].observation.poster,"media/pitch-849843-1-3.jpg");
});
test("each built-in pitch selects its own clip; other files have no video",()=>{
  const s=setup();
  for(const pitch of [1,2,3]) {s.update(pitch);assert(!s.elements.frame.hidden);assert.match(s.video.getAttribute("src"),new RegExp(`1-${pitch}-official\\.mp4$`));}
  s.update(3,false,1,false);assert(s.elements.section.hidden);assert(!s.video.getAttribute("src"));
  s.update(4);assert(s.elements.frame.hidden);
});
test("playing does not reveal results; ended reveals once",async()=>{
  const s=setup();s.update(1);await s.click();assert.equal(s.reveals.length,0);
  s.video.ended=true;s.callbacks.ended();assert.deepEqual(s.reveals,["1:849843:1:1"]);
  s.callbacks.ended();assert.equal(s.reveals.length,1);
});
test("pitch switch stops old video and rejects a stale ended event",async()=>{
  const s=setup();s.update(1);await s.click();s.video.currentTime=6;s.update(2);
  assert(s.video.paused);assert.equal(s.video.currentTime,0);s.video.ended=true;s.callbacks.ended();assert.equal(s.reveals.length,0);
  s.update(2,false,2);s.callbacks.ended();assert.equal(s.reveals.length,0);
});
test("hiding results resets playback and clears the observation marker",async()=>{
  const s=setup();s.update(3,true);s.inspect();assert(!s.elements.marker.hidden);
  s.update(3,false);assert(s.elements.marker.hidden);assert(s.elements.observationImage.hidden);assert(s.video.paused);assert.equal(s.video.currentTime,0);
});
test("mitt inspection needs third-pitch evidence and disclosed result",()=>{
  const s=setup();
  for(const pitch of [1,2]) {s.update(pitch,true);s.inspect();assert(s.elements.marker.hidden);assert(s.elements.inspect.hidden);}
  s.update(3,false);s.inspect();assert(s.elements.marker.hidden);assert(s.elements.inspect.disabled);
  s.update(3,true,1,true,false);s.inspect();assert(s.elements.marker.hidden);
  s.update(3,true);s.inspect();assert(!s.elements.marker.hidden);assert(s.video.hidden);
  assert.equal(s.elements.observationImage.getAttribute("src"),"media/pitch-849843-1-3.jpg");
  assert.equal(s.elements.marker.style.left,"44.609375%");
});
test("mitt marker waits for annotated image decode",()=>{
  const s=setup();s.elements.observationImage.complete=false;s.elements.observationImage.naturalWidth=0;
  s.update(3,true);s.inspect();assert(s.elements.marker.hidden);
  s.elements.observationImage.complete=true;s.elements.observationImage.naturalWidth=1280;s.elements.observationImage.callbacks.load();assert(!s.elements.marker.hidden);
  s.elements.observationImage.callbacks.error();assert(s.elements.marker.hidden);
});
test("returning to playback removes the still marker before playing",async()=>{
  const s=setup();s.update(3,true);s.inspect();await s.click();assert(s.elements.marker.hidden);assert(s.elements.observationImage.hidden);assert(!s.video.hidden);
});
test("late play rejection cannot overwrite newer pitch or still state",async()=>{
  const s=setup();s.update(1);let reject;s.video.play=()=>new Promise((_,fail)=>{reject=fail;});
  const pending=s.click();s.update(2);const message=s.elements.status.textContent;reject(new Error("late"));await pending;assert.equal(s.elements.status.textContent,message);
  s.update(3,true);const stillPending=s.click();s.inspect();const stillMessage=s.elements.status.textContent;reject(new Error("late"));await stillPending;assert.equal(s.elements.status.textContent,stillMessage);
});
test("playback failure is retryable and does not reveal",async()=>{
  const s=setup();s.update();s.video.play=()=>Promise.reject(new Error("blocked"));await s.click();assert.match(s.elements.status.textContent,/다시/);assert.equal(s.reveals.length,0);
});
test("intentional pause cancels a pending play without displaying failure",async()=>{
  const s=setup();s.update(1);let reject;
  s.video.play=()=>{s.video.paused=false;s.callbacks.play();return new Promise((_,fail)=>{reject=fail;});};
  const pending=s.click();await s.click();
  reject(Object.assign(new Error("paused"),{name:"AbortError"}));await pending;
  assert(s.video.paused);assert.equal(s.elements.play.textContent,"투구 영상 재생");
  assert.doesNotMatch(s.elements.status.textContent,/못했습니다/);assert.equal(s.reveals.length,0);
});
test("media error fallback belongs to the current pitch and retry restores video",async()=>{
  const s=setup();s.update(2);s.video.error={code:4};s.callbacks.error();assert(s.video.hidden);assert(!s.elements.fallback.hidden);
  assert.match(s.elements.fallback.getAttribute("src"),/1-2-official\.jpg$/);assert(s.elements.marker.hidden);assert.equal(s.reveals.length,0);
  await s.click();assert(!s.video.hidden);assert(s.elements.fallback.hidden);
});
test("source links follow disclosure and clearing stops playback",async()=>{
  const s=setup();s.update(1);assert(s.elements.sourceLink.hidden);s.update(1,true);assert(!s.elements.sourceLink.hidden);
  await s.click();s.controller.update(null);s.video.ended=true;s.callbacks.ended();assert(s.elements.section.hidden);assert(s.video.paused);assert.equal(s.reveals.length,0);assert(s.elements.sourceLink.hidden);
});

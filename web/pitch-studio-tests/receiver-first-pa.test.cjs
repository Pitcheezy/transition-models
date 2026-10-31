"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const fs = require("node:fs"), path = require("node:path"), vm = require("node:vm");
const site = fs.existsSync(path.join(__dirname, "../dist")) ? path.join(__dirname, "../dist") : path.join(__dirname, "../pitch-studio");
const { validate, createSession, observation } = require(path.join(site, "receiver-contract.js"));
const demo = require(path.join(site, "receiver-demo-849843.js"));
const records = { window: {} };
vm.runInNewContext(fs.readFileSync(path.join(site, "data.js"), "utf8"), records);
test("real first PA uses original keys and unscaled pitch selection shares", () => {
  const data = validate(demo.packet);
  assert.deepEqual(data.decisions.map(d=>d.pitch_id), ["849843:1:1", "849843:1:2", "849843:1:3"]);
  assert.deepEqual(data.decisions.map(d=>d.pre.candidates[0].pitch_type), ["ST", "CH", "SI"]);
  assert.deepEqual(data.decisions.map(d=>d.pre.candidates[0].selection_probability), [.2747000042139988, .4070252755337158, .3303230709313974]);
  for(const d of data.decisions) assert(d.pre.candidates.reduce((s,c)=>s+c.selection_probability,0)<1);
  assert.equal(data.decisions[0].pre.candidates[0].zone_id, "low_middle");
});
test("first PA shows mitt only on third pitch after reveal and hides on rewind", () => {
  const session = createSession(demo.packet);
  for(let i=0;i<3;i++) {
    assert.equal(session.view().post,null);
    assert.equal(observation(session.view(),records.window.DEMO_DATA.pitches),null);
    session.reveal(true);
    const v=session.view(),mitt=observation(v,records.window.DEMO_DATA.pitches);
    assert.equal(v.pitcher.name,"Michael King"); assert.equal(v.batter.name,"Pete Crow-Armstrong");
    assert.equal(v.post.actual.pitch_type,["SI","ST","FF"][i]);
    assert.equal(mitt.status,i===2?"key_matched":"missing");
    assert.equal(mitt.x,i===2?-.05172667411468945:null);
    if(i<2) assert(session.next());
  }
  assert.equal(session.view().post.actual.result_label,"삼진");
  assert.equal(session.view().post.we.home_delta,.024007574284530042);
  assert.equal(session.next(),false); session.previous(); assert.equal(session.view().post,null);
});
test("generation provenance does not claim current backend version", () => {
  assert.equal(demo.packet.source.revision,"2eb718ef13024ad2d98d28e248388db7f8dc1bc9");
  assert.equal(demo.packet.source.exported_at,"2026-09-30T17:48:53+09:00");
  assert.match(demo.packet.source.model_id,/ARM-B P3/);
  assert.equal(demo.provenance.loaded_backend_commit,null);
  assert.equal(demo.originals.length,5);
  assert.equal(demo.packet.timeline.decisions.length,3);
  assert(!/100\.108\.|\/Users\/|serving_worktree|process_started|observer-zone-v1/.test(JSON.stringify(demo)));
});
test("only known named zones are accepted without conversion", () => {
  for(const z of ["high_left","high_middle","high_right","middle_left","middle_middle","middle_right","low_left","low_middle","low_right"]) {
    const p=structuredClone(demo.packet);p.timeline.decisions[0].pre.recommendation.candidates[0].zone_id=z;
    assert.equal(validate(p).decisions[0].pre.candidates[0].zone_id,z);
  }
  for(const z of ["outside","low_center","7","",{},10]) {
    const p=structuredClone(demo.packet);p.timeline.decisions[0].pre.recommendation.candidates[0].zone_id=z;
    assert.throws(()=>validate(p));
  }
});

// Exercise receiver.js with the real adapters/data. The small DOM shim does not
// render layout, autoplay policy, or a native decoder; browser QA covers those.
function domElement(tag = "div") {
  let ownText = "", value = "";
  const classes = new Set(), attributes = new Map(), listeners = new Map();
  const element = { tagName: tag.toUpperCase(), children: [], style: {}, dataset: {},
    hidden: false, disabled: false, complete: true, naturalWidth: 1280, focus() {}, reset() {},
    classList: { remove: name => classes.delete(name), contains: name => classes.has(name),
      toggle(name, force) { const on = force ?? !classes.has(name); on ? classes.add(name) : classes.delete(name); return on; } },
    append(child) { this.children.push(child); },
    replaceChildren(...children) { ownText = ""; this.children = children; },
    setAttribute(name, val) { attributes.set(name, String(val)); },
    getAttribute: name => attributes.get(name) ?? null,
    removeAttribute(name) { attributes.delete(name); },
    addEventListener(name, fn) { if (!listeners.has(name)) listeners.set(name, []); listeners.get(name).push(fn); },
    emit(name) { return [...(listeners.get(name) || [])].map(fn => fn({ target: element, type: name })); },
  };
  Object.defineProperties(element, {
    textContent: { get() { return ownText + this.children.map(child => child.textContent).join(""); }, set(text) { ownText = String(text); this.children = []; } },
    value: { get: () => value, set: text => { value = String(text); } },
    className: { get: () => [...classes].join(" "), set: text => { classes.clear(); for (const cls of String(text).split(/\s+/)) if (cls) classes.add(cls); } },
  });
  return element;
}

async function receiverDom(search = "?game=849843", { fullGameObservation, failAsset, expectError = false } = {}) {
  const html = fs.readFileSync(path.join(site, "receiver.html"), "utf8"), elements = new Map();
  for (const match of html.matchAll(/<([a-z][a-z0-9-]*)\b([^>]*\bid="([^"]+)"[^>]*)>/gi)) {
    const element = domElement(match[1]); element.hidden = /\bhidden\b/.test(match[2]); element.disabled = /\bdisabled\b/.test(match[2]);
    elements.set(match[3], element);
  }
  const get = id => { assert(elements.has(id), `HTML is missing ${id}`); return elements.get(id); };
  const video = get("pitch-video");
  Object.assign(video, { paused: true, ended: false, currentTime: 0, duration: 7, error: null,
    pause() { const playing = !this.paused; this.paused = true; if (playing) this.emit("pause"); },
    load() { this.currentTime = 0; this.ended = false; this.error = null; this.emit("emptied"); },
    play() { this.paused = false; this.ended = false; this.emit("play"); this.emit("playing"); return Promise.resolve(); },
  });
  const document = Object.assign(domElement(), { hidden: false, querySelectorAll: () => [], getElementById: get,
    createElement: tag => domElement(tag), createElementNS: (_, tag) => domElement(tag) });
  const events = domElement(), location = { search, pathname: "/receiver.html", hash: "" };
  const history = Object.fromEntries(["pushState", "replaceState"].map(method => [method, (_, title, url) => {
    const next = new URL(url, "https://example.test"); location.search = next.search; location.pathname = next.pathname;
  }]));
  const timers = new Map(); let timerId = 0;
  const context = vm.createContext({ document, location, history, console, crypto: require("node:crypto").webcrypto,
    TextDecoder, TextEncoder, URLSearchParams,
    setTimeout(fn) { const id = ++timerId; timers.set(id, fn); return id; }, clearTimeout: id => timers.delete(id),
    fetch: async name => {
      if (failAsset && String(name).split("?")[0] === failAsset) return { ok: false, status: 404, arrayBuffer: async () => new ArrayBuffer(0) };
      const bytes = fs.readFileSync(path.join(site, String(name).split("?")[0]));
      return { ok: true, arrayBuffer: async () => bytes.buffer.slice(bytes.byteOffset, bytes.byteOffset + bytes.byteLength) };
    },
  });
  context.window = context; context.addEventListener = events.addEventListener.bind(events);
  for (const match of html.matchAll(/<script src="([^"?]+)(?:\?[^"]*)?"[^>]*><\/script>/g)) {
    vm.runInContext(fs.readFileSync(path.join(site, match[1]), "utf8"), context, { filename: match[1] });
    // Override only the observation result; keep the real game/session and renderer.
    if (match[1] === "receiver-fullgame.js" && fullGameObservation)
      context.PitchReceiverFullGame.observation = fullGameObservation;
  }
  for (let attempt = 0; attempt < 100; attempt++) {
    if (!get("response-workspace").hidden || !get("import-error").hidden || search === "") break;
    await new Promise(resolve => setTimeout(resolve, 5));
  }
  if (!expectError) assert.equal(get("import-error").hidden, true, get("import-error").textContent);
  const fire = async (id, event = "click") => {
    assert.equal(get(id).disabled, false, `${id} must be enabled`);
    await Promise.all(get(id).emit(event)); await new Promise(resolve => setImmediate(resolve));
  };
  const select = async (id, value) => { get(id).value = value; await fire(id, "change"); };
  const end = async () => { video.currentTime = video.duration; video.ended = true; video.paused = true; video.emit("pause"); video.emit("ended"); };
  const shapes = name => get("location-plot").children.filter(c => (c.getAttribute("class") || "").split(/\s+/).includes(name));
  return { get, video, document, events, location, fire, select, end, shapes, timers };
}

function receivedShapes(s, className) {
  const descendants = element => [element, ...element.children.flatMap(descendants)];
  return descendants(s.get("received-post")).filter(element => element.classList.contains(className));
}

test("receiver hides actual point, outcome, and recorded zone when seeking back without resetting time", async () => {
  const s = await receiverDom(); await s.fire("play-pitch-video"); await s.end();
  assert.equal(s.get("received-post").hidden, false); assert.equal(s.shapes("location-actual").length, 1);
  s.video.currentTime = 1.25; s.video.ended = false; s.video.emit("seeking");
  assert.equal(s.video.currentTime, 1.25); assert.equal(s.get("received-post").hidden, true);
  assert.equal(s.shapes("location-actual").length, 0);
  assert.match(s.get("zone-status").textContent, /참고/);
  s.video.emit("seeked"); await s.video.play();
  assert.equal(s.get("received-post").hidden, true); assert.equal(s.video.currentTime, 1.25);
});

test("receiver manual and native replay clear an already disclosed result", async () => {
  for (const native of [false, true]) {
    const s = await receiverDom(); await s.fire("play-pitch-video"); await s.end();
    if (native) { s.video.currentTime = 0; await s.video.play(); }
    else await s.fire("play-pitch-video");
    assert.equal(s.get("received-post").hidden, true); assert.equal(s.shapes("location-actual").length, 0);
    assert.equal(s.video.currentTime, 0); assert.equal(s.video.paused, false);
  }
});

test("receiver perspective matches watch default and preserves source, time and reveal state",async()=>{
  const s=await receiverDom("?game=849843&pitch=849843%3A1%3A2");
  s.video.currentTime=1.2;
  await s.select("location-perspective","catcher");
  assert.equal(s.video.currentTime,1.2);assert.equal(s.shapes("location-actual").length,0);
  await s.fire("reveal-pitch");
  const x=Number(s.shapes("location-actual")[0].getAttribute("cx"));
  const result=s.get("received-post").textContent,src=s.video.getAttribute("src"),time=s.video.currentTime;
  await s.select("location-perspective","pitcher");
  const mirror=Number(s.shapes("location-actual")[0].getAttribute("cx"));
  assert(Math.abs(x+mirror-320)<1e-9);
  assert.equal(s.get("received-post").textContent,result);
  assert.equal(s.video.getAttribute("src"),src);assert.equal(s.video.currentTime,time);
  assert.match(s.get("location-plot").getAttribute("aria-label"),/투수 → 포수/);
});

test("receiver never draws or retains a mitt marker for missing, nonfinite or outside coordinates in either perspective", async () => {
  let x = .75;
  const s = await receiverDom("?game=849843", {
    fullGameObservation: view => view.revealed ? { status: "estimated", x } : { status: "missing", x: null },
  });
  assert.equal(receivedShapes(s, "mitt-dot").length, 0);
  await s.fire("reveal-pitch");
  for (const invalid of [null, NaN, Infinity, -Infinity, -2.0001, 2.0001]) {
    x = .75;
    await s.select("location-perspective", "pitcher");
    assert.equal(receivedShapes(s, "mitt-dot").length, 1, "start with a visible point to test stale-marker removal");
    x = invalid;
    for (const perspective of ["catcher", "pitcher"]) {
      await s.select("location-perspective", perspective);
      assert.equal(s.get("received-post").hidden, false);
      assert.equal(receivedShapes(s, "mitt-dot").length, 0, String(x) + " in " + perspective);
      assert.equal(receivedShapes(s, "mitt-horizontal").length, 0, "no empty or clamped mitt graphic");
      assert.equal(s.shapes("location-actual").length, 1, "invalid mitt input must not hide the separately recorded actual pitch");
    }
  }
});

test("receiver mirrors valid mitt positions including zero and exact endpoints without changing raw values", async () => {
  let x = -.75;
  const s = await receiverDom("?game=849843", {
    fullGameObservation: view => view.revealed ? { status: "estimated", x } : { status: "missing", x: null },
  });
  for (const perspective of ["pitcher", "catcher"]) {
    await s.select("location-perspective", perspective);
    assert.equal(receivedShapes(s, "mitt-dot").length, 0);
  }
  await s.fire("reveal-pitch");
  for (const [raw, catcher, pitcher] of [[-2, 0, 100], [-.75, 31.25, 68.75], [0, 50, 50], [.75, 68.75, 31.25], [2, 100, 0]]) {
    x = raw;
    for (const [perspective, expected] of [["catcher", catcher], ["pitcher", pitcher]]) {
      await s.select("location-perspective", perspective);
      const dots = receivedShapes(s, "mitt-dot"), graphics = receivedShapes(s, "mitt-horizontal");
      assert.equal(dots.length, 1); assert.equal(graphics.length, 1);
      assert.equal(dots[0].style.left, expected + "%");
      assert.ok(graphics[0].getAttribute("aria-label").includes("원본 미트 x " + raw.toFixed(4) + " ft"));
      assert.equal(x, raw);
    }
  }
  await s.fire("next-pitch");
  assert.equal(s.get("received-post").hidden, true);
  assert.equal(receivedShapes(s, "mitt-dot").length, 0);
});

test("receiver decoder failure clears disclosed results and interrupts continuation", async () => {
  const s = await receiverDom(); await s.fire("start-pa-sequence"); await s.end();
  assert.equal(s.timers.size, 1);
  s.video.error = { code: 4 }; s.video.emit("error");
  assert.equal(s.get("received-post").hidden, true); assert.equal(s.shapes("location-actual").length, 0);
  assert.equal(s.timers.size, 0); assert.equal(s.get("stop-pa-sequence").disabled, true);
});

test("receiver-to-watch links carry the selected full-game pitch through navigation and history", async () => {
  const s = await receiverDom("?game=849843&pitch=849843%3A2%3A1");
  const check = key => {
    for (const id of ["receiver-watch-current", "receiver-watch-featured"]) {
      assert.equal(s.get(id).hidden, false);
      const target = new URL(s.get(id).href, "https://example.test/");
      assert.equal(target.pathname, "/watch.html"); assert.equal(target.searchParams.get("game"), "849843");
      assert.equal(target.searchParams.get("pitch"), key);
    }
  };
  check("849843:2:1"); await s.fire("reveal-pitch"); await s.fire("next-pitch"); check("849843:2:2");
  s.location.search = "?game=849843&pitch=849843%3A1%3A3";
  await Promise.all(s.events.emit("popstate")); check("849843:1:3");
  assert.equal(s.get("received-post").hidden, true);
});

test("archive and imported sample cannot masquerade as the full-game watch data source", async () => {
  const s = await receiverDom("?archive=first-pa&pitch=849843%3A1%3A3");
  for (const id of ["receiver-watch-current", "receiver-watch-featured"]) assert.equal(s.get(id).hidden, true);
  await s.fire("load-full-game");
  assert.equal(s.get("receiver-watch-current").hidden, false);
  await s.fire("try-sample");
  for (const id of ["receiver-watch-current", "receiver-watch-featured"]) assert.equal(s.get(id).hidden, true);
  assert.equal(s.get("pitch-video").getAttribute("src"), null);
});

for(const gameId of [849845,823407]){
  test(`receiver ${gameId} labels absent recommendations and preserves its route and reveal gate`,async()=>{
    const s=await receiverDom(`?game=${gameId}`);
    assert.match(s.get('source-badge').textContent,/공식 경기 기록/);
    assert.match(s.get('recommendation-status').textContent,/추천 파일 미수신/);
    assert.equal(s.get('legacy-provenance').hidden,true);
    assert.equal(s.shapes('location-actual').length,0);
    assert(s.get('receiver-watch-current').href.includes(`game=${gameId}`));
    await s.fire('play-pitch-video');await s.end();
    assert.equal(s.shapes('location-actual').length,1);
    await s.fire('load-full-game');
    assert(s.location.search.includes(`game=${gameId}`));
    assert.equal(s.shapes('location-actual').length,0);
  });
}
test('receiver automatic ball can reveal the record without inventing video or coordinates',async()=>{
  const s=await receiverDom('?game=823407&pitch=823407%3A35%3A4');
  assert.doesNotMatch(s.get('pitch-video-missing-reason').textContent,/자동 볼/);
  assert.match(s.get('pitch-video-missing-reason').textContent,/투구 영상이 없습니다/);
  assert.equal(s.video.getAttribute('src'),null);
  await s.fire('reveal-pitch');
  assert.equal(s.get('received-post').hidden,false);
  assert.match(s.get('pitch-video-missing-reason').textContent,/자동 볼 기록/);
  assert.equal(s.shapes('location-actual').length,0);
  assert.equal(s.get('received-post').textContent.includes('고의사구'),true);
});
test('receiver header, dates, counts and notes describe the loaded game only',async()=>{
  const s=await receiverDom('?game=823407&pitch=823407%3A1%3A1');
  const title=s.get('featured-title');
  assert.equal(title.children.filter(child=>child.tagName==='IMG').length,2);
  assert.match(title.textContent,/탬파베이 레이스\s+@\s+필라델피아 필리스/);
  assert.match(s.get('pitch-identity').textContent,/^현지 2026\.09\.26 · 한국 09\.27 · /);
  assert.equal(s.get('featured-coverage').textContent,'88타석 · 실제 투구 355구 + 자동 볼 4건');
  assert.match(s.get('video-coverage').textContent,/355 \/ 355구 \(자동 볼 4건 제외\)/);
  assert.equal(s.get('scientific-note-featured').hidden,true);
  assert.equal(s.get('scientific-note-stage').hidden,true);
  const c=await receiverDom('?game=849843&pitch=849843%3A1%3A1');
  assert.equal(c.get('featured-title').children.filter(child=>child.tagName==='IMG').length,2);
  assert.match(c.get('pitch-identity').textContent,/^현지 2026\.09\.29 · 한국 09\.30 · /);
  assert.equal(c.get('scientific-note-featured').hidden,false);
});

test('a failed added game never shows the Cubs heading or the recommendation notes',async()=>{
  const s=await receiverDom('?game=849845',{failAsset:'game-849845.json',expectError:true});
  assert.equal(s.get('import-error').hidden,false);
  assert.equal(s.get('featured-title').textContent,'경기를 불러오지 못했습니다');
  assert.equal(s.get('legacy-provenance').hidden,true);
  assert.equal(s.get('scientific-note-featured').hidden,true);
  assert.equal(s.get('scientific-note-stage').hidden,true);
});
test('team names in the rebuilt heading keep full contrast; only the @ stays muted',async()=>{
  const s=await receiverDom('?game=849845&pitch=849845%3A1%3A1');
  const spans=s.get('featured-title').children.filter(child=>child.tagName==='SPAN');
  assert.deepEqual(spans.map(span=>span.className),['featured-team','','featured-team']);
});
test('after the sample, opening the full game returns to the last real game',async()=>{
  const s=await receiverDom('?game=849845&pitch=849845%3A1%3A1');
  await s.fire('try-sample');
  assert.equal(s.get('featured-title').textContent,'합성 연결 테스트 자료');
  assert.equal(s.get('legacy-provenance').hidden,true);
  await s.fire('load-full-game');
  assert.match(s.get('import-status').textContent,/필라델피아 필리스 @ 애틀랜타 브레이브스/);
});
test('the archive first plate appearance keeps its Korean heading, logos and provenance',async()=>{
  const s=await receiverDom('?archive=first-pa&pitch=849843%3A1%3A3');
  const title=s.get('featured-title');
  assert.equal(title.children.filter(child=>child.tagName==='IMG').length,2);
  assert.match(title.textContent,/시카고 컵스\s+@\s+샌디에이고 파드리스/);
  assert.equal(s.get('legacy-provenance').hidden,false);
  assert.equal(s.get('featured-date').textContent,'현지 2026.09.29 · 한국 09.30 · 저장 경기');
});
test('retrying after a different game fails reopens that game, not the previous one',async()=>{
  const s=await receiverDom('?game=849845&pitch=849845%3A1%3A1',{failAsset:'game-823407.json'});
  s.location.search='?game=823407&pitch=823407%3A1%3A1';
  await Promise.all(s.events.emit('popstate')||[]);
  for(let i=0;i<50&&s.get('import-error').hidden;i++) await new Promise(resolve=>setTimeout(resolve,5));
  assert.equal(s.get('featured-title').textContent,'경기를 불러오지 못했습니다');
  await s.fire('load-full-game');
  for(let i=0;i<50&&s.get('import-error').hidden;i++) await new Promise(resolve=>setTimeout(resolve,5));
  assert.equal(new URLSearchParams(s.location.search).get('game'),'823407');
  assert.equal(s.get('featured-title').textContent,'경기를 불러오지 못했습니다');
});
test('the sample clears the previous game counts and notes',async()=>{
  const s=await receiverDom('?game=849845&pitch=849845%3A1%3A1');
  await s.fire('try-sample');
  assert.equal(s.get('featured-coverage').textContent,'합성 자료 · 실제 경기 아님');
  assert.equal(s.get('scientific-note-featured').hidden,true);
});

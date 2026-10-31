"use strict";
// Real Chrome, private local files only. Boundary seeks and synthetic stale events
// are recorded separately from the first three complete video playbacks.
const fs=require("node:fs"),path=require("node:path"),assert=require("node:assert/strict");
const {chromium}=require("playwright");
const origin=new URL(process.argv[2]||"");
if(origin.protocol!=="http:"||!["127.0.0.1","localhost","[::1]"].includes(origin.hostname)||origin.username||origin.password)throw Error("loopback HTTP origin required");
const sourceOverlay=process.argv[4]?path.resolve(process.argv[4]):null;
const output=path.resolve(process.argv[3]||"outputs/exhibition_1101/player-qa");
const receipt={source_mode:sourceOverlay?"local source overlay over immutable clip pack":"pack files",kind:"local_chrome_private_clip_acceptance",at:new Date().toISOString(),checks:[],external_requests:[],page_errors:[],limitations:["Not actual iPhone Safari","Not automatic cross-monitor synchronization","Only first three clips played completely; boundary/error cases below use explicit seek or synthetic events","Not all 261 videos visually reviewed","Persisted lifecycle events are simulated; actual browser BFCache eligibility is not asserted"]};
let browser,context,page;
async function check(name,fn){try{const detail=await fn();receipt.checks.push({name,passed:true,detail:detail??null});console.log("PASS",name);}catch(error){receipt.checks.push({name,passed:false,error:String(error)});throw error;}}
async function select(index){await page.locator("#global").selectOption(String(index));await page.waitForFunction(i=>document.querySelector("#global").value===String(i),index);}
async function nearEnd(){await page.locator("video").evaluate(async v=>{if(v.readyState<1)await new Promise((resolve,reject)=>{v.addEventListener("loadedmetadata",resolve,{once:true});v.addEventListener("error",reject,{once:true});});v.pause();v.currentTime=Math.max(0,v.duration-.2);});await page.waitForFunction(()=>{const v=document.querySelector("video");return !v.seeking&&v.currentTime>v.duration-.4;});}
(async()=>{fs.mkdirSync(output,{recursive:true});try{
 browser=await chromium.launch({channel:"chrome",headless:true});
 context=await browser.newContext({viewport:{width:1440,height:1050}});
 await context.route("**/*",route=>{const url=new URL(route.request().url());if(url.origin===origin.origin){const name=url.pathname.slice(1);if(sourceOverlay&&["index.html","core.js","player.js","player.css"].includes(name||"index.html"))return route.fulfill({path:path.join(sourceOverlay,name||"index.html")});return route.continue();}receipt.external_requests.push(url.origin);return route.abort();});
 page=await context.newPage();page.on("pageerror",e=>receipt.page_errors.push(e.message));
 const manifestResponse=await context.request.get(new URL("registry.json",origin).href);assert.equal(manifestResponse.status(),200);const manifest=await manifestResponse.json();
 await check("initial target paused, 262 choices, safe paths",async()=>{
  await page.goto(new URL("?pitch=849843%3A1%3A1",origin).href);await page.waitForFunction(()=>document.querySelector("#global").options.length===262);
  assert.equal(await page.locator("#pitch-key").textContent(),"849843:1:1");assert.equal(await page.locator("video").evaluate(v=>v.paused),true);assert.equal(await page.locator("#stop").isDisabled(),true);
  assert.equal(await page.locator("#pa option").count(),71);return{pitches:262,plate_appearances:71};
 });
 await check("first three clips played completely in sequence",async()=>{
  await page.evaluate(()=>{window.qaEnded=[];document.addEventListener("ended",e=>{if(e.target.tagName!=="VIDEO")return;window.qaEnded.push({key:document.querySelector("#pitch-key").textContent,time:e.target.currentTime,duration:e.target.duration,rate:e.target.playbackRate});if(window.qaEnded.length===3)document.querySelector("#stop").click();},true);});
  await page.locator("#speed").selectOption("2");await page.locator("#start").click();
  await page.waitForFunction(()=>window.qaEnded?.length===3,{},{timeout:90000});const ended=await page.evaluate(()=>window.qaEnded);
  assert.deepEqual(ended.map(e=>e.key),["849843:1:1","849843:1:2","849843:1:3"]);for(const row of ended)assert.ok(Math.abs(row.time-row.duration)<.2);assert.equal(await page.locator("#stop").isDisabled(),true);
  // The chosen speed must survive the chained clip replacement (the load algorithm resets playbackRate to defaultPlaybackRate).
  assert.deepEqual(ended.map(e=>e.rate),[2,2,2]);return ended;
 });
 await check("selected speed carries into the next clip after 다음 공",async()=>{
  await page.locator("#next").click();await page.waitForFunction(()=>document.querySelector("video")?.readyState>=1);
  const rates=await page.locator("video").evaluate(v=>[v.playbackRate,v.defaultPlaybackRate]);assert.deepEqual(rates,[2,2]);assert.equal(await page.locator("#speed").inputValue(),"2");return{key:await page.locator("#pitch-key").textContent(),rates};
 });
 await check("labels carry monitor 1 cues: inning/half (Bot→말), batter, N구; no PA index",async()=>{
  const half=p=>p.half==="Top"?"초":"말",labelOf=p=>`${p.inning}회 ${half(p)} · ${p.batter} · ${p.pitch_number}구`;
  const bottom=manifest.pitches.findIndex(p=>p.half!=="Top");assert.ok(bottom>0);await select(bottom);
  assert.equal(await page.locator("#identity").textContent(),labelOf(manifest.pitches[bottom]));assert.match(await page.locator("#identity").textContent(),/^\d+회 말 · /);
  const paTexts=await page.locator("#pa option").evaluateAll(o=>o.map(x=>[x.value,x.textContent]));assert.equal(paTexts.length,71);
  for(const [value,text]of paTexts){const first=manifest.pitches.find(p=>String(p.pa_index)===value);assert.equal(text,`${first.inning}회 ${half(first)} · ${first.batter}`);}
  const globalTexts=await page.locator("#global option").evaluateAll(o=>o.map(x=>x.textContent));assert.equal(globalTexts.length,262);
  globalTexts.forEach((text,i)=>{const p=manifest.pitches[i];assert.ok(text.startsWith(`${p.game_pitch_number} · ${labelOf(p)}`),text);});
  for(const text of[...paTexts.map(x=>x[1]),...globalTexts])assert.doesNotMatch(text,/\bBot\b|PA \d/);
  const copy=await page.evaluate(()=>document.querySelector(".intro small").textContent+" "+document.querySelector("aside").textContent);assert.match(copy,/이닝.*타자.*N구/s);assert.doesNotMatch(copy,/타석·구 번호/);
  assert.equal(await page.locator("#pitch-key").textContent(),manifest.pitches[bottom].pitch_key);
  return{bottom_half_example:manifest.pitches[bottom].pitch_key,identity:labelOf(manifest.pitches[bottom]),pa_options:paTexts.length,global_options:globalTexts.length};
 });
 await check("Space and arrows work right after a mouse click on 다음 공 / 이전 공",async()=>{
  await select(5);await page.waitForFunction(()=>document.querySelector("video")?.readyState>=1);
  await page.locator("#next").click();await page.waitForFunction(k=>document.querySelector("#pitch-key").textContent===k,manifest.pitches[6].pitch_key);
  assert.notEqual(await page.evaluate(()=>document.activeElement?.id),"next");
  await page.keyboard.press("Space");await page.waitForFunction(()=>!document.querySelector("video").paused);assert.equal(await page.locator("#pitch-key").textContent(),manifest.pitches[6].pitch_key);
  await page.keyboard.press("Space");await page.waitForFunction(()=>document.querySelector("video").paused);
  await page.keyboard.press("ArrowLeft");await page.waitForFunction(k=>document.querySelector("#pitch-key").textContent===k,manifest.pitches[5].pitch_key);
  await page.locator("#prev").click();await page.waitForFunction(k=>document.querySelector("#pitch-key").textContent===k,manifest.pitches[4].pitch_key);
  await page.keyboard.press("ArrowRight");await page.waitForFunction(k=>document.querySelector("#pitch-key").textContent===k,manifest.pitches[5].pitch_key);
  assert.equal(await page.locator("video").evaluate(v=>v.paused),true);return{space_after_click_played_same_pitch:true,arrows_after_click_moved_one_pitch:true};
 });
 await check("manual selection rejects detached old-video ended/error",async()=>{
  await page.evaluate(()=>window.qaOldVideo=document.querySelector("video"));await select(3);const key=await page.locator("#pitch-key").textContent();
  await page.evaluate(()=>{window.qaOldVideo.dispatchEvent(new Event("ended"));window.qaOldVideo.dispatchEvent(new Event("error"));});assert.equal(await page.locator("#pitch-key").textContent(),key);assert.equal(await page.locator("video").evaluate(v=>v.paused),true);return{synthetic_events:true,key};
 });
 await check("PA boundary chain transition (seek-assisted)",async()=>{
  const index=manifest.pitches.findIndex((p,i)=>i+1<manifest.pitches.length&&p.pa_index!==manifest.pitches[i+1].pa_index);await select(index);await nearEnd();await page.locator("#start").click();await page.waitForFunction(key=>document.querySelector("#pitch-key").textContent===key,manifest.pitches[index+1].pitch_key);await page.locator("#stop").click();return{from:manifest.pitches[index].pitch_key,to:manifest.pitches[index+1].pitch_key,seek_assisted:true};
 });
 await check("excluded clip stops chain without skip (seek-assisted)",async()=>{
  const index=manifest.pitches.findIndex(p=>p.status==="excluded");await select(index-1);await nearEnd();await page.locator("#start").click();await page.waitForFunction(key=>document.querySelector("#pitch-key").textContent===key,manifest.pitches[index].pitch_key);assert.equal(await page.locator("video").count(),0);assert.equal(await page.locator("#start").isDisabled(),true);assert.equal(await page.locator("#stop").isDisabled(),true);assert.match(await page.locator("#status").textContent(),/제외/);return{excluded:manifest.pitches[index].pitch_key,seek_assisted:true};
 });
 await check("missing media error and explicit retry",async()=>{
  const clip=new URL(manifest.pitches[0].src,origin).href;await page.route(clip,route=>route.abort());await select(0);await page.waitForFunction(()=>document.querySelector("#retry").hidden===false);assert.equal(await page.locator("#start").isDisabled(),true);
  const errorText=await page.locator("#status").textContent();assert.match(errorText,/serve\.py 터미널/);assert.doesNotMatch(errorText,/파일을 확인/);
  await page.locator("h1").click();await page.keyboard.press("Space");await page.waitForTimeout(300);assert.equal(await page.locator("#status").textContent(),errorText);// play() rejection must not replace the error text with the autoplay hint
  await page.unroute(clip);await page.locator("#retry").click();await page.waitForFunction(()=>document.querySelector("video")?.readyState>=1);assert.equal(await page.locator("#retry").isHidden(),true);
  assert.equal(await page.locator("video").evaluate(v=>v.playbackRate),2);return{network_failure_injected:true,error_text_points_to_server:true,speed_after_retry:2};
 });
 await check("stopping while the clip request is still pending keeps the stop status, not the autoplay hint",async()=>{
  // pause() rejects the pending play() with AbortError; that is the operator's own stop, not an autoplay refusal.
  const clip=new URL(manifest.pitches[2].src,origin).href;let release;const held=new Promise(resolve=>{release=resolve;});await page.route(clip,async route=>{await held;await route.continue().catch(()=>{});});// the browser may cancel a held media request after pause()
  try{await select(2);await page.waitForFunction(()=>document.querySelector("video")&&document.querySelector("#retry").hidden);await page.locator("#start").click();await page.waitForTimeout(150);await page.locator("#stop").click();await page.waitForTimeout(500);
   assert.doesNotMatch(await page.locator("#status").textContent(),/자동 재생이 허용되지/);assert.equal(await page.locator("#stop").isDisabled(),true);assert.equal(await page.locator("#start").isDisabled(),false);}
  finally{release();await page.unroute(clip);}
  await page.waitForFunction(()=>document.querySelector("video")?.readyState>=1);return{clip_request_held_during_start_then_stop:true};
 });
 await check("native seek cancels chain",async()=>{await page.locator("#start").click();await page.waitForFunction(()=>!document.querySelector("video").paused);await page.locator("video").evaluate(v=>{v.currentTime=1;});await page.waitForFunction(()=>document.querySelector("#stop").disabled);await page.locator("video").evaluate(v=>v.pause());});
 await check("persisted restoration resets same pitch paused; immediate start before metadata works (simulated lifecycle)",async()=>{
  await select(1);await page.waitForFunction(()=>document.querySelector("video")?.readyState>=1);await page.locator("video").evaluate(v=>{v.currentTime=1.2;});await page.waitForFunction(()=>!document.querySelector("video").seeking);
  const clip=new URL(manifest.pitches[1].src,origin).href;let release;const delayed=new Promise(resolve=>{release=resolve;});await page.route(clip,async route=>{await delayed;await route.continue();});
  try {
   await page.evaluate(()=>{window.qaBeforeRestore=document.querySelector("video");window.dispatchEvent(new PageTransitionEvent("pagehide",{persisted:true}));window.dispatchEvent(new PageTransitionEvent("pageshow",{persisted:true}));});
   assert.equal(await page.locator("#pitch-key").textContent(),"849843:1:2");assert.equal(await page.locator("video").evaluate(v=>v.paused&&v.currentTime===0&&v!==window.qaBeforeRestore),true);assert.equal(await page.locator("#stop").isDisabled(),true);
   await page.evaluate(()=>{window.qaBeforeRestore.dispatchEvent(new Event("ended"));window.qaBeforeRestore.dispatchEvent(new Event("error"));});assert.equal(await page.locator("#pitch-key").textContent(),"849843:1:2");
   await page.locator("#start").click();assert.equal(await page.locator("#stop").isDisabled(),false);release();await page.waitForFunction(()=>document.querySelector("video")?.readyState>=2&&!document.querySelector("video").paused);assert.equal(await page.locator("#stop").isDisabled(),false);
   await page.waitForFunction(()=>document.querySelector("#pitch-key").textContent==="849843:1:3",{},{timeout:20000});await page.locator("#stop").click();
  }finally{release();await page.unroute(clip);}
  return{simulated_persisted_events:true,restored_seconds:0,actual_bfcache_restore:"not measured by this scenario",metadata_delayed:true,immediate_start_before_metadata:true,restored_clip_completed_without_seek:true};
 });
 await check("last clip ends without wrapping (seek-assisted)",async()=>{await select(261);await nearEnd();await page.locator("#start").click();await page.waitForFunction(()=>document.querySelector("#status").textContent.includes("마지막"));assert.equal(await page.locator("#global").inputValue(),"261");assert.equal(await page.locator("#next").isDisabled(),true);return{seek_assisted:true};});
 await check("restart ended clip preserves chain mode",async()=>{await page.locator("#start").click();await page.waitForFunction(()=>!document.querySelector("video").paused);assert.equal(await page.locator("#stop").isDisabled(),false);await page.locator("#stop").click();});
 await check("desktop and phone layouts",async()=>{await select(1);await page.waitForFunction(()=>document.querySelector("video")?.readyState>=2);await page.locator("video").evaluate(v=>v.play());await page.waitForFunction(()=>document.querySelector("video").currentTime>.3);await page.locator("video").evaluate(v=>v.pause());for(const width of[1440,390,320]){await page.setViewportSize({width,height:width===1440?1050:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:path.join(output,`player-${width}.png`),fullPage:true});}return[1440,390,320];});
 await check("keyboard selection and direct URL target",async()=>{await page.locator("h1").click();await page.keyboard.press("ArrowRight");assert.equal(await page.locator("#global").inputValue(),"2");await page.goto(new URL("?pitch=849843%3A69%3A2",origin).href);await page.waitForFunction(()=>document.querySelector("#pitch-key").textContent==="849843:69:2");assert.equal(await page.locator("video").count(),0);});
 await check("unknown ?pitch= falls back to the first pitch with a visible notice; the player stays usable",async()=>{
  await page.goto(new URL("?pitch=849843%3A999%3A1",origin).href);await page.waitForFunction(()=>document.querySelector("#status").textContent.includes("등록되지 않은"));
  const status=await page.locator("#status").textContent();assert.match(status,/849843:999:1/);assert.doesNotMatch(status,/ZIP/);
  assert.equal(await page.locator("#pitch-key").textContent(),manifest.pitches[0].pitch_key);assert.equal(await page.locator("#global").isDisabled(),false);assert.equal(await page.locator("#global option").count(),262);assert.equal(await page.locator("video").count(),1);
  assert.equal(await page.evaluate(()=>new URLSearchParams(location.search).get("pitch")),manifest.pitches[0].pitch_key);return{status};
 });
 await check("전체 화면 covers the stage: identity and pitch key stay visible and survive clip replacement",async()=>{
  await page.locator("h1").click();await page.locator("#full").click();await page.waitForFunction(()=>document.fullscreenElement?.id==="stage");
  const visible=()=>page.evaluate(()=>["identity","pitch-key"].map(id=>{const el=document.getElementById(id),r=el.getBoundingClientRect(),hit=document.elementFromPoint(r.left+r.width/2,r.top+r.height/2);return{id,inViewport:r.width>0&&r.bottom<=innerHeight&&r.top>=0,hit:hit===el||el.contains(hit)||(hit&&hit.contains(el))};}));
  const before=await visible();assert.deepEqual(before.map(x=>x.inViewport&&x.hit),[true,true]);const identityBefore=await page.locator("#identity").textContent();
  await page.keyboard.press("ArrowRight");await page.waitForFunction(k=>document.querySelector("#pitch-key").textContent===k,manifest.pitches[1].pitch_key);
  assert.equal(await page.evaluate(()=>document.fullscreenElement?.id),"stage");assert.notEqual(await page.locator("#identity").textContent(),identityBefore);
  const after=await visible();assert.deepEqual(after.map(x=>x.inViewport&&x.hit),[true,true]);
  await page.evaluate(()=>document.exitFullscreen());await page.waitForFunction(()=>!document.fullscreenElement);return{fullscreen_element:"stage",identity_visible_before_and_after_clip_replacement:true};
 });
 await check("no external calls or unhandled page errors",async()=>{assert.deepEqual(receipt.external_requests,[]);assert.deepEqual(receipt.page_errors,[]);});
 receipt.passed=true;
 }catch(error){receipt.passed=false;receipt.error=String(error);if(page)await page.screenshot({path:path.join(output,"failure.png"),fullPage:true}).catch(()=>{});process.exitCode=1;}
 finally{await context?.close();await browser?.close();fs.writeFileSync(path.join(output,"receipt.json"),JSON.stringify(receipt,null,2)+"\n");console.log(JSON.stringify({passed:receipt.passed,checks:receipt.checks.length,output}));}
})();

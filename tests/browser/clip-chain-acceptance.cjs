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
  await page.evaluate(()=>{window.qaEnded=[];document.addEventListener("ended",e=>{if(e.target.tagName!=="VIDEO")return;window.qaEnded.push({key:document.querySelector("#pitch-key").textContent,time:e.target.currentTime,duration:e.target.duration});if(window.qaEnded.length===3)document.querySelector("#stop").click();},true);});
  await page.locator("#speed").selectOption("2");await page.locator("#start").click();
  await page.waitForFunction(()=>window.qaEnded?.length===3,{},{timeout:90000});const ended=await page.evaluate(()=>window.qaEnded);
  assert.deepEqual(ended.map(e=>e.key),["849843:1:1","849843:1:2","849843:1:3"]);for(const row of ended)assert.ok(Math.abs(row.time-row.duration)<.2);assert.equal(await page.locator("#stop").isDisabled(),true);return ended;
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
  const clip=new URL(manifest.pitches[0].src,origin).href;await page.route(clip,route=>route.abort());await select(0);await page.waitForFunction(()=>document.querySelector("#retry").hidden===false);assert.equal(await page.locator("#start").isDisabled(),true);await page.unroute(clip);await page.locator("#retry").click();await page.waitForFunction(()=>document.querySelector("video")?.readyState>=1);assert.equal(await page.locator("#retry").isHidden(),true);return{network_failure_injected:true};
 });
 await check("native seek cancels chain",async()=>{await page.locator("#start").click();await page.waitForFunction(()=>!document.querySelector("video").paused);await page.locator("video").evaluate(v=>{v.currentTime=1;});await page.waitForFunction(()=>document.querySelector("#stop").disabled);await page.locator("video").evaluate(v=>v.pause());});
 await check("persisted page restoration rebinds events and retains paused pitch/time (simulated lifecycle)",async()=>{
  await select(1);await page.waitForFunction(()=>document.querySelector("video")?.readyState>=1);await page.locator("video").evaluate(v=>{v.currentTime=1.2;});await page.waitForFunction(()=>!document.querySelector("video").seeking);
  await page.evaluate(()=>{window.qaBeforeRestore=document.querySelector("video");window.dispatchEvent(new PageTransitionEvent("pagehide",{persisted:true}));window.dispatchEvent(new PageTransitionEvent("pageshow",{persisted:true}));});
  await page.waitForFunction(()=>{const v=document.querySelector("video");return v!==window.qaBeforeRestore&&v.readyState>=1&&!v.seeking&&Math.abs(v.currentTime-1.2)<.1;});assert.equal(await page.locator("#pitch-key").textContent(),"849843:1:2");assert.equal(await page.locator("video").evaluate(v=>v.paused),true);assert.equal(await page.locator("#stop").isDisabled(),true);
  await page.evaluate(()=>{window.qaBeforeRestore.dispatchEvent(new Event("ended"));window.qaBeforeRestore.dispatchEvent(new Event("error"));});assert.equal(await page.locator("#pitch-key").textContent(),"849843:1:2");
  await nearEnd();await page.locator("#start").click();await page.waitForFunction(()=>document.querySelector("#pitch-key").textContent==="849843:1:3");await page.locator("#stop").click();return{simulated_persisted_events:true,restored_seconds:1.2,actual_bfcache_restore:"not measured by this scenario",seek_assisted_end:true};
 });
 await check("last clip ends without wrapping (seek-assisted)",async()=>{await select(261);await nearEnd();await page.locator("#start").click();await page.waitForFunction(()=>document.querySelector("#status").textContent.includes("마지막"));assert.equal(await page.locator("#global").inputValue(),"261");assert.equal(await page.locator("#next").isDisabled(),true);return{seek_assisted:true};});
 await check("restart ended clip preserves chain mode",async()=>{await page.locator("#start").click();await page.waitForFunction(()=>!document.querySelector("video").paused);assert.equal(await page.locator("#stop").isDisabled(),false);await page.locator("#stop").click();});
 await check("desktop and phone layouts",async()=>{await select(1);await page.waitForFunction(()=>document.querySelector("video")?.readyState>=2);await page.locator("video").evaluate(v=>v.play());await page.waitForFunction(()=>document.querySelector("video").currentTime>.3);await page.locator("video").evaluate(v=>v.pause());for(const width of[1440,390,320]){await page.setViewportSize({width,height:width===1440?1050:844});assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);await page.screenshot({path:path.join(output,`player-${width}.png`),fullPage:true});}return[1440,390,320];});
 await check("keyboard selection and direct URL target",async()=>{await page.locator("h1").click();await page.keyboard.press("ArrowRight");assert.equal(await page.locator("#global").inputValue(),"2");await page.goto(new URL("?pitch=849843%3A69%3A2",origin).href);await page.waitForFunction(()=>document.querySelector("#pitch-key").textContent==="849843:69:2");assert.equal(await page.locator("video").count(),0);});
 await check("unknown ID fails explicitly rather than silently changing pitch",async()=>{await page.goto(new URL("?pitch=849843%3A999%3A1",origin).href);await page.waitForFunction(()=>document.querySelector("#status").textContent.includes("등록되지 않은"));assert.equal(await page.locator("#global").isDisabled(),true);});
 await check("no external calls or unhandled page errors",async()=>{assert.deepEqual(receipt.external_requests,[]);assert.deepEqual(receipt.page_errors,[]);});
 receipt.passed=true;
 }catch(error){receipt.passed=false;receipt.error=String(error);if(page)await page.screenshot({path:path.join(output,"failure.png"),fullPage:true}).catch(()=>{});process.exitCode=1;}
 finally{await context?.close();await browser?.close();fs.writeFileSync(path.join(output,"receipt.json"),JSON.stringify(receipt,null,2)+"\n");console.log(JSON.stringify({passed:receipt.passed,checks:receipt.checks.length,output}));}
})();

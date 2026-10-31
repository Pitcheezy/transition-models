"use strict";
const {test} = require("node:test");
const assert = require("node:assert/strict");
const {validateRegistry,createState,transition:t} = require("../../web/clip-chain/core.js");
function fixture(){
 let n=0; const pitches=[];
 for(let pa=1;pa<=71;pa++)for(let pitch=1;pitch<=(pa<=49?4:3);pitch++){
   n++;const excluded=pa===69&&pitch===2;
   pitches.push({pitch_key:`849843:${pa}:${pitch}`,game_pitch_number:n,pa_index:pa,pitch_number:pitch,inning:Math.ceil(pa/8),half:"Top",batter:"Batter",pitcher:"Pitcher",status:excluded?"excluded":"available",reason:excluded?"pitch_type_mismatch":null,src:excluded?null:`clips/${pa}_${pitch}_id.mp4`,bytes:excluded?null:100,sha256:excluded?null:"a".repeat(64),duration_s:excluded?null:6});
 } return {schema:"clip-chain-v1",game_pk:849843,pitches};
}
test("accepts complete261clip/262pitch registry and starts paused",()=>{const r=fixture();assert.equal(validateRegistry(r),r);assert.deepEqual(createState(r),{index:0,epoch:0,chain:false,mode:"paused"});});
test("query selects exact ID and invalid ID fails rather than showing another pitch",()=>{const r=fixture();assert.equal(r.pitches[createState(r,"849843:2:3").index].pitch_key,"849843:2:3");assert.throws(()=>createState(r,"849843:999:1"));});
for(const [name,mutate]of[
 ["missing row",r=>r.pitches.pop()],
 ["duplicate ID",r=>r.pitches[1].pitch_key=r.pitches[0].pitch_key],
 ["wrong game",r=>r.game_pk=849845],
 ["different key game",r=>r.pitches[0].pitch_key="849845:1:1"],
 ["sequence mismatch",r=>r.pitches[1].game_pitch_number=17],
 ["pa mismatch",r=>r.pitches[0].pa_index=2],
 ["duplicate clip",r=>r.pitches[1].src=r.pitches[0].src],
 ["remote URL",r=>r.pitches[0].src="https://example.com/a.mp4"],
 ["path traversal",r=>r.pitches[0].src="clips/../x.mp4"],
 ["encoded traversal",r=>r.pitches[0].src="clips/%2e%2e/x.mp4"],
 ["query injection",r=>r.pitches[0].src="clips/x.mp4?x=1"],
 ["backslash",r=>r.pitches[0].src="clips\\x.mp4"],
 ["bad SHA",r=>r.pitches[0].sha256="a"],
 ["nonfinite duration",r=>r.pitches[0].duration_s=Infinity],
 ["missing excluded reason",r=>r.pitches.find(p=>p.status==="excluded").reason=""],
 ["excluded with video",r=>r.pitches.find(p=>p.status==="excluded").src="clips/wrong.mp4"],
 ["object player name",r=>r.pitches[0].batter={name:"x"}],
])test(`rejects ${name}`,()=>{const r=fixture();mutate(r);assert.throws(()=>validateRegistry(r));});
test("chain advances only after matching playing generation ended",()=>{const r=fixture();let s=createState(r);s=t(s,r,{type:"start"});assert.equal(s.chain,true);const pending=s;assert.equal(t(s,r,{type:"ended",epoch:0}),pending);s=t(s,r,{type:"playing",epoch:0});s=t(s,r,{type:"ended",epoch:0});assert.equal(s.index,1);assert.equal(s.epoch,1);assert.equal(s.chain,true);assert.equal(s.mode,"pending");assert.equal(t(s,r,{type:"ended",epoch:0}),s);});
test("start while already playing still advances at end",()=>{const r=fixture();let s=t(createState(r),r,{type:"playing",epoch:0});s=t(s,r,{type:"start"});assert.equal(s.mode,"playing");assert.equal(t(s,r,{type:"ended",epoch:0}).index,1);});
test("manual selection cancels chain and stale play/error/end cannot affect new clip",()=>{const r=fixture();let s=t(createState(r),r,{type:"start"});s=t(s,r,{type:"select",index:8});assert.equal(s.chain,false);assert.equal(s.mode,"paused");for(const type of ["playing","error","ended","pause","seek"])assert.equal(t(s,r,{type,epoch:0}),s);});
test("missing clip stops chain without silently skipping",()=>{const r=fixture();const idx=r.pitches.findIndex(p=>p.status==="excluded");let s=createState(r,r.pitches[idx-1].pitch_key);s=t(s,r,{type:"start"});s=t(s,r,{type:"playing",epoch:0});s=t(s,r,{type:"ended",epoch:0});assert.equal(s.index,idx);assert.equal(s.mode,"unavailable");assert.equal(s.chain,false);assert.equal(t(s,r,{type:"start"}),s);});
test("seek, pause and stop cancel chain; error requires explicit reload",()=>{const r=fixture();for(const type of["seek","pause","stop","error"]){let s=t(createState(r),r,{type:"start"});s=t(s,r,{type,epoch:0});assert.equal(s.chain,false);if(type==="error"){assert.equal(t(s,r,{type:"start"}),s);const retry=t(s,r,{type:"select",index:0});assert.equal(retry.mode,"paused");assert.equal(retry.epoch,1);}}});
test("last clip ends without wrapping; restart creates new media generation",()=>{const r=fixture();let s=createState(r,r.pitches.at(-1).pitch_key);s=t(s,r,{type:"start"});s=t(s,r,{type:"playing",epoch:0});s=t(s,r,{type:"ended",epoch:0});assert.equal(s.index,261);assert.equal(s.chain,false);assert.equal(s.mode,"ended");s=t(s,r,{type:"start"});assert.equal(s.index,261);assert.equal(s.epoch,1);assert.equal(s.chain,true);assert.equal(s.mode,"pending");});
test("unavailable initial target remains unavailable and cannot play",()=>{const r=fixture();const s=createState(r,"849843:69:2");assert.equal(s.mode,"unavailable");assert.equal(t(s,r,{type:"playing",epoch:0}),s);});
test("invalid selections do not alter current pitch",()=>{const r=fixture(),s=createState(r);for(const index of[-1,262,NaN,1.5,"3"])assert.equal(t(s,r,{type:"select",index}),s);});

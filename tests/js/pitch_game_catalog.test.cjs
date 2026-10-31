"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const fs = require("node:fs"), path = require("node:path"), crypto = require("node:crypto"), vm = require("node:vm");
const catalog = require("../../web/pitch-studio/game-catalog.js");
const games = require("../../web/pitch-studio/receiver-fullgame.js");
const media = require("../../web/pitch-studio/receiver-game-media.js");
const zones = require("../../web/pitch-studio/receiver-zones.js");
const routes = require("../../web/pitch-studio/receiver-route.js");
const root = path.join(__dirname,"../../web/pitch-studio");
const sha = bytes => crypto.createHash("sha256").update(bytes).digest("hex");
function read(id,suffix="") {
  const bytes=fs.readFileSync(path.join(root,`game-${id}${suffix}.json`));
  return {bytes,data:JSON.parse(bytes),hash:sha(bytes)};
}

test("catalog is limited to the three curated games, excluding the locked evaluation game",()=>{
  assert.deepEqual(catalog.list().map(g=>g.game_pk),[849843,849845,823407]);
  for(const id of [849844,747139,999999,"0849843","849843 ","849843.0",null,undefined,true,{},[],NaN,Infinity]) assert.equal(catalog.get(id),null);
  assert.equal(catalog.get("849843"),catalog.get(849843));
  assert.ok(Object.isFrozen(catalog)&&Object.isFrozen(catalog.list()));
  assert.throws(()=>{catalog.get(849843).game_sha256="a";},TypeError);
  assert.throws(()=>catalog.list().push({}),TypeError);
});

for(const id of [849843,849845,823407]) {
  test(`game ${id}: exact game/media/zone bytes activate only their own keyed data`,()=>{
    const entry=catalog.get(id),g=read(id),m=read(id,"-media"),z=read(id,"-zones");
    assert.equal(g.hash,entry.game_sha256);assert.equal(m.hash,entry.media_sha256);assert.equal(z.hash,entry.zones_sha256);
    const session=games.createVerifiedSession(g.data,g.hash);
    assert.equal(session.view().pitch_id,entry.first_pitch);
    assert.deepEqual(session.view().summary,{pitches:entry.pitches,plate_appearances:entry.plate_appearances,ready:entry.ready,unsupported:entry.unsupported,missing:entry.missing});
    const clips=media.createVerifiedMedia(m.data,g.data,m.hash);
    const heights=zones.createVerifiedZones(z.data,g.data,z.hash);
    assert.equal(Object.keys(clips.media).length,entry.media_count);
    assert.equal(Object.keys(clips.media).length+Object.keys(clips.excluded).length,entry.pitches);
    assert.equal(Object.keys(heights).length,entry.zones_count);
    for(const pitch of g.data.pitches) {
      const link=routes.query("game",pitch.pitch_id), route=routes.parse(link);
      assert.equal(route.pitchId,pitch.pitch_id);
      session.select(route.pitchId);
      assert.equal(session.view().post,null);
      session.reveal(true);
      assert.deepEqual(session.view().post.actual,pitch.post.actual);
      assert.ok(clips.media[pitch.pitch_id]||clips.excluded[pitch.pitch_id]);
      assert.ok(heights[pitch.pitch_id]||entry.non_pitch_ids.includes(pitch.pitch_id));
    }
    const changed=structuredClone(g.data);changed.pitches[0].pitcher.name+=" changed";
    assert.throws(()=>games.createVerifiedSession(changed,sha(JSON.stringify(changed))),/바이트/);
    for(const other of catalog.list().filter(g=>g.game_pk!==id)) {
      const foreign=read(other.game_pk);
      assert.throws(()=>media.createVerifiedMedia(m.data,foreign.data,m.hash));
      assert.throws(()=>zones.createVerifiedZones(z.data,foreign.data,z.hash));
      assert.throws(()=>games.createVerifiedSession(g.data,other.game_sha256));
      assert.throws(()=>routes.parse(`?game=${other.game_pk}&pitch=${entry.first_pitch}`));
    }
  });
}

for(const id of [849845,823407]) test(`game ${id}: video/actual records never pretend to be received model recommendations`,()=>{
  const entry=catalog.get(id),g=read(id),s=games.createVerifiedSession(g.data,g.hash);
  assert.equal(entry.ready,0);assert.equal(entry.unsupported,0);assert.equal(entry.missing,entry.pitches);
  assert.equal(entry.timing,false);
  assert.equal(g.data.source.kind,"official_record");assert.equal(g.data.source.model_id,null);
  assert.equal(routes.parse(`?game=${id}`).pitchId,entry.first_pitch);
  assert.throws(()=>routes.parse(`?game=${id}&archive=first-pa`));
  assert.throws(()=>routes.parse(`?game=${id}&demo=849843-pa1`));
  for(const p of g.data.pitches){
    assert.deepEqual(p.pre,{status:"missing",provenance:"absent",recorded_at:null,policy:null,candidates:[]});
    assert.equal(p.post.setup,null);s.select(p.pitch_id);
    assert.equal(s.view().post,null);s.reveal(true);assert.ok(s.view().post.actual);
    assert.deepEqual(games.observation(s.view()),{status:"missing",x:null});
  }
});

test("browser catalog and adapters use the same allowlist and no untrusted globals",()=>{
  const context=vm.createContext({URLSearchParams});
  for(const name of ["game-catalog.js","receiver-fullgame.js","receiver-game-media.js","receiver-zones.js","receiver-route.js"]) vm.runInContext(fs.readFileSync(path.join(root,name),"utf8"),context);
  const g=read(849845),m=read(849845,"-media"),z=read(849845,"-zones");
  const s=context.PitchReceiverFullGame.createVerifiedSession(g.data,g.hash);
  assert.equal(s.view().game.game_pk,849845);
  assert.ok(context.PitchReceiverGameMedia.createVerifiedMedia(m.data,g.data,m.hash));
  assert.ok(context.PitchReceiverZones.createVerifiedZones(z.data,g.data,z.hash));
  assert.equal(context.PitchReceiverRoute.parse("?game=849845").pitchId,s.view().pitch_id);
  assert.equal(context.PitchGameCatalog.get(849844),null);
});

test("the four automatic balls stay in the record denominator without invented video or zone",()=>{
  const g=read(823407),m=read(823407,"-media"),z=read(823407,"-zones"),entry=catalog.get(823407);
  assert.equal(entry.pitches,359);assert.equal(entry.media_count,355);assert.equal(entry.zones_count,355);
  assert.deepEqual(entry.non_pitch_ids,["823407:35:1","823407:35:2","823407:35:3","823407:35:4"]);
  assert.ok(Object.isFrozen(entry.non_pitch_ids));
  const video=media.validate(m.data,g.data),height=zones.validate(z.data,g.data);
  for(const key of entry.non_pitch_ids) {
    assert.equal(video.media[key],undefined);assert.equal(height[key],undefined);
    assert.equal(video.excluded[key].reason,"automatic_ball_no_video");
  }
  const wrongReason=structuredClone(m.data);wrongReason.excluded[0].reason="manual_override";
  assert.throws(()=>media.validate(wrongReason,g.data));
  const wrongType=structuredClone(m.data);wrongType.excluded[0].received_pitch_type="FF";
  assert.throws(()=>media.validate(wrongType,g.data));
  const falseAuto=structuredClone(g.data);falseAuto.pitches.find(p=>p.pitch_id===entry.non_pitch_ids[0]).post.actual.x=1;
  assert.throws(()=>media.validate(m.data,falseAuto));assert.throws(()=>zones.validate(z.data,falseAuto));
  const falseDescription=structuredClone(g.data);falseDescription.pitches.find(p=>p.pitch_id===entry.non_pitch_ids[0]).post.actual.description="ball";
  assert.throws(()=>media.validate(m.data,falseDescription));assert.throws(()=>zones.validate(z.data,falseDescription));
  const borrowedZone=structuredClone(z.data),p=g.data.pitches.find(p=>p.pitch_id===entry.non_pitch_ids[0]);
  borrowedZone.pitches[0]={...borrowedZone.pitches[0],pitch_id:p.pitch_id,batter_id:p.batter.id,pitcher_id:p.pitcher.id};
  assert.throws(()=>zones.validate(borrowedZone,g.data));
  const missing=structuredClone(z.data);missing.pitches.pop();assert.throws(()=>zones.validate(missing,g.data));
});

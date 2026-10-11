"use strict";
const test = require("node:test"), assert = require("node:assert/strict");
const ui = require("./playback.js");
function fixture() {
  return {
    schema:"intent_observation_playback_v1",
    media:{path:"media/clip.mp4",sha256:"a".repeat(64),source_offset_seconds_exact:"100",clip_end_seconds_exact:"100"},
    scope:{game_pk:747139,pa:2,start_source_seconds_exact:"110",end_source_seconds_exact:"170",full_pa_verified:false,live_availability_verified:false,human_label:false},
    observations:[
      {index:0,cutoff_seconds_exact:"105",frame_seconds_exact:"104",publication_seconds_exact:"108",status:"accepted",observation_status:"unknown",candidate_status:"candidate",reference_pitch_id:null,image_path:"frames/000.jpg"},
      {index:1,cutoff_seconds_exact:"115",frame_seconds_exact:"114",publication_seconds_exact:"118",status:"accepted",observation_status:"unavailable",candidate_status:"no_candidate",reference_pitch_id:"747139:2:1",image_path:"frames/001.jpg"},
      {index:2,cutoff_seconds_exact:"145",frame_seconds_exact:"144",publication_seconds_exact:"155",status:"accepted",observation_status:"unknown",candidate_status:"ambiguous",reference_pitch_id:"747139:2:2",image_path:"frames/002.jpg"},
      {index:3,cutoff_seconds_exact:"160",frame_seconds_exact:null,publication_seconds_exact:null,status:"error",observation_status:"unavailable",candidate_status:"error",reference_pitch_id:null,image_path:null},
      {index:4,cutoff_seconds_exact:"165",frame_seconds_exact:null,publication_seconds_exact:null,status:"not_attempted",observation_status:"unavailable",candidate_status:"not_attempted",reference_pitch_id:null,image_path:null}
    ],
    references:[
      {pitch_id:"747139:2:1",decision_seconds_exact:"110",decision_upper_seconds_exact:"111",release_lower_seconds_exact:"120",release_upper_seconds_exact:"121",conservative_temporal_ready:true,nominal_start_temporal_ready:true,usable_mitt:false},
      {pitch_id:"747139:2:2",decision_seconds_exact:"140",decision_upper_seconds_exact:"141",release_lower_seconds_exact:"150",release_upper_seconds_exact:"151",conservative_temporal_ready:false,nominal_start_temporal_ready:false,usable_mitt:false}
    ],
    summary:{planned_observations:5,interval_observations:4,outside_interval_observations:1,accepted:3,errors:1,not_attempted:1,verified_mitt:0,conservative_ready_pitches:1}
  };
}
test("publication boundary and reverse seeking hide future results",()=>{
  const d=ui.validateData(fixture());
  assert.equal(ui.stateAt(d,17.999).latest,null);
  assert.equal(ui.stateAt(d,18).latest.index,1);
  assert.equal(ui.stateAt(d,18).timely.length,1);
  assert.equal(ui.stateAt(d,18).usableMitt,false);
  assert.equal(ui.stateAt(d,16).latest,null);
});
test("previous pitch cannot carry into active pitch or after release",()=>{
  const d=fixture();
  assert.equal(ui.stateAt(d,45).active.pitch_id,"747139:2:2");
  assert.equal(ui.stateAt(d,45).latest.index,1);
  assert.equal(ui.stateAt(d,45).timely.length,0);
  assert.equal(ui.stateAt(d,55).latest.index,2);
  assert.equal(ui.stateAt(d,55).active,null);
  assert.equal(ui.stateAt(d,55).timely.length,0);
});
test("outside interval output cannot become current and unassigned stays unassigned",()=>{
  const d=fixture(); assert.equal(ui.stateAt(d,10).latest,null);
  d.observations[1].reference_pitch_id=null;
  assert.equal(ui.stateAt(d,18).timely.length,0);
  assert.equal(ui.stateAt(d,18).latest.reference_pitch_id,null);
});
test("uncertain decision boundary is excluded and release boundary is strict",()=>{
  const d=fixture(); d.observations[1].frame_seconds_exact="221/2";
  assert.equal(ui.stateAt(d,18).timely.length,0);
  d.observations[1].frame_seconds_exact="114"; d.observations[1].publication_seconds_exact="120";
  assert.equal(ui.stateAt(d,20).timely.length,0);
});
test("error and not attempted stay in counts without fabricated output",()=>{
  const d=ui.validateData(fixture()); assert.equal(d.summary.errors,1);
  assert.equal(ui.stateAt(d,69).latest.index,2);
});
for (const [name,mutate] of [
  ["future input", d=>d.observations[1].frame_seconds_exact="116"],
  ["publication before cutoff",d=>d.observations[1].publication_seconds_exact="114"],
  ["different pitch",d=>d.observations[1].reference_pitch_id="747139:3:1"],
  ["claimed mitt",d=>d.references[0].usable_mitt=true],
  ["claimed full PA",d=>d.scope.full_pa_verified=true],
  ["claimed human labels",d=>d.scope.human_label=true],
  ["claimed live",d=>d.scope.live_availability_verified=true],
  ["absolute image",d=>d.observations[1].image_path="C:/private/frame.jpg"],
  ["parent image",d=>d.observations[1].image_path="frames/../frame.jpg"],
  ["summary mismatch",d=>d.summary.accepted=4],
  ["error with output",d=>d.observations[3].image_path="frames/003.jpg"],
  ["empty frame time",d=>d.observations[1].frame_seconds_exact=""],
  ["bad denominator",d=>d.scope.start_source_seconds_exact="110/0"],
  ["overflow",d=>d.scope.start_source_seconds_exact="999999999999999999999"],
  ["scope outside media",d=>d.scope.end_source_seconds_exact="201"],
  ["duplicate observation",d=>d.observations[1].index=0],
  ["duplicate pitch",d=>d.references[1].pitch_id=d.references[0].pitch_id]
]) test(`reject ${name}`,()=>{const d=fixture();mutate(d);assert.throws(()=>ui.validateData(d));});
test("fractional scope uses exact rational source rather than rounded decimal",()=>{
  const d=fixture();d.scope.start_source_seconds_exact="110000001/1000000";
  d.observations[1].frame_seconds_exact="110";
  assert.equal(ui.inScope(d,d.observations[1]),false);
});

test("missing error status stays absent",()=>{const d=fixture();d.observations[3].observation_status=null;assert.equal(ui.validateData(d).observations[3].observation_status,null);});

test("half-open scope never reveals output at or after its end",()=>{const d=fixture();d.observations[2].publication_seconds_exact="170";assert.equal(ui.stateAt(d,70).latest.index,1);assert.equal(ui.stateAt(d,71).latest.index,1);assert.equal(ui.stateAt(d,70).active,null);});

test("empty conservative window is valid but cannot be timely",()=>{const d=fixture();d.references[1].decision_upper_seconds_exact="145";d.references[1].release_lower_seconds_exact="144";d.references[1].release_upper_seconds_exact="154";ui.validateData(d);assert.equal(ui.stateAt(d,46).timely.length,0);});

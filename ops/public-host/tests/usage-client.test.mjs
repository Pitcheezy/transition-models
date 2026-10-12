import test from "node:test";
import assert from "node:assert/strict";
import { createUsageClient } from "../client/usage-client.mjs";
function fixture(extra={}) {
  let time=0,utc=Date.parse("2026-10-12T12:00:00Z"),visible=true,deny=false,n=0;
  const calls=[],statuses=[];
  const ok=()=>new Response('{"accepted":true}',{status:200});
  const client=createUsageClient({telemetryEnabled:true,feedbackEnabled:true,retainDays:30,gamePk:123,now:()=>time,wall:()=>utc,visible:()=>visible,
    optedOut:()=>deny,uuid:()=>String(++n),onStatus:s=>statuses.push(s),
    fetchFn:async(path,init)=>{calls.push({path,body:JSON.parse(init.body),init});return ok();},...extra});
  return {client,calls,statuses,ok,advance:ms=>{time+=ms;utc+=ms;},setDay:x=>{utc=Date.parse(x);},
    hide:()=>{visible=false;client.sample();},show:()=>{visible=true;client.sample();},deny:()=>{deny=true;}};
}
test("no requests before explicit participation; withdrawal stops future sends",async()=>{
  const f=fixture();await f.client.flush();assert.equal(f.calls.length,0);
  await f.client.grant();f.advance(30000);await f.client.flush();
  assert.equal(f.calls[1].body.active_ms,30000);
  assert.equal(f.calls[1].init.credentials,"omit");assert.equal(f.calls[1].init.redirect,"error");assert.equal(f.calls[1].init.referrerPolicy,"no-referrer");
  f.client.withdraw();f.advance(30000);await f.client.flush();assert.equal(f.calls.length,2);
  await f.client.grant();assert.notEqual(f.calls[2].body.session_id,f.calls[0].body.session_id);
  f.client.destroy();
});
test("initial connection wait is excluded; hidden and long sleep gaps are not active time",async()=>{
  let release;const responses=[];
  const f=fixture({fetchFn:async(_path,init)=>{responses.push(JSON.parse(init.body));if(responses.length===1)return await new Promise(r=>release=r);return new Response('{"accepted":true}');}});
  const start=f.client.grant();f.advance(5000);release(f.ok());await start;
  f.advance(30000);await f.client.flush();assert.equal(responses[1].active_ms,30000);
  f.hide();f.advance(60000);await f.client.flush();assert.equal(responses[2].active_ms,30000);
  f.show();f.advance(60001);await f.client.flush();assert.equal(responses[3].active_ms,30000);
  f.advance(10000);await f.client.flush();assert.equal(responses[4].active_ms,40000);f.client.destroy();
});
test("failed transmission retries identical payload before new cumulative value",async()=>{
  let reject=true;const calls=[];
  const f=fixture({fetchFn:async(_p,init)=>{calls.push(JSON.parse(init.body));if(reject)throw new Error("offline");return new Response('{"accepted":true}');}});
  await f.client.grant();f.advance(5000);reject=false;await f.client.flush();
  assert.deepEqual(calls[1],calls[0]);f.advance(30000);await f.client.flush();
  assert.equal(calls[2].sequence,1);assert.equal(calls[2].active_ms,30000);f.client.destroy();
});
test("UTC midnight and game changes start new zero-time sessions",async()=>{
  const f=fixture();await f.client.grant();f.advance(30000);await f.client.flush();
  f.setDay("2026-10-13T00:00:00Z");await f.client.flush();
  assert.equal(f.calls[2].body.sequence,0);assert.equal(f.calls[2].body.active_ms,0);
  assert.notEqual(f.calls[2].body.session_id,f.calls[0].body.session_id);
  f.client.setGame(456);await new Promise(r=>setImmediate(r));
  assert.equal(f.calls[3].body.game_pk,456);assert.equal(f.calls[3].body.active_ms,0);f.client.destroy();
});
test("privacy opt-out blocks session and feedback; invalid ack is not success",async()=>{
  const f=fixture();f.deny();await f.client.grant();await f.client.sendFeedback("helpful");assert.equal(f.calls.length,0);
  const g=fixture({fetchFn:async()=>new Response("<html>SPA</html>")});assert.equal(await g.client.grant(),false);
  assert.equal(g.client.state.started,false);g.client.destroy();
});
test("feedback retries same ID; lost acknowledgement cannot silently duplicate changed opinion or new day",async()=>{
  let offline=true;const calls=[];
  const f=fixture({fetchFn:async(_p,init)=>{calls.push(JSON.parse(init.body));if(offline)throw new Error("offline");return new Response('{"accepted":true}');}});
  assert.equal((await f.client.sendFeedback("helpful")).ok,false);
  assert.equal((await f.client.sendFeedback("problem")).uncertain,true);assert.equal(calls.length,1);
  offline=false;assert.equal((await f.client.sendFeedback("helpful")).ok,true);assert.deepEqual(calls[0],calls[1]);
  await f.client.sendFeedback("helpful");assert.equal(calls.length,2);
  f.client.setGame(456);offline=true;await f.client.sendFeedback("problem");
  f.setDay("2026-10-13T00:00:00Z");
  assert.equal((await f.client.sendFeedback("problem")).uncertain,true);assert.equal(calls.length,3);f.client.destroy();
});
test("late acknowledgement after opt-out never resumes measurement",async()=>{
  let resolveJson;let requests=0;
  const f=fixture({fetchFn:async()=>{requests++;return{ok:true,json:()=>new Promise(r=>resolveJson=r)};}});
  const pending=f.client.grant();await new Promise(r=>setImmediate(r));f.client.withdraw();
  resolveJson({accepted:true});await pending;assert.equal(f.client.state.consent,false);
  assert.equal(f.statuses.at(-1),"off");f.advance(30000);await f.client.flush();assert.equal(requests,1);f.client.destroy();
});

test("response headers without a completing JSON body time out and unlock retry",async()=>{
  const f=fixture({fetchFn:async()=>({ok:true,json:()=>new Promise(()=>{})})});
  assert.equal(await f.client.grant(),false);
  assert.equal(f.client.state.started,false);assert.equal(f.statuses.at(-1),"retry");f.client.destroy();
});

test("independent gates prevent direct calls to the disabled collection kind", async () => {
  const onlyFeedback=fixture({telemetryEnabled:false});
  assert.equal(await onlyFeedback.client.grant(),false);
  assert.equal((await onlyFeedback.client.sendFeedback("helpful")).ok,true);
  assert.deepEqual(onlyFeedback.calls.map(x=>x.path),["/_telemetry/feedback"]);
  assert.equal(onlyFeedback.client.state.telemetryEnabled,false);
  assert.equal(onlyFeedback.client.state.feedbackEnabled,true);onlyFeedback.client.destroy();
  const onlySession=fixture({feedbackEnabled:false});
  assert.equal((await onlySession.client.sendFeedback("helpful")).disabled,true);
  assert.equal(await onlySession.client.grant(),true);
  assert.deepEqual(onlySession.calls.map(x=>x.path),["/_telemetry/session"]);onlySession.client.destroy();
});

test("retention is required and strictly bounded; legacy enabled never enables collection", async () => {
  for(const retainDays of [undefined,null,0,91,30.5,"30",true,NaN]){
    const f=fixture({retainDays});
    assert.equal(await f.client.grant(),false);
    assert.equal((await f.client.sendFeedback("helpful")).disabled,true);
    assert.equal(f.calls.length,0);assert.equal(f.client.state.retainDays,null);f.client.destroy();
  }
  const legacy=fixture({telemetryEnabled:undefined,feedbackEnabled:undefined,enabled:true});
  assert.equal(await legacy.client.grant(),false);
  assert.equal((await legacy.client.sendFeedback("helpful")).disabled,true);
  assert.equal(legacy.calls.length,0);legacy.client.destroy();
  for(const retainDays of [1,90]){
    const f=fixture({retainDays});assert.equal(f.client.state.retainDays,retainDays);
    assert.equal(await f.client.grant(),true);f.client.withdraw();
    assert.equal((await f.client.sendFeedback("helpful")).ok,true);f.client.destroy();
  }
});

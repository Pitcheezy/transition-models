import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, rm, readdir, readFile } from 'node:fs/promises';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { runStage4Notice } from '../exhibit-stage4-notice.mjs';
const origin = 'https://notice.example.test';
const token = 'synthetic-notice-token-for-unit-tests-only-not-real';
const versionPin = '5999cf0d-4f18-4d43-bcd6-320e04860369';
function server({ lostOn=false, lostOff=false, conflict=false, initialOn=false, otherAfterLost=false }={}) {
  let revision = initialOn ? 1 : 0, active=initialOn, etag=initialOn ? '"'+'1'.repeat(32)+'"' : null;
  const audit=[]; const calls=[];
  const fetchImpl=async (_url, init) => {
    calls.push(init.method);
    const headers={ 'content-type':'application/json', 'cache-control':'no-store, no-transform' };
    if (init.method==='PUT') {
      const c=JSON.parse(init.body);
      if (conflict && !c.active) return new Response(null,{status:412});
      revision++; active=c.active; etag='"'+String(revision).repeat(32)+'"';
      audit.push({schema:'pitcheezy-notice-audit-v1',operator:otherAfterLost?'another-run':c.operator,
        reason:c.reason,revision,active,message_id:'maintenance',etag_after:etag});
      if ((lostOn&&active)||(lostOff&&!active)) throw new Error('secret-bearing-transport-error');
      headers.etag=etag;
      return new Response(JSON.stringify({active,message_id:'maintenance',revision,since:active?'2026-11-02T00:00:00.000Z':null,
        change_id:'12345678-abcd-abcd-abcd-123456789012',audit_recorded:true}),{headers});
    }
    if(etag)headers.etag=etag;
    return new Response(JSON.stringify({state:{active,message_id:revision?'maintenance':null,revision,
      since:active?'2026-11-02T00:00:00.000Z':null,etag},audit,audit_truncated:false,audit_unavailable:false,messages:{maintenance:'copy'}}),{headers});
  };
  return { fetchImpl,calls,get active(){return active;} };
}
async function run(options={}, callbacks={}) {
  const dir=await mkdtemp(join(tmpdir(),'stage4-notice-'));
  const s=server(options);
  try {
    const report=await runStage4Notice({origin,token,versionPin,runId:'stage4-synthetic-0001',outDir:join(dir,'run'),fetchImpl:s.fetchImpl,...callbacks});
    const names=await readdir(join(dir,'run'));
    const text=(await Promise.all(names.map(n=>readFile(join(dir,'run',n),'utf8')))).join('');
    assert.equal(text.includes(token),false); assert.equal(text.includes('secret-bearing'),false);
    assert.equal(JSON.stringify(report).includes(origin),false);
    assert.ok(s.calls.length<=8);
    return {report,s};
  }finally{await rm(dir,{recursive:true,force:true});}
}
test('normal cycle is five requests and exactly restores owned revision',async()=>{
  const {report,s}=await run();assert.equal(report.passed,true);assert.equal(report.expected_final_revision,2);
  assert.deepEqual(s.calls,['GET','PUT','GET','PUT','GET']);assert.equal(s.active,false);
});
test('browser assertion failure still closes notice and never reports pass',async()=>{
  const {report,s}=await run({}, {onActive:async()=>{throw new Error('browser_failed');}});
  assert.equal(report.passed,false);assert.equal(report.final_off_confirmed,true);assert.equal(s.active,false);
});
test('lost ON acknowledgement uses read and owned OFF, never repeats ON',async()=>{
  const {report,s}=await run({lostOn:true});assert.equal(report.passed,false);assert.equal(report.final_off_confirmed,true);
  assert.deepEqual(s.calls,['GET','PUT','GET','PUT','GET']);assert.equal(s.active,false);
});
test('lost OFF acknowledgement observes final state without repeating write',async()=>{
  const {report,s}=await run({lostOff:true});assert.equal(report.passed,false);assert.equal(report.final_off_confirmed,true);
  assert.deepEqual(s.calls,['GET','PUT','GET','PUT','GET']);
});
test('competing operator ownership or conditional conflict is not overwritten',async()=>{
  const a=await run({lostOn:true,otherAfterLost:true});assert.equal(a.report.final_off_confirmed,false);
  assert.deepEqual(a.s.calls,['GET','PUT','GET']);assert.equal(a.s.active,true);
  const b=await run({conflict:true});assert.equal(b.report.conflict,true);assert.equal(b.report.passed,false);
  assert.equal(b.s.calls.filter(x=>x==='PUT').length,2);
});
test('initial active notice is refused with one read and no writes',async()=>{
  const {report,s}=await run({initialOn:true});assert.equal(report.passed,false);assert.deepEqual(s.calls,['GET']);
});

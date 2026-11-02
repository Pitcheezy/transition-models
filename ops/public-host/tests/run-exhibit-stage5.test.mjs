import test from 'node:test';
import assert from 'node:assert/strict';
import { mkdtemp, mkdir, writeFile, readFile, readdir, rm, access } from 'node:fs/promises';
import { join, relative, isAbsolute, resolve } from 'node:path';
import { tmpdir } from 'node:os';
import { spawnSync } from 'node:child_process';
import { fileURLToPath } from 'node:url';
import { main, prepareStage5, validateStage5Plan, STAGE5_ORIGIN } from '../run-exhibit-stage5.mjs';
import { hash } from '../exhibit-site.mjs';
const VERSION='5999cf0d-4f18-4d43-bcd6-320e04860369', OLD_VERSION='12345678-abcd-abcd-abcd-123456789012';
const NOW=Date.parse('2026-11-02T10:00:00.000Z');
const CODE='stage5-FAKE-code-CANARY';
const COOKIE='__Host-pz_viewer=v3.123.456.'+'a'.repeat(64)+'.'+'b'.repeat(16)+'.'+'c'.repeat(64);
const ZIP='3c3b8006b892872bfff3423e2bd6ba49ea3de17ee92fbecef07e0b076bc8da51';
const SOURCE='c47fe6cb78479362e7250141da946814cc33bd31',OLD_SOURCE='fba6b2ff846dcfa9afad9ea5df4204007e0604c1';
const missing=p=>access(p).then(()=>false,()=>true);
async function treeText(root){let out='';for(const e of await readdir(root,{withFileTypes:true})){const p=join(root,e.name);out+=e.isDirectory()?await treeText(p):await readFile(p,'utf8');}return out;}
async function fixture(t){
 const root=await mkdtemp(join(tmpdir(),'pz-stage5-only-'));
 t.after(async()=>{const rel=relative(resolve(tmpdir()),resolve(root));assert.ok(!isAbsolute(rel)&&!rel.startsWith('..')&&rel.startsWith('pz-stage5-only-'));await rm(root,{recursive:true,force:true});});
 const run_id='stage5-synthetic-0001',site=join(root,'candidate'),oldSite=join(root,'old');
 await mkdir(site);await mkdir(oldSite);
 const build={'index.html':'<!doctype html><title>synthetic new</title>','favicon.svg':'<svg/>','assets/index-test.js':'console.log(1);','assets/index-test.css':'body{}',
  'v1/setup/849843.json':'{}','v1/game/849843.json':'{}','v1/games/2026-09-30.json':'{}','v1/dates.json':'{}','v1/manifest.json':'{}','v1/health.json':'{}'};
 const old={'index.html':'<!doctype html><title>synthetic old</title>','v1/manifest.json':'{"dates":["old"]}'};
 async function persist(dir,files){for(const [name,text] of Object.entries(files)){await mkdir(join(dir,...name.split('/').slice(0,-1)),{recursive:true});await writeFile(join(dir,...name.split('/')),text);}}
 await persist(site,build);await persist(oldSite,old);
 const rows=files=>Object.entries(files).map(([path,text])=>({path,bytes:Buffer.byteLength(text),sha256_raw:hash(text)}));
 const receipt={schema:'pitcheezy-exhibition-intake-v1',profile:'exhibition-c47fe6cb',source_commit:SOURCE,data_generation_commit:'cb1cfa8f759fd77adc75595316a389208c752dba',zip:{sha256:ZIP},
  catalogue:{advertised_dates:1,missing_date_files:[]},files:rows(build)};
 const oldReceipt={schema:receipt.schema,source_commit:OLD_SOURCE,catalogue:{missing_date_files:[]},files:[...rows(old),
  {path:'v1/game/849844.json',bytes:123,sha256_raw:'f'.repeat(64)}]};
 const receiptPath=join(root,'receipt.json'),oldReceiptPath=join(root,'old-receipt.json');
 await writeFile(receiptPath,JSON.stringify(receipt));await writeFile(oldReceiptPath,JSON.stringify(oldReceipt));
 const collection='{"telemetry_enabled":false}',collectionPath=join(root,'collection.json');await writeFile(collectionPath,collection);
 const plan={schema:'pitcheezy-stage5-plan-v1',approved:false,phase:'cutover',origin:STAGE5_ORIGIN,run_id,version_pin:VERSION,site,receipt:receiptPath,receipt_sha256:hash(JSON.stringify(receipt)),
  access_code_file:join(root,'missing-credential-CANARY'),run_directory:join(root,run_id),window_start_utc:null,window_end_utc:null,request_limit:24,
  collection_file:collectionPath,collection_sha256:hash(collection),zip_sha256:ZIP};
 const fx={root,site,oldSite,plan,build,old,collection,calls:[],outputs:[],now:NOW,mode:'cutover',override:null};
 fx.fetch=async(url,init)=>{
  assert.ok(url.startsWith(STAGE5_ORIGIN+'/'));assert.equal(init.redirect,'manual');assert.equal(init.cache,'no-store');
  const path=new URL(url).pathname+new URL(url).search,method=init.method||'GET';fx.calls.push({path,method});
  const changed=await fx.override?.({path,method,init});if(changed!==undefined)return changed;
  const headers={'CF-Ray':'a123456789abcdef-ABC'};
  if(method==='DELETE')return new Response(null,{status:204,headers});
  if(method==='POST'){assert.equal(JSON.parse(init.body).code,CODE);return new Response('{"authenticated":true}',{headers:{...headers,'Set-Cookie':COOKIE+'; Path=/; Secure; HttpOnly'}});}
  if(path.startsWith('/_publish/'))return new Response(null,{status:503,headers});
  if(!new Headers(init.headers).has('Cookie'))return new Response('required',{status:401,headers:{...headers,'X-Pitcheezy-Access':'required'}});
  assert.equal(new Headers(init.headers).get('Cookie'),COOKIE);
  if(['/v1/game/999999.json','/v1/game/849844.json','/v1/setup/849844.json','/v1/games/2026-10-01.json'].includes(path))return new Response('missing',{status:404,headers});
  if(path==='/index.html')return new Response(null,{status:307,headers:{...headers,Location:'/'}});
  if(path==='/collection-settings.json')return new Response(collection,{headers});
  const key=path==='/'||path==='/?game=849843'?'index.html':path.slice(1),source=(fx.mode==='cutover'?build:old)[key];assert.notEqual(source,undefined,path);
  const mime=key==='index.html'?'text/html':key.endsWith('.js')?'text/javascript':key.endsWith('.css')?'text/css':key.endsWith('.svg')?'image/svg+xml':'application/json';
  return new Response(method==='HEAD'?null:source,{headers:{...headers,'Content-Type':mime,ETag:'"old-r2-tag"','Cache-Control':'no-store, no-transform'}});
 };
 fx.input=async(p=fx.plan,raw=null)=>{const path=join(root,'input-'+(fx.outputs.length)+'-'+Math.random().toString(16).slice(2)+'.json'),text=raw??JSON.stringify(p);await writeFile(path,text);return {path,sha:hash(text),args:['--input',path,'--input-sha256',hash(text)]};};
 fx.run=async(p=fx.plan,{execute=false,raw=null,args=null}={})=>{const input=await fx.input(p,raw);fx.lastInput=input;fx.outputs=[];
  const rc=await main(args??[...input.args,...(execute?['--execute']:[])],{fetchImpl:fx.fetch,clock:()=>fx.now,write:s=>fx.outputs.push(JSON.parse(s))});return {rc,out:fx.outputs.at(-1),input};};
 fx.approve=async()=>{await writeFile(plan.access_code_file,CODE);return {...plan,approved:true,window_start_utc:'2026-11-02T09:59:00.000Z',window_end_utc:'2026-11-02T10:10:00.000Z'};};
 fx.rollback=cutover=>{const {collection_file,collection_sha256,zip_sha256,...common}=cutover;return {...common,phase:'rollback',request_limit:5,version_pin:OLD_VERSION,site:oldSite,receipt:oldReceiptPath,
  receipt_sha256:hash(JSON.stringify(oldReceipt)),cutover_input_sha256:fx.lastInput.sha,cutover_version_pin:VERSION};};
 return fx;
}

test('default dry-run validates local pins, never reads missing credential or creates output',async t=>{
 const fx=await fixture(t),{rc,out}=await fx.run();assert.equal(rc,0);assert.equal(out.service_requests,0);assert.equal(fx.calls.length,0);
 assert.equal(await missing(fx.plan.run_directory),true);assert.equal(await missing(fx.plan.access_code_file),true);
 const {path,sha}=fx.lastInput;const result=spawnSync(process.execPath,[fileURLToPath(new URL('../run-exhibit-stage5.mjs',import.meta.url)),'--input',path,'--input-sha256',sha],{encoding:'utf8'});
 assert.equal(result.status,0,result.stderr);assert.equal(JSON.parse(result.stdout).mode,'local_dry_run');assert.equal(await missing(fx.plan.run_directory),true);
});
test('cutover reuses the actual stage4 read path: exact24, final reserved logout and safe receipts',async t=>{
 const fx=await fixture(t),p=await fx.approve(),result=await fx.run(p,{execute:true});assert.equal(result.rc,0,JSON.stringify(result.out));assert.equal(fx.calls.length,24);
 assert.equal(fx.calls.at(-1).method,'DELETE');assert.equal(result.out.service_requests,24);
 const text=await treeText(p.run_directory);for(const canary of [CODE,COOKIE,STAGE5_ORIGIN,fx.root])assert.equal(text.includes(canary),false,canary);
 const report=JSON.parse(await readFile(join(p.run_directory,'cutover','result.private.json'),'utf8'));assert.equal(report.result.schema,'pitcheezy-stage4-read-result-v1');assert.equal(report.result.verifier_pass,19);
 const repeat=await fx.run(p,{execute:true});assert.equal(repeat.rc,1);assert.equal(fx.calls.length,24);
});
test('one rollback uses old HTML and manifest only, exactly5; cycle cannot be renewed',async t=>{
 const fx=await fixture(t),p=await fx.approve();await fx.run(p,{execute:true});const rollback=fx.rollback(p);fx.calls=[];fx.mode='rollback';
 const result=await fx.run(rollback,{execute:true});assert.equal(result.rc,0,JSON.stringify(result.out));assert.equal(fx.calls.length,5);
 assert.deepEqual(fx.calls.map(c=>c.method+' '+c.path),['GET /','POST /_access/v1/session','GET /','GET /v1/manifest.json','DELETE /_access/v1/session']);
 assert.equal((await fx.run(rollback,{execute:true})).rc,1);assert.equal(fx.calls.length,5);
});
test('rollback dry-run needs no prior cycle; wrong baseline/receipt pins fail locally',async t=>{
 const fx=await fixture(t);fx.lastInput={sha:'a'.repeat(64)};const p={...fx.rollback(fx.plan),approved:false};
 assert.equal((await fx.run(p)).rc,0);assert.equal(fx.calls.length,0);assert.equal(await missing(p.run_directory),true);
 await writeFile(join(fx.oldSite,'index.html'),'changed');assert.equal((await fx.run(p)).rc,2);assert.equal(fx.calls.length,0);
});
test('preflight rejects malformed JSON/hash/origin/keys/paths/budgets/approval/window before fetch or output',async t=>{
 const fx=await fixture(t),approved=await fx.approve();
 const mutations=[{approved:false},{origin:'https://app.pitcheezy.com/'},{origin:'https://app.pitcheezy.com:443'},{origin:'https://u:p@app.pitcheezy.com'},
 {origin:'https://APP.pitcheezy.com'},{origin:'http://app.pitcheezy.com'},{origin:STAGE5_ORIGIN+'/x'}, {origin:STAGE5_ORIGIN+'?x=1'},
 {access_code:CODE},{site:'relative'},{receipt_sha256:'0'.repeat(64)},{collection_sha256:'0'.repeat(64)},{request_limit:25},{version_pin:'oops'},
 {window_start_utc:null,window_end_utc:null},{window_start_utc:'2026-11-02T11:00:00.000Z',window_end_utc:'2026-11-02T11:05:00.000Z'},
 {window_start_utc:'2026-11-02T09:00:00.000Z',window_end_utc:'2026-11-02T09:05:00.000Z'},
 {window_start_utc:'2026-11-02T09:59:00Z'},{window_end_utc:'2026-11-02T10:20:00.000Z'}, {version_pin:'00000000-0000-0000-0000-000000000000'}];
 for(const change of mutations){const result=await fx.run({...approved,...change},{execute:true});assert.equal(result.rc,2,JSON.stringify(change));assert.equal(fx.calls.length,0);assert.equal(await missing(approved.run_directory),true);}
 assert.equal((await fx.run(fx.plan,{raw:'{badjson'})).rc,2);
 const input=await fx.input();assert.equal((await fx.run(fx.plan,{args:['--input',input.path,'--input-sha256','f'.repeat(64)]})).rc,2);
 assert.equal((await fx.run(fx.plan,{args:['--input',input.path]})).rc,2);assert.equal(fx.calls.length,0);
});
test('cutover wrong body/status/redirect stop immediately and log out once',async t=>{
 for(const kind of ['body','status','redirect','network']){const fx=await fixture(t),p=await fx.approve();fx.override=({path})=>{
  if(path!=='/v1/setup/849843.json')return;if(kind==='network')throw new Error(CODE+COOKIE+fx.root);
  return kind==='body'?new Response('WRONG'):kind==='status'?new Response('bad',{status:503}):new Response(null,{status:302,headers:{Location:'https://elsewhere.test/'}});
 };const result=await fx.run(p,{execute:true});assert.equal(result.rc,1);assert.equal(fx.calls.length,7);assert.equal(fx.calls.at(-1).method,'DELETE');
 for(const canary of [CODE,COOKIE,fx.root])assert.equal((await treeText(p.run_directory)).includes(canary),false);}
});
test('window expiry stops ordinary dispatch but permits one reserved logout',async t=>{
 const fx=await fixture(t),p=await fx.approve();fx.override=({method})=>{if(method==='POST')fx.now=Date.parse(p.window_end_utc);};
 const result=await fx.run(p,{execute:true});assert.equal(result.rc,1);assert.equal(fx.calls.length,6);assert.equal(result.out.service_requests,6);assert.equal(fx.calls.at(-1).method,'DELETE');
});
test('rollback gate/status/body/header/login failures stop with appropriate reserved logout',async t=>{
 for(const kind of ['gate','body','header','auth','redirect','logout']){
  const fx=await fixture(t),p=await fx.approve();await fx.run(p,{execute:true});const rollback=fx.rollback(p);fx.calls=[];fx.mode='rollback';
  fx.override=({path,method,init})=>{
   if(kind==='gate'&&method==='GET'&&!new Headers(init.headers).has('Cookie'))return new Response('oops',{status:200});
   if(kind==='auth'&&method==='POST')return new Response('{"authenticated":false}',{headers:{'Set-Cookie':COOKIE}});
   if(kind==='logout'&&method==='DELETE')return new Response('bad',{status:500});
   if(path==='/v1/manifest.json'){
    if(kind==='body')return new Response('wrong');
    if(kind==='header')return new Response(fx.old['v1/manifest.json']);
    if(kind==='redirect')return new Response(null,{status:301,headers:{Location:'/'}});
   }
  };
  const result=await fx.run(rollback,{execute:true});assert.equal(result.rc,1,kind);
  assert.equal(fx.calls.filter(c=>c.method==='DELETE').length,kind==='gate'?0:1,kind);assert.ok(fx.calls.length<=5);
 }
});
test('rollback refuses missing/incomplete/no-dispatch/mismatched cutover contexts',async t=>{
 const fx=await fixture(t),p=await fx.approve();fx.lastInput={sha:'f'.repeat(64)};let rb=fx.rollback(p);
 assert.equal((await fx.run(rb,{execute:true})).rc,1);assert.equal(fx.calls.length,0);
 await fx.run(p,{execute:true});rb=fx.rollback(p);fx.calls=[];
 assert.equal((await fx.run({...rb,cutover_input_sha256:'f'.repeat(64)},{execute:true})).rc,1);assert.equal(fx.calls.length,0);
 const reportPath=join(p.run_directory,'cutover','result.private.json'),report=JSON.parse(await readFile(reportPath));
 await writeFile(reportPath,JSON.stringify({...report,service_requests:0}));assert.equal((await fx.run(rb,{execute:true})).rc,1);assert.equal(fx.calls.length,0);
 await rm(reportPath);assert.equal((await fx.run(rb,{execute:true})).rc,1);assert.equal(fx.calls.length,0);
});
test('pre-existing phase output prevents credential read and remote dispatch',async t=>{
 const fx=await fixture(t),p=await fx.approve();await mkdir(p.run_directory);await rm(p.access_code_file);
 const result=await fx.run(p,{execute:true});assert.equal(result.rc,1);assert.equal(fx.calls.length,0);assert.equal(await missing(p.access_code_file),true);
});
test('strict validation keeps phase source and raw receipt pins separate',async t=>{
 const fx=await fixture(t);assert.equal(validateStage5Plan(fx.plan).phase,'cutover');
 const receipt=JSON.parse(await readFile(fx.plan.receipt));receipt.source_commit=OLD_SOURCE;await writeFile(fx.plan.receipt,JSON.stringify(receipt));
 await assert.rejects(prepareStage5({...fx.plan,receipt_sha256:hash(JSON.stringify(receipt))}),/candidate_provenance_mismatch/);assert.equal(fx.calls.length,0);
});

test('parallel invocations share an exclusive cycle: only one can dispatch',async t=>{
 const fx=await fixture(t),p=await fx.approve(),input=await fx.input(p),outputs=[[],[]];
 const results=await Promise.all(outputs.map(write=>main([...input.args,'--execute'],{fetchImpl:fx.fetch,clock:()=>fx.now,write:s=>write.push(JSON.parse(s))})));
 assert.deepEqual(results.sort(),[0,1]);assert.equal(fx.calls.length,24);
});
test('credential failure is persisted with zero dispatch and cannot authorize rollback',async t=>{
 const fx=await fixture(t),p=await fx.approve();await rm(p.access_code_file);
 const result=await fx.run(p,{execute:true});assert.equal(result.rc,1);assert.equal(result.out.service_requests,0);
 const rb=fx.rollback(p);await writeFile(p.access_code_file,CODE);assert.equal((await fx.run(rb,{execute:true})).rc,1);assert.equal(fx.calls.length,0);
});
test('unknown fetch result is counted once, never retried, and no invented zero is reported',async t=>{
 const fx=await fixture(t),p=await fx.approve();fx.override=()=>{throw new Error('origin-private-path-'+CODE);};
 const result=await fx.run(p,{execute:true});assert.equal(result.rc,1);assert.equal(result.out.service_requests,1);assert.equal(fx.calls.length,1);
 const report=JSON.parse(await readFile(join(p.run_directory,'cutover','result.private.json'),'utf8'));assert.equal(report.result.transport.unknown_responses,1);assert.equal(report.result.transport.retries,0);
});

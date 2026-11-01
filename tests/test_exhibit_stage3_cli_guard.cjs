'use strict';
const {test} = require('node:test');
const assert = require('node:assert/strict');
const {Readable} = require('node:stream');
const fs = require('node:fs');
const path = require('node:path');
const os = require('node:os');
const {spawnSync} = require('node:child_process');
const {makePublisherGuard} = require('../scripts/exhibit_stage3_cli_guard.cjs');
const account='a'.repeat(32),worker='unit-worker',version='11111111-1111-1111-1111-111111111111';
const prefix=`/client/v4/accounts/${account}/workers/scripts/${worker}`;
const digest='b'.repeat(64), valid=JSON.stringify({name:'PUBLISH_TOKEN_SHA256',type:'secret_text',text:digest});
function send(guard, opts) {
  return new Promise(resolve=>{guard.dispatch(opts,{onError:()=>resolve('blocked')});});
}

test('publisher PUT accepts one streamed exact body and blocks a second',async()=>{
  let resolveAccepted,calls=0;
  const accepted=new Promise(r=>{resolveAccepted=r;});
  const g=makePublisherGuard({dispatch(o){calls++;resolveAccepted(o);return true;}},account,worker,null,true);
  g.dispatch({origin:'https://api.cloudflare.com',path:prefix+'/secrets',method:'PUT',body:Readable.from([valid.slice(0,14),valid.slice(14)])},{onError:()=>assert.fail('unexpected refusal')});
  assert.equal((await accepted).body.toString(),valid);
  assert.equal(await send(g,{origin:'https://api.cloudflare.com',path:prefix+'/secrets',method:'PUT',body:valid}),'blocked');
  assert.equal(calls,1);
});

test('wrong secret name/type/digest/extra field/size/target refused',async()=>{
  const invalid=[
    JSON.stringify({name:'ACCESS_CODE_SHA256',type:'secret_text',text:digest}),
    JSON.stringify({name:'PUBLISH_TOKEN_SHA256',type:'plain_text',text:digest}),
    JSON.stringify({name:'PUBLISH_TOKEN_SHA256',type:'secret_text',text:'raw-token'}),
    JSON.stringify({name:'PUBLISH_TOKEN_SHA256',type:'secret_text',text:digest,extra:1}),
    'x'.repeat(513),'{bad',null
  ];
  for(const body of invalid){
    const g=makePublisherGuard({dispatch(){assert.fail('unexpected PUT');}},account,worker,null,true);
    assert.equal(await send(g,{origin:'https://api.cloudflare.com',path:prefix+'/secrets',method:'PUT',body}),'blocked');
  }
  for(const [origin,p] of [['https://other.example',prefix+'/secrets'],['https://api.cloudflare.com',prefix],['https://api.cloudflare.com',prefix+'/secrets?extra=1']]){
    const g=makePublisherGuard({dispatch(){assert.fail('unexpected target');}},account,worker,null,true);
    assert.equal(await send(g,{origin,path:p,method:'PUT',body:valid}),'blocked');
  }
});

test('read commands refuse all mutations; version GET limited to one exact UUID',async()=>{
  const seen=[];
  const g=makePublisherGuard({dispatch(o){seen.push(o);return true;}},account,worker,version,false);
  g.dispatch({origin:'https://api.cloudflare.com',path:prefix+'/versions/'+version,method:'GET'},{onError:()=>assert.fail()});
  assert.equal(await send(g,{origin:'https://api.cloudflare.com',path:prefix+'/versions/'+version,method:'GET'}),'blocked');
  assert.equal(await send(g,{origin:'https://api.cloudflare.com',path:prefix+'/versions/22222222-2222-2222-2222-222222222222',method:'GET'}),'blocked');
  assert.equal(await send(g,{origin:'https://api.cloudflare.com',path:prefix+'/secrets',method:'PUT',body:valid}),'blocked');
  assert.equal(seen.length,1);
});

test('base guard OAuth refresh remains possible once, with no other POST',async()=>{
  let done,calls=0;
  const accepted=new Promise(r=>{done=r;});
  const form='grant_type=refresh_token&refresh_token=fake&client_id=unit';
  const g=makePublisherGuard({dispatch(o){calls++;done(o.body);return true;}},account,worker,null,false);
  g.dispatch({origin:'https://dash.cloudflare.com',path:'/oauth2/token',method:'POST',body:form},{onError:()=>assert.fail()});
  assert.equal((await accepted).toString(),form);
  assert.equal(await send(g,{origin:'https://dash.cloudflare.com',path:'/oauth2/token',method:'POST',body:form}),'blocked');
  assert.equal(await send(g,{origin:'https://api.cloudflare.com',path:prefix+'/deployments',method:'POST',body:'{}'}),'blocked');
  assert.equal(calls,1);
});

test('stalled publisher body does not dispatch after timeout',async()=>{
  let finish,calls=0;
  const body=(async function*(){await new Promise(r=>{finish=r;});yield valid;})();
  const g=makePublisherGuard({dispatch(){calls++;}},account,worker,null,true);
  assert.equal(await send(g,{origin:'https://api.cloudflare.com',path:prefix+'/secrets',method:'PUT',body}),'blocked');
  finish();await new Promise(r=>setImmediate(r));assert.equal(calls,0);
});

test('fixed Wrangler secret put passes exact guarded body to fake dispatcher only',()=>{
  const tmp=fs.mkdtempSync(path.join(os.tmpdir(),'stage3-guard-test-'));
  try{
    const root=path.resolve(__dirname,'..');
    const config=path.join(tmp,'wrangler.json'),empty=path.join(tmp,'empty'),wrapper=path.join(tmp,'wrapper.cjs'),trace=path.join(tmp,'trace.json');
    fs.writeFileSync(config,JSON.stringify({name:worker,compatibility_date:'2026-01-01',workers_dev:false,vars:{UPLOAD_ENABLED:'false'}}));
    fs.writeFileSync(empty,'');
    const undici=path.join(root,'ops/public-host-tooling/node_modules/undici');
    const guard=path.join(root,'scripts/exhibit_stage3_cli_guard.cjs');
    const cli=path.join(root,'ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js');
    fs.writeFileSync(wrapper,`
      const fs=require('node:fs');const u=require(${JSON.stringify(undici)});
      const {makePublisherGuard}=require(${JSON.stringify(guard)});
      const fake={dispatch(o,h){
        const body=JSON.parse(o.body.toString());
        fs.writeFileSync(${JSON.stringify(trace)},JSON.stringify({method:o.method,path:o.path,name:body.name,type:body.type,digestMatches:body.text===${JSON.stringify(digest)}}));
        h.onConnect(()=>{});h.onHeaders(200,[Buffer.from('content-type'),Buffer.from('application/json')],()=>{},'OK');
        h.onData(Buffer.from(JSON.stringify({success:true,errors:[],messages:[],result:{}})));h.onComplete([]);return true;
      }};
      u.setGlobalDispatcher(makePublisherGuard(fake,${JSON.stringify(account)},${JSON.stringify(worker)},null,true));
    `);
    const env={SYSTEMROOT:process.env.SYSTEMROOT,WINDIR:process.env.WINDIR,USERPROFILE:tmp,APPDATA:tmp,LOCALAPPDATA:tmp,TEMP:tmp,TMP:tmp,PATH:path.dirname(process.execPath),CLOUDFLARE_API_TOKEN:'fake-test-only',CLOUDFLARE_ACCOUNT_ID:account,CI:'true',WRANGLER_WRITE_LOGS:'false',WRANGLER_SEND_METRICS:'false',WRANGLER_SEND_ERROR_REPORTS:'false',WRANGLER_LOG:'log',WRANGLER_LOG_SANITIZE:'true',CLOUDFLARE_LOAD_DEV_VARS_FROM_DOT_ENV:'false',NO_COLOR:'1'};
    const child=spawnSync(process.execPath,['--require',wrapper,cli,'secret','put','PUBLISH_TOKEN_SHA256','--config',config,'--env-file',empty],{cwd:tmp,input:digest+'\n',encoding:'utf8',timeout:30000,env});
    assert.equal(child.status,0,child.stdout+child.stderr);
    assert.deepEqual(JSON.parse(fs.readFileSync(trace)),{method:'PUT',path:prefix+'/secrets',name:'PUBLISH_TOKEN_SHA256',type:'secret_text',digestMatches:true});
    assert.doesNotMatch(child.stdout+child.stderr,new RegExp(digest+'|fake-test-only'));
  }finally{
    assert.equal(path.dirname(path.resolve(tmp)),path.resolve(os.tmpdir()));assert.ok(path.basename(tmp).startsWith('stage3-guard-test-'));fs.rmSync(tmp,{recursive:true,force:true});
  }
});

test('production preload without pinned stage3 manifest fails closed',()=>{
  const guard=path.resolve(__dirname,'../scripts/exhibit_stage3_cli_guard.cjs');
  const child=spawnSync(process.execPath,['--require',guard,'-e','process.stdout.write("unexpected")'],{encoding:'utf8',env:{SYSTEMROOT:process.env.SYSTEMROOT,WRANGLER_WRITE_LOGS:'false',PITCHEEZY_STAGE3_MANIFEST:path.join(os.tmpdir(),'no-stage3-manifest'),PITCHEEZY_STAGE3_MANIFEST_SHA256:'a'.repeat(64)}});
  assert.notEqual(child.status,0);assert.doesNotMatch(child.stdout,/unexpected/);assert.match(child.stderr,/stage3 guard initialization failed/);
});

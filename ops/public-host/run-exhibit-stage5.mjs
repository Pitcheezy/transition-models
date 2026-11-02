/** App cutover confirmation only. Never changes routes, resources, configuration or credentials. */
import { readFile, mkdir, open, lstat } from 'node:fs/promises';
import { isAbsolute, basename, join, resolve } from 'node:path';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { prepareSite, validateIntakeReceipt, hash } from './exhibit-site.mjs';
import { plainPath } from './monitor-cli.mjs';
import { runStage4Read } from './exhibit-stage4-read.mjs';
import { createStage4Transport, Stage4Error } from './exhibit-stage4-transport.mjs';
import { ACCESS_HEADER, ACCESS_ROUTE } from './access.mjs';

export const STAGE5_ORIGIN = 'https://app.pitcheezy.com';
export const STAGE5_BUDGET = Object.freeze({ cutover:24, rollback:5, cycle:29 });
const ZIP='3c3b8006b892872bfff3423e2bd6ba49ea3de17ee92fbecef07e0b076bc8da51';
const NEW_SOURCE='c47fe6cb78479362e7250141da946814cc33bd31';
const OLD_SOURCE='fba6b2ff846dcfa9afad9ea5df4204007e0604c1';
const DATA_SOURCE='cb1cfa8f759fd77adc75595316a389208c752dba';
const UUID=/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
const SHA=/^[a-f0-9]{64}$/;
const COOKIE=/^__Host-pz_viewer=v3\.[1-9][0-9]{0,15}\.[1-9][0-9]{0,15}\.[a-f0-9]{64}\.[a-f0-9]{16}\.[a-f0-9]{64}$/;
class Stage5Error extends Error {}
const need=(ok,code)=>{if(!ok)throw new Stage5Error(code);};
const safeCode=e=>(e instanceof Stage5Error || e instanceof Stage4Error) && /^[a-z][a-z0-9_]{0,63}$/.test(e.message)?e.message:'stage5_failed';
const exactKeys=(p,keys)=>p && Object.getPrototypeOf(p)===Object.prototype && Object.keys(p).sort().join('|')===[...keys].sort().join('|');
const COMMON=['schema','approved','phase','origin','run_id','version_pin','site','receipt','receipt_sha256','access_code_file','run_directory','window_start_utc','window_end_utc','request_limit'];
const PHASE_KEYS={cutover:['collection_file','collection_sha256','zip_sha256'],rollback:['cutover_input_sha256','cutover_version_pin']};
function utcMillis(value){
  if(typeof value!=='string'||!/^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}\.\d{3}Z$/.test(value))return NaN;
  const n=Date.parse(value); return Number.isFinite(n)&&new Date(n).toISOString()===value?n:NaN;
}
export function validateStage5Plan(p){
  need(p && ['cutover','rollback'].includes(p.phase),'plan_invalid');
  need(exactKeys(p,[...COMMON,...PHASE_KEYS[p.phase]]),'plan_keys_invalid');
  need(p.schema==='pitcheezy-stage5-plan-v1'&&typeof p.approved==='boolean','plan_invalid');
  need(p.origin===STAGE5_ORIGIN,'target_refused');
  need(/^stage5-[a-z0-9]+(?:-[a-z0-9]+)*$/.test(p.run_id)&&p.run_id.length>=15&&p.run_id.length<=64,'run_id_invalid');
  need(UUID.test(p.version_pin),'version_pin_invalid');
  need(p.request_limit===STAGE5_BUDGET[p.phase],'budget_invalid');
  for(const key of ['site','receipt','access_code_file','run_directory',...(p.phase==='cutover'?['collection_file']:[])])
    need(typeof p[key]==='string'&&isAbsolute(p[key])&&!/[\p{Cc}]/u.test(p[key]),'absolute_path_required');
  need(basename(p.run_directory)===p.run_id,'cycle_directory_invalid');
  need(SHA.test(p.receipt_sha256),'receipt_pin_invalid');
  if(p.phase==='cutover')need(p.zip_sha256===ZIP&&SHA.test(p.collection_sha256),'candidate_pin_invalid');
  else need(SHA.test(p.cutover_input_sha256)&&UUID.test(p.cutover_version_pin),'cutover_context_invalid');
  const a=p.window_start_utc,b=p.window_end_utc;
  if(a===null&&b===null)need(!p.approved,'execution_window_required');
  else {
    const start=utcMillis(a),end=utcMillis(b);
    need(Number.isFinite(start)&&Number.isFinite(end)&&end>start&&end-start<=900000,'execution_window_invalid');
  }
  return p;
}
function checkWindow(p,clock){
  const now=clock(); need(Number.isFinite(now)&&now>=utcMillis(p.window_start_utc)&&now<utcMillis(p.window_end_utc),'execution_window_closed');
}
async function localBytes(path,max){
  await plainPath(path);const info=await lstat(path);
  need(info.isFile()&&info.size<=max,'local_file_invalid');
  const bytes=await readFile(path);need(bytes.length<=max,'local_file_invalid');return bytes;
}
async function pinnedReceipt(p){
  const bytes=await localBytes(p.receipt,2*1024*1024);
  need(hash(bytes)===p.receipt_sha256,'receipt_changed');
  let parsed;try{parsed=JSON.parse(bytes.toString('utf8'));}catch{throw new Stage5Error('receipt_json_invalid');}
  try{return validateIntakeReceipt(parsed);}catch{throw new Stage5Error('receipt_invalid');}
}
export async function prepareStage5(p){
  validateStage5Plan(p);
  for(const key of ['site','receipt','run_directory',...(p.phase==='cutover'?['collection_file']:[])])await plainPath(p[key]);
  const receipt=await pinnedReceipt(p);
  if(p.phase==='rollback'){
    need(receipt.source_commit===OLD_SOURCE,'rollback_source_mismatch');
    // Deliberately never walk/read the other old game files, including locked evaluation data.
    const files=new Map();
    for(const name of ['index.html','v1/manifest.json']){
      const row=receipt.files.find(f=>f.path===name);need(row&&row.bytes>0&&row.bytes<=8*1024*1024,'rollback_baseline_missing');
      const bytes=await localBytes(join(p.site,...name.split('/')),8*1024*1024);
      need(bytes.length===row.bytes&&hash(bytes)===row.sha256_raw,'rollback_baseline_changed');
      files.set(name,{bytes,sha256:row.sha256_raw});
    }
    return {files};
  }
  let prepared;try{prepared=await prepareSite({site:p.site,receipt:p.receipt,expectData:6,game:'849843'});}catch{throw new Stage5Error('candidate_invalid');}
  need(JSON.stringify(prepared.intake)===JSON.stringify(receipt),'receipt_changed');
  need(prepared.files.size===10&&receipt.files.length===10&&receipt.profile==='exhibition-c47fe6cb'&&receipt.source_commit===NEW_SOURCE&&
    receipt.data_generation_commit===DATA_SOURCE&&receipt.zip?.sha256===ZIP&&receipt.catalogue.advertised_dates===1&&receipt.catalogue.missing_date_files.length===0,'candidate_provenance_mismatch');
  const collectionBytes=await localBytes(p.collection_file,16384);
  need(collectionBytes.length>0&&hash(collectionBytes)===p.collection_sha256,'collection_changed');
  return {prepared,collectionBytes};
}
async function save(path,value){
  const h=await open(await plainPath(path),'wx',0o600);
  try{await h.writeFile(JSON.stringify(value,null,2)+'\n');await h.sync();}finally{await h.close();}
}
async function bytes(response,max=8*1024*1024){
  if(!response.body)return Buffer.alloc(0);
  const r=response.body.getReader(),chunks=[];let size=0;
  try{while(true){const part=await r.read();if(part.done)break;size+=part.value.byteLength;if(size>max){await r.cancel();throw new Stage5Error('response_body_too_large');}chunks.push(part.value);}}
  finally{r.releaseLock();}return Buffer.concat(chunks);
}
/** Old app confirmation: five fixed requests; cleanup remains reserved even after a failed body check. */
export async function runStage5Rollback({files,accessCode,outDir,versionPin,fetchImpl}){
  const transport=await createStage4Transport({origin:STAGE5_ORIGIN,outDir,versionPin,fetchImpl,limit:5,reserve:1,
    allowed:[{method:'GET',path:'/'},{method:'GET',path:'/v1/manifest.json'},{method:'POST',path:ACCESS_ROUTE},{method:'DELETE',path:ACCESS_ROUTE}]});
  let session=null,failure=null,logout='not_needed';
  try{
    const gate=await transport.fetch(STAGE5_ORIGIN+'/',{}, {statuses:[401]});
    need(gate.headers.get(ACCESS_HEADER)==='required','access_header_mismatch');await bytes(gate);
    const login=await transport.fetch(STAGE5_ORIGIN+ACCESS_ROUTE,{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({code:accessCode})},{statuses:[200]});
    const pair=(login.headers.get('Set-Cookie')||'').split(';')[0];
    need(COOKIE.test(pair),'login_cookie_missing_or_invalid');session=pair;
    let auth;try{auth=JSON.parse((await bytes(login,16384)).toString('utf8'));}catch{throw new Stage5Error('login_body_invalid');}
    need(auth?.authenticated===true,'login_not_authenticated');
    for(const [path,key] of [['/','index.html'],['/v1/manifest.json','v1/manifest.json']]){
      const response=await transport.fetch(STAGE5_ORIGIN+path,{headers:{Cookie:session}},{statuses:[200]});
      const expected=files.get(key),raw=await bytes(response);
      need(raw.length===expected.bytes.length&&hash(raw)===expected.sha256,'rollback_remote_bytes_mismatch');
      if(key==='index.html')need(/^text\/html\b/.test(response.headers.get('Content-Type')||''),'static_mime_mismatch');
      else need(response.headers.get('ETag')!==null&&response.headers.get('Cache-Control')==='no-store, no-transform','data_headers_mismatch');
    }
  }catch(e){failure=safeCode(e);transport.halt(failure);}
  finally{if(session!==null){try{const r=await transport.cleanupFetch(STAGE5_ORIGIN+ACCESS_ROUTE,{method:'DELETE',headers:{Cookie:session}},{statuses:[204]});await bytes(r);logout='confirmed_204';}catch{logout='unconfirmed';failure??='logout_unconfirmed';}session=null;}}
  return {passed:failure===null&&logout==='confirmed_204'&&transport.summary().attempted_requests===5,failure,logout,transport:transport.summary()};
}
async function begin(p,inputSha){
  const root=await plainPath(p.run_directory);
  if(p.phase==='cutover'){
    await mkdir(root);
    await save(join(root,'cycle.private.json'),{schema:'pitcheezy-stage5-cycle-v1',run_id:p.run_id,cutover_input_sha256:inputSha,cutover_version_pin:p.version_pin});
  }else{
    const cycle=JSON.parse((await localBytes(join(root,'cycle.private.json'),16384)).toString('utf8'));
    need(exactKeys(cycle,['schema','run_id','cutover_input_sha256','cutover_version_pin'])&&cycle.schema==='pitcheezy-stage5-cycle-v1'&&cycle.run_id===p.run_id&&
      cycle.cutover_input_sha256===p.cutover_input_sha256&&cycle.cutover_version_pin===p.cutover_version_pin,'cycle_context_mismatch');
    const completed=JSON.parse((await localBytes(join(root,'cutover','result.private.json'),65536)).toString('utf8'));
    need(completed.schema==='pitcheezy-stage5-result-v1'&&completed.phase==='cutover'&&completed.input_sha256===p.cutover_input_sha256&&
      completed.version_pin===p.cutover_version_pin&&Number.isInteger(completed.service_requests)&&completed.service_requests>0&&completed.service_requests<=24,'cutover_not_completed');
    const dispatched=JSON.parse((await localBytes(join(root,'cutover','dispatch-started.private.json'),16384)).toString('utf8'));
    need(dispatched.input_sha256===p.cutover_input_sha256&&dispatched.version_pin===p.cutover_version_pin,'cutover_not_attempted');
  }
  const phaseDir=join(root,p.phase);await mkdir(phaseDir);
  await save(join(phaseDir,'started.private.json'),{schema:'pitcheezy-stage5-phase-v1',input_sha256:inputSha,phase:p.phase,version_pin:p.version_pin,request_limit:p.request_limit});
  return phaseDir;
}
/** Dependencies are for local fake-fetch tests. The CLI cannot load user-selected modules or adapters. */
export async function main(args,{fetchImpl=fetch,clock=Date.now,write=value=>process.stdout.write(value+'\n')}={}){
  let p,inputSha,inputs,execute;
  const emit=v=>write(JSON.stringify(v));
  try{
    const {values}=parseArgs({args,options:{input:{type:'string'},'input-sha256':{type:'string'},execute:{type:'boolean',default:false}}});
    need(typeof values.input==='string'&&isAbsolute(values.input),'absolute_input_required');
    need(SHA.test(values['input-sha256']),'input_pin_required');
    const raw=await localBytes(values.input,65536);inputSha=hash(raw);need(inputSha===values['input-sha256'],'input_changed');
    try{p=JSON.parse(raw.toString('utf8'));}catch{throw new Stage5Error('input_json_invalid');}
    inputs=await prepareStage5(p);execute=values.execute;
    if(!execute){emit({mode:'local_dry_run',passed:true,phase:p.phase,approved:p.approved,service_requests:0,files:p.phase==='cutover'?10:2,budget:STAGE5_BUDGET});return 0;}
    need(p.approved,'stage5_approval_required');checkWindow(p,clock);
    need(p.version_pin!=='00000000-0000-0000-0000-000000000000','version_placeholder_refused');
  }catch(e){emit({passed:false,code:safeCode(e),service_requests:0});return 2;}
  let phaseDir,dispatches=0,result=null,failure=null;
  try{
    phaseDir=await begin(p,inputSha);checkWindow(p,clock);
    const credential=(await localBytes(p.access_code_file,1024)).toString('utf8').trim();
    need(/^[^\s\p{Cc}]{8,128}$/u.test(credential),'credential_file_invalid');checkWindow(p,clock);
    let marked=false;
    const dispatch=async(url,init)=>{
      const cleanup=init?.method==='DELETE'&&url===STAGE5_ORIGIN+ACCESS_ROUTE;
      if(!cleanup){try{checkWindow(p,clock);}catch{throw new Stage4Error('execution_window_closed');}}
      if(!marked){await save(join(phaseDir,'dispatch-started.private.json'),{input_sha256:inputSha,version_pin:p.version_pin});marked=true;}
      // Metadata is written before any possible send. Failure is never retried.
      dispatches++;
      try{return await fetchImpl(url,init);}catch{throw new Stage4Error('remote_dispatch_failed');}
    };
    result=p.phase==='cutover'?await runStage4Read({target:{origin:STAGE5_ORIGIN},...inputs,accessCode:credential,
      outDir:join(phaseDir,'requests'),versionPin:p.version_pin,fetchImpl:dispatch}):await runStage5Rollback({...inputs,accessCode:credential,
      outDir:join(phaseDir,'requests'),versionPin:p.version_pin,fetchImpl:dispatch});
    if(!result.passed)failure=result.failure||'acceptance_failed';
  }catch(e){failure=safeCode(e);}
  const report={schema:'pitcheezy-stage5-result-v1',phase:p.phase,input_sha256:inputSha,passed:failure===null&&result?.passed===true,
    failure,service_requests:dispatches,request_limit:p.request_limit,version_pin:p.version_pin,
    version_basis:'operator_management_pin_not_http_or_server_log_proof',route_changed_by_tool:false,server_logs:'pending',real_phone:'not_tested',result};
  if(phaseDir){try{await save(join(phaseDir,'result.private.json'),report);}catch{report.passed=false;report.failure='receipt_write_failed';}}
  emit({passed:report.passed,phase:p.phase,code:report.failure,service_requests:dispatches,logout:result?.logout??'not_needed'});
  return report.passed?0:1;
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url))process.exitCode=await main(process.argv.slice(2));

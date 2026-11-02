/** Stage4 local preparation by default. Remote execution requires approved input AND --execute. */
import { readFile, mkdir, writeFile } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { fileURLToPath } from 'node:url';
import { createRequire } from 'node:module';
import { parseArgs } from 'node:util';
import { prepareSite, hash } from './exhibit-site.mjs';
import { parseOrigin } from './verify-exhibit-remote.mjs';
import { runStage4Read } from './exhibit-stage4-read.mjs';
import { openStage4Browser } from './exhibit-stage4-browser.mjs';
import { runStage4Notice } from './exhibit-stage4-notice.mjs';
const require = createRequire(import.meta.url);
export const STAGE4_BUDGET = Object.freeze({ read:24, browser:180, notice:8, total:212 });
const fail = code => { throw new Error(code); };
const codeOf = e => /^[a-z][a-z0-9_]{0,79}$/.test(e?.message || '') ? e.message : 'stage4_failed';
const save = (path, value) => writeFile(path, JSON.stringify(value,null,2)+'\n',{flag:'wx'});
export function validateStage4Plan(p) {
  if (!p || p.schema!=='pitcheezy-stage4-plan-v1' || typeof p.approved!=='boolean') fail('plan_invalid');
  parseOrigin(p.origin);
  if (['pitcheezy.com','app.pitcheezy.com','www.pitcheezy.com','media.pitcheezy.com'].includes(new URL(p.origin).hostname)) fail('public_target_refused');
  if (!/^stage4-[a-z0-9-]{8,48}$/.test(p.run_id || '') || !/^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/.test(p.version_pin || '')) fail('plan_pin_invalid');
  for (const key of ['site','receipt','collection_file','access_code_file','notice_token_file','playwright_module','out_directory'])
    if (typeof p[key]!=='string' || !p[key]) fail('plan_path_missing');
  if (!/^[a-f0-9]{64}$/.test(p.collection_sha256 || '') || p.zip_sha256!=='3c3b8006b892872bfff3423e2bd6ba49ea3de17ee92fbecef07e0b076bc8da51') fail('plan_artifact_pin_invalid');
  if (p.normal_sample_ms!==600000 || p.observation_timeout_ms!==120000 || p.request_limit!==212) fail('plan_budget_invalid');
  return p;
}
export async function prepareStage4(p) {
  validateStage4Plan(p);
  const prepared=await prepareSite({site:p.site,receipt:p.receipt,expectData:6,game:'849843'});
  if(prepared.intake.profile!=='exhibition-c47fe6cb' || prepared.intake.zip.sha256!==p.zip_sha256 ||
    prepared.intake.source_commit!=='c47fe6cb78479362e7250141da946814cc33bd31' ||
    prepared.intake.data_generation_commit!=='cb1cfa8f759fd77adc75595316a389208c752dba') fail('candidate_provenance_mismatch');
  const collectionBytes=await readFile(p.collection_file);
  if(hash(collectionBytes)!==p.collection_sha256) fail('collection_changed');
  return {prepared,collectionBytes};
}
export async function main(args) {
  let p, inputs;
  try {
    const {values}=parseArgs({args,options:{input:{type:'string'},execute:{type:'boolean',default:false}}});
    if(!values.input)fail('input_required');
    p=JSON.parse((await readFile(resolve(values.input),'utf8')).replace(/^\uFEFF/,''));
    inputs=await prepareStage4(p);
    if(!values.execute){process.stdout.write(JSON.stringify({mode:'local_dry_run',passed:true,service_requests:0,
      files:inputs.prepared.files.size,budget:STAGE4_BUDGET,approved:p.approved})+'\n');return 0;}
    if(!p.approved)fail('stage4_approval_required');
  }catch(e){process.stdout.write(JSON.stringify({passed:false,code:codeOf(e),service_requests:0})+'\n');return 2;}
  const report={schema:'pitcheezy-stage4-acceptance-v1',started_at:new Date().toISOString(),passed:false,
    version_pin:p.version_pin,budget:STAGE4_BUDGET,stage3_server_logs:'pending',stage4_server_logs:'pending',
    real_phone:'not_tested',public_app_changed:false,source_build_unchanged:true};
  let browser, view, outputReady=false;
  try {
    await mkdir(resolve(p.out_directory)); outputReady=true;
    await save(join(p.out_directory,'run-started.private.json'),{started_at:report.started_at,run_id:p.run_id,
      version_pin:p.version_pin,budget:STAGE4_BUDGET});
    const accessCode=(await readFile(p.access_code_file,'utf8')).trim();
    const noticeToken=(await readFile(p.notice_token_file,'utf8')).trim();
    if(!/^[^\s\p{Cc}]{8,128}$/u.test(accessCode)||!/^[A-Za-z0-9_-]{43,128}$/.test(noticeToken))fail('credential_file_invalid');
    report.read=await runStage4Read({target:parseOrigin(p.origin),...inputs,accessCode,
      outDir:join(p.out_directory,'read'),versionPin:p.version_pin});
    if(!report.read.passed)fail('read_acceptance_failed');
    process.stdout.write('{"phase":"read_complete","next":"single_tab_observation"}\n');
    const {chromium}=require(resolve(p.playwright_module));
    browser=await chromium.launch({channel:'chrome',headless:true});
    view=await openStage4Browser({browser,origin:p.origin,accessCode,outDir:join(p.out_directory,'browser'),maxRequests:180,versionPin:p.version_pin});
    report.normal=await view.sampleNormal(p.normal_sample_ms);
    process.stdout.write('{"phase":"normal_sample_complete","next":"notice_cycle"}\n');
    report.notice=await runStage4Notice({origin:p.origin,token:noticeToken,outDir:join(p.out_directory,'notice'),versionPin:p.version_pin,runId:p.run_id,
      onActive:async()=>{
        const hidden=await view.waitHidden(p.observation_timeout_ms);
        let synthetic;
        view.setSyntheticGameError(true);
        try{synthetic=await view.waitSyntheticGameError(p.observation_timeout_ms);}
        finally{view.setSyntheticGameError(false);}
        return {hidden,synthetic,evidence_kind:'notice_real_server_plus_browser_synthetic_error'};
      },
      onRestored:()=>view.waitRestored(p.observation_timeout_ms)});
    report.passed=report.notice.passed;
    if(!report.notice.passed)report.failure=report.notice.failure??'notice_acceptance_failed';
  }catch(e){report.failure=codeOf(e);}
  finally{
    if(view){try{report.browser=await view.close();if(report.browser.fatal || !report.browser.logged_out || report.browser.incomplete_or_failed)report.passed=false;}
      catch{report.passed=false;report.cleanup_failure='browser_cleanup_failed';}}
    if(browser)await browser.close().catch(()=>{report.passed=false;report.cleanup_failure='browser_close_failed';});
  }
  report.finished_at=new Date().toISOString();
  if(outputReady){try{await save(join(p.out_directory,'acceptance.private.json'),report);}catch{report.passed=false;report.receipt_written=false;}}
  process.stdout.write(JSON.stringify({passed:report.passed,code:report.failure??null,receipt_written:outputReady&&report.receipt_written!==false,
    notice_off_confirmed:report.notice?.final_off_confirmed??null,phone:'not_tested'})+'\n');
  return report.passed?0:1;
}
if(process.argv[1] && resolve(process.argv[1])===fileURLToPath(import.meta.url))process.exitCode=await main(process.argv.slice(2));

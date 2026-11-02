/** Local received-build rehearsal of the stage4 browser/controller. Never accepts a remote target. */
import { mkdir, writeFile } from 'node:fs/promises';
import { resolve, join } from 'node:path';
import { createRequire } from 'node:module';
import { fileURLToPath } from 'node:url';
import { parseArgs } from 'node:util';
import { prepareSite, makeAssets } from './exhibit-site.mjs';
import { startLocalHost, boundedCleanup } from './rehearsal/local-host.mjs';
import { openStage4Browser } from './exhibit-stage4-browser.mjs';
import { runStage4Notice } from './exhibit-stage4-notice.mjs';
const require=createRequire(import.meta.url);
export async function rehearseStage4({site,receipt,out,playwright}) {
  const prepared=await prepareSite({site,receipt,expectData:6,game:'849843'});
  if(prepared.intake.profile!=='exhibition-c47fe6cb')throw Error('candidate_profile_invalid');
  await mkdir(resolve(out));
  const report={schema:'pitcheezy-stage4-received-local-v1',evidence_kind:'received_build_loopback_real_gateway',
    source_commit:prepared.intake.source_commit,data_generation_commit:prepared.intake.data_generation_commit,
    zip_sha256:prepared.intake.zip.sha256,passed:false,remote_service_requests:0,real_phone:false,
    limitations:['Loopback, ephemeral synthetic credentials and data copy; no Cloudflare setting, production credential or remote service request.',
      '75 seconds of real local polling, not the planned 600-second remote measurement.',
      'Browser intercepted error is synthetic; notice ON/OFF uses our real local gateway.',
      'Routing disables browser cache; Chrome headless 390px is not iPhone Safari.']};
  let host,browser,view;
  try {
    host=await startLocalHost({notice:true,access:{},assets:makeAssets(prepared.files,prepared.classified.static)});
    for(const key of prepared.classified.data){const r=await host.publish('/'+key,prepared.files.get(key).bytes);if(r.status!==200)throw Error('local_upload_failed');await r.arrayBuffer();}
    const {chromium}=require(resolve(playwright));
    browser=await chromium.launch({channel:'chrome',headless:true});
    view=await openStage4Browser({browser,origin:host.origin,accessCode:host.accessCodes[0],outDir:join(out,'browser'),
      versionPin:'00000000-0000-4000-8000-000000000004',allowLoopback:true});
    process.stdout.write('{"phase":"local_browser_ready"}\n');
    report.normal=await view.sampleNormal(75000);
    report.notice=await runStage4Notice({origin:'https://stage4-loopback.invalid',token:'synthetic-local-notice-token-never-a-production-secret',
      outDir:join(out,'notice'),versionPin:'00000000-0000-4000-8000-000000000004',runId:'stage4-local-received-0001',
      fetchImpl:async(url,init)=>{
        if(url!=='https://stage4-loopback.invalid/_notice/v1/state')throw Error('local_adapter_target_refused');
        if(init.method==='GET')return host.noticeState();
        if(init.method==='PUT')return host.setNotice(JSON.parse(init.body),new Headers(init.headers).get('If-Match'));
        throw Error('local_adapter_method_refused');
      },
      onActive:async()=>{const hidden=await view.waitHidden(120000);view.setSyntheticGameError(true);
        let synthetic;try{synthetic=await view.waitSyntheticGameError(120000);}finally{view.setSyntheticGameError(false);}
        return {hidden,synthetic};},
      onRestored:()=>view.waitRestored(120000)});
    report.passed=report.notice.passed;
    if(!report.notice.passed)report.failure=report.notice.failure??'notice_acceptance_failed';
  }catch(e){report.failure=/^[a-z_]+$/.test(e?.message||'')?e.message:'local_rehearsal_failed';}
  finally{
    if(view){try{report.browser=await view.close();if(report.browser.fatal||!report.browser.logged_out||report.browser.incomplete_or_failed)report.passed=false;}
      catch{report.passed=false;report.browser_cleanup='failed';}}
    if(browser)await browser.close().catch(()=>{report.passed=false;});
    if(host){report.local_host_cleanup=await boundedCleanup(()=>host.dispose());if(report.local_host_cleanup.status!=='complete')report.passed=false;}
  }
  await writeFile(join(out,'receipt.json'),JSON.stringify(report,null,2)+'\n',{flag:'wx'});
  return report;
}
if(process.argv[1]&&resolve(process.argv[1])===fileURLToPath(import.meta.url)){
  try{const {values}=parseArgs({options:{site:{type:'string'},receipt:{type:'string'},out:{type:'string'},playwright:{type:'string'}}});
    for(const k of ['site','receipt','out','playwright'])if(!values[k])throw Error('argument_required');
    const r=await rehearseStage4(values);process.stdout.write(JSON.stringify(r)+'\n');process.exitCode=r.passed?0:1;
  }catch{process.stdout.write('{"passed":false,"code":"local_rehearsal_setup_failed"}\n');process.exitCode=2;}
}

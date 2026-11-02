const {test}=require('node:test');
const assert=require('node:assert/strict');
const fs=require('node:fs');
const os=require('node:os');
const path=require('node:path');
const {createHash}=require('node:crypto');
const {spawnSync}=require('node:child_process');
const harness=path.join(__dirname,'exhibition-build-acceptance.cjs');
function fixture(t){
  const root=fs.mkdtempSync(path.join(os.tmpdir(),'pz-browser-pin-'));
  t.after(()=>{const resolved=path.resolve(root);assert.equal(path.dirname(resolved),path.resolve(os.tmpdir()));assert.ok(path.basename(resolved).startsWith('pz-browser-pin-'));fs.rmSync(resolved,{recursive:true,force:true});});
  const site=path.join(root,'site'),out=path.join(root,'out');fs.mkdirSync(site);
  const files={'index.html':'<!doctype html><div id="root"></div>','favicon.svg':'<svg/>','assets/index-test.js':'/* synthetic */','assets/index-test.css':'body{}','v1/manifest.json':'{}','v1/health.json':'{}','v1/dates.json':'{}','v1/game/849843.json':'{}'};
  const entries=[];
  for(const [name,contents]of Object.entries(files)){
    const target=path.join(site,name);fs.mkdirSync(path.dirname(target),{recursive:true});fs.writeFileSync(target,contents);
    const bytes=Buffer.from(contents);entries.push({path:name,bytes:bytes.length,sha256_raw:createHash('sha256').update(bytes).digest('hex')});
  }
  fs.writeFileSync(path.join(root,'intake-receipt.json'),JSON.stringify({schema:'pitcheezy-exhibition-intake-v1',source_commit:'a'.repeat(40),files:entries,catalogue:{missing_date_files:[]}}));
  return {root,site,out};
}
for(const mutation of ['bytes','missing','extra'])test('browser refuses '+mutation+' before server/output/browser starts',t=>{
  const {site,out}=fixture(t);
  if(mutation==='bytes')fs.writeFileSync(path.join(site,'index.html'),'changed');
  if(mutation==='missing')fs.unlinkSync(path.join(site,'index.html'));
  if(mutation==='extra')fs.writeFileSync(path.join(site,'extra.txt'),'extra');
  const run=spawnSync(process.execPath,[harness,site,out],{encoding:'utf8',timeout:15000,env:{...process.env,PLAYWRIGHT_MODULE:'module_must_not_be_loaded'}});
  assert.equal(run.status,1,run.stderr);assert.match(run.stderr,/site_(bytes_mismatch|sha256_mismatch|missing_file|extra_file)/);assert.equal(fs.existsSync(out),false);
});

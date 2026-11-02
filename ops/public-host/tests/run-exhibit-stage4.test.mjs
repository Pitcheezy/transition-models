import test from 'node:test';
import assert from 'node:assert/strict';
import { validateStage4Plan, STAGE4_BUDGET } from '../run-exhibit-stage4.mjs';
const plan=()=>({schema:'pitcheezy-stage4-plan-v1',approved:false,origin:'https://isolated.example.test',run_id:'stage4-synthetic-0001',
 version_pin:'5999cf0d-4f18-4d43-bcd6-320e04860369',site:'site',receipt:'receipt',collection_file:'collection',access_code_file:'access',
 notice_token_file:'notice',playwright_module:'playwright',out_directory:'out',collection_sha256:'a'.repeat(64),
 zip_sha256:'3c3b8006b892872bfff3423e2bd6ba49ea3de17ee92fbecef07e0b076bc8da51',normal_sample_ms:600000,observation_timeout_ms:120000,request_limit:212});
test('stage4 refuses public targets and larger/incomplete plans before I/O',()=>{
 assert.equal(validateStage4Plan(plan()).approved,false);
 for(const host of ['pitcheezy.com','app.pitcheezy.com','www.pitcheezy.com','media.pitcheezy.com'])assert.throws(()=>validateStage4Plan({...plan(),origin:'https://'+host}));
 for(const change of [{approved:'yes'},{request_limit:213},{normal_sample_ms:600001},{observation_timeout_ms:120001},{zip_sha256:'b'.repeat(64)},{version_pin:'no'},{notice_token_file:''}])
 assert.throws(()=>validateStage4Plan({...plan(),...change}));
 assert.equal(STAGE4_BUDGET.read+STAGE4_BUDGET.browser+STAGE4_BUDGET.notice,STAGE4_BUDGET.total);
});

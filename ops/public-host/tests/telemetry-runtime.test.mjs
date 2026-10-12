import test from "node:test";
import assert from "node:assert/strict";
import { randomUUID } from "node:crypto";
import { readFileSync } from "node:fs";
import { fileURLToPath } from "node:url";
import { Miniflare } from "miniflare";
import { saveMeasurement, summarizeTelemetry, cleanupTelemetry } from "../telemetry.mjs";
const origin="https://ui.example.test";
const makeSession=()=>({v:1,consent:true,session_id:randomUUID(),game_pk:123,sequence:0,active_ms:0});
const makeFeedback=()=>({v:1,consent:true,feedback_id:randomUUID(),game_pk:123,rating:"helpful",reason:"none"});
test("actual D1/Worker: opt-in storage, race-safe budget, idempotency, reporting and retention",async()=>{
  const mf=new Miniflare({
    modules:true,scriptPath:fileURLToPath(new URL("../worker.mjs",import.meta.url)),
    compatibilityDate:"2026-07-30",d1Databases:["TELEMETRY_DB"],
    ratelimits:{TELEMETRY_LIMITER:{namespace_id:"1001",simple:{limit:60,period:60}}},
    bindings:{
      TELEMETRY_ENABLED:"true",FEEDBACK_ENABLED:"true",COLLECTION_ORIGIN:origin,
      TELEMETRY_RETAIN_DAYS:"30",SESSION_WRITES_PER_DAY:"100",FEEDBACK_ROWS_PER_DAY:"10",
      TELEMETRY_RATE_SECRET:"synthetic-key-only-not-a-real-account-credential-12345",
    },
  });
  try {
    await mf.ready;
    const db=await mf.getD1Database("TELEMETRY_DB");
    const sql=readFileSync(new URL("../migrations/0001_telemetry.sql",import.meta.url),"utf8");
    await db.batch(sql.split(";").map(x=>x.trim()).filter(Boolean).map(x=>db.prepare(x)));
    const now=Date.parse("2026-10-12T12:00:00Z"),opts={days:30,limit:100};
    const s=makeSession(),s2=makeSession();
    await saveMeasurement(db,s,"session",now,opts);
    await saveMeasurement(db,s,"session",now+1,opts);
    assert.equal((await db.prepare("SELECT used FROM telemetry_budget WHERE kind='session'").first()).used,1);
    await saveMeasurement(db,{...s,sequence:1,active_ms:30000},"session",now+30000,opts);
    await saveMeasurement(db,{...s,sequence:2,active_ms:60000},"session",now+60000,opts);
    await saveMeasurement(db,{...s,sequence:1,active_ms:30000},"session",now+60001,opts);
    await assert.rejects(saveMeasurement(db,{...s,sequence:2,active_ms:30000},"session",now+61000,opts),/identity_conflict/);
    await assert.rejects(saveMeasurement(db,{...s,sequence:3,active_ms:90000},"session",now+60002,opts),/invalid_session_update/);
    await assert.rejects(saveMeasurement(db,{...s,game_pk:999},"session",now+60003,opts),/identity_conflict/);
    await assert.rejects(saveMeasurement(db,{...makeSession(),sequence:1},"session",now,opts),/session_start_required/);
    await saveMeasurement(db,s2,"session",now,opts);
    await Promise.all([
      saveMeasurement(db,{...s2,sequence:1,active_ms:20000},"session",now+30000,opts),
      saveMeasurement(db,{...s2,sequence:2,active_ms:30000},"session",now+30000,opts),
    ]);
    const row=await db.prepare("SELECT * FROM usage_sessions WHERE session_id=?").bind(s2.session_id).first();
    assert.equal(row.active_ms,30000); assert.equal(row.sequence,2);
    const f=makeFeedback();
    await saveMeasurement(db,f,"feedback",now,{days:30,limit:2});
    await saveMeasurement(db,f,"feedback",now+1,{days:30,limit:2});
    await assert.rejects(saveMeasurement(db,{...f,rating:"problem"},"feedback",now+2,opts),/identity_conflict/);
    const concurrent=await Promise.allSettled([
      saveMeasurement(db,makeFeedback(),"feedback",now,{days:30,limit:2}),
      saveMeasurement(db,makeFeedback(),"feedback",now,{days:30,limit:2}),
    ]);
    assert.equal(concurrent.filter(x=>x.status==="fulfilled").length,1);
    assert.match(concurrent.find(x=>x.status==="rejected").reason.message,/daily_limit/);
    const report=await summarizeTelemetry(db,"2026-10-12","2026-10-12",now+60000);
    assert.deepEqual(report.sessions,[{utc_day:"2026-10-12",game_pk:123,sessions:2,active_ms:90000,mean_active_ms:45000}]);
    assert.equal(report.feedback[0].responses,2);
    await assert.rejects(summarizeTelemetry(db,"2026-02-30","2026-10-12",now),/invalid_report_range/);
    assert.equal(JSON.stringify(report).includes(s.session_id),false);
    // Real HTTP/Worker/D1/ratelimit path, with fresh current-day data.
    const value=makeSession();
    const post=()=>mf.dispatchFetch(origin+"/_telemetry/session",{
      method:"POST",headers:{"Content-Type":"application/json",Origin:origin,"CF-Connecting-IP":"192.0.2.1"},
      body:JSON.stringify(value),
    });
    const first=await post(); assert.equal(first.status,200,await first.clone().text());
    assert.deepEqual(await first.json(),{accepted:true});
    assert.equal((await post()).status,200);
    assert.equal((await mf.dispatchFetch(origin+"/_telemetry/session")).status,405);
    const oldReport=await summarizeTelemetry(db,"2026-10-12","2026-10-12",now+31*86400000);
    assert.equal(oldReport.sessions.length,0); assert.equal(oldReport.feedback.length,0);
    await cleanupTelemetry({TELEMETRY_DB:db,TELEMETRY_ENABLED:"false"},now+32*86400000);
    assert.equal((await db.prepare("SELECT COUNT(*) AS n FROM usage_sessions").first()).n,0);
    assert.equal((await db.prepare("SELECT COUNT(*) AS n FROM feedback").first()).n,0);
    assert.equal((await db.prepare("SELECT COUNT(*) AS n FROM telemetry_budget").first()).n,0);
  } finally {await mf.dispose();}
});

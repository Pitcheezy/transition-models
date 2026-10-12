"use strict";
// Synthetic HTTP acknowledgements; no production data, account or Song code.
const {before,after,test}=require("node:test");
const assert=require("node:assert/strict");
const http=require("node:http");
const fs=require("node:fs/promises");
const path=require("node:path");
const playwright=require("playwright");
const ROOT=path.resolve(__dirname,"../..");
const ENGINE=process.env.BROWSER_ENGINE||"chromium";
let browser,server,origin,requests=[],mode="ok",delayed=[];
before(async()=>{
  server=http.createServer(async(req,res)=>{
    if(req.url.startsWith("/_telemetry/")){
      let body="";for await(const chunk of req)body+=chunk;
      requests.push({path:req.url,body:JSON.parse(body),cookie:req.headers.cookie});
      res.setHeader("Content-Type","application/json");
      if(mode==="delay"){delayed.push(res);return;}
      res.statusCode=mode==="fail"?503:200;res.end(mode==="fail"?'{"error":"collection_unavailable"}':'{"accepted":true}');return;
    }
    if(req.url==="/"){
      res.setHeader("Content-Type","text/html; charset=utf-8");
      res.end(`<!doctype html><html lang="ko"><meta name="viewport" content="width=device-width"><title>합성 운영 UI 검사</title><link rel="stylesheet" href="/widget.css"><h1>합성 경기 관전</h1><p>가짜 경기와 응답으로만 검사합니다.</p><div id="slot"></div><script type="module">import{mountUsageWidget}from"/widget.mjs";window.mount=(options)=>{window.widget?.destroy();window.widget=mountUsageWidget(document.querySelector("#slot"),options);};window.ready=true;</script></html>`);return;
    }
    const names=new Set(["/usage-client.mjs","/widget.mjs","/widget.css"]);
    if(!names.has(req.url)){res.statusCode=404;res.end();return;}
    res.setHeader("Content-Type",req.url.endsWith(".css")?"text/css":"text/javascript");
    res.end(await fs.readFile(path.join(ROOT,"ops/public-host/client",req.url.slice(1))));
  });
  await new Promise(r=>server.listen(0,"127.0.0.1",r));origin="http://127.0.0.1:"+server.address().port;
  browser=await playwright[ENGINE].launch({headless:true,...(process.env.BROWSER_CHANNEL?{channel:process.env.BROWSER_CHANNEL}:{})});
});
after(async()=>{
  for(const res of delayed)res.end('{"accepted":true}');
  await browser?.close();await new Promise(r=>server.close(r));
});
async function pageFor(options={}){
  requests=[];mode="ok";delayed=[];
  const context=await browser.newContext({viewport:{width:375,height:700}});
  const page=await context.newPage();await page.clock.install({time:new Date("2026-10-12T12:00:00Z")});
  await page.goto(origin);await page.waitForFunction(()=>window.ready);
  await page.evaluate(opts=>window.mount(opts),options);
  return {page,context};
}
test("default off; keyboard accessible and no unsolicited collection",async()=>{
  const {page,context}=await pageFor();
  assert.equal(await page.getByRole("checkbox",{name:"방문 통계 참여"}).isDisabled(),true);
  await page.clock.fastForward(60000);assert.equal(requests.length,0);await context.close();
});
test("explicit consent, active pulse, credential-omit intent and withdrawal",async(t)=>{
  const {page,context}=await pageFor({enabled:true,gamePk:123});
  await context.addCookies([{name:"private_cookie",value:"must-not-send",url:origin}]);
  const checkbox=page.getByRole("checkbox",{name:"방문 통계 참여"});await checkbox.focus();await page.keyboard.press("Space");
  await page.waitForFunction(()=>document.querySelector('[role="status"]').textContent.startsWith("참여 중"));
  assert.equal(requests[0].body.active_ms,0);
  if(ENGINE==="webkit" && requests[0].cookie) t.diagnostic("Known local WebKit transport limitation: credentials omit requested but cookie arrived; server must not retain headers. Physical Safari pending.");
  else assert.equal(requests[0].cookie,undefined);
  assert.deepEqual(Object.keys(requests[0].body).sort(),["active_ms","consent","game_pk","sequence","session_id","v"]);
  await page.clock.fastForward(30000);
  await page.waitForFunction(()=>document.querySelector('[role="status"]').textContent.startsWith("참여 중"));
  await new Promise(r=>setTimeout(r,100));assert.equal(requests.length,2);
  assert.equal(requests[1].body.active_ms,30000);
  await checkbox.uncheck();await page.clock.fastForward(60000);assert.equal(requests.length,2);
  assert.match(await page.getByRole("status").first().textContent(),/참여하지/);await context.close();
});
test("one-click feedback is separate from usage participation and resends the same ID",async()=>{
  const {page,context}=await pageFor({enabled:true,gamePk:123});mode="fail";
  await page.getByRole("button",{name:"도움이 돼요",exact:true}).click();
  await page.getByText("전송 확인이 안 됐습니다.",{exact:false}).waitFor();
  assert.equal(requests.length,1);assert.equal(requests[0].path,"/_telemetry/feedback");
  assert.equal(await page.getByRole("button",{name:"설명이 어려워요"}).isDisabled(),true);
  mode="ok";await page.getByRole("button",{name:"도움이 돼요",exact:true}).click();
  await page.getByText("의견을 받았습니다. 감사합니다.",{exact:true}).waitFor();
  assert.deepEqual(requests[1].body,requests[0].body);
  assert.equal(await page.getByRole("button",{name:"도움이 돼요",exact:true}).isDisabled(),true);
  await context.close();
});
test("game switch while feedback pending cannot display an old receipt for the new game",async()=>{
  const {page,context}=await pageFor({enabled:true,gamePk:123});mode="delay";
  await page.getByRole("button",{name:"불편한 점이 있어요"}).click();
  while(!delayed.length)await new Promise(r=>setTimeout(r,10));
  await page.evaluate(()=>window.widget.setGame(456));
  for(const res of delayed)res.end('{"accepted":true}');
  await new Promise(r=>setTimeout(r,100));
  assert.equal(await page.getByRole("status").nth(1).textContent(),"");
  mode="ok";await page.getByRole("button",{name:"도움이 돼요",exact:true}).click();
  await page.getByText("의견을 받았습니다. 감사합니다.",{exact:true}).waitFor();
  assert.equal(requests.at(-1).body.game_pk,456);await context.close();
});
test("privacy preference disables collection, widget fits mobile width, teardown is safe",async()=>{
  const {page,context}=await pageFor();
  await page.evaluate(()=>{Object.defineProperty(navigator,"globalPrivacyControl",{value:true,configurable:true});window.mount({enabled:true,gamePk:123});});
  assert.equal(await page.getByRole("checkbox",{name:"방문 통계 참여"}).isDisabled(),true);
  assert.equal(await page.getByRole("button",{name:"도움이 돼요",exact:true}).isDisabled(),true);
  assert.equal(await page.evaluate(()=>document.documentElement.scrollWidth<=innerWidth),true);
  await fs.mkdir(path.join(ROOT,".cache"),{recursive:true});
  await page.screenshot({path:path.join(ROOT,".cache","telemetry-widget-"+ENGINE+".png"),fullPage:true});
  await page.evaluate(()=>{window.widget.destroy();window.widget.destroy();});
  await page.clock.fastForward(60000);assert.equal(requests.length,0);await context.close();
});

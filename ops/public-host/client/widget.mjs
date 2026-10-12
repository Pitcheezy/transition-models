import { createUsageClient } from "./usage-client.mjs";

/** Our standalone adapter; no dependency on or changes to Song's frontend. */
export function mountUsageWidget(container, options={}) {
  const doc=container.ownerDocument;
  const el=(tag,text)=>{const node=doc.createElement(tag);if(text)node.textContent=text;return node;};
  const root=el("section");root.className="pitcheezy-usage-widget";
  root.setAttribute("aria-label","서비스 이용 의견");
  const title=el("strong","함께 다듬는 야구 관전");
  const notice=el("p","방문 통계는 선택 사항입니다. 참여하면 경기별 탭 세션과 화면 활성 시간을 기록합니다. 이름·연락처·페이지 주소는 수집하지 않습니다.");
  const retention=el("p","운영 제안: 기록 30일 보관. 의견 버튼은 선택한 평가만 보냅니다. 아래 기능은 운영 설정 후 활성화됩니다.");
  const label=el("label");const check=el("input");check.type="checkbox";
  label.append(check,doc.createTextNode(" 방문 통계 참여"));
  const state=el("p");state.setAttribute("role","status");state.setAttribute("aria-live","polite");
  const feedbackState=el("p");feedbackState.setAttribute("role","status");feedbackState.setAttribute("aria-live","polite");
  const feedbackGroup=el("div");feedbackGroup.setAttribute("role","group");feedbackGroup.setAttribute("aria-label","짧은 의견");
  const meanings={off:"참여하지 않고 있습니다.",starting:"참여 연결 중입니다.",active:"참여 중입니다. 언제든 해제하면 이후 전송을 멈춥니다.",
    retry:"통계 연결이 지연됩니다. 관전은 계속할 수 있습니다.",paused:"통계 전송을 멈췄습니다. 다시 참여하려면 해제 후 선택하세요.",disabled:"현재 기록·의견 수집이 꺼져 있거나 브라우저의 수집 거부 설정이 켜져 있습니다."};
  const client=createUsageClient({...options,visible:options.visible||(()=>doc.visibilityState==="visible"),
    onStatus:value=>{state.textContent=meanings[value]||meanings.off;}});
  check.disabled=!client.state.enabled;
  state.textContent=client.state.enabled?meanings.off:meanings.disabled;
  check.addEventListener("change",()=>{if(check.checked)void client.grant();else client.withdraw();});
  const buttons=[];
  let generation=0;
  for(const [rating,text] of [["helpful","도움이 돼요"],["unclear","설명이 어려워요"],["problem","불편한 점이 있어요"]]){
    const button=el("button",text);button.type="button";button.disabled=!client.state.enabled;
    button.addEventListener("click",async()=>{
      const current=generation;
      for(const b of buttons)b.disabled=true;
      feedbackState.textContent="의견을 보내는 중입니다.";
      const result=await client.sendFeedback(rating);
      if(disposed || current!==generation)return;
      feedbackState.textContent=result.ok?"의견을 받았습니다. 감사합니다.":"전송 확인이 안 됐습니다. 같은 의견 버튼으로 다시 시도할 수 있습니다.";
      if(!result.ok) for(const b of buttons)b.disabled=b!==button||!client.state.enabled;
    });buttons.push(button);feedbackGroup.append(button);
  }
  root.append(title,notice,retention,label,state,feedbackGroup,feedbackState);
  container.replaceChildren(root);
  const tick=setInterval(()=>void client.flush(),30000);
  const visibility=()=>{client.sample();void client.flush();};
  const pagehide=()=>{void client.flush();};
  doc.addEventListener("visibilitychange",visibility);
  doc.defaultView?.addEventListener("pagehide",pagehide);
  let disposed=false;
  return {
    setGame(gamePk) {
      if(disposed)return;
      const changed=client.state.gamePk!==gamePk;
      client.setGame(gamePk);
      if(changed){generation++;feedbackState.textContent="";for(const b of buttons)b.disabled=!client.state.enabled;}
    },
    destroy(){
      if(disposed)return;disposed=true;clearInterval(tick);client.destroy();
      doc.removeEventListener("visibilitychange",visibility);doc.defaultView?.removeEventListener("pagehide",pagehide);
      root.remove();
    },
  };
}

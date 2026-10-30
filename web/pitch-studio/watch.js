/* Recorded watch mode. One selected pitch is the only source of video and panels. */
(function () {
  "use strict";
  const el = id => document.getElementById(id), video = el("pitch-video");
  let session = null, media = {}, zones = {}, excluded = {}, generation = 1;
  let keys = [], sequence = null, phase = "준비 중", zoneNote = "", sequenceActive = false;
  let timings = {}, resultReady = false, frameRequest = null, frameEpoch = 0;
  let context = null, filterPage = 0, metadata = new Map(), extrasPending = false, routeFailed = false;
  class WatchRouteError extends Error {}
  const filterSize = 12;
  const text = (id, value) => { el(id).textContent = value; };
  const append = (parent, tag, value, className) => {
    const item = document.createElement(tag); item.textContent = value;
    if (className) item.className = className;
    parent.append(item); return item;
  };
  function focusedPitch(id) {
    const active=document.activeElement;
    return el(id).contains(active)?active?.getAttribute("data-pitch-id"):null;
  }
  function restorePitchFocus(id,key) {
    if(!key)return;
    const buttons=Array.from(el(id).children);
    const target=buttons.find(item=>item.getAttribute("data-pitch-id")===key)
      ||buttons.find(item=>item.getAttribute("aria-current")==="true");
    target?.focus({preventScroll:true});
  }
  const view = () => session?.view();
  const binding = () => `${generation}:${view()?.pitch_id}`;
  const clock = value => Number.isFinite(value) && value >= 0
    ? `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, "0")}` : "—";
  function tick() {
    const row = media[view()?.pitch_id];
    text("watch-clock", row && video.getAttribute("src") === row.video
      ? `${clock(video.currentTime)} / ${clock(video.duration)} · 현재 투구 클립` : extrasPending?"영상 자료 확인 중":"영상 미연결");
    transport();
  }
  function timing() { return timings[view()?.pitch_id] || null; }
  function transport() {
    const row=media[view()?.pitch_id], duration=video.duration;
    const ready=Boolean(row && video.getAttribute("src")===row.video && Number.isFinite(duration) && duration>0 && !video.error);
    el("watch-transport").hidden=!row;
    for(const id of ["watch-scrub","watch-toggle","watch-back","watch-forward","watch-rate","watch-mute","watch-fullscreen"]) el(id).disabled=!ready;
    el("watch-toggle").disabled=!row;
    const fraction=ready?Math.max(0,Math.min(1,video.currentTime/duration)):0;
    const scrub=el("watch-scrub");scrub.value=String(Math.round(fraction*1000));
    scrub.style.setProperty("--progress",`${fraction*100}%`);
    scrub.setAttribute("aria-valuetext",`${clock(video.currentTime)} / ${clock(duration)}`);
    text("watch-progress-time",`${clock(video.currentTime)} / ${clock(duration)}`);
    text("watch-toggle",video.error?"↻ 다시 시도":video.paused?"▶ 재생":"Ⅱ 정지");
    el("watch-toggle").setAttribute("aria-label",video.error?"영상 다시 불러오기":video.paused?"재생":"일시정지");
    text("watch-mute",video.muted?"소리 켜기":"음소거");
    el("watch-mute").setAttribute("aria-label",video.muted?"소리 켜기":"음소거");
    el("watch-mute").removeAttribute("aria-pressed");
    const event=timing(), valid=ready && event && event.upper_seconds<duration;
    el("watch-event-marker").hidden=!valid;
    if(valid) el("watch-event-marker").style.left=`${100*event.upper_seconds/duration}%`;
    text("watch-event-label",valid?`◆ ${event.label} ${event.upper_seconds.toFixed(2)}초 · AI 프레임 확인 · 실제 위치 표시`
      :"도착 시점 미확인 · 실제 위치는 클립 종료 후 표시");
  }
  function cancelFrame() {
    frameEpoch++;
    if(frameRequest!==null && video.cancelVideoFrameCallback) video.cancelVideoFrameCallback(frameRequest);
    frameRequest=null;
  }
  function arrival(time) {
    const row=media[view()?.pitch_id];
    if(!session || resultReady || !row || video.error || video.seeking || video.getAttribute("src")!==row.video) return;
    if(PitchWatchTiming.reached(timing(),time,video.duration) && !view().revealed) {
      session.reveal(true);phase="실제 위치 공개";render(true);
    }
  }
  function frames() {
    cancelFrame();
    if(!video.requestVideoFrameCallback) return;
    const epoch=frameEpoch, id=binding();
    const frame=(_,meta)=>{
      frameRequest=null;
      if(epoch!==frameEpoch || id!==binding() || video.paused) return;
      arrival(meta.mediaTime);tick();
      frameRequest=video.requestVideoFrameCallback(frame);
    };
    frameRequest=video.requestVideoFrameCallback(frame);
  }
  function hideResult() {
    const exposed=resultReady||view().revealed;
    resultReady=false;session.reveal(false);phase="추천 확인";
    if(exposed)render(true);else text("watch-phase",phase);
  }
  function stop(reason = "manual") { sequence?.stop(reason); }
  function controls() {
    for(const id of ["watch-filter-pitcher","watch-filter-batter","watch-filter-count","watch-filter-clear","watch-show-recommendations","watch-show-actual","watch-show-mitt"]) el(id).disabled = !session;
    el("watch-game-scrub").disabled = !session;
    el("watch-pa").disabled = !session;
    el("watch-pitch").disabled = !session;
    el("watch-start").disabled = !session || !media[view().pitch_id] || sequenceActive;
    el("watch-stop").disabled = !sequenceActive;
    el("watch-prev").disabled = !session || keys.indexOf(view().pitch_id) === 0;
    el("watch-next").disabled = !session || keys.indexOf(view().pitch_id) >= keys.length - 1;
  }
  const clip = PitchReceiverVideo.create({video,
    section:el("pitch-video-section"),frame:el("pitch-video-frame"),missing:el("pitch-video-missing"),
    status:el("pitch-video-status"),play:el("play-pitch-video"),fallback:el("pitch-video-fallback"),
    inspect:el("inspect-pitch-mitt"),observationImage:el("pitch-observation-image"),
    marker:el("pitch-observation-marker"),observationNote:el("pitch-observation-note"),
    sourceLink:el("pitch-video-source")}, completed => {
      if (!session || completed !== binding()) return;
      resultReady=true;session.reveal(true); phase = "결과 공개"; render(true);
    }, {}, {
      errorMessage: "영상을 불러오지 못했습니다. 다시 시도하거나 ‘이 공 상세 분석’에서 결과를 확인하세요.",
      onEnded: completed => sequence?.ended(completed),
      onInterrupt: reason => {
        if (!session) return;
        stop(reason);
        if (reason === "seek" || reason === "manual") {
          cancelFrame();hideResult();
        } else if (reason === "error") { cancelFrame();hideResult();phase = "영상 오류 · 관전 정지"; text("watch-phase", phase);tick(); }
      },
    });
  function drawLocations(v) {
    const svg = el("watch-location"), model = PitchReceiverLocation.build(v, zones[v.pitch_id] || null);
    const showRecommendations=el("watch-show-recommendations").checked;
    const showActual=el("watch-show-actual").checked;
    svg.replaceChildren();
    const shape = (tag, attrs, content="") => {
      const item = document.createElementNS("http://www.w3.org/2000/svg",tag);
      for (const [key,value] of Object.entries(attrs)) item.setAttribute(key,String(value));
      item.textContent=content; svg.append(item);
    };
    shape("rect",{x:60,y:18,width:200,height:250,class:"location-field"});
    for(let i=0;i<=4;i++) {
      const x=60+i*50;
      shape("line",{x1:x,y1:18,x2:x,y2:268,class:i===2?"location-zero":"location-grid"});
      shape("text",{x,y:297,class:"location-tick","text-anchor":"middle"},String(i-2));
    }
    for(let i=0;i<=5;i++) {
      const y=268-i*50;
      shape("line",{x1:60,y1:y,x2:260,y2:y,class:"location-grid"});
      shape("text",{x:42,y:y+4,class:"location-tick","text-anchor":"end"},String(i));
    }
    shape("text",{x:270,y:297,class:"location-tick"},"x/ft");
    shape("text",{x:12,y:12,class:"location-tick"},"z/ft");
    const outline=model.zone || PitchReceiverLocation.referenceZone();
    if(outline) {
      const x=60+outline.nx*200,y=18+outline.ny*250,w=outline.nw*200,h=outline.nh*250;
      shape("rect",{x,y,width:w,height:h,class:model.zone?"strike-zone":"reference-zone"});
      for(let i=1;i<3;i++) {
        shape("line",{x1:x+w*i/3,y1:y,x2:x+w*i/3,y2:y+h,class:model.zone?"strike-zone-division":"reference-zone-division"});
        shape("line",{x1:x,y1:y+h*i/3,x2:x+w,y2:y+h*i/3,class:model.zone?"strike-zone-division":"reference-zone-division"});
      }
    }
    for(const point of showRecommendations?model.groups:[]) {
      const x=60+point.nx*200,y=18+point.ny*250,mark=PitchReceiverLocation.marker(point);
      shape("rect",{x:x-mark.width/2,y:y-12,width:mark.width,height:24,rx:3,class:"location-recommended"});
      shape("text",{x,y:y+4,"text-anchor":"middle",class:"location-rank"},mark.text);
    }
    if(showActual && model.actual?.status==="plottable") {
      const cx=60+model.actual.nx*200,cy=18+model.actual.ny*250;
      shape("circle",{cx,cy,r:15,class:"location-actual-halo"});
      shape("circle",{cx,cy,r:7,class:"location-actual"});
    }
    text("watch-zone-note", model.zone ? `${v.batter.name} · 기록 존 ${model.zone.bottom.toFixed(2)}–${model.zone.top.toFixed(2)} ft`
      : `점선은 참고 존 · 높이 1.5–3.5ft 예시 · 타자 기록 아님. ${zoneNote || (timing()?"기록 존과 실제 공은 표시된 도착 시점에 공개합니다.":"기록 존과 실제 공은 클립 종료 뒤 표시합니다.")}`);
    const coordinate = p => p.status === "missing" ? "좌표 미제공" : `x ${p.x.toFixed(2)} / z ${p.z.toFixed(2)} ft${p.status==="outside"?" · 도표 밖":""}`;
    const descriptions = showRecommendations?model.recommendations.map(p=>`${p.rank}위 ${p.label}: ${coordinate(p)}`):["추천 점 표시 꺼짐"];
    text("watch-coordinate-note", !showActual?"실제 공 표시 꺼짐 · 결과 카드는 공개 시점에 표시합니다.":model.actual ? `실제 ${coordinate(model.actual)} · 홈플레이트 통과 위치` : "현재 실제 공 위치 숨김 · 추천 근사 위치만 표시");
    if(showActual && model.actual) descriptions.push(`실제 ${resultReady?model.actual.label:"공 위치"}: ${coordinate(model.actual)}`);
    svg.setAttribute("aria-label",`${v.pitch_id} · 포수 시점 · ${descriptions.join("; ")}`);
  }
  function renderMitt(v) {
    el("watch-mitt-panel").hidden=!el("watch-show-mitt").checked;
    el("watch-mitt-axis").hidden=true;
    text("watch-mitt-value","—");
    if(!resultReady || !v?.revealed){text("watch-mitt-status","클립 종료 뒤 받은 가로 관측을 확인할 수 있습니다.");return;}
    const observation=PitchReceiverFullGame.observation(v);
    if(observation.status!=="estimated"){
      text("watch-mitt-status",observation.status==="unavailable"?"이 투구는 판독 기권 · 좌표 없음":"이 투구의 미트 관측은 미제공입니다.");return;
    }
    text("watch-mitt-value",`x ${observation.x.toFixed(4)} ft`);
    if(observation.x < -2 || observation.x > 2){text("watch-mitt-status","받은 가로 추정이 표시 범위 밖입니다. 끝점으로 옮겨 그리지 않습니다.");return;}
    text("watch-mitt-status","받은 셋업 가로 추정 · 영상 프레임 대응 미검증");
    el("watch-mitt-axis").hidden=false;
    el("watch-mitt-dot").style.left=`${(observation.x+2)*25}%`;
    el("watch-mitt-axis").setAttribute("aria-label",`포수 시점 가로 추정 ${observation.x.toFixed(4)} ft. 높이·의도·제구 오차 아님`);
  }
  function renderContext(v) {
    if(!context)return;
    const focused=focusedPitch("watch-ribbon");
    text("watch-situation-line",context.situation(v.pitch_id));
    text("watch-ribbon-title",`${v.at_bat_number}번째 타석 · 투구 순서`);
    el("watch-ribbon").replaceChildren();
    for(const p of context.ribbon(v.pitch_id,resultReady)){
      const button=append(el("watch-ribbon"),"button","",`watch-pitch-chip kind-${p.kind}`);
      button.type="button";button.setAttribute("data-pitch-id",p.key);
      if(p.isCurrent)button.setAttribute("aria-current","true");
      button.setAttribute("aria-label",`${p.pitchNumber}구 · ${p.label}${p.isCurrent?" · 현재 공":""}`);
      append(button,"strong",`${p.pitchNumber}구`,"chip-number");append(button,"span",p.label,"chip-label");
      button.addEventListener("click",()=>select(p.key));
    }
    restorePitchFocus("watch-ribbon",focused);
    const prior=context.prior(v.pitch_id);
    text("watch-history-title",`${v.pitcher.name} · 앞선 선택`);
    text("watch-history-summary",prior.total
      ?`이 공 이전 ${prior.total}구 · 평균 ${prior.averageMph===null?"미제공":`${prior.averageMph.toFixed(1)} mph`} · 구속 기록 ${prior.speedCount}구`
      :"이 투수의 이번 경기 첫 공입니다. 비교할 이전 투구가 아직 없습니다.");
    el("watch-history-list").replaceChildren();
    for(const type of prior.types){
      const row=append(el("watch-history-list"),"div","","watch-history-row");
      append(row,"strong",type.label);
      const track=append(row,"div","","history-bar");track.setAttribute("aria-hidden","true");
      append(track,"i","").style.width=`${type.share*100}%`;
      append(row,"span",`${type.count}구 · ${(100*type.share).toFixed(1)}%`);
      append(row,"small",type.averageMph===null?"구속 미제공":`${type.averageMph.toFixed(1)} mph · ${type.speedCount}구`);
    }
  }
  function initFilters() {
    const options=context.options();
    for(const [id,label,items] of [["watch-filter-pitcher","전체 투수",options.pitchers],["watch-filter-batter","전체 타자",options.batters],["watch-filter-count","전체 카운트",options.counts]]){
      el(id).replaceChildren();append(el(id),"option",label).value="all";
      for(const item of items)append(el(id),"option",item.name||item.label).value=item.id||item.value;
      el(id).value="all";
    }
  }
  function renderFilters() {
    if(!context || !session)return;
    const focused=focusedPitch("watch-filter-results");
    const matches=context.matchingKeys({pitcher:el("watch-filter-pitcher").value,batter:el("watch-filter-batter").value,count:el("watch-filter-count").value});
    const pages=Math.max(1,Math.ceil(matches.length/filterSize));filterPage=Math.min(filterPage,pages-1);
    text("watch-filter-status",matches.length?`${matches.length}구 일치 · ${filterPage+1}/${pages}쪽${matches.includes(view().pitch_id)?"":" · 지금 보는 공은 조건 밖"}`:"조건에 맞는 투구가 없습니다. 조건을 바꾸거나 초기화하세요.");
    el("watch-filter-results").replaceChildren();
    for(const key of matches.slice(filterPage*filterSize,(filterPage+1)*filterSize)){
      const p=metadata.get(key),s=p.situation;
      const button=append(el("watch-filter-results"),"button","","watch-filter-item");button.type="button";
      button.setAttribute("data-pitch-id",key);
      if(key===view().pitch_id)button.setAttribute("aria-current","true");
      append(button,"strong",`${s.inning}회 ${s.half==="Top"?"초":"말"} · PA${p.at_bat_number} · ${p.pitch_number}구`);
      append(button,"span",`${p.pitcher.name} → ${p.batter.name}`);
      append(button,"small",`${s.balls}볼 ${s.strikes}스트라이크`);
      button.addEventListener("click",()=>select(key));
    }
    el("watch-filter-prev").disabled=filterPage<=0;
    el("watch-filter-next").disabled=filterPage>=pages-1;
    restorePitchFocus("watch-filter-results",focused);
  }
  function render(preservePosition=false) {
    if (!session) return;
    const v=view(),s=v.situation;
    for(const id of ["pitch-video-section","watch-candidates","watch-location","watch-result"]) el(id).setAttribute("data-pitch-id",v.pitch_id);
    text("watch-score",`${s.inning}회 ${s.half==="Top"?"초":"말"} · CHC ${s.away_score} : ${s.home_score} SD · ${s.balls}B ${s.strikes}S · ${s.outs} OUT`);
    const bases=[1,2,4].flatMap((bit,i)=>s.bases&bit?[`${i+1}루`]:[]);
    text("watch-players",`${v.pitcher.name} → ${v.batter.name} · ${bases.length?bases.join("·"):"주자 없음"}`);
    text("watch-identity",`${v.at_bat_number}번째 타석 · ${v.pitch_number}구 · ${v.pitch_id} · ${v.position}/${v.count}구`);
    text("watch-phase",phase);
    renderContext(v);renderFilters();renderMitt(v);
    for(const id of ["watch-back-analysis","watch-detail-current","watch-detail-footer"]) el(id).href=`receiver.html?game=849843&pitch=${encodeURIComponent(v.pitch_id)}`;
    gamePosition(keys.indexOf(v.pitch_id),true);
    el("watch-pa").value=String(v.at_bat_number);
    const group=session.groups().find(g=>g.pa===v.at_bat_number);
    el("watch-pitch").replaceChildren();
    for(const pitch of group.pitches) append(el("watch-pitch"),"option",`${pitch.pitch_number}구`).value=pitch.key;
    el("watch-pitch").value=v.pitch_id;
    el("watch-candidates").replaceChildren();
    const best=v.pre.status==="ready"?v.pre.candidates[0]:null;
    text("watch-best-summary",best?`추천 1위 · ${best.pitch_label}`:"이 공의 추천은 미지원입니다.");
    if(v.pre.status!=="ready") append(el("watch-candidates"),"p","이 투구의 추천은 미지원입니다.");
    for(const c of v.pre.candidates) {
      const row=append(el("watch-candidates"),"div","","watch-candidate");
      append(row,"strong",`${c.rank} · ${c.pitch_label}`);
      append(row,"span",c.selection_probability==null?"비중 미제공":`${(100*c.selection_probability).toFixed(1)}%`);
      append(row,"small",c.target?`x ${c.target.x.toFixed(2)} / z ${c.target.z.toFixed(2)} ft`:"추천 위치 미제공");
    }
    const a=v.post?.actual;
    el("watch-result").hidden=false;
    text("watch-result",resultReady && v.revealed && a
      ? `${a.pitch_label ?? "구종 미제공"} · ${a.result_label ?? a.event_label ?? "결과 미제공"}${a.speed_mph==null?"":` · ${a.speed_mph.toFixed(1)} mph`}${a.event_label && a.event_label!==a.result_label?` · ${a.event_label}`:""}`
      : v.revealed ? "실제 위치 공개 · 구종·판정·타구 결과는 클립 종료 후 공개합니다." : "실제 선택은 영상이 끝나면 공개합니다.");
    el("watch-result").classList.toggle("is-revealed",resultReady);
    drawLocations(v);
    clip.update({enabled:true,context:generation,pitch_id:v.pitch_id,revealed:v.revealed,media,
      observationAllowed:false,preservePosition});
    el("play-pitch-video").hidden=true;
    el("inspect-pitch-mitt").hidden=true;
    if(media[v.pitch_id] && !resultReady) text("pitch-video-status",timing()
      ? `${v.pitch_number}구 · 공 도착 시점의 실제 위치를 먼저 표시하고 전체 결과는 클립 종료 후 공개합니다.`
      : `${v.pitch_number}구 · 도착 시점 미확인. 클립 종료 뒤 저장 결과를 공개합니다.`);
    const missing=el("pitch-video-missing");
    if(extrasPending)text("pitch-video-status","영상 자료 확인 중 · 추천과 투구 순서를 먼저 살펴볼 수 있습니다.");
    missing.textContent=extrasPending?"영상 자료 확인 중입니다. 잠시 기다려 주세요.":excluded[v.pitch_id]
      ? "구종 기록이 달라 영상을 연결하지 않았습니다. 다른 투구를 고르거나 상세 분석에서 결과를 확인하세요."
      : "확인된 영상을 불러오지 못했습니다. 다른 투구를 고르거나 상세 분석에서 결과를 확인하세요.";
    controls();tick();
  }
  function select(key,historyMode="push") {
    if(!keys.includes(key))throw new WatchRouteError();
    stop();cancelFrame();resultReady=false;session.select(key);phase="추천 확인";render(); remember(historyMode);
  }
  function gamePosition(index,commit=false) {
    const key=keys[index];if(!key)return;
    const [,pa,pitch]=key.split(":");
    const label=`${index+1} / ${keys.length}구 · ${pa}번째 타석 ${pitch}구`;
    text("watch-game-position",label);
    el("watch-game-scrub").setAttribute("aria-valuetext",label);
    if(commit){el("watch-game-scrub").max=String(keys.length);el("watch-game-scrub").value=String(index+1);}
  }
  function remember(mode="push") {
    const query=`?game=849843&pitch=${encodeURIComponent(view().pitch_id)}`;
    if(location.search!==query) history[mode==="replace"?"replaceState":"pushState"](null,"",`${location.pathname}${query}`);
  }
  function createSequence() {
    stop();
    const scope=el("watch-play-scope").value;
    sequence=PitchReceiverSequence.create({scope,
      getState:()=>{
        const v=view(),group=session.groups().find(g=>g.pa===v.at_bat_number),order=scope==="game"?keys:group.keys;
        return {enabled:true,binding:binding(),pa:v.at_bat_number,pitchId:v.pitch_id,revealed:v.revealed,
          nextId:order[order.indexOf(v.pitch_id)+1]||null,hasVideo:Boolean(media[v.pitch_id])};
      },
      startClip:()=>{cancelFrame();resultReady=false;session.reveal(false);phase="영상 재생";render();return clip.restart();},
      advance:key=>{cancelFrame();resultReady=false;session.select(key);phase="추천 확인";render();remember("replace");},
      onChange:({active,phase:sequencePhase,reason})=>{
        sequenceActive=active;controls();
        text("watch-sequence-status",sequencePhase==="waiting"?"결과 확인 · 5초 뒤 다음 공으로 이어집니다."
          :active?`${scope==="game"?"경기 끝까지":"현재 타석"} 이어보기 중`
          :reason==="complete"?`${scope==="game"?"저장 경기":"현재 타석"} 관전을 마쳤습니다.`
          :reason==="missing"?"영상이 없는 투구에서 멈췄습니다. 다음 공은 직접 선택해 주세요."
          :reason==="blocked"?"재생이 차단돼 멈췄습니다. 재생 버튼으로 다시 시작해 주세요."
          :"이어보기 정지 · ‘이어보기 시작’을 누르면 현재 공부터 다시 시작합니다.");
      },
    });
  }
  async function asset(name) {
    const controller=new AbortController(), deadline=Date.now()+10000;
    let timer;
    const checkDeadline=()=>{if(controller.signal.aborted || Date.now()>=deadline)throw new Error("자료 확인 시간 초과");};
    const timeout=new Promise((_,reject)=>{timer=setTimeout(()=>{
      reject(new Error("자료 확인 시간 초과"));controller.abort();
    },10000);});
    const load=(async()=>{
      const response=await fetch(name,{credentials:"omit",signal:controller.signal});
      checkDeadline();if(!response.ok) throw new Error("저장 자료 요청 실패");
      const bytes=await response.arrayBuffer();checkDeadline();
      if(bytes.byteLength>5*1024*1024) throw new Error("자료 크기 초과");
      const digest=await crypto.subtle.digest("SHA-256",bytes);checkDeadline();
      const packet=JSON.parse(new TextDecoder("utf-8",{fatal:true}).decode(bytes));checkDeadline();
      return {packet,hash:Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,"0")).join("")};
    })();
    try{return await Promise.race([load,timeout]);}finally{clearTimeout(timer);}
  }
  function fail(error) {
    routeFailed=error instanceof WatchRouteError;extrasPending=false;
    stop();cancelFrame();resultReady=false;clip.update(null);session=null;generation++;controls();transport();
    for(const id of ["watch-score","watch-players","watch-identity","watch-result","watch-coordinate-note","watch-zone-note"]) text(id,"");
    el("watch-location").replaceChildren();el("watch-candidates").replaceChildren();
    el("watch-location").removeAttribute("aria-label");
    el("watch-result").hidden=true;el("watch-result").classList.toggle("is-revealed",false);
    el("watch-pa").replaceChildren();el("watch-pitch").replaceChildren();
    text("watch-game-position","경기 자료 미연결");
    context=null;metadata.clear();
    for(const id of ["watch-ribbon","watch-history-list","watch-filter-results"])el(id).replaceChildren();
    for(const id of ["watch-situation-line","watch-history-summary","watch-filter-status","watch-best-summary"])text(id,"");
    text("watch-ribbon-title","이 타석의 투구 순서");text("watch-history-title","이 투수의 앞선 선택");
    for(const id of ["watch-filter-pitcher","watch-filter-batter","watch-filter-count"])el(id).replaceChildren();
    el("watch-filter-prev").disabled=true;el("watch-filter-next").disabled=true;
    renderMitt(null);el("watch-mitt-panel").hidden=true;
    el("watch-retry").hidden=false;
    text("watch-retry",routeFailed?"첫 공으로 이동":"자료 다시 불러오기");
    text("watch-phase","자료 확인 실패");text("watch-load-status",routeFailed
      ?"지원하지 않는 주소입니다. ‘첫 공으로 이동’을 누르거나 경기 선택에서 다시 시작해 주세요."
      :"저장 경기 자료를 확인하지 못했습니다. ‘자료 다시 불러오기’를 누르거나 경기 선택에서 다시 시작해 주세요.");
  }
  function route() {
    const q=new URLSearchParams(location.search);
    if(q.getAll("game").length>1||q.getAll("pitch").length>1||q.has("game")&&q.get("game")!=="849843") throw new WatchRouteError();
    return q.get("pitch")||"849843:1:1";
  }
  el("watch-retry").addEventListener("click",()=>routeFailed
    ?location.replace("watch.html?game=849843&pitch=849843%3A1%3A1"):location.reload());
  el("watch-start").addEventListener("click",()=>{if(session){createSequence();sequence.start();}});
  el("watch-stop").addEventListener("click",()=>{stop();clip.pause();});
  el("watch-play-scope").addEventListener("change",()=>{stop();clip.pause();});
  el("watch-pa").addEventListener("change",()=>{if(session)select(session.groups().find(g=>g.pa===Number(el("watch-pa").value)).keys[0]);});
  el("watch-pitch").addEventListener("change",()=>{if(session)select(el("watch-pitch").value);});
  for(const id of ["watch-filter-pitcher","watch-filter-batter","watch-filter-count"])el(id).addEventListener("change",()=>{
    if(!session)return;stop();clip.pause();filterPage=0;renderFilters();
  });
  el("watch-filter-clear").addEventListener("click",()=>{
    if(!session)return;stop();clip.pause();
    for(const id of ["watch-filter-pitcher","watch-filter-batter","watch-filter-count"])el(id).value="all";
    filterPage=0;renderFilters();
  });
  for(const [id,delta] of [["watch-filter-prev",-1],["watch-filter-next",1]])el(id).addEventListener("click",()=>{
    if(!session)return;filterPage=Math.max(0,filterPage+delta);renderFilters();
  });
  for(const id of ["watch-show-recommendations","watch-show-actual","watch-show-mitt"])el(id).addEventListener("change",()=>{
    if(session){drawLocations(view());renderMitt(view());}
  });
  el("watch-game-scrub").addEventListener("input",()=>{
    if(!session)return;
    stop("seek");clip.pause();
    const value=Number(el("watch-game-scrub").value);
    if(Number.isInteger(value)&&value>=1&&value<=keys.length)gamePosition(value-1);
  });
  el("watch-game-scrub").addEventListener("change",()=>{
    if(!session)return;
    const value=Number(el("watch-game-scrub").value);
    if(Number.isInteger(value)&&value>=1&&value<=keys.length)select(keys[value-1]);
    else gamePosition(keys.indexOf(view().pitch_id),true);
  });
  for(const [id,delta] of [["watch-prev",-1],["watch-next",1]]) el(id).addEventListener("click",()=>{
    const key=keys[keys.indexOf(view()?.pitch_id)+delta];if(key&&session)select(key);
  });
  video.addEventListener("play",()=>{if(session){phase="영상 재생";text("watch-phase",phase);}});
  video.addEventListener("pause",()=>{if(session&&!video.ended&&video.paused){phase="일시정지";text("watch-phase",phase);}});
  video.addEventListener("waiting",()=>{if(session&&!video.paused)text("watch-phase","영상 불러오는 중 · 같은 투구 유지");});
  video.addEventListener("playing",()=>{if(session){text("watch-phase",view().revealed?"실제 위치 공개":"영상 재생");frames();}});
  video.addEventListener("timeupdate",()=>{if(!video.requestVideoFrameCallback && !video.paused)arrival(video.currentTime);tick();});
  video.addEventListener("seeked",()=>{arrival(video.currentTime);tick();if(!video.paused)frames();});
  for(const event of ["loadedmetadata","emptied","play","pause","volumechange","durationchange"]) video.addEventListener(event,tick);
  function seek(time) {
    if(!session || !Number.isFinite(video.duration) || video.duration<=0 || !Number.isFinite(time)) return;
    stop("seek");cancelFrame();hideResult();
    video.currentTime=Math.max(0,Math.min(video.duration,time));tick();
  }
  el("watch-toggle").addEventListener("click",()=>{stop("manual");if(session&&video.ended){cancelFrame();hideResult();}clip.toggle();});
  el("watch-back").addEventListener("click",()=>seek(video.currentTime-3));
  el("watch-forward").addEventListener("click",()=>seek(video.currentTime+3));
  el("watch-scrub").addEventListener("input",()=>seek(Number(el("watch-scrub").value)*video.duration/1000));
  el("watch-rate").addEventListener("change",()=>{
    const rate=Number(el("watch-rate").value);if([0.5,0.75,1,1.25].includes(rate))video.playbackRate=rate;
  });
  el("watch-mute").addEventListener("click",()=>{video.muted=!video.muted;transport();});
  el("watch-fullscreen").addEventListener("click",async()=>{
    try {
      if(document.fullscreenElement)await document.exitFullscreen();
      else if(el("pitch-video-section").requestFullscreen)await el("pitch-video-section").requestFullscreen();
      else if(video.webkitEnterFullscreen)video.webkitEnterFullscreen();
      else text("pitch-video-status","이 브라우저에서는 전체 화면을 지원하지 않습니다. 현재 화면에서 재생할 수 있습니다.");
    }catch(_){text("pitch-video-status","전체 화면을 열지 못했습니다. 현재 화면에서 재생할 수 있습니다.");}
  });
  document.addEventListener("visibilitychange",()=>{if(document.hidden){stop();clip.pause();}});
  window.addEventListener("pagehide",()=>{stop();clip.pause();});
  window.addEventListener("popstate",()=>{if(session)try{select(route(),"replace");}catch(error){fail(error);}});
  (async()=>{
    try {
      route();
      const game=await asset("game-849843.json?v=1"),first=route();
      session=PitchReceiverFullGame.createVerifiedSession(game.packet,game.hash);
      keys=session.groups().flatMap(g=>g.keys);
      if(!keys.includes(first))throw new WatchRouteError();
      session.select(first);
      context=PitchWatchContext.create(game.packet.pitches);
      metadata=new Map(game.packet.pitches.map(p=>[p.pitch_id,{pitch_id:p.pitch_id,at_bat_number:p.at_bat_number,pitch_number:p.pitch_number,situation:p.situation,pitcher:p.pitcher,batter:p.batter}]));
      initFilters();
      el("watch-pa").replaceChildren();
      for(const group of session.groups()) append(el("watch-pa"),"option",`${group.inning}회 ${group.half==="Top"?"초":"말"} · PA${group.pa} · ${group.batter}`).value=group.pa;
      phase="추천 확인";extrasPending=true;render();remember("replace");video.controls=false;
      text("watch-load-status","경기 자료 준비됨 · 영상·존 자료를 확인 중입니다. 투구를 먼저 살펴볼 수 있습니다.");
      const loadGeneration=generation;
      const extra=await Promise.allSettled([asset("game-849843-media.json?v=1"),asset("game-849843-zones.json?v=1"),asset("game-849843-timing.json?v=1")]);
      if(!session || generation!==loadGeneration)return;
      extrasPending=false;
      let incomplete=false;
      if(extra[0].status==="fulfilled") try {
        const received=PitchReceiverGameMedia.createVerifiedMedia(extra[0].value.packet,game.packet,extra[0].value.hash,window.PitchReceiverMedia||{});
        media=received.media;excluded=received.excluded;
      } catch (_) { incomplete=true; /* No unverified media fallback. */ }
      else incomplete=true;
      if(extra[1].status==="fulfilled") try {zones=PitchReceiverZones.createVerifiedZones(extra[1].value.packet,game.packet,extra[1].value.hash);}catch(_){incomplete=true;zoneNote="기록 존 확인 실패 · 참고 존만 표시";}
      else {incomplete=true;zoneNote="기록 존 미연결 · 참고 존만 표시";}
      if(extra[2].status==="fulfilled")try{timings=PitchWatchTiming.createVerifiedTiming(extra[2].value.packet,media,extra[2].value.hash);}catch(_){incomplete=true; /* Unverified timing must fall back to clip end. */ }
      else incomplete=true;
      render(true);
      el("watch-retry").hidden=!incomplete;
      text("watch-load-status",`저장 경기 262구 · 추천246/미지원16 · 영상${Object.keys(media).length}구 · 기록 자료 재생${incomplete?" · 일부 자료를 확인하지 못했습니다. ‘자료 다시 불러오기’로 재시도할 수 있습니다.":""}`);
    } catch(error){fail(error);}
  })();
})();

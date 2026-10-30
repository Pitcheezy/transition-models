/* Recorded watch mode. One selected pitch is the only source of video and panels. */
(function () {
  "use strict";
  const el = id => document.getElementById(id), video = el("pitch-video");
  let session = null, media = {}, zones = {}, excluded = {}, generation = 1;
  let keys = [], sequence = null, phase = "준비 중", zoneNote = "", sequenceActive = false;
  const text = (id, value) => { el(id).textContent = value; };
  const append = (parent, tag, value, className) => {
    const item = document.createElement(tag); item.textContent = value;
    if (className) item.className = className;
    parent.append(item); return item;
  };
  const view = () => session?.view();
  const binding = () => `${generation}:${view()?.pitch_id}`;
  const clock = value => Number.isFinite(value) && value >= 0
    ? `${Math.floor(value / 60)}:${String(Math.floor(value % 60)).padStart(2, "0")}` : "—";
  function tick() {
    const row = media[view()?.pitch_id];
    text("watch-clock", row && video.getAttribute("src") === row.video
      ? `${clock(video.currentTime)} / ${clock(video.duration)} · 현재 투구 클립` : "영상 미연결");
  }
  function stop(reason = "manual") { sequence?.stop(reason); }
  function controls() {
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
      session.reveal(true); phase = "결과 공개"; render(true);
    }, {}, {
      onEnded: completed => sequence?.ended(completed),
      onInterrupt: reason => {
        if (!session) return;
        stop(reason);
        if (reason === "seek" || reason === "manual") {
          session.reveal(false); phase = "추천 확인"; render(true);
        } else if (reason === "error") { phase = "영상 오류 · 관전 정지"; text("watch-phase", phase); }
      },
    });
  function drawLocations(v) {
    const svg = el("watch-location"), model = PitchReceiverLocation.build(v, zones[v.pitch_id] || null);
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
    if(model.zone) {
      const x=60+model.zone.nx*200,y=18+model.zone.ny*250,w=model.zone.nw*200,h=model.zone.nh*250;
      shape("rect",{x,y,width:w,height:h,class:"strike-zone"});
      for(let i=1;i<3;i++) {
        shape("line",{x1:x+w*i/3,y1:y,x2:x+w*i/3,y2:y+h,class:"strike-zone-division"});
        shape("line",{x1:x,y1:y+h*i/3,x2:x+w,y2:y+h*i/3,class:"strike-zone-division"});
      }
    }
    for(const point of model.groups) {
      const x=60+point.nx*200,y=18+point.ny*250,mark=PitchReceiverLocation.marker(point);
      shape("rect",{x:x-mark.width/2,y:y-12,width:mark.width,height:24,rx:3,class:"location-recommended"});
      shape("text",{x,y:y+4,"text-anchor":"middle",class:"location-rank"},mark.text);
    }
    if(model.actual?.status==="plottable") {
      const cx=60+model.actual.nx*200,cy=18+model.actual.ny*250;
      shape("circle",{cx,cy,r:15,class:"location-actual-halo"});
      shape("circle",{cx,cy,r:7,class:"location-actual"});
    }
    text("watch-zone-note", model.zone ? `${v.batter.name} · 기록 존 ${model.zone.bottom.toFixed(2)}–${model.zone.top.toFixed(2)} ft`
      : zoneNote || "기록 존과 실제 공은 클립 종료 뒤 표시합니다.");
    const coordinate = p => p.status === "missing" ? "좌표 미제공" : `x ${p.x.toFixed(2)} / z ${p.z.toFixed(2)} ft${p.status==="outside"?" · 도표 밖":""}`;
    const descriptions = model.recommendations.map(p=>`${p.rank}위 ${p.label}: ${coordinate(p)}`);
    text("watch-coordinate-note", model.actual ? `실제 ${coordinate(model.actual)} · 홈플레이트 통과 위치` : "현재 실제 공 위치 숨김 · 추천 근사 위치만 표시");
    if(model.actual) descriptions.push(`실제 ${model.actual.label}: ${coordinate(model.actual)}`);
    svg.setAttribute("aria-label",`${v.pitch_id} · 포수 시점 · ${descriptions.join("; ")}`);
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
    el("watch-back-analysis").href=`receiver.html?game=849843&pitch=${encodeURIComponent(v.pitch_id)}`;
    el("watch-pa").value=String(v.at_bat_number);
    const group=session.groups().find(g=>g.pa===v.at_bat_number);
    el("watch-pitch").replaceChildren();
    for(const pitch of group.pitches) append(el("watch-pitch"),"option",`${pitch.pitch_number}구`).value=pitch.key;
    el("watch-pitch").value=v.pitch_id;
    el("watch-candidates").replaceChildren();
    if(v.pre.status!=="ready") append(el("watch-candidates"),"p","이 투구의 추천은 미지원입니다.");
    for(const c of v.pre.candidates) {
      const row=append(el("watch-candidates"),"div","","watch-candidate");
      append(row,"strong",`${c.rank} · ${c.pitch_label}`);
      append(row,"span",c.selection_probability==null?"비중 미제공":`${(100*c.selection_probability).toFixed(1)}%`);
      append(row,"small",c.target?`x ${c.target.x.toFixed(2)} / z ${c.target.z.toFixed(2)} ft`:"추천 위치 미제공");
    }
    const a=v.post?.actual;
    el("watch-result").hidden=false;
    text("watch-result",v.revealed && a
      ? `${a.pitch_label ?? "구종 미제공"} · ${a.result_label ?? a.event_label ?? "결과 미제공"}${a.speed_mph==null?"":` · ${a.speed_mph.toFixed(1)} mph`}${a.event_label && a.event_label!==a.result_label?` · ${a.event_label}`:""}`
      : "영상이 끝나면 실제 구종·판정·위치를 공개합니다.");
    el("watch-result").classList.toggle("is-revealed",v.revealed);
    drawLocations(v);
    clip.update({enabled:true,context:generation,pitch_id:v.pitch_id,revealed:v.revealed,media,
      observationAllowed:false,preservePosition});
    const missing=el("pitch-video-missing");
    missing.textContent=excluded[v.pitch_id]
      ? "구종 기록이 달라 영상을 연결하지 않았습니다. 다른 투구를 고르거나 상세 분석에서 결과를 확인하세요."
      : "확인된 영상을 불러오지 못했습니다. 다른 투구를 고르거나 상세 분석에서 결과를 확인하세요.";
    controls();tick();
  }
  function select(key,historyMode="push") {
    stop(); session.select(key);phase="추천 확인";render(); remember(historyMode);
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
      startClip:()=>{session.reveal(false);phase="영상 재생";render();return clip.restart();},
      advance:key=>{session.select(key);phase="추천 확인";render();remember("replace");},
      onChange:({active,phase:sequencePhase,reason})=>{
        sequenceActive=active;controls();
        text("watch-sequence-status",sequencePhase==="waiting"?"결과 확인 · 5초 뒤 다음 공으로 이어집니다."
          :active?`${scope==="game"?"경기 끝까지":"현재 타석"} 이어보기 중`
          :reason==="complete"?`${scope==="game"?"저장 경기":"현재 타석"} 관전을 마쳤습니다.`
          :reason==="missing"?"영상이 없는 투구에서 멈췄습니다. 다음 공은 직접 선택해 주세요."
          :reason==="blocked"?"재생이 차단돼 멈췄습니다. 재생 버튼으로 다시 시작해 주세요."
          :"이어보기 정지 · 관전 시작을 누르면 현재 공부터 다시 시작합니다.");
      },
    });
  }
  async function asset(name) {
    const response=await fetch(name,{credentials:"omit"});
    if(!response.ok) throw new Error("저장 자료 요청 실패");
    const bytes=await response.arrayBuffer();if(bytes.byteLength>5*1024*1024) throw new Error("자료 크기 초과");
    const digest=await crypto.subtle.digest("SHA-256",bytes);
    return {packet:JSON.parse(new TextDecoder("utf-8",{fatal:true}).decode(bytes)),hash:Array.from(new Uint8Array(digest),b=>b.toString(16).padStart(2,"0")).join("")};
  }
  function fail(error) {
    stop();clip.update(null);session=null;generation++;controls();
    for(const id of ["watch-score","watch-players","watch-identity","watch-result","watch-coordinate-note","watch-zone-note"]) text(id,"");
    el("watch-location").replaceChildren();el("watch-candidates").replaceChildren();
    el("watch-pa").replaceChildren();el("watch-pitch").replaceChildren();
    text("watch-phase","자료 확인 실패");text("watch-load-status",`${error.message}. 경기 선택에서 다시 시작해 주세요.`);
  }
  function route() {
    const q=new URLSearchParams(location.search);
    if(q.getAll("game").length>1||q.getAll("pitch").length>1||q.has("game")&&q.get("game")!=="849843") throw new Error("지원하지 않는 경기 주소");
    return q.get("pitch")||"849843:1:1";
  }
  el("watch-start").addEventListener("click",()=>{if(session){createSequence();sequence.start();}});
  el("watch-stop").addEventListener("click",()=>{stop();clip.pause();});
  el("watch-play-scope").addEventListener("change",()=>{stop();clip.pause();});
  el("watch-pa").addEventListener("change",()=>{if(session)select(session.groups().find(g=>g.pa===Number(el("watch-pa").value)).keys[0]);});
  el("watch-pitch").addEventListener("change",()=>{if(session)select(el("watch-pitch").value);});
  for(const [id,delta] of [["watch-prev",-1],["watch-next",1]]) el(id).addEventListener("click",()=>{
    const key=keys[keys.indexOf(view()?.pitch_id)+delta];if(key&&session)select(key);
  });
  video.addEventListener("play",()=>{if(session){phase="영상 재생";text("watch-phase",phase);}});
  video.addEventListener("pause",()=>{if(session&&!video.ended&&video.paused){phase="일시정지";text("watch-phase",phase);}});
  video.addEventListener("waiting",()=>{if(session&&!video.paused)text("watch-phase","영상 불러오는 중 · 같은 투구 유지");});
  video.addEventListener("playing",()=>{if(session)text("watch-phase","영상 재생");});
  for(const event of ["timeupdate","loadedmetadata","emptied"]) video.addEventListener(event,tick);
  document.addEventListener("visibilitychange",()=>{if(document.hidden){stop();clip.pause();}});
  window.addEventListener("pagehide",()=>{stop();clip.pause();});
  window.addEventListener("popstate",()=>{if(session)try{select(route(),"replace");}catch(error){fail(error);}});
  (async()=>{
    try {
      const first=route(),game=await asset("game-849843.json?v=1");
      session=PitchReceiverFullGame.createVerifiedSession(game.packet,game.hash);session.select(first);
      const extra=await Promise.allSettled([asset("game-849843-media.json?v=1"),asset("game-849843-zones.json?v=1")]);
      if(extra[0].status==="fulfilled") try {
        const received=PitchReceiverGameMedia.createVerifiedMedia(extra[0].value.packet,game.packet,extra[0].value.hash,window.PitchReceiverMedia||{});
        media=received.media;excluded=received.excluded;
      } catch (_) { /* No unverified media fallback. */ }
      if(extra[1].status==="fulfilled") try {zones=PitchReceiverZones.createVerifiedZones(extra[1].value.packet,game.packet,extra[1].value.hash);}catch(_){zoneNote="기록 존 확인 실패 · 좌표 격자만 표시";}
      else zoneNote="기록 존 미연결 · 좌표 격자만 표시";
      keys=session.groups().flatMap(g=>g.keys);
      for(const group of session.groups()) append(el("watch-pa"),"option",`${group.inning}회 ${group.half==="Top"?"초":"말"} · PA${group.pa} · ${group.batter}`).value=group.pa;
      phase="추천 확인";render();remember("replace");
      text("watch-load-status",`저장 경기 262구 · 추천246/미지원16 · 영상${Object.keys(media).length}구 · 기록 자료 재생`);
    } catch(error){fail(error);}
  })();
})();

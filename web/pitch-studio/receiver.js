"use strict";
const node = (id) => document.getElementById(id);
let session = null,
  loadVersion = 0,
  preparedEnvelope = null,
  rawFiles = [],
  builtInDemo = false;
let gameMedia = null, excludedMedia = {}, mediaLoadNote = "";
let gameZones = null, zoneLoadNote = "", currentMode = "file";
const fullGame = () => session?.view().full_game === true;
const locationPerspective = () => node("location-perspective").value || "pitcher";
function observationFor(view) {
  return view.full_game
    ? PitchReceiverFullGame.observation(view)
    : PitchReceiver.observation(view, window.DEMO_DATA.pitches);
}
const pitchVideo = PitchReceiverVideo.create({
  video: node("pitch-video"), section: node("pitch-video-section"),
  frame: node("pitch-video-frame"), missing: node("pitch-video-missing"),
  status: node("pitch-video-status"), play: node("play-pitch-video"),
  fallback: node("pitch-video-fallback"),
  inspect: node("inspect-pitch-mitt"), observationImage: node("pitch-observation-image"),
  marker: node("pitch-observation-marker"), observationNote: node("pitch-observation-note"),
  sourceLink: node("pitch-video-source"),
}, (binding) => {
  if (!session || !builtInDemo || binding !== `${loadVersion}:${session.view().pitch_id}`) return;
  session.reveal(true);
  render();
}, window.PitchReceiverMedia, {
  onEnded: (binding) => paSequence.ended(binding),
  onInterrupt: (reason) => {
    if (paSequence.isActive()) paSequence.stop(reason);
    if (session && ["seek", "manual", "error"].includes(reason)) {
      session.reveal(false); render(true);
    }
  },
});
function sequenceState() {
  const view = session?.view();
  const group = view?.full_game ? session.groups().find(g => g.pa === view.at_bat_number) : null;
  const index = group?.keys.indexOf(view.pitch_id) ?? -1;
  return {enabled: Boolean(builtInDemo && group), binding: `${loadVersion}:${view?.pitch_id}`,
    pa: view?.at_bat_number, pitchId: view?.pitch_id, revealed: view?.revealed,
    nextId: group?.keys[index + 1] || null, hasVideo: Boolean(gameMedia?.[view?.pitch_id])};
}
function renderSequenceControls() {
  const state = sequenceState();
  node("pa-sequence-controls").hidden = !state.enabled;
  node("start-pa-sequence").disabled = paSequence.isActive() || !state.hasVideo;
  node("stop-pa-sequence").disabled = !paSequence.isActive();
}
const paSequence = PitchReceiverSequence.create({
  getState: sequenceState,
  startClip: () => { session.reveal(false); render(); return pitchVideo.restart(); },
  advance: (key) => { session.select(key); render(); rememberRoute(); },
  onChange: ({phase, reason}) => {
    renderSequenceControls();
    const messages = {
      complete: "이 타석의 마지막 공까지 봤습니다. 다음 타석은 직접 선택해 주세요.",
      missing: "확인된 영상이 없어 이어보기를 멈췄습니다. 현재 공의 결과는 직접 공개할 수 있습니다.",
      blocked: "자동 재생을 시작하지 못해 멈췄습니다. 재생 버튼으로 다시 확인해 주세요.",
      error: "영상 오류로 이어보기를 멈췄습니다. 결과를 직접 공개하거나 다시 시작할 수 있습니다.",
      pause: "영상 일시정지로 이어보기를 멈췄습니다.",
      seek: "영상 탐색으로 이어보기를 멈췄습니다.",
      hidden: "페이지를 벗어나 이어보기를 멈췄습니다.",
    };
    node("pa-sequence-status").textContent = phase === "waiting"
      ? "결과 확인 중 · 5초 뒤 같은 타석의 다음 공을 재생합니다."
      : phase === "playing" ? "한 타석 이어보기 중 · 현재 공의 추천을 확인하세요."
      : messages[reason] || "이어보기 정지 · 현재 공부터 다시 시작할 수 있습니다.";
  },
});
const MAX_BYTES = 5 * 1024 * 1024;
const put = (id, text) => {
  node(id).textContent = text;
};
function clear() {
  paSequence.stop();
  loadVersion++;
  session = null;
  builtInDemo = false;
  gameMedia = null;
  gameZones = null;
  zoneLoadNote = "";
  currentMode = "file";
  put("replay-status", "");
  excludedMedia = {};
  mediaLoadNote = "";
  pitchVideo.update(null);
  for (const id of ["receiver-watch-current", "receiver-watch-featured"]) node(id).hidden = true;
  node("pitch-tabs").hidden = true;
  node("game-navigation").hidden = true;
  node("pa-select").replaceChildren();
  node("inning-select").replaceChildren();
  put("game-coverage", "");
  node("receiver-stage").classList.remove("has-video");
  preparedEnvelope = null;
  node("download-prepared").disabled = true;
  node("response-workspace").hidden = true;
  node("source-details").hidden = true;
  node("source-details").replaceChildren();
  renderSequenceControls();
  node("received-post").replaceChildren();
  node("received-candidates").replaceChildren();
  renderLocations(null);
  for (const id of [
    "game-name",
    "pitch-identity",
    "players",
    "source-badge",
    "publication-state",
    "recommendation-status",
    "import-error",
  ])
    put(id, "");
  node("current-situation").replaceChildren();
  node("import-error").hidden = true;
  node("response-file").value = "";
  put(
    "import-status",
    "파일 대기 · 전달받은 응답을 선택하면 이 화면에 표시합니다.",
  );
}
function resetRaw() {
  node("raw-form").reset();
  rawFiles = [];
  node("raw-endpoints").replaceChildren();
}
function textElement(tag, text, parent) {
  const e = document.createElement(tag);
  e.textContent = text;
  parent.append(e);
  return e;
}
function renderLocations(view) {
  const zone = view?.full_game ? gameZones?.[view.pitch_id] ?? null : null;
  const direction = locationPerspective(), info = PitchReceiverLocation.perspectiveInfo(direction);
  const model = PitchReceiverLocation.build(view, zone, direction);
  const wrapper = node("location-comparison"), svg = node("location-plot"), values = node("location-values");
  wrapper.hidden = !model;
  svg.replaceChildren();
  values.replaceChildren();
  put("location-state", "");
  put("zone-status", "");
  if (!model) { svg.setAttribute("aria-label", "투구 자료 없음"); return; }
  put("location-perspective-note", info.description);
  const ticks = PitchReceiverLocation.horizontalTicks(direction);
  const shape = (tag, attrs, text = "") => {
    const element = document.createElementNS("http://www.w3.org/2000/svg", tag);
    for (const [key, value] of Object.entries(attrs)) element.setAttribute(key, String(value));
    element.textContent = text;
    svg.append(element);
    return element;
  };
  shape("rect", {x: 60, y: 18, width: 200, height: 250, class: "location-field"});
  for (let i = 0; i <= 4; i++) {
    const x = 60 + i * 50;
    shape("line", {x1:x, y1:18, x2:x, y2:268, class: i === 2 ? "location-zero" : "location-grid"});
    shape("text", {x, y:306, class:"location-tick", "text-anchor":"middle"}, String(ticks[i]));
  }
  for (let i = 0; i <= 5; i++) {
    const y = 268 - i * 50;
    shape("line", {x1:60, y1:y, x2:260, y2:y, class:"location-grid"});
    shape("text", {x:24, y:y+4, class:"location-tick", "text-anchor":"end"}, String(i));
  }
  shape("text", {x:278,y:306,class:"location-tick"}, "x / ft");
  shape("text", {x:8,y:12,class:"location-tick"}, "z / ft");
  const outline = model.zone || PitchReceiverLocation.referenceZone();
  if (outline) {
    const x = 60 + outline.nx * 200, y = 18 + outline.ny * 250;
    const w = outline.nw * 200, h = outline.nh * 250;
    shape("rect", {x,y,width:w,height:h,class:model.zone ? "strike-zone" : "reference-zone"});
    for (let i=1;i<3;i++) {
      shape("line", {x1:x+w*i/3,y1:y,x2:x+w*i/3,y2:y+h,class:model.zone ? "strike-zone-division" : "reference-zone-division"});
      shape("line", {x1:x,y1:y+h*i/3,x2:x+w,y2:y+h*i/3,class:model.zone ? "strike-zone-division" : "reference-zone-division"});
    }
  }
  if (model.zone) {
    put("zone-status", `${view.batter.name}의 기록 존 · 하단 ${model.zone.bottom.toFixed(2)} / 상단 ${model.zone.top.toFixed(2)} ft`);
  } else put("zone-status", `점선은 참고 존 · 높이 1.5–3.5ft 예시 · 타자 기록 아님. ${zone && !view.revealed ? "결과 공개 뒤 기록 존으로 바뀝니다." : zoneLoadNote || "타자 기록 존 미연결."}`);
  // No jitter or clamping: shared recommendation coordinates retain all ranks.
  for (const group of model.groups) {
    const x = 60 + group.nx * 200, y = 18 + group.ny * 250;
    const marker = PitchReceiverLocation.marker(group);
    shape("circle", {cx:x,cy:y,r:marker.width/2,class:"location-recommended"});
    shape("text", {x,y:y+4,"text-anchor":"middle",class:"location-rank"}, marker.text);
  }
  if (model.actual?.status === "plottable") {
    const x = 60 + model.actual.nx * 200, y = 18 + model.actual.ny * 250;
    shape("circle", {cx:x,cy:y,r:17,class:"location-actual-halo"});
    shape("circle", {cx:x,cy:y,r:7,class:"location-actual"});
  }
  const description = (point) => {
    if (point.status === "missing") return "좌표 미제공 · 점 없음";
    return `x ${point.x.toFixed(2)} / z ${point.z.toFixed(2)} ft${point.status === "outside" ? " · 도표 범위 밖, 점 없음" : ""}`;
  };
  for (const point of model.recommendations) textElement("li", `${point.rank} · ${point.label}: ${description(point)}`, values);
  if (!model.recommendations.length) textElement("li", "표시할 추천 위치가 없습니다.", values);
  if (model.actual) textElement("li", `실제 · ${model.actual.label}: ${description(model.actual)}`, values).className = "location-actual-value";
  put("location-state", model.revealed ? "실제 홈플레이트 통과 위치 · 포구 지점 아님" : "결과 공개 전 · 실제 공 위치 숨김");
  const spokenRows = Array.from(values.children, (row) => row.textContent).join("; ");
  svg.setAttribute("aria-label", `${model.pitch_id} · ${info.label} 위치 비교. ${spokenRows}. ${node("location-state").textContent}`);
}
function render(preservePosition = false) {
  if (!session) return;
  const view = session.view(),
    s = view.situation;
  const currentObservation = observationFor(view);
  pitchVideo.update({ context: loadVersion, pitch_id: view.pitch_id, revealed: view.revealed, enabled: builtInDemo,
    media: view.full_game ? gameMedia : null,
    observationAllowed: !view.full_game && currentObservation?.status === "key_matched", preservePosition });
  for (const id of ["receiver-watch-current", "receiver-watch-featured"]) {
    node(id).hidden = !view.full_game;
    node(id).href = view.full_game ? `watch.html?game=849843&pitch=${encodeURIComponent(view.pitch_id)}` : "watch.html?game=849843";
  }
  put("pitch-video-missing-reason", view.full_game && excludedMedia[view.pitch_id]
    ? "영상 등록부와 받은 경기 자료의 구종이 달라 영상 연결을 보류했습니다. 어느 기록도 임의로 수정하지 않았습니다."
    : "이 투구의 확인된 영상을 불러오지 못했습니다.");
  node("pitch-tabs").hidden = !builtInDemo;
  node("receiver-stage").classList.toggle("has-video", builtInDemo);
  renderNavigation(view);
  renderSequenceControls();
  node("video-next-pitch").hidden = !builtInDemo || !view.can_next;
  put("video-next-pitch", "다음 투구 보기");
  node("response-workspace").hidden = false;
  put(
    "source-badge",
    currentMode === "archive" ? "옛 첫 타석 수신본 · 별도 3구 보관 자료" : view.source.kind === "synthetic"
      ? "합성 연결 테스트 · 실제 경기 아님"
      : "제공받은 모델 응답 · 검증 전 실험 추천",
  );
  put(
    "publication-state",
    view.revealed ? "현재 투구 결과 공개됨" : "현재 투구 결과 숨김",
  );
  put("game-name", `${view.game.away_team} @ ${view.game.home_team}`);
  put(
    "pitch-identity",
    `${builtInDemo ? "현지 2026-09-29 / 한국 09-30" : `${view.game.date} (파일 기준)`} · ${view.at_bat_number}번째 타석 · ${view.pitch_number}구 · 키 ${view.pitch_id}`,
  );
  const bases = [1, 2, 4].flatMap((bit, i) =>
    s.bases & bit ? [`${i + 1}루`] : [],
  );
  node("current-situation").replaceChildren();
  for (const value of [
    `${s.inning}회 ${s.half === "Top" ? "초" : "말"}`,
    `${s.outs} OUT`,
    `${s.balls}B · ${s.strikes}S`,
    bases.length ? bases.join("·") : "주자 없음",
    `원정 ${s.away_score} : ${s.home_score} 홈`,
  ])
    textElement("span", value, node("current-situation"));
  put(
    "players",
    `${view.pitcher.name} (${view.pitcher.hand ?? "유형 미제공"}) · ${view.batter.name} (${view.batter.hand ?? "유형 미제공"})`,
  );
  node("previous-pitch").disabled = !view.can_previous;
  node("next-pitch").disabled = !view.can_next;
  node("reveal-pitch").disabled = view.revealed;
  node("hide-pitch").disabled = !view.revealed;
  put(
    "recommendation-status",
    view.pre.status === "ready"
      ? "파일에 포함된 추천 후보"
      : "이 투구는 추천 미지원입니다.",
  );
  try {
    renderLocations(view);
  } catch (error) {
    reportError(error, loadVersion);
    return;
  }
  const candidates = node("received-candidates");
  candidates.replaceChildren();
  for (const c of view.pre.candidates) {
    const item = document.createElement("div");
    item.className = "received-candidate";
    candidates.append(item);
    textElement(
      "strong",
      `${c.rank}. ${c.pitch_label} · ${c.selection_probability == null ? "비중 미제공" : `${(c.selection_probability * 100).toFixed(1)}%`}`,
      item,
    );
    const bar = document.createElement("progress");
    bar.className = "selection-bar";
    bar.max = 1;
    bar.value = c.selection_probability;
    bar.hidden = c.selection_probability == null;
    bar.setAttribute("aria-label", `${c.pitch_label} 구종 선택 비율`);
    item.append(bar);
    textElement(
      "p",
      c.target
        ? `근사 목표 · 포수 시점 x ${c.target.x.toFixed(2)} ft / z ${c.target.z.toFixed(2)} ft`
        : "목표 위치 미지원",
      item,
    );
  }
  const post = node("received-post");
  post.replaceChildren();
  post.hidden = !view.revealed;
  node("post-placeholder").hidden = view.revealed;
  if (!view.revealed) return;
  const a = view.post?.actual ?? {},
    dl = document.createElement("dl");
  post.append(dl);
  const metric = (label, value) => {
    textElement("dt", label, dl);
    textElement("dd", value, dl);
  };
  metric("공개된 결과", a.result_label ?? a.event_label ?? "미제공");
  if (a.event_label) metric("타석 결과", a.event_label);
  metric(
    "실제 구종 / 구속",
    `${a.pitch_label ?? "미제공"} / ${a.speed_mph == null ? "미제공" : `${a.speed_mph.toFixed(1)} mph`}`,
  );
  metric("공의 플레이트 x", a.x == null ? "미제공" : `${a.x.toFixed(2)} ft`);
  metric("공의 플레이트 z (지면 기준 높이)", a.z == null ? "미제공" : `${a.z.toFixed(2)} ft`);
  const we = view.post?.we ?? {};
  const percent = (value) =>
    value == null ? "미제공" : `${(value * 100).toFixed(1)}%`;
  metric(
    "홈팀 승리 기대 (전 → 후)",
    `${percent(we.home_before)} → ${percent(we.home_after)}`,
  );
  metric(
    "홈팀 승리 기대 변화",
    we.home_delta == null
      ? "미제공"
      : `${we.home_delta > 0 ? "+" : ""}${(we.home_delta * 100).toFixed(1)}%p`,
  );
  textElement(
    "p",
    view.post?.we ? "투구 직전 → 다음 기록 직전 상태의 홈팀 승리 기대 근사입니다. 경기 마지막 기록은 최종 승패를 사용하며, 볼카운트는 반영하지 않습니다. 선수 책임이나 교체 효과를 뜻하지 않습니다." : "이 저장 응답에는 승리 기대와 사건확률이 제공되지 않았습니다.",
    post,
  ).className = "receiver-note";
  const observation = observationFor(view);
  const labels = {
    synthetic: "합성 자료에는 실제 관측을 연결하지 않습니다.",
    missing: "이 투구의 저장 관측이 없습니다.",
    conflict: "키·선수·구종 대조 불일치 · 좌표 표시 보류",
    unavailable: "기권 · 좌표 없음",
    estimated: "같은 저장 응답의 미검토 AI 가로 위치 추정 · 영상 대응 미검증",
    key_matched: builtInDemo && view.pitch_id === "849843:1:3"
      ? "미검토 AI 가로 위치 추정 · 키·선수·구종·발췌 영상 대응 확인"
      : "미검토 AI 가로 위치 추정 · 키·선수·구종 일치 · 영상 대응 미검증",
  };
  metric(
    view.full_game ? "받은 셋업 가로 추정 x" : "우리 저장 미트 x",
    observation.x === null ? "—" : `${observation.x.toFixed(4)} ft`,
  );
  if (observation.x !== null && observation.x >= -2 && observation.x <= 2) {
    const graphic = textElement("div", "", post);
    graphic.className = "mitt-horizontal";
    graphic.setAttribute("role", "img");
    graphic.setAttribute(
      "aria-label",
      `${PitchReceiverLocation.perspectiveInfo(locationPerspective()).label} · 원본 미트 x ${observation.x.toFixed(4)} ft. 높이와 투수 의도는 표시하지 않습니다.`,
    );
    const track = textElement("div", "", graphic);
    track.className = "mitt-track";
    const marker = textElement("span", "", track);
    marker.className = "mitt-dot";
    marker.style.left = `${PitchReceiverLocation.screenX(observation.x, locationPerspective()) * 100}%`;
    textElement(
      "div",
      locationPerspective() === "pitcher" ? "+2 ft　← 중계 방향 · 0 →　−2 ft" : "−2 ft　← 포수 시점 · 0 →　+2 ft",
      graphic,
    ).className = "mitt-axis";
  }
  const note = textElement(
    "p",
    labels[observation.status] +
      " 미트와 공의 측정 평면이 달라 차이를 제구 오차로 계산하지 않습니다.",
    post,
  );
  note.className = "observation-caution";
}
async function sha256(bytes) {
  return Array.from(
    new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
  )
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
}
async function openText(text, name, version, inputBytes, originals = []) {
  const envelope = JSON.parse(text);
  const candidateSession = PitchReceiver.createSession(envelope);
  const bytes = inputBytes ?? new TextEncoder().encode(text);
  const hash = await sha256(bytes);
  if (version !== loadVersion) return;
  session = candidateSession;
  preparedEnvelope = envelope;
  node("download-prepared").disabled = false;
  const view = session.view();
  put(
    "import-status",
    "파일 구조·연결 검사 통과 · 실제 모델·영상 대응 인증 아님",
  );
  const info = node("source-details");
  info.hidden = false;
  textElement("div", `파일: ${name}`, info);
  textElement(
    "div",
    `${originals.length ? "조립한 묶음" : "입력 파일"} SHA256: ${hash}`,
    info,
  );
  for (const original of originals) {
    textElement(
      "div",
      `원본 파일: ${original.name} · SHA256: ${original.hash}`,
      info,
    );
    if (original.endpoint)
      textElement("div", `원래 요청 경로: ${original.endpoint}`, info);
  }
  textElement("div", `제공자 기재 모델: ${view.source.model_id}`, info);
  textElement(
    "div",
    `제공자가 기재한 자료 생성 코드 커밋: ${view.source.revision} · 생성 시각: ${view.source.exported_at}`,
    info,
  );
  render();
}
function reportError(error, version) {
  if (version !== loadVersion) return;
  clear();
  put("import-status", "자료를 불러오지 않았습니다.");
  put("import-error", `검사 실패: ${error.message}`);
  node("import-error").hidden = false;
  node("file-tools").open = true;
  put("replay-status", `자료 확인 실패: ${error.message} 위의 ‘경기 전체 열기’로 다시 시작할 수 있습니다.`);
}

function rememberRoute(method = "push") {
  const key = builtInDemo ? session?.view().pitch_id : null;
  const query = PitchReceiverRoute.query(currentMode, key);
  if (window.location.search !== query)
    window.history[method === "replace" ? "replaceState" : "pushState"](null, "", `${window.location.pathname}${query}${window.location.hash}`);
}
function selectPitch(key) {
  paSequence.stop();
  session.select(key);
  syncPaFilter();
  render();
  rememberRoute();
}
function renderNavigation(view) {
  node("game-navigation").hidden = !view.full_game;
  const videoCount = Object.keys(gameMedia || window.PitchReceiverMedia).length;
  put("video-coverage", view.full_game ? `영상 연결 ${videoCount} / ${view.count}구` : "공식 영상 3 / 3구");
  if (view.full_game) {
    node("pa-select").value = String(view.at_bat_number);
    put("game-coverage", `전체 ${view.count}구 중 ${view.position}구 · 71타석 · 추천 246구 / 미지원 16구. ${mediaLoadNote || "투구별 영상 종료 후 실제 결과 공개 · 영상 미연결 투구도 결과 비교 가능"}`);
  }
  const tabs = node("pitch-tabs");
  tabs.setAttribute("aria-label", "현재 타석 투구 선택");
  tabs.replaceChildren();
  const pitches = view.full_game
    ? session.groups().find(g => g.pa === view.at_bat_number).pitches
    : [1, 2, 3].map(n => ({key:`849843:1:${n}`, pitch_number:n}));
  for (const pitch of pitches) {
    const button = textElement("button", `${pitch.pitch_number}구`, tabs);
    button.type = "button";
    button.dataset.pitch = pitch.pitch_number;
    button.dataset.key = pitch.key;
    if (pitch.key === view.pitch_id) button.setAttribute("aria-current", "step");
  }
}
function fillPaOptions(inning = "all") {
  const select = node("pa-select");
  select.replaceChildren();
  for (const group of session.groups()) {
    if (inning !== "all" && `${group.inning}-${group.half}` !== inning) continue;
    const option = textElement("option", `${group.inning}회 ${group.half === "Top" ? "초" : "말"} · ${group.pa}번째 타석 · ${group.batter}`, select);
    option.value = group.pa;
  }
}
function syncPaFilter() {
  if (!fullGame()) return;
  const view = session.view(), filter = node("inning-select");
  if (filter.value !== "all" && filter.value !== `${view.situation.inning}-${view.situation.half}`) {
    filter.value = "all";
    fillPaOptions();
  }
}
async function loadFullGame(startKey = PitchReceiverRoute.FIRST, historyMode = "push") {
  resetRaw();
  clear();
  const version = loadVersion;
  put("import-status", "경기 전체 자료를 불러오는 중입니다.");
  put("replay-status", "경기 자료·영상 목록·타자별 기록 존을 불러오는 중입니다.");
  try {
    const response = await fetch("game-849843.json?v=1", {credentials:"omit"});
    if (!response.ok) throw new Error("저장 경기 파일을 불러오지 못했습니다.");
    const bytes = await response.arrayBuffer();
    if (bytes.byteLength > MAX_BYTES) throw new Error("경기 파일 크기 초과");
    const packet = JSON.parse(new TextDecoder("utf-8", {fatal:true}).decode(bytes));
    const hash = await sha256(bytes);
    const candidate = PitchReceiverFullGame.createVerifiedSession(packet, hash);
    candidate.select(startKey);
    if (version !== loadVersion) return;
    let zones = null, zoneNote = "";
    try {
      const zoneResponse = await fetch("game-849843-zones.json?v=1", {credentials:"omit"});
      if (!zoneResponse.ok) throw new Error("기록 존 요청 실패");
      const zoneBytes = await zoneResponse.arrayBuffer();
      if (zoneBytes.byteLength > MAX_BYTES) throw new Error("기록 존 크기 초과");
      zones = PitchReceiverZones.createVerifiedZones(JSON.parse(new TextDecoder("utf-8", {fatal:true}).decode(zoneBytes)), packet, await sha256(zoneBytes));
    } catch (_) { zoneNote = "기록 존 자료 확인 실패 · 1ft 좌표 격자만 표시"; }
    if (version !== loadVersion) return;
    gameZones = zones;
    zoneLoadNote = zoneNote;
    let verifiedMedia = null, mediaHash = null, loadNote = "";
    try {
      const mediaResponse = await fetch("game-849843-media.json?v=1", {credentials:"omit"});
      if (!mediaResponse.ok) throw new Error("영상 목록 요청 실패");
      const mediaBytes = await mediaResponse.arrayBuffer();
      if (mediaBytes.byteLength > MAX_BYTES) throw new Error("영상 목록 크기 초과");
      const mediaPacket = JSON.parse(new TextDecoder("utf-8", {fatal:true}).decode(mediaBytes));
      mediaHash = await sha256(mediaBytes);
      verifiedMedia = PitchReceiverGameMedia.createVerifiedMedia(mediaPacket, packet, mediaHash, window.PitchReceiverMedia);
    } catch (_) {
      loadNote = "전체 영상 목록 검사 실패 · 기존 첫3구 영상만 표시합니다. 추천·결과는 계속 비교할 수 있습니다.";
    }
    if (version !== loadVersion) return;
    gameMedia = verifiedMedia?.media || null;
    excludedMedia = verifiedMedia?.excluded || {};
    mediaLoadNote = loadNote;
    session = candidate;
    currentMode = "game";
    builtInDemo = true;
    const filter = node("inning-select");
    textElement("option", "전체 이닝", filter).value = "all";
    const seen = new Set();
    for (const group of session.groups()) {
      const key = `${group.inning}-${group.half}`;
      if (seen.has(key)) continue;
      seen.add(key);
      textElement("option", `${group.inning}회 ${group.half === "Top" ? "초" : "말"}`, filter).value = key;
    }
    fillPaOptions();
    const info = node("source-details");
    info.hidden = false;
    textElement("div", `공개용 선별 파일 SHA256: ${hash}`, info);
    textElement("div", `수신 원응답 SHA256: ${session.view().source.sha256}`, info);
    textElement("div", "경기 후 저장 응답의 재생입니다. 실행 서버 커밋·실시간 사전 가용성은 미확인입니다.", info);
    if (verifiedMedia) textElement("div", `영상 연결 목록 SHA256: ${mediaHash} · 투구ID/선수/구종 대조 ${Object.keys(gameMedia).length}구, 불일치 제외 ${Object.keys(excludedMedia).length}구.`, info);
    textElement("div", "첫3구는 저장 영상, 나머지는 MLB 공식 영상 서버에서 선택한 클립만 읽습니다. 로컬 원본 SHA는 원격 서버의 현재 영상 바이트까지 보증하지 않습니다.", info);
    put("import-status", "849843 저장 경기 · 구조·투구 키 검사 통과");
    put("replay-status", zoneNote || "기록 존 262구 연결 · 타석과 투구를 바꾸어도 같은 위치의 링크를 공유할 수 있습니다.");
    render();
    rememberRoute(historyMode);
    node("file-tools").open = false;
    node("response-workspace").focus();
  } catch (error) { reportError(error, version); }
}
async function loadFirstPa(startPitch = 1, historyMode = "push") {
  resetRaw();
  clear();
  const version = loadVersion;
  try {
    const demo = window.PitchReceiverDemo849843;
    await openText(
      JSON.stringify(demo.packet),
      "849843 첫 타석 · 제공받은 원응답에서 선별",
      version,
      undefined,
      demo.originals,
    );
    if (version !== loadVersion) return;
    builtInDemo = true;
    currentMode = "archive";
    if (Number.isInteger(startPitch) && startPitch >= 1 && startPitch <= 3) {
      for (let i = 1; i < startPitch; i++) { session.reveal(true); session.next(); }
      session.reveal(false);
    }
    render();
    rememberRoute(historyMode);
    put("replay-status", "옛 별도 수신본 3구입니다. ‘경기 전체 열기’를 누르면 71타석·262구 관전으로 이동합니다.");
    node("file-tools").open = false;
    node("response-workspace").focus();
  } catch (error) {
    reportError(error, version);
  }
}
node("load-first-pa").addEventListener("click", () => loadFullGame());
node("load-full-game").addEventListener("click", () => loadFullGame());
node("pitch-tabs").addEventListener("click", (event) => {
  const button = event.target.closest("button[data-key]");
  if (!button) return;
  if (fullGame()) selectPitch(button.dataset.key);
  else loadFirstPa(Number(button.dataset.pitch));
});
node("pa-select").addEventListener("change", () => {
  if (!fullGame()) return;
  const group = session.groups().find(g => g.pa === Number(node("pa-select").value));
  if (group) selectPitch(group.keys[0]);
});
node("inning-select").addEventListener("change", () => {
  if (!fullGame()) return;
  fillPaOptions(node("inning-select").value);
  const group = session.groups().find(g => g.pa === Number(node("pa-select").value));
  if (group) selectPitch(group.keys[0]);
});
node("video-next-pitch").addEventListener("click", () => {
  paSequence.stop();
  if (builtInDemo && session?.view().can_next) { session.next(); syncPaFilter(); render(); rememberRoute(); }
});
for (const link of document.querySelectorAll(".video-jump")) {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    loadFullGame("849843:1:3");
  });
}
node("response-file").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  resetRaw();
  clear();
  const version = loadVersion;
  try {
    if (file.size > MAX_BYTES)
      throw new Error("파일 크기는 5MB 이하여야 합니다.");
    const bytes = await file.arrayBuffer();
    const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    await openText(text, file.name, version, bytes);
    if (version === loadVersion && session) rememberRoute();
  } catch (error) {
    reportError(error, version);
  }
});
node("try-sample").addEventListener("click", async () => {
  resetRaw();
  clear();
  const version = loadVersion;
  try {
    await openText(
      JSON.stringify(window.PitchReceiverSample),
      "합성 연결 검사 자료",
      version,
    );
    if (version === loadVersion && session) rememberRoute();
  } catch (error) {
    reportError(error, version);
  }
});
function downloadJson(value, name) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value)], {
      type: "application/json",
    }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = name;
  document.body.append(a);
  a.click();
  a.remove();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
}
node("download-template").addEventListener("click", () =>
  downloadJson(
    window.PitchReceiverSample,
    "pitcheezy-receiver-synthetic-template.json",
  ),
);
node("download-prepared").addEventListener("click", () => {
  if (preparedEnvelope)
    downloadJson(
      preparedEnvelope,
      `pitcheezy-${preparedEnvelope.game_pk}-pa${preparedEnvelope.at_bat_number}-${preparedEnvelope.source.kind}.json`,
    );
});
node("clear-import").addEventListener("click", () => {
  resetRaw();
  clear();
  rememberRoute();
});
node("raw-form").addEventListener("input", clear);
node("raw-form").addEventListener("change", clear);
node("reveal-files").addEventListener("change", (event) => {
  rawFiles = [];
  const parent = node("raw-endpoints");
  parent.replaceChildren();
  const files = Array.from(event.target.files);
  if (files.length > 100) {
    // The form change handler clears status, so keep this instruction beside the input.
    textElement("p", "한 타석의 파일만 선택하세요. 최대 100개입니다.", parent);
    return;
  }
  for (const file of files) {
    const label = textElement("label", `${file.name} · 원래 요청 주소`, parent);
    label.className = "raw-endpoint";
    const endpoint = document.createElement("input");
    endpoint.type = "text";
    endpoint.required = true;
    endpoint.maxLength = 2000;
    endpoint.placeholder = "제공받은 /api/watch/경기번호/reveal/index 경로";
    endpoint.autocomplete = "off";
    label.append(endpoint);
    rawFiles.push({ file, endpoint });
  }
});
node("raw-form").addEventListener("submit", async (event) => {
  event.preventDefault();
  clear();
  const version = loadVersion;
  try {
    const timelineFile = node("timeline-file").files[0];
    if (!timelineFile || !rawFiles.length)
      throw new Error("경기 파일과 한 타석의 결과 파일을 선택하세요.");
    const files = [
      { file: timelineFile },
      ...rawFiles.map(({ file, endpoint }) => ({
        file,
        endpoint: endpoint.value.trim(),
      })),
    ];
    if (files.reduce((sum, { file }) => sum + file.size, 0) > MAX_BYTES)
      throw new Error("원본 파일 전체 합계는 5MB 이하여야 합니다.");
    const source = {
      kind: node("raw-kind").value,
      revision: node("raw-revision").value.trim(),
      exported_at: node("raw-generated").value.trim(),
      model_id: node("raw-model").value.trim(),
    };
    const pa = Number(node("raw-pa").value);
    const parsed = await Promise.all(
      files.map(async ({ file, endpoint }) => {
        const bytes = await file.arrayBuffer();
        return {
          name: file.name,
          endpoint,
          hash: await sha256(bytes),
          response: JSON.parse(
            new TextDecoder("utf-8", { fatal: true }).decode(bytes),
          ),
        };
      }),
    );
    if (version !== loadVersion) return;
    const envelope = PitchReceiver.assemble({
      timeline: parsed[0].response,
      at_bat_number: pa,
      source,
      reveals: parsed.slice(1).map(({ endpoint, response }) => ({
        source_endpoint: endpoint,
        response,
      })),
    });
    const text = JSON.stringify(envelope);
    if (new TextEncoder().encode(text).length > MAX_BYTES)
      throw new Error(
        "조립한 묶음이 5MB를 넘습니다. 제공자에게 작은 공개용 응답을 요청하세요.",
      );
    const originals = parsed.map((p, i) => ({
      name: p.name,
      hash: p.hash,
      endpoint: i ? envelope.reveals[i - 1].source_endpoint : null,
    }));
    await openText(
      text,
      "원본 응답으로 조립한 한 타석",
      version,
      undefined,
      originals,
    );
    if (version === loadVersion && session) rememberRoute();
  } catch (error) {
    reportError(error, version);
  }
});
node("location-perspective").addEventListener("change", () => {
  if (session) render(true);
});
node("reveal-pitch").addEventListener("click", () => {
  paSequence.stop();
  session?.reveal(true);
  render();
});
node("hide-pitch").addEventListener("click", () => {
  paSequence.stop();
  session?.reveal(false);
  render();
});
node("next-pitch").addEventListener("click", () => {
  paSequence.stop();
  session?.next();
  syncPaFilter();
  render();
  if (session) rememberRoute();
});
node("previous-pitch").addEventListener("click", () => {
  paSequence.stop();
  session?.previous();
  syncPaFilter();
  render();
  if (session) rememberRoute();
});
async function restoreRoute() {
  paSequence.stop();
  try {
    const route = PitchReceiverRoute.parse(window.location.search);
    if (route.mode === "file") {
      clear();
      node("file-tools").open = true;
      put("replay-status", "파일은 주소에 저장되지 않습니다. 본인이 보관한 파일을 다시 선택해 주세요.");
    } else if (route.mode === "game" && fullGame()) {
      session.select(route.pitchId);
      syncPaFilter();
      render();
      rememberRoute("replace");
    } else if (route.mode === "game") await loadFullGame(route.pitchId, "replace");
    else await loadFirstPa(Number(route.pitchId.split(":")[2]), "replace");
  } catch (error) { reportError(error, loadVersion); }
}
window.addEventListener("popstate", restoreRoute);
node("start-pa-sequence").addEventListener("click", () => paSequence.start());
node("stop-pa-sequence").addEventListener("click", () => { paSequence.stop(); pitchVideo.pause(); });
document.addEventListener("visibilitychange", () => {
  if (document.hidden && paSequence.isActive()) { paSequence.stop("hidden"); pitchVideo.pause(); }
});
window.addEventListener("pagehide", () => { paSequence.stop("hidden"); pitchVideo.pause(); });
restoreRoute();

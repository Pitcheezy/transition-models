"use strict";
const node = (id) => document.getElementById(id);
let session = null,
  loadVersion = 0,
  preparedEnvelope = null,
  rawFiles = [],
  builtInDemo = false;
const pitchVideo = PitchReceiverVideo.create({
  video: node("pitch-video"), section: node("pitch-video-section"),
  frame: node("pitch-video-frame"), missing: node("pitch-video-missing"),
  status: node("pitch-video-status"), play: node("play-pitch-video"),
  fallback: node("pitch-video-fallback"),
}, (binding) => {
  if (!session || !builtInDemo || binding !== `${loadVersion}:${session.view().pitch_id}`) return;
  session.reveal(true);
  render();
});
const MAX_BYTES = 5 * 1024 * 1024;
const put = (id, text) => {
  node(id).textContent = text;
};
function clear() {
  loadVersion++;
  session = null;
  builtInDemo = false;
  pitchVideo.update(null);
  preparedEnvelope = null;
  node("download-prepared").disabled = true;
  node("response-workspace").hidden = true;
  node("source-details").hidden = true;
  node("source-details").replaceChildren();
  node("received-post").replaceChildren();
  node("received-candidates").replaceChildren();
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
function render() {
  if (!session) return;
  const view = session.view(),
    s = view.situation;
  pitchVideo.update({ context: loadVersion, pitch_id: view.pitch_id, revealed: view.revealed, enabled: builtInDemo });
  node("response-workspace").hidden = false;
  put(
    "source-badge",
    view.source.kind === "synthetic"
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
    `${view.game.date} · ${view.at_bat_number}번째 타석 · ${view.pitch_number}구 · 키 ${view.pitch_id}`,
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
  const candidates = node("received-candidates");
  candidates.replaceChildren();
  for (const c of view.pre.candidates) {
    const item = document.createElement("div");
    item.className = "received-candidate";
    candidates.append(item);
    textElement(
      "strong",
      `${c.rank}. ${c.pitch_label} · ${(c.selection_probability * 100).toFixed(1)}%`,
      item,
    );
    const bar = document.createElement("progress");
    bar.className = "selection-bar";
    bar.max = 1;
    bar.value = c.selection_probability;
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
  const a = view.post.actual,
    dl = document.createElement("dl");
  post.append(dl);
  const metric = (label, value) => {
    textElement("dt", label, dl);
    textElement("dd", value, dl);
  };
  metric("공개된 결과", a.result_label ?? a.event_label ?? "미제공");
  metric(
    "실제 구종 / 구속",
    `${a.pitch_label ?? "미제공"} / ${a.speed_mph === null ? "미제공" : `${a.speed_mph.toFixed(1)} mph`}`,
  );
  metric("공의 플레이트 x", a.x === null ? "미제공" : `${a.x.toFixed(2)} ft`);
  const we = view.post.we;
  const percent = (value) =>
    value === null ? "미제공" : `${(value * 100).toFixed(1)}%`;
  metric(
    "홈팀 승리 기대 (전 → 후)",
    `${percent(we.home_before)} → ${percent(we.home_after)}`,
  );
  metric(
    "홈팀 승리 기대 변화",
    we.home_delta === null
      ? "미제공"
      : `${we.home_delta > 0 ? "+" : ""}${(we.home_delta * 100).toFixed(1)}%p`,
  );
  textElement(
    "p",
    "투구 직전 → 다음 기록 직전 상태의 홈팀 승리 기대 근사입니다. 경기 마지막 기록은 최종 승패를 사용하며, 볼카운트는 반영하지 않습니다. 선수 책임이나 교체 효과를 뜻하지 않습니다.",
    post,
  ).className = "receiver-note";
  const observation = PitchReceiver.observation(view, window.DEMO_DATA.pitches);
  const labels = {
    synthetic: "합성 자료에는 실제 관측을 연결하지 않습니다.",
    missing: "이 투구의 저장 관측이 없습니다.",
    conflict: "키·선수·구종 대조 불일치 · 좌표 표시 보류",
    unavailable: "기권 · 좌표 없음",
    key_matched: builtInDemo && view.pitch_id === "849843:1:3"
      ? "미검토 AI 가로 위치 추정 · 키·선수·구종·발췌 영상 대응 확인"
      : "미검토 AI 가로 위치 추정 · 키·선수·구종 일치 · 영상 대응 미검증",
  };
  metric(
    "우리 저장 미트 x",
    observation.x === null ? "—" : `${observation.x.toFixed(4)} ft`,
  );
  if (observation.x !== null) {
    const graphic = textElement("div", "", post);
    graphic.className = "mitt-horizontal";
    graphic.setAttribute("role", "img");
    graphic.setAttribute(
      "aria-label",
      `포수 시점 미트 가로 위치 ${observation.x.toFixed(4)} ft. 높이와 투수 의도는 표시하지 않습니다.`,
    );
    const track = textElement("div", "", graphic);
    track.className = "mitt-track";
    const marker = textElement("span", "", track);
    marker.className = "mitt-dot";
    marker.style.left = `${Math.max(0, Math.min(100, (observation.x + 2) * 25))}%`;
    textElement(
      "div",
      "−2 ft　← 포수 시점 · 0 · 가로 위치 →　+2 ft",
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
}
async function loadFirstPa(startPitch = 1) {
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
    if (startPitch === 3) {
      session.reveal(true); session.next();
      session.reveal(true); session.next();
      session.reveal(false);
    }
    render();
    node("file-tools").open = false;
    node("response-workspace").focus();
  } catch (error) {
    reportError(error, version);
  }
}
node("load-first-pa").addEventListener("click", () => loadFirstPa());
for (const link of document.querySelectorAll(".video-jump")) {
  link.addEventListener("click", (event) => {
    event.preventDefault();
    loadFirstPa(3);
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
  } catch (error) {
    reportError(error, version);
  }
});
node("reveal-pitch").addEventListener("click", () => {
  session?.reveal(true);
  render();
});
node("hide-pitch").addEventListener("click", () => {
  session?.reveal(false);
  render();
});
node("next-pitch").addEventListener("click", () => {
  session?.next();
  render();
});
node("previous-pitch").addEventListener("click", () => {
  session?.previous();
  render();
});
if (new URLSearchParams(window.location.search).get("demo") === "849843-pa1")
  loadFirstPa(new URLSearchParams(window.location.search).get("pitch") === "3" ? 3 : 1);

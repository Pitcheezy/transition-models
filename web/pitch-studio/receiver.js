"use strict";
const node = (id) => document.getElementById(id);
let session = null,
  loadVersion = 0;
const put = (id, text) => {
  node(id).textContent = text;
};
function clear() {
  loadVersion++;
  session = null;
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
  put("import-status", "실제 응답 미수신 · JSON 전달 양식을 준비했습니다.");
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
  node("response-workspace").hidden = false;
  put(
    "source-badge",
    view.source.kind === "synthetic"
      ? "합성 연결 테스트 · 실제 경기 아님"
      : "가져온 응답 · 출처 미인증",
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
  const observation = PitchReceiver.observation(view, window.DEMO_DATA.pitches);
  const labels = {
    synthetic: "합성 자료에는 실제 관측을 연결하지 않습니다.",
    missing: "이 투구의 저장 관측이 없습니다.",
    conflict: "키·선수·구종 대조 불일치 · 좌표 표시 보류",
    unavailable: "기권 · 좌표 없음",
    key_matched: "키·선수·구종 일치 · 영상 대응 미검증",
  };
  metric(
    "우리 저장 미트 x",
    observation.x === null ? "—" : `${observation.x.toFixed(2)} ft`,
  );
  const note = textElement(
    "p",
    labels[observation.status] +
      " 미트와 공의 측정 평면이 달라 차이를 제구 오차로 계산하지 않습니다.",
    post,
  );
  note.className = "observation-caution";
}
async function openText(text, name, version, inputBytes) {
  const candidateSession = PitchReceiver.createSession(JSON.parse(text));
  const bytes = inputBytes ?? new TextEncoder().encode(text);
  const hash = Array.from(
    new Uint8Array(await crypto.subtle.digest("SHA-256", bytes)),
  )
    .map((b) => b.toString(16).padStart(2, "0"))
    .join("");
  if (version !== loadVersion) return;
  session = candidateSession;
  const view = session.view();
  put(
    "import-status",
    "파일 구조·연결 검사 통과 · 실제 모델·영상 대응 인증 아님",
  );
  const info = node("source-details");
  info.hidden = false;
  textElement("div", `파일: ${name}`, info);
  textElement("div", `입력 파일 SHA256: ${hash}`, info);
  textElement("div", `제공자 기재 모델: ${view.source.model_id}`, info);
  textElement(
    "div",
    `기재 커밋: ${view.source.revision} · 생성 시각: ${view.source.exported_at}`,
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
}
node("response-file").addEventListener("change", async (event) => {
  const file = event.target.files[0];
  if (!file) return;
  clear();
  const version = loadVersion;
  try {
    if (file.size > 5 * 1024 * 1024)
      throw new Error("파일 크기는 5MB 이하여야 합니다.");
    const bytes = await file.arrayBuffer();
    const text = new TextDecoder("utf-8", { fatal: true }).decode(bytes);
    await openText(text, file.name, version, bytes);
  } catch (error) {
    reportError(error, version);
  }
});
node("try-sample").addEventListener("click", async () => {
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
node("download-template").addEventListener("click", () => {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(window.PitchReceiverSample, null, 2)], {
      type: "application/json",
    }),
  );
  const a = document.createElement("a");
  a.href = url;
  a.download = "pitcheezy-receiver-synthetic-template.json";
  a.click();
  setTimeout(() => URL.revokeObjectURL(url), 1000);
});
node("clear-import").addEventListener("click", clear);
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

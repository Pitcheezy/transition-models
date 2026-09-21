"use strict";

const form = document.querySelector("#state-form");
const notice = document.querySelector("#notice");
const prediction = document.querySelector("#prediction");
const names = {
  FF: "포심", SI: "싱커", FC: "커터", SL: "슬라이더", ST: "스위퍼",
  CU: "커브", KC: "너클커브", CH: "체인지업", FS: "스플리터",
};
const labels = {
  Ball: "볼 계열 · 볼넷 제외",
  Strike: "스트라이크 계열 · 파울 포함",
  Single: "단타", Double: "2루타", Triple: "3루타", HomeRun: "홈런",
  FieldOut: "범타 계열 · 일부 실책 등 포함",
  Strikeout: "삼진", Walk: "볼넷 계열", HitByPitch: "몸에 맞는 공",
};
const numeric = new Set([
  "pitcher", "batter", "balls", "strikes", "outs_when_up", "inning",
  "on_1b", "on_2b", "on_3b", "home_score", "away_score",
]);
let result = null;
let revision = 0;

function pct(value) {
  return value > 0 && value < 0.0001 ? "<0.01%" : `${(value * 100).toFixed(2)}%`;
}

function status(message, error = false) {
  notice.textContent = message;
  notice.classList.toggle("error", error);
}

function invalidate() {
  revision++;
  result = null;
  prediction.hidden = true;
  document.querySelector("#latency").textContent = "다시 계산 필요";
  status("입력이 변경됐습니다. 새 상황으로 다시 계산하세요.");
}

async function request(url, options) {
  const response = await fetch(url, options);
  const body = await response.json();
  if (!response.ok) throw new Error(body.error || "요청 실패");
  return body;
}

async function loadExample() {
  const data = await request("/api/example");
  for (const field of form.elements) {
    if (field.name) field.value = data.state[field.name] ?? "";
  }
  const video = document.querySelector("#video");
  if (data.video_url) {
    video.src = data.video_url;
    video.hidden = false;
    document.querySelector("#video-empty").hidden = true;
  }
  invalidate();
  status("기록에서 가져온 예시입니다. 영상 자동 인식 결과가 아닙니다.");
}

function showCandidate() {
  if (!result) return;
  const selected = document.querySelector("#candidate").value;
  const choice = result.candidates.find(candidate => candidate.action === selected);
  document.querySelector("#hit").textContent = pct(choice.display_probabilities.hit);
  const list = document.querySelector("#probabilities");
  list.replaceChildren();
  for (const [name, value] of Object.entries(choice.legacy_probabilities)) {
    const row = document.createElement("div");
    row.className = "prob-row";
    const label = document.createElement("div");
    label.className = "prob-label";
    const title = document.createElement("span");
    const amount = document.createElement("span");
    title.textContent = labels[name] || name;
    amount.textContent = pct(value);
    label.append(title, amount);
    const bar = document.createElement("div");
    const fill = document.createElement("i");
    bar.className = "bar";
    fill.style.width = `${value * 100}%`;
    bar.append(fill);
    row.append(label, bar);
    list.append(row);
  }
}

function renderCandidates() {
  const select = document.querySelector("#candidate");
  const rows = document.querySelector("#candidates");
  select.replaceChildren();
  rows.replaceChildren();
  for (const candidate of result.candidates) {
    const option = document.createElement("option");
    option.value = candidate.action;
    option.textContent = `${names[candidate.action]} (${candidate.action})` +
      (candidate.supported ? "" : " · 추천 대상 제외");
    select.append(option);
    const row = document.createElement("tr");
    const values = [
      names[candidate.action],
      candidate.supported ? "지원" : "제외",
      candidate.expected_cost === null ? "미지원" : candidate.expected_cost.toFixed(4),
      pct(candidate.display_probabilities.hit),
    ];
    for (const value of values) {
      const cell = document.createElement("td");
      cell.textContent = value;
      row.append(cell);
    }
    rows.append(row);
  }
  select.value = result.recommendation ||
    result.candidates.find(candidate => candidate.supported)?.action ||
    result.candidates[0].action;
}

async function predict(event) {
  event.preventDefault();
  const requestRevision = ++revision;
  const payload = {};
  for (const [name, value] of new FormData(form)) {
    payload[name] = value === "" ? null : (numeric.has(name) ? Number(value) : value);
  }
  const button = document.querySelector("#predict");
  button.disabled = true;
  prediction.hidden = true;
  status("과거 프로필로 각 구종의 확률을 계산하고 있습니다.");
  try {
    const response = await request("/api/predict", {
      method: "POST",
      headers: {"Content-Type": "application/json"},
      body: JSON.stringify(payload),
    });
    // Discard a response if the user edited the state while inference was running.
    if (revision !== requestRevision) return;
    result = response;
    document.querySelector("#recommended").textContent = result.recommendation
      ? `${names[result.recommendation]} · ${result.recommendation}` : "추천 보류";
    document.querySelector("#comparison").textContent = result.empirical_recommendation
      ? `경험적 기준선: ${names[result.empirical_recommendation]} · 실제 실점 개선 미입증`
      : "지원 범위 밖에서는 추천을 표시하지 않습니다.";
    document.querySelector("#latency").textContent = `서버 계산 ${result.elapsed_ms.toFixed(0)} ms`;
    renderCandidates();
    prediction.hidden = false;
    showCandidate();
    const reasonText = result.reason?.startsWith("Policy evaluation")
      ? "기존 정책 평가는 1~8회 범위입니다. 9회 이후에는 추천을 보류합니다."
      : "이 투수의 과거 자료에서 충분히 지원되는 구종이 부족합니다.";
    status(result.reason ? reasonText
      : "계산 완료. 현재 모델은 구종을 비교하며 목표 위치는 추천하지 않습니다.");
  } catch (error) {
    if (revision === requestRevision) {
      result = null;
      prediction.hidden = true;
      status(error.message, true);
    }
  } finally {
    button.disabled = false;
  }
}

form.addEventListener("input", invalidate);
form.addEventListener("submit", predict);
document.querySelector("#candidate").addEventListener("change", showCandidate);
document.querySelector("#example").addEventListener("click", () => {
  loadExample().catch(error => status(error.message, true));
});

(async () => {
  try {
    await request("/api/health");
    document.querySelector("#health").textContent = "● 모델 준비 완료";
    await loadExample();
  } catch (error) {
    document.querySelector("#health").textContent = "연결 실패";
    status(error.message, true);
  }
})();

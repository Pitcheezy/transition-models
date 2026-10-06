"use strict";
const data = window.DEMO_DATA;
const rows = Object.values(data.pitches).sort((a, b) => {
  const x = a.pitch_id.split(":").map(Number),
    y = b.pitch_id.split(":").map(Number);
  return x[1] - y[1] || x[2] - y[2];
});
const requestedPitch = new URLSearchParams(location.search).get("pitch");
let selected = Object.hasOwn(data.pitches, requestedPitch) ? requestedPitch : rows[0].pitch_id,
  revealed = false,
  unit = "ft",
  filter = "all",
  view = "analysis";
const $ = (id) => document.getElementById(id);
const reasons = {
  readers_disagree_on_mitt: "두 AI 판독자의 미트 위치 불일치",
  glove_not_distinguishable: "글러브 구분 불가",
  only_one_reader_found_a_setup_frame: "한 AI 판독자만 셋업 확인",
  glove_hidden_by_catcher_body: "포수 몸에 가림",
};
const pitchTypes = {
  FF: "포심",
  SI: "싱커",
  SL: "슬라이더",
  ST: "스위퍼",
  CU: "커브",
  KC: "너클 커브",
  CH: "체인지업",
  FC: "커터",
  FS: "스플리터",
};
const signNumber = (v) => `${v > 0 ? "+" : ""}${v.toFixed(2)}`;
const format = (v) =>
  v === null ? "기권" : `${signNumber(v * (unit === "in" ? 12 : 1))} ${unit}`;
const current = () => data.pitches[selected];
const visibleRows = () =>
  rows.filter((r) => filter === "all" || r.status === filter);
const node = (tag, props = {}, text = "") => {
  const el = document.createElement(tag);
  Object.assign(el, props);
  el.textContent = text;
  return el;
};
const SVG = "http://www.w3.org/2000/svg";
function svg(tag, attrs = {}, text = "") {
  const el = document.createElementNS(SVG, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, String(v));
  el.textContent = text;
  return el;
}
function drawChart() {
  const r = current(),
    grid = $("chart-grid"),
    points = $("chart-points");
  grid.replaceChildren();
  points.replaceChildren();
  // The same horizontal sign convention is used, while rows retain their different measurement planes.
  const bound = Math.max(
    1.5,
    Math.ceil(
      Math.max(
        ...rows.map((p) => Math.abs(p.actual_plate_x_ft)),
        ...rows
          .filter((p) => p.mitt_x_ft !== null)
          .map((p) => Math.abs(p.mitt_x_ft)),
      ) * 2,
    ) / 2,
  );
  const x = (v) => 80 + ((v + bound) / (2 * bound)) * 600;
  for (let i = -3; i <= 3; i++) {
    const value = (i * bound) / 3,
      pos = x(value);
    grid.append(
      svg("line", {
        x1: pos,
        y1: 45,
        x2: pos,
        y2: 212,
        stroke: i === 0 ? "#637b9a" : "#2a405c",
        "stroke-dasharray": i === 0 ? "4 5" : "2 6",
      }),
    );
    grid.append(
      svg(
        "text",
        {
          x: pos,
          y: 246,
          fill: "#aabcce",
          "font-size": 14,
          "text-anchor": "middle",
        },
        `${signNumber(value * (unit === "in" ? 12 : 1))}`,
      ),
    );
  }
  for (const y of [92, 182])
    grid.append(
      svg("line", { x1: 80, x2: 680, y1: y, y2: y, stroke: "#3a5270" }),
    );
  grid.append(
    svg(
      "text",
      { x: 80, y: 274, fill: "#aabcce", "font-size": 13 },
      "포수 왼쪽 · 3루",
    ),
    svg(
      "text",
      {
        x: 680,
        y: 274,
        fill: "#aabcce",
        "font-size": 13,
        "text-anchor": "end",
      },
      "포수 오른쪽 · 1루",
    ),
  );
  if (!revealed) {
    $("chart-desc").textContent =
      "공개 전입니다. 투구 공개 버튼을 누르면 선택한 투구의 관측값을 표시합니다.";
    return;
  }
  const marker = (value, y, color, label) => {
    const pos = x(value);
    points.append(
      svg("circle", { cx: pos, cy: y, r: 18, fill: color, opacity: 0.12 }),
      svg("circle", {
        cx: pos,
        cy: y,
        r: 8,
        fill: color,
        stroke: color,
        "stroke-width": 2,
      }),
      svg(
        "text",
        {
          x: pos,
          y: y - 29,
          fill: color,
          "font-size": 15,
          "font-weight": 650,
          "text-anchor": "middle",
        },
        `${label} ${format(value)}`,
      ),
    );
  };
  if (r.mitt_x_ft !== null) marker(r.mitt_x_ft, 92, "#5de3cf", "미트");
  else
    points.append(
      svg(
        "text",
        {
          x: 380,
          y: 97,
          fill: "#aabcce",
          "font-size": 16,
          "text-anchor": "middle",
        },
        "미트 판독 기권 · 좌표 없음",
      ),
    );
  marker(r.actual_plate_x_ft, 182, "#ffbe69", "공");
  $("chart-desc").textContent =
    `서로 다른 측정 위치를 가로축에서 비교합니다. 미트 ${format(r.mitt_x_ft)}, 공 ${format(r.actual_plate_x_ft)}. 제구 오차를 나타내지 않습니다.`;
}
function renderList() {
  const list = $("pitch-list");
  list.replaceChildren();
  for (const r of visibleRows()) {
    const parts = r.pitch_id.split(":");
    const b = node("button", {
      className: `pitch-item ${selected === r.pitch_id ? "selected" : ""}`,
    });
    b.setAttribute("aria-pressed", String(selected === r.pitch_id));
    b.setAttribute(
      "aria-label",
      `${r.inning}회 ${r.half === "top" ? "초" : "말"}, ${parts[1]}번째 타석 ${parts[2]}구, ${r.status === "estimated" ? "좌표 있음" : "기권"}`,
    );
    b.append(
      node(
        "strong",
        {},
        `${r.inning}회 ${r.half === "top" ? "초" : "말"} · ${parts[1]}타석 ${parts[2]}구`,
      ),
      node("small", {}, r.batter),
      node(
        "span",
        {
          className: `availability ${r.status === "estimated" ? "available" : ""}`,
        },
        r.status === "estimated" ? "좌표 있음" : "기권",
      ),
    );
    b.addEventListener("click", () => selectPitch(r.pitch_id));
    list.append(b);
  }
}
function render() {
  const r = current(),
    parts = r.pitch_id.split(":");
  $("pitch-inning").textContent =
    `${r.inning}회 ${r.half === "top" ? "초" : "말"} · ${parts[1]}번째 타석`;
  $("pitch-title").textContent = `${parts[2]}구 관측`;
  $("matchup").textContent = `${r.pitcher} / ${r.batter}`;
  $("count-context").textContent =
    `투구 전 카운트 ${r.balls_before}볼 ${r.strikes_before}스트라이크`;
  $("type-context").textContent = revealed
    ? `${pitchTypes[r.pitch_type] || r.pitch_type} · ${r.pitch_type}`
    : "투구 결과 공개 대기";
  $("pitch-key").textContent = r.pitch_id;
  $("reveal-state").textContent = revealed ? "공개 후" : "공개 전";
  $("reveal-state").className = `state-label ${revealed ? "revealed" : ""}`;
  $("chart-cover").hidden = revealed;
  $("mitt-value").textContent = revealed ? format(r.mitt_x_ft) : "—";
  $("ball-value").textContent = revealed ? format(r.actual_plate_x_ft) : "—";
  $("mitt-note").textContent = !revealed
    ? "공개 전"
    : r.mitt_x_ft === null
      ? "이전 좌표를 사용하지 않습니다"
      : "영상 속 셋업 미트의 추정 위치";
  $("ball-note").textContent = revealed
    ? "저장된 Statcast 플레이트 통과 위치"
    : "공개 전";
  $("reveal-pitch").textContent = revealed
    ? "공개 전으로 되돌리기"
    : "투구 공개";
  $("observation-status").textContent = !revealed
    ? "투구 공개를 누르면 해당 기록의 관측값을 표시합니다."
    : r.status === "unavailable"
      ? `기권 사유: ${reasons[r.unavailable_reason] || r.unavailable_reason}`
      : "저장된 좌표를 표시했습니다. 실시간 분석 결과가 아닙니다.";
  const list = visibleRows(),
    index = list.findIndex((p) => p.pitch_id === selected);
  $("previous-pitch").disabled = index <= 0;
  $("next-pitch").disabled = index < 0 || index === list.length - 1;
  drawChart();
  renderList();
}
function selectPitch(id) {
  if (!Object.hasOwn(data.pitches, id))
    throw new Error("알 수 없는 투구입니다.");
  selected = id;
  revealed = false;
  render();
}
function step(delta) {
  const list = visibleRows(),
    index = list.findIndex((r) => r.pitch_id === selected),
    target = list[index + delta];
  if (target) selectPitch(target.pitch_id);
}
$("previous-pitch").addEventListener("click", () => step(-1));
$("next-pitch").addEventListener("click", () => step(1));
$("reveal-pitch").addEventListener("click", () => {
  revealed = !revealed;
  render();
});
$("pitch-filter").addEventListener("change", (e) => {
  filter = e.target.value;
  const list = visibleRows();
  if (!list.some((r) => r.pitch_id === selected)) selected = list[0].pitch_id;
  revealed = false;
  render();
});
for (const b of document.querySelectorAll("[data-unit]"))
  b.addEventListener("click", () => {
    unit = b.dataset.unit;
    for (const x of document.querySelectorAll("[data-unit]")) {
      x.classList.toggle("active", x === b);
      x.setAttribute("aria-pressed", String(x === b));
    }
    render();
  });
render();

const agreedQuote =
  "평가 2경기에서 AI와 사람이 모두 표시한 58구의 미트 점 차이 중앙값은 2.5px입니다. 같은 변환 기준의 좌표 차이는 중앙값 약 1.1인치이며, 물리 정확도나 투수 의도를 검증한 값은 아닙니다.";
$("view-validation").innerHTML = `
  <div class="page-heading"><div><p class="eyebrow">EVIDENCE, BEFORE CONFIDENCE</p><h1 id="validation-title">판독 결과를 사람의 표시와 비교했습니다.</h1><p class="subheading">필리스 @ 브레이브스 · 2026.09.29 / 레이스 @ 필리스 · 2026.09.26</p></div><span class="evidence-tag">M3 평가 기록</span></div>
  <div class="metric-grid"><article class="metric"><span>미트 점 차이 중앙값</span><strong>2.5<em>px</em></strong><p>AI와 사람이 모두 표시한 58구</p></article><article class="metric"><span>같은 변환 기준 좌표 차이</span><strong>1.1<em>in</em></strong><p>중앙값 · x·z 거리 · 물리 정확도 아님</p></article><article class="metric"><span>AI가 좌표를 출력한 장면</span><strong>58<em>/ 86</em></strong><p>기권 28장 · 기권도 결과에 포함</p></article></div>
  <div class="evidence-layout"><article class="evidence-card"><div class="section-head"><div><p class="eyebrow">ALL 86 FRAMES</p><h2>표시와 기권을 함께 봅니다.</h2></div><span class="count-tag">평가 2경기</span></div><div class="coverage-bar" aria-label="전체 86장 중 둘 다 표시 58장, 사람만 표시 26장, 둘 다 기권 2장"><span class="both" style="flex:58"></span><span class="human-only" style="flex:26"></span><span class="neither" style="flex:2"></span></div><div class="coverage-legend"><span><i style="background:#2869f5"></i>둘 다 표시 <b>58</b></span><span><i style="background:#adc7ff"></i>사람만 표시 <b>26</b></span><span><i style="background:#8994a8"></i>둘 다 기권 <b>2</b></span></div><div class="table-wrap"><table><caption>경기별 표시 수</caption><thead><tr><th>평가 경기</th><th>전체 장면</th><th>AI 표시</th><th>사람 표시</th></tr></thead><tbody><tr><th>필라델피아 필리스 @ 애틀랜타 브레이브스<br><small>2026.09.29 · NL 와일드카드 1차전 · Truist Park</small></th><td>57</td><td>43</td><td>56</td></tr><tr><th>탬파베이 레이스 @ 필라델피아 필리스<br><small>2026.09.26 · 정규시즌 · Citizens Bank Park</small></th><td>29</td><td>15</td><td>28</td></tr><tr class="total-row"><th>합계</th><td>86</td><td>58</td><td>84</td></tr></tbody></table></div><p class="evidence-foot">AI 기권 28장 중 사람은 26장에 미트를 표시했습니다. 모든 기권을 올바른 판정으로 해석할 수는 없습니다.</p></article>
  <article class="evidence-card scope-card"><p class="eyebrow">READ THE RESULT CORRECTLY</p><h2>작은 차이, 분명한 범위.</h2><div class="scope-row"><span class="scope-mark">01</span><div><h3>동일한 변환 기준</h3><p>AI와 사람 좌표가 같은 카메라 변환을 공유합니다. 실제 공간의 측정 정확도를 뜻하지 않습니다.</p></div></div><div class="scope-row"><span class="scope-mark">02</span><div><h3>한 명의 사람 검토</h3><p>사람 한 명이 한 번 표시했습니다. 사람 간 일치도와 반복 신뢰도는 아직 측정하지 않았습니다.</p></div></div><div class="scope-row"><span class="scope-mark">03</span><div><h3>압축 영상의 선택 편향</h3><p>타석 마지막 공이 많은 표본입니다. 전체 투구나 실시간 중계 성능으로 일반화하지 않습니다.</p></div></div></article></div>
  <blockquote class="agreed-quote">${agreedQuote}</blockquote>
  <div class="report-foot"><span>대표 비교: <b>크리스 세일 대 브라이슨 스톳 · 2회 초</b><br>필리스 @ 브레이브스 · 2026.09.29 · 내부 키 849845:10:4</span><button class="text-button" id="local-example-help">현장 비교 그림 안내</button></div>`;
$("view-story").innerHTML = `
  <div class="vision-intro"><p class="eyebrow">THE QUESTION BEHIND THE PROJECT</p><h1 id="story-title">포수가 요구한 곳에,<br>공이 도착했는가.</h1><p>영상에서 읽은 미트 위치를 출발점으로,<br>투구의 목표와 실행을 구분해 분석합니다.</p><span class="evidence-tag">프로젝트 목표 · 현재 검증 완료를 뜻하지 않습니다</span></div>
  <div class="journey"><article><span class="journey-number">01</span><h2>위치를 관측한다</h2><p>포수 미트 위치를 판독하고, 좌표로 변환합니다. 불일치·판독 불가 장면은 기권합니다.</p><span class="journey-status ready">구현 · 개발 자료 검증</span></article><article><span class="journey-number">02</span><h2>목표를 확인한다</h2><p>쉬는 글러브와 실제로 요구한 목표를 구분합니다. 미트가 보인다는 것만으로 목표를 확정하지 않습니다.</p><span class="journey-status">추가 정의·검증 필요</span></article><article><span class="journey-number">03</span><h2>같은 기준으로 비교한다</h2><p>목표와 공의 위치를 같은 깊이·시점·좌표 기준으로 맞춘 뒤, 투구 수행의 차이를 평가합니다.</p><span class="journey-status">향후 분석 단계</span></article></div>
  <div class="project-summary"><div><p class="eyebrow">TODAY'S DEMO</p><h2>지금 보여드리는 것은<br>관측에서 검증까지의 흐름입니다.</h2><p>39구 기록 탐색, 공개 전후 표시, 27구 미트 좌표, 12구 기권 처리와 별도 두 경기의 사람 비교 결과를 확인할 수 있습니다.</p><button class="primary-button" data-open-view="analysis">투구 관측 열기</button></div><div class="next-work"><h3>다음 검증</h3><ol><li><strong>연속 영상의 시간순 처리</strong><span>한 타석에서 실제 판독과 입력·출력 시간을 계측합니다.</span></li><li><strong>새 영상과 독립 라벨러</strong><span>이미 검토한 자료를 벗어나 새로운 평가를 수행합니다.</span></li><li><strong>목표와 도착 위치의 기준 정합</strong><span>포수 요구 위치와 공의 도착 위치를 비교할 조건을 검증합니다.</span></li></ol></div></div>`;
function setView(next) {
  if (!["analysis", "validation", "story"].includes(next))
    throw new Error("지원하지 않는 화면입니다.");
  view = next;
  for (const name of ["analysis", "validation", "story"]) {
    $(`view-${name}`).hidden = name !== next;
    $(`view-${name}`).classList.toggle("active", name === next);
  }
  for (const b of document.querySelectorAll("[data-view]")) {
    b.classList.toggle("active", b.dataset.view === next);
    if (b.dataset.view === next) b.setAttribute("aria-current", "page");
    else b.removeAttribute("aria-current");
  }
  history.replaceState(null, "", `#${next}`);
}
for (const b of document.querySelectorAll("[data-view]"))
  b.addEventListener("click", () => setView(b.dataset.view));
for (const b of document.querySelectorAll("[data-open-view]"))
  b.addEventListener("click", () => {
    setView(b.dataset.openView);
    window.scrollTo({
      top: 0,
      behavior: matchMedia("(prefers-reduced-motion: reduce)").matches
        ? "instant"
        : "smooth",
    });
  });
function showDialog(html) {
  $("dialog-content").innerHTML = html;
  $("info-dialog").showModal();
}
$("guide-button").addEventListener("click", () =>
  showDialog(
    `<p class="eyebrow">60–90 SECONDS</p><h2>이 순서로 설명해 보세요.</h2><ol><li><b>내가 맡은 부분</b><p>“영상 속 포수 미트의 AI 판독 결과를 좌표로 바꾸고, 사람 표시와 비교하는 부분을 맡았습니다.”</p></li><li><b>한 투구 공개하기</b><p>“39구 중 좌표가 있는 27구의 가로 위치를 보여줍니다. 기권 12구에는 미트 좌표를 표시하지 않습니다.”</p></li><li><b>검증 리포트로 이동하기</b><p>${agreedQuote}</p></li><li><b>목표와 현재를 구분하기</b><p>“최종적으로 포수의 요구와 투구 수행을 비교하려고 합니다. 지금은 오프라인 위치 판독을 검증한 단계이며, 실시간성과 제구 오차는 앞으로 검증합니다.”</p></li></ol>`,
  ),
);
$("source-button").addEventListener("click", () =>
  showDialog(
    `<p class="eyebrow">DATA & SCOPE</p><h2>저장된 관측 기록을 보여줍니다.</h2><p><b>시연:</b> 컵스 @ 파드리스(2026.09.29)의 기존 JSONL 39구 중 미트 좌표 27구, 기권 12구. 전체 262구 중 선택된 압축 영상 자료입니다. 이 경기의 사람 검토는 없습니다.</p><p><b>공의 위치:</b> 저장된 MLB Statcast의 홈플레이트 통과 가로 좌표를 투구 키로 연결했습니다. 미트는 플레이트 뒤의 셋업 위치이므로 같은 단위라도 같은 측정 평면이 아닙니다.</p><p><b>별도 평가:</b> 필리스 @ 브레이브스(09.29), 레이스 @ 필리스(09.26), 2026년 두 경기 총 86장. 보고서의 기존 수치를 표시하며 새 평가를 수행한 것은 아닙니다.</p><p><b>공개 버튼:</b> 사전 처리한 값의 표시를 조작하는 시연입니다. 실제 영상이나 서비스와 자동 동기화하지 않습니다. 미트 좌표를 포수의 의도, 목표 위치 정답, 제구 오차로 확정하지 않습니다.</p><p><b>자료 보존:</b> 홈과 서비스에는 사용자 승인으로 공개한 기록 리플레이와 판독 정지 이미지가 있습니다. 사람 원본 라벨은 포함하지 않습니다. 기존 시연 JSONL·M3 결과는 변경하지 않았습니다.</p><a href="https://github.com/Pitcheezy/transition-models/blob/feature/intent-v0/docs/INTENT_V0_DEMO_REHEARSAL.md" target="_blank" rel="noopener">프로젝트 검증 설명 보기</a>`,
  ),
);
$("local-example-help").addEventListener("click", () =>
  showDialog(
    `<p class="eyebrow">LOCAL PRESENTATION MATERIAL</p><h2>크리스 세일 대 브라이슨 스톳</h2><p>이미 전달한 비교 자료 ZIP 안의 <b>index.html</b>을 별도로 열어주세요. 이 비교 그림은 기존 로컬 자료에서 확인할 수 있습니다. 홈의 영상은 별도 시연 경기입니다.</p><p><b>초록 원</b>은 AI 미트 점, <b>빨간 십자</b>는 사람 미트 점입니다. 이 사례는 출력 좌표 거리의 합산 중앙값에 가장 가까운 사례로 선정됐습니다.</p><p>필리스 @ 브레이브스(2026.09.29, 내부 키849845:10:4)의 사례이며, 컵스 @ 파드리스 시연과 구분합니다. 미트 판독 비교 그림이지 공이 요구 위치에 도착했음을 입증하는 그림은 아닙니다.</p>`,
  ),
);
$("info-dialog").addEventListener("click", (e) => {
  if (e.target === $("info-dialog")) {
    const r = $("info-dialog").getBoundingClientRect();
    if (
      e.clientX < r.left ||
      e.clientX > r.right ||
      e.clientY < r.top ||
      e.clientY > r.bottom
    )
      $("info-dialog").close();
  }
});
setView(
  ["analysis", "validation", "story"].includes(location.hash.slice(1))
    ? location.hash.slice(1)
    : "analysis",
);

// WebMCP mirrors visible actions; hidden pre-reveal coordinates stay out of readback.
function stateSnapshot() {
  const r = current();
  return {
    view,
    pitch_id: selected,
    filter,
    unit,
    revealed,
    mitt_x_ft: revealed ? r.mitt_x_ft : null,
    actual_plate_x_ft: revealed ? r.actual_plate_x_ft : null,
    status: revealed ? r.status : "not_revealed",
    live_analysis: false,
  };
}
const context = document.modelContext;
if (context?.registerTool) {
  const lifecycle = new AbortController();
  const register = (tool) => {
    try {
      Promise.resolve(
        context.registerTool(tool, { signal: lifecycle.signal }),
      ).catch(() => {});
    } catch {}
  };
  register({
    name: "get_pitch_demo_state",
    title: "투구 시연 상태 읽기",
    description:
      "현재 화면과 공개 여부를 읽습니다. 공개 전 좌표는 반환하지 않습니다.",
    inputSchema: {
      type: "object",
      properties: {},
      additionalProperties: false,
    },
    annotations: { readOnlyHint: true },
    execute: () => stateSnapshot(),
  });
  register({
    name: "select_demo_pitch",
    title: "기록 투구 선택",
    description: "39개 기록 중 한 투구를 선택하고 공개 전 상태로 돌아갑니다.",
    inputSchema: {
      type: "object",
      properties: { pitch_id: { type: "string" } },
      required: ["pitch_id"],
      additionalProperties: false,
    },
    annotations: { readOnlyHint: false },
    execute: (input) => {
      if (
        !input ||
        typeof input.pitch_id !== "string" ||
        Object.keys(input).some((k) => k !== "pitch_id") ||
        !Object.hasOwn(data.pitches, input.pitch_id)
      )
        throw new Error("39개 기록에 포함된 pitch_id가 필요합니다.");
      filter = "all";
      $("pitch-filter").value = "all";
      selectPitch(input.pitch_id);
      setView("analysis");
      return stateSnapshot();
    },
  });
  register({
    name: "set_demo_reveal",
    title: "투구 공개 상태 변경",
    description:
      "선택된 기록의 관측값을 표시하거나 숨깁니다. 실제 경기 진행을 변경하지 않습니다.",
    inputSchema: {
      type: "object",
      properties: { revealed: { type: "boolean" } },
      required: ["revealed"],
      additionalProperties: false,
    },
    annotations: { readOnlyHint: false },
    execute: (input) => {
      if (
        !input ||
        typeof input.revealed !== "boolean" ||
        Object.keys(input).some((k) => k !== "revealed")
      )
        throw new Error("revealed는 boolean이어야 합니다.");
      revealed = input.revealed;
      render();
      return stateSnapshot();
    },
  });
  window.addEventListener("pagehide", () => lifecycle.abort(), { once: true });
}

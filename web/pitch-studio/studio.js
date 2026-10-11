"use strict";
const $ = (id) => document.getElementById(id),
  preview = window.PRODUCT_PREVIEW;
let scenario = "execution",
  phase = new URLSearchParams(location.search).get("phase") || "pre",
  mediaMode = "video";
const phases = ["pre", "post", "batter", "manager"];
if (!phases.includes(phase)) phase = "pre";
const getCase = () => preview.scenarios[scenario];
const percent = (x) =>
  `${(x * 100).toFixed(Math.abs(x * 100 - Math.round(x * 100)) < 1e-8 ? 0 : 1)}%`;
function renderMedia() {
  const still = mediaMode !== "video";
  $("studio-still").hidden = !still;
  $("studio-video").hidden = still;
  $("concept-target").hidden = mediaMode !== "target";
  $("actual-marker").hidden = mediaMode !== "observation";
  $("observation-panel").hidden = mediaMode !== "observation";
  if (still) $("studio-video").pause();
  $("video-status").textContent =
    mediaMode === "target"
      ? "예상 위치 표시 예시"
      : mediaMode === "observation"
        ? "실제 저장 관측 · 판독 정지 프레임"
        : "기록 리플레이 · 예시 분석의 배경 영상";
  if (mediaMode === "target")
    $("video-status").textContent =
      "예상 목표 표시 예시 · 이 영상의 실제 예측 아님";
}
function render() {
  const c = getCase();
  const situations = {
    execution: ["6회 초", "1 OUT", "1B · 2S", "1·2루"],
    batter: ["5회 초", "2 OUT", "0B · 2S", "3루"],
    manager: ["7회 초", "1 OUT", "2B · 1S", "1·2루"],
    missed: ["4회 초", "0 OUT", "2B · 1S", "2루"],
  };
  document.getElementById("situation-values").innerHTML = situations[scenario]
    .map((t) => `<span>${t}</span>`)
    .join("");
  for (const b of document.querySelectorAll("[data-phase]"))
    b.setAttribute("aria-selected", String(b.dataset.phase === phase));
  $("pitch-label").textContent = c.pitch_label;
  $("pitch-code").textContent = c.pitch_type;
  $("zone-label").textContent = c.zone_label;
  $("target-overlay-name").textContent = c.zone_label;
  $("concept-target").style.left = `${54 - ((c.zone - 1) % 3) * 4}%`;
  $("concept-target").style.top = `${47 + Math.floor((c.zone - 1) / 3) * 4}%`;
  $("zone-grid").replaceChildren();
  for (let i = 1; i <= 9; i++) {
    const cell = document.createElement("div");
    cell.className = i === c.zone ? "zone active" : "zone";
    cell.textContent = i === c.zone ? "⊕" : String(i);
    cell.setAttribute(
      "aria-label",
      i === c.zone ? `${i}번 구역, 예시 목표` : `${i}번 구역`,
    );
    $("zone-grid").append(cell);
  }
  $("pitch-options").innerHTML = c.choices
    .map(
      (p, i) =>
        `<div class="pitch-option"><span>${String(i + 1).padStart(2, "0")}</span><strong>${p.label}</strong><b>${p.share}%</b></div>`,
    )
    .join("");
  const p = c.probabilities,
    groups = [
      ["스트라이크", p.strike, "#ceff78"],
      ["볼", p.ball, "#9bada5"],
      ["파울", p.foul, "#8fc0f4"],
      ["안타", p.single + p.double + p.triple + p.home_run, "#ffb782"],
      ["아웃·병살", p.out + p.double_play, "#7aa18b"],
      ["몸에 맞는 공", p.hbp, "#8b95a8"],
    ];
  $("probability-bars").innerHTML = groups
    .map(
      ([name, value, color]) =>
        `<div class="probability-row"><span>${name}</span><b>${percent(value)}</b><div><i style="width:${value * 100}%;background:${color}"></i></div></div>`,
    )
    .join("");
  $("outcomes-detail").innerHTML = preview.class_order
    .map(
      (key) =>
        `<div><dt>${preview.labels[key]}</dt><dd>${percent(p[key])}</dd></div>`,
    )
    .join("");
  const display = {
    pre: [
      "PRE-PITCH PLAN",
      c.pre,
      "추천 구종과 목표 위치, 그 선택에서 예상되는 결과를 함께 보여주는 완성형 화면입니다.",
    ],
    post: ["PITCHER EXECUTION", c.post, c.post_text],
    batter: ["BATTER RESPONSE", c.batter, c.batter_text],
    manager: [
      "DUGOUT DECISION",
      c.manager,
      c.manager_text + " 수치는 수비 팀의 승리 전망을 가정한 예시입니다.",
    ],
  }[phase];
  $("insight-kicker").textContent = display[0];
  $("insight-title").textContent = display[1];
  $("insight-text").textContent = display[2];
  const metrics =
    phase === "manager"
      ? [
          ["현재 투수 유지", `${c.keep.toFixed(1)}%`],
          ["교체 후보 A", `${c.replace.toFixed(1)}%`],
          [
            "전망 차이",
            `${c.replace - c.keep > 0 ? "+" : ""}${(c.replace - c.keep).toFixed(1)}%p`,
          ],
        ]
      : phase === "batter"
        ? [
            ["타격 대응 지수", `${c.contact_score}/100`],
            [
              "타구 질",
              c.contact_score > 90
                ? "매우 좋음"
                : c.contact_score >= 60
                  ? "좋음"
                  : "아쉬움",
            ],
            ["결과와 분리", "대응 중심"],
          ]
        : phase === "post"
          ? [
              ["투구 수행 지수", `${c.command_score}/100`],
              ["목표 대비", c.command_score > 85 ? "일치" : "이탈"],
              ["검토 포인트", "제구·타격 분리"],
            ]
          : [
              ["추천 구종", c.pitch_label],
              ["추천 위치", c.zone_label],
              [
                "안타 확률",
                percent(p.single + p.double + p.triple + p.home_run),
              ],
            ];
  $("insight-metrics").innerHTML = metrics
    .map(
      ([name, value]) =>
        `<div><span>${name}</span><strong>${value}</strong></div>`,
    )
    .join("");
  $("attribution-grid").innerHTML = [
    ["post", "투수", c.pitcher, "요구 위치와 실행 비교"],
    ["batter", "타자", c.batter, "공의 난도와 대응 비교"],
    ["manager", "벤치", c.manager, "당시 유지·교체 대안 비교"],
  ]
    .map(
      ([id, name, value, note]) =>
        `<button data-card-phase="${id}" class="attribution ${phase === id ? "selected" : ""}"><span>${name} 관점 </span><strong>${value}</strong><small>${note}</small></button>`,
    )
    .join("");
  for (const b of document.querySelectorAll("[data-card-phase]"))
    b.addEventListener("click", () => setPhase(b.dataset.cardPhase));
  $("dugout-title").textContent = c.manager;
}
function setPhase(next) {
  if (!phases.includes(next)) return;
  phase = next;
  render();
}
for (const b of document.querySelectorAll("[data-phase]")) {
  b.addEventListener("click", () => setPhase(b.dataset.phase));
  b.addEventListener("keydown", (e) => {
    if (!["ArrowLeft", "ArrowRight"].includes(e.key)) return;
    e.preventDefault();
    const next =
      phases[(phases.indexOf(phase) + (e.key === "ArrowRight" ? 1 : 3)) % 4];
    document.querySelector(`[data-phase="${next}"]`).focus();
    setPhase(next);
  });
}
$("scenario").addEventListener("change", (e) => {
  if (!Object.hasOwn(preview.scenarios, e.target.value)) return;
  scenario = e.target.value;
  mediaMode = "video";
  renderMedia();
  render();
});
$("show-target").addEventListener("click", () => {
  mediaMode = "target";
  renderMedia();
});
$("show-observation").addEventListener("click", () => {
  mediaMode = "observation";
  renderMedia();
});
$("play-clip").addEventListener("click", () => {
  mediaMode = "video";
  renderMedia();
  $("studio-video").currentTime = 0;
  $("studio-video")
    .play()
    .catch(() => {
      $("video-status").textContent = "영상 컨트롤의 재생 버튼을 눌러주세요";
    });
});
$("studio-video").addEventListener("play", () => {
  mediaMode = "video";
  renderMedia();
});
$("studio-video").addEventListener("error", () => {
  $("video-status").textContent = "영상 재생 불가 · 정지 장면을 이용하세요";
});
$("view-manager").addEventListener("click", () => setPhase("manager"));
$("open-contract").addEventListener("click", () =>
  $("contract-dialog").showModal(),
);
render();
renderMedia();

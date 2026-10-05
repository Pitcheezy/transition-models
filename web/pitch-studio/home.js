"use strict";
const film = document.getElementById("hero-video"),
  poster = document.getElementById("hero-still"),
  mark = document.getElementById("hero-marker"),
  toggle = document.getElementById("hero-toggle"),
  label = document.getElementById("film-mode");
let observing = false;
function setObservation(value) {
  observing = value;
  film.hidden = value;
  poster.hidden = !value;
  mark.hidden = !value;
  if (value) film.pause();
  else
    film.play().catch(() => {
      label.textContent = "버튼을 눌러 영상을 재생해주세요";
    });
  toggle.textContent = value ? "영상 다시 재생 ↻" : "미트 위치 보기 ＋";
  label.textContent = value
    ? "사전 판독 · 정지 프레임 · 실시간 추적 아님"
    : "실제 중계 프레임으로 재구성한 리플레이";
}
toggle.addEventListener("click", () => setObservation(!observing));
if (matchMedia("(prefers-reduced-motion: reduce)").matches)
  setObservation(true);
film.addEventListener("error", () => {
  setObservation(true);
  label.textContent = "정지 장면으로 보기 · 영상 재생 불가";
});
const oldViews = {
  "#analysis": "service.html",
  "#validation": "report.html#validation",
  "#story": "report.html#story",
};
if (Object.hasOwn(oldViews, location.hash))
  location.replace(oldViews[location.hash]);

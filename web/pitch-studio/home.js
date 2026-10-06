"use strict";
const film = document.getElementById("hero-video"),
  poster = document.getElementById("hero-still"),
  mark = document.getElementById("hero-marker"),
  toggle = document.getElementById("hero-toggle"),
  play = document.getElementById("hero-play"),
  label = document.getElementById("film-mode");
let observing = false;
let playRequest = 0;
let mediaFailed = false;
function showPlaybackState() {
  if (observing) return;
  play.textContent = film.paused ? "영상 재생 ▶" : "일시정지 Ⅱ";
  label.textContent = film.paused
    ? "일시정지 · 재생 버튼으로 계속 보기"
    : "실제 중계 프레임으로 재구성한 리플레이";
}
async function playFilm() {
  const request = ++playRequest;
  label.textContent = "영상을 불러오는 중입니다";
  try {
    if (mediaFailed || film.error) {
      mediaFailed = false;
      film.load();
    }
    await film.play();
    if (!observing && request === playRequest) showPlaybackState();
  } catch {
    // An earlier request must not overwrite the still-frame or a newer retry.
    if (observing || request !== playRequest) return;
    play.textContent = "영상 재생 ▶";
    label.textContent = "재생 버튼을 눌러주세요 · 미트 정지 장면도 볼 수 있습니다";
  }
}
function setObservation(value) {
  ++playRequest;
  observing = value;
  film.hidden = value;
  poster.hidden = !value;
  mark.hidden = !value;
  play.hidden = value;
  toggle.textContent = value ? "영상 다시 재생 ↻" : "미트 위치 보기 ＋";
  if (value) {
    film.pause();
    label.textContent = "사전 판독 · 정지 프레임 · 실시간 추적 아님";
  } else playFilm();
}
toggle.addEventListener("click", () => setObservation(!observing));
play.addEventListener("click", () => {
  if (film.paused) playFilm();
  else {
    ++playRequest;
    film.pause();
    showPlaybackState();
  }
});
film.addEventListener("playing", () => {
  if (observing) film.pause();
  else showPlaybackState();
});
film.addEventListener("pause", showPlaybackState);
function showMediaError() {
  mediaFailed = true;
  setObservation(true);
  label.textContent = "정지 장면으로 보기 · 영상 재생 불가";
}
film.addEventListener("error", showMediaError);
film.querySelector("source")?.addEventListener("error", showMediaError);
setObservation(matchMedia("(prefers-reduced-motion: reduce)").matches);
const oldViews = {
  "#analysis": "service.html",
  "#validation": "report.html#validation",
  "#story": "report.html#story",
};
if (Object.hasOwn(oldViews, location.hash))
  location.replace(oldViews[location.hash]);

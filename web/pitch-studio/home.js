"use strict";
const film = document.getElementById("hero-video"), poster = document.getElementById("hero-still"), play = document.getElementById("hero-play"), label = document.getElementById("film-mode");
let still = true, playRequest = 0, mediaFailed = false;
function showPlaybackState() {
  if (still) return;
  play.textContent = film.paused ? "영상 재생 ▶" : "일시정지 Ⅱ";
  label.textContent = film.paused ? "일시정지 · 재생 버튼으로 계속 보기" : "4투구 하이라이트 · 약 24초";
}
function showStill(message) {
  ++playRequest; still = true;
  film.pause(); film.hidden = true; poster.hidden = false;
  play.textContent = "영상 재생 ▶"; label.textContent = message;
}
async function playFilm() {
  const request = ++playRequest;
  label.textContent = "영상을 불러오는 중입니다";
  try {
    if (mediaFailed || film.error) { mediaFailed = false; film.load(); }
    await film.play();
    if (request !== playRequest) return;
    still = false; film.hidden = false; poster.hidden = true;
    showPlaybackState();
  } catch (error) {
    if (request !== playRequest) return;
    if (error?.name === "NotAllowedError") showStill("재생 버튼을 눌러주세요 · 첫 타석 관전은 바로 열 수 있습니다");
    else showMediaError();
  }
}
play.addEventListener("click", () => {
  if (film.paused || still) playFilm();
  else { ++playRequest; film.pause(); showPlaybackState(); }
});
film.addEventListener("playing", showPlaybackState);
film.addEventListener("pause", showPlaybackState);
function showMediaError() {
  mediaFailed = true;
  showStill("영상 연결을 확인해 주세요 · 재생 버튼으로 다시 시도");
}
film.addEventListener("error", showMediaError);
film.querySelector("source")?.addEventListener("error", showMediaError);
if (film.networkState === 3) mediaFailed = true;
showStill("경기 미리보기 · 재생 버튼으로 하이라이트 보기");
if (!matchMedia("(prefers-reduced-motion: reduce)").matches) playFilm();
const oldViews = {"#analysis":"watch.html?game=849843","#validation":"report.html#validation","#story":"report.html#story"};
function redirectOldView() { if (Object.hasOwn(oldViews,location.hash)) location.replace(oldViews[location.hash]); }
redirectOldView(); window.addEventListener("hashchange",redirectOldView);

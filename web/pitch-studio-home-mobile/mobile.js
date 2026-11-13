"use strict";
// 모바일 데모 홈 전용 스크립트. hero 영상 제어는 web/pitch-studio-home/home.js와 같은 동작이다.
// 차이: (1) <source>가 둘(공개 미디어 주소 → 같은 폴더 사본)이라 마지막 source의 error만 '모두 실패'로 본다.
//       (2) 데이터 절약 모드(saveData)에서는 자동재생하지 않고 포스터를 유지한다. <video>에 autoplay 속성을 두지 않아
//           자동재생은 오직 아래 play() 호출이 맡는다(속성이 있으면 브라우저가 스크립트와 무관하게 받아 재생을 시도할 수 있음).
//       (3) 고정 하단 바의 실제 높이를 --bar-h 에 반영해 본문 끝이 가려지지 않게 한다.
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
    if (error?.name === "NotAllowedError") showStill("재생 버튼을 눌러주세요 · 서비스는 아래 ‘서비스 열기’로 바로 열 수 있습니다");
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
const sources = film.querySelectorAll("source");
sources[sources.length - 1]?.addEventListener("error", showMediaError);
if (film.networkState === 3) mediaFailed = true;
showStill("경기 미리보기 · 재생 버튼으로 하이라이트 보기");
const saveData = navigator.connection?.saveData === true;
if (saveData) film.preload = "none"; // 힌트일 뿐이며 이미 시작된 metadata 요청은 막지 못할 수 있다(추정)
if (!matchMedia("(prefers-reduced-motion: reduce)").matches && !saveData) playFilm();
else if (saveData) label.textContent = "데이터 절약 모드 · 재생 버튼으로 하이라이트 보기";

// 고정 하단 바 높이 → CSS 변수. ResizeObserver가 없으면 CSS 기본값(132px)을 그대로 쓴다.
// border-box를 관찰해야 safe-area 패딩만 바뀌는 경우(iOS 도구막대 접힘 등, 추정)도 감지된다.
const bar = document.querySelector(".cta-bar");
if (bar && "ResizeObserver" in window) {
  new ResizeObserver(() => {
    document.documentElement.style.setProperty("--bar-h", `${Math.ceil(bar.getBoundingClientRect().height)}px`);
  }).observe(bar, { box: "border-box" });
}

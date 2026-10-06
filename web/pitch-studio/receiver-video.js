/* Playback of a verified, fixed pitch excerpt. Never an automatic video detector. */
(function (root) {
  "use strict";
  const PITCH = "849843:1:3";
  const VIDEO = "media/pitch-849843-1-3.mp4";
  function create(elements, onReveal) {
    const { video, section, frame, missing, status, play, fallback } = elements;
    let binding = null, active = false, generation = 0, failed = false;
    let revealed = false, started = false;
    function reset() {
      generation++;
      started = false;
      video.pause();
      try { video.currentTime = 0; } catch (_) { /* Metadata may not be loaded yet. */ }
      video.load();
      play.textContent = "투구 영상 재생";
    }
    function update(state) {
      const next = state?.enabled ? `${state.context}:${state.pitch_id}` : null;
      const changed = binding !== next;
      const hiding = !changed && revealed && !state?.revealed;
      if (changed) {
        active = false;
        reset();
        binding = next;
        failed = false;
      }
      section.hidden = !state?.enabled;
      active = Boolean(state?.enabled && state.pitch_id === PITCH);
      frame.hidden = !active;
      missing.hidden = active;
      play.hidden = !active;
      revealed = Boolean(state?.revealed);
      if (active) {
        if (video.getAttribute("src") !== VIDEO) {
          video.setAttribute("src", VIDEO);
          video.load();
        }
        if (hiding) reset();
        video.hidden = failed;
        fallback.hidden = !failed;
        if (changed || hiding) {
          status.textContent = "3구 투구 동작 · 약 3초 · 소리 없음. 재생이 끝나면 저장된 결과를 공개합니다.";
        }
      } else {
        video.removeAttribute("src");
        status.textContent = "1·2구는 영상 미확보입니다. 추천과 실제 결과는 아래에서 확인할 수 있습니다.";
      }
    }
    async function toggle() {
      if (!active) return;
      if (!video.paused) { video.pause(); return; }
      const request = ++generation;
      if (failed) {
        failed = false;
        video.hidden = false;
        fallback.hidden = true;
        video.load();
      }
      if (video.ended) video.currentTime = 0;
      try { await video.play(); }
      catch (_) {
        if (request !== generation || !active) return;
        status.textContent = "재생을 시작하지 못했습니다. 재생 버튼을 다시 눌러주세요.";
        play.textContent = "다시 재생 시도";
      }
    }
    play.addEventListener("click", toggle);
    video.addEventListener("play", () => {
      if (!active) { video.pause(); return; }
      started = true;
      play.textContent = "일시정지";
      status.textContent = "3구 영상 재생 중 · 실제 투구를 확인한 뒤 저장 결과를 표시합니다.";
    });
    video.addEventListener("pause", () => {
      if (active && !failed) play.textContent = video.ended ? "영상 다시 보기" : "투구 영상 재생";
    });
    video.addEventListener("ended", () => {
      if (!active || !started || !video.ended) return;
      started = false;
      onReveal(binding);
      play.textContent = "영상 다시 보기";
      status.textContent = "3구 영상 재생 완료 · 아래에 실제 결과와 저장된 미트 가로 위치를 공개했습니다.";
    });
    video.addEventListener("error", () => {
      if (!active || !video.error) return;
      failed = true;
      started = false;
      video.hidden = true;
      fallback.hidden = false;
      play.textContent = "영상 다시 불러오기";
      status.textContent = "영상 로딩 실패 · 확인된 정지 장면을 표시합니다. 다시 불러오거나 아래 결과 공개를 사용할 수 있습니다.";
    });
    return { update };
  }
  const api = { create };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PitchReceiverVideo = api;
})(typeof window !== "undefined" ? window : globalThis);

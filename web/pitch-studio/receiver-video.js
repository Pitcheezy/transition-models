/* Verified per-pitch replay and a separately annotated still. No live tracking. */
(function (root) {
  "use strict";
  function create(elements, onReveal, media) {
    const { video, section, frame, missing, status, play, fallback,
      inspect, observationImage, marker, observationNote, sourceLink } = elements;
    let binding = null, active = false, generation = 0, failed = false;
    let revealed = false, started = false, inspecting = false, record = null;
    let canInspect = false;
    function showMode() {
      video.hidden = inspecting || failed;
      fallback.hidden = inspecting || !failed;
      observationImage.hidden = !inspecting;
      marker.hidden = !(inspecting && canInspect && observationImage.complete && observationImage.naturalWidth > 0);
      observationNote.hidden = !inspecting;
      inspect.textContent = inspecting ? "영상으로 돌아가기" : "미트 판독 장면";
      inspect.disabled = !canInspect;
    }
    function reset() {
      generation++;
      started = false;
      inspecting = false;
      video.pause();
      try { video.currentTime = 0; } catch (_) { /* Metadata may not be loaded yet. */ }
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
      record = state?.enabled && Object.hasOwn(media, state.pitch_id) ? media[state.pitch_id] : null;
      active = Boolean(record);
      section.hidden = !state?.enabled;
      frame.hidden = !active;
      missing.hidden = active;
      play.hidden = !active;
      revealed = Boolean(state?.revealed);
      canInspect = Boolean(active && revealed && state?.observationAllowed && record.observation);
      inspect.hidden = !record?.observation;
      if (!canInspect) inspecting = false;
      sourceLink.hidden = !active || !revealed;
      if (active) {
        video.setAttribute("aria-label", `첫 타석 ${record.pitch_number}구의 실제 투구 영상`);
        video.setAttribute("poster", record.poster);
        fallback.setAttribute("src", record.poster);
        fallback.setAttribute("alt", `${record.pitch_number}구 투구 전 정지 장면 · 미트 주석 없음`);
        if (changed || video.getAttribute("src") !== record.video) {
          video.setAttribute("src", record.video);
          video.load();
        }
        if (hiding) { reset(); video.load(); }
        if (record.observation) {
          observationImage.setAttribute("src", record.observation.poster);
          marker.style.left = `${record.observation.x_pixels / record.observation.width * 100}%`;
          marker.style.top = `${record.observation.y_pixels / record.observation.height * 100}%`;
        }
        sourceLink.href = record.page_url;
        if (changed || hiding) {
          status.textContent = `${record.pitch_number}구 · 약 ${Math.round(record.duration_seconds)}초. 재생이 끝나면 저장된 결과를 공개합니다.`;
        }
      } else {
        video.removeAttribute("src");
        video.load();
        sourceLink.removeAttribute("href");
        status.textContent = "이 자료에 대응하는 확인된 영상이 없습니다.";
      }
      showMode();
    }
    async function toggle() {
      if (!active) return;
      if (!video.paused && !inspecting) { video.pause(); return; }
      const request = ++generation;
      if (inspecting) { inspecting = false; video.currentTime = 0; }
      if (failed) { failed = false; video.load(); }
      showMode();
      if (video.ended) video.currentTime = 0;
      try { await video.play(); }
      catch (error) {
        if (request !== generation || !active || inspecting) return;
        if (error.name === "AbortError" && video.paused) return;
        status.textContent = "재생을 시작하지 못했습니다. 재생 버튼을 다시 눌러주세요.";
        play.textContent = "다시 재생 시도";
      }
    }
    function inspectStill() {
      if (!canInspect) return;
      if (inspecting) { toggle(); return; }
      generation++;
      inspecting = true;
      started = false;
      video.pause();
      showMode();
      play.textContent = "영상 다시 보기";
      status.textContent = "별도로 판독한 투구 전 정지 장면 · 초록 표시가 저장된 미트 중심입니다.";
    }
    play.addEventListener("click", toggle);
    inspect.addEventListener("click", inspectStill);
    observationImage.addEventListener("load", showMode);
    observationImage.addEventListener("error", () => {
      marker.hidden = true;
      if (inspecting) status.textContent = "판독 장면을 불러오지 못했습니다. 영상으로 돌아가거나 저장된 가로 위치를 확인해주세요.";
    });
    video.addEventListener("play", () => {
      if (!active || inspecting) { video.pause(); return; }
      started = true;
      play.textContent = "일시정지";
      status.textContent = `${record.pitch_number}구 영상 재생 중 · 재생 후 저장 결과를 표시합니다.`;
    });
    video.addEventListener("playing", () => {
      if (!active || inspecting) video.pause();
    });
    video.addEventListener("pause", () => {
      generation++;
      if (active && !failed && !inspecting) {
        play.textContent = video.ended ? "영상 다시 보기" : "투구 영상 재생";
        if (!video.ended) status.textContent = `${record.pitch_number}구 영상 일시정지 · 재생 버튼으로 이어볼 수 있습니다.`;
      }
    });
    video.addEventListener("ended", () => {
      if (!active || inspecting || !started || !video.ended) return;
      started = false;
      onReveal(binding);
      play.textContent = "영상 다시 보기";
      status.textContent = `${record.pitch_number}구 재생 완료 · 실제 결과 공개${canInspect ? " · 미트 판독 장면도 확인할 수 있습니다." : " · 이 투구의 미트 관측은 없습니다."}`;
    });
    video.addEventListener("error", () => {
      if (!active || !video.error) return;
      failed = true;
      started = false;
      showMode();
      if (inspecting) return;
      play.textContent = "영상 다시 불러오기";
      status.textContent = "영상 로딩 실패 · 확인된 정지 장면을 표시합니다. 다시 불러오거나 결과 공개를 사용할 수 있습니다.";
    });
    return { update };
  }
  const api = { create };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PitchReceiverVideo = api;
})(typeof window !== "undefined" ? window : globalThis);

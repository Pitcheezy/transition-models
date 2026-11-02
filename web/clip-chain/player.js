"use strict";
(async function () {
  const $ = id => document.getElementById(id), api = window.ClipChain;
  let registry, state, video = null, rate = 1;
  const selectable = ["global", "pa", "pitch", "prev", "next", "speed", "full", "copy", "start", "stop"];
  const putStatus = text => { $("status").textContent = text; };
  const label = p => api.label(p), autoplayText = "자동 재생이 허용되지 않았습니다. 영상의 재생 버튼을 눌러 주세요.";
  function reason(p) { return p.reason === "pitch_type_mismatch" ? "영상 등록부와 받은 경기 자료의 구종이 달라 제외했습니다" : p.reason; }
  function options(node, rows) { node.replaceChildren(...rows.map(([value, text]) => { const option = document.createElement("option"); option.value = value; option.textContent = text; return option; })); }
  function dispatch(event) {
    const previous = state; state = api.transition(state, registry, event);
    if (state.epoch !== previous.epoch) render(); else buttons();
  }
  function buttons() {
    const p = registry.pitches[state.index], usable = p.status === "available";
    $("prev").disabled = state.index === 0; $("next").disabled = state.index === registry.pitches.length - 1;
    $("start").disabled = !usable || state.chain || state.mode === "error";
    $("stop").disabled = !state.chain; $("full").disabled = !usable; $("speed").disabled = !usable;
    $("retry").hidden = state.mode !== "error";
    if (state.mode === "unavailable") putStatus(`영상 제외 · ${reason(p)} · 다음 공을 직접 선택하세요.`);
    else if (state.mode === "error") putStatus("영상 재생을 중단했습니다. serve.py 터미널이 켜져 있는지 확인하고, 다시 켰다면 터미널에 표시된 주소로 이 페이지를 다시 여세요. 그 뒤 이 공을 다시 불러오세요.");
    else if (state.mode === "ended") putStatus(state.index === registry.pitches.length - 1 ? "경기 마지막 투구 클립이 끝났습니다." : "클립이 끝났습니다. 다음 공을 선택하거나 이어 재생하세요.");
    else putStatus(state.chain ? "이어 재생 중 · 클립 종료 후 다음 구로 이동" : state.mode === "playing" ? "현재 투구만 재생 중" : "모니터 1의 이닝(초/말)·타자·N구를 맞춘 뒤 재생하세요.");
  }
  async function play(epoch) {
    const current = video;
    if (!current || epoch !== state.epoch) return;
    if (current.ended) current.currentTime = 0;
    try { await current.play(); }
    catch (error) {
      // AbortError: a newer load or an intentional pause superseded this play(). Keep an error state's own message.
      if (epoch !== state.epoch || error?.name === "AbortError" || state.mode === "error") return;
      dispatch({type:"stop",epoch});
      if (error?.name === "NotAllowedError") putStatus(autoplayText);
    }
  }
  function render() {
    const p = registry.pitches[state.index], epoch = state.epoch;
    const prior = video; video = null;
    // A fresh video node binds every media event to one immutable pitch generation.
    if (prior) { prior.pause(); prior.removeAttribute("src"); prior.load(); }
    $("identity").textContent = label(p); $("ordinal").textContent = `${p.game_pitch_number} / ${registry.pitches.length}구`;
    $("pitch-key").textContent = p.pitch_key; $("players").textContent = `${p.pitcher || "투수 미표시"} → ${p.batter || "타자 미표시"}`;
    $("global").value = String(state.index); $("pa").value = String(p.pa_index);
    options($("pitch"), registry.pitches.flatMap((row, i) => row.pa_index === p.pa_index ? [[String(i), `${row.pitch_number}구${row.status === "excluded" ? " · 영상 제외" : ""}`]] : []));
    $("pitch").value = String(state.index);
    const url = new URL(location.href); url.searchParams.set("pitch", p.pitch_key); history.replaceState(null, "", url);
    $("video-slot").replaceChildren();
    if (p.status === "available") {
      const node = document.createElement("video"); video = node;
      // The load algorithm resets playbackRate to defaultPlaybackRate, so both carry the chosen speed into every new clip.
      node.controls = true; node.playsInline = true; node.preload = "metadata"; node.defaultPlaybackRate = rate; node.playbackRate = rate;
      node.setAttribute("aria-label", `${label(p)} 공식 투구 클립`); node.src = p.src;
      const valid = () => epoch === state.epoch && video === node;
      node.addEventListener("playing", () => { if (valid()) dispatch({type:"playing",epoch}); });
      node.addEventListener("pause", () => { if (valid() && !node.ended) dispatch({type:"pause",epoch}); });
      node.addEventListener("seeking", () => { if (valid()) { dispatch({type:"seek",epoch}); if (!node.paused) dispatch({type:"playing",epoch}); } });
      node.addEventListener("error", () => { if (valid()) { dispatch({type:"error",epoch}); node.pause(); } });
      node.addEventListener("ended", () => { if (valid()) dispatch({type:"ended",epoch}); });
      $("video-slot").append(node);
      if (state.chain) void play(epoch);
    } else { const note = document.createElement("p"); note.className = "empty"; note.textContent = `이 공의 영상은 연결하지 않았습니다. ${reason(p)}`; $("video-slot").append(note); }
    buttons();
  }
  try {
    const response = await fetch("registry.json", {cache:"no-store"});
    if (!response.ok) throw new Error("등록부 파일을 읽지 못했습니다.");
    registry = api.validateRegistry(await response.json());
    const requested = new URLSearchParams(location.search).get("pitch"); let notice = null;
    try { state = api.createState(registry, requested); }
    catch (error) { if (!requested) throw error; state = api.createState(registry); notice = `주소의 ?pitch=${requested.slice(0, 40)} 값은 등록되지 않은 투구 ID입니다. 첫 투구를 표시합니다. 모니터 1의 이닝·타자·N구로 다시 선택하세요.`; }
    options($("global"), registry.pitches.map((p, i) => [String(i), `${p.game_pitch_number} · ${label(p)}${p.status === "excluded" ? " · 영상 제외" : ""}`]));
    const paRows = new Map(); registry.pitches.forEach(p => { if (!paRows.has(p.pa_index)) paRows.set(p.pa_index, api.paLabel(p)); });
    options($("pa"), [...paRows].map(([id, text]) => [String(id), text]));
    selectable.forEach(id => { $(id).disabled = false; });
    $("coverage").textContent = "전체 262구 · 영상 연결 261구 · 식별 불일치 제외 1구. 전시용 비공개 파일로 실행합니다.";
    const choose = index => dispatch({type:"select",index});
    $("global").addEventListener("change", e => choose(Number(e.target.value)));
    $("pitch").addEventListener("change", e => choose(Number(e.target.value)));
    $("pa").addEventListener("change", e => choose(registry.pitches.findIndex(p => p.pa_index === Number(e.target.value))));
    $("prev").addEventListener("click", () => choose(state.index - 1)); $("next").addEventListener("click", () => choose(state.index + 1));
    $("retry").addEventListener("click", () => choose(state.index));
    $("start").addEventListener("click", () => { const priorEpoch = state.epoch; dispatch({type:"start"}); if (state.chain && state.epoch === priorEpoch) void play(state.epoch); });
    $("stop").addEventListener("click", () => { dispatch({type:"stop"}); video?.pause(); });
    $("speed").addEventListener("change", e => { rate = Number(e.target.value); if (video) { video.defaultPlaybackRate = rate; video.playbackRate = rate; } });
    // The stage (identity line + video + pitch key) goes fullscreen, so it survives video node replacement and keeps the pitch visible.
    $("full").addEventListener("click", async () => { try { if (document.fullscreenElement) await document.exitFullscreen(); else if ($("stage").requestFullscreen) await $("stage").requestFullscreen(); else if (video?.webkitEnterFullscreen) video.webkitEnterFullscreen(); else putStatus("영상의 전체 화면 버튼을 이용해 주세요."); } catch { putStatus("이 브라우저에서는 영상의 전체 화면 버튼을 이용해 주세요."); } });
    $("copy").addEventListener("click", async () => { try { await navigator.clipboard.writeText(registry.pitches[state.index].pitch_key); putStatus("현재 투구 ID를 복사했습니다."); } catch { putStatus(`복사가 허용되지 않았습니다. 이 ID를 직접 사용하세요: ${registry.pitches[state.index].pitch_key}`); } });
    // A mouse click leaves focus on the button in Chrome/Edge; drop it so Space/arrows reach the shortcuts instead of re-pressing the button.
    ["prev", "next", "retry", "copy", "full", "start", "stop"].forEach(id => $(id).addEventListener("click", e => { if (e.detail > 0) e.currentTarget.blur(); }));
    document.addEventListener("keydown", e => { if (e.ctrlKey || e.altKey || e.metaKey || e.target.closest("input,select,textarea,button,a,video,[contenteditable]")) return; if (e.key === "ArrowLeft") { e.preventDefault(); choose(state.index - 1); } else if (e.key === "ArrowRight") { e.preventDefault(); choose(state.index + 1); } else if (e.code === "Space" && video) { e.preventDefault(); if (state.mode === "error") return; if (video.paused) void play(state.epoch); else video.pause(); } });
    window.addEventListener("pagehide", () => {
      state = api.transition(state, registry, {type:"suspend"}); video?.pause();
    });
    window.addEventListener("pageshow", event => {
      if (!event.persisted) return;
      // BFCache preserves old listeners too. Rebuild the video with a fresh
      // generation at 0 seconds, keep the selected pitch, and require an explicit play.
      state = api.transition(state, registry, {type:"select",index:state.index});
      render();
      if (registry.pitches[state.index].status === "available") putStatus("돌아온 투구를 처음부터 재생하세요. 이어 재생은 자동으로 시작하지 않습니다.");
    });
    render();
    if (notice) putStatus(notice);
  } catch (error) { selectable.forEach(id => { $(id).disabled = true; }); $("identity").textContent = "영상 플레이어를 시작할 수 없습니다"; $("video-slot").textContent = "전달팩을 다시 확인해 주세요."; putStatus(`${error.message} ZIP을 모두 풀고 serve.py로 실행하세요.`); }
})();

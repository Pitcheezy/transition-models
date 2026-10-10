"use strict";
(function () {
  const fail = message => { throw new Error(message); };
  function seconds(value) {
    if (typeof value !== "string" || !/^(0|[1-9]\d*)(\/[1-9]\d*)?$/.test(value)) fail("시각 형식이 올바르지 않습니다.");
    const parts = value.split("/").map(Number);
    if (parts.some(n => !Number.isSafeInteger(n))) fail("시각 범위가 너무 큽니다.");
    const n = parts[0] / (parts[1] || 1);
    if (!Number.isFinite(n)) fail("시각 범위를 확인하세요.");
    return n;
  }
  const inScope = (data, o) => {
    const t = seconds(o.frame_seconds_exact ?? o.cutoff_seconds_exact);
    return t >= seconds(data.scope.start_source_seconds_exact) && t < seconds(data.scope.end_source_seconds_exact);
  };
  function validateData(data) {
    if (!data || data.schema !== "intent_observation_playback_v1") fail("지원하지 않는 재생 자료입니다.");
    const { media: m, scope: s, observations: obs, references: refs, summary: sum } = data;
    if (!m || m.path !== "media/clip.mp4" || !/^[a-f0-9]{64}$/.test(m.sha256)) fail("영상 식별 정보가 잘못되었습니다.");
    if (!s || !Number.isSafeInteger(s.game_pk) || s.game_pk <= 0 || !Number.isSafeInteger(s.pa) || s.pa <= 0 || s.full_pa_verified !== false || s.live_availability_verified !== false || s.human_label !== false) fail("이 화면은 검증 전 개발 구간만 지원합니다.");
    const offset = seconds(m.source_offset_seconds_exact), end = seconds(m.clip_end_seconds_exact);
    const low = seconds(s.start_source_seconds_exact), high = seconds(s.end_source_seconds_exact);
    if (low < offset || high <= low || high > offset + end) fail("구간이 영상 범위를 벗어났습니다.");
    if (!Array.isArray(obs) || !obs.length || !Array.isArray(refs) || !refs.length || !sum) fail("관측 또는 투구 참조가 없습니다.");
    const ids = new Set(); let priorDecision = -1;
    for (const r of refs) {
      if (!new RegExp(`^${s.game_pk}:${s.pa}:[1-9]\\d*$`).test(r.pitch_id) || ids.has(r.pitch_id)) fail("투구 참조 식별자가 잘못되었습니다.");
      ids.add(r.pitch_id);
      const d = seconds(r.decision_seconds_exact), u = seconds(r.decision_upper_seconds_exact), l = seconds(r.release_lower_seconds_exact), h = seconds(r.release_upper_seconds_exact);
      if (d < priorDecision || u < d || h <= d || h < u || h < l || typeof r.conservative_temporal_ready !== "boolean" || typeof r.nominal_start_temporal_ready !== "boolean" || r.usable_mitt !== false) fail("투구 참조 시각/범위가 잘못되었습니다.");
      priorDecision = d;
    }
    let previous = -1, previousCutoff = -1;
    for (const o of obs) {
      if (!Number.isSafeInteger(o.index) || o.index <= previous) fail("관측 순서가 중복되거나 바뀌었습니다.");
      previous = o.index;
      const cutoff = seconds(o.cutoff_seconds_exact);
      if (cutoff < previousCutoff) fail("마감 시각 순서가 잘못되었습니다.");
      previousCutoff = cutoff;
      if (o.reference_pitch_id !== null && !ids.has(o.reference_pitch_id)) fail("다른 투구의 관측입니다.");
      if (!["accepted", "error", "not_attempted"].includes(o.status)) fail("알 수 없는 실행 상태입니다.");
      if (o.frame_seconds_exact !== null && seconds(o.frame_seconds_exact) > cutoff) fail("마감 이후 프레임이 들어왔습니다.");
      if (o.status === "accepted") {
        if (o.frame_seconds_exact === null || seconds(o.publication_seconds_exact) < cutoff || !["unknown", "unavailable"].includes(o.observation_status) || !["candidate", "ambiguous", "no_candidate"].includes(o.candidate_status) || !/^frames\/\d+\.jpg$/.test(o.image_path)) fail("확정되지 않은 관측 계약이 잘못되었습니다.");
      } else if (o.publication_seconds_exact !== null || o.image_path !== null || o.candidate_status !== o.status || ![null, "unavailable"].includes(o.observation_status)) fail("오류/미시도 상태에 결과가 붙어 있습니다.");
    }
    const count = status => obs.filter(o => o.status === status).length;
    const n = obs.filter(o => inScope(data, o)).length;
    const expected = { planned_observations: obs.length, interval_observations: n, outside_interval_observations: obs.length - n, accepted: count("accepted"), errors: count("error"), not_attempted: count("not_attempted"), verified_mitt: 0, conservative_ready_pitches: refs.filter(r => r.conservative_temporal_ready).length };
    for (const [key, value] of Object.entries(expected)) if (sum[key] !== value) fail("요약 수치와 관측 기록이 다릅니다.");
    return data;
  }
  function stateAt(data, clipSeconds) {
    if (!Number.isFinite(clipSeconds)) fail("영상 시각이 잘못되었습니다.");
    const source = clipSeconds + seconds(data.media.source_offset_seconds_exact);
    const low = seconds(data.scope.start_source_seconds_exact), high = seconds(data.scope.end_source_seconds_exact);
    const active = source >= low && source < high ? data.references.find(r => source >= seconds(r.decision_seconds_exact) && source < seconds(r.release_upper_seconds_exact)) || null : null;
    const published = data.observations.filter(o => o.status === "accepted" && inScope(data, o) && source >= low && seconds(o.publication_seconds_exact) < high && seconds(o.publication_seconds_exact) <= source);
    const latest = published.reduce((last, o) => !last || seconds(o.publication_seconds_exact) >= seconds(last.publication_seconds_exact) ? o : last, null);
    const timely = active ? published.filter(o => o.reference_pitch_id === active.pitch_id && seconds(o.frame_seconds_exact) >= seconds(active.decision_upper_seconds_exact) && seconds(o.publication_seconds_exact) < seconds(active.release_lower_seconds_exact) && source < seconds(active.release_lower_seconds_exact)) : [];
    return { source, active, latest, timely, usableMitt: false };
  }
  const api = { seconds, inScope, validateData, stateAt };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof document === "undefined") return;
  const $ = id => document.getElementById(id);
  const statusText = { candidate: "후보 있음 · 미트 미확정", ambiguous: "후보 모호 · 미트 미확정", no_candidate: "후보 없음 · 기권", error: "실행 오류", not_attempted: "미시도" };
  const time = v => v === null ? "—" : `${seconds(v).toFixed(3)}`;
  const add = (parent, tag, text) => { const el = document.createElement(tag); el.textContent = text; parent.append(el); return el; };
  async function init() {
    const response = await fetch("replay-data.json", { cache: "no-store" });
    if (!response.ok) fail("재생 기록 파일을 읽지 못했습니다.");
    const data = validateData(await response.json()), video = $("video");
    const offset = seconds(data.media.source_offset_seconds_exact), low = seconds(data.scope.start_source_seconds_exact) - offset, high = seconds(data.scope.end_source_seconds_exact) - offset;
    $("scope").textContent = `개발 경기 ${data.scope.game_pk} · ${data.scope.pa}번째 타석의 제한 구간 · 원본 ${time(data.scope.start_source_seconds_exact)}–${time(data.scope.end_source_seconds_exact)}초`;
    for (const [value, label] of [[data.summary.planned_observations,"전체 계획"],[data.summary.interval_observations,"구간 안 입력"],[data.summary.outside_interval_observations,"구간 밖 입력"],[data.summary.verified_mitt,"확정 미트"]]) { const box = add($("summary"), "div", ""); box.className = "stat"; add(box,"strong",String(value)); add(box,"span",label); }
    const seek = source => { video.currentTime = Math.min(high, Math.max(low, source - offset)); render(); };
    for (const r of data.references) { const b = add($("pitch-nav"),"button",`${r.pitch_id.split(":")[2]}구 판단 참조`); b.type = "button"; b.addEventListener("click",() => seek(seconds(r.decision_seconds_exact))); }
    const rows = data.observations.map(o => { const row = add($("rows"),"tr",""); row.dataset.index = o.index; row.dataset.outside = String(!inScope(data,o)); add(row,"td",`#${o.index + 1}${inScope(data,o) ? "" : " · 구간 밖"}`); add(row,"td",`${time(o.frame_seconds_exact)} / ${time(o.cutoff_seconds_exact)}`); add(row,"td",time(o.publication_seconds_exact)); add(row,"td",o.reference_pitch_id || "미배정"); const status = add(row,"td",""); const cell = add(row,"td",""); const jump = add(cell,"button","발행 시점"); jump.type = "button"; const pub = o.publication_seconds_exact === null ? null : seconds(o.publication_seconds_exact); jump.disabled = pub === null || !inScope(data,o) || pub < low + offset || pub >= high + offset; jump.addEventListener("click",() => seek(pub)); return { o,row,status }; });
    function render() {
      const state = stateAt(data, video.currentTime);
      $("clock").textContent = `원본 ${state.source.toFixed(3)}초 · 클립 ${video.currentTime.toFixed(3)}초`;
      $("active").textContent = state.active ? `투구 참조: ${state.active.pitch_id} · 판단 이후 / 릴리스 범위 종료 전` : "현재 시각: 투구 전 참조 범위 밖";
      const last = state.latest;
      $("observation").textContent = last ? `관측 #${last.index + 1} · ${statusText[last.candidate_status]}` : "이 구간에서 아직 발행된 관측이 없습니다.";
      $("details").replaceChildren();
      if (last) {
        if ($("frame").getAttribute("src") !== last.image_path) { $("frame").hidden = true; $("frame").src = last.image_path; }
        for (const [label,value] of [["입력 프레임",`${time(last.frame_seconds_exact)}초`],["발행 시각",`${time(last.publication_seconds_exact)}초`],["참조 투구",last.reference_pitch_id || "미배정"],["현재와의 관계",state.active && last.reference_pitch_id === state.active.pitch_id ? "같은 투구의 과거 입력" : "현재 투구의 유효값 아님"]]) { add($("details"),"dt",label); add($("details"),"dd",value); }
      } else { $("frame").hidden = true; $("frame").removeAttribute("src"); }
      $("ready").textContent = state.timely.length ? "시각 조건을 만족한 저장 관측이 있지만 미트는 미확정입니다." : "현재 투구의 보수적 시각 조건을 만족한 발행 관측 없음 · 확정 미트 없음";
      for (const {o,row,status} of rows) { const visible = o.status === "accepted" && seconds(o.publication_seconds_exact) < high + offset && seconds(o.publication_seconds_exact) <= state.source; status.textContent = visible ? statusText[o.candidate_status] : o.status === "accepted" ? "발행 전" : state.source >= seconds(o.cutoff_seconds_exact) ? `저장 실행: ${statusText[o.status]}` : "계획 · 시각 도달 전"; row.dataset.current = String(last === o); }
      $("toggle").textContent = video.paused ? "재생" : "일시정지";
    }
    video.addEventListener("loadedmetadata",() => { if (video.duration + 0.05 < high) return showError(new Error("영상 길이가 구간보다 짧습니다.")); video.currentTime = low; render(); });
    video.addEventListener("timeupdate",() => { if (video.currentTime >= high) { video.pause(); if (video.currentTime > high) video.currentTime = high; } render(); });
    video.addEventListener("seeking",() => { if (video.currentTime < low) video.currentTime = low; if (video.currentTime > high) video.currentTime = high; render(); });
    video.addEventListener("play",render); video.addEventListener("pause",render);
    video.addEventListener("error",() => showError(new Error("영상을 읽을 수 없습니다. 검증된 팩을 다시 확인하세요.")));
    $("frame").addEventListener("load",() => { const latest = stateAt(data, video.currentTime).latest; $("frame").hidden = !latest || $("frame").getAttribute("src") !== latest.image_path; });
    $("frame").addEventListener("error",() => showError(new Error("입력 프레임을 읽을 수 없습니다.")));
    $("restart").addEventListener("click",() => seek(low + offset));
    $("toggle").addEventListener("click",async () => { if (video.paused) { if (video.currentTime >= high - 0.01) seek(low + offset); try { await video.play(); } catch { showError(new Error("브라우저가 재생을 시작하지 못했습니다.")); } } else video.pause(); });
    video.src = data.media.path; $("app").hidden = false; render();
  }
  function showError(error) { $("video").pause(); $("app").hidden = true; $("error").textContent = error.message; $("error").hidden = false; }
  init().catch(showError);
})();

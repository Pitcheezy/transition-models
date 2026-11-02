"use strict";
(function (scope) {
  function validateRegistry(value) {
    if (!value || value.schema !== "clip-chain-v1" || value.game_pk !== 849843 || !Array.isArray(value.pitches) || value.pitches.length !== 262) throw new Error("849843의 262구 등록부가 필요합니다.");
    const keys = new Set(), paths = new Set(); let available = 0;
    value.pitches.forEach((pitch, index) => {
      const match = /^849843:([1-9]\d*):([1-9]\d*)$/.exec(pitch.pitch_key);
      if (!match || keys.has(pitch.pitch_key) || pitch.game_pitch_number !== index + 1 || pitch.pa_index !== Number(match[1]) || pitch.pitch_number !== Number(match[2])) throw new Error("투구 ID·순서 또는 중복 오류");
      keys.add(pitch.pitch_key);
      if (index && (pitch.pa_index < value.pitches[index - 1].pa_index || (pitch.pa_index === value.pitches[index - 1].pa_index && pitch.pitch_number <= value.pitches[index - 1].pitch_number))) throw new Error("타석·투구 순서 오류");
      if (pitch.status === "available") {
        if (typeof pitch.src !== "string" || !/^clips\/[A-Za-z0-9_-]+\.mp4$/.test(pitch.src) || paths.has(pitch.src)) throw new Error("안전한 고유 클립 경로가 필요합니다.");
        if (!Number.isSafeInteger(pitch.bytes) || pitch.bytes <= 0 || !/^[a-f0-9]{64}$/.test(pitch.sha256) || !Number.isFinite(pitch.duration_s) || pitch.duration_s <= 0) throw new Error("클립 크기·해시·길이 오류");
        paths.add(pitch.src); available += 1;
      } else if (pitch.status !== "excluded" || pitch.src !== null || typeof pitch.reason !== "string" || !pitch.reason.trim()) throw new Error("제외 사유가 필요합니다.");
      for (const key of ["batter", "pitcher"]) if (typeof pitch[key] !== "string") throw new Error("선수 표시 형식 오류");
    });
    if (available !== 261) throw new Error("전시 등록부는 연결 261구·제외 1구여야 합니다.");
    return value;
  }
  function createState(registry, initialKey) {
    validateRegistry(registry);
    let index = 0;
    if (initialKey) { index = registry.pitches.findIndex(p => p.pitch_key === initialKey); if (index < 0) throw new Error("등록되지 않은 투구 ID입니다."); }
    return { index, epoch: 0, chain: false, mode: registry.pitches[index].status === "available" ? "paused" : "unavailable" };
  }
  function select(state, registry, index, chained = false) {
    if (!Number.isInteger(index) || index < 0 || index >= registry.pitches.length) return state;
    const usable = registry.pitches[index].status === "available";
    return { index, epoch: state.epoch + 1, chain: chained && usable, mode: !usable ? "unavailable" : chained ? "pending" : "paused" };
  }
  function transition(state, registry, event) {
    if (event.epoch !== undefined && event.epoch !== state.epoch) return state;
    if (event.type === "select") return select(state, registry, event.index);
    if (event.type === "suspend") return { ...state, epoch: state.epoch + 1, chain: false, mode: state.mode === "unavailable" || state.mode === "error" ? state.mode : "paused" };
    if (event.type === "start") return registry.pitches[state.index].status === "available" && state.mode !== "error" ? (state.mode === "ended" ? select(state, registry, state.index, true) : { ...state, chain: true, mode: state.mode === "playing" ? "playing" : "pending" }) : state;
    if (event.type === "stop" || event.type === "pause" || event.type === "seek") return { ...state, chain: false, mode: state.mode === "unavailable" || state.mode === "error" ? state.mode : "paused" };
    if (event.type === "playing") return registry.pitches[state.index].status === "available" && state.mode !== "error" ? { ...state, mode: "playing" } : state;
    if (event.type === "error") return { ...state, mode: "error", chain: false };
    if (event.type === "ended") {
      if (state.mode !== "playing") return state;
      if (!state.chain || state.index + 1 === registry.pitches.length) return { ...state, chain: false, mode: "ended" };
      return select(state, registry, state.index + 1, true);
    }
    return state;
  }
  // Monitor 1 (Song's app) shows inning/half, batter and the pitch number within the PA; it never shows PA index or game-wide pitch number.
  function half(p) { return p.half === "Top" ? "초" : "말"; }
  function paLabel(p) { return `${p.inning || "?"}회 ${half(p)} · ${p.batter || "타자 미표시"}`; }
  function label(p) { return `${paLabel(p)} · ${p.pitch_number}구`; }
  const api = { validateRegistry, createState, transition, label, paLabel };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else scope.ClipChain = api;
})(typeof globalThis !== "undefined" ? globalThis : this);

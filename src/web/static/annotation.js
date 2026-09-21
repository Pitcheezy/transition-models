"use strict";
(() => {
  const $ = id => document.getElementById(id);
  const {context, pitches} = JSON.parse($("annotation-data").textContent);
  const video = $("video");
  const key = p => `${p.game_pk}/${p.at_bat_number}/${p.pitch_number}`;
  const storageKey = `smartpitch-timing:${context.manifest_sha256}:${context.source.media_url}`;
  let entries = new Map();
  let selected = 0;
  const message = text => { $("message").textContent = text; };
  video.src = context.source.media_url;
  $("source").href = context.source.page_url;
  pitches.forEach((p, i) => $("pitch").add(new Option(`타석 ${p.at_bat_number} · 투구 ${p.pitch_number}`, i)));
  const documentData = () => ({...context, annotator: $("annotator").value.trim(), annotations: [...entries.values()]});
  function validateRow(row) {
    if (!row || ![row.game_pk, row.at_bat_number, row.pitch_number].every(v => Number.isInteger(v) && v > 0)) throw Error("투구 ID는 양의 정수여야 합니다.");
    const p = pitches.find(p => key(p) === key(row));
    if (!p || p.play_id !== row.play_id) throw Error("투구 ID가 일치하지 않습니다.");
    if (Object.keys(row).sort().join() !== ["game_pk", "at_bat_number", "pitch_number", "play_id", "status", "decision_seconds", "release_seconds", "uncertainty_seconds", "note"].sort().join()) throw Error("주석 필드를 확인하세요.");
    if (typeof row.note !== "string" || !row.note.trim()) throw Error("확인 근거를 입력하세요.");
    const {decision_seconds: d, release_seconds: r, uncertainty_seconds: u} = row;
    if (row.status === "unavailable") {
      if ([d, r, u].some(v => v !== null)) throw Error("확인 불가 투구의 시각은 비워야 합니다.");
    } else if (row.status !== "annotated" || ![d, r, u].every(v => typeof v === "number" && Number.isFinite(v)) || u <= 0 || d - u < 0 || d + u >= r - u || r + u > context.source.duration_seconds) {
      throw Error("판단 시각은 오차 범위를 포함해 릴리스보다 앞서야 하며 영상 길이 이내여야 합니다.");
    }
  }
  function validateOrder(rows) {
    const ordered = rows.filter(r => r.status === "annotated").sort((a, b) => a.at_bat_number - b.at_bat_number || a.pitch_number - b.pitch_number);
    ordered.forEach((r, i) => {
      if (i && r.decision_seconds - r.uncertainty_seconds <= ordered[i - 1].release_seconds + ordered[i - 1].uncertainty_seconds) throw Error("이전 투구와 시각이 겹치거나 순서가 뒤바뀌었습니다.");
    });
  }
  function loadDocument(data) {
    if (Object.keys(data).sort().join() !== [...Object.keys(context), "annotator", "annotations"].sort().join() || typeof data.annotator !== "string" || !Array.isArray(data.annotations)) throw Error("주석 문서 형식이 다릅니다.");
    const equal = (a, b) => typeof a === "object" && a !== null && typeof b === "object" && b !== null ? Object.keys(a).length === Object.keys(b).length && Object.keys(a).every(k => equal(a[k], b[k])) : a === b;
    if (!Object.keys(context).every(k => equal(data[k], context[k]))) throw Error("다른 경기·영상·manifest의 주석입니다.");
    const next = new Map();
    data.annotations.forEach(row => { validateRow(row); if (next.has(key(row))) throw Error("중복 투구 ID입니다."); next.set(key(row), row); });
    validateOrder([...next.values()]);
    entries = next;
    $("annotator").value = data.annotator;
  }
  function persist() {
    try { localStorage.setItem(storageKey, JSON.stringify(documentData())); }
    catch { message("브라우저 임시 저장 실패: JSON을 내보내 별도로 보관하세요."); }
  }
  function render() {
    const p = pitches[selected], row = entries.get(key(p)), s = p.pre_state;
    $("pitch").value = String(selected);
    $("reference").textContent = `ID ${key(p)} · playId ${p.play_id}\n기록 대조: ${s.inning}회 ${s.inning_topbot} · ${s.balls}볼 ${s.strikes}스트라이크 · ${s.outs_when_up}아웃 · 투수 ${s.pitcher} · 타자 ${s.batter}\n주자: 1루 ${s.on_1b ?? "없음"}, 2루 ${s.on_2b ?? "없음"}, 3루 ${s.on_3b ?? "없음"} · 점수 ${s.away_score}:${s.home_score}`;
    $("status").value = row?.status ?? "annotated";
    $("decision").value = row?.decision_seconds ?? "";
    $("release").value = row?.release_seconds ?? "";
    $("uncertainty").value = row?.uncertainty_seconds ?? 0.15;
    $("note").value = row?.note ?? "";
    $("previous").disabled = selected === 0;
    $("next").disabled = selected === pitches.length - 1;
    const timed = [...entries.values()].filter(r => r.status === "annotated").length;
    $("progress").textContent = `시각 확인 ${timed} · 확인 불가 ${entries.size - timed} · 미검토 ${pitches.length - entries.size}`;
  }
  function seek(seconds) {
    if (!Number.isFinite(seconds) || !Number.isFinite(video.duration)) return message("영상 로딩을 기다린 후 시각을 입력하세요.");
    $("capture-decision").disabled = true;
    $("capture-release").disabled = true;
    $("clock").textContent = "영상 탐색 중…";
    video.pause(); video.currentTime = Math.min(video.duration, Math.max(0, seconds));
  }
  function updateClock() {
    const busy = video.seeking || video.readyState < 2;
    $("capture-decision").disabled = busy;
    $("capture-release").disabled = busy;
    $("clock").textContent = busy ? "영상 탐색 중…" : `${video.currentTime.toFixed(3)}초`;
  }
  ["timeupdate", "seeking", "seeked", "loadeddata"].forEach(event => video.addEventListener(event, updateClock));
  video.addEventListener("error", () => message("영상 재생 실패: 네트워크와 Chrome 재생을 확인하세요."));
  $("jump").onclick = () => seek($("seek").valueAsNumber);
  $("back").onclick = () => seek(video.currentTime - 0.1);
  $("forward").onclick = () => seek(video.currentTime + 0.1);
  function capture(field) {
    if (video.seeking || video.readyState < 2) return message("탐색이 끝나고 화면이 바뀐 후 기록하세요.");
    video.pause(); $(field).value = video.currentTime.toFixed(3);
  }
  $("capture-decision").onclick = () => capture("decision");
  $("capture-release").onclick = () => capture("release");
  $("pitch").onchange = () => { selected = Number($("pitch").value); render(); message(""); };
  $("previous").onclick = () => { selected--; render(); message(""); };
  $("next").onclick = () => { selected++; render(); message(""); };
  $("save").onclick = () => {
    try {
      if (!$("annotator").value.trim()) throw Error("검토자를 입력하세요.");
      const p = pitches[selected], unavailable = $("status").value === "unavailable";
      const row = {game_pk: p.game_pk, at_bat_number: p.at_bat_number, pitch_number: p.pitch_number, play_id: p.play_id, status: $("status").value,
        decision_seconds: unavailable ? null : $("decision").valueAsNumber, release_seconds: unavailable ? null : $("release").valueAsNumber,
        uncertainty_seconds: unavailable ? null : $("uncertainty").valueAsNumber, note: $("note").value.trim()};
      validateRow(row);
      const next = new Map(entries); next.set(key(p), row); validateOrder([...next.values()]);
      entries = next; message("저장했습니다. JSON 내보내기로 파일을 보관하세요."); persist(); render();
    } catch (error) { message(error.message); }
  };
  $("export").onclick = () => {
    $("json").value = JSON.stringify(documentData(), null, 2);
    const url = URL.createObjectURL(new Blob([$("json").value], {type: "application/json"}));
    const a = document.createElement("a"); a.href = url; a.download = `game_${context.game_pk}_timing.json`; a.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
  };
  $("import").onclick = () => {
    try { loadDocument(JSON.parse($("json").value)); persist(); render(); message("불러왔습니다."); }
    catch (error) { message(error.message); }
  };
  try { const saved = localStorage.getItem(storageKey); if (saved) loadDocument(JSON.parse(saved)); }
  catch (error) { message(`임시 주석을 복원하지 못했습니다: ${error.message}`); }
  render(); updateClock();
})();

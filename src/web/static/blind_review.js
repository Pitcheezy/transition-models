"use strict";

(() => {
  const $ = (id) => document.getElementById(id);
  const clone = (value) => JSON.parse(JSON.stringify(value));
  const initial = JSON.parse($("review-data").textContent);
  let data = clone(initial);
  let selected = 0;
  let formDirty = false;
  let unsavedDownload = false;
  let localUrl = null;
  const video = $("video");
  const fields = [
    ["balls", "볼", "number", 0, 3],
    ["strikes", "스트라이크", "number", 0, 2],
    ["outs", "아웃", "number", 0, 2],
    ["runner_on_1b", "1루 주자", "boolean"],
    ["runner_on_2b", "2루 주자", "boolean"],
    ["runner_on_3b", "3루 주자", "boolean"],
    ["inning", "이닝", "number", 1],
    ["inning_topbot", "초 / 말", "half"],
    ["home_score", "홈팀 점수", "number", 0],
    ["away_score", "원정팀 점수", "number", 0],
  ];
  const key = (row) => [row.game_pk, row.at_bat_number, row.pitch_number].join("/");
  const identity = (row) => `${key(row)} | ${row.play_id}`;
  const fail = (message) => { throw new Error(message); };
  const finite = (n) => typeof n === "number" && Number.isFinite(n);
  const message = (text) => { $("message").textContent = text; };
  const numberOrNull = (input) => input.value.trim() === "" ? null : Number(input.value);
  const originalRoster = new Map(initial.rows.map((row) => [key(row), row.play_id]));
  const rowFields = Object.keys(initial.rows[0]).sort();
  const observedFields = fields.map(([name]) => name).sort();
  const sameKeys = (value, keys) => value && !Array.isArray(value) &&
    typeof value === "object" && JSON.stringify(Object.keys(value).sort()) === JSON.stringify(keys);

  function validateRow(row) {
    if (!sameKeys(row, rowFields) || !sameKeys(row.observed, observedFields)) fail("투구 기록의 필드 구성이 다릅니다.");
    if (![row.game_pk, row.at_bat_number, row.pitch_number].every((v) => Number.isInteger(v) && v > 0)) fail("투구 키는 양의 정수여야 합니다.");
    if (originalRoster.get(key(row)) !== row.play_id) fail("투구 키와 play_id가 원래 묶음과 다릅니다.");
    if (!["unreviewed", "annotated", "unavailable"].includes(row.status)) fail("알 수 없는 검토 상태입니다.");
    if (typeof row.note !== "string") fail("확인 근거는 문자열이어야 합니다.");
    for (const [name, label, kind, min, max] of fields) {
      const value = row.observed[name];
      if (value === null) continue;
      if (kind === "boolean" && typeof value !== "boolean") fail(`${label}: 주자 유무 또는 빈칸을 선택하세요.`);
      if (kind === "half" && !["Top", "Bot"].includes(value)) fail("이닝 초/말 값이 잘못됐습니다.");
      if (kind === "number" && (!Number.isInteger(value) || value < min || (max !== undefined && value > max))) fail(`${label}: ${max === undefined ? `${min} 이상` : `${min}~${max}`}의 정수 또는 빈칸이어야 합니다.`);
    }
    if (row.status !== "annotated") {
      if ([row.decision_seconds, row.release_seconds, row.uncertainty_seconds, row.readability, ...Object.values(row.observed)].some((v) => v !== null)) fail("미검토·판단 불가 행의 시각·판독값은 모두 비워야 합니다. '시각·판독값 비우기'를 사용하세요.");
      if (row.status === "unavailable" && !row.note.trim()) fail("판단 불가 사유를 적어 주세요. 장면을 아직 찾지 못했다면 미검토입니다.");
      return;
    }
    const d = row.decision_seconds, r = row.release_seconds, u = row.uncertainty_seconds;
    if (![d, r, u].every(finite) || d < 0 || u <= 0 || d - u < 0 || d + u >= r - u || r + u > initial.source.duration_seconds) fail("시각·오차 범위를 확인하세요. 양의 오차가 필요하며 판단 구간이 릴리스 구간보다 앞서고 영상 범위 안에 있어야 합니다.");
    if (Math.abs(d * 4 - Math.round(d * 4)) > 1e-7) fail("판단 시각은 직접 확인한 0.25초 격자여야 합니다. 자동 반올림하지 않습니다.");
    const present = Object.values(row.observed).filter((v) => v !== null).length;
    if (row.readability === "readable" ? present !== fields.length : row.readability === "partial" ? present === 0 || present === fields.length : true) fail("전체 판독이면 10필드, 일부 판독이면 1~9필드를 직접 기록하세요.");
    if (!row.note.trim()) fail("판단 경계·연속성·릴리스 확인 근거를 적어 주세요.");
  }

  function validateReviewer(reviewer) {
    if (!sameKeys(reviewer, Object.keys(initial.reviewer).sort())) fail("검토자 필드 구성이 다릅니다.");
    if (typeof reviewer.name !== "string" || ![null, "human", "ai", "mixed"].includes(reviewer.kind)) fail("검토자 이름·방식을 확인하세요.");
    if (![null, true, false].includes(reviewer.prior_reference_exposure)) fail("기존 정답 노출 여부는 true/false/null이어야 합니다.");
    if (reviewer.reviewed_at !== null) {
      const date = reviewer.reviewed_at;
      if (typeof date !== "string" || !/^\d{4}-\d{2}-\d{2}$/.test(date) || Number.isNaN(Date.parse(`${date}T00:00:00Z`)) || new Date(`${date}T00:00:00Z`).toISOString().slice(0, 10) !== date) fail("검토 날짜는 실제 YYYY-MM-DD 날짜여야 합니다.");
    }
  }

  function validateImport(incoming) {
    if (!sameKeys(incoming, Object.keys(initial).sort())) fail("묶음 필드 구성이 다릅니다.");
    for (const name of ["schema", "study_id", "manifest_sha256", "protocol_sha256", "package_id"]) {
      if (incoming[name] !== initial[name]) fail(`${name}: 다른 묶음을 불러올 수 없습니다.`);
    }
    if (!sameKeys(incoming.source, Object.keys(initial.source).sort()) || Object.keys(initial.source).some((name) => incoming.source[name] !== initial.source[name])) fail("영상 출처 또는 길이가 원래 묶음과 다릅니다.");
    if (!Array.isArray(incoming.rows) || incoming.rows.length !== initial.rows.length) fail("투구 수가 원래 묶음과 다릅니다.");
    const seen = new Set();
    for (const row of incoming.rows) {
      validateRow(row);
      if (seen.has(key(row))) fail("중복 투구 키가 있습니다.");
      seen.add(key(row));
    }
    validateReviewer(incoming.reviewer);
    if (incoming.rows.some((row) => row.status !== "unreviewed") && (!incoming.reviewer.name.trim() || incoming.reviewer.kind === null || incoming.reviewer.reviewed_at === null || incoming.reviewer.prior_reference_exposure === null)) fail("확인·판단 불가 기록을 저장하려면 검토자 이름·방식·날짜·기존 정답 노출 여부를 모두 입력하세요. 미검토만 있는 초안은 비워 둘 수 있습니다.");
    const ordered = incoming.rows.filter((row) => row.status === "annotated").sort((a, b) => a.game_pk - b.game_pk || a.at_bat_number - b.at_bat_number || a.pitch_number - b.pitch_number);
    for (let i = 1; i < ordered.length; i++) {
      const previous = ordered[i - 1], current = ordered[i];
      if (current.decision_seconds - current.uncertainty_seconds <= previous.release_seconds + previous.uncertainty_seconds) fail(`투구 ${key(previous)}와 ${key(current)}의 오차 구간이 겹치거나 시간 순서가 뒤집혔습니다. 투구 식별과 시각을 확인하세요.`);
    }
  }

  for (const [name, labelText, kind, min, max] of fields) {
    const label = document.createElement("label");
    label.append(document.createTextNode(labelText));
    const input = document.createElement(kind === "number" ? "input" : "select");
    input.id = `field-${name}`;
    if (kind === "number") { input.type = "number"; input.min = min; if (max !== undefined) input.max = max; input.step = "1"; }
    else {
      const options = kind === "boolean" ? [["", "판독 불가"], ["true", "주자 있음"], ["false", "주자 없음"]] : [["", "판독 불가"], ["Top", "초"], ["Bot", "말"]];
      for (const [value, text] of options) input.add(new Option(text, value));
    }
    label.append(input);
    $("observed-fields").append(label);
    input.addEventListener("input", () => { formDirty = true; });
  }

  function setForm(row) {
    $("identity").textContent = `투구 ${key(row)} · play_id ${row.play_id}`;
    for (const [id, name] of [["status", "status"], ["decision", "decision_seconds"], ["release", "release_seconds"], ["uncertainty", "uncertainty_seconds"], ["readability", "readability"], ["note", "note"]]) $(id).value = row[name] ?? "";
    for (const [name] of fields) $(`field-${name}`).value = row.observed[name] ?? "";
    $("pitch").value = String(selected);
    $("previous").disabled = selected === 0;
    $("next").disabled = selected === data.rows.length - 1;
    formDirty = false;
  }

  function renderMetadata() {
    $("reviewer-name").value = data.reviewer.name;
    $("reviewer-kind").value = data.reviewer.kind ?? "";
    $("reviewer-date").value = data.reviewer.reviewed_at ?? "";
    $("reviewer-exposure").value = data.reviewer.prior_reference_exposure ?? "";
  }

  function readMetadata() {
    return {name: $("reviewer-name").value.trim(), kind: $("reviewer-kind").value || null, reviewed_at: $("reviewer-date").value || null, prior_reference_exposure: $("reviewer-exposure").value === "" ? null : $("reviewer-exposure").value === "true"};
  }

  function refreshProgress() {
    const counts = {unreviewed: 0, annotated: 0, unavailable: 0};
    for (const row of data.rows) counts[row.status]++;
    $("progress").textContent = `이 검토자의 기록: 확인 ${counts.annotated} / 판단 불가 ${counts.unavailable} / 미검토 ${counts.unreviewed}`;
    [...$("pitch").options].forEach((option, i) => { const row = data.rows[i]; option.textContent = `${i + 1}. PA ${row.at_bat_number} / ${row.pitch_number}구 · ${{unreviewed: "미검토", annotated: "확인", unavailable: "판단 불가"}[row.status]}`; });
  }

  function saveForm() {
    const row = clone(data.rows[selected]);
    row.status = $("status").value;
    row.decision_seconds = numberOrNull($("decision"));
    row.release_seconds = numberOrNull($("release"));
    row.uncertainty_seconds = numberOrNull($("uncertainty"));
    row.readability = $("readability").value || null;
    row.note = $("note").value.trim();
    for (const [name, , kind] of fields) {
      const value = $(`field-${name}`).value;
      row.observed[name] = value === "" ? null : kind === "number" ? Number(value) : kind === "boolean" ? value === "true" : value;
    }
    validateRow(row);
    const reviewer = readMetadata();
    validateReviewer(reviewer);
    const updated = {...data, reviewer, rows: data.rows.map((existing, index) => index === selected ? row : existing)};
    validateImport(updated);
    data = updated;
    formDirty = false;
    unsavedDownload = true;
    refreshProgress();
    message("이 투구를 메모리에 저장했습니다. 파일 보관은 JSON 내보내기를 사용하세요.");
  }

  function selectRow(index) {
    if (index < 0 || index >= data.rows.length) return;
    if (formDirty && !window.confirm("저장하지 않은 현재 투구 입력을 버리고 이동할까요? 보존하려면 취소 후 이 투구 저장을 누르세요.")) { $("pitch").value = String(selected); return; }
    selected = index;
    setForm(data.rows[selected]);
    message("투구를 선택했습니다. 영상은 직접 탐색하세요.");
  }

  function seek(seconds) {
    if (!finite(seconds) || seconds < 0 || seconds > initial.source.duration_seconds) fail("영상 범위 안의 재생 초를 입력하세요.");
    video.pause();
    video.currentTime = seconds;
  }

  function safely(action) { try { action(); } catch (error) { message(error.message); } }
  $("source").href = initial.source.page_url;
  $("package").textContent = `묶음 ${initial.package_id} · 원본 길이 ${initial.source.duration_seconds.toFixed(3)}초`;
  video.src = initial.source.media_url;
  data.rows.forEach((row, i) => $("pitch").add(new Option(identity(row), String(i))));
  renderMetadata(); setForm(data.rows[0]); refreshProgress();
  $("pitch").addEventListener("change", () => selectRow(Number($("pitch").value)));
  $("previous").addEventListener("click", () => selectRow(selected - 1));
  $("next").addEventListener("click", () => selectRow(selected + 1));
  for (const id of ["status", "decision", "release", "uncertainty", "readability", "note"]) $(id).addEventListener("input", () => { formDirty = true; });
  for (const id of ["reviewer-name", "reviewer-kind", "reviewer-date", "reviewer-exposure"]) $(id).addEventListener("input", () => { unsavedDownload = true; });
  $("jump").addEventListener("click", () => safely(() => { if ($("seek").value.trim() === "") fail("이동할 재생 초를 입력하세요."); seek(Number($("seek").value)); }));
  document.querySelectorAll("[data-step]").forEach((button) => button.addEventListener("click", () => safely(() => seek(Math.round((video.currentTime + Number(button.dataset.step)) * 1000) / 1000))));
  for (const target of ["decision", "release"]) $(`capture-${target}`).addEventListener("click", () => safely(() => {
    if (video.readyState < 2 || video.seeking) fail("영상 탐색이 끝나고 화면이 표시된 다음 캡처하세요.");
    $(target).value = video.currentTime.toFixed(3); formDirty = true;
    message("현재 재생 시각을 복사했습니다. 화면·격자·오차는 직접 확인하세요.");
  }));
  $("clear-values").addEventListener("click", () => {
    if (!window.confirm("현재 투구 입력의 시각·판독값을 비울까요? 상태와 메모는 유지합니다.")) return;
    for (const id of ["decision", "release", "uncertainty", "readability"]) $(id).value = "";
    for (const [name] of fields) $(`field-${name}`).value = "";
    formDirty = true; message("시각·판독값 입력을 비웠습니다. 상태와 메모를 확인한 뒤 저장하세요.");
  });
  $("save").addEventListener("click", () => safely(saveForm));
  $("export").addEventListener("click", () => safely(() => {
    saveForm(); validateImport(data);
    const url = URL.createObjectURL(new Blob([JSON.stringify(data, null, 2) + "\n"], {type: "application/json"}));
    const link = document.createElement("a"); link.href = url; link.download = `${initial.study_id}_review.json`; link.click();
    setTimeout(() => URL.revokeObjectURL(url), 1000);
    unsavedDownload = false;
    message("JSON 다운로드를 요청했습니다. 파일이 저장됐는지 확인하세요. 미검토 행·미입력 검토자 정보는 최종 제출 전에 완료해야 합니다.");
  }));
  $("import").addEventListener("click", async () => {
    try {
      const file = $("import-file").files[0];
      if (!file) fail("불러올 JSON 파일을 선택하세요.");
      const incoming = JSON.parse(await file.text()); validateImport(incoming);
      if (!window.confirm("검증된 JSON으로 현재 메모리의 기록 전체를 바꿀까요? 저장하지 않은 입력은 사라집니다.")) return;
      const byKey = new Map(incoming.rows.map((row) => [key(row), row]));
      incoming.rows = initial.rows.map((row) => byKey.get(key(row)));
      data = clone(incoming); selected = 0; renderMetadata(); setForm(data.rows[0]); refreshProgress(); unsavedDownload = false;
      message("같은 묶음의 JSON을 불러왔습니다. 파일의 기록만 반영했으며 기존 정답은 불러오지 않았습니다.");
    } catch (error) { message(`불러오지 않았습니다: ${error.message}`); }
  });
  video.addEventListener("timeupdate", () => { $("clock").textContent = `${video.currentTime.toFixed(3)}초`; });
  video.addEventListener("seeking", () => { $("video-status").textContent = "영상 탐색 중… 화면이 갱신될 때까지 기다리세요."; });
  video.addEventListener("seeked", () => { $("clock").textContent = `${video.currentTime.toFixed(3)}초`; $("video-status").textContent = "탐색 완료. 브라우저 재생 위치는 프레임 단위 정답이 아닙니다."; });
  video.addEventListener("loadedmetadata", () => {
    const differs = !finite(video.duration) || Math.abs(video.duration - initial.source.duration_seconds) > 0.5;
    $("video-status").textContent = differs ? "주의: 영상 길이가 등록된 출처와 다릅니다. 같은 편집본인지 확인할 때까지 기록하지 마세요." : "영상 정보를 읽었습니다. 출처와 같은 편집본인지 확인하고 직접 탐색하세요.";
  });
  video.addEventListener("error", () => { $("video-status").textContent = "영상을 열지 못했습니다. 같은 편집본의 로컬 파일을 사용할 수 있습니다. 추출·재생 실패는 판단 불가가 아니므로 미검토로 남기세요."; });
  $("local-video").addEventListener("change", () => {
    const file = $("local-video").files[0]; if (!file) return;
    if (localUrl) URL.revokeObjectURL(localUrl);
    localUrl = URL.createObjectURL(file); video.src = localUrl; video.load();
  });
  $("remote-video").addEventListener("click", () => {
    video.src = initial.source.media_url; video.load(); $("local-video").value = "";
    if (localUrl) { URL.revokeObjectURL(localUrl); localUrl = null; }
  });
  window.addEventListener("beforeunload", (event) => { if (formDirty || unsavedDownload) { event.preventDefault(); event.returnValue = ""; } });
})();

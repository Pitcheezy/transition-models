/* Offline pre-pitch sequence review. No inference, networking, localStorage or automatic saving. */
(function () {
  "use strict";
  const RESPONSE = "pitcheezy-mitt-sequence-review-response-dev-v1";
  const DRAFT = "pitcheezy-mitt-sequence-review-draft-dev-v1";
  const PRESENTATION = ["unreviewed", "held_seen", "no_clear_hold", "not_determinable"];
  const VISIBILITY = ["full", "partial", "hidden", "unknown"];
  const ROW_KEYS = ["sequence_id", "delivery_start_n", "delivery_note", "presentation", "hold_start_n",
    "hold_end_n", "point_n", "mitt", "visibility", "reason"];
  const clone = value => JSON.parse(JSON.stringify(value));
  const fail = message => { throw new Error(message); };
  const exact = (value, keys) => value && typeof value === "object" && !Array.isArray(value)
    && Object.keys(value).sort().join("|") === keys.slice().sort().join("|");
  const finite = value => typeof value === "number" && Number.isFinite(value);

  function validate(manifest, hash, response, {draft = false} = {}) {
    if (!exact(response, ["schema", "manifest_sha256", "reviewer_id", "rows"])) fail("응답 문서 필드가 다릅니다.");
    if (response.schema !== RESPONSE || response.manifest_sha256 !== hash || !/^[a-f0-9]{64}$/.test(hash))
      fail("응답 버전 또는 manifest SHA256이 다릅니다.");
    if (typeof response.reviewer_id !== "string") fail("검토자 ID는 문자열이어야 합니다.");
    const sequences = new Map(manifest.sequences.map(s => [s.sequence_id, s]));
    if (!Array.isArray(response.rows) || response.rows.length !== sequences.size) fail("행 수가 다릅니다.");
    const seen = new Set();
    for (const row of response.rows) {
      if (!exact(row, ROW_KEYS)) fail("응답 행 필드가 다릅니다.");
      const seq = sequences.get(row.sequence_id);
      if (!seq || seen.has(row.sequence_id)) fail("투구 ID 중복/누락입니다.");
      seen.add(row.sequence_id);
      const n = seq.frames.length, id = row.sequence_id;
      const frameNo = (value, name) => {
        if (value === null) return null;
        if (!Number.isInteger(value) || value < 1 || value > n) fail(`${id}: ${name}가 1..${n} 밖입니다.`);
        return value;
      };
      const start = frameNo(row.hold_start_n, "구간 시작"), end = frameNo(row.hold_end_n, "구간 끝");
      const point = frameNo(row.point_n, "중심 프레임");
      frameNo(row.delivery_start_n, "투구 동작 시작");
      if (!PRESENTATION.includes(row.presentation) || !VISIBILITY.includes(row.visibility)
        || typeof row.reason !== "string" || typeof row.delivery_note !== "string") fail("잘못된 판정 값입니다.");
      if (row.presentation === "held_seen") {
        if (!draft) {
          if (start === null || end === null || start > end) fail(`${id}: 멈춘 구간의 시작과 끝을 지정하세요.`);
          if (point === null || point < start || point > end) fail(`${id}: 중심은 멈춘 구간 안의 프레임에서 표시하세요.`);
          if (!["full", "partial"].includes(row.visibility)) fail(`${id}: 중심에는 full/partial 가시성이 필요합니다.`);
          if (row.visibility === "partial" && !row.reason.trim()) fail(`${id}: 일부 가림의 이유를 적으세요.`);
        }
        if (row.mitt !== null || !draft) {
          const frame = seq.frames[(point || 1) - 1];
          if (!Array.isArray(row.mitt) || row.mitt.length !== 2 || !row.mitt.every(finite)
            || row.mitt[0] < 0 || row.mitt[1] < 0 || row.mitt[0] >= frame.width || row.mitt[1] >= frame.height)
            fail(`${id}: 미트 중심이 프레임 밖이거나 없습니다.`);
        }
      } else {
        if ([start, end, point, row.mitt].some(v => v !== null)) fail(`${id}: 구간·중심은 멈춘 구간 보임에서만 씁니다.`);
        if (!draft && row.presentation !== "unreviewed" && !row.reason.trim()) fail(`${id}: 이유를 적으세요.`);
      }
      if (!draft && row.presentation !== "unreviewed" && row.delivery_start_n === null && !row.delivery_note.trim())
        fail(`${id}: 투구 동작 시작 프레임을 지정하거나 못 정한 이유를 적으세요.`);
    }
    if (!draft && response.rows.some(r => r.presentation !== "unreviewed") && !response.reviewer_id.trim())
      fail("검토자 ID를 입력하세요.");
    return clone(response);
  }

  function setPresentation(row, value) {
    if (!PRESENTATION.includes(value)) fail("잘못된 상태입니다.");
    const next = clone(row);
    next.presentation = value;
    if (value !== "held_seen") Object.assign(next, {hold_start_n: null, hold_end_n: null, point_n: null, mitt: null});
    if (value === "unreviewed") Object.assign(next, {visibility: "unknown", reason: ""});
    return next;
  }

  function markHold(row, which, n) {
    const next = clone(row);
    if (next.presentation !== "held_seen") next.presentation = "held_seen";
    next[which === "start" ? "hold_start_n" : "hold_end_n"] = n;
    // a new bound on the wrong side of the other one clears the other bound
    if (next.hold_start_n !== null && next.hold_end_n !== null && next.hold_start_n > next.hold_end_n)
      next[which === "start" ? "hold_end_n" : "hold_start_n"] = null;
    if (next.point_n !== null && ((next.hold_start_n !== null && next.point_n < next.hold_start_n)
      || (next.hold_end_n !== null && next.point_n > next.hold_end_n))) { next.point_n = null; next.mitt = null; }
    return next;
  }

  function markPoint(row, n, point) {
    const next = clone(row);
    if (next.presentation !== "held_seen") next.presentation = "held_seen";
    next.point_n = n; next.mitt = point;
    return next;
  }

  function imagePoint(clientX, clientY, rect, frame) {
    if (![clientX, clientY, rect.left, rect.top, rect.width, rect.height, frame.width, frame.height].every(finite)
      || rect.width <= 0 || rect.height <= 0) fail("이미지 좌표 변환 정보가 잘못되었습니다.");
    const x = (clientX - rect.left) * frame.width / rect.width;
    const y = (clientY - rect.top) * frame.height / rect.height;
    if (x < 0 || y < 0 || x >= frame.width || y >= frame.height) fail("이미지 밖 클릭입니다.");
    return [x, y];
  }

  function exportResponse(response, manifest, hash) {
    return JSON.stringify(validate(manifest, hash, response), null, 2) + "\n";
  }
  function exportDraft(response, manifest, hash, current) {
    const doc = {schema: DRAFT, response: validate(manifest, hash, response, {draft: true}), current};
    return JSON.stringify(doc, null, 2) + "\n";
  }
  function parseImport(text, manifest, hash) {
    const doc = JSON.parse(text);
    if (doc && doc.schema === DRAFT) {
      if (!exact(doc, ["schema", "response", "current"]) || !exact(doc.current, ["sequence_id", "n"]))
        fail("초안 문서 필드가 다릅니다.");
      const response = validate(manifest, hash, doc.response, {draft: true});
      const seq = manifest.sequences.find(s => s.sequence_id === doc.current.sequence_id);
      if (!seq || !Number.isInteger(doc.current.n) || doc.current.n < 1 || doc.current.n > seq.frames.length)
        fail("초안의 현재 위치가 이 검토 팩에 없습니다.");
      return {response, current: doc.current};
    }
    return {response: validate(manifest, hash, doc), current: null};
  }

  function init() {
    const $ = id => document.getElementById(id);
    const say = text => { $("message").textContent = text; };
    try {
      const initial = JSON.parse($("review-data").textContent);
      const manifest = initial.manifest, hash = initial.response.manifest_sha256;
      let state = validate(manifest, hash, initial.response, {draft: true});
      let seqPos = 0, n = 1, dirty = false, timer = null;
      const seq = () => manifest.sequences[seqPos];
      const row = () => state.rows.find(r => r.sequence_id === seq().sequence_id);
      const replace = next => { Object.assign(row(), next); dirty = true; render(); };
      function render() {
        const s = seq(), r = row(), f = s.frames[n - 1];
        $("reviewer").value = state.reviewer_id;
        $("seq-label").textContent = ` 투구 ${seqPos + 1} / ${manifest.sequences.length} (${s.sequence_id}) `;
        $("frame-label").textContent = ` 프레임 ${n} / ${s.frames.length} · 시작 후 ${f.seconds_from_start.toFixed(2)}초`;
        $("frame").src = f.path;
        $("presentation").value = r.presentation; $("visibility").value = r.visibility;
        $("reason").value = r.reason; $("delivery-note").value = r.delivery_note;
        const showPoint = r.point_n === n && r.mitt;
        $("marker").hidden = !showPoint;
        if (showPoint) {
          $("marker").style.left = `${100 * r.mitt[0] / f.width}%`;
          $("marker").style.top = `${100 * r.mitt[1] / f.height}%`;
        }
        $("coordinates").textContent = r.mitt ? `중심: 프레임 ${r.point_n}, x=${r.mitt[0].toFixed(1)}, y=${r.mitt[1].toFixed(1)}`
          : "미트 좌표 없음";
        $("marks").textContent = `투구 동작 시작 ${r.delivery_start_n ?? "-"} · 구간 ${r.hold_start_n ?? "-"}–${r.hold_end_n ?? "-"}`;
        const strip = $("strip");
        strip.textContent = "";
        for (let k = 1; k <= s.frames.length; k++) {
          const cell = document.createElement("span");
          if (r.hold_start_n !== null && r.hold_end_n !== null && k >= r.hold_start_n && k <= r.hold_end_n) cell.className = "hold";
          if (k === r.delivery_start_n) cell.className = "del";
          if (k === n) cell.className = "cur";
          strip.appendChild(cell);
        }
        $("prev").disabled = n === 1; $("next").disabled = n === s.frames.length;
        $("seq-prev").disabled = seqPos === 0; $("seq-next").disabled = seqPos === manifest.sequences.length - 1;
      }
      const stop = () => { if (timer) { clearInterval(timer); timer = null; $("play").textContent = "재생"; } };
      const step = d => { const len = seq().frames.length; n = Math.min(len, Math.max(1, n + d)); render(); };
      const toSeq = d => { stop(); seqPos = Math.min(manifest.sequences.length - 1, Math.max(0, seqPos + d)); n = 1; say(""); render(); };
      $("prev").onclick = () => { stop(); step(-1); };
      $("next").onclick = () => { stop(); step(1); };
      $("seq-prev").onclick = () => toSeq(-1);
      $("seq-next").onclick = () => toSeq(1);
      $("play").onclick = () => {
        if (timer) return stop();
        $("play").textContent = "정지";
        timer = setInterval(() => { if (n >= seq().frames.length) stop(); else step(1); }, 100);
      };
      $("mark-delivery").onclick = () => replace({delivery_start_n: n});
      $("clear-delivery").onclick = () => replace({delivery_start_n: null});
      $("mark-start").onclick = () => replace(markHold(row(), "start", n));
      $("mark-end").onclick = () => replace(markHold(row(), "end", n));
      $("presentation").onchange = () => replace(setPresentation(row(), $("presentation").value));
      $("visibility").onchange = () => replace({visibility: $("visibility").value});
      $("reason").oninput = () => { row().reason = $("reason").value; dirty = true; };
      $("delivery-note").oninput = () => { row().delivery_note = $("delivery-note").value; dirty = true; };
      $("reviewer").oninput = () => { state.reviewer_id = $("reviewer").value; dirty = true; };
      $("frame").onclick = event => {
        try {
          const image = $("frame"), f = seq().frames[n - 1];
          if (!image.complete || image.naturalWidth !== f.width || image.naturalHeight !== f.height)
            fail("이미지가 로드되지 않았거나 원본 크기와 다릅니다.");
          const r = row();
          if (r.hold_start_n !== null && r.hold_end_n !== null && (n < r.hold_start_n || n > r.hold_end_n))
            fail("중심은 멈춘 구간 안의 프레임에서 표시하세요.");
          replace(markPoint(r, n, imagePoint(event.clientX, event.clientY, image.getBoundingClientRect(), f)));
          say(["full", "partial"].includes(row().visibility) ? "중심을 기록했습니다." : "가시성 full 또는 partial을 직접 선택하세요.");
        } catch (error) { say(error.message); }
      };
      document.addEventListener("keydown", event => {
        if (["INPUT", "TEXTAREA", "SELECT"].includes(event.target.tagName)) return;
        if (event.ctrlKey || event.metaKey || event.altKey) return;
        const key = event.key.toLowerCase();
        if (key === "arrowleft") { stop(); step(-1); } else if (key === "arrowright") { stop(); step(1); }
        else if (key === " ") { event.preventDefault(); $("play").click(); }
        else if (key === "d") $("mark-delivery").click();
        else if (key === "s") $("mark-start").click();
        else if (key === "e") $("mark-end").click();
      });
      function download(text, filename, note) {
        const url = URL.createObjectURL(new Blob([text], {type: "application/json"}));
        const link = document.createElement("a");
        link.href = url; link.download = filename;
        document.body.appendChild(link); link.click(); link.remove();
        setTimeout(() => URL.revokeObjectURL(url), 1000);
        say(`${note} 다운로드를 요청했습니다. 파일 저장을 확인한 뒤 닫으세요. 저장을 취소했다면 다시 저장하세요.`);
      }
      $("export").onclick = () => {
        try { download(exportResponse(state, manifest, hash), "sequence_review_response.json", "제출용 응답"); }
        catch (error) { say(error.message); }
      };
      $("draft-export").onclick = () => {
        try {
          download(exportDraft(state, manifest, hash, {sequence_id: seq().sequence_id, n}),
            "sequence_review_draft.json", "작업 초안(제출용 아님)");
        } catch (error) { say(error.message); }
      };
      $("import").onchange = async () => {
        const file = $("import").files[0];
        if (!file) return;
        try {
          const imported = parseImport(await file.text(), manifest, hash);
          if (dirty && !window.confirm("현재 입력을 불러온 내용으로 바꿀까요? 내보내지 않은 입력은 사라집니다.")) return;
          state = imported.response;
          if (imported.current) {
            seqPos = manifest.sequences.findIndex(s => s.sequence_id === imported.current.sequence_id);
            n = imported.current.n;
          }
          dirty = false; render();
          say(imported.current ? "작업 초안을 불러왔습니다. 이어서 입력한 뒤 제출용 응답을 내보내세요." : "검증한 응답을 불러왔습니다.");
        } catch (error) { say(`불러오기 거부 — 현재 입력을 유지했습니다: ${error.message}`); }
        finally { $("import").value = ""; }
      };
      $("frame").onerror = () => say("이미지를 불러올 수 없습니다. 팩의 frames 폴더를 확인하세요.");
      window.addEventListener("beforeunload", event => { if (dirty) { event.preventDefault(); event.returnValue = ""; } });
      render();
    } catch (error) { say(`초기화 실패: ${error.message}`); }
  }

  const api = {validate, setPresentation, markHold, markPoint, imagePoint, exportResponse, exportDraft, parseImport};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof document !== "undefined") init();
})();

/* Offline human review. No inference, networking, localStorage or automatic saving. */
(function () {
  "use strict";
  const statuses = ["unreviewed", "marked", "unavailable", "unknown"];
  const visibilities = ["full", "partial", "hidden", "unknown"];
  const poses = ["presented_target", "resting", "moving", "unknown"];
  const clone = value => JSON.parse(JSON.stringify(value));
  const fail = message => { throw new Error(message); };
  const exact = (value, keys) => value && typeof value === "object" && !Array.isArray(value)
    && Object.keys(value).sort().join("|") === keys.slice().sort().join("|");
  const finite = value => typeof value === "number" && Number.isFinite(value);

  function validateResponse(manifest, expectedHash, response, exporting = false) {
    if (!exact(response, ["schema", "protocol_version", "manifest_sha256", "reviewer_id", "rows"]))
      fail("응답 문서 필드가 다릅니다.");
    if (manifest.schema !== "intent_source_review_pack_v1"
      || manifest.protocol_version !== "cv_observation_v1"
      || response.schema !== "intent_source_review_response_v1"
      || response.protocol_version !== manifest.protocol_version
      || !/^[a-f0-9]{64}$/.test(expectedHash) || response.manifest_sha256 !== expectedHash)
      fail("응답 버전 또는 manifest SHA256이 다릅니다.");
    if (typeof response.reviewer_id !== "string" || !Array.isArray(response.rows)
      || !Array.isArray(manifest.frames) || response.rows.length !== manifest.frames.length)
      fail("검토자 ID 또는 행 수가 잘못되었습니다.");
    const frames = new Map(), frameNumbers = new Map();
    for (const [index, frame] of manifest.frames.entries()) {
      if (typeof frame.observation_id !== "string" || frames.has(frame.observation_id)
        || !Number.isInteger(frame.width) || frame.width <= 0
        || !Number.isInteger(frame.height) || frame.height <= 0
        || !/^[a-f0-9]{64}$/.test(frame.image_sha256)
        || !/^images\/[A-Za-z0-9_-]+\.(jpg|jpeg|png)$/.test(frame.path))
        fail("프레임 식별자, 이미지 경로 또는 크기가 잘못되었습니다.");
      frames.set(frame.observation_id, frame);
      frameNumbers.set(frame.observation_id, index + 1);
    }
    const seen = new Set();
    for (const row of response.rows) {
      if (!exact(row, ["observation_id", "image_sha256", "status", "mitt", "visibility", "pose", "reason"]))
        fail("응답 행 필드가 다릅니다.");
      const frame = frames.get(row.observation_id);
      if (!frame || seen.has(row.observation_id) || row.image_sha256 !== frame.image_sha256)
        fail("관측 ID 중복/누락 또는 이미지 SHA256 불일치입니다.");
      seen.add(row.observation_id);
      const label = `프레임 ${frameNumbers.get(row.observation_id)} (${row.observation_id})`;
      if (!statuses.includes(row.status) || !visibilities.includes(row.visibility)
        || !poses.includes(row.pose) || typeof row.reason !== "string") fail("잘못된 판정 값입니다.");
      if (row.status === "marked") {
        if (!Array.isArray(row.mitt) || row.mitt.length !== 2 || !row.mitt.every(finite)
          || row.mitt[0] < 0 || row.mitt[0] >= frame.width || row.mitt[1] < 0
          || row.mitt[1] >= frame.height || !["full", "partial"].includes(row.visibility))
          fail(`${label}: marked에는 이미지 안의 점과 full/partial 가시성이 필요합니다.`);
        if (row.visibility === "partial" && !row.reason.trim())
          fail(`${label}: 부분 가림(partial)을 표시한 이유를 입력하세요.`);
      } else if (row.mitt !== null) fail("marked 이외 상태는 mitt가 null이어야 합니다.");
      if (["unavailable", "unknown"].includes(row.status) && !row.reason.trim())
        fail(`${label}: 판정 이유가 필요합니다.`);
    }
    if ((exporting || response.rows.some(row => row.status !== "unreviewed"))
      && !response.reviewer_id.trim()) fail("검토자 ID를 입력하세요.");
    return clone(response);
  }

  function imagePoint(clientX, clientY, rect, frame) {
    if (![clientX, clientY, rect.left, rect.top, rect.width, rect.height,
      frame.width, frame.height].every(finite) || rect.width <= 0 || rect.height <= 0
      || frame.width <= 0 || frame.height <= 0) fail("이미지 좌표 변환 정보가 잘못되었습니다.");
    const x = (clientX - rect.left) * frame.width / rect.width;
    const y = (clientY - rect.top) * frame.height / rect.height;
    if (x < 0 || y < 0 || x >= frame.width || y >= frame.height) fail("이미지 밖 클릭입니다.");
    return [x, y];
  }

  function setStatus(row, status) {
    if (!statuses.includes(status)) fail("잘못된 상태입니다.");
    const next = clone(row);
    next.status = status;
    if (status !== "marked") next.mitt = null;
    if (status === "unreviewed") Object.assign(next, {visibility: "unknown", pose: "unknown", reason: ""});
    return next;
  }

  function parseResponse(text, manifest, expectedHash) {
    return validateResponse(manifest, expectedHash, JSON.parse(text));
  }
  function exportResponse(response, manifest, expectedHash) {
    return JSON.stringify(validateResponse(manifest, expectedHash, response, true), null, 2) + "\n";
  }

  function init() {
    const $ = id => document.getElementById(id);
    const message = text => { $("message").textContent = text; };
    try {
      const initial = JSON.parse($("review-data").textContent);
      const manifest = initial.manifest, hash = initial.response.manifest_sha256;
      let state = validateResponse(manifest, hash, initial.response), position = 0, dirty = false;
      if (!manifest.frames.length) fail("검토할 프레임이 없습니다.");
      const frame = () => manifest.frames[position];
      const row = () => state.rows.find(item => item.observation_id === frame().observation_id);
      function render() {
        const current = row(), item = frame();
        $("reviewer").value = state.reviewer_id;
        $("index").value = position + 1;
        $("total").textContent = `/ ${manifest.frames.length}`;
        $("prev").disabled = position === 0;
        $("next").disabled = position === manifest.frames.length - 1;
        $("caption").textContent = `${item.observation_id} · 원본 ${item.width} × ${item.height}px`;
        $("frame").src = item.path;
        $("frame").alt = item.observation_id;
        for (const key of ["status", "visibility", "pose", "reason"]) $(key).value = current[key];
        const point = current.mitt;
        $("marker").hidden = !point;
        if (point) {
          $("marker").style.left = `${100 * point[0] / item.width}%`;
          $("marker").style.top = `${100 * point[1] / item.height}%`;
        }
        $("coordinates").textContent = point ? `원본 픽셀 x=${point[0].toFixed(2)}, y=${point[1].toFixed(2)}`
          : "미트 좌표 없음";
      }
      function move(next) {
        if (!Number.isInteger(next) || next < 0 || next >= manifest.frames.length) {
          message("유효한 프레임 번호를 입력하세요."); render(); return;
        }
        position = next; message(""); render();
      }
      $("prev").onclick = () => move(position - 1);
      $("next").onclick = () => move(position + 1);
      $("index").max = manifest.frames.length;
      $("index").onchange = () => move(Number($("index").value) - 1);
      $("reviewer").oninput = () => { state.reviewer_id = $("reviewer").value; dirty = true; };
      for (const key of ["visibility", "pose", "reason"]) {
        $(key).oninput = () => { row()[key] = $(key).value; dirty = true; };
      }
      $("status").onchange = () => { Object.assign(row(), setStatus(row(), $("status").value)); dirty = true; render(); };
      $("frame").onclick = event => {
        try {
          const image = $("frame"), item = frame();
          if (!image.complete || image.naturalWidth !== item.width || image.naturalHeight !== item.height)
            fail("이미지가 로드되지 않았거나 원본 크기와 다릅니다.");
          row().mitt = imagePoint(event.clientX, event.clientY, image.getBoundingClientRect(), item);
          row().status = "marked"; dirty = true; render();
          message(["full", "partial"].includes(row().visibility) ? "좌표를 기록했습니다." : "가시성 full 또는 partial을 직접 선택하세요.");
        } catch (error) { message(error.message); }
      };
      $("frame").onerror = () => message("이미지를 불러올 수 없습니다. 패키지의 images 폴더를 확인하세요.");
      $("export").onclick = () => {
        try {
          const text = exportResponse(state, manifest, hash);
          const url = URL.createObjectURL(new Blob([text], {type: "application/json"}));
          const link = document.createElement("a");
          link.href = url; link.download = "human_review_response.json";
          document.body.appendChild(link); link.click(); link.remove();
          setTimeout(() => URL.revokeObjectURL(url), 1000);
          message("다운로드를 요청했습니다. 파일 저장을 확인한 뒤 닫으세요. 자동 저장은 없습니다.");
        } catch (error) { message(error.message); }
      };
      $("import").onchange = async () => {
        const file = $("import").files[0];
        if (!file) return;
        try {
          const imported = parseResponse(await file.text(), manifest, hash);
          if (dirty && !window.confirm("현재 입력을 불러온 응답으로 바꿀까요? 내보내지 않은 입력은 사라집니다.")) return;
          state = imported; dirty = false; render(); message("검증한 응답을 불러왔습니다.");
        } catch (error) { message(`불러오기 거부 — 현재 입력을 유지했습니다: ${error.message}`); }
        finally { $("import").value = ""; }
      };
      window.addEventListener("beforeunload", event => {
        if (dirty) { event.preventDefault(); event.returnValue = ""; }
      });
      render();
    } catch (error) { message(`초기화 실패: ${error.message}`); }
  }

  const api = {validateResponse, imagePoint, setStatus, parseResponse, exportResponse};
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  if (typeof document !== "undefined") init();
})();

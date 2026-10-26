/* Saved-frame consumer only: never infer a missing point, a future event or a missing name. */
(function () {
  "use strict";

  const COMPARISON_SCHEMA = "pitcheezy-reacquire-frame-comparison-dev-v1";
  function validComparisonFrame(pitch, frame) {
    if (!frame || frame.width !== 1280 || frame.height !== 720 ||
        typeof pitch.pitch_id !== "string" || pitch.pitch_id.trim() === "" ||
        !Number.isInteger(frame.frame_index) || frame.frame_index < 0 ||
        !Number.isFinite(frame.frame_seconds) || frame.frame_seconds < 0 ||
        typeof frame.sha256 !== "string" || !/^[a-f0-9]{64}$/i.test(frame.sha256)) return false;
    const candidate = frame.reacquire;
    return !!candidate && [candidate.selection, candidate.tracking].every(row => row &&
      row.pitch_id === pitch.pitch_id && row.frame_index === frame.frame_index &&
      row.frame_seconds === frame.frame_seconds) && candidate.tracking.source_sha256 === frame.sha256;
  }

  function selectedFrame(frame, mode) {
    if (mode === "baseline") return frame;
    if (!frame.reacquire?.selection || !frame.reacquire?.tracking) throw new Error("재탐색 행이 없습니다.");
    return { ...frame, selection: frame.reacquire.selection, tracking: frame.reacquire.tracking };
  }

  function trackingText(state, segment) {
    if (state === "tracking") return `확인된 패치 추적${Number.isInteger(segment) ? ` · 구간 ${segment}` : ""} · 미트 식별 아님`;
    if (state === "reacquire_search") return "재탐색 중 · 현재 점 없음";
    if (state === "reacquire_candidate") return "미확정 재탐색 후보 · 다음 프레임 확인 전 · 현재 점 없음";
    if (state === "lost") return "추적 종료 · 현재 점 없음";
    if (state === "unseeded") return "시드 없음 · 현재 점 없음";
    return "지원하지 않는 상태 · 현재 점 없음";
  }

  function comparisonText(frame, view) {
    if (view.loading || view.error || !view.image) return "이미지 준비 전에는 비교 표시를 비웁니다.";
    const candidate = frame.reacquire;
    if (!candidate) return "";
    return `기존: ${trackingText(frame.selection.tracker_state)} / 재탐색: ${trackingText(candidate.tracking.state, candidate.tracking.segment_id)}`;
  }

  function reasonText(frame) {
    return frame.tracking ? `추적: ${frame.tracking.reason} / 멈춤 판정: ${frame.selection.reason}` : frame.selection.reason;
  }

  function historyFor(pitch, frame) {
    const event = frame.selection.last_historical_candidate;
    if (!event || event.pitch_id !== pitch.pitch_id ||
        event.frame_index > frame.frame_index || event.frame_seconds > frame.frame_seconds ||
        event.available_frame > frame.frame_index || event.available_seconds > frame.frame_seconds) return null;
    const source = pitch.frames.find(item => item.frame_index === event.frame_index);
    if (!source || source.frame_seconds !== event.frame_seconds) return null;
    return { event, frame: source };
  }

  class Controller {
    constructor(data, { loadImage, onChange,
      setTimer = (callback, delay) => setTimeout(callback, delay),
      clearTimer = id => clearTimeout(id) }) {
      if (data?.schema !== "pitcheezy-track-frame-view-dev-v1" ||
          !Array.isArray(data.pitches) || !data.pitches.length ||
          !data.pitches.every(pitch => pitch && Array.isArray(pitch.frames) && pitch.frames.length)) {
        throw new Error("지원하지 않는 자료 형식입니다.");
      }
      Object.assign(this, { data, loadImage, onChange, setTimer, clearTimer });
      this.hasComparison = data.comparison_schema === COMPARISON_SCHEMA;
      if (this.hasComparison && !data.pitches.every(pitch => pitch.frames.every(frame => validComparisonFrame(pitch, frame)))) {
        throw new Error("재탐색 자료의 프레임·이미지 연결이 유효하지 않습니다.");
      }
      this.mode = "baseline";
      this.pitchIndex = 0; this.frameIndex = 0; this.generation = 0; this.timer = null;
      this.playing = false; this.view = { loading: true, image: null, history: null, historyPending: false, error: null };
    }
    get pitch() { return this.data.pitches[this.pitchIndex]; }
    get rawFrame() { return this.pitch.frames[this.frameIndex]; }
    get frame() { return selectedFrame(this.rawFrame, this.mode); }
    emit() {
      this.onChange({ ...this.view, pitch: this.pitch, frame: this.frame,
        rawFrame: this.rawFrame, mode: this.mode, hasComparison: this.hasComparison,
        pitchIndex: this.pitchIndex, frameIndex: this.frameIndex, playing: this.playing });
    }
    cancelTimer() { if (this.timer !== null) this.clearTimer(this.timer); this.timer = null; }
    pause() { this.playing = false; this.cancelTimer(); this.emit(); }
    async show(index) {
      this.cancelTimer();
      this.frameIndex = Math.max(0, Math.min(index, this.pitch.frames.length - 1));
      const generation = ++this.generation, frame = this.frame, pitch = this.pitch;
      this.view = { loading: true, image: null, history: null, historyPending: false, error: null };
      this.emit();
      try {
        const image = await this.loadImage(frame);
        if (generation !== this.generation) return;
        const history = historyFor(pitch, frame);
        this.view = { loading: false, image, history: null, historyPending: !!history, error: null };
        this.emit(); this.schedule();
        if (!history) return;
        try {
          const sameImage = history.frame.frame_index === frame.frame_index && history.frame.sha256 === frame.sha256;
          const historicalImage = sameImage ? image : await this.loadImage(history.frame);
          if (generation !== this.generation) return;
          this.view = { ...this.view, history: { ...history, image: historicalImage }, historyPending: false };
          this.emit();
        } catch (_) {
          if (generation !== this.generation) return;
          this.view = { ...this.view, history: null, historyPending: false, historyError: true }; this.emit();
        }
      } catch (_) {
        if (generation !== this.generation) return;
        this.playing = false; this.cancelTimer();
        this.view = { loading: false, image: null, history: null, historyPending: false, error: "이미지 또는 화면 처리에 실패했습니다. 현재·과거 표시를 비웠습니다." };
        this.emit();
      }
    }
    seek(index) { this.playing = false; return this.show(index); }
    switchMode(mode) {
      if (!["baseline", "reacquire"].includes(mode) || (mode === "reacquire" && !this.hasComparison)) throw new Error("지원하지 않는 비교 방식입니다.");
      this.playing = false; this.mode = mode;
      return this.show(this.frameIndex);
    }
    switchPitch(index) {
      this.playing = false;
      this.pitchIndex = Math.max(0, Math.min(index, this.data.pitches.length - 1));
      return this.show(0);
    }
    toggle() {
      if (this.playing) return this.pause();
      if (this.view.error || this.frameIndex === this.pitch.frames.length - 1) return;
      this.playing = true; this.emit(); this.schedule();
    }
    schedule() {
      this.cancelTimer();
      if (!this.playing || this.view.loading || this.view.error) return;
      if (this.frameIndex === this.pitch.frames.length - 1) { this.pause(); return; }
      const delay = (this.pitch.frames[this.frameIndex + 1].frame_seconds - this.frame.frame_seconds) * 1000;
      if (!Number.isFinite(delay) || delay <= 0) { this.pause(); return; }
      this.timer = this.setTimer(() => { this.timer = null; void this.show(this.frameIndex + 1); }, delay);
    }
  }

  function handleKey(event, controller) {
    if (event.altKey || event.ctrlKey || event.metaKey || event.shiftKey || event.repeat ||
        event.target?.isContentEditable || /^(INPUT|SELECT|TEXTAREA|BUTTON)$/.test(event.target?.tagName || "")) return false;
    if (event.code === "Space") controller.toggle();
    else if (event.key === "ArrowLeft") void controller.seek(controller.frameIndex - 1);
    else if (event.key === "ArrowRight") void controller.seek(controller.frameIndex + 1);
    else return false;
    event.preventDefault(); return true;
  }

  function validPoint(point, frame) {
    return Array.isArray(point) && point.length === 2 && point.every(Number.isFinite) &&
      point[0] >= 0 && point[0] < frame.width && point[1] >= 0 && point[1] < frame.height;
  }

  function historyStatus(view) {
    if (view.loading) return "현재 이미지 준비 중";
    if (view.error) return "표시 없음";
    if (view.historyPending) return "기록 이미지 준비 중";
    if (view.historyError) return "기록 이미지 또는 화면 처리에 실패했습니다.";
    if (view.history && !validPoint(view.history.event.point_px, view.history.frame)) {
      return "기록 좌표가 유효하지 않아 표시하지 않습니다.";
    }
    return "이 시점까지 표시할 발생 기록 없음";
  }

  function visiblePoints(frame) {
    const selection = frame.selection;
    const track = selection.tracker_state === "tracking" && validPoint(selection.current_track_point_px, frame)
      ? selection.current_track_point_px : null;
    const current = selection.current_candidate;
    const candidate = track && selection.selection_state === "stationary" && current &&
      typeof current.pitch_id === "string" && current.pitch_id.trim() !== "" &&
      current.pitch_id === selection.pitch_id && current.frame_index === frame.frame_index &&
      (selection.segment_id === undefined || current.segment_id === selection.segment_id) &&
      current.frame_seconds === frame.frame_seconds && validPoint(current.point_px, frame)
      ? current.point_px : null;
    return { track, candidate };
  }

  /* OCR rows are joined to the displayed frame on all four keys; one exact row or nothing. */
  const OCR_SCHEMA = "pitcheezy-ocr-frame-view-dev-v1";
  const OCR_ROLES = ["pitcher", "batter"];
  const OCR_STATUSES = new Set(["read", "abstain", "error"]);
  const OCR_RELATIONS = new Set(["not_compared", "literal_same", "literal_changed"]);

  function validOcrRole(value) {
    return !!value && typeof value === "object" && typeof value.raw_text === "string" &&
      typeof value.reason === "string" && OCR_STATUSES.has(value.status) &&
      OCR_RELATIONS.has(value.temporal_relation) &&
      (value.status === "read" ? typeof value.name_text === "string" && value.name_text.trim() !== "" : value.name_text === null) &&
      (value.status === "read" || value.temporal_relation === "not_compared") &&
      ((value.temporal_relation === "not_compared") === (value.compared_to_frame === null)) &&
      (value.compared_to_frame === null || (Number.isInteger(value.compared_to_frame) && value.compared_to_frame >= 0));
  }

  function ocrFor(ocr, pitch, frame) {
    if (ocr === null || ocr === undefined) return { kind: "unavailable" };
    if (ocr.schema !== OCR_SCHEMA || !Array.isArray(ocr.pitches)) return { kind: "unsupported" };
    const entries = ocr.pitches.filter(entry => entry && entry.pitch_id === pitch.pitch_id);
    if (entries.length === 0) return { kind: "none" };
    if (entries.length !== 1 || !Array.isArray(entries[0].rows)) return { kind: "mismatch" };
    const rows = entries[0].rows.filter(row => row && row.pitch_id === pitch.pitch_id &&
      row.frame_index === frame.frame_index && row.frame_seconds === frame.frame_seconds &&
      row.image_sha256 === frame.sha256);
    if (rows.length !== 1 || !rows[0].roles || !OCR_ROLES.every(role => validOcrRole(rows[0].roles[role]))) return { kind: "mismatch" };
    return { kind: "row", row: rows[0] };
  }

  const BLANK = "—";
  function blankRoles() {
    const texts = {};
    for (const role of OCR_ROLES) texts[role] = { raw: BLANK, name: BLANK, state: BLANK, relation: BLANK };
    return texts;
  }

  function ocrRoleText(value) {
    const state = value.status === "read" ? "읽음" : value.status === "abstain" ? "기권" : "엔진 오류";
    const relation = value.temporal_relation === "not_compared" ? "비교 없음"
      : value.temporal_relation === "literal_same" ? `직전 읽음과 문자열 같음 · 비교 원본 번호 ${value.compared_to_frame}`
      : `직전 읽음과 문자열 다름 · 비교 원본 번호 ${value.compared_to_frame} · 선수 교체 근거 아님`;
    return {
      raw: value.raw_text === "" ? "(빈 문자열)" : value.raw_text,
      name: value.status === "read" ? value.name_text : BLANK,
      state: `${state} · ${value.reason}`,
      relation: value.status === "read" ? relation : "비교 없음"
    };
  }

  /* Pure view model: strings only, computed from the current frame and the current image state. */
  function ocrView(ocr, pitch, frame, view) {
    const roles = blankRoles();
    if (view.loading) return { status: "이미지 준비 중 · 표시 비움", roles };
    if (view.error) return { status: "표시 없음", roles };
    const match = ocrFor(ocr, pitch, frame);
    if (match.kind === "unavailable") return { status: "이 팩에는 OCR 관측 자료가 없습니다", roles };
    if (match.kind === "unsupported") return { status: "지원하지 않는 OCR 자료 형식 · 표시하지 않습니다", roles };
    if (match.kind === "none") return { status: "관측 자료 없음 · 이 투구는 OCR을 실행하지 않았습니다", roles };
    if (match.kind === "mismatch") return { status: "관측 불일치 · 이 프레임에 맞는 저장 관측이 없어 표시하지 않습니다", roles };
    for (const role of OCR_ROLES) roles[role] = ocrRoleText(match.row.roles[role]);
    return { status: `저장 관측 · 원본 번호 ${match.row.frame_index} · 자료 시각 ${match.row.frame_seconds.toFixed(3)}초`, roles };
  }

  function mount(document) {
    const get = id => document.getElementById(id);
    const data = JSON.parse(get("track-data").textContent);
    const ocr = JSON.parse(get("ocr-data").textContent);
    const currentCanvas = get("current-canvas"), historicalCanvas = get("history-canvas");
    function draw(canvas, image) {
      const context = canvas.getContext("2d");
      context.clearRect(0, 0, canvas.width, canvas.height);
      if (image) context.drawImage(image, 0, 0, canvas.width, canvas.height);
      return context;
    }
    function mark(context, point, color, radius, fill) {
      context.beginPath(); context.arc(point[0], point[1], radius, 0, Math.PI * 2);
      context.lineWidth = 4; context.strokeStyle = "#07111d"; context.stroke();
      context.lineWidth = 2; context.strokeStyle = color; context.stroke();
      if (fill) { context.fillStyle = color; context.fill(); }
    }
    function renderOcr(texts) {
      get("ocr-status").textContent = texts.status;
      for (const role of OCR_ROLES) {
        for (const field of ["raw", "name", "state", "relation"]) get(`ocr-${role}-${field}`).textContent = texts.roles[role][field];
      }
    }
    data.pitches.forEach(pitch => {
      const [, pa, number] = pitch.pitch_id.split(":");
      const option = document.createElement("option");
      option.value = get("pitch-select").options.length;
      option.textContent = `PA ${pa} · ${number}구`; get("pitch-select").append(option);
    });
    const controller = new Controller(data, {
      loadImage: frame => new Promise((resolve, reject) => {
        const image = new Image();
        image.onload = () => image.naturalWidth === frame.width && image.naturalHeight === frame.height
          ? resolve(image) : reject(new Error("image dimensions differ"));
        image.onerror = reject; image.src = frame.image;
      }),
      onChange(view) {
        const { pitch, frame, frameIndex, pitchIndex, image } = view;
        const context = draw(currentCanvas, image), historyContext = draw(historicalCanvas, null);
        get("pitch-select").value = pitchIndex; get("pitch-key").textContent = `투구 키 ${pitch.pitch_id}`;
        get("frame-slider").max = pitch.frames.length - 1; get("frame-slider").value = frameIndex;
        get("previous-frame").disabled = frameIndex === 0;
        get("next-frame").disabled = frameIndex === pitch.frames.length - 1;
        get("previous-pitch").disabled = pitchIndex === 0;
        get("next-pitch").disabled = pitchIndex === data.pitches.length - 1;
        get("play").textContent = view.playing ? "정지" : "재생";
        get("play").disabled = !!view.error || frameIndex === pitch.frames.length - 1;
        get("frame-time").textContent = `${frameIndex + 1} / ${pitch.frames.length}장 · 원본 번호 ${frame.frame_index} · 자료 시각 ${frame.frame_seconds.toFixed(3)}초`;
        get("frame-status").textContent = view.loading ? "이미지 준비 중 · 표시 비움" : view.error || "현재 저장 프레임";
        get("track-state").textContent = "—"; get("candidate-state").textContent = "—"; get("reason").textContent = "—";
        get("history-status").textContent = historyStatus(view);
        renderOcr(ocrView(ocr, pitch, frame, view));
        get("comparison-controls").hidden = !view.hasComparison;
        get("mode-select").value = view.mode;
        get("comparison-status").textContent = comparisonText(view.rawFrame, view);
        get("current-title").textContent = view.hasComparison ? `현재 프레임 · ${view.mode === "baseline" ? "기존 추적" : "제한된 재탐색"}` : "현재 프레임";
        get("segment-state").textContent = "—";
        if (!image) return;
        const points = visiblePoints(frame);
        if (points.track) mark(context, points.track, "#4ee4ef", 5, true);
        if (points.candidate) mark(context, points.candidate, "#7bff8d", 13, false);
        get("track-state").textContent = trackingText(frame.selection.tracker_state, frame.selection.segment_id);
        get("segment-state").textContent = view.mode === "reacquire"
          ? (Number.isInteger(frame.selection.segment_id) ? `구간 ${frame.selection.segment_id} · 멈춤 조건은 구간마다 새로 충족` : "확정된 현재 구간 없음")
          : "기존 추적 · 재탐색 없음";
        get("candidate-state").textContent = points.candidate ? "현재 구간에서 조건 충족" : "현재 후보 없음";
        get("reason").textContent = reasonText(frame);
        if (view.history && validPoint(view.history.event.point_px, view.history.frame)) {
          draw(historicalCanvas, view.history.image);
          mark(historyContext, view.history.event.point_px, "#ffb454", 9, false);
          const segment = view.history.event.segment_id;
          get("history-status").textContent = `최초 발생 기록${Number.isInteger(segment) ? ` · 구간 ${segment}` : ""} · ${view.history.event.frame_seconds.toFixed(3)}초 · 원본 번호 ${view.history.event.frame_index} · 현재 위치로 사용하지 않음`;
        }
      }
    });
    get("pitch-select").addEventListener("change", event => void controller.switchPitch(Number(event.target.value)));
    get("mode-select").addEventListener("change", event => void controller.switchMode(event.target.value));
    get("frame-slider").addEventListener("input", event => void controller.seek(Number(event.target.value)));
    get("previous-frame").addEventListener("click", () => void controller.seek(controller.frameIndex - 1));
    get("next-frame").addEventListener("click", () => void controller.seek(controller.frameIndex + 1));
    get("previous-pitch").addEventListener("click", () => void controller.switchPitch(controller.pitchIndex - 1));
    get("next-pitch").addEventListener("click", () => void controller.switchPitch(controller.pitchIndex + 1));
    get("play").addEventListener("click", () => controller.toggle());
    document.addEventListener("keydown", event => handleKey(event, controller));
    void controller.show(0);
    return controller;
  }

  if (typeof module !== "undefined" && module.exports) module.exports = { Controller, historyFor, historyStatus, visiblePoints, handleKey, ocrFor, ocrView, selectedFrame, trackingText, comparisonText, reasonText };
  if (typeof document !== "undefined") {
    try { mount(document); }
    catch (_) { const status = document.getElementById("frame-status"); if (status) status.textContent = "자료를 열지 못했습니다. 팩 무결성을 다시 확인해 주세요."; }
  }
})();

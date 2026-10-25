/* Saved-frame consumer only: never infer a missing point or a future event. */
(function () {
  "use strict";

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
      if (data.schema !== "pitcheezy-track-frame-view-dev-v1" || !data.pitches?.length) throw new Error("지원하지 않는 자료 형식입니다.");
      Object.assign(this, { data, loadImage, onChange, setTimer, clearTimer });
      this.pitchIndex = 0; this.frameIndex = 0; this.generation = 0; this.timer = null;
      this.playing = false; this.view = { loading: true, image: null, history: null, historyPending: false, error: null };
    }
    get pitch() { return this.data.pitches[this.pitchIndex]; }
    get frame() { return this.pitch.frames[this.frameIndex]; }
    emit() {
      this.onChange({ ...this.view, pitch: this.pitch, frame: this.frame,
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
          const historicalImage = history.frame === frame ? image : await this.loadImage(history.frame);
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
        this.view = { loading: false, image: null, history: null, historyPending: false, error: "이미지를 불러오지 못했습니다. 현재·과거 표시를 비웠습니다." };
        this.emit();
      }
    }
    seek(index) { this.playing = false; return this.show(index); }
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

  function visiblePoints(frame) {
    const selection = frame.selection;
    const track = selection.tracker_state === "tracking" && validPoint(selection.current_track_point_px, frame)
      ? selection.current_track_point_px : null;
    const current = selection.current_candidate;
    const candidate = track && selection.selection_state === "stationary" && current &&
      current.pitch_id === selection.pitch_id && current.frame_index === frame.frame_index &&
      current.frame_seconds === frame.frame_seconds && validPoint(current.point_px, frame)
      ? current.point_px : null;
    return { track, candidate };
  }

  function mount(document) {
    const get = id => document.getElementById(id);
    const data = JSON.parse(get("track-data").textContent);
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
        get("history-status").textContent = view.loading ? "현재 이미지 준비 중" : view.error ? "표시 없음" : view.historyPending ? "기록 이미지 준비 중" : view.historyError ? "기록 이미지를 불러오지 못했습니다." : "이 시점까지 표시할 발생 기록 없음";
        if (!image) return;
        const points = visiblePoints(frame);
        if (points.track) mark(context, points.track, "#4ee4ef", 5, true);
        if (points.candidate) mark(context, points.candidate, "#7bff8d", 13, false);
        get("track-state").textContent = points.track ? "현재 패치 있음 · 미트 식별 미검증" : "현재 추적 점 없음";
        get("candidate-state").textContent = points.candidate ? "현재 구간에서 조건 충족" : "현재 후보 없음";
        get("reason").textContent = frame.selection.reason;
        if (view.history && validPoint(view.history.event.point_px, view.history.frame)) {
          draw(historicalCanvas, view.history.image);
          mark(historyContext, view.history.event.point_px, "#ffb454", 9, false);
          get("history-status").textContent = `최초 발생 기록 · ${view.history.event.frame_seconds.toFixed(3)}초 · 원본 번호 ${view.history.event.frame_index} · 현재 위치로 사용하지 않음`;
        }
      }
    });
    get("pitch-select").addEventListener("change", event => void controller.switchPitch(Number(event.target.value)));
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

  if (typeof module !== "undefined" && module.exports) module.exports = { Controller, historyFor, visiblePoints, handleKey };
  if (typeof document !== "undefined") {
    try { mount(document); }
    catch (_) { const status = document.getElementById("frame-status"); if (status) status.textContent = "자료를 열지 못했습니다. 팩 무결성을 다시 확인해 주세요."; }
  }
})();

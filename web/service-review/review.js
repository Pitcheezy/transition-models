(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else { root.ServiceReview = api; api.mount(document); }
})(typeof globalThis !== "undefined" ? globalThis : this, function () {
  "use strict";
  const SCHEMA = "pitcheezy-service-review-v1";
  const PROFILE = "teammate_export_20261009_v1";
  const MEDIA_SCHEMA = "pitcheezy-service-review-media-v1";
  const MAX_BYTES = 5 * 1024 * 1024;
  // Supplied S contract geometry; this is not a measurement of the physical plate.
  const SERVICE_ZONE_HALF_WIDTH = .83;
  const finite = value => typeof value === "number" && Number.isFinite(value);
  const object = value => value !== null && typeof value === "object" && !Array.isArray(value);
  const text = value => typeof value === "string" ? value : "";
  const clone = value => JSON.parse(JSON.stringify(value));
  const assert = (condition, message) => { if (!condition) throw new Error(message); };
  const numeric = (value, low, high) => finite(value) && value >= low && value <= high;
  const integer = (value, low, high) => Number.isInteger(value) && numeric(value, low, high);

  function assertPreOnly(value, depth = 0) {
    assert(depth <= 24, "투구 전 정보의 구조가 너무 깊습니다.");
    if (Array.isArray(value)) { for (const item of value) assertPreOnly(item, depth + 1); }
    else if (object(value)) for (const [key, item] of Object.entries(value)) {
      assert(!["post", "actual", "result", "we", "catcher_setup", "setup_x_ft", "setup_status"].includes(key),
        "투구 전 정보에 사후 관측 필드가 포함되어 있습니다.");
      assertPreOnly(item, depth + 1);
    }
  }

  function validateReport(report) {
    assert(object(report) && report.schema === SCHEMA && report.profile === PROFILE,
      "지원하는 정규화 보고서 형식이 아닙니다. 원본 응답은 먼저 정규화해주세요.");
    assert(object(report.game) && integer(report.game.game_pk, 1, 2147483647) &&
      object(report.source), "경기 또는 출처 정보가 없습니다.");
    assert(["synthetic", "provided_export"].includes(report.source.input_kind) &&
      /^[a-f0-9]{64}$/.test(report.source.sha256), "보고서 출처 정보가 올바르지 않습니다.");
    assert(object(report.zone_bounds) && numeric(report.zone_bounds.bottom, -20, 20) &&
      numeric(report.zone_bounds.top, -20, 20) && report.zone_bounds.bottom < report.zone_bounds.top,
    "구역 경계가 올바르지 않습니다.");
    assert(Array.isArray(report.pitches) && report.pitches.length <= 2000, "투구 목록이 올바르지 않습니다.");
    const keys = new Set();
    for (const pitch of report.pitches) {
      assert(object(pitch) && text(pitch.key) && text(pitch.pa_key) && !keys.has(pitch.key),
        "중복되거나 누락된 투구 식별자가 있습니다.");
      keys.add(pitch.key);
      assert(integer(pitch.pitch_number, 1, 100) && integer(pitch.at_bat_number, 1, 999) &&
        object(pitch.pre) && object(pitch.pre.situation) && object(pitch.pre.pitcher) &&
        object(pitch.pre.batter), "투구 전 정보가 올바르지 않습니다.");
      // Local file selection bypasses the launcher's checks; bind the same identity here.
      const paKey = `${report.game.game_pk}:${pitch.at_bat_number}`;
      assert(pitch.pa_key === paKey && pitch.key === `${paKey}:${pitch.pitch_number}`,
        "경기·타석·투구 번호와 식별자가 일치하지 않습니다.");
      assertPreOnly(pitch.pre);
      const s = pitch.pre.situation;
      assert(integer(s.inning, 1, 99) && ["Top", "Bot"].includes(s.half) && integer(s.outs, 0, 2) &&
        integer(s.balls, 0, 3) && integer(s.strikes, 0, 2) && integer(s.bases, 0, 7) &&
        integer(s.home_score, 0, 1000) && integer(s.away_score, 0, 1000), "투구 전 상황 값이 올바르지 않습니다.");
      const rec = pitch.pre.recommendation;
      assert(object(rec) && ["ready", "unsupported", "missing"].includes(rec.status) &&
        Array.isArray(rec.candidates) && rec.candidates.length <= 30 &&
        ((rec.status === "ready") === (rec.candidates.length > 0)), "추천 상태가 올바르지 않습니다.");
      const ranks = new Set();
      for (const c of rec.candidates) {
        assert(object(c) && integer(c.rank, 1, 30) && !ranks.has(c.rank) && text(c.pitch_type),
          "추천 후보의 순위 또는 구종이 올바르지 않습니다.");
        ranks.add(c.rank);
        assert(c.selection_probability === null || numeric(c.selection_probability, 0, 1),
          "구종 선택 비중이 올바르지 않습니다.");
        assert(c.target === null || (object(c.target) && numeric(c.target.x, -20, 20) &&
          numeric(c.target.z, -20, 20)), "추천 위치가 올바르지 않습니다.");
      }
      assert(object(pitch.post), "사후 데이터 컨테이너가 없습니다.");
      const a = pitch.post.actual;
      assert(a === null || object(a), "실제 투구 정보가 올바르지 않습니다.");
      if (a) for (const key of ["x", "z", "speed_mph", "setup_x_ft"]) {
        assert(a[key] == null || finite(a[key]), "실제 투구 좌표 또는 속도가 유한수가 아닙니다.");
      }
    }
    return report;
  }

  function groupsFor(report) {
    const groups = new Map();
    for (const pitch of report.pitches) {
      if (!groups.has(pitch.pa_key)) groups.set(pitch.pa_key, []);
      groups.get(pitch.pa_key).push(pitch);
    }
    return Array.from(groups, ([key, pitches]) => ({ key, pitches }));
  }

  function viewFor(report, key, revealed = false) {
    validateReport(report);
    assert(typeof revealed === "boolean", "공개 여부는 명시적인 참/거짓 값이어야 합니다.");
    const pitch = report.pitches.find(p => p.key === key);
    assert(pitch, "선택한 투구가 보고서에 없습니다.");
    // Only the four pre-pitch containers are projected. No raw row/PA metadata enters the view.
    const pre = clone({ situation: pitch.pre.situation, pitcher: pitch.pre.pitcher,
      batter: pitch.pre.batter, recommendation: pitch.pre.recommendation });
    return { key: pitch.key, pa_key: pitch.pa_key, at_bat_number: pitch.at_bat_number,
      pitch_number: pitch.pitch_number, pre, actual: revealed ? clone(pitch.post.actual) : null,
      revealed };
  }

  function initialState(report) {
    validateReport(report);
    return { report, key: report.pitches.length ? report.pitches[0].key : null, revealed: false };
  }
  function selectPitch(state, key) {
    assert(state.report.pitches.some(p => p.key === key), "선택한 투구가 없습니다.");
    return { report: state.report, key, revealed: false };
  }
  function selectPA(state, paKey) {
    const pitch = state.report.pitches.find(p => p.pa_key === paKey);
    assert(pitch, "선택한 타석이 없습니다.");
    return selectPitch(state, pitch.key);
  }
  function reveal(state) {
    assert(state.key !== null, "공개할 투구가 없습니다.");
    return { report: state.report, key: state.key, revealed: true };
  }

  function setupSummary(view) {
    if (!view.revealed) return { status: "hidden", message: "" };
    const actual = view.actual;
    if (!actual || actual.setup_status == null) return { status: "not_supplied", message: "영상 추정 행 없음" };
    if (actual.setup_status === "unavailable") return { status: "unavailable", message: "영상은 있으나 추정 기권" };
    if (actual.setup_status === "estimated") return finite(actual.setup_x_ft) ?
      { status: "estimated", message: "" } : { status: "coordinate_missing", message: "가로 좌표 미제공" };
    return { status: "unsupported", message: "미트 추정 상태를 해석할 수 없습니다." };
  }

  function plotModel(report, view) {
    const zone = { left: -SERVICE_ZONE_HALF_WIDTH, right: SERVICE_ZONE_HALF_WIDTH,
      bottom: report.zone_bounds.bottom, top: report.zone_bounds.top,
      columnCenters: [-2 / 3, 0, 2 / 3].map(f => f * SERVICE_ZONE_HALF_WIDTH),
      verticalDividers: [-1 / 3, 1 / 3].map(f => f * SERVICE_ZONE_HALF_WIDTH) };
    const bounds = { left: -2.5, right: 2.5,
      bottom: Math.min(0, report.zone_bounds.bottom - .65),
      top: Math.max(5, report.zone_bounds.top + .65) };
    const point = (x, z, label, kind) => ({ x, z, label, kind,
      clipped: x < bounds.left || x > bounds.right || z < bounds.bottom || z > bounds.top });
    const grouped = new Map();
    for (const c of view.pre.recommendation.candidates.slice().sort((a, b) => a.rank - b.rank)) {
      if (c.target === null) continue;
      const key = `${c.target.x}:${c.target.z}`;
      if (!grouped.has(key)) grouped.set(key, { ...point(c.target.x, c.target.z, "", "candidate"), ranks: [] });
      grouped.get(key).ranks.push(c.rank);
    }
    const points = Array.from(grouped.values(), p => ({ ...p, label: p.ranks.join("·") }));
    const actual = view.revealed ? view.actual : null;
    if (actual && finite(actual.x) && finite(actual.z)) points.push({ ...point(actual.x, actual.z, "실제", "actual"),
      overlapsCandidate: grouped.has(`${actual.x}:${actual.z}`) });
    const setup = actual && actual.setup_status === "estimated" && finite(actual.setup_x_ft) ?
      { x: actual.setup_x_ft, clipped: Math.abs(actual.setup_x_ft) > 2.5 } : null;
    return { bounds, zone, points, setup, setupSummary: setupSummary(view) };
  }

  function createLoadCoordinator({ clear, commit, fail }) {
    let sequence = 0;
    return async function load(reader) {
      const current = ++sequence;
      clear();
      try {
        const result = validateReport(await reader());
        if (current === sequence) commit(result);
      } catch (error) {
        if (current === sequence) fail(error);
      }
    };
  }

  function validateMediaManifest(manifest) {
    assert(object(manifest) && manifest.schema === MEDIA_SCHEMA &&
      integer(manifest.game_pk, 1, 2147483647) && /^[a-f0-9]{64}$/.test(manifest.source_sha256),
    "영상 연결 정보의 형식 또는 출처가 올바르지 않습니다.");
    assert(Array.isArray(manifest.clips) && manifest.clips.length <= 2000,
      "영상 연결 목록이 올바르지 않습니다.");
    const keys = new Set(), playIds = new Set();
    for (const clip of manifest.clips) {
      assert(object(clip) && typeof clip.pitch_key === "string" &&
        new RegExp(`^${manifest.game_pk}:[1-9][0-9]{0,2}:[1-9][0-9]{0,2}$`).test(clip.pitch_key) &&
        !keys.has(clip.pitch_key), "영상 투구 식별자가 누락되었거나 중복되었습니다.");
      assert(typeof clip.play_id === "string" && /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/i.test(clip.play_id) &&
        !playIds.has(clip.play_id.toLowerCase()), "영상 play_id가 올바르지 않거나 중복되었습니다.");
      // Restrict to one local directory and plain filenames. No URL, encoded traversal or queries.
      assert(typeof clip.video === "string" && /^media\/[A-Za-z0-9][A-Za-z0-9_-]*\.mp4$/.test(clip.video) &&
        typeof clip.poster === "string" && /^media\/[A-Za-z0-9][A-Za-z0-9_-]*\.(?:jpg|jpeg|png)$/.test(clip.poster),
      "영상과 포스터는 media 폴더 안의 로컬 파일이어야 합니다.");
      assert(/^[a-f0-9]{64}$/.test(clip.video_sha256) && /^[a-f0-9]{64}$/.test(clip.poster_sha256) &&
        numeric(clip.duration_seconds, .001, 3600), "영상 파일 해시 또는 길이가 올바르지 않습니다.");
      keys.add(clip.pitch_key); playIds.add(clip.play_id.toLowerCase());
    }
    return manifest;
  }

  function mediaBinding(report, key, manifest) {
    if (manifest === null) return { clip: null, reason: "이 묶음에는 연결된 공식 클립이 없습니다." };
    validateMediaManifest(manifest);
    if (manifest.game_pk !== report.game.game_pk || manifest.source_sha256 !== report.source.sha256)
      return { clip: null, reason: "현재 보고서와 영상의 경기 또는 원문 해시가 달라 연결하지 않았습니다." };
    if (!report.pitches.some(p => p.key === key)) return { clip: null, reason: "보고서에 해당 투구가 없습니다." };
    const clip = manifest.clips.find(c => c.pitch_key === key);
    return { clip: clip ? clone(clip) : null, reason: clip ? "" : "이 투구에 연결된 공식 클립이 없습니다. 결과는 직접 공개할 수 있습니다." };
  }

  function createMediaController({ clear, status, reveal: revealResult }) {
    let sequence = 0, current = null;
    const active = token => current !== null && token === current.token;
    function reset() {
      sequence++;
      current = null;
      clear();
    }
    function select(report, key, manifest) {
      reset();
      const binding = mediaBinding(report, key, manifest);
      current = { token: sequence, key, gamePk: report.game.game_pk, sourceSha256: report.source.sha256,
        clip: binding.clip, played: false, completed: false, failed: false };
      status({ phase: binding.clip ? "ready" : "unavailable", message: binding.reason });
      return { token: current.token, clip: binding.clip };
    }
    function signal(token, event) {
      if (!active(token) || !current.clip || current.failed || current.completed) return false;
      if (event === "play") { current.played = true; status({ phase: "playing", message: "클립 재생 중 · 종료하면 이 투구의 결과가 공개됩니다." }); }
      else if (event === "pause") status({ phase: "paused", message: "일시 정지 · 계속 재생하거나 결과를 직접 공개할 수 있습니다." });
      else if (event === "error") {
        current.failed = true;
        status({ phase: "error", message: "영상을 재생하지 못했습니다. 다시 불러오거나 영상 없이 결과를 공개하세요." });
      } else if (event === "ended" && current.played) {
        current.completed = true;
        status({ phase: "ended", message: "클립 재생 종료 · 이 투구의 결과를 공개했습니다." });
        revealResult({ key: current.key, gamePk: current.gamePk, sourceSha256: current.sourceSha256 });
      } else return false;
      return true;
    }
    async function requestPlay(token, start) {
      if (!active(token) || !current.clip || current.failed || current.completed) return false;
      try {
        await start();
        return signal(token, "play");
      } catch (error) {
        // Native pause/load can interrupt a pending play promise without a media failure.
        // signal retains the session guard, so a detached player's interruption stays inert.
        return signal(token, error && error.name === "AbortError" ? "pause" : "error");
      }
    }
    return { reset, select, signal, requestPlay };
  }

  function parseBytes(bytes) {
    assert(bytes.byteLength <= MAX_BYTES, "보고서는 최대 5 MiB까지 열 수 있습니다.");
    return JSON.parse(new TextDecoder("utf-8", { fatal: true }).decode(bytes));
  }

  function mount(doc) {
    const $ = id => doc.getElementById(id);
    if (!$("report-file")) return;
    let state = null, currentVideo = null, currentMediaToken = null;
    let mediaManifest = null, mediaManifestLoaded = false, mediaManifestError = "";
    const make = (tag, className, value) => {
      const el = doc.createElement(tag);
      if (className) el.className = className;
      if (value !== undefined) el.textContent = String(value);
      return el;
    };
    const replace = (id, ...nodes) => $(id).replaceChildren(...nodes);
    const say = (id, value) => { $(id).textContent = value; };
    const fmt = value => finite(value) ? value.toFixed(2) : "없음";
    const half = value => value === "Top" ? "초" : "말";
    const team = side => text(state.report.game[side + "_team"]) || (side === "away" ? "원정" : "홈");
    const svg = (tag, attrs = {}, value) => {
      const el = doc.createElementNS("http://www.w3.org/2000/svg", tag);
      for (const [key, val] of Object.entries(attrs)) el.setAttribute(key, String(val));
      if (value !== undefined) el.textContent = String(value);
      return el;
    };

    const mediaController = createMediaController({
      clear() {
        currentMediaToken = null;
        if (currentVideo) {
          const previous = currentVideo;
          currentVideo = null;
          previous.pause();
          previous.removeAttribute("src");
          previous.removeAttribute("poster");
          previous.load();
        }
        replace("media-player");
        say("media-caption", ""); say("media-status", "");
        $("media-play").hidden = true; $("media-retry").hidden = true;
        $("media-play").disabled = false;
      },
      status({ phase, message }) {
        say("media-status", message || "추천 검토를 마쳤다면 클립을 재생하세요.");
        $("media-retry").hidden = phase !== "error";
        $("media-play").disabled = phase === "error" || phase === "ended";
      },
      reveal(selection) {
        if (state && state.key === selection.key && state.report.game.game_pk === selection.gamePk &&
          state.report.source.sha256 === selection.sourceSha256) { state = reveal(state); render(); }
      }
    });

    function prepareMedia() {
      if (!state || !state.key) { mediaController.reset(); return; }
      const selection = mediaController.select(state.report, state.key, mediaManifest);
      currentMediaToken = selection.token;
      if (!selection.clip) {
        if (!mediaManifestLoaded) say("media-status", "영상 연결 정보를 확인하고 있습니다. 결과는 직접 공개할 수 있습니다.");
        else if (mediaManifestError) say("media-status", mediaManifestError);
        return;
      }
      const clip = selection.clip, video = make("video", "official-clip");
      currentVideo = video;
      video.controls = true;
      video.playsInline = true;
      video.preload = "metadata";
      video.setAttribute("aria-label", `선택한 투구 ${state.key}의 공식 클립`);
      video.addEventListener("play", () => mediaController.signal(selection.token, "play"));
      video.addEventListener("pause", () => mediaController.signal(selection.token, "pause"));
      video.addEventListener("error", () => mediaController.signal(selection.token, "error"));
      video.addEventListener("ended", () => {
        if (video.ended && !video.error) mediaController.signal(selection.token, "ended");
      });
      video.src = clip.video;
      video.poster = clip.poster;
      replace("media-player", video);
      $("media-play").hidden = false;
      say("media-caption", `${state.key} · 공식 클립 ${clip.duration_seconds.toFixed(2)}초 · play_id ${clip.play_id}`);
      video.load();
    }

    function changeSelection(nextState) {
      state = nextState;
      prepareMedia();
      render();
    }

    function renderPlot(view) {
      const model = plotModel(state.report, view), b = model.bounds;
      const x = value => 45 + (Math.max(b.left, Math.min(b.right, value)) - b.left) / (b.right - b.left) * 330;
      const y = value => 295 - (Math.max(b.bottom, Math.min(b.top, value)) - b.bottom) / (b.top - b.bottom) * 264;
      const chart = svg("svg", { viewBox: "0 0 420 335", role: "img", "aria-label": "추천 위치 비교. 공개 전에는 추천 좌표만 표시됩니다." });
      chart.append(svg("rect", { x: 45, y: 31, width: 330, height: 264, rx: 10, fill: "#f8fafb" }));
      for (const value of [-2, -1, 0, 1, 2]) {
        chart.append(svg("line", { x1: x(value), x2: x(value), y1: 31, y2: 295, stroke: "#e5ecef", "stroke-dasharray": "3 5" }));
        chart.append(svg("text", { x: x(value), y: 315, "text-anchor": "middle", fill: "#8b9aa2", "font-size": 10 }, value));
      }
      for (let value = Math.ceil(b.bottom); value <= Math.floor(b.top); value++) {
        chart.append(svg("line", { x1: 45, x2: 375, y1: y(value), y2: y(value), stroke: "#e5ecef", "stroke-dasharray": "3 5" }));
        chart.append(svg("text", { x: 31, y: y(value) + 3, "text-anchor": "end", fill: "#8b9aa2", "font-size": 10 }, value));
      }
      const zone = model.zone;
      chart.append(svg("rect", { x: x(zone.left), y: y(zone.top), width: x(zone.right) - x(zone.left),
        height: y(zone.bottom) - y(zone.top), fill: "#e8f2ee", "fill-opacity": .8, stroke: "#84a69a", "stroke-width": 1.5 }));
      for (let column = 0; column < 2; column++) {
        const vx = zone.verticalDividers[column], vz = zone.bottom + (zone.top - zone.bottom) * (column + 1) / 3;
        chart.append(svg("line", { x1: x(vx), x2: x(vx), y1: y(zone.top), y2: y(zone.bottom), stroke: "#b4cbbf", "stroke-dasharray": "3 4" }));
        chart.append(svg("line", { x1: x(zone.left), x2: x(zone.right), y1: y(vz), y2: y(vz), stroke: "#b4cbbf", "stroke-dasharray": "3 4" }));
      }
      chart.append(svg("text", { x: 388, y: 315, fill: "#8b9aa2", "font-size": 10 }, "x"));
      chart.append(svg("text", { x: 31, y: 19, fill: "#8b9aa2", "font-size": 10 }, "z"));
      for (const p of model.points) {
        const color = p.kind === "actual" ? "#db6836" : p.ranks[0] === 1 ? "#087e6c" : p.ranks[0] === 2 ? "#427a94" : "#79849e";
        const ring = p.kind === "actual" && p.overlapsCandidate;
        const matchingGroup = ring ? pointsForCoordinate(model.points, p.x, p.z) : null;
        const radius = p.kind === "candidate" ? Math.min(34, 14 + Math.max(0, p.label.length - 1) * 2) :
          ring ? Math.min(34, 14 + Math.max(0, matchingGroup.label.length - 1) * 2) + 5 : 8;
        const circle = svg("circle", { cx: x(p.x), cy: y(p.z), r: radius,
          fill: ring ? "none" : color, stroke: ring ? color : "#fff", "stroke-width": 2.5 });
        circle.append(svg("title", {}, `${p.kind === "actual" ? "실제" : "후보 " + p.label}: x ${fmt(p.x)}, z ${fmt(p.z)} ft${p.clipped ? " · 보기 범위 밖" : ""}`));
        chart.append(circle);
        if (p.kind === "candidate") chart.append(svg("text", { x: x(p.x), y: y(p.z) + 4, "text-anchor": "middle", fill: "#fff", "font-size": 11, "font-weight": 700 }, p.label));
        if (p.clipped) chart.append(svg("text", { x: x(p.x), y: y(p.z) - 17, "text-anchor": "middle", fill: color, "font-size": 12 }, "↗"));
      }
      replace("plot", chart);
      const legend = make("span", "legend-item");
      legend.append(make("span", "legend-dot"), make("span", "", "숫자 = 추천 순위 · 같은 위치는 묶음"));
      const legends = [legend];
      if (view.revealed) {
        const observed = make("span", "legend-item");
        observed.append(make("span", "legend-dot actual-dot"), make("span", "", "실제 투구 · 겹치면 테두리"));
        legends.push(observed);
      }
      replace("plot-legend", ...legends);
      const clipped = model.points.filter(p => p.clipped);
      say("plot-clipping", clipped.length ? `보기 범위 밖: ${clipped.map(p => p.kind === "actual" ? "실제 투구" : "추천 " + p.label).join(", ")} · 경계에 표시하며 원 좌표는 카드에 유지합니다.` : "");
      replace("setup-rail");
      if (!view.revealed) return;
      const rail = $("setup-rail");
      rail.append(make("h3", "", "미트 가로 위치 추정 · 미검토 · 투수 의도 아님"));
      rail.append(make("p", "", "포수 시점 · 오른쪽 + · 서비스 좌표 기준"));
      if (!model.setup) {
        rail.append(make("p", "", model.setupSummary.message));
        return;
      }
      const railSvg = svg("svg", { viewBox: "0 0 420 56", role: "img", "aria-label": `미트 가로 위치 ${fmt(model.setup.x)} ft. 높이 정보 없음.` });
      railSvg.append(svg("line", { x1: 45, x2: 375, y1: 22, y2: 22, stroke: "#c3d2d7", "stroke-width": 2 }));
      for (const value of [-2.5, 0, 2.5]) {
        railSvg.append(svg("line", { x1: x(value), x2: x(value), y1: 18, y2: 27, stroke: "#90a5ae" }));
        railSvg.append(svg("text", { x: x(value), y: 44, fill: "#8b9aa2", "font-size": 10, "text-anchor": "middle" }, value));
      }
      railSvg.append(svg("circle", { cx: x(model.setup.x), cy: 22, r: 6, fill: "#9654a1", stroke: "#fff", "stroke-width": 2 }));
      rail.append(railSvg, make("p", "", `x ${fmt(model.setup.x)} ft · 높이 미제공${model.setup.clipped ? " · 보기 범위 밖: 경계에 표시" : ""}`));
    }

    function render() {
      const report = state.report;
      $("report-content").hidden = !state.key;
      $("empty-state").hidden = Boolean(state.key);
      if (!state.key) { say("load-status", "보고서는 읽었지만 검토할 투구가 없습니다."); return; }
      const view = viewFor(report, state.key, state.revealed), pre = view.pre, s = pre.situation;
      say("game-meta", `${text(report.game.kst_date) || "날짜 미제공"} KST · GAME ${report.game.game_pk}`);
      say("game-title", `${team("away")} vs ${team("home")}`);
      replace("source-badges", make("span", "badge", "사후 검토"),
        make("span", "badge", `원천: ${text(report.source.upstream_kind) || "미제공"}`),
        make("span", "badge", report.source.input_kind === "synthetic" ? "합성 자료" : "제공된 내보내기"));
      const groups = groupsFor(report);
      replace("pa-select", ...groups.map(group => {
        const first = group.pitches[0], sit = first.pre.situation;
        const option = make("option", "", `${sit.inning}회 ${half(sit.half)} · PA ${first.at_bat_number} · ${text(first.pre.batter.name) || "타자 미제공"}`);
        option.value = group.key; return option;
      }));
      $("pa-select").value = view.pa_key;
      replace("pitch-buttons", ...report.pitches.filter(p => p.pa_key === view.pa_key).map(p => {
        const button = make("button", "pitch-button", `${p.pitch_number}구`);
        button.type = "button";
        button.setAttribute("aria-pressed", String(p.key === view.key));
        button.addEventListener("click", () => changeSelection(selectPitch(state, p.key)));
        return button;
      }));
      say("pitch-heading", `${s.inning}회 ${half(s.half)} · ${view.pitch_number}번째 투구`);
      for (const side of ["away", "home"]) replace(side + "-score",
        make("span", "team-short", team(side)), make("span", "", s[side + "_score"]));
      replace("count", make("span", "", `${s.balls} B · ${s.strikes} S · ${s.outs} O`), make("small", "", "볼 · 스트라이크 · 아웃"));
      const diamond = make("span", "base-diamond");
      for (const [name, bit] of [["first", 1], ["second", 2], ["third", 4]]) diamond.append(make("span", "base " + name + (s.bases & bit ? " on" : "")));
      const occupied = [1, 2, 3].filter(n => s.bases & (1 << (n - 1)));
      replace("base-state", diamond, make("span", "", occupied.length ? `주자 ${occupied.join("·")}루` : "주자 없음"));
      replace("people", ...[["투수", pre.pitcher, "hand"], ["타자", pre.batter, "side"]].map(([label, person, handKey]) => {
        const el = make("div", "person");
        el.append(make("small", "", label), make("strong", "", text(person.name) || "이름 미제공"),
          make("span", "", ({ R: "우", L: "좌", S: "스위치" })[person[handKey]] || "방향 미제공"));
        return el;
      }));
      const rec = pre.recommendation;
      const provenance = { asof_replay: "as-of 재생", captured_live: "원천 표기 captured_live · 실시간 검증 안 됨", absent: "추천 시점 근거 없음" };
      say("recommendation-context", provenance[rec.provenance] || "추천 시점 근거 없음");
      if (rec.status !== "ready") replace("candidate-list", make("div", "empty-recommendation",
        `${rec.status === "unsupported" ? "이 상황의 추천은 지원되지 않습니다." : "이 투구의 추천이 제공되지 않았습니다."}${text(rec.reason) ? " " + rec.reason : ""}`));
      else replace("candidate-list", ...rec.candidates.slice().sort((a, b) => a.rank - b.rank).map(c => {
        const card = make("article", "candidate"), detail = make("div", "");
        detail.append(make("strong", "", text(c.pitch_label) || c.pitch_type),
          make("p", "target-description", `${text(c.zone_label) || "구역 미제공"} · ${c.target ? `x ${fmt(c.target.x)} / z ${fmt(c.target.z)} ft` : "위치 없음"}`));
        const probability = make("div", "probability", c.selection_probability === null ? "미제공" : `${(c.selection_probability * 100).toFixed(1)}%`);
        probability.append(make("small", "", "구종 선택 비중"));
        card.append(make("span", "rank", c.rank), detail, probability); return card;
      }));
      renderPlot(view);
      replace("actual-content");
      $("reveal-button").disabled = view.revealed;
      say("reveal-button", view.revealed ? "공개됨" : "영상 없이 결과 공개");
      $("reveal-hint").hidden = view.revealed;
      if (view.revealed) {
        if (!view.actual) replace("actual-content", make("p", "actual-description", "이 투구의 실제 관측 데이터가 제공되지 않았습니다."));
        else {
          const a = view.actual, grid = make("div", "actual-grid");
          for (const [label, value] of [["실제 구종", text(a.pitch_label) || text(a.pitch_type) || "미제공"],
            ["구속", finite(a.speed_mph) ? `${a.speed_mph.toFixed(1)} mph` : "미제공"],
            ["관측 위치", finite(a.x) && finite(a.z) ? `${fmt(a.x)} / ${fmt(a.z)} ft` : "미제공"],
            ["투구 결과", text(a.result_label) || text(a.description) || "미제공"]]) {
            const stat = make("div", "actual-stat"); stat.append(make("small", "", label), make("strong", "", value)); grid.append(stat);
          }
          replace("actual-content", grid);
          if (text(a.play_text)) $("actual-content").append(make("p", "actual-description", a.play_text));
        }
      }
      replace("source-detail");
      for (const [label, value] of [["원문 SHA-256", report.source.sha256], ["입력 종류", report.source.input_kind],
        ["원천 종류", text(report.source.upstream_kind) || "미제공"], ["보고된 리비전", text(report.source.reported_revision) || "미제공"],
        ["프로파일", report.profile], ["투구 식별자", view.key],
        ["원천 기록 시각", text(rec.recorded_at) || "미제공"], ["추천 정책", rec.policy ? text(rec.policy.identity) || text(rec.policy.name) || "미제공" : "미제공"]]) {
        $("source-detail").append(make("dt", "", label), make("dd", "", value));
      }
      replace("report-warnings", ...(Array.isArray(report.warnings) ? report.warnings : []).filter(v => typeof v === "string").map(w => make("li", "", w)));
    }

    const load = createLoadCoordinator({
      clear() {
        state = null;
        mediaController.reset();
        $("report-content").hidden = true;
        $("empty-state").hidden = true;
        // Remove already revealed content immediately, including pending/failed replacements.
        for (const id of ["actual-content", "plot", "plot-legend", "setup-rail", "candidate-list", "source-detail", "report-warnings", "people", "pitch-buttons", "pa-select", "source-badges"]) replace(id);
        for (const id of ["game-meta", "game-title", "pitch-heading", "away-score", "home-score", "count", "base-state", "recommendation-context", "plot-clipping"]) say(id, "");
        $("load-status").classList.remove("error");
        say("load-status", "보고서를 확인하고 있습니다.");
      },
      commit(report) { say("load-status", `로컬 보고서 · ${report.pitches.length}개 투구 · 업로드하지 않습니다.`); changeSelection(initialState(report)); },
      fail(error) { $("empty-state").hidden = false; $("load-status").classList.add("error");
        say("load-status", `보고서를 열지 못했습니다. ${error instanceof Error ? error.message : "파일을 확인해주세요."}`); }
    });
    $("pa-select").addEventListener("change", event => { if (state) changeSelection(selectPA(state, event.target.value)); });
    $("reveal-button").addEventListener("click", () => { if (state) { state = reveal(state); render(); } });
    $("media-play").addEventListener("click", () => {
      const video = currentVideo, token = currentMediaToken;
      if (video && token !== null) mediaController.requestPlay(token, () => video.play());
    });
    $("media-retry").addEventListener("click", () => { if (state) changeSelection(selectPitch(state, state.key)); });
    $("report-file").addEventListener("change", event => {
      const file = event.target.files[0];
      if (!file) return;
      event.target.value = "";
      load(async () => { assert(file.size <= MAX_BYTES, "보고서는 최대 5 MiB까지 열 수 있습니다."); return parseBytes(await file.arrayBuffer()); });
    });
    load(async () => {
      const response = await fetch("./review-data.json", { cache: "no-store" });
      assert(response.ok, "review-data.json이 없습니다. ‘보고서 열기’에서 로컬 파일을 선택해주세요.");
      return parseBytes(await response.arrayBuffer());
    });
    (async () => {
      try {
        const response = await fetch("./review-media.json", { cache: "no-store" });
        if (response.status !== 404) {
          assert(response.ok, "영상 연결 정보를 읽지 못했습니다. 추천 검토와 직접 공개는 계속할 수 있습니다.");
          mediaManifest = validateMediaManifest(parseBytes(await response.arrayBuffer()));
        }
      } catch (_error) {
        mediaManifest = null;
        mediaManifestError = "영상 연결 정보를 사용할 수 없습니다. 추천 검토와 직접 공개는 계속할 수 있습니다.";
      }
      mediaManifestLoaded = true;
      if (state) prepareMedia();
    })();
  }
  function pointsForCoordinate(points, x, z) {
    return points.find(p => p.kind === "candidate" && p.x === x && p.z === z);
  }
  return { SCHEMA, PROFILE, MAX_BYTES, MEDIA_SCHEMA, SERVICE_ZONE_HALF_WIDTH, validateReport, viewFor, initialState, selectPitch, selectPA,
    reveal, groupsFor, plotModel, setupSummary, createLoadCoordinator, validateMediaManifest, mediaBinding,
    createMediaController, parseBytes, mount };
});

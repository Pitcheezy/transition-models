"use strict";
/* Pitcheezy 관전 화면 시안(A 범위, 2026-11-03) — 완료 경기 849843의 저장 재생. 바닐라 JS, 외부 자원 0.
 *
 * 존 좌표 변환은 Song 앱 고정 빌드(c47fe6cb) Zone.tsx와 같은 방향으로 맞췄다(투수 시점).
 *   - Zone.tsx 5행 주석 "Pitcher's view. Drawing mirrors the source plate_x"
 *   - 11행 PLATE_HALF = .83, 14행 U = 100, 16행 VIEW_X = -1, 17행 ux = VIEW_X * x * U, 18행 uz = -z * U
 *   - 창 여백은 Zone.tsx 13행 MARGIN.main { x .42, z .45 } + pad .16 — 이것은 Song의 **상세 시트(fullWindow) 창** 값이다.
 *     Song 라이브 메인 창은 12행 주석·23행대로 { x .12, z .24 } + pad .08로 더 좁다. 이 시안은 넓은 쪽(상세 시트 창)을 쓰되
 *     Song 시트처럼 선택 투구에 맞춰 창을 넓히지는 않는다(25~28행 include 처리 없음).
 *   - 22~33행 zoneWindow, 35~40행 place(창 밖이면 가장자리 표식), 45~53행 groupTargets — 규칙은 Song과 같다
 *   - GameScreen.tsx 124~131행: 우타자 실루엣은 화면 오른쪽, 좌타자는 왼쪽(669~670행 at-right/at-left)
 * 원본 좌표(actual.x, target.x)는 포수 기준 plate_x(오른쪽 +)이며 바꾸지 않는다. 화면에 그릴 때만 좌우를 뒤집는다.
 * zone_label의 '왼쪽·오른쪽'도 포수 기준이므로(예: 1구 후보 3 high_left, x = -0.553) 투수 시점 그림과는 좌우가 반대다.
 * 라벨은 데이터 그대로 두고 화면·범례에 '포수 기준'이라고 적는다.
 *
 * 모든 문구는 데이터 값으로만 만들고, 없는 값은 '자료 없음'으로 쓴다. 추측 값은 만들지 않는다.
 * 순수 함수는 Relay 객체로 내보내 node 검증 스크립트에서도 쓴다(DOM 부분은 브라우저에서만 실행).
 */
(function () {
  const V2 = typeof document !== "undefined" && !!document.documentElement.dataset.v2; // v2.html(Song 틀 시안, 11/9)만 true. v1(index.html)은 그대로. node(require 스모크)에서는 document가 없어 v1 값(독립 검토 2차 지적)
  const U = 100, VIEW_X = -1, PLATE_HALF = 0.83, MARGIN = V2 ? { x: 0.12, z: 0.24 } : { x: 0.42, z: 0.45 }, PAD = V2 ? 0.08 : 0.16; // v2: Song 라이브 메인 창(좁음, NOTES 44행)과 같은 여백 → 존 상자가 Song 틀과 같은 크기(약 150×160px)
  const SQ = 14, R_DOT = 11, RING = 4, ARROW = 7; // 그리기 단위(1 ft = 100). viewBox가 고정이라 화면 폭에 비례해 커진다
  const AUTO_SECONDS = 10, NA = "자료 없음";
  const KIND_WORD = { ball: "볼", strike: "스트라이크·파울", inplay: "타격", unknown: "결과 미확인" };
  /* 결과별 연출 분기(actual.description 8종, 2026-11-06). swing: 방망이 회전 여부. ball: 공이 도착한 뒤의 움직임.
   *   take 도착 뒤 사라짐 / block 포수 앞에서 아래로 짧게 튐 / miss 헛스윙(공은 그대로 도착) / foul 타자 쪽 뒤 위로 커지며 날아감
   *   / tip 파울팁: 방망이를 스치고 포수 앞으로 짧게 떨어짐(멀리 가지 않음, 11/6 검토 D-F4) / inplay 시청자 쪽으로 커지며 날아감 */
  const ANIM_OF = {
    ball: { swing: false, ball: "take" }, called_strike: { swing: false, ball: "take" },
    blocked_ball: { swing: false, ball: "block" },
    swinging_strike: { swing: true, ball: "miss" }, swinging_strike_blocked: { swing: true, ball: "miss" },
    foul: { swing: true, ball: "foul" }, foul_tip: { swing: true, ball: "tip" },
    hit_into_play: { swing: true, ball: "inplay" },
  };
  const KIND_OF = {
    ball: "ball", blocked_ball: "ball",
    called_strike: "strike", swinging_strike: "strike", swinging_strike_blocked: "strike", foul: "strike", foul_tip: "strike",
    hit_into_play: "inplay",
  };
  const BADGE_OF = { // 카드 결과 배지의 색 분류(문구는 event_label 그대로)
    strikeout: "out", field_out: "out", grounded_into_double_play: "out", double_play: "out", force_out: "out", sac_fly: "out", sac_bunt: "out",
    single: "hit", double: "hit", triple: "hit", home_run: "hit",
    walk: "onbase", intent_walk: "onbase", hit_by_pitch: "onbase", field_error: "onbase",
  };

  // ---------- 순수 함수 ----------
  const isNum = (v) => typeof v === "number" && Number.isFinite(v);
  const halfWord = (h) => (h === "Top" ? "초" : h === "Bot" || h === "Bottom" ? "말" : NA);
  const isTop = (h) => h === "Top";
  const kmh = (mph) => (isNum(mph) ? Math.round(mph * 1.609344) : null);
  const kindOf = (desc) => KIND_OF[desc] || "unknown";
  const text = (v) => (v === null || v === undefined || v === "" ? NA : String(v));
  const fixed = (v, d) => (isNum(v) ? v.toFixed(d) : NA);
  const pct = (p) => (isNum(p) ? Math.round(p * 100) + "%" : NA);
  const handWord = (h, role) => (h === "R" ? (role === "p" ? "우투" : "우타") : h === "L" ? (role === "p" ? "좌투" : "좌타") : h === "S" ? "양타" : "");
  const who = (person, role) => {
    if (!person || !person.name) return NA;
    const j = person.jersey !== null && person.jersey !== undefined && person.jersey !== "" ? ` (${person.jersey})` : "";
    const h = handWord(role === "p" ? person.hand : person.side, role);
    return person.name + j + (h ? ` ${h}` : "");
  };
  const clamp = (v, lo, hi) => Math.min(hi, Math.max(lo, v));
  const ux = (x) => VIEW_X * x * U;
  const uz = (z) => -z * U;

  function zoneWindow(bounds) {
    const xMax = PLATE_HALF + MARGIN.x, zLo = bounds.bottom - MARGIN.z, zHi = bounds.top + MARGIN.z;
    return { xMin: -xMax, xMax, zLo, zHi, vb: { x: -(xMax + PAD) * U, y: uz(zHi + PAD), w: 2 * (xMax + PAD) * U, h: (zHi - zLo + 2 * PAD) * U } };
  }
  /** 표식의 화면 위치. 창 밖이면 out=true, 창 가장자리로 잘라 그리고 dx/dz는 잘린 방향(화면 기준). Zone.tsx 35~40행과 같은 규칙. */
  function place(p, w) {
    const out = p.x < w.xMin || p.x > w.xMax || p.z < w.zLo || p.z > w.zHi;
    const x = Math.max(w.xMin, Math.min(w.xMax, p.x)), z = Math.max(w.zLo, Math.min(w.zHi, p.z));
    return { out, x: ux(x), y: uz(z), dx: VIEW_X * Math.sign(p.x - x), dz: Math.sign(p.z - z) };
  }
  /** 창 밖 표식은 창 안쪽으로 조금 들여 그린다(표식과 화살이 다 보이게). 존까지는 닿지 않게 여백 안으로 제한. */
  function inset(at, size) {
    if (!at.out) return at;
    const sx = Math.min(size + ARROW, MARGIN.x * U - 3), sz = Math.min(size + ARROW, MARGIN.z * U - 3);
    return { out: true, x: at.x - at.dx * sx, y: at.y + at.dz * sz, dx: at.dx, dz: at.dz };
  }
  /** 같은 목표 위치의 후보는 한 네모에 '1·3'처럼 모아 쓴다(Zone.tsx 45~53행과 같은 .05 ft 기준). */
  function groupTargets(cands) {
    const out = [];
    const sorted = (cands || []).filter((c) => c && c.target && isNum(c.target.x) && isNum(c.target.z)).sort((a, b) => a.rank - b.rank);
    for (const c of sorted) {
      const g = out.find((o) => Math.abs(o.x - c.target.x) < 0.05 && Math.abs(o.z - c.target.z) < 0.05);
      if (g) g.ranks.push(c.rank); else out.push({ x: c.target.x, z: c.target.z, ranks: [c.rank] });
    }
    return out;
  }
  /** 득점 타석: 다음 타석 첫 투구의 situation_before 점수(마지막 타석은 game 최종 점수)와 비교해 바뀐 타석.
   *  득점 시점도 구분한다 — mid: 타석 도중(투구 사이) 점수가 바뀐 첫 투구(그 공 던지기 전 상황이 직전 투구와 다름),
   *  atResult: 마지막 투구 전 점수와 타석 뒤 점수가 다름(= 타석 결과로 득점). 둘 다일 수도 있다. */
  function scoreChanges(data) {
    const pas = data.pas || [], P = data.pitches || [], out = new Map();
    const score = (p) => (p && p.situation_before && isNum(p.situation_before.away_score) && isNum(p.situation_before.home_score) ? [p.situation_before.away_score, p.situation_before.home_score] : null);
    const same = (a, b) => a[0] === b[0] && a[1] === b[1];
    for (let i = 0; i < pas.length; i++) {
      const a = pas[i], before = score(P[a.first_index]);
      if (!before) continue;
      let after;
      if (i + 1 < pas.length) { after = score(P[pas[i + 1].first_index]); if (!after) continue; }
      else after = [data.game.away_score, data.game.home_score];
      if (same(before, after)) continue;
      let mid = null, last = before;
      for (let k = a.first_index + 1; k <= a.last_index; k++) {
        const s = score(P[k]); if (!s) continue;
        if (!same(s, last) && !mid) mid = { index: k, pitch_number: P[k].pitch_number, from: last, to: s };
        last = s;
      }
      out.set(a.pa_key, { before, after, mid, atResult: !same(last, after) });
    }
    return out;
  }
  /** 득점 시점 문구: '2구 전(타석 중)' / '타석 결과' / 둘 다. 데이터로 시점을 알 수 없으면 '자료 없음'. */
  function scoreWhen(sc) {
    const parts = [];
    if (sc && sc.mid) parts.push(`${sc.mid.pitch_number}구 전(타석 중)`);
    if (sc && sc.atResult) parts.push("타석 결과");
    return parts.length ? parts.join(" + ") : NA;
  }
  /** 타순 도출: 공격 half별로 batting_order마다 첫 등장 타자 = 선발, 이후 다른 타자 = 교체. 투수는 상대 half에서 등장 순서대로. */
  function lineups(data) {
    const pas = data.pas || [];
    const side = (batHalfTop) => {
      const orders = new Map(), pitchers = [];
      for (const a of pas) {
        if (isTop(a.half) === batHalfTop) {
          const o = a.batting_order;
          if (!orders.has(o)) orders.set(o, []);
          const list = orders.get(o);
          if (!list.some((b) => b.id === a.batter.id)) list.push(a.batter);
        } else if (a.pitcher && !pitchers.some((p) => p.id === a.pitcher.id)) pitchers.push(a.pitcher);
      }
      return { orders: [...orders.entries()].sort((x, y) => x[0] - y[0]).map(([order, batters]) => ({ order, starter: batters[0], subs: batters.slice(1) })), pitchers };
    };
    return { away: side(true), home: side(false) };
  }
  /** 결과별 연출 계획(순수 함수, node 검증에도 씀). 자료가 없을 때의 기본값: 공 비행 700ms, 타구 상승은 '조금 위', 타구 650ms, 화면 밖으로 나가지 않음.
   *  자막은 result_label(타구는 event_label 우선), 없으면 '자료 없음'. 작은 글자(sub)는 call_label이 자막과 다를 때만(예: '삼진' 뒤 '헛스윙', '볼넷' 뒤 '볼'). 값을 만들지 않는다.
   *  out(화면 위로 완전히 나감)은 비거리가 아니라 실제 결과 event === "home_run"일 때만: 300 ft 넘는 외야 뜬공 아웃·2루타가 홈런처럼 보이지 않게(11/6 검토 D-F4). 깊은 타구도 세로 방향은 발사각 구간을 그대로 따른다. */
  function animPlan(actual) {
    const a = actual || {}, t = a.tracking || {}, spec = ANIM_OF[a.description] || null;
    const plan = {
      kind: spec ? spec.ball : "take", swing: spec ? spec.swing : false, known: !!spec,
      flightMs: isNum(a.speed_mph) ? clamp(560 + (97.6 - a.speed_mph) * 10, 560, 900) : 700,
      caption: text(a.result_label), sub: null,
    };
    if (a.call_label && a.call_label !== plan.caption) plan.sub = a.call_label;
    if (plan.kind === "inplay") {
      const la = t.launch_angle_deg, ev = t.exit_velocity_mph, dist = t.distance_feet;
      plan.caption = a.event_label || text(a.result_label); plan.sub = null;
      plan.lift = isNum(la) ? (la > 25 ? "high" : la >= 10 ? "mid" : "flat") : "mid";
      plan.out = a.event === "home_run"; // 자료의 실제 결과. 비거리는 참고 값으로만 남긴다(깊은 아웃은 lift로 충분)
      plan.deep = isNum(dist) && dist >= 300;
      plan.hitMs = isNum(ev) ? clamp(800 - (ev - 30) * 350 / 78, 450, 800) : 650;
    }
    return plan;
  }
  /** 글자 폭 어림(그리기 단위). getBBox가 0을 돌려주는 숨겨진 탭 등에서만 쓴다: 한글 1em, 공백 .3em, 그 밖(숫자, 라틴) .58em. */
  function textWidthGuess(str, em) {
    let w = 0;
    for (const ch of String(str || "")) w += /[\u3131-\uD79D]/.test(ch) ? em : /\s/.test(ch) ? em * 0.3 : em * 0.58;
    return w;
  }
  /** 결과 자막 자리(순수 함수). 창 안 여섯 자리(아래 가운데, 왼쪽, 오른쪽, 위 가운데, 왼쪽, 오른쪽) 중 표식(obs: {x, y, r})과 겹치지 않는 첫 자리.
   *  tw 글자 폭, h 자막 높이, padX 좌우 여백, gap 창 가장자리와의 간격(모두 그리기 단위). 여섯 자리가 전부 겹치면 가장 적게 겹치는 자리와 겹친 수(overlap)를 돌려준다(이 경기 자료에서는 0회, 11/6 검토 C-F1). */
  function captionSpot(w, tw, h, obs, padX, gap) {
    const half = tw / 2 + padX, lim = w.xMax * U - half - 2; // 자막 rect가 창 안에 머무는 최대 가로 이동
    const xs = lim > 0 ? [0, -lim, lim] : [0];
    const ys = [uz(w.zLo) - gap - h / 2, uz(w.zHi) + gap + h / 2];
    let best = null;
    for (const y of ys) for (const x of xs) {
      const n = (obs || []).filter((o) => o.x + o.r > x - half && o.x - o.r < x + half && o.y + o.r > y - h / 2 && o.y - o.r < y + h / 2).length;
      if (!best || n < best.overlap) best = { x, y, overlap: n };
      if (n === 0) return best;
    }
    return best;
  }
  const Relay = { U, VIEW_X, PLATE_HALF, MARGIN, PAD, NA, halfWord, kmh, kindOf, text, fixed, pct, who, ux, uz, zoneWindow, place, inset, groupTargets, scoreChanges, scoreWhen, lineups, animPlan, ANIM_OF, captionSpot, textWidthGuess };
  if (typeof module === "object" && module && module.exports) { module.exports = Relay; return; }
  if (typeof document === "undefined") return;

  // ---------- DOM ----------
  const $ = (id) => document.getElementById(id);
  const SVG_NS = "http://www.w3.org/2000/svg";
  function el(tag, attrs, ...kids) {
    const n = document.createElement(tag);
    for (const k in attrs || {}) { const v = attrs[k]; if (v === null || v === undefined || v === false) continue; if (k === "class") n.className = v; else if (k === "text") n.textContent = v; else n.setAttribute(k, v === true ? "" : v); }
    for (const kid of kids) if (kid !== null && kid !== undefined) n.append(kid);
    return n;
  }
  function svg(tag, attrs, textContent) {
    const n = document.createElementNS(SVG_NS, tag);
    for (const k in attrs || {}) if (attrs[k] !== null && attrs[k] !== undefined) n.setAttribute(k, attrs[k]);
    if (textContent !== undefined) n.textContent = textContent;
    return n;
  }
  const reduceMotion = () => window.matchMedia && window.matchMedia("(prefers-reduced-motion: reduce)").matches;

  const S = { data: null, pas: [], P: [], paOf: new Map(), scoring: new Map(), sel: -1, inTab: null, rows: [], cards: new Map(), auto: false, left: AUTO_SECONDS, timer: null, view: "relay", note: null, said: "자동 진행 꺼짐", animOn: true, anim: { raf: 0, raf3d: 0, timers: [] } }; // anim.raf 공 연출 루프, anim.raf3d 3D 타자 스윙 루프(둘 다 cancelAnim이 끊는다)

  fetch("./data/849843.json", { cache: "no-store" })
    .then((r) => { if (!r.ok) throw new Error("HTTP " + r.status); return r.json(); })
    .then(init)
    .catch((err) => { $("load-state").textContent = `경기 자료를 불러오지 못했습니다 (${err && err.message ? err.message : err}). 로컬 서버(http://localhost:8790/relay/)에서 열어 주세요.`; });

  function init(data) {
    if (!data || !Array.isArray(data.pitches) || !Array.isArray(data.pas) || !data.game) { $("load-state").textContent = "경기 자료 형식이 예상과 다릅니다 (pitches/pas/game 없음)"; return; }
    S.data = data; S.P = data.pitches; S.pas = data.pas;
    for (const a of S.pas) S.paOf.set(a.pa_key, a);
    S.scoring = scoreChanges(data);
    const g = data.game;
    $("s-away-abbr").textContent = text(g.away_abbr); $("s-home-abbr").textContent = text(g.home_abbr);
    const tag = $("hdr-tag"); tag.textContent = "저장 경기 재생"; // 팀 부분(.r-tag-game)은 항상 둘째 줄
    tag.append(el("span", { class: "r-tag-game", text: `${text(g.away_abbr)} @ ${text(g.home_abbr)}` }));
    buildInningTabs(); buildCards(); buildLineup(); buildRecord(); buildFooter();
    wireTopTabs(); wireAuto(); wireNav();
    $("load-state").hidden = true; $("panel-relay").hidden = false;
    selectPitch(0, { scroll: false }); // 처음 열면 1회 초 1구
  }

  // ----- 3. 점수 띠 -----
  function renderScore(p, pa) {
    const s = p.situation_before || {};
    $("s-away").textContent = text(s.away_score); $("s-home").textContent = text(s.home_score);
    $("s-inning").textContent = isNum(s.inning) ? `${s.inning}회 ${halfWord(s.half)}` : NA;
    const count = $("s-count"); count.textContent = "";
    for (const [label, word, n, max] of [["B", "볼", s.balls, 3], ["S", "스트라이크", s.strikes, 2], ["O", "아웃", s.outs, 2]]) {
      // role=img + aria-label: 글자 'B'와 점은 보조기기에 안 읽히고 '볼 1'처럼 개수가 읽힌다
      const row = el("span", { class: "c-row", role: "img", "aria-label": `${word} ${isNum(n) ? n : NA}` }, el("b", { text: label, "aria-hidden": "true" }));
      for (let i = 0; i < max; i++) row.append(el("i", { class: isNum(n) && i < n ? "on" : "", "aria-hidden": "true" }));
      count.append(row);
    }
    const r = s.runners || {};
    $("d-1").classList.toggle("on", r.first === true); $("d-2").classList.toggle("on", r.second === true); $("d-3").classList.toggle("on", r.third === true);
    const on = ["first", "second", "third"].filter((k) => r[k] === true).map((k) => ({ first: "1루", second: "2루", third: "3루" })[k]);
    $("diamond-title").textContent = on.length ? `주자 ${on.join(", ")}` : "주자 없음";
    $("w-pitcher").textContent = who(p.pitcher, "p"); $("w-batter").textContent = who(p.batter, "b");
    const c = p.context_before, ctx = $("w-ctx"); ctx.textContent = ""; // 타자 줄, 투수 줄을 따로(span은 block)
    if (c && c.batter) ctx.append(el("span", { text: `타자 오늘 ${text(c.batter.at_bats)}타수 ${text(c.batter.hits)}안타` }));
    if (c && c.pitcher) ctx.append(el("span", { text: `투수 ${text(c.pitcher.pitches)}구, 탈삼진 ${text(c.pitcher.strikeouts)}, 자책 ${text(c.pitcher.earned_runs)}` }));
    if (!ctx.childElementCount) ctx.textContent = "경기 중 누적 기록 " + NA;
  }

  // ----- 4. 존 그림 -----
  function renderZone(p, pa) {
    cancelAnim(); // 진행 중인 연출(rAF, 스윙 타이머)을 끊고 아래에서 SVG를 통째로 다시 그린다
    const bounds = S.data.zone_bounds && isNum(S.data.zone_bounds.top) && isNum(S.data.zone_bounds.bottom) ? S.data.zone_bounds : { bottom: 1.6, top: 3.3899 };
    const w = zoneWindow(bounds);
    const root = $("zone"); root.textContent = "";
    root.setAttribute("viewBox", `${w.vb.x} ${w.vb.y} ${w.vb.w} ${w.vb.h}`); root.setAttribute("preserveAspectRatio", "xMidYMid meet");
    const left = -PLATE_HALF * U, right = PLATE_HALF * U, top = uz(bounds.top), bottom = uz(bounds.bottom);
    root.append(svg("rect", { class: "z-outside", x: -w.xMax * U, y: uz(w.zHi), width: 2 * w.xMax * U, height: (w.zHi - w.zLo) * U }));
    root.append(svg("rect", { class: "z-box", x: left, y: top, width: right - left, height: bottom - top }));
    for (const i of [1, 2]) {
      root.append(svg("line", { class: "z-grid", x1: left + (right - left) * i / 3, x2: left + (right - left) * i / 3, y1: top, y2: bottom }));
      root.append(svg("line", { class: "z-grid", y1: top + (bottom - top) * i / 3, y2: top + (bottom - top) * i / 3, x1: left, x2: right }));
    }
    const parts = [], obs = []; // obs: 결과 자막이 피해야 할 표식 자리(추천 네모, 번호 원)
    // 추천 후보: rank 숫자가 든 둥근 네모 (target = 과거 투구 분포의 대략 위치, 참고)
    const rec = p.rec || {};
    const groups = rec.status === "ready" ? groupTargets(rec.candidates) : [];
    for (const g of groups) {
      const at = inset(place(g, w), SQ), label = g.ranks.join("·");
      const node = svg("g", { class: `z-rec r${g.ranks[0]}${at.out ? " out" : ""}` });
      node.append(svg("rect", { x: at.x - SQ, y: at.y - SQ, width: 2 * SQ, height: 2 * SQ, rx: 5 }));
      if (at.out) node.append(arrow(at, SQ));
      node.append(svg("text", { x: at.x, y: at.y + 5, "text-anchor": "middle" }, label));
      node.append(svg("title", null, `추천 ${label}순위 위치(참고), 가로 ${g.x.toFixed(2)} ft, 높이 ${g.z.toFixed(2)} ft, 포수 기준${at.out ? ", 화면 밖" : ""}`));
      root.append(node); obs.push({ x: at.x, y: at.y, r: SQ });
      parts.push(`추천 ${label}순위 네모${at.out ? "(화면 밖)" : ""}`);
    }
    // 이번 타석의 투구들: pitch_number 번호 원. 선택 투구는 맨 위에 라임 링
    const list = [];
    if (pa) for (let i = pa.first_index; i <= pa.last_index; i++) if (S.P[i]) list.push(S.P[i]);
    const ordered = list.filter((q) => q.index !== p.index).concat(list.filter((q) => q.index === p.index));
    let drawn = 0, selAt = null;
    for (const q of ordered) {
      const a = q.actual || {};
      if (!isNum(a.x) || !isNum(a.z)) continue;
      const kind = kindOf(a.description), selected = q.index === p.index;
      const at = inset(place({ x: a.x, z: a.z }, w), R_DOT);
      if (selected) selAt = at; // 연출의 공이 도착하는 자리 = 선택 투구 표식 자리
      const node = svg("g", { class: `z-dot ${kind}${selected ? " sel" : ""}${at.out ? " out" : ""}` });
      node.append(svg("circle", { cx: at.x, cy: at.y, r: R_DOT }));
      if (at.out) node.append(arrow(at, R_DOT));
      if (selected) node.append(svg("circle", { class: "z-ring", cx: at.x, cy: at.y, r: R_DOT + RING }));
      node.append(svg("text", { x: at.x, y: at.y + 4.5, "text-anchor": "middle" }, String(q.pitch_number)));
      node.append(svg("title", null, `${q.pitch_number}구 ${text(a.pitch_label)}, ${KIND_WORD[kind]}, 가로 ${a.x.toFixed(2)} ft, 높이 ${a.z.toFixed(2)} ft, 포수 기준${at.out ? ", 화면 밖" : ""}`));
      root.append(node); drawn++; obs.push({ x: at.x, y: at.y, r: R_DOT + (selected ? RING : 0) });
    }
    const side = p.batter && (p.batter.side === "L" || p.batter.side === "R") ? p.batter.side : null;
    $("bat-left").hidden = side !== "L"; $("bat-right").hidden = side !== "R";
    b3Show(side); // 3D 타자가 붙어 있으면 서 있는 쪽 띠로 옮기고 idle 자세. 없으면 위 SVG 타자 그대로
    $("legend-view").textContent = `투수 시점, ${side === "L" ? "좌타자는 화면 왼쪽" : side === "R" ? "우타자는 화면 오른쪽" : "타석 방향 " + NA}`;
    root.setAttribute("aria-label", `투수 시점 스트라이크존${parts.length ? ": " + parts.join(", ") : ""}. 이번 타석 투구 ${drawn}개, 선택 ${p.pitch_number}구`);
    // 결과별 연출 오버레이(맨 위, 보조기기에는 숨김). 선택 투구에 위치 값이 없으면 공은 그리지 않고 자막만 그린다
    const layer = svg("g", { class: "z-anim", "aria-hidden": "true" });
    root.append(layer);
    playAnim(p, w, selAt, layer, side, obs);
  }
  function arrow(at, r) { // 창 밖 표식의 바깥쪽 화살(작은 삼각형)
    const n = Math.hypot(at.dx, at.dz) || 1, ax = at.dx / n, ay = -at.dz / n, L = r + ARROW, hw = ARROW * 0.75;
    const bx = at.x + ax * (r + 0.5), by = at.y + ay * (r + 0.5);
    return svg("path", { class: "z-arrow", d: `M${at.x + ax * L} ${at.y + ay * L} L${bx - ay * hw} ${by + ax * hw} L${bx + ay * hw} ${by - ax * hw}Z` });
  }

  // ----- 5. 투구 패널 -----
  function renderPanel(p, pa) {
    $("pp-title").textContent = `${text(p.pitch_number)}구를 던지기 전 추천`;
    const recs = $("pp-recs"); recs.textContent = "";
    const rec = p.rec || null;
    if (rec && rec.status === "ready" && Array.isArray(rec.candidates) && rec.candidates.length) {
      const row = el("div", { class: "chips" });
      for (const c of [...rec.candidates].sort((a, b) => a.rank - b.rank)) {
        row.append(el("div", { class: `chip r${c.rank}` },
          el("i", { class: "rk", text: String(c.rank) }),
          el("span", { class: "chip-body" }, el("b", { text: text(c.pitch_label) }), el("small", { text: text(c.zone_label) })),
          el("span", { class: "share", text: pct(c.detail && c.detail.probability) })));
      }
      recs.append(row);
      recs.append(el("p", { class: "rec-meta", text: `위치 이름의 왼쪽, 오른쪽은 포수 기준입니다(그림은 투수 시점이라 좌우 반대). 숫자는 정책 선택 비중(%)입니다. 기록 ${text(rec.recorded_at)}${rec.policy && rec.policy.name ? ", 정책 " + rec.policy.name : ""}.` }));
    } else {
      const why = rec ? text(rec.reason) : NA;
      recs.append(el("p", { class: "rec-none" }, el("b", { text: "이 투수는 추천이 없습니다." }), ` 사유: ${why}${rec && rec.status ? " (상태 " + rec.status + ")" : ""}`));
    }
    const a = p.actual || {}, t = a.tracking || {}, dl = $("pp-actual"); dl.textContent = "";
    const row = (k, v) => { dl.append(el("dt", { text: k })); dl.append(el("dd", { text: v })); };
    row("구종", a.pitch_label ? `${a.pitch_label}${a.pitch_type ? " (" + a.pitch_type + ")" : ""}` : NA);
    row("속도", isNum(a.speed_mph) ? `${kmh(a.speed_mph)} km/h (${a.speed_mph} mph)` : NA);
    row("판정과 결과", a.call_label || a.result_label ? (a.result_label && a.result_label !== a.call_label ? `판정 ${text(a.call_label)}, 결과 ${a.result_label}` : text(a.call_label || a.result_label)) : NA);
    row("위치", `${text(a.zone_label)} (포수 기준)${isNum(a.x) && isNum(a.z) ? `, 가로 ${a.x.toFixed(2)} ft, 높이 ${a.z.toFixed(2)} ft` : ""}`);
    row("회전수", isNum(t.spin_rate_rpm) ? `${t.spin_rate_rpm} rpm` : NA);
    row("익스텐션", isNum(t.extension_feet) ? `${t.extension_feet.toFixed(1)} ft` : NA);
    if (isNum(t.exit_velocity_mph) || isNum(t.launch_angle_deg) || isNum(t.distance_feet)) {
      row("타구", [
        isNum(t.exit_velocity_mph) ? `타구 속도 ${kmh(t.exit_velocity_mph)} km/h (${t.exit_velocity_mph} mph)` : `타구 속도 ${NA}`,
        isNum(t.launch_angle_deg) ? `발사각 ${t.launch_angle_deg}°` : `발사각 ${NA}`,
        isNum(t.distance_feet) ? `비거리 ${Math.round(t.distance_feet * 0.3048)} m (${t.distance_feet} ft)` : `비거리 ${NA}`,
      ].join(", "));
    } else row("타구", NA);
    if (a.event_label) row("타석 결과", `${a.event_label}${pa && pa.result_text ? ", " + pa.result_text : ""}`);
    $("btn-prev").disabled = p.index <= 0; $("btn-next").disabled = p.index >= S.P.length - 1;
  }

  // ----- 6. 이닝 탭 -----
  function buildInningTabs() {
    const box = $("intabs"); box.textContent = "";
    const innings = (S.data.linescore && Array.isArray(S.data.linescore.innings) ? S.data.linescore.innings.map((i) => i.inning) : [...new Set(S.pas.map((a) => a.inning))]).filter(isNum);
    const keys = [["score", `득점 (${S.scoring.size})`], ...innings.map((n) => [String(n), `${n}회`])];
    for (const [key, label] of keys) {
      const b = el("button", { type: "button", role: "tab", id: "intab-" + key, "aria-selected": "false", "aria-controls": "pa-panel", tabindex: "-1", "data-tab": key, text: label });
      b.addEventListener("click", () => setInningTab(key, { focus: false }));
      box.append(b);
    }
    box.addEventListener("keydown", (e) => arrowTabs(e, box, (btn) => setInningTab(btn.dataset.tab, { focus: true })));
  }
  function setInningTab(key, opts) {
    S.inTab = key;
    const box = $("intabs");
    for (const b of box.querySelectorAll("[role=tab]")) {
      const on = b.dataset.tab === key; b.setAttribute("aria-selected", on ? "true" : "false"); b.tabIndex = on ? 0 : -1;
      if (on) $("pa-panel").setAttribute("aria-labelledby", b.id);
      if (on && opts && opts.focus) b.focus();
      if (on) { // 탭 줄 안에서만 가로로 스크롤(scrollIntoView는 페이지를 세로로도 움직이므로 쓰지 않음)
        const bx = b.offsetLeft, bw = b.offsetWidth, sl = box.scrollLeft, cw = box.clientWidth, behavior = reduceMotion() ? "auto" : "smooth";
        if (bx < sl + 8) box.scrollTo({ left: Math.max(0, bx - 16), behavior });
        else if (bx + bw > sl + cw - 8) box.scrollTo({ left: bx + bw - cw + 16, behavior });
      }
    }
    for (const li of $("pa-list").children) {
      if (li.classList.contains("half-head")) li.hidden = key === "score" || li.dataset.inning !== key;
      else li.hidden = key === "score" ? li.dataset.scoring !== "1" : li.dataset.inning !== key;
    }
  }
  function arrowTabs(e, box, activate) {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight" && e.key !== "Home" && e.key !== "End") return;
    const tabs = [...box.querySelectorAll("[role=tab]")], i = tabs.indexOf(document.activeElement);
    if (i < 0) return;
    e.preventDefault();
    const j = e.key === "Home" ? 0 : e.key === "End" ? tabs.length - 1 : (i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length;
    activate(tabs[j]);
  }

  // ----- 7. 타석 카드 -----
  function buildCards() {
    const ol = $("pa-list"); ol.textContent = ""; S.rows = []; S.cards.clear();
    const g = S.data.game; let lastHalf = null;
    for (const a of S.pas) {
      const halfKey = `${a.inning}:${a.half}`;
      if (halfKey !== lastHalf) {
        lastHalf = halfKey;
        ol.append(el("li", { class: "half-head", "data-inning": String(a.inning), role: "presentation", text: `${a.inning}회 ${halfWord(a.half)}, ${text(isTop(a.half) ? g.away_abbr : g.home_abbr)} 공격` }));
      }
      const sc = S.scoring.get(a.pa_key);
      const card = el("li", { class: "pa-card", "data-inning": String(a.inning), "data-scoring": sc ? "1" : "0", id: "pa-" + String(a.pa_key).replace(/[^0-9A-Za-z_-]/g, "_") });
      const badge = el("span", { class: `badge ${BADGE_OF[a.event] || "other"}`, text: text(a.event_label) });
      card.append(el("div", { class: "pa-head" },
        el("span", { class: "pa-order", text: isNum(a.batting_order) ? `${a.batting_order}번` : NA }),
        el("b", { class: "pa-batter", text: a.batter && a.batter.name ? a.batter.name : NA }),
        el("small", { class: "pa-sub", text: a.batter ? `${a.batter.jersey !== null && a.batter.jersey !== undefined ? "(" + a.batter.jersey + ") " : ""}${handWord(a.batter.side, "b")}` : "" }),
        badge));
      card.append(el("p", { class: "pa-result", text: `${a.inning}회 ${halfWord(a.half)}, ${text(a.result_text)}, ${text(a.pitch_count)}구, 투수 ${a.pitcher && a.pitcher.name ? a.pitcher.name : NA}` }));
      if (sc) card.append(el("p", { class: "pa-score", text: `득점 ${text(g.away_abbr)} ${sc.before[0]} : ${sc.before[1]} ${text(g.home_abbr)} → ${sc.after[0]} : ${sc.after[1]}, 득점 시점 ${scoreWhen(sc)}` }));
      const rows = el("ol", { class: "pitch-rows", role: "list" });
      for (let i = a.first_index; i <= a.last_index; i++) {
        const q = S.P[i]; if (!q) continue;
        const act = q.actual || {}, kind = kindOf(act.description);
        const btn = el("button", { type: "button", class: "prow", "data-index": String(i), "aria-pressed": "false" },
          el("i", { class: `g1 ${kind}`, text: text(q.pitch_number) }),
          el("b", { text: text(act.pitch_label) }),
          el("small", { text: isNum(act.speed_mph) ? `${kmh(act.speed_mph)} km/h` : NA }),
          el("span", { class: "res", text: text(act.result_label) }));
        btn.addEventListener("click", () => selectPitch(i, { scroll: false }));
        rows.append(el("li", null, btn)); S.rows[i] = btn;
      }
      card.append(rows); ol.append(card); S.cards.set(a.pa_key, card);
    }
  }

  // ----- 선택 -----
  function selectPitch(i, opts) {
    if (!S.P[i]) return;
    const prev = S.rows[S.sel]; if (prev) { prev.setAttribute("aria-pressed", "false"); const c = prev.closest(".pa-card"); if (c) c.classList.remove("is-current"); }
    S.sel = i;
    const p = S.P[i], pa = S.paOf.get(p.pa_key) || null;
    renderScore(p, pa); renderZone(p, pa); renderPanel(p, pa);
    const row = S.rows[i];
    if (row) {
      row.setAttribute("aria-pressed", "true"); const card = row.closest(".pa-card"); if (card) card.classList.add("is-current");
      if (card && card.hidden) setInningTab(String(p.inning), { focus: false }); // 보이지 않는 이닝이면 그 이닝 탭으로
      if (opts && opts.scroll) scrollToRow(row, card, opts.scroll === "force");
    }
    if (S.inTab === null) setInningTab(String(p.inning), { focus: false });
    S.note = null; // 투구를 새로 고르면 stopAuto가 남긴 안내 문구는 지운다
    if (S.auto) S.left = AUTO_SECONDS;
    renderAuto();
  }
  /** 선택 줄로 스크롤 — 타석 목록이 이미 화면에 보일 때만(목록을 읽는 중일 때 따라감). 처음 화면처럼 목록이 화면 아래에 있으면
   *  페이지를 내리지 않아 존, 점수 띠, 이전/다음 버튼이 그대로 보인다. force(기록 탭 '그 타석 보기')는 그 타석 카드 머리로 이동. */
  function scrollToRow(row, card, force) {
    if (!row.scrollIntoView) return;
    const behavior = reduceMotion() ? "auto" : "smooth";
    if (force) { (card || row).scrollIntoView({ block: "start", behavior }); return; }
    const lr = $("pa-list").getBoundingClientRect();
    if (lr.top < window.innerHeight && lr.bottom > 0) row.scrollIntoView({ block: "nearest", behavior });
  }
  function wireNav() {
    $("btn-prev").addEventListener("click", () => selectPitch(S.sel - 1, { scroll: true }));
    $("btn-next").addEventListener("click", () => selectPitch(S.sel + 1, { scroll: true }));
  }

  // ----- 2. 자동 진행 -----
  /** 자동 진행이 멈춰야 하는 상태: 브라우저 탭이 가려졌거나, 상단 탭이 중계가 아닐 때(보이지 않는 사이 넘어가지 않게). */
  const autoPaused = () => document.hidden || S.view !== "relay";
  /** 보조기기 안내(role=status)는 켜짐, 꺼짐, 일시정지, 종료처럼 상태가 바뀔 때만 한 번. 매초 바뀌는 카운트다운은 aria-hidden 요소에만 쓴다. */
  function announce(msg) { if (S.said === msg) return; S.said = msg; $("auto-status").textContent = msg; }
  function renderAuto() {
    const sw = $("auto-switch"), c = $("auto-count");
    sw.setAttribute("aria-checked", S.auto ? "true" : "false");
    if (!S.auto) { c.textContent = S.note || "꺼짐"; announce(S.note ? `자동 진행 꺼짐. ${S.note}` : "자동 진행 꺼짐"); }
    else if (S.sel >= S.P.length - 1) { c.textContent = "마지막 투구"; announce("마지막 투구"); }
    else if (autoPaused()) { c.textContent = "다른 화면, 일시정지"; announce("자동 진행 일시정지"); }
    else { c.textContent = `${S.left}초 후 다음 투구`; announce(`자동 진행 켜짐, ${AUTO_SECONDS}초마다 다음 투구`); }
  }
  function stopAuto(msg) { S.auto = false; if (S.timer) clearInterval(S.timer); S.timer = null; S.note = msg || null; renderAuto(); }
  function wireAuto() {
    $("auto-switch").addEventListener("click", () => {
      if (S.auto) { stopAuto(); return; }
      if (S.sel >= S.P.length - 1) { stopAuto("마지막 투구, 앞에서 다시 고르세요"); return; }
      S.auto = true; S.left = AUTO_SECONDS; S.note = null; renderAuto();
      S.timer = setInterval(() => {
        if (!S.auto) return;
        if (autoPaused()) { renderAuto(); return; } // 탭이 가려지거나 라인업·기록 탭이면 멈춤(건너뛰기 방지), 돌아오면 이어감
        S.left -= 1;
        if (S.left > 0) { renderAuto(); return; }
        if (S.sel >= S.P.length - 1) { stopAuto("마지막 투구, 자동 진행 종료"); return; }
        selectPitch(S.sel + 1, { scroll: true });
        if (S.sel >= S.P.length - 1) stopAuto("마지막 투구, 자동 진행 종료");
      }, 1000);
    });
    document.addEventListener("visibilitychange", () => { if (S.auto) renderAuto(); });
  }

  // ----- 1. 상단 탭 -----
  function wireTopTabs() {
    const box = document.querySelector(".toptabs");
    const tabs = [...box.querySelectorAll("[role=tab]")];
    const show = (view, focus) => {
      S.view = view;
      for (const t of tabs) { const on = t.dataset.view === view; t.setAttribute("aria-selected", on ? "true" : "false"); t.tabIndex = on ? 0 : -1; if (on && focus) t.focus(); }
      for (const v of ["relay", "lineup", "record"]) $("panel-" + v).hidden = v !== view;
      if (S.auto) renderAuto(); // 라인업·기록 탭이면 '일시정지' 표시, 중계로 돌아오면 카운트다운 재개
      if (B3.api && !(S.anim.raf3d)) B3.api.reset(b3Still()); // 3D 대기 반복은 중계 화면에서만(다른 탭에선 정지 자세, 돌아오면 다시 반복). 연출 중이면 건드리지 않는다(끝나면 reset이 따로 온다)
    };
    for (const t of tabs) t.addEventListener("click", () => show(t.dataset.view, false));
    box.addEventListener("keydown", (e) => arrowTabs(e, box, (t) => show(t.dataset.view, true)));
  }

  // ----- 라인업 탭 -----
  function buildLineup() {
    const root = $("lineup-root"); root.textContent = "";
    const g = S.data.game, L = lineups(S.data);
    const pp = g.probable_pitchers || {};
    for (const [key, teamName, abbr, side, role] of [["away", g.away_team, g.away_abbr, L.away, "원정"], ["home", g.home_team, g.home_abbr, L.home, "홈"]]) {
      const sec = el("section", { class: "team-card", "aria-label": `${text(abbr)} 라인업` });
      sec.append(el("h2", null, el("span", { class: "abbr", text: text(abbr) }), ` ${text(teamName)} `, el("small", { text: role })));
      const ol = el("ol", { class: "order", role: "list" });
      for (const o of side.orders) {
        const li = el("li", null, el("span", { class: "num", text: `${o.order}번` }), el("span", { class: "name" }, el("b", { text: text(o.starter && o.starter.name) }), el("small", { text: o.starter ? ` ${o.starter.jersey !== null && o.starter.jersey !== undefined ? "(" + o.starter.jersey + ") " : ""}${handWord(o.starter.side, "b")}` : "" })));
        for (const s of o.subs) li.append(el("span", { class: "sub", text: `교체: ${text(s.name)}${s.jersey !== null && s.jersey !== undefined ? " (" + s.jersey + ")" : ""} ${handWord(s.side, "b")}` }));
        ol.append(li);
      }
      if (!side.orders.length) ol.append(el("li", { text: NA }));
      sec.append(ol);
      const probable = pp[key] && pp[key].name ? `예고 선발은 ${pp[key].name}.` : null;
      sec.append(el("p", { class: "pitchers" }, el("b", { text: "투수(등판 순)" }), " ", side.pitchers.length ? side.pitchers.map((p) => who(p, "p")).join(", ") + "." : NA, probable ? el("span", { class: "probable", text: probable }) : null));
      root.append(sec);
    }
  }

  // ----- 기록 탭 -----
  function buildRecord() {
    const root = $("record-root"); root.textContent = "";
    const g = S.data.game, ls = S.data.linescore || {};
    const status = g.status === "final" ? "경기 종료" : text(g.status_text || g.status);
    root.append(el("p", { class: "game-meta" },
      el("span", { class: "final", text: `${text(g.away_team)} ${text(g.away_score)} : ${text(g.home_score)} ${text(g.home_team)}` }),
      el("span", { text: `${status}, ${text(g.date_kst)} (KST), ${text(g.venue)}` })));
    const innings = Array.isArray(ls.innings) ? ls.innings : [];
    const table = el("table", { class: "linescore" }), thead = el("thead"), tbody = el("tbody");
    const hr = el("tr", null, el("th", { scope: "col", text: "팀" }));
    for (const i of innings) hr.append(el("th", { scope: "col", text: String(i.inning) }));
    for (const k of ["R", "H", "E", "BB"]) hr.append(el("th", { scope: "col", class: "tot", text: k }));
    thead.append(hr);
    const cell = (v) => (v === null || v === undefined ? "–" : String(v));
    for (const [key, abbr] of [["away", g.away_abbr], ["home", g.home_abbr]]) {
      const tr = el("tr", null, el("th", { scope: "row", text: text(abbr) }));
      for (const i of innings) tr.append(el("td", { text: cell(i[key]) }));
      const t = (ls.teams && ls.teams[key]) || {};
      for (const k of ["runs", "hits", "errors", "bb_hbp"]) tr.append(el("td", { class: "tot", text: cell(t[k]) }));
      tbody.append(tr);
    }
    table.append(el("caption", { text: "이닝별 득점. R 득점, H 안타, E 실책, BB 볼넷과 사구." }), thead, tbody);
    root.append(el("div", { class: "table-wrap" }, table));
    const notes = [];
    const last = innings[innings.length - 1];
    if (last && last.home === null && g.status === "final") notes.push(`${last.inning}회 말은 공격 없음(홈 팀 리드로 경기 종료)이라 '–'로 표시합니다`);
    if (ls.basis) notes.push(`집계 기준은 ${ls.basis}`);
    if (ls.provenance) notes.push(`출처는 runs=${text(ls.provenance.runs)}, hits=${text(ls.provenance.hits)}, errors=${text(ls.provenance.errors)}, bb_hbp=${text(ls.provenance.bb_hbp)}`);
    root.append(el("p", { class: "panel-note", text: notes.length ? notes.join(". ") + "." : NA }));
    // 득점 타석 요약(중계 탭 '득점'과 같은 계산)
    const ul = el("ul", { class: "score-list" });
    for (const [key, sc] of S.scoring) {
      const a = S.paOf.get(key); if (!a) continue;
      // 득점 시점을 적는다: 타석 도중(예: 2구 전) 난 점수를 타석 결과가 낸 것처럼 읽히지 않게
      const li = el("li", null, el("b", { text: `${a.inning}회 ${halfWord(a.half)}` }), ` ${text(a.batter && a.batter.name)}, ${text(a.event_label)}, ${text(a.result_text)}, 득점 시점 ${scoreWhen(sc)} → ${text(g.away_abbr)} ${sc.after[0]} : ${sc.after[1]} ${text(g.home_abbr)}`);
      const btn = el("button", { type: "button", class: "link-btn", text: "그 타석 보기" });
      btn.addEventListener("click", () => { document.getElementById("tab-relay").click(); selectPitch(sc.mid ? sc.mid.index : a.first_index, { scroll: "force" }); });
      li.append(" ", btn); ul.append(li);
    }
    root.append(el("h2", { class: "pp-sub", text: `득점 타석 (${S.scoring.size})` }), ul);
  }

  function buildFooter() {
    const d = S.data, pub = d.publish || {}, pol = (S.P[0] && S.P[0].rec && S.P[0].rec.policy) || {};
    const dl = $("foot-meta"); dl.textContent = ""; // 가운뎃점 한 줄 대신 항목별 <dt>/<dd>
    const rows = [
      ["schema", text(d.schema)], ["발행", text(pub.published_at)], ["투구", `${S.P.length}구`], ["타석", `${S.pas.length}타석`],
      ["추천 정책", text(pol.name)], ["추천 없음", `${S.P.filter((p) => !p.rec || p.rec.status !== "ready").length}구`],
    ];
    for (const [k, v] of rows) { dl.append(el("dt", { text: k })); dl.append(el("dd", { text: v })); }
  }

  // ----- 화면 밝기(테마): 기본 밝은 화면, 저장값만 따른다(OS 설정 자동 전환 없음) -----
  const THEME_KEY = "pz-relay-theme";
  function setTheme(theme, save) {
    document.documentElement.dataset.theme = theme;
    const dark = theme === "dark", btn = $("theme-switch");
    btn.textContent = dark ? "밝게" : "어둡게";
    btn.setAttribute("aria-label", `${dark ? "밝게" : "어둡게"}, 지금은 ${dark ? "어두운" : "밝은"} 화면`); // 보이는 글자로 시작(WCAG 2.5.3 Label in Name, 11/6 검토 C-F2)
    const meta = document.querySelector('meta[name="theme-color"]'), bg = getComputedStyle(document.documentElement).getPropertyValue("--bg").trim();
    if (meta && bg) meta.setAttribute("content", bg); // 토큰 값을 그대로 읽어 색 리터럴을 두 번 적지 않는다
    if (B3.api) B3.api.setTheme(theme); // 3D 타자 조명도 같은 테마로
    if (save) { try { localStorage.setItem(THEME_KEY, theme); } catch (e) { /* 저장소를 못 쓰면 이번 방문에만 적용 */ } }
  }
  function wireTheme() {
    setTheme(document.documentElement.dataset.theme === "dark" ? "dark" : "light", false); // head의 인라인 스크립트가 첫 페인트 전에 세팅한 값
    $("theme-switch").addEventListener("click", () => setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark", true));
  }

  // ----- 2b. 투구 애니메이션 스위치: 기본 켜짐, 감속 모션 설정이면 기본 꺼짐이고 켜도 결과 자막만 -----
  const ANIM_KEY = "pz-relay-anim";
  function storedAnimPref() { // "on" | "off" | null(저장값 없음 또는 저장소 접근 실패)
    try { const v = localStorage.getItem(ANIM_KEY); if (v === "on" || v === "off") return v; } catch (e) { /* 저장값 없음과 같게 */ }
    return null;
  }
  function readAnimPref() { const v = storedAnimPref(); return v ? v === "on" : !reduceMotion(); }
  function renderAnimSwitch() {
    $("anim-switch").setAttribute("aria-checked", S.animOn ? "true" : "false");
    $("anim-state").textContent = !S.animOn ? "꺼짐" : reduceMotion() ? "켜짐, 감속 모션 설정이라 결과 자막만" : "켜짐";
  }
  function wireAnim() {
    S.animOn = readAnimPref(); renderAnimSwitch();
    $("anim-switch").addEventListener("click", () => {
      S.animOn = !S.animOn; renderAnimSwitch();
      try { localStorage.setItem(ANIM_KEY, S.animOn ? "on" : "off"); } catch (e) { /* 이번 방문에만 적용 */ }
      const p = S.P[S.sel]; if (p) renderZone(p, S.paOf.get(p.pa_key) || null); // 켜면 지금 투구를 다시 연출, 끄면 오버레이가 사라진다
    });
    if (window.matchMedia) { // 화면이 열린 채 OS 감속 모션 설정이 바뀌면: 저장값이 없을 때 기본값을 다시 읽고, 라벨과 지금 투구를 함께 다시 그린다(11/6 검토 C-F5)
      const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
      const onChange = () => { if (storedAnimPref() === null) S.animOn = readAnimPref(); renderAnimSwitch(); const p = S.P[S.sel]; if (p) renderZone(p, S.paOf.get(p.pa_key) || null); };
      if (mq.addEventListener) mq.addEventListener("change", onChange);
    }
  }

  // ----- 4b. 결과별 공, 스윙 연출 -----
  /* 투수 시점이므로 공은 시청자 가까이(크게, 존 창 위 가운데)에서 출발해 멀어지며(작아지며) 실제 도착 위치(actual.x, z의 표식 자리)에 닿는다(ease-in).
   * 릴리스 포인트, 궤적(vx0 등), 타구 방향 자료는 발행 파일에 없으므로 전부 '도착 위치와 결과로 만든 연출'이다(범례에 적음). 타구의 좌우는 꺾지 않는다.
   * SVG 속성(cx, cy, r)은 WAAPI로 못 움직여 rAF 루프로 직접 갱신한다. 루프는 한 번에 하나(S.anim.raf), 새 투구를 고르면 cancelAnim으로 끊는다. */
  const easeIn = (t) => t * t, easeOut = (t) => 1 - (1 - t) * (1 - t), lerp = (a, b, k) => a + (b - a) * k;
  function cancelAnim() {
    const A = S.anim;
    if (A.raf) cancelAnimationFrame(A.raf); A.raf = 0;
    if (A.raf3d) cancelAnimationFrame(A.raf3d); A.raf3d = 0;
    for (const t of A.timers) clearTimeout(t); A.timers = [];
    $("bat-left").classList.remove("swing"); $("bat-right").classList.remove("swing");
    if (B3.api) { if (B3.api.container) b3Opacity(B3.api.container, 1, false); B3.api.reset(b3Still()); } // 3D 타자는 대기 자세로(사람형은 대기 동작 반복; 끊긴 스윙·반응 자세에서 섞여 돌아감). 애니메이션 끔·다른 화면·감속 모션이면 정지 자세. hit 끝 투명 처리 도중이었으면 바로 불투명으로
  }
  /** 3D 대기 반복을 돌리지 않을 조건: 애니메이션 스위치 끔, 감속 모션 설정, 중계 화면이 아닐 때(숨은 캔버스에 30 fps로 그리지 않게; 11/9 독립 검토) */
  function b3Still() { return { still: !S.animOn || reduceMotion() || S.view !== "relay" }; }
  const HIT_FADE_FROM = 0.86; // hit 연출 진행률 이 값부터 끝(1)까지 상자 투명도 1→0(전체 약 2.2 s 중 마지막 0.3 s)
  /** hit 연출 끝의 3D 상자 투명도. soft=true면 0.35 s 전환(대기 자세가 서서히 나타남), 아니면 즉시(프레임마다 값 설정). v ≥ 1이면 인라인 값을 지운다 */
  function b3Opacity(box, v, soft) { box.style.transition = soft ? "opacity .35s ease" : "none"; box.style.opacity = v >= 1 ? "" : String(Math.max(0, Math.min(1, v))); }
  function later(fn, ms) { const A = S.anim, t = setTimeout(() => { A.timers = A.timers.filter((x) => x !== t); fn(); }, ms); A.timers.push(t); }
  /** 한 구간을 rAF로 진행한다. 탭이 숨겨지면(document.hidden) 바로 최종 상태(frame(1)). slot은 rAF 손잡이 자리("raf" 공, "raf3d" 3D 스윙): 자리마다 루프는 하나 */
  function run(ms, ease, frame, done, slot = "raf") {
    const A = S.anim, t0 = performance.now();
    const step = (now) => {
      const k = document.hidden ? 1 : Math.min(1, (now - t0) / ms);
      frame(ease(k));
      if (k < 1) A[slot] = requestAnimationFrame(step); else { A[slot] = 0; if (done) done(); }
    };
    A[slot] = requestAnimationFrame(step);
  }
  function swingBat(side) { // CSS keyframes(.batband.swing .bat) 480ms: 도착 순간 수평(30%), 팔로스루(-120도)를 잠깐 멈춘 뒤 자세로 되돌아온다. 끝난 뒤 클래스 제거(점프 없음, 11/6 검토 D-F3)
    const band = $(side === "L" ? "bat-left" : "bat-right");
    band.classList.add("swing");
    later(() => band.classList.remove("swing"), 500);
  }
  function setBall(ball, cx, cy, r, op) { ball.setAttribute("cx", cx); ball.setAttribute("cy", cy); ball.setAttribute("r", r); ball.setAttribute("opacity", op); }
  const CAP = { h: 30, padX: 10, gap: 3, em: 18, subEm: 15 }; // 자막 rect 높이, 좌우 여백, 창 가장자리 간격, 글자 크기(relay.css .z-caption과 같은 값, 그리기 단위)
  /** 결과 자막. 자리는 captionSpot(순수 함수)이 창 안 여섯 자리 중 표식(obs: 이번 타석 번호 원, 추천 네모)과 겹치지 않는 곳을 고른다(다른 투구의 원을 덮지 않는다).
   *  다음 투구까지 유지(renderZone이 SVG를 비울 때 함께 사라짐). 여섯 자리가 전부 겹치면(이 경기 자료에서는 0회) 가장 적게 겹치는 자리에 두고 1.2초 뒤 흐리게(.dim) 해 아래 표식이 비친다. */
  function drawCaption(layer, w, obs, main, sub) {
    const g = svg("g", { class: "z-caption" });
    const t = svg("text", { "text-anchor": "middle" }, main);
    if (sub) { t.append(document.createTextNode(" ")); t.append(svg("tspan", { class: "z-cap-sub" }, sub)); }
    const rect = svg("rect", { height: CAP.h, rx: 6 });
    g.append(rect, t); layer.append(g);
    let tw = 0;
    try { tw = t.getBBox().width; } catch (e) { tw = 0; }
    if (!(tw > 0)) tw = textWidthGuess(main, CAP.em) + (sub ? textWidthGuess(sub, CAP.subEm) + 6 : 0); // 숨겨진 탭 등에서 getBBox가 0이면 글자 폭을 어림
    const spot = captionSpot(w, tw, CAP.h, obs, CAP.padX, CAP.gap);
    t.setAttribute("x", spot.x); t.setAttribute("y", spot.y + 6);
    rect.setAttribute("x", spot.x - tw / 2 - CAP.padX); rect.setAttribute("y", spot.y - CAP.h / 2); rect.setAttribute("width", tw + 2 * CAP.padX);
    if (spot.overlap > 0) later(() => g.classList.add("dim"), 1200);
  }
  /** 분기는 animPlan(순수 함수). at가 없으면(선택 투구에 x, z 없음) 자막만. 스위치 꺼짐이면 아무것도 그리지 않는다. obs는 자막이 피할 표식 자리. */
  function playAnim(p, w, at, layer, side, obs) {
    if (!S.animOn) return;
    const plan = animPlan(p.actual);
    if (reduceMotion() || document.hidden || !at) { drawCaption(layer, w, obs, plan.caption, plan.sub); return; } // 최종 상태만
    const x0 = ux(0), y0 = uz(w.zHi) + R_DOT * 2.2, r0 = R_DOT * 2.2, H = (w.zHi - w.zLo) * U;
    const ball = svg("circle", { class: "z-ball" }); setBall(ball, x0, y0, r0, 0.5); layer.append(ball);
    if (plan.swing && side) {
      // 3D 타자가 붙어 있으면: 공이 나타나는 지금부터 도착(flightMs)까지 클립의 연출 기준 시점 앞부분을, 그 뒤 팔로스루를 원속도로(어댑터 swing). 판정(plan)은 그대로
      // hit(11/9 사용자 "유효한 타격·진루·홈런은 치고 나가는 동작"): 인플레이이고 자료의 타석 결과가 안타·홈런(BADGE_OF "hit": single·double·triple·home_run)일 때만. 아웃·실책 출루·파울은 contact 그대로. 모델에 hit 클립이 없으면 어댑터가 contact로 대체
      const swingKind = plan.kind === "miss" ? "miss" : plan.kind === "inplay" && BADGE_OF[(p.actual || {}).event] === "hit" ? "hit" : "contact";
      const sw = B3.api && B3.api.ok() ? B3.api.swing(swingKind, plan.flightMs) : null;
      if (sw) {
        let fallen = false; // 연출 도중 3D가 멈추면(문맥 상실 등) 그 자리에서 해제하고 SVG 스윙으로 넘어간다(다음 투구까지 타자가 안 보이는 일 방지, 11/6 D-F3류 점프보다 공백이 더 나쁨)
        // hit(안타·홈런) 클립일 때만: 마지막 0.3 s쯤(u ≥ HIT_FADE_FROM)에 상자를 서서히 투명하게 — 타자가 1루 쪽으로 달려 틀 밖으로 나가며 사라지고, 끝나면 대기 자세가 0.35 s에 걸쳐 다시 나타난다(끝 자세→대기 컷에서 가장자리에 남은 몸이 튀어 보이는 것을 가림; 11/9 중계 캡처)
        const fadeBox = sw.kind === "hit" && B3.api.container ? B3.api.container : null; // 어댑터가 실제로 고른 재생 항목(kind)으로 판단(클립 이름이 아니라; 독립 검토 지적)
        run(sw.ms, (t) => t, (u) => { if (fallen) return; if (B3.api && B3.api.ok()) { sw.frame(u); if (fadeBox) b3Opacity(fadeBox, u < HIT_FADE_FROM ? 1 : (1 - u) / (1 - HIT_FADE_FROM), false); return; } fallen = true; detach3D("3D 중단(연출 중)"); swingBat(side); }, () => { if (!fallen && B3.api && B3.api.ok()) { B3.api.reset(b3Still()); if (fadeBox) b3Opacity(fadeBox, 1, true); } }, "raf3d"); // 끝나면 대기 동작으로(모듈이 0.35 s 섞어 넘어감; 11/9 사용자 "자세 전후엔 항상 대기 자세")
      } else later(() => swingBat(side), Math.max(0, plan.flightMs - 140)); // SVG: 도착 0.14초 전에 방망이가 돌기 시작
    } else if (side && (plan.kind === "take" || plan.kind === "block")) {
      // 안 치는 공(볼·스트라이크·블록, 11/9 사용자 "스트라이크나 볼일 때 이모션"): 3D 타자가 붙어 있고 모델에 반응 클립이 있으면 공이 도착한 뒤 한 발 물러나는 반응(어댑터 react). 끝나면 대기 동작으로.
      // SVG 타자·반응 클립 없는 모델(마네킹)은 전처럼 아무 동작 없음. 판정·자막은 그대로
      const rx = B3.api && B3.api.ok() && typeof B3.api.react === "function" ? B3.api.react(plan.flightMs) : null; // react 없는(옛 캐시) 어댑터는 마네킹처럼 반응 없음
      if (rx) {
        let fallen = false;
        run(rx.ms, (t) => t, (u) => { if (fallen) return; if (B3.api && B3.api.ok()) { rx.frame(u); return; } fallen = true; detach3D("3D 중단(연출 중)"); }, () => { if (!fallen && B3.api && B3.api.ok()) B3.api.reset(b3Still()); }, "raf3d");
      }
    }
    run(plan.flightMs, easeIn, (k) => setBall(ball, lerp(x0, at.x, k), lerp(y0, at.y, k), lerp(r0, R_DOT, k), lerp(0.5, 0.95, k)), () => {
      drawCaption(layer, w, obs, plan.caption, plan.sub);
      const gone = () => ball.remove();
      if (plan.kind === "block") { // 포수 앞에서 아래로 짧게 튀고 사라짐
        run(380, easeOut, (k) => setBall(ball, at.x, at.y + 34 * Math.sin(Math.PI * k), R_DOT, 0.95 * (1 - k)), gone);
      } else if (plan.kind === "foul") { // 방망이에 맞아 타자 쪽 뒤 위로(시청자 쪽으로 오며 커진다). 타석 방향이 없으면 똑바로 위
        ball.classList.add("foul");
        const dir = side === "L" ? -1 : side === "R" ? 1 : 0, x1 = at.x + dir * w.xMax * U * 0.7, y1 = uz(w.zHi) - R_DOT * 2, r1 = R_DOT * 2.6;
        run(500, easeOut, (k) => setBall(ball, lerp(at.x, x1, k), lerp(at.y, y1, k), lerp(R_DOT, r1, k), 0.95 * (1 - k)), gone);
      } else if (plan.kind === "tip") { // 파울팁: 방망이를 스치고 포수 앞으로 짧게(40단위) 떨어지며 사라짐. 뒤로 날아가지 않는다
        ball.classList.add("foul");
        run(320, easeOut, (k) => setBall(ball, at.x, at.y + 40 * k, R_DOT, 0.95 * (1 - k)), gone);
      } else if (plan.kind === "inplay") { // 시청자 쪽으로 커지며 날아감. 세로는 발사각, 시간은 타구 속도, 홈런(event)만 화면 위로 완전히 나간다. 좌우는 자료가 없어 똑바로
        ball.classList.add("hit");
        const dy = plan.lift === "high" ? -0.9 * H : plan.lift === "mid" ? -0.4 * H : 0.1 * H;
        const y1 = plan.out ? w.vb.y - R_DOT * 4 : at.y + dy, r1 = plan.out ? R_DOT * 3 : R_DOT * 2.6;
        run(plan.hitMs, easeOut, (k) => setBall(ball, at.x, lerp(at.y, y1, k), lerp(R_DOT, r1, k), 0.95 * (1 - Math.max(0, k - 0.35) / 0.65)), gone);
      } else { // take, miss: 도착한 자리에 번호 원이 이미 있으므로 0.2초 뒤 사라짐
        run(200, easeOut, (k) => setBall(ball, at.x, at.y, R_DOT, 0.95 * (1 - k)), gone);
      }
    });
  }

  // ----- 4c. 3D 타자(선택 사항, 2026-11-08 단위 3) -----
  /* batter3d-host.js(모듈)가 glb 읽기·WebGL 초기화에 성공하면 attach3D(api)를 한 번 부른다. 그 전·실패·모듈 미지원 브라우저에서는 SVG 타자(.batter)가 그대로다.
   * 여기서는 상자(api.container)를 서 있는 쪽 띠로 옮기고 .zone-row에 has3d·side-l/side-r를 붙여 열 폭(88/72px)을 바꾼다. 재생 시간·결과 판정은 위 playAnim 하나가 쥔다.
   * 실행 중 WebGL 문맥 상실 등으로 api.ok()가 false가 되면 detach3D로 상자를 치우고 SVG로 되돌아간다. */
  const B3 = { api: null };
  function zoneRow() { return document.querySelector(".zone-row"); }
  function attach3D(api) {
    if (!api || !api.container || typeof api.swing !== "function" || typeof api.ok !== "function") return false;
    if (B3.api && B3.api !== api) detach3D("다른 3D 타자로 교체");
    B3.api = api;
    // 연출(공 비행·SVG 스윙 타이머·3D 스윙)이 진행 중이면 지금 전환하지 않는다: 이미 예약된 SVG 스윙이 숨겨진 채 돌아 그 투구에 스윙이 안 보이는 일을 막는다(11/8 독립 검토).
    // 연출이 끝나는 대로(또는 다음 renderZone에서) 전환한다. 첫 투구가 끝난 뒤에도 사용자가 아무것도 누르지 않으면 3D가 안 보이던 문제(11/8 21:5x 확인)를 막는다
    b3ShowWhenIdle();
    return true;
  }
  function b3ShowWhenIdle() {
    if (!B3.api) return;
    const A = S.anim; // later()의 콜백 안에서는 자기 타이머가 이미 목록에서 빠져 있어 다른 연출 타이머만 센다. 새 투구가 오면 cancelAnim이 이 타이머도 지우고 renderZone이 직접 b3Show
    if (A.raf || A.raf3d || A.timers.length) { later(b3ShowWhenIdle, 120); return; }
    const p = S.P[S.sel]; if (p) b3Show(p.batter && (p.batter.side === "L" || p.batter.side === "R") ? p.batter.side : null);
  }
  /** 3D를 떼고 SVG 타자로 되돌린다. 진행 중인 3D 스윙 루프(raf3d)는 끊지 않는다: 다음 프레임에서 playAnim의 감싼 frame이 api 없음을 보고 SVG 스윙으로 이어 간다(두 번 불려도 두 번째는 조용히 끝남) */
  function detach3D(reason) {
    const api = B3.api; B3.api = null;
    const row = zoneRow(); if (row) row.classList.remove("has3d", "side-l", "side-r");
    if (!api) return;
    try { api.dispose(); } catch (e) { /* 무시 */ }
    if (api.container && api.container.parentNode) api.container.remove();
    if (reason) console.info("3D 타자 해제, SVG 타자로:", reason);
  }
  /** 선택 투구의 타석 방향(side)에 맞춰 3D 상자를 보이는 띠로 옮기고 idle. side가 없거나 3D가 없으면 열 폭을 원래대로 */
  function b3Show(side) {
    const row = zoneRow(); if (!row) return;
    if (B3.api && !B3.api.ok()) detach3D("3D 중단(WebGL 문맥 상실 등)");
    if (!B3.api || !side) { row.classList.remove("has3d", "side-l", "side-r"); return; }
    const api = B3.api, band = $(side === "L" ? "bat-left" : "bat-right");
    if (api.container.parentNode !== band) band.append(api.container);
    row.classList.add("has3d"); row.classList.toggle("side-l", side === "L"); row.classList.toggle("side-r", side === "R");
    api.setSide(side); api.setTheme(document.documentElement.dataset.theme === "dark" ? "dark" : "light"); api.resize(); api.reset(b3Still());
  }
  window.PZRelay = Object.freeze({ attach3D, detach3D, state3D: () => (B3.api ? { attached: true, model: B3.api.modelName || null, ...B3.api.state() } : { attached: false }) });

  wireTheme(); wireAnim(); // 자료 로딩과 무관하게 바로 동작(const 정의 뒤에서 호출)
})();

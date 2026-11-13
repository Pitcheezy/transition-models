"use strict";
/* relay-v4.js — v4 시안(2026-11-09). relay.js(v1·v2 공용, 11/9 13:58 판)를 복사해 고친 것. v1·v2는 relay.js를 그대로 쓴다.
 * v4에서 바꾼 것: 머리(점수·이닝·볼카운트·주자·이닝별 점수를 보고 있는 공 시점까지만), 이닝 탭·기록 화면 없음(→ 시트),
 *   아래 메뉴 5칸(추천·라인업 = 화면, 선수·구종·기록 = 시트), 시트 6종(자세히·타석 선택·이닝별 기록·선수·구종·기록; Song 고정 빌드 c47fe6cb와 같은 내용·문구),
 *   추천 칸 누르면 자세히, 이번 타석 접기/펼치기, 실제 투구 한 줄(Song 형식), 자동 진행은 시트가 열려 있으면 멈춤, 3D 타자 유니폼 색(공격 팀).
 * 아래 원래 머리말은 relay.js 그대로다. */
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

  // 결과 낱말의 한국어(Song 앱 Vy 표와 같은 낱말). 발행 파일의 result_label·event_label이 영어로 남은 경우(예 field_error → 'Field Error', 11/10 사용자 지적)에만 쓴다
  const EVENT_KO = { single: "1루타", double: "2루타", triple: "3루타", home_run: "홈런", walk: "볼넷", intent_walk: "고의4구", hit_by_pitch: "몸에 맞는 공", strikeout: "삼진", strikeout_double_play: "삼진 병살", field_out: "아웃", force_out: "포스 아웃", grounded_into_double_play: "병살타", double_play: "병살", sac_fly: "희생 플라이", sac_bunt: "희생 번트", field_error: "실책 출루", fielders_choice: "야수 선택", fielders_choice_out: "야수 선택 아웃", catcher_interf: "포수 방해", triple_play: "삼중살" };
  const HANGUL = /[ㄱ-힝]/;
  /** 화면에 쓸 결과 낱말: 자료 낱말에 한글이 있으면 그대로, 영어뿐이면 event로 EVENT_KO, 그것도 없으면 자료 낱말 그대로 */
  const koLabel = (label, event) => (label && !HANGUL.test(label) && EVENT_KO[event] ? EVENT_KO[event] : label);
  const resultWord = (a) => (a ? koLabel(a.result_label, a.event) : null);
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
  function inset(at, size, al = ARROW, m = MARGIN) { // al = 화살 길이, m = 창 여백(ft). 작은 존(자세히·구종)은 화살을 px 배율로, 여백은 그 창의 값으로(11/10 총점검: 화살이 3px로 잘림)
    if (!at.out) return at;
    const sx = Math.min(size + al, m.x * U - 3), sz = Math.min(size + al, m.z * U - 3);
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
      caption: text(resultWord(a)), sub: null,
    };
    if (a.call_label && a.call_label !== plan.caption) plan.sub = a.call_label;
    if (plan.kind === "inplay") {
      const la = t.launch_angle_deg, ev = t.exit_velocity_mph, dist = t.distance_feet;
      plan.caption = koLabel(a.event_label, a.event) || text(resultWord(a)); plan.sub = null;
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
  function captionSpot(w, tw, h, obs, padX, gap, air = 0) { // air: 표식 테두리와 자막 테두리 사이 여유(그리기 단위)
    const half = tw / 2 + padX, lim = w.xMax * U - half - 2; // 자막 rect가 창 안에 머무는 최대 가로 이동
    const xs = lim > 0 ? [0, -lim, lim] : [0];
    const ys = [uz(w.zLo) - gap - h / 2, uz(w.zHi) + gap + h / 2];
    let best = null;
    for (const y of ys) for (const x of xs) {
      const n = (obs || []).filter((o) => o.x + o.r + air > x - half && o.x - o.r - air < x + half && o.y + o.r + air > y - h / 2 && o.y - o.r - air < y + h / 2).length;
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
    .catch((err) => { console.warn("경기 자료 읽기 실패", err); loadFailed(location.protocol === "file:" ? " (파일로 열면 읽을 수 없어요 — 로컬 서버에서 여세요)" : ""); }); // 방문객 문구(11/10 재점검)
  /** 읽기 실패: 문구를 쓰고, 눌러도 아무 일 없는 조작(스위치 줄·아래 메뉴·머리 둘째 줄)은 숨긴다(뒤로·문구·발 밑만 남음, 11/10 3차) */
  function loadFailed(extra) { $("load-state").textContent = "경기 기록을 불러오지 못했어요. 잠시 뒤 다시 열어 주세요." + (extra || ""); for (const n of [$("v4-controls"), document.querySelector(".bottom-nav"), document.querySelector(".hd-2"), $("hd-score"), $("hd-tag")]) if (n) n.hidden = true; } // 빈 점수·'저장 경기'도 숨김(11/10 4차)

  function init(data) {
    if (!data || !Array.isArray(data.pitches) || !data.pitches.length || !data.pitches.every((q, i) => q && q.index === i && q.pa_key) || !Array.isArray(data.pas) || !data.game) { console.warn("경기 자료 형식이 예상과 다름(pitches/pas/game 없음, 빈 투구 목록 또는 index·pa_key가 맞지 않는 투구 — 11/10 4차)"); loadFailed(); return; }
    S.data = data; S.P = data.pitches; S.pas = data.pas;
    for (const a of S.pas) S.paOf.set(a.pa_key, a);
    S.scoring = scoreChanges(data);
    const g = data.game;
    $("hd-away").textContent = text(g.away_abbr); $("hd-home").textContent = text(g.home_abbr);
    buildLineup(); buildFooter();
    wireBottomNav(); wireAuto(); wireNav(); wireV4();
    $("load-state").hidden = true; $("panel-relay").hidden = false;
    selectPitch(0, { scroll: false }); // 처음 열면 1회 초 1구
  }

  // ----- 3. 머리(v4): 점수·이닝·볼카운트·주자·이닝별 점수 — 전부 '이 공 던지기 전' 값(결과를 미리 보여 주지 않는다) -----
  function renderScore(p) {
    const s = p.situation_before || {}, g = S.data.game;
    $("hd-away-r").textContent = isNum(s.away_score) ? String(s.away_score) : "–"; $("hd-home-r").textContent = isNum(s.home_score) ? String(s.home_score) : "–";
    $("hd-score").setAttribute("aria-label", `이 공 던지기 전 점수 ${text(g.away_abbr)} ${text(s.away_score)}, ${text(g.home_abbr)} ${text(s.home_score)}`);
    const inningText = isNum(s.inning) ? `${s.inning}회${halfWord(s.half)}` : NA; // 보이는 글자('1회초 ▾')와 같은 낱말로 시작(WCAG 2.5.3, 11/10 총점검)
    $("hd-tag").textContent = endedAt(p) ? "경기 종료" : "저장 경기"; // 경기의 마지막 공(타석이 끝남): 머리 오른쪽 태그로만 알린다(점수·이닝은 계속 '던지기 전')
    $("s-inning").textContent = isNum(s.inning) ? `${s.inning}회${halfWord(s.half)} ▾` : DASH; // Song 라이브 형식(띄어쓰기 없음, ▾ = 누르면 타석 선택)
    const count = $("s-count"); count.textContent = "";
    for (const [label, n, max] of [["B", s.balls, 3], ["S", s.strikes, 2], ["O", s.outs, 2]]) {
      const row = el("span", { class: "c-row" }, el("b", { text: label }));
      for (let i = 0; i < max; i++) row.append(el("i", { class: isNum(n) && i < n ? "on" : "" }));
      count.append(row);
    }
    const r = s.runners || {};
    $("d-1").classList.toggle("on", r.first === true); $("d-2").classList.toggle("on", r.second === true); $("d-3").classList.toggle("on", r.third === true);
    const on = ["first", "second", "third"].filter((k) => r[k] === true).map((k) => ({ first: "1루", second: "2루", third: "3루" })[k]);
    $("hd-state").setAttribute("aria-label", `${inningText}, 볼 ${text(s.balls)} 스트라이크 ${text(s.strikes)} 아웃 ${text(s.outs)}, ${on.length ? "주자 " + on.join(", ") : "주자 없음"}. 타석 선택`);
    renderMiniLine(p);
  }
  /** 머리 오른쪽 작은 이닝별 점수. 자료 linescore_before(그 공 던지기 전까지 공개된 플레이)를 그대로: 아직 오지 않은 칸은 비우고, 지금 반 이닝 칸은 강조 */
  function renderMiniLine(p) {
    const box = $("mini-ls"); box.textContent = "";
    const g = S.data.game, ls = lineAt(p), inn = Array.isArray(ls.innings) ? ls.innings : [], s = p.situation_before || {};
    const bat = (side) => (side === "away") === isTop(s.half); // Song 라이브: 지금 이닝 칸(머리·두 팀)을 강조. v4는 공격 팀 칸 글자를 라임으로 한 번 더
    box.append(el("span", { class: "h tm", text: " " }), el("span", { class: "tm", text: text(g.away_abbr) }), el("span", { class: "tm", text: text(g.home_abbr) }));
    for (const i of inn) {
      const now = s.inning === i.inning;
      box.append(el("span", { class: now ? "h cur" : "h", text: String(i.inning) }));
      for (const side of ["away", "home"]) box.append(el("span", { class: now ? (bat(side) ? "cur bat" : "cur") : "", text: i[side] === null || i[side] === undefined ? "" : String(i[side]) }));
    }
    const t = ls.teams || {};
    box.append(el("span", { class: "r h", text: "R" }), el("span", { class: "r", text: cellOr(t.away && t.away.runs, "0") }), el("span", { class: "r", text: cellOr(t.home && t.home.runs, "0") }));
    $("hd-ls").setAttribute("aria-label", `이닝별 점수, 이 공 던지기 전까지. ${text(g.away_abbr)} ${cellOr(t.away && t.away.runs, "0")}, ${text(g.home_abbr)} ${cellOr(t.home && t.home.runs, "0")}. 이닝별 기록 보기`);
  }
  const endedAt = (p) => !!(S.data && S.data.game && S.data.game.status === "final" && p.index === S.P.length - 1 && paResultAt(p));
  const cellOr = (v, dflt) => (v === null || v === undefined ? dflt : String(v));
  /** 그 공 시점의 이닝별 점수 자료. 공마다 linescore_before가 있고, 없으면(옛 자료) 경기 전체 linescore로 */
  function lineAt(p) { return (p && p.linescore_before) || S.data.linescore || {}; }

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
    if (pa) for (let i = pa.first_index; i <= Math.min(pa.last_index, p.index); i++) if (S.P[i]) list.push(S.P[i]); // v4: 고른 공까지만(머리처럼 뒤 공·결과를 미리 보여 주지 않는다, 11/10 총점검)
    const ordered = list.filter((q) => q.index !== p.index).concat(list.filter((q) => q.index === p.index));
    let drawn = 0, selAt = null;
    for (const q of ordered) {
      const a = q.actual || {};
      if (!isNum(a.x) || !isNum(a.z)) continue;
      const kind = kindOf(a.description), selected = q.index === p.index;
      const at = inset(place({ x: a.x, z: a.z }, w), R_DOT);
      { const e = R_DOT + RING + 1.5; at.y = clamp(at.y, w.vb.y + e, w.vb.y + w.vb.h - e); } /* 여백은 모든 표식이 고리 포함 같은 값: 다른 공을 골라도 표식이 1~3px 뛰지 않게(11/10 3차) */ // 창 가장자리 띠의 표식은 원·고리가 그림 밖으로 잘리지 않게 안쪽으로(최대 약 0.08 ft, 존 밖 여백 안에서만; 제목의 좌표는 실제 값 그대로, 11/10 재점검)
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
    $("legend-view").textContent = `투수 시점 · ${side === "L" ? "좌타자" : side === "R" ? "우타자" : "타석 방향 미확인"}`; // v4: Song 범례 형식
    root.setAttribute("aria-label", `투수 시점 스트라이크존${parts.length ? ": " + parts.join(", ") : ""}. 이번 타석 투구 ${drawn}개, 선택 ${p.pitch_number}구`);
    // 결과별 연출 오버레이(맨 위, 보조기기에는 숨김). 선택 투구에 위치 값이 없으면 공은 그리지 않고 자막만 그린다
    const layer = svg("g", { class: "z-anim", "aria-hidden": "true" });
    root.append(layer);
    playAnim(p, w, selAt, layer, side, obs);
  }
  function arrow(at, r, al = ARROW) { // 창 밖 표식의 바깥쪽 화살(작은 삼각형)
    const n = Math.hypot(at.dx, at.dz) || 1, ax = at.dx / n, ay = -at.dz / n, L = r + al, hw = al * 0.75;
    const bx = at.x + ax * (r + 0.5), by = at.y + ay * (r + 0.5);
    return svg("path", { class: "z-arrow", d: `M${at.x + ax * L} ${at.y + ay * L} L${bx - ay * hw} ${by + ax * hw} L${bx + ay * hw} ${by - ax * hw}Z` });
  }

  // ----- 5. 투구 패널 -----
  function renderPanel(p, pa) {
    $("pp-title").textContent = `이 공 던지기 전 추천\u00a0·\u00a0${text(p.pitch_number)}구`; // 붙는 빈칸: 좁은 화면에서 '· N구'만 다음 줄로 가지 않게(11/10 총점검)
    const recs = $("pp-recs"); recs.textContent = "";
    const rec = p.rec || null, ready = rec && rec.status === "ready" && Array.isArray(rec.candidates) && rec.candidates.length;
    // Song 메인처럼 세 칸. 누르면 자세히 시트(추천 표·위치·비중). 추천이 없는 공은 세 칸 모두 '—'
    const cands = ready ? [...rec.candidates].sort((a, b) => a.rank - b.rank).slice(0, 3) : [];
    const label = ready ? `추천 후보 ${cands.map((c) => `${c.rank}순위 ${text(c.pitch_label)}`).join("; ")}. 자세히 보기` : `${recWhy(rec, recState(rec).st).replace(/[.]$/, "")}. 자세히 보기`;
    const row = el("button", { type: "button", class: "chips", "aria-label": label, "aria-haspopup": "dialog" });
    for (let k = 0; k < 3; k++) {
      const c = cands[k];
      row.append(c ? el("span", { class: `chip r${c.rank}` }, el("i", { class: "rk", text: String(c.rank) }), el("b", { text: text(c.pitch_label) }))
        : el("span", { class: "chip none" }, el("b", { text: "—" })));
    }
    row.addEventListener("click", () => openSheet("detail", { from: "chips" })); // 칸 버튼은 공마다 다시 만들어지므로 닫으면 closeSheet가 지금 화면의 칸 버튼으로(없으면 '자세히') 포커스를 돌린다(11/10 재점검; 주석 6차)
    recs.append(row);
    // 실제 투구 한 줄(Song .sv-actual-line): 번호 원 · 구종 · km/h · 결과
    const a = p.actual || {}, kind = kindOf(a.description);
    $("pp-actual-title").textContent = `실제 투구 · ${text(p.pitch_number)}구 · ${(p.batter && p.batter.name) || "타자 미확인"}`;
    const line = $("pp-actual"); line.textContent = "";
    line.append(el("i", { class: `g1 ${kind}`, text: text(p.pitch_number) }), el("b", { text: a.pitch_label || "구종 미상" }),
      isNum(a.speed_mph) ? el("small", { text: `${kmh(a.speed_mph)}km/h` }) : null, el("span", { class: "res", text: actualWord(a, p) }));
    $("btn-prev").disabled = p.index <= 0; $("btn-next").disabled = p.index >= S.P.length - 1;
  }
  /** 실제 투구 줄의 결과 낱말: 자료 result_label(판정·결과 한국어), 없으면 call_label */
  function actualWord(a, p) { const r = p ? paResultAt(p) : null; return r || text(a && (resultWord(a) || a.call_label)); } // Song: 타석이 이 공으로 끝나면 타석 결과 글(예 '우익수 방면 1루타'), 아니면 result_label

  // ----- 6. 이닝 탭: v4에는 없음(타석 선택 시트가 대신) -----
  function arrowTabs(e, box, activate) {
    if (e.key !== "ArrowLeft" && e.key !== "ArrowRight" && e.key !== "Home" && e.key !== "End") return;
    const tabs = [...box.querySelectorAll("[role=tab]")], i = tabs.indexOf(document.activeElement);
    if (i < 0) return;
    e.preventDefault();
    const j = e.key === "Home" ? 0 : e.key === "End" ? tabs.length - 1 : (i + (e.key === "ArrowRight" ? 1 : tabs.length - 1)) % tabs.length;
    activate(tabs[j]);
  }

  // ----- 7. 타석 카드: v4에는 없음(이번 타석 목록은 renderAtbat) -----

  // ----- 선택 -----
  function selectPitch(i, opts) {
    if (!S.P[i]) return;
    S.sel = i;
    const p = S.P[i], pa = S.paOf.get(p.pa_key) || null;
    const ae = document.activeElement, fk = ae === $("btn-prev") ? "prev" : ae === $("btn-next") ? "next" : ae && ae.closest && ae.closest("#pp-recs") ? "chips" : ae && ae.classList && ae.classList.contains("prow") ? "row" : null; const rowSeen = fk === "row" && ((r, cs) => r.bottom > (parseFloat(cs.scrollPaddingTop) || 0) && r.top < innerHeight - (parseFloat(cs.scrollPaddingBottom) || 0))(ae.getBoundingClientRect(), getComputedStyle(document.documentElement)); /* 고정 머리·아래 줄에 가린 행은 안 보이는 것으로(11/10 4차) */ /* 행이 화면에 보이던 때만 다시 보이게 민다: 자동 진행 중 내려 둔 페이지를 끌어오지 않게(11/10 3차) */ // 다시 그리면 사라지는(또는 끝에서 비활성이 되는) 요소에 있던 포커스
    renderScore(p); renderZone(p, pa); renderPanel(p, pa); renderAtbat(p);
    if (fk && (!document.activeElement || document.activeElement === document.body || document.activeElement.disabled)) { // 포커스가 body로 떨어졌거나 비활성 버튼에 남았으면 같은 자리로(11/10 총점검, 비활성은 11/10 재점검)
      const n = fk === "prev" ? ($("btn-prev").disabled ? $("btn-next") : $("btn-prev")) : fk === "next" ? ($("btn-next").disabled ? $("btn-prev") : $("btn-next")) : fk === "chips" ? $("pp-recs").querySelector(".chips") : $("pa-list").querySelector('.prow[aria-pressed="true"]');
      if (n) { n.focus({ preventScroll: true }); if (fk === "row" && rowSeen) n.scrollIntoView({ block: "nearest" }); } // 행은 머리·고정 줄 밑으로 숨지 않게(scroll-padding 적용)
    } // v4: 목록이 자리를 옮기지 않으므로 페이지 스크롤 따라가기 없음(고정 줄 아래로 숨지 않게)
    S.note = null; // 투구를 새로 고르면 stopAuto가 남긴 안내 문구는 지운다
    if (S.auto) S.left = AUTO_SECONDS;
    renderAuto();
    if (S.sheet) renderSheet(); // 열려 있는 시트(자세히·선수·구종·기록 등)는 고른 공 기준으로 다시 그린다
  }
  /** 이번 타석(Song .sv-atbat): 그 타석의 모든 공을 최근 것부터. 고른 공이 타석을 끝낸 공이면 맨 위에 타석 결과 줄. 줄을 누르면 그 공을 고르고 자세히 시트(Song oa) */
  function renderAtbat(p) {
    const list = S.P.filter((q) => q.pa_key === p.pa_key && q.index <= p.index), ol = $("pa-list"); ol.textContent = ""; // v4: 고른 공까지 던진 공만(뒤 공·타석 결과를 미리 보여 주지 않는다, 11/10 총점검). 결과 줄은 고른 공이 타석을 끝낸 공일 때만
    $("atbat-title").textContent = `이번 타석 · ${list.length}구 던짐`;
    const res = paResultAt(p);
    if (res) ol.append(el("li", { class: "result" }, el("b", { text: res })));
    for (const q of [...list].reverse()) {
      const a = q.actual || {}, kind = kindOf(a.description);
      const head = `${q.pitch_number}구 ${a.pitch_label || "구종 미상"} ${isNum(a.speed_mph) ? kmh(a.speed_mph) + "km/h " : ""}`, full = `${head}${resultWord(a) || "기록 없음"}. 자세히 보기`;
      const hide = q.index === p.index && document.documentElement.classList.contains("pz-flying"); // 공이 날아가는 동안 읽기 이름도 결과 없이(닿으면 flying(false)가 되살림, 11/10 3차)
      const b = el("button", { type: "button", class: "prow", "aria-pressed": String(q.index === p.index), "aria-label": hide ? `${head.trim()}. 자세히 보기` : full, "data-label": hide ? full : null },
        el("i", { class: `g1 ${kind}`, text: text(q.pitch_number) }), el("span", { class: "pr-what" }, el("b", { text: a.pitch_label || "구종 미상" }), isNum(a.speed_mph) ? el("small", { text: `${kmh(a.speed_mph)}km/h` }) : null),
        el("span", { class: "res", text: resultWord(a) || "기록 없음" }));
      b.addEventListener("click", () => pickAndDetail(q.index, "row"));
      ol.append(el("li", null, b));
    }
  }
  function wireNav() {
    $("btn-prev").addEventListener("click", () => selectPitch(S.sel - 1, { scroll: true }));
    $("btn-next").addEventListener("click", () => selectPitch(S.sel + 1, { scroll: true }));
  }

  // ----- 2. 자동 진행 -----
  /** 자동 진행이 멈춰야 하는 상태: 브라우저 탭이 가려졌거나, 상단 탭이 중계가 아닐 때(보이지 않는 사이 넘어가지 않게). */
  const autoPaused = () => document.hidden || S.view !== "relay" || !!S.sheet; // v4: 시트를 읽는 동안에도 멈춤(읽던 내용이 다음 공으로 바뀌지 않게)
  /** 보조기기 안내(role=status)는 켜짐, 꺼짐, 일시정지, 종료처럼 상태가 바뀔 때만 한 번. 매초 바뀌는 카운트다운은 aria-hidden 요소에만 쓴다. */
  function announce(msg) { if (S.said === msg) return; S.said = msg; $("auto-status").textContent = msg; }
  function renderAuto() {
    const sw = $("auto-switch"), c = $("auto-count");
    sw.setAttribute("aria-checked", S.auto ? "true" : "false");
    if (!S.auto) { c.textContent = S.note ? S.note.split(",")[0] : "꺼짐"; announce(S.note ? `자동 진행 꺼짐. ${S.note}` : "자동 진행 꺼짐"); }
    else if (S.sel >= S.P.length - 1) { c.textContent = "마지막 투구"; announce("마지막 투구"); }
    else if (autoPaused()) { c.textContent = "멈춤"; announce(S.sheet ? "자동 진행 일시정지, 시트를 보는 동안" : "자동 진행 일시정지"); }
    else { c.textContent = `${S.left}초 뒤 다음`; announce(`자동 진행 켜짐, ${AUTO_SECONDS}초마다 다음 투구`); }
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

  // ----- 1. 아래 메뉴(v4): 추천·라인업 = 화면 전환, 선수·구종·기록 = 시트 -----
  function showView(view) {
    S.view = view;
    for (const v of ["relay", "lineup"]) $("panel-" + v).hidden = v !== view;
    $("v4-controls").hidden = view !== "relay"; // 두 스위치는 추천 화면에서만
    renderNavState();
    if (S.auto) renderAuto(); // 라인업이면 '멈춤' 표시, 추천으로 돌아오면 카운트다운 재개
    if (B3.api && !(S.anim.raf3d)) B3.api.reset(b3Still()); // 3D 대기 반복은 추천 화면에서만(연출 중이면 건드리지 않는다)
    window.scrollTo(0, 0);
  }
  function renderNavState() {
    for (const b of document.querySelectorAll(".bottom-nav button")) {
      if (b.dataset.view) { if (b.dataset.view === S.view && !S.sheet) b.setAttribute("aria-current", "page"); else b.removeAttribute("aria-current"); }
      if (b.dataset.sheet) b.setAttribute("aria-expanded", S.sheet && S.sheet.kind === b.dataset.sheet ? "true" : "false");
    }
  }
  function wireBottomNav() {
    for (const b of document.querySelectorAll(".bottom-nav button")) {
      b.addEventListener("click", () => {
        if (b.dataset.view) { if (S.sheet) closeSheet(false); showView(b.dataset.view); return; }
        if (S.sheet && S.sheet.kind === b.dataset.sheet) { closeSheet(true); return; } // 같은 메뉴를 다시 누르면 닫기
        openSheet(b.dataset.sheet, { from: b });
      });
    }
  }

  // ----- 라인업 탭 -----
  function buildLineup() {
    const root = $("lineup-root"); root.textContent = "";
    const g = S.data.game, L = lineups(S.data);
    const pp = g.probable_pitchers || {};
    for (const [key, teamName, abbr, side, role] of [["away", g.away_team, g.away_abbr, L.away, "원정"], ["home", g.home_team, g.home_abbr, L.home, "홈"]]) {
      const sec = el("section", { class: "team-card", "aria-label": `${text(abbr)} 라인업` });
      sec.append(el("h2", null, el("span", { class: "abbr", text: text(abbr) }), ` ${teamKo(teamName)} `, el("small", { text: role })));
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

  // ----- 기록 탭: v4에는 없음(기록 시트가 대신) -----

  function buildFooter() {
    const d = S.data, pub = d.publish || {}, pol = (S.P[0] && S.P[0].rec && S.P[0].rec.policy) || {};
    const dl = $("foot-meta"); dl.textContent = ""; // 가운뎃점 한 줄 대신 항목별 <dt>/<dd>
    const stamp = (iso) => { const t = Date.parse(iso); return Number.isFinite(t) ? new Intl.DateTimeFormat("ko-KR", { timeZone: "Asia/Seoul", year: "numeric", month: "long", day: "numeric", hour: "2-digit", minute: "2-digit", hourCycle: "h23" }).format(t) + " (한국 시각)" : text(iso); };
    const rows = [
      ["발행", stamp(pub.published_at)], ["투구", `${S.P.length}구`], ["타석", `${S.pas.length}타석`],
      ["추천 없음", `${S.P.filter((p) => !p.rec || p.rec.status !== "ready").length}구`],
    ]; // 방문객에게 개발용 문자열(schema·영문 정책·UTC 원문)은 보이지 않게, 접힌 '자료 정보'에 그대로 둔다(11/10 3차)
    for (const [k, v] of rows) { dl.append(el("dt", { text: k })); dl.append(el("dd", { text: v })); }
    const old = dl.parentNode && dl.parentNode.querySelector(".foot-src"); if (old) old.remove();
    const src = el("dl", { class: "foot-meta" });
    for (const [k, v] of [["schema", text(d.schema)], ["발행(UTC)", text(pub.published_at)], ["추천 정책", text(pol.name)]]) { src.append(el("dt", { text: k })); src.append(el("dd", { text: v })); }
    dl.after(el("details", { class: "foot-src" }, el("summary", { text: "자료 정보" }), src));
  }

  // ----- 화면 밝기(테마): 기본 밝은 화면, 저장값만 따른다(OS 설정 자동 전환 없음) -----
  const THEME_KEY = "pz-relay-theme";
  function setTheme(theme, save) {
    document.documentElement.dataset.theme = theme;
    const dark = theme === "dark", btn = $("theme-switch");
    if (btn) { // v4에는 밝기 버튼이 없다(밝은 화면만)
    btn.textContent = dark ? "밝게" : "어둡게";
    btn.setAttribute("aria-label", `${dark ? "밝게" : "어둡게"}, 지금은 ${dark ? "어두운" : "밝은"} 화면`); // 보이는 글자로 시작(WCAG 2.5.3 Label in Name, 11/6 검토 C-F2)
    }
    const meta = document.querySelector('meta[name="theme-color"]'), bg = getComputedStyle(document.documentElement).getPropertyValue("--bg").trim();
    if (meta && bg && !document.documentElement.dataset.v4) meta.setAttribute("content", bg); // v4: 머리가 진녹이라 theme-color는 html 값(#091811) 그대로 // 토큰 값을 그대로 읽어 색 리터럴을 두 번 적지 않는다
    if (B3.api) B3.api.setTheme(theme); // 3D 타자 조명도 같은 테마로
    if (save) { try { localStorage.setItem(THEME_KEY, theme); } catch (e) { /* 저장소를 못 쓰면 이번 방문에만 적용 */ } }
  }
  function wireTheme() {
    setTheme(document.documentElement.dataset.theme === "dark" ? "dark" : "light", false); // head의 인라인 스크립트가 첫 페인트 전에 세팅한 값
    if ($("theme-switch")) $("theme-switch").addEventListener("click", () => setTheme(document.documentElement.dataset.theme === "dark" ? "light" : "dark", true));
  }

  // ----- 2b. 투구 애니메이션 스위치: 기본 켜짐, 감속 모션 설정이면 기본 꺼짐이고 켜도 결과 자막만 -----
  const ANIM_KEY = "pz-relay-v4-anim"; // v1·v2(pz-relay-anim)와 따로: 다른 판에서 끈 설정이 v4를 꺼진 채로 열지 않게(11/10 총점검)
  function storedAnimPref() { // "on" | "off" | null(저장값 없음 또는 저장소 접근 실패)
    try { const v = localStorage.getItem(ANIM_KEY); if (v === "on" || v === "off") return v; } catch (e) { /* 저장값 없음과 같게 */ }
    return null;
  }
  function readAnimPref() { const v = storedAnimPref(); return v ? v === "on" : !reduceMotion(); }
  function renderAnimSwitch() {
    $("anim-switch").setAttribute("aria-checked", S.animOn ? "true" : "false");
    $("anim-state").textContent = !S.animOn ? "꺼짐" : reduceMotion() ? "켜짐(자막만)" : "켜짐"; // 감속 모션 설정이면 결과 자막만
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
  /** 공 비행 중 표시: html.pz-flying이면 CSS가 결과 글을 가리고(자리는 그대로), 머리 태그는 '저장 경기'. 끝나면 마지막 공의 '경기 종료'를 되살린다(11/10 재점검) */
  function flying(on) {
    document.documentElement.classList.toggle("pz-flying", !!on);
    if (!on) { const r = document.querySelector("#pa-list .prow[data-label]"); if (r) { r.setAttribute("aria-label", r.dataset.label); r.removeAttribute("data-label"); } } // 비행 중 뺀 결과를 읽기 이름에 되살린다(11/10 3차)
    else { const r = document.querySelector('#pa-list .prow[aria-pressed="true"]:not([data-label])'), res = r && r.querySelector(".res"), full = r && r.getAttribute("aria-label"), tail = res ? res.textContent + ". 자세히 보기" : ""; if (tail && full && full.endsWith(tail)) { r.dataset.label = full; r.setAttribute("aria-label", full.slice(0, -tail.length).trim() + ". 자세히 보기"); } } // 목록을 다시 그리지 않는 재연출(애니메이션 스위치 켬·감속 모션 해제)에서도 결과를 뺀다(11/10 4차)
    const p = S.P[S.sel]; $("hd-tag").textContent = !on && p && endedAt(p) ? "경기 종료" : "저장 경기";
  }
  function cancelAnim() {
    const A = S.anim; flying(false);
    if (A.raf) cancelAnimationFrame(A.raf); A.raf = 0;
    if (A.raf3d) cancelAnimationFrame(A.raf3d); A.raf3d = 0;
    for (const t of A.timers) clearTimeout(t); A.timers = [];
    $("bat-left").classList.remove("swing"); $("bat-right").classList.remove("swing");
    if (B3.api) { if (B3.api.container) { b3Opacity(B3.api.container, 1, false); B3.api.container.classList.remove("exiting"); } B3.api.reset(b3Still()); } // 3D 타자는 대기 자세로(사람형은 대기 동작 반복; 끊긴 스윙·반응 자세에서 섞여 돌아감). 애니메이션 끔·다른 화면·감속 모션이면 정지 자세. hit 끝 투명 처리 도중이었으면 바로 불투명으로
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
      const k = document.hidden ? 1 : Math.min(1, Math.max(0, (now - t0) / ms)); // rAF 시각이 t0보다 앞설 수 있다(음수면 공이 지나가고 r < 0, 11/10 총점검)
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
    const spot = captionSpot(w, tw, CAP.h, obs, CAP.padX, CAP.gap, 3); // 3 = 원 테두리 1.25 + 자막 테두리 0.75 + 여유 1(11/10 재점검: 4구에서 테두리가 닿았다)
    t.setAttribute("x", spot.x); t.setAttribute("y", spot.y + 6);
    rect.setAttribute("x", spot.x - tw / 2 - CAP.padX); rect.setAttribute("y", spot.y - CAP.h / 2); rect.setAttribute("width", tw + 2 * CAP.padX);
    if (spot.overlap > 0) later(() => g.classList.add("dim"), 1200);
  }
  /** 분기는 animPlan(순수 함수). at가 없으면(선택 투구에 x, z 없음) 자막만. 스위치 꺼짐이면 아무것도 그리지 않는다. obs는 자막이 피할 표식 자리. */
  function playAnim(p, w, at, layer, side, obs) {
    if (!S.animOn) return;
    const plan = animPlan(p.actual);
    const paRes = plan.kind !== "inplay" ? paResultAt(p) : null; if (paRes) { plan.caption = paRes; plan.sub = null; } // 삼진·볼넷 등: 자막도 '루킹 삼진'·'볼넷'(실제 투구 줄·결과 줄과 같은 낱말, 11/10 총점검). 타구는 짧은 낱말 그대로
    if (reduceMotion() || document.hidden || !at) { drawCaption(layer, w, obs, plan.caption, plan.sub); return; } // 최종 상태만
    flying(true); // 공이 도착할 때까지 결과 글을 가린다(자막과 같은 때 나타나게, 11/10 재점검)
    const x0 = ux(0), y0 = uz(w.zHi) + R_DOT * 2.2, r0 = R_DOT * 2.2, H = (w.zHi - w.zLo) * U;
    const ball = svg("circle", { class: "z-ball" }); setBall(ball, x0, y0, r0, 0.5); layer.append(ball);
    if (plan.swing && side) {
      // 3D 타자가 붙어 있으면: 공이 나타나는 지금부터 도착(flightMs)까지 클립의 연출 기준 시점 앞부분을, 그 뒤 팔로스루를 원속도로(어댑터 swing). 판정(plan)은 그대로
      // hit(11/9 사용자 "유효한 타격·진루·홈런은 치고 나가는 동작"): 인플레이이고 자료의 타석 결과가 안타·홈런(BADGE_OF "hit": single·double·triple·home_run)일 때만. 아웃·실책 출루·파울은 contact 그대로. 모델에 hit 클립이 없으면 어댑터가 contact로 대체
      const exitKind = exitKindOf(p) && b3HasExit(exitKindOf(p), side) ? exitKindOf(p) : null; // v4: 이 공으로 타석이 끝나고 모델에 나가기 클립이 있으면 스윙 뒤 나가기(출루 = 달리기, 아웃 = 옆걸음). 그때는 안타도 hit 클립 대신 contact 스윙 뒤 달리기(11/9 사용자). 없으면 전과 같음
      const swingKind = plan.kind === "miss" ? "miss" : !exitKind && plan.kind === "inplay" && BADGE_OF[(p.actual || {}).event] === "hit" ? "hit" : "contact";
      const sw = B3.api && B3.api.ok() ? B3.api.swing(swingKind, plan.flightMs, exitKind ? { follow: EXIT_FOLLOW[swingKind] } : undefined) : null;
      if (sw) {
        let fallen = false; // 연출 도중 3D가 멈추면(문맥 상실 등) 그 자리에서 해제하고 SVG 스윙으로 넘어간다(다음 투구까지 타자가 안 보이는 일 방지, 11/6 D-F3류 점프보다 공백이 더 나쁨)
        // hit(안타·홈런) 클립일 때만: 마지막 0.3 s쯤(u ≥ HIT_FADE_FROM)에 상자를 서서히 투명하게 — 타자가 1루 쪽으로 달려 틀 밖으로 나가며 사라지고, 끝나면 대기 자세가 0.35 s에 걸쳐 다시 나타난다(끝 자세→대기 컷에서 가장자리에 남은 몸이 튀어 보이는 것을 가림; 11/9 중계 캡처)
        const fadeBox = sw.kind === "hit" && B3.api.container ? B3.api.container : null; // 어댑터가 실제로 고른 재생 항목(kind)으로 판단(클립 이름이 아니라; 독립 검토 지적)
        run(sw.ms, (t) => t, (u) => { if (fallen) return; if (B3.api && B3.api.ok()) { sw.frame(u); if (fadeBox) b3Opacity(fadeBox, u < HIT_FADE_FROM ? 1 : (1 - u) / (1 - HIT_FADE_FROM), false); return; } fallen = true; detach3D("3D 중단(연출 중)"); swingBat(side); }, () => { if (!fallen && B3.api && B3.api.ok()) { if (exitKind && playExit(exitKind, side)) return; B3.api.reset(b3Still()); if (fadeBox) b3Opacity(fadeBox, 1, true); } }, "raf3d"); // 끝나면 나가기 동작(v4) 또는 대기 동작으로(모듈이 0.35 s 섞어 넘어감; 11/9 사용자 "자세 전후엔 항상 대기 자세")
      } else later(() => swingBat(side), Math.max(0, plan.flightMs - 140)); // SVG: 도착 0.14초 전에 방망이가 돌기 시작
    } else if (side && (plan.kind === "take" || plan.kind === "block")) {
      // 안 치는 공(볼·스트라이크·블록, 11/9 사용자 "스트라이크나 볼일 때 이모션"): 3D 타자가 붙어 있고 모델에 반응 클립이 있으면 공이 도착한 뒤 한 발 물러나는 반응(어댑터 react). 끝나면 대기 동작으로.
      // SVG 타자·반응 클립 없는 모델(마네킹)은 전처럼 아무 동작 없음. 판정·자막은 그대로
      const exitKind = exitKindOf(p) && b3HasExit(exitKindOf(p), side) ? exitKindOf(p) : null; // v4: 볼넷(출루) = 반응 뒤 달리기, 루킹 삼진(아웃) = 반응 뒤 옆걸음
      const rx = B3.api && B3.api.ok() && typeof B3.api.react === "function" ? B3.api.react(plan.flightMs, exitKind ? { follow: EXIT_FOLLOW.take } : undefined) : null; // react 없는(옛 캐시) 어댑터는 마네킹처럼 반응 없음
      if (rx) {
        let fallen = false;
        run(rx.ms, (t) => t, (u) => { if (fallen) return; if (B3.api && B3.api.ok()) { rx.frame(u); return; } fallen = true; detach3D("3D 중단(연출 중)"); }, () => { if (!fallen && B3.api && B3.api.ok()) { if (exitKind && playExit(exitKind, side)) return; B3.api.reset(b3Still()); } }, "raf3d");
      }
    }
    run(plan.flightMs, easeIn, (k) => setBall(ball, lerp(x0, at.x, k), lerp(y0, at.y, k), lerp(r0, R_DOT, k), lerp(0.5, 0.95, k)), () => {
      flying(false); drawCaption(layer, w, obs, plan.caption, plan.sub);
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

  // ----- 4b'. 나가기 동작(v4, 11/9 사용자 "출루 상황일 때 스윙 후에 Fast Run, 아웃 상황에선 좌타·우타가 상황에 맞게 strafe walking") -----
  /* 이 공으로 타석이 끝날 때만(자료 pas: complete, last_index, event). 출루(안타·2루타·3루타·홈런·볼넷·고의4구·몸에 맞는 공·실책 출루) = 달리기,
   * 아웃(삼진·타구 아웃·병살 등) = 옆걸음. 그 밖(자료 없음)은 전처럼 대기 자세로. 좌타·우타별 클립은 어댑터가 고른다(_l 좌타 = 거울, 바깥쪽으로). */
  const EXIT_FOLLOW = { contact: 0.85, miss: 0.9, take: 0.8 }; // 나가기가 이어질 때 스윙·반응을 기준 시점 뒤 몇 초까지만 재생할지(팔로스루가 끝나는 무렵)
  /* 나가기 진행률 [from, to] 구간에서 3D 상자 투명도 1→0(부드럽게). 우타자 달리기는 존 쪽(안쪽) 틀 가장자리에 닿기 전에 거의 사라지게 일찍(독립 검토: 머리가 u≈0.42에 닿음).
   * 나가는 동안 상자 안쪽 가장자리에 마스크(.exiting)를 걸어 잘린 선이 보이지 않게. 끝나면 대기 자세가 0.35 s에 나타난다 */
  const EXIT_FADE = { run_R: [0.12, 0.42], run_L: [0.3, 0.75], strafe_R: [0.35, 0.8], strafe_L: [0.35, 0.8] };
  const smoothFade = (u, a, b) => { const t = Math.min(1, Math.max(0, (u - a) / (b - a))); return 1 - t * t * (3 - 2 * t); };
  /* 타자가 베이스에 나가는 결과(배지 색 표와 따로: 포스 아웃·야수 선택은 대개 타자가 1루에 산다) / 타자가 아웃되는 결과 */
  const EXIT_RUN = new Set(["single", "double", "triple", "home_run", "walk", "intent_walk", "hit_by_pitch", "field_error", "fielders_choice", "fielders_choice_out", "force_out", "catcher_interf"]);
  const EXIT_OUT = new Set(["strikeout", "strikeout_double_play", "field_out", "grounded_into_double_play", "double_play", "triple_play", "sac_fly", "sac_bunt", "sac_fly_double_play", "sac_bunt_double_play"]);
  function exitKindOf(p) {
    const pa = p && S.paOf.get(p.pa_key);
    if (!pa || !pa.complete || p.index !== pa.last_index || !pa.event) return null;
    return EXIT_RUN.has(pa.event) ? "run" : EXIT_OUT.has(pa.event) ? "strafe" : null;
  }
  /** 어댑터에 그 나가기 클립이 있는지(없으면 스윙·반응을 끝까지 재생하고 전처럼 대기로) */
  function b3HasExit(kind, side) { return !!(B3.api && typeof B3.api.exit === "function" && side && B3.api.play && B3.api.play[`${kind}_${side === "L" ? "l" : "r"}`]); }
  /** 스윙·반응이 끝난 자리에서 나가기 동작을 재생한다. 애니메이션 끔·감속 모션이면 하지 않는다. 시작했으면 true */
  function playExit(kind, side) {
    const api = B3.api; if (!api || !S.animOn || reduceMotion() || !b3HasExit(kind, side)) return false;
    const ex = api.exit(kind, side); if (!ex) return false;
    const box = api.container; let fallen = false;
    run(ex.ms, (t) => t, (u) => {
      if (fallen) return;
      if (B3.api === api && api.ok()) { ex.frame(u); const [fa, fb] = EXIT_FADE[`${kind}_${side}`] || [0.35, 0.8]; b3Opacity(box, smoothFade(u, fa, fb), false); return; }
      fallen = true; detach3D("3D 중단(나가기 중)");
    }, () => { box.classList.remove("exiting"); if (!fallen && B3.api === api && api.ok()) { api.reset(b3Still()); b3Opacity(box, 1, true); } }, "raf3d");
    box.classList.add("exiting");
    return true;
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
    B3.api = api; S.b3Lost = false; S.b3Tries = 0; // 연속 실패만 센다
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
    if (reason && /문맥|중단/.test(reason)) { S.b3Lost = true; b3Later(1500); } // 폰 앱 전환·잠금으로 문맥을 잃으면 화면이 보일 때 다시 붙인다(최대 3번, 11/10 총점검)
  }
  function b3Later(ms) { clearTimeout(S.b3Timer); S.b3Timer = setTimeout(() => { S.b3Timer = 0; b3Retry(); }, ms); } // 다시 붙이기 예약은 늘 하나만(앞 예약은 지운다, 11/10 4차; 울리면 표시를 지운다, 5차)
  function b3Retry() {
    if (B3.api || !S.b3Lost || document.hidden || (S.b3Tries || 0) >= 3 || !window.PZBatter3D || typeof window.PZBatter3D.init !== "function") return;
    if (window.PZBatter3D.status && window.PZBatter3D.status().busy) return; // 이미 읽는 중이면 그 결과를 기다린다(횟수에 넣지 않음)
    S.b3Tries = (S.b3Tries || 0) + 1;
    Promise.resolve(window.PZBatter3D.init()).then((api) => { if (!api && !B3.api && S.b3Lost && S.b3Tries < 3) b3Later(S.b3Tries === 1 ? 3000 : 8000); }).catch(() => { /* SVG 타자 그대로 */ }); // 실패하면 3초·8초 뒤 다시(화면이 계속 보여도, 11/10 3차)
  }
  document.addEventListener("visibilitychange", () => { if (!document.hidden && S.b3Lost && !B3.api && !S.b3Timer) b3Later(600); }); // 기다리는 예약(1.5·3·8초)이 있으면 앞당기지 않는다(앱 전환으로 3번을 몇 초 만에 다 쓰지 않게, 11/10 5차)
  /** 선택 투구의 타석 방향(side)에 맞춰 3D 상자를 보이는 띠로 옮기고 idle. side가 없거나 3D가 없으면 열 폭을 원래대로 */
  function b3Show(side) {
    const row = zoneRow(); if (!row) return;
    if (B3.api && !B3.api.ok()) detach3D("3D 중단(WebGL 문맥 상실 등)");
    if (!B3.api || !side) { row.classList.remove("has3d", "side-l", "side-r"); return; }
    const api = B3.api, band = $(side === "L" ? "bat-left" : "bat-right");
    if (api.container.parentNode !== band) band.append(api.container);
    row.classList.add("has3d"); row.classList.toggle("side-l", side === "L"); row.classList.toggle("side-r", side === "R");
    api.setSide(side); api.setTheme(document.documentElement.dataset.theme === "dark" ? "dark" : "light");
    if (typeof api.setUniform === "function") api.setUniform(uniformFor(S.P[S.sel])); // v4: 공격 팀 유니폼 색(사람형 모델만, 마네킹은 무동작)
    api.resize(); api.reset(b3Still());
  }

  // ----- 4d. 유니폼 색(v4, 11/9 사용자 "팀 테마 색상에 맞춰 너무 빨갛고 파랗지 않게 자연스럽게") -----
  /* 공격 팀(초 = 원정, 말 = 홈) 기준. 홈 팀은 흰 유니폼, 원정 팀은 회색 원정 유니폼(야구 관례). 팀 색은 채도를 낮춰 소매·양말·벨트·헬멧·줄무늬에만.
   * 로고·글자는 넣지 않는다(구단 상표). 값은 텍스처 픽셀 색 옮기기(batter3d.js recolorPixels)의 입력이다. 목록에 없는 팀은 중립(남색). */
  const TEAM_TONE = {
    SD: { accent: "#3d2d23", stripe: "#8c7a66", helmet: "#3a2b21" }, // 샌디에이고: 짙은 갈색, 옅은 갈색 줄무늬
    CHC: { accent: "#24396b", stripe: "#7d8aa6", helmet: "#22376a" }, // 컵스: 짙은 남청(원색 파랑보다 어둡고 탁하게)
  };
  const TONE_DEFAULT = { accent: "#2b3446", stripe: "#8a93a3", helmet: "#283143" };
  function uniformFor(p) {
    if (!p || !S.data) return null;
    const g = S.data.game, home = !isTop(p.half), abbr = home ? g.home_abbr : g.away_abbr, tone = TEAM_TONE[abbr] || TONE_DEFAULT;
    return {
      body: home ? { base: "#f3efe7", accent: tone.accent, stripe: tone.stripe, stripeAmt: 0.55 } : { base: "#b9bdc0", accent: tone.accent, stripe: "#a3a8ac", stripeAmt: 0.25 },
      helmet: { color: tone.helmet, lift: 0.55 },
    };
  }
  // ----- 8. 시트(v4): Song 고정 빌드(c47fe6cb)의 시트(.sv-backdrop/.sv-sheet frame-c)와 같은 내용·문구·순서 -----
  /* 사양은 Song 번들을 읽고 실제 앱(V3 로컬)과 대조해 정리한 것(11/9, 자세히 시트는 262구 전부 일치 확인). 다른 점(v4 결정):
   *   - 머리의 점수·이닝별 점수는 보고 있는 공 시점(이 공 던지기 전)까지만. Song은 끝난 경기면 최종 점수.
   *   - 아래 메뉴 '추천'은 추천 화면으로 돌아가기(Song은 자세히 시트). '라인업'은 화면(v2 라인업).
   * 시트는 하나만. 열린 채 고른 공이 바뀌면(‹ ›) 같은 시트를 고른 공 기준으로 다시 그리고 크기·스크롤·포커스(data-fk)를 유지한다. 값이 없으면 '—'. */
  const TEAM_KO = { "Chicago Cubs": "컵스", "San Diego Padres": "샌디에이고" }; // Song 번들 팀 이름표에서 이 경기 두 팀(확인한 값만). 없는 팀은 영문 이름 마지막 낱말(Song과 같은 규칙)
  const teamKo = (full) => TEAM_KO[full] || String(full || DASH).split(" ").slice(-1)[0];
  const DASH = "—";
  const halfTag = (inning, half) => `${inning}회 ${halfWord(half)}`;
  const pickTag = (p) => `${halfTag(p.inning, p.half)} · ${(p.batter && p.batter.name) || "타자 미상"} · ${text(p.pitch_number)}구`;
  const STAT_NOTE = "경기 전 시즌 기록 미확인. 오늘 기록은 현재 공식 피드의 해당 시점까지 사건을 재구성한 값으로 이후 기록 정정이 반영될 수 있습니다. 출루는 안타+볼넷+몸에 맞는 공입니다. 확인되지 않은 값은 —로 표시합니다.";
  const RECORD_NOTE = "공개된 시점까지의 기록이며 이후 정정될 수 있어요. 출루는 안타·볼넷·몸에 맞는 공을 합한 값이에요.";
  const KIND_SHEET = { ball: "볼", inplay: "타격", strike: "스트라이크·파울", unknown: "결과 미확인" };
  /** 위치 이름(Song Sr): 자료 zone_label의 좌우(포수 기준)를 투수 시점으로 바꾸고, '가운데 높이 중앙' → '한가운데', '가운데 높이 ' → '가운데 ' */
  const placeWord = (s) => String(s || "").replace(/왼쪽|오른쪽/g, (w) => (w === "왼쪽" ? "오른쪽" : "왼쪽")).replace("가운데 높이 중앙", "한가운데").replace("가운데 높이 ", "가운데 ");
  /** 속도(Song Ms, km/h 기본): 공백 없이 '155km/h' */
  const speedWord = (mph) => (isNum(mph) ? `${Math.round(mph * 1.609344)}km/h` : "");
  /** 받침 있으면 '은', 없으면 '는'(마지막 글자 기준) */
  const topicParticle = (word) => { const ch = String(word).slice(-1).charCodeAt(0) - 44032; return ch >= 0 && ch < 11172 && ch % 28 !== 0 ? "은" : "는"; };
  const kstClock = (iso) => { const d = new Date(iso); if (isNaN(d)) return "시간 미정"; const k = new Date(d.getTime() + 9 * 3600e3); return `${String(k.getUTCHours()).padStart(2, "0")}:${String(k.getUTCMinutes()).padStart(2, "0")}`; };
  /** 타석이 이 공으로 끝났으면 그 타석 결과 글(result_text, 없으면 event_label), 아니면 null */
  function paResultAt(p) {
    if (!p || !p.actual || !p.actual.event) return null;
    const pa = S.paOf.get(p.pa_key); if (!pa || !pa.complete) return null;
    return pa.result_text || koLabel(pa.event_label, pa.event) || "결과 기록 없음";
  }
  /** 추천 상태(Song yr): ready(후보 있음) / unsupported / missing */
  function recState(rec) {
    const cands = rec && rec.status === "ready" && Array.isArray(rec.candidates) ? [...rec.candidates].sort((a, b) => a.rank - b.rank).slice(0, 3) : [];
    const st = cands.length ? "ready" : rec && (rec.status === "unsupported" || rec.status === "unavailable") ? "unsupported" : "missing";
    return { st, cands };
  }
  function recWhy(rec, st) {
    if (st === "unsupported") return rec.reason !== null && rec.reason !== undefined ? rec.reason : "추천을 지원하지 않는 상황이에요.";
    if (!rec) return "이 시점에는 추천이 없어요";
    return rec.reason && rec.reason.trim() !== "이 투구의 저장된 추천이 없습니다." ? rec.reason : "이 공은 기록된 추천이 없어요.";
  }

  function openSheet(kind, opts) {
    if (!S.data || !SHEETS[kind] || !S.P[S.sel]) return;
    const o = opts || {};
    const ret = o.from || (S.sheet ? S.sheet.ret : document.activeElement);
    if (S.sheet) closeSheet(false);
    const backdrop = el("div", { class: "sh-backdrop" });
    const sheet = el("div", { class: "sh", role: "dialog", "aria-modal": "true", "aria-labelledby": "sh-title", tabindex: "-1" });
    const grip = el("button", { type: "button", class: "sh-grip", "aria-expanded": "false", "aria-label": "시트 크게 보기" }, el("i", { "aria-hidden": "true" }));
    const head = el("div", { class: "sh-head" }), body = el("div", { class: "sh-body" });
    sheet.append(grip, head, body); backdrop.append(sheet); $("sheet-root").append(backdrop);
    S.sheet = { kind, backdrop, sheet, head, body, grip, ret, state: Object.assign({}, o.state) };
    const setFull = (full) => { sheet.classList.toggle("full", full); grip.setAttribute("aria-expanded", String(full)); grip.setAttribute("aria-label", full ? "시트 반만 보기" : "시트 크게 보기"); if (S.sheet && S.sheet.sheet === sheet) renderSheetLayout(); };
    const openedAt = performance.now();
    sheet.addEventListener("click", (e) => { if (e.detail > 0 && performance.now() - openedAt < 350) { e.preventDefault(); e.stopPropagation(); } }, true); // 연 직후 두 번째 누르기가 시트 안 버튼(문자 로그 줄 등)을 눌러 다른 타석으로 가지 않게. 키보드(detail 0)는 그대로(11/10 3차)
    backdrop.addEventListener("click", (e) => { if (e.target !== backdrop) return; if (performance.now() - openedAt > 350) closeSheet(true); else sheet.focus({ preventScroll: true }); }); // 무시한 두 번째 누르기에도 포커스는 시트에(Esc가 계속 듣게, 11/10 재점검) // 연 직후 두 번째 누르기가 배경에 떨어져 바로 닫히지 않게(11/10 총점검)
    grip.addEventListener("click", (e) => { const d = sheet.dataset.dragged; delete sheet.dataset.dragged; if (d && e.detail > 0) return; setFull(!sheet.classList.contains("full")); }); // 끌기 직후 포인터 클릭만 무시(키보드 Enter·Space는 detail 0, 11/10 재점검)
    body.addEventListener("scroll", () => { if (!sheet.classList.contains("full") && body.scrollTop > 4) setFull(true); }, { passive: true }); // Song: 반 높이에서 본문을 4px 넘게 내리면 크게(한 방향)
    sheet.addEventListener("keydown", sheetKeys);
    document.documentElement.classList.add("sheet-open"); // html에 걸어야 뷰포트 스크롤이 잠기고 머리(sticky)가 제자리(독립 검토)
    wireSheetDrag(sheet, head, grip, setFull);
    renderSheet();
    sheet.focus({ preventScroll: true });
    renderNavState(); if (S.auto) renderAuto();
  }
  function closeSheet(restoreFocus) {
    const sh = S.sheet; if (!sh) return;
    S.sheet = null; sh.backdrop.remove(); document.documentElement.classList.remove("sheet-open");
    renderNavState(); if (S.auto) renderAuto();
    let r = sh.ret; // "chips"·"row" 표지는 지금 화면의 같은 컨트롤로(11/10 재점검)
    if (r === "row") r = $("pa-list").querySelector('.prow[aria-pressed="true"]') || $("btn-detail"); else if (r === "chips") r = $("pp-recs").querySelector(".chips") || $("btn-detail");
    if (restoreFocus && r && r.isConnected && typeof r.focus === "function") r.focus({ preventScroll: true });
  }
  /** 손잡이·머리 끌기(Song): 위로 40px 넘게 → 크게, 아래로 60px 넘게 → 크게였으면 반, 반이었으면 닫기. 8px 넘게 끌면 손잡이 누르기는 무시. 머리의 다른 버튼에서 시작한 끌기는 무시 */
  function wireSheetDrag(sheet, head, grip, setFull) {
    let y0 = null, dy = 0, id = null, h0 = 0;
    const start = (e) => { if (e.button !== undefined && e.button !== 0) return; const t = e.target; if (t.closest("button") && t.closest("button") !== grip) return; y0 = e.clientY; dy = 0; id = e.pointerId; h0 = sheet.getBoundingClientRect().height; try { e.currentTarget.setPointerCapture(id); } catch (err) { /* 무시 */ } };
    const move = (e) => { if (y0 === null || e.pointerId !== id) return; dy = e.clientY - y0; if (Math.abs(dy) > 8) sheet.dataset.dragged = "1"; sheet.style.transition = "none"; sheet.style.transform = dy > 0 ? `translateY(${dy}px)` : ""; sheet.style.height = dy < 0 && !sheet.classList.contains("full") ? `${h0 - dy}px` : ""; }; // Song처럼 끄는 동안 따라 움직인다(max-height가 위를 막음, 11/10 총점검)
    const end = (e) => {
      if (y0 === null || (e && e.pointerId !== id)) return;
      y0 = null; sheet.style.transition = ""; sheet.style.transform = ""; sheet.style.height = "";
      if (dy < -40) setFull(true);
      else if (dy > 60) { if (sheet.classList.contains("full")) setFull(false); else closeSheet(true); }
      if (Math.abs(dy) <= 8) delete sheet.dataset.dragged;
    };
    for (const el2 of [grip, head]) { el2.addEventListener("pointerdown", start); el2.addEventListener("pointermove", move); el2.addEventListener("pointerup", end); el2.addEventListener("pointercancel", end); el2.style.touchAction = "none"; }
  }
  /** 다른 시트로 바꾼다(Song Te: 연 버튼은 처음 것 그대로) */
  function swapSheet(kind, state) { const ret = S.sheet ? S.sheet.ret : null; openSheet(kind, { from: ret, state }); }
  /** Esc 닫기, Tab은 시트 안에서만 돈다 */
  function sheetKeys(e) {
    const sh = S.sheet; if (!sh) return;
    if (e.key === "Escape") { e.preventDefault(); closeSheet(true); return; }
    if (e.key !== "Tab") return;
    const f = [...sh.sheet.querySelectorAll("button, select, a[href], [tabindex]")].filter((x) => !x.disabled && x.tabIndex >= 0 && x.getAttribute("tabindex") !== "-1" && x.getClientRects().length); // 고르지 않은 탭(tabindex -1)은 Tab이 안 가므로 뺀다
    if (!f.length) return;
    const first = f[0], last = f[f.length - 1];
    if (e.shiftKey && (document.activeElement === first || document.activeElement === sh.sheet)) { e.preventDefault(); last.focus(); }
    else if (!e.shiftKey && document.activeElement === last) { e.preventDefault(); first.focus(); }
  }
  function renderSheet() {
    const sh = S.sheet, p = S.P[S.sel]; if (!sh || !p) return;
    const ae = document.activeElement, fk = ae && sh.sheet.contains(ae) && ae.dataset ? ae.dataset.fk : null;
    const keepTop = sh.state.keepScroll ? sh.body.scrollTop : 0;
    sh.head.textContent = ""; sh.body.textContent = "";
    const title = el("h2", { id: "sh-title" }), tools = el("div", { class: "sh-tools" });
    SHEETS[sh.kind](p, { title, tools, body: sh.body, state: sh.state });
    sh.sheet.classList.toggle("tall", sh.kind === "mix" || (sh.kind === "player" && sh.state.tab === "pitcher")); // Song: 투수 탭·구종은 반 높이 56dvh/420px
    const close = el("button", { type: "button", class: "sh-close", "data-fk": "close", text: "닫기" });
    close.addEventListener("click", () => closeSheet(true));
    tools.append(close); sh.head.append(title, tools);
    sh.state.keepScroll = false; sh.body.scrollTop = keepTop;
    if (fk) { let n = sh.sheet.querySelector(`[data-fk="${fk}"]`); if (n && n.disabled && (fk === "prev" || fk === "next")) n = sh.sheet.querySelector(`[data-fk="${fk === "prev" ? "next" : "prev"}"]`); if (n && !n.disabled) n.focus({ preventScroll: true }); else sh.sheet.focus({ preventScroll: true }); } // 끝에서 비활성이 된 화살표는 반대쪽으로(주 화면과 같은 규칙, 11/10 3차)
  }
  /** 크게/작게 바뀔 때 크기에 따라 보이는 부분(구종 시트의 위치 그림)을 다시 그린다 */
  function renderSheetLayout() { if (S.sheet && S.sheet.kind === "mix") { S.sheet.state.keepScroll = true; renderSheet(); } }
  /** 시트 안에서 공을 고른다(시트는 열어 둔 채, 스크롤·크기 유지). 3D·연출·머리·본문도 같이 바뀐다 */
  function pickInSheet(i) { if (!S.P[i] || !S.sheet) return; S.sheet.state.keepScroll = true; selectPitch(i, { scroll: false }); }
  /** 공을 고르고 자세히 시트를 연다(Song oa: 기록의 타석, 타석 선택) */
  function pickAndDetail(i, from) { if (!S.P[i]) return; const ret = from || (S.sheet ? S.sheet.ret : null); if (S.sheet) closeSheet(false); selectPitch(i, { scroll: false }); openSheet("detail", { from: ret }); }

  // --- 작은 그리기 도구 ---
  function table(cls, heads, rows, opts) {
    const t = el("table", { class: cls }), o = opts || {};
    const hr = el("tr"); heads.forEach((h, i) => hr.append(el("th", { scope: "col", class: (o.headClass && o.headClass[i]) || null, text: h }))); t.append(el("thead", null, hr));
    const tb = el("tbody");
    for (const r of rows) {
      const tr = el("tr", r.cls ? { class: r.cls } : null);
      r.cells.forEach((c, i) => { if (c instanceof Node) { tr.append(c); return; } const isHead = i === 0 && o.rowHead; tr.append(el(isHead ? "th" : "td", Object.assign({ text: c }, isHead ? { scope: "row" } : {}, r.cellClass && r.cellClass[i] ? { class: r.cellClass[i] } : {}))); });
      tb.append(tr);
    }
    t.append(tb); return t;
  }
  function dl(rows, cls) { const d = el("dl", { class: "sh-dl" + (cls ? " " + cls : "") }); for (const [k, v, lang] of rows) d.append(el("dt", { text: k }), el("dd", lang ? { text: v, lang } : { text: v })); return d; }

  // --- 작은 존(Song 상세 창: 가로 반폭 1.25 ft, 높이 존 ±0.45 ft, 실제 공이 밖이면 그 공 + 0.3 ft까지 넓힘, 여백 0.16 ft) ---
  function detailWindow(bounds, a) {
    let xMax = 1.25, zLo = bounds.bottom - 0.45, zHi = bounds.top + 0.45;
    if (a && isNum(a.x) && Math.abs(a.x) <= 2.2) xMax = Math.max(xMax, Math.abs(a.x) + 0.3);
    if (a && isNum(a.z) && a.z >= -0.5 && a.z <= 5.5) { zLo = Math.min(zLo, a.z - 0.3); zHi = Math.max(zHi, a.z + 0.3); }
    const pad = 0.16; return { xMin: -xMax, xMax, zLo, zHi, vb: { x: -(xMax + pad) * U, y: -(zHi + pad) * U, w: 2 * (xMax + pad) * U, h: (zHi - zLo + 2 * pad) * U } };
  }
  function zoneFrame(w, bounds, cls) {
    const root = svg("svg", { class: cls, viewBox: `${w.vb.x} ${w.vb.y} ${w.vb.w} ${w.vb.h}`, preserveAspectRatio: "xMidYMid meet", role: "img" });
    const left = -PLATE_HALF * U, right = PLATE_HALF * U, top = uz(bounds.top), bottom = uz(bounds.bottom);
    root.append(svg("rect", { class: "z-box", x: left, y: top, width: right - left, height: bottom - top }));
    for (const i of [1, 2]) {
      root.append(svg("line", { class: "z-grid", x1: left + (right - left) * i / 3, x2: left + (right - left) * i / 3, y1: top, y2: bottom }));
      root.append(svg("line", { class: "z-grid", y1: top + (bottom - top) * i / 3, y2: top + (bottom - top) * i / 3, x1: left, x2: right }));
    }
    return { root, top, bottom };
  }
  const SMALL_MARGIN = { x: 1.25 - PLATE_HALF, z: 0.45 }; // 작은 존 창(detailWindow)의 존 밖 여백(ft): 창 밖 표식을 이만큼 안쪽까지 들일 수 있다
  const zoneBounds = () => (S.data.zone_bounds && isNum(S.data.zone_bounds.top) && isNum(S.data.zone_bounds.bottom) ? S.data.zone_bounds : { bottom: 1.6, top: 3.3899 });
  /** 존 그림 상자(폭 boxW px, 높이 190 px)에 viewBox가 들어가는 배율 F(Song: min(W/vb.w, (H−16)/vb.h)). u = 1 px의 그리기 단위 */
  const pxUnit = (w, boxW) => 1 / Math.max(1e-6, Math.min((boxW > 0 ? boxW : 343) / w.vb.w, (190 - 16) / w.vb.h));
  const fs = (px, u) => ({ style: `font-size:${(px * u).toFixed(2)}px` }); // SVG 글자 크기를 화면 px로(CSS 고정 크기보다 우선)
  function detailZone(p, boxW) {
    const bounds = zoneBounds(), a = p.actual || {}, w = detailWindow(bounds, a), { root, top, bottom } = zoneFrame(w, bounds, "dt-zone"), u = pxUnit(w, boxW);
    const parts = [], rs = recState(p.rec), rects = [];
    if (rs.st === "ready") for (const g of groupTargets(rs.cands)) {
      const sq = 11 * u, label = g.ranks.join("·"), hw = Math.max(11, 5 + 4.5 * label.length) * u;
      const al = 7 * u, at = inset(place(g, w), sq, al, SMALL_MARGIN), node = svg("g", { class: `z-rec r${g.ranks[0]}${at.out ? " out" : ""}` });
      node.append(svg("rect", { x: at.x - hw, y: at.y - sq, width: 2 * hw, height: 2 * sq, rx: 5 * u })); if (at.out) node.append(arrow(at, sq, al));
      const tx = svg("text", Object.assign({ x: at.x, y: at.y + 5.5 * u, "text-anchor": "middle" }, fs(15, u)), label); node.append(tx); root.append(node);
      rects.push({ x: at.x, y: at.y, hw, hh: sq, tx, cls: `z-rec r${g.ranks[0]}` });
      for (const r of g.ranks) parts.push(`추천 ${r}순위 위치 네모`);
    }
    const setup = a.catcher_setup && isNum(a.catcher_setup.plate_x_feet) ? a.catcher_setup.plate_x_feet : null;
    let mittBox = null; // 미트 글자 상자(옮긴 번호가 피한다, Song el.box)
    if (setup !== null) { // 미트(포수 자리 잡기) 위치: 세로 점선 + '미트'
      const mx = ux(setup), inside = Math.abs(setup) <= w.xMax, x = inside ? mx : (mx > 0 ? 1 : -1) * (w.xMax * U - 8 * u);
      const g = svg("g", { class: "z-mitt" });
      { const rl = (inside ? 26 : 34) * u; mittBox = { x: x - rl / 2, y: top - 6 * u - 16 * u + 3 * u, w: rl, h: 16 * u }; }
      g.append(svg("line", { x1: x, x2: x, y1: top - 4 * u, y2: bottom + 4 * u }));
      g.append(svg("text", Object.assign({ x, y: top - 6 * u, "text-anchor": "middle" }, fs(14, u)), inside ? "미트" : mx > 0 ? "미트→" : "←미트"));
      root.append(g);
    }
    if (isNum(a.x) && isNum(a.z)) {
      const r9 = 9 * u, al = 7 * u, kind = kindOf(a.description), at = inset(place({ x: a.x, z: a.z }, w), r9, al, SMALL_MARGIN), node = svg("g", { class: `z-dot ${kind} sel${at.out ? " out" : ""}` });
      node.append(svg("circle", { cx: at.x, cy: at.y, r: r9 })); if (at.out) node.append(arrow(at, r9, al));
      node.append(svg("circle", { class: "z-ring", cx: at.x, cy: at.y, r: 12 * u }));
      const hit = rects.filter((q) => Math.abs(q.x - at.x) < q.hw + 14 * u && Math.abs(q.y - at.y) < q.hh + 14 * u); // 실제 공이 추천 네모와 겹침(Song sv-g1-out / sv-rec-lift). 14 = 고리 12 + 2(Song 고리 상자 Nt, 11/10 3차)
      if (!hit.length) node.append(svg("text", Object.assign({ x: at.x, y: at.y + 4 * u, "text-anchor": "middle" }, fs(12, u)), String(p.pitch_number)));
      root.append(node);
      if (hit.length) {
        for (const q of hit) { const L = (6 + 8 * q.tx.textContent.length) * u; if (Math.abs(q.x - at.x) >= L / 2 + 14 * u || Math.abs(q.y - 0.5 * u - at.y) >= 9 * u + 14 * u) continue; q.tx.setAttribute("visibility", "hidden"); root.append(svg("text", Object.assign({ class: `rec-lift ${q.cls.split(" ").pop()}`, "aria-hidden": "true", x: q.x, y: q.y + 5.5 * u, "text-anchor": "middle" }, fs(15, u)), q.tx.textContent)); } // Song Vt: 순위 글자 상자가 고리 상자와 겹칠 때만 위로 올리고 원래 글자는 숨김(11/10 4차)
        const m = (6 + 7 * String(p.pitch_number).length) * u, ov = (A, B) => A.x < B.x + B.w && B.x < A.x + A.w && A.y < B.y + B.h && B.y < A.y + A.h, vis = (B) => { const vw = (boxW > 0 ? boxW : 343) * u, vh = 190 * u, vx = w.vb.x + (w.vb.w - vw) / 2, vy = w.vb.y + (w.vb.h - vh) / 2; return B.x >= vx && B.y >= vy && B.x + B.w <= vx + vw && B.y + B.h <= vy + vh; }; // Song $(xe): 그려지는 그림 전체(가로 boxW, 세로 190) 안(11/10 4차)
        const obs = rects.map((q) => ({ x: q.x - q.hw, y: q.y - q.hh, w: 2 * q.hw, h: 2 * q.hh })).concat(mittBox ? [mittBox] : []);
        const X = [[0, -18 * u], [0, 26 * u], [12 * u + m / 2 + 4 * u, 4 * u], [-12 * u - m / 2 - 4 * u, 4 * u]].map(([dx, dy]) => ({ d: [dx, dy], b: { x: at.x + dx - m / 2, y: at.y + dy - 11 * u, w: m, h: 14 * u } }));
        const free = (X.find((c) => vis(c.b) && !obs.some((o) => ov(o, c.b))) || X.find((c) => vis(c.b)) || X[0]).d; // Song dl: 번호 상자가 창 안이고 네모·미트 글자와 안 겹치는 첫 자리(위→아래→오른쪽→왼쪽, 11/10 3차)
        root.append(svg("text", Object.assign({ class: "g1-out", x: at.x + free[0], y: at.y + free[1], "text-anchor": "middle", style: `font-size:${(11 * u).toFixed(2)}px;stroke-width:${(3 * u).toFixed(2)}px` }), String(p.pitch_number))); // 번호는 겹치지 않는 자리로(흰 테두리 화면 3px, Song 값)
      }
      parts.push(`실제 투구 동그라미${at.out ? ` (화면 밖, 가로 ${a.x.toFixed(2)}ft (포수 기준), 높이 ${a.z.toFixed(2)}ft)` : ""}`);
    }
    root.setAttribute("aria-label", `투수 시점 스트라이크존: ${parts.join(", ") || "표시할 위치 없음"}`);
    return root;
  }

  const SHEETS = {
    /** 자세히(Song Pp): 고른 공의 결과·위치·추적값, 그 공을 던지기 전 추천 표. ‹ ›는 경기 전체 공을 넘긴다(끝에서는 비활성) */
    detail(p, c) {
      c.title.textContent = `${halfTag(p.inning, p.half)} · ${text(p.pitch_number)}구 · ${(p.batter && p.batter.name) || "타자"}`;
      const nav = el("span", { class: "sh-nav" });
      const prev = el("button", { type: "button", class: "sh-step", "data-fk": "prev", "aria-label": "이전 공", text: "‹" }), next = el("button", { type: "button", class: "sh-step", "data-fk": "next", "aria-label": "다음 공", text: "›" });
      prev.disabled = p.index <= 0; next.disabled = p.index >= S.P.length - 1;
      prev.addEventListener("click", () => pickInSheet(p.index - 1)); next.addEventListener("click", () => pickInSheet(p.index + 1));
      nav.append(prev, next); c.tools.append(nav);
      const a = p.actual || null;
      const act = el("section", { class: "dt-sec" });
      if (!a) act.append(el("p", { class: "sh-muted", text: "실제 투구 기록 없음" }));
      else {
        const kind = kindOf(a.description), zone = placeWord(a.zone_label), sp = speedWord(a.speed_mph), t = a.tracking || null;
        act.append(el("p", { class: "dt-line" }, el("i", { class: `g1 ${kind} ring`, "aria-hidden": "true", text: text(p.pitch_number) }), el("b", { text: `${a.pitch_label || "구종 미상"}${sp ? " " + sp : ""}` }), el("span", { text: [resultWord(a), zone].filter(Boolean).join(" · ") })));
        act.append(el("div", { class: "dt-zone-box" }, detailZone(p, c.body.clientWidth - 32)));
        act.append(el("p", { class: "dt-legend", "aria-hidden": "true" }, el("span", null, el("i", { class: "k rec" }), "추천"), el("span", null, el("i", { class: `k ${kind}` }), `실제 (${KIND_SHEET[kind]})`), el("span", { text: "투수 시점" })));
        const rows = [["판정", [resultWord(a) || "기록 없음", zone].filter(Boolean).join(" · ")], ["원본 좌표", isNum(a.x) && isNum(a.z) ? `가로 ${a.x.toFixed(2)} ft · 높이 ${a.z.toFixed(2)} ft (포수 기준)` : "위치 정보 없음"]];
        const missing = [];
        for (const [label, v, unit, digits] of [["회전수", t && t.spin_rate_rpm, " rpm", 0], ["익스텐션", t && t.extension_feet, " ft", 1], ["타구 속도", t && t.exit_velocity_mph, " mph"], ["발사각", t && t.launch_angle_deg, "°"], ["비거리", t && t.distance_feet, " ft"]]) {
          if (isNum(v)) rows.push([label, `${digits === undefined ? String(v) : v.toFixed(digits)}${unit}`]); else missing.push(label);
        }
        const res = paResultAt(p); if (res) rows.push(["타석 결과", res]);
        if (a.play_text) rows.push(["원본 기록", a.play_text, "en"]);
        act.append(dl(rows, "facts"));
        if (missing.length) act.append(el("p", { class: "sh-muted dt-missing", text: `${missing.join("·")}${topicParticle(missing[missing.length - 1])} 이 공 자료에 없어요` }));
      }
      c.body.append(act);
      const recSec = el("section", { class: "dt-sec" }, el("h3", { class: "sh-h3", text: "이 공을 던지기 전 추천" }));
      const rec = p.rec || null, rs = recState(rec);
      if (rs.st === "ready") {
        const prov = rec.provenance === "captured_live" ? "경기 중 투구 전에 기록한 추천" : "경기 뒤, 그 공을 던지기 전 정보만으로 계산한 추천";
        recSec.append(el("p", { class: "sh-muted", text: `${prov}${rec.recorded_at ? ` · ${kstClock(rec.recorded_at)} 기록` : ""}` }));
        recSec.append(table("sh-table dt-rec", ["순위 · 구종", "대략 위치", "정책 선택 비중"], rs.cands.map((cd) => ({ cells: [
          el("td", null, el("i", { class: `rk r${Math.min(cd.rank, 3)}`, text: String(cd.rank) }), el("span", { class: "sr-only", text: `${cd.rank}순위 ` }), text(cd.pitch_label)),
          placeWord(cd.zone_label) || "위치 없음",
          (() => { const raw = cd.probability !== null && cd.probability !== undefined ? cd.probability : cd.detail ? cd.detail.probability : null; return isNum(raw) ? `${Math.round(raw * 100)}%` : DASH; })(), // Song Mp: probability ?? detail.probability
        ] }))));
        recSec.append(el("p", { class: "sh-muted", text: "정책 선택 비중은 성공·적중 확률이 아니에요. 위치는 과거 투구 분포의 대략 위치이며, 칸별 가치 지도가 아니에요." }));
      } else recSec.append(el("p", { text: recWhy(rec, rs.st) }));
      c.body.append(recSec);
    },

    /** 선수(Song player-b/p): 타자·투수 탭. 제목은 고른 탭의 선수 이름. 오늘 기록은 고른 공 던지기 전(context_before) */
    player(p, c) {
      const tab = c.state.tab === "pitcher" ? "pitcher" : "batter", g = S.data.game, top = isTop(p.half);
      const person = (tab === "batter" ? p.batter : p.pitcher) || null;
      c.title.textContent = person && person.name ? person.name : "선수 정보";
      const tabs = el("div", { class: "sh-tabs", role: "tablist", "aria-label": "선수" });
      for (const [k, label] of [["batter", "타자"], ["pitcher", "투수"]]) {
        const b = el("button", { type: "button", role: "tab", "aria-selected": String(k === tab), tabindex: k === tab ? "0" : "-1", "data-fk": "tab-" + k, text: label });
        b.addEventListener("click", () => { c.state.tab = k; renderSheet(); });
        tabs.append(b);
      }
      tabs.addEventListener("keydown", (e) => arrowTabs(e, tabs, (b) => { const k = b.dataset.fk; b.click(); const n = S.sheet && S.sheet.sheet.querySelector(`[data-fk="${k}"]`); if (n) n.focus(); }));
      const panel = el("div", { role: "tabpanel", "aria-label": tab === "batter" ? "타자" : "투수" });
      const teamFull = (tab === "batter") === top ? g.away_team : g.home_team, hand = handWord(tab === "batter" ? person && person.side : person && person.hand, tab === "batter" ? "b" : "p");
      panel.append(el("p", { class: "sh-name" }, el("b", { text: person && person.name ? person.name : DASH }), " ", el("span", { text: `${teamKo(teamFull)}${hand ? " · " + hand : ""}` })));
      const ctx = p.context_before || {}, aa = (v, unit) => (isNum(v) ? `${v}${unit}` : `${unit} ${DASH}`);
      const jersey = person && person.jersey ? `#${person.jersey}` : DASH;
      if (tab === "batter") { const b = ctx.batter || {}; panel.append(dl([["등번호", jersey], ["시즌", `AVG ${DASH} · OPS ${DASH}`], ["오늘 · 이 공 전", [aa(b.at_bats, "타수"), aa(b.hits, "안타"), aa(b.on_base, "출루")].join(" · ")]], "facts")); }
      else {
        const q = ctx.pitcher || {};
        panel.append(dl([["등번호", jersey], ["시즌", `ERA ${DASH}`], ["오늘 · 이 공 전", [aa(q.pitches, "구"), aa(q.strikeouts, "삼진"), aa(q.earned_runs, "자책")].join(" · ")]], "facts"));
        const mix = pitchMix(p);
        panel.append(el("h3", { class: "sh-h3", text: `오늘 구종 · 이 공까지 ${mix.total}구` })); // 위 '오늘 · 이 공 전'(이 공 빼고)과 수가 하나 다른 이유를 글로(11/10 총점검; Song은 '오늘 구종 · N구')
        panel.append(mix.total ? mixTable(mix) : el("p", { class: "sh-muted", text: "확인된 구종 기록이 없어요." }));
      }
      panel.append(el("p", { class: "sh-muted", text: STAT_NOTE }));
      c.body.append(tabs, panel);
    },

    /** 구종(Song mix): 고른 공을 던진 투수의 오늘 구종(첫 공부터 고른 공까지 포함). 크게 보면 던진 위치 그림 */
    mix(p, c) {
      const name = p.pitcher && p.pitcher.name ? p.pitcher.name : null;
      c.title.textContent = `${name ? shortName(name) : "투수"} 오늘 구종`;
      const mix = pitchMix(p);
      if (!mix.total) { c.body.append(el("p", { class: "sh-muted", text: "확인된 구종 기록이 없어요." })); return; }
      c.body.append(el("p", { class: "sh-muted", text: `받은 기록 중 구종이 확인된 ${mix.total}구 기준 · 고른 공(${pickTag(p)})까지` }));
      c.body.append(mixTable(mix));
      if (S.sheet && S.sheet.sheet.classList.contains("full")) c.body.append(mixMap(mix));
    },

    /** 기록(Song history): 문자 로그 · 라인업 · 박스 · 분석. 열 때마다 문자 로그부터 */
    record(p, c) {
      c.title.textContent = "경기 기록";
      const seg = ["log", "lineup", "box", "analysis"].includes(c.state.seg) ? c.state.seg : "log";
      const row = el("div", { class: "sh-seg" });
      for (const [k, label] of [["log", "문자 로그"], ["lineup", "라인업"], ["box", "박스"], ["analysis", "분석"]]) {
        const b = el("button", { type: "button", "aria-pressed": String(k === seg), "data-fk": "seg-" + k, text: label });
        b.addEventListener("click", () => { c.state.seg = k; renderSheet(); });
        row.append(b);
      }
      c.body.append(row);
      if (seg === "log") recordLog(p, c);
      else if (seg === "lineup") recordLineup(c);
      else if (seg === "box") recordBox(c);
      else c.body.append(el("div", { class: "sh-unmeasured" }, el("h3", null, "분석 ", el("span", { class: "sh-tag", text: "준비 중" })), el("p", { text: "성분별 책임 분해·기대실점·타구 예상 결과는 아직 연결되지 않았어요." })));
      c.body.append(el("p", { class: "sh-muted", text: RECORD_NOTE }));
    },

    /** 타석 선택(Song Kp, 머리 왼쪽): 반 이닝 고르기(기본 = 고른 공의 반 이닝) + 그 반 이닝의 모든 타석(최종 결과). 누르면 그 타석 첫 공 + 자세히 */
    atbat(p, c) {
      c.title.textContent = "타석 선택";
      const key = c.state.half || `${p.inning}:${p.half}`;
      const halves = []; for (const a of S.pas) { const k = `${a.inning}:${a.half}`; if (!halves.includes(k)) halves.push(k); }
      const sel = el("select", { "aria-label": "이닝과 초말 선택", "data-fk": "half" });
      for (const k of halves) { const [n, h] = k.split(":"); const opt = el("option", { value: k, text: halfTag(Number(n), h) }); if (k === key) opt.selected = true; sel.append(opt); }
      sel.addEventListener("change", () => { c.state.half = sel.value; renderSheet(); });
      const box = el("button", { type: "button", class: "sh-btn", "data-fk": "box", text: "박스스코어" });
      box.addEventListener("click", () => swapSheet("linescore"));
      c.body.append(el("div", { class: "sh-pa-controls" }, el("label", null, "이닝 ", sel), box));
      const list = S.pas.filter((a) => `${a.inning}:${a.half}` === key);
      if (!list.length) { c.body.append(el("p", { class: "sh-muted", text: "공개된 타석이 아직 없어요." })); return; }
      const ol = el("ol", { class: "sh-pa-list" });
      for (const a of list) {
        const viewing = a.pa_key === p.pa_key, res = a.complete ? a.result_text || koLabel(a.event_label, a.event) || "결과 기록 없음" : "타석 진행 중";
        const n = isNum(a.pitch_count) ? a.pitch_count : isNum(a.first_index) && isNum(a.last_index) ? Math.max(0, a.last_index - a.first_index + 1) : "–";
        const b = el("button", { type: "button", class: `sh-pa-item${a.complete ? "" : " open"}`, "data-fk": "pa-" + a.pa_key, "aria-current": viewing ? "true" : null },
          el("span", { class: "who" }, isNum(a.batting_order) && a.batting_order ? `${a.batting_order}번 · ` : "", el("b", { text: (a.batter && a.batter.name) || "타자 미상" }), viewing ? el("small", { text: " · 보는 중" }) : null),
          el("span", { class: "res", text: `${res} · ${n}구` }));
        b.disabled = !isNum(a.first_index) || !S.P[a.first_index];
        b.addEventListener("click", () => pickAndDetail(a.first_index));
        ol.append(el("li", null, b));
      }
      c.body.append(ol);
    },

    /** 이닝별 기록(Song gb, 머리 오른쪽·박스스코어): 고른 공 던지기 전까지 공개된 플레이(자료 linescore_before) */
    linescore(p, c) {
      c.title.textContent = "이닝별 기록";
      const g = S.data.game, ls = p.linescore_before || null, s = p.situation_before || {};
      if (!ls) { c.body.append(el("p", { class: "sh-muted", text: `이닝별 기록은 아직 준비 중이에요. 지금 점수는 ${teamKo(g.away_team)} ${cellOr(s.away_score, cellOr(g.away_score, "–"))} : ${cellOr(s.home_score, cellOr(g.home_score, "–"))} ${teamKo(g.home_team)}예요.` })); return; }
      const inn = Array.isArray(ls.innings) ? ls.innings : [], n = Math.max(9, inn.length, isNum(s.inning) ? s.inning : 0), t = ls.teams || {};
      const cellOf = (side, k) => { const i = inn.find((x) => x.inning === k); return i && isNum(i[side]) ? String(i[side]) : "–"; };
      const heads = ["팀"]; for (let k = 1; k <= n; k++) heads.push(String(k)); heads.push("R", "H", "E", "사사구");
      const rows = [["away", g.away_team], ["home", g.home_team]].map(([side, full]) => {
        const tt = t[side] || {}, cells = [teamKo(full)];
        for (let k = 1; k <= n; k++) cells.push(cellOf(side, k));
        cells.push(el("td", { class: "tot" }, el("b", { text: isNum(tt.runs) ? String(tt.runs) : "–" })), isNum(tt.hits) ? String(tt.hits) : "–", isNum(tt.errors) ? String(tt.errors) : "–", isNum(tt.bb_hbp) ? String(tt.bb_hbp) : "–");
        const cellClass = cells.map((_, ci) => (ci >= 1 && ci <= n && s.inning === ci ? (isTop(s.half) === (side === "away") ? "cur" : "curcol") : null));
        return { cells, cellClass };
      });
      const tb = table("sh-box", heads, rows, { rowHead: true, headClass: heads.map((_, i) => (i >= 1 && i <= n && s.inning === i ? "cur" : i === heads.length - 4 ? "tot" : null)) });
      const sasa = tb.querySelector("thead th:last-child"); if (sasa) sasa.title = "볼넷+몸에 맞는 공";
      const wrap = el("div", { class: "sh-box-scroll" }, tb); c.body.append(wrap);
      { const cur = tb.querySelector("thead th.cur"), Rh = tb.querySelector("thead th.tot"); if (cur && Rh && getComputedStyle(Rh).position === "sticky") { const over = cur.getBoundingClientRect().right - Rh.getBoundingClientRect().left; if (over > 0) wrap.scrollLeft += over + 6; } } // 좁은 화면(합계 고정)에서 지금 이닝이 R 밑에 숨지 않게(11/10 재점검)
      c.body.append(el("p", { class: "sh-muted", text: `공개된 플레이까지만 셉니다. 아직 오지 않은 이닝은 –로 표시해요.${isNum(s.inning) ? ` 강조한 칸은 지금 보는 ${halfTag(s.inning, s.half)}${topicParticle(halfWord(s.half)) === "은" ? "이에요" : "예요"}.` : ""}` })); // '초예요'·'말이에요'(Song 원문은 '초이에요', 11/10 총점검)
    },
  };
  /** Song Sm: 이름 마지막 낱말(Jr. 같은 꼬리가 있으면 두 낱말) */
  function shortName(s) { const c = String(s).trim().split(/\s+/), d = c.length > 2 && /^(Jr\.?|Sr\.?|I{2,3}|IV)$/.test(c[c.length - 1]) ? 2 : 1; return c.length > d ? c.slice(-d).join(" ") : s; }

  /** 오늘 구종(Song Zm): 경기 첫 공부터 고른 공까지(포함), 같은 투수, 구종 코드가 있는 공. 구종 코드별, 많은 순(같으면 먼저 던진 순). 평균 구속 = mph 평균 × 1.609344 반올림 */
  function pitchMix(p) {
    const id = p.pitcher && p.pitcher.id, by = new Map(); let total = 0;
    for (let i = 0; i <= p.index; i++) {
      const q = S.P[i]; if (!q || !q.pitcher || q.pitcher.id !== id) continue;
      const a = q.actual || {}; if (!a.pitch_type) continue;
      total++;
      if (!by.has(a.pitch_type)) by.set(a.pitch_type, { type: a.pitch_type, label: a.pitch_label || a.pitch_type, n: 0, mph: [], pts: [] });
      const r = by.get(a.pitch_type); r.n++; if (isNum(a.speed_mph)) r.mph.push(a.speed_mph); r.pts.push(q);
    }
    const rows = [...by.values()].sort((x, y) => y.n - x.n); // Array.sort는 안정 정렬 → 같은 수는 먼저 던진 순
    return { total, rows };
  }
  function mixTable(mix) {
    return table("sh-table mix", ["구종", "투구 수", "비율", "평균 구속"], mix.rows.map((r) => ({ cells: [r.label, String(r.n), `${Math.round((r.n / mix.total) * 100)}%`, r.mph.length ? `${Math.round((r.mph.reduce((s, v) => s + v, 0) / r.mph.length) * 1.609344)} km/h` : DASH] })));
  }
  /** 크게 본 구종 시트의 '오늘 던진 위치': 공마다 줄임말+번호(같은 첫 글자가 겹치면 두 글자) */
  function mixMap(mix) {
    const sec = el("section", { class: "mix-map" }, el("h3", { class: "sh-h3", text: "오늘 던진 위치" }));
    const firsts = mix.rows.map((r) => r.label.slice(0, 1)), abbr = new Map(mix.rows.map((r, i) => [r.type, firsts.filter((f) => f === firsts[i]).length > 1 ? r.label.slice(0, 2) : r.label.slice(0, 1)]));
    const bounds = zoneBounds(), w = detailWindow(bounds, null), { root } = zoneFrame(w, bounds, "dt-zone"), u = pxUnit(w, S.sheet ? S.sheet.body.clientWidth - 32 : 343);
    let noPos = 0; const marks = new Map();
    for (const [r, q] of mix.rows.flatMap((r) => r.pts.map((q) => [r, q])).sort((x, y) => x[1].index - y[1].index)) { // Song처럼 던진 순서: 겹치면 나중 공이 위, 합친 글자도 던진 순서(11/10 3차)
      const a = q.actual; if (!isNum(a.x) || !isNum(a.z)) { noPos++; continue; }
      const key = `${a.x.toFixed(3)}|${a.z.toFixed(3)}`; // Song: 결과 색 없이 자리로만 합친다
      if (!marks.has(key)) marks.set(key, { x: a.x, z: a.z, labels: [], sel: false });
      const m = marks.get(key); m.labels.push(abbr.get(r.type)); if (q.index === S.sel) m.sel = true;
    }
    for (const m of marks.values()) {
      const r9 = 9 * u, al = 7 * u, at = inset(place({ x: m.x, z: m.z }, w), r9, al, SMALL_MARGIN), g = svg("g", { class: `z-dot label${at.out ? " out" : ""}` }); // Song .sv-actual.label: 흰 원·진한 글자(결과 색 없음, 글자가 원 밖으로 나가도 읽힘)
      g.append(svg("circle", { cx: at.x, cy: at.y, r: r9 })); if (at.out) g.append(arrow(at, r9, al)); g.append(svg("text", Object.assign({ x: at.x, y: at.y + 4 * u, "text-anchor": "middle" }, fs(at.out || m.labels.length > 1 ? 11 : 12, u)), m.labels.join("·"))); /* Song: 창 안 한 글자만 12px, 나머지 11px(11/10 3차) */ root.append(g);
    }
    root.setAttribute("aria-label", "오늘 던진 위치, 투수 시점");
    sec.append(el("div", { class: "dt-zone-box" }, root), el("p", { class: "mix-key", text: mix.rows.map((r) => `${abbr.get(r.type)}=${r.label}`).join(" · ") }));
    sec.append(el("p", { class: "sh-muted", text: `경기 전체 투구가 모두 수신됐다는 뜻은 아니에요. 구속이 없는 공은 평균에서 제외해요.${noPos ? ` 위치 정보가 없는 ${noPos}구는 그림에서 뺐어요.` : ""}` }), el("p", { class: "sh-muted", text: "시즌별 사용률·헛스윙률·피xwOBA는 아직 연결되지 않았어요." }));
    return sec;
  }
  /** 기록 · 문자 로그(Song sb): 첫 공이 고른 공 이전인 타석, 최근 것부터. 마지막 공이 고른 공 뒤면 '타석 진행 중 · (고른 공까지 던진 수)구'. 누르면 그 타석 첫 공 + 자세히 */
  function recordLog(p, c) {
    c.body.append(el("p", { class: "sh-muted", text: `고른 공(${pickTag(p)})까지의 타석이에요. 마지막 공으로 가면 경기 전체가 보여요.` }));
    const ol = el("ol", { class: "sh-log" });
    for (let k = S.pas.length - 1; k >= 0; k--) {
      const a = S.pas[k]; if (!isNum(a.first_index) || a.first_index > p.index) continue;
      const open = isNum(a.last_index) && a.last_index > p.index;
      let cnt = 0; if (open) for (let i = a.first_index; i <= p.index; i++) if (S.P[i] && S.P[i].pa_key === a.pa_key) cnt++;
      const res = open ? "타석 진행 중" : a.complete ? a.result_text || koLabel(a.event_label, a.event) || "결과 기록 없음" : "타석 진행 중";
      const b = el("button", { type: "button", "data-fk": "log-" + a.pa_key }, el("b", { text: `${halfTag(a.inning, a.half)} · ${(a.batter && a.batter.name) || "타자 미상"}` }), el("span", { text: `${res} · ${open ? cnt : isNum(a.pitch_count) ? a.pitch_count : cnt}구` }));
      b.addEventListener("click", () => pickAndDetail(a.first_index));
      ol.append(el("li", null, b));
    }
    c.body.append(ol);
  }
  /** 기록 · 라인업: 발행본 경기 종료 시점 명단(current.context.lineups) 그대로 */
  function recordLineup(c) {
    c.body.append(el("p", { class: "sh-muted", text: "발행본의 명단은 경기 종료 시점 기준이에요(교체 포함). 고른 공 시점의 명단은 따로 없어요." }));
    const g = S.data.game, L = (S.data.current && S.data.current.context && S.data.current.context.lineups) || S.data.current_context && S.data.current_context.lineups || {};
    for (const side of ["away", "home"]) {
      c.body.append(el("h3", { class: "sh-team", text: teamKo(g[`${side}_team`]) }));
      const list = Array.isArray(L[side]) ? L[side] : [];
      if (!list.length) { c.body.append(el("p", { class: "sh-muted", text: "라인업 정보 없음" })); continue; }
      const ol = el("ol", { class: "sh-order" });
      for (const r of list) ol.append(el("li", { text: `${text(r.order)}번 · ${r.name || "선수 미확인"}` }));
      c.body.append(ol);
    }
  }
  /** 기록 · 박스: 발행본 경기 종료 시점 박스(current.context.boxscore) 그대로 — 타자 타수·안타·출루, 투수 투구·삼진·자책 */
  function recordBox(c) {
    c.body.append(el("p", { class: "sh-muted", text: "발행본의 박스는 경기 종료 시점 기준이에요. 고른 공 시점의 선수별 합계는 따로 없어요(선수 칸의 ‘오늘 기록’이 그 시점 값이에요)." }));
    const g = S.data.game, B = (S.data.current && S.data.current.context && S.data.current.context.boxscore) || {};
    const v = (x) => (x === null || x === undefined ? DASH : String(x));
    for (const side of ["away", "home"]) {
      const sec = el("section", { class: "sh-boxsec" }, el("h3", { class: "sh-team", text: teamKo(g[`${side}_team`]) }));
      const b = B[side];
      if (!b) { sec.append(el("p", { class: "sh-muted", text: "박스 기록 정보 없음" })); c.body.append(sec); continue; }
      sec.append(table("sh-table box", ["타자", "타수", "안타", "출루"], (b.batters || []).map((r) => ({ cells: [r.name || "", v(r.at_bats), v(r.hits), v(r.on_base)] }))));
      sec.append(table("sh-table box", ["투수", "투구", "삼진", "자책"], (b.pitchers || []).map((r) => ({ cells: [r.name || "", v(r.pitches), v(r.strikeouts), v(r.earned_runs)] }))));
      c.body.append(sec);
    }
  }

  // ----- 9. v4 조작 묶기: 머리 두 버튼, 자세히, 이번 타석 접기 -----
  function wireV4() {
    $("hd-state").addEventListener("click", (e) => openSheet("atbat", { from: e.currentTarget }));
    $("hd-ls").addEventListener("click", (e) => openSheet("linescore", { from: e.currentTarget }));
    $("btn-detail").addEventListener("click", (e) => openSheet("detail", { from: e.currentTarget }));
    const tg = $("atbat-toggle"), box = $("pa-panel");
    tg.addEventListener("click", () => { const folded = !box.classList.contains("folded"); box.classList.toggle("folded", folded); tg.setAttribute("aria-expanded", String(!folded)); tg.textContent = folded ? "펼치기 ▾" : "접기 ▴"; });
  }

  window.PZRelay = Object.freeze({ attach3D, detach3D, select: (i) => selectPitch(i, { scroll: false }), sheet: () => (S.sheet ? S.sheet.kind : null), exitOf: (i) => exitKindOf(S.P[i]), state3D: () => (B3.api ? { attached: true, model: B3.api.modelName || null, ...B3.api.state() } : { attached: false }) });

  wireTheme(); wireAnim(); // 자료 로딩과 무관하게 바로 동작(const 정의 뒤에서 호출)
})();

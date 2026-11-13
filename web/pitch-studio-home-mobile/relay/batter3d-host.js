/* batter3d-host.js — relay 호스트에 3D 타자(batter3d 모듈)를 "선택 사항"으로 붙이는 어댑터(2026-11-08 단위 3, 로컬 시안).
 * 원칙: 이 파일이 없거나, 모듈 로딩·glb 읽기·WebGL 초기화 중 하나라도 실패하면 relay.js의 SVG 타자가 그대로 쓰인다(아무것도 바꾸지 않는다).
 *       성공한 뒤에만 relay.js가 내놓은 window.PZRelay.attach3D(api)를 한 번 부른다. 경기 결과 판정·공 연출·자막은 relay.js 그대로다(여기서 건드리지 않음).
 * 시간 기준은 relay.js 하나다: 공이 나타나는 순간(renderZone)부터 도착(flightMs)까지를 클립의 '연출 기준 시점'(cue) 앞부분에 맞춰 재생하고,
 *       도착 뒤 팔로스루는 원래 속도로 end까지 간다. end 뒤에는 reset()으로 대기 동작(사람형은 반복)으로 섞여 돌아간다(11/9; 그 전엔 다음 투구까지 끝 자세 유지였다).
 *       안 치는 공(볼·루킹·블록)은 react(): 도착 + REACT_DELAY_MS 뒤 take 클립(메타에 있을 때만).
 *       안타·홈런(자료의 타석 결과 single/double/triple/home_run)은 swing("hit"): 메타에 hit가 있으면 치고 1루 쪽으로 달려 나가는 클립, 없으면 contact와 같다(11/9).
 * 재생 구간(PLAY)은 원본 클립 시간(초) 기준이다. 원본 클립 길이(duration)와 재생 구간(0..end)을 구분해 적는다:
 *   - contact(타격·파울·파울팁): clip contact_hit1(Mixamo Baseball_Hit_1, 원본 2.90 s), cue 1.456042 s(배트 끝 속도 최대, 240표본 구간 중점), end 2.1 s.
 *     원본 끝(k≳0.87, 2.5 s 이후)은 타자가 1루로 달려 나가 화면 밖이므로 재생하지 않는다. 기존 contact(Baseball_Hit)·contact_hit2도 끝에서 같은 이탈이 있어(11/8 측정) 고르지 않았다.
 *   - miss(헛스윙): clip miss(Baseball_Strike, 원본 6.93 s), cue 1.198889 s, end 2.45 s(동작이 거의 멈추는 지점). 몸통은 구간 전체에서 화면 안.
 *   cue·end는 '연출 기준 시점 추정'이며 실제 공 접촉 시각이 아니다(README 8·9절).
 * URL 매개변수(로컬 검증용): ?batter3d=off → 붙이지 않음, ?batter3d=<이름> → 다른 모델 파일(assets/<이름>.glb) 시도(없으면 실패 경로 = SVG 유지).
 */
import { createBatter3D } from "./batter3d/batter3d.js?v=4"; // ?v=4(11/9 V4): 브라우저 캐시에 남은 이전 판 모듈과 섞이지 않게(v1·v2에도 무해)

const ASSETS = "./batter3d/assets/";
const DEFAULT_MODEL = "batter-indexed";
// 호스트 전용 카메라 보정(모델 메타의 view 위에 덮어씀). 캔버스는 CSS로 열의 2.6배 폭(260×251px @375px)이라 세로 기준 프레이밍이 된다. zoom 0.8: 대기 자세 키가 틀의 78 %(약 196px), 배트 끝 포함 14자세 가장자리 접촉 0(README 9.11).
// (이전 9.10: 열 100px 틀 + zoom 1.5는 팔로스루 배트가 잘려 사용자가 "안 가리게" 요청)
const HOST_VIEW = { zoom: 0.8 };
const PLAY = {
  contact: { clip: "contact_hit1", cue: 1.456042, end: 2.1 },
  miss: { clip: "miss", cue: 1.198889, end: 2.45 },
};

const EXIT_KEYS = ["run_r", "run_l", "strafe_r", "strafe_l"]; // 나가기 동작(11/9 V4): 출루 = 달리기, 아웃 = 옆걸음. _r 우타자, _l 좌타자(거울로 그려짐)
const EXIT_BLEND_S = 0.25; // 스윙·반응 끝 자세 → 나가기 동작 섞는 시간
const REACT_DELAY_MS = 250; // 안 치는 공: 공이 도착(판정 자막)하고 이만큼 뒤에 반응 클립 시작(사람이 판정을 보고 움직이는 느낌)
/** 재생 끝 시각(초): opts.follow가 있으면 cue + follow(원래 end를 넘지 않게, 최소 0.05 s), 없으면 원래 end */
const endFor = (p, opts) => (opts && Number.isFinite(opts.follow) ? Math.min(p.end, p.cue + Math.max(0.05, opts.follow)) : p.end);

const state = { api: null, busy: false, last: null }; // last: 마지막 시도 결과(검증용)

/** 재생 구간: 모델 메타(meta.play)에 있으면 그것, 없거나 모자라면 위 PLAY(마네킹 기본값). 사람형 캐릭터(11/9)는 클립 길이·연출 기준 시점이 달라 변환기가 메타에 넣는다.
 *  take(안 치는 공 반응)는 선택 사항: 메타에 올바르게 있으면 쓰고, 없거나 틀리면 빼기만 한다(contact·miss는 그대로) */
function resolvePlay(b) {
  const mp = b && b.meta && b.meta.play; if (!mp || typeof mp !== "object") return PLAY;
  const out = {};
  const okEntry = (p) => p && typeof p.clip === "string" && Number.isFinite(p.cue) && Number.isFinite(p.end) && p.cue < p.end;
  for (const k of ["contact", "miss"]) { const p = mp[k]; if (!okEntry(p)) return PLAY; out[k] = { clip: p.clip, cue: p.cue, end: p.end }; }
  if (okEntry(mp.take)) out.take = { clip: mp.take.clip, cue: mp.take.cue, end: mp.take.end };
  if (okEntry(mp.hit)) out.hit = { clip: mp.hit.clip, cue: mp.hit.cue, end: mp.hit.end }; // hit(안타·홈런)도 선택 사항
  for (const k of EXIT_KEYS) { const p = mp[k]; if (p && typeof p.clip === "string" && Number.isFinite(p.cue) && Number.isFinite(p.end) && p.cue >= 0 && p.cue < p.end) out[k] = { clip: p.clip, cue: p.cue, end: p.end }; } // 나가기(11/9 V4)도 선택 사항(cue 0 허용)
  return out;
}

function modelFromQuery() {
  let q = null;
  try { q = new URLSearchParams(location.search).get("batter3d"); } catch (e) { q = null; }
  if (q === "off") return null;
  const pageDefault = document.documentElement.dataset.batter3dModel; // 페이지가 정한 기본 모델(11/9 v4.html = batter-ctl-v4). 없으면 마네킹
  return q && /^[A-Za-z0-9_-]{1,64}$/.test(q) ? q : pageDefault && /^[A-Za-z0-9_-]{1,64}$/.test(pageDefault) ? pageDefault : DEFAULT_MODEL;
}

/** 로딩 → 초기화 → 검사 → attach. 실패하면 상자를 치우고 null(SVG 유지). 다시 부를 수 있다(검증용: 실패 흉내 뒤 복구). */
async function init(opts = {}) {
  if (state.api) return state.api;
  if (state.busy) return null;
  const host = window.PZRelay;
  if (!host || typeof host.attach3D !== "function") { state.last = "host 없음"; return null; }
  const modelName = opts.modelName || modelFromQuery();
  if (!modelName) { state.last = "꺼짐(?batter3d=off)"; return null; }
  state.busy = true;
  const box = document.createElement("div"); box.className = "bat3d"; box.setAttribute("aria-hidden", "true");
  // 숨겨진 띠(오른쪽) 안에서 초기화한다. relay.js가 보이는 쪽 띠로 옮기고 크기를 맞춘다
  (document.getElementById("bat-right") || document.body).append(box);
  let b = null;
  try {
    b = await createBatter3D(box, { assetsBase: ASSETS, modelName, side: "R", theme: document.documentElement.dataset.theme === "dark" ? "dark" : "light", view: HOST_VIEW });
  } catch (e) { // 메타·glb 읽기 실패(404 등) 또는 모듈 오류 → SVG 유지
    box.remove(); state.busy = false; state.last = `로딩 실패: ${e && e.message ? e.message : e}`; return null;
  }
  const st = b.getState(), play = resolvePlay(b);
  if (play.take && !(st.clips[play.take.clip] > 0 && play.take.end <= st.clips[play.take.clip] + 1e-6)) delete play.take;
  for (const k of EXIT_KEYS) if (play[k] && !(st.clips[play[k].clip] > 0 && play[k].end <= st.clips[play[k].clip] + 1e-6)) delete play[k]; // 나가기도 glb와 안 맞으면 그것만 뺀다
  if (play.hit && !(st.clips[play.hit.clip] > 0 && play.hit.end <= st.clips[play.hit.clip] + 1e-6)) delete play.hit; // hit도 선택 사항: 안 맞으면 hit만 뺀다(안타·홈런도 contact로) // take는 선택 사항: glb에 클립이 없거나 구간이 길이를 넘으면 take만 뺀다(contact·miss 검사는 아래에서 그대로 치명). PLAY 상수에는 take가 없어 건드리지 않는다
  const why = !b.ok || b.mode !== "webgl" ? `초기화 실패: ${st.mode}${st.error ? " " + st.error : ""}`
    : Object.entries(play).some(([k, p]) => !EXIT_KEYS.includes(k) && (!(st.clips[p.clip] > 0) || !(p.end <= st.clips[p.clip] + 1e-6) || !(p.cue < p.end))) ? "클립·재생 구간 불일치" : null;
  if (why) { try { b.dispose(); } catch (e) { /* 무시 */ } box.remove(); state.busy = false; state.last = why; return null; }

  const ro = typeof ResizeObserver === "function" ? new ResizeObserver(() => { if (state.api === api) b.resize(); }) : null;
  if (ro) ro.observe(box);
  // WebGL 문맥 상실은 모듈이 ok=false로만 바꾸고 알리지 않으므로, 여기서 캔버스 이벤트를 받아 바로 호스트에 해제를 요청한다(다음 투구까지 빈 캔버스+숨은 SVG로 남지 않게; 11/8 독립 검토 지적)
  const canvas = box.querySelector("canvas");
  const onLost = () => { if (state.api === api) { try { host.detach3D("WebGL 문맥 상실"); } catch (e) { try { api.dispose(); } catch (e2) { /* 무시 */ } } } };
  if (canvas) canvas.addEventListener("webglcontextlost", onLost, false);
  const api = {
    container: box,
    modelName,
    play,
    ok: () => b.ok && !b.disposed,
    setSide: (s) => b.setSide(s),
    setTheme: (t) => b.setTheme(t),
    setUniform: (u) => (typeof b.setUniform === "function" ? b.setUniform(u) : false), // 유니폼 색(11/9 V4): 사람형 모델의 옷·헬멧 텍스처만, 마네킹은 무동작. v1·v2는 부르지 않는다
    resize: () => b.resize(),
    reset: (o) => b.reset(o), // o.still: 정지 자세(애니메이션 끔·다른 화면). 감속 모션은 모듈이 스스로 본다
    state: () => b.getState(),
    /** kind "contact" | "miss" | "hit"(안타·홈런; 메타에 hit가 없으면 contact), leadMs = 공 비행 시간. 돌려주는 frame(u)는 전체 진행률 u(0..1)를 클립 시간으로 바꿔 그 자세를 그린다(그 프레임만, 자체 시계 없음) */
    swing(kind, leadMs, opts) { // opts.follow(11/9 V4): 기준 시점 뒤 이만큼(초)만 재생하고 끝낸다(나가기 동작이 이어질 때). 없으면 전과 같이 end까지
      const key = kind === "miss" ? "miss" : kind === "hit" && play.hit ? "hit" : "contact"; const p = play[key]; const d = b.getState().clips[p.clip];
      if (!(d > 0) || !(leadMs > 0)) return null;
      const endT = endFor(p, opts), followMs = (endT - p.cue) * 1000, ms = leadMs + followMs;
      return {
        ms, kind: key, clip: p.clip, leadMs, followMs, // kind = 실제로 고른 재생 항목(hit가 없어 contact로 대체되면 "contact")
        frame: (u) => {
          const tau = Math.min(1, Math.max(0, u)) * ms;
          const t = tau <= leadMs ? p.cue * (tau / leadMs) : p.cue + (tau - leadMs) / 1000; // 앞: 비행 시간에 맞춰(원속도 아님), 뒤: 원속도
          b.setSwing(p.clip, Math.min(1, t / d));
        },
      };
    },
    /** 안 치는 공(볼·스트라이크·블록)의 반응(11/9). leadMs = 공 비행 시간. 공 도착 + REACT_DELAY_MS 뒤에 take 클립을 cue→end 원속도로 그린다.
     *  그 전에는 setSwing을 부르지 않아 대기 반복이 그대로 돈다(첫 프레임에 reset()을 한 번 불러, 앞 연출이 끊긴 채 멈춘 자세였다면 대기로 되돌린다).
     *  모델 메타에 take가 없으면(마네킹) null → 호스트는 전처럼 아무 동작 없음 */
    react(leadMs, opts) { // opts.follow: swing과 같음
      const p = play.take; if (!p) return null; const d = b.getState().clips[p.clip];
      if (!(d > 0) || !(leadMs >= 0)) return null;
      const startMs = leadMs + REACT_DELAY_MS, playMs = (endFor(p, opts) - p.cue) * 1000, ms = startMs + playMs; let primed = false;
      return {
        ms, clip: p.clip, startMs, playMs,
        frame: (u) => {
          const tau = Math.min(1, Math.max(0, u)) * ms;
          if (tau < startMs) { if (!primed) { primed = true; b.reset(); } return; }
          const t = p.cue + (tau - startMs) / 1000; b.setSwing(p.clip, Math.min(1, t / d));
        },
      };
    },
    /** 나가기 동작(11/9 V4). kind "run"(출루: 달려 나감) | "strafe"(아웃: 옆걸음으로 비켜 나감), side "L" | "R". 메타에 해당 항목이 없으면 null(호스트는 전처럼 대기로).
     *  돌려주는 frame(u)는 진행률 u(0..1)를 클립 시간 cue→end(원속도)로 바꿔 그 자세를 그린다. 첫 프레임은 앞 동작의 끝 자세에서 EXIT_BLEND_S 동안 섞여 넘어간다 */
    exit(kind, side) {
      const key = `${kind === "run" ? "run" : "strafe"}_${side === "L" ? "l" : "r"}`, p = play[key]; if (!p) return null; const d = b.getState().clips[p.clip];
      if (!(d > 0)) return null;
      const ms = (p.end - p.cue) * 1000;
      return { ms, kind: key, clip: p.clip, frame: (u) => { const t = p.cue + Math.min(1, Math.max(0, u)) * (p.end - p.cue); b.setSwing(p.clip, Math.min(1, t / d), { blendIn: EXIT_BLEND_S }); } };
    },
    dispose() { if (state.api === api) state.api = null; if (ro) ro.disconnect(); if (canvas) canvas.removeEventListener("webglcontextlost", onLost, false); try { b.dispose(); } catch (e) { /* 무시 */ } if (box.parentNode) box.remove(); },
  };
  state.api = api; state.busy = false; state.last = "연결됨";
  try { host.attach3D(api); } catch (e) { api.dispose(); state.last = `attach 실패: ${e && e.message ? e.message : e}`; return null; }
  return api;
}

window.PZBatter3D = Object.freeze({ init, PLAY, status: () => ({ attached: !!state.api, busy: state.busy, last: state.last, model: state.api ? state.api.modelName : null, play: state.api ? state.api.play : null }) });
init();

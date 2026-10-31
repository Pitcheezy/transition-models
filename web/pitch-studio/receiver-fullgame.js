/* Curated saved-game adapter. No fetching, inference, endpoint reconstruction or live claims. */
(function (root, factory) {
  "use strict";
  const api = factory(typeof module === "object" && module.exports ? require("./game-catalog.js") : root.PitchGameCatalog);
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.PitchReceiverFullGame = api;
})(typeof globalThis === "object" ? globalThis : this, function (catalog) {
  "use strict";
  const SCHEMA = "pitcheezy-static-game-v1";
  const copy = (value) => JSON.parse(JSON.stringify(value));
  const requireValue = (test, message) => { if (!test) throw new TypeError(message); };
  function fields(value, keys) {
    requireValue(value !== null && typeof value === "object" && !Array.isArray(value), "객체가 필요합니다.");
    requireValue(Object.keys(value).length === keys.length && keys.every(k => Object.hasOwn(value, k)), "자료 필드가 계약과 다릅니다.");
  }
  function text(value, nullable = false) {
    requireValue((nullable && value === null) || (typeof value === "string" && value.length > 0 && value.length <= 300 && !/[\u0000-\u001f]/.test(value)), "문자열이 올바르지 않습니다.");
  }
  function number(value, min = -20, max = 20, nullable = false) {
    requireValue((nullable && value === null) || (typeof value === "number" && Number.isFinite(value) && value >= min && value <= max), "수치가 올바르지 않습니다.");
  }
  function integer(value, min = 0, max = 100000) {
    number(value, min, max); requireValue(Number.isInteger(value), "정수가 필요합니다.");
  }
  function person(value) {
    fields(value, ["id", "name", "hand"]); integer(value.id, 1, 999999999); text(value.name);
    requireValue([null, "L", "R", "S"].includes(value.hand), "선수 손잡이 값이 올바르지 않습니다.");
  }
  function validate(input) {
    fields(input, ["schema", "source", "game", "units", "claims", "pitches"]);
    requireValue(input.schema === SCHEMA, "전체 경기 저장 자료 형식이 아닙니다.");
    const s = input.source;
    fields(s, ["kind", "sha256", "report_sha256", "revision", "exported_at", "model_id", "upstream_kind"]);
    requireValue(["provided_export", "official_record"].includes(s.kind) && s.upstream_kind === "archive", "저장 응답만 지원합니다.");
    for (const hash of [s.sha256, s.report_sha256]) requireValue(typeof hash === "string" && /^[a-f0-9]{64}$/.test(hash), "자료 SHA가 필요합니다.");
    requireValue(s.revision === null && s.exported_at === null, "미확인 생성 버전을 채울 수 없습니다.");
    if (s.kind === "official_record") requireValue(s.model_id === null, "추천을 받지 않은 기록에 모델을 표시할 수 없습니다.");
    else text(s.model_id);
    const game = input.game;
    fields(game, ["game_pk", "date", "away_team", "home_team"]); integer(game.game_pk, 1, 99999999999);
    text(game.away_team); text(game.home_team);
    requireValue(typeof game.date === "string" && /^\d{4}-\d{2}-\d{2}$/.test(game.date) && new Date(`${game.date}T00:00:00Z`).toISOString().slice(0,10) === game.date, "경기 날짜가 올바르지 않습니다.");
    fields(input.units, ["position", "speed", "probability", "setup"]);
    requireValue(input.units.position === "feet" && input.units.speed === "mph" && input.units.probability === "pitch_type_selection_share" && input.units.setup === "feet_catcher_view_right_positive", "자료 단위가 다릅니다.");
    fields(input.claims, ["live_timing_verified", "complete_game_verified", "human_mitt_accuracy_measured"]);
    requireValue(Object.values(input.claims).every(v => v === false), "미검증 주장을 승인하지 않습니다.");
    requireValue(Array.isArray(input.pitches) && input.pitches.length > 0 && input.pitches.length <= 2000, "투구 목록이 필요합니다.");
    const keys = new Set(), indexes = new Set();
    for (const p of input.pitches) {
      fields(p, ["index", "pitch_id", "at_bat_number", "pitch_number", "situation", "pitcher", "batter", "pre", "post"]);
      integer(p.index); integer(p.at_bat_number, 1, 999); integer(p.pitch_number, 1, 100);
      requireValue(p.pitch_id === `${game.game_pk}:${p.at_bat_number}:${p.pitch_number}`, "투구 키가 경기·타석·번호와 다릅니다.");
      requireValue(!keys.has(p.pitch_id) && !indexes.has(p.index), "중복 투구 키 또는 순번입니다.");
      keys.add(p.pitch_id); indexes.add(p.index);
      const sit = p.situation;
      fields(sit, ["inning", "outs", "balls", "strikes", "bases", "home_score", "away_score", "half"]);
      for (const [k, lo, hi] of [["inning",1,99],["outs",0,2],["balls",0,3],["strikes",0,2],["bases",0,7],["home_score",0,100],["away_score",0,100]]) integer(sit[k],lo,hi);
      requireValue(["Top", "Bot"].includes(sit.half), "이닝 구분이 올바르지 않습니다.");
      person(p.pitcher); person(p.batter);
      const rec = p.pre;
      fields(rec, ["status", "provenance", "recorded_at", "policy", "candidates"]);
      requireValue(["ready", "unsupported", "missing"].includes(rec.status), "추천 상태가 올바르지 않습니다.");
      requireValue(["asof_replay", "captured_live", "absent"].includes(rec.provenance), "추천 출처가 올바르지 않습니다.");
      text(rec.recorded_at, true);
      if (rec.recorded_at !== null) requireValue(/^\d{4}-\d\d-\d\dT\d\d:\d\d:\d\d(?:\.\d+)?Z$/.test(rec.recorded_at) && Number.isFinite(Date.parse(rec.recorded_at)), "추천 기록 시각이 올바르지 않습니다.");
      if (rec.policy !== null) { fields(rec.policy, ["name", "identity"]); text(rec.policy.name,true); text(rec.policy.identity,true); }
      requireValue(Array.isArray(rec.candidates) && rec.candidates.length <= 30 && (rec.status === "ready") === Boolean(rec.candidates.length), "추천 상태와 후보가 일치하지 않습니다.");
      const ranks = new Set(), types = new Set(); let mass = 0;
      for (const c of rec.candidates) {
        fields(c, ["rank", "pitch_type", "pitch_label", "zone_id", "zone_label", "target", "selection_probability"]);
        integer(c.rank,1,30); text(c.pitch_type); text(c.pitch_label); text(c.zone_id,true); text(c.zone_label,true);
        requireValue(!ranks.has(c.rank) && !types.has(c.pitch_type), "추천 순위 또는 구종이 중복입니다.");
        ranks.add(c.rank); types.add(c.pitch_type);
        number(c.selection_probability,0,1,true); mass += c.selection_probability ?? 0;
        if (c.target !== null) { fields(c.target,["x","z"]); number(c.target.x); number(c.target.z); requireValue(c.zone_id !== null,"목표 구역이 필요합니다."); }
      }
      requireValue(mass <= 1 + 1e-6, "선택 비중 합이 1을 넘습니다.");
      fields(p.post, ["actual", "setup"]);
      if (s.kind === "official_record") requireValue(rec.status === "missing" && rec.provenance === "absent" && rec.recorded_at === null && rec.policy === null && rec.candidates.length === 0 && p.post.setup === null, "공식 경기 기록에 미수신 추천·미트 추정을 채울 수 없습니다.");
      if (p.post.actual !== null) {
        const a = p.post.actual;
        fields(a, ["pitch_type", "pitch_label", "description", "result_label", "event", "event_label", "speed_mph", "x", "z"]);
        for (const k of ["pitch_type","pitch_label","description","result_label","event","event_label"]) text(a[k],true);
        number(a.speed_mph,0,150,true); number(a.x,-20,20,true); number(a.z,-20,20,true);
      }
      if (p.post.setup !== null) {
        const setup = p.post.setup;
        fields(setup,["status","x"]);
        requireValue(p.post.actual !== null && ["estimated", "unavailable"].includes(setup.status), "셋업 상태가 올바르지 않습니다.");
        number(setup.x,-20,20,true);
        requireValue(setup.status === "estimated" || setup.x === null, "기권 셋업에는 좌표를 넣을 수 없습니다.");
      }
    }
    const result = copy(input);
    result.pitches.sort((a,b) => a.index-b.index);
    for (let i=0;i<result.pitches.length;i++) {
      const p=result.pitches[i], prev=result.pitches[i-1], next=result.pitches[i+1];
      requireValue(!prev || p.at_bat_number > prev.at_bat_number || (p.at_bat_number === prev.at_bat_number && p.pitch_number > prev.pitch_number), "투구 순번과 타석 순서가 충돌합니다.");
      requireValue(!(p.post.actual?.event || p.post.actual?.event_label) || !next || next.at_bat_number !== p.at_bat_number, "타석 종료 결과가 앞선 투구에 포함됐습니다.");
      p.pre.candidates.sort((a,b)=>a.rank-b.rank);
    }
    return result;
  }
  function createSession(input) {
    const data = validate(input), rows=data.pitches;
    const byKey = new Map(rows.map((p,i)=>[p.pitch_id,i]));
    const groups=[];
    for (const p of rows) {
      let group=groups.at(-1);
      if (!group || group.pa !== p.at_bat_number) {
        group={pa:p.at_bat_number,inning:p.situation.inning,half:p.situation.half,batter:p.batter.name,keys:[],pitches:[]};
        groups.push(group);
      }
      group.keys.push(p.pitch_id); group.pitches.push({key:p.pitch_id,pitch_number:p.pitch_number});
    }
    const summary={pitches:rows.length,plate_appearances:groups.length,ready:0,unsupported:0,missing:0};
    rows.forEach(p=>summary[p.pre.status]++);
    let cursor=0, revealed=false;
    return {
      view() {
        const p=rows[cursor];
        return copy({source:data.source,game:data.game,full_game:true,
          at_bat_number:p.at_bat_number,index:p.index,pitch_id:p.pitch_id,pitch_number:p.pitch_number,
          situation:p.situation,pitcher:p.pitcher,batter:p.batter,pre:p.pre,
          revealed,post:revealed?{...p.post,we:null}:null,
          can_previous:cursor>0,can_next:revealed && cursor<rows.length-1,
          position:cursor+1,count:rows.length,summary});
      },
      groups() { return copy(groups); },
      reveal(value) { requireValue(typeof value === "boolean", "공개 상태는 boolean이어야 합니다."); revealed=value; },
      next() { if (!revealed || cursor>=rows.length-1) return false; cursor++;revealed=false;return true; },
      previous() { if (!cursor) return false;cursor--;revealed=false;return true; },
      select(key) { requireValue(byKey.has(key),"목록에 없는 투구입니다.");cursor=byKey.get(key);revealed=false;return true; },
    };
  }
  function observation(view) {
    const setup = view?.full_game === true && view.revealed === true ? view.post?.setup : null;
    if (!setup) return {status:"missing",x:null};
    if (setup.status === "estimated" && typeof setup.x === "number" && Number.isFinite(setup.x)) return {status:"estimated",x:setup.x};
    return {status:"unavailable",x:null};
  }
  function createVerifiedSession(input, contentHash) {
    const entry = catalog.get(input?.game?.game_pk);
    requireValue(entry && contentHash === entry.game_sha256, "검토된 전체 경기 파일의 바이트와 다릅니다.");
    const session = createSession(input), view = session.view();
    requireValue(view.count === entry.pitches && view.summary.plate_appearances === entry.plate_appearances && ["ready", "unsupported", "missing"].every(k => view.summary[k] === entry[k]), "고정 경기 범위와 다릅니다.");
    requireValue(view.source.sha256 === entry.source_sha256 && view.source.kind === entry.source_kind, "영상과 연결할 수신 원문이 다릅니다.");
    return session;
  }
  return {validate,createSession,createVerifiedSession,observation};
});

/* Our file receiver only. No model calls, network requests or inference. */
(function (root) {
  "use strict";
  const fail = (message) => {
    throw new Error(message);
  };
  const object = (x, label) => {
    if (!x || typeof x !== "object" || Array.isArray(x))
      fail(`${label}: 객체가 필요합니다.`);
    return x;
  };
  const integer = (x, lo, hi, label) => {
    if (!Number.isSafeInteger(x) || x < lo || x > hi)
      fail(`${label}: 정수 범위를 확인하세요.`);
    return x;
  };
  const string = (x, label, max = 200) => {
    if (typeof x !== "string" || !x.trim() || x.length > max)
      fail(`${label}: 문자열을 확인하세요.`);
    return x;
  };
  const number = (x, label, lo = -10000, hi = 10000) => {
    if (typeof x !== "number" || !Number.isFinite(x) || x < lo || x > hi)
      fail(`${label}: 유한수 범위를 확인하세요.`);
    return x;
  };
  const nullableNumber = (x, label, lo, hi) =>
    x === null ? null : number(x, label, lo, hi);
  const nullableText = (x, label) =>
    x == null ? null : string(x, label, 1000);
  const validCalendarDate = (year, month, day) => {
    // Validate the written date, before Date.parse normalizes it or applies an offset.
    const leap = year % 4 === 0 && (year % 100 !== 0 || year % 400 === 0);
    const days = [31, leap ? 29 : 28, 31, 30, 31, 30, 31, 31, 30, 31, 30, 31];
    return month >= 1 && month <= 12 && day >= 1 && day <= days[month - 1];
  };
  const namedZones = new Set([
    "high_left",
    "high_middle",
    "high_right",
    "middle_left",
    "middle_middle",
    "middle_right",
    "low_left",
    "low_middle",
    "low_right",
  ]);
  const zone = (value) => {
    if (value === null || namedZones.has(value)) return value;
    // Legacy synthetic packets used integers. Do not convert between the two conventions.
    return integer(value, 1, 9, "구역");
  };
  const only = (x, fields, label) => {
    if (Object.keys(x).some((k) => !fields.includes(k)))
      fail(`${label}: 허용되지 않은 필드가 있습니다.`);
  };
  const person = (p, handKey) => {
    object(p, "선수");
    only(p, ["id", "name", handKey], "선수");
    if (
      p[handKey] !== null &&
      !(handKey === "side" ? ["L", "R", "S"] : ["L", "R"]).includes(p[handKey])
    )
      fail("선수 좌우 유형이 잘못됐습니다.");
    return {
      id: integer(p.id, 1, 999999999, "선수 ID"),
      name: string(p.name, "선수 이름"),
      hand: nullableText(p[handKey], "좌우 유형"),
    };
  };
  function candidate(c) {
    object(c, "추천 후보");
    only(
      c,
      [
        "rank",
        "pitch_type",
        "pitch_label",
        "zone_id",
        "zone_label",
        "target",
        "detail",
      ],
      "추천 후보",
    );
    const detail = object(c.detail, "추천 비율");
    only(
      detail,
      ["probability", "reference_probability", "kernel_mass", "kernel_ess"],
      "추천 세부 정보",
    );
    const target = c.target === null ? null : object(c.target, "목표 위치");
    if (target) only(target, ["x", "z"], "목표 위치");
    if (target && c.zone_id === null) fail("위치와 구역 지원 상태가 다릅니다.");
    return {
      rank: integer(c.rank, 1, 30, "추천 순위"),
      pitch_type: string(c.pitch_type, "구종 코드", 20),
      pitch_label: string(c.pitch_label, "구종 이름"),
      zone_id: zone(c.zone_id),
      target: target
        ? {
            x: number(target.x, "목표 x", -10, 10),
            z: number(target.z, "목표 z", -5, 10),
          }
        : null,
      selection_probability: number(detail.probability, "구종 선택 비율", 0, 1),
    };
  }
  function validate(input) {
    object(input, "전달 파일");
    only(
      input,
      ["schema", "source", "game_pk", "at_bat_number", "timeline", "reveals"],
      "전달 파일",
    );
    if (input.schema !== "pitcheezy-receiver-v1")
      fail("pitcheezy-receiver-v1 전달 파일이 필요합니다.");
    const source = object(input.source, "출처");
    only(source, ["kind", "revision", "exported_at", "model_id"], "출처");
    if (!["synthetic", "provided_export"].includes(source.kind))
      fail("출처 유형이 필요합니다.");
    const revision = string(source.revision, "소스 커밋", 40);
    if (!/^[a-f0-9]{40}$/.test(revision))
      fail("소스 커밋은 40자리 SHA여야 합니다.");
    const exportedAt = string(source.exported_at, "생성 시각");
    const date = /^(\d{4})-(\d\d)-(\d\d)T.+(?:Z|[+-]\d\d:\d\d)$/.exec(exportedAt);
    if (
      !date ||
      !validCalendarDate(Number(date[1]), Number(date[2]), Number(date[3])) ||
      !Number.isFinite(Date.parse(exportedAt))
    )
      fail("생성 시각에 ISO 날짜와 시간대를 넣어주세요.");
    const model = string(source.model_id, "모델 식별자");
    const gamePk = integer(input.game_pk, 1, 999999999, "경기 ID");
    const pa = integer(input.at_bat_number, 1, 999, "타석 번호");
    const timeline = object(input.timeline, "timeline");
    only(
      timeline,
      [
        "schema",
        "badge",
        "game",
        "policy",
        "location",
        "we_note",
        "coverage",
        "decisions",
      ],
      "timeline",
    );
    if (timeline.schema !== "pitcheezy-watch-along-v1")
      fail("공개용 watch API 응답이 필요합니다.");
    const game = object(timeline.game, "경기");
    if (Object.hasOwn(game, "final"))
      fail("최종 점수가 든 내부 원본 파일은 받지 않습니다.");
    only(
      game,
      ["game_pk", "date", "game_type", "away_team", "home_team"],
      "경기",
    );
    if (game.game_pk !== gamePk) fail("경기 ID가 서로 다릅니다.");
    if (
      !Array.isArray(timeline.decisions) ||
      !timeline.decisions.length ||
      timeline.decisions.length > 2000
    )
      fail("투구 목록 크기가 잘못됐습니다.");
    const ids = new Set(),
      indexes = new Set(),
      selected = [];
    for (const d of timeline.decisions) {
      object(d, "투구");
      if (["actual", "we", "post", "result"].some((k) => Object.hasOwn(d, k)))
        fail(
          "투구 전 응답에 투구 후 정보가 있습니다. 내부 저장 파일은 사용할 수 없습니다.",
        );
      only(
        d,
        [
          "index",
          "pa_id",
          "at_bat_number",
          "pitch_number",
          "situation",
          "pitcher",
          "batter",
          "status",
          "pre",
        ],
        "투구 전 행",
      );
      const index = integer(d.index, 0, 10000, "원래 index");
      const atBat = integer(d.at_bat_number, 1, 999, "타석");
      const pitch = integer(d.pitch_number, 1, 100, "투구 번호");
      if (d.pa_id !== `${gamePk}:${atBat}`)
        fail("pa_id와 경기·타석 번호가 다릅니다.");
      const id = `${d.pa_id}:${pitch}`;
      if (ids.has(id) || indexes.has(index))
        fail("중복 투구 키 또는 index가 있습니다.");
      ids.add(id);
      indexes.add(index);
      const s = object(d.situation, "투구 전 상황");
      only(
        s,
        [
          "inning",
          "half",
          "outs",
          "balls",
          "strikes",
          "bases",
          "home_score",
          "away_score",
        ],
        "투구 전 상황",
      );
      if (!["Top", "Bot"].includes(s.half))
        fail("half는 Top 또는 Bot이어야 합니다.");
      const situation = {
        inning: integer(s.inning, 1, 99, "이닝"),
        half: s.half,
      };
      for (const [key, max] of [
        ["outs", 2],
        ["balls", 3],
        ["strikes", 2],
        ["bases", 7],
        ["home_score", 100],
        ["away_score", 100],
      ])
        situation[key] = integer(s[key], 0, max, key);
      const pre = object(d.pre, "투구 전 추천");
      only(pre, ["status", "reason", "recommendation"], "투구 전 추천");
      if (!["ready", "unsupported"].includes(pre.status))
        fail("추천 지원 상태가 잘못됐습니다.");
      let candidates = [];
      if (pre.status === "ready") {
        const recommendation = object(pre.recommendation, "추천");
        only(
          recommendation,
          ["candidates", "candidate_law", "reference_law"],
          "추천",
        );
        if (
          !Array.isArray(recommendation.candidates) ||
          !recommendation.candidates.length ||
          recommendation.candidates.length > 30
        )
          fail("추천 후보가 필요합니다.");
        candidates = recommendation.candidates
          .map(candidate)
          .sort((a, b) => a.rank - b.rank);
        if (
          new Set(candidates.map((c) => c.rank)).size !== candidates.length ||
          new Set(candidates.map((c) => c.pitch_type)).size !==
            candidates.length
        )
          fail("추천 순위 또는 구종이 중복됐습니다.");
        if (
          candidates.reduce((total, c) => total + c.selection_probability, 0) >
          1 + 1e-8
        )
          fail("구종 선택 비율 합이 1을 넘습니다.");
      } else if (pre.recommendation !== null)
        fail("미지원 추천은 null이어야 합니다.");
      const normalized = {
        index,
        pitch_id: id,
        pitch_number: pitch,
        situation,
        pitcher: person(d.pitcher, "hand"),
        batter: person(d.batter, "side"),
        pre: { status: pre.status, candidates },
      };
      if (atBat === pa) selected.push(normalized);
    }
    if (!selected.length) fail("선택한 타석이 응답에 없습니다.");
    selected.sort((a, b) => a.index - b.index);
    for (let i = 1; i < selected.length; i++)
      if (selected[i].pitch_number <= selected[i - 1].pitch_number)
        fail("index와 투구 번호 순서가 다릅니다.");
    if (
      !Array.isArray(input.reveals) ||
      input.reveals.length !== selected.length
    )
      fail("선택한 타석의 각 투구에 reveal 연결 정보가 하나씩 필요합니다.");
    const revealMap = new Map();
    for (const wrapper of input.reveals) {
      object(wrapper, "reveal 연결");
      only(wrapper, ["pitch_id", "source_endpoint", "response"], "reveal 연결");
      const response = object(wrapper.response, "reveal 응답");
      only(response, ["index", "actual", "we"], "reveal 응답");
      const d = selected.find((d) => d.index === response.index);
      if (!d || d.pitch_id !== wrapper.pitch_id)
        fail("reveal의 투구 키와 index가 일치하지 않습니다.");
      if (wrapper.source_endpoint !== `/api/watch/${gamePk}/reveal/${d.index}`)
        fail("reveal의 원본 엔드포인트가 일치하지 않습니다.");
      if (revealMap.has(d.index)) fail("reveal이 중복됐습니다.");
      const a = object(response.actual, "실제 결과");
      only(
        a,
        [
          "pitch_type",
          "pitch_label",
          "description",
          "result_label",
          "event",
          "event_label",
          "play_text",
          "speed_mph",
          "x",
          "z",
          "zone_label",
        ],
        "실제 결과",
      );
      const actual = {};
      for (const key of [
        "pitch_type",
        "pitch_label",
        "result_label",
        "event_label",
      ])
        actual[key] = nullableText(a[key], key);
      for (const [key, lo, hi] of [
        ["speed_mph", 0, 150],
        ["x", -20, 20],
        ["z", -20, 20],
      ])
        actual[key] = nullableNumber(a[key], key, lo, hi);
      const w = object(response.we, "WE");
      only(
        w,
        ["home_before", "home_after", "home_delta", "batting_delta"],
        "WE",
      );
      const we = {};
      for (const [key, lo, hi] of [
        ["home_before", 0, 1],
        ["home_after", 0, 1],
        ["home_delta", -1, 1],
        ["batting_delta", -1, 1],
      ])
        we[key] = nullableNumber(w[key], key, lo, hi);
      if (
        [we.home_before, we.home_after, we.home_delta].every(
          (v) => v !== null,
        ) &&
        Math.abs(we.home_after - we.home_before - we.home_delta) > 0.001
      )
        fail("WE 전후 값과 변화량이 일치하지 않습니다.");
      if (
        we.home_delta !== null &&
        we.batting_delta !== null &&
        Math.abs(
          we.batting_delta -
            (d.situation.half === "Top" ? -we.home_delta : we.home_delta),
        ) > 0.001
      )
        fail("WE 공격·수비 방향이 일치하지 않습니다.");
      revealMap.set(d.index, { actual, we });
    }
    return {
      source: {
        kind: source.kind,
        revision,
        exported_at: exportedAt,
        model_id: model,
      },
      game: {
        game_pk: gamePk,
        date: string(game.date, "경기 날짜"),
        away_team: string(game.away_team, "원정팀"),
        home_team: string(game.home_team, "홈팀"),
      },
      at_bat_number: pa,
      decisions: selected.map((d) => ({ ...d, post: revealMap.get(d.index) })),
    };
  }
  function assemble({ timeline, at_bat_number, source, reveals }) {
    object(timeline, "timeline");
    object(timeline.game, "경기");
    const pa = integer(at_bat_number, 1, 999, "타석 번호");
    if (!Array.isArray(timeline.decisions))
      fail("timeline 투구 목록이 필요합니다.");
    if (!Array.isArray(reveals) || !reveals.length || reveals.length > 100)
      fail("선택한 한 타석의 reveal 파일들이 필요합니다.");
    const wrapped = reveals.map((entry) => {
      object(entry, "원응답 연결");
      only(entry, ["source_endpoint", "response"], "원응답 연결");
      object(entry.response, "reveal 응답");
      const d = timeline.decisions.find(
        (row) => row.index === entry.response.index && row.at_bat_number === pa,
      );
      if (!d) fail("reveal index가 선택한 타석에 없습니다.");
      let endpoint = string(
        entry.source_endpoint,
        "원래 요청 주소",
        2000,
      ).trim();
      if (!endpoint.startsWith("/")) {
        let url;
        try {
          url = new URL(endpoint);
        } catch {
          fail("원래 요청 주소를 확인하세요.");
        }
        if (
          !["http:", "https:"].includes(url.protocol) ||
          url.username ||
          url.password ||
          url.search ||
          url.hash
        )
          fail("요청 주소에는 인증정보·쿼리·조각 없이 HTTP 경로만 넣어주세요.");
        endpoint = url.pathname;
      }
      // The caller supplies the original endpoint; it is never invented from array order.
      if (endpoint !== `/api/watch/${timeline.game.game_pk}/reveal/${d.index}`)
        fail("원래 요청 주소의 경기/index와 응답이 일치하지 않습니다.");
      return {
        pitch_id: `${d.pa_id}:${d.pitch_number}`,
        source_endpoint: endpoint,
        response: entry.response,
      };
    });
    const envelope = {
      schema: "pitcheezy-receiver-v1",
      source,
      game_pk: timeline.game.game_pk,
      at_bat_number: pa,
      timeline,
      reveals: wrapped,
    };
    validate(envelope);
    return envelope;
  }
  function createSession(input) {
    const data = validate(input);
    let cursor = 0,
      revealed = false;
    return {
      view() {
        const d = data.decisions[cursor];
        // Projection, not a security boundary: local input contains the full retrospective file.
        return JSON.parse(
          JSON.stringify({
            source: data.source,
            game: data.game,
            at_bat_number: data.at_bat_number,
            index: d.index,
            pitch_id: d.pitch_id,
            pitch_number: d.pitch_number,
            situation: d.situation,
            pitcher: d.pitcher,
            batter: d.batter,
            pre: d.pre,
            revealed,
            post: revealed ? d.post : null,
            can_previous: cursor > 0,
            can_next: revealed && cursor < data.decisions.length - 1,
          }),
        );
      },
      reveal(value) {
        if (typeof value !== "boolean")
          fail("공개 상태는 boolean이어야 합니다.");
        revealed = value;
      },
      next() {
        if (!revealed || cursor >= data.decisions.length - 1) return false;
        cursor++;
        revealed = false;
        return true;
      },
      previous() {
        if (cursor === 0) return false;
        cursor--;
        revealed = false;
        return true;
      },
    };
  }
  function observation(view, records) {
    if (!view.revealed) return null;
    if (view.source.kind === "synthetic")
      return { status: "synthetic", x: null };
    if (!Object.hasOwn(records, view.pitch_id))
      return { status: "missing", x: null };
    const row = records[view.pitch_id];
    if (
      row.pitch_id !== view.pitch_id ||
      row.pitcher !== view.pitcher.name ||
      row.batter !== view.batter.name ||
      !view.post.actual.pitch_type ||
      row.pitch_type !== view.post.actual.pitch_type
    )
      return { status: "conflict", x: null };
    if (row.status === "unavailable") return { status: "unavailable", x: null };
    if (row.status !== "estimated" || !Number.isFinite(row.mitt_x_ft))
      return { status: "conflict", x: null };
    return { status: "key_matched", x: row.mitt_x_ft };
  }
  const api = { validate, assemble, createSession, observation };
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.PitchReceiver = api;
})(typeof globalThis === "object" ? globalThis : this);

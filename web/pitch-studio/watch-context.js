/* Saved-game context. Call with validated rows; post data is read only within each disclosure boundary. */
(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.PitchWatchContext = api;
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";
  const emptyPrior = () => ({ total: 0, speedCount: 0, averageMph: null, types: [] });
  const countValue = row => `${row.situation.balls}-${row.situation.strikes}`;
  const unknownTypes = new Set(["unknown", "unk", "un", "na", "n/a"]);
  const results = new Map([
    ["automatic_ball", "automatic"],
    ...["ball", "blocked_ball", "intent_ball", "pitchout"].map(code => [code, "ball"]),
    ...["called_strike", "swinging_strike", "swinging_strike_blocked", "foul_tip", "missed_bunt"].map(code => [code, "strike"]),
    ...["foul", "foul_bunt", "foul_pitchout"].map(code => [code, "foul"]),
    ...["hit_into_play", "hit_into_play_no_out", "hit_into_play_score"].map(code => [code, "inplay"]),
    ["hit_by_pitch", "hbp"],
  ]);
  const labels = { automatic:"자동 볼", ball: "볼", strike: "스트라이크", foul: "파울", inplay: "인플레이", hbp: "몸에 맞는 공", unknown: "결과 미제공", hidden: "결과 숨김" };

  function create(input) {
    if (!Array.isArray(input)) throw new TypeError("검증된 투구 목록이 필요합니다.");
    // Sorting a new array does not copy/read post, or change the caller's rows.
    const rows = input.slice().sort((a, b) => a.index - b.index);
    const byKey = new Map(), pitchers = new Map(), batters = new Map(), counts = new Set();
    for (const row of rows) {
      if (byKey.has(row.pitch_id)) throw new TypeError("중복 투구 키입니다.");
      byKey.set(row.pitch_id, row);
      for (const [person, people] of [[row.pitcher, pitchers], [row.batter, batters]]) {
        const id = String(person.id);
        if (!people.has(id)) people.set(id, { id, name: person.name });
      }
      counts.add(countValue(row));
    }

    function options() {
      return {
        pitchers: [...pitchers.values()].map(person => ({ ...person })),
        batters: [...batters.values()].map(person => ({ ...person })),
        counts: [...counts].sort((a, b) => {
          const [ab, as] = a.split("-").map(Number), [bb, bs] = b.split("-").map(Number);
          return ab - bb || as - bs;
        }).map(value => {
          const [balls, strikes] = value.split("-");
          return { value, label: `${balls}볼 ${strikes}스트라이크` };
        }),
      };
    }

    function matchingKeys(filters) {
      if (!filters || typeof filters !== "object" || Array.isArray(filters)
          || Object.keys(filters).some(key => !["pitcher", "batter", "count"].includes(key))) return [];
      for (const [field, allowed] of [["pitcher", pitchers], ["batter", batters], ["count", counts]]) {
        if (typeof filters[field] !== "string" || (filters[field] !== "all" && !allowed.has(filters[field]))) return [];
      }
      return rows.filter(row => (filters.pitcher === "all" || String(row.pitcher.id) === filters.pitcher)
        && (filters.batter === "all" || String(row.batter.id) === filters.batter)
        && (filters.count === "all" || countValue(row) === filters.count)).map(row => row.pitch_id);
    }

    function situation(key) {
      const row = byKey.get(key);
      if (!row) return "상황 정보 없음";
      const s = row.situation;
      const bases = [1, 2, 4].flatMap((bit, i) => s.bases & bit ? [`${i + 1}루`] : []);
      return `${s.inning}회 ${s.half === "Top" ? "초" : "말"} · ${s.balls}볼 ${s.strikes}스트라이크 · ${s.outs}아웃 · ${bases.length ? `주자 ${bases.join("·")}` : "주자 없음"}`;
    }

    function prior(key) {
      const selected = byKey.get(key);
      if (!selected) return emptyPrior();
      const summary = emptyPrior(), types = new Map();
      let speedSum = 0;
      for (const row of rows) {
        if (row.index >= selected.index) break;
        if (row.pitcher.id !== selected.pitcher.id) continue;
        // Never inspect current/future post, another pitcher's post, or recommendation shares.
        const actual = row.post?.actual;
        if(actual?.description === "automatic_ball" && actual.pitch_type === null && actual.speed_mph === null) continue;
        summary.total++;
        const suppliedCode = typeof actual?.pitch_type === "string" ? actual.pitch_type.trim() : "";
        const code = !suppliedCode || unknownTypes.has(suppliedCode.toLowerCase()) ? "unknown" : suppliedCode;
        if (!types.has(code)) types.set(code, {
          code, label: code === "unknown" ? "구종 미제공" : (actual.pitch_label || code),
          count: 0, share: 0, averageMph: null, speedCount: 0, speedSum: 0,
        });
        const type = types.get(code);
        type.count++;
        const speed = actual?.speed_mph;
        if (typeof speed === "number" && Number.isFinite(speed)) {
          summary.speedCount++; speedSum += speed;
          type.speedCount++; type.speedSum += speed;
        }
      }
      summary.averageMph = summary.speedCount ? speedSum / summary.speedCount : null;
      summary.types = [...types.values()].map(({ speedSum: sum, ...type }) => ({
        ...type, share: type.count / summary.total,
        averageMph: type.speedCount ? sum / type.speedCount : null,
      })).sort((a, b) => b.count - a.count || a.code.localeCompare(b.code));
      return summary;
    }

    function ribbon(key, resultReady) {
      const selected = byKey.get(key);
      if (!selected) return [];
      return rows.filter(row => row.at_bat_number === selected.at_bat_number).map(row => {
        const isCurrent = row.pitch_id === key;
        const visible = row.index < selected.index || (isCurrent && resultReady === true);
        // Keep the access behind the condition: getters in tests enforce this boundary.
        const kind = visible ? (results.get(row.post?.actual?.description) || "unknown") : "hidden";
        return { key: row.pitch_id, pitchNumber: row.pitch_number, label: labels[kind], kind, isCurrent };
      });
    }

    return { options, matchingKeys, situation, prior, ribbon };
  }
  return { create };
});

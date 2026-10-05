/* Deliberately synthetic. No actual game or model output is represented. */
(function (root) {
  const decisions = [
    [14, 1, 0, "ready"],
    [15, 2, 1, "unsupported"],
    [16, 3, 2, "ready"],
  ].map(([index, pitch_number, strikes, status]) => ({
    index,
    pa_id: "900001:5",
    at_bat_number: 5,
    pitch_number,
    situation: {
      inning: 2,
      half: "Top",
      outs: 1,
      balls: 0,
      strikes,
      bases: 3,
      home_score: 0,
      away_score: 1,
    },
    pitcher: { id: 900001, name: "테스트 투수", hand: "R" },
    batter: { id: 900002, name: "테스트 타자", side: "L" },
    status: "TEST_ONLY",
    pre: {
      status,
      reason: status === "unsupported" ? "연결 검사 전용 미지원 사례" : null,
      recommendation:
        status === "unsupported"
          ? null
          : {
              candidates: [
                {
                  rank: 1,
                  pitch_type: "SI",
                  pitch_label: "싱커",
                  zone_id: 7,
                  target: { x: -0.4, z: 1.8 },
                  detail: { probability: 0.48 },
                },
                {
                  rank: 2,
                  pitch_type: "SL",
                  pitch_label: "슬라이더",
                  zone_id: null,
                  target: null,
                  detail: { probability: 0.27 },
                },
              ],
            },
    },
  }));
  const value = {
    schema: "pitcheezy-receiver-v1",
    source: {
      kind: "synthetic",
      revision: "9c3018913780cde2d12db522c2a420a6e283db7c",
      model_id: "synthetic-receiver-test-not-a-model",
      exported_at: "2026-10-05T00:00:00Z",
    },
    game_pk: 900001,
    at_bat_number: 5,
    timeline: {
      schema: "pitcheezy-watch-along-v1",
      game: {
        game_pk: 900001,
        date: "연결 검사 전용",
        away_team: "테스트 원정팀",
        home_team: "테스트 홈팀",
      },
      decisions,
    },
    reveals: decisions.map((d, i) => ({
      pitch_id: `900001:5:${d.pitch_number}`,
      source_endpoint: `/api/watch/900001/reveal/${d.index}`,
      response: {
        index: d.index,
        actual: {
          pitch_type: i === 1 ? null : "SI",
          pitch_label: i === 1 ? null : "싱커",
          result_label: "연결 테스트 결과",
          event_label: null,
          speed_mph: i === 1 ? null : 93.2,
          x: i === 1 ? null : -0.3,
          z: i === 1 ? null : 1.9,
        },
        we: {
          home_before: 0.52,
          home_after: 0.53,
          home_delta: 0.01,
          batting_delta: -0.01,
        },
      },
    })),
  };
  if (typeof module === "object" && module.exports) module.exports = value;
  else root.PitchReceiverSample = value;
})(typeof globalThis === "object" ? globalThis : this);

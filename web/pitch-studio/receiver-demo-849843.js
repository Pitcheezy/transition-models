/* Supplied model responses, display projection only. Not a live model call. */
(function (root) {
  const value = {
    packet: {
      schema: "pitcheezy-receiver-v1",
      source: {
        kind: "provided_export",
        revision: "2eb718ef13024ad2d98d28e248388db7f8dc1bc9",
        model_id:
          "ARM-B P3 (pitch type only), frozen <=2025 (ML-POLICY-VAL-v1)",
        exported_at: "2026-09-30T17:48:53+09:00",
      },
      game_pk: 849843,
      at_bat_number: 1,
      timeline: {
        schema: "pitcheezy-watch-along-v1",
        game: {
          game_pk: 849843,
          date: "2026-09-29",
          game_type: "F",
          away_team: "Chicago Cubs",
          home_team: "San Diego Padres",
        },
        decisions: [
          {
            index: 0,
            pa_id: "849843:1",
            at_bat_number: 1,
            pitch_number: 1,
            situation: {
              inning: 1,
              half: "Top",
              outs: 0,
              balls: 0,
              strikes: 0,
              bases: 0,
              home_score: 0,
              away_score: 0,
            },
            pitcher: {
              id: 650633,
              name: "Michael King",
              hand: "R",
            },
            batter: {
              id: 691718,
              name: "Pete Crow-Armstrong",
              side: "L",
            },
            pre: {
              status: "ready",
              reason: null,
              recommendation: {
                candidates: [
                  {
                    rank: 1,
                    pitch_type: "ST",
                    pitch_label: "스위퍼",
                    zone_id: "low_middle",
                    zone_label: "낮은 중앙",
                    target: {
                      x: 0,
                      z: 1.8983166666666667,
                    },
                    detail: {
                      probability: 0.2747000042139988,
                    },
                  },
                  {
                    rank: 2,
                    pitch_type: "SI",
                    pitch_label: "싱커",
                    zone_id: "middle_middle",
                    zone_label: "가운데 높이 중앙",
                    target: {
                      x: 0,
                      z: 2.4949500000000002,
                    },
                    detail: {
                      probability: 0.2628638309844694,
                    },
                  },
                  {
                    rank: 3,
                    pitch_type: "FF",
                    pitch_label: "포심",
                    zone_id: "high_left",
                    zone_label: "높은 왼쪽",
                    target: {
                      x: -0.5533333333333333,
                      z: 3.0915833333333333,
                    },
                    detail: {
                      probability: 0.26071535924273803,
                    },
                  },
                ],
              },
            },
          },
          {
            index: 1,
            pa_id: "849843:1",
            at_bat_number: 1,
            pitch_number: 2,
            situation: {
              inning: 1,
              half: "Top",
              outs: 0,
              balls: 0,
              strikes: 1,
              bases: 0,
              home_score: 0,
              away_score: 0,
            },
            pitcher: {
              id: 650633,
              name: "Michael King",
              hand: "R",
            },
            batter: {
              id: 691718,
              name: "Pete Crow-Armstrong",
              side: "L",
            },
            pre: {
              status: "ready",
              reason: null,
              recommendation: {
                candidates: [
                  {
                    rank: 1,
                    pitch_type: "CH",
                    pitch_label: "체인지업",
                    zone_id: "low_left",
                    zone_label: "낮은 왼쪽",
                    target: {
                      x: -0.5533333333333333,
                      z: 1.8983166666666667,
                    },
                    detail: {
                      probability: 0.4070252755337158,
                    },
                  },
                  {
                    rank: 2,
                    pitch_type: "FF",
                    pitch_label: "포심",
                    zone_id: "high_middle",
                    zone_label: "높은 중앙",
                    target: {
                      x: 0,
                      z: 3.0915833333333333,
                    },
                    detail: {
                      probability: 0.3470532254523957,
                    },
                  },
                  {
                    rank: 3,
                    pitch_type: "ST",
                    pitch_label: "스위퍼",
                    zone_id: "low_left",
                    zone_label: "낮은 왼쪽",
                    target: {
                      x: -0.5533333333333333,
                      z: 1.8983166666666667,
                    },
                    detail: {
                      probability: 0.12118881480304974,
                    },
                  },
                ],
              },
            },
          },
          {
            index: 2,
            pa_id: "849843:1",
            at_bat_number: 1,
            pitch_number: 3,
            situation: {
              inning: 1,
              half: "Top",
              outs: 0,
              balls: 0,
              strikes: 2,
              bases: 0,
              home_score: 0,
              away_score: 0,
            },
            pitcher: {
              id: 650633,
              name: "Michael King",
              hand: "R",
            },
            batter: {
              id: 691718,
              name: "Pete Crow-Armstrong",
              side: "L",
            },
            pre: {
              status: "ready",
              reason: null,
              recommendation: {
                candidates: [
                  {
                    rank: 1,
                    pitch_type: "SI",
                    pitch_label: "싱커",
                    zone_id: "middle_right",
                    zone_label: "가운데 높이 오른쪽",
                    target: {
                      x: 0.5533333333333333,
                      z: 2.4949500000000002,
                    },
                    detail: {
                      probability: 0.3303230709313974,
                    },
                  },
                  {
                    rank: 2,
                    pitch_type: "FF",
                    pitch_label: "포심",
                    zone_id: "high_left",
                    zone_label: "높은 왼쪽",
                    target: {
                      x: -0.5533333333333333,
                      z: 3.0915833333333333,
                    },
                    detail: {
                      probability: 0.26657454726225066,
                    },
                  },
                  {
                    rank: 3,
                    pitch_type: "CH",
                    pitch_label: "체인지업",
                    zone_id: "low_left",
                    zone_label: "낮은 왼쪽",
                    target: {
                      x: -0.5533333333333333,
                      z: 1.8983166666666667,
                    },
                    detail: {
                      probability: 0.2507603808280645,
                    },
                  },
                ],
              },
            },
          },
        ],
      },
      reveals: [
        {
          pitch_id: "849843:1:1",
          source_endpoint: "/api/watch/849843/reveal/0",
          response: {
            index: 0,
            actual: {
              pitch_type: "SI",
              pitch_label: "싱커",
              description: "called_strike",
              result_label: "루킹 스트라이크",
              event_label: null,
              speed_mph: 96.3,
              x: 0.5020274927383699,
              z: 2.3973047159663667,
            },
            we: {
              home_before: 0.5032562229053412,
              home_after: 0.5032562229053412,
              home_delta: 0,
              batting_delta: 0,
            },
          },
        },
        {
          pitch_id: "849843:1:2",
          source_endpoint: "/api/watch/849843/reveal/1",
          response: {
            index: 1,
            actual: {
              pitch_type: "ST",
              pitch_label: "스위퍼",
              description: "swinging_strike",
              result_label: "헛스윙",
              event_label: null,
              speed_mph: 86.4,
              x: 1.282487876437138,
              z: 1.4800826426424478,
            },
            we: {
              home_before: 0.5032562229053412,
              home_after: 0.5032562229053412,
              home_delta: 0,
              batting_delta: 0,
            },
          },
        },
        {
          pitch_id: "849843:1:3",
          source_endpoint: "/api/watch/849843/reveal/2",
          response: {
            index: 2,
            actual: {
              pitch_type: "FF",
              pitch_label: "포심",
              description: "foul_tip",
              result_label: "삼진",
              event_label: "삼진",
              speed_mph: 97.6,
              x: -0.4124845298848476,
              z: 2.9667149324245607,
            },
            we: {
              home_before: 0.5032562229053412,
              home_after: 0.5272637971898713,
              home_delta: 0.024007574284530042,
              batting_delta: -0.024007574284530042,
            },
          },
        },
      ],
    },
    originals: [
      {
        name: "watch-games.json",
        hash: "aa8aee3e8a2a5428e4243793d6a4cd2b1e3886752edaec3dcb0cea7504c4f0ac",
      },
      {
        name: "watch-849843.json",
        hash: "871b9e20f18e16cf653954e28c107a34df88fee9550d61335ea5fbcdc494a36a",
      },
      {
        name: "reveal-0.json",
        hash: "9248491228832c2512a5d8bad72deeab8b8056989b55d0bf5eefc997ff901340",
      },
      {
        name: "reveal-1.json",
        hash: "c4d3c7a64a30bcfdfe2bf77787941703e9f74af836c03ab33ad732fdc1a649ff",
      },
      {
        name: "reveal-2.json",
        hash: "7b83b5b62bfddb7d52a3b25b60b195fc18a1bc724429ce865d4b6d326531d112",
      },
    ],
    provenance: {
      capture_manifest_sha256:
        "85d39f6ffa5931ceb29e21af23a5317552887298bc4c27d324d8097e98353fc3",
      policy_identity_sha256:
        "a6dffaea70976368a9cdc9f1a8bff4267b1c138162ee48aafda00e81e989109c",
      loaded_backend_commit: null,
      scope:
        "First PA display fields only; original private bundle is not published.",
    },
  };
  if (typeof module === "object" && module.exports) module.exports = value;
  else root.PitchReceiverDemo849843 = value;
})(typeof globalThis === "object" ? globalThis : this);

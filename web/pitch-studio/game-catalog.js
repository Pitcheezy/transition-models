/* Curated archive allowlist. A menu entry never implies a model ran for that game. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.PitchGameCatalog = api;
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";
  const games = [
    {
      game_pk: 849843,
      game_sha256: "89e14e12e0f0a2ae2475aff16b8757486143f6a4586239434a1f8b0be6bb3c22",
      media_sha256: "8680befcbd43b570b1cd2f708e1d767e0e4055a9850dda327ae871219df17e0a",
      zones_sha256: "210fd6bac3a0fe6b89c0c066ed29dd9667f6ee5362d933e17329ebc23771ea8b",
      source_sha256: "df606a11c6db465c054252ef8d331aeb23aa21565b4960bd586f3dcf8f62f6b7",
      statcast_sha256: "0513145c760741abef96fa295a97c1ba80106dfc0db4301544af782277eefd9b",
      feed_sha256: "30b82143aff97f2f85c065a7eaec6d574f8a8fe7765789197b766157c4b0fc56",
      source_kind: "provided_export", pitches: 262, plate_appearances: 71,
      ready: 246, unsupported: 16, missing: 0, media_count: 261, zones_count: 262, non_pitch_ids: [],
      first_pitch: "849843:1:1", away: "CHC", home: "SD",
      title: "시카고 컵스 @ 샌디에이고 파드리스", date: "2026-09-30", local_date: "2026-09-29", timing: true,
    },
    {
      game_pk: 849845,
      game_sha256: "1cfee6332cf2701895b86cb993c68db8ecdac593cc8e402b28401f36160edeee",
      media_sha256: "eee57e8bc87e62a903624b148ac4e48ad80ac6ea918c6044598f110692d7fba2",
      zones_sha256: "b2454e305924beb98977fdee5034c4bdb16c563b78737f684bf5639417d0e4b4",
      source_sha256: "8498af56aa1c4ef9bf9f7e3126b271d4d44c24dd2ea3edda41fc4082e7e4a75e",
      statcast_sha256: "8bb2722a2ac1299f57c977c14ae5690e235bb2d9b170c23b57df3c47ad72d02e",
      feed_sha256: "8498af56aa1c4ef9bf9f7e3126b271d4d44c24dd2ea3edda41fc4082e7e4a75e",
      source_kind: "official_record", pitches: 250, plate_appearances: 70,
      ready: 0, unsupported: 0, missing: 250, media_count: 250, zones_count: 250, non_pitch_ids: [],
      first_pitch: "849845:1:1", away: "PHI", home: "ATL",
      title: "필라델피아 필리스 @ 애틀랜타 브레이브스", date: "2026-09-30", local_date: "2026-09-29", timing: false,
    },
    {
      game_pk: 823407,
      game_sha256: "7552f7d3477c879cbef50bb0a51f7a5c8eb8d8560554deaaf02afacc4a91cdc2",
      media_sha256: "d1e348850599b7577868bb4e8f31aa55632651da939b0ecbcf0f147427876067",
      zones_sha256: "74d9ab1c9d64af72362b5a8a39bff667855948c3d06121e22ddf76ebc704c2dc",
      source_sha256: "1431b296b3ad0ff7aeee83f908e76ab86d9109b9ed0c79d638fc1fdb6281d799",
      statcast_sha256: "b6f8f6eafa969f228fdf994b816b28c9765afc6c267929cbcf01bf920ed43258",
      feed_sha256: "1431b296b3ad0ff7aeee83f908e76ab86d9109b9ed0c79d638fc1fdb6281d799",
      source_kind: "official_record", pitches: 359, plate_appearances: 88,
      ready: 0, unsupported: 0, missing: 359, media_count: 355, zones_count: 355,
      non_pitch_ids: ["823407:35:1","823407:35:2","823407:35:3","823407:35:4"],
      first_pitch: "823407:1:1", away: "TB", home: "PHI",
      title: "탬파베이 레이스 @ 필라델피아 필리스", date: "2026-09-27", local_date: "2026-09-26", timing: false,
    },
  ].map(game => Object.freeze({...game,non_pitch_ids:Object.freeze([...game.non_pitch_ids])}));
  const byId = new Map(games.map(game => [String(game.game_pk), game]));
  function get(id) {
    if (!((typeof id === "string" && /^[1-9][0-9]{0,10}$/.test(id)) || (Number.isSafeInteger(id) && id > 0))) return null;
    return byId.get(String(id)) || null;
  }
  function list() { return Object.freeze([...games]); }
  return Object.freeze({get, list});
});

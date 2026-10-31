/* Recorded strike-zone heights only. No inference or recommendation recalculation. */
(function (root, factory) {
  "use strict";
  const api = factory(typeof module === "object" && module.exports ? require("./game-catalog.js") : root.PitchGameCatalog);
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.PitchReceiverZones = api;
})(typeof globalThis === "object" ? globalThis : this, function (catalog) {
  "use strict";
  const requireValue = (condition, message) => { if (!condition) throw new TypeError(message); };
  const integer = value => Number.isSafeInteger(value) && value > 0;
  function fields(value, names) {
    requireValue(value !== null && typeof value === "object" && !Array.isArray(value), "존 높이 자료 객체가 필요합니다.");
    requireValue(Object.keys(value).length === names.length && names.every(name => Object.hasOwn(value, name)), "존 높이 자료 필드가 계약과 다릅니다.");
  }
  function validate(packet, gamePacket) {
    fields(packet, ["schema", "game_pk", "game_sha256", "source", "units", "timing", "source_pitch_count", "pitches"]);
    const entry = catalog.get(packet.game_pk);
    requireValue(packet.schema === "pitcheezy-strike-zones-v1" && entry, "대상 경기의 존 높이 자료가 아닙니다.");
    requireValue(packet.game_sha256 === entry.game_sha256, "존 높이와 저장 경기의 출처가 다릅니다.");
    fields(packet.source, ["kind", "statcast_sha256", "feed_sha256"]);
    requireValue(packet.source.kind === "statcast_record" && packet.source.statcast_sha256 === entry.statcast_sha256 && packet.source.feed_sha256 === entry.feed_sha256, "존 높이의 원본 기록이 고정본과 다릅니다.");
    fields(packet.units, ["height", "reference", "perspective"]);
    requireValue(packet.units.height === "feet" && packet.units.reference === "ground" && packet.units.perspective === "catcher" && packet.timing === "historical_record", "존 높이의 단위 또는 기록 시점이 다릅니다.");
    requireValue(gamePacket?.schema === "pitcheezy-static-game-v1" && gamePacket.game?.game_pk === packet.game_pk, "존 높이와 경기 자료가 일치하지 않습니다.");
    requireValue(Array.isArray(gamePacket.pitches) && gamePacket.pitches.length === entry.pitches && packet.source_pitch_count === entry.pitches && Array.isArray(packet.pitches) && packet.pitches.length === entry.zones_count, "존 높이 자료의 전체 투구 수가 다릅니다.");
    const pitches = new Map();
    for (const pitch of gamePacket.pitches) {
      requireValue(pitch !== null && typeof pitch === "object" && integer(pitch.at_bat_number) && integer(pitch.pitch_number) && pitch.pitch_id === `${packet.game_pk}:${pitch.at_bat_number}:${pitch.pitch_number}` && !pitches.has(pitch.pitch_id), "저장 경기 투구 키가 잘못됐거나 중복입니다.");
      requireValue(integer(pitch.batter?.id) && integer(pitch.pitcher?.id), "저장 경기 선수 ID가 잘못됐습니다.");
      pitches.set(pitch.pitch_id, pitch);
    }
    const zones = Object.create(null);
    for (const record of packet.pitches) {
      fields(record, ["pitch_id", "batter_id", "pitcher_id", "bottom_ft", "top_ft"]);
      const pitch = pitches.get(record.pitch_id);
      requireValue(typeof record.pitch_id === "string" && pitch && !Object.hasOwn(zones, record.pitch_id), "존 높이 투구 키가 없거나 중복입니다.");
      requireValue(!entry.non_pitch_ids.includes(record.pitch_id), "투구 없는 자동 볼에 기록 존을 채울 수 없습니다.");
      requireValue(integer(record.batter_id) && integer(record.pitcher_id) && record.batter_id === pitch.batter.id && record.pitcher_id === pitch.pitcher.id, "존 높이의 선수 ID가 다릅니다.");
      const bottom = record.bottom_ft, top = record.top_ft;
      requireValue(typeof bottom === "number" && typeof top === "number" && Number.isFinite(bottom) && Number.isFinite(top) && 0.5 <= bottom && bottom < top && top <= 5 && 0.5 <= top - bottom && top - bottom <= 4, "존 높이의 상·하단 값이 잘못됐습니다.");
      zones[record.pitch_id] = Object.freeze({ bottom, top, source: "statcast_record" });
    }
    for (const [id,pitch] of pitches) {
      if (Object.hasOwn(zones,id)) continue;
      const actual = pitch.post?.actual;
      requireValue(entry.non_pitch_ids.includes(id) && actual && actual.description === "automatic_ball" && ["pitch_type","x","z","speed_mph"].every(key => actual[key] === null), "존 높이 자료에서 투구가 누락됐습니다.");
    }
    requireValue(Object.keys(zones).length + entry.non_pitch_ids.length === pitches.size, "존 높이 자료에서 투구가 누락됐습니다.");
    return Object.freeze(zones);
  }
  // The caller hashes the actual fetched bytes and passes the game whose bytes
  // already passed createVerifiedSession. The sidecar's game hash is also pinned.
  function createVerifiedZones(packet, gamePacket, fileHash) {
    const entry = catalog.get(packet?.game_pk);
    requireValue(entry && fileHash === entry.zones_sha256, "존 높이 자료의 실제 바이트 SHA가 고정본과 다릅니다.");
    return validate(packet, gamePacket);
  }
  return Object.freeze({ validate, createVerifiedZones, expectedSHA: catalog.get(849843).zones_sha256, expectedGameSHA: catalog.get(849843).game_sha256 });
});

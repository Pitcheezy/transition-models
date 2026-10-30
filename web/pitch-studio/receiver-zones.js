/* Recorded strike-zone heights only. No inference or recommendation recalculation. */
(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.PitchReceiverZones = api;
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";
  const GAME_SHA256 = "89e14e12e0f0a2ae2475aff16b8757486143f6a4586239434a1f8b0be6bb3c22";
  const ASSET_SHA256 = "210fd6bac3a0fe6b89c0c066ed29dd9667f6ee5362d933e17329ebc23771ea8b";
  const STATCAST_SHA256 = "0513145c760741abef96fa295a97c1ba80106dfc0db4301544af782277eefd9b";
  const FEED_SHA256 = "30b82143aff97f2f85c065a7eaec6d574f8a8fe7765789197b766157c4b0fc56";
  const requireValue = (condition, message) => { if (!condition) throw new TypeError(message); };
  const integer = value => Number.isSafeInteger(value) && value > 0;
  function fields(value, names) {
    requireValue(value !== null && typeof value === "object" && !Array.isArray(value), "존 높이 자료 객체가 필요합니다.");
    requireValue(Object.keys(value).length === names.length && names.every(name => Object.hasOwn(value, name)), "존 높이 자료 필드가 계약과 다릅니다.");
  }
  function validate(packet, gamePacket) {
    fields(packet, ["schema", "game_pk", "game_sha256", "source", "units", "timing", "source_pitch_count", "pitches"]);
    requireValue(packet.schema === "pitcheezy-strike-zones-v1" && packet.game_pk === 849843, "대상 경기의 존 높이 자료가 아닙니다.");
    requireValue(packet.game_sha256 === GAME_SHA256, "존 높이와 저장 경기의 출처가 다릅니다.");
    fields(packet.source, ["kind", "statcast_sha256", "feed_sha256"]);
    requireValue(packet.source.kind === "statcast_record" && packet.source.statcast_sha256 === STATCAST_SHA256 && packet.source.feed_sha256 === FEED_SHA256, "존 높이의 원본 기록이 고정본과 다릅니다.");
    fields(packet.units, ["height", "reference", "perspective"]);
    requireValue(packet.units.height === "feet" && packet.units.reference === "ground" && packet.units.perspective === "catcher" && packet.timing === "historical_record", "존 높이의 단위 또는 기록 시점이 다릅니다.");
    requireValue(gamePacket?.schema === "pitcheezy-static-game-v1" && gamePacket.game?.game_pk === 849843, "존 높이와 경기 자료가 일치하지 않습니다.");
    requireValue(Array.isArray(gamePacket.pitches) && gamePacket.pitches.length === 262 && packet.source_pitch_count === 262 && Array.isArray(packet.pitches) && packet.pitches.length === 262, "존 높이 자료의 전체 투구 수가 다릅니다.");
    const pitches = new Map();
    for (const pitch of gamePacket.pitches) {
      requireValue(pitch !== null && typeof pitch === "object" && integer(pitch.at_bat_number) && integer(pitch.pitch_number) && pitch.pitch_id === `849843:${pitch.at_bat_number}:${pitch.pitch_number}` && !pitches.has(pitch.pitch_id), "저장 경기 투구 키가 잘못됐거나 중복입니다.");
      requireValue(integer(pitch.batter?.id) && integer(pitch.pitcher?.id), "저장 경기 선수 ID가 잘못됐습니다.");
      pitches.set(pitch.pitch_id, pitch);
    }
    const zones = Object.create(null);
    for (const record of packet.pitches) {
      fields(record, ["pitch_id", "batter_id", "pitcher_id", "bottom_ft", "top_ft"]);
      const pitch = pitches.get(record.pitch_id);
      requireValue(typeof record.pitch_id === "string" && pitch && !Object.hasOwn(zones, record.pitch_id), "존 높이 투구 키가 없거나 중복입니다.");
      requireValue(integer(record.batter_id) && integer(record.pitcher_id) && record.batter_id === pitch.batter.id && record.pitcher_id === pitch.pitcher.id, "존 높이의 선수 ID가 다릅니다.");
      const bottom = record.bottom_ft, top = record.top_ft;
      requireValue(typeof bottom === "number" && typeof top === "number" && Number.isFinite(bottom) && Number.isFinite(top) && 0.5 <= bottom && bottom < top && top <= 5 && 0.5 <= top - bottom && top - bottom <= 4, "존 높이의 상·하단 값이 잘못됐습니다.");
      zones[record.pitch_id] = Object.freeze({ bottom, top, source: "statcast_record" });
    }
    requireValue(Object.keys(zones).length === pitches.size, "존 높이 자료에서 투구가 누락됐습니다.");
    return Object.freeze(zones);
  }
  // The caller hashes the actual fetched bytes and passes the game whose bytes
  // already passed createVerifiedSession. The sidecar's game hash is also pinned.
  function createVerifiedZones(packet, gamePacket, fileHash) {
    requireValue(fileHash === ASSET_SHA256, "존 높이 자료의 실제 바이트 SHA가 고정본과 다릅니다.");
    return validate(packet, gamePacket);
  }
  return Object.freeze({ validate, createVerifiedZones, expectedSHA: ASSET_SHA256, expectedGameSHA: GAME_SHA256 });
});

/* Pitch-ID media binding for the pinned saved game. No inference or remote-byte verification. */
(function (root, factory) {
  "use strict";
  const api = factory(typeof module === "object" && module.exports ? require("./game-catalog.js") : root.PitchGameCatalog);
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.PitchReceiverGameMedia = api;
})(typeof globalThis === "object" ? globalThis : this, function (catalog) {
  "use strict";
  const HASH = /^[a-f0-9]{64}$/;
  const UUID = /^[a-f0-9]{8}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{4}-[a-f0-9]{12}$/;
  const TYPE = /^[A-Z]{2}$/;
  const requireValue = (condition, message) => { if (!condition) throw new TypeError(message); };
  const copy = value => JSON.parse(JSON.stringify(value));
  function fields(value, names) {
    requireValue(value !== null && typeof value === "object" && !Array.isArray(value), "영상 자료 객체가 필요합니다.");
    requireValue(Object.keys(value).length === names.length && names.every(n => Object.hasOwn(value, n)), "영상 자료 필드가 계약과 다릅니다.");
  }
  function freeze(value) {
    for (const child of Object.values(value)) if (child && typeof child === "object") freeze(child);
    return Object.freeze(value);
  }
  function validate(packet, game, baseMedia = {}) {
    fields(packet, ["schema", "game_pk", "game_sha256", "registry_sha256", "source_pitch_count", "records", "excluded"]);
    const entry = catalog.get(packet.game_pk);
    requireValue(packet.schema === "pitcheezy-static-game-media-v1" && entry, "대상 경기 영상 목록이 아닙니다.");
    requireValue(packet.game_sha256 === entry.game_sha256 && HASH.test(packet.registry_sha256), "영상과 저장 경기의 출처가 다릅니다.");
    requireValue(game?.schema === "pitcheezy-static-game-v1" && game.game?.game_pk === packet.game_pk, "경기 자료가 일치하지 않습니다.");
    requireValue(Array.isArray(game.pitches) && game.pitches.length === entry.pitches && packet.source_pitch_count === entry.pitches, "전체 투구 수가 일치하지 않습니다.");
    requireValue(Array.isArray(packet.records) && Array.isArray(packet.excluded) && packet.records.length + packet.excluded.length === entry.pitches, "영상과 제외 목록의 전체 투구 수가 다릅니다.");
    const pitches = new Map();
    for (const pitch of game.pitches) {
      requireValue(pitch.pitch_id === `${packet.game_pk}:${pitch.at_bat_number}:${pitch.pitch_number}` && !pitches.has(pitch.pitch_id), "저장 경기 투구 키가 잘못됐습니다.");
      pitches.set(pitch.pitch_id, pitch);
    }
    const seen = new Set(), plays = new Set(), media = Object.create(null), excluded = Object.create(null);
    function take(id) {
      requireValue(typeof id === "string" && pitches.has(id) && !seen.has(id), "영상 투구 키가 없거나 중복입니다.");
      seen.add(id);
      return pitches.get(id);
    }
    for (const record of packet.records) {
      fields(record, ["pitch_id", "at_bat_number", "pitch_number", "play_id", "pitcher_id", "batter_id", "pitch_type", "video", "page_url", "video_sha256", "bytes", "duration_seconds"]);
      const pitch = take(record.pitch_id);
      requireValue(record.at_bat_number === pitch.at_bat_number && record.pitch_number === pitch.pitch_number, "영상 타석·투구 번호가 다릅니다.");
      requireValue(record.pitcher_id === pitch.pitcher?.id && record.batter_id === pitch.batter?.id, "영상 선수 ID가 다릅니다.");
      requireValue(typeof record.pitch_type === "string" && TYPE.test(record.pitch_type) && record.pitch_type === pitch.post?.actual?.pitch_type, "영상과 저장 결과의 구종이 다릅니다.");
      requireValue(typeof record.play_id === "string" && UUID.test(record.play_id) && !plays.has(record.play_id), "공식 playId가 잘못됐거나 중복입니다.");
      plays.add(record.play_id);
      requireValue(typeof record.video === "string" && record.video.length < 1000 && /^https:\/\/sporty-clips\.mlb\.com\/[A-Za-z0-9_+=-]+\.mp4$/.test(record.video), "허용된 공식 영상 주소가 아닙니다.");
      requireValue(record.page_url === `https://baseballsavant.mlb.com/sporty-videos?playId=${record.play_id}`, "공식 영상 출처와 playId가 다릅니다.");
      requireValue(typeof record.video_sha256 === "string" && HASH.test(record.video_sha256), "기록된 영상 SHA가 필요합니다.");
      requireValue(Number.isSafeInteger(record.bytes) && record.bytes > 0 && record.bytes <= 80_000_000, "기록된 영상 크기가 잘못됐습니다.");
      requireValue(typeof record.duration_seconds === "number" && Number.isFinite(record.duration_seconds) && record.duration_seconds > 0 && record.duration_seconds <= 120, "기록된 영상 길이가 잘못됐습니다.");
      media[record.pitch_id] = copy(record);
    }
    for (const item of packet.excluded) {
      fields(item, ["pitch_id", "reason", "registry_pitch_type", "received_pitch_type"]);
      const pitch = take(item.pitch_id);
      const actual = pitch.post?.actual;
      if (item.reason === "automatic_ball_no_video") {
        requireValue(entry.non_pitch_ids.includes(item.pitch_id) && actual && actual.description === "automatic_ball" && ["pitch_type","x","z","speed_mph"].every(key => actual[key] === null) && item.registry_pitch_type === null && item.received_pitch_type === null, "자동 볼의 영상 제외 근거가 저장 결과와 다릅니다.");
      } else {
        requireValue(item.reason === "pitch_type_mismatch" && TYPE.test(item.registry_pitch_type) && TYPE.test(item.received_pitch_type) && item.registry_pitch_type !== item.received_pitch_type && item.received_pitch_type === actual?.pitch_type, "영상 제외 근거가 저장 결과와 다릅니다.");
      }
      excluded[item.pitch_id] = copy(item);
    }
    requireValue(seen.size === pitches.size, "영상 목록에서 투구가 누락됐습니다.");
    requireValue(baseMedia !== null && typeof baseMedia === "object" && !Array.isArray(baseMedia), "기존 영상 목록이 잘못됐습니다.");
    for (const [id, local] of Object.entries(baseMedia)) {
      const record = media[id];
      requireValue(/^849843:1:[123]$/.test(id) && record && local.pitch_id === id && local.pitch_number === record.pitch_number && local.play_id === record.play_id && local.video_sha256 === record.video_sha256, "기존 영상과 새 투구 목록의 신원이 다릅니다.");
      requireValue(local.video === `media/pitch-849843-1-${record.pitch_number}-official.mp4` && local.poster === `media/pitch-849843-1-${record.pitch_number}-official.jpg` && HASH.test(local.poster_sha256) && local.page_url === record.page_url, "기존 영상 자산 경로가 다릅니다.");
      media[id] = { ...record, ...copy(local), at_bat_number: record.at_bat_number };
    }
    return freeze({ media, excluded });
  }
  // Caller must pass the game whose exact bytes already passed createVerifiedSession.
  // The manifest hash authenticates the shipped mapping, not current MLB response bytes.
  function createVerifiedMedia(packet, game, actualSha256, baseMedia = {}) {
    const entry = catalog.get(packet?.game_pk);
    requireValue(entry && actualSha256 === entry.media_sha256 && HASH.test(actualSha256), "영상 목록의 실제 바이트 SHA가 고정본과 다릅니다.");
    return validate(packet, game, baseMedia);
  }
  return Object.freeze({ validate, createVerifiedMedia });
});

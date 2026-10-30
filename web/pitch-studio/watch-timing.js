/* Local replay annotations, never a live model result or catcher-coordinate measurement. */
(function(root) {
  "use strict";
  const ASSET_SHA256 = "4126a81ced9ee934a406a7aee69a5798a82f6644e8f04cfd3cec088d947198c6";
  const labels = {catch:"포구",contact:"배트 접촉",plate_arrival:"포수 앞 공 도착"};
  const check = (yes, message) => { if (!yes) throw new TypeError(message); };
  function validate(packet, media) {
    check(packet?.schema === "pitcheezy-watch-events-v1" && packet.game_pk === 849843 && Array.isArray(packet.records), "재생 시점 자료가 다릅니다.");
    const result = Object.create(null);
    for (const row of packet.records) {
      const record = media[row.pitch_id];
      check(/^849843:[1-5]:[1-9]\d*$/.test(row.pitch_id) && !Object.hasOwn(result,row.pitch_id), "시점 투구가 범위 밖이거나 중복입니다.");
      check(record && row.play_id === record.play_id && /^[a-f0-9]{64}$/.test(row.video_sha256) && row.video_sha256 === record.video_sha256, "시점과 영상의 신원이 다릅니다.");
      check(Object.hasOwn(labels,row.event_kind) && row.method === "ai_frame_review", "시점의 관측 근거가 없습니다.");
      check([row.lower_seconds,row.upper_seconds,record.duration_seconds].every(x=>typeof x==="number"&&Number.isFinite(x))
        && row.lower_seconds>=0 && row.upper_seconds>row.lower_seconds && row.upper_seconds<record.duration_seconds
        && row.upper_seconds-row.lower_seconds<=0.25, "시점 경계가 잘못됐습니다.");
      result[row.pitch_id]=Object.freeze({...row,label:labels[row.event_kind]});
    }
    return Object.freeze(result);
  }
  function createVerifiedTiming(packet,media,hash) {
    check(hash===ASSET_SHA256,"재생 시점 파일의 SHA가 고정본과 다릅니다.");
    return validate(packet,media);
  }
  function reached(event,time,duration) {
    return Boolean(event && Number.isFinite(time) && Number.isFinite(duration)
      && event.upper_seconds < duration && time >= event.upper_seconds);
  }
  const api={validate,createVerifiedTiming,reached};
  if(typeof module!=="undefined"&&module.exports) module.exports=api;
  else root.PitchWatchTiming=api;
})(typeof window!=="undefined"?window:globalThis);

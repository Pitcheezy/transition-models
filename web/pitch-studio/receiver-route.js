/* Public replay navigation only. No result/reveal state is serialized. */
(function (root, factory) {
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.PitchReceiverRoute = api;
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";
  const FIRST = "849843:1:1";
  function pitch(value) {
    if (typeof value !== "string" || !/^849843:[1-9][0-9]{0,2}:[1-9][0-9]?$/.test(value))
      throw new Error("올바른 경기·타석·투구 주소가 아닙니다.");
    return value;
  }
  function parse(search) {
    const q = new URLSearchParams(search);
    for (const k of ["game", "pitch", "archive", "demo", "mode"])
      if (q.getAll(k).length > 1) throw new Error("중복된 관전 주소입니다.");
    if (q.get("mode") === "file") return { mode: "file", pitchId: null };
    if (q.has("game") && q.get("game") !== "849843") throw new Error("지원하지 않는 경기 주소입니다.");
    if (q.has("archive") && q.get("archive") !== "first-pa") throw new Error("지원하지 않는 보관 자료입니다.");
    const archive = q.get("archive") === "first-pa";
    const legacy = q.get("demo") === "849843-pa1";
    let key = q.get("pitch") || FIRST;
    if (legacy && /^[1-3]$/.test(key)) key = `849843:1:${key}`;
    pitch(key);
    if (archive && !/^849843:1:[1-3]$/.test(key)) throw new Error("옛 수신본은 첫 타석 3구만 포함합니다.");
    return { mode: archive ? "archive" : "game", pitchId: key };
  }
  function query(mode, key) {
    if (mode === "file") return "?mode=file";
    pitch(key);
    if (mode === "archive" && !/^849843:1:[1-3]$/.test(key)) throw new Error("보관 자료 범위를 벗어났습니다.");
    if (!["game", "archive"].includes(mode)) throw new Error("관전 모드가 올바르지 않습니다.");
    return `${mode === "archive" ? "?archive=first-pa" : "?game=849843"}&pitch=${encodeURIComponent(key)}`;
  }
  return { parse, query, FIRST };
});

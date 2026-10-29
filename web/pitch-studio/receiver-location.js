/* Display geometry only: no DOM, network, inference, or physical coordinate conversion. */
(function (root, factory) {
  "use strict";
  const api = factory();
  if (typeof module === "object" && module.exports) module.exports = api;
  else root.PitchReceiverLocation = api;
})(typeof globalThis === "object" ? globalThis : this, function () {
  "use strict";

  const domain = Object.freeze({ xMin: -2, xMax: 2, zMin: 0, zMax: 5 });
  const finite = (value) => typeof value === "number" && Number.isFinite(value);
  const object = (value) => value !== null && typeof value === "object" && !Array.isArray(value);
  const label = (value, fallback) => typeof value === "string" && value.trim() ? value : fallback;

  function position(value) {
    const x = object(value) && finite(value.x) ? value.x : null;
    const z = object(value) && finite(value.z) ? value.z : null;
    if (x === null || z === null) return { x, z, status: "missing", nx: null, ny: null };
    if (x < domain.xMin || x > domain.xMax || z < domain.zMin || z > domain.zMax)
      return { x, z, status: "outside", nx: null, ny: null };
    return {
      x, z, status: "plottable",
      nx: (x - domain.xMin) / (domain.xMax - domain.xMin),
      ny: (domain.zMax - z) / (domain.zMax - domain.zMin),
    };
  }

  /**
   * Build one fixed feet-domain chart from a validated PitchReceiver session.view().
   * nx increases left to right; ny increases top to bottom. Missing/outside pairs
   * have no drawing coordinates. Actual plate position is read only after reveal.
   * Identical plotted recommendations share a rank label without dropping rows.
   * null clears the chart; malformed current identity throws for the caller to clear.
   */
  function build(view) {
    if (view == null) return null;
    if (!object(view) || typeof view.pitch_id !== "string" ||
        !/^[1-9][0-9]*:[1-9][0-9]*:[1-9][0-9]*$/.test(view.pitch_id))
      throw new TypeError("현재 투구 식별자가 필요합니다.");

    const candidates = view.pre?.status === "ready" && Array.isArray(view.pre.candidates)
      ? view.pre.candidates : [];
    const recommendations = candidates.map((candidate) => {
      if (!object(candidate) || !Number.isSafeInteger(candidate.rank) ||
          candidate.rank < 1 || candidate.rank > 30)
        throw new TypeError("추천 후보의 순위가 올바르지 않습니다.");
      return {
        rank: candidate.rank,
        label: label(candidate.pitch_label, label(candidate.pitch_type, "추천 구종")),
        ...position(candidate.target),
      };
    });

    const grouped = new Map();
    for (const row of recommendations) {
      if (row.status !== "plottable") continue;
      const key = JSON.stringify([row.x, row.z]);
      if (!grouped.has(key)) grouped.set(key, {
        ranks: [], label: "", x: row.x, z: row.z, nx: row.nx, ny: row.ny,
      });
      grouped.get(key).ranks.push(row.rank);
    }
    const groups = Array.from(grouped.values(), (group) => {
      group.ranks.sort((a, b) => a - b);
      group.label = group.ranks.join("·");
      return group;
    });

    const revealed = view.revealed === true;
    let actual = null;
    if (revealed && object(view.post?.actual)) actual = {
      label: label(view.post.actual.pitch_label, "실제 투구"),
      ...position(view.post.actual),
    };
    return { pitch_id: view.pitch_id, domain: { ...domain }, recommendations, groups, actual, revealed };
  }

  function marker(group) {
    const text = group.label.length <= 7 ? group.label : `${group.ranks[0]}+${group.ranks.length - 1}`;
    return { text, width: Math.max(24, 7 * text.length + 10) };
  }

  return { build, marker };
});

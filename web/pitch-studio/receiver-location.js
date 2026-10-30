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

  function perspectiveInfo(perspective = "catcher") {
    if (perspective === "pitcher") return {
      label: "중계 방향 · 투수 → 포수",
      description: "중앙 외야 영상과 같은 좌우 방향입니다. 원본 x는 왼쪽이 양수, 오른쪽이 음수입니다.",
    };
    if (perspective === "catcher") return {
      label: "포수 시점 · 포수 → 투수",
      description: "포수 뒤에서 투수를 보는 방향입니다. 중앙 외야 영상과 좌우가 반대이며, 원본 x는 오른쪽이 양수입니다.",
    };
    throw new TypeError("지원하지 않는 도표 시점입니다.");
  }

  // Only display direction changes. The source x value and its sign stay intact.
  function screenX(x, perspective = "catcher") {
    perspectiveInfo(perspective);
    if (!finite(x) || x < domain.xMin || x > domain.xMax) return null;
    return (perspective === "pitcher" ? domain.xMax - x : x - domain.xMin) / (domain.xMax - domain.xMin);
  }
  function horizontalTicks(perspective = "catcher") {
    perspectiveInfo(perspective);
    return perspective === "pitcher" ? [2, 1, 0, -1, -2] : [-2, -1, 0, 1, 2];
  }

  function position(value, perspective = "catcher") {
    const x = object(value) && finite(value.x) ? value.x : null;
    const z = object(value) && finite(value.z) ? value.z : null;
    if (x === null || z === null) return { x, z, status: "missing", nx: null, ny: null };
    if (x < domain.xMin || x > domain.xMax || z < domain.zMin || z > domain.zMax)
      return { x, z, status: "outside", nx: null, ny: null };
    return {
      x, z, status: "plottable",
      nx: screenX(x, perspective),
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
  function build(view, recordedZone = null, perspective = "catcher") {
    perspectiveInfo(perspective);
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
        ...position(candidate.target, perspective),
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
      ...position(view.post.actual, perspective),
    };
    let zone = null;
    if (revealed && recordedZone !== null) {
      if (!object(recordedZone) || recordedZone.source !== "statcast_record" ||
          !finite(recordedZone.bottom) || !finite(recordedZone.top) ||
          recordedZone.bottom < domain.zMin || recordedZone.top > domain.zMax ||
          recordedZone.bottom >= recordedZone.top) throw new TypeError("존 높이 자료가 올바르지 않습니다.");
      // Home-plate width: 17 inches. This outline does not classify umpire calls.
      const halfWidth = 17 / 24;
      const upperLeft = position({x:-halfWidth,z:recordedZone.top});
      const lowerRight = position({x:halfWidth,z:recordedZone.bottom});
      zone = { ...recordedZone, nx:upperLeft.nx, ny:upperLeft.ny,
        nw:lowerRight.nx-upperLeft.nx, nh:lowerRight.ny-upperLeft.ny };
    }
    return { pitch_id: view.pitch_id, domain: { ...domain }, recommendations, groups, actual, revealed, zone };
  }

  function marker(group) {
    const text = group.label.length <= 7 ? group.label : `${group.ranks[0]}+${group.ranks.length - 1}`;
    return { text, width: Math.max(24, 7 * text.length + 10) };
  }

  // Schematic aid only. Never read the current batter's post-pitch zone here.
  function referenceZone() {
    const upperLeft = position({x: -17/24, z: 3.5});
    const lowerRight = position({x: 17/24, z: 1.5});
    return {source:"display_reference",bottom:1.5,top:3.5,
      nx:upperLeft.nx,ny:upperLeft.ny,nw:lowerRight.nx-upperLeft.nx,nh:lowerRight.ny-upperLeft.ny};
  }

  return { build, marker, referenceZone, screenX, horizontalTicks, perspectiveInfo };
});

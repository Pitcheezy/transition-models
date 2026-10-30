/* Opt-in, one-plate-appearance replay. Results are never inferred here. */
(function (root) {
  "use strict";
  function create({ getState, startClip, advance, onChange,
    schedule = setTimeout, cancel = clearTimeout, delayMs = 5000 }) {
    if (![getState, startClip, advance, onChange, schedule, cancel].every(fn => typeof fn === "function")
        || !Number.isFinite(delayMs) || delayMs < 0)
      throw new TypeError("Invalid sequence controller options");
    let active = false, phase = "stopped", epoch = 0, timer = null, expected = null;
    function notify(reason) { onChange({ active, phase, reason }); }
    function clearTimer() {
      if (timer !== null) cancel(timer);
      timer = null;
    }
    function stop(reason = "manual") {
      epoch++;
      clearTimer();
      active = false;
      phase = "stopped";
      expected = null;
      notify(reason);
    }
    function read() {
      try { return getState(); } catch (_) { return null; }
    }
    function valid(state) {
      const pitch = typeof state?.pitchId === "string" && /^(\d+):(\d+):(\d+)$/.exec(state.pitchId);
      const next = typeof state?.nextId === "string" && /^(\d+):(\d+):(\d+)$/.exec(state.nextId);
      return state?.enabled === true && typeof state.binding === "string" && state.binding.length > 0
        && pitch && Number(pitch[2]) === state.pa && Number(pitch[3]) > 0
        && Number.isInteger(state.pa) && state.pa > 0
        && (state.nextId === null || (next && next[1] === pitch[1] && next[2] === pitch[2]
          && Number(next[3]) > Number(pitch[3])));
    }
    function matches(state) {
      return active && valid(state) && expected && state.binding === expected.binding
        && state.pitchId === expected.pitchId && state.pa === expected.pa;
    }
    function launch(state) {
      const request = ++epoch;
      expected = { binding: state.binding, pitchId: state.pitchId, pa: state.pa, nextId: state.nextId };
      phase = "playing";
      notify("playing");
      if (!active || epoch !== request) return;
      let result;
      try { result = startClip(); }
      catch (_) { if (active && epoch === request) stop("blocked"); return; }
      Promise.resolve(result).then(ok => {
        if (active && epoch === request && matches(read()) && ok === false) stop("blocked");
      }, () => {
        if (active && epoch === request && matches(read())) stop("blocked");
      });
    }
    function start() {
      epoch++;
      clearTimer();
      const state = read();
      if (!valid(state)) { stop("unavailable"); return false; }
      if (state.hasVideo !== true) { stop("missing"); return false; }
      active = true;
      launch(state);
      return active;
    }
    function ended(binding) {
      const state = read();
      if (!active || phase !== "playing" || !matches(state)
          || binding !== expected.binding || state.revealed !== true) return;
      if (state.hasVideo !== true) { stop("missing"); return; }
      if (state.nextId !== expected.nextId) { stop("changed"); return; }
      if (state.nextId === null) { stop("complete"); return; }
      const request = epoch, completed = { ...expected };
      phase = "waiting";
      notify("waiting");
      if (!active || epoch !== request || phase !== "waiting") return;
      timer = schedule(() => {
        if (!active || epoch !== request || phase !== "waiting") return;
        timer = null;
        const current = read();
        if (!matches(current) || current.revealed !== true || current.nextId !== completed.nextId) {
          stop("changed"); return;
        }
        if (current.hasVideo !== true) { stop("missing"); return; }
        // Retire this timer before advancing: a duplicate callback cannot advance twice.
        phase = "transitioning";
        try { advance(completed.nextId); }
        catch (_) { if (active && epoch === request) stop("changed"); return; }
        if (!active || epoch !== request) return;
        const next = read();
        if (!valid(next) || next.pa !== completed.pa || next.pitchId !== completed.nextId
            || next.binding === completed.binding || next.revealed !== false) {
          stop("changed"); return;
        }
        if (next.hasVideo !== true) { stop("missing"); return; }
        launch(next);
      }, delayMs);
    }
    return { start, ended, stop, isActive: () => active };
  }
  const api = { create };
  if (typeof module !== "undefined" && module.exports) module.exports = api;
  else root.PitchReceiverSequence = api;
})(typeof window !== "undefined" ? window : globalThis);

/** Fixed, bounded synthetic viewer polling. This module never opens a network connection. */
import { setTimeout as delay } from "node:timers/promises";

export const VIEWER_POLICY = Object.freeze({
  interval_ms: 5000, polls_per_viewer: 6, objects_per_poll: 2,
  payload_bytes: 32768, max_start_lateness_ms: 500, maximum_body_bytes: 64 * 1024 * 1024,
});
const round = value => Math.round(value * 100) / 100;
const safeReadCodes = new Set(["read_status", "read_integrity", "read_date", "read_age", "read_cache"]);

export function validateViewerWorkload(input = {}) {
  if (!input || typeof input !== "object" || Array.isArray(input) ||
      Object.keys(input).sort().join(",") !== "viewers" || ![30, 50].includes(input.viewers)) {
    throw new Error("invalid_viewer_workload");
  }
  const expected = input.viewers * VIEWER_POLICY.polls_per_viewer * VIEWER_POLICY.objects_per_poll;
  if (expected * VIEWER_POLICY.payload_bytes > VIEWER_POLICY.maximum_body_bytes) {
    throw new Error("invalid_viewer_workload");
  }
  return { mode: "viewer-polling", viewers: input.viewers, ...VIEWER_POLICY,
    expected_load_requests: expected, expected_load_body_bytes: expected * VIEWER_POLICY.payload_bytes,
    scheduled_window_ms: VIEWER_POLICY.interval_ms * VIEWER_POLICY.polls_per_viewer,
    last_scheduled_start_ms: VIEWER_POLICY.interval_ms * (VIEWER_POLICY.polls_per_viewer - 1) };
}

const realClock = {
  now: () => performance.now(),
  wait: (ms, signal) => delay(Math.max(0, ms), undefined, { signal }),
};

/** read(viewerIndex, objectIndex, signal) must consume and verify the whole response.
 * A private injected clock is for scheduler tests; CLI profiles always use the real clock.
 */
export async function runViewerSchedule(input, read, { signal, clock = realClock } = {}) {
  const profile = validateViewerWorkload(input);
  if (typeof read !== "function") throw new Error("invalid_reader");
  const controller = new AbortController();
  const begin = clock.now();
  const counts = { planned: profile.expected_load_requests, started: 0,
    succeeded: 0, failed: 0, cancelled: 0, not_started: profile.expected_load_requests };
  const samples = [], errors = [];
  const polls = Array.from({ length: profile.viewers }, (_, viewer) =>
    Array.from({ length: profile.polls_per_viewer }, (_, slot) => ({
      viewer, slot, scheduled_offset_ms: slot * profile.interval_ms, state: "not_started",
      started_offset_ms: null, start_lateness_ms: null, finished_offset_ms: null,
      duration_ms: null, reads_started: 0, reads_succeeded: 0,
    })));
  let failure = null, inFlight = 0, maximumInFlight = 0;
  const fail = code => { failure ??= code; controller.abort(); };
  const externalAbort = () => fail("aborted");
  signal?.addEventListener("abort", externalAbort, { once: true });
  if (signal?.aborted) externalAbort();

  const viewerLoop = async viewer => {
    for (const row of polls[viewer]) {
      if (controller.signal.aborted) break;
      const due = begin + row.scheduled_offset_ms;
      try {
        await clock.wait(Math.max(0, due - clock.now()), controller.signal);
      } catch { if (!controller.signal.aborted) fail("scheduler_failed"); break; }
      if (controller.signal.aborted) break;
      const started = clock.now();
      row.started_offset_ms = round(started - begin);
      row.start_lateness_ms = round(Math.max(0, started - due));
      if (started - due > profile.max_start_lateness_ms) {
        row.state = "missed"; fail("start_late"); break;
      }
      row.state = "running";
      const boundary = due + profile.interval_ms;
      const stopTimer = new AbortController();
      const boundarySignal = AbortSignal.any([controller.signal, stopTimer.signal]);
      const boundaryWait = clock.wait(Math.max(0, boundary - clock.now()), boundarySignal)
        .then(() => { if (!stopTimer.signal.aborted && !controller.signal.aborted) {
          row.state = "missed"; fail("poll_overrun");
        } })
        .catch(() => { if (!boundarySignal.aborted) fail("scheduler_failed"); });
      try {
        for (let object = 0; object < profile.objects_per_poll; object++) {
          if (controller.signal.aborted) break;
          if (clock.now() >= boundary) { row.state = "missed"; fail("poll_overrun"); break; }
          counts.started++; counts.not_started--; row.reads_started++;
          inFlight++; maximumInFlight = Math.max(maximumInFlight, inFlight);
          const requestStarted = clock.now();
          try {
            await read(viewer, object, controller.signal);
            counts.succeeded++; row.reads_succeeded++;
            samples.push(clock.now() - requestStarted);
          } catch (error) {
            if (controller.signal.aborted) {
              counts.cancelled++; errors.push("cancelled");
            } else {
              counts.failed++;
              const code = safeReadCodes.has(error?.message) ? error.message : "request_failed";
              errors.push(code); fail(code);
            }
          } finally { inFlight--; }
          if (clock.now() >= boundary && !controller.signal.aborted) {
            row.state = "missed"; fail("poll_overrun");
          }
          if (controller.signal.aborted) break;
        }
        if (row.state === "running") {
          row.state = !controller.signal.aborted && row.reads_succeeded === profile.objects_per_poll
            ? "completed" : "cancelled";
        }
      } finally {
        stopTimer.abort();
        await boundaryWait;
        row.finished_offset_ms = round(clock.now() - begin);
        row.duration_ms = round(clock.now() - started);
      }
      if (controller.signal.aborted) break;
    }
  };

  try {
    // Settle every admitted read before the caller disposes its temporary runtime.
    const settled = await Promise.allSettled(polls.map((_, viewer) =>
      viewerLoop(viewer).catch(error => { fail("scheduler_failed"); throw error; })));
    if (settled.some(result => result.status === "rejected")) fail("scheduler_failed");
  } finally { signal?.removeEventListener("abort", externalAbort); }
  const flat = polls.flat();
  const completed = flat.filter(row => row.state === "completed").length;
  const delays = flat.filter(row => row.start_lateness_ms !== null).map(row => row.start_lateness_ms);
  return { profile, request_counts: counts, samples_ms: samples, failure_codes: errors,
    elapsed_ms: round(clock.now() - begin), maximum_in_flight: maximumInFlight,
    in_flight_at_finish: inFlight, completed_polls: completed,
    missed_polls: flat.filter(row => row.state === "missed").length,
    maximum_start_lateness_ms: delays.length ? Math.max(...delays) : null,
    polls: flat, failure,
    passed: failure === null && counts.succeeded === counts.planned &&
      counts.failed === 0 && counts.cancelled === 0 && inFlight === 0 &&
      completed === profile.viewers * profile.polls_per_viewer };
}
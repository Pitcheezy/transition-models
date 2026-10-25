import test from "node:test";
import assert from "node:assert/strict";
import { runViewerSchedule, validateViewerWorkload, VIEWER_POLICY } from "../rehearsal/viewer-polling.mjs";
import { main, validateWorkload } from "../rehearse-local.mjs";
import { writeFile, readFile } from "node:fs/promises";
import { join } from "node:path";
import { createTestDirectory } from "./helpers/owned-temp.mjs";

class FakeClock {
  time = 0;
  pending = new Set();
  pauses = new Map();
  now = () => this.time;
  wait = (ms, signal) => new Promise((resolve, reject) => {
    if (signal?.aborted) { reject(new Error("aborted")); return; }
    const row = { at: this.time + Math.max(0, ms), finish: null };
    const abort = () => { this.pending.delete(row); reject(new Error("aborted")); };
    row.finish = () => {
      this.pending.delete(row); signal?.removeEventListener("abort", abort); resolve();
    };
    signal?.addEventListener("abort", abort, { once: true });
    this.pending.add(row);
  });
  async drive(promise) {
    let done = false, result, error;
    promise.then(value => { result = value; done = true; }, value => { error = value; done = true; });
    for (let turns = 0; turns < 1000 && !done; turns++) {
      // Drain promise continuations before moving monotonic time to the next event.
      for (let i = 0; i < 40; i++) await Promise.resolve();
      if (done) break;
      assert.ok(this.pending.size, "scheduler must either finish or have an outstanding timer");
      const next = Math.min(...[...this.pending].map(row => row.at));
      this.time = next + (this.pauses.get(next) || 0);
      this.pauses.delete(next);
      for (const row of [...this.pending]) if (row.at <= this.time) row.finish();
    }
    assert.equal(done, true, "scheduler should settle within the fake clock turn bound");
    if (error) throw error;
    assert.equal(this.pending.size, 0, "all timers must be settled or cancelled");
    return result;
  }
}

test("viewer profiles are fixed and cannot expand or replace legacy bounds", () => {
  for (const viewers of [30, 50]) {
    const profile = validateViewerWorkload({ viewers });
    assert.equal(profile.expected_load_requests, viewers * 12);
    assert.equal(profile.expected_load_body_bytes, viewers * 12 * 32768);
    assert.equal(profile.last_scheduled_start_ms, 25000);
    assert.equal(profile.scheduled_window_ms, 30000);
    assert.equal(profile.max_start_lateness_ms, 500);
    assert.ok(profile.expected_load_body_bytes <= 64 * 1024 * 1024);
  }
  for (const input of [{}, null, [], { viewers: "30" }, { viewers: true }, { viewers: 16 },
    { viewers: 51 }, { viewers: 30, origin: "https://example.test" },
    { viewers: 30, token: "existing" }, { viewers: 30, interval_ms: 1 },
    { viewers: 30, payload_bytes: 1024 }, { viewers: 30, polls: 7 }]) {
    assert.throws(() => validateViewerWorkload(input), /invalid_viewer_workload/);
  }
  assert.throws(() => validateWorkload({ concurrency: 17 }), /invalid_workload/);
  assert.equal(validateWorkload({ concurrency: 16 }).concurrency, 16);
  assert.equal(Object.isFrozen(VIEWER_POLICY), true);
});

for (const viewers of [30, 50]) test("fixed " + viewers + "-viewer profile sends exactly two ordered reads per slot", async () => {
  const clock = new FakeClock();
  const active = Array(viewers).fill(0);
  const sequences = Array.from({ length: viewers }, () => []);
  const report = await clock.drive(runViewerSchedule({ viewers }, async (viewer, object, signal) => {
    active[viewer]++;
    assert.equal(active[viewer], 1, "a viewer must never overlap its reads or polls");
    sequences[viewer].push(object);
    await clock.wait(20, signal);
    active[viewer]--;
  }, { clock }));
  assert.equal(report.passed, true);
  assert.deepEqual(report.request_counts, {
    planned: viewers * 12, started: viewers * 12, succeeded: viewers * 12,
    failed: 0, cancelled: 0, not_started: 0,
  });
  assert.equal(report.completed_polls, viewers * 6);
  assert.equal(report.maximum_in_flight, viewers);
  assert.equal(report.in_flight_at_finish, 0);
  assert.equal(report.elapsed_ms, 25040, "six slots do not imply a full 30-second observed duration");
  assert.equal(report.maximum_start_lateness_ms, 0);
  for (const sequence of sequences) assert.deepEqual(sequence, [0, 1, 0, 1, 0, 1, 0, 1, 0, 1, 0, 1]);
  assert.deepEqual(report.polls.filter(row => row.viewer === 0).map(row => row.started_offset_ms),
    [0, 5000, 10000, 15000, 20000, 25000]);
});

test("500ms lateness is recorded without drifting later slots; 501ms fails without catch-up", async () => {
  for (const [pause, passes] of [[500, true], [501, false]]) {
    const clock = new FakeClock(); clock.pauses.set(5000, pause);
    let reads = 0;
    const report = await clock.drive(runViewerSchedule({ viewers: 30 }, async () => { reads++; }, { clock }));
    assert.equal(report.passed, passes);
    assert.equal(report.maximum_start_lateness_ms, pause);
    if (passes) {
      assert.equal(reads, 360);
      const rows = report.polls.filter(row => row.viewer === 0);
      assert.equal(rows[1].started_offset_ms, 5500);
      assert.equal(rows[2].started_offset_ms, 10000);
    } else {
      assert.equal(report.failure, "start_late");
      assert.equal(reads, 60, "only the completed first slot may have issued requests");
      assert.equal(report.request_counts.not_started, 300);
    }
  }
});

test("a poll crossing its fixed boundary cancels admitted reads and never catches up", async () => {
  const clock = new FakeClock();
  const objects = [];
  const report = await clock.drive(runViewerSchedule({ viewers: 30 }, async (viewer, object, signal) => {
    objects.push(object);
    await clock.wait(6000, signal);
  }, { clock }));
  assert.equal(report.passed, false);
  assert.equal(report.failure, "poll_overrun");
  assert.equal(report.elapsed_ms, 5000);
  assert.equal(report.request_counts.started, 30);
  assert.equal(report.request_counts.cancelled, 30);
  assert.equal(report.request_counts.not_started, 330);
  assert.equal(report.in_flight_at_finish, 0);
  assert.ok(objects.every(object => object === 0), "second reads must not be admitted");
});

for (const failedObject of [0, 1]) test("read " + failedObject + " failure stops later reads and preserves accounting", async () => {
  const clock = new FakeClock();
  const observed = [];
  const report = await clock.drive(runViewerSchedule({ viewers: 30 }, async (viewer, object, signal) => {
    observed.push([viewer, object]);
    if (viewer === 0 && object === failedObject) throw new Error("read_integrity");
    await clock.wait(10, signal);
  }, { clock }));
  assert.equal(report.passed, false);
  assert.equal(report.failure, "read_integrity");
  assert.equal(report.request_counts.failed, 1);
  assert.equal(report.request_counts.started, report.request_counts.succeeded +
    report.request_counts.failed + report.request_counts.cancelled);
  assert.equal(report.request_counts.planned, report.request_counts.started + report.request_counts.not_started);
  assert.equal(report.in_flight_at_finish, 0);
  assert.ok(observed.filter(([viewer]) => viewer === 0).every(([, object]) => object <= failedObject));
  assert.ok(report.polls.filter(row => row.slot > 0).every(row => row.state === "not_started"));
});

test("an already-aborted run admits no request and records every planned read as unstarted", async () => {
  const controller = new AbortController(); controller.abort();
  const clock = new FakeClock();
  const report = await clock.drive(runViewerSchedule({ viewers: 30 }, () => {
    assert.fail("read must not be called");
  }, { signal: controller.signal, clock }));
  assert.equal(report.failure, "aborted");
  assert.equal(report.request_counts.started, 0);
  assert.equal(report.request_counts.not_started, 360);
});

test("viewer CLI rejects existing or invalid output and forbidden flags before starting a runtime", { timeout: 2000 }, async (t) => {
  const dir = await createTestDirectory(t);
  const path = join(dir, "receipt.json");
  await writeFile(path, "keep");
  const messages = []; const original = process.stderr.write;
  process.stderr.write = chunk => { messages.push(String(chunk)); return true; };
  try {
    for (const args of [
      ["--mode", "viewer-polling", "--viewers", "30", "--output", path],
      ["--mode", "viewer-polling", "--viewers", "50", "--output", join(dir, "missing", "receipt.json")],
      ["--mode", "viewer-polling", "--viewers", "30", "--concurrency", "30"],
      ["--mode", "viewer-polling", "--viewers", "50", "--bytes", "32768"],
      ["--mode", "viewer-polling", "--viewers", "30", "--origin", "https://example.test"],
      ["--mode", "viewer-polling", "--viewers", "30", "--token", "existing"],
    ]) assert.equal(await main(args), 2);
  } finally { process.stderr.write = original; }
  assert.equal(await readFile(path, "utf8"), "keep");
  assert.equal(messages.length, 6);
});
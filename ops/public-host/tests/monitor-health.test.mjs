import test from "node:test";
import assert from "node:assert/strict";
import { createHash } from "node:crypto";
import { validateConfig, configFingerprint, probe, initialState, advanceState, validateState } from "../monitor.mjs";
import { classifyEvent } from "../alerts.mjs";

const NOW = Date.parse("2026-10-18T07:00:00Z");
const ISO = new Date(NOW).toISOString();
const baseConfig = () => ({ schema: "pitcheezy-host-monitor-v1", origin: "https://synthetic.example.test",
  allow_loopback_http: false, timeout_ms: 200, max_body_bytes: 32768, timestamp_pointer: "/published_at",
  timestamp_format: "rfc3339", max_age_seconds: 120, clock_skew_seconds: 30, page_sha256: null });
const config = (extra = {}) => ({ ...baseConfig(), health_contract: "pitcheezy-publish-health-v1", active_game_ids: [123], ...extra });
const game = (extra = {}) => ({ checked_at: ISO, sequence_checked: 20, file_sequence: 7, feed_ok: true, ...extra });
const body = (extra = {}) => ({ schema: "pitcheezy-publish-health-v1", published_at: ISO, sequence: 20,
  game_checks: { "123": game() }, ...extra });
async function run(document = body(), c = config(), options = {}) {
  const calls = [];
  const result = await probe(c, { now: () => NOW, fetchImpl: async (url, init) => {
    calls.push([new URL(url).pathname, init.method]);
    if (url.endsWith("/v1/health.json")) return new Response(JSON.stringify(document), { headers: {
      "Content-Type": "application/json", Date: new Date(NOW).toUTCString(), Age: "0", ...options.headers } });
    return new Response("<!doctype html><html><title>synthetic</title></html>", {
      status: options.pageStatus || 200, headers: { "Content-Type": "text/html" } });
  } });
  assert.deepEqual(calls.sort(), [["/", "GET"], ["/v1/health.json", "GET"]]);
  return result;
}
const checkBody = patch => body({ game_checks: { "123": game(patch) } });
const event = issues => ({ id: "a".repeat(64), kind: "opened", at_ms: NOW, issues });

test("optional config preserves existing config bytes, fingerprint and timestamp-only semantics", async () => {
  const c = baseConfig(), before = JSON.stringify(c);
  const expected = createHash("sha256").update(JSON.stringify(Object.fromEntries(
    Object.entries(c).sort(([a], [b]) => a.localeCompare(b))))).digest("hex");
  validateConfig(c);
  assert.equal(JSON.stringify(c), before);
  assert.equal(configFingerprint(c), expected);
  const result = await run(body({ game_checks: { "123": game({ feed_ok: false }) } }), c);
  assert.equal(result.status, "available");
  assert.equal(result.semantic_health, "unmeasured");
  assert.equal(Object.hasOwn(result.health, "publisher"), false);
});

test("contract selection requires explicit bounded unique active IDs and top health clock before I/O", async () => {
  const malformed = [ { health_contract: "other" }, { health_contract: null }, { timestamp_pointer: null },
    { timestamp_pointer: "/publish/published_at" }, { active_game_ids: null }, { active_game_ids: [123, 123] },
    { active_game_ids: [0] }, { active_game_ids: [true] }, { active_game_ids: ["123"] },
    { active_game_ids: [1e12] }, { active_game_ids: Array.from({ length: 33 }, (_, i) => i + 1) } ];
  for (const value of malformed) await assert.rejects(probe(config(value), { fetchImpl: () => assert.fail("network") }));
  for (const key of ["active_game_ids", "health_contract"]) {
    const c = config(); delete c[key];
    await assert.rejects(probe(c, { fetchImpl: () => assert.fail("network") }));
  }
  assert.doesNotThrow(() => validateConfig(config({ active_game_ids: [] })));
  assert.throws(() => validateState(initialState(baseConfig()), config()), { code: "config_changed_use_new_state" });
});

test("fresh checks accept unchanged game file sequence and ignore unknown reason/fields", async () => {
  for (const reason of ["held_last_accepted", "future_reason_without_allowlist"]) {
    const document = body({ receipt: { reason }, unknown_future_key: true });
    document.game_checks[123].future_field = "accepted";
    const result = await run(document);
    assert.equal(result.status, "available");
    assert.equal(result.semantic_health, "publisher_checks_passed");
    assert.equal(result.health.publisher.games[0].file_sequence, 7);
    assert.equal(result.health.publisher.games[0].sequence_checked, 20);
    assert.equal(result.javascript_execution, "unmeasured");
    assert.doesNotMatch(JSON.stringify(result), /future_reason|synthetic\.example/);
  }
});

test("active checked-at stale, missing, invalid and future are failures even with fresh global health", async () => {
  for (const [checked_at, expected] of [
    [new Date(NOW - 121000).toISOString(), "game_check_stale"], [undefined, "game_check_invalid"],
    ["not-time", "game_check_invalid"], [NOW, "game_check_invalid"],
    [new Date(NOW + 31000).toISOString(), "game_check_invalid"],
  ]) {
    const r = await run(checkBody({ checked_at }));
    assert.equal(r.health.freshness.status, "fresh"); assert.equal(r.status, "failed");
    assert.deepEqual(r.issues, [expected]);
  }
  assert.equal((await run(checkBody({ checked_at: new Date(NOW - 120000).toISOString() }))).status, "available");
});

test("feed failures and invalid sequence relationships have bounded publisher diagnostics", async () => {
  assert.deepEqual((await run(checkBody({ feed_ok: false }))).issues, ["game_check_feed_failed"]);
  for (const patch of [{ feed_ok: "false" }, { sequence_checked: true }, { sequence_checked: -1 },
    { sequence_checked: "20" }, { file_sequence: -1 }, { file_sequence: true }, { file_sequence: "7" },
    { file_sequence: 21 }, { sequence_checked: 21 }, { file_sequence: undefined }]) {
    const r = await run(checkBody(patch));
    assert.equal(r.status, "failed"); assert.deepEqual(r.issues, ["game_check_invalid"]);
  }
  for (const sequence of [true, -1, "20", Number.MAX_SAFE_INTEGER + 1]) {
    const r = await run(body({ sequence }));
    assert.equal(r.status, "failed"); assert.ok(r.issues.includes("health_contract_invalid"));
  }
});

test("missing optional game_checks or active row is unconfirmed, not invalid or green; no game GET", async () => {
  for (const doc of [body({ game_checks: undefined }), body({ game_checks: {} })]) {
    const result = await run(doc);
    assert.equal(result.status, "partial"); assert.deepEqual(result.issues, []);
    assert.equal(result.semantic_health, "publisher_checks_incomplete");
    assert.equal(result.health.publisher.games[0].code, "game_check_missing");
  }
  for (const game_checks of [null, [], false]) {
    const result = await run(body({ game_checks }));
    assert.equal(result.status, "failed"); assert.deepEqual(result.issues, ["health_contract_invalid"]);
  }
  const result = await run(body({ game_checks: { "123": null } }));
  assert.equal(result.status, "failed"); assert.deepEqual(result.issues, ["game_check_invalid"]);
});

test("null file sequence is a withdrawal, accepted by contract but not confirmed available", async () => {
  const r = await run(checkBody({ file_sequence: null }));
  assert.equal(r.status, "partial"); assert.deepEqual(r.issues, []);
  assert.equal(r.health.publisher.games[0].code, "game_file_withdrawn");
  assert.deepEqual((await run(checkBody({ file_sequence: null, feed_ok: false }))).issues, ["game_check_feed_failed"]);
});

test("inactive and final rows may stop; no active IDs still requires a fresh global heartbeat", async () => {
  const doc = body({ game_checks: { "123": game(), "456": game({ checked_at: "2020-01-01T00:00:00Z", feed_ok: false }),
    "789": { malformed_old_entry: true } } });
  assert.equal((await run(doc)).status, "available");
  assert.equal((await run(body({ game_checks: undefined }), config({ active_game_ids: [] }))).status, "available");
  const stale = await run(body({ published_at: "2020-01-01T00:00:00Z", game_checks: undefined }), config({ active_game_ids: [] }));
  assert.equal(stale.status, "failed"); assert.deepEqual(stale.issues, ["freshness_stale"]);
  assert.equal(stale.semantic_health, "publisher_checks_failed");
  assert.equal((await run(body({ schema: "other" }), config({ active_game_ids: [] }))).status, "failed");
});

test("all game failures deduplicate into fixed categories and fit monitor and alert state bounds", async () => {
  const ids = Array.from({ length: 32 }, (_, i) => i + 1);
  const checks = Object.fromEntries(ids.map((id, i) => [id, i % 2 ? game({ checked_at: "2020-01-01T00:00:00Z", feed_ok: false }) : game({ file_sequence: 99 })]));
  const c = config({ active_game_ids: ids });
  const result = await run(body({ schema: "other", published_at: "2020-01-01T00:00:00Z", game_checks: checks }), c,
    { pageStatus: 500, headers: { Age: "bad" } });
  assert.equal(result.issues.length, 7);
  assert.equal(new Set(result.issues).size, result.issues.length);
  assert.equal(classifyEvent(event(result.issues)), "unclassified");
  let state = initialState(c);
  for (const offset of [0, 1]) state = advanceState(state, { ...result, observed_at_ms: NOW + offset }, c).state;
  assert.doesNotThrow(() => validateState(state, c));
});

test("new publisher issues route to Song; a hosting issue routes both", () => {
  for (const issue of ["health_contract_invalid", "game_check_invalid", "game_check_stale", "game_check_feed_failed"]) {
    assert.equal(classifyEvent(event([issue])), "publish_stalled");
    assert.equal(classifyEvent(event([issue, "health_http_error"])), "unclassified");
  }
});

test("unconfirmed active evidence cannot close incidents and breaks consecutive recovery counts", async () => {
  const c = config(), bad = await run(checkBody({ feed_ok: false }), c), good = await run(body(), c);
  const partial = await run(body({ game_checks: {} }), c);
  let state = initialState(c), tick = NOW;
  const step = r => { const v = advanceState(state, { ...r, observed_at_ms: tick++ }, c); state = v.state; return v; };
  assert.equal(step(bad).event, null); assert.equal(step(bad).event.kind, "opened");
  step(good); step(partial); step(partial);
  assert.notEqual(state.incident, null); assert.equal(state.successes, 0);
  assert.equal(step(good).event, null); assert.equal(step(good).event.kind, "recovered");
  const changed = config({ active_game_ids: [] });
  assert.throws(() => validateState(state, changed), { code: "config_changed_use_new_state" });
});

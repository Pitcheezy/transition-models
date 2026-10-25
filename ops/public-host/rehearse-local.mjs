/** Bounded closed-loop and fixed viewer-polling rehearsals. Not a public CDN capacity measurement. */
import { readFile, writeFile, lstat, stat } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { resolve, dirname } from "node:path";
import { parseArgs } from "node:util";
import { createRequire } from "node:module";
import { startLocalHost, fixtureHtml, hash, boundedCleanup } from "./rehearsal/local-host.mjs";
import { probe, initialState, advanceState } from "./monitor.mjs";
import { validateViewerWorkload, runViewerSchedule } from "./rehearsal/viewer-polling.mjs";
const require = createRequire(import.meta.url);
const int = (v, a, b) => Number.isInteger(v) && v >= a && v <= b;
function need(value, code) { if (!value) throw new Error(code); }

export function validateWorkload(options = {}) {
  const value = { requests: 120, concurrency: 6, payload_bytes: 32768, ...options };
  need(Object.keys(value).sort().join(",") === "concurrency,payload_bytes,requests", "invalid_workload");
  need(int(value.requests, 1, 1000) && int(value.concurrency, 1, 16) &&
    int(value.payload_bytes, 256, 1048576) && value.requests * value.payload_bytes <= 64 * 1024 * 1024,
  "invalid_workload");
  return value;
}
export function syntheticBody(bytes, version = 1) {
  const base = JSON.stringify({ synthetic: true, synthetic_version: version, padding: "" });
  return JSON.stringify({ synthetic: true, synthetic_version: version,
    padding: "x".repeat(bytes - Buffer.byteLength(base)) });
}
export function summarizeLoad(samples, failures, elapsed, maximumInFlight, options) {
  const sorted = [...samples].sort((a, b) => a - b);
  const percentile = q => sorted.length ? Math.round(sorted[Math.ceil(sorted.length * q) - 1] * 100) / 100 : null;
  return { ...options, attempted: samples.length + failures.length, successful: samples.length,
    failed: failures.length, failure_codes: [...new Set(failures)].sort(),
    elapsed_ms: Math.round(elapsed * 100) / 100, maximum_in_flight: maximumInFlight,
    p50_ms: percentile(0.5), p95_ms: percentile(0.95), max_ms: percentile(1),
    observed_requests_per_second: elapsed > 0 ? Math.round(samples.length / elapsed * 100000) / 100 : null,
    latency_scope: "loopback request start through body receipt and SHA verification",
    workload: "closed-loop synthetic, no user think time" };
}
export async function checkRead(response, expected, bytes) {
  need(response.status === 200, "read_status");
  const body = new Uint8Array(await response.arrayBuffer());
  need(body.byteLength === bytes && hash(body) === expected, "read_integrity");
  need(Number.isFinite(Date.parse(response.headers.get("Date"))), "read_date");
  need(response.headers.get("Age") === "0", "read_age");
  need((response.headers.get("Cache-Control") || "").toLowerCase().split(",").map(v => v.trim()).includes("no-store"), "read_cache");
}
async function sourceReceipt() {
  const files = ["worker.mjs", "gateway.mjs", "telemetry.mjs", "notice.mjs", "access.mjs", "monitor.mjs",
    "rehearsal/local-host.mjs", "rehearsal/viewer-polling.mjs", "rehearse-local.mjs", "package-lock.json"];
  const values = {};
  for (const name of files) values[name] = hash(await readFile(new URL(name, import.meta.url)));
  return values;
}
export async function runLocalRehearsal(input = {}) {
  const options = validateWorkload(input);
  const controller = new AbortController();
  const deadline = setTimeout(() => controller.abort(), 90000);
  const start = performance.now();
  let host, phase = "start", report;
  const completed = [];
  const safeCodes = new Set(["read_status", "read_integrity", "read_date", "read_age", "read_cache"]);
  const codeOf = error => safeCodes.has(error.message) ? error.message : controller.signal.aborted ? "deadline" : "request_failed";
  try {
    report = { schema: "pitcheezy-local-host-rehearsal-v1", target: "ephemeral-loopback-miniflare",
      synthetic: true, public_capacity_verified: false, song_contract_verified: false,
      environment: { node: process.version, platform: process.platform, arch: process.arch,
        miniflare: require("miniflare/package.json").version },
      source_sha256: await sourceReceipt(), options, completed_phases: completed, load: null, passed: false };
    host = await startLocalHost({ signal: controller.signal });
    report.startup_ms = Math.round(performance.now() - start);
    const get = (path, init = {}) => fetch(host.origin + path, { ...init, redirect: "error",
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(5000)]), cache: "no-store" });
    const consumeWrite = async response => {
      need(response.status === 200, "write_failed");
      const tag = response.headers.get("ETag");
      await response.arrayBuffer();
      need(/^"[a-f0-9]{32}"$/.test(tag || ""), "write_etag");
      return tag;
    };
    const game = "/v1/game/123.json", health = "/v1/health.json";
    const body = syntheticBody(options.payload_bytes);
    const expected = hash(body);
    let gameTag = await consumeWrite(await host.publish(game, body));
    const healthBody = at => JSON.stringify({ synthetic: true, synthetic_publish: { at } });
    let healthTag = await consumeWrite(await host.publish(health, healthBody(new Date().toISOString())));
    phase = "warmup";
    await checkRead(await get(game), expected, options.payload_bytes);
    completed.push("warmup");

    phase = "read_load";
    let next = 0, inFlight = 0, maximumInFlight = 0;
    const samples = [], failures = [];
    const begin = performance.now();
    await Promise.all(Array.from({ length: Math.min(options.concurrency, options.requests) }, async () => {
      while (next < options.requests && !controller.signal.aborted) {
        next++; inFlight++; maximumInFlight = Math.max(maximumInFlight, inFlight);
        const time = performance.now();
        try {
          await checkRead(await get(game), expected, options.payload_bytes);
          samples.push(performance.now() - time);
        } catch (error) { failures.push(codeOf(error)); }
        finally { inFlight--; }
      }
    }));
    report.load = summarizeLoad(samples, failures, performance.now() - begin, maximumInFlight, options);
    need(samples.length === options.requests && failures.length === 0, "load_failed");
    completed.push("read_load");

    phase = "concurrent_conflict";
    const attempts = await Promise.all([
      host.publish(game, syntheticBody(options.payload_bytes, 2), gameTag),
      host.publish(game, syntheticBody(options.payload_bytes, 3), gameTag),
    ]);
    need(attempts.map(x => x.status).sort().join(",") === "200,412", "conflict_failed");
    for (const response of attempts) await response.arrayBuffer();
    const current = await get(game);
    gameTag = current.headers.get("ETag");
    const currentBody = await current.text();
    need([2, 3].includes(JSON.parse(currentBody).synthetic_version), "conflict_content");
    completed.push("concurrent_conflict");

    phase = "withdraw_restore";
    const tombstone = await consumeWrite(await host.withdraw(game, gameTag));
    for (const method of ["GET", "HEAD"]) {
      const missing = await get(game, { method });
      need(missing.status === 404, "withdraw_failed"); await missing.arrayBuffer();
    }
    const restoredTag = await consumeWrite(await host.publish(game, currentBody, tombstone));
    need(restoredTag !== gameTag, "aba_etag");
    await checkRead(await get(game), hash(currentBody), options.payload_bytes);
    const oldDelete = await host.withdraw(game, gameTag);
    need(oldDelete.status === 412, "stale_withdraw_accepted"); await oldDelete.arrayBuffer();
    completed.push("withdraw_restore");

    phase = "freshness_incident";
    const config = { schema: "pitcheezy-host-monitor-v1", origin: host.origin, allow_loopback_http: true,
      timeout_ms: 5000, max_body_bytes: 1048576, timestamp_pointer: "/synthetic_publish/at",
      timestamp_format: "rfc3339", max_age_seconds: 120, clock_skew_seconds: 30, page_sha256: hash(fixtureHtml) };
    let state = initialState(config);
    const observations = [];
    const observe = async () => {
      need(!controller.signal.aborted, "deadline");
      const p = await probe(config);
      // Actual loopback requests; no fabricated monitor timestamps.
      const advanced = advanceState(state, p, config);
      state = advanced.state;
      const result = { status: p.status, freshness: p.health.freshness?.status ?? null,
        incident_open: state.incident !== null, event: advanced.event?.kind ?? null };
      observations.push(result); return result;
    };
    need((await observe()).status === "available", "initial_probe");
    healthTag = await consumeWrite(await host.publish(health,
      healthBody(new Date(Date.now() - 300000).toISOString()), healthTag));
    need((await observe()).incident_open === false, "early_incident");
    need((await observe()).event === "opened", "incident_missing");
    await consumeWrite(await host.publish(health, healthBody(new Date().toISOString()), healthTag));
    need((await observe()).incident_open === true, "early_recovery");
    need((await observe()).event === "recovered", "recovery_missing");
    report.monitor_observations = observations;
    completed.push("freshness_incident");
    report.passed = true;
  } catch (error) {
    report ??= { schema: "pitcheezy-local-host-rehearsal-v1", synthetic: true, passed: false };
    if (error.cleanup) report.cleanup = error.cleanup;
    report.failure = { phase, code: controller.signal.aborted ? "deadline" : "phase_failed" };
  } finally {
    controller.abort(); clearTimeout(deadline);
    if (host) report.cleanup = await boundedCleanup(() => host.dispose());
    if (report?.cleanup && report.cleanup.status !== "complete") {
      report.passed = false;
      report.failure = { phase: "cleanup", code: report.cleanup.code };
    }
  }
  report.total_ms = Math.round(performance.now() - start);
  return report;
}

/** Authenticated, fixed-schedule synthetic viewers on a new local R2 only. */
export async function runViewerPollingRehearsal(input) {
  const options = validateViewerWorkload(input);
  const controller = new AbortController();
  const deadline = setTimeout(() => controller.abort(), 90000);
  const begin = performance.now();
  const cookies = [], nonces = new Set();
  let host, report, phase = "start";
  const preparation = [];
  try {
    report = { schema: "pitcheezy-local-viewer-polling-v1", target: "ephemeral-loopback-miniflare",
      synthetic: true, public_capacity_verified: false, song_contract_verified: false,
      real_health_contract_verified: false, browser_rendering_verified: false,
      environment: { node: process.version, platform: process.platform, arch: process.arch,
        miniflare: require("miniflare/package.json").version },
      source_sha256: await sourceReceipt(), options, preparation_requests: preparation,
      sessions: { created: 0, unique_random_nonces: false, minimum_remaining_ms: null },
      access_gate_enabled: true, load: null, schedule: null, passed: false };
    host = await startLocalHost({ signal: controller.signal, access: {} });
    report.startup_ms = Math.round(performance.now() - begin);
    const get = (path, init = {}, signal = controller.signal) => fetch(host.origin + path, {
      ...init, redirect: "error", cache: "no-store",
      signal: AbortSignal.any([controller.signal, signal, AbortSignal.timeout(5000)]),
    });
    const prepare = async (kind, method, path, action) => {
      controller.signal.throwIfAborted();
      const row = { kind, method, path, status: null };
      preparation.push(row);
      const response = await action();
      row.status = response.status;
      return response;
    };
    phase = "access_check";
    const denied = await prepare("access_check", "GET", "/v1/game/123.json",
      () => get("/v1/game/123.json"));
    need(denied.status === 401 && denied.headers.get("X-Pitcheezy-Access") === "required", "access_not_gated");
    await denied.arrayBuffer();

    phase = "viewer_login";
    let minimumRemaining = Infinity;
    for (let viewer = 0; viewer < options.viewers; viewer++) {
      const response = await prepare("login", "POST", "/_access/v1/session",
        () => get("/_access/v1/session", { method: "POST",
          headers: { "Content-Type": "application/json" },
          body: JSON.stringify({ code: host.accessCodes[0] }) }));
      need(response.status === 200, "viewer_login_failed");
      const cookie = (response.headers.get("Set-Cookie") || "").split(";")[0];
      const parts = cookie.slice(cookie.indexOf("=") + 1).split(".");
      need(cookie.startsWith("pz_viewer=v3.") && parts.length === 6 &&
        /^[a-f0-9]{16}$/.test(parts[4]) && !nonces.has(parts[4]), "viewer_session_not_unique");
      const body = await response.json();
      const remaining = Date.parse(body.expires_at) - Date.now();
      need(body.authenticated === true && remaining > 90000, "viewer_session_too_short");
      cookies.push(cookie); nonces.add(parts[4]); minimumRemaining = Math.min(minimumRemaining, remaining);
    }
    report.sessions = { created: cookies.length, unique_random_nonces: nonces.size === options.viewers,
      minimum_remaining_ms: Math.floor(minimumRemaining) };

    phase = "publish_fixtures";
    const fixtures = [
      { path: "/v1/game/123.json", body: syntheticBody(options.payload_bytes, 1) },
      { path: "/v1/health.json", body: syntheticBody(options.payload_bytes, 2) },
    ].map(item => ({ ...item, bytes: Buffer.byteLength(item.body), sha256: hash(item.body) }));
    report.fixtures = fixtures.map(({ path, bytes, sha256 }) => ({ path, bytes, sha256 }));
    for (const fixture of fixtures) {
      const response = await prepare("publish", "PUT", "/_publish" + fixture.path,
        () => host.publish(fixture.path, fixture.body));
      need(response.status === 200 && /^"[a-f0-9]{32}"$/.test(response.headers.get("ETag") || ""), "fixture_publish_failed");
      await response.arrayBuffer();
    }
    phase = "warmup";
    for (const fixture of fixtures) {
      const response = await prepare("warmup", "GET", fixture.path,
        () => get(fixture.path, { headers: { Cookie: cookies[0] } }));
      await checkRead(response, fixture.sha256, fixture.bytes);
    }

    phase = "viewer_polling";
    const schedule = await runViewerSchedule(input, async (viewer, object, signal) => {
      const fixture = fixtures[object];
      await checkRead(await get(fixture.path, { headers: { Cookie: cookies[viewer] } }, signal),
        fixture.sha256, fixture.bytes);
    }, { signal: controller.signal });
    const { samples_ms, failure_codes, ...safeSchedule } = schedule;
    report.schedule = safeSchedule;
    report.load = { ...summarizeLoad(samples_ms, failure_codes, schedule.elapsed_ms,
      schedule.maximum_in_flight, options),
      workload: "fixed 5-second slots; two sequential reads per authenticated synthetic viewer",
      latency_scope: "loopback GET start through full body receipt and SHA/header verification",
      expected_load_requests: options.expected_load_requests };
    report.passed = schedule.passed;
    if (!schedule.passed) report.failure = { phase,
      code: controller.signal.aborted ? "deadline" : schedule.failure || "polling_failed" };
  } catch (error) {
    report ??= { schema: "pitcheezy-local-viewer-polling-v1", synthetic: true, passed: false,
      preparation_requests: preparation };
    if (error.cleanup) report.cleanup = error.cleanup;
    report.failure = { phase, code: controller.signal.aborted ? "deadline" : "phase_failed" };
  } finally {
    controller.abort(); clearTimeout(deadline);
    cookies.fill(""); nonces.clear();
    if (host) report.cleanup = await boundedCleanup(() => host.dispose());
    if (report.cleanup && report.cleanup.status !== "complete") {
      report.passed = false; report.failure = { phase: "cleanup", code: report.cleanup.code };
    }
  }
  report.request_accounting = {
    preparation_started: preparation.length,
    preparation_by_kind: Object.fromEntries(["access_check", "login", "publish", "warmup"].map(kind =>
      [kind, preparation.filter(row => row.kind === kind).length])),
    load_started: report.schedule?.request_counts.started ?? 0,
    total_runtime_entry_started: preparation.length + (report.schedule?.request_counts.started ?? 0),
    automatic_retries: 0, redirects_followed: 0,
    scope: "script requests to the temporary runtime entry; excludes Miniflare internal operations",
  };
  report.total_ms = Math.round(performance.now() - begin);
  return report;
}

async function preflightOutput(path) {
  if (!path) return;
  const exists = await lstat(path).then(() => true, error => {
    if (error.code === "ENOENT") return false;
    throw error;
  });
  need(!exists, "output_exists");
  need((await stat(dirname(resolve(path)))).isDirectory(), "output_parent_required");
}
export async function main(args) {
  try {
    const { values } = parseArgs({ args, options: {
      mode: { type: "string" }, viewers: { type: "string" },
      requests: { type: "string" }, concurrency: { type: "string" }, bytes: { type: "string" },
      output: { type: "string" },
    } });
    const mode = values.mode ?? "closed-loop";
    let input;
    if (mode === "viewer-polling") {
      need(values.requests === undefined && values.concurrency === undefined && values.bytes === undefined &&
        /^(30|50)$/.test(values.viewers || ""), "invalid_viewer_workload");
      input = { viewers: Number(values.viewers) };
      validateViewerWorkload(input);
    } else {
      need(mode === "closed-loop" && values.viewers === undefined, "invalid_workload");
      input = {};
      for (const [flag, key] of [["requests", "requests"], ["concurrency", "concurrency"], ["bytes", "payload_bytes"]]) {
        if (values[flag] !== undefined) {
          need(/^[1-9][0-9]*$/.test(values[flag]), "invalid_workload");
          input[key] = Number(values[flag]);
        }
      }
      validateWorkload(input);
    }
    await preflightOutput(values.output);
    const report = mode === "viewer-polling" ? await runViewerPollingRehearsal(input) : await runLocalRehearsal(input);
    const text = JSON.stringify(report, null, 2) + "\n";
    if (values.output) await writeFile(values.output, text, { flag: "wx", mode: 0o600 });
    process.stdout.write(text);
    return report.passed ? 0 : 1;
  } catch { process.stderr.write('{"ok":false,"code":"rehearsal_arguments_or_output_error"}\n'); return 2; }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await main(process.argv.slice(2));
}

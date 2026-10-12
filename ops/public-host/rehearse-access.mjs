/** Local viewer access-gate rehearsal (WS-access1). Ephemeral loopback Miniflare only; codes never leave the process. */
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { resolve } from "node:path";
import { parseArgs } from "node:util";
import { createRequire } from "node:module";
import { startLocalHost, hash, boundedCleanup } from "./rehearsal/local-host.mjs";
import { probe } from "./monitor.mjs";
const require = createRequire(import.meta.url);
function need(value, code) { if (!value) throw new Error(code); }

async function sourceReceipt() {
  const files = ["worker.mjs", "gateway.mjs", "access.mjs", "notice.mjs", "monitor.mjs", "telemetry.mjs",
    "rehearsal/local-host.mjs", "rehearse-access.mjs", "package-lock.json"];
  const values = {};
  for (const name of files) values[name] = hash(await readFile(new URL(name, import.meta.url)));
  return values;
}

export async function runAccessRehearsal() {
  const controller = new AbortController();
  const deadline = setTimeout(() => controller.abort(), 60000);
  const start = performance.now();
  let host, phase = "start", report;
  const completed = [];
  try {
    report = { schema: "pitcheezy-local-access-rehearsal-v1", target: "ephemeral-loopback-miniflare",
      synthetic: true, real_viewer_codes: false, access_targets_decided: false, mlb_usage_permission: "not_implied",
      environment: { node: process.version, platform: process.platform, arch: process.arch,
        miniflare: require("miniflare/package.json").version },
      source_sha256: await sourceReceipt(), completed_phases: completed, passed: false,
      note: "Loopback http uses the unprefixed cookie without Secure; production https uses __Host- and Secure. Edge IP absent locally: shared limiter pool." };
    host = await startLocalHost({ signal: controller.signal, notice: true, access: { sessionSeconds: 2 } });
    report.startup_ms = Math.round(performance.now() - start);
    const get = (path, init = {}) => fetch(host.origin + path, { ...init, redirect: "manual",
      signal: AbortSignal.any([controller.signal, AbortSignal.timeout(5000)]), cache: "no-store" });
    const game = "/v1/game/123.json";
    const body = JSON.stringify({ synthetic: true, synthetic_version: 1 });
    const published = await host.publish(game, body);
    need(published.status === 200, "publish_failed"); await published.arrayBuffer();
    const matrix = async (cookie) => {
      const out = {};
      for (const [method, route] of [["GET", "/"], ["HEAD", "/"], ["GET", "/fixture.mjs"], ["GET", game], ["HEAD", game], ["GET", "/v1/health.json"], ["OPTIONS", game], ["POST", "/_telemetry/session"]]) {
        const init = { method, headers: { ...(cookie ? { Cookie: cookie } : {}), ...(method === "POST" ? { "Content-Type": "application/json" } : {}) }, ...(method === "POST" ? { body: "{}" } : {}) };
        const r = await get(route, init); const text = await r.text();
        out[method + " " + route] = { status: r.status, content_type: r.headers.get("Content-Type"), cache_control: r.headers.get("Cache-Control"),
          access: r.headers.get("X-Pitcheezy-Access"), vary: r.headers.get("Vary"), html: /<!doctype html>/i.test(text), body_bytes: Buffer.byteLength(text) };
      }
      return out;
    };
    phase = "locked";
    const locked = await matrix(null);
    for (const [k, v] of Object.entries(locked)) {
      if (k.startsWith("OPTIONS")) need(v.status === 204, "options_" + k);
      else need(v.status === 401 && v.access === "required" && v.cache_control === "no-store", "locked_" + k);
    }
    const upload = await host.publish("/v1/health.json", JSON.stringify({ synthetic: true, synthetic_publish: { at: new Date().toISOString() } }));
    need(upload.status === 200, "upload_blocked_by_gate"); await upload.arrayBuffer();
    const monitored = await probe({ schema: "pitcheezy-host-monitor-v1", origin: host.origin, allow_loopback_http: true, timeout_ms: 5000,
      max_body_bytes: 1048576, timestamp_pointer: "/synthetic_publish/at", timestamp_format: "rfc3339", max_age_seconds: 120, clock_skew_seconds: 30, page_sha256: null });
    need(monitored.status === "failed" && monitored.access_gate_active === true, "monitor_classification");
    report.locked = locked; report.upload_while_locked = "accepted";
    report.monitor_while_locked = { status: monitored.status, access_gate_active: monitored.access_gate_active, issues: monitored.issues };
    completed.push("locked");

    phase = "login";
    const wrong = await host.login("synthetic-wrong-code-000");
    need(wrong.status === 401 && wrong.headers.get("Set-Cookie") === null, "wrong_code"); await wrong.arrayBuffer();
    const t0 = performance.now();
    const opened = await host.login(host.accessCodes[0]);
    const loginMs = Math.round((performance.now() - t0) * 100) / 100;
    need(opened.status === 200, "login_failed"); await opened.arrayBuffer();
    const setCookie = opened.headers.get("Set-Cookie") || "";
    const cookie = setCookie.split(";")[0];
    need(/^pz_viewer=v1\./.test(cookie) && /HttpOnly/.test(setCookie) && /SameSite=Strict/.test(setCookie) && /Path=\//.test(setCookie), "cookie_attributes");
    const form = await host.login(host.accessCodes[0], { form: true });
    need(form.status === 303 && form.headers.get("Location") === "/", "form_redirect"); await form.arrayBuffer();
    report.login = { wrong_code_status: 401, json_login_ms: loginMs, cookie_attributes: setCookie.replace(/=v1\.[^;]+/, "=<redacted>"), form_login_status: 303 };
    completed.push("login");

    phase = "unlocked";
    const unlocked = await matrix(cookie);
    for (const [k, v] of Object.entries(unlocked)) {
      if (k.startsWith("OPTIONS")) need(v.status === 204, "options_" + k);
      else if (k.startsWith("POST")) need(v.status === 503, "telemetry_reached_" + k); // collection not configured locally
      else need(v.status === 200, "unlocked_" + k);
    }
    need(unlocked["GET /"].cache_control?.startsWith("private") && /Cookie/.test(unlocked["GET /"].vary || ""), "private_cache");
    const data = await get(game, { headers: { Cookie: cookie } });
    need(await data.text() === body, "data_bytes");
    report.unlocked = unlocked;
    completed.push("unlocked");

    phase = "logout_and_expiry";
    const logout = await get("/_access/v1/session", { method: "DELETE", headers: { Cookie: cookie } });
    need(logout.status === 204 && /Max-Age=0/.test(logout.headers.get("Set-Cookie") || ""), "logout"); await logout.arrayBuffer();
    const afterLogout = await get("/", { headers: { Cookie: cookie } });
    need(afterLogout.status === 200, "server_side_state_unexpected: stateless session still valid until expiry; client cleared the cookie");
    await afterLogout.arrayBuffer();
    const cleared = await get("/");
    need(cleared.status === 401, "cleared_cookie_still_open"); await cleared.arrayBuffer();
    const again = await host.login(host.accessCodes[0]);
    const shortCookie = (again.headers.get("Set-Cookie") || "").split(";")[0]; await again.arrayBuffer();
    need((await (await get("/", { headers: { Cookie: shortCookie } })).text()).length > 0, "short_session_open");
    await new Promise(r => setTimeout(r, 2300));
    const expired = await get("/", { headers: { Cookie: shortCookie } });
    need(expired.status === 401, "session_did_not_expire"); await expired.arrayBuffer();
    report.logout_and_expiry = { logout_status: 204, cookie_cleared_then_locked: true,
      stateless_note: "Logout clears the browser cookie; a copied cookie value stays valid until expiry or code/secret rotation.",
      session_seconds: 2, expired_after_wait_ms: 2300, expired_status: 401 };
    completed.push("logout_and_expiry");
    report.passed = true;
  } catch (error) {
    report ??= { schema: "pitcheezy-local-access-rehearsal-v1", synthetic: true, passed: false };
    if (error.cleanup) report.cleanup = error.cleanup;
    report.failure = { phase, code: controller.signal.aborted ? "deadline" : /^[a-z_/.0-9: -]+$/i.test(error.message) ? error.message : "phase_failed" };
  } finally {
    controller.abort(); clearTimeout(deadline);
    if (host) report.cleanup = await boundedCleanup(() => host.dispose());
    if (report?.cleanup && report.cleanup.status !== "complete") { report.passed = false; report.failure = { phase: "cleanup", code: report.cleanup.code }; }
  }
  report.total_ms = Math.round(performance.now() - start);
  return report;
}

export async function main(args) {
  try {
    const { values } = parseArgs({ args, options: { output: { type: "string" } } });
    const report = await runAccessRehearsal();
    const text = JSON.stringify(report, null, 2) + "\n";
    if (values.output) await writeFile(values.output, text, { flag: "wx", mode: 0o600 });
    process.stdout.write(text);
    return report.passed ? 0 : 1;
  } catch { process.stderr.write('{"ok":false,"code":"rehearsal_arguments_or_output_error"}\n'); return 2; }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await main(process.argv.slice(2));
}

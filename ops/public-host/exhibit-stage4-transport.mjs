/** Bounded stage4 service transport. Private metadata journals; no credentials or bodies are persisted. */
import { mkdir, open } from "node:fs/promises";
import { isAbsolute, join } from "node:path";
import { plainPath } from "./monitor-cli.mjs";
import { parseOrigin } from "./verify-exhibit-remote.mjs";

const UUID = /^[a-f0-9]{8}(?:-[a-f0-9]{4}){3}-[a-f0-9]{12}$/;
const RAY = /^[a-f0-9]{16,32}(?:-[A-Z0-9]{3,10})?$/i;
const METHODS = new Set(["GET", "HEAD", "POST", "PUT", "DELETE"]);
export class Stage4Error extends Error { constructor(code) { super(code); this.code = code; } }
const need = (ok, code) => { if (!ok) throw new Stage4Error(code); };
const safeCode = e => e instanceof Stage4Error ? e.code : "transport_or_journal_failed";
const utc = () => new Date().toISOString();
function safePath(path) {
  if (typeof path !== "string" || path.length > 300 || !/^\/[A-Za-z0-9_./-]*(?:\?(?:game=[1-9][0-9]{0,11}|date=\d{4}-\d{2}-\d{2}))?$/.test(path)) return false;
  return !path.split("?")[0].split("/").some(p => p === "." || p === "..");
}
async function writeExclusive(file, value) {
  const handle = await open(await plainPath(file), "wx", 0o600);
  try { await handle.writeFile(JSON.stringify(value, null, 2) + "\n", "utf8"); await handle.sync(); }
  finally { await handle.close(); }
}

/**
 * allowed: exact [{method,path}], including a fixed safe query where required.
 * fetch/cleanupFetch(url, init, {statuses?, redirectTo?}) return the Response, with body untouched.
 * A completed journal proves response headers only, not body validation or stored server logs.
 * reserve requests belong only to cleanupFetch; any normal failure halts subsequent normal sends.
 */
export async function createStage4Transport({ origin, outDir, limit, allowed, versionPin,
  fetchImpl = fetch, reserve = 1 } = {}) {
  let output;
  try {
    parseOrigin(origin);
    need(Number.isInteger(limit) && limit >= 1 && limit <= 1000 && Number.isInteger(reserve) && reserve >= 0 && reserve < limit, "budget_invalid");
    need(UUID.test(versionPin || "") && typeof fetchImpl === "function", "version_or_adapter_invalid");
    need(Array.isArray(allowed) && allowed.length > 0 && allowed.length <= 100, "allowlist_invalid");
    const keys = allowed.map(a => {
      need(a && Object.keys(a).sort().join(",") === "method,path" && METHODS.has(a.method) && safePath(a.path), "allowlist_invalid");
      return a.method + " " + a.path;
    });
    need(new Set(keys).size === keys.length, "duplicate_allowlist_entry");
    need(typeof outDir === "string" && isAbsolute(outDir), "absolute_output_required");
    output = await plainPath(outDir);
    await mkdir(output);
    await writeExclusive(join(output, "started.private.json"), {
      schema: "pitcheezy-stage4-transport-v1", started_utc: utc(), request_limit: limit, cleanup_reserve: reserve,
      expected_deployment_version: versionPin, version_basis: "operator_management_pin_not_http_or_server_log_proof",
    });
    const permitted = new Set(keys);
    let issued = 0, attempted = 0, normal = 0, cleanup = 0, completed = 0, unknown = 0, halted = false, busy = false, failure = null;
    const halt = (code = "validation_failed") => { halted = true; failure ??= /^[a-z_]{1,64}$/.test(code) ? code : "validation_failed"; };
    const summary = () => ({ attempted_requests: attempted, completed_header_records: completed,
      normal_requests: normal, cleanup_requests: cleanup, request_limit: limit, cleanup_reserve: reserve,
      halted, failure, retries: 0, unknown_responses: unknown, pending_possible: attempted !== completed || unknown > 0 });
    const send = async (url, init = {}, expectation = {}, isCleanup = false) => {
      let row = null, prefix = null;
      try {
        need(!busy, "parallel_request_refused");
        need(isCleanup || !halted, "transport_halted");
        need(typeof url === "string" && url.startsWith(origin + "/"), "target_refused");
        const parsed = new URL(url), path = parsed.pathname + parsed.search;
        const method = init.method ?? "GET";
        need(parsed.origin === origin && !parsed.username && !parsed.password && !parsed.hash && url === origin + path && safePath(path), "target_refused");
        need(permitted.has(method + " " + path), "operation_refused");
        need(attempted < limit && (isCleanup ? cleanup < reserve : normal < limit - reserve), "request_budget_exhausted");
        need(expectation && Object.keys(expectation).every(k => ["statuses", "redirectTo"].includes(k)), "expectation_invalid");
        const statuses = expectation.statuses;
        need(statuses === undefined || (Array.isArray(statuses) && statuses.length > 0 && statuses.every(s => Number.isInteger(s) && s >= 100 && s <= 599)), "expectation_invalid");
        need(expectation.redirectTo === undefined || expectation.redirectTo === null || expectation.redirectTo === "/", "expectation_invalid");
        busy = true;
        const sequence = ++issued;
        prefix = join(output, `request-${String(sequence).padStart(3, "0")}`);
        row = { sequence, method, path, cleanup: isCleanup, started_utc: utc(), finished_utc: null,
          status: null, ray: null, outcome: "pending", expected_deployment_version: versionPin,
          version_basis: "operator_management_pin_not_http_or_server_log_proof" };
        await writeExclusive(prefix + ".started.private.json", row);
        attempted++; if (isCleanup) cleanup++; else normal++;
        let response;
        try {
          const timeout = AbortSignal.timeout(15000);
          response = await fetchImpl(url, { ...init, method, redirect: "manual", cache: "no-store", credentials: "omit",
            referrerPolicy: "no-referrer", signal: init.signal ? AbortSignal.any([init.signal, timeout]) : timeout });
          row.status = response.status;
          const ray = response.headers.get("CF-Ray");
          row.ray = RAY.test(ray || "") ? ray : null;
          row.finished_utc = utc();
          need(!response.redirected, "redirect_followed_refused");
          if (response.status >= 300 && response.status < 400)
            need(expectation.redirectTo === "/" && response.headers.get("Location") === "/", "redirect_refused");
          need(statuses === undefined || statuses.includes(response.status), "unexpected_status");
          row.outcome = "response_headers_received";
        } catch (error) {
          row.finished_utc = utc(); row.outcome = row.status === null ? "unknown" : "response_rejected"; if (row.status === null) unknown++;
          row.code = safeCode(error);
          if (response?.body) await response.body.cancel().catch(() => {});
          throw error;
        } finally {
          await writeExclusive(prefix + ".completed.private.json", row);
          completed++;
        }
        return response;
      } catch (error) { halt(safeCode(error)); throw new Stage4Error(safeCode(error)); }
      finally { if (row) busy = false; }
    };
    return { fetch: (url, init, expectation) => send(url, init, expectation, false),
      cleanupFetch: (url, init, expectation) => send(url, init, expectation, true), summary, halt };
  } catch (error) { throw new Stage4Error(safeCode(error)); }
}

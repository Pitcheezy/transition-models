/** Stage4 read acceptance only: 24 bounded service requests, with the final request reserved for logout. */
import { ACCESS_HEADER, ACCESS_ROUTE } from "./access.mjs";
import { classifySite, hash, validateIntakeReceipt } from "./exhibit-site.mjs";
import { verifyExhibitRemote } from "./verify-exhibit-remote.mjs";
import { createStage4Transport, Stage4Error } from "./exhibit-stage4-transport.mjs";

const SOURCE = "c47fe6cb78479362e7250141da946814cc33bd31";
const DATA_SOURCE = "cb1cfa8f759fd77adc75595316a389208c752dba";
const DATA = ["v1/setup/849843.json", "v1/game/849843.json", "v1/games/2026-09-30.json", "v1/dates.json", "v1/manifest.json", "v1/health.json"];
const ABSENT = ["/v1/game/999999.json", "/v1/game/849844.json", "/v1/setup/849844.json", "/v1/games/2026-10-01.json"];
const COOKIE = /^(__Host-)?pz_viewer=v3\.[1-9][0-9]{0,15}\.[1-9][0-9]{0,15}\.[a-f0-9]{64}\.[a-f0-9]{16}\.[a-f0-9]{64}$/;
const need = (ok, code) => { if (!ok) throw new Stage4Error(code); };
const codeOf = e => e instanceof Stage4Error ? e.code : "read_acceptance_failed";
const MIME = { html: /^text\/html\b/, svg: /^image\/svg\+xml\b/, js: /^(?:text|application)\/(?:x-)?(?:java|ecma)script\b/, css: /^text\/css\b/ };
async function boundedBytes(response, limit = 8 * 1024 * 1024) {
  if (!response.body) return Buffer.alloc(0);
  const reader = response.body.getReader(), chunks = []; let size = 0;
  try {
    while (true) {
      const { value, done } = await reader.read(); if (done) break;
      size += value.byteLength;
      if (size > limit) { await reader.cancel(); throw new Stage4Error("response_body_too_large"); }
      chunks.push(value);
    }
  } finally { reader.releaseLock(); }
  return Buffer.concat(chunks);
}
function checkedInputs(prepared, accessCode, collectionBytes) {
  try {
    const intake = structuredClone(validateIntakeReceipt(prepared?.intake));
    need(intake.profile === "exhibition-c47fe6cb" && intake.source_commit === SOURCE && intake.data_generation_commit === DATA_SOURCE,
      "candidate_provenance_mismatch");
    need(intake.catalogue.missing_date_files.length === 0 && intake.catalogue.advertised_dates === 1, "candidate_catalogue_mismatch");
    need(prepared.files instanceof Map && prepared.files.size === 10 && intake.files.length === 10, "candidate_count_mismatch");
    const files = new Map();
    for (const entry of intake.files) {
      const source = prepared.files.get(entry.path);
      need(source?.bytes instanceof Uint8Array, "candidate_bytes_missing");
      const bytes = Buffer.from(source.bytes), digest = hash(bytes);
      need(bytes.length === entry.bytes && digest === entry.sha256_raw && digest === source.sha256, "candidate_bytes_changed");
      files.set(entry.path, { bytes, sha256: digest });
    }
    const classified = classifySite([...files.keys()], { expectData: 6, game: "849843" });
    need(classified.data.join("|") === DATA.join("|") && classified.static.length === 4, "candidate_paths_mismatch");
    need(typeof accessCode === "string" && /^[^\s\p{Cc}]{8,128}$/u.test(accessCode), "access_code_invalid");
    need(collectionBytes instanceof Uint8Array && collectionBytes.byteLength > 0 && collectionBytes.byteLength <= 16384, "collection_bytes_invalid");
    return { prepared: { intake, files, classified }, collection: Buffer.from(collectionBytes) };
  } catch (error) { throw new Stage4Error(codeOf(error)); }
}

export async function runStage4Read({ target, prepared: input, accessCode, collectionBytes, outDir, versionPin, fetchImpl = fetch } = {}) {
  const { prepared, collection } = checkedInputs(input, accessCode, collectionBytes);
  const origin = target?.origin;
  const allowed = [
    ...new Set(["/", "/?game=849843", ...[...prepared.files.keys()].map(k => "/" + k), ...ABSENT, "/collection-settings.json"]),
  ].map(path => ({ method: "GET", path }));
  allowed.push({ method: "HEAD", path: "/_publish/v1/health.json" }, { method: "HEAD", path: "/v1/manifest.json" },
    { method: "POST", path: ACCESS_ROUTE }, { method: "DELETE", path: ACCESS_ROUTE });
  const transport = await createStage4Transport({ origin, outDir, limit: 24, reserve: 1, allowed, versionPin, fetchImpl });
  let session = null, verifier = null, failure = null, logout = "not_needed", collectionMatched = false;
  const checks = [];
  const check = (name, ok) => { checks.push({ name, passed: Boolean(ok) }); need(ok, "acceptance_mismatch"); };
  const gate = async () => {
    for (const path of ["/", "/favicon.svg", "/v1/manifest.json"]) {
      const response = await transport.fetch(origin + path, {}, { statuses: [401] });
      check("unauthenticated_401:" + path, response.headers.get(ACCESS_HEADER) === "required");
      await boundedBytes(response);
    }
    const response = await transport.fetch(origin + "/_publish/v1/health.json", { method: "HEAD" }, { statuses: [503] });
    await boundedBytes(response); check("upload_off_503", true);
  };
  const verifiedFetch = async (url, init) => {
    let response;
    try {
      const path = new URL(url).pathname + new URL(url).search, method = init?.method ?? "GET";
      const indexRedirect = path === "/index.html";
      response = await transport.fetch(url, init, { statuses: ABSENT.includes(path) ? [404] : indexRedirect ? [200, 301, 302, 303, 307, 308] : [200],
        ...(indexRedirect ? { redirectTo: "/" } : {}) });
      if (method === "POST" && path === ACCESS_ROUTE) {
        const pair = (response.headers.get("Set-Cookie") || "").split(";")[0];
        if (COOKIE.test(pair)) session = pair;
        need(session !== null, "login_cookie_missing_or_invalid");
      }
      // Excluded evaluation data: status only, never inspect its body.
      if (ABSENT.includes(path)) return response;
      if (response.status >= 300) return response;
      if (method === "HEAD") {
        need(response.headers.get("ETag") !== null && response.headers.get("Cache-Control") === "no-store, no-transform", "data_headers_mismatch");
        return response;
      }
      const key = path === "/" || path === "/?game=849843" ? "index.html" : path.slice(1);
      if (prepared.files.has(key)) {
        const expected = prepared.files.get(key);
        const bytes = await boundedBytes(response.clone());
        need(bytes.length === expected.bytes.length && hash(bytes) === expected.sha256, "remote_bytes_mismatch");
        if (key.startsWith("v1/")) need(response.headers.get("ETag") !== null && response.headers.get("Cache-Control") === "no-store, no-transform", "data_headers_mismatch");
        else {
          const kind = key === "index.html" ? "html" : key === "favicon.svg" ? "svg" : key.endsWith(".js") ? "js" : "css";
          need(MIME[kind].test(response.headers.get("Content-Type") || ""), "static_mime_mismatch");
        }
      }
      return response;
    } catch (error) {
      if (response?.body && !response.body.locked) void response.body.cancel().catch(() => {});
      transport.halt(codeOf(error)); throw new Stage4Error(codeOf(error));
    }
  };
  try {
    await gate();
    verifier = await verifyExhibitRemote({ target: { origin, kind: "https" }, prepared, game: "849843", accessCode, fetchImpl: verifiedFetch });
    need(verifier.passed && verifier.counts.requests === 18 && verifier.pass === 19, "verifier_failed");
    const response = await transport.fetch(origin + "/collection-settings.json", { headers: { Cookie: session } }, { statuses: [200] });
    const bytes = await boundedBytes(response, 16384);
    collectionMatched = bytes.length === collection.length && hash(bytes) === hash(collection);
    check("collection_settings_bytes", collectionMatched);
  } catch (error) { failure = codeOf(error); transport.halt(failure); }
  finally {
    if (session !== null) {
      try {
        const response = await transport.cleanupFetch(origin + ACCESS_ROUTE, { method: "DELETE", headers: { Cookie: session } }, { statuses: [204] });
        await boundedBytes(response); logout = "confirmed_204";
      } catch { logout = "unconfirmed"; failure ??= "logout_unconfirmed"; }
      session = null;
    }
  }
  const transportResult = transport.summary();
  return { schema: "pitcheezy-stage4-read-result-v1", passed: failure === null && logout === "confirmed_204" && transportResult.attempted_requests === 24,
    failure, source_commit: SOURCE, data_generation_commit: DATA_SOURCE, expected_deployment_version: versionPin,
    version_basis: "operator_management_pin_not_http_or_server_log_proof", transport: transportResult,
    checks: [...checks, ...(verifier?.checks ?? []).map(({ name, passed }) => ({ name, passed }))],
    verifier_pass: verifier?.pass ?? null, verifier_fail: verifier?.fail ?? null, collection_matched: collectionMatched, logout,
    limitations: ["HTTP byte and response checks only; no browser, notice mutation or deployment.",
      "Per-request private header receipts need separate stored-server-log correlation.", "Excluded evaluation data bodies are not inspected."] };
}

/**
 * First-connection rehearsal (WS-ops2): Song's delivered contract examples uploaded through OUR Worker in the
 * documented order, served next to Song's built public screen (dist-public). Everything is local and
 * ephemeral: the examples are Song's synthetic snapshots, the screen bundle is a read-only build of the
 * pinned commit, nothing is published or deployed. Codes/tokens stay in process; receipts hold hashes only.
 */
import { readFile, writeFile, stat, readdir } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { resolve, join, extname, normalize, sep } from "node:path";
import { parseArgs } from "node:util";
import { createRequire } from "node:module";
import { createHash, randomBytes } from "node:crypto";
import { Miniflare } from "miniflare";
import { waitForReady, boundedCleanup } from "./rehearsal/local-host.mjs";
const require = createRequire(import.meta.url);
export const EXPECTED = require("./examples/collab001-expected-files.json");
const hash = value => createHash("sha256").update(value).digest("hex");
function need(value, code) { if (!value) throw new Error(code); }
const MIME = { ".html": "text/html; charset=utf-8", ".js": "text/javascript; charset=utf-8", ".css": "text/css; charset=utf-8",
  ".svg": "image/svg+xml", ".json": "application/json; charset=utf-8", ".png": "image/png", ".ico": "image/x-icon", ".map": "application/json" };

/** Serves the built screen like the ASSETS binding would: files only, no SPA fallback for unknown paths. */
async function assetServer(dist) {
  const root = resolve(dist);
  const files = new Map();
  async function walk(dir) {
    for (const entry of await readdir(dir, { withFileTypes: true })) {
      const full = join(dir, entry.name);
      if (entry.isDirectory()) await walk(full);
      else if (entry.isFile()) files.set("/" + full.slice(root.length + 1).split(sep).join("/"), await readFile(full));
    }
  }
  await walk(root);
  need(files.has("/index.html"), "dist_index_missing");
  return {
    count: files.size,
    bytes: [...files.values()].reduce((n, b) => n + b.length, 0),
    index_sha256: hash(files.get("/index.html")),
    fetch(request) {
      const url = new URL(request.url);
      const path = url.pathname === "/" ? "/index.html" : normalize(url.pathname).split(sep).join("/");
      const body = files.get(path);
      if (!body) return new Response("not found", { status: 404, headers: { "Content-Type": "text/plain" } });
      const headers = { "Content-Type": MIME[extname(path)] || "application/octet-stream" };
      // Hashed assets could be cached for a year; index.html must be revalidated. Mirrors typical static hosting.
      headers["Cache-Control"] = path === "/index.html" ? "public, max-age=0, must-revalidate" : "public, max-age=31536000, immutable";
      return new Response(request.method === "HEAD" ? null : body, { status: 200, headers });
    },
  };
}

export async function loadExamples(dir) {
  const root = resolve(dir);
  const files = {};
  for (const row of EXPECTED.files) {
    const raw = await readFile(join(root, row.path));
    files[row.path] = { bytes: raw, sha256: hash(raw), matches: hash(raw) === row.sha256, ...row };
  }
  return files;
}

export async function startFirstConnectionHost({ examples, dist, readOrigin = "", signal } = {}) {
  const token = randomBytes(32).toString("base64url");
  const files = await loadExamples(examples);
  const assets = await assetServer(dist);
  const mf = new Miniflare({
    modules: true, modulesRoot: fileURLToPath(new URL("./", import.meta.url)), scriptPath: fileURLToPath(new URL("./worker.mjs", import.meta.url)),
    compatibilityDate: "2026-07-30", host: "127.0.0.1", port: 0, r2Buckets: ["PUBLISH_BUCKET"],
    ratelimits: { PUBLISH_LIMITER: { namespace_id: "1002", simple: { limit: 600, period: 60 } } },
    bindings: { DATA_READ_ENABLED: "true", UPLOAD_ENABLED: "true", PUBLISH_TOKEN_SHA256: hash(token), READ_ORIGIN: readOrigin },
    serviceBindings: { ASSETS: request => assets.fetch(request) },
  });
  try {
    const origin = (await waitForReady(mf.ready, signal)).origin;
    const url = new URL(origin);
    need(url.protocol === "http:" && url.hostname === "127.0.0.1", "local_target_required");
    const authed = (path, init) => fetch(origin + "/_publish/" + path, { ...init, redirect: "error",
      signal: AbortSignal.timeout(10000), headers: { Authorization: "Bearer " + token, ...init.headers } });
    const etags = {};
    const host = {
      origin, files, assets: { count: assets.count, bytes: assets.bytes, index_sha256: assets.index_sha256 }, etags,
      get: (path, init = {}) => fetch(origin + "/" + path, { ...init, redirect: "error", signal: AbortSignal.timeout(10000), cache: "no-store" }),
      /** Uploads one delivered example to its documented target with the documented precondition chain. */
      async upload(examplePath) {
        const row = files[examplePath];
        need(row && row.matches, "example_hash_mismatch:" + examplePath);
        const current = etags[row.target];
        const response = await authed(row.target, { method: "PUT", body: row.bytes, headers: {
          "Content-Type": "application/json", "X-Content-SHA256": row.sha256,
          ...(current ? { "If-Match": current } : { "If-None-Match": "*" }) } });
        const text = await response.text();
        need(response.status === 200, "upload_failed:" + row.target + ":" + response.status);
        etags[row.target] = response.headers.get("ETag");
        return { target: row.target, status: response.status, etag: etags[row.target], stored: JSON.parse(text).stored };
      },
      /**
       * Test-only variant: the same example with `publish.published_at` (and health's top-level `published_at`)
       * moved to `atIso`, so a screen compares against a current publish time instead of the 2026-10-05 snapshot
       * time. The bytes differ from the pack, so the receipt records them as a separate shifted artefact.
       */
      async uploadShifted(examplePath, atIso) {
        const row = files[examplePath];
        need(row && row.matches, "example_hash_mismatch:" + examplePath);
        const value = JSON.parse(new TextDecoder().decode(row.bytes));
        value.publish = { ...value.publish, published_at: atIso };
        if (Object.hasOwn(value, "published_at")) value.published_at = atIso;
        const bytes = new TextEncoder().encode(JSON.stringify(value));
        const digest = hash(bytes);
        const current = etags[row.target];
        const response = await authed(row.target, { method: "PUT", body: bytes, headers: {
          "Content-Type": "application/json", "X-Content-SHA256": digest,
          ...(current ? { "If-Match": current } : { "If-None-Match": "*" }) } });
        await response.arrayBuffer();
        need(response.status === 200, "upload_failed:" + row.target + ":" + response.status);
        etags[row.target] = response.headers.get("ETag");
        return { target: row.target, etag: etags[row.target], shifted_sha256: digest, original_sha256: row.sha256, published_at: atIso };
      },
      async withdraw(target) {
        const response = await authed(target, { method: "DELETE", headers: { "If-Match": etags[target] } });
        await response.arrayBuffer();
        need(response.status === 200, "withdraw_failed:" + target);
        etags[target] = response.headers.get("ETag");
        return etags[target];
      },
      dispose: () => mf.dispose(),
    };
    return host;
  } catch (error) {
    const cleanup = await boundedCleanup(() => mf.dispose());
    throw Object.assign(error instanceof Error ? error : new Error("local_start_failed"), { cleanup });
  }
}

/** The documented order: lists first, then the one game through its six snapshots, then the archive game, setup, health last. */
export const PROCEDURE = [
  "examples/manifest-live.json", "examples/dates.json", "examples/games-live.json", "examples/games-archive.json",
  "examples/game-pregame.json", "examples/game-live.json", "examples/game-live-unconfirmed.json", "examples/game-disconnected.json",
  "examples/game-between-innings.json", "examples/game-final.json", "examples/game-final-archive.json", "examples/setup.json",
  "examples/health-live.json",
];

async function sourceReceipt() {
  const values = {};
  for (const name of ["worker.mjs", "gateway.mjs", "notice.mjs", "access.mjs", "rehearsal/local-host.mjs", "rehearse-first-connection.mjs", "examples/collab001-expected-files.json", "package-lock.json"]) {
    values[name] = hash(await readFile(new URL(name, import.meta.url)));
  }
  return values;
}

export async function runFirstConnection({ examples, dist }) {
  const start = performance.now();
  const report = { schema: "pitcheezy-first-connection-rehearsal-v1", target: "ephemeral-loopback-miniflare", synthetic: true,
    song_examples_commit: EXPECTED.commit, screen_commit: "ef4e4df2f0547331459f9d952c5d76e1090f11e8",
    screen_rendering_verified: "separate browser receipt", live_data: false, real_hosting: false,
    environment: { node: process.version, platform: process.platform, arch: process.arch, miniflare: require("miniflare/package.json").version },
    source_sha256: await sourceReceipt(), steps: [], passed: false };
  let host;
  try {
    host = await startFirstConnectionHost({ examples, dist, readOrigin: "https://screen.example.test" });
    report.assets = host.assets;
    report.examples = Object.fromEntries(Object.entries(host.files).map(([k, v]) => [k, { bytes: v.bytes.length, sha256: v.sha256, hash_matches_pack: v.matches }]));
    need(Object.values(host.files).every(f => f.matches), "pack_hash_mismatch");
    report.steps.push({ step: "hashes", ok: true, files: Object.keys(host.files).length });
    // Before anything is published: data 404 as JSON, the screen itself served.
    const missing = await host.get("v1/game/900200.json"); await missing.arrayBuffer();
    need(missing.status === 404 && /application\/json/.test(missing.headers.get("Content-Type")), "missing_not_json_404");
    const index = await host.get(""); const indexText = await index.text();
    need(index.status === 200 && /<div id="root">/.test(indexText), "screen_not_served");
    report.steps.push({ step: "empty_host", missing_json_404: true, screen_served: true });
    // Documented upload order.
    const uploads = [];
    for (const examplePath of PROCEDURE) {
      const result = await host.upload(examplePath);
      const read = await host.get(result.target);
      const body = new Uint8Array(await read.arrayBuffer());
      need(read.status === 200 && hash(body) === host.files[examplePath].sha256, "readback_mismatch:" + result.target);
      need(read.headers.get("ETag") === result.etag && read.headers.get("Cache-Control") === "no-store" &&
        read.headers.get("Age") === "0" && Number.isFinite(Date.parse(read.headers.get("Date"))), "readback_headers:" + result.target);
      uploads.push({ example: examplePath, target: result.target, bytes: body.length, etag: result.etag, readback_sha256_matches: true });
    }
    report.steps.push({ step: "procedure_uploads", ok: true, uploads });
    // Replacement chain: six snapshots on one path moved the ETag each time and the last body is game-final.
    const finalRead = await host.get("v1/game/900200.json");
    need(hash(new Uint8Array(await finalRead.arrayBuffer())) === host.files["examples/game-final.json"].sha256, "final_not_last");
    need(new Set(uploads.filter(u => u.target === "v1/game/900200.json").map(u => u.etag)).size === 6, "etag_not_unique_per_snapshot");
    report.steps.push({ step: "replacement_chain", ok: true, snapshots: 6 });
    // Hosting conditions 1-1: conditional GET, cross-origin exposure, 404 not index, deletion, whole-file replace.
    const tag = host.etags["v1/game/900200.json"];
    const notModified = await host.get("v1/game/900200.json", { headers: { "If-None-Match": tag } }); await notModified.arrayBuffer();
    need(notModified.status === 304 && notModified.headers.get("ETag") === tag, "conditional_get");
    const cross = await host.get("v1/health.json", { headers: { Origin: "https://screen.example.test" } }); await cross.arrayBuffer();
    need(cross.headers.get("Access-Control-Allow-Origin") === "https://screen.example.test" && /Date, Age, ETag/.test(cross.headers.get("Access-Control-Expose-Headers")), "cors_exposure");
    const other = await host.get("v1/health.json", { headers: { Origin: "https://evil.example.test" } }); await other.arrayBuffer();
    need(other.headers.get("Access-Control-Allow-Origin") === null, "cors_leak");
    const notFound = await host.get("v1/game/1.json"); const nfText = await notFound.text();
    need(notFound.status === 404 && !/<!doctype/i.test(nfText), "404_served_index");
    const stale = await host.get("v1/game/900200.json", { headers: { "If-None-Match": uploads[4].etag } }); await stale.arrayBuffer();
    need(stale.status === 200, "stale_tag_got_304");
    const tomb = await host.withdraw("v1/game/900101.json");
    const gone = await host.get("v1/game/900101.json"); await gone.arrayBuffer();
    need(gone.status === 404, "withdraw_not_reflected");
    const restored = await host.upload("examples/game-final-archive.json");
    need(restored.etag !== tomb, "restore_etag");
    const back = await host.get("v1/game/900101.json");
    need(hash(new Uint8Array(await back.arrayBuffer())) === host.files["examples/game-final-archive.json"].sha256, "restore_bytes");
    report.steps.push({ step: "hosting_conditions", conditional_get_304: true, cross_origin_exposes_date_age_etag: true, other_origin_blocked: true,
      missing_is_json_404: true, deletion_reflected_immediately: true, restore_new_etag: true, cache_control: "no-store (revalidate every time)",
      not_checked: ["real CDN Date/Age behaviour", "long cache for final files (not implemented)", "partial file visibility on a real uploader"] });
    report.deployment_list = { contract: EXPECTED.contract, song_publisher_commit: EXPECTED.commit, song_screen_commit: report.screen_commit,
      our_host_commit: "recorded in the handoff record (git HEAD at receipt time)", screen_index_sha256: host.assets.index_sha256 };
    report.passed = true;
  } catch (error) {
    report.failure = /^[a-z_0-9:./-]+$/i.test(error.message) ? error.message : "phase_failed";
  } finally {
    if (host) report.cleanup = await boundedCleanup(() => host.dispose());
    if (report.cleanup && report.cleanup.status !== "complete") { report.passed = false; report.failure = "cleanup:" + report.cleanup.code; }
  }
  report.total_ms = Math.round(performance.now() - start);
  return report;
}

export async function main(args) {
  try {
    const { values } = parseArgs({ args, options: { examples: { type: "string" }, dist: { type: "string" }, output: { type: "string" } } });
    need(values.examples && values.dist, "arguments_required");
    for (const dir of [values.examples, values.dist]) need((await stat(dir)).isDirectory(), "directory_required");
    const report = await runFirstConnection({ examples: values.examples, dist: values.dist });
    const text = JSON.stringify(report, null, 2) + "\n";
    if (values.output) await writeFile(values.output, text, { flag: "wx", mode: 0o600 });
    process.stdout.write(text);
    return report.passed ? 0 : 1;
  } catch { process.stderr.write('{"ok":false,"code":"rehearsal_arguments_or_output_error"}\n'); return 2; }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await main(process.argv.slice(2));
}

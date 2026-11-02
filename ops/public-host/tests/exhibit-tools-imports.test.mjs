// The deploy-day tools must load from a checkout WITHOUT ops/public-host/node_modules: their static ESM import graph may
// reach only node: built-ins and our own files (never miniflare via rehearsal/local-host.mjs), and a child Node imports each
// one with NODE_PATH unset.
import test from "node:test";
import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { readFile } from "node:fs/promises";
import { dirname, relative, resolve } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { promisify } from "node:util";

const run = promisify(execFile);
const root = resolve(dirname(fileURLToPath(import.meta.url)), "..");
const TOOLS = ["verify-exhibit-remote.mjs", "exhibit-upload-plans.mjs", "exhibit-token-helper.mjs"];
// Static forms only: import x from "s"; import {..} from "s"; import "s"; export {..} from "s"; export * from "s"; import("s").
const SPECIFIER = /(?:^|[;\s}])(?:import|export)\s+(?:[^'";]*?\s+from\s+)?["']([^"'\n]+)["']|\bimport\s*\(\s*["']([^"'\n]+)["']\s*\)/g;
const isRelative = s => s.startsWith("./") || s.startsWith("../");

async function importGraph(entry) {
  const graph = new Map(); // absolute file -> specifiers written in it
  const queue = [resolve(root, entry)];
  while (queue.length) {
    const file = queue.pop();
    if (graph.has(file)) continue;
    const text = await readFile(file, "utf8"); // a dangling relative import fails here (ENOENT)
    const specifiers = [...text.matchAll(SPECIFIER)].map(m => m[1] ?? m[2]);
    graph.set(file, specifiers);
    for (const s of specifiers) if (isRelative(s)) queue.push(resolve(dirname(file), s));
  }
  return graph;
}

test("static import graph of the three tools: every bare specifier is node:*, local-host.mjs/miniflare never appear, exhibit-site.mjs is the shared module", async () => {
  for (const tool of TOOLS) {
    const graph = await importGraph(tool);
    const files = [...graph.keys()].map(f => relative(root, f).split("\\").join("/"));
    const bare = [...graph.values()].flat().filter(s => !isRelative(s));
    assert.ok(bare.length > 0, tool);
    for (const s of bare) assert.ok(s.startsWith("node:"), `${tool}: bare specifier ${s} is not a node: built-in`);
    assert.equal(bare.includes("miniflare"), false, tool);
    assert.equal(files.includes("rehearsal/local-host.mjs"), false, `${tool} must not reach rehearsal/local-host.mjs`);
    assert.equal(files.includes("rehearse-exhibit-host.mjs"), false, `${tool} must not reach the Miniflare rehearsal`);
    assert.ok(files.includes(tool), tool);
    if (tool !== "exhibit-token-helper.mjs") assert.ok(files.includes("exhibit-site.mjs"), `${tool} takes prepareSite/hash from exhibit-site.mjs`);
    for (const f of files) assert.ok(!f.startsWith("../") && f.endsWith(".mjs"), `${tool}: ${f} stays inside ops/public-host`);
  }
  // The rehearsal keeps re-exporting the moved names, so its callers and tests are unchanged.
  const rehearsal = await readFile(resolve(root, "rehearse-exhibit-host.mjs"), "utf8");
  assert.match(rehearsal, /export \{ validateIntakeReceipt, verifySite, classifySite, makeAssets, prepareSite, EXHIBIT_GAME, hash \};/);
  assert.match(rehearsal, /from "\.\/exhibit-site\.mjs"/);
  const site = await readFile(resolve(root, "exhibit-site.mjs"), "utf8");
  const siteSpecifiers = [...site.matchAll(SPECIFIER)].map(m => m[1] ?? m[2]);
  assert.deepEqual(siteSpecifiers.filter(s => /miniflare|local-host|rehearse/.test(s)), [], "exhibit-site.mjs imports neither Miniflare nor the rehearsal");
  assert.ok(siteSpecifiers.includes("node:crypto"), "hash() comes from node:crypto");
});

test("live: a child Node (NODE_PATH unset) imports each tool as an ES module without running its CLI", { timeout: 60000 }, async () => {
  const env = { ...process.env };
  delete env.NODE_PATH;
  for (const tool of TOOLS) {
    const href = pathToFileURL(resolve(root, tool)).href;
    const { stdout, stderr } = await run(process.execPath, ["--input-type=module", "-e",
      `const m = await import(${JSON.stringify(href)}); process.stdout.write("imported " + Object.keys(m).sort().join(","));`],
      { env, windowsHide: true, timeout: 30000 });
    assert.match(stdout, /^imported /, tool);
    assert.ok(stdout.includes("main"), `${tool} exports main`);
    assert.equal(stderr, "", tool);
  }
});

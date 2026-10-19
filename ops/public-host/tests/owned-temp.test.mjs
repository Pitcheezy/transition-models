import test from "node:test";
import assert from "node:assert/strict";
import { readFile, writeFile, lstat, mkdir, rename, symlink, unlink, rmdir } from "node:fs/promises";
import { dirname, join } from "node:path";
import { execFile } from "node:child_process";
import { promisify } from "node:util";
import { createTestDirectory } from "./helpers/owned-temp.mjs";

const execute = promisify(execFile);
const helperUrl = new URL("./helpers/owned-temp.mjs", import.meta.url).href;
const ignoreMissing = error => { if (error.code !== "ENOENT") throw error; };

for (const outcome of ["success", "setup failure", "assertion failure"]) {
  test("owned fixture cleanup runs after child test " + outcome, async (t) => {
    const sibling = await createTestDirectory(t);
    const sentinel = join(sibling, "sentinel.txt");
    const marker = join(sibling, "created.txt");
    const source = join(sibling, "child.test.mjs");
    await writeFile(sentinel, "unrelated sibling must survive");
    const child = [
      'import test from "node:test";',
      'import assert from "node:assert/strict";',
      'import { writeFile, readFile } from "node:fs/promises";',
      'import { join } from "node:path";',
      "import { createTestDirectory } from " + JSON.stringify(helperUrl) + ";",
      'test("synthetic cleanup fixture", async (t) => {',
      "  const directory = await createTestDirectory(t);",
      "  await writeFile(" + JSON.stringify(marker) + ", directory);",
      outcome === "setup failure" ? '  throw new Error("synthetic setup failure");' : "",
      '  await writeFile(join(directory, "fixture.txt"), "synthetic fixture");',
      outcome === "assertion failure" ? '  assert.fail("synthetic assertion failure");' :
        '  assert.equal(await readFile(join(directory, "fixture.txt"), "utf8"), "synthetic fixture");',
      "});",
    ].join("\n");
    await writeFile(source, child);
    // A fresh runner must not inherit the parent test worker's internal execution context.
    const childEnv = { ...process.env };
    delete childEnv.NODE_TEST_CONTEXT;
    const result = await execute(process.execPath, ["--test", "--test-reporter=tap", source],
      { timeout: 10000, env: childEnv })
      .then(value => ({ ...value, code: 0 }), error => error);
    assert.match(result.stdout, /^# tests 1$/m);
    assert.equal(result.code, outcome === "success" ? 0 : 1);
    if (outcome !== "success") assert.match(result.stdout, /synthetic (setup|assertion) failure/);
    const directory = await readFile(marker, "utf8");
    assert.equal(dirname(directory), dirname(sibling));
    await assert.rejects(lstat(directory), { code: "ENOENT" });
    assert.equal(await readFile(sentinel, "utf8"), "unrelated sibling must survive");
  });
}

for (const replacement of ["linked", "replaced"]) {
  test("cleanup refuses a " + replacement + " fixture root and preserves unrelated data", async (t) => {
    const sibling = await createTestDirectory(t);
    const sentinel = join(sibling, "sentinel.txt");
    const held = join(sibling, "original");
    await writeFile(sentinel, "unrelated sibling must survive");
    let cleanup;
    const directory = await createTestDirectory({ after(fn) { cleanup = fn; } });
    assert.equal(dirname(directory), dirname(sibling));
    let moved = false, linked = false, replaced = false;
    try {
      await writeFile(join(directory, "original.txt"), "original fixture");
      await rename(directory, held);
      moved = true;
      if (replacement === "linked") {
        await symlink(sibling, directory, process.platform === "win32" ? "junction" : "dir");
        linked = true;
      } else {
        await mkdir(directory);
        replaced = true;
        await writeFile(join(directory, "replacement.txt"), "replacement fixture");
      }
      await assert.rejects(cleanup(), /unsafe_test_cleanup_path/);
      assert.equal(await readFile(sentinel, "utf8"), "unrelated sibling must survive");
      assert.equal(await readFile(join(held, "original.txt"), "utf8"), "original fixture");
      if (replaced) assert.equal(await readFile(join(directory, "replacement.txt"), "utf8"), "replacement fixture");
    } finally {
      if (linked) await unlink(directory).catch(ignoreMissing);
      if (replaced) {
        await unlink(join(directory, "replacement.txt")).catch(ignoreMissing);
        await rmdir(directory).catch(ignoreMissing);
      }
      if (moved) await rename(held, directory);
      await cleanup();
    }
    await assert.rejects(lstat(directory), { code: "ENOENT" });
  });
}

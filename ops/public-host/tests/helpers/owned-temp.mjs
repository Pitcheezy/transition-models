import { mkdtemp, realpath, lstat, readdir, unlink, rmdir } from "node:fs/promises";
import { tmpdir } from "node:os";
import { basename, dirname, join } from "node:path";

const PREFIX = "pitcheezy-host-test-";
const need = (condition, code) => { if (!condition) throw new Error(code); };

/** Register cleanup before callers write into this exact, fresh, flat test directory. */
export async function createTestDirectory(t) {
  // Canonical parent paths also satisfy the CLI's no-symlink input requirement.
  const parent = await realpath(tmpdir());
  const directory = await mkdtemp(join(parent, PREFIX));
  let identity;
  t.after(async () => {
    const entry = await lstat(directory, { bigint: true });
    const target = await realpath(directory);
    need(identity && !entry.isSymbolicLink() && entry.isDirectory() &&
      target === directory && dirname(target) === parent &&
      basename(target).startsWith(PREFIX) && basename(target).length > PREFIX.length &&
      entry.dev === identity.dev && entry.ino === identity.ino &&
      entry.birthtimeNs === identity.birthtimeNs, "unsafe_test_cleanup_path");
    const entries = await readdir(directory, { withFileTypes: true });
    need(entries.every(entry => entry.isFile()), "unsafe_test_cleanup_entry");
    for (const entry of entries) await unlink(join(directory, entry.name));
    await rmdir(directory);
  });
  identity = await lstat(directory, { bigint: true });
  return directory;
}

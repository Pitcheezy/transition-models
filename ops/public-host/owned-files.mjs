/** Track newly created files and remove only matching owned bytes after catchable I/O failure. */
import { open, lstat, unlink } from "node:fs/promises";

export async function writeNew(path, content, owned) {
  const file = await open(path, "wx", 0o600);
  const entry = { path, identity: null, namedIdentity: null, expected: Buffer.from(content, "utf8") };
  owned.push(entry); // Track creation before any stat/write/sync can fail.
  try {
    entry.identity = await file.stat({ bigint: true });
    entry.namedIdentity = await lstat(path, { bigint: true });
    await file.writeFile(content, "utf8");
    await file.sync();
  } finally { await file.close(); }
}

async function removeOwned(entry) {
  let file;
  try {
    const named = await lstat(entry.path, { bigint: true });
    if (!entry.identity || !entry.namedIdentity || !named.isFile() || named.isSymbolicLink() ||
        named.dev !== entry.namedIdentity.dev || named.ino !== entry.namedIdentity.ino ||
        named.ino !== entry.identity.ino || named.size > BigInt(entry.expected.length)) return false;
    file = await open(entry.path, "r");
    // Windows can report different dev values for named and handle stats.
    // Compare each API with its own creation identity; bigint keeps large inode IDs exact.
    const opened = await file.stat({ bigint: true });
    if (opened.dev !== entry.identity.dev || opened.ino !== entry.identity.ino || opened.size !== named.size) return false;
    // A failed write may have produced only a prefix. Never remove unexpected replacement contents.
    const bytes = Buffer.alloc(entry.expected.length + 1);
    let offset = 0;
    while (offset < bytes.length) {
      const { bytesRead } = await file.read(bytes, offset, bytes.length - offset, null);
      if (!bytesRead) break;
      offset += bytesRead;
    }
    if (BigInt(offset) !== opened.size || !bytes.subarray(0, offset).equals(entry.expected.subarray(0, offset))) return false;
    await file.close(); file = null;
    const current = await lstat(entry.path, { bigint: true });
    if (current.isSymbolicLink() || current.dev !== named.dev || current.ino !== named.ino ||
        current.size !== named.size || current.mtimeNs !== named.mtimeNs || current.ctimeNs !== named.ctimeNs) return false;
    await unlink(entry.path);
    return true;
  } catch (error) {
    return error.code === "ENOENT"; // Already absent is safe; other cleanup failures need operator attention.
  } finally { if (file) await file.close().catch(() => {}); }
}
export async function rollback(owned) {
  let complete = true;
  for (const entry of [...owned].reverse()) if (!await removeOwned(entry)) complete = false;
  return complete;
}


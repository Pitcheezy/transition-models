import test from "node:test";
import assert from "node:assert/strict";
import { execFile } from "node:child_process";
import { createHash } from "node:crypto";
import { readFile, readdir, stat } from "node:fs/promises";
import { userInfo } from "node:os";
import { join } from "node:path";
import { promisify } from "node:util";
import { createTestDirectory } from "./helpers/owned-temp.mjs";
import { main, nextSteps, parseAces, currentPrincipal, defaultIcaclsPath, SECRET_NAME } from "../exhibit-token-helper.mjs";

const WIN = process.platform === "win32";
const run = promisify(execFile);
function sink() {
  const chunks = [];
  return { write: chunk => { chunks.push(String(chunk)); return true; }, text: () => chunks.join("") };
}
/** Independent reading of the file's ACL: one ACE token per "<principal>:(flags)" group in the icacls listing. */
async function aclOf(path) {
  const { stdout } = await run(defaultIcaclsPath(), [path], { windowsHide: true });
  return { listing: stdout, aces: [...stdout.matchAll(/(\S+):((?:\([^)]*\))+)/g)].map(m => ({ principal: m[1], flags: m[2] })) };
}

test("writes a new 43-char base64url token file, prints only its SHA-256 and the next commands, refuses an existing path", async (t) => {
  const dir = await createTestDirectory(t);
  const out = join(dir, "publish-token.txt");
  const stdout = sink(), stderr = sink();
  assert.equal(await main(["--out", out], { stdout, stderr }), 0);
  assert.equal(stderr.text(), "");
  const token = await readFile(out, "utf8");
  assert.match(token, /^[A-Za-z0-9_-]{43}$/, "32 random bytes as base64url, no trailing newline");
  const lines = stdout.text().split("\n");
  assert.match(lines[0], /^[a-f0-9]{64}$/);
  assert.equal(lines[0], createHash("sha256").update(token).digest("hex"), "printed digest is the digest of the file bytes");
  assert.equal(stdout.text().includes(token), false, "the token itself is never printed");
  assert.equal(stdout.text().includes(token.slice(0, 12)), false);
  assert.ok(stdout.text().includes(`secret put ${SECRET_NAME}`));
  assert.ok(stdout.text().includes("PITCHEEZY_PUBLISH_TOKEN"));
  assert.ok(stdout.text().includes(`(Get-Content -Raw "${out}").Trim()`), "PowerShell read-back trims a stray CR/LF");
  assert.ok(stdout.text().includes("$(cat "));
  assert.ok(stdout.text().includes("ACL") && stdout.text().includes("exFAT") && stdout.text().includes("6단계"), "privacy comes from the ACL; folder and deletion guidance printed");
  if (WIN) {
    // The file's ACL is reduced to exactly one explicit grant for the current user; nothing inherited from the folder.
    const { listing, aces } = await aclOf(out);
    assert.equal(aces.length, 1, listing);
    assert.doesNotMatch(listing, /\(I\)/, "no inherited entries: " + listing);
    assert.equal(aces[0].flags, "(F)", listing);
    assert.equal(aces[0].principal.split("\\").pop().toLowerCase(), userInfo().username.toLowerCase(), listing);
    assert.equal(aces[0].principal.toLowerCase(), currentPrincipal().toLowerCase(), listing);
    // The same user still reads the exact bytes afterwards.
    assert.equal(await readFile(out, "utf8"), token);
  } else {
    t.diagnostic("ACL assertions skipped: not win32 (mode 0o600 applies)");
  }
  const before = await stat(out);
  const second = sink(), secondErr = sink();
  assert.equal(await main(["--out", out], { stdout: second, stderr: secondErr }), 2);
  assert.equal(second.text(), "");
  assert.deepEqual(JSON.parse(secondErr.text()), { ok: false, code: "output_exists" });
  assert.equal(await readFile(out, "utf8"), token, "existing file untouched");
  assert.equal((await stat(out)).mtimeMs, before.mtimeMs);
  assert.deepEqual(await readdir(dir), ["publish-token.txt"]);
  // Two runs never produce the same token.
  const other = sink();
  assert.equal(await main(["--out", join(dir, "second.txt")], { stdout: other, stderr: sink() }), 0);
  assert.notEqual(await readFile(join(dir, "second.txt"), "utf8"), token);
  assert.notEqual(other.text().split("\n")[0], lines[0]);
});

test("win32: when the ACL cannot be restricted the file is deleted and the run fails with acl_restrict_failed (no digest printed)", { skip: !WIN && "win32 only" }, async (t) => {
  const dir = await createTestDirectory(t);
  const out = join(dir, "never-kept.txt");
  const stdout = sink(), stderr = sink();
  assert.equal(await main(["--out", out], { stdout, stderr, icacls: join(dir, "no-such-icacls.exe") }), 2);
  assert.equal(stdout.text(), "");
  assert.deepEqual(JSON.parse(stderr.text()), { ok: false, code: "acl_restrict_failed" });
  assert.deepEqual(await readdir(dir), [], "the unrestricted token file does not survive");
});

test("ACE parsing and principal form", () => {
  const listing = 'C:\\x\\t.txt Sritone\\CodexSandboxUsers:(I)(M)\n' +
    '             S-1-5-21-1-2-3-4:(I)(M,DC)\n             Sritone\\Sritone:(I)(F)\n             NT AUTHORITY\\SYSTEM:(I)(F)\n\n1 files processed\n';
  const aces = parseAces(listing);
  assert.deepEqual(aces.map(a => [a.principal, a.flags, a.inherited]), [
    ["Sritone\\CodexSandboxUsers", "(I)(M)", true], ["S-1-5-21-1-2-3-4", "(I)(M,DC)", true], ["Sritone\\Sritone", "(I)(F)", true], ["AUTHORITY\\SYSTEM", "(I)(F)", true]]);
  assert.deepEqual(parseAces("C:\\x\\t.txt Sritone\\Sritone:(F)\n\nSuccessfully processed 1 files; Failed processing 0 files\n"),
    [{ principal: "Sritone\\Sritone", flags: "(F)", inherited: false }]);
  assert.equal(currentPrincipal({ USERDOMAIN: "DOM" }), "DOM\\" + userInfo().username);
  assert.equal(currentPrincipal({ USERDOMAIN: "" }), userInfo().username, "empty USERDOMAIN falls back to the bare user name");
  assert.equal(currentPrincipal({}), userInfo().username);
});

test("argument errors are coded and write nothing", async (t) => {
  const dir = await createTestDirectory(t);
  const stderr = sink();
  assert.equal(await main([], { stdout: sink(), stderr }), 2);
  assert.deepEqual(JSON.parse(stderr.text()), { ok: false, code: "out_required" });
  const unknown = sink();
  assert.equal(await main(["--out", join(dir, "x.txt"), "--bogus"], { stdout: sink(), stderr: unknown }), 2);
  assert.deepEqual(JSON.parse(unknown.text()), { ok: false, code: "token_helper_error" });
  assert.deepEqual(await readdir(dir), []);
  assert.ok(nextSteps("FILE", "CFG").some(line => line.includes("--config CFG")));
  assert.ok(nextSteps("FILE", "CFG").some(line => line.includes('(Get-Content -Raw "FILE").Trim()')));
});

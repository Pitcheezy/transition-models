/**
 * User-run helper: a fresh publisher bearer token (32 random bytes, base64url, 43 chars) written to a NEW file.
 * Prints only the token's SHA-256 hex (the value of the Worker secret PUBLISH_TOKEN_SHA256) and the next commands.
 * The token itself is never printed; the file has no trailing newline (the read-back lines below .Trim() anyway).
 *
 * Privacy of the file comes from its ACL, not from the 0o600 mode: Node ignores the mode bits on Windows and a new file
 * inherits its folder's ACL. On win32 the helper therefore strips inherited entries and grants only the current user
 * (icacls <file> /inheritance:r /grant:r "DOMAIN\USER:F", then re-reads the ACL); if that fails the file is deleted and the
 * run exits 2 with acl_restrict_failed. Put the file in a folder outside Projects, %TEMP%, Documents and the exFAT D:
 * drive (exFAT has no ACLs at all), never next to plans or receipts, and delete it once step 6 (upload OFF) is confirmed.
 */
import { execFile } from "node:child_process";
import { createHash, randomBytes } from "node:crypto";
import { open, unlink } from "node:fs/promises";
import { userInfo } from "node:os";
import { join, resolve } from "node:path";
import { fileURLToPath } from "node:url";
import { parseArgs, promisify } from "node:util";

export const TOKEN_BYTES = 32;
export const SECRET_NAME = "PUBLISH_TOKEN_SHA256";
class HelperError extends Error { constructor(code) { super(code); this.code = code; } }
const run = promisify(execFile);

export function defaultIcaclsPath(env = process.env) {
  return join(env.SystemRoot || env.SYSTEMROOT || "C:\\Windows", "System32", "icacls.exe");
}

/** DOMAIN\USER for icacls. A bare user name can resolve to the machine SID when the computer carries the same name. */
export function currentPrincipal(env = process.env) {
  const user = userInfo().username;
  const domain = (env.USERDOMAIN || "").trim();
  return domain ? `${domain}\\${user}` : user;
}

/** ACE tokens of an icacls listing, e.g. "Sritone\\Sritone:(F)" or "BUILTIN\\Users:(I)(M)". The localized summary line has none. */
export function parseAces(listing) {
  return [...String(listing).matchAll(/(\S+):((?:\([^)]*\))+)/g)].map(m => ({ principal: m[1], flags: m[2], inherited: m[2].includes("(I)") }));
}

async function restrictAcl(path, icacls) {
  const principal = currentPrincipal();
  const user = userInfo().username.toLowerCase();
  await run(icacls, [path, "/inheritance:r", "/grant:r", `${principal}:F`], { windowsHide: true });
  const { stdout } = await run(icacls, [path], { windowsHide: true });
  const aces = parseAces(stdout);
  const only = aces[0];
  if (aces.length !== 1 || only.inherited || only.principal.split("\\").pop().toLowerCase() !== user || only.flags !== "(F)") {
    throw new HelperError("acl_restrict_failed");
  }
}

export function nextSteps(outPath, configPath) {
  const config = configPath || "<candidate>/host/wrangler.deploy.json";
  return [
    `# 1) Worker 비밀 등록: 아래 프롬프트에 위 digest(64자 hex)를 붙여 넣는다. 토큰 원문이 아니다. 사용자 로그인 상태에서만.`,
    `node ops/public-host-tooling/node_modules/wrangler/bin/wrangler.js secret put ${SECRET_NAME} --config ${config}`,
    `# 2) publisher-cli 실행 직전에만 파일에서 환경 변수로 읽는다 (인자·계획 파일·로그·이슈에 쓰지 않는다).`,
    `#    PowerShell: $env:PITCHEEZY_PUBLISH_TOKEN = (Get-Content -Raw "${outPath}").Trim()`,
    `#    bash:       export PITCHEEZY_PUBLISH_TOKEN="$(cat "${outPath}")"`,
    `# 3) 업로드가 끝나면 변수를 지운다: Remove-Item Env:PITCHEEZY_PUBLISH_TOKEN  /  unset PITCHEEZY_PUBLISH_TOKEN`,
    `# 4) 파일의 비공개성은 폴더·파일 ACL에서 온다(Windows는 mode 0600을 무시한다${process.platform === "win32" ? "; 이 파일의 ACL은 현재 사용자만으로 제한했다" : ""}).`,
    `#    Projects·%TEMP%·Documents·exFAT D: 밖의 폴더에 두고 계획·영수증과 같은 폴더에 두지 않는다. 6단계(업로드 OFF) 확인 뒤 파일을 지운다.`,
    `#    회수는 Worker에서 ${SECRET_NAME}를 새 digest로 바꾸는 것이다.`,
  ];
}

export async function main(args, { stdout = process.stdout, stderr = process.stderr, platform = process.platform, icacls = defaultIcaclsPath() } = {}) {
  let file = null, out = null, written = false;
  try {
    const { values } = parseArgs({ args, options: { out: { type: "string" }, config: { type: "string" } } });
    if (!values.out) throw new HelperError("out_required");
    out = resolve(values.out);
    const token = randomBytes(TOKEN_BYTES).toString("base64url");
    file = await open(out, "wx", 0o600); // refuses an existing path; never overwrites
    written = true;
    try { await file.writeFile(token, "utf8"); await file.sync(); } finally { await file.close(); }
    if (platform === "win32") {
      try { await restrictAcl(out, icacls); } catch { throw new HelperError("acl_restrict_failed"); }
    }
    const digest = createHash("sha256").update(token).digest("hex");
    stdout.write(digest + "\n" + nextSteps(out, values.config).join("\n") + "\n");
    return 0;
  } catch (error) {
    const code = error?.code === "EEXIST" ? "output_exists" : error instanceof HelperError ? error.code : "token_helper_error";
    if (written && code === "acl_restrict_failed") {
      // A token whose file ACL could not be restricted is discarded: restore inheritance (owner keeps WRITE_DAC) so the unlink succeeds.
      await run(icacls, [out, "/reset"], { windowsHide: true }).catch(() => {});
      await unlink(out).catch(() => {});
    }
    stderr.write(JSON.stringify({ ok: false, code }) + "\n");
    return 2;
  }
}
if (process.argv[1] && resolve(process.argv[1]) === fileURLToPath(import.meta.url)) {
  process.exitCode = await main(process.argv.slice(2));
}

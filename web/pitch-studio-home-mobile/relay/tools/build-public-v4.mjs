// build-public-v4.mjs — relay V4를 공개 호스트(app) 정적 폴더 public/로 모은다(2026-11-10 사용자 "v4로 배포버전 바꾸자"). 배포는 하지 않는다(파일만 만든다).
//   node tools/build-public-v4.mjs <후보 폴더> [--replace]   → <후보 폴더>/public/ 에 쓴다
//   후보 폴더는 git 작업 트리 밖이어야 하고, 이미 release-manifest.json이 있는(조립된) 후보는 --replace일 때만 다시 쓴다.
// 넣는 것: index.html(v4.html에서 생성), relay-v4.css, relay-v4.js, batter3d-host.js, batter3d/batter3d.js, three.js vendor 5(V3 공개본과 같은 목록),
//   batter3d/assets/batter-ctl-v4.glb·.meta.json(사람형 모델 변환본에 나가기 동작을 덧붙인 것).
// 경기 자료는 넣지 않는다: 공개본 relay-v4.js는 ./data/849843.json 대신 호스트의 공개 자료 경로 ./v1/game/849843.json을 읽는다
//   (V3처럼 호스트의 자료 스위치 DATA_READ_ENABLED·삭제 표시가 화면에도 적용되게 — 11/10 배포 전 점검 지적). 그 밖의 JS·CSS는 원본과 같은 바이트.
// index.html에서 바꾸는 것: 제목·설명(개발용 문구 → 방문객용), 뒤로(←)는 갈 곳이 없어(공개 경기 1개) 자리만 남기고 숨김. 그 밖의 바이트는 v4.html 그대로.
// 안전: 임시 폴더에 다 만들고 검사가 끝난 뒤에만 public/을 바꾼다. 있던 public/collection-settings.json(호스트 설정 짝)은 그대로 옮겨 둔다.
// 목록 V4-PUBLIC.json은 후보 폴더 밖(한 단계 위)에 쓴다 — 검사기는 후보 폴더 안의 목록에 없는 파일을 거부한다.
import { readFileSync, writeFileSync, mkdirSync, copyFileSync, statSync, rmSync, readdirSync, existsSync, mkdtempSync, cpSync } from "node:fs";
import { createHash } from "node:crypto";
import { spawnSync } from "node:child_process";
import { tmpdir } from "node:os";
import { resolve, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const relay = resolve(here, "..");
const args = process.argv.slice(2);
const replace = args.includes("--replace");
const outRoot = args.find((a) => !a.startsWith("--"));
if (!outRoot) { console.error("후보 폴더가 필요하다"); process.exit(2); }
const root = resolve(outRoot);
{ // git 작업 트리 안(이 저장소·다른 체크아웃 모두)이면 거부
  let p = root; while (!existsSync(p) && dirname(p) !== p) p = dirname(p);
  const g = spawnSync("git", ["-C", p, "rev-parse", "--show-toplevel"], { encoding: "utf8" });
  if (g.status === 0) { console.error("출력은 git 작업 트리 밖이어야 한다: " + g.stdout.trim()); process.exit(2); }
}
if (existsSync(join(root, "release-manifest.json")) && !replace) { console.error("조립된 후보(release-manifest.json 있음)는 --replace일 때만 다시 쓴다"); process.exit(2); }
const out = join(root, "public");
const tmp = mkdtempSync(join(tmpdir(), "pz-v4-public-"));
const read = (p) => readFileSync(resolve(relay, p), "utf8");
const put = (rel, text) => { const p = join(tmp, rel); mkdirSync(dirname(p), { recursive: true }); writeFileSync(p, text); };
const copy = (rel) => { const p = join(tmp, rel); mkdirSync(dirname(p), { recursive: true }); copyFileSync(resolve(relay, rel), p); };
try {
  let html = read("v4.html");
  const must = (re, to, what) => { const before = html; html = html.replace(re, to); if (html === before) throw new Error("치환 실패: " + what); };
  must(/<title>[^<]*<\/title>/, () => "<title>Pitcheezy 중계</title>", "title");
  must(/<meta\s+name="description"\s+content="[^"]*"\s*\/>/, () => '<meta name="description" content="끝난 경기를 한 공씩 다시 보며, 그 공을 던지기 전의 투구 추천을 살펴보는 Pitcheezy 중계 화면." />', "description");
  must(/<a class="hd-back" href="\.\.\/index\.html" aria-label="홈 화면으로">/, () => '<a class="hd-back" aria-hidden="true" tabindex="-1" style="visibility: hidden">', "back link");
  if (!/<meta name="robots" content="noindex" \/>/.test(html)) throw new Error("robots noindex가 없다");
  if (/localhost|127\.0\.0\.1|8790|demo-test|\.\.\//.test(html)) throw new Error("index.html에 로컬 주소·상위 경로가 남아 있다");
  put("index.html", html);

  let js = read("relay-v4.js");
  const DATA_DEV = 'fetch("./data/849843.json", { cache: "no-store" })';
  if (js.split(DATA_DEV).length !== 2) throw new Error("relay-v4.js 자료 주소가 정확히 한 곳이 아니다");
  if (/\/v1\//.test(js)) throw new Error("relay-v4.js에 이미 /v1/ 주소가 있다");
  js = js.replace(DATA_DEV, () => 'fetch("./v1/game/849843.json", { cache: "no-store" })');
  put("relay-v4.js", js);

  for (const f of ["relay-v4.css", "batter3d-host.js", "batter3d/batter3d.js",
    "batter3d/vendor/three.module.js", "batter3d/vendor/three.core.js", "batter3d/vendor/addons/loaders/GLTFLoader.js",
    "batter3d/vendor/addons/utils/BufferGeometryUtils.js", "batter3d/vendor/addons/utils/SkeletonUtils.js",
    "batter3d/assets/batter-ctl-v4.glb", "batter3d/assets/batter-ctl-v4.meta.json"]) copy(f);

  for (const f of ["relay-v4.js", "relay-v4.css", "batter3d-host.js", "batter3d/batter3d.js"]) {
    const t = readFileSync(join(tmp, f), "utf8");
    const bad = t.match(/https?:\/\/(?:localhost|127\.0\.0\.1)[^\s"')]*|demo-test|\.\/data\//g);
    if (bad) throw new Error(`${f}에 로컬 주소·개발 자료 경로: ${bad.join(", ")}`);
  }
  // 검사 통과 → public/ 교체(호스트 설정 짝 collection-settings.json은 보존)
  const cs = join(out, "collection-settings.json"), keep = existsSync(cs) ? readFileSync(cs) : null;
  rmSync(out, { recursive: true, force: true }); mkdirSync(dirname(out), { recursive: true });
  cpSync(tmp, out, { recursive: true });
  if (keep) writeFileSync(cs, keep);
} finally { rmSync(tmp, { recursive: true, force: true }); }

const files = [];
const walk = (dir, base = "") => { for (const name of readdirSync(dir).sort()) { const p = join(dir, name); const rel = base ? `${base}/${name}` : name; if (statSync(p).isDirectory()) walk(p, rel); else { const b = readFileSync(p); files.push({ path: rel, bytes: b.length, sha256: createHash("sha256").update(b).digest("hex") }); } } };
walk(out);
const total = files.reduce((a, f) => a + f.bytes, 0);
writeFileSync(join(root, "..", "V4-PUBLIC.json"), JSON.stringify({ schema: "pitcheezy-relay-v4-public-v1", builtAt: new Date().toISOString(), source: "relay v4.html + relay-v4.css/js + batter3d (worktree claude/mobile-home-demo-1103, 미커밋)", data: "./v1/game/849843.json (호스트 공개 자료, 정적 사본 없음)", files, total }, null, 1));
console.error(`${out}: ${files.length}개 파일, ${total.toLocaleString()} B`);
for (const f of files) console.error(`  ${f.sha256.slice(0, 8)}  ${String(f.bytes).padStart(9)}  ${f.path}`);

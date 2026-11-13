// build-public.mjs — relay v2(Pitcheezy 색 기본)를 공개 호스트에 올릴 수 있는 정적 폴더로 모은다(2026-11-09). 배포는 하지 않는다(파일만 만든다).
//   node tools/build-public.mjs <출력 폴더> [--model batter-ctl|batter-indexed] [--palette pz|song] [--home <홈 주소>] [--sub v2]
// 출력: <출력 폴더>/<sub>/ 아래 index.html(v2.html에서 생성), relay.js, relay-v2.css, batter3d-host.js, batter3d/{batter3d.js, vendor/*, assets/<model>.glb|.meta.json}, data/849843.json, 그리고 <출력 폴더>의 상위 폴더에 MANIFEST.json(SHA-256; 공개 폴더 밖).
// 규칙: 저장소 밖(D:)에 쓴다. 모델 선택(batter-ctl|batter-indexed)은 사용자 결정(기본값은 인자로만 정한다).
import { readFileSync, writeFileSync, mkdirSync, copyFileSync, statSync, rmSync, readdirSync } from "node:fs";
import { createHash } from "node:crypto";
import { resolve, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const relay = resolve(here, "..");
const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf(k); return i >= 0 && args[i + 1] ? args[i + 1] : d; };
const outRoot = args.find((a, i) => !a.startsWith("--") && (i === 0 || !args[i - 1].startsWith("--")));
if (!outRoot) { console.error("출력 폴더가 필요하다"); process.exit(2); }
const model = opt("--model", null); if (!["batter-ctl", "batter-indexed"].includes(model)) { console.error("--model batter-ctl|batter-indexed 를 명시하라(모델 선택은 사용자 결정)"); process.exit(2); }
const palette = opt("--palette", "pz"); if (!["pz", "song"].includes(palette)) { console.error("--palette pz|song"); process.exit(2); }
const home = opt("--home", "https://pitcheezy.com/");
const sub = opt("--sub", "v2");
const out = resolve(outRoot, sub);
if (resolve(outRoot).startsWith(resolve(relay))) { console.error("출력은 저장소 밖이어야 한다"); process.exit(2); }
rmSync(out, { recursive: true, force: true }); mkdirSync(out, { recursive: true });
const read = (p) => readFileSync(resolve(relay, p), "utf8");
const put = (rel, text) => { const p = join(out, rel); mkdirSync(dirname(p), { recursive: true }); writeFileSync(p, text); };
const copy = (rel) => { const p = join(out, rel); mkdirSync(dirname(p), { recursive: true }); copyFileSync(resolve(relay, rel), p); };

// index.html ← v2.html: 색 기본값, 홈 링크, 설명. 그 밖의 바이트는 그대로(틀·id·스크립트 태그 모두 v2와 같다)
let html = read("v2.html");
const must = (re, to, what) => { const before = html; html = html.replace(re, to); if (html === before) throw new Error("치환 실패: " + what); };
if (palette === "pz") {
  // 같은 줄의 `} catch (e) {}`가 뒤따르므로 줄 주석(//)을 쓰면 안 된다(블록 주석만)
  must(/if \(pal === "pz"\) document\.documentElement\.dataset\.palette = "pz";/, () => 'if (pal !== "song") document.documentElement.dataset.palette = "pz"; /* 공개본: Pitcheezy 색 기본, ?palette=song 이면 Song 색 */', "palette default");
}
must(/<a href="\.\.\/index\.html" class="wordmark"/, () => `<a href="${home}" class="wordmark"`, "home link");
must(/<title>([^<]*)<\/title>/, (m, t) => `<title>${t.replace(" v2, Song 틀 + 3D 타자", "")} — Pitcheezy</title>`, "title");
if (!/<meta name="robots" content="noindex" \/>/.test(html)) throw new Error("robots noindex가 없다");
if (/batter3d\/assets\/demo-test|localhost|127\.0\.0\.1|8794|8790/.test(html)) throw new Error("index.html에 로컬 주소가 남아 있다");
put("index.html", html);

{ // relay.js: 로딩 실패 안내문의 로컬 서버 주소만 공개용 문장으로(동작 변경 없음)
  let rj = read("relay.js"); const before = rj;
  rj = rj.replace("로컬 서버(http://localhost:8790/relay/)에서 열어 주세요.", "잠시 뒤 새로고침해 주세요.");
  if (rj === before) throw new Error("relay.js 안내문 치환 실패");
  put("relay.js", rj);
}
copy("relay-v2.css"); copy("batter3d/batter3d.js");
let host = read("batter3d-host.js");
if (model !== "batter-indexed") { const before = host; host = host.replace('const DEFAULT_MODEL = "batter-indexed";', `const DEFAULT_MODEL = "${model}"; // 공개본 기본 모델(빌드 인자)`); if (host === before) throw new Error("DEFAULT_MODEL 치환 실패"); }
put("batter3d-host.js", host);
for (const v of ["batter3d/vendor/three.module.js", "batter3d/vendor/three.core.js", "batter3d/vendor/addons/loaders/GLTFLoader.js", "batter3d/vendor/addons/utils/BufferGeometryUtils.js", "batter3d/vendor/addons/utils/SkeletonUtils.js"]) copy(v);
copy(`batter3d/assets/${model}.glb`); copy(`batter3d/assets/${model}.meta.json`);
copy("data/849843.json");

// 로컬 주소·개발용 경로가 섞이지 않았는지
for (const f of ["relay.js", "batter3d-host.js", "batter3d/batter3d.js"]) {
  const t = readFileSync(join(out, f), "utf8");
  const bad = t.match(/https?:\/\/(?:localhost|127\.0\.0\.1)[^\s"')]*/g);
  if (bad) throw new Error(`${f}에 로컬 주소: ${bad.join(", ")}`);
}

// MANIFEST
const files = [];
const walk = (dir, base = "") => { for (const name of readdirSync(dir).sort()) { const p = join(dir, name); const rel = base ? `${base}/${name}` : name; if (statSync(p).isDirectory()) walk(p, rel); else files.push({ path: `${sub}/${rel}`, bytes: statSync(p).size, sha256: createHash("sha256").update(readFileSync(p)).digest("hex") }); } };
walk(out);
const total = files.reduce((a, f) => a + f.bytes, 0);
const manifest = { schema: "pitcheezy-relay-public-candidate-v1", builtAt: new Date().toISOString(), source: "relay v2.html + relay.js + relay-v2.css + batter3d (worktree claude/mobile-home-demo-1103)", sub, model, palette, home, note: model === "batter-ctl" ? "사람형 모델 포함 — 모델 선택은 사용자 결정" : "마네킹(Mixamo 파생) 모델", files, totalBytes: total };
writeFileSync(join(resolve(outRoot), "..", "MANIFEST.json"), JSON.stringify(manifest, null, 1)); // 공개 폴더 밖(후보 폴더 루트)
console.error(`${out}: ${files.length}개 파일, ${total.toLocaleString()} B (${(total / 1048576).toFixed(2)} MB), model ${model}, palette ${palette}`);
for (const f of files) console.error(`  ${f.sha256.slice(0, 8)}  ${String(f.bytes).padStart(9)}  ${f.path}`);

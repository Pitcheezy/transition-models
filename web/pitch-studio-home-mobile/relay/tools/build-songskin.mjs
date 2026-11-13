// build-songskin.mjs — V3: Song 고정 빌드(v0 스냅샷의 public 4파일) + Pitcheezy 색 테마 + 3D 타자 덧입히기 → 정적 폴더(2026-11-09). 배포는 하지 않는다.
//   node tools/build-songskin.mjs <출력 폴더> --model batter-ctl|batter-indexed [--song <v0 스냅샷 폴더>]
// 출력: <출력 폴더>/public/ (배포용: Song index.html(세 줄 삽입)+assets+favicon + pz/{pz-theme.css, pz-batter.js, batter3d/...})
//       <출력 폴더>/local-serve/ (public + v1/ 자료 사본; 로컬 정적 서버로 열어 보기용) · <출력 폴더>/MANIFEST.json(public의 SHA-256)
// Song 파일은 index.html에 세 태그를 끼워 넣는 것 말고는 바이트 그대로 복사한다(assets/*.js·css 불변).
import { readFileSync, writeFileSync, mkdirSync, copyFileSync, statSync, rmSync, readdirSync, cpSync } from "node:fs";
import { createHash } from "node:crypto";
import { resolve, dirname, join } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const relay = resolve(here, "..");
const args = process.argv.slice(2);
const opt = (k, d) => { const i = args.indexOf(k); return i >= 0 && args[i + 1] ? args[i + 1] : d; };
const outRoot = args.find((a, i) => !a.startsWith("--") && (i === 0 || !args[i - 1].startsWith("--")));
if (!outRoot) { console.error("출력 폴더가 필요하다"); process.exit(2); }
if (resolve(outRoot).startsWith(resolve(relay))) { console.error("출력은 저장소 밖이어야 한다"); process.exit(2); }
const model = opt("--model", null); if (!["batter-ctl", "batter-indexed"].includes(model)) { console.error("--model batter-ctl|batter-indexed 를 명시하라(모델 선택은 사용자 결정)"); process.exit(2); }
const songDir = resolve(opt("--song", "D:/pitcheezy_exhibit_check/v0-snapshot-20261109"));
const pub = resolve(outRoot, "public"), loc = resolve(outRoot, "local-serve");
rmSync(pub, { recursive: true, force: true }); rmSync(loc, { recursive: true, force: true }); mkdirSync(pub, { recursive: true });

// 1) Song 정적 4파일 그대로
for (const f of ["index.html", "favicon.svg", "assets/index-X1sSTTQ4.js", "assets/index-ks_hu7Ji.css"]) { const p = join(pub, f); mkdirSync(dirname(p), { recursive: true }); copyFileSync(join(songDir, "public", f), p); }
// 2) index.html에 세 태그: 테마 CSS(Song CSS 뒤), import map(Song 모듈 스크립트 앞), 우리 모듈(마지막). theme-color는 Pitcheezy 헤더색
let html = readFileSync(join(pub, "index.html"), "utf8");
const must = (re, to, what) => { const b = html; html = html.replace(re, to); if (html === b) throw new Error("치환 실패: " + what); };
must(/<script type="module" crossorigin src="\.\/assets\/index-[^"]+\.js"><\/script>/, (m) => `<script type="importmap">{ "imports": { "three": "./pz/batter3d/vendor/three.module.js", "three/addons/": "./pz/batter3d/vendor/addons/" } }</script>\n    ${m}`, "importmap before Song module");
must(/(<link rel="stylesheet" crossorigin href="\.\/assets\/index-[^"]+\.css">)/, (m, a) => `${a}\n    <link rel="stylesheet" href="./pz/pz-theme.css">\n    <script type="module" src="./pz/pz-batter.js"></script>`, "theme css + host module after Song css");
must(/<meta name="theme-color" content="#f5f7f8" \/>/, () => '<meta name="theme-color" content="#091811" />', "theme-color");
writeFileSync(join(pub, "index.html"), html);
// 3) pz/: 테마·호스트·3D 모듈·vendor·모델
const put = (rel, text) => { const p = join(pub, rel); mkdirSync(dirname(p), { recursive: true }); writeFileSync(p, text); };
const copy = (fromRel, toRel) => { const p = join(pub, toRel); mkdirSync(dirname(p), { recursive: true }); copyFileSync(resolve(relay, fromRel), p); };
put("pz/pz-theme.css", readFileSync(join(here, "songskin/pz-theme.css"), "utf8"));
{ let js = readFileSync(join(here, "songskin/pz-batter.js"), "utf8"); const b = js; js = js.replace('const MODEL = "__MODEL__";', `const MODEL = ${JSON.stringify(model)};`); if (js === b) throw new Error("MODEL 치환 실패"); put("pz/pz-batter.js", js); }
copy("batter3d/batter3d.js", "pz/batter3d/batter3d.js");
for (const v of ["vendor/three.module.js", "vendor/three.core.js", "vendor/addons/loaders/GLTFLoader.js", "vendor/addons/utils/BufferGeometryUtils.js", "vendor/addons/utils/SkeletonUtils.js"]) copy(`batter3d/${v}`, `pz/batter3d/${v}`);
copy(`batter3d/assets/${model}.glb`, `pz/batter3d/assets/${model}.glb`); copy(`batter3d/assets/${model}.meta.json`, `pz/batter3d/assets/${model}.meta.json`);
for (const f of ["pz/pz-batter.js", "pz/batter3d/batter3d.js", "pz/pz-theme.css"]) { const t = readFileSync(join(pub, f), "utf8"); const bad = t.match(/https?:\/\/(?:localhost|127\.0\.0\.1)[^\s"')]*/g); if (bad) throw new Error(`${f}에 로컬 주소: ${bad.join(", ")}`); }
// 4) local-serve = public + v1 자료
cpSync(pub, loc, { recursive: true }); cpSync(join(songDir, "data-v1"), join(loc, "v1"), { recursive: true });
// 5) MANIFEST(public)
const files = [];
const walk = (dir, base = "") => { for (const name of readdirSync(dir).sort()) { const p = join(dir, name); const rel = base ? `${base}/${name}` : name; if (statSync(p).isDirectory()) walk(p, rel); else files.push({ path: rel, bytes: statSync(p).size, sha256: createHash("sha256").update(readFileSync(p)).digest("hex") }); } };
walk(pub);
const total = files.reduce((a, f) => a + f.bytes, 0);
writeFileSync(join(resolve(outRoot), "MANIFEST.json"), JSON.stringify({ schema: "pitcheezy-songskin-candidate-v1", builtAt: new Date().toISOString(), song: "c47fe6cb public 4 files from v0 snapshot (index.html: 3 tags inserted, theme-color)", model, note: model === "batter-ctl" ? "사람형 모델 포함 — 모델 선택은 사용자 결정" : "마네킹(Mixamo 파생) 모델", files, totalBytes: total }, null, 1));
console.error(`${pub}: ${files.length}개 파일, ${total.toLocaleString()} B (${(total / 1048576).toFixed(2)} MB), model ${model}`);
for (const f of files) console.error(`  ${f.sha256.slice(0, 8)}  ${String(f.bytes).padStart(9)}  ${f.path}`);

// bundle-demo.mjs — relay 중계 화면(v1·v2·v2t)을 서버 없이 더블클릭으로 열리는 HTML 파일 하나로 묶는다(2026-11-09, Song 전달용 로컬 데모).
//   node tools/bundle-demo.mjs v1|v2|v2t|v4 <출력 폴더>   (v4 = v4.html + relay-v4.css + relay-v4.js + batter-ctl-v4.glb(나가기 동작 4개), 2026-11-09)
//   (이전 사용법) node tools/bundle-demo.mjs v1|v2|v2t <출력 폴더>   (v2t = v2-tabs.html: v2 틀 + Pitcheezy 색 기본 + 토글을 v0 선수 시트 탭 양식으로, 2026-11-09; 처음 이름 v3)
// 넣는 것: HTML + CSS + relay.js + 경기 자료 JSON + 3D 모듈·어댑터 + three.js(vendor) + batter-ctl.glb/meta(base64).
// 방법: (1) fetch 가로채기 — data/849843.json, batter3d/assets/* 요청을 내장 문자열/data: URL로 답한다(GLTFLoader의 FileLoader도 fetch를 쓴다)
//       (2) ES 모듈 — 각 모듈 소스를 문자열로 넣고 실행 시 Blob URL을 만들어 import 지정자를 바꿔 끼운 뒤 어댑터를 import()한다(import map·외부 파일 없음)
//       (3) 기본 모델을 batter-ctl로 고정(파일 열 때 ?batter3d= 가 없으므로)
// 주의: 3D 모델 변환본이 파일 안에 들어간다 → 팀 내부 전달만. 출력은 저장소 밖(D:)에 둔다.
import { readFileSync, writeFileSync, mkdirSync } from "node:fs";
import { resolve, dirname } from "node:path";
import { fileURLToPath } from "node:url";

const here = dirname(fileURLToPath(import.meta.url));
const relay = resolve(here, "..");
const [, , version = "v2", outDir = "D:/pitcheezy_assets/build/demo"] = process.argv;
if (!["v1", "v2", "v2t", "v4"].includes(version)) { console.error("v1, v2, v2t 또는 v4"); process.exit(2); }
const read = (p) => readFileSync(resolve(relay, p), "utf8");
const b64 = (p) => readFileSync(resolve(relay, p)).toString("base64");
const safe = (s) => s.replace(/<\/script/gi, "<\\/script").replace(/<!--/g, "<\\!--"); // 인라인 <script> 안에서 HTML 파서가 끊지 않게
const lit = (s) => safe(JSON.stringify(s));

const htmlFile = version === "v1" ? "index.html" : version === "v2" ? "v2.html" : version === "v4" ? "v4.html" : "v2-tabs.html";
const cssFile = version === "v1" ? "relay.css" : version === "v4" ? "relay-v4.css" : "relay-v2.css";
const MODEL = version === "v4" ? "batter-ctl-v4" : "batter-ctl"; // v4는 나가기 동작이 든 별도 모델(v4.html이 data-batter3d-model로 고른다)
let html = read(htmlFile);
const css = read(cssFile);
const css3 = version === "v2t" ? read("relay-v2-tabs.css") : null; // v2t는 relay-v2.css 뒤에 relay-v2-tabs.css를 더 읽는다
const relayJs = read(version === "v4" ? "relay-v4.js" : "relay.js");
const host = read("batter3d-host.js").replace('const DEFAULT_MODEL = "batter-indexed";', 'const DEFAULT_MODEL = "batter-ctl"; // 단일 파일 데모: 사람형 캐릭터 고정');
if (!host.includes('DEFAULT_MODEL = "batter-ctl"')) throw new Error("DEFAULT_MODEL 치환 실패");
const mod = read("batter3d/batter3d.js");
const hostSrc = host.replace("./batter3d/batter3d.js?v=4", "./batter3d/batter3d.js"); // 어댑터의 판 표시(?v=4)를 떼고 Blob 주소로 바꿔 끼운다
const vendor = {
  core: read("batter3d/vendor/three.core.js"),
  three: read("batter3d/vendor/three.module.js"),
  bgu: read("batter3d/vendor/addons/utils/BufferGeometryUtils.js"),
  sk: read("batter3d/vendor/addons/utils/SkeletonUtils.js"),
  gltf: read("batter3d/vendor/addons/loaders/GLTFLoader.js"),
};
const data = read("data/849843.json");
const meta = read(`batter3d/assets/${MODEL}.meta.json`);
const glb = b64(`batter3d/assets/${MODEL}.glb`);

// --- HTML 수술: 스타일시트 인라인, relay.js 인라인(본문 끝), import map·모듈 태그 제거
html = html.replace(/<link rel="stylesheet" href="relay(?:-v2|-v4)?\.css\?v=\d+" \/>/, () => `<style>\n${css.replace(/<\/style/gi, "<\\/style")}\n</style>`);
if (!html.includes("<style>")) throw new Error("스타일시트 치환 실패");
if (css3 !== null) {
  html = html.replace(/<link rel="stylesheet" href="relay-v2-tabs\.css\?v=\d+" \/>/, () => `<style>\n${css3.replace(/<\/style/gi, "<\\/style")}\n</style>`);
  if ((html.match(/<style>/g) || []).length !== 2) throw new Error("v2t 스타일시트 치환 실패");
}
html = html.replace(/\s*<script src="relay(?:-v4)?\.js(?:\?v=\d+)?" defer><\/script>/, "");
html = html.replace(/\s*<script type="importmap">[\s\S]*?<\/script>/, "");
html = html.replace(/\s*<script type="module" src="batter3d-host\.js(?:\?v=\d+)?"><\/script>/, "");
if (/<script[^>]*\ssrc=|type="importmap"/.test(html)) throw new Error("스크립트 태그 제거 실패");
html = html.replace(/<title>([^<]*)<\/title>/, (m, t) => `<title>${t} — 단일 파일 데모</title>`);

const shim = `<script>
/* 단일 파일 데모: 네트워크 없이 내장 자료로 답하는 fetch 가로채기 */
(function () {
  var files = {
    "data/849843.json": { type: "application/json", text: ${lit(data)} },
    ${lit(`batter3d/assets/${MODEL}.meta.json`)}: { type: "application/json", text: ${lit(meta)} },
    ${lit(`batter3d/assets/${MODEL}.glb`)}: { type: "model/gltf-binary", b64: ${lit(glb)} }
  };
  var orig = window.fetch.bind(window);
  function key(input) {
    var s = typeof input === "string" ? input : (input && input.url) || String(input);
    s = s.split("#")[0].split("?")[0];
    try { var base = location.href.split("#")[0].split("?")[0].replace(/[^/]*$/, ""); if (s.indexOf(base) === 0) s = s.slice(base.length); } catch (e) {}
    return s.replace(/^\\.\\//, "");
  }
  window.fetch = function (input, init) {
    var f = files[key(input)];
    if (!f) return orig(input, init);
    if (f.b64) return orig("data:" + f.type + ";base64," + f.b64);
    return Promise.resolve(new Response(f.text, { status: 200, headers: { "Content-Type": f.type } }));
  };
  window.__PZ_SINGLE_FILE = { version: ${JSON.stringify(version)}, builtAt: ${JSON.stringify(new Date().toISOString())} };
})();
</script>`;

const modules = `<script>
/* 단일 파일 데모: ES 모듈을 Blob URL로 이어 붙인다(three.js r187 vendor → GLTFLoader → batter3d.js → batter3d-host.js) */
(function () {
  var src = { core: ${lit(vendor.core)}, three: ${lit(vendor.three)}, bgu: ${lit(vendor.bgu)}, sk: ${lit(vendor.sk)}, gltf: ${lit(vendor.gltf)}, mod: ${lit(mod)}, host: ${lit(hostSrc)} };
  var blob = function (code) { return URL.createObjectURL(new Blob([code], { type: "text/javascript" })); };
  var sub = function (code, from, to) { return code.replace(new RegExp("from\\\\s+['\\"]" + from.replace(/[.*+?^$()|[\\]\\\\/]/g, "\\\\$&") + "['\\"]", "g"), 'from "' + to + '"'); };
  var coreUrl = blob(src.core);
  var threeUrl = blob(sub(src.three, "./three.core.js", coreUrl));
  var bguUrl = blob(sub(src.bgu, "three", threeUrl));
  var skUrl = blob(sub(src.sk, "three", threeUrl));
  var gltfUrl = blob(sub(sub(sub(src.gltf, "three", threeUrl), "../utils/BufferGeometryUtils.js", bguUrl), "../utils/SkeletonUtils.js", skUrl));
  var modUrl = blob(sub(sub(src.mod, "three", threeUrl), "three/addons/loaders/GLTFLoader.js", gltfUrl));
  var hostUrl = blob(sub(src.host, "./batter3d/batter3d.js", modUrl));
  import(hostUrl).catch(function (e) { console.warn("3D 모듈 로딩 실패(SVG 타자 유지):", e && e.message || e); });
})();
</script>`;

// 순서: head 맨 앞 테마 스크립트 다음에 shim, 본문 끝에 relay.js(원래 defer) → 모듈 로더
html = html.replace("</head>", () => `${shim}\n</head>`); // 함수형 치환: 치환 문자열 안의 $' $& 같은 패턴이 해석되지 않게(three.js 소스에 $'가 있어 </html>가 끼어드는 사고가 났다)
html = html.replace("</body>", () => `<script>\n${safe(relayJs)}\n</script>\n${modules}\n</body>`);

mkdirSync(outDir, { recursive: true });
const out = resolve(outDir, `pitcheezy-relay-${version}-demo.html`);
writeFileSync(out, html, "utf8");
const bytes = Buffer.byteLength(html, "utf8");
console.log(`${out} ${bytes.toLocaleString()} B (${(bytes / 1048576).toFixed(2)} MB)`);

// 로컬 자산 서버 (개발 전용). D:\pitcheezy_assets 아래 파일을 읽어 주고(GET), 변환 결과를 build/ 아래에만 저장한다(POST).
// 127.0.0.1에만 묶고, CORS는 localhost 출처에만 연다. 외부 네트워크 요청은 없다. 의존 패키지 없음(Node 내장 모듈만).
// 실행: node tools/asset-server.mjs [포트]   (환경 변수 PZ_ASSETS로 루트, PORT로 포트 변경)
// 2026-11-08 단위 2: 잘못된 URL 인코딩(decodeURIComponent 예외)은 400으로 답하고 서버는 계속 돈다. 요청 처리 중 예외도 500으로 답한다.
import http from "node:http";
import fs from "node:fs";
import path from "node:path";

const ROOT = path.resolve(process.env.PZ_ASSETS || "D:\\pitcheezy_assets");
const PORT = Number(process.argv[2] || process.env.PORT || 8794); // 8791은 다른 launch 항목이 쓴다
const MIME = {
  ".fbx": "application/octet-stream", ".glb": "model/gltf-binary", ".gltf": "model/gltf+json", ".bin": "application/octet-stream",
  ".json": "application/json; charset=utf-8", ".png": "image/png", ".jpg": "image/jpeg", ".txt": "text/plain; charset=utf-8", ".md": "text/plain; charset=utf-8",
};

/** URL → ROOT 아래 절대 경로. 디코딩 실패(잘못된 % 표기)나 ROOT 밖이면 null */
function resolveSafe(url) {
  let rel;
  try { rel = decodeURIComponent(String(url).split("?")[0]); } catch (e) { return null; } // URIError → 400
  if (rel.includes("\0")) return null;
  rel = rel.replace(/^\/+/, "");
  const abs = path.resolve(ROOT, rel);
  return abs === ROOT || abs.startsWith(ROOT + path.sep) ? abs : null;
}

function handle(req, res) {
  const origin = req.headers.origin || "";
  const cors = {
    "Access-Control-Allow-Origin": /^http:\/\/(localhost|127\.0\.0\.1)(:\d+)?$/.test(origin) ? origin : "null",
    "Access-Control-Allow-Methods": "GET, POST, OPTIONS",
    "Access-Control-Allow-Headers": "Content-Type",
    "Cache-Control": "no-store",
  };
  if (req.method === "OPTIONS") { res.writeHead(204, cors); res.end(); return; }
  const abs = resolveSafe(req.url || "/");
  if (!abs) { res.writeHead(400, cors); res.end("bad path"); req.resume(); return; }

  if (req.method === "GET") {
    fs.stat(abs, (err, st) => {
      if (err) { res.writeHead(404, cors); res.end("not found"); return; }
      if (st.isDirectory()) {
        fs.readdir(abs, (e2, list) => { res.writeHead(200, { ...cors, "Content-Type": MIME[".json"] }); res.end(JSON.stringify(e2 ? [] : list)); });
        return;
      }
      res.writeHead(200, { ...cors, "Content-Type": MIME[path.extname(abs).toLowerCase()] || "application/octet-stream", "Content-Length": st.size });
      const rs = fs.createReadStream(abs);
      rs.on("error", () => { try { res.destroy(); } catch (e) { /* 무시 */ } });
      rs.pipe(res);
    });
    return;
  }

  if (req.method === "POST") { // 저장은 build/ 아래 .glb .json .png .jpg 만
    const rel = path.relative(ROOT, abs).replace(/\\/g, "/");
    if (!rel.startsWith("build/") || !/\.(glb|json|png|jpg)$/i.test(rel)) { res.writeHead(403, cors); res.end("only build/*.glb|json|png|jpg"); req.resume(); return; }
    fs.mkdirSync(path.dirname(abs), { recursive: true });
    const ws = fs.createWriteStream(abs);
    let bytes = 0, failed = false;
    const fail = (code, msg) => { if (failed) return; failed = true; try { ws.destroy(); } catch (e) { /* 무시 */ } fs.rm(abs, { force: true }, () => {}); res.writeHead(code, cors); res.end(msg); };
    req.on("data", (c) => { bytes += c.length; });
    req.on("error", () => fail(400, "request error")); // 끊긴 업로드는 반쪽 파일을 남기지 않는다
    ws.on("error", () => fail(500, "write error"));
    ws.on("finish", () => { if (failed) return; res.writeHead(200, { ...cors, "Content-Type": MIME[".json"] }); res.end(JSON.stringify({ saved: rel, bytes })); });
    req.pipe(ws);
    return;
  }
  res.writeHead(405, cors); res.end(); req.resume();
}

const server = http.createServer((req, res) => {
  try { handle(req, res); }
  catch (e) { // 처리 중 예외: 응답만 500으로 끝내고 서버는 계속 실행
    try { if (!res.headersSent) res.writeHead(500, { "Cache-Control": "no-store" }); res.end("server error"); } catch (e2) { /* 무시 */ }
    console.error("request error", e && e.message ? e.message : e);
  }
});
server.on("clientError", (err, socket) => { try { socket.end("HTTP/1.1 400 Bad Request\r\n\r\n"); } catch (e) { /* 무시 */ } });

server.listen(PORT, "127.0.0.1", () => { console.log(`asset server http://127.0.0.1:${PORT}/ root ${ROOT}`); });

// append-clips.mjs — 이미 만든 glb(사람형 batter-ctl)에 retarget-mixamo.mjs가 만든 클립 JSON을 애니메이션으로 덧붙여 새 glb를 쓴다(2026-11-09 V4, 의존 패키지 없음).
//   node append-clips.mjs <in.glb> <out.glb> <in.meta.json> <out.meta.json> <spec.json>
//   spec.json = { boneMap: {대상 원래 뼈 이름: glb 노드 이름}, refAnimation: "take", clips: [{ name, file, loops, rootScale, end, note, source }] }
// 하는 일: (1) 클립 JSON(three.js AnimationClip.toJSON)의 트랙 이름을 boneMap으로 glb 노드 이름에 맞춘다(변환기 fbx-to-glb.html과 같은 규칙).
//   (2) loops > 1이면 같은 주기를 이어 붙이고 골반 위치는 주기마다 앞으로 간 만큼 더한다(달리기·걷기 반복). rootScale은 골반 수평 이동(x, z)만 줄인다(틀 안에 오래 보이게; 발이 조금 미끄러짐).
//   (3) 노드 번호는 기준 애니메이션(refAnimation, 같은 도구로 옮긴 take)의 채널이 가리키는 노드를 그대로 쓴다(같은 이름 노드가 둘인 spine_03·neck_01도 같은 쪽).
//   (4) BIN 덩어리 끝에 시간·값 배열을 붙이고 accessor·sampler·channel을 더한다. 기존 바이트는 그대로 두고 덧붙이기만 한다.
// 메타: clips[name](길이·출처)과 play[name]({clip, cue: 0, end})을 더한다. 기존 항목은 바꾸지 않는다.
import { readFileSync, writeFileSync } from "node:fs";
import { createHash } from "node:crypto";

const [, , inGlb, outGlb, inMeta, outMeta, specFile] = process.argv;
if (!inGlb || !outGlb || !inMeta || !outMeta || !specFile) { process.stdout.write("사용: node append-clips.mjs <in.glb> <out.glb> <in.meta.json> <out.meta.json> <spec.json>\n"); process.exit(2); }
const sha = (buf) => createHash("sha256").update(buf).digest("hex");
const spec = JSON.parse(readFileSync(specFile, "utf8"));
const src = readFileSync(inGlb);
if (src.readUInt32LE(0) !== 0x46546c67) throw new Error("glb 아님");
const jsonLen = src.readUInt32LE(12); if (src.readUInt32LE(16) !== 0x4e4f534a) throw new Error("JSON 덩어리 없음");
const gltf = JSON.parse(src.subarray(20, 20 + jsonLen).toString("utf8"));
const binHead = 20 + jsonLen; const binLen = src.readUInt32LE(binHead); if (src.readUInt32LE(binHead + 4) !== 0x004e4942) throw new Error("BIN 덩어리 없음");
const bin0 = src.subarray(binHead + 8, binHead + 8 + binLen);
if (gltf.buffers.length !== 1) throw new Error("버퍼가 하나가 아님");

// 기준 애니메이션의 채널: "노드이름.경로" → 노드 번호
const ref = gltf.animations.find((a) => a.name === (spec.refAnimation || "take"));
if (!ref) throw new Error("기준 애니메이션 없음: " + spec.refAnimation);
const PATH = { rotation: "quaternion", translation: "position", scale: "scale" };
const nodeOf = new Map();
for (const ch of ref.channels) nodeOf.set(`${gltf.nodes[ch.target.node].name}.${PATH[ch.target.path]}`, ch.target.node);

const chunks = []; let off = binLen; const pad4 = (n) => (4 - (n % 4)) % 4;
function addBuffer(f32) {
  const p = pad4(off); if (p) { chunks.push(Buffer.alloc(p)); off += p; }
  const buf = Buffer.from(f32.buffer, f32.byteOffset, f32.byteLength); chunks.push(buf);
  const bv = gltf.bufferViews.push({ buffer: 0, byteOffset: off, byteLength: buf.length }) - 1; off += buf.length; return bv;
}
function addAccessor(f32, type, minmax) {
  const comps = { SCALAR: 1, VEC3: 3, VEC4: 4 }[type]; const count = f32.length / comps;
  const acc = { bufferView: addBuffer(f32), componentType: 5126, count, type };
  if (minmax) { const mn = Array(comps).fill(Infinity), mx = Array(comps).fill(-Infinity); for (let i = 0; i < count; i++) for (let k = 0; k < comps; k++) { const v = f32[i * comps + k]; if (v < mn[k]) mn[k] = v; if (v > mx[k]) mx[k] = v; } acc.min = mn; acc.max = mx; }
  return gltf.accessors.push(acc) - 1;
}

const meta = JSON.parse(readFileSync(inMeta, "utf8")); meta.clips = meta.clips || {}; meta.play = meta.play || {};
const report = [];
for (const c of spec.clips) {
  if (gltf.animations.some((a) => a.name === c.name)) throw new Error("이미 있는 애니메이션 이름: " + c.name);
  const raw = readFileSync(c.file); const clip = JSON.parse(raw.toString("utf8"));
  const loops = Math.max(1, c.loops | 0 || 1), rs = Number.isFinite(c.rootScale) ? c.rootScale : 1, dur = clip.duration;
  if (loops !== 1 || rs !== 1) throw new Error(`${c.name}: loops·rootScale은 retarget-mixamo.mjs(RETARGET_LOOPS·RETARGET_ROOT_SCALE)에서 월드 좌표로 하세요 — 골반 위치 트랙은 회전된 Root 로컬이라 여기서 x·z만 바꾸면 틀린다(독립 검토)`);
  const t0 = clip.tracks[0].times; // 모든 트랙이 같은 시간 축(retarget 도구가 30 fps로 균일 표본)
  for (const t of clip.tracks) if (t.times.length !== t0.length || t.times.some((v, i) => Math.abs(v - t0[i]) > 1e-6)) throw new Error(`${c.name}: 트랙마다 시간 축이 다름(${t.name})`);
  const nk = t0.length, times = [];
  for (let L = 0; L < loops; L++) for (let i = L === 0 ? 0 : 1; i < nk; i++) times.push(t0[i] + L * dur); // 다음 주기의 첫 키(= 앞 주기 끝과 같은 자세)는 뺀다
  const timeAcc = addAccessor(new Float32Array(times), "SCALAR", true);
  const anim = { name: c.name, channels: [], samplers: [] }; const missing = [];
  for (const t of clip.tracks) {
    const dot = t.name.indexOf("."); const bone = t.name.slice(0, dot), prop = t.name.slice(dot + 1);
    const key = `${(spec.boneMap && spec.boneMap[bone]) || bone}.${prop}`; const node = nodeOf.get(key);
    if (node === undefined) { missing.push(key); continue; }
    const comps = prop === "quaternion" ? 4 : 3, v = t.values, out = [];
    if (prop === "position") {
      const x0 = v[0], z0 = v[2], dx = v[(nk - 1) * 3] - x0, dz = v[(nk - 1) * 3 + 2] - z0;
      for (let L = 0; L < loops; L++) for (let i = L === 0 ? 0 : 1; i < nk; i++) { const x = v[i * 3] + L * dx, y = v[i * 3 + 1], z = v[i * 3 + 2] + L * dz; out.push(x0 + (x - x0) * rs, y, z0 + (z - z0) * rs); }
    } else {
      for (let L = 0; L < loops; L++) for (let i = L === 0 ? 0 : 1; i < nk; i++) for (let k = 0; k < comps; k++) out.push(v[i * comps + k]);
    }
    const s = anim.samplers.push({ input: timeAcc, output: addAccessor(new Float32Array(out), comps === 4 ? "VEC4" : "VEC3", false), interpolation: "LINEAR" }) - 1;
    anim.channels.push({ sampler: s, target: { node, path: prop === "quaternion" ? "rotation" : prop === "position" ? "translation" : "scale" } });
  }
  if (missing.length) throw new Error(`${c.name}: glb에 없는 트랙 ${missing.join(", ")}`);
  gltf.animations.push(anim);
  const total = times[times.length - 1], end = Number.isFinite(c.end) ? Math.min(c.end, total) : total;
  meta.clips[c.name] = { duration: total, source: { file: c.file.split(/[\\/]/).pop(), sha256: sha(raw), fbx: c.source || null, note: `${c.note || ""} tools/append-clips.mjs로 덧붙임(sha256은 클립 JSON)` } };
  meta.play[c.name] = { clip: c.name, cue: 0, end, note: c.playNote || "나가기 동작(11/9 V4): cue 0 = 재생 시작, end = 재생 끝. 선택 사항 — 없으면 어댑터 exit()가 null" };
  report.push({ name: c.name, tracks: anim.channels.length, keys: times.length, duration: +total.toFixed(4), loops, rootScale: rs });
}
gltf.buffers[0].byteLength = off;
const tail = Buffer.concat(chunks); const binNew = Buffer.concat([bin0, tail]); const binPad = pad4(binNew.length);
const jsonBuf = Buffer.from(JSON.stringify(gltf), "utf8"); const jsonPad = pad4(jsonBuf.length);
const total = 12 + 8 + jsonBuf.length + jsonPad + 8 + binNew.length + binPad;
const out = Buffer.alloc(total); let o = 0;
out.writeUInt32LE(0x46546c67, o); out.writeUInt32LE(2, o + 4); out.writeUInt32LE(total, o + 8); o += 12;
out.writeUInt32LE(jsonBuf.length + jsonPad, o); out.writeUInt32LE(0x4e4f534a, o + 4); o += 8; jsonBuf.copy(out, o); o += jsonBuf.length; out.fill(0x20, o, o + jsonPad); o += jsonPad;
out.writeUInt32LE(binNew.length + binPad, o); out.writeUInt32LE(0x004e4942, o + 4); o += 8; binNew.copy(out, o); o += binNew.length; out.fill(0, o, o + binPad);
// 기존 BIN 바이트가 그대로인지 확인
if (!out.subarray(20 + jsonBuf.length + jsonPad + 8, 20 + jsonBuf.length + jsonPad + 8 + binLen).equals(bin0)) throw new Error("기존 BIN 바이트가 달라짐");
writeFileSync(outGlb, out);
meta.appended = { at: new Date().toISOString(), tool: "relay/batter3d/tools/append-clips.mjs", from: { file: inGlb.split(/[\\/]/).pop(), sha256: sha(src) }, clips: report.map((r) => r.name) };
const outName = outGlb.split(/[\\/]/).pop();
meta.output = { ...(meta.output || {}), name: outName.replace(/\.glb$/, ""), glb: outName, meta: outMeta.split(/[\\/]/).pop(), glbBytes: out.length, glbSha256: sha(out), derivedFrom: meta.output && meta.output.glb ? { glb: meta.output.glb, glbSha256: meta.output.glbSha256 } : null };
writeFileSync(outMeta, JSON.stringify(meta, null, 1) + "\n", "utf8");
process.stdout.write(JSON.stringify({ in: { bytes: src.length, sha256: sha(src).slice(0, 12) }, out: { bytes: out.length, sha256: sha(out).slice(0, 12) }, animations: gltf.animations.map((a) => a.name), report }, null, 1) + "\n");

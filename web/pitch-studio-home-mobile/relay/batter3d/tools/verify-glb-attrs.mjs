// verify-glb-attrs.mjs — 인덱스화된 glb(후보)를 되풀어(unroll) 원본 glb와 모든 정점 속성을 바이트 단위로 대조한다.
// 사용: node verify-glb-attrs.mjs <원본.glb> <후보.glb>
// 검사: (1) 메시·프리미티브 수와 속성 집합(POSITION, NORMAL, TEXCOORD_n, JOINTS_n, WEIGHTS_n, …)이 같은가
//       (2) 후보의 각 속성을 indices로 되풀었을 때 원본과 요소별 바이트가 전부 같은가(componentType·normalized·type 포함)
//       (3) skins(joints 목록·inverseBindMatrices 바이트), animations(sampler input/output 바이트·채널 대상), materials JSON이 같은가
// 외부 의존 없음. 결과는 사람이 읽는 표와 종료 코드(0 전부 일치, 1 불일치, 2 사용 오류).
import fs from "node:fs";
import path from "node:path";
import crypto from "node:crypto";

const COMP = { 5120: [Int8Array, 1], 5121: [Uint8Array, 1], 5122: [Int16Array, 2], 5123: [Uint16Array, 2], 5125: [Uint32Array, 4], 5126: [Float32Array, 4] };
const NUM = { SCALAR: 1, VEC2: 2, VEC3: 3, VEC4: 4, MAT2: 4, MAT3: 9, MAT4: 16 };

function readGlb(file) {
  const buf = fs.readFileSync(file);
  if (buf.readUInt32LE(0) !== 0x46546c67) throw new Error(`${file}: glTF 매직 아님`);
  const version = buf.readUInt32LE(4), total = buf.readUInt32LE(8);
  if (version !== 2) throw new Error(`${file}: glb 버전 ${version}`);
  if (total !== buf.length) throw new Error(`${file}: 헤더 길이 ${total} ≠ 파일 ${buf.length}`);
  let off = 12, json = null, bin = null;
  while (off < buf.length) {
    const len = buf.readUInt32LE(off), type = buf.readUInt32LE(off + 4); const data = buf.subarray(off + 8, off + 8 + len);
    if (type === 0x4e4f534a) json = JSON.parse(data.toString("utf8")); else if (type === 0x004e4942) bin = data;
    off += 8 + len;
  }
  if (!json) throw new Error(`${file}: JSON 청크 없음`);
  return { file, bytes: buf.length, sha256: crypto.createHash("sha256").update(buf).digest("hex"), json, bin: bin || Buffer.alloc(0), jsonBytes: Buffer.byteLength(JSON.stringify(json)) };
}

/** 접근자(accessor)를 요소(element) 단위의 바이트 배열 목록으로 읽는다(stride 처리). 반환: { count, elemBytes, at(i) → Buffer } */
function accessorBytes(g, idx) {
  const a = g.json.accessors[idx];
  if (a.sparse) throw new Error(`accessor ${idx}: sparse 미지원`);
  const bv = g.json.bufferViews[a.bufferView];
  const [, compSize] = COMP[a.componentType]; const n = NUM[a.type]; const elemBytes = compSize * n;
  const stride = bv.byteStride || elemBytes; const base = (bv.byteOffset || 0) + (a.byteOffset || 0);
  if (base + (a.count - 1) * stride + elemBytes > (bv.byteOffset || 0) + bv.byteLength) throw new Error(`accessor ${idx}: bufferView 범위 초과`);
  return { count: a.count, elemBytes, componentType: a.componentType, type: a.type, normalized: !!a.normalized, min: a.min, max: a.max, at: (i) => g.bin.subarray(base + i * stride, base + i * stride + elemBytes), whole: () => { const out = Buffer.alloc(a.count * elemBytes); for (let i = 0; i < a.count; i++) g.bin.copy(out, i * elemBytes, base + i * stride, base + i * stride + elemBytes); return out; } };
}
function indicesOf(g, prim) {
  if (prim.indices === undefined) return null;
  const acc = accessorBytes(g, prim.indices); const [Ctor] = COMP[acc.componentType]; const raw = acc.whole();
  return { count: acc.count, componentType: acc.componentType, values: new Ctor(raw.buffer, raw.byteOffset, acc.count) };
}
const sha = (b) => crypto.createHash("sha256").update(b).digest("hex").slice(0, 16);

function meshList(g) {
  const out = [];
  (g.json.meshes || []).forEach((m, mi) => m.primitives.forEach((p, pi) => out.push({ mi, pi, name: m.name || `mesh${mi}`, prim: p })));
  return out;
}

function main() {
  const [origFile, candFile] = process.argv.slice(2);
  if (!origFile || !candFile) { console.error("사용: node verify-glb-attrs.mjs <원본.glb> <후보.glb>"); process.exit(2); }
  const A = readGlb(origFile), B = readGlb(candFile);
  const problems = [];
  const say = (s) => console.log(s);
  say(`원본 ${path.basename(A.file)}: ${A.bytes.toLocaleString()} B, SHA-256 ${A.sha256}`);
  say(`후보 ${path.basename(B.file)}: ${B.bytes.toLocaleString()} B, SHA-256 ${B.sha256}`);
  const ma = meshList(A), mb = meshList(B);
  if (ma.length !== mb.length) problems.push(`프리미티브 수 다름 ${ma.length} vs ${mb.length}`);
  say(`\n[정점 속성 대조] 프리미티브 ${ma.length}개`);
  for (let i = 0; i < Math.min(ma.length, mb.length); i++) {
    const pa = ma[i], pb = mb[i];
    const attrsA = Object.keys(pa.prim.attributes).sort(), attrsB = Object.keys(pb.prim.attributes).sort();
    const same = JSON.stringify(attrsA) === JSON.stringify(attrsB);
    say(`\n  ${pa.name} ↔ ${pb.name}: 속성 ${attrsA.join(", ")}${same ? "" : " ≠ 후보 " + attrsB.join(", ")}`);
    if (pa.name !== pb.name) problems.push(`프리미티브 ${i} 이름 다름 ${pa.name} vs ${pb.name}`);
    if (!same) { problems.push(`${pa.name}: 속성 집합 다름`); continue; }
    if (pa.prim.mode !== pb.prim.mode) problems.push(`${pa.name}: mode 다름`);
    if ((pa.prim.material === undefined) !== (pb.prim.material === undefined)) problems.push(`${pa.name}: material 유무 다름`);
    const ia = indicesOf(A, pa.prim), ib = indicesOf(B, pb.prim);
    if (ia) problems.push(`${pa.name}: 원본에 indices 있음(비인덱스 원본을 가정) — 되풀기 비교는 원본 indices도 되풀어 진행`);
    if (!ib) { problems.push(`${pb.name}: 후보에 indices 없음`); continue; }
    const vertsB = accessorBytes(B, pb.prim.attributes[attrsB[0]]).count;
    say(`    원본 정점 ${accessorBytes(A, pa.prim.attributes[attrsA[0]]).count.toLocaleString()} → 후보 정점 ${vertsB.toLocaleString()}, indices ${ib.count.toLocaleString()} (${ib.componentType === 5123 ? "Uint16" : ib.componentType === 5125 ? "Uint32" : "Uint8"})`);
    for (const name of attrsA) {
      const accA = accessorBytes(A, pa.prim.attributes[name]), accB = accessorBytes(B, pb.prim.attributes[name]);
      const meta = `${accA.type}/${accA.componentType}${accA.normalized ? "/norm" : ""}`;
      const metaB = `${accB.type}/${accB.componentType}${accB.normalized ? "/norm" : ""}`;
      if (meta !== metaB) { problems.push(`${pa.name}.${name}: 형식 다름 ${meta} vs ${metaB}`); say(`    ${name}: 형식 다름 ${meta} vs ${metaB}`); continue; }
      // 되풀기: 원본 요소 i ↔ 후보 요소 indices[i] (원본에 indices가 있으면 원본도 되풀어 비교)
      const nA = ia ? ia.count : accA.count;
      if (nA !== ib.count) { problems.push(`${pa.name}.${name}: 요소 수 다름 원본 ${nA} vs 후보 되풀기 ${ib.count}`); say(`    ${name}: 요소 수 다름 ${nA} vs ${ib.count}`); continue; }
      let mismatch = 0, first = -1;
      for (let i = 0; i < nA; i++) {
        const ea = accA.at(ia ? ia.values[i] : i), eb = accB.at(ib.values[i]);
        if (!ea.equals(eb)) { mismatch++; if (first < 0) first = i; }
      }
      const mm = accA.min && accB.min ? (JSON.stringify(accA.min) === JSON.stringify(accB.min) && JSON.stringify(accA.max) === JSON.stringify(accB.max) ? "min/max 일치" : "min/max 다름") : "min/max 없음";
      say(`    ${name.padEnd(10)} ${meta.padEnd(14)} 요소 ${nA.toLocaleString()} 되풀기 비교: ${mismatch === 0 ? "전부 일치" : `불일치 ${mismatch}개(첫 ${first})`} | 후보 고유 요소 SHA ${sha(accB.whole())} | ${mm}`);
      if (mismatch) problems.push(`${pa.name}.${name}: 불일치 ${mismatch}`);
      if (mm === "min/max 다름") problems.push(`${pa.name}.${name}: min/max 다름`);
    }
    // 후보 정점이 실제로 서로 다른지(합쳐지지 않은 중복이 남았는지)도 세어 본다 — 정보용
    const keys = new Set(); const accs = attrsB.map((n) => accessorBytes(B, pb.prim.attributes[n]));
    for (let v = 0; v < vertsB; v++) keys.add(accs.map((a) => a.at(v).toString("hex")).join("|"));
    say(`    후보 고유 정점(모든 속성 기준) ${keys.size.toLocaleString()} / ${vertsB.toLocaleString()}${keys.size === vertsB ? " (중복 없음)" : " (중복 " + (vertsB - keys.size) + ")"}`);
  }
  // skins
  say(`\n[스킨] 원본 ${(A.json.skins || []).length} / 후보 ${(B.json.skins || []).length}`);
  (A.json.skins || []).forEach((sa, i) => {
    const sb = (B.json.skins || [])[i]; if (!sb) { problems.push(`skin ${i} 후보에 없음`); return; }
    const ja = sa.joints.map((j) => A.json.nodes[j].name), jb = sb.joints.map((j) => B.json.nodes[j].name);
    const jointsSame = JSON.stringify(ja) === JSON.stringify(jb);
    const ibmA = sa.inverseBindMatrices !== undefined ? accessorBytes(A, sa.inverseBindMatrices).whole() : null, ibmB = sb.inverseBindMatrices !== undefined ? accessorBytes(B, sb.inverseBindMatrices).whole() : null;
    const ibmSame = ibmA && ibmB ? ibmA.equals(ibmB) : ibmA === ibmB;
    say(`  skin ${i}: joints ${ja.length}${jointsSame ? " 이름 순서 일치" : " 다름"}, inverseBindMatrices ${ibmSame ? "바이트 일치" : "다름"}`);
    if (!jointsSame) problems.push(`skin ${i}: joints 다름`); if (!ibmSame) problems.push(`skin ${i}: inverseBindMatrices 다름`);
  });
  // animations
  const anA = A.json.animations || [], anB = B.json.animations || [];
  say(`\n[애니메이션] 원본 ${anA.length} / 후보 ${anB.length}`);
  anA.forEach((a, i) => {
    const b = anB[i]; if (!b) { problems.push(`animation ${i} 후보에 없음`); return; }
    let bad = 0;
    if (a.name !== b.name || a.channels.length !== b.channels.length || a.samplers.length !== b.samplers.length) bad++;
    else for (let c = 0; c < a.channels.length; c++) {
      const ca = a.channels[c], cb = b.channels[c];
      if (ca.target.path !== cb.target.path || A.json.nodes[ca.target.node].name !== B.json.nodes[cb.target.node].name) { bad++; continue; }
      const sa = a.samplers[ca.sampler], sb = b.samplers[cb.sampler];
      if (sa.interpolation !== sb.interpolation) { bad++; continue; }
      if (!accessorBytes(A, sa.input).whole().equals(accessorBytes(B, sb.input).whole())) bad++;
      if (!accessorBytes(A, sa.output).whole().equals(accessorBytes(B, sb.output).whole())) bad++;
    }
    say(`  ${a.name}: 채널 ${a.channels.length}, ${bad === 0 ? "대상·보간·키프레임 바이트 일치" : "불일치 " + bad}`);
    if (bad) problems.push(`animation ${a.name}: 불일치 ${bad}`);
  });
  // materials, nodes
  const matSame = JSON.stringify(A.json.materials || []) === JSON.stringify(B.json.materials || []);
  say(`\n[materials] ${matSame ? "JSON 일치" : "다름"} (${(A.json.materials || []).length}개)`);
  if (!matSame) problems.push("materials 다름");
  const nodeNamesA = (A.json.nodes || []).map((n) => n.name), nodeNamesB = (B.json.nodes || []).map((n) => n.name);
  say(`[nodes] 원본 ${nodeNamesA.length} / 후보 ${nodeNamesB.length}, 이름 순서 ${JSON.stringify(nodeNamesA) === JSON.stringify(nodeNamesB) ? "일치" : "다름"}`);
  if (JSON.stringify(nodeNamesA) !== JSON.stringify(nodeNamesB)) problems.push("nodes 다름");
  say(`\n[JSON 청크] 원본 ${A.jsonBytes.toLocaleString()} B / 후보 ${B.jsonBytes.toLocaleString()} B; BIN 원본 ${A.bin.length.toLocaleString()} B / 후보 ${B.bin.length.toLocaleString()} B`);
  say(`\n결론: ${problems.length === 0 ? "모든 정점 속성·스킨·애니메이션·재질 일치" : problems.length + "건 문제"}`);
  for (const p of problems) say("  - " + p);
  process.exit(problems.length ? 1 : 0);
}
main();

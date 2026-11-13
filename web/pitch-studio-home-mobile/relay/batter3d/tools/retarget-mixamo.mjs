// retarget-mixamo.mjs — Mixamo(Without Skin) 동작 클립을 외부 구매 타자 모델 뼈대로 옮긴다(2026-11-09, 스트라이크·볼 반응 동작용).
//   node --import ./node-three.mjs retarget-mixamo.mjs <대상.fbx(스킨 포함, 예 ANIM_Idle.fbx)> <원본.fbx(Mixamo)> <출력.clip.json> [클립이름=take] [보고서.json]
// 방법: 두 뼈대의 '휴식 자세'(대상 = 스킨의 바인드 자세 A-pose, 원본 = 노드 자세 T-pose)를 기준으로
//   (1) 뼈마다 휴식 자세의 뼈 방향(부모→자식 월드 벡터)이 같아지도록 대상 휴식 회전을 돌려 맞추고(T/A 자세 차이 흡수),
//   (2) 프레임마다 원본 뼈의 '월드 회전 변화량'(현재 × 휴식⁻¹)을 그 맞춘 대상 휴식 회전에 곱해 대상 월드 회전으로 삼고,
//   (3) 위에서 아래로 부모 월드 회전을 나눠 대상 로컬 회전 트랙을 만든다. 골반 위치는 다리 길이 비율로 옮긴다.
// 두 뼈대 모두 Y 위, 정면 +z, 왼쪽 +x(측정값, 보고서에 기록)라 전역 회전은 두지 않는다. 뼈 축 규약(Mixamo Y축, UE계 X축)이 달라 로컬 회전 복사는 쓰지 않는다.
// 출력은 three.js AnimationClip JSON(대상 원래 뼈 이름). 변환기(fbx-to-glb.html) 'ctl' 프로필이 읽어 다른 클립과 같이 이름을 바꾸고 glb에 넣는다.
import { readFileSync, writeFileSync } from "node:fs";
import { basename } from "node:path";
import * as THREE from "three";
import { FBXLoader } from "three/addons/loaders/FBXLoader.js";

THREE.TextureLoader.prototype.load = function (url) { const t = new THREE.Texture(); t.name = String(url); return t; };
const warnings = []; console.warn = (...a) => warnings.push(a.join(" ").slice(0, 200)); console.error = console.warn;
const [, , targetFile, sourceFile, outFile, clipName = "take", reportFile = null] = process.argv;
if (!targetFile || !sourceFile || !outFile) { process.stdout.write("사용: node --import ./node-three.mjs retarget-mixamo.mjs <대상.fbx> <원본.fbx> <출력.json> [이름] [보고서]\n"); process.exit(2); }
const load = (f) => { const b = readFileSync(f); return new FBXLoader().parse(b.buffer.slice(b.byteOffset, b.byteOffset + b.byteLength), ""); };
const strip = (n) => n.replace(/^mixamorig\d*/, "");

// 대상 뼈 이름 → 원본(Mixamo, 접두 뺀) 뼈 이름
const NAMES = {
  Pelvis: "Hips", spine_01: "Spine", spine_02: "Spine1", spine_03: "Spine2", neck_01: "Neck", head: "Head",
  clavicle_l: "LeftShoulder", Upperarm_L: "LeftArm", lowerarm_l: "LeftForeArm", Hand_L: "LeftHand",
  clavicle_r: "RightShoulder", Upperarm_R: "RightArm", lowerarm_r: "RightForeArm", Hand_R: "RightHand",
  Thigh_L: "LeftUpLeg", calf_l: "LeftLeg", Foot_L: "LeftFoot", ball_l: "LeftToeBase",
  Thigh_R: "RightUpLeg", calf_r: "RightLeg", Foot_R: "RightFoot", ball_r: "RightToeBase",
};
for (const side of ["l", "r"]) {
  const M = side === "l" ? "Left" : "Right";
  for (const [f, m] of [["thumb", "Thumb"], ["index", "Index"], ["middle", "Middle"], ["ring", "Ring"], ["pinky", "Pinky"]]) for (const i of [1, 2, 3]) NAMES[`${f}_0${i}_${side}`] = `${M}Hand${m}${i}`;
}
// 뼈 방향을 정하는 자식(휴식 자세 정렬용). 없으면 방향 정렬 없이 회전 변화량만 적용
const DIR_CHILD = {
  Pelvis: "spine_01", spine_01: "spine_02", spine_02: "spine_03", spine_03: "neck_01", neck_01: "head",
  clavicle_l: "Upperarm_L", Upperarm_L: "lowerarm_l", lowerarm_l: "Hand_L", Hand_L: "middle_01_l", clavicle_r: "Upperarm_R", Upperarm_R: "lowerarm_r", lowerarm_r: "Hand_R", Hand_R: "middle_01_r",
  Thigh_L: "calf_l", calf_l: "Foot_L", Foot_L: "ball_l", Thigh_R: "calf_r", calf_r: "Foot_R", Foot_R: "ball_r",
};
for (const side of ["l", "r"]) for (const f of ["thumb", "index", "middle", "ring", "pinky"]) { DIR_CHILD[`${f}_01_${side}`] = `${f}_02_${side}`; DIR_CHILD[`${f}_02_${side}`] = `${f}_03_${side}`; }

const target = load(targetFile), source = load(sourceFile);
target.updateMatrixWorld(true); source.updateMatrixWorld(true);
const bonesOf = (root) => { const out = []; root.traverse((o) => { if (o.isBone) out.push(o); }); return out; };
const tBones = bonesOf(target), sBones = bonesOf(source);
// 대상: 같은 이름이 둘인 뼈(spine_03, neck_01)는 자식이 있는 쪽(실제 사슬)을 쓴다. 트랙 이름은 뼈 이름 그대로(원본 클립들과 같은 방식)
const byName = new Map(); const dupes = [];
for (const b of tBones) { const prev = byName.get(b.name); if (!prev) byName.set(b.name, b); else { dupes.push(b.name); if (b.children.length > prev.children.length) byName.set(b.name, b); } }
const sByName = new Map(); for (const b of sBones) sByName.set(strip(b.name), b);
// 대상 바인드 자세(월드): 스킨 메시들의 boneInverses⁻¹. 어느 스킨에도 없는 뼈는 노드 자세(정적이라 가정, 보고서에 표시)
const bindWorld = new Map(); const skins = []; target.traverse((o) => { if (o.isSkinnedMesh) skins.push(o); });
for (const m of skins) m.skeleton.bones.forEach((b, i) => { if (!bindWorld.has(b)) bindWorld.set(b, new THREE.Matrix4().copy(m.skeleton.boneInverses[i]).invert()); });
const noBind = tBones.filter((b) => !bindWorld.has(b)).map((b) => b.name);
for (const b of tBones) if (!bindWorld.has(b)) bindWorld.set(b, b.matrixWorld.clone());
const restWorldT = (b) => bindWorld.get(b);
const restWorldS = new Map(); for (const b of sBones) restWorldS.set(b, b.matrixWorld.clone());
const _dp = new THREE.Vector3(), _ds = new THREE.Vector3(); let scaleWarn = 0;
const qOf = (m) => { const q = new THREE.Quaternion(); m.decompose(_dp, q, _ds); if (Math.abs(_ds.x - 1) > 1e-3 || Math.abs(_ds.y - 1) > 1e-3 || Math.abs(_ds.z - 1) > 1e-3) scaleWarn++; return q; }; // decompose: 스케일이 섞인 행렬에서도 회전만(setFromRotationMatrix는 스케일 있으면 틀림, 11/9 독립 검토)
const pOf = (m) => new THREE.Vector3().setFromMatrixPosition(m);

// 선택(11/9 V4): RETARGET_MIRROR=1 = 원본 동작을 좌우 거울로(왼쪽 뼈 ↔ 오른쪽 뼈, x 반사). 좌타자는 화면에서 거울로 그려지므로, 원본 그대로의 모습을 좌타자에게 보이려면 데이터를 미리 거울로 둔다
const MIRROR = /^(1|true|yes)$/i.test(String(process.env.RETARGET_MIRROR || "")); // '0'·'false'는 끔(독립 검토)
// 뼈 쌍과 정렬 회전
const pairs = []; const missing = [];
for (const [tn, sn] of Object.entries(NAMES)) {
  const tb = byName.get(tn), sb = sByName.get(sn);
  if (!tb || !sb) { missing.push(`${tn}→${sn}${!tb ? "(대상 없음)" : ""}${!sb ? "(원본 없음)" : ""}`); continue; }
  const T0 = qOf(restWorldT(tb)), S0 = qOf(restWorldS.get(sb));
  const A = new THREE.Quaternion(); let aligned = false, alignDeg = 0;
  const cn = DIR_CHILD[tn]; const tc = cn && byName.get(cn), sc = cn && NAMES[cn] && sByName.get(NAMES[cn]);
  if (tc && sc) {
    const dT = pOf(restWorldT(tc)).sub(pOf(restWorldT(tb))), dS = pOf(restWorldS.get(sc)).sub(pOf(restWorldS.get(sb)));
    if (dT.lengthSq() > 1e-6 && dS.lengthSq() > 1e-6) { dT.normalize(); dS.normalize(); A.setFromUnitVectors(dT, dS); aligned = true; alignDeg = THREE.MathUtils.radToDeg(Math.acos(Math.min(1, Math.max(-1, dT.dot(dS))))); }
  }
  pairs.push({ tn, sn, tb, sb, T0, S0, A, aligned, alignDeg, base: A.clone().multiply(T0) /* 정렬된 대상 휴식 월드 회전 */ });
  { const snM = MIRROR ? (sn.startsWith("Left") ? "Right" + sn.slice(4) : sn.startsWith("Right") ? "Left" + sn.slice(5) : sn) : sn; const sbM = sByName.get(snM) || sb; const p = pairs[pairs.length - 1]; p.sbM = sbM; p.S0M = qOf(restWorldS.get(sbM)); if (MIRROR && sbM === sb && snM !== sn) missing.push(`거울 짝 없음 ${sn}→${snM}`); }
}
const pairOf = new Map(pairs.map((p) => [p.tb, p]));
// 다리 길이 비율(골반 → 발목, 휴식 자세)
const legT = pOf(restWorldT(byName.get("Pelvis"))).y - pOf(restWorldT(byName.get("Foot_L"))).y;
const legS = pOf(restWorldS.get(sByName.get("Hips"))).y - pOf(restWorldS.get(sByName.get("LeftFoot"))).y;
const ratio = legT / legS;
// 정면·좌우 확인(휴식 자세): 왼손 x 부호, 발·머리 z, 위 방향
const facing = (hand, foot, head, rest) => { const h = pOf(rest(hand)), f = pOf(rest(foot)), hd = pOf(rest(head)); return { leftHandX: +h.x.toFixed(1), leftFootZ: +f.z.toFixed(1), headZ: +hd.z.toFixed(1), up: hd.y > f.y }; };
const face = { target: facing(byName.get("Hand_L"), byName.get("Foot_L"), byName.get("head"), restWorldT), source: facing(sByName.get("LeftHand"), sByName.get("LeftFoot"), sByName.get("Head"), (b) => restWorldS.get(b)) };
// 전제 확인(틀리면 쓰지 않고 중단): 두 휴식 자세의 왼쪽(+x) 부호와 위 방향이 같아야 전역 회전 없이 월드 변화량을 옮길 수 있다
if (Math.sign(face.target.leftHandX) !== Math.sign(face.source.leftHandX) || face.target.up !== face.source.up || Math.abs(face.target.leftHandX) < 1 || Math.abs(face.source.leftHandX) < 1) {
  process.stdout.write(`중단: 휴식 자세 정면·좌우가 다르다(대상 왼손 x ${face.target.leftHandX}, 원본 ${face.source.leftHandX}; 위 ${face.target.up}/${face.source.up}). 전역 회전 정렬이 필요하다 — 이 도구는 그 경우를 지원하지 않는다.\n`); process.exit(1);
}
if (missing.length) process.stdout.write(`주의: 대응 못 한 뼈 ${missing.length}개 ${missing.join(", ")}\n`);

const order = []; target.traverse((o) => { if (o.isBone) order.push(o); }); // 깊이 우선 = 부모가 먼저
// 디버그: 정렬된 휴식 자세만(동작 변화량 없음)을 대상에 적용했을 때의 발·손 위치, 행렬 스케일
if (process.env.RETARGET_DEBUG) {
  const sc = (m) => { const s = new THREE.Vector3(); m.decompose(new THREE.Vector3(), new THREE.Quaternion(), s); return s.toArray().map((v) => +v.toFixed(3)); };
  for (const nm of ["Root", "Pelvis", "Thigh_L", "calf_l", "Foot_L", "Upperarm_L", "Hand_L"]) { const b = byName.get(nm); process.stdout.write(`${nm}: bindScale=${sc(restWorldT(b))} nodeScale=${sc(b.matrixWorld)} localScale=${b.scale.toArray().map((v) => +v.toFixed(3))} bindPos=${pOf(restWorldT(b)).toArray().map((v) => +v.toFixed(1))} nodePos=${pOf(b.matrixWorld).toArray().map((v) => +v.toFixed(1))} parent=${b.parent && b.parent.name}\n`); }
  for (const nm of ["Hips", "LeftUpLeg", "LeftLeg", "LeftFoot", "LeftArm"]) { const b = sByName.get(nm); process.stdout.write(`src ${nm}: scale=${sc(b.matrixWorld)} pos=${pOf(b.matrixWorld).toArray().map((v) => +v.toFixed(1))}\n`); }
  const worldNow = new Map();
  for (const b of order) { const p = pairOf.get(b); const Tw = p ? p.base.clone() : qOf(restWorldT(b)); worldNow.set(b, Tw); if (p) { const par = b.parent; const pq = par && par.isBone ? worldNow.get(par) : qOf(par ? par.matrixWorld : new THREE.Matrix4()); b.quaternion.copy(pq.clone().invert().multiply(Tw)); } }
  target.updateMatrixWorld(true);
  const W = (nm) => { const v = new THREE.Vector3(); byName.get(nm).getWorldPosition(v); return v.toArray().map((x) => +x.toFixed(1)); };
  process.stdout.write(`D=I(정렬 휴식만): Pelvis=${W("Pelvis")} Thigh_L=${W("Thigh_L")} calf_l=${W("calf_l")} Foot_L=${W("Foot_L")} Foot_R=${W("Foot_R")} Hand_L=${W("Hand_L")} Hand_R=${W("Hand_R")} head=${W("head")}\n`);
  // 바인드 자세 그대로(정렬 없이) 적용
  for (const b of order) { if (!b.parent || !b.parent.isBone) continue; b.quaternion.copy(qOf(restWorldT(b.parent)).invert().multiply(qOf(restWorldT(b)))); }
  target.updateMatrixWorld(true);
  process.stdout.write(`바인드 자세 재구성: Pelvis=${W("Pelvis")} Thigh_L=${W("Thigh_L")} calf_l=${W("calf_l")} Foot_L=${W("Foot_L")} Hand_L=${W("Hand_L")} head=${W("head")} (기대: 바인드 bindPos와 같아야)\n`);
  process.exit(0);
}

// 원본 샘플링(30 fps)
const clip = source.animations[0]; const fps = 30; const n = Math.max(2, Math.round(clip.duration * fps) + 1); const times1 = Array.from({ length: n }, (_, i) => Math.min(clip.duration, i / fps));
// 선택(11/9 V4): RETARGET_LOOPS = 주기 반복 수(골반은 주기마다 앞으로 간 만큼 이어서), RETARGET_ROOT_SCALE = 골반 수평 이동(월드 x, z) 배율(틀 안에 오래 보이게; 발이 조금 미끄러짐).
//   골반 위치 트랙은 부모(Root) 로컬 좌표라 축이 돌아가 있다(측정: 월드 −x 이동이 로컬 x·y·z에 나뉨) → 반드시 월드에서 바꾼 뒤 로컬로 옮긴다
// RETARGET_TIME_SCALE = 결과 시간 늘이기(1.5면 1.5배 느리게; 발 미끄러짐 없이 천천히 — 이동 배율만 줄이면 발이 미끄러진다는 독립 검토)
const envNum = (name, dflt, ok) => { const raw = process.env[name]; if (raw === undefined || String(raw).trim() === "") return dflt; const v = Number(raw); if (!Number.isFinite(v) || !ok(v)) { process.stdout.write(`중단: ${name}=${raw} 값이 잘못됐다\n`); process.exit(2); } return v; };
const LOOPS = envNum("RETARGET_LOOPS", 1, (v) => Number.isInteger(v) && v >= 1 && v <= 20), ROOT_SCALE = envNum("RETARGET_ROOT_SCALE", 1, (v) => v > 0 && v <= 2), TIME_SCALE = envNum("RETARGET_TIME_SCALE", 1, (v) => v >= 0.25 && v <= 4);
const samples = []; for (let L = 0; L < LOOPS; L++) for (let i = L === 0 ? 0 : 1; i < n; i++) samples.push({ t: times1[i] + L * clip.duration, ts: times1[i], L });
const times = samples.map((x) => x.t * TIME_SCALE);
const mixer = new THREE.AnimationMixer(source); const act = mixer.clipAction(clip); act.play();
const quat = new Map(pairs.map((p) => [p.tb, []])); const pelvisPos = [];
const pelvis = byName.get("Pelvis"), hips = sByName.get("Hips"), hipsRest = pOf(restWorldS.get(hips)), pelvisRest = pOf(restWorldT(pelvis));
const parentWorldQ = (b, worldNow) => { const par = b.parent; if (!par || !par.isBone) return qOf(par ? par.matrixWorld : new THREE.Matrix4()); return worldNow.get(par) || qOf(restWorldT(par)); };
// 선택(11/9 V4): RETARGET_YAW_DEG = 결과 동작 전체를 세로축으로 돌리는 각도(도). 달리기·옆걸음처럼 원본이 정면(+z)으로 움직이는 클립을 타자 틀의 원하는 방향으로 보낼 때.
//   골반 위 조상 뼈(Root)는 돌리지 않고 그 아래 모든 뼈의 월드 회전에 앞에서 곱한다(자식 로컬은 그대로, 골반 로컬만 바뀜). 골반 위치는 휴식 위치를 중심으로 돌린다. 없으면 0(기존과 같음)
const YAW_DEG = Number(process.env.RETARGET_YAW_DEG || 0); const qYaw = new THREE.Quaternion().setFromAxisAngle(new THREE.Vector3(0, 1, 0), THREE.MathUtils.degToRad(YAW_DEG));
const pelvisAncestors = new Set(); for (let a = byName.get("Pelvis").parent; a; a = a.parent) pelvisAncestors.add(a);
// 골반 월드 위치(비율·돌림 적용) — 반복·배율의 기준(첫 프레임)과 한 주기 이동량(끝 − 처음, 수평만)
const pelvisWorldAt = (ts) => { act.time = Math.min(ts, clip.duration - 1e-5); mixer.update(0); source.updateMatrixWorld(true); const hp = new THREE.Vector3().setFromMatrixPosition(hips.matrixWorld); const hoff = hp.sub(hipsRest); if (MIRROR) hoff.x = -hoff.x; const pw = hoff.multiplyScalar(ratio).add(pelvisRest); if (YAW_DEG) { const off = pw.clone().sub(pelvisRest); off.applyQuaternion(qYaw); pw.copy(pelvisRest).add(off); } return pw; };
const pw0 = pelvisWorldAt(0), pwEnd = pelvisWorldAt(clip.duration), cycle = new THREE.Vector3(pwEnd.x - pw0.x, 0, pwEnd.z - pw0.z);
for (const smp of samples) {
  const t = smp.ts;
  act.time = Math.min(t, clip.duration - 1e-5); mixer.update(0); source.updateMatrixWorld(true);
  const worldNow = new Map();
  for (const b of order) {
    const p = pairOf.get(b);
    if (!p) { const r = qOf(restWorldT(b)); worldNow.set(b, YAW_DEG && !pelvisAncestors.has(b) ? qYaw.clone().multiply(r) : r); continue; }
    const src = MIRROR ? p.sbM : p.sb, src0 = MIRROR ? p.S0M : p.S0;
    const S = new THREE.Quaternion().setFromRotationMatrix(src.matrixWorld); const D = S.multiply(src0.clone().invert());
    if (MIRROR) { D.y = -D.y; D.z = -D.z; } // 좌우 거울(x → −x 반사): 반대쪽 뼈의 월드 회전 변화량을 반사해 쓴다
    const Tw = D.multiply(p.base); if (YAW_DEG) Tw.premultiply(qYaw); worldNow.set(b, Tw);
    const local = parentWorldQ(b, worldNow).clone().invert().multiply(Tw).normalize(); quat.get(b).push(local.x, local.y, local.z, local.w); // clone: 부모의 저장된 월드 회전을 제자리에서 뒤집으면 다음 형제가 깨진다(첫 실행에서 다리가 위로 솟은 원인)
  }
  const hp = new THREE.Vector3().setFromMatrixPosition(hips.matrixWorld); const hoff = hp.sub(hipsRest); if (MIRROR) hoff.x = -hoff.x; const pw = hoff.multiplyScalar(ratio).add(pelvisRest);
  if (YAW_DEG) { const off = pw.clone().sub(pelvisRest); off.applyQuaternion(qYaw); pw.copy(pelvisRest).add(off); }
  if (LOOPS > 1 || ROOT_SCALE !== 1) { pw.x = pw0.x + (pw.x - pw0.x + smp.L * cycle.x) * ROOT_SCALE; pw.z = pw0.z + (pw.z - pw0.z + smp.L * cycle.z) * ROOT_SCALE; }
  const parM = pelvis.parent && pelvis.parent.isBone ? restWorldT(pelvis.parent) : (pelvis.parent ? pelvis.parent.matrixWorld : new THREE.Matrix4());
  const pl = pw.applyMatrix4(parM.clone().invert()); pelvisPos.push(pl.x, pl.y, pl.z);
}
const tracks = [];
for (const p of pairs) tracks.push(new THREE.QuaternionKeyframeTrack(`${p.tn}.quaternion`, times, quat.get(p.tb)));
tracks.push(new THREE.VectorKeyframeTrack("Pelvis.position", times, pelvisPos));
const out = new THREE.AnimationClip(clipName, times[times.length - 1], tracks); out.validate();
writeFileSync(outFile, JSON.stringify(THREE.AnimationClip.toJSON(out)), "utf8");

// 검사: 대상에서 결과 클립을 재생해 발·머리·손 위치를 본다(원본에 비율을 곱한 값과 나란히)
const mixerT = new THREE.AnimationMixer(target); const actT = mixerT.clipAction(out); actT.play();
const WB = (b) => { const v = new THREE.Vector3(); b.getWorldPosition(v); return v; };
const r1 = (v) => [v.x, v.y, v.z].map((x) => +x.toFixed(1));
const rows = []; let minAnkle = Infinity, maxAnkle = -Infinity, minToe = Infinity, headMin = Infinity, headMax = -Infinity;
for (const smp of samples) {
  const t = smp.t * TIME_SCALE;
  actT.time = Math.min(t, out.duration - 1e-5); mixerT.update(0); target.updateMatrixWorld(true);
  act.time = Math.min(smp.ts, clip.duration - 1e-5); mixer.update(0); source.updateMatrixWorld(true);
  const fl = WB(byName.get("Foot_L")), fr = WB(byName.get("Foot_R")), bl = WB(byName.get("ball_l")), br = WB(byName.get("ball_r")), hd = WB(byName.get("head")), hl = WB(byName.get("Hand_L")), hr = WB(byName.get("Hand_R")), pv = WB(pelvis);
  minAnkle = Math.min(minAnkle, fl.y, fr.y); maxAnkle = Math.max(maxAnkle, fl.y, fr.y); minToe = Math.min(minToe, bl.y, br.y); headMin = Math.min(headMin, hd.y); headMax = Math.max(headMax, hd.y);
  if (Math.abs(t * 4 - Math.round(t * 4)) < 1e-3 || t === times[times.length - 1]) {
    const sfl = WB(sByName.get("LeftFoot")), shd = WB(sByName.get("Head")), shl = WB(sByName.get("LeftHand")), shr = WB(sByName.get("RightHand")), shp = WB(hips);
    rows.push({ t: +t.toFixed(2), tgt: { pelvis: r1(pv), ankleY: [+fl.y.toFixed(1), +fr.y.toFixed(1)], toeY: [+bl.y.toFixed(1), +br.y.toFixed(1)], headY: +hd.y.toFixed(1), handGap: +hl.distanceTo(hr).toFixed(1), handL: r1(hl), handR: r1(hr), footL: r1(fl) },
      srcScaled: { hipsY: +(pelvisRest.y + (shp.y - hipsRest.y) * ratio).toFixed(1), ankleLY: +(sfl.y * ratio).toFixed(1), headY: +(shd.y * ratio).toFixed(1), handGap: +(shl.distanceTo(shr) * ratio).toFixed(1) } });
  }
}
// 대상 자체 대기 자세(ANIM_Idle t=0)와 결과 t=0의 차이(전환 시 튐 크기, cm)
const names = { handL: "Hand_L", handR: "Hand_R", head: "head", footL: "Foot_L", footR: "Foot_R", pelvis: "Pelvis" };
mixerT.stopAllAction(); const idleAct = mixerT.clipAction(target.animations[0]); idleAct.play(); idleAct.time = 0; mixerT.update(0); target.updateMatrixWorld(true);
const idlePose = Object.fromEntries(Object.entries(names).map(([k, nm]) => [k, WB(byName.get(nm))]));
mixerT.stopAllAction(); actT.reset().play(); actT.time = 0; mixerT.update(0); target.updateMatrixWorld(true);
const pop = Object.fromEntries(Object.entries(names).map(([k, nm]) => [k, +idlePose[k].distanceTo(WB(byName.get(nm))).toFixed(1)]));

const report = {
  tool: "relay/batter3d/tools/retarget-mixamo.mjs (three.js 0.187.0 FBXLoader, Node)", target: basename(targetFile), source: basename(sourceFile), out: outFile, clip: clipName,
  yawDeg: YAW_DEG, mirror: MIRROR, loops: LOOPS, rootScale: ROOT_SCALE, timeScale: TIME_SCALE, sourceClip: { name: clip.name, duration: +clip.duration.toFixed(4), tracks: clip.tracks.length }, outClip: { duration: +out.duration.toFixed(4), tracks: out.tracks.length, keys: times.length, keysPerCycle: n, fps: +(fps / TIME_SCALE).toFixed(3) },
  pairs: pairs.length, missing, duplicatesInTarget: [...new Set(dupes)], targetBonesWithoutBind: noBind, skins: skins.map((m) => `${m.name}(${m.skeleton.bones.length})`),
  rest: { targetPelvisY: +pelvisRest.y.toFixed(1), targetAnkleY: +pOf(restWorldT(byName.get("Foot_L"))).y.toFixed(1), sourceHipsY: +hipsRest.y.toFixed(1), sourceAnkleY: +pOf(restWorldS.get(sByName.get("LeftFoot"))).y.toFixed(1), legRatio: +ratio.toFixed(4), facing: face },
  align: Object.fromEntries(pairs.filter((p) => p.aligned).map((p) => [p.tn, +p.alignDeg.toFixed(1)])), notAligned: pairs.filter((p) => !p.aligned).map((p) => p.tn),
  result: { ankleY: [+minAnkle.toFixed(1), +maxAnkle.toFixed(1)], toeYmin: +minToe.toFixed(1), headY: [+headMin.toFixed(1), +headMax.toFixed(1)], popFromIdleCm: pop }, samples: rows, warnings: [...new Set(warnings)].slice(0, 10),
  scaledMatrices: scaleWarn, // 스케일이 1이 아닌 행렬에서 회전을 뽑은 횟수(0이 정상. 0이 아니면 decompose로 처리했지만 골반 위치 비율은 다시 볼 것)
};
if (scaleWarn) process.stdout.write(`주의: 스케일이 1이 아닌 행렬 ${scaleWarn}개(회전은 decompose로 뽑았다)\n`);
if (reportFile) writeFileSync(reportFile, JSON.stringify(report, null, 1), "utf8");
process.stdout.write(JSON.stringify({ ...report, samples: undefined }, null, 1) + "\n");
for (const r of rows) process.stdout.write(`t=${r.t} pelvis=${r.tgt.pelvis} ankleY=${r.tgt.ankleY} toeY=${r.tgt.toeY} headY=${r.tgt.headY}(src x${ratio.toFixed(2)}=${r.srcScaled.headY}) handGap=${r.tgt.handGap}(src ${r.srcScaled.handGap}) handL=${r.tgt.handL} handR=${r.tgt.handR} footL=${r.tgt.footL}\n`);

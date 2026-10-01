"""Build a self-contained hand-labeling page for catcher-mitt and plate front-edge points.

    python -m intent.label_pack --game 747139 --frames-root <checkout with outputs/frames> \
        --sample 40 --out outputs/intent_label/game_747139_pack.html

The page embeds JPEG crops of the selected decision frames, so it stays on the local disk
(``outputs/`` is git-ignored; the video is MLB's). The labeler sees no assistant marks. The
committed manifest (``docs/results/mlb_p0/game_<game>_intent_label_pack_v0.json``) holds only
pitch ids, frame hashes, crop boxes and the selection rule, so the labels can be checked later
without the images. Import the downloaded labels with ``python -m intent.human_labels``.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import io
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs/results/mlb_p0"
PACK_SCHEMA = "intent_label_pack_v0"
MAIN_BOX = (440, 120, 840, 400)  # x0, y0, x1, y1 in original 1280x720 pixels
MAIN_ZOOM = 2
PLATE_BOX = (520, 280, 820, 360)
PLATE_ZOOM = 4
JPEG_QUALITY = 90


def _sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def _spread(items, count):
    """Pick ``count`` items evenly spread over the ordered list (deterministic)."""
    if count <= 0 or not items:
        return []
    if count >= len(items):
        return list(items)
    if count == 1:
        return [items[len(items) // 2]]
    picks = sorted({round(i * (len(items) - 1) / (count - 1)) for i in range(count)})
    return [items[i] for i in picks]


def select_frames(points, sample, unavailable_share=0.2):
    """Evenly spread picks over estimated frames plus a share of assistant abstentions."""
    frames = sorted(points["frames"], key=lambda f: (f["at_bat_number"], f["pitch_number"]))
    estimated = [f for f in frames if f["status"] == "estimated"]
    unavailable = [f for f in frames if f["status"] != "estimated"]
    n_unavailable = min(len(unavailable), round(sample * unavailable_share))
    n_estimated = min(len(estimated), sample - n_unavailable)
    chosen = _spread(estimated, n_estimated) + _spread(unavailable, n_unavailable)
    return sorted(chosen, key=lambda f: (f["at_bat_number"], f["pitch_number"]))


def _crop_jpeg(image, box, zoom):
    from PIL import Image

    crop = image.crop(box)
    crop = crop.resize((crop.width * zoom, crop.height * zoom), Image.Resampling.LANCZOS)
    buffer = io.BytesIO()
    crop.save(buffer, format="JPEG", quality=JPEG_QUALITY)
    return "data:image/jpeg;base64," + base64.b64encode(buffer.getvalue()).decode("ascii")


def build_pack(points, frames_root, sample, *, verify_frames=True):
    """Return (manifest, page_frames): the committable manifest and the embedded page data."""
    from PIL import Image

    game_pk = points["game_pk"]
    selected = select_frames(points, sample)
    entries, page_frames = [], []
    for frame in selected:
        path = Path(frames_root) / frame["path"]
        data = path.read_bytes()
        if verify_frames and _sha256_bytes(data) != frame["image_sha256"]:
            raise ValueError(f"frame bytes changed for {frame['path']}")
        pitch_id = f"{game_pk}:{frame['at_bat_number']}:{frame['pitch_number']}"
        entries.append(
            {
                "pitch_id": pitch_id,
                "frame_seconds": frame["frame_seconds"],
                "path": frame["path"],
                "image_sha256": frame["image_sha256"],
                "assistant_status": frame["status"],
            }
        )
        with Image.open(io.BytesIO(data)) as image:
            image = image.convert("RGB")
            page_frames.append(
                {
                    "pitch_id": pitch_id,
                    "frame_seconds": frame["frame_seconds"],
                    "image_sha256": frame["image_sha256"],
                    "main": {
                        "box": list(MAIN_BOX),
                        "zoom": MAIN_ZOOM,
                        "src": _crop_jpeg(image, MAIN_BOX, MAIN_ZOOM),
                    },
                    "plate": {
                        "box": list(PLATE_BOX),
                        "zoom": PLATE_ZOOM,
                        "src": _crop_jpeg(image, PLATE_BOX, PLATE_ZOOM),
                    },
                }
            )
    body = json.dumps([[e["pitch_id"], e["image_sha256"]] for e in entries])
    manifest = {
        "schema": PACK_SCHEMA,
        "game_pk": game_pk,
        "pack_id": _sha256_bytes(body.encode("utf-8"))[:16],
        "selection": {
            "rule": "frames sorted by (at_bat_number, pitch_number); evenly spread picks over "
            "the assistant-estimated frames plus about 20 percent over the assistant "
            "abstentions; deterministic, no random seed",
            "sample": sample,
            "points_method": points.get("method"),
        },
        "crops": {
            "main": {"box": list(MAIN_BOX), "zoom": MAIN_ZOOM},
            "plate": {"box": list(PLATE_BOX), "zoom": PLATE_ZOOM},
        },
        "blind": "the page shows no assistant marks",
        "frames": entries,
    }
    return manifest, page_frames


PAGE = r"""<!doctype html>
<html lang="ko"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>미트 라벨링 __GAME__</title>
<style>
:root { --bg:#f3f5f1; --surface:#fff; --ink:#18212c; --muted:#5a6470; --line:#d5dad2; --accent:#2c6a50; --mark:#d0312d; --mark2:#1f6fd1; }
@media (prefers-color-scheme: dark) { :root { --bg:#12171d; --surface:#1a212a; --ink:#e5e9e3; --muted:#9aa4ae; --line:#2c3540; --accent:#72b996; --mark:#ff5a52; --mark2:#5aa2ff; color-scheme:dark; } }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.6 "Malgun Gothic","Apple SD Gothic Neo",system-ui,sans-serif; padding:16px; }
.wrap { max-width:1040px; margin:0 auto; display:grid; gap:14px; }
h1 { font-size:1.3rem; margin:0; }
.help { color:var(--muted); font-size:.92rem; margin:0; }
.bar { display:flex; flex-wrap:wrap; gap:8px; align-items:center; }
.bar .grow { flex:1; }
button { font:inherit; padding:6px 12px; border:1px solid var(--line); background:var(--surface); color:var(--ink); border-radius:4px; cursor:pointer; }
button.primary { background:var(--accent); color:var(--surface); border-color:var(--accent); }
button.on { outline:2px solid var(--mark); }
button:focus-visible { outline:2px solid var(--accent); outline-offset:2px; }
canvas { width:100%; height:auto; display:block; background:#000; cursor:crosshair; border:1px solid var(--line); }
.panel { background:var(--surface); border:1px solid var(--line); padding:12px; display:grid; gap:8px; }
.label { font-weight:600; }
.status { font-family:ui-monospace,Consolas,monospace; font-size:.88rem; color:var(--muted); }
.chips { display:flex; flex-wrap:wrap; gap:4px; }
.chip { width:26px; height:22px; font-size:.72rem; display:grid; place-items:center; border:1px solid var(--line); background:var(--surface); cursor:pointer; padding:0; }
.chip.done { background:var(--accent); color:var(--surface); border-color:var(--accent); }
.chip.cur { outline:2px solid var(--mark); }
input[type=text] { font:inherit; padding:5px 8px; border:1px solid var(--line); background:var(--surface); color:var(--ink); }
textarea { width:100%; height:120px; font:12px ui-monospace,Consolas,monospace; }
</style></head><body><div class="wrap">
<h1>포수 미트 · 플레이트 앞선 라벨링 (경기 __GAME__)</h1>
<p class="help">위 그림에서 <b>포수가 투수에게 내미는 미트(글러브)의 중심</b>을 한 번 클릭하세요. 아래 확대 그림에서 <b>홈플레이트 앞선(투수 쪽, 가장 아래 직선 모서리)의 왼쪽 끝과 오른쪽 끝</b>을 차례로 클릭하세요(다시 누르면 가까운 끝이 옮겨집니다). 미트가 안 보이거나 포수가 아직 앉지 않았으면 아래 버튼으로 표시합니다. 키: ← 이전, → 또는 Enter 다음. 진행 상황은 이 브라우저에 자동 저장됩니다. 다 하면 <b>라벨 JSON 내려받기</b>를 눌러 파일을 Claude에게 알려 주세요.</p>
<div class="bar"><label>라벨러 이름(선택) <input id="labeler" type="text" size="16"></label><span class="grow"></span><span id="progress" class="status"></span><span id="timer" class="status"></span></div>
<div class="chips" id="chips"></div>
<div class="panel"><div class="bar"><span class="label" id="title"></span><span class="grow"></span>
<button id="m-hidden" type="button">미트 안 보임(가림)</button><button id="m-setup" type="button">포수 셋업 아님</button><button id="m-camera" type="button">중앙 카메라 아님</button></div>
<canvas id="main"></canvas><div class="status" id="m-status"></div></div>
<div class="panel"><div class="bar"><span class="label">플레이트 앞선 (4배 확대)</span><span class="grow"></span><button id="p-hidden" type="button">플레이트 안 보임</button><button id="clear" type="button">이 프레임 지우기</button></div>
<canvas id="plate"></canvas><div class="status" id="p-status"></div></div>
<div class="bar"><button id="prev" type="button">← 이전</button><button id="next" type="button" class="primary">다음 →</button><span class="grow"></span><button id="export" type="button" class="primary">라벨 JSON 내려받기</button><button id="copy" type="button">JSON 복사</button></div>
<textarea id="out" hidden readonly></textarea>
</div>
<script>
const PACK = __PACK__;
const FRAMES = __FRAMES__;
const KEY = "intent-label-" + PACK.game_pk + "-" + PACK.pack_id;
let state = { labeler: "", elapsed_ms: 0, frames: {} };
try { const saved = JSON.parse(localStorage.getItem(KEY) || "null"); if (saved && saved.frames) state = saved; } catch (e) {}
let cur = 0; const imgs = {};
const $ = (id) => document.getElementById(id);
$("labeler").value = state.labeler || "";
$("labeler").addEventListener("input", () => { state.labeler = $("labeler").value; save(); });
function save() { try { localStorage.setItem(KEY, JSON.stringify(state)); } catch (e) {} }
function rec(id) { if (!state.frames[id]) state.frames[id] = { mitt: null, mitt_status: null, plate_front: null, plate_status: null }; return state.frames[id]; }
function done(r) { return r && r.mitt_status && r.plate_status && (r.plate_status !== "marked" || (r.plate_front && r.plate_front.left_end && r.plate_front.right_end)); }
function load(src) { if (!imgs[src]) { const im = new Image(); im.src = src; imgs[src] = im; } return imgs[src]; }
function toOrig(canvas, view, ev) { const r = canvas.getBoundingClientRect(); const sx = canvas.width / r.width; const x = (ev.clientX - r.left) * sx / view.zoom + view.box[0]; const y = (ev.clientY - r.top) * sx / view.zoom + view.box[1]; return [Math.round(x * 10) / 10, Math.round(y * 10) / 10]; }
function toView(view, p) { return [(p[0] - view.box[0]) * view.zoom, (p[1] - view.box[1]) * view.zoom]; }
function cross(ctx, p, color) { ctx.strokeStyle = color; ctx.lineWidth = 2; ctx.beginPath(); ctx.moveTo(p[0] - 10, p[1]); ctx.lineTo(p[0] + 10, p[1]); ctx.moveTo(p[0], p[1] - 10); ctx.lineTo(p[0], p[1] + 10); ctx.stroke(); ctx.beginPath(); ctx.arc(p[0], p[1], 6, 0, Math.PI * 2); ctx.stroke(); }
function draw() {
  const f = FRAMES[cur]; const r = rec(f.pitch_id); const css = getComputedStyle(document.documentElement);
  const mark = css.getPropertyValue("--mark").trim(); const mark2 = css.getPropertyValue("--mark2").trim();
  for (const [id, view] of [["main", f.main], ["plate", f.plate]]) {
    const c = $(id); const im = load(view.src);
    const paint = () => { c.width = im.naturalWidth; c.height = im.naturalHeight; const ctx = c.getContext("2d"); ctx.drawImage(im, 0, 0);
      if (id === "main" && r.mitt) cross(ctx, toView(view, r.mitt), mark);
      if (r.plate_front) { const ends = [r.plate_front.left_end, r.plate_front.right_end].filter(Boolean).map((p) => toView(view, p));
        ctx.strokeStyle = mark2; ctx.lineWidth = 2; if (ends.length === 2) { ctx.beginPath(); ctx.moveTo(ends[0][0], ends[0][1]); ctx.lineTo(ends[1][0], ends[1][1]); ctx.stroke(); }
        for (const e of ends) cross(ctx, e, mark2); } };
    if (im.complete && im.naturalWidth) paint(); else im.onload = paint;
  }
  $("title").textContent = f.pitch_id + "  ·  " + f.frame_seconds.toFixed(2) + " s";
  $("m-status").textContent = "미트: " + (r.mitt_status === "marked" ? "(" + r.mitt.join(", ") + ")" : (r.mitt_status || "아직 없음"));
  $("p-status").textContent = "앞선: " + (r.plate_status === "marked" ? JSON.stringify(r.plate_front) : (r.plate_status || "아직 없음"));
  for (const [id, st] of [["m-hidden", "hidden"], ["m-setup", "not_in_setup"], ["m-camera", "not_centre_field"]]) $(id).classList.toggle("on", r.mitt_status === st);
  $("p-hidden").classList.toggle("on", r.plate_status === "hidden");
  const n = FRAMES.filter((x) => done(state.frames[x.pitch_id])).length;
  $("progress").textContent = n + " / " + FRAMES.length + " 완료";
  $("chips").innerHTML = ""; FRAMES.forEach((x, i) => { const b = document.createElement("button"); b.type = "button"; b.className = "chip" + (done(state.frames[x.pitch_id]) ? " done" : "") + (i === cur ? " cur" : ""); b.textContent = i + 1; b.title = x.pitch_id; b.onclick = () => { cur = i; draw(); }; $("chips").appendChild(b); });
}
$("main").addEventListener("click", (ev) => { const f = FRAMES[cur]; const r = rec(f.pitch_id); r.mitt = toOrig($("main"), f.main, ev); r.mitt_status = "marked"; save(); draw(); });
$("plate").addEventListener("click", (ev) => { const f = FRAMES[cur]; const r = rec(f.pitch_id); const p = toOrig($("plate"), f.plate, ev);
  let pf = r.plate_front || { left_end: null, right_end: null };
  if (!pf.left_end) pf.left_end = p; else if (!pf.right_end) pf.right_end = p;
  else { const dl = Math.hypot(p[0] - pf.left_end[0], p[1] - pf.left_end[1]); const dr = Math.hypot(p[0] - pf.right_end[0], p[1] - pf.right_end[1]); if (dl < dr) pf.left_end = p; else pf.right_end = p; }
  if (pf.left_end && pf.right_end && pf.left_end[0] > pf.right_end[0]) pf = { left_end: pf.right_end, right_end: pf.left_end };
  r.plate_front = pf; r.plate_status = pf.left_end && pf.right_end ? "marked" : null; save(); draw(); });
for (const [id, st] of [["m-hidden", "hidden"], ["m-setup", "not_in_setup"], ["m-camera", "not_centre_field"]]) $(id).onclick = () => { const r = rec(FRAMES[cur].pitch_id); r.mitt = null; r.mitt_status = st; save(); draw(); };
$("p-hidden").onclick = () => { const r = rec(FRAMES[cur].pitch_id); r.plate_front = null; r.plate_status = "hidden"; save(); draw(); };
$("clear").onclick = () => { state.frames[FRAMES[cur].pitch_id] = { mitt: null, mitt_status: null, plate_front: null, plate_status: null }; save(); draw(); };
$("prev").onclick = () => { cur = Math.max(0, cur - 1); draw(); };
$("next").onclick = () => { cur = Math.min(FRAMES.length - 1, cur + 1); draw(); };
document.addEventListener("keydown", (ev) => { if (ev.target.tagName === "INPUT") return; if (ev.key === "ArrowLeft") $("prev").click(); if (ev.key === "ArrowRight" || ev.key === "Enter") $("next").click(); });
setInterval(() => { if (document.visibilityState === "visible") { state.elapsed_ms += 1000; if (state.elapsed_ms % 10000 === 0) save(); $("timer").textContent = Math.round(state.elapsed_ms / 60000) + "분"; } }, 1000);
function payload() { return { schema: "intent_human_labels_v0", game_pk: PACK.game_pk, pack_id: PACK.pack_id, labeler: state.labeler || null, exported_at: new Date().toISOString(), elapsed_seconds: Math.round(state.elapsed_ms / 1000),
  frames: FRAMES.map((f) => { const r = state.frames[f.pitch_id] || {}; return { pitch_id: f.pitch_id, frame_seconds: f.frame_seconds, image_sha256: f.image_sha256, mitt_status: r.mitt_status || null, mitt: r.mitt || null, plate_status: r.plate_status || null, plate_front: r.plate_status === "marked" ? r.plate_front : null }; }) }; }
$("export").onclick = () => { const text = JSON.stringify(payload(), null, 1); const a = document.createElement("a"); a.href = URL.createObjectURL(new Blob([text], { type: "application/json" })); a.download = "game_" + PACK.game_pk + "_intent_human_labels.json"; document.body.appendChild(a); a.click(); a.remove(); };
$("copy").onclick = () => { const text = JSON.stringify(payload(), null, 1); const out = $("out"); out.hidden = false; out.value = text; out.select(); try { navigator.clipboard.writeText(text); } catch (e) {} };
draw();
</script></body></html>
"""


def render_page(manifest, page_frames):
    pack = {"game_pk": manifest["game_pk"], "pack_id": manifest["pack_id"]}
    return (
        PAGE.replace("__GAME__", str(manifest["game_pk"]))
        .replace("__PACK__", json.dumps(pack))
        .replace("__FRAMES__", json.dumps(page_frames))
    )


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--game", type=int, required=True)
    parser.add_argument("--points", type=Path, default=None)
    parser.add_argument("--frames-root", type=Path, default=ROOT)
    parser.add_argument("--sample", type=int, default=40)
    parser.add_argument(
        "--out", type=Path, required=True, help="HTML page (keep it under outputs/)"
    )
    parser.add_argument("--manifest", type=Path, default=None)
    args = parser.parse_args(argv)
    points = json.loads(
        (args.points or RESULTS / f"game_{args.game}_intent_points_v0.json").read_text(
            encoding="utf-8-sig"
        )
    )
    if points.get("game_pk") != args.game:
        parser.error("points file is for another game")
    if "outputs" not in args.out.resolve().parts:
        parser.error("the page embeds MLB frames; write it under outputs/ (git-ignored)")
    manifest, page_frames = build_pack(points, args.frames_root, args.sample)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(render_page(manifest, page_frames), encoding="utf-8")
    manifest_path = args.manifest or RESULTS / f"game_{args.game}_intent_label_pack_v0.json"
    manifest_path.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
    )
    print(
        json.dumps(
            {
                "page": str(args.out),
                "page_bytes": args.out.stat().st_size,
                "manifest": str(manifest_path),
                "pack_id": manifest["pack_id"],
                "frames": len(manifest["frames"]),
                "assistant_status": {
                    s: sum(1 for f in manifest["frames"] if f["assistant_status"] == s)
                    for s in ("estimated", "unavailable")
                },
            },
            ensure_ascii=False,
            indent=1,
        )
    )


if __name__ == "__main__":
    main()

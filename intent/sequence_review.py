"""CV-34: offline human review of short pre-pitch sequences (development schema, no AI points).

A reviewer steps or plays one pitch's grid frames (10 fps) from near the window start up to the
release-nearest index (grid frames at or before it) and records, by hand:

* delivery start: the first frame where the pitcher's lead leg starts to lift (or none + reason);
* presentation: ``held_seen`` with the frames where the catcher holds the mitt still in one place,
  or ``no_clear_hold`` / ``not_determinable`` with a reason;
* for ``held_seen``, the mitt-body centre clicked on one frame inside that interval.

Centre reading (a point on one frame) and the temporal judgment (interval, state) are separate
fields and are scored separately. The page shows no AI points, AI states or outcome. Blinding
measures, and their limits:

* sequence ids are opaque, the id-to-pitch map stays outside the pack, frames are written in id
  order with one fixed modification time and content-addressed names;
* an optional crop (``--crop``) removes the score bug, which shows inning, count and pitch count;
* every source grid frame at or before the release-nearest index is retained. No model output
  chooses the review window; cropping removes pixels, not time. Random temporal trimming could
  hide the very hold interval being evaluated and is no longer used.

The pack is blind only for a reviewer who does not consult the repository's public 747139 timing,
points or result files: frame counts can be matched to public timing, and name graphics in
close-up frames can still reveal the batter. A held
interval that starts at frame 1 is left-censored and must be reported as such.

A seeded, pre-registered 25 percent of sequences is assigned to two reviewers for independent
agreement; it is reported apart from any disagreement follow-up. An AI never fills a response.

    python -m intent.sequence_review build --bundle outputs/cv_mitt_dev_20261025/bundle_v1 \
        --pack outputs/cv_mitt_review_seq_20261025/pack --private outputs/cv_mitt_review_seq_20261025/private \
        --crop 330,100,950,600
    python -m intent.sequence_review check --pack <pack> --response <response.json>
"""

from __future__ import annotations

import argparse
import hashlib
import html
import json
import math
import shutil
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
PACK_SCHEMA = "pitcheezy-mitt-sequence-review-pack-dev-v1"
RESPONSE_SCHEMA = "pitcheezy-mitt-sequence-review-response-dev-v1"
DRAFT_SCHEMA = "pitcheezy-mitt-sequence-review-draft-dev-v1"
PRESENTATION = ("unreviewed", "held_seen", "no_clear_hold", "not_determinable")
VISIBILITY = ("full", "partial", "hidden", "unknown")
ROW_KEYS = (
    "sequence_id",
    "delivery_start_n",
    "delivery_note",
    "presentation",
    "hold_start_n",
    "hold_end_n",
    "point_n",
    "mitt",
    "visibility",
    "reason",
)
DOUBLE_FRACTION = 0.25

INSTRUCTIONS = (
    "한 투구의 투구 전 장면을 순서대로 봅니다(10장/초). 결과·AI 점·판정은 보여 주지 않습니다. "
    "① 투수의 앞다리가 처음 들리기 시작하는 프레임을 '투구 동작 시작'으로 지정합니다. 안 보이면 비워 두고 이유를 적습니다. "
    "② 포수가 미트를 한 자리에 내밀고 멈춰 있는 구간이 보이면 '멈춘 구간 보임'을 고르고 시작·끝 프레임을 지정합니다. "
    "③ 그 구간 안의 한 프레임에서 미트 몸체의 가운데를 클릭합니다. "
    "멈춘 구간이 없거나 판단할 수 없으면 그 상태와 이유를 적습니다. 낮은 위치의 미트도 위치로만 봅니다. "
    "'쉬는 자세'나 투수의 의도는 판단하지 않습니다."
)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def sequence_id(pitch_id: str, salt: str) -> str:
    return "seq_" + hashlib.sha256(f"{salt}|{pitch_id}".encode()).hexdigest()[:10]


def double_assignment(sequence_ids, seed: str, fraction: float = DOUBLE_FRACTION):
    """Pre-registered two-reviewer sample: lowest seeded hashes, round(fraction * n) of them."""
    if not 0 < fraction < 1:
        raise ValueError("fraction must be between 0 and 1")
    ids = sorted(set(sequence_ids))
    count = max(1, round(fraction * len(ids))) if ids else 0
    ranked = sorted(ids, key=lambda s: hashlib.sha256(f"{seed}|{s}".encode()).hexdigest())
    return sorted(ranked[:count])


def blank_response(manifest, manifest_sha256):
    return {
        "schema": RESPONSE_SCHEMA,
        "manifest_sha256": manifest_sha256,
        "reviewer_id": "",
        "rows": [
            {
                "sequence_id": s["sequence_id"],
                "delivery_start_n": None,
                "delivery_note": "",
                "presentation": "unreviewed",
                "hold_start_n": None,
                "hold_end_n": None,
                "point_n": None,
                "mitt": None,
                "visibility": "unknown",
                "reason": "",
            }
            for s in manifest["sequences"]
        ],
    }


def _frame_no(value, name, count, sid):
    if value is None:
        return None
    if not isinstance(value, int) or isinstance(value, bool) or not 1 <= value <= count:
        raise ValueError(f"{sid}: {name} outside 1..{count}")
    return value


def validate_response(manifest, manifest_sha256, response, *, draft=False):
    """Python mirror of the page validator, used at intake. Raises ValueError."""

    def fail(message):
        raise ValueError(message)

    if not isinstance(response, dict) or set(response) != {
        "schema",
        "manifest_sha256",
        "reviewer_id",
        "rows",
    }:
        fail("response fields differ")
    if response["schema"] != RESPONSE_SCHEMA or response["manifest_sha256"] != manifest_sha256:
        fail("response schema or manifest hash differs")
    if not isinstance(response["reviewer_id"], str):
        fail("reviewer id must be text")
    sequences = {s["sequence_id"]: s for s in manifest["sequences"]}
    rows = response["rows"]
    if not isinstance(rows, list) or len(rows) != len(sequences):
        fail("row count differs")
    seen = set()
    for row in rows:
        if not isinstance(row, dict) or set(row) != set(ROW_KEYS):
            fail("row fields differ")
        seq = sequences.get(row["sequence_id"])
        if seq is None or row["sequence_id"] in seen:
            fail("unknown or duplicate sequence id")
        seen.add(row["sequence_id"])
        n = len(seq["frames"])

        start, end, point = (
            _frame_no(row[k], k, n, row["sequence_id"])
            for k in ("hold_start_n", "hold_end_n", "point_n")
        )
        _frame_no(row["delivery_start_n"], "delivery_start_n", n, row["sequence_id"])
        if row["presentation"] not in PRESENTATION or row["visibility"] not in VISIBILITY:
            fail("invalid presentation or visibility")
        if not isinstance(row["reason"], str) or not isinstance(row["delivery_note"], str):
            fail("reason and delivery_note must be text")
        if row["presentation"] == "held_seen":
            if not draft:
                if start is None or end is None or start > end:
                    fail(f"{row['sequence_id']}: held_seen needs start <= end")
                if point is None or not start <= point <= end:
                    fail(
                        f"{row['sequence_id']}: the centre frame must lie inside the held interval"
                    )
                if row["visibility"] not in ("full", "partial"):
                    fail(f"{row['sequence_id']}: a centre needs full or partial visibility")
                if row["visibility"] == "partial" and not row["reason"].strip():
                    fail(f"{row['sequence_id']}: partial visibility needs a reason")
            mitt = row["mitt"]
            if mitt is not None or not draft:
                frame = seq["frames"][(point or 1) - 1]
                if (
                    not isinstance(mitt, list)
                    or len(mitt) != 2
                    or not all(
                        isinstance(v, (int, float)) and not isinstance(v, bool) and math.isfinite(v)
                        for v in mitt
                    )
                    or not (0 <= mitt[0] < frame["width"] and 0 <= mitt[1] < frame["height"])
                ):
                    fail(f"{row['sequence_id']}: mitt point must lie inside the frame")
        else:
            if any(v is not None for v in (start, end, point, row["mitt"])):
                fail(f"{row['sequence_id']}: only held_seen carries an interval and a point")
            if not draft and row["presentation"] != "unreviewed" and not row["reason"].strip():
                fail(f"{row['sequence_id']}: a reason is required")
        if (
            not draft
            and row["presentation"] != "unreviewed"
            and row["delivery_start_n"] is None
            and not row["delivery_note"].strip()
        ):
            fail(f"{row['sequence_id']}: give the delivery start frame or a note why not")
    if (
        not draft
        and any(r["presentation"] != "unreviewed" for r in rows)
        and not response["reviewer_id"].strip()
    ):
        fail("reviewer id required")
    return response


def render_page(manifest, response, script_version="dev"):
    data = json.dumps(
        {"manifest": manifest, "response": response}, ensure_ascii=False, allow_nan=False
    )
    data = data.replace("<", "\\u003c")
    page = PAGE.replace("__SCRIPT_VERSION__", html.escape(script_version))
    page = page.replace("__COUNT__", str(len(manifest["sequences"])))
    page = page.replace("__INSTRUCTIONS__", html.escape(INSTRUCTIONS))
    return page.replace("__DATA__", data)


FIXED_MTIME = 1_700_000_000  # one constant modification time for every frame file and folder


def to_source_pixels(point, crop_box):
    """A point clicked on a cropped review frame, back in source-frame pixels."""
    if crop_box is None:
        return list(point)
    return [point[0] + crop_box[0], point[1] + crop_box[1]]


def build(
    bundle: Path,
    pack: Path,
    private: Path,
    pitch_ids=None,
    salt="cv34-seq-v1",
    seed="cv34-double-v1",
    crop_box=None,
):
    import os

    from PIL import Image

    from intent.mitt_dev_bundle import read_json

    if pack.exists() or private.exists():
        raise SystemExit("pack and private directories must be new")
    if private.resolve() in pack.resolve().parents or pack.resolve() in private.resolve().parents:
        raise SystemExit("the private map must not live inside the reviewer pack")
    manifest_in = read_json(bundle / "manifest.json")
    chosen = [p for p in manifest_in["pitches"] if p["status"] == "extracted"]
    if pitch_ids:
        chosen = [p for p in chosen if p["pitch_id"] in set(pitch_ids)]
    # write in opaque-id order so file creation order says nothing about pitch order
    chosen.sort(key=lambda p: sequence_id(p["pitch_id"], salt))
    sequences, mapping = [], []
    for p in chosen:
        sid = sequence_id(p["pitch_id"], salt)
        _, ab, pn = p["pitch_id"].split(":")
        frames = [
            f
            for f in p["frames"]
            if "grid" in f["roles"] and f["index"] <= p["window"]["release_index"]
        ]
        if len(frames) < 10:
            raise SystemExit(f"sequence {sid} has fewer than 10 pre-release grid frames")
        folder = pack / "frames" / sid
        folder.mkdir(parents=True)
        out_frames = []
        for n, f in enumerate(frames, start=1):
            src = bundle / f"pa{ab}_p{pn}" / f"frame_{f['index']:06d}.jpg"
            staging = folder / f"{n:03d}.tmp"
            if crop_box is None:
                shutil.copyfile(src, staging)
            else:
                with Image.open(src) as image:
                    image.crop(tuple(crop_box)).save(staging, format="JPEG", quality=92)
            # content-addressed name: a rebuilt frame never reuses a cached URL
            rel = f"frames/{sid}/{n:03d}_{sha256_file(staging)[:8]}.jpg"
            staging.replace(pack / rel)
            os.utime(pack / rel, (FIXED_MTIME, FIXED_MTIME))
            with Image.open(pack / rel) as image:
                width, height = image.size
            out_frames.append(
                {
                    "n": n,
                    "path": rel,
                    "sha256": sha256_file(pack / rel),
                    "width": width,
                    "height": height,
                    "seconds_from_start": round(
                        (f["index"] - frames[0]["index"]) * 1001 / 60000, 3
                    ),
                }
            )
        os.utime(folder, (FIXED_MTIME, FIXED_MTIME))
        sequences.append({"sequence_id": sid, "fps_nominal": 10, "frames": out_frames})
        mapping.append(
            {
                "sequence_id": sid,
                "pitch_id": p["pitch_id"],
                "frame_indices": [f["index"] for f in frames],
                "dropped_leading_grid_frames": 0,
                "dropped_trailing_grid_frames": 0,
            }
        )
    manifest = {
        "schema": PACK_SCHEMA,
        "scope": "development review of pre-pitch sequences; not an independent evaluation",
        "instructions": INSTRUCTIONS,
        "source_crop_box": list(crop_box) if crop_box else None,
        "sequences": sequences,
    }
    (pack / "manifest.json").write_text(
        json.dumps(manifest, indent=1, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    digest = sha256_file(pack / "manifest.json")
    double = double_assignment([s["sequence_id"] for s in sequences], seed)
    response = blank_response(manifest, digest)
    script_version = sha256_file(ROOT / "intent/sequence_review.js")[:12]
    (pack / "index.html").write_text(
        render_page(manifest, response, script_version), encoding="utf-8"
    )
    shutil.copyfile(ROOT / "intent/sequence_review.js", pack / "sequence_review.js")
    # frame files and folders share one time so they reveal no order; the page, script and
    # manifest keep real times so a browser never serves a stale copy of a rebuilt pack
    os.utime(pack / "frames", (FIXED_MTIME, FIXED_MTIME))
    private.mkdir(parents=True)
    (private / "private_map.json").write_text(
        json.dumps(
            {
                "manifest_sha256": digest,
                "salt": salt,
                "double_review_seed": seed,
                "double_review_fraction": DOUBLE_FRACTION,
                "double_review_sequences": double,
                "source_crop_box": list(crop_box) if crop_box else None,
                "mapping": mapping,
                "rule": "all source grid frames at or before release-nearest are retained; "
                "no temporal trimming or candidate-based selection; double-review assignment is seeded; "
                "frame counts can identify pitches when combined with public timing; "
                "double-review agreement is reported "
                "apart from disagreement follow-ups; with one reviewer only, inter-human agreement is "
                "incomplete; a held interval starting at frame 1 is left-censored",
            },
            indent=1,
        )
        + "\n",
        encoding="utf-8",
    )
    return manifest, digest, double


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)
    b = sub.add_parser("build")
    b.add_argument("--bundle", type=Path, required=True)
    b.add_argument("--pack", type=Path, required=True)
    b.add_argument("--private", type=Path, required=True)
    b.add_argument("--pitch", action="append")
    b.add_argument("--crop", help="x0,y0,x1,y1 source-pixel box shown to the reviewer")
    c = sub.add_parser("check")
    c.add_argument("--pack", type=Path, required=True)
    c.add_argument("--response", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.cmd == "build":
        for path in (args.pack, args.private):
            if "outputs" not in path.resolve().parts:
                parser.error("review packs embed broadcast frames; keep them under outputs/")
        crop = [int(v) for v in args.crop.split(",")] if args.crop else None
        manifest, digest, double = build(
            args.bundle, args.pack, args.private, args.pitch, crop_box=crop
        )
        print(
            json.dumps(
                {
                    "sequences": len(manifest["sequences"]),
                    "manifest_sha256": digest,
                    "double": len(double),
                }
            )
        )
    else:
        manifest = json.loads((args.pack / "manifest.json").read_text(encoding="utf-8"))
        digest = sha256_file(args.pack / "manifest.json")
        validate_response(manifest, digest, json.loads(args.response.read_text(encoding="utf-8")))
        print("response valid")


PAGE = """<!doctype html>
<html lang="ko"><head><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta http-equiv="Content-Security-Policy" content="default-src 'none'; img-src 'self';
style-src 'unsafe-inline'; script-src 'self'">
<title>투구 전 미트 연속 검토</title>
<style>
body{font:16px system-ui,sans-serif;max-width:1400px;margin:20px auto;padding:12px}
button,input,select,textarea{font:inherit;padding:6px;margin:3px}p,li{line-height:1.55}
#canvas{position:relative;display:inline-block;max-width:100%;line-height:0;cursor:crosshair}
#frame{display:block;max-width:100%;height:auto}#marker{position:absolute;width:14px;height:14px;
border:2px solid #ffdc00;border-radius:50%;transform:translate(-50%,-50%);pointer-events:none;
box-shadow:0 0 0 1px #000}#message{white-space:pre-wrap;color:#9c2100;min-height:1.5em}
.workspace{display:grid;grid-template-columns:minmax(0,1fr) 340px;gap:18px;align-items:start}
fieldset{padding:12px;position:sticky;top:12px;min-width:0}fieldset label{display:block;margin:8px 0}
.marks{font-family:monospace}#strip{display:flex;gap:2px;margin:6px 0;flex-wrap:wrap}
#strip span{width:10px;height:14px;background:#dde;display:inline-block}
#strip span.cur{background:#333}#strip span.hold{background:#7bc47f}#strip span.del{background:#e3a03b}
#warning{background:#fff5cc;padding:10px}.hint{font-size:14px;color:#445}
@media(max-width:900px){.workspace{grid-template-columns:1fr}fieldset{position:static}}
</style><script src="sequence_review.js?v=__SCRIPT_VERSION__" defer></script></head><body>
<h1>투구 전 미트 연속 검토 (__COUNT__구)</h1>
<details open><summary>검토 방법</summary><p>__INSTRUCTIONS__</p>
<p class="hint">키보드: ←/→ 한 프레임, 스페이스 재생/정지, D 투구 동작 시작, S 멈춘 구간 시작, E 멈춘 구간 끝.</p></details>
<p id="warning">자동 저장하지 않습니다. 닫기 전에 작업 초안 또는 제출용 응답을 저장하세요.
AI 점·판정·투구 결과는 이 페이지에 없습니다.</p>
<label>검토자 ID <input id="reviewer" autocomplete="off"></label>
<button id="draft-export" type="button">작업 초안 저장 · 제출용 아님</button>
<button id="export" type="button">제출용 응답 JSON 내보내기</button>
<label>저장한 응답 / 초안 불러오기 <input id="import" type="file" accept="application/json,.json"></label>
<div id="message" role="alert"></div>
<nav><button id="seq-prev" type="button">이전 투구</button><span id="seq-label"></span>
<button id="seq-next" type="button">다음 투구</button></nav>
<div class="workspace"><section>
<nav><button id="prev" type="button">◀ 프레임</button><button id="play" type="button">재생</button>
<button id="next" type="button">프레임 ▶</button><span id="frame-label" class="marks"></span></nav>
<div id="strip" aria-hidden="true"></div>
<div id="canvas"><img id="frame" alt="검토할 원본 프레임"><span id="marker" hidden></span></div>
<p id="coordinates" class="marks">미트 좌표 없음</p></section>
<fieldset><legend>이 투구의 사람 판정</legend>
<button id="mark-delivery" type="button">이 프레임 = 투구 동작 시작 (D)</button>
<button id="clear-delivery" type="button">투구 동작 시작 지우기</button>
<label>투구 동작 시작을 못 정한 이유 <input id="delivery-note"></label>
<label>멈춘 구간 <select id="presentation">
<option value="unreviewed">아직 검토하지 않음</option>
<option value="held_seen">미트를 한 자리에 멈춘 구간이 보임</option>
<option value="no_clear_hold">멈춘 구간이 분명하지 않음</option>
<option value="not_determinable">판단할 수 없음(화면·가림 등)</option></select></label>
<button id="mark-start" type="button">이 프레임 = 구간 시작 (S)</button>
<button id="mark-end" type="button">이 프레임 = 구간 끝 (E)</button>
<label>미트 가시성(중심 표시 프레임) <select id="visibility">
<option value="unknown">확신 없음 / 아직 선택 안 함</option><option value="full">전체가 보임</option>
<option value="partial">일부가 가려짐</option><option value="hidden">가려져 보이지 않음</option></select></label>
<p class="hint">중심은 구간 안의 한 프레임에서 미트 몸체 가운데를 클릭합니다. 보이지 않는 위치는 추측하지 않습니다.</p>
<p id="marks" class="marks"></p>
<label for="reason">이유 / 메모</label><textarea id="reason" rows="3" style="width:100%;box-sizing:border-box"></textarea>
</fieldset></div><script type="application/json" id="review-data">__DATA__</script>
</body></html>"""


if __name__ == "__main__":
    main()

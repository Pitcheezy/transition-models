"""Private CV49c sampled object-relation viewer; agreement never establishes truth."""

import argparse
import base64
import importlib.util
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.object_reference import (
    _box,
    _fields,
    _hex,
    _identity,
    _image_name,
    _integer,
    _text,
    loads_json,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "context_sequence_overlay", ROOT / "scripts/79_compare_object_references.py"
)
overlay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(overlay)
digest, xml = overlay.digest, overlay._xml
PITCHES = {f"849843:1:{n}" for n in range(1, 4)}
CROP = [450, 240, 660, 470]
MANIFEST_FIELDS = {
    "schema",
    "source_audit_sha256",
    "source_context_sha256",
    "selection_rule",
    "crop_xyxy",
    "sequences",
}
SEQUENCE_FIELDS = {
    "pitch_key",
    "play_id",
    "clip_sha256",
    "time_base",
    "first_pts",
    "release_lower_pts",
    "representative_pts",
    "frames",
}
FRAME_FIELDS = {
    "sample_index",
    "frame_pts",
    "image_sha256",
    "image_path",
    "crop_sha256",
    "crop_path",
}
RELATION_FIELDS = {
    "frame_pts",
    "image_sha256",
    "owner",
    "arm_wrist_link",
    "candidate_type",
    "attachment",
    "candidate_box",
    "reason",
}
ENUMS = {
    "temporal_relation": {"consistent_in_samples", "changed_or_occluded", "unclear"},
    "owner": {"catcher", "other", "unclear"},
    "arm_wrist_link": {"visible", "occluded", "unclear"},
    "candidate_type": {"mitt_like", "bare_hand", "gear", "unclear"},
    "attachment": {"wrist", "leg_or_torso", "unclear"},
}
LABELS = {
    "owner": {"catcher": "포수", "other": "다른 대상", "unclear": "불명"},
    "arm_wrist_link": {"visible": "직접 보임", "occluded": "가려짐", "unclear": "불명"},
    "candidate_type": {
        "mitt_like": "미트처럼 보임",
        "bare_hand": "맨손",
        "gear": "장비",
        "unclear": "불명",
    },
    "attachment": {"wrist": "손목", "leg_or_torso": "다리 또는 몸통", "unclear": "불명"},
    "temporal_relation": {
        "consistent_in_samples": "선택한 표본에서 관계가 일관됨",
        "changed_or_occluded": "관계 변화 또는 가림",
        "unclear": "표본 사이 관계 불명",
    },
}


def _enum(value, name):
    if type(value) is not str or value not in ENUMS[name]:
        raise ValueError(f"invalid {name}")


def _list(value, length, label):
    if type(value) is not list or len(value) != length:
        raise ValueError(f"{label}: expected exactly {length} entries")


def validate_manifest(data):
    _fields(data, MANIFEST_FIELDS, "manifest")
    if (
        data["schema"] != "cv49c_sequence_v1"
        or data["selection_rule"] != "first_mid_representative_mid_last"
    ):
        raise ValueError("wrong manifest schema or selection rule")
    _box(data["crop_xyxy"], 1280, 720, "crop_xyxy")
    if data["crop_xyxy"] != CROP:
        raise ValueError("context crop differs from the frozen crop")
    for name in ("source_audit_sha256", "source_context_sha256"):
        _hex(data[name], 64, name)
    _list(data["sequences"], 3, "sequences")
    seen, plays, paths = set(), set(), set()
    for seq in data["sequences"]:
        _fields(seq, SEQUENCE_FIELDS, "sequence")
        key = seq["pitch_key"]
        if type(key) is not str or key not in PITCHES or key in seen:
            raise ValueError("unexpected or duplicate pitch_key")
        seen.add(key)
        if seq["time_base"] != "1/90000":
            raise ValueError("time_base differs from the frozen clock")
        for name in ("first_pts", "release_lower_pts", "representative_pts"):
            _integer(seq[name], name)
        if seq["first_pts"] >= seq["release_lower_pts"]:
            raise ValueError("empty pre-release interval")
        _list(seq["frames"], 5, "frames")
        previous, previous_index = -1, -1
        for index, frame in enumerate(seq["frames"]):
            _fields(frame, FRAME_FIELDS, "frame")
            _integer(frame["sample_index"], "sample_index", 0, 4096)
            if frame["sample_index"] <= previous_index or (
                index == 0 and frame["sample_index"] != 0
            ):
                raise ValueError("sample_index must increase from zero")
            previous_index = frame["sample_index"]
            _identity({**seq, **frame}, 849843)
            pts = frame["frame_pts"]
            if not seq["first_pts"] <= pts < seq["release_lower_pts"] or pts <= previous:
                raise ValueError("frame PTS must increase and precede release cutoff")
            previous = pts
            _hex(frame["crop_sha256"], 64, "crop_sha256")
            for name in ("image_path", "crop_path"):
                _image_name(frame[name])
                path = frame[name].casefold()
                if path in paths:
                    raise ValueError("duplicate image path")
                paths.add(path)
        if seq["play_id"] in plays:
            raise ValueError("duplicate play_id")
        plays.add(seq["play_id"])
        if seq["frames"][2]["frame_pts"] != seq["representative_pts"]:
            raise ValueError("representative PTS must be the middle selected frame")
        indices = [frame["sample_index"] for frame in seq["frames"]]
        if indices[1] != indices[2] // 2 or indices[3] != (indices[2] + indices[4]) // 2:
            raise ValueError("sample indices do not follow the frozen midpoint rule")
    return data


def validate_reading(data, manifest, manifest_sha):
    validate_manifest(manifest)
    _hex(manifest_sha, 64, "manifest SHA")
    _fields(data, {"schema", "manifest_sha256", "reader", "model", "sequences"}, "reading")
    if data["schema"] != "cv49c_relations_v1" or data["manifest_sha256"] != manifest_sha:
        raise ValueError("reading schema or manifest SHA mismatch")
    for name in ("reader", "model"):
        _text(data[name], name)
    _list(data["sequences"], 3, "reading sequences")
    expected = {s["pitch_key"]: s for s in manifest["sequences"]}
    seen = set()
    for seq in data["sequences"]:
        _fields(
            seq, {"pitch_key", "temporal_relation", "sequence_note", "frames"}, "reading sequence"
        )
        key = seq["pitch_key"]
        if type(key) is not str or key not in expected or key in seen:
            raise ValueError("unknown or duplicate reading pitch")
        seen.add(key)
        _enum(seq["temporal_relation"], "temporal_relation")
        _text(seq["sequence_note"], "sequence_note", 2000)
        _list(seq["frames"], 5, "reading frames")
        frames = {f["frame_pts"]: f for f in expected[key]["frames"]}
        used = set()
        for row in seq["frames"]:
            _fields(row, RELATION_FIELDS, "relation")
            _integer(row["frame_pts"], "reading frame_pts")
            pts = row["frame_pts"]
            if (
                pts not in frames
                or pts in used
                or row["image_sha256"] != frames[pts]["image_sha256"]
            ):
                raise ValueError("reading frame PTS/hash binding mismatch")
            used.add(pts)
            for name in ("owner", "arm_wrist_link", "candidate_type", "attachment"):
                _enum(row[name], name)
            _text(row["reason"], "reason", 2000)
            box = row["candidate_box"]
            if row["candidate_type"] == "unclear" and box is not None:
                raise ValueError("unclear candidate must have null box")
            if box is not None:
                _box(box, 1280, 720, "candidate_box")
    return data


def evidence_complete(row):
    return (
        row["owner"] == "catcher"
        and row["arm_wrist_link"] == "visible"
        and row["candidate_type"] == "mitt_like"
        and row["attachment"] == "wrist"
        and row["candidate_box"] is not None
    )


def frame_svg(raw, rows, *, crop=False):
    x, y, width, height = (450, 240, 210, 230) if crop else (0, 0, 1280, 720)
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" viewBox="{x} {y} {width} {height}" role="img" aria-label="현재 프레임과 AI의 대략적 상자">',
        f'<image x="{x}" y="{y}" width="{width}" height="{height}" href="data:image/png;base64,{base64.b64encode(raw).decode()}"/>',
    ]
    for side, color in (("a", "#00e5ff"), ("b", "#ff5de4")):
        box = rows[side]["candidate_box"]
        if box is not None:
            left, top, right, bottom = box
            dash = ' stroke-dasharray="5 3"' if side == "b" else ""
            parts.append(
                f'<rect data-reader="{side}" x="{left}" y="{top}" width="{right - left}" height="{bottom - top}" fill="none" stroke="{color}" stroke-width="2"{dash}/>'
            )
    return "\n".join([*parts, "</svg>"])


def render_html(report, rasters):
    parts = [
        '<!doctype html><html lang="ko"><meta charset="utf-8"><meta name="viewport" content="width=device-width"><title>CV49c · 포수 문맥과 시간순 표본</title>',
        '<style>body{background:#101827;color:#e7eef9;font:16px system-ui;max-width:1300px;margin:auto;padding:24px}button,select{font:inherit;padding:9px;margin:4px}button[aria-pressed="true"]{outline:3px solid #00e5ff}.images{display:grid;grid-template-columns:3fr 1fr;gap:12px}.images svg{width:100%;max-height:650px;background:#060b13}.readings{display:grid;grid-template-columns:1fr 1fr;gap:20px}article{border:1px solid #64748b;padding:14px}[hidden]{display:none!important}p{line-height:1.6;overflow-wrap:anywhere}@media(max-width:700px){.images,.readings{grid-template-columns:1fr}}</style>',
        "<h1>포수 팔·손목·물체 관계 · 개발 검토</h1><p>처음 3장은 오식별 원인을 좁히는 진단 표본이었습니다. 이번에는 같은 3구에서 5장씩 고정했습니다. 사용자 판단 입력은 필요하지 않습니다. 시간순으로 팔·손목과 물체의 연결 근거 및 미해결 이유를 확인하세요.</p>",
        "<p>A 청록 실선 / B 분홍 점선: 서로 별개의 AI 대략적 상자. 일치해도 검증된 미트·정확도·포수 목표·투수 의도가 아닙니다. 원본 PTS의 간격 표본이며 연속 추적이나 실제 움직임 검증이 아닙니다. 뒤 시점까지 본 사후 개발 검토입니다.</p>",
        '<label>투구 <select id="pitch">'
        + "".join(
            f'<option value="{i}">{xml(s["pitch_key"])}</option>'
            for i, s in enumerate(report["sequences"])
        )
        + '</select></label><button id="previous">이전 장</button><span id="samples">'
        + "".join(f'<button data-sample="{i}">{i + 1}장</button>' for i in range(5))
        + '</span><button id="next">다음 장</button><p id="position" aria-live="polite"></p>',
    ]
    for si, seq in enumerate(report["sequences"]):
        for fi, row in enumerate(seq["frames"]):
            parts.append(
                f'<section class="frame" data-sequence="{si}" data-frame="{fi}" hidden><h2>{xml(seq["pitch_key"])} · {fi + 1}/5장 · PTS {row["frame_pts"]}</h2><p>마지막 참고 프레임(사후 판독): PTS {seq["available_after_pts"]} · 실시간 처리 시각을 측정한 값이 아닙니다 · 미트 검증: 미완료</p><div class="images">'
            )
            full, crop = rasters[(seq["pitch_key"], row["frame_pts"])]
            parts.extend(
                [
                    frame_svg(full, row["readings"]),
                    frame_svg(crop, row["readings"], crop=True),
                    '</div><div class="readings">',
                ]
            )
            for side in ("a", "b"):
                reading, author = row["readings"][side], report["readers"][side]
                details = " / ".join(
                    f"{label}: {LABELS[name][reading[name]]}"
                    for name, label in (
                        ("owner", "물체 소유자"),
                        ("arm_wrist_link", "팔·손목 연결"),
                        ("candidate_type", "물체 모양"),
                        ("attachment", "부착 부위"),
                    )
                )
                completeness = (
                    "기록 요건 충족(정답 검증 아님)"
                    if reading["evidence_complete"]
                    else "관계 근거 미완성"
                )
                parts.append(
                    f"<article><h3>{side.upper()} · {xml(author['reader'])} / {xml(author['model'])}</h3><p>{xml(details)}</p><p>{xml(completeness)}</p><p>{xml(reading['reason'])}</p><p>표본 간 관계: {xml(LABELS['temporal_relation'][seq['reading_sequences'][side]['temporal_relation']])}</p><p>{xml(seq['reading_sequences'][side]['sequence_note'])}</p></article>"
                )
            parts.append("</div></section>")
    parts.append("""<script>
(() => {
  const pitch = document.getElementById('pitch'); let frame = 0;
  function render() {
    document.querySelectorAll('.frame').forEach(panel => {
      panel.hidden = !(Number(panel.dataset.sequence) === Number(pitch.value) && Number(panel.dataset.frame) === frame);
    });
    document.querySelectorAll('[data-sample]').forEach(button => button.setAttribute('aria-pressed', String(Number(button.dataset.sample) === frame)));
    document.getElementById('previous').disabled = frame === 0;
    document.getElementById('next').disabled = frame === 4;
    document.getElementById('position').textContent = `${frame + 1}/5장 · 현재 프레임의 상자만 표시`;
  }
  pitch.addEventListener('change', () => { frame = 0; render(); });
  document.getElementById('samples').addEventListener('click', event => { if (event.target.dataset.sample !== undefined) { frame = Number(event.target.dataset.sample); render(); } });
  document.getElementById('previous').addEventListener('click', () => { frame = Math.max(0, frame - 1); render(); });
  document.getElementById('next').addEventListener('click', () => { frame = Math.min(4, frame + 1); render(); });
  render();
})();
</script></html>""")
    return "\n".join(parts).encode("utf-8")


def build_package(manifest_path, reading_a_path, reading_b_path, output, *, private_root=None):
    manifest_path, output = (
        overlay._without_links(Path(manifest_path)),
        overlay._without_links(Path(output)),
    )
    allowed = overlay._without_links(
        Path(private_root) if private_root is not None else ROOT / "outputs"
    ).resolve()
    try:
        relative = output.resolve().relative_to(allowed)
    except ValueError as exc:
        raise ValueError("output must be private outputs/cv49c_*") from exc
    if len(relative.parts) != 1 or not relative.name.startswith("cv49c_") or output.exists():
        raise ValueError("output must be a new private outputs/cv49c_* directory")
    raw = overlay._snapshot(manifest_path, overlay.JSON_LIMIT)
    manifest = validate_manifest(loads_json(raw))
    readings, reading_hashes = {}, {}
    for side, path in (("a", reading_a_path), ("b", reading_b_path)):
        content = overlay._snapshot(overlay._without_links(Path(path)), overlay.JSON_LIMIT)
        readings[side] = validate_reading(loads_json(content), manifest, digest(raw))
        reading_hashes[side] = digest(content)
    rasters, sequences = {}, []
    for seq in manifest["sequences"]:
        entries = {
            side: next(s for s in reading["sequences"] if s["pitch_key"] == seq["pitch_key"])
            for side, reading in readings.items()
        }
        frames = []
        for frame in seq["frames"]:
            images = []
            for prefix, size in (("image", (1280, 720)), ("crop", (210, 230))):
                images.append(
                    overlay._image_snapshot(
                        {
                            "image": frame[f"{prefix}_path"],
                            "image_sha256": frame[f"{prefix}_sha256"],
                            "width": size[0],
                            "height": size[1],
                            "pitch_key": seq["pitch_key"],
                        },
                        manifest_path.parent,
                    )
                )
            rasters[(seq["pitch_key"], frame["frame_pts"])] = images
            rows = {
                side: next(r for r in entry["frames"] if r["frame_pts"] == frame["frame_pts"])
                for side, entry in entries.items()
            }
            frames.append(
                {
                    **frame,
                    "verified_mitt": False,
                    "available_after_pts": seq["frames"][-1]["frame_pts"],
                    "readings": {
                        side: {
                            **row,
                            "evidence_complete": evidence_complete(row),
                            "verified_mitt": False,
                        }
                        for side, row in rows.items()
                    },
                }
            )
        sequences.append(
            {
                **seq,
                "available_after_pts": seq["frames"][-1]["frame_pts"],
                "reading_sequences": {
                    side: {k: entry[k] for k in ("temporal_relation", "sequence_note")}
                    for side, entry in entries.items()
                },
                "frames": frames,
            }
        )
    report = {
        "schema": "cv49c_comparison_v1",
        "manifest_sha256": digest(raw),
        "source_audit_sha256": manifest["source_audit_sha256"],
        "source_context_sha256": manifest["source_context_sha256"],
        "reading_sha256": reading_hashes,
        "readers": {
            side: {k: reading[k] for k in ("reader", "model")} for side, reading in readings.items()
        },
        "evidence_kind": "sampled_offline_ai_relations_not_identity_or_human_truth",
        "verified_mitt": False,
        "counts": {
            "sampled_frames": 15,
            "verified_mitt": 0,
            "readers": {
                side: {
                    "evidence_complete_frames": sum(
                        frame["readings"][side]["evidence_complete"]
                        for seq in sequences
                        for frame in seq["frames"]
                    ),
                    "unclear_candidate_frames": sum(
                        frame["readings"][side]["candidate_type"] == "unclear"
                        for seq in sequences
                        for frame in seq["frames"]
                    ),
                }
                for side in ("a", "b")
            },
        },
        "sequences": sequences,
    }
    html = render_html(report, rasters)
    report["artifacts"] = [{"path": "index.html", "sha256": digest(html)}]
    encoded = (json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    output.mkdir(parents=True)
    (output / "index.html").write_bytes(html)
    (output / "comparison.json").write_bytes(encoded)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "reading-a", "reading-b", "output"):
        parser.add_argument("--" + name, required=True, type=Path)
    args = parser.parse_args(argv)
    build_package(args.manifest, args.reading_a, args.reading_b, args.output)
    print("CV49c private sequence package built; verified mitt remains false.")


if __name__ == "__main__":
    main()

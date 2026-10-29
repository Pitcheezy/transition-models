"""Posthoc CV49b geometry comparison; never run or select a model from AI references."""

import argparse
import base64
import importlib.util
import json
import math
import re
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.object_reference import (
    IDENTITY_FIELDS,
    _iou,
    loads_json,
    validate_input,
    validate_reading,
)

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "object_overlay", ROOT / "scripts/79_compare_object_references.py"
)
overlay = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(overlay)
digest, xml = overlay.digest, overlay._xml


def snapshot(path):
    return overlay._snapshot(overlay._without_links(Path(path)), overlay.JSON_LIMIT)


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value):
        raise ValueError("finite numeric coordinate/score required")
    return value


def _response(value, frame, crop, plan):
    expected = {
        "schema": "local_glove_detection_v1",
        "coordinate_system": "original_image_pixels",
        "image_size": [1280, 720],
        "crop_xyxy": crop,
        "threshold": 0.5,
        "model_name": plan["model_name"],
        "weights_sha256": plan["weights_sha256"],
        "runtime_versions": plan["expected_runtime"],
        "device": "cuda",
        "threads": 4,
        "catcher_association_verified": False,
        "center_is_box_centroid_proxy": True,
    }
    if type(value) is not dict or any(value.get(k) != v for k, v in expected.items()):
        raise ValueError("engine response provenance/coordinates mismatch")
    detections = value.get("detections")
    if type(detections) is not list or len(detections) > 100:
        raise ValueError("bounded detection list required")
    seen = set()
    for detection in detections:
        if type(detection) is not dict:
            raise ValueError("detection must be an object")
        index = detection.get("detection_index")
        if type(index) is not int or not 0 <= index < 100 or index in seen:
            raise ValueError("duplicate/invalid detection index")
        seen.add(index)
        box = detection.get("box_xyxy")
        if type(box) is not list or len(box) != 4:
            raise ValueError("box requires four source coordinates")
        left, top, right, bottom = map(_number, box)
        if not (0 <= left < right <= frame["width"] and 0 <= top < bottom <= frame["height"]):
            raise ValueError("box outside source image")
        score = _number(detection["score"])
        if (
            not 0 <= score <= 1
            or detection.get("label") != 40
            or detection.get("category") != "baseball glove"
            or detection.get("above_threshold") is not (score >= 0.5)
        ):
            raise ValueError("invalid glove detection/threshold")
    candidates = [d for d in detections if d["above_threshold"]]
    status = (
        "no_candidate" if not candidates else "candidate" if len(candidates) == 1 else "ambiguous"
    )
    if value.get("selection_status") != status or value.get("candidate") != (
        candidates[0] if len(candidates) == 1 else None
    ):
        raise ValueError("engine candidate/status mismatch")
    return value


def _svg(frame, row, references, image):
    raster = base64.b64encode(image).decode("ascii")
    scene = frame["pitch_key"].replace(":", "_") + "_" + row["view"]
    parts = [
        '<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1280 1230">',
        "<style>text{font:13px sans-serif;paint-order:stroke;stroke:#111;stroke-width:2px}</style>",
        f'<defs><g id="{scene}">',
        f'<image width="1280" height="720" href="data:image/png;base64,{raster}"/>',
    ]
    boxes = []
    for side, color in (("a", "#00e5ff"), ("b", "#ff5de4")):
        for obj in references[side]["objects"]:
            symbol = {"mitt": "M", "bare_hand": "H", "protective_gear": "G"}[obj["kind"]]
            boxes.extend((box, color, f"{side.upper()} {symbol}", 1) for box in obj["boxes"])
    boxes.extend(
        (
            d["box_xyxy"],
            "#ffdf00" if d["above_threshold"] else "#aaa",
            f"D{d['detection_index']} score {d['score']:.4f}",
            2,
        )
        for d in row["engine_response"]["detections"]
    )
    for box, color, label, weight in boxes:
        x, y, right, bottom = box
        parts.append(
            f'<rect x="{x}" y="{y}" width="{right - x}" height="{bottom - y}" fill="none" stroke="{color}" stroke-width="{weight}"/>'
        )
        parts.append(f'<text x="{x}" y="{max(13, y - 3)}" fill="{color}">{xml(label)}</text>')
    parts += [
        f'</g></defs><use href="#{scene}"/>',
        '<text x="10" y="750" fill="white">Same fixed context crop; source coordinates retained</text>',
        f'<svg x="0" y="765" width="420" height="460" viewBox="450 240 210 230" overflow="hidden"><use href="#{scene}"/></svg>',
        "</svg>",
    ]
    return "\n".join(parts)


def export_comparison(
    plan_path,
    input_path,
    run_path,
    reading_a_path,
    reading_b_path,
    destination,
    *,
    private_root=None,
):
    """Accept only a complete, frozen six-attempt run and export an inert local report."""
    destination = overlay._without_links(Path(destination))
    allowed = overlay._without_links(
        Path(private_root) if private_root else ROOT / "outputs"
    ).resolve()
    if (
        destination.exists()
        or destination.parent.resolve() != allowed
        or re.fullmatch(r"cv49b_[A-Za-z0-9_-]+", destination.name) is None
    ):
        raise ValueError("fresh outputs/cv49b_* directory required")
    paths = [plan_path, input_path, run_path, reading_a_path, reading_b_path]
    raw_plan, raw_input, raw_run, raw_a, raw_b = [snapshot(p) for p in paths]
    plan, manifest, run = (
        loads_json(raw_plan),
        validate_input(loads_json(raw_input)),
        loads_json(raw_run),
    )
    input_sha = digest(raw_input)
    if (
        plan.get("schema") != "pitcheezy-glove-diagnostic-plan-v1"
        or plan.get("input_sha256") != input_sha
        or plan.get("model_name") != "fasterrcnn_mobilenet_v3_large_fpn"
        or plan.get("threshold") != 0.5
        or manifest["game_pk"] != 849843
        or len(manifest["frames"]) != 3
    ):
        raise ValueError("frozen CV49b plan/input mismatch")
    readings = {"a": loads_json(raw_a), "b": loads_json(raw_b)}
    for side, raw, slot in (("a", raw_a, "codex"), ("b", raw_b, "claude")):
        if digest(raw) != plan["readings_sha256"][slot]:
            raise ValueError("reading SHA mismatch")
        validate_reading(readings[side], manifest, input_sha)
    if readings["a"]["reviewer_id"] == readings["b"]["reviewer_id"]:
        raise ValueError("distinct saved readers required")
    if (
        run.get("schema") != "pitcheezy-glove-diagnostic-result-v1"
        or run.get("status") != "completed"
        or run.get("plan_sha256") != digest(raw_plan)
        or run.get("input_sha256") != input_sha
        or run.get("frozen_inputs_unchanged") is not True
        or run.get("first_error") is not None
        or run.get("counts") != {"completed": 6, "error": 0, "not_run": 0}
        or run.get("planned_predictions") != 6
        or len(run.get("frames", [])) != 6
    ):
        raise ValueError("complete frozen six-attempt report required")
    checks = run.get("frozen_checks")
    if (
        not isinstance(checks, list)
        or not checks
        or any(
            c.get("unchanged") is not True or c.get("expected_sha256") != c.get("actual_sha256")
            for c in checks
        )
    ):
        raise ValueError("frozen source checks failed")
    run_dir = Path(run_path).parent
    if snapshot(run_dir / "plan.json") != raw_plan or snapshot(run_dir / "input.json") != raw_input:
        raise ValueError("saved run plan/input mismatch")
    frames = {f["pitch_key"]: f for f in manifest["frames"]}
    if set(frames) != {f"849843:1:{i}" for i in (1, 2, 3)}:
        raise ValueError("fixed first-PA keys required")
    images = {
        key: overlay._image_snapshot(frame, Path(input_path).parent)
        for key, frame in frames.items()
    }
    refs = {
        side: {f["pitch_key"]: f for f in reading["frames"]} for side, reading in readings.items()
    }
    compared, seen, cards = [], set(), []
    for index, row in enumerate(run["frames"]):
        key, view = row.get("pitch_key"), row.get("view")
        if key not in frames or view not in ("full_frame", "context_crop") or (key, view) in seen:
            raise ValueError("duplicate/unknown prediction identity")
        seen.add((key, view))
        frame = frames[key]
        if (
            (frame["width"], frame["height"], frame["context_crop"])
            != (1280, 720, [450, 240, 660, 470])
            or any(row.get(k) != frame[k] for k in IDENTITY_FIELDS)
            or row.get("status") != "completed"
            or row.get("error") is not None
        ):
            raise ValueError("prediction identity/status mismatch")
        crop = None if view == "full_frame" else frame["context_crop"]
        if row.get("crop_xyxy") != crop or row.get("attempt_file") != f"attempts/{index:02d}.json":
            raise ValueError("prediction crop/attempt binding mismatch")
        attempt = snapshot(run_dir / row["attempt_file"])
        if digest(attempt) != row["attempt_sha256"] or loads_json(attempt) != {
            k: v for k, v in row.items() if k not in ("attempt_file", "attempt_sha256")
        }:
            raise ValueError("attempt SHA/content mismatch")
        engine = _response(row["engine_response"], frame, crop, plan)
        overlaps = []
        for side in ("a", "b"):
            for obj in refs[side][key]["objects"]:
                overlaps.append(
                    {
                        "reader": side,
                        "kind": obj["kind"],
                        "reference_status": obj["status"],
                        "reference_boxes": obj["boxes"],
                        "detection_indices": [d["detection_index"] for d in engine["detections"]],
                        "pairwise_ious": [
                            [_iou(d["box_xyxy"], b) for b in obj["boxes"]]
                            for d in engine["detections"]
                        ]
                        if obj["status"] == "located"
                        else None,
                    }
                )
        compared.append({**row, "geometric_comparisons": overlaps})
        svg = _svg(frame, row, {side: refs[side][key] for side in refs}, images[key])
        rows = "".join(
            f"<tr><td>{xml(o['reader'])}</td><td>{xml(o['kind'])}</td><td>{xml(o['reference_status'])}</td><td>{xml(json.dumps(o['pairwise_ious']))}</td></tr>"
            for o in overlaps
        )
        cards.append(
            (
                key,
                f"<section><h3>{xml(view)} · {xml(engine['selection_status'])}</h3>{svg}<table><tr><th>Reader</th><th>Object</th><th>Status</th><th>All detection × reference IoUs</th></tr>{rows}</table></section>",
            )
        )
    report = {
        "schema": "pitcheezy-glove-candidate-comparison-v1",
        "plan_sha256": digest(raw_plan),
        "input_sha256": input_sha,
        "run_sha256": digest(raw_run),
        "reading_a_sha256": digest(raw_a),
        "reading_b_sha256": digest(raw_b),
        "frame_count": 3,
        "condition_count": 6,
        "accuracy_measured": False,
        "human_comparison_measured": False,
        "frames": compared,
    }
    html = '<!doctype html><html lang="ko"><meta charset="utf-8"><title>CV49b · local glove candidates</title><style>body{background:#111827;color:#eee;font:16px system-ui;margin:24px}article>div{display:grid;grid-template-columns:1fr 1fr;gap:18px}svg{width:100%}table{font-size:12px;table-layout:fixed;width:100%;overflow-wrap:anywhere}td{border:1px solid #555}section{min-width:0}</style><h1>CV49b · 3 frames / 6 conditions</h1><p>비공개 AI 개발 비교. 정확도·사람 평가 미측정. IoU는 영역 겹침이며 미트 식별·포수 목표·투수 의도 검증이 아닙니다. A 청록 / B 자홍, M 미트·H 맨손·G 보호 장비. 검출은 노랑(점수 ≥0.5)·회색(미만). 점수는 정확도가 아닙니다. 모든 검출을 보존하며 참고 상자와의 거리로 선택하지 않습니다.</p>'
    html += "".join(
        f"<article><h2>{xml(key)}</h2><div>{''.join(card for k, card in cards if k == key)}</div></article>"
        for key in frames
    )
    html += "</html>"
    destination.mkdir(parents=True, exist_ok=False)
    (destination / "comparison.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    (destination / "index.html").write_text(html, encoding="utf-8")
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "input", "run", "reading-a", "reading-b", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    export_comparison(args.plan, args.input, args.run, args.reading_a, args.reading_b, args.out)


if __name__ == "__main__":
    main()

import base64
import importlib.util
import json
import re
from pathlib import Path

import pytest
from PIL import Image

from intent.local_glove_detector import select_glove_detections
from src.data.object_reference import (
    COORDINATE_SYSTEM,
    IDENTITY_FIELDS,
    INPUT_SCHEMA,
    KINDS,
    READING_SCHEMA,
)

SPEC = importlib.util.spec_from_file_location(
    "glove_comparison",
    Path(__file__).resolve().parents[1] / "scripts/81_compare_glove_candidates.py",
)
cli = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cli)


def save(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


@pytest.fixture
def bundle(tmp_path):
    source = tmp_path / "source"
    source.mkdir()
    manifest = {
        "schema": INPUT_SCHEMA,
        "source_commit": "a" * 40,
        "source_review_sha256_lf": "b" * 64,
        "game_pk": 849843,
        "frames": [],
    }
    for i in (1, 2, 3):
        path = source / f"f{i}.png"
        Image.new("RGB", (1280, 720), (20 * i, 0, 0)).save(path)
        manifest["frames"].append(
            {
                "pitch_key": f"849843:1:{i}",
                "play_id": f"00000000-0000-0000-0000-00000000000{i}",
                "clip_sha256": str(i) * 64,
                "frame_pts": i,
                "time_base": "1/90000",
                "image": path.name,
                "image_sha256": cli.digest(path.read_bytes()),
                "width": 1280,
                "height": 720,
                "context_crop": [450, 240, 660, 470],
            }
        )
    input_path = source / "input.json"
    save(input_path, manifest)
    input_sha = cli.digest(input_path.read_bytes())
    readings = []
    for side in ("a", "b"):
        reading = {
            "schema": READING_SCHEMA,
            "input_sha256": input_sha,
            "reviewer_id": side,
            "model": "synthetic",
            "prior_exposure": "synthetic",
            "coordinate_system": COORDINATE_SYSTEM,
            "frames": [
                {
                    **{k: f[k] for k in IDENTITY_FIELDS},
                    "objects": [
                        {
                            "kind": kind,
                            "status": "located" if kind == "mitt" else "unclear",
                            "boxes": [[460, 250, 480, 270]] if kind == "mitt" else [],
                            "reason": "synthetic <script>",
                        }
                        for kind in KINDS
                    ],
                }
                for f in manifest["frames"]
            ],
        }
        path = source / f"{side}.json"
        save(path, reading)
        readings.append(path)
    plan = {
        "schema": "pitcheezy-glove-diagnostic-plan-v1",
        "input_sha256": input_sha,
        "model_name": "fasterrcnn_mobilenet_v3_large_fpn",
        "threshold": 0.5,
        "weights_sha256": "c" * 64,
        "expected_runtime": {"torch": "2.6.0+cu124", "torchvision": "0.21.0+cu124"},
        "readings_sha256": {
            slot: cli.digest(p.read_bytes())
            for slot, p in zip(("codex", "claude"), readings, strict=True)
        },
    }
    plan_path = source / "plan.json"
    save(plan_path, plan)
    run_dir = source / "run"
    (run_dir / "attempts").mkdir(parents=True)
    (run_dir / "input.json").write_bytes(input_path.read_bytes())
    (run_dir / "plan.json").write_bytes(plan_path.read_bytes())
    report = {
        "schema": "pitcheezy-glove-diagnostic-result-v1",
        "plan_sha256": cli.digest(plan_path.read_bytes()),
        "input_sha256": input_sha,
        "status": "completed",
        "frozen_inputs_unchanged": True,
        "first_error": None,
        "counts": {"completed": 6, "error": 0, "not_run": 0},
        "planned_predictions": 6,
        "frozen_checks": [
            {"unchanged": True, "expected_sha256": "c" * 64, "actual_sha256": "c" * 64}
        ],
        "frames": [],
    }
    for frame in manifest["frames"]:
        for view in ("full_frame", "context_crop"):
            crop = None if view == "full_frame" else frame["context_crop"]
            boxes = (
                [[460.5, 250.5, 480.5, 270.5], [500, 300, 510, 310]]
                if crop is None
                else [[10.5, 10.5, 30.5, 30.5], [50, 60, 60, 70]]
            )
            engine = select_glove_detections(
                boxes, [0.8, 0.2], [40, 40], image_size=[1280, 720], crop=crop
            )
            engine.update({k: plan[k] for k in ("model_name", "weights_sha256")})
            engine.update(runtime_versions=plan["expected_runtime"], device="cuda", threads=4)
            row = {
                **{k: frame[k] for k in IDENTITY_FIELDS},
                "view": view,
                "crop_xyxy": crop,
                "status": "completed",
                "error": None,
                "engine_response": engine,
            }
            name = f"attempts/{len(report['frames']):02d}.json"
            save(run_dir / name, row)
            report["frames"].append(
                {
                    **row,
                    "attempt_file": name,
                    "attempt_sha256": cli.digest((run_dir / name).read_bytes()),
                }
            )
    run_path = run_dir / "result.json"
    save(run_path, report)
    private = tmp_path / "outputs"
    return [plan_path, input_path, run_path, *readings, private / "cv49b_compare"], private


def run(bundle):
    return cli.export_comparison(*bundle[0], private_root=bundle[1])


def test_complete_run_preserves_floats_all_detections_and_never_offsets_crop_twice(bundle):
    report = run(bundle)
    rows = report["frames"]
    assert (report["frame_count"], report["condition_count"]) == (3, 6)
    assert report["accuracy_measured"] is report["human_comparison_measured"] is False
    for row in rows:
        assert len(row["engine_response"]["detections"]) == 2
        assert row["engine_response"]["detections"][0]["box_xyxy"] == [460.5, 250.5, 480.5, 270.5]
        assert row["engine_response"]["selection_status"] == "candidate"
        assert row["geometric_comparisons"][1]["pairwise_ious"] is None
    assert rows[0]["geometric_comparisons"] == rows[1]["geometric_comparisons"]
    html = (bundle[0][-1] / "index.html").read_text(encoding="utf-8")
    assert "<script" not in html
    scenes = re.findall(r'<g id="([^"]+)"', html)
    assert len(scenes) == len(set(scenes)) == 6
    for data in re.findall(r'href="data:image/png;base64,([^"]+)"', html):
        assert base64.b64decode(data) in [
            (bundle[0][1].parent / f"f{i}.png").read_bytes() for i in (1, 2, 3)
        ]


@pytest.mark.parametrize(
    "kind",
    [
        "missing",
        "duplicate",
        "identity",
        "attempt",
        "plan",
        "reading",
        "incomplete",
        "frozen",
        "nonfinite",
    ],
)
def test_invalid_evidence_rejected_without_output(bundle, kind):
    args, _ = bundle
    report = json.loads(args[2].read_bytes())
    if kind == "missing":
        report["frames"].pop()
    elif kind == "duplicate":
        report["frames"][1] = report["frames"][0]
    elif kind == "identity":
        report["frames"][0]["frame_pts"] += 1
    elif kind == "attempt":
        (args[2].parent / "attempts/00.json").write_text("{}")
    elif kind == "plan":
        report["plan_sha256"] = "f" * 64
    elif kind == "reading":
        args[3].write_bytes(args[3].read_bytes() + b" ")
    elif kind == "incomplete":
        report["status"] = "incomplete"
    elif kind == "frozen":
        report["frozen_inputs_unchanged"] = False
    elif kind == "nonfinite":
        report["frames"][0]["engine_response"]["detections"][0]["box_xyxy"][0] = float("nan")
    save(args[2], report)
    with pytest.raises(ValueError):
        run(bundle)
    assert not args[-1].exists()


def test_existing_or_nonprivate_output_is_not_replaced(bundle):
    run(bundle)
    with pytest.raises(ValueError, match="fresh"):
        run(bundle)
    bundle[0][-1] = bundle[1].parent / "cv49b_escape"
    with pytest.raises(ValueError, match="fresh"):
        run(bundle)

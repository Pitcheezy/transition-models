"""Hand-labeling pack and the assistant-vs-person setup check."""

import hashlib
import json
import sys
from pathlib import Path

import pytest
from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intent.human_labels import compare, validate_labels  # noqa: E402
from intent.human_labels import main as labels_main  # noqa: E402
from intent.label_pack import build_pack, render_page, select_frames  # noqa: E402
from intent.label_pack import main as pack_main  # noqa: E402
from intent.plate_feet import PLATE_WIDTH_FEET  # noqa: E402

FRONT = {"front_left": [636.0, 322.0], "front_right": [690.0, 322.0]}


def _points(tmp_path, n=10, unavailable=(3, 7)):
    frames = []
    for i in range(n):
        rel = f"outputs/frames/evalset_{i}.jpg"
        path = tmp_path / rel
        path.parent.mkdir(parents=True, exist_ok=True)
        Image.new("RGB", (1280, 720), (30 + i, 90, 40)).save(path, quality=90)
        sha = hashlib.sha256(path.read_bytes()).hexdigest()
        est = i not in unavailable
        frames.append(
            {
                "at_bat_number": i + 1,
                "pitch_number": 1,
                "frame_seconds": float(i * 10),
                "image_sha256": sha,
                "path": rel,
                "status": "estimated" if est else "unavailable",
                "unavailable_reason": None if est else "catcher_not_in_setup",
                "mitt_center": [660.0, 240.0] if est else None,
                "uncertainty_pixels": 10.0 if est else None,
                "plate_corners": dict(FRONT, back_left=[640.0, 318.0], back_right=[686.0, 318.0])
                if est
                else None,
            }
        )
    return {
        "schema": "intent_points_v0",
        "game_pk": 747139,
        "method": {"kind": "t", "version": "v0"},
        "frames": frames,
    }


def test_selection_is_deterministic_and_keeps_some_abstentions(tmp_path):
    points = _points(tmp_path)
    picked = select_frames(points, 5)
    assert len(picked) == 5
    assert sum(1 for f in picked if f["status"] != "estimated") == 1
    assert picked == select_frames(points, 5)
    assert [f["at_bat_number"] for f in picked] == sorted(f["at_bat_number"] for f in picked)


def test_pack_embeds_crops_checks_hashes_and_stays_under_outputs(tmp_path):
    points = _points(tmp_path)
    manifest, page_frames = build_pack(points, tmp_path, 5)
    assert len(manifest["frames"]) == len(page_frames) == 5
    assert all(f["main"]["src"].startswith("data:image/jpeg;base64,") for f in page_frames)
    assert "src" not in json.dumps(manifest["frames"])
    page = render_page(manifest, page_frames)
    assert manifest["pack_id"] in page and "intent_human_labels_v0" in page
    bad = json.loads(json.dumps(points))
    bad["frames"][0]["image_sha256"] = "0" * 64
    with pytest.raises(ValueError):
        build_pack(bad, tmp_path, 10)
    src = tmp_path / "points.json"
    src.write_text(json.dumps(points), encoding="utf-8")
    with pytest.raises(SystemExit):
        pack_main(
            [
                "--game",
                "747139",
                "--points",
                str(src),
                "--frames-root",
                str(tmp_path),
                "--out",
                str(tmp_path / "page.html"),
            ]
        )
    out = tmp_path / "outputs" / "label" / "page.html"
    pack_main(
        [
            "--game",
            "747139",
            "--points",
            str(src),
            "--frames-root",
            str(tmp_path),
            "--sample",
            "5",
            "--out",
            str(out),
            "--manifest",
            str(tmp_path / "m.json"),
        ]
    )
    assert (
        out.is_file()
        and json.loads((tmp_path / "m.json").read_text(encoding="utf-8"))["pack_id"]
        == manifest["pack_id"]
    )


def _labels(manifest, person_mitt=(664.0, 244.0)):
    rows = []
    for f in manifest["frames"]:
        if f["assistant_status"] == "estimated":
            rows.append(
                {
                    "pitch_id": f["pitch_id"],
                    "frame_seconds": f["frame_seconds"],
                    "image_sha256": f["image_sha256"],
                    "mitt_status": "marked",
                    "mitt": list(person_mitt),
                    "plate_status": "marked",
                    "plate_front": {
                        "left_end": FRONT["front_left"],
                        "right_end": FRONT["front_right"],
                    },
                }
            )
        else:
            rows.append(
                {
                    "pitch_id": f["pitch_id"],
                    "frame_seconds": f["frame_seconds"],
                    "image_sha256": f["image_sha256"],
                    "mitt_status": "not_in_setup",
                    "mitt": None,
                    "plate_status": "hidden",
                    "plate_front": None,
                }
            )
    return {
        "schema": "intent_human_labels_v0",
        "game_pk": 747139,
        "pack_id": manifest["pack_id"],
        "labeler": "t",
        "elapsed_seconds": 60,
        "frames": rows,
    }


def test_labels_are_checked_against_the_pack_and_compared_in_pixels_and_feet(tmp_path):
    points = _points(tmp_path)
    manifest, _ = build_pack(points, tmp_path, 5)
    labels = _labels(manifest)
    rows = validate_labels(labels, manifest)
    report = compare(rows, points, None)
    assert (
        report["availability"]["both_marked"] == 4 and report["availability"]["both_abstained"] == 1
    )
    assert report["mitt_pixels"]["dx_assistant_minus_person"]["mean"] == pytest.approx(-4.0)
    assert report["mitt_pixels"]["dy_assistant_minus_person"]["mean"] == pytest.approx(-4.0)
    # same plate edge (54 px wide): 4 px left of the person -> +4/54 plate widths of plate_x;
    # 4 px higher -> +4/54 plate widths of height
    assert report["mitt_feet_same_plate"]["x"]["mean"] == pytest.approx(PLATE_WIDTH_FEET * 4 / 54)
    assert report["mitt_feet_same_plate"]["z"]["mean"] == pytest.approx(PLATE_WIDTH_FEET * 4 / 54)
    assert report["plate_front_end_pixels"]["median"] == pytest.approx(0.0)
    tampered = json.loads(json.dumps(labels))
    tampered["frames"][0]["image_sha256"] = "1" * 64
    with pytest.raises(ValueError):
        validate_labels(tampered, manifest)
    inconsistent = json.loads(json.dumps(labels))
    inconsistent["frames"][0]["mitt"] = None
    with pytest.raises(ValueError):
        validate_labels(inconsistent, manifest)
    other_pack = dict(labels, pack_id="nope")
    with pytest.raises(ValueError):
        validate_labels(other_pack, manifest)
    # CLI writes the stored labels and the report
    paths = {
        name: tmp_path / f"{name}.json"
        for name in ("labels", "manifest", "points", "out_l", "out_r")
    }
    paths["labels"].write_text(json.dumps(labels), encoding="utf-8")
    paths["manifest"].write_text(json.dumps(manifest), encoding="utf-8")
    paths["points"].write_text(json.dumps(points), encoding="utf-8")
    labels_main(
        [
            "--game",
            "747139",
            "--labels",
            str(paths["labels"]),
            "--manifest",
            str(paths["manifest"]),
            "--points",
            str(paths["points"]),
            "--calibration",
            str(tmp_path / "none.json"),
            "--out-labels",
            str(paths["out_l"]),
            "--out-report",
            str(paths["out_r"]),
        ]
    )
    stored = json.loads(paths["out_l"].read_text(encoding="utf-8"))
    assert stored["label_source"] == "human_manual_annotation" and len(stored["frames"]) == 5
    assert (
        json.loads(paths["out_r"].read_text(encoding="utf-8"))["availability"]["both_marked"] == 4
    )


def test_pack_crop_boxes_are_per_game_and_all_frames_can_be_taken(tmp_path):
    points = _points(tmp_path)
    manifest, page_frames = build_pack(
        points, tmp_path, 100, main_box=(300, 200, 960, 520), plate_box=(500, 440, 760, 500)
    )
    assert manifest["selection"]["all_frames"] is True and len(manifest["frames"]) == 10
    assert manifest["crops"]["main"]["box"] == [300, 200, 960, 520]
    assert page_frames[0]["plate"]["box"] == [500, 440, 760, 500]

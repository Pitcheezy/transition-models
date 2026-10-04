"""Unchanged image delivery and honest empty review state with strict response binding."""

import hashlib
import json
from copy import deepcopy

import pytest
from PIL import Image

from intent.quality_audit import SCHEMA, availability, validate_inputs
from intent.review_queue import check_response, prepare
from intent.schema import make_unavailable


def write(path, doc):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(doc), encoding="utf-8")


@pytest.fixture
def source(tmp_path):
    root = tmp_path / "repo"
    results = root / "docs/results/mlb_p0"
    results.mkdir(parents=True)
    games = []
    for g in (849845, 823407):
        image_path = root / f"outputs/frames/{g}/frame_000030.jpg"
        image_path.parent.mkdir(parents=True)
        Image.new("RGB", (20, 12), (25, 60, 90)).save(image_path)
        sha = hashlib.sha256(image_path.read_bytes()).hexdigest()
        pid = f"{g}:2:3"
        points = {
            "schema": "intent_points_v0",
            "game_pk": g,
            "video": {"fps_num": 30, "fps_den": 1},
            "frames": [
                {
                    "at_bat_number": 2,
                    "pitch_number": 3,
                    "frame_index": 30,
                    "frame_seconds": 1.0,
                    "image_sha256": sha,
                    "path": image_path.relative_to(root).as_posix(),
                    "status": "unavailable",
                    "unavailable_reason": "not_in_setup",
                    "mitt_center": None,
                }
            ],
        }
        frame = {
            "pitch_id": pid,
            "frame_seconds": 1.0,
            "image_sha256": sha,
            "path": image_path.relative_to(root).as_posix(),
        }
        manifest = {
            "schema": "intent_label_pack_v0",
            "game_pk": g,
            "pack_id": str(g),
            "frames": [dict(frame, assistant_status="unavailable")],
        }
        labels = {
            "schema": "intent_human_labels_v0",
            "game_pk": g,
            "pack_id": str(g),
            "frames": [
                dict(frame, mitt_status="marked", mitt=[10, 6], plate_status=None, plate_front=None)
            ],
        }
        rec = make_unavailable(
            pid,
            "frame",
            sha,
            {"kind": "assistant_visual_estimate", "version": "v0"},
            1.0,
            "assistant_visual_estimate",
            "not_in_setup",
            frame_index=30,
        )
        docs = {"points": points, "manifest": manifest, "labels": labels}
        sources = {}
        for key, doc in docs.items():
            path = results / f"{g}_{key}.json"
            write(path, doc)
            sources[key] = {
                "path": path.name,
                "sha256": hashlib.sha256(path.read_bytes()).hexdigest(),
            }
        jsonl = results / f"{g}_output.jsonl"
        jsonl.write_text(json.dumps(rec) + "\n", encoding="utf-8")
        sources["jsonl"] = {
            "path": jsonl.name,
            "sha256": hashlib.sha256(jsonl.read_bytes()).hexdigest(),
        }
        p, h, _ = validate_inputs(g, **docs, records=[rec])
        games.append({"game_pk": g, "sources": sources, "availability": availability(p, h)})
    report = root / "docs/quality.json"
    write(report, {"schema": SCHEMA, "games": games})
    return root, report, root / "outputs/cv_review_test"


def create(source):
    root, report, out = source
    return prepare(root, report, out, expected_count=2)


def response_file(source, update=None):
    out = source[2]
    response = json.loads((out / "reviewer/response_template.json").read_text())
    if update:
        update(response)
    path = out / "human_response.json"
    write(path, response)
    return path


def test_source_only_queue_copies_bytes_and_starts_with_zero_reviews(source):
    root, report, out = source
    result = create(source)
    assert result["prepared"] == result["unreviewed"] == 2
    assert result["completed_reviews"] == 0 and not result["independent_validation"]
    private = json.loads((out / "private_selection.json").read_text())
    manifest = json.loads((out / "reviewer/manifest.json").read_text())
    assert all("pitch_id" not in f and "status" not in f for f in manifest["frames"])
    assert "assistant_status" not in json.dumps(manifest)
    mappings = {row["observation_id"]: row for row in private["mapping"]}
    for frame in manifest["frames"]:
        assert (out / "reviewer" / frame["path"]).read_bytes() == (
            root / mappings[frame["observation_id"]]["source_path"]
        ).read_bytes()
    page = (out / "reviewer/index.html").read_text(encoding="utf-8")
    assert "resting" in page and "AI/사람 결과" in page and "crop" not in page
    template = out / "reviewer/response_template.json"
    before = template.read_bytes()
    assert check_response(out, template) == {"completed": 0, "unreviewed": 2, "unknown": 0}
    assert template.read_bytes() == before
    with pytest.raises(ValueError, match="already exists"):
        create(source)


@pytest.mark.parametrize(
    "change", ["source_hash", "image_bytes", "report_count", "report_duplicate_game"]
)
def test_invalid_frozen_selection_aborts_before_writing(source, change):
    root, report_path, out = source
    report = json.loads(report_path.read_text())
    game = report["games"][0]
    if change == "source_hash":
        game["sources"]["points"]["sha256"] = "0" * 64
    elif change == "image_bytes":
        next((root / "outputs/frames").rglob("*.jpg")).write_bytes(b"wrong")
    elif change == "report_count":
        game["availability"]["cells"]["human_only"] += 1
    else:
        report["games"].append(deepcopy(game))
    write(report_path, report)
    with pytest.raises(ValueError):
        create(source)
    assert not out.exists()


def test_path_escape_with_matching_metadata_hash_is_rejected(source):
    root, report_path, _ = source
    report = json.loads(report_path.read_text())
    source_row = report["games"][0]["sources"]["points"]
    point_path = root / "docs/results/mlb_p0" / source_row["path"]
    points = json.loads(point_path.read_text())
    points["frames"][0]["path"] = "../outside.jpg"
    write(point_path, points)
    source_row["sha256"] = hashlib.sha256(point_path.read_bytes()).hexdigest()
    write(report_path, report)
    with pytest.raises(ValueError, match="escapes"):
        create(source)


def test_actual_external_mark_and_unknown_are_counted_without_mutation(source):
    create(source)

    def update(response):
        response["reviewer_id"] = "human-2"
        response["rows"][0].update(status="marked", mitt=[10, 6], visibility="full", pose="resting")
        response["rows"][1].update(status="unknown", reason="cannot determine glove body")

    path = response_file(source, update)
    before = path.read_bytes()
    assert check_response(source[2], path) == {"completed": 1, "unreviewed": 0, "unknown": 1}
    assert path.read_bytes() == before


@pytest.mark.parametrize(
    "change",
    [
        "version",
        "manifest_hash",
        "image_hash",
        "duplicate",
        "pitch_key",
        "nan",
        "bounds",
        "unavailable_point",
        "unknown_point",
        "missing_reviewer",
    ],
)
def test_invalid_response_is_rejected(source, change):
    create(source)

    def update(response):
        row = response["rows"][0]
        response["reviewer_id"] = "human-2"
        row.update(status="marked", mitt=[10, 6], visibility="full")
        if change == "version":
            response["protocol_version"] = "other"
        elif change == "manifest_hash":
            response["manifest_sha256"] = "0" * 64
        elif change == "image_hash":
            row["image_sha256"] = "0" * 64
        elif change == "duplicate":
            response["rows"][1] = deepcopy(row)
        elif change == "pitch_key":
            row["pitch_id"] = "849845:2:3"
        elif change == "nan":
            row["mitt"][0] = float("nan")
        elif change == "bounds":
            row["mitt"][0] = 20
        elif change == "unavailable_point":
            row.update(status="unavailable", reason="hidden")
        elif change == "unknown_point":
            row.update(status="unknown", reason="uncertain")
        else:
            response["reviewer_id"] = ""

    with pytest.raises(ValueError):
        check_response(source[2], response_file(source, update))


def test_manifest_tamper_does_not_create_new_review_baseline(source):
    create(source)
    path = source[2] / "reviewer/manifest.json"
    path.write_text(path.read_text() + " ")
    with pytest.raises(ValueError, match="SHA256 mismatch"):
        check_response(source[2], source[2] / "reviewer/response_template.json")


def test_frame_index_clock_mismatch_with_rebound_metadata_is_rejected(source):
    root, report_path, out = source
    report = json.loads(report_path.read_text())
    binding = report["games"][0]["sources"]["points"]
    path = root / "docs/results/mlb_p0" / binding["path"]
    points = json.loads(path.read_text())
    points["frames"][0]["frame_index"] = 31
    write(path, points)
    binding["sha256"] = hashlib.sha256(path.read_bytes()).hexdigest()
    write(report_path, report)
    with pytest.raises(ValueError, match="source clock"):
        create(source)
    assert not out.exists()


def test_source_symlink_is_rejected_when_supported(source, tmp_path):
    root, _, _ = source
    path = next((root / "outputs/frames").rglob("*.jpg"))
    target = tmp_path / "external.jpg"
    target.write_bytes(path.read_bytes())
    path.unlink()
    try:
        path.symlink_to(target)
    except OSError:
        pytest.skip("host does not permit creating test symlinks")
    with pytest.raises(ValueError, match="symlink"):
        create(source)

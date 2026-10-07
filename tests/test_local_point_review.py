"""Synthetic saved-result tests; no training, inference, or real images are used."""

import base64
import hashlib
import json
import math
from collections import Counter
from pathlib import Path

import pytest
from PIL import Image

from intent import local_point_review as review


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, allow_nan=False), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def create_package(tmp_path, counts):
    frames, refs, cohorts, bindings = [], [], {game: [] for game in counts}, []
    excluded = []
    for game, (total, marked) in counts.items():
        crop = [2, 4, 62, 44] if game == 823407 else [4, 2, 60, 46]
        for index in range(total):
            image = tmp_path / "images" / f"{game}_{index}.jpg"
            image.parent.mkdir(parents=True, exist_ok=True)
            Image.new("RGB", (64, 48), (index * 3, 50 if game == 823407 else 170, 60)).save(image)
            digest = review._sha(image.read_bytes())
            identity = f"{game}:1:{index + 1}"
            frame = {
                "observation_id": identity,
                "game_pk": game,
                "image_path": str(image),
                "image_sha256": digest,
                "width": 64,
                "height": 48,
                "legacy_main_crop": crop,
            }
            frames.append(frame)
            uv = (
                [0.2 + 0.5 * index / total, 0.4]
                if game == 823407
                else [0.6, 0.3 + 0.4 * index / total]
            )
            ref = {
                "observation_id": identity,
                "game_pk": game,
                "image_sha256": digest,
                "legacy_mitt_status": "marked" if index < marked else "not_in_setup",
                "mitt": review._project(uv, crop) if index < marked else None,
            }
            refs.append(ref)
            if index < marked:
                cohorts[game].append((frame, uv))
            else:
                excluded.append(
                    {
                        "observation_id": identity,
                        "game_pk": game,
                        "legacy_mitt_status": "not_in_setup",
                        "reason": "legacy_nonmarked_is_not_a_negative",
                    }
                )
            bindings.append([str(image), digest, "image"])
    manifest_path, refs_path = tmp_path / "manifest.json", tmp_path / "references.json"
    manifest_sha = write(manifest_path, {"schema": "local_glove_frames_v1", "frames": frames})
    refs_sha = write(
        refs_path,
        {
            "schema": "local_glove_references_v1",
            "manifest_sha256": manifest_sha,
            "references": refs,
        },
    )
    bindings += [
        [str(manifest_path), manifest_sha, "manifest"],
        [str(refs_path), refs_sha, "references"],
    ]
    run = tmp_path / "saved_run"
    plan = {
        "schema": "local_point_experiment_plan_v1",
        "manifest": str(manifest_path),
        "manifest_sha256": manifest_sha,
        "references": str(refs_path),
        "references_sha256": refs_sha,
        "seeds": [42, 43, 44],
        "input_view": "legacy_main_crop",
    }
    artifact_sha = {"plan.json": write(run / "plan.json", plan)}
    plan_sha = artifact_sha["plan.json"]
    artifact_sha["run_manifest.json"] = write(
        run / "run_manifest.json",
        {
            "schema": "local_point_experiment_run_v1",
            "plan_sha256": plan_sha,
            "input_bindings": bindings,
        },
    )
    artifact_sha["events.json"] = write(run / "events.json", {"events": []})
    ledger = [
        {
            **arm,
            "path": f"checkpoints/{arm['arm_id']}.pt",
            "sha256": review._sha(arm["arm_id"].encode()),
        }
        for arm in review._arms()
    ]
    artifact_sha["checkpoint_ledger.json"] = write(
        run / "checkpoint_ledger.json",
        {
            "schema": "local_point_checkpoint_ledger_v1",
            "plan_sha256": plan_sha,
            "checkpoints": ledger,
        },
    )
    ledger_sha = artifact_sha["checkpoint_ledger.json"]
    summaries = []
    for entry in ledger:
        arm = {key: entry[key] for key in ("arm_id", "train_game", "test_game", "seed")}
        key, train, test = arm["arm_id"], arm["train_game"], arm["test_game"]
        training = {
            **arm,
            "status": "completed",
            "checkpoint_sha256": entry["sha256"],
            "training_observation_ids": [row[0]["observation_id"] for row in cohorts[train]],
        }
        predictions = [
            {
                "observation_id": frame["observation_id"],
                "image_sha256": frame["image_sha256"],
                "status": "completed",
                "normalized_point": [0.75, 0.25],
            }
            for frame, _ in cohorts[test]
        ]
        if train == 823407 and arm["seed"] == 42:
            predictions[0].update(
                status="error", normalized_point=None, error_type="SyntheticFailure"
            )
            predictions[1].update(status="not_attempted", normalized_point=None)
        evaluation = {
            **arm,
            "status": "completed",
            "checkpoint_sha256": entry["sha256"],
            "checkpoint_ledger_sha256": ledger_sha,
            "predictions": predictions,
        }
        artifact_sha[f"training/{key}.json"] = write(run / "training" / f"{key}.json", training)
        artifact_sha[f"evaluation/{key}.json"] = write(
            run / "evaluation" / f"{key}.json", evaluation
        )
        mean = [
            sum(row[1][axis] for row in cohorts[train]) / len(cohorts[train]) for axis in (0, 1)
        ]
        summaries.append(
            {
                **arm,
                "planned_marked": len(cohorts[test]),
                "prediction_states": dict(Counter(row["status"] for row in predictions)),
                "baselines_all_marked": {
                    "crop_center": {"normalized_point": [0.5, 0.5]},
                    "training_game_mean": {"normalized_point": mean},
                },
            }
        )
    report = {
        "schema": "local_point_experiment_report_v1",
        "status": "completed_with_errors",
        "results_usable": True,
        "manifest_sha256": manifest_sha,
        "references_sha256": refs_sha,
        "plan_sha256": plan_sha,
        "checkpoint_ledger_sha256": ledger_sha,
        "artifact_sha256": artifact_sha,
        "arms": summaries,
        "checkpoints": [
            {key: value for key, value in entry.items() if key != "path"} for entry in ledger
        ],
        "unique_marked_frames": sum(marked for _, marked in counts.values()),
        "unique_original_frames": sum(total for total, _ in counts.values()),
        "seed_repetitions": 3,
        "prediction_rows_planned": 3 * sum(marked for _, marked in counts.values()),
        "seed_repetitions_are_independent_samples": False,
        "excluded": excluded,
    }
    report_path = run / "report.json"
    write(report_path, report)
    return manifest_path, refs_path, report_path


@pytest.fixture
def package(tmp_path, monkeypatch):
    counts = {823407: (3, 2), 849845: (4, 3)}
    monkeypatch.setattr(review, "EXPECTED_COUNTS", counts)
    return create_package(tmp_path, counts)


def change_artifact(package, relative, change):
    report_path = package[2]
    path = report_path.parent / relative
    document = read(path)
    change(document)
    digest = write(path, document)
    report = read(report_path)
    report["artifact_sha256"][relative] = digest
    write(report_path, report)


def extract_data(html):
    opening = '<script id="review-data" type="application/json">'
    return json.loads(html.split(opening, 1)[1].split("</script>", 1)[0])


def test_all_marked_frames_and_all_seeds_are_preserved_with_original_bytes(package):
    data = review.collect_review_data(*package)
    manifest = read(package[0])
    originals = {row["observation_id"]: row for row in manifest["frames"]}
    assert len(data["frames"]) == 5
    assert data["default_seed"] == 42 and data["seeds"] == [42, 43, 44]
    assert len(data["excluded"]) == 2
    for row in data["frames"]:
        assert set(row["predictions"]) == {"42", "43", "44"}
        encoded = row["image_data"].split(",", 1)[1]
        assert (
            base64.b64decode(encoded)
            == Path(originals[row["observation_id"]]["image_path"]).read_bytes()
        )
        assert "image_path" not in row
    states = [row["predictions"]["42"]["status"] for row in data["frames"]]
    assert states.count("error") == 1 and states.count("not_attempted") == 1


def test_production_84_marked_cohort_is_complete(tmp_path):
    package = create_package(tmp_path, review.EXPECTED_COUNTS)
    data = review.collect_review_data(*package)
    assert len(data["frames"]) == 84
    assert Counter(row["game_pk"] for row in data["frames"]) == {823407: 28, 849845: 56}


def test_original_coordinate_projection_and_opposite_training_mean(package):
    data = review.collect_review_data(*package)
    row = next(row for row in data["frames"] if row["game_pk"] == 849845)
    prediction = row["predictions"]["43"]
    assert prediction["model_point"] == [46.0, 13.0]
    assert prediction["crop_center"] == [32.0, 24.0]
    expected_u = (0.2 + (0.2 + 0.5 / 3)) / 2
    assert prediction["training_game_mean"] == pytest.approx([4 + expected_u * 56, 2 + 0.4 * 44])
    assert prediction["train_game"] == 823407


def test_builder_writes_only_one_new_standalone_html_file(package, tmp_path):
    out = tmp_path / "outputs" / "cv_local_point_review_synthetic"
    result = review.build_review(*package, out)
    assert result == out / "index.html"
    assert list(out.iterdir()) == [result]
    html = result.read_text(encoding="utf-8")
    data = extract_data(html)
    assert len(data["frames"]) == 5
    assert data["provenance"]["model_calls"] == 0
    assert data["provenance"]["annotation_editing"] is False
    assert data["provenance"]["independent_validation"] is False
    for required in (
        'id="game"',
        'id="seed"',
        'id="previous"',
        'id="next"',
        'id="original-only"',
        "기존 단일 라벨러",
        "AI:",
        "학습 경기 평균",
    ):
        assert required in html
    assert "fetch(" not in html and "XMLHttpRequest" not in html
    assert "<form" not in html and "contenteditable" not in html
    assert "connect-src 'none'" in html and "img-src data:" in html
    assert str(tmp_path) not in html


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("results_usable", False),
        ("results_usable", 1),
        ("status", "invalid_frozen_inputs"),
        ("status", "training_incomplete"),
    ],
)
def test_invalidated_or_unusable_results_rejected_before_output(package, tmp_path, field, value):
    report = read(package[2])
    report[field] = value
    write(package[2], report)
    out = tmp_path / "outputs" / "cv_local_point_review_invalid"
    with pytest.raises(review.ReviewError):
        review.build_review(*package, out)
    assert not out.exists()


@pytest.mark.parametrize("source", ["manifest", "references", "image", "evaluation"])
def test_changed_input_or_saved_artifact_is_rejected(package, source):
    if source == "manifest":
        package[0].write_bytes(package[0].read_bytes() + b" ")
    elif source == "references":
        package[1].write_bytes(package[1].read_bytes() + b" ")
    elif source == "image":
        image = Path(read(package[0])["frames"][0]["image_path"])
        image.write_bytes(image.read_bytes() + b"changed")
    else:
        path = package[2].parent / "evaluation/train_823407_seed_42.json"
        path.write_bytes(path.read_bytes() + b" ")
    with pytest.raises(review.ReviewError, match="SHA-256|binding"):
        review.collect_review_data(*package)


@pytest.mark.parametrize(
    "mutation",
    ["missing", "duplicate", "wrong_hash", "wrong_game", "point_on_failure", "out_of_range"],
)
def test_prediction_contract_is_revalidated_even_with_updated_artifact_hash(package, mutation):
    def change(document):
        rows = document["predictions"]
        if mutation == "missing":
            rows.pop()
        elif mutation == "duplicate":
            rows.append(dict(rows[0]))
        elif mutation == "wrong_hash":
            rows[0]["image_sha256"] = "0" * 64
        elif mutation == "wrong_game":
            document["test_game"] = document["train_game"]
        elif mutation == "point_on_failure":
            rows[0]["normalized_point"] = [0.5, 0.5]
        else:
            rows[2]["normalized_point"] = [1.1, 0.5]

    change_artifact(package, "evaluation/train_823407_seed_42.json", change)
    with pytest.raises(review.ReviewError):
        review.collect_review_data(*package)


def test_training_ids_cannot_include_test_game(package):
    change_artifact(
        package,
        "training/train_823407_seed_42.json",
        lambda row: row["training_observation_ids"].__setitem__(0, "849845:1:1"),
    )
    with pytest.raises(review.ReviewError, match="opposite-game"):
        review.collect_review_data(*package)


def test_baseline_is_recomputed_from_training_game_only(package):
    report = read(package[2])
    report["arms"][0]["baselines_all_marked"]["training_game_mean"]["normalized_point"] = [0.9, 0.9]
    write(package[2], report)
    with pytest.raises(review.ReviewError, match="training-only"):
        review.collect_review_data(*package)


def test_report_cannot_remove_a_seed(package):
    report = read(package[2])
    report["arms"].pop()
    write(package[2], report)
    with pytest.raises(review.ReviewError, match="six"):
        review.collect_review_data(*package)


def test_report_denominator_cannot_hide_failed_rows(package):
    report = read(package[2])
    report["arms"][0]["planned_marked"] -= 1
    write(package[2], report)
    with pytest.raises(review.ReviewError, match="denominator"):
        review.collect_review_data(*package)


def test_error_text_is_inert_json_not_html_or_javascript(package):
    malicious = '</script><script>alert("not allowed")</script><img src=https://example.invalid>'
    change_artifact(
        package,
        "evaluation/train_823407_seed_42.json",
        lambda row: row["predictions"][0].update(error_type=malicious),
    )
    data = review.collect_review_data(*package)
    html = review.render_html(data)
    assert malicious not in html
    restored = extract_data(html)
    selected = next(row for row in restored["frames"] if row["game_pk"] == 849845)
    assert selected["predictions"]["42"]["error_type"] == malicious
    assert "\\u003c/script\\u003e" in html
    script_hash = base64.b64encode(hashlib.sha256(review.VIEWER_JS.encode()).digest()).decode()
    assert f"script-src 'sha256-{script_hash}'" in html


def test_existing_output_is_not_overwritten(package, tmp_path):
    out = tmp_path / "outputs" / "cv_local_point_review_existing"
    out.mkdir(parents=True)
    sentinel = out / "index.html"
    sentinel.write_text("keep")
    with pytest.raises(FileExistsError):
        review.build_review(*package, out)
    assert sentinel.read_text() == "keep"


def test_output_location_is_restricted_to_new_review_outputs(package, tmp_path):
    with pytest.raises(review.ReviewError, match="Output"):
        review.build_review(*package, tmp_path / "some_other_folder")


def test_no_model_or_training_dependency_is_required():
    source = Path(review.__file__).read_text(encoding="utf-8")
    assert "import torch" not in source
    assert "import local_point_model" not in source
    assert "train_point_model(" not in source
    assert "predict_points(" not in source


def test_nonfinite_json_and_duplicate_fields_are_rejected(package):
    report_path = package[2]
    report_path.write_text('{"schema": NaN}')
    with pytest.raises(review.ReviewError, match="Nonfinite"):
        review.collect_review_data(*package)
    report_path.write_text('{"schema": "a", "schema": "b"}')
    with pytest.raises(review.ReviewError, match="Duplicate"):
        review.collect_review_data(*package)


def test_gaussian_or_confidence_values_are_not_added_to_viewer(package):
    data = review.collect_review_data(*package)
    row = data["frames"][0]["predictions"]["42"]
    assert set(row) == {
        "status",
        "error_type",
        "train_game",
        "model_point",
        "crop_center",
        "training_game_mean",
    }
    assert all(math.isfinite(value) for value in row["crop_center"])

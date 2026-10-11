"""Checks for full-denominator, identity-bound local glove development reports."""

import hashlib
import json
import math
from copy import deepcopy

import pytest

from intent.local_glove_report import build_report, main


def documents(size=7, marked=5):
    manifest = {
        "schema": "local_glove_frames_v1",
        "frames": [
            {
                "observation_id": f"observation-{i}",
                "game_pk": 11 if i < 4 else 22,
                "image_sha256": hashlib.sha256(str(i).encode()).hexdigest(),
                "width": 80,
                "height": 60,
                "legacy_main_crop": [10, 10, 70, 50],
                "image_path": f"not-opened/{i}.jpg",
            }
            for i in range(size)
        ],
    }
    references = {
        "schema": "local_glove_references_v1",
        "manifest_sha256": "a" * 64,
        "references": [
            {
                "observation_id": frame["observation_id"],
                "game_pk": frame["game_pk"],
                "image_sha256": frame["image_sha256"],
                "legacy_mitt_status": "marked" if i < marked else "not_in_setup",
                "mitt": [20, 20] if i < marked else None,
            }
            for i, frame in enumerate(manifest["frames"])
        ],
    }
    predictions = {
        "schema": "local_glove_predictions_v1",
        "manifest_sha256": "a" * 64,
        "model_id": "fixture-detector",
        "input_view": "full_frame",
        "threshold": 0.5,
        "device": "cpu",
        "frames": [],
    }
    return manifest, references, predictions


def prediction(frame, selection="candidate", point=None):
    point = ([23, 24] if point is None else point) if selection == "candidate" else None
    return {
        "observation_id": frame["observation_id"],
        "image_sha256": frame["image_sha256"],
        "status": "completed",
        "selection_status": selection,
        "point": point,
        "detections": [],
        "error": None,
        "timing": {"model_seconds": 0.1, "service_seconds": 0.2},
    }


@pytest.fixture
def sample():
    manifest, references, predictions = documents()
    frames = manifest["frames"]
    predictions["frames"] = [
        prediction(frames[0]),
        prediction(frames[1], point=[14, 28]),
        prediction(frames[2], "no_candidate"),
        prediction(frames[3], "ambiguous"),
        {
            **prediction(frames[4], "no_candidate"),
            "status": "error",
            "selection_status": None,
            "error": "runtime unavailable",
            "timing": {"model_seconds": None, "service_seconds": 0.6},
        },
        prediction(frames[5]),
    ]
    references["references"][6]["legacy_mitt_status"] = "not_centre_field"
    return manifest, references, predictions


def test_full_denominator_crosstab_and_hand_computed_distances(sample):
    saved = deepcopy(sample)
    report = build_report(*sample)
    summary = report["summary"]
    assert summary["counts"] == {
        "planned": 7,
        "attempted": 6,
        "completed": 5,
        "error": 1,
        "not_attempted": 1,
        "candidate": 3,
        "no_candidate": 1,
        "ambiguous": 1,
        "human_marked": 5,
        "legacy_abstained": 2,
    }
    assert summary["availability"]["legacy_reference_by_prediction_state"] == {
        "legacy_marked": {
            "candidate": 2,
            "no_candidate": 1,
            "ambiguous": 1,
            "error": 1,
            "not_attempted": 0,
        },
        "legacy_abstained": {
            "candidate": 1,
            "no_candidate": 0,
            "ambiguous": 0,
            "error": 0,
            "not_attempted": 1,
        },
    }
    discrepancy = summary["conditional_point_discrepancy"]
    assert discrepancy["n"] == 2
    assert discrepancy["distance_pixels"] == {"n": 2, "median": 7.5, "p90": 9.5}
    assert discrepancy["distance_image_diagonal"]["median"] == pytest.approx(0.075)
    assert discrepancy["distance_image_diagonal"]["p90"] == pytest.approx(0.095)
    assert report["frames"][0]["difference"]["dx_image_diagonal"] == pytest.approx(0.03)
    assert report["frames"][1]["difference"]["dx_image_diagonal"] == pytest.approx(-0.06)
    assert report["frames"][1]["difference"]["dy_image_diagonal"] == pytest.approx(0.08)
    cutoffs = summary["fixed_pixel_sensitivity"]["cutoffs"]
    assert [entry["numerator"] for entry in cutoffs] == [1, 2, 2, 2]
    assert [entry["denominator"] for entry in cutoffs] == [5] * 4
    assert [entry["fraction"] for entry in cutoffs] == [0.2, 0.4, 0.4, 0.4]
    assert [(g["game_pk"], g["counts"]["planned"]) for g in report["games"]] == [(11, 4), (22, 3)]
    assert report["games"][1]["conditional_point_discrepancy"]["n"] == 0
    assert sample == saved
    assert report["provenance"]["manifest_bytes_verified"] is False


def test_84_marked_denominator_includes_unattempted_error_and_abstention():
    manifest, references, predictions = documents(size=86, marked=84)
    predictions["frames"] = [
        prediction(manifest["frames"][0]),
        prediction(manifest["frames"][1], "no_candidate"),
        {
            **prediction(manifest["frames"][2], "no_candidate"),
            "status": "error",
            "selection_status": None,
            "error": "failed",
        },
        prediction(manifest["frames"][84]),
    ]
    report = build_report(manifest, references, predictions)
    assert report["summary"]["counts"]["planned"] == 86
    assert report["summary"]["counts"]["human_marked"] == 84
    assert report["summary"]["counts"]["legacy_abstained"] == 2
    assert report["summary"]["counts"]["not_attempted"] == 82
    for cutoff in report["summary"]["fixed_pixel_sensitivity"]["cutoffs"]:
        assert cutoff["numerator"] == 1
        assert cutoff["denominator"] == 84
        assert cutoff["fraction"] == pytest.approx(1 / 84)
    assert report["development_only"] is True
    for flag in (
        "independent_validation",
        "catcher_association_verified",
        "live",
        "physical_accuracy_measured",
    ):
        assert report[flag] is False
    assert not any("false_positive" in key or "accuracy" in key for key in report["summary"])


def test_zero_marked_denominator_is_null():
    manifest, references, predictions = documents(size=2, marked=0)
    report = build_report(manifest, references, predictions)
    assert report["summary"]["counts"]["not_attempted"] == 2
    assert report["summary"]["conditional_point_discrepancy"]["distance_pixels"] == {
        "n": 0,
        "median": None,
        "p90": None,
    }
    assert all(
        x["fraction"] is None for x in report["summary"]["fixed_pixel_sensitivity"]["cutoffs"]
    )


@pytest.mark.parametrize("index,key", [(0, "frames"), (1, "references"), (2, "frames")])
def test_duplicate_ids_rejected(sample, index, key):
    sample[index][key].append(deepcopy(sample[index][key][0]))
    with pytest.raises(ValueError, match="duplicate observation_id"):
        build_report(*sample)


@pytest.mark.parametrize("index,key", [(1, "references"), (2, "frames")])
def test_unknown_ids_and_image_hash_mismatches_rejected(sample, index, key):
    sample[index][key][0]["observation_id"] = "unplanned"
    with pytest.raises(ValueError, match="unknown observation_id"):
        build_report(*sample)
    sample[index][key][0]["observation_id"] = sample[0]["frames"][0]["observation_id"]
    sample[index][key][0]["image_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="image SHA256 mismatch"):
        build_report(*sample)


def test_reference_set_must_cover_full_plan_but_predictions_may_be_missing(sample):
    sample[1]["references"].pop()
    with pytest.raises(ValueError, match="missing reference"):
        build_report(*sample)


def test_hash_and_game_binding_rejected(sample):
    sample[2]["manifest_sha256"] = "b" * 64
    with pytest.raises(ValueError, match="manifest SHA256 mismatch"):
        build_report(*sample)
    sample[2]["manifest_sha256"] = "a" * 64
    sample[1]["references"][0]["game_pk"] = 999
    with pytest.raises(ValueError, match="game_pk mismatch"):
        build_report(*sample)


@pytest.mark.parametrize("point", [[80, 20], [20, 60], [-1, 20], [True, 20], [math.inf, 20]])
@pytest.mark.parametrize("reference", [False, True])
def test_invalid_points_rejected(sample, point, reference):
    if reference:
        sample[1]["references"][0]["mitt"] = point
    else:
        sample[2]["frames"][0]["point"] = point
    with pytest.raises(ValueError):
        build_report(*sample)


@pytest.mark.parametrize(
    "changes",
    [
        {"selection_status": "candidate", "point": None},
        {"selection_status": "no_candidate", "point": [1, 2]},
        {"selection_status": "ambiguous", "point": [1, 2]},
        {"selection_status": None},
        {"error": "completed with failure"},
        {"status": "error", "error": "failed"},
        {"status": "error", "selection_status": None, "point": None, "error": None},
    ],
)
def test_selection_point_status_consistency(sample, changes):
    sample[2]["frames"][0].update(changes)
    with pytest.raises(ValueError):
        build_report(*sample)


@pytest.mark.parametrize(
    "detection",
    [
        {"nested": {"score": math.nan}},
        {"box_xyxy": [0, 0, 81, 20]},
        {"center_xy": [80, 20]},
        {"score": 1.1},
        "not an object",
    ],
)
def test_detections_nonfinite_or_out_of_bounds_rejected(sample, detection):
    sample[2]["frames"][0]["detections"] = [detection]
    with pytest.raises(ValueError):
        build_report(*sample)


@pytest.mark.parametrize("seconds", [-1, math.nan, None, True])
def test_invalid_completed_timing_rejected(sample, seconds):
    sample[2]["frames"][0]["timing"]["model_seconds"] = seconds
    with pytest.raises(ValueError):
        build_report(*sample)


def write_inputs(tmp_path, sample):
    manifest, references, predictions = deepcopy(sample)
    manifest_path = tmp_path / "manifest.json"
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    digest = hashlib.sha256(manifest_path.read_bytes()).hexdigest()
    paths = [manifest_path]
    for name, document in (("references", references), ("predictions", predictions)):
        document["manifest_sha256"] = digest
        path = tmp_path / f"{name}.json"
        path.write_text(json.dumps(document), encoding="utf-8")
        paths.append(path)
    return paths


def arguments(paths, out):
    return [
        "--manifest",
        str(paths[0]),
        "--references",
        str(paths[1]),
        "--predictions",
        str(paths[2]),
        "--out",
        str(out),
    ]


def test_cli_binds_file_bytes_and_refuses_existing_output(tmp_path, sample):
    paths = write_inputs(tmp_path, sample)
    output = tmp_path / "report.json"
    report = main(arguments(paths, output))
    assert json.loads(output.read_text(encoding="utf-8")) == report
    assert report["provenance"]["manifest_bytes_verified"] is True
    assert report["provenance"]["image_bytes_verified"] is False
    for name, path in zip(("manifest", "references", "predictions"), paths, strict=True):
        assert (
            report["provenance"]["input_files"][name]["sha256"]
            == hashlib.sha256(path.read_bytes()).hexdigest()
        )
    before = output.read_bytes()
    with pytest.raises(FileExistsError):
        main(arguments(paths, output))
    assert output.read_bytes() == before


def test_cli_rejects_different_manifest_bytes_even_when_same_json(tmp_path, sample):
    paths = write_inputs(tmp_path, sample)
    with paths[0].open("a", encoding="utf-8") as handle:
        handle.write("\n")
    output = tmp_path / "report.json"
    with pytest.raises(ValueError, match="manifest file bytes"):
        main(arguments(paths, output))
    assert not output.exists()


def test_cli_rejects_duplicate_json_keys(tmp_path, sample):
    paths = write_inputs(tmp_path, sample)
    text = paths[2].read_text(encoding="utf-8")
    paths[2].write_text(
        text.replace('"device": "cpu"', '"device": "cpu", "device": "cpu"'), encoding="utf-8"
    )
    with pytest.raises(ValueError, match="duplicate JSON object key"):
        main(arguments(paths, tmp_path / "report.json"))


def _run_metadata(predictions, status="completed"):
    predictions.update(
        run_status=status,
        frozen_inputs_unchanged=True,
        eligible_for_development_comparison=True,
    )


def _detection(box=(20, 20, 26, 28), score=0.8):
    return {
        "label": 40,
        "category": "baseball glove",
        "box_xyxy": list(box),
        "center_xy": [(box[0] + box[2]) / 2, (box[1] + box[3]) / 2],
        "score": score,
        "above_threshold": score >= 0.5,
    }


@pytest.fixture
def benchmark_sample():
    manifest, references, predictions = documents(size=3, marked=3)
    _run_metadata(predictions)
    row = prediction(manifest["frames"][0])
    row["detections"] = [_detection()]
    row["point"] = row["detections"][0]["center_xy"]
    row["engine_response"] = {
        "threshold": 0.5,
        "selection_status": "candidate",
        "detections": deepcopy(row["detections"]),
        "candidate": deepcopy(row["detections"][0]),
    }
    predictions["frames"] = [row]
    return manifest, references, predictions


@pytest.mark.parametrize("status", ["invalidated", "frozen_inputs_changed"])
def test_invalidated_run_refused_before_scoring(benchmark_sample, status):
    benchmark_sample[2]["run_status"] = status
    with pytest.raises(ValueError, match="ineligible"):
        build_report(*benchmark_sample)


@pytest.mark.parametrize("key", ["frozen_inputs_unchanged", "eligible_for_development_comparison"])
@pytest.mark.parametrize("value", [False, 0, 1, None, "true"])
def test_explicit_ineligible_or_nonboolean_run_flags_refused(benchmark_sample, key, value):
    benchmark_sample[2][key] = value
    with pytest.raises(ValueError, match="ineligible"):
        build_report(*benchmark_sample)


@pytest.mark.parametrize(
    "key", ["run_status", "frozen_inputs_unchanged", "eligible_for_development_comparison"]
)
def test_partially_missing_integrity_metadata_refused(benchmark_sample, key):
    del benchmark_sample[2][key]
    with pytest.raises(ValueError, match="incomplete"):
        build_report(*benchmark_sample)


def test_legacy_saved_results_explicitly_report_unverified_contract_and_integrity(sample):
    report = build_report(*sample)
    assert report["provenance"]["run_integrity"] == {
        "metadata_present": False,
        "declared_claims_checked": False,
        "assessment": "not_established_legacy_saved_result",
        "run_status": None,
        "frozen_input_bytes_reverified": False,
    }
    assert report["provenance"]["detection_contract_checked"] is False
    assert any("Run-integrity metadata is absent" in text for text in report["limitations"])


@pytest.mark.parametrize("status", ["completed", "completed_with_errors", "failed", "interrupted"])
def test_eligible_run_metadata_preserves_partial_denominators(benchmark_sample, status):
    _run_metadata(benchmark_sample[2], status)
    report = build_report(*benchmark_sample)
    assert report["provenance"]["run_integrity"]["declared_claims_checked"] is True
    assert report["provenance"]["run_integrity"]["run_status"] == status
    assert report["provenance"]["detection_contract_checked"] is True
    assert report["summary"]["counts"]["planned"] == 3
    assert report["summary"]["counts"]["not_attempted"] == 2


@pytest.mark.parametrize(
    "change",
    [
        {"score": 0.49, "above_threshold": False},
        {"score": 0.8, "above_threshold": False},
        {"score": 0.8, "above_threshold": 1},
        {"label": 1},
        {"label": 40.0},
        {"category": "baseball bat"},
        {"center_xy": [20, 20]},
    ],
)
def test_benchmark_detection_contract_cannot_override_scored_point(benchmark_sample, change):
    benchmark_sample[2]["frames"][0]["detections"][0].update(change)
    with pytest.raises(ValueError, match="benchmark"):
        build_report(*benchmark_sample)


@pytest.mark.parametrize("key", ["label", "box_xyxy", "center_xy", "score", "above_threshold"])
def test_benchmark_detection_requires_core_fields(benchmark_sample, key):
    del benchmark_sample[2]["frames"][0]["detections"][0][key]
    with pytest.raises(ValueError, match="requires"):
        build_report(*benchmark_sample)


def test_benchmark_candidate_without_detection_rejected(benchmark_sample):
    benchmark_sample[2]["frames"][0]["detections"] = []
    with pytest.raises(ValueError, match="selection_status"):
        build_report(*benchmark_sample)


def test_benchmark_multiple_high_scores_cannot_be_candidate(benchmark_sample):
    benchmark_sample[2]["frames"][0]["detections"].append(_detection((30, 30, 40, 40), 0.9))
    with pytest.raises(ValueError, match="selection_status"):
        build_report(*benchmark_sample)


def test_benchmark_point_must_be_selected_centroid(benchmark_sample):
    benchmark_sample[2]["frames"][0]["point"] = [20, 20]
    with pytest.raises(ValueError, match="uniquely selected"):
        build_report(*benchmark_sample)


def test_benchmark_uses_inclusive_threshold(benchmark_sample):
    row = benchmark_sample[2]["frames"][0]
    row["detections"][0]["score"] = 0.5
    row.pop("engine_response")
    report = build_report(*benchmark_sample)
    assert report["summary"]["counts"]["candidate"] == 1


@pytest.mark.parametrize("selection", ["no_candidate", "ambiguous"])
def test_benchmark_valid_abstentions_keep_full_denominator(benchmark_sample, selection):
    row = benchmark_sample[2]["frames"][0]
    row.pop("engine_response")
    row["selection_status"], row["point"] = selection, None
    row["detections"] = [] if selection == "no_candidate" else [_detection(), _detection(score=0.9)]
    report = build_report(*benchmark_sample)
    assert report["summary"]["counts"][selection] == 1
    assert report["summary"]["fixed_pixel_sensitivity"]["cutoffs"][0]["denominator"] == 3


@pytest.mark.parametrize("field", ["threshold", "selection_status", "candidate", "detections"])
def test_benchmark_engine_snapshot_must_match_scored_contract(benchmark_sample, field):
    row = benchmark_sample[2]["frames"][0]
    row["engine_response"][field] = {
        "threshold": 0.4,
        "selection_status": "ambiguous",
        "candidate": None,
        "detections": [],
    }[field]
    with pytest.raises(ValueError, match="engine_response"):
        build_report(*benchmark_sample)


def test_cropped_benchmark_boxes_must_remain_in_declared_crop(benchmark_sample):
    predictions = benchmark_sample[2]
    predictions["input_view"] = "legacy_main_crop"
    row = predictions["frames"][0]
    row.pop("engine_response")
    row["detections"] = [_detection((0, 0, 20, 20))]
    row["point"] = row["detections"][0]["center_xy"]
    with pytest.raises(ValueError, match="input view"):
        build_report(*benchmark_sample)


def test_first_pass_timing_keeps_errors_and_uses_explicit_available_counts(sample):
    report = build_report(*sample)
    timing = report["summary"]["first_pass_timing_seconds"]
    assert timing["model_seconds"]["n"] == 5
    assert timing["service_seconds"]["n"] == 6
    assert report["frames"][4]["error"] == "runtime unavailable"
    assert report["summary"]["counts"]["not_attempted"] == 1


def test_cli_invalidated_run_does_not_write_report(tmp_path, benchmark_sample):
    benchmark_sample[2].update(
        run_status="invalidated",
        frozen_inputs_unchanged=False,
        eligible_for_development_comparison=False,
    )
    paths = write_inputs(tmp_path, benchmark_sample)
    output = tmp_path / "invalidated-report.json"
    with pytest.raises(ValueError, match="ineligible"):
        main(arguments(paths, output))
    assert not output.exists()

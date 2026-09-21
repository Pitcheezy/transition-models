"""Regression coverage for the formerly shuffled point/sequence target contract."""

import importlib.util
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import pytest
import torch

from src.data.features import CONTINUOUS_FEATURES, PITCH_TYPES
from src.data.point_data import (
    CLASS_NAMES,
    load_point_data,
    make_point_data,
    pitch_ids,
    validate_point_data,
    validate_split_ids,
)
from src.data.preprocess import (
    build_vectors_batch,
    extract_labels_10class,
    fit_scaler,
    sort_by_batter_and_time,
)
from src.evaluation.point_metrics import align_predictions, calibration_error, probability_metrics
from src.inference.transition_model import build_135dim_feature


def sample_frame():
    rows = []
    for i, (batter, description, event, strikes) in enumerate(
        [
            (20, "swinging_strike", "strikeout", 2),
            (10, "ball", None, 0),
            (30, "hit_into_play", "home_run", 1),
        ]
    ):
        rows.append(
            {
                **{column: float(i + 1) for column in CONTINUOUS_FEATURES},
                "game_pk": 100,
                "at_bat_number": i + 1,
                "pitch_number": 1,
                "batter": batter,
                "game_date": pd.Timestamp("2024-08-01"),
                "description": description,
                "events": event,
                "pitch_type": "FF",
                "zone": 5,
                "balls": 0,
                "strikes": strikes,
                "outs_when_up": 0,
                "on_1b": None,
                "on_2b": None,
                "on_3b": None,
                "stand": "R",
                "p_throws": "R",
                "inning": 1,
            }
        )
    return pd.DataFrame(rows)


def payload():
    frame = sample_frame()
    vectors = build_vectors_batch(frame, fit_scaler(frame), PITCH_TYPES, model="B")
    return make_point_data(frame, vectors)


def test_real_vector_builder_and_loader_keep_targets_together(tmp_path):
    point = payload()
    sequence_labels = extract_labels_10class(sort_by_batter_and_time(sample_frame()))
    assert not np.array_equal(point["labels_10"], sequence_labels)
    torch.save({**point, "labels": point["labels_4"]}, tmp_path / "model_b_test.pt")
    np.save(tmp_path / "labels_10_test.npy", sequence_labels)
    loaded = load_point_data(tmp_path, "test")
    np.testing.assert_array_equal(loaded["labels"], [7, 0, 5])
    np.testing.assert_array_equal(loaded["pitch_ids"][:, 1], [1, 2, 3])
    assert loaded["vectors"][0, 50:53].argmax() == 2


def test_preprocessing_entrypoint_preserves_point_alignment(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[1] / "scripts/04_preprocess.py"
    spec = importlib.util.spec_from_file_location("preprocess_entry", script)
    entry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(entry)
    frames = []
    for game, date in enumerate(["2023-07-01", "2024-05-01", "2024-08-01"]):
        frame = sample_frame()
        frame["game_date"] = date
        frame["game_pk"] = game + 1
        frame["hit_location"] = np.nan
        frames.append(frame)
    monkeypatch.setattr(entry, "load_seasons", lambda years: pd.concat(frames, ignore_index=True))
    output = tmp_path / "generated"
    monkeypatch.setattr(sys, "argv", [str(script), "--output-dir", str(output)])
    entry.main()
    for split in ("train", "val", "test"):
        data = load_point_data(output, split)
        np.testing.assert_array_equal(data["labels"], [7, 0, 5])
        assert not np.array_equal(data["labels"], np.load(output / f"labels_10_{split}.npy"))
    with pytest.raises(FileExistsError):
        entry.main()


def test_legacy_files_fail_closed(tmp_path):
    torch.save({"vectors": np.zeros((3, 77)), "labels": np.zeros(3)}, tmp_path / "model_b_test.pt")
    np.save(tmp_path / "labels_10_test.npy", [0, 1, 2])
    with pytest.raises(ValueError, match="Unaligned legacy"):
        load_point_data(tmp_path, "test")


@pytest.mark.parametrize(
    "problem", ["length", "duplicate", "nan", "class_order", "fractional_label"]
)
def test_reject_invalid_point_contract(problem):
    point = payload()
    if problem == "length":
        point["labels_10"] = np.array([0])
    elif problem == "duplicate":
        point["pitch_ids"][1] = point["pitch_ids"][0]
    elif problem == "nan":
        point["vectors"][0, 0] = np.nan
    elif problem == "class_order":
        point["class_names"] = CLASS_NAMES[::-1]
    else:
        point["labels_10"] = np.array([0.5, 1, 2])
    with pytest.raises(ValueError):
        validate_point_data(point)


@pytest.mark.parametrize("key_value", [np.nan, 1.5])
def test_reject_missing_or_fractional_pitch_key(key_value):
    frame = sample_frame().astype({"game_pk": float})
    frame.loc[0, "game_pk"] = key_value
    with pytest.raises(ValueError, match="finite integers"):
        pitch_ids(frame)


def test_npz_common_mask_and_requested_width(tmp_path):
    point = payload()
    point["vectors"] = np.pad(point["vectors"], ((0, 0), (0, 58)))
    point["labels_10"][1] = -1
    np.savez(tmp_path / "point_test.npz", **point)
    loaded = load_point_data(tmp_path, "test", 77)
    assert loaded["vectors"].shape == (2, 77)
    np.testing.assert_array_equal(loaded["pitch_ids"][:, 1], [1, 3])
    with pytest.raises(ValueError, match="unavailable"):
        load_point_data(tmp_path, "test", 151)


def test_unmapped_dataframe_labels_become_negative_sentinel():
    frame = sample_frame()
    frame.loc[1, "description"] = "unmapped_event"
    vectors = build_vectors_batch(frame, fit_scaler(frame), PITCH_TYPES, model="B")
    point = make_point_data(frame, vectors)
    assert point["labels_4"][1] == point["labels_10"][1] == -1


def test_cross_split_overlap_is_rejected():
    with pytest.raises(ValueError, match="overlap"):
        validate_split_ids({"train": payload(), "test": payload()})


def predictions():
    point = payload()
    return {
        "pitch_ids": point["pitch_ids"],
        "targets": point["labels_10"],
        "class_names": CLASS_NAMES,
        "probs": np.eye(10)[point["labels_10"]],
    }


def test_prediction_reordering_is_identity_based():
    reference = predictions()
    order = [2, 0, 1]
    candidate = {
        key: value[order] if key != "class_names" else value for key, value in reference.items()
    }
    np.testing.assert_array_equal(align_predictions(reference, candidate), reference["probs"])


@pytest.mark.parametrize(
    "problem", ["missing_ids", "different_cohort", "duplicate", "wrong_target", "class_order"]
)
def test_incomparable_predictions_fail(problem):
    reference, candidate = predictions(), predictions()
    if problem == "missing_ids":
        del candidate["pitch_ids"]
    elif problem == "different_cohort":
        candidate["pitch_ids"][0, 0] += 1
    elif problem == "duplicate":
        candidate["pitch_ids"][1] = candidate["pitch_ids"][0]
    elif problem == "wrong_target":
        candidate["targets"][0] = 1
    else:
        candidate["class_names"] = CLASS_NAMES[::-1]
    with pytest.raises(ValueError):
        align_predictions(reference, candidate)


def test_probability_metrics_include_endpoint_bins_and_nonzero_rare_mass():
    assert calibration_error(np.array([0.0, 1.0]), np.array([0.0, 1.0])) == 0
    perfect = predictions()
    result = probability_metrics(perfect["probs"], perfect["targets"])
    assert result["ce"] == result["brier"] == result["ece_15"] == 0
    uniform = probability_metrics(np.full((3, 10), 0.1), perfect["targets"])
    assert uniform["per_class"]["HomeRun"]["recall"] == 0
    assert uniform["per_class"]["HomeRun"]["mean_probability"] == pytest.approx(0.1)
    assert uniform["ce"] == pytest.approx(np.log(10))
    assert uniform["brier"] == pytest.approx(0.9)


@pytest.mark.parametrize("value", [np.nan, -0.1, 1.1])
def test_invalid_probabilities_rejected(value):
    probs = np.full((3, 10), 0.1)
    probs[0, 0] = value
    with pytest.raises(ValueError):
        probability_metrics(probs, np.array([0, 1, 2]))


@pytest.mark.parametrize("cluster_value", [2, "2"])
def test_inference_builder_accepts_json_integer_cluster_ids(cluster_value):
    cluster = {
        "count_cluster_id_scaled": 1.5,
        "arsenal_func_scaled": [0.25] * 32,
        "arsenal_moment_scaled": [0.5] * 20,
    }
    arsenal = {"pitcher_to_cluster": {"123": cluster_value}, "clusters": {"2": cluster}}
    by_pitcher = build_135dim_feature(np.zeros(77), arsenal, pitcher_id=123)
    explicit = build_135dim_feature(np.zeros(77), arsenal, pitcher_cluster=2)
    np.testing.assert_array_equal(by_pitcher, explicit)
    assert by_pitcher[82] == 1.5


def test_comparison_checks_canonical_truth_even_when_runs_agree(tmp_path, monkeypatch):
    script = Path(__file__).resolve().parents[1] / "scripts/49_compare_aligned_runs.py"
    spec = importlib.util.spec_from_file_location("comparison_entry", script)
    entry = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(entry)
    data_dir, run_dir = tmp_path / "data", tmp_path / "run"
    data_dir.mkdir()
    run_dir.mkdir()
    (run_dir / "manifest.json").write_text(json.dumps({"status": "complete"}))
    for split in ("val", "test"):
        np.savez(data_dir / f"point_{split}.npz", **payload())
        prediction = predictions()
        prediction["targets"] = prediction["targets"][::-1]
        np.savez(run_dir / f"predictions_{split}.npz", **prediction)
    monkeypatch.setattr(
        sys,
        "argv",
        [
            str(script),
            "--data-dir",
            str(data_dir),
            "--runs",
            str(run_dir),
            "--output",
            str(tmp_path / "out.json"),
        ],
    )
    with pytest.raises(ValueError, match="canonical test"):
        entry.main()

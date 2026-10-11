"""Synthetic fold isolation, checkpoint barrier, frozen inputs, and full denominators."""

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image

from intent import local_point_experiment as experiment


def write(path, document):
    path.write_text(json.dumps(document), encoding="utf-8")


def read(path):
    return json.loads(path.read_bytes())


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    counts = {823407: (3, 2), 849845: (4, 3)}
    monkeypatch.setattr(experiment, "EXPECTED_COUNTS", counts)
    code = tmp_path / "synthetic_model.py"
    code.write_text("# fake backend, never executed")
    monkeypatch.setattr(experiment, "REQUIRED_CODE_FILES", {code.resolve()})
    frames, refs = [], []
    for game, (total, marked) in counts.items():
        size = (40, 30) if game == 823407 else (48, 36)
        crop = [4, 2, size[0] - 4, size[1] - 4]
        for index in range(total):
            path = tmp_path / f"{game}_{index}.jpg"
            Image.new("RGB", size, (40 if game == 823407 else 150, index * 40, 60)).save(path)
            frame = {
                "observation_id": f"{game}:1:{index + 1}",
                "game_pk": game,
                "image_path": str(path),
                "image_sha256": experiment._sha(path.read_bytes()),
                "width": size[0],
                "height": size[1],
                "legacy_main_crop": crop,
            }
            frames.append(frame)
            uv = (
                [0.25, 0.5][index]
                if game == 823407 and index < marked
                else [0.2, 0.4, 0.8][index]
                if index < marked
                else None
            )
            point = (
                [crop[0] + uv * (crop[2] - crop[0]), crop[1] + uv * (crop[3] - crop[1])]
                if uv is not None
                else None
            )
            refs.append(
                {
                    "observation_id": frame["observation_id"],
                    "game_pk": game,
                    "image_sha256": frame["image_sha256"],
                    "legacy_mitt_status": "marked" if point else "not_in_setup",
                    "mitt": point,
                }
            )
    manifest = tmp_path / "manifest.json"
    references = tmp_path / "references.json"
    write(manifest, {"schema": "local_glove_frames_v1", "frames": frames})
    write(
        references,
        {
            "schema": "local_glove_references_v1",
            "manifest_sha256": experiment._sha(manifest.read_bytes()),
            "references": refs,
        },
    )
    plan = {
        "schema": experiment.PLAN_SCHEMA,
        "manifest": str(manifest),
        "manifest_sha256": experiment._sha(manifest.read_bytes()),
        "references": str(references),
        "references_sha256": experiment._sha(references.read_bytes()),
        "directions": experiment.DIRECTIONS,
        "device": "cpu",
        **experiment.SETTINGS,
        "code_files": [{"path": str(code), "sha256": experiment._sha(code.read_bytes())}],
    }
    plan_path = tmp_path / "plan.json"
    write(plan_path, plan)
    return plan_path, tmp_path / "new_run"


class Backend:
    def __init__(
        self,
        *,
        fail_training=False,
        invalid_prediction=False,
        short_prediction=False,
        after_train=None,
    ):
        self.calls = []
        self.fail_training = fail_training
        self.invalid_prediction = invalid_prediction
        self.short_prediction = short_prediction
        self.after_train = after_train

    def train_point_model(self, images, normalized_points, *, seed, device):
        assert images.dtype == normalized_points.dtype == np.float32
        assert images.shape[1:] == (3, 128, 192)
        assert len(images) in (2, 3) and device == "cpu"
        assert normalized_points.shape == (len(images), 2)
        expected = (
            [[0.25, 0.25], [0.5, 0.5]] if len(images) == 2 else [[0.2, 0.2], [0.4, 0.4], [0.8, 0.8]]
        )
        np.testing.assert_allclose(normalized_points, expected)
        self.calls.append(("train", len(images), seed))
        if self.fail_training and len(self.calls) == 1:
            raise RuntimeError("synthetic training failure")
        if self.after_train:
            self.after_train()
        checkpoint = {
            "metadata": {"seed": seed, "train_count": len(images), "epochs_completed": 20},
            "mean": normalized_points.mean(axis=0).tolist(),
        }
        return object(), checkpoint

    def load_point_model(self, path, *, device, expected_sha256):
        assert sum(row[0] == "train" for row in self.calls) == 6
        assert (path.parent.parent / "checkpoint_ledger.json").is_file()
        assert experiment._sha(path.read_bytes()) == expected_sha256 and device == "cpu"
        self.calls.append(("load", path.name))
        model = read(path)
        return model, model["metadata"]

    def predict_points(self, model, images, *, device):
        assert device == "cpu" and len(images) != model["metadata"]["train_count"]
        self.calls.append(("predict", len(images)))
        result = np.tile(np.asarray(model["mean"], dtype=np.float32), (len(images), 1))
        if self.invalid_prediction:
            result[0, 0] = np.nan
        return result[:-1] if self.short_prediction else result


def save_checkpoint(checkpoint, path):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(checkpoint, stream)


def test_train_game_isolation_and_all_six_checkpoint_barrier(fixture):
    backend = Backend()
    report = experiment.run(*fixture, backend=backend, checkpoint_writer=save_checkpoint)
    assert report["status"] == "completed"
    assert [row[0] for row in backend.calls[:6]] == ["train"] * 6
    assert len(report["checkpoints"]) == 6
    assert report["unique_marked_frames"] == 5 and report["prediction_rows_planned"] == 15
    assert report["seed_repetitions_are_independent_samples"] is False
    assert len(report["per_seed"]) == 3
    assert all(
        seed["planned_marked"] == 5 and seed["prediction_states"] == {"completed": 5}
        for seed in report["per_seed"]
    )
    assert len(report["excluded"]) == 2
    assert all(row["reason"] == "legacy_nonmarked_is_not_a_negative" for row in report["excluded"])
    assert str(fixture[0].parent) not in json.dumps(report)
    for relative_path, digest in report["artifact_sha256"].items():
        assert not Path(relative_path).is_absolute()
        assert experiment._sha((fixture[1] / relative_path).read_bytes()) == digest
    events = read(fixture[1] / "events.json")["events"]
    frozen_index = next(
        i for i, row in enumerate(events) if row["event"] == "all_checkpoints_frozen"
    )
    assert sum(row["event"] == "training_completed" for row in events[:frozen_index]) == 6
    assert not any(row["event"].startswith("evaluation") for row in events[:frozen_index])
    first = report["arms"][0]
    assert first["planned_marked"] == 3
    assert first["baselines_all_marked"]["training_game_mean"]["normalized_point"] == [0.375, 0.375]
    paired = first["paired_model_minus_baseline"]["training_game_mean"]["distance_pixels"]
    assert paired["n"] == 3 and paired["median"] == pytest.approx(0, abs=1e-5)


def test_failed_training_prevents_every_evaluation(fixture):
    backend = Backend(fail_training=True)
    report = experiment.run(*fixture, backend=backend, checkpoint_writer=save_checkpoint)
    assert report["status"] == "training_incomplete"
    assert all(row[0] == "train" for row in backend.calls)
    assert not (fixture[1] / "checkpoint_ledger.json").exists()
    assert all(
        arm["prediction_states"] == {"not_attempted": arm["planned_marked"]}
        for arm in report["arms"]
    )


@pytest.mark.parametrize("kind", ["point", "short"])
def test_prediction_failures_preserve_primary_denominator(fixture, kind):
    backend = Backend(invalid_prediction=kind == "point", short_prediction=kind == "short")
    report = experiment.run(*fixture, backend=backend, checkpoint_writer=save_checkpoint)
    assert report["status"] == "completed_with_errors"
    for arm in report["arms"]:
        assert sum(arm["prediction_states"].values()) == arm["planned_marked"]
        expected_errors = 1 if kind == "point" else arm["planned_marked"]
        assert arm["prediction_states"]["error"] == expected_errors
        assert (
            arm["baselines_all_marked"]["crop_center"]["errors"]["distance_pixels"]["n"]
            == arm["planned_marked"]
        )
        assert (
            arm["paired_model_minus_baseline"]["crop_center"]["distance_pixels"]["n"]
            == arm["planned_marked"] - expected_errors
        )


def rebind_reference(fixture, mutate):
    plan = read(fixture[0])
    path = Path(plan["references"])
    document = read(path)
    mutate(document)
    write(path, document)
    plan["references_sha256"] = experiment._sha(path.read_bytes())
    write(fixture[0], plan)


@pytest.mark.parametrize("kind", ["out_of_crop", "duplicate", "hash", "nan"])
def test_bad_reference_rejected_before_outputs(fixture, kind):
    def mutate(document):
        first = document["references"][0]
        if kind == "out_of_crop":
            first["mitt"] = [2, 6]
        elif kind == "duplicate":
            document["references"].append(first.copy())
        elif kind == "hash":
            first["image_sha256"] = "0" * 64
        else:
            first["mitt"] = [float("nan"), 6]

    rebind_reference(fixture, mutate)
    with pytest.raises(ValueError):
        experiment.run(*fixture, backend=Backend(), checkpoint_writer=save_checkpoint)
    assert not fixture[1].exists()


def test_changed_source_during_training_aborts_evaluation(fixture):
    plan = read(fixture[0])
    source = Path(read(Path(plan["manifest"]))["frames"][0]["image_path"])
    backend = Backend(after_train=lambda: source.write_bytes(source.read_bytes() + b"changed"))
    report = experiment.run(*fixture, backend=backend, checkpoint_writer=save_checkpoint)
    assert report["status"] == "invalid_frozen_inputs" and not report["results_usable"]
    assert len(backend.calls) == 1 and backend.calls[0][0] == "train"
    assert all(arm["model_errors"] is None for arm in report["arms"])


def test_changed_code_before_run_is_rejected(fixture):
    path = Path(read(fixture[0])["code_files"][0]["path"])
    path.write_text("changed source")
    with pytest.raises(ValueError, match="code binding"):
        experiment.run(*fixture, backend=Backend(), checkpoint_writer=save_checkpoint)
    assert not fixture[1].exists()


def test_ledger_changed_after_last_evaluation_invalidates_report(fixture, monkeypatch):
    original_write = experiment._write

    def write_and_tamper(path, value):
        digest = original_write(path, value)
        if path.parent.name == "evaluation" and path.stem == "train_849845_seed_44":
            ledger = fixture[1] / "checkpoint_ledger.json"
            ledger.write_bytes(ledger.read_bytes() + b" ")
        return digest

    monkeypatch.setattr(experiment, "_write", write_and_tamper)
    report = experiment.run(*fixture, backend=Backend(), checkpoint_writer=save_checkpoint)
    assert report["status"] == "invalid_frozen_inputs" and not report["results_usable"]
    assert all(arm["model_errors"] is None for arm in report["arms"])
    expected = report["artifact_sha256"]["checkpoint_ledger.json"]
    assert report["checkpoint_ledger_sha256"] == expected
    assert experiment._sha((fixture[1] / "checkpoint_ledger.json").read_bytes()) != expected


@pytest.mark.parametrize(
    "relative_path",
    [
        "plan.json",
        "run_manifest.json",
        "training/train_823407_seed_42.json",
        "evaluation/train_823407_seed_42.json",
        "events.json",
    ],
)
def test_output_json_keeps_write_time_hash_and_rejects_changes(fixture, monkeypatch, relative_path):
    original_write = experiment._write
    frozen = {}

    def write_and_tamper(path, value):
        digest = original_write(path, value)
        if path.name == "events.json":
            target = fixture[1] / relative_path
            frozen["sha256"] = experiment._sha(target.read_bytes())
            document = read(target)
            if relative_path.startswith("evaluation/"):
                document["predictions"][0]["normalized_point"] = [0.01, 0.99]
            else:
                document["unexpected_change"] = True
            write(target, document)
        return digest

    monkeypatch.setattr(experiment, "_write", write_and_tamper)
    report = experiment.run(*fixture, backend=Backend(), checkpoint_writer=save_checkpoint)
    assert report["status"] == "invalid_frozen_inputs" and not report["results_usable"]
    assert all(arm["model_errors"] is None for arm in report["arms"])
    assert report["artifact_sha256"][relative_path] == frozen["sha256"]
    assert experiment._sha((fixture[1] / relative_path).read_bytes()) != frozen["sha256"]


def test_existing_output_is_never_reused(fixture):
    fixture[1].mkdir()
    with pytest.raises(FileExistsError):
        experiment.run(*fixture, backend=Backend(), checkpoint_writer=save_checkpoint)

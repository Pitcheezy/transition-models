"""Fake-engine checks for immutable benchmark inputs and partial first-pass records."""

import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from PIL import Image

from intent.local_glove_benchmark import (
    PLAN_SCHEMA,
    REQUIRED_CODE_FILES,
    FrozenInputError,
    run,
)


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write_json(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def planned(tmp_path):
    frames = []
    for index in range(3):
        path = tmp_path / f"image-{index}.jpg"
        with Image.new("RGB", (16, 16), (40 + 40 * index, 20, 10)) as image:
            image.save(path, format="JPEG", quality=100)
        frames.append(
            {
                "observation_id": f"observation-{index}",
                "game_pk": 849843,
                "image_sha256": digest(path),
                "width": 16,
                "height": 16,
                "legacy_main_crop": [2, 2, 14, 14],
                "image_path": str(path),
            }
        )
    manifest = tmp_path / "manifest.json"
    write_json(manifest, {"schema": "local_glove_frames_v1", "frames": frames})
    weights = tmp_path / "weights.pth"
    weights.write_bytes(b"fake checkpoint, never loaded by torch")
    extra_code = tmp_path / "extra-code.py"
    extra_code.write_text("# frozen optional dependency\n", encoding="utf-8")
    code_files = [
        {"path": str(path), "sha256": digest(path)}
        for path in sorted(REQUIRED_CODE_FILES) + [extra_code]
    ]
    plan = {
        "schema": PLAN_SCHEMA,
        "manifest": str(manifest),
        "manifest_sha256": digest(manifest),
        "model_id": "ssdlite320_mobilenet_v3_large",
        "weights": str(weights),
        "weights_sha256": digest(weights),
        "input_view": "full_frame",
        "threshold": 0.5,
        "device": "cpu",
        "threads": 1,
        "warmups": 1,
        "passes": 2,
        "code_files": code_files,
    }
    path = tmp_path / "plan.json"
    write_json(path, plan)
    return {
        "path": path,
        "plan": plan,
        "manifest": manifest,
        "weights": weights,
        "extra_code": extra_code,
        "frames": frames,
        "out": tmp_path / "new-run",
    }


class Clock:
    def __init__(self):
        self.value = 0

    def __call__(self):
        self.value += 0.01
        return self.value


def engine_factory(actions=None, load_hook=None, metadata=False):
    instances = []
    actions = actions or {}

    class FakeEngine:
        def __init__(self, *args, **kwargs):
            self.args, self.kwargs = args, kwargs
            self.calls = []
            instances.append(self)

        def load(self):
            if metadata:
                self.runtime_versions = {"torch": "fake-torch", "torchvision": "fake-vision"}
                self.provenance = {"fixture": True, "offline": True}
            if load_hook:
                load_hook()

        def predict(self, image, *, crop, threshold):
            self.calls.append(
                {"crop": crop, "threshold": threshold, "pixel": image.getpixel((0, 0))}
            )
            action = actions.get(len(self.calls))
            if isinstance(action, BaseException):
                raise action
            if callable(action):
                action()
            if isinstance(action, dict):
                return deepcopy(action)
            detection = {
                "center_xy": [8, 8],
                "box_xyxy": [6, 6, 10, 10],
                "score": 0.9,
                "label": 40,
                "above_threshold": True,
            }
            return {
                "selection_status": "candidate",
                "candidate": detection,
                "detections": [detection],
                "model_seconds": 0.001,
                "runtime_versions": {"backend": "fake-response"},
                "weights_sha256": self.args[2],
            }

    return FakeEngine, instances


def execute(planned, **engine_options):
    factory, instances = engine_factory(**engine_options)
    summary = run(planned["path"], planned["out"], engine_factory=factory, clock=Clock())
    predictions = json.loads((planned["out"] / "predictions.json").read_text(encoding="utf-8"))
    return summary, predictions, instances


def test_fixed_passes_first_pass_only_and_attempt_hash_timing_binding(planned):
    summary, predictions, instances = execute(planned)
    assert summary["status"] == "completed"
    assert summary["planned_frames"] == 3
    assert summary["planned_passes"] == 2
    assert summary["measured_attempts"] == 6
    assert summary["first_pass_attempted"] == summary["first_pass_completed"] == 3
    assert summary["first_pass_errors"] == summary["first_pass_not_attempted"] == 0
    assert len(predictions["frames"]) == 3
    assert len(instances[0].calls) == 7  # one blank warmup, then exactly two passes
    assert instances[0].calls[0]["pixel"] == (0, 0, 0)
    assert summary["predictions_sha256"] == digest(planned["out"] / "predictions.json")
    assert summary["plan_sha256"] == digest(planned["out"] / "plan.json")
    assert summary["frozen_inputs_unchanged"] is True
    assert all(row["status"] == "unchanged" for row in summary["frozen_input_checks"])
    for row in predictions["frames"]:
        attempt = planned["out"] / row["attempt_file"]["path"]
        assert row["attempt_file"]["sha256"] == digest(attempt)
        raw = json.loads(attempt.read_text(encoding="utf-8"))
        assert raw["timing"]["service_seconds"] is None
        assert row["timing"]["service_seconds"] == pytest.approx(0.01)
        assert row["engine_response"]["runtime_versions"] == {"backend": "fake-response"}
    for timing in summary["timings"]:
        assert timing["attempt_sha256"] == digest(planned["out"] / timing["attempt_path"])
    assert summary["engine_metadata"] == {}  # fake engines need no optional attributes


def test_completed_with_errors_preserves_first_failure_despite_later_success(planned):
    summary, predictions, _ = execute(planned, actions={2: RuntimeError("first frame failed")})
    assert summary["status"] == "completed_with_errors"
    assert summary["first_pass_completed"] == 2
    assert summary["first_pass_errors"] == summary["error_attempts"] == 1
    assert summary["completed_attempts"] == 5
    assert predictions["frames"][0]["status"] == "error"
    assert predictions["frames"][0]["error"] == "RuntimeError"
    repeated = json.loads(
        (planned["out"] / "attempts/pass_01_frame_000.json").read_text(encoding="utf-8")
    )
    assert repeated["status"] == "completed"


def test_repeat_failure_is_separate_from_successful_first_pass(planned):
    summary, predictions, _ = execute(planned, actions={5: RuntimeError("repeat failed")})
    assert summary["status"] == "completed_with_errors"
    assert summary["first_pass_errors"] == 0
    assert summary["error_attempts"] == 1
    assert all(row["status"] == "completed" for row in predictions["frames"])


def test_interrupt_persists_attempt_and_missing_denominator(planned):
    summary, predictions, instances = execute(planned, actions={3: KeyboardInterrupt()})
    assert summary["status"] == "interrupted"
    assert summary["failure"] == "KeyboardInterrupt"
    assert summary["first_pass_attempted"] == summary["measured_attempts"] == 2
    assert summary["first_pass_completed"] == summary["first_pass_errors"] == 1
    assert summary["first_pass_not_attempted"] == 1
    assert [r["status"] for r in predictions["frames"]] == ["completed", "error"]
    assert predictions["frames"][-1]["error"] == "KeyboardInterrupt"
    assert len(instances[0].calls) == 3
    assert len(list((planned["out"] / "attempts").iterdir())) == 2


def test_startup_failure_still_emits_empty_first_pass(planned):
    def fail():
        raise RuntimeError("cannot load")

    summary, predictions, _ = execute(planned, load_hook=fail)
    assert summary["status"] == "failed"
    assert summary["startup_seconds"] is None
    assert summary["first_pass_attempted"] == summary["measured_attempts"] == 0
    assert summary["first_pass_not_attempted"] == 3
    assert predictions["frames"] == []


@pytest.mark.parametrize("name", ["path", "manifest", "weights", "extra_code"])
@pytest.mark.parametrize("missing", [False, True])
def test_final_missing_or_changed_input_persists_invalidated_summary(planned, name, missing):
    path = planned[name]

    def change():
        if missing:
            path.unlink()
        else:
            path.write_bytes(b"changed after preflight")

    summary, predictions, _ = execute(planned, load_hook=change)
    assert summary["status"] == "invalidated"
    assert summary["failure"] == "FrozenInputsChanged"
    assert summary["execution_status"] == "completed"
    assert summary["first_pass_attempted"] == 3
    assert summary["frozen_inputs_unchanged"] is False
    assert predictions["run_status"] == "invalidated"
    assert predictions["eligible_for_development_comparison"] is False
    changed = [row for row in summary["frozen_input_checks"] if row["path"] == str(path)]
    assert len(changed) == 1
    assert changed[0]["status"] == ("unavailable" if missing else "changed")
    assert json.loads((planned["out"] / "benchmark.json").read_text())["status"] == "invalidated"


def test_image_changed_after_last_read_invalidates_successful_prediction(planned):
    path = planned["frames"][-1]["image_path"]
    summary, predictions, _ = execute(
        planned, actions={7: lambda: Path(path).write_bytes(b"changed after final image read")}
    )
    assert summary["status"] == "invalidated"
    assert summary["execution_status"] == "completed"
    assert predictions["frames"][-1]["status"] == "completed"
    assert any(
        row["kind"] == "image" and row["status"] == "changed"
        for row in summary["frozen_input_checks"]
    )


def test_image_missing_during_run_is_error_and_invalidated(planned):
    image = Path(planned["frames"][0]["image_path"])
    summary, predictions, _ = execute(planned, load_hook=image.unlink)
    assert summary["status"] == "invalidated"
    assert summary["execution_status"] == "completed_with_errors"
    assert summary["first_pass_errors"] == 1
    assert summary["error_attempts"] == 2
    assert predictions["frames"][0]["error"] == "FrozenInputError"
    assert len(summary["input_integrity_failures"]) == 2


@pytest.mark.parametrize("name", ["manifest", "weights", "extra_code"])
def test_preflight_hash_mismatch_never_constructs_engine(planned, name):
    planned[name].write_bytes(b"changed before run")
    factory, instances = engine_factory()
    with pytest.raises(ValueError):
        run(planned["path"], planned["out"], engine_factory=factory)
    assert instances == []
    assert not planned["out"].exists()


def test_preflight_image_hash_mismatch_rejected(planned):
    Path(planned["frames"][0]["image_path"]).write_bytes(b"changed")
    factory, instances = engine_factory()
    with pytest.raises(FrozenInputError, match="Image bytes changed"):
        run(planned["path"], planned["out"], engine_factory=factory)
    assert instances == []
    assert not planned["out"].exists()


def test_output_is_never_overwritten_or_implicitly_resumed(planned):
    execute(planned)
    before = {
        p.relative_to(planned["out"]): p.read_bytes()
        for p in planned["out"].rglob("*")
        if p.is_file()
    }
    factory, instances = engine_factory()
    with pytest.raises(FileExistsError):
        run(planned["path"], planned["out"], engine_factory=factory)
    after = {
        p.relative_to(planned["out"]): p.read_bytes()
        for p in planned["out"].rglob("*")
        if p.is_file()
    }
    assert before == after
    assert instances == []


def test_binding_must_include_actual_runner_and_detector_paths(planned, tmp_path):
    # Copies with the right basenames do not bind the executable source files.
    copied = []
    for source in sorted(REQUIRED_CODE_FILES):
        path = tmp_path / source.name
        path.write_bytes(source.read_bytes())
        copied.append({"path": str(path), "sha256": digest(path)})
    planned["plan"]["code_files"] = copied
    write_json(planned["path"], planned["plan"])
    factory, instances = engine_factory()
    with pytest.raises(ValueError, match="Actual benchmark runner and detector"):
        run(planned["path"], planned["out"], engine_factory=factory)
    assert instances == []


def test_duplicate_code_binding_is_rejected(planned):
    planned["plan"]["code_files"].append(deepcopy(planned["plan"]["code_files"][0]))
    write_json(planned["path"], planned["plan"])
    with pytest.raises(ValueError, match="Duplicate code binding"):
        run(planned["path"], planned["out"], engine_factory=engine_factory()[0])


@pytest.mark.parametrize("passes", [0, 4, True])
def test_pass_count_is_bounded_at_three(planned, passes):
    planned["plan"]["passes"] = passes
    write_json(planned["path"], planned["plan"])
    with pytest.raises(ValueError, match="Invalid bounded integer"):
        run(planned["path"], planned["out"], engine_factory=engine_factory()[0])


def test_optional_engine_metadata_and_response_provenance_preserved(planned):
    summary, predictions, _ = execute(planned, metadata=True)
    assert summary["engine_metadata"] == {
        "runtime_versions": {"torch": "fake-torch", "torchvision": "fake-vision"},
        "provenance": {"fixture": True, "offline": True},
    }
    assert predictions["engine_metadata"] == summary["engine_metadata"]
    assert (
        predictions["frames"][0]["engine_response"]["weights_sha256"]
        == planned["plan"]["weights_sha256"]
    )


def test_fixed_crop_and_threshold_are_passed_to_every_call(planned):
    planned["plan"]["input_view"] = "legacy_main_crop"
    planned["plan"]["threshold"] = 0.7
    planned["plan"]["passes"] = 1
    write_json(planned["path"], planned["plan"])
    summary, _, instances = execute(planned)
    assert summary["planned_passes"] == 1
    assert all(
        call["crop"] == [2, 2, 14, 14] and call["threshold"] == 0.7 for call in instances[0].calls
    )


@pytest.mark.parametrize(
    "response",
    [
        {
            "selection_status": "candidate",
            "candidate": None,
            "detections": [],
            "model_seconds": 0.1,
        },
        {
            "selection_status": "no_candidate",
            "candidate": None,
            "detections": [],
            "model_seconds": float("nan"),
        },
        {
            "selection_status": "candidate",
            "candidate": {"center_xy": [16, 8]},
            "detections": [],
            "model_seconds": 0.1,
        },
    ],
)
def test_malformed_engine_result_becomes_persisted_error_not_truncated_success(planned, response):
    summary, predictions, _ = execute(planned, actions={2: response})
    assert summary["status"] == "completed_with_errors"
    assert predictions["frames"][0]["status"] == "error"
    assert predictions["frames"][0]["point"] is None
    path = planned["out"] / "attempts/pass_00_frame_000.json"
    assert json.loads(path.read_text())["status"] == "error"

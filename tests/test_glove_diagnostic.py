"""CV49b executes one fixed six-case comparison without another inference pass."""

import hashlib
import importlib.util
import json
from pathlib import Path

import pytest
from PIL import Image

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/80_diagnose_glove_candidates.py"
SPEC = importlib.util.spec_from_file_location("glove_diagnostic", SCRIPT)
diagnostic = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(diagnostic)


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


@pytest.fixture
def planned(tmp_path):
    frames = []
    for index in range(1, 4):
        image_path = tmp_path / f"p{index}.png"
        with Image.new("RGB", (1280, 720), (index, 0, 0)) as image:
            image.save(image_path)
        frames.append(
            {
                "pitch_key": f"849843:1:{index}",
                "play_id": f"00000000-0000-0000-0000-{index:012d}",
                "clip_sha256": str(index) * 64,
                "frame_pts": index * 100,
                "time_base": "1/90000",
                "image": image_path.name,
                "image_sha256": sha(image_path),
                "width": 1280,
                "height": 720,
                "context_crop": [450, 240, 660, 470],
            }
        )
    manifest = {
        "schema": "pitcheezy-object-reference-input-v1",
        "source_commit": "a" * 40,
        "source_review_sha256_lf": "b" * 64,
        "game_pk": 849843,
        "frames": frames,
    }
    input_path, plan_path, weights = (
        tmp_path / name for name in ("input.json", "plan.json", "weights.pth")
    )
    write(input_path, manifest)
    weights.write_bytes(b"synthetic checkpoint for fake engine only")
    plan = {
        "schema": diagnostic.SCHEMA,
        "input_sha256": sha(input_path),
        "model_name": diagnostic.MODEL,
        "weights_sha256": sha(weights),
        "threshold": 0.5,
        "device": "cuda",
        "threads": 4,
        "warmups": 0,
        "passes": 1,
        "code_files": {name: sha(diagnostic.ROOT / name) for name in diagnostic.REQUIRED_CODE},
        "expected_runtime": diagnostic.RUNTIME,
        "readings_sha256": {"codex": "c" * 64, "claude": "d" * 64},
    }
    write(plan_path, plan)
    return {
        "plan": plan,
        "manifest": manifest,
        "plan_path": plan_path,
        "input_path": input_path,
        "weights": weights,
        "output": tmp_path / "result",
        "private_root": tmp_path,
    }


def factory(*, load_hook=None, predict_hook=None):
    instances = []

    class FakeEngine:
        runtime_versions = diagnostic.RUNTIME.copy()

        def __init__(self, *args, **kwargs):
            self.args, self.kwargs, self.calls, self.loads = args, kwargs, [], 0
            instances.append(self)

        def load(self):
            self.loads += 1
            if load_hook:
                load_hook(self)

        def predict(self, image, **kwargs):
            self.calls.append((image, kwargs))
            if predict_hook:
                value = predict_hook(self)
                if value is not None:
                    return value
            return {
                "schema": "local_glove_detection_v1",
                "selection_status": "candidate",
                "detections": [
                    {
                        "box_xyxy": [451.25, 241.5, 480.75, 270.25],
                        "score": 0.6,
                        "above_threshold": True,
                    }
                ],
                "candidate": {"box_xyxy": [451.25, 241.5, 480.75, 270.25]},
                "model_seconds": 0.1,
                "crop_xyxy": kwargs["crop"],
            }

    return FakeEngine, instances


def run(planned, engine):
    return diagnostic.run(
        planned["plan_path"],
        planned["input_path"],
        planned["weights"],
        planned["output"],
        private_root=planned["private_root"],
        engine_factory=engine,
    )


def update_plan(planned):
    write(planned["plan_path"], planned["plan"])


def update_input(planned):
    write(planned["input_path"], planned["manifest"])
    planned["plan"]["input_sha256"] = sha(planned["input_path"])
    update_plan(planned)


def test_exact_six_calls_bind_same_bytes_and_keep_original_coordinates(planned):
    engine, instances = factory()
    report = run(planned, engine)
    instance = instances[0]
    assert len(instances) == instance.loads == 1
    assert len(instance.calls) == 6
    assert instance.kwargs == {"device": "cuda", "threads": 4}
    assert report["status"] == "completed"
    assert report["counts"] == {"completed": 6, "error": 0, "not_run": 0}
    for index, frame in enumerate(planned["manifest"]["frames"]):
        full, crop = instance.calls[index * 2 : index * 2 + 2]
        assert full[0] == crop[0] == (planned["input_path"].parent / frame["image"]).read_bytes()
        assert full[1] == {"image_sha256": frame["image_sha256"], "threshold": 0.5, "crop": None}
        assert crop[1]["crop"] == frame["context_crop"]
    for row in report["frames"]:
        assert row["engine_response"]["candidate"]["box_xyxy"] == [451.25, 241.5, 480.75, 270.25]
        path = planned["output"] / row["attempt_file"]
        assert sha(path) == row["attempt_sha256"]
        assert json.loads(path.read_text())["engine_response"] == row["engine_response"]
    assert (planned["output"] / "plan.json").read_bytes() == planned["plan_path"].read_bytes()


@pytest.mark.parametrize(
    "field,value",
    [
        ("input_sha256", "0" * 64),
        ("weights_sha256", "0" * 64),
        ("threshold", 0.4),
        ("device", "cpu"),
        ("threads", 2),
        ("warmups", 1),
        ("passes", 2),
        ("model_name", "ssdlite320_mobilenet_v3_large"),
        ("expected_runtime", {}),
        ("readings_sha256", {"codex": "c" * 64}),
        ("code_files", {}),
    ],
)
def test_invalid_plan_rejected_before_engine_or_output(planned, field, value):
    engine, instances = factory()
    planned["plan"][field] = value
    update_plan(planned)
    with pytest.raises(ValueError):
        run(planned, engine)
    assert not instances and not planned["output"].exists()


@pytest.mark.parametrize("change", ["id", "crop", "dimensions", "image_hash", "duplicate"])
def test_invalid_frame_rejected_before_engine(planned, change):
    first = planned["manifest"]["frames"][0]
    if change == "id":
        first["pitch_key"] = "849843:2:1"
    elif change == "crop":
        first["context_crop"][0] += 1
    elif change == "dimensions":
        first["width"] = 1279
    elif change == "image_hash":
        first["image_sha256"] = "0" * 64
    else:
        planned["manifest"]["frames"][1] = first
    update_input(planned)
    engine, instances = factory()
    with pytest.raises(ValueError):
        run(planned, engine)
    assert not instances and not planned["output"].exists()


def test_load_failure_retains_all_six_not_run(planned):
    def fail(_):
        raise RuntimeError("synthetic load failure")

    engine, instances = factory(load_hook=fail)
    report = run(planned, engine)
    assert report["status"] == "incomplete"
    assert report["counts"] == {"completed": 0, "error": 0, "not_run": 6}
    assert report["first_error"] == {"stage": "load", "type": "RuntimeError"}
    assert not instances[0].calls
    assert len(list((planned["output"] / "attempts").glob("*.json"))) == 6


def test_actual_runtime_mismatch_does_not_predict(planned):
    engine, instances = factory(
        load_hook=lambda instance: setattr(instance, "runtime_versions", {})
    )
    report = run(planned, engine)
    assert report["counts"]["not_run"] == 6 and not instances[0].calls


def test_prediction_failure_not_retried_or_replaced(planned):
    def predict(instance):
        if len(instance.calls) == 2:
            raise RuntimeError("synthetic failure")

    engine, instances = factory(predict_hook=predict)
    report = run(planned, engine)
    assert len(instances[0].calls) == 6
    assert report["counts"] == {"completed": 5, "error": 1, "not_run": 0}
    assert report["frames"][1]["error"] == "RuntimeError"
    assert report["frames"][1]["engine_response"] is None


def test_keyboard_interrupt_preserves_first_attempt_and_remaining_not_run(planned):
    def interrupt(_):
        raise KeyboardInterrupt

    engine, instances = factory(predict_hook=interrupt)
    report = run(planned, engine)
    assert len(instances[0].calls) == 1
    assert report["counts"] == {"completed": 0, "error": 1, "not_run": 5}


@pytest.mark.parametrize("target", ["plan_path", "input_path", "weights", "image"])
def test_changed_source_invalidates_report(planned, target):
    path = planned["input_path"].parent / "p1.png" if target == "image" else planned[target]

    def mutate(instance):
        if len(instance.calls) == 6:
            path.write_bytes(path.read_bytes() + b"changed")

    engine, _ = factory(predict_hook=mutate)
    report = run(planned, engine)
    assert report["status"] == "invalidated"
    assert not report["frozen_inputs_unchanged"]
    assert report["counts"]["completed"] == 6


def test_nonfinite_prediction_is_recorded_error(planned):
    engine, _ = factory(
        predict_hook=lambda _: {
            "schema": "local_glove_detection_v1",
            "selection_status": "no_candidate",
            "score": float("nan"),
        }
    )
    report = run(planned, engine)
    assert report["counts"]["error"] == 6


@pytest.mark.parametrize("response", [[], {}, {"schema": "wrong"}])
def test_malformed_response_is_not_completed(planned, response):
    engine, _ = factory(predict_hook=lambda _: response)
    report = run(planned, engine)
    assert report["counts"]["error"] == 6


def test_existing_output_refused(planned):
    planned["output"].mkdir()
    engine, instances = factory()
    with pytest.raises(FileExistsError):
        run(planned, engine)
    assert not instances


def test_duplicate_json_rejected(planned):
    planned["plan_path"].write_text('{"schema": "a", "schema": "b"}', encoding="utf-8")
    engine, instances = factory()
    with pytest.raises(ValueError, match="duplicate"):
        run(planned, engine)
    assert not instances

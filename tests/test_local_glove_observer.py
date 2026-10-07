"""Synthetic adapter checks; no torch model is imported or invoked."""

import hashlib
import json
from dataclasses import replace
from types import SimpleNamespace

import pytest
from PIL import Image

from intent import local_glove_observer as observer
from intent.local_glove_detector import select_glove_detections


def digest(data):
    return hashlib.sha256(data).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


class Clock:
    def __init__(self):
        self.now = 1_000_000_000

    def perf_counter_ns(self):
        self.now += 1_000_000
        return self.now

    def get_clock_info(self, name):
        assert name == "perf_counter"
        return SimpleNamespace(
            implementation="synthetic counter", monotonic=True, adjustable=False, resolution=1e-9
        )


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    image = tmp_path / "image.jpg"
    Image.new("RGB", (16, 12), "blue").save(image)
    weights = tmp_path / "weights.pth"
    weights.write_bytes(b"synthetic checkpoint; never deserialized")
    model = "ssdlite320_mobilenet_v3_large"
    sha = digest(weights.read_bytes())
    spec = replace(observer.SPECS[model], sha256_prefix=sha[:8])
    monkeypatch.setattr(observer, "SPECS", {model: spec})
    config = {
        "schema": observer.CONFIG_SCHEMA,
        "model_id": model,
        "weights": str(weights),
        "weights_sha256": sha,
        "device": "cpu",
        "threads": 2,
        "threshold": 0.5,
        "input_view": "full_frame",
        "crop_xyxy": None,
    }
    request = {
        "schema": observer.session.MAPPED_REQUEST_SCHEMA,
        "observation_id": "1" * 32,
        "image_sha256": digest(image.read_bytes()),
        "width": 16,
        "height": 12,
        "source_time_seconds": 1.5,
        "source_time_basis": "decoded_pts",
        "source_time_seconds_exact": "3/2",
        "requested_cutoff_seconds_exact": "2",
        "prompt": observer.session.PROMPT,
        "response_schema": observer.session.RESPONSE_FIELDS,
    }
    config_path, request_path = tmp_path / "config.json", tmp_path / "request.json"
    write(config_path, config)
    write(request_path, request)
    return request_path, image, config_path, tmp_path / "response.json"


def factory(fixture, count=1, *, mutate=None, fail=None, seen=None):
    config = read(fixture[2])
    spec = observer.SPECS[config["model_id"]]

    class Engine:
        def __init__(self, model_name, weights_path, expected_sha256, *, device, threads):
            if seen is not None:
                seen.append("init")
            assert model_name == config["model_id"]
            assert str(weights_path) == config["weights"]
            assert expected_sha256 == config["weights_sha256"]
            assert (device, threads) == ("cpu", 2)

        def load(self):
            if fail == "load":
                raise RuntimeError("synthetic load failure")
            if fail == "interrupt":
                raise KeyboardInterrupt("synthetic interrupted initialization")
            return self

        def predict(self, data, *, image_sha256, crop, threshold):
            if fail == "predict":
                raise RuntimeError("synthetic inference failure")
            assert data == fixture[1].read_bytes() and image_sha256 == digest(data)
            assert crop is None and threshold == 0.5
            result = select_glove_detections(
                [[2, 2, 10, 10]] * count,
                [0.9] * count,
                [40] * count,
                image_size=[16, 12],
                threshold=threshold,
            )
            result.update(
                model_name=config["model_id"],
                weights_name=f"{spec.weights_enum}.COCO_V1",
                weights_url=spec.weights_url,
                weights_sha256=config["weights_sha256"],
                device="cpu",
                threads=2,
                batch_size=1,
                runtime_versions={"torch": "2.6.0", "torchvision": "0.21.0"},
                decode_seconds=0.001,
                preprocess_seconds=0.001,
                model_seconds=0.001,
                postprocess_seconds=0.001,
            )
            if mutate:
                mutate(result)
            return result

    return Engine


@pytest.mark.parametrize(
    "count,selection,status",
    [(0, "no_candidate", "unavailable"), (1, "candidate", "unknown"), (2, "ambiguous", "unknown")],
)
def test_candidates_never_become_marked(fixture, count, selection, status):
    sidecar = observer.observe(*fixture, engine_factory=factory(fixture, count), clock=Clock())
    response = read(fixture[3])
    assert (
        fixture[3].with_name(observer.CONFIG_SNAPSHOT_NAME).read_bytes() == fixture[2].read_bytes()
    )
    assert response["status"] == status and response["mitt"] is None
    assert response["visibility"] == response["pose"] == "unknown"
    assert response["reason"] and sidecar["selection_status"] == selection
    assert (sidecar["candidate"] is not None) == (count == 1)
    for key, path in zip(("request", "image", "config", "response"), fixture, strict=True):
        assert sidecar[f"{key}_sha256"] == digest(path.read_bytes())
    for field in (
        "catcher_association_verified",
        "human_label",
        "independent_validation",
        "full_pa_verified",
        "live_availability_verified",
    ):
        assert sidecar[field] is False
    stages = list(sidecar["timing"]["stages"].values())
    assert sidecar["timing"]["clock"] == "perf_counter_ns"
    assert sidecar["timing"]["clock_info"]["implementation"] == "synthetic counter"
    assert all(s["status"] == "completed" for s in stages)
    assert all(
        a["finished_perf_counter_ns"] == b["started_perf_counter_ns"]
        for a, b in zip(stages, stages[1:], strict=False)
    )
    assert sidecar["timing"]["elapsed_seconds"] == pytest.approx(
        sum(s["elapsed_seconds"] for s in stages)
    )


@pytest.mark.parametrize("change", ["image", "dimensions", "identity", "future", "roi", "weights"])
def test_input_failures_do_not_load_model(fixture, change):
    request, config = read(fixture[0]), read(fixture[2])
    if change == "image":
        fixture[1].write_bytes(fixture[1].read_bytes() + b"changed")
    elif change == "dimensions":
        request["width"] += 1
    elif change == "identity":
        request["observation_id"] = "invalid"
    elif change == "future":
        request["requested_cutoff_seconds_exact"] = "1"
    elif change == "roi":
        config["crop_xyxy"] = [0, 0, 16, 12]
    else:
        config["weights_sha256"] = config["weights_sha256"][:8] + "0" * 56
    write(fixture[0], request)
    write(fixture[2], config)
    seen = []
    with pytest.raises(ValueError):
        observer.observe(*fixture, engine_factory=factory(fixture, seen=seen), clock=Clock())
    assert not seen and not fixture[3].exists()
    assert (
        fixture[3].with_name(observer.CONFIG_SNAPSHOT_NAME).read_bytes() == fixture[2].read_bytes()
    )
    assert read(fixture[3].with_name("local_detector_result.json"))["status"] == "failed"


@pytest.mark.parametrize("stage", ["load", "predict"])
def test_engine_errors_are_failures_not_abstentions(fixture, stage):
    with pytest.raises(RuntimeError, match="synthetic"):
        observer.observe(*fixture, engine_factory=factory(fixture, fail=stage), clock=Clock())
    assert not fixture[3].exists()
    sidecar = read(fixture[3].with_name("local_detector_result.json"))
    assert sidecar["status"] == "failed" and sidecar["response_sha256"] is None
    assert sidecar["errors"][0]["type"] == "RuntimeError"


def test_interrupt_preserves_failure_sidecar_without_response(fixture):
    with pytest.raises(KeyboardInterrupt):
        observer.observe(*fixture, engine_factory=factory(fixture, fail="interrupt"), clock=Clock())
    assert not fixture[3].exists()
    assert (
        read(fixture[3].with_name("local_detector_result.json"))["errors"][0]["type"]
        == "KeyboardInterrupt"
    )


@pytest.mark.parametrize("change", ["point", "selection", "provenance", "scope"])
def test_invalid_engine_evidence_fails(fixture, change):
    def mutate(result):
        if change == "point":
            result["candidate"]["center_xy"] = [99, 99]
        elif change == "selection":
            result["selection_status"] = "no_candidate"
        elif change == "provenance":
            result["weights_sha256"] = "0" * 64
        else:
            result["catcher_association_verified"] = True

    with pytest.raises(ValueError):
        observer.observe(*fixture, engine_factory=factory(fixture, mutate=mutate), clock=Clock())
    assert not fixture[3].exists()


def test_changed_input_during_inference_fails(fixture):
    def mutate(_):
        fixture[2].write_bytes(fixture[2].read_bytes() + b" ")

    with pytest.raises(ValueError, match="input changed"):
        observer.observe(*fixture, engine_factory=factory(fixture, mutate=mutate), clock=Clock())
    assert not fixture[3].exists()


def test_existing_response_is_preserved(fixture):
    fixture[3].write_bytes(b"previous")
    with pytest.raises(ValueError, match="fresh"):
        observer.observe(*fixture, engine_factory=factory(fixture), clock=Clock())
    assert fixture[3].read_bytes() == b"previous"


def test_config_snapshot_is_not_overwritten(fixture):
    snapshot = fixture[3].with_name(observer.CONFIG_SNAPSHOT_NAME)
    snapshot.write_bytes(b"previous config")
    with pytest.raises(ValueError, match="fresh"):
        observer.observe(*fixture, engine_factory=factory(fixture), clock=Clock())
    assert snapshot.read_bytes() == b"previous config"


def test_cli_passes_explicit_paths(fixture, monkeypatch):
    calls = []
    monkeypatch.setattr(observer, "observe", lambda *args, **kwargs: calls.append((args, kwargs)))
    assert (
        observer.main(
            [
                "--request",
                str(fixture[0]),
                "--image",
                str(fixture[1]),
                "--config",
                str(fixture[2]),
                "--response",
                str(fixture[3]),
            ]
        )
        == 0
    )
    assert calls[0][0] == fixture

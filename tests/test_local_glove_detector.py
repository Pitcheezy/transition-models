"""Test offline provenance, abstention, and coordinates without real model calls."""

import hashlib
import json
from contextlib import contextmanager
from dataclasses import replace
from io import BytesIO
from types import SimpleNamespace

import pytest
from PIL import Image

from intent import local_glove_detector as detector

MODEL = "ssdlite320_mobilenet_v3_large"


def test_crop_projection_clips_before_adding_original_offsets():
    assert detector.project_box(
        [-5, -2, 40, 60], image_size=(640, 480), crop=(100, 200, 300, 400)
    ) == (100, 200, 140, 260)
    result = detector.select_glove_detections(
        [[-5, -2, 40, 60]],
        [0.8],
        [40],
        image_size=(640, 480),
        crop=(100, 200, 300, 400),
    )
    assert result["candidate"]["center_xy"] == [120, 230]
    assert result["candidate"]["box_was_clipped"] is True
    assert result["catcher_association_verified"] is False
    assert result["center_is_box_centroid_proxy"] is True


@pytest.mark.parametrize(
    "box",
    [
        [1, 2, 1, 5],
        [4, 2, 1, 5],
        [1, 5, 4, 5],
        [0, 0, float("nan"), 5],
        [0, 0, float("inf"), 5],
        [0, False, 5, 5],
        [0, "0", 5, 5],
        [0, 0, 5],
        [0, 0, 5, 5, 6],
        [101, 0, 102, 5],
        [-2, 0, -1, 5],
        [0, 100, 5, 101],
        [0, 0, 10**400, 5],
        "1234",
    ],
)
def test_invalid_or_nonintersecting_boxes_are_rejected(box):
    with pytest.raises(detector.DetectorError):
        detector.project_box(box, image_size=(100, 100))


@pytest.mark.parametrize(
    ("image_size", "crop"),
    [
        ((0, 100), None),
        ((100, -1), None),
        ((True, 100), None),
        ((100.0, 100), None),
        ((100, 100, 3), None),
        ((100, 100), (0, 0, 101, 20)),
        ((100, 100), (-1, 0, 20, 20)),
        ((100, 100), (20, 0, 20, 20)),
        ((100, 100), (0, 0, 20.0, 20)),
        ((100, 100), (0, 0, True, 20)),
    ],
)
def test_invalid_image_or_crop_boundaries_are_rejected(image_size, crop):
    with pytest.raises(detector.DetectorError):
        detector.project_box([1, 1, 3, 3], image_size=image_size, crop=crop)


def test_retains_low_score_gloves_but_excludes_other_classes_and_uses_inclusive_threshold():
    result = detector.select_glove_detections(
        [[1, 1, 3, 3], [4, 4, 6, 6], [7, 7, 9, 9]],
        [0.99, 0.49, 0.5],
        [1, 40, 40],
        image_size=(10, 10),
    )
    assert result["selection_status"] == "candidate"
    assert [item["detection_index"] for item in result["detections"]] == [1, 2]
    assert result["candidate"] == result["detections"][1]
    assert result["candidate"]["center_xy"] == [8, 8]
    assert result["detections"][0]["above_threshold"] is False
    assert json.loads(json.dumps(result)) == result


def test_multiple_gloves_abstain_even_with_a_clear_highest_score():
    result = detector.select_glove_detections(
        [[1, 1, 3, 3], [4, 4, 6, 6]], [0.99, 0.5], [40, 40], image_size=(10, 10)
    )
    assert result["selection_status"] == "ambiguous"
    assert result["candidate"] is None
    assert len(result["detections"]) == 2


@pytest.mark.parametrize("scores", [[], [0.49]])
def test_no_candidate_preserves_empty_or_subthreshold_results(scores):
    result = detector.select_glove_detections(
        [[1, 1, 3, 3]] if scores else [], scores, [40] if scores else [], image_size=(10, 10)
    )
    assert result["selection_status"] == "no_candidate"
    assert result["candidate"] is None


@pytest.mark.parametrize("score", [float("nan"), float("inf"), -0.1, 1.1, True, "0.9", None])
def test_bad_scores_rejected_even_for_non_glove_class(score):
    with pytest.raises(detector.DetectorError):
        detector.select_glove_detections([[1, 1, 3, 3]], [score], [1], image_size=(10, 10))


@pytest.mark.parametrize("label", [True, 40.0, "40", -1, 91, None])
def test_non_integer_or_out_of_range_labels_rejected(label):
    with pytest.raises(detector.DetectorError):
        detector.select_glove_detections([[1, 1, 3, 3]], [0.9], [label], image_size=(10, 10))


@pytest.mark.parametrize("threshold", [True, "0.5", float("nan"), -0.1, 1.1])
def test_invalid_threshold_rejected(threshold):
    with pytest.raises(detector.DetectorError):
        detector.select_glove_detections([], [], [], image_size=(10, 10), threshold=threshold)


def test_parallel_output_length_mismatch_rejected():
    with pytest.raises(detector.DetectorError, match="equal lengths"):
        detector.select_glove_detections([[1, 1, 3, 3]], [], [40], image_size=(10, 10))


def test_constructor_does_not_import_runtime(monkeypatch):
    monkeypatch.setattr(
        detector.importlib, "import_module", lambda name: pytest.fail(f"unexpected import: {name}")
    )
    engine = detector.LocalGloveDetector(MODEL, "not-read.pth", "a79551df" + "0" * 56)
    assert engine.startup_seconds is None
    assert engine.runtime_versions == {}


@pytest.mark.parametrize("digest", ["a79551df", "0" * 64, "A79551DF" + "0" * 56, None])
def test_checkpoint_requires_full_digest_and_official_prefix(digest):
    with pytest.raises(detector.DetectorError):
        detector.LocalGloveDetector(MODEL, "not-read.pth", digest)


class FakeTensor:
    def __init__(self, data, shape=None, events=None):
        self.data = data
        self.shape = (
            shape
            if shape is not None
            else ((len(data), len(data[0])) if data and isinstance(data[0], list) else (len(data),))
        )
        self.ndim = len(self.shape)
        self.events = events

    def to(self, device):
        if self.events is not None:
            self.events.append(("tensor_to", device))
        return self

    def detach(self):
        return self

    def cpu(self):
        return self

    def tolist(self):
        return self.data


@pytest.fixture
def fake_runtime(tmp_path, monkeypatch):
    checkpoint = b"synthetic checkpoint for mocked tests only"
    digest = hashlib.sha256(checkpoint).hexdigest()
    spec = replace(detector.SPECS[MODEL], sha256_prefix=digest[:8])
    monkeypatch.setattr(detector, "SPECS", {MODEL: spec})
    path = tmp_path / "weights.pth"
    path.write_bytes(checkpoint)
    events = []
    output = [
        {
            "boxes": FakeTensor([[1, 2, 5, 6]]),
            "scores": FakeTensor([0.8]),
            "labels": FakeTensor([40]),
        }
    ]

    class Model:
        def load_state_dict(self, state, *, strict):
            assert state == {"synthetic": "state"}
            assert strict is True
            events.append("load_state")

        def eval(self):
            events.append("eval")
            return self

        def to(self, device):
            events.append(("model_to", device))
            return self

        def __call__(self, batch):
            assert len(batch) == 1
            events.append("model")
            return output

    def builder(**kwargs):
        assert kwargs == {"weights": None, "weights_backbone": None, "num_classes": 91}
        events.append("builder")
        return Model()

    def load(stream, *, weights_only, map_location):
        assert stream.read() == checkpoint
        assert weights_only is True
        assert map_location == "cpu"
        events.append("load_bytes")
        return {"synthetic": "state"}

    @contextmanager
    def inference_mode():
        events.append("inference_enter")
        yield
        events.append("inference_exit")

    def transform(image):
        assert image.mode == "RGB"
        events.append(("transform", image.size))
        return FakeTensor([], events=events)

    categories = ["unused"] * 91
    categories[0] = "__background__"
    categories[40] = "baseball glove"
    weights = SimpleNamespace(
        url=spec.weights_url, meta={"categories": categories}, transforms=lambda: transform
    )
    torch = SimpleNamespace(
        __version__="2.6.0+cu124",
        set_num_threads=lambda number: events.append(("threads", number)),
        load=load,
        inference_mode=inference_mode,
        is_tensor=lambda value: isinstance(value, FakeTensor),
        cuda=SimpleNamespace(
            is_available=lambda: True,
            synchronize=lambda: events.append("synchronize"),
        ),
    )
    torchvision = SimpleNamespace(__version__="0.21.0+cu124")
    detection_module = SimpleNamespace(
        **{spec.weights_enum: SimpleNamespace(COCO_V1=weights), MODEL: builder}
    )
    modules = {
        "torch": torch,
        "torchvision": torchvision,
        "torchvision.models.detection": detection_module,
    }
    monkeypatch.setattr(detector.importlib, "import_module", lambda name: modules[name])
    return SimpleNamespace(
        engine=detector.LocalGloveDetector(MODEL, path, digest),
        events=events,
        weights=weights,
        torch=torch,
        torchvision=torchvision,
        output=output,
        path=path,
    )


def test_lazy_engine_local_load_once_and_original_pixel_predictions(fake_runtime):
    engine = fake_runtime.engine
    image = Image.new("RGB", (100, 80))
    first = engine.predict(image, crop=(20, 30, 40, 50))
    second = engine.predict(image)
    assert first["candidate"]["center_xy"] == [23, 34]
    assert first["candidate"]["box_xyxy"] == [21, 32, 25, 36]
    assert second["candidate"]["center_xy"] == [3, 4]
    assert first["image_size"] == [100, 80]
    assert first["decode_seconds"] is None
    assert engine.startup_seconds >= 0
    assert fake_runtime.events.count("builder") == 1
    assert fake_runtime.events.count("model") == 2
    assert fake_runtime.events.count(("threads", 4)) == 1
    assert fake_runtime.events.index("eval") < fake_runtime.events.index("model")
    assert "synchronize" not in fake_runtime.events
    for key in ("preprocess_seconds", "model_seconds", "postprocess_seconds"):
        assert first[key] >= 0
    assert json.loads(json.dumps(first)) == first


def test_verified_checkpoint_bytes_are_the_bytes_deserialized(fake_runtime, monkeypatch):
    original_import = detector.importlib.import_module

    def mutate_after_verification(name):
        fake_runtime.path.write_bytes(b"changed after verification")
        return original_import(name)

    monkeypatch.setattr(detector.importlib, "import_module", mutate_after_verification)
    fake_runtime.engine.load()
    assert "load_bytes" in fake_runtime.events


def test_checkpoint_mismatch_refuses_before_import(fake_runtime, monkeypatch):
    fake_runtime.path.write_bytes(b"tampered")
    monkeypatch.setattr(
        detector.importlib, "import_module", lambda name: pytest.fail("must not import")
    )
    with pytest.raises(detector.DetectorError, match="SHA-256 mismatch"):
        fake_runtime.engine.load()


@pytest.mark.parametrize("change", ["category", "category_count", "url"])
def test_metadata_mismatch_refuses_before_building(fake_runtime, change):
    if change == "category":
        fake_runtime.weights.meta["categories"][40] = "baseball bat"
    elif change == "category_count":
        fake_runtime.weights.meta["categories"].pop()
    else:
        fake_runtime.weights.url = "https://example.invalid/weights.pth"
    with pytest.raises(detector.DetectorError, match="metadata"):
        fake_runtime.engine.load()
    assert "builder" not in fake_runtime.events


def test_wrong_runtime_versions_are_rejected(fake_runtime):
    fake_runtime.torchvision.__version__ = "0.22.0"
    with pytest.raises(detector.DetectorError, match="runtime versions"):
        fake_runtime.engine.load()


def test_supported_mac_runtime_pair(fake_runtime):
    fake_runtime.torch.__version__ = "2.8.0"
    fake_runtime.torchvision.__version__ = "0.23.0"
    fake_runtime.engine.load()
    assert fake_runtime.engine.runtime_versions == {"torch": "2.8.0", "torchvision": "0.23.0"}


def test_cuda_does_not_fall_back_when_unavailable(fake_runtime):
    fake_runtime.engine.device = "cuda"
    fake_runtime.torch.cuda.is_available = lambda: False
    with pytest.raises(detector.DetectorError, match="CUDA"):
        fake_runtime.engine.load()
    assert "builder" not in fake_runtime.events


def test_cuda_synchronization_surrounds_model_timer(fake_runtime):
    fake_runtime.engine.device = "cuda"
    fake_runtime.engine.predict(Image.new("RGB", (20, 20)))
    events = fake_runtime.events
    index = events.index("model")
    assert events[index - 2 : index + 3] == [
        "synchronize",
        "inference_enter",
        "model",
        "synchronize",
        "inference_exit",
    ]


def test_encoded_images_require_matching_sha_and_return_decode_time(fake_runtime):
    buffer = BytesIO()
    Image.new("RGB", (20, 20)).save(buffer, format="PNG")
    raw = buffer.getvalue()
    result = fake_runtime.engine.predict(raw, image_sha256=hashlib.sha256(raw).hexdigest())
    assert result["decode_seconds"] >= 0
    with pytest.raises(detector.DetectorError, match="SHA-256"):
        fake_runtime.engine.predict(raw, image_sha256="0" * 64)
    with pytest.raises(detector.DetectorError, match="SHA-256"):
        fake_runtime.engine.predict(raw)


@pytest.mark.parametrize("kind", ["crop", "threshold", "input", "pil_sha"])
def test_invalid_input_refuses_before_any_model_load(fake_runtime, kind):
    image = Image.new("RGB", (20, 20))
    kwargs = {}
    if kind == "crop":
        kwargs["crop"] = (0, 0, 21, 21)
    elif kind == "threshold":
        kwargs["threshold"] = float("nan")
    elif kind == "input":
        image = [[1, 2]]
    else:
        kwargs["image_sha256"] = "0" * 64
    with pytest.raises(detector.DetectorError):
        fake_runtime.engine.predict(image, **kwargs)
    assert "builder" not in fake_runtime.events


@pytest.mark.parametrize("field", ["boxes", "scores", "labels"])
def test_model_tensor_shapes_are_strict(fake_runtime, field):
    fake_runtime.output[0][field] = FakeTensor([[1, 2, 3]])
    with pytest.raises(detector.DetectorError, match="shape"):
        fake_runtime.engine.predict(Image.new("RGB", (20, 20)))


def test_nan_model_score_and_float_model_label_are_rejected(fake_runtime):
    fake_runtime.output[0]["scores"] = FakeTensor([float("nan")])
    with pytest.raises(detector.DetectorError, match="score"):
        fake_runtime.engine.predict(Image.new("RGB", (20, 20)))
    fake_runtime.output[0]["scores"] = FakeTensor([0.8])
    fake_runtime.output[0]["labels"] = FakeTensor([40.0])
    with pytest.raises(detector.DetectorError, match="label"):
        fake_runtime.engine.predict(Image.new("RGB", (20, 20)))


def test_empty_output_is_a_valid_abstention(fake_runtime):
    fake_runtime.output[0] = {
        "boxes": FakeTensor([], shape=(0, 4)),
        "scores": FakeTensor([]),
        "labels": FakeTensor([]),
    }
    result = fake_runtime.engine.predict(Image.new("RGB", (20, 20)))
    assert result["selection_status"] == "no_candidate"
    assert result["candidate"] is None

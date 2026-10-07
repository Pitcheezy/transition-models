"""Offline COCO glove candidates for development; no catcher or intent verification.

Importing this module does not import torch, torchvision, or Pillow. The engine uses
only a caller-supplied, fully SHA-256-verified checkpoint and never downloads weights.
Box centroids are a glove-location proxy, not a verified catcher-mitt center.
"""

from __future__ import annotations

import hashlib
import importlib
import math
import re
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from io import BytesIO
from numbers import Integral, Real
from pathlib import Path
from types import MappingProxyType
from typing import Any

GLOVE_LABEL = 40
GLOVE_CATEGORY = "baseball glove"
DEFAULT_THRESHOLD = 0.5
SCHEMA = "local_glove_detection_v1"
SUPPORTED_RUNTIME_PAIRS = frozenset({("2.6.0", "0.21.0"), ("2.8.0", "0.23.0")})


class DetectorError(ValueError):
    """Reject invalid input, unsupported runtime, or unverified model provenance."""


@dataclass(frozen=True)
class DetectorSpec:
    """Bind a constructor and explicit weights version to official provenance."""

    name: str
    weights_enum: str
    weights_url: str
    sha256_prefix: str
    torchvision_version: str = "0.21.0"
    torch_version: str = "2.6.0"
    label: int = GLOVE_LABEL
    category: str = GLOVE_CATEGORY


SPECS = MappingProxyType(
    {
        "ssdlite320_mobilenet_v3_large": DetectorSpec(
            "ssdlite320_mobilenet_v3_large",
            "SSDLite320_MobileNet_V3_Large_Weights",
            "https://download.pytorch.org/models/ssdlite320_mobilenet_v3_large_coco-a79551df.pth",
            "a79551df",
        ),
        "fasterrcnn_mobilenet_v3_large_fpn": DetectorSpec(
            "fasterrcnn_mobilenet_v3_large_fpn",
            "FasterRCNN_MobileNet_V3_Large_FPN_Weights",
            "https://download.pytorch.org/models/fasterrcnn_mobilenet_v3_large_fpn-fb6a3cc7.pth",
            "fb6a3cc7",
        ),
    }
)


def _sequence(value: Any, name: str, length: int | None = None) -> Sequence:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes, bytearray)):
        raise DetectorError(f"{name} must be a sequence")
    if length is not None and len(value) != length:
        raise DetectorError(f"{name} must have length {length}")
    return value


def _number(value: Any, name: str) -> float:
    if isinstance(value, bool) or not isinstance(value, Real):
        raise DetectorError(f"{name} must be a finite number")
    try:
        result = float(value)
    except (OverflowError, ValueError) as exc:
        raise DetectorError(f"{name} must be a finite number") from exc
    if not math.isfinite(result):
        raise DetectorError(f"{name} must be a finite number")
    return result


def _integer(value: Any, name: str) -> int:
    if isinstance(value, bool) or not isinstance(value, Integral):
        raise DetectorError(f"{name} must be an integer")
    return int(value)


def _sha(value: Any, name: str) -> str:
    if not isinstance(value, str) or re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise DetectorError(f"{name} must be a full lowercase SHA-256")
    return value


def _region(image_size: Sequence, crop: Sequence | None) -> tuple[int, int, int, int]:
    width, height = (
        _integer(value, "image dimension") for value in _sequence(image_size, "image_size", 2)
    )
    if width <= 0 or height <= 0:
        raise DetectorError("image dimensions must be positive")
    if crop is None:
        return 0, 0, width, height
    left, top, right, bottom = (
        _integer(value, "crop coordinate") for value in _sequence(crop, "crop", 4)
    )
    if not 0 <= left < right <= width or not 0 <= top < bottom <= height:
        raise DetectorError("crop must have positive area inside the original image")
    return left, top, right, bottom


def project_box(
    box: Sequence, *, image_size: Sequence, crop: Sequence | None = None
) -> tuple[float, float, float, float]:
    """Clip a crop-local box to its image and offset into original-image pixels.

    Coordinates are continuous XYXY edges. Crop coordinates are integer Pillow
    boundaries. Non-finite, reversed, or non-intersecting boxes are rejected.
    """
    left, top, right, bottom = _region(image_size, crop)
    x1, y1, x2, y2 = (_number(value, "box coordinate") for value in _sequence(box, "box", 4))
    if x1 >= x2 or y1 >= y2:
        raise DetectorError("box must have positive area")
    width, height = right - left, bottom - top
    x1, x2 = max(0.0, x1), min(float(width), x2)
    y1, y2 = max(0.0, y1), min(float(height), y2)
    if x1 >= x2 or y1 >= y2:
        raise DetectorError("box must intersect the detector input image")
    return x1 + left, y1 + top, x2 + left, y2 + top


def select_glove_detections(
    boxes: Sequence,
    scores: Sequence,
    labels: Sequence,
    *,
    image_size: Sequence,
    crop: Sequence | None = None,
    threshold: float = DEFAULT_THRESHOLD,
) -> dict:
    """Retain all glove boxes and accept only one candidate at or above threshold.

    A unique glove may belong to another player. This selector performs no catcher
    association, reference-label lookup, score calibration, or nearest-label matching.
    """
    left, top, right, bottom = _region(image_size, crop)
    threshold = _number(threshold, "threshold")
    if not 0 <= threshold <= 1:
        raise DetectorError("threshold must be in [0, 1]")
    boxes = _sequence(boxes, "boxes")
    scores = _sequence(scores, "scores")
    labels = _sequence(labels, "labels")
    if len(boxes) != len(scores) or len(boxes) != len(labels):
        raise DetectorError("boxes, scores, and labels must have equal lengths")
    detections = []
    for index, (box, score, label) in enumerate(zip(boxes, scores, labels, strict=True)):
        score = _number(score, "score")
        if not 0 <= score <= 1:
            raise DetectorError("score must be in [0, 1]")
        label = _integer(label, "label")
        if not 0 <= label < 91:
            raise DetectorError("label must be in [0, 90]")
        projected = project_box(box, image_size=image_size, crop=crop)
        if label != GLOVE_LABEL:
            continue
        original = tuple(_number(value, "box coordinate") for value in box)
        unbounded = (original[0] + left, original[1] + top, original[2] + left, original[3] + top)
        detections.append(
            {
                "detection_index": index,
                "label": GLOVE_LABEL,
                "category": GLOVE_CATEGORY,
                "box_xyxy": list(projected),
                "center_xy": [(projected[0] + projected[2]) / 2, (projected[1] + projected[3]) / 2],
                "score": score,
                "above_threshold": score >= threshold,
                "box_was_clipped": projected != unbounded,
            }
        )
    candidates = [item for item in detections if item["above_threshold"]]
    status = (
        "no_candidate" if not candidates else "candidate" if len(candidates) == 1 else "ambiguous"
    )
    return {
        "schema": SCHEMA,
        "coordinate_system": "original_image_pixels",
        "image_size": [int(value) for value in image_size],
        "crop_xyxy": None if crop is None else [left, top, right, bottom],
        "threshold": threshold,
        "selection_status": status,
        "detections": detections,
        "candidate": candidates[0] if len(candidates) == 1 else None,
        "catcher_association_verified": False,
        "center_is_box_centroid_proxy": True,
    }


def _verified_checkpoint(path: Path, expected_sha256: str, spec: DetectorSpec) -> bytes:
    expected_sha256 = _sha(expected_sha256, "expected_sha256")
    if not expected_sha256.startswith(spec.sha256_prefix):
        raise DetectorError("expected_sha256 does not match the official checkpoint hash prefix")
    data = path.read_bytes()
    if hashlib.sha256(data).hexdigest() != expected_sha256:
        raise DetectorError("local checkpoint SHA-256 mismatch")
    return data


def _image_input(image: Any, image_sha256: str | None) -> tuple[Any, float | None]:
    from PIL import Image

    if isinstance(image, bytes):
        expected = _sha(image_sha256, "image_sha256 for image bytes")
        if hashlib.sha256(image).hexdigest() != expected:
            raise DetectorError("image SHA-256 mismatch")
        started = time.perf_counter()
        with Image.open(BytesIO(image)) as opened:
            if getattr(opened, "n_frames", 1) != 1:
                raise DetectorError("animated image inputs are unsupported")
            opened.load()
            image = opened.copy()
        decoded_seconds = time.perf_counter() - started
    elif isinstance(image, Image.Image):
        if image_sha256 is not None:
            raise DetectorError("image_sha256 verifies encoded bytes, not a PIL image")
        if getattr(image, "n_frames", 1) != 1:
            raise DetectorError("animated image inputs are unsupported")
        decoded_seconds = None
    else:
        raise DetectorError("image must be a PIL image or SHA-256-bound encoded bytes")
    _region(image.size, None)
    return image, decoded_seconds


class LocalGloveDetector:
    """Load an explicit local checkpoint lazily; run batch-one glove detection.

    CPU thread count is a process-wide torch setting. Use a separate worker when
    other models require different settings. CPU/CUDA selection never falls back.
    PIL callers should decode and verify source bytes before measuring prediction.
    """

    def __init__(
        self,
        model_name: str,
        weights_path: str | Path,
        expected_sha256: str,
        *,
        device: str = "cpu",
        threads: int = 4,
    ) -> None:
        if not isinstance(model_name, str) or model_name not in SPECS:
            raise DetectorError("unsupported model_name")
        if device not in ("cpu", "cuda"):
            raise DetectorError("device must be explicitly cpu or cuda")
        threads = _integer(threads, "threads")
        if threads <= 0:
            raise DetectorError("threads must be positive")
        self.spec = SPECS[model_name]
        self.weights_path = Path(weights_path)
        self.expected_sha256 = _sha(expected_sha256, "expected_sha256")
        if not self.expected_sha256.startswith(self.spec.sha256_prefix):
            raise DetectorError(
                "expected_sha256 does not match the official checkpoint hash prefix"
            )
        self.device = device
        self.threads = threads
        self.startup_seconds: float | None = None
        self.runtime_versions: dict[str, str] = {}
        self._model = None
        self._torch = None
        self._transform = None

    def load(self) -> LocalGloveDetector:
        """Verify bytes, then import the pinned runtime and load strictly once."""
        if self._model is not None:
            return self
        started = time.perf_counter()
        checkpoint = _verified_checkpoint(self.weights_path, self.expected_sha256, self.spec)
        torch = importlib.import_module("torch")
        torchvision = importlib.import_module("torchvision")
        detection = importlib.import_module("torchvision.models.detection")
        versions = {"torch": torch.__version__, "torchvision": torchvision.__version__}
        runtime_pair = tuple(versions[name].split("+")[0] for name in ("torch", "torchvision"))
        if runtime_pair not in SUPPORTED_RUNTIME_PAIRS:
            raise DetectorError("runtime versions do not match the pinned detector specification")
        weights = getattr(detection, self.spec.weights_enum).COCO_V1
        categories = weights.meta.get("categories")
        if (
            not isinstance(categories, (list, tuple))
            or len(categories) != 91
            or categories[0] != "__background__"
            or categories[GLOVE_LABEL] != GLOVE_CATEGORY
            or weights.url != self.spec.weights_url
        ):
            raise DetectorError("weights category metadata or official URL mismatch")
        if self.device == "cuda" and not torch.cuda.is_available():
            raise DetectorError("CUDA was requested but is unavailable")
        torch.set_num_threads(self.threads)
        model = getattr(detection, self.spec.name)(
            weights=None, weights_backbone=None, num_classes=91
        )
        state = torch.load(BytesIO(checkpoint), weights_only=True, map_location="cpu")
        model.load_state_dict(state, strict=True)
        model.eval()
        model.to(self.device)
        if self.device == "cuda":
            torch.cuda.synchronize()
        self._transform = weights.transforms()
        self._torch = torch
        self._model = model
        self.runtime_versions = versions
        self.startup_seconds = time.perf_counter() - started
        return self

    def predict(
        self,
        image: Any,
        *,
        crop: Sequence | None = None,
        threshold: float = DEFAULT_THRESHOLD,
        image_sha256: str | None = None,
    ) -> dict:
        """Return original-pixel glove candidates with separate processing timings."""
        image, decode_seconds = _image_input(image, image_sha256)
        region = _region(image.size, crop)
        # Validate selection configuration before loading weights or invoking a model.
        select_glove_detections([], [], [], image_size=image.size, crop=crop, threshold=threshold)
        self.load()
        torch = self._torch
        started = time.perf_counter()
        rgb = image.convert("RGB")
        if crop is not None:
            rgb = rgb.crop(region)
        tensor = self._transform(rgb).to(self.device)
        if torch is None:
            raise DetectorError("runtime was not loaded")
        if self.device == "cuda":
            torch.cuda.synchronize()
        preprocess_seconds = time.perf_counter() - started
        with torch.inference_mode():
            started = time.perf_counter()
            output = self._model([tensor])
            if self.device == "cuda":
                torch.cuda.synchronize()
            model_seconds = time.perf_counter() - started
        started = time.perf_counter()
        if (
            not isinstance(output, list)
            or len(output) != 1
            or not isinstance(output[0], Mapping)
            or not {"boxes", "scores", "labels"}.issubset(output[0])
        ):
            raise DetectorError("model must return one boxes/scores/labels mapping")
        prediction = output[0]
        values = {}
        for name, dimensions in (("boxes", 2), ("scores", 1), ("labels", 1)):
            tensor_output = prediction[name]
            if not torch.is_tensor(tensor_output) or tensor_output.ndim != dimensions:
                raise DetectorError(f"{name} has an invalid tensor shape")
            if name == "boxes" and tensor_output.shape[1] != 4:
                raise DetectorError("boxes must have shape [N, 4]")
            values[name] = tensor_output.detach().cpu().tolist()
        result = select_glove_detections(
            values["boxes"],
            values["scores"],
            values["labels"],
            image_size=image.size,
            crop=crop,
            threshold=threshold,
        )
        result.update(
            {
                "model_name": self.spec.name,
                "weights_name": f"{self.spec.weights_enum}.COCO_V1",
                "weights_url": self.spec.weights_url,
                "weights_sha256": self.expected_sha256,
                "runtime_versions": dict(self.runtime_versions),
                "device": self.device,
                "threads": self.threads,
                "batch_size": 1,
                "decode_seconds": decode_seconds,
                "preprocess_seconds": preprocess_seconds,
                "model_seconds": model_seconds,
                "postprocess_seconds": time.perf_counter() - started,
            }
        )
        return result

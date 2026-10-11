"""Observe one frame with a local glove detector without claiming catcher identity.

Generic glove boxes remain in a private sidecar. The existing observation response
never marks their centroids as verified catcher-mitt centers. No implicit downloads,
retries, ROI selection, tracking, or service calls are performed.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
import time
import uuid
from fractions import Fraction
from pathlib import Path

from PIL import Image

from intent import observation_session as session
from intent.local_glove_detector import (
    GLOVE_CATEGORY,
    GLOVE_LABEL,
    SCHEMA,
    SPECS,
    LocalGloveDetector,
)
from intent.replay import _no_links

CONFIG_SCHEMA = "local_glove_observer_config_v1"
SIDECAR_SCHEMA = "local_glove_observer_result_v1"
CONFIG_SNAPSHOT_NAME = "local_detector_config.json"
CONFIG_FIELDS = {
    "schema",
    "model_id",
    "weights",
    "weights_sha256",
    "device",
    "threads",
    "threshold",
    "input_view",
    "crop_xyxy",
}
REQUEST_FIELDS = {
    "schema",
    "observation_id",
    "image_sha256",
    "width",
    "height",
    "source_time_seconds",
    "prompt",
    "response_schema",
}


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _path(value, *, existing=True):
    path = Path(value).absolute()
    _no_links(path)
    if existing and not path.is_file():
        raise ValueError("Expected a regular input file")
    return path.resolve()


def _json(raw):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError("Duplicate JSON field")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("Nonfinite JSON value")

    value = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(value, dict):
        raise ValueError("Expected JSON object")
    return value


def _number(value, low=0, high=math.inf):
    if type(value) not in (int, float) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError("Invalid finite numeric value")
    return value


def _encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def _write(path, data):
    _no_links(path)
    with path.open("xb") as stream:
        stream.write(data)


def _request(request, data):
    mapped = request.get("schema") == session.MAPPED_REQUEST_SCHEMA
    fields = REQUEST_FIELDS | (set(session.MAPPED_TIME_FIELDS) if mapped else set())
    if (
        set(request) != fields
        or request.get("schema") not in (session.REQUEST_SCHEMA, session.MAPPED_REQUEST_SCHEMA)
        or request.get("prompt") != session.PROMPT
        or request.get("response_schema") != session.RESPONSE_FIELDS
    ):
        raise ValueError("Unexpected anonymous observation request")
    identity = request.get("observation_id")
    if not isinstance(identity, str) or uuid.UUID(identity).hex != identity:
        raise ValueError("Invalid observation identity")
    if request.get("image_sha256") != _sha(data):
        raise ValueError("Request image SHA256 mismatch")
    seconds = _number(request.get("source_time_seconds"))
    if mapped:
        if any(type(request.get(key)) not in (str, int) for key in session.MAPPED_TIME_FIELDS[1:]):
            raise ValueError("Exact source times must be strings or integers")
        actual = Fraction(request["source_time_seconds_exact"])
        cutoff = Fraction(request["requested_cutoff_seconds_exact"])
        if (
            request["source_time_basis"] != "decoded_pts"
            or not 0 <= actual <= cutoff
            or float(actual) != seconds
        ):
            raise ValueError("Invalid exact frame time/cutoff")
    with Image.open(io.BytesIO(data)) as image:
        if (
            image.format != "JPEG"
            or any(type(request[k]) is not int or request[k] <= 0 for k in ("width", "height"))
            or image.size != (request["width"], request["height"])
        ):
            raise ValueError("Original JPEG dimensions mismatch")
        image.verify()


def _config(config):
    if set(config) != CONFIG_FIELDS or config.get("schema") != CONFIG_SCHEMA:
        raise ValueError("Unexpected local observer configuration")
    if config["model_id"] not in SPECS or config["device"] not in ("cpu", "cuda"):
        raise ValueError("Unsupported explicit model/device")
    if config["input_view"] != "full_frame" or config["crop_xyxy"] is not None:
        raise ValueError("This adapter supports only explicit full-frame input without ROI")
    if type(config["threads"]) is not int or not 1 <= config["threads"] <= 32:
        raise ValueError("Invalid CPU thread count")
    _number(config["threshold"], 0, 1)
    digest = config["weights_sha256"]
    if (
        not isinstance(digest, str)
        or not re.fullmatch(r"[a-f0-9]{64}", digest)
        or not digest.startswith(SPECS[config["model_id"]].sha256_prefix)
    ):
        raise ValueError("Explicit official checkpoint SHA256 required")
    if not isinstance(config["weights"], str) or not Path(config["weights"]).is_absolute():
        raise ValueError("Checkpoint must use an explicit absolute local path")
    weights = _path(config["weights"])
    if _sha(weights.read_bytes()) != digest:
        raise ValueError("Checkpoint SHA256 mismatch")
    return weights


def _prediction(result, request, config):
    """Validate the engine's complete selection before preserving its proxy output."""
    if not isinstance(result, dict):
        raise ValueError("Detector response must be an object")
    result = _json(_encode(result))
    spec = SPECS[config["model_id"]]
    expected = {
        "schema": SCHEMA,
        "coordinate_system": "original_image_pixels",
        "image_size": [request["width"], request["height"]],
        "crop_xyxy": None,
        "threshold": config["threshold"],
        "model_name": config["model_id"],
        "weights_name": f"{spec.weights_enum}.COCO_V1",
        "weights_url": spec.weights_url,
        "weights_sha256": config["weights_sha256"],
        "device": config["device"],
        "threads": config["threads"],
        "batch_size": 1,
    }
    if any(result.get(key) != value for key, value in expected.items()):
        raise ValueError("Detector response provenance/configuration mismatch")
    if (
        result.get("catcher_association_verified") is not False
        or result.get("center_is_box_centroid_proxy") is not True
    ):
        raise ValueError("Detector must retain unverified glove-centroid scope")
    if not isinstance(result.get("runtime_versions"), dict) or not all(
        isinstance(result["runtime_versions"].get(key), str) and result["runtime_versions"][key]
        for key in ("torch", "torchvision")
    ):
        raise ValueError("Actual detector runtime versions required")
    for field in ("decode_seconds", "preprocess_seconds", "model_seconds", "postprocess_seconds"):
        _number(result.get(field))
    detections = result.get("detections")
    if not isinstance(detections, list):
        raise ValueError("Detector detections must be a list")
    seen, candidates = set(), []
    for detection in detections:
        if not isinstance(detection, dict):
            raise ValueError("Invalid detection")
        index = detection.get("detection_index")
        if type(index) is not int or index < 0 or index in seen:
            raise ValueError("Duplicate or invalid detection index")
        seen.add(index)
        if detection.get("label") != GLOVE_LABEL or detection.get("category") != GLOVE_CATEGORY:
            raise ValueError("Unexpected detector category")
        box = detection.get("box_xyxy")
        if not isinstance(box, list) or len(box) != 4:
            raise ValueError("Expected four original-image box coordinates")
        x1, y1, x2, y2 = (_number(v) for v in box)
        if not 0 <= x1 < x2 <= request["width"] or not 0 <= y1 < y2 <= request["height"]:
            raise ValueError("Detector box outside original image")
        center = detection.get("center_xy")
        if not isinstance(center, list) or len(center) != 2:
            raise ValueError("Expected box centroid")
        for value in center:
            _number(value)
        if center != [(x1 + x2) / 2, (y1 + y2) / 2]:
            raise ValueError("Detector centroid differs from box")
        score = _number(detection.get("score"), 0, 1)
        above = score >= config["threshold"]
        if (
            detection.get("above_threshold") is not above
            or type(detection.get("box_was_clipped")) is not bool
        ):
            raise ValueError("Detector threshold/clipping flag mismatch")
        if above:
            candidates.append(detection)
    selection = (
        "no_candidate" if not candidates else "candidate" if len(candidates) == 1 else "ambiguous"
    )
    if result.get("selection_status") != selection or result.get("candidate") != (
        candidates[0] if len(candidates) == 1 else None
    ):
        raise ValueError("Detector selection disagrees with its candidates")
    return result


def observe(
    request_path,
    image_path,
    config_path,
    response_path,
    *,
    sidecar_path=None,
    engine_factory=LocalGloveDetector,
    clock=time,
):
    """Write one conservative response plus source-bound private detector evidence."""
    inputs = [_path(path) for path in (request_path, image_path, config_path)]
    response_path = _path(response_path, existing=False)
    sidecar_path = _path(
        sidecar_path or response_path.with_name("local_detector_result.json"), existing=False
    )
    config_snapshot = _path(response_path.with_name(CONFIG_SNAPSHOT_NAME), existing=False)
    outputs = (response_path, sidecar_path, config_snapshot)
    if len(set(inputs)) != 3 or len(set(outputs)) != 3:
        raise ValueError("Input/output files must be distinct")
    for path in outputs:
        if path.exists() or path in inputs or path.parent != inputs[0].parent:
            raise ValueError("Outputs must be fresh files alongside the request")
    started = clock.perf_counter_ns()
    if type(started) is not int or started < 0:
        raise ValueError("Invalid adapter monotonic clock")
    clock_info = {"status": "unavailable_for_injected_clock"}
    if hasattr(clock, "get_clock_info"):
        info = clock.get_clock_info("perf_counter")
        clock_info = {
            "status": "measured_runtime",
            "implementation": info.implementation,
            "monotonic": info.monotonic,
            "adjustable": info.adjustable,
            "resolution_seconds": info.resolution,
        }
    current_start, current_stage = started, "input_validation"
    stages = {}
    sidecar = {
        "schema": SIDECAR_SCHEMA,
        "status": "failed",
        "request_sha256": None,
        "image_sha256": None,
        "config_sha256": None,
        "config_snapshot_file": CONFIG_SNAPSHOT_NAME,
        "response_sha256": None,
        "observation_id": None,
        "configuration": None,
        "engine_response": None,
        "selection_status": None,
        "candidate": None,
        "errors": [],
        "human_label": False,
        "independent_validation": False,
        "catcher_association_verified": False,
        "full_pa_verified": False,
        "live_availability_verified": False,
    }

    def finish_stage(status):
        finished = clock.perf_counter_ns()
        if type(finished) is not int or finished < current_start:
            raise ValueError("Adapter monotonic clock moved backwards")
        stages[current_stage] = {
            "status": status,
            "started_perf_counter_ns": current_start,
            "finished_perf_counter_ns": finished,
            "elapsed_seconds": (finished - current_start) / 1e9,
        }
        return finished

    try:
        raw_request, data, raw_config = (path.read_bytes() for path in inputs)
        sidecar.update(
            request_sha256=_sha(raw_request),
            image_sha256=_sha(data),
            config_sha256=_sha(raw_config),
        )
        # Preserve the exact bytes, including whitespace, before config interpretation.
        _write(config_snapshot, raw_config)
        request, config = _json(raw_request), _json(raw_config)
        _request(request, data)
        sidecar["observation_id"] = request["observation_id"]
        weights = _config(config)
        sidecar.update(observation_id=request["observation_id"], configuration=config)
        current_start = finish_stage("completed")
        current_stage = "model_initialization"
        engine = engine_factory(
            config["model_id"],
            weights,
            config["weights_sha256"],
            device=config["device"],
            threads=config["threads"],
        )
        engine.load()
        current_start = finish_stage("completed")
        current_stage = "inference"
        result = engine.predict(
            data, image_sha256=request["image_sha256"], crop=None, threshold=config["threshold"]
        )
        current_start = finish_stage("completed")
        current_stage = "response_validation_serialization"
        # Keep serializable raw evidence even when the stricter engine contract fails.
        sidecar["engine_response"] = _json(_encode(result))
        result = _prediction(result, request, config)
        sidecar.update(
            engine_response=result,
            selection_status=result["selection_status"],
            candidate=result["candidate"],
        )
        selection = result["selection_status"]
        response = {
            "schema": session.RESPONSE_SCHEMA,
            "observation_id": request["observation_id"],
            "image_sha256": request["image_sha256"],
            "status": "unavailable" if selection == "no_candidate" else "unknown",
            "mitt": None,
            "visibility": "unknown",
            "pose": "unknown",
            "reason": {
                "candidate": "Generic glove-box centroid retained in sidecar; catcher identity and mitt-body center are unverified.",
                "ambiguous": "Multiple glove candidates; no verified catcher-mitt center selected.",
                "no_candidate": "Detector found no glove candidate above the fixed threshold; this is not proof that the mitt is absent.",
            }[selection],
        }
        session._validate_response(response, request, require_partial_reason=True)
        encoded_response = _encode(response)
        # Recheck every bound input before publishing. Model failures never become abstentions.
        for path, expected in zip(inputs, (raw_request, data, raw_config), strict=True):
            if _path(path).read_bytes() != expected:
                raise ValueError("Observer input changed during processing")
        if _sha(_path(weights).read_bytes()) != config["weights_sha256"]:
            raise ValueError("Checkpoint changed during processing")
        finished = finish_stage("completed")
        sidecar.update(status="accepted", response_sha256=_sha(encoded_response))
    except (Exception, KeyboardInterrupt) as exc:
        finished = finish_stage("failed")
        sidecar["errors"].append({"type": type(exc).__name__, "message": str(exc)})
        sidecar["timing"] = {
            "clock": "perf_counter_ns",
            "clock_info": clock_info,
            "started_perf_counter_ns": started,
            "finished_perf_counter_ns": finished,
            "elapsed_seconds": (finished - started) / 1e9,
            "scope": "adapter entry through failure handling, including any config snapshot write; excludes final sidecar write",
            "cross_clock_alignment": "not established with outer loop monotonic_ns; compare durations, not absolute timestamps",
            "stages": stages,
        }
        _write(sidecar_path, _encode(sidecar))
        raise
    sidecar["timing"] = {
        "clock": "perf_counter_ns",
        "clock_info": clock_info,
        "started_perf_counter_ns": started,
        "finished_perf_counter_ns": finished,
        "elapsed_seconds": (finished - started) / 1e9,
        "scope": "adapter entry through response serialization and final input checks; includes config snapshot write; excludes final response/sidecar writes",
        "cross_clock_alignment": "not established with outer loop monotonic_ns; compare durations, not absolute timestamps",
        "stages": stages,
    }
    encoded_sidecar = _encode(sidecar)
    _write(sidecar_path, encoded_sidecar)
    _write(response_path, encoded_response)
    return sidecar


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("request", "image", "config", "response"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    parser.add_argument("--sidecar", type=Path)
    args = parser.parse_args(argv)
    observe(args.request, args.image, args.config, args.response, sidecar_path=args.sidecar)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

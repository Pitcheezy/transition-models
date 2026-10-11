"""Measure a trusted local AI pixel-observation handoff, without inferring pitch intent.

Elapsed time includes Codex orchestration and tool delays. It is neither model-only
latency nor live broadcast availability. File hashes and clock checks are consistency
guards for the same trusted host/session, not security or reboot attestation.
"""

from __future__ import annotations

import argparse
import io
import json
import platform
import time
import uuid
from fractions import Fraction
from pathlib import Path

from PIL import Image

from intent.replay import _no_links, _number, _write_new
from src.vision.frames import CACHE_SCHEMA, _seek, _sha256

REQUEST_SCHEMA = "intent_visual_observation_request_v1"
RESPONSE_SCHEMA = "intent_visual_observation_v1"
SESSION_SCHEMA = "intent_visual_observation_session_v1"
MAPPED_REQUEST_SCHEMA = "intent_visual_observation_request_v2"
MAPPED_SESSION_SCHEMA = "intent_visual_observation_session_v2"
MAPPED_TIME_FIELDS = (
    "source_time_basis",
    "source_time_seconds_exact",
    "requested_cutoff_seconds_exact",
)
LEGACY_PROMPT = (
    "Inspect only image.jpg and this request. Mark the center of the visible catcher's "
    "mitt body in original full-frame pixel coordinates [x,y], including a resting mitt. "
    "Do not substitute wrist, arm or ball. Judge pose separately; a still image may "
    "not establish motion. Do not infer pitch identity, pitcher intent, target location, "
    "physical coordinates, release time, calibration or prior labels. Use unavailable "
    "if the mitt center cannot be located, unknown if the judgment is uncertain; both "
    "require null mitt and a nonblank reason. Return exactly the response_schema fields "
    "as one JSON object. This is an AI observation, never a human label."
)
LEGACY_RESPONSE_FIELDS = {
    "schema": RESPONSE_SCHEMA,
    "observation_id": "copy request observation_id",
    "image_sha256": "copy request image_sha256",
    "status": "marked|unavailable|unknown",
    "mitt": "[x,y] finite in image bounds for marked; otherwise null",
    "visibility": "full|partial|hidden|unknown; marked requires full or partial",
    "pose": "presented_target|resting|moving|unknown",
    "reason": "string; nonblank for unavailable or unknown",
}
PROMPT = (
    LEGACY_PROMPT + " A marked partial mitt also requires a nonblank reason for partial visibility."
)
RESPONSE_FIELDS = {
    **LEGACY_RESPONSE_FIELDS,
    "reason": "string; nonblank for unavailable, unknown or marked partial",
}


def _path(value):
    path = Path(value).absolute()
    _no_links(path)
    return path.resolve()


def _output(value):
    path = _path(value)
    if path.parent.name != "outputs" or not path.name.startswith("cv_observation_"):
        raise ValueError("output must be an outputs/cv_observation_* directory")
    return path


def _source(frame, receipt, seconds):
    image_bytes, receipt_bytes = frame.read_bytes(), receipt.read_bytes()
    doc = json.loads(receipt_bytes)
    seconds = float(_seek(seconds))
    if (
        doc.get("schema") != CACHE_SCHEMA
        or not isinstance(doc.get("media_url"), str)
        or not doc["media_url"].strip()
        or type(doc.get("frame_seconds")) not in (int, float)
        or doc["frame_seconds"] != seconds
        or doc.get("sha256") != _sha256(image_bytes)
    ):
        raise ValueError("source receipt schema/time/image SHA256 mismatch")
    with Image.open(io.BytesIO(image_bytes)) as image:
        if image.format != "JPEG":
            raise ValueError("source frame must be an original JPEG")
        dimensions = image.size
        image.verify()
    return image_bytes, receipt_bytes, dimensions


def _publish(out, data, request, source_binding, schema):
    """Publish the anonymous image/request before pinning private source metadata."""
    out.mkdir(parents=True, exist_ok=False)
    public = out / "request"
    public.mkdir()
    with (public / "image.jpg").open("xb") as stream:
        stream.write(data)
    # Start immediately before request publication, including the small file-write cost.
    started_monotonic_ns, started_utc_ns = time.monotonic_ns(), time.time_ns()
    _write_new(public / "request.json", request)
    session = {
        "schema": schema,
        "host": platform.node(),
        "started_monotonic_ns": started_monotonic_ns,
        "started_utc_ns": started_utc_ns,
        "request_sha256": _sha256((public / "request.json").read_bytes()),
        "image_sha256": request["image_sha256"],
        "generator_code_sha256": _sha256(Path(__file__).read_bytes()),
        **source_binding,
    }
    _write_new(out / "session.json", session)
    return request


def _request(data, dimensions, seconds, schema):
    return {
        "schema": schema,
        "observation_id": uuid.uuid4().hex,
        "image_sha256": _sha256(data),
        "width": dimensions[0],
        "height": dimensions[1],
        "source_time_seconds": float(seconds),
        "prompt": PROMPT,
        "response_schema": RESPONSE_FIELDS,
    }


def begin(frame_path, source_seconds, out, source_receipt):
    """Publish one legacy anonymous request without changing the v1 receipt contract."""
    frame, receipt, out = _path(frame_path), _path(source_receipt), _output(out)
    data, receipt_data, dimensions = _source(frame, receipt, source_seconds)
    binding = {
        "source_frame": str(frame),
        "source_receipt": str(receipt),
        "source_receipt_sha256": _sha256(receipt_data),
        "source_time_seconds": float(source_seconds),
    }
    return _publish(
        out,
        data,
        _request(data, dimensions, source_seconds, REQUEST_SCHEMA),
        binding,
        SESSION_SCHEMA,
    )


def _load_mapped(directory):
    from intent import clip_capture, clip_clock, clip_frames

    verified = clip_frames.load_verified_frame(directory)
    hashes = {
        module.__name__: _sha256(Path(module.__file__).read_bytes())
        for module in (clip_frames, clip_clock, clip_capture)
    }
    return verified, hashes


def _mapped_source(directory):
    """Reverify mapped evidence and preserve actual time separately from requested cutoff."""
    directory = _path(directory)
    verified, helper_hashes = _load_mapped(directory)
    frame, receipt = _path(verified["image_path"]), _path(verified["receipt_path"])
    data, receipt_data = frame.read_bytes(), receipt.read_bytes()
    document = json.loads(receipt_data)
    if (
        _sha256(receipt_data) != verified["receipt_sha256"]
        or _sha256(data) != document["artifacts"]["image.jpg"]["sha256"]
    ):
        raise ValueError("mapped image/receipt changed during validation")
    seconds, cutoff = verified["source_seconds"], verified["requested_source_seconds"]
    if not isinstance(seconds, Fraction) or not isinstance(cutoff, Fraction) or seconds > cutoff:
        raise ValueError("mapped actual time must be an exact Fraction at or before cutoff")
    with Image.open(io.BytesIO(data)) as image:
        if image.format != "JPEG" or image.size != verified["dimensions"]:
            raise ValueError("mapped frame JPEG/dimensions mismatch")
        image.verify()
    binding = {
        "source_frame": str(frame),
        "source_receipt": str(receipt),
        "source_receipt_sha256": verified["receipt_sha256"],
        "source_time_seconds": float(seconds),
        "source_time_basis": "decoded_pts",
        "source_time_seconds_exact": str(seconds),
        "requested_cutoff_seconds_exact": str(cutoff),
        "mapped_frame_directory": str(directory),
        "mapped_frame_helper_code_sha256": helper_hashes,
    }
    return data, receipt_data, verified["dimensions"], binding


def begin_mapped(mapped_frame, out):
    """Publish an anonymous observation request from a verified decoded-clock frame."""
    out = _output(out)
    data, _, dimensions, binding = _mapped_source(mapped_frame)
    request = _request(data, dimensions, binding["source_time_seconds"], MAPPED_REQUEST_SCHEMA)
    request.update({key: binding[key] for key in MAPPED_TIME_FIELDS})
    return _publish(out, data, request, binding, MAPPED_SESSION_SCHEMA)


def _partial_reason_required(request):
    """Read the exact saved request contract without upgrading historical acceptance."""
    if request.get("prompt") == PROMPT and request.get("response_schema") == RESPONSE_FIELDS:
        return True
    if (
        request.get("prompt") == LEGACY_PROMPT
        and request.get("response_schema") == LEGACY_RESPONSE_FIELDS
    ):
        return False
    raise ValueError("Unexpected observation prompt/response contract")


def _validate_response(response, request, *, require_partial_reason=True):
    if not isinstance(response, dict) or response.keys() != RESPONSE_FIELDS.keys():
        raise ValueError("unexpected response fields")
    if (
        response["schema"] != RESPONSE_SCHEMA
        or response["observation_id"] != request["observation_id"]
        or response["image_sha256"] != request["image_sha256"]
    ):
        raise ValueError("response schema/observation/image binding mismatch")
    status = response["status"]
    if (
        status not in ("marked", "unavailable", "unknown")
        or response["visibility"] not in ("full", "partial", "hidden", "unknown")
        or response["pose"] not in ("presented_target", "resting", "moving", "unknown")
        or not isinstance(response["reason"], str)
    ):
        raise ValueError("invalid response status/visibility/pose/reason")
    if status == "marked":
        point = response["mitt"]
        if (
            not isinstance(point, list)
            or len(point) != 2
            or response["visibility"] not in ("full", "partial")
        ):
            raise ValueError("marked requires a visible finite pixel point")
        x, y = (_number(v, "mitt") for v in point)
        if not 0 <= x < request["width"] or not 0 <= y < request["height"]:
            raise ValueError("mitt outside image bounds")
        if (
            require_partial_reason
            and response["visibility"] == "partial"
            and not response["reason"].strip()
        ):
            raise ValueError("marked partial requires an explicit reason")
    elif response["mitt"] is not None or not response["reason"].strip():
        raise ValueError("unavailable/unknown requires null mitt and nonblank reason")


def finish(out, response_path):
    """Accept a real response once, verify bindings, and record handoff elapsed time."""
    out = Path(out)
    out = _output(out.parent if out.name == "session.json" else out)
    response_path = _path(response_path)
    response_bytes = response_path.read_bytes()
    finished_monotonic_ns, finished_utc_ns = time.monotonic_ns(), time.time_ns()
    paths = {name: _path(out / name) for name in ("session.json", "request/request.json")}
    session_bytes = paths["session.json"].read_bytes()
    session = json.loads(session_bytes)
    request_bytes = paths["request/request.json"].read_bytes()
    request = json.loads(request_bytes)
    if session.get("schema") not in (SESSION_SCHEMA, MAPPED_SESSION_SCHEMA):
        raise ValueError("unknown observation session schema")
    mapped = session["schema"] == MAPPED_SESSION_SCHEMA
    if mapped:
        if not isinstance(session.get("mapped_frame_directory"), str):
            raise ValueError("mapped session requires a mapped-frame directory")
        data, receipt_data, dimensions, binding = _mapped_source(session["mapped_frame_directory"])
        if any(session.get(key) != value for key, value in binding.items()):
            raise ValueError("mapped source/time/helper binding mismatch")
        if any(request.get(key) != binding[key] for key in MAPPED_TIME_FIELDS):
            raise ValueError("mapped request exact-time binding mismatch")
    else:
        data, receipt_data, dimensions = _source(
            _path(session["source_frame"]),
            _path(session["source_receipt"]),
            session["source_time_seconds"],
        )
    if (
        session.get("host") != platform.node()
        or session["request_sha256"] != _sha256(request_bytes)
        or session["image_sha256"] != _sha256(data)
        or session["source_receipt_sha256"] != _sha256(receipt_data)
        or session["generator_code_sha256"] != _sha256(Path(__file__).read_bytes())
        or _path(out / "request/image.jpg").read_bytes() != data
        or request.get("schema") != (MAPPED_REQUEST_SCHEMA if mapped else REQUEST_SCHEMA)
        or request["image_sha256"] != session["image_sha256"]
        or request["source_time_seconds"] != session["source_time_seconds"]
        or (request["width"], request["height"]) != dimensions
    ):
        raise ValueError("session/source/request/image/host consistency mismatch")
    for key in ("started_monotonic_ns", "started_utc_ns"):
        if type(session[key]) is not int or session[key] < 0:
            raise ValueError("invalid session clock")
    elapsed = finished_monotonic_ns - session["started_monotonic_ns"]
    utc_elapsed = finished_utc_ns - session["started_utc_ns"]
    if elapsed < 0 or utc_elapsed < 0 or abs(elapsed - utc_elapsed) > 5_000_000_000:
        raise ValueError("clock mismatch: reboot/clock adjustment or invalid same-host session")
    response = json.loads(response_bytes)
    _validate_response(response, request, require_partial_reason=True)
    result = {
        "schema": "intent_visual_observation_result_v2"
        if mapped
        else "intent_visual_observation_result_v1",
        "source_kind": "ai_visual_observation",
        "human_label": False,
        "availability_not_measured": True,
        "independent_validation": False,
        "source_time_seconds": request["source_time_seconds"],
        "request_sha256": _sha256(request_bytes),
        "session_sha256": _sha256(session_bytes),
        "raw_response_sha256": _sha256(response_bytes),
        "raw_response": response,
        "started_monotonic_ns": session["started_monotonic_ns"],
        "started_utc_ns": session["started_utc_ns"],
        "finished_monotonic_ns": finished_monotonic_ns,
        "finished_utc_ns": finished_utc_ns,
        "elapsed_seconds": elapsed / 1e9,
        "elapsed_scope": "request publication through response receipt; includes Codex "
        "orchestration and tool delays; not model-only latency or live availability",
        "clock_contract": "trusted same host/session; consistency check, not security attestation",
    }
    if mapped:
        result.update({key: request[key] for key in MAPPED_TIME_FIELDS})
        result["live_availability_verified"] = False
    _write_new(out / "result.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    start = subs.add_parser("begin")
    for option in ("frame", "receipt", "out"):
        start.add_argument(f"--{option}", type=Path, required=True)
    start.add_argument("--source-seconds", type=float, required=True)
    mapped = subs.add_parser("begin-mapped")
    mapped.add_argument("--mapped-frame", type=Path, required=True)
    mapped.add_argument("--out", type=Path, required=True)
    end = subs.add_parser("finish")
    end.add_argument("--session", type=Path, required=True)
    end.add_argument("--response", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.command == "begin":
        result = begin(args.frame, args.source_seconds, args.out, args.receipt)
    elif args.command == "begin-mapped":
        result = begin_mapped(args.mapped_frame, args.out)
    else:
        result = finish(args.session, args.response)
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

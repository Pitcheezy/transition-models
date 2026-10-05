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
from pathlib import Path

from PIL import Image

from intent.replay import _no_links, _number, _write_new
from src.vision.frames import CACHE_SCHEMA, _seek, _sha256

REQUEST_SCHEMA = "intent_visual_observation_request_v1"
RESPONSE_SCHEMA = "intent_visual_observation_v1"
SESSION_SCHEMA = "intent_visual_observation_session_v1"
PROMPT = (
    "Inspect only image.jpg and this request. Mark the center of the visible catcher's "
    "mitt body in original full-frame pixel coordinates [x,y], including a resting mitt. "
    "Do not substitute wrist, arm or ball. Judge pose separately; a still image may "
    "not establish motion. Do not infer pitch identity, pitcher intent, target location, "
    "physical coordinates, release time, calibration or prior labels. Use unavailable "
    "if the mitt center cannot be located, unknown if the judgment is uncertain; both "
    "require null mitt and a nonblank reason. Return exactly the response_schema fields "
    "as one JSON object. This is an AI observation, never a human label."
)
RESPONSE_FIELDS = {
    "schema": RESPONSE_SCHEMA,
    "observation_id": "copy request observation_id",
    "image_sha256": "copy request image_sha256",
    "status": "marked|unavailable|unknown",
    "mitt": "[x,y] finite in image bounds for marked; otherwise null",
    "visibility": "full|partial|hidden|unknown; marked requires full or partial",
    "pose": "presented_target|resting|moving|unknown",
    "reason": "string; nonblank for unavailable or unknown",
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


def begin(frame_path, source_seconds, out, source_receipt):
    """Publish one anonymous request and privately pin its source/time/hash receipt."""
    frame, receipt, out = _path(frame_path), _path(source_receipt), _output(out)
    data, receipt_data, (width, height) = _source(frame, receipt, source_seconds)
    request = {
        "schema": REQUEST_SCHEMA,
        "observation_id": uuid.uuid4().hex,
        "image_sha256": _sha256(data),
        "width": width,
        "height": height,
        "source_time_seconds": float(source_seconds),
        "prompt": PROMPT,
        "response_schema": RESPONSE_FIELDS,
    }
    out.mkdir(parents=True, exist_ok=False)
    public = out / "request"
    public.mkdir()
    with (public / "image.jpg").open("xb") as stream:
        stream.write(data)
    # Start immediately before request publication, including the small file-write cost.
    started_monotonic_ns, started_utc_ns = time.monotonic_ns(), time.time_ns()
    _write_new(public / "request.json", request)
    session = {
        "schema": SESSION_SCHEMA,
        "host": platform.node(),
        "started_monotonic_ns": started_monotonic_ns,
        "started_utc_ns": started_utc_ns,
        "request_sha256": _sha256((public / "request.json").read_bytes()),
        "image_sha256": request["image_sha256"],
        "source_frame": str(frame),
        "source_receipt": str(receipt),
        "source_receipt_sha256": _sha256(receipt_data),
        "source_time_seconds": float(source_seconds),
        "generator_code_sha256": _sha256(Path(__file__).read_bytes()),
    }
    _write_new(out / "session.json", session)
    return request


def _validate_response(response, request):
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
    data, receipt_data, dimensions = _source(
        _path(session["source_frame"]),
        _path(session["source_receipt"]),
        session["source_time_seconds"],
    )
    if (
        session.get("schema") != SESSION_SCHEMA
        or session.get("host") != platform.node()
        or session["request_sha256"] != _sha256(request_bytes)
        or session["image_sha256"] != _sha256(data)
        or session["source_receipt_sha256"] != _sha256(receipt_data)
        or session["generator_code_sha256"] != _sha256(Path(__file__).read_bytes())
        or _path(out / "request/image.jpg").read_bytes() != data
        or request.get("schema") != REQUEST_SCHEMA
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
    _validate_response(response, request)
    result = {
        "schema": "intent_visual_observation_result_v1",
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
    _write_new(out / "result.json", result)
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    subs = parser.add_subparsers(dest="command", required=True)
    start = subs.add_parser("begin")
    for option in ("frame", "receipt", "out"):
        start.add_argument(f"--{option}", type=Path, required=True)
    start.add_argument("--source-seconds", type=float, required=True)
    end = subs.add_parser("finish")
    end.add_argument("--session", type=Path, required=True)
    end.add_argument("--response", type=Path, required=True)
    args = parser.parse_args(argv)
    result = (
        begin(args.frame, args.source_seconds, args.out, args.receipt)
        if args.command == "begin"
        else finish(args.session, args.response)
    )
    print(json.dumps(result, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

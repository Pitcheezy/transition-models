"""IntentEstimate v1: builders and the validator the service side will mirror.

Rules (from docs/INTENT_V0_WORK_ORDER.md):
- ``status`` is ``estimated`` or ``unavailable``; there is no ``observed``.
- ``is_intent_proxy`` is always true; ``catcher_intent_verified`` and
  ``independent_ground_truth`` are always false; ``accuracy_estimate`` is null until measured.
- ``points`` holds exactly the coordinate frames that were actually reached, in hop order
  ``image_pixels`` -> ``annotated_image_zone`` -> ``plate_feet``; hops are never skipped.
- A transform whose error is unknown stores ``error=null`` with ``error_status="unmeasured"``.
- ``evidence.frame_index`` is the source-video frame number (a nonnegative integer); a frame
  grabbed by time uses ``round(frame_time * fps)``.
- ``plate_feet`` is keyed ``x``/``z`` like Statcast ``plate_x``/``plate_z``.
- A record that stops short names what blocked the next hop: ``no_image_plane_calibration``
  (stopped at image_pixels), ``no_plate_plane_calibration`` (annotated_image_zone),
  ``no_batter_zone_bounds`` (plate_feet; the service's next frame is the batter zone9).

The 2026-10-02 rules (frame_index, x/z, blockers) follow the service-side validator
``apps/observer/backend/observer_app/intent.py`` in SongRoute/pitcheezy at its commit 8771c06.
"""

from __future__ import annotations

import math
import re
from copy import deepcopy
from fractions import Fraction

SCHEMA_VERSION = 1
STATUSES = ("estimated", "unavailable")
FRAMES = ("image_pixels", "annotated_image_zone", "plate_feet")
LABEL_SOURCES = ("video_module", "assistant_visual_estimate", "human_manual_annotation")
REVIEW_STATUSES = ("unreviewed", "reviewed")
FRAME_KEYS = {
    "image_pixels": ("x", "y"),
    "annotated_image_zone": ("x", "y"),
    "plate_feet": ("x", "z"),
}
BLOCKED_BY = {
    "image_pixels": "no_image_plane_calibration",
    "annotated_image_zone": "no_plate_plane_calibration",
    "plate_feet": "no_batter_zone_bounds",
}
BLOCKERS = tuple(BLOCKED_BY.values())
ERROR_STATUSES = ("measured", "unmeasured")
PITCH_ID = re.compile(r"^\d+:\d+:\d+$")
SHA256 = re.compile(r"^[0-9a-f]{64}$")
TOP_KEYS = {
    "schema_version",
    "pitch_id",
    "clip_id",
    "clip_sha256",
    "status",
    "unavailable_reason",
    "method",
    "evidence",
    "provenance",
    "deepest_frame",
    "blocked_by",
    "points",
    "transform_chain",
    "uncertainty",
    "is_intent_proxy",
    "claims",
}
TRANSFORM_KEYS = {
    "source_frame",
    "target_frame",
    "method",
    "version",
    "error",
    "error_units",
    "error_status",
    "evidence",
}
CLAIM_KEYS = {
    "catcher_intent_verified",
    "independent_ground_truth",
    "physical_plate_coordinates",
    "accuracy_estimate",
}


class IntentEstimateError(ValueError):
    """Raised with a human-readable reason when a record breaks the v1 contract."""


def _fail(reason):
    raise IntentEstimateError(reason)


def _finite(value):
    return isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)


def _nonempty(value):
    return isinstance(value, str) and value.strip() != ""


def _check_point(point, name, keys=("x", "y"), extra=()):
    if not isinstance(point, dict) or set(point) != {*keys, *extra}:
        _fail(f"{name} must be an object with keys " + ", ".join((*keys, *extra)))
    if not all(_finite(point[key]) for key in keys):
        _fail(f"{name} coordinates must be finite numbers")


def frame_index_from_time(frame_time, fps_num, fps_den):
    """Source-video frame number of a frame grabbed by time: round(frame_time * fps)."""
    if not (_finite(frame_time) and frame_time >= 0):
        raise IntentEstimateError("frame_time must be a nonnegative number")
    if not (isinstance(fps_num, int) and isinstance(fps_den, int) and fps_num > 0 and fps_den > 0):
        raise IntentEstimateError("fps must be a positive integer ratio")
    return int(round(Fraction(str(frame_time)) * fps_num / fps_den))


def validate_intent_estimate(doc):
    """Return the record unchanged when it satisfies IntentEstimate v1; raise otherwise."""
    if not isinstance(doc, dict):
        _fail("record must be an object")
    if set(doc) != TOP_KEYS:
        missing, extra = TOP_KEYS - set(doc), set(doc) - TOP_KEYS
        _fail(f"unexpected record keys (missing {sorted(missing)}, extra {sorted(extra)})")
    if doc["schema_version"] != SCHEMA_VERSION:
        _fail("schema_version must be 1")
    if not (isinstance(doc["pitch_id"], str) and PITCH_ID.match(doc["pitch_id"])):
        _fail("pitch_id must be <game_pk>:<at_bat_number>:<pitch_number>")
    if not _nonempty(doc["clip_id"]):
        _fail("clip_id is required")
    if not (isinstance(doc["clip_sha256"], str) and SHA256.match(doc["clip_sha256"])):
        _fail("clip_sha256 must be a 64-hex digest")
    if doc["status"] not in STATUSES:
        _fail("status must be estimated or unavailable (observed does not exist)")
    method = doc["method"]
    if not (isinstance(method, dict) and set(method) == {"kind", "version"}):
        _fail("method must have kind and version")
    if not (_nonempty(method["kind"]) and _nonempty(method["version"])):
        _fail("method.kind and method.version must be nonempty")
    evidence = doc["evidence"]
    if not (isinstance(evidence, dict) and set(evidence) == {"frame_index", "frame_time"}):
        _fail("evidence must have frame_index and frame_time")
    if type(evidence["frame_index"]) is not int or evidence["frame_index"] < 0:
        _fail("evidence.frame_index must be a nonnegative integer (source-video frame number)")
    if not (_finite(evidence["frame_time"]) and evidence["frame_time"] >= 0):
        _fail("evidence.frame_time must be a nonnegative number")
    prov = doc["provenance"]
    if not (isinstance(prov, dict) and set(prov) == {"label_source", "review_status"}):
        _fail("provenance must have label_source and review_status")
    if prov["label_source"] not in LABEL_SOURCES:
        _fail("provenance.label_source is not a known source")
    if prov["review_status"] not in REVIEW_STATUSES:
        _fail("provenance.review_status must be unreviewed or reviewed")
    if doc["is_intent_proxy"] is not True:
        _fail("is_intent_proxy must be true: the catcher setup is a proxy for intent")
    claims = doc["claims"]
    if not (isinstance(claims, dict) and set(claims) == CLAIM_KEYS):
        _fail("claims must have exactly the four claim keys")
    if (
        claims["catcher_intent_verified"] is not False
        or claims["independent_ground_truth"] is not False
    ):
        _fail("catcher_intent_verified and independent_ground_truth must be false")
    if claims["physical_plate_coordinates"] not in (True, False):
        _fail("physical_plate_coordinates must be a boolean")
    acc = claims["accuracy_estimate"]
    if acc is not None and not (isinstance(acc, dict) and acc):
        _fail("accuracy_estimate must be null until measured, or a nonempty object")
    unc = doc["uncertainty"]
    if not (isinstance(unc, dict) and set(unc) == {"value", "units", "basis"}):
        _fail("uncertainty must have value, units and basis")
    if not (unc["value"] is None or (_finite(unc["value"]) and unc["value"] >= 0)):
        _fail("uncertainty.value must be a nonnegative number or null")
    if not (_nonempty(unc["units"]) and _nonempty(unc["basis"])):
        _fail("uncertainty.units and basis must be nonempty")
    if doc["blocked_by"] is not None and doc["blocked_by"] not in BLOCKERS:
        _fail("blocked_by must be one of " + ", ".join(BLOCKERS) + " or null")
    chain = doc["transform_chain"]
    if not isinstance(chain, list):
        _fail("transform_chain must be a list")
    points = doc["points"]
    if not isinstance(points, dict):
        _fail("points must be an object")

    if doc["status"] == "unavailable":
        if not _nonempty(doc["unavailable_reason"]):
            _fail("unavailable records need an unavailable_reason")
        if points or chain or doc["deepest_frame"] is not None or doc["blocked_by"] is not None:
            _fail("unavailable records carry no points, transforms, deepest_frame or blocked_by")
        return doc

    if doc["unavailable_reason"] is not None:
        _fail("estimated records must not carry an unavailable_reason")
    deepest = doc["deepest_frame"]
    if deepest not in FRAMES:
        _fail("deepest_frame must be image_pixels, annotated_image_zone or plate_feet")
    reached = FRAMES[: FRAMES.index(deepest) + 1]
    if tuple(points) != reached:
        _fail(f"points keys must be exactly the reached frames in order {reached}")
    _check_point(points["image_pixels"], "points.image_pixels")
    if "annotated_image_zone" in points:
        zone = points["annotated_image_zone"]
        _check_point(zone, "points.annotated_image_zone", extra=("inside_annotated_quad",))
        if zone["inside_annotated_quad"] not in (True, False):
            _fail("inside_annotated_quad must be a boolean")
    if "plate_feet" in points:
        _check_point(
            points["plate_feet"], "points.plate_feet", FRAME_KEYS["plate_feet"], ("x_convention",)
        )
        if points["plate_feet"]["x_convention"] != "statcast_plate_x_catcher_view":
            _fail("plate_feet.x_convention must be statcast_plate_x_catcher_view")
    if len(chain) != len(reached) - 1:
        _fail("transform_chain must have one entry per hop actually taken")
    for index, step in enumerate(chain):
        if not (isinstance(step, dict) and set(step) == TRANSFORM_KEYS):
            _fail(f"transform_chain[{index}] has wrong keys")
        if (step["source_frame"], step["target_frame"]) != (reached[index], reached[index + 1]):
            _fail(f"transform_chain[{index}] must map {reached[index]} -> {reached[index + 1]}")
        if not (_nonempty(step["method"]) and _nonempty(step["version"])):
            _fail(f"transform_chain[{index}] needs method and version")
        if step["error_status"] not in ERROR_STATUSES:
            _fail(f"transform_chain[{index}].error_status must be measured or unmeasured")
        if step["error_status"] == "unmeasured" and step["error"] is not None:
            _fail(f"transform_chain[{index}]: an unmeasured error must be null")
        if step["error_status"] == "measured" and not (
            _finite(step["error"]) and step["error"] >= 0
        ):
            _fail(f"transform_chain[{index}]: a measured error must be a nonnegative number")
        if not _nonempty(step["error_units"]):
            _fail(f"transform_chain[{index}].error_units is required")
        if not isinstance(step["evidence"], dict):
            _fail(f"transform_chain[{index}].evidence must be an object")
    if doc["blocked_by"] != BLOCKED_BY[deepest]:
        _fail(f"a record that stops at {deepest} must set blocked_by={BLOCKED_BY[deepest]}")
    if claims["physical_plate_coordinates"] is not (deepest == "plate_feet"):
        _fail("physical_plate_coordinates must be true exactly when plate_feet is reached")
    return doc


def _base(pitch_id, clip_id, clip_sha256, method, frame_time, label_source, frame_index):
    return {
        "schema_version": SCHEMA_VERSION,
        "pitch_id": pitch_id,
        "clip_id": clip_id,
        "clip_sha256": clip_sha256,
        "method": deepcopy(method),
        "evidence": {"frame_index": frame_index, "frame_time": frame_time},
        "provenance": {"label_source": label_source, "review_status": "unreviewed"},
        "is_intent_proxy": True,
        "claims": {
            "catcher_intent_verified": False,
            "independent_ground_truth": False,
            "physical_plate_coordinates": False,
            "accuracy_estimate": None,
        },
    }


def make_unavailable(
    pitch_id, clip_id, clip_sha256, method, frame_time, label_source, reason, *, frame_index
):
    doc = _base(pitch_id, clip_id, clip_sha256, method, frame_time, label_source, frame_index)
    doc.update(
        {
            "status": "unavailable",
            "unavailable_reason": reason,
            "deepest_frame": None,
            "blocked_by": None,
            "points": {},
            "transform_chain": [],
            "uncertainty": {"value": None, "units": "pixels", "basis": "no estimate"},
        }
    )
    return validate_intent_estimate(doc)


def make_estimate(
    pitch_id,
    clip_id,
    clip_sha256,
    method,
    frame_time,
    label_source,
    image_pixels,
    uncertainty_pixels,
    uncertainty_basis,
    annotated_zone=None,
    zone_transform=None,
    plate_feet=None,
    feet_transform=None,
    *,
    frame_index,
):
    """Build an estimated record for the deepest frame given: pixels, zone, or plate feet.

    ``plate_feet`` is ``(plate_x_ft, plate_z_ft)``; the record stores it as ``x``/``z`` with the
    fixed ``x_convention`` (``z`` is the height above the ground, Statcast plate_z).
    """
    doc = _base(pitch_id, clip_id, clip_sha256, method, frame_time, label_source, frame_index)
    points = {"image_pixels": {"x": float(image_pixels[0]), "y": float(image_pixels[1])}}
    chain = []
    deepest = "image_pixels"
    if annotated_zone is not None:
        if zone_transform is None:
            raise IntentEstimateError("annotated_image_zone needs its transform step")
        points["annotated_image_zone"] = {
            "x": float(annotated_zone[0]),
            "y": float(annotated_zone[1]),
            "inside_annotated_quad": bool(annotated_zone[2]),
        }
        chain.append(deepcopy(zone_transform))
        deepest = "annotated_image_zone"
    if plate_feet is not None:
        if annotated_zone is None or feet_transform is None:
            raise IntentEstimateError("plate_feet needs the zone hop and its own transform step")
        points["plate_feet"] = {
            "x": float(plate_feet[0]),
            "z": float(plate_feet[1]),
            "x_convention": "statcast_plate_x_catcher_view",
        }
        chain.append(deepcopy(feet_transform))
        deepest = "plate_feet"
    doc.update(
        {
            "status": "estimated",
            "unavailable_reason": None,
            "deepest_frame": deepest,
            "blocked_by": BLOCKED_BY[deepest],
            "points": points,
            "transform_chain": chain,
            "uncertainty": {
                "value": float(uncertainty_pixels),
                "units": "pixels",
                "basis": uncertainty_basis,
            },
        }
    )
    if deepest == "plate_feet":
        doc["claims"]["physical_plate_coordinates"] = True
    return validate_intent_estimate(doc)

"""Identity-bound development comparison of local glove candidates and old labels.

The pure API checks declared manifest bindings. The CLI additionally checks the
actual manifest file bytes; neither path opens image files or runs a model.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path
from statistics import median

SCHEMA = "local_glove_report_v1"
SENSITIVITY_PIXELS = (5, 10, 20, 50)
LEGACY_STATUSES = {"marked", "hidden", "not_in_setup", "not_centre_field"}
PREDICTION_STATES = ("candidate", "no_candidate", "ambiguous", "error", "not_attempted")
LIMITATIONS = [
    "Previously reviewed, single-labeler development frames; not new independent validation.",
    "Legacy nonmarked labels use older definitions and are not current true negatives.",
    "Availability cross-tabs are descriptive; no false-positive or abstention-correctness rates.",
    "Point differences are conditional on both points existing, not overall accuracy.",
    "Fixed pixel sensitivity fractions include every legacy marked frame in their denominator.",
    "Pixel sensitivity cutoffs are descriptive, not success thresholds or physical tolerances.",
    "No physical-coordinate accuracy, pitcher intent, live latency, or pre-pitch success claim.",
    "Stored image hashes are matched; image bytes are not reopened by this report.",
    "Timing describes the supplied first pass; repeat timings belong to a separate artifact.",
]


def _finite_tree(value, name):
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"nonfinite number in {name}")
    if isinstance(value, dict):
        for key, item in value.items():
            _finite_tree(item, f"{name}.{key}")
    elif isinstance(value, (list, tuple)):
        for index, item in enumerate(value):
            _finite_tree(item, f"{name}[{index}]")


def _number(value, name, minimum=None, maximum=None):
    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or (minimum is not None and value < minimum)
        or (maximum is not None and value > maximum)
    ):
        raise ValueError(f"invalid finite number: {name}")
    return float(value)


def _text(value, name):
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"nonempty string required: {name}")
    return value


def _integer(value, name):
    if type(value) is not int or value <= 0:
        raise ValueError(f"positive integer required: {name}")
    return value


def _sha(value, name):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError(f"invalid SHA256: {name}")
    return value


def _document(value, schema, name):
    if not isinstance(value, dict) or value.get("schema") != schema:
        raise ValueError(f"unexpected {name} schema")
    _finite_tree(value, name)


def _index(rows, name):
    if not isinstance(rows, list):
        raise ValueError(f"{name} must be a list")
    result = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{name} row must be an object")
        identity = _text(row.get("observation_id"), f"{name}.observation_id")
        if identity in result:
            raise ValueError(f"duplicate observation_id in {name}: {identity}")
        result[identity] = row
    return result


def _point(value, frame, name):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{name} must be [x, y]")
    x, y = (_number(item, name, minimum=0) for item in value)
    if x >= frame["width"] or y >= frame["height"]:
        raise ValueError(f"out-of-bounds point in {name}")
    return [x, y]


def _box(value, frame, name):
    if not isinstance(value, (list, tuple)) or len(value) != 4:
        raise ValueError(f"{name} must be [x1, y1, x2, y2]")
    x1, y1, x2, y2 = (_number(item, name, minimum=0) for item in value)
    if not (x1 < x2 <= frame["width"] and y1 < y2 <= frame["height"]):
        raise ValueError(f"out-of-bounds box in {name}")


def _validate_manifest(manifest):
    _document(manifest, "local_glove_frames_v1", "manifest")
    frames = _index(manifest.get("frames"), "manifest.frames")
    for identity, frame in frames.items():
        _integer(frame.get("game_pk"), f"{identity}.game_pk")
        _integer(frame.get("width"), f"{identity}.width")
        _integer(frame.get("height"), f"{identity}.height")
        _sha(frame.get("image_sha256"), f"{identity}.image_sha256")
        _text(frame.get("image_path"), f"{identity}.image_path")
        _box(frame.get("legacy_main_crop"), frame, f"{identity}.legacy_main_crop")
    return frames


def _bound_rows(document, key, frames, *, require_all, game_required):
    indexed = _index(document.get(key), key)
    if set(indexed) - set(frames):
        raise ValueError(f"unknown observation_id in {key}")
    if require_all and set(indexed) != set(frames):
        raise ValueError(f"missing reference observation_id in {key}")
    for identity, row in indexed.items():
        frame = frames[identity]
        if row.get("image_sha256") != frame["image_sha256"]:
            raise ValueError(f"image SHA256 mismatch: {identity}")
        if game_required or "game_pk" in row:
            if type(row.get("game_pk")) is not int or row["game_pk"] != frame["game_pk"]:
                raise ValueError(f"game_pk mismatch: {identity}")
    return indexed


RUN_INTEGRITY_FIELDS = {
    "run_status",
    "frozen_inputs_unchanged",
    "eligible_for_development_comparison",
}


def _validate_run_integrity(predictions):
    """Refuse invalidated runs; distinguish old inputs with no integrity claims."""
    present = RUN_INTEGRITY_FIELDS.intersection(predictions)
    if not present:
        return {
            "metadata_present": False,
            "declared_claims_checked": False,
            "assessment": "not_established_legacy_saved_result",
            "run_status": None,
            "frozen_input_bytes_reverified": False,
        }
    if predictions.get("run_status") in {"invalidated", "frozen_inputs_changed"}:
        raise ValueError("invalidated run is ineligible for development comparison")
    for key in ("frozen_inputs_unchanged", "eligible_for_development_comparison"):
        if key in predictions and predictions[key] is not True:
            raise ValueError(f"run is ineligible for development comparison: {key}")
    if present != RUN_INTEGRITY_FIELDS:
        raise ValueError("incomplete run-integrity metadata")
    status = predictions["run_status"]
    if status not in {"completed", "completed_with_errors", "failed", "interrupted"}:
        raise ValueError("unsupported run_status for development comparison")
    return {
        "metadata_present": True,
        "declared_claims_checked": True,
        "assessment": "declared_eligible_not_independently_reverified",
        "run_status": status,
        "frozen_input_bytes_reverified": False,
    }


def _validate_detection_contract(row, frame, threshold, input_view):
    """Recompute score selection and original-pixel centroids from saved boxes."""
    if row["status"] == "error":
        return
    region = (
        frame["legacy_main_crop"]
        if input_view == "legacy_main_crop"
        else [0, 0, frame["width"], frame["height"]]
    )
    candidates = []
    for detection in row["detections"]:
        required = {"label", "box_xyxy", "center_xy", "score", "above_threshold"}
        if not required <= set(detection):
            raise ValueError(
                "benchmark detection requires label, box, center, score and threshold flag"
            )
        if type(detection["label"]) is not int or detection["label"] != 40:
            raise ValueError("benchmark detection class must be baseball glove (40)")
        if "category" in detection and detection["category"] != "baseball glove":
            raise ValueError("benchmark detection category mismatch")
        x1, y1, x2, y2 = detection["box_xyxy"]
        if not (region[0] <= x1 < x2 <= region[2] and region[1] <= y1 < y2 <= region[3]):
            raise ValueError("benchmark detection box lies outside its declared input view")
        center = _point(detection["center_xy"], frame, "detection.center_xy")
        if center != [(x1 + x2) / 2, (y1 + y2) / 2]:
            raise ValueError("benchmark detection center must equal its box centroid")
        score = _number(detection["score"], "detection.score", 0, 1)
        above = score >= threshold
        if type(detection["above_threshold"]) is not bool or detection["above_threshold"] != above:
            raise ValueError("benchmark detection threshold flag does not match its score")
        if above:
            candidates.append(detection)
    expected = (
        "no_candidate" if not candidates else "candidate" if len(candidates) == 1 else "ambiguous"
    )
    if row["selection_status"] != expected:
        raise ValueError("benchmark selection_status disagrees with threshold-qualified detections")
    candidate = candidates[0] if len(candidates) == 1 else None
    expected_point = None if candidate is None else candidate["center_xy"]
    if row["point"] != expected_point:
        raise ValueError("benchmark point must equal the uniquely selected box centroid")
    if "engine_response" in row:
        response = row["engine_response"]
        if not isinstance(response, dict):
            raise ValueError("benchmark engine_response must be an object")
        if (
            _number(response.get("threshold"), "engine_response.threshold", 0, 1) != threshold
            or response.get("selection_status") != expected
            or response.get("detections") != row["detections"]
            or response.get("candidate") != candidate
        ):
            raise ValueError(
                "benchmark engine_response disagrees with the scored detection contract"
            )


def _validate_prediction(row, frame, *, threshold=None, input_view=None):
    status, selection, point = row.get("status"), row.get("selection_status"), row.get("point")
    if status not in {"completed", "error"}:
        raise ValueError("prediction status must be completed or error")
    if "point" not in row or "selection_status" not in row or "error" not in row:
        raise ValueError("prediction point, selection_status and error fields are required")
    if status == "error":
        if selection is not None or point is not None:
            raise ValueError("error prediction cannot carry a selection or point")
        _text(row["error"], "prediction.error")
    else:
        if row["error"] is not None:
            raise ValueError("completed prediction cannot carry an error")
        if selection not in {"candidate", "no_candidate", "ambiguous"}:
            raise ValueError("invalid completed selection_status")
        if selection == "candidate":
            _point(point, frame, "prediction.point")
        elif point is not None:
            raise ValueError("non-candidate completed prediction cannot carry a point")
    detections = row.get("detections")
    if not isinstance(detections, list) or any(not isinstance(d, dict) for d in detections):
        raise ValueError("detections must be a list of objects")
    for detection in detections:
        if "box_xyxy" in detection:
            _box(detection["box_xyxy"], frame, "detection.box_xyxy")
        if "center_xy" in detection:
            _point(detection["center_xy"], frame, "detection.center_xy")
        if "score" in detection:
            _number(detection["score"], "detection.score", 0, 1)
    timing = row.get("timing")
    if not isinstance(timing, dict) or not {"model_seconds", "service_seconds"} <= set(timing):
        raise ValueError("prediction timing requires model_seconds and service_seconds")
    for key in ("model_seconds", "service_seconds"):
        if timing[key] is None and status == "error":
            continue
        _number(timing[key], key, minimum=0)

    if threshold is not None:
        _validate_detection_contract(row, frame, threshold, input_view)


def _summary(values):
    """Use a linear-interpolated 90th percentile, including for signed differences."""
    if not values:
        return {"n": 0, "median": None, "p90": None}
    values = sorted(values)
    position = (len(values) - 1) * 0.9
    lo, hi = math.floor(position), math.ceil(position)
    return {
        "n": len(values),
        "median": float(median(values)),
        "p90": values[lo] + (values[hi] - values[lo]) * (position - lo),
    }


def _fraction(numerator, denominator):
    return {
        "numerator": numerator,
        "denominator": denominator,
        "fraction": numerator / denominator if denominator else None,
    }


def _aggregate(rows):
    counts = {
        key: 0
        for key in (
            "planned",
            "attempted",
            "completed",
            "error",
            "not_attempted",
            "candidate",
            "no_candidate",
            "ambiguous",
            "human_marked",
            "legacy_abstained",
        )
    }
    cross = {
        status: dict.fromkeys(PREDICTION_STATES, 0)
        for status in ("legacy_marked", "legacy_abstained")
    }
    for row in rows:
        counts["planned"] += 1
        state = row["prediction_state"]
        counts[state] += 1
        counts["attempted"] += state != "not_attempted"
        counts["completed"] += state in {"candidate", "no_candidate", "ambiguous"}
        marked = row["legacy_mitt_status"] == "marked"
        counts["human_marked" if marked else "legacy_abstained"] += 1
        cross["legacy_marked" if marked else "legacy_abstained"][state] += 1
    pairs = [row["difference"] for row in rows if row["difference"] is not None]
    metrics = (
        "distance_pixels",
        "dx_pixels",
        "dy_pixels",
        "distance_image_diagonal",
        "dx_image_diagonal",
        "dy_image_diagonal",
    )
    return {
        "counts": counts,
        "availability": {
            "completed_over_planned": _fraction(counts["completed"], counts["planned"]),
            "candidate_over_planned": _fraction(counts["candidate"], counts["planned"]),
            "legacy_reference_by_prediction_state": cross,
            "legacy_status_counts": dict(
                sorted(Counter(r["legacy_mitt_status"] for r in rows).items())
            ),
        },
        "conditional_point_discrepancy": {
            "n": len(pairs),
            "sign_convention": "prediction_minus_legacy_reference; x right, y down",
            "normalization": "sqrt(width**2 + height**2), original full image",
            "percentile_method": "linear",
            **{key: _summary([pair[key] for pair in pairs]) for key in metrics},
        },
        "fixed_pixel_sensitivity": {
            "interpretation": "descriptive fractions, not accuracy or a success criterion",
            "denominator_basis": "all_legacy_marked_in_manifest_including_error_abstention_missing",
            "cutoffs": [
                {
                    "maximum_distance_pixels": cutoff,
                    **_fraction(
                        sum(pair["distance_pixels"] <= cutoff for pair in pairs),
                        counts["human_marked"],
                    ),
                }
                for cutoff in SENSITIVITY_PIXELS
            ],
        },
        "first_pass_timing_seconds": {
            key: _summary([row["timing"][key] for row in rows if row["timing"][key] is not None])
            for key in ("model_seconds", "service_seconds")
        },
    }


def build_report(manifest, references, predictions):
    """Return a new report without I/O, mutation, model calls, or denominator filtering.

    Declared manifest hashes must agree. Only main() can additionally bind those
    hashes to the original manifest bytes, whose JSON formatting is not retained here.
    """
    frames = _validate_manifest(manifest)
    _document(references, "local_glove_references_v1", "references")
    _document(predictions, "local_glove_predictions_v1", "predictions")
    run_integrity = _validate_run_integrity(predictions)
    manifest_sha = _sha(references.get("manifest_sha256"), "references.manifest_sha256")
    if predictions.get("manifest_sha256") != manifest_sha:
        raise ValueError("manifest SHA256 mismatch between references and predictions")
    refs = _bound_rows(references, "references", frames, require_all=True, game_required=True)
    preds = _bound_rows(predictions, "frames", frames, require_all=False, game_required=False)
    for key in ("model_id", "device"):
        _text(predictions.get(key), key)
    if predictions.get("input_view") not in {"full_frame", "legacy_main_crop"}:
        raise ValueError("invalid input_view")
    threshold = _number(predictions.get("threshold"), "threshold", 0, 1)
    rows = []
    for identity, frame in frames.items():
        reference, prediction = refs[identity], preds.get(identity)
        legacy_status = reference.get("legacy_mitt_status")
        if legacy_status not in LEGACY_STATUSES:
            raise ValueError(f"invalid legacy_mitt_status: {identity}")
        if "mitt" not in reference:
            raise ValueError(f"reference mitt is required: {identity}")
        if legacy_status == "marked":
            _point(reference["mitt"], frame, "reference.mitt")
        elif reference["mitt"] is not None:
            raise ValueError("legacy nonmarked reference cannot carry a mitt point")
        state, point = "not_attempted", None
        timing = {"model_seconds": None, "service_seconds": None}
        if prediction is not None:
            _validate_prediction(
                prediction,
                frame,
                threshold=threshold if run_integrity["metadata_present"] else None,
                input_view=predictions["input_view"],
            )
            state = (
                prediction["selection_status"] if prediction["status"] == "completed" else "error"
            )
            point, timing = prediction["point"], dict(prediction["timing"])
        difference = None
        if legacy_status == "marked" and point is not None:
            dx, dy = (float(point[i] - reference["mitt"][i]) for i in (0, 1))
            diagonal = math.hypot(frame["width"], frame["height"])
            distance = math.hypot(dx, dy)
            difference = {
                "dx_pixels": dx,
                "dy_pixels": dy,
                "distance_pixels": distance,
                "dx_image_diagonal": dx / diagonal,
                "dy_image_diagonal": dy / diagonal,
                "distance_image_diagonal": distance / diagonal,
            }
        rows.append(
            {
                "observation_id": identity,
                "game_pk": frame["game_pk"],
                "image_sha256": frame["image_sha256"],
                "legacy_mitt_status": legacy_status,
                "prediction_state": state,
                "point": None if point is None else list(point),
                "difference": difference,
                "timing": timing,
                "error": None if prediction is None else prediction["error"],
            }
        )
    games = sorted({row["game_pk"] for row in rows})
    return {
        "schema": SCHEMA,
        "development_only": True,
        "independent_validation": False,
        "catcher_association_verified": False,
        "live": False,
        "physical_accuracy_measured": False,
        "manifest_sha256": manifest_sha,
        "provenance": {
            "manifest_bytes_verified": False,
            "image_bytes_verified": False,
            "reference_kind": "legacy_single_labeler_development",
            "run_integrity": run_integrity,
            "detection_contract_checked": run_integrity["metadata_present"],
        },
        "model": {
            key: predictions[key] for key in ("model_id", "input_view", "threshold", "device")
        },
        "limitations": list(LIMITATIONS)
        + (
            []
            if run_integrity["metadata_present"]
            else [
                "Run-integrity metadata is absent: eligibility and the detection-selection contract are not established for this legacy saved result."
            ]
        ),
        "summary": _aggregate(rows),
        "games": [
            {"game_pk": game, **_aggregate([row for row in rows if row["game_pk"] == game])}
            for game in games
        ],
        "frames": rows,
    }


def _unique_object(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"duplicate JSON object key: {key}")
        result[key] = value
    return result


def main(argv=None):
    """Read three bound documents and create one fresh report file."""
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("manifest", "references", "predictions", "out"):
        parser.add_argument(f"--{name}", type=Path, required=True)
    args = parser.parse_args(argv)
    if args.out.exists():
        raise FileExistsError(f"report output already exists: {args.out}")
    blobs = {
        name: getattr(args, name).read_bytes() for name in ("manifest", "references", "predictions")
    }
    documents = {
        name: json.loads(blob.decode("utf-8-sig"), object_pairs_hook=_unique_object)
        for name, blob in blobs.items()
    }
    manifest_sha = hashlib.sha256(blobs["manifest"]).hexdigest()
    for name in ("references", "predictions"):
        if documents[name].get("manifest_sha256") != manifest_sha:
            raise ValueError(f"{name} does not bind the manifest file bytes")
    report = build_report(**documents)
    report["provenance"].update(
        manifest_bytes_verified=True,
        input_files={
            name: {
                "filename": getattr(args, name).name,
                "sha256": hashlib.sha256(blob).hexdigest(),
            }
            for name, blob in blobs.items()
        },
    )
    payload = json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    with args.out.open("x", encoding="utf-8", newline="\n") as handle:
        handle.write(payload)
    return report


if __name__ == "__main__":
    main()

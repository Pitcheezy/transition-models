"""Run a frozen local glove-candidate benchmark without reading human references.

Only first-pass predictions are scored. Later fixed passes measure repeat latency,
never replace a failed or unfavorable first prediction. No network or implicit resume.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import platform
import re
import statistics
import time
from pathlib import Path

from PIL import Image

from intent.local_glove_detector import SPECS, LocalGloveDetector
from intent.replay import _no_links

PLAN_SCHEMA = "local_glove_benchmark_plan_v1"
PLAN_FIELDS = {
    "schema",
    "manifest",
    "manifest_sha256",
    "model_id",
    "weights",
    "weights_sha256",
    "input_view",
    "threshold",
    "device",
    "threads",
    "warmups",
    "passes",
    "code_files",
}
REQUIRED_CODE_FILES = frozenset(
    {
        Path(__file__).resolve(),
        Path(__file__).with_name("local_glove_detector.py").resolve(),
    }
)


class FrozenInputError(ValueError):
    """A planned image could not be verified at the moment of processing."""


def _hash(data):
    return hashlib.sha256(data).hexdigest()


def _file(path):
    path = Path(path).absolute()
    _no_links(path)
    if not path.is_file():
        raise ValueError("Expected a regular existing file")
    return path


def _json(path):
    def pairs(values):
        result = {}
        for key, value in values:
            if key in result:
                raise ValueError("Duplicate JSON field")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("Nonfinite JSON value")

    data = _file(path).read_bytes()
    return json.loads(data, object_pairs_hook=pairs, parse_constant=constant), _hash(data)


def _write(path, value):
    # Serialize first: malformed responses must not leave a truncated success file.
    payload = json.dumps(value, indent=2, allow_nan=False) + "\n"
    with Path(path).open("x", encoding="utf-8") as stream:
        stream.write(payload)


def _number(value, low, high):
    if type(value) not in (float, int) or not math.isfinite(value) or not low <= value <= high:
        raise ValueError("Invalid bounded numeric value")
    return value


def _integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise ValueError("Invalid bounded integer value")
    return value


def _sha(value):
    if not isinstance(value, str) or re.fullmatch(r"[0-9a-f]{64}", value) is None:
        raise ValueError("Full lowercase SHA256 required")
    return value


def _validate(plan_path, out):
    out = Path(out).absolute()
    _no_links(out)
    if out.exists():
        raise FileExistsError("New benchmark output directory required")
    plan, plan_hash = _json(plan_path)
    if not isinstance(plan, dict) or set(plan) != PLAN_FIELDS or plan["schema"] != PLAN_SCHEMA:
        raise ValueError("Unexpected benchmark plan fields/schema")
    if plan["model_id"] not in SPECS or plan["device"] not in ("cpu", "cuda"):
        raise ValueError("Unsupported explicit model or device")
    if plan["input_view"] not in ("full_frame", "legacy_main_crop"):
        raise ValueError("Unknown input view")
    _number(plan["threshold"], 0, 1)
    for name, maximum in (("threads", 32), ("warmups", 20), ("passes", 3)):
        _integer(plan[name], 1, maximum)
    bindings = plan["code_files"]
    if not isinstance(bindings, list) or not bindings:
        raise ValueError("Code bindings required")
    bound_paths = set()
    for row in bindings:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            raise ValueError("Code binding requires path and sha256")
        path = _file(row["path"]).resolve()
        if path in bound_paths:
            raise ValueError("Duplicate code binding")
        bound_paths.add(path)
        if _hash(path.read_bytes()) != _sha(row["sha256"]):
            raise ValueError("Code changed from frozen plan")
    if not REQUIRED_CODE_FILES <= bound_paths:
        raise ValueError("Actual benchmark runner and detector code bindings required")
    if _hash(_file(plan["weights"]).read_bytes()) != _sha(plan["weights_sha256"]):
        raise ValueError("Checkpoint changed from frozen plan")
    manifest, digest = _json(plan["manifest"])
    if (
        digest != _sha(plan["manifest_sha256"])
        or not isinstance(manifest, dict)
        or manifest.get("schema") != "local_glove_frames_v1"
    ):
        raise ValueError("Frame manifest differs from frozen plan")
    frames = manifest.get("frames")
    if not isinstance(frames, list) or not 1 <= len(frames) <= 86:
        raise ValueError("Planned frame count must be between 1 and 86")
    ids, hashes = set(), set()
    for frame in frames:
        if not isinstance(frame, dict):
            raise ValueError("Invalid frame record")
        oid, digest = frame.get("observation_id"), _sha(frame.get("image_sha256"))
        if not isinstance(oid, str) or not oid.strip() or oid in ids or digest in hashes:
            raise ValueError("Duplicate or invalid frame identity")
        ids.add(oid)
        hashes.add(digest)
        _integer(frame.get("game_pk"), 1, 2**63 - 1)
        _integer(frame.get("width"), 1, 32768)
        _integer(frame.get("height"), 1, 32768)
        with _image(frame) as image:
            crop = frame.get("legacy_main_crop")
            if (
                not isinstance(crop, list)
                or len(crop) != 4
                or any(type(v) is not int for v in crop)
                or not 0 <= crop[0] < crop[2] <= image.width
                or not 0 <= crop[1] < crop[3] <= image.height
            ):
                raise ValueError("Invalid fixed crop bounds")
    return plan, plan_hash, manifest, out


def _image(frame):
    try:
        raw = _file(frame["image_path"]).read_bytes()
        if _hash(raw) != frame["image_sha256"]:
            raise ValueError("Image bytes changed")
        with Image.open(io.BytesIO(raw)) as image:
            if image.format != "JPEG" or list(image.size) != [frame["width"], frame["height"]]:
                raise ValueError("Image format/dimensions differ from manifest")
            return image.convert("RGB")
    except Exception as error:
        raise FrozenInputError(str(error)) from error


def _stats(values):
    if not values:
        return {"n": 0, "median": None, "p95": None, "min": None, "max": None}
    values = sorted(values)
    position = (len(values) - 1) * 0.95
    lower = int(position)
    upper = min(lower + 1, len(values) - 1)
    p95 = values[lower] + (position - lower) * (values[upper] - values[lower])
    return {
        "n": len(values),
        "median": statistics.median(values),
        "p95": p95,
        "min": values[0],
        "max": values[-1],
    }


def _response_fields(response, frame):
    """Validate before marking a response complete; retain available engine provenance."""
    if not isinstance(response, dict):
        raise ValueError("Engine response must be an object")
    snapshot = json.loads(json.dumps(response, allow_nan=False))
    selection, candidate = snapshot.get("selection_status"), snapshot.get("candidate")
    if selection not in ("candidate", "no_candidate", "ambiguous"):
        raise ValueError("Invalid engine selection")
    detections = snapshot.get("detections")
    if not isinstance(detections, list) or any(not isinstance(d, dict) for d in detections):
        raise ValueError("Invalid engine detections")
    point = None
    if selection == "candidate":
        if not isinstance(candidate, dict):
            raise ValueError("Candidate selection requires a candidate")
        point = candidate.get("center_xy")
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError("Candidate requires center_xy")
        x, y = (_number(value, 0, math.inf) for value in point)
        if x >= frame["width"] or y >= frame["height"]:
            raise ValueError("Candidate point outside original frame")
    elif candidate is not None:
        raise ValueError("Non-candidate selection cannot carry a candidate")
    model_seconds = _number(snapshot.get("model_seconds"), 0, math.inf)
    return {
        "status": "completed",
        "selection_status": selection,
        "point": point,
        "detections": detections,
        "engine_response": snapshot,
        "timing": {"model_seconds": model_seconds, "service_seconds": None},
    }


def _frozen_checks(plan_path, plan_hash, plan, manifest):
    """Collect post-run failures rather than raising before partial artifacts are saved."""
    files = [
        ("plan", plan_path, plan_hash),
        ("manifest", plan["manifest"], plan["manifest_sha256"]),
        ("weights", plan["weights"], plan["weights_sha256"]),
        *[("code", row["path"], row["sha256"]) for row in plan["code_files"]],
        *[("image", row["image_path"], row["image_sha256"]) for row in manifest["frames"]],
    ]
    checks = []
    for kind, path, expected in files:
        record = {
            "kind": kind,
            "path": str(path),
            "expected_sha256": expected,
            "actual_sha256": None,
            "status": "unavailable",
            "error": None,
        }
        try:
            record["actual_sha256"] = _hash(_file(path).read_bytes())
            record["status"] = "unchanged" if record["actual_sha256"] == expected else "changed"
        except Exception as error:
            record["error"] = type(error).__name__
        checks.append(record)
    return checks


def _engine_metadata(engine):
    metadata = {}
    for name in ("runtime_versions", "provenance"):
        try:
            value = getattr(engine, name, None)
            if value is not None and not callable(value):
                metadata[name] = json.loads(json.dumps(value, allow_nan=False))
        except Exception as error:
            metadata[f"{name}_unavailable"] = type(error).__name__
    return metadata


def run(plan_path, out, *, engine_factory=LocalGloveDetector, clock=time.perf_counter):
    """Execute a fresh frozen benchmark, persisting failure and first-pass denominators."""
    plan, plan_hash, manifest, out = _validate(plan_path, out)
    plan_bytes = _file(plan_path).read_bytes()
    if _hash(plan_bytes) != plan_hash:
        raise ValueError("Plan changed after preflight")
    out.mkdir(parents=True)
    (out / "attempts").mkdir()
    with (out / "plan.json").open("xb") as stream:
        stream.write(plan_bytes)
    start = clock()
    result = {
        "schema": "local_glove_predictions_v1",
        "manifest_sha256": plan["manifest_sha256"],
        "model_id": plan["model_id"],
        "input_view": plan["input_view"],
        "threshold": plan["threshold"],
        "device": plan["device"],
        "frames": [],
        "development_only": True,
        "catcher_association_verified": False,
    }
    timing_rows, warmups, failure = [], [], None
    integrity_failures = []
    status, engine = "started", None
    startup_seconds = None
    try:
        engine = engine_factory(
            plan["model_id"],
            plan["weights"],
            plan["weights_sha256"],
            device=plan["device"],
            threads=plan["threads"],
        )
        engine.load()
        startup_seconds = clock() - start
        first = manifest["frames"][0]
        crop = first["legacy_main_crop"] if plan["input_view"] == "legacy_main_crop" else None
        with Image.new("RGB", (first["width"], first["height"])) as blank:
            for index in range(plan["warmups"]):
                before = clock()
                response = _response_fields(
                    engine.predict(blank, crop=crop, threshold=plan["threshold"]), first
                )
                warmups.append(
                    {
                        "index": index,
                        "model_seconds": response["timing"]["model_seconds"],
                        "service_seconds": clock() - before,
                        "engine_response": response["engine_response"],
                    }
                )
        for repeat in range(plan["passes"]):
            for index, frame in enumerate(manifest["frames"]):
                before = clock()
                row = {
                    "observation_id": frame["observation_id"],
                    "image_sha256": frame["image_sha256"],
                    "status": "error",
                    "selection_status": None,
                    "point": None,
                    "detections": [],
                    "error": None,
                    "timing": {"model_seconds": None, "service_seconds": None},
                }
                interrupted = False
                try:
                    with _image(frame) as image:
                        crop = (
                            frame["legacy_main_crop"]
                            if plan["input_view"] == "legacy_main_crop"
                            else None
                        )
                        row.update(
                            _response_fields(
                                engine.predict(image, crop=crop, threshold=plan["threshold"]), frame
                            )
                        )
                except (Exception, KeyboardInterrupt) as error:
                    row["error"] = type(error).__name__
                    interrupted = isinstance(error, KeyboardInterrupt)
                    if isinstance(error, FrozenInputError):
                        integrity_failures.append(
                            {
                                "pass": repeat,
                                "index": index,
                                "observation_id": frame["observation_id"],
                                "error": str(error),
                            }
                        )
                # The immutable raw record necessarily has service_seconds=null:
                # this measurement ends only after that record has been written.
                relative = f"attempts/pass_{repeat:02d}_frame_{index:03d}.json"
                path = out / relative
                _write(path, row)
                row["timing"]["service_seconds"] = clock() - before
                digest = _hash(path.read_bytes())
                row["attempt_file"] = {"path": relative, "sha256": digest}
                timing_rows.append(
                    {
                        "pass": repeat,
                        "index": index,
                        "observation_id": frame["observation_id"],
                        "image_sha256": frame["image_sha256"],
                        "status": row["status"],
                        **row["timing"],
                        "attempt_path": relative,
                        "attempt_sha256": digest,
                    }
                )
                if repeat == 0:
                    result["frames"].append(row)
                if interrupted:
                    raise KeyboardInterrupt
        status = (
            "completed_with_errors"
            if any(r["status"] == "error" for r in timing_rows)
            else "completed"
        )
    except (Exception, KeyboardInterrupt) as error:
        status = "interrupted" if isinstance(error, KeyboardInterrupt) else "failed"
        failure = type(error).__name__
    finally:
        checks = _frozen_checks(plan_path, plan_hash, plan, manifest)
        unchanged = not integrity_failures and all(row["status"] == "unchanged" for row in checks)
        execution_status, execution_failure = status, failure
        if not unchanged:
            status, failure = "invalidated", "FrozenInputsChanged"
        first_errors = sum(r["status"] == "error" for r in result["frames"])
        all_errors = sum(r["status"] == "error" for r in timing_rows)
        metadata = _engine_metadata(engine)
        result.update(
            run_status=status,
            frozen_inputs_unchanged=unchanged,
            eligible_for_development_comparison=unchanged,
            engine_metadata=metadata,
            plan_sha256=plan_hash,
        )
        summary = {
            "schema": "local_glove_benchmark_run_v1",
            "status": status,
            "failure": failure,
            "execution_status": execution_status,
            "execution_failure": execution_failure,
            "plan_sha256": plan_hash,
            "manifest_sha256": plan["manifest_sha256"],
            "planned_frames": len(manifest["frames"]),
            "planned_passes": plan["passes"],
            "first_pass_attempted": len(result["frames"]),
            "first_pass_completed": len(result["frames"]) - first_errors,
            "first_pass_errors": first_errors,
            "first_pass_not_attempted": len(manifest["frames"]) - len(result["frames"]),
            "measured_attempts": len(timing_rows),
            "completed_attempts": len(timing_rows) - all_errors,
            "error_attempts": all_errors,
            "startup_seconds": startup_seconds,
            "total_seconds": clock() - start,
            "warmups": warmups,
            "timings": timing_rows,
            "model_seconds": _stats(
                [r["model_seconds"] for r in timing_rows if r["model_seconds"] is not None]
            ),
            "service_seconds": _stats([r["service_seconds"] for r in timing_rows]),
            "frozen_inputs_unchanged": unchanged,
            "frozen_input_checks": checks,
            "input_integrity_failures": integrity_failures,
            "engine_metadata": metadata,
            "clock": vars(time.get_clock_info("perf_counter")),
            "python": platform.python_version(),
            "platform": platform.system(),
            "scope": "Persistent model, batch1. Service includes read/hash/decode/predict/select/attempt write; hash binding and final logs excluded. Startup excludes interpreter/imports and plan/input preflight. Fixed black-image warmups; repeats are latency measurements, not extra independent labeled frames.",
            "attempt_timing_contract": {
                "raw_attempt_service_seconds": None,
                "reason": "Measurement ends after the immutable raw-attempt write.",
                "measured_values": "timings and first-pass predictions",
                "binding": "relative attempt path and SHA256 of the exact raw-attempt bytes",
            },
            "live_availability_verified": False,
        }
        _write(out / "predictions.json", result)
        summary["predictions_sha256"] = _hash((out / "predictions.json").read_bytes())
        _write(out / "benchmark.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    summary = run(args.plan, args.out)
    print(
        json.dumps(
            {
                key: summary[key]
                for key in (
                    "status",
                    "planned_frames",
                    "first_pass_attempted",
                    "measured_attempts",
                    "total_seconds",
                )
            },
            indent=2,
        )
    )
    return 0 if summary["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

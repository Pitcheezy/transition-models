"""Audit local glove replay evidence without model calls or accuracy claims.

The original video/checkpoint is not required. Saved request images, exact config
snapshots, sidecars and loop receipts remain required for artifact revalidation.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
import uuid
from pathlib import Path

from intent import observation_report as outer
from intent import observation_session as session
from intent.local_glove_detector import SPECS
from intent.local_glove_observer import CONFIG_FIELDS, CONFIG_SCHEMA, SIDECAR_SCHEMA, _prediction
from intent.replay import _no_links

SCHEMA = "local_glove_observer_report_v1"
_STAGES = (
    "input_validation",
    "model_initialization",
    "inference",
    "response_validation_serialization",
)
_FALSE_FLAGS = (
    "human_label",
    "independent_validation",
    "catcher_association_verified",
    "full_pa_verified",
    "live_availability_verified",
)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _inventory(run):
    """Bind the saved run, including private logs, without exporting their contents."""
    _no_links(run)
    result = {}
    for path in sorted(run.rglob("*")):
        _no_links(path)
        if path.is_file():
            result[path.relative_to(run).as_posix()] = _sha(path.read_bytes())
        elif not path.is_dir():
            raise ValueError("Expected regular run artifacts")
    return result


def _digest(value):
    if (
        not isinstance(value, str)
        or len(value) != 64
        or any(c not in "0123456789abcdef" for c in value)
    ):
        raise ValueError("Expected lowercase SHA256")
    return value


def _number(value):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError("Expected finite nonnegative duration/value")
    return value


def _configuration(config):
    """Validate saved configuration without opening an original checkpoint/path."""
    if not isinstance(config, dict) or set(config) != CONFIG_FIELDS:
        raise ValueError("Unexpected saved configuration fields")
    if config["schema"] != CONFIG_SCHEMA or config["model_id"] not in SPECS:
        raise ValueError("Unexpected saved model configuration")
    if (
        config["device"] not in ("cpu", "cuda")
        or type(config["threads"]) is not int
        or not 1 <= config["threads"] <= 32
        or config["input_view"] != "full_frame"
        or config["crop_xyxy"] is not None
        or _number(config["threshold"]) > 1
        or not isinstance(config["weights"], str)
        or not config["weights"]
        or not _digest(config["weights_sha256"]).startswith(SPECS[config["model_id"]].sha256_prefix)
    ):
        raise ValueError("Unsupported saved configuration")
    return {
        key: config[key]
        for key in ("model_id", "weights_sha256", "device", "threads", "threshold", "input_view")
    }


def _frozen_config(manifest):
    argv = manifest.get("observer_argv")
    if not isinstance(argv, list) or argv.count("--config") != 1:
        raise ValueError("Frozen observer command must declare one --config argument")
    position = argv.index("--config") + 1
    if position >= len(argv) or not isinstance(argv[position], str):
        raise ValueError("Frozen observer config argument is missing")
    config_path = argv[position]
    bindings = manifest.get("input_code_bindings")
    if not isinstance(bindings, list):
        raise ValueError("Missing frozen input bindings")
    matches = [
        item for item in bindings if isinstance(item, dict) and item.get("path") == config_path
    ]
    if len(matches) != 1:
        raise ValueError("Observer config must have one frozen byte binding")
    item = matches[0]
    outer._int(item["bytes"])
    _digest(item["sha256"])
    return item


def _inner_timing(sidecar):
    timing = sidecar.get("timing")
    if not isinstance(timing, dict) or timing.get("clock") != "perf_counter_ns":
        raise ValueError("Expected adapter perf_counter_ns timing")
    begin = outer._int(timing["started_perf_counter_ns"])
    end = outer._int(timing["finished_perf_counter_ns"])
    if end < begin:
        raise ValueError("Adapter timing moved backwards")
    outer._same_number(timing["elapsed_seconds"], (end - begin) / 1e9)
    stages = timing.get("stages")
    if not isinstance(stages, dict) or not stages or set(stages) - set(_STAGES):
        raise ValueError("Unexpected adapter timing stages")
    previous, failed, values, statuses = begin, False, {}, {}
    for name in _STAGES:
        if name not in stages:
            if any(later in stages for later in _STAGES[_STAGES.index(name) + 1 :]):
                raise ValueError("Adapter timing stages must form a prefix")
            break
        stage = stages[name]
        if not isinstance(stage, dict) or stage.get("status") not in ("completed", "failed"):
            raise ValueError("Unfinished adapter timing stage")
        start = outer._int(stage["started_perf_counter_ns"])
        finish = outer._int(stage["finished_perf_counter_ns"])
        if failed or start != previous or not start <= finish <= end:
            raise ValueError("Adapter stage sequence is inconsistent")
        outer._same_number(stage["elapsed_seconds"], (finish - start) / 1e9)
        values[name] = (finish - start) / 1e9
        statuses[name] = stage["status"]
        previous, failed = finish, stage["status"] == "failed"
    accepted = sidecar["status"] == "accepted"
    if (
        previous != end
        or (accepted and (failed or len(stages) != len(_STAGES)))
        or (not accepted and not failed)
    ):
        raise ValueError("Adapter timing outcome disagrees with sidecar status")
    return {
        "total_seconds": (end - begin) / 1e9,
        "stage_seconds": values,
        "stage_status": statuses,
        "clock": "perf_counter_ns",
    }


def _bound_request(directory, row, evidence):
    request, request_hash = outer._read(directory / "request/request.json")
    identity = request.get("observation_id")
    if not isinstance(identity, str) or uuid.UUID(identity).hex != identity:
        raise ValueError("Invalid observation identity")
    if request.get("schema") != session.MAPPED_REQUEST_SCHEMA:
        raise ValueError("Expected a mapped loop observation request")
    if (
        request.get("prompt") != session.PROMPT
        or request.get("response_schema") != session.RESPONSE_FIELDS
    ):
        raise ValueError("Unexpected observation prompt/response contract")
    if any(type(request.get(key)) is not int or request[key] <= 0 for key in ("width", "height")):
        raise ValueError("Invalid request image dimensions")
    image_hash = _digest(request.get("image_sha256"))
    if evidence["image"] != image_hash:
        raise ValueError("Sidecar/request image byte binding mismatch")
    saved_session, _ = outer._read(directory / "session.json")
    if (
        saved_session.get("schema") != session.MAPPED_SESSION_SCHEMA
        or saved_session.get("request_sha256") != request_hash
        or saved_session.get("image_sha256") != image_hash
    ):
        raise ValueError("Session/request image binding mismatch")
    cutoff = outer._fraction(row["cutoff_seconds_exact"])
    actual = outer._fraction(request["source_time_seconds_exact"])
    if (
        "actual_source_seconds_exact" in row
        and outer._fraction(row["actual_source_seconds_exact"]) != actual
    ):
        raise ValueError("Request differs from recorded actual source time")
    if (
        request.get("source_time_basis") != "decoded_pts"
        or outer._fraction(request["requested_cutoff_seconds_exact"]) != cutoff
        or outer._fraction(request["source_time_seconds_exact"]) != actual
        or not 0 <= actual <= cutoff
    ):
        raise ValueError("Sidecar request source/cutoff mismatch")
    outer._same_number(request["source_time_seconds"], float(actual))
    return request, request_hash


def _artifacts(run, index, row, binding):
    directory = run / "outputs" / f"cv_observation_{index:03d}"
    request_dir = directory / "request"
    sidecar_path = request_dir / "local_detector_result.json"
    evidence = {}
    for name, path in {
        "session": directory / "session.json",
        "request": request_dir / "request.json",
        "image": request_dir / "image.jpg",
        "response": request_dir / "response.json",
        "result": directory / "result.json",
        "sidecar": sidecar_path,
        "config_snapshot": request_dir / "local_detector_config.json",
    }.items():
        evidence[name] = _sha(path.read_bytes()) if path.is_file() else None
    if not sidecar_path.exists():
        if row["status"] == "accepted":
            raise ValueError("Accepted local observation lacks a sidecar")
        identity = None
        if evidence["request"] is not None:
            request, _ = _bound_request(directory, row, evidence)
            identity = request["observation_id"]
        elif row.get("observer_dispatch") is not None:
            raise ValueError("Dispatched attempt lacks its saved request")
        if evidence["config_snapshot"] is not None:
            raw = (request_dir / "local_detector_config.json").read_bytes()
            if binding["sha256"] != _sha(raw) or binding["bytes"] != len(raw):
                raise ValueError("Unpublished config snapshot differs from frozen input")
        return {
            "observation_id": identity,
            "evidence_sha256": evidence,
            "sidecar_status": None,
            "response_binding": "unverified_error_artifact"
            if evidence["response"]
            else "not_published",
        }, None
    sidecar, _ = outer._read(sidecar_path)
    if sidecar.get("schema") != SIDECAR_SCHEMA or sidecar.get("status") not in (
        "accepted",
        "failed",
    ):
        raise ValueError("Unexpected local observer sidecar")
    if any(sidecar.get(key) is not False for key in _FALSE_FLAGS):
        raise ValueError("Unsupported verified-mitt/human/live claim")
    if sidecar.get("config_snapshot_file") != "local_detector_config.json":
        raise ValueError("Expected fixed raw config snapshot filename")
    request, request_hash = _bound_request(directory, row, evidence)
    identity = request["observation_id"]
    if sidecar.get("image_sha256") != request["image_sha256"]:
        raise ValueError("Sidecar image SHA256 mismatch")
    if sidecar.get("request_sha256") != request_hash or sidecar.get("observation_id") not in (
        identity,
        None if sidecar["status"] == "failed" else identity,
    ):
        raise ValueError("Sidecar request hash/identity mismatch")
    raw_config = (request_dir / "local_detector_config.json").read_bytes()
    if sidecar.get("config_sha256") != _sha(raw_config) or (
        binding["sha256"] != _sha(raw_config) or binding["bytes"] != len(raw_config)
    ):
        raise ValueError("Sidecar/config snapshot/frozen byte binding mismatch")
    config, _ = outer._read(request_dir / "local_detector_config.json")
    public_config = _configuration(config)
    if sidecar.get("configuration") != config and not (
        sidecar["status"] == "failed" and sidecar.get("configuration") is None
    ):
        raise ValueError("Sidecar configuration differs from saved config bytes")
    errors = sidecar.get("errors")
    if not isinstance(errors, list) or any(
        not isinstance(error, dict)
        or not isinstance(error.get("type"), str)
        or not isinstance(error.get("message"), str)
        for error in errors
    ):
        raise ValueError("Invalid private adapter error evidence")
    if bool(errors) != (sidecar["status"] == "failed"):
        raise ValueError("Adapter status/error evidence mismatch")
    timing = _inner_timing(sidecar)
    selection, engine_timing = None, None
    if sidecar["status"] == "accepted":
        prediction = _prediction(sidecar.get("engine_response"), request, config)
        selection = prediction["selection_status"]
        if (
            sidecar.get("selection_status") != selection
            or sidecar.get("candidate") != prediction["candidate"]
        ):
            raise ValueError("Sidecar selection differs from its validated engine response")
        engine_timing = {
            key: prediction[key]
            for key in (
                "decode_seconds",
                "preprocess_seconds",
                "model_seconds",
                "postprocess_seconds",
            )
        }
        _digest(sidecar.get("response_sha256"))
    elif row["status"] == "accepted":
        raise ValueError("Accepted loop observation has failed adapter evidence")
    elif sidecar.get("response_sha256") is not None:
        raise ValueError("Failed adapter cannot claim a published response SHA256")
    if evidence["response"] is not None:
        response, response_hash = outer._read(request_dir / "response.json")
        session._validate_response(response, request)
        expected = "unavailable" if selection == "no_candidate" else "unknown"
        if (
            sidecar["status"] != "accepted"
            or sidecar.get("response_sha256") != response_hash
            or response["status"] != expected
            or response["mitt"] is not None
            or response["visibility"] != "unknown"
            or response["pose"] != "unknown"
        ):
            raise ValueError("Local response hash/selection/unverified-mitt contract mismatch")
    elif row["status"] == "accepted":
        raise ValueError("Accepted observation lacks a saved response")
    return {
        "observation_id": identity,
        "evidence_sha256": evidence,
        "sidecar_status": sidecar["status"],
        "response_binding": "verified" if evidence["response"] is not None else "not_published",
        "adapter_timing": timing,
        "engine_timing_seconds": engine_timing,
        "selection_status": selection if row["status"] == "accepted" else None,
    }, public_config


def _summary(rows, accessor):
    values = [value for row in rows if (value := accessor(row)) is not None]
    if not values:
        return {"n": 0, "min": None, "median": None, "max": None}
    return {
        "n": len(values),
        "min": min(values),
        "median": statistics.median(values),
        "max": max(values),
    }


def build_report(run_dir):
    """Validate immutable saved replay evidence and report every planned cutoff."""
    run = Path(run_dir)
    before = _inventory(run)
    base = outer.build_report(run)
    manifest, _ = outer._read(run / "run_manifest.json")
    binding = _frozen_config(manifest)
    rows, configurations, identities = [], [], set()
    counts = dict.fromkeys(
        (
            "attempted",
            "accepted",
            "candidate",
            "ambiguous",
            "no_candidate",
            "error",
            "not_attempted",
            "verified_mitt",
            "publication_within_5s",
            "candidate_publication_within_5s",
        ),
        0,
    )
    for index, cutoff in enumerate(manifest["plan"]["cutoffs"]):
        row = {
            "index": index,
            "cutoff_seconds_exact": str(outer._fraction(cutoff)),
            "status": "not_attempted",
            "selection_status": None,
            "observation_id": None,
            "publication_seconds": None,
            "dispatch_seconds": None,
            "outer_phase_seconds": {},
            "adapter_timing": None,
            "engine_timing_seconds": None,
        }
        if index < len(base["observations"]):
            recorded = base["observations"][index]
            attempt, attempt_hash = outer._read(run / "attempts" / f"{index:03d}.json")
            details, config = _artifacts(run, index, attempt, binding)
            row.update(details)
            if config is not None and config not in configurations:
                configurations.append(config)
            identity = row["observation_id"]
            if identity is not None:
                if identity in identities:
                    raise ValueError("Duplicate observation identity across planned cutoffs")
                identities.add(identity)
            row.update(
                status=details.get("selection_status")
                if attempt["status"] == "accepted"
                else "error",
                attempt_sha256=attempt_hash,
                observation_status=recorded["observation_status"],
                publication_seconds=recorded["accepted_latency_from_schedule_seconds"],
                dispatch_seconds=recorded["dispatch_lateness_seconds"],
                outer_phase_seconds={
                    k: v for k, v in recorded["phase_seconds"].items() if k in outer._LOOP_PHASES
                },
            )
            counts["attempted"] += 1
            if attempt["status"] == "accepted":
                counts["accepted"] += 1
                on_time = row["publication_seconds"] <= outer.THRESHOLD_SECONDS
                counts["publication_within_5s"] += int(on_time)
                counts["candidate_publication_within_5s"] += int(
                    on_time and row["status"] == "candidate"
                )
        counts[row["status"]] += 1
        rows.append(row)
    if len(configurations) > 1:
        raise ValueError("A fixed observer run cannot mix configurations")
    if before != _inventory(run):
        raise ValueError("Run artifacts changed while building the report")
    return {
        "schema": SCHEMA,
        "run_status": base["run_status"],
        "planned": base["planned"],
        "counts": counts,
        "rates_per_planned": {key: value / base["planned"] for key, value in counts.items()},
        "configuration": configurations[0] if configurations else None,
        "latency_threshold_seconds": outer.THRESHOLD_SECONDS,
        "development_only": True,
        "accuracy_evaluated": False,
        **dict.fromkeys(_FALSE_FLAGS, False),
        "study_scope": "Existing ten-cutoff development diagnostic; separate from the 86-frame comparison. No new independent or physical target claims.",
        "count_notice": "Candidate means one generic glove-box candidate, not a verified catcher mitt. Ambiguous, no candidate, errors and not attempted retain the full planned denominator.",
        "timing_notice": "Outer publication is schedule-to-validated-publication using loop monotonic_ns; <=5 seconds is a local replay target, not live availability. Inner adapter stages use perf_counter_ns durations. Their absolute timestamps are never subtracted from outer timestamps; nested durations must not be added twice. Adapter total excludes final artifact writes; model time excludes load and outer extraction/process/publication.",
        "integrity_notice": "Saved file consistency is checked, not independently attested execution. Raw loop images and config copies are required for revalidation; original video and checkpoint files are not required. Public output contains only allowlisted fields and hashes.",
        "evidence_sha256": {
            **base["evidence_sha256"],
            "events": before.get("events.jsonl"),
            "saved_artifact_inventory": _sha(json.dumps(before, sort_keys=True).encode()),
            "frozen_config": binding["sha256"],
        },
        "saved_artifact_count": len(before),
        "observations": rows,
        "timing_summary_seconds": {
            "outer_publication": _summary(rows, lambda row: row["publication_seconds"]),
            "adapter_total": _summary(
                rows, lambda row: (row["adapter_timing"] or {}).get("total_seconds")
            ),
            "model_initialization": _summary(
                rows,
                lambda row: (
                    (row["adapter_timing"] or {})
                    .get("stage_seconds", {})
                    .get("model_initialization")
                ),
            ),
            "inference_stage": _summary(
                rows,
                lambda row: (row["adapter_timing"] or {}).get("stage_seconds", {}).get("inference"),
            ),
            "engine_model": _summary(
                rows, lambda row: (row["engine_timing_seconds"] or {}).get("model_seconds")
            ),
        },
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    _no_links(args.out)
    if args.out.exists():
        raise FileExistsError("Report output must be a fresh file")
    try:
        report = build_report(args.run)
    except (KeyError, TypeError, OSError, ValueError) as exc:
        parser.error(f"Invalid local glove observation run: {exc}")
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

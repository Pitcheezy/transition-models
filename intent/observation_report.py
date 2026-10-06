"""Audit local observation-loop outcomes and delays without scoring model accuracy."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import statistics
from fractions import Fraction
from pathlib import Path

from intent import observation_loop, observation_session

SCHEMA = "intent_observation_loop_report_v1"
THRESHOLD_SECONDS = 5


def _pairs(pairs):
    result = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"Duplicate JSON key: {key}")
        result[key] = value
    return result


def _read(path):
    if path.is_symlink() or not path.is_file():
        raise ValueError(f"Expected regular artifact: {path.name}")
    raw = path.read_bytes()
    value = json.loads(raw, object_pairs_hook=_pairs, parse_constant=_bad_constant)
    if not isinstance(value, dict):
        raise ValueError(f"Expected JSON object: {path.name}")
    return value, hashlib.sha256(raw).hexdigest()


def _bad_constant(value):
    raise ValueError(f"Nonfinite JSON value: {value}")


def _int(value):
    if type(value) is not int or value < 0:
        raise ValueError("Expected nonnegative integer clock/index")
    return value


def _fraction(value):
    if type(value) not in (str, int):
        raise ValueError("Expected exact rational string/integer")
    try:
        return Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("Invalid rational time") from exc


def _same_number(value, expected):
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError("Expected finite numeric duration")
    if not math.isclose(value, expected, rel_tol=0, abs_tol=1e-9):
        raise ValueError("Recorded duration disagrees with monotonic clock")


def _accepted(run, row, cutoff, accepted_ns):
    directory = run / "outputs" / f"cv_observation_{row['index']:03d}"
    result, result_hash = _read(directory / "result.json")
    request, request_hash = _read(directory / "request/request.json")
    response, response_hash = _read(directory / "request/response.json")
    session, session_hash = _read(directory / "session.json")
    if (
        result.get("schema") != "intent_visual_observation_result_v2"
        or request.get("schema") != observation_session.MAPPED_REQUEST_SCHEMA
        or result.get("request_sha256") != request_hash
        or result.get("session_sha256") != session_hash
        or result.get("raw_response_sha256") != response_hash
        or result.get("raw_response") != response
        or session.get("request_sha256") != request_hash
        or result.get("human_label") is not False
        or result.get("independent_validation") is not False
        or result.get("live_availability_verified") is not False
        or response.get("status") != row["observation_status"]
    ):
        raise ValueError("Accepted result/request/session/response binding mismatch")
    image = directory / "request/image.jpg"
    if image.is_symlink() or not image.is_file():
        raise ValueError("Missing regular request image")
    if hashlib.sha256(image.read_bytes()).hexdigest() != request["image_sha256"]:
        raise ValueError("Request image hash mismatch")
    observation_session._validate_response(response, request)
    actual = _fraction(row["actual_source_seconds_exact"])
    for document in (request, result):
        if (
            _fraction(document["requested_cutoff_seconds_exact"]) != cutoff
            or _fraction(document["source_time_seconds_exact"]) != actual
            or document.get("source_time_basis") != "decoded_pts"
        ):
            raise ValueError("Accepted exact-time binding mismatch")
    if not 0 <= actual <= cutoff:
        raise ValueError("Accepted frame exceeds causal cutoff")
    finished = _int(result["finished_monotonic_ns"])
    if not row["observer_exit"]["monotonic_ns"] <= finished <= accepted_ns:
        raise ValueError("Result validation is outside exit/publication interval")
    return result_hash


_EXTRA_STAMPS = (
    "input_bindings_verified",
    "frame_extracted",
    "request_ready",
    "output_bindings_verified",
)
_LOOP_PHASES = {
    "input_binding_verification": ("preparation_started", "input_bindings_verified"),
    "frame_extraction": ("input_bindings_verified", "frame_extracted"),
    "request_preparation": ("frame_extracted", "request_ready"),
    "dispatch_overhead": ("request_ready", "observer_dispatch"),
    "observer_process": ("observer_dispatch", "observer_exit"),
    "output_binding_verification": ("observer_exit", "output_bindings_verified"),
    "response_validation_publication": ("output_bindings_verified", "response_accepted"),
}
_PROVIDER_STAGES = ("input_validation", "auth_status", "cli_call", "parse_validate_write")


def _loop_phases(row, stamps):
    version = row.get("phase_timing_version")
    if version is None:
        if any(name in stamps for name in _EXTRA_STAMPS):
            raise ValueError("Extra phase timestamps require a timing version")
        return {}
    if type(version) is not int or version != 1:
        raise ValueError("Unsupported phase timing version")
    if row["status"] == "accepted" and any(name not in stamps for name in _EXTRA_STAMPS):
        raise ValueError("Accepted instrumented attempt lacks phase timestamps")
    if "request_ready" in stamps and stamps.get("frame_ready") != stamps["request_ready"]:
        raise ValueError("Request-ready alias disagrees with legacy frame-ready clock")
    values = {}
    for name, (begin, end) in _LOOP_PHASES.items():
        if end not in stamps:
            continue
        if begin not in stamps:
            raise ValueError("Completed phase lacks its starting timestamp")
        values[name] = (stamps[end] - stamps[begin]) / 1e9
    return values


def _provider_phases(run, row, stamps):
    path = run / "outputs" / f"cv_observation_{row['index']:03d}" / "request/provider_metadata.json"
    if not path.exists():
        return {}, None, "metadata_absent"
    metadata, digest = _read(path)
    timing = metadata.get("timing_v1")
    if timing is None:
        return {}, digest, "legacy_metadata_without_timing"
    if (
        not isinstance(timing, dict)
        or timing.get("clock") != "monotonic_ns"
        or not isinstance(timing.get("scope"), str)
        or not timing["scope"].strip()
        or not isinstance(timing.get("stages"), dict)
        or set(timing["stages"]) != {*_PROVIDER_STAGES, "total"}
    ):
        raise ValueError("Malformed provider phase timing")

    def interval(stage):
        if not isinstance(stage, dict) or stage.get("status") not in ("completed", "failed"):
            raise ValueError("Unfinished or invalid provider timing stage")
        begin = _int(stage["started_monotonic_ns"])
        end = _int(stage["finished_monotonic_ns"])
        if end < begin:
            raise ValueError("Provider timing moved backwards")
        _same_number(stage["elapsed_seconds"], (end - begin) / 1e9)
        return begin, end

    if "observer_exit" not in stamps and row["status"] == "error":
        # Interrupted processes may save metadata without a captured outer exit.
        # Keep the error and file hash, but do not invent a bounding timestamp.
        return {}, digest, "unavailable_without_observer_exit"
    total_start, total_end = interval(timing["stages"]["total"])
    provider_accepted = metadata.get("status") == "accepted"
    if metadata.get("status") not in ("accepted", "failed") or (
        timing["stages"]["total"]["status"] != ("completed" if provider_accepted else "failed")
    ):
        raise ValueError("Provider outcome disagrees with its total timing")
    if (
        "observer_dispatch" not in stamps
        or "observer_exit" not in stamps
        or not stamps["observer_dispatch"] <= total_start <= total_end <= stamps["observer_exit"]
    ):
        raise ValueError("Provider timing outside measured observer process")
    if row["status"] == "accepted" and (
        metadata.get("status") != "accepted" or timing["stages"]["total"]["status"] != "completed"
    ):
        raise ValueError("Accepted response disagrees with provider timing outcome")
    values = {
        "provider.total": (total_end - total_start) / 1e9,
        "process_start_to_adapter": (total_start - stamps["observer_dispatch"]) / 1e9,
        "process_exit_tail": (stamps["observer_exit"] - total_end) / 1e9,
    }
    previous = total_start
    missing_or_failed = False
    for name in _PROVIDER_STAGES:
        stage = timing["stages"][name]
        if stage is None:
            missing_or_failed = True
            if provider_accepted:
                raise ValueError("Accepted provider omitted a timing stage")
            continue
        begin, end = interval(stage)
        if missing_or_failed or not previous <= begin <= end <= total_end:
            raise ValueError("Provider timing sequence is inconsistent")
        values[f"provider.{name}"] = (end - begin) / 1e9
        previous = end
        missing_or_failed = stage["status"] == "failed"
        if missing_or_failed and provider_accepted:
            raise ValueError("Accepted provider has a failed timing stage")
    return values, digest, "validated_with_outer_bounds"


def _phase_summaries(rows):
    names = sorted({name for row in rows for name in row["phase_seconds"]})
    summary = {}
    for name in names:
        values = [row["phase_seconds"][name] for row in rows if name in row["phase_seconds"]]
        summary[name] = {
            "n": len(values),
            "min": min(values),
            "median": statistics.median(values),
            "max": max(values),
        }
    return summary


def build_report(run_dir):
    """Validate saved evidence, keeping every planned observation in the denominator."""
    run = Path(run_dir)
    manifest, manifest_hash = _read(run / "run_manifest.json")
    plan, plan_hash = _read(run / "plan.json")
    if (
        manifest.get("schema") != observation_loop.RUN_SCHEMA
        or plan.get("schema") != observation_loop.PLAN_SCHEMA
        or set(plan) != observation_loop._FIELDS
        or manifest.get("plan") != plan
        or manifest.get("full_pa_verified") is not False
        or manifest.get("live_availability_verified") is not False
    ):
        raise ValueError("Unexpected run/plan schema or unsupported verification claim")
    values = plan["cutoffs"]
    if not isinstance(values, list) or not 1 <= len(values) <= 50:
        raise ValueError("Invalid planned denominator")
    cutoffs = [_fraction(value) for value in values]
    if cutoffs[0] < 0 or any(a >= b for a, b in zip(cutoffs, cutoffs[1:], strict=False)):
        raise ValueError("Cutoffs must be nonnegative and strictly ascending")
    start = _int(manifest["started_monotonic_ns"])
    utc_start = _int(manifest["started_utc_ns"])
    files = sorted((run / "attempts").iterdir())
    if len(files) > len(cutoffs):
        raise ValueError("More attempts than planned observations")
    counts = dict.fromkeys(
        (
            "attempted",
            "accepted",
            "marked",
            "unavailable",
            "unknown",
            "errors",
            "dispatched",
            "dispatch_within_5s",
            "publication_within_5s",
            "both_within_5s",
        ),
        0,
    )
    rows, previous_finish = [], start
    for index, path in enumerate(files):
        if path.name != f"{index:03d}.json":
            raise ValueError("Attempts must form a consecutive prefix with canonical filenames")
        row, row_hash = _read(path)
        cutoff = cutoffs[index]
        offset = cutoff - cutoffs[0]
        delay_ns = math.ceil(offset * 1_000_000_000)
        scheduled = start + delay_ns
        if (
            type(row["index"]) is not int
            or row["index"] != index
            or _fraction(row["cutoff_seconds_exact"]) != cutoff
            or _fraction(row["scheduled_offset_seconds_exact"]) != offset
            or _int(row["scheduled_input_monotonic_ns"]) != scheduled
            or _int(row["scheduled_input_utc_ns"]) != utc_start + delay_ns
        ):
            raise ValueError("Attempt disagrees with fixed plan schedule")
        stamps = {}
        last = previous_finish
        for key in (
            "preparation_started",
            "input_bindings_verified",
            "frame_extracted",
            "frame_ready",
            "request_ready",
            "observer_dispatch",
            "observer_exit",
            "output_bindings_verified",
            "response_accepted",
            "attempt_finished",
        ):
            value = row.get(key)
            if value is None:
                continue
            ns = _int(value["monotonic_ns"])
            _int(value["utc_ns"])
            _same_number(value["elapsed_seconds"], (ns - start) / 1e9)
            if ns < last or (key == "preparation_started" and ns < scheduled):
                raise ValueError("Attempt clock sequence moved backwards")
            stamps[key], last = ns, ns
        if "attempt_finished" not in stamps:
            raise ValueError("Persisted attempt lacks finish timestamp")
        previous_finish = stamps["attempt_finished"]
        errors = row["errors"]
        if not isinstance(errors, list) or any(not isinstance(e, str) or not e for e in errors):
            raise ValueError("Invalid attempt errors")
        counts["attempted"] += 1
        dispatch_delay = publication_delay = None
        if "observer_dispatch" in stamps:
            if "preparation_started" not in stamps or "frame_ready" not in stamps:
                raise ValueError("Dispatch lacks preparation/frame timestamps")
            dispatch_delay = (stamps["observer_dispatch"] - scheduled) / 1e9
            _same_number(row["dispatch_lateness_seconds"], dispatch_delay)
            counts["dispatched"] += 1
            counts["dispatch_within_5s"] += dispatch_delay <= THRESHOLD_SECONDS
        result_hash = None
        if row["status"] == "accepted":
            if (
                errors
                or any(
                    key not in stamps
                    for key in ("observer_dispatch", "observer_exit", "response_accepted")
                )
                or type(row["observer_exit_code"]) is not int
                or row["observer_exit_code"] != 0
            ):
                raise ValueError("Accepted attempt lacks successful process/publication evidence")
            publication_delay = (stamps["response_accepted"] - scheduled) / 1e9
            _same_number(row["accepted_latency_from_schedule_seconds"], publication_delay)
            result_hash = _accepted(run, row, cutoff, stamps["response_accepted"])
            counts["accepted"] += 1
            counts[row["observation_status"]] += 1
            counts["publication_within_5s"] += publication_delay <= THRESHOLD_SECONDS
            counts["both_within_5s"] += (
                publication_delay <= THRESHOLD_SECONDS and dispatch_delay <= THRESHOLD_SECONDS
            )
        elif row["status"] == "error":
            if not errors or row["observation_status"] is not None or "response_accepted" in stamps:
                raise ValueError("Error must remain separate from accepted observation/abstention")
            counts["errors"] += 1
        else:
            raise ValueError("Unknown attempt status")
        phases = _loop_phases(row, stamps)
        provider_phases, provider_hash, provider_timing_status = _provider_phases(run, row, stamps)
        phases.update(provider_phases)
        rows.append(
            {
                "index": index,
                "cutoff_seconds_exact": str(cutoff),
                "status": row["status"],
                "observation_status": row["observation_status"],
                "dispatch_lateness_seconds": dispatch_delay,
                "accepted_latency_from_schedule_seconds": publication_delay,
                "attempt_sha256": row_hash,
                "result_sha256": result_hash,
                "provider_metadata_sha256": provider_hash,
                "provider_timing_status": provider_timing_status,
                "phase_seconds": phases,
            }
        )
    # A killed process may have dispatched work without reaching its finally block.
    # Such work must not be silently called "not attempted".
    events_path = run / "events.jsonl"
    if events_path.exists():
        if events_path.is_symlink() or not events_path.is_file():
            raise ValueError("Expected a regular event log")
        for line in events_path.read_text(encoding="utf-8").splitlines():
            event = json.loads(line, object_pairs_hook=_pairs, parse_constant=_bad_constant)
            if not isinstance(event, dict) or _int(event["index"]) >= counts["attempted"]:
                raise ValueError("Unpersisted attempt event; incomplete evidence cannot be scored")
    for child, prefix in (("outputs", "cv_observation_"), ("frames", "frame_")):
        directory = run / child
        if directory.exists():
            expected = {f"{prefix}{i:03d}" for i in range(counts["attempted"])}
            if any(path.name not in expected for path in directory.iterdir()):
                raise ValueError("Orphan attempt artifacts; incomplete evidence cannot be scored")
    planned = len(cutoffs)
    state, summary_hash = "not_finalized", None
    summary_path = run / "summary.json"
    if summary_path.exists():
        summary, summary_hash = _read(summary_path)
        if summary.get("schema") != observation_loop.RUN_SCHEMA or any(
            summary.get(key) != value
            for key, value in {
                "planned": planned,
                "attempted": counts["attempted"],
                "accepted": counts["accepted"],
                "errors": counts["errors"],
                "full_pa_verified": False,
                "live_availability_verified": False,
            }.items()
        ):
            raise ValueError("Summary disagrees with validated attempts")
        if any(
            type(summary[key]) is not int for key in ("planned", "attempted", "accepted", "errors")
        ):
            raise ValueError("Summary counts must be integers")
        state = summary.get("status")
        if state not in ("completed", "completed_with_errors", "interrupted"):
            raise ValueError("Unknown finalized run status")
        if state != "interrupted" and counts["attempted"] != planned:
            raise ValueError("Finalized complete run has missing attempts")
        if (state == "completed" and counts["errors"]) or (
            state == "completed_with_errors" and not counts["errors"]
        ):
            raise ValueError("Finalized status disagrees with errors")
    counts["not_attempted"] = planned - counts["attempted"]
    return {
        "schema": SCHEMA,
        "run_status": state,
        "planned": planned,
        "counts": counts,
        "rates_per_planned": {key: value / planned for key, value in counts.items()},
        "latency_threshold_seconds": THRESHOLD_SECONDS,
        "threshold_scope": "Development schedule-to-dispatch/publication target, not live SLA.",
        "full_pa_verified": False,
        "live_availability_verified": False,
        "accuracy_evaluated": False,
        "notice": "Local replay timing includes extraction, process and validation. Marked means "
        "an accepted point, not a correct point. Unavailable/unknown are model abstentions; "
        "errors and not-attempted observations remain separate. Saved-artifact consistency "
        "is checked; original video provenance and model execution are not re-attested.",
        "evidence_sha256": {
            "manifest": manifest_hash,
            "saved_plan": plan_hash,
            "summary": summary_hash,
        },
        "observations": rows,
        "phase_summary_seconds": _phase_summaries(rows),
        "phase_notice": "Optional measured phases only; omitted stages are not zero. Provider "
        "CLI time includes network/server work, not pure model inference. Provider timings "
        "are nested within observer_process and must not be added to outer phases twice. "
        "process_start_to_adapter includes launch, imports and argument setup; "
        "it is not interpreter startup alone.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = build_report(args.run_dir)
    except (KeyError, TypeError, OSError, ValueError) as exc:
        parser.error(f"Invalid observation run: {exc}")
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

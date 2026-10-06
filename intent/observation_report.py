"""Audit local observation-loop outcomes and delays without scoring model accuracy."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
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
            "frame_ready",
            "observer_dispatch",
            "observer_exit",
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

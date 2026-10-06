"""Saved-artifact audit tests; no observer or video decoder is invoked."""

import hashlib
import json

import pytest

from intent import observation_loop, observation_report, observation_session


def write(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(document), encoding="utf-8")
    return hashlib.sha256(path.read_bytes()).hexdigest()


def read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def stamp(seconds):
    return {
        "monotonic_ns": 1_000_000_000 + int(seconds * 1e9),
        "utc_ns": 10_000_000_000 + int(seconds * 1e9),
        "elapsed_seconds": seconds,
    }


@pytest.fixture
def run(tmp_path):
    plan = {
        "schema": observation_loop.PLAN_SCHEMA,
        "capture_dir": "unused",
        "cutoffs": ["180", "185", "190"],
        "observer_argv": ["unused"],
        "observer_code_files": ["unused"],
        "observer_timeout_seconds": 240,
        "ffmpeg": "unused",
        "extract_timeout_seconds": 120,
    }
    write(tmp_path / "plan.json", plan)
    write(
        tmp_path / "run_manifest.json",
        {
            "schema": observation_loop.RUN_SCHEMA,
            "plan": plan,
            "started_monotonic_ns": 1_000_000_000,
            "started_utc_ns": 10_000_000_000,
            "full_pa_verified": False,
            "live_availability_verified": False,
        },
    )
    (tmp_path / "attempts").mkdir()
    return tmp_path


def add(run, index, status="unavailable", dispatch=1, publication=2):
    offset = index * 5
    row = {
        "index": index,
        "cutoff_seconds_exact": str(180 + offset),
        "scheduled_offset_seconds_exact": str(offset),
        "scheduled_input_monotonic_ns": stamp(offset)["monotonic_ns"],
        "scheduled_input_utc_ns": stamp(offset)["utc_ns"],
        "preparation_started": stamp(offset + dispatch - 0.5),
        "frame_ready": stamp(offset + dispatch),
        "observer_dispatch": stamp(offset + dispatch),
        "observer_exit": stamp(offset + publication - 0.2),
        "observer_exit_code": 0,
        "response_accepted": stamp(offset + publication),
        "attempt_finished": stamp(offset + publication),
        "dispatch_lateness_seconds": dispatch,
        "accepted_latency_from_schedule_seconds": publication,
        "actual_source_seconds_exact": str(180 + offset),
        "status": "accepted",
        "observation_status": status,
        "errors": [],
    }
    directory = run / "outputs" / f"cv_observation_{index:03d}"
    image = directory / "request/image.jpg"
    image.parent.mkdir(parents=True)
    image.write_bytes(b"synthetic-image")
    request = {
        "schema": observation_session.MAPPED_REQUEST_SCHEMA,
        "image_sha256": hashlib.sha256(image.read_bytes()).hexdigest(),
        "observation_id": str(index),
        "width": 100,
        "height": 100,
        "source_time_basis": "decoded_pts",
        "source_time_seconds_exact": str(180 + offset),
        "requested_cutoff_seconds_exact": str(180 + offset),
    }
    response = {
        "schema": observation_session.RESPONSE_SCHEMA,
        "observation_id": str(index),
        "image_sha256": request["image_sha256"],
        "status": status,
        "mitt": [30, 40] if status == "marked" else None,
        "visibility": "full" if status == "marked" else "unknown",
        "pose": "unknown",
        "reason": "" if status == "marked" else "not visible",
    }
    request_hash = write(directory / "request/request.json", request)
    response_hash = write(directory / "request/response.json", response)
    session_hash = write(directory / "session.json", {"request_sha256": request_hash})
    result = {
        "schema": "intent_visual_observation_result_v2",
        "request_sha256": request_hash,
        "session_sha256": session_hash,
        "raw_response_sha256": response_hash,
        "raw_response": response,
        "human_label": False,
        "independent_validation": False,
        "live_availability_verified": False,
        "finished_monotonic_ns": stamp(offset + publication - 0.1)["monotonic_ns"],
        **{
            key: request[key]
            for key in (
                "source_time_basis",
                "source_time_seconds_exact",
                "requested_cutoff_seconds_exact",
            )
        },
    }
    write(directory / "result.json", result)
    write(run / "attempts" / f"{index:03d}.json", row)
    return row


def test_late_accepted_observations_do_not_become_live_success(run):
    add(run, 0, "unavailable", dispatch=1, publication=13)
    add(run, 1, "marked", dispatch=10, publication=24)
    add(run, 2, "unknown", dispatch=21, publication=33)
    result = observation_report.build_report(run)
    assert result["planned"] == 3
    assert result["counts"]["accepted"] == 3
    assert result["counts"]["marked"] == result["counts"]["unavailable"] == 1
    assert result["counts"]["unknown"] == 1
    assert result["counts"]["dispatch_within_5s"] == 1
    assert result["counts"]["publication_within_5s"] == 0
    assert result["rates_per_planned"]["dispatch_within_5s"] == pytest.approx(1 / 3)
    assert not result["live_availability_verified"]
    assert not result["full_pa_verified"]
    assert not result["accuracy_evaluated"]


def test_interrupted_prefix_retains_unattempted_denominator(run):
    row = add(run, 0)
    row.update(
        status="error",
        observation_status=None,
        errors=["KeyboardInterrupt:"],
        response_accepted=None,
    )
    write(run / "attempts/000.json", row)
    write(
        run / "summary.json",
        {
            "schema": observation_loop.RUN_SCHEMA,
            "status": "interrupted",
            "planned": 3,
            "attempted": 1,
            "accepted": 0,
            "errors": 1,
            "full_pa_verified": False,
            "live_availability_verified": False,
        },
    )
    result = observation_report.build_report(run)
    assert result["counts"]["not_attempted"] == 2
    assert result["counts"]["errors"] == 1
    assert result["counts"]["unavailable"] == 0
    assert result["rates_per_planned"]["errors"] == pytest.approx(1 / 3)


@pytest.mark.parametrize("change", ["schedule", "metric", "future", "image", "response", "missing"])
def test_mismatched_evidence_is_rejected(run, change):
    row = add(run, 0)
    directory = run / "outputs/cv_observation_000"
    if change == "schedule":
        row["scheduled_input_monotonic_ns"] += 1
    elif change == "metric":
        row["accepted_latency_from_schedule_seconds"] = 0.1
    elif change == "future":
        row["actual_source_seconds_exact"] = "181"
    elif change == "image":
        (directory / "request/image.jpg").write_bytes(b"changed")
    elif change == "response":
        response = read(directory / "request/response.json")
        response["status"] = "marked"
        write(directory / "request/response.json", response)
    elif change == "missing":
        (directory / "result.json").unlink()
    write(run / "attempts/000.json", row)
    with pytest.raises(ValueError):
        observation_report.build_report(run)


def test_summary_cannot_hide_missing_attempts(run):
    add(run, 0)
    write(
        run / "summary.json",
        {
            "schema": observation_loop.RUN_SCHEMA,
            "status": "completed",
            "planned": 3,
            "attempted": 1,
            "accepted": 1,
            "errors": 0,
            "full_pa_verified": False,
            "live_availability_verified": False,
        },
    )
    with pytest.raises(ValueError, match="missing attempts"):
        observation_report.build_report(run)


def test_hole_in_attempt_prefix_rejected(run):
    add(run, 1)
    with pytest.raises(ValueError, match="consecutive prefix"):
        observation_report.build_report(run)


def test_strict_json_and_cli_no_overwrite(run, tmp_path):
    output = tmp_path / "report.json"
    observation_report.main(["--run-dir", str(run), "--out", str(output)])
    assert read(output)["counts"]["not_attempted"] == 3
    with pytest.raises(FileExistsError):
        observation_report.main(["--run-dir", str(run), "--out", str(output)])
    (run / "attempts/000.json").write_text('{"index":0,"index":1}')
    with pytest.raises(ValueError, match="Duplicate"):
        observation_report.build_report(run)


def test_interrupt_while_waiting_before_next_scheduled_time(run):
    add(run, 0)
    row = {
        "index": 1,
        "cutoff_seconds_exact": "185",
        "scheduled_offset_seconds_exact": "5",
        "scheduled_input_monotonic_ns": stamp(5)["monotonic_ns"],
        "scheduled_input_utc_ns": stamp(5)["utc_ns"],
        "preparation_started": None,
        "observer_dispatch": None,
        "response_accepted": None,
        "observation_status": None,
        "status": "error",
        "errors": ["KeyboardInterrupt:"],
        "attempt_finished": stamp(3),
    }
    write(run / "attempts/001.json", row)
    result = observation_report.build_report(run)
    assert result["counts"]["errors"] == 1 and result["counts"]["not_attempted"] == 1


@pytest.mark.parametrize("evidence", ["event", "directory"])
def test_killed_unpersisted_attempt_is_not_reported_as_unattempted(run, evidence):
    if evidence == "event":
        (run / "events.jsonl").write_text(
            json.dumps({"event": "observer_dispatch", "index": 0}) + "\n", encoding="utf-8"
        )
    else:
        (run / "outputs/cv_observation_000").mkdir(parents=True)
    with pytest.raises(ValueError, match="incomplete evidence"):
        observation_report.build_report(run)

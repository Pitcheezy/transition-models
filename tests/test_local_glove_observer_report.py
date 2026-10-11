"""Synthetic saved-run checks; no model, subprocess, source video or checkpoint."""

import hashlib
import json

import pytest

from intent import local_glove_observer_report as report
from intent import observation_loop, observation_session
from intent.local_glove_detector import SPECS, select_glove_detections


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return sha(path.read_bytes())


def read(path):
    return json.loads(path.read_bytes())


def stamp(seconds):
    return {
        "monotonic_ns": 1_000_000_000 + round(seconds * 1e9),
        "utc_ns": 10_000_000_000 + round(seconds * 1e9),
        "elapsed_seconds": seconds,
    }


@pytest.fixture
def run(tmp_path):
    root = tmp_path / "raw_loop"
    root.mkdir()
    (root / "attempts").mkdir()
    model = "ssdlite320_mobilenet_v3_large"
    config = {
        "schema": report.CONFIG_SCHEMA,
        "model_id": model,
        "weights": "C:/PRIVATE_SOURCE/checkpoint.pth",
        "weights_sha256": SPECS[model].sha256_prefix + "0" * 56,
        "device": "cpu",
        "threads": 4,
        "threshold": 0.5,
        "input_view": "full_frame",
        "crop_xyxy": None,
    }
    raw_config = json.dumps(config, indent=3).encode()
    argv = [
        "C:/PRIVATE_SOURCE/python.exe",
        "-m",
        "intent.local_glove_observer",
        "--config",
        "C:/PRIVATE_SOURCE/observer_config.json",
        "--request",
        "{request}",
        "--image",
        "{image}",
        "--response",
        "{response}",
    ]
    plan = {
        "schema": observation_loop.PLAN_SCHEMA,
        "capture_dir": "C:/PRIVATE_SOURCE/capture",
        "cutoffs": ["180", "185", "190", "195", "200"],
        "observer_argv": argv,
        "observer_code_files": ["C:/PRIVATE_SOURCE/observer_config.json"],
        "observer_timeout_seconds": 240,
        "ffmpeg": "unused",
        "extract_timeout_seconds": 120,
    }
    write(root / "plan.json", plan)
    protocol = {
        "prompt": observation_session.PROMPT,
        "response_schema": observation_session.RESPONSE_FIELDS,
        "request_schema": observation_session.MAPPED_REQUEST_SCHEMA,
    }
    write(
        root / "run_manifest.json",
        {
            "schema": observation_loop.RUN_SCHEMA,
            "plan": plan,
            "observer_argv": argv,
            "input_code_bindings": [
                {"path": argv[4], "sha256": sha(raw_config), "bytes": len(raw_config)}
            ],
            "protocol": protocol,
            "protocol_sha256": sha(json.dumps(protocol, sort_keys=True).encode()),
            "started_monotonic_ns": 1_000_000_000,
            "started_utc_ns": 10_000_000_000,
            "full_pa_verified": False,
            "live_availability_verified": False,
        },
    )
    return root, config, raw_config


def inner_timing(*, failed=False, begin=9_000_000_000_000_000):
    names = report._STAGES[:2] if failed else report._STAGES
    stages = {}
    for index, name in enumerate(names):
        stages[name] = {
            "status": "failed" if failed and index == len(names) - 1 else "completed",
            "started_perf_counter_ns": begin + index * 1_000_000,
            "finished_perf_counter_ns": begin + (index + 1) * 1_000_000,
            "elapsed_seconds": 0.001,
        }
    return {
        "clock": "perf_counter_ns",
        "clock_info": {"status": "synthetic"},
        "started_perf_counter_ns": begin,
        "finished_perf_counter_ns": begin + len(names) * 1_000_000,
        "elapsed_seconds": len(names) * 0.001,
        "stages": stages,
    }


def add(run, index, count=1, *, publication=2, failed=False):
    root, config, raw_config = run
    offset = index * 5
    row = {
        "index": index,
        "cutoff_seconds_exact": str(180 + offset),
        "scheduled_offset_seconds_exact": str(offset),
        "scheduled_input_monotonic_ns": stamp(offset)["monotonic_ns"],
        "scheduled_input_utc_ns": stamp(offset)["utc_ns"],
        "phase_timing_version": 1,
        "preparation_started": stamp(offset),
        "input_bindings_verified": stamp(offset + 0.1),
        "frame_extracted": stamp(offset + 0.2),
        "frame_ready": stamp(offset + 0.5),
        "request_ready": stamp(offset + 0.5),
        "observer_dispatch": stamp(offset + 0.5),
        "observer_exit": stamp(offset + publication - 0.2),
        "observer_exit_code": 1 if failed else 0,
        "output_bindings_verified": None if failed else stamp(offset + publication - 0.1),
        "response_accepted": None if failed else stamp(offset + publication),
        "attempt_finished": stamp(offset + publication),
        "dispatch_lateness_seconds": 0.5,
        "accepted_latency_from_schedule_seconds": None if failed else publication,
        "actual_source_seconds_exact": str(180 + offset),
        "status": "error" if failed else "accepted",
        "observation_status": None if failed else "unavailable" if count == 0 else "unknown",
        "errors": ["RuntimeError: PRIVATE_SOURCE provider secret"] if failed else [],
    }
    directory = root / "outputs" / f"cv_observation_{index:03d}"
    request_dir = directory / "request"
    request_dir.mkdir(parents=True)
    (request_dir / "image.jpg").write_bytes(f"saved-image-{index}".encode())
    image_hash = sha((request_dir / "image.jpg").read_bytes())
    request = {
        "schema": observation_session.MAPPED_REQUEST_SCHEMA,
        "image_sha256": image_hash,
        "observation_id": f"{index + 1:032x}",
        "width": 100,
        "height": 100,
        "source_time_basis": "decoded_pts",
        "source_time_seconds": 180 + offset,
        "source_time_seconds_exact": str(180 + offset),
        "requested_cutoff_seconds_exact": str(180 + offset),
        "prompt": observation_session.PROMPT,
        "response_schema": observation_session.RESPONSE_FIELDS,
    }
    request_hash = write(request_dir / "request.json", request)
    session_hash = write(
        directory / "session.json",
        {
            "schema": observation_session.MAPPED_SESSION_SCHEMA,
            "request_sha256": request_hash,
            "image_sha256": image_hash,
            "source_binding": {"source_frame": "C:/PRIVATE_SOURCE/frame.jpg"},
        },
    )
    engine = select_glove_detections(
        [[2, 2, 20, 20]] * count,
        [0.9] * count,
        [40] * count,
        image_size=[100, 100],
        threshold=0.5,
    )
    spec = SPECS[config["model_id"]]
    engine.update(
        model_name=config["model_id"],
        weights_name=f"{spec.weights_enum}.COCO_V1",
        weights_url=spec.weights_url,
        weights_sha256=config["weights_sha256"],
        device="cpu",
        threads=4,
        batch_size=1,
        runtime_versions={"torch": "2.6.0", "torchvision": "0.21.0"},
        decode_seconds=0.0001,
        preprocess_seconds=0.0001,
        model_seconds=0.0005,
        postprocess_seconds=0.0001,
    )
    response_hash = None
    if not failed:
        response = {
            "schema": observation_session.RESPONSE_SCHEMA,
            "observation_id": request["observation_id"],
            "image_sha256": image_hash,
            "status": row["observation_status"],
            "mitt": None,
            "visibility": "unknown",
            "pose": "unknown",
            "reason": "PRIVATE_SOURCE provider raw reason",
        }
        response_hash = write(request_dir / "response.json", response)
        write(
            directory / "result.json",
            {
                "schema": "intent_visual_observation_result_v2",
                "request_sha256": request_hash,
                "session_sha256": session_hash,
                "raw_response_sha256": response_hash,
                "raw_response": response,
                "human_label": False,
                "independent_validation": False,
                "live_availability_verified": False,
                "finished_monotonic_ns": stamp(offset + publication - 0.05)["monotonic_ns"],
                **{key: request[key] for key in observation_session.MAPPED_TIME_FIELDS},
            },
        )
    (request_dir / "local_detector_config.json").write_bytes(raw_config)
    write(
        request_dir / "local_detector_result.json",
        {
            "schema": report.SIDECAR_SCHEMA,
            "status": "failed" if failed else "accepted",
            "request_sha256": request_hash,
            "image_sha256": image_hash,
            "config_sha256": sha(raw_config),
            "config_snapshot_file": "local_detector_config.json",
            "response_sha256": response_hash,
            "observation_id": request["observation_id"],
            "configuration": config,
            "engine_response": None if failed else engine,
            "selection_status": None if failed else engine["selection_status"],
            "candidate": None if failed else engine["candidate"],
            "errors": [{"type": "RuntimeError", "message": "PRIVATE_SOURCE failure"}]
            if failed
            else [],
            **dict.fromkeys(report._FALSE_FLAGS, False),
            "timing": inner_timing(failed=failed),
        },
    )
    write(root / "attempts" / f"{index:03d}.json", row)
    return directory


@pytest.mark.parametrize(
    "old_prompt,old_schema,accepted",
    [(True, True, True), (False, False, True), (True, False, False), (False, True, False)],
)
def test_saved_local_request_accepts_only_complete_contract_pairs(
    run, old_prompt, old_schema, accepted
):
    directory = add(run, 0)
    request = read(directory / "request/request.json")
    request.update(
        prompt=observation_session.LEGACY_PROMPT if old_prompt else observation_session.PROMPT,
        response_schema=(
            observation_session.LEGACY_RESPONSE_FIELDS
            if old_schema
            else observation_session.RESPONSE_FIELDS
        ),
    )
    request_hash = write(directory / "request/request.json", request)
    saved_session = read(directory / "session.json")
    saved_session["request_sha256"] = request_hash
    write(directory / "session.json", saved_session)
    row = read(run[0] / "attempts/000.json")
    evidence = {"image": request["image_sha256"]}
    if accepted:
        assert report._bound_request(directory, row, evidence) == (request, request_hash)
    else:
        with pytest.raises(ValueError, match="prompt/response contract"):
            report._bound_request(directory, row, evidence)


def test_full_denominator_and_publication_boundary(run):
    add(run, 0, 1, publication=5)
    add(run, 1, 2)
    add(run, 2, 0)
    add(run, 3, failed=True)
    result = report.build_report(run[0])
    assert result["planned"] == 5
    assert result["counts"] == {
        "attempted": 4,
        "accepted": 3,
        "candidate": 1,
        "ambiguous": 1,
        "no_candidate": 1,
        "error": 1,
        "not_attempted": 1,
        "verified_mitt": 0,
        "publication_within_5s": 3,
        "candidate_publication_within_5s": 1,
    }
    assert result["rates_per_planned"]["candidate"] == 0.2
    assert [row["status"] for row in result["observations"]] == [
        "candidate",
        "ambiguous",
        "no_candidate",
        "error",
        "not_attempted",
    ]
    assert result["observations"][3]["engine_timing_seconds"] is None
    assert result["observations"][4]["publication_seconds"] is None
    assert result["counts"]["verified_mitt"] == 0
    assert result["development_only"]
    assert not result["accuracy_evaluated"]
    assert all(result[key] is False for key in report._FALSE_FLAGS)


def test_large_unrelated_perf_epoch_is_never_subtracted_from_loop_clock(run):
    add(run, 0)
    result = report.build_report(run[0])
    row = result["observations"][0]
    assert row["publication_seconds"] == 2
    assert row["adapter_timing"]["total_seconds"] == 0.004
    assert row["adapter_timing"]["stage_seconds"]["model_initialization"] == 0.001
    assert row["engine_timing_seconds"]["model_seconds"] == 0.0005
    assert result["timing_summary_seconds"]["outer_publication"]["n"] == 1
    assert result["timing_summary_seconds"]["engine_model"]["median"] == 0.0005


def test_fraction_over_full_plan_is_not_latency_success_or_accuracy(run):
    add(run, 0, publication=5.000000001)
    result = report.build_report(run[0])
    assert result["counts"]["publication_within_5s"] == 0
    assert result["counts"]["candidate"] == 1
    assert result["rates_per_planned"]["candidate"] == 0.2
    assert not result["live_availability_verified"]


def test_public_output_has_no_paths_images_provider_text_or_raw_boxes(run):
    add(run, 0)
    text = json.dumps(report.build_report(run[0]))
    for private in (
        "PRIVATE_SOURCE",
        "provider raw reason",
        "source_frame",
        "box_xyxy",
        "center_xy",
        "started_perf_counter_ns",
        "started_monotonic_ns",
    ):
        assert private not in text
    assert str(run[0]) not in text


@pytest.mark.parametrize(
    "field",
    ["request_sha256", "image_sha256", "config_sha256", "response_sha256", "observation_id"],
)
def test_sidecar_identity_and_every_hash_are_bound_to_actual_files(run, field):
    directory = add(run, 0)
    path = directory / "request/local_detector_result.json"
    value = read(path)
    value[field] = "0" * (32 if field == "observation_id" else 64)
    write(path, value)
    with pytest.raises(ValueError):
        report.build_report(run[0])


@pytest.mark.parametrize(
    "relative",
    [
        "request/image.jpg",
        "request/local_detector_config.json",
        "request/local_detector_result.json",
        "request/request.json",
        "request/response.json",
        "session.json",
        "result.json",
    ],
)
def test_required_raw_artifacts_cannot_be_removed(run, relative):
    directory = add(run, 0)
    (directory / relative).unlink()
    with pytest.raises((ValueError, OSError)):
        report.build_report(run[0])


@pytest.mark.parametrize(
    "change",
    ["image", "config_bytes", "frozen_hash", "frozen_path", "frozen_size", "session_image"],
)
def test_saved_and_frozen_input_bytes_are_verified(run, change):
    directory = add(run, 0)
    if change == "image":
        (directory / "request/image.jpg").write_bytes(b"changed")
    elif change == "config_bytes":
        path = directory / "request/local_detector_config.json"
        path.write_bytes(path.read_bytes() + b"\n")
    elif change == "session_image":
        path = directory / "session.json"
        value = read(path)
        value["image_sha256"] = "0" * 64
        session_hash = write(path, value)
        path = directory / "result.json"
        value = read(path)
        value["session_sha256"] = session_hash
        write(path, value)
    else:
        path = run[0] / "run_manifest.json"
        value = read(path)
        field = {"frozen_hash": "sha256", "frozen_path": "path", "frozen_size": "bytes"}[change]
        value["input_code_bindings"][0][field] = 1 if field == "bytes" else "wrong"
        write(path, value)
    with pytest.raises(ValueError):
        report.build_report(run[0])


@pytest.mark.parametrize(
    "change",
    [
        "selection",
        "candidate",
        "threshold",
        "verified",
        "nonfinite",
        "timing_elapsed",
        "timing_gap",
        "timing_clock",
        "timing_failed",
    ],
)
def test_candidate_and_timing_contracts_are_revalidated(run, change):
    directory = add(run, 0)
    path = directory / "request/local_detector_result.json"
    value = read(path)
    if change == "selection":
        value["engine_response"]["selection_status"] = "no_candidate"
    elif change == "candidate":
        value["candidate"]["center_xy"] = [99, 99]
    elif change == "threshold":
        value["engine_response"]["threshold"] = 0.8
    elif change == "verified":
        value["catcher_association_verified"] = True
    elif change == "nonfinite":
        value["engine_response"]["model_seconds"] = float("nan")
    elif change == "timing_elapsed":
        value["timing"]["elapsed_seconds"] = 0.01
    elif change == "timing_gap":
        value["timing"]["stages"]["inference"]["started_perf_counter_ns"] += 1
    elif change == "timing_clock":
        value["timing"]["clock"] = "monotonic_ns"
    elif change == "timing_failed":
        value["timing"]["stages"]["inference"]["status"] = "failed"
    write(path, value)
    with pytest.raises(ValueError):
        report.build_report(run[0])


def test_no_candidate_is_not_human_mitt_absence(run):
    add(run, 0, count=0)
    result = report.build_report(run[0])
    assert result["counts"]["no_candidate"] == 1
    assert result["counts"]["verified_mitt"] == 0
    assert "accuracy" not in result["counts"]
    assert "false_positive" not in json.dumps(result)


def test_interrupted_before_dispatch_retains_error_and_missing_denominators(run):
    root = run[0]
    write(
        root / "attempts/000.json",
        {
            "index": 0,
            "cutoff_seconds_exact": "180",
            "scheduled_offset_seconds_exact": "0",
            "scheduled_input_monotonic_ns": stamp(0)["monotonic_ns"],
            "scheduled_input_utc_ns": stamp(0)["utc_ns"],
            "status": "error",
            "observation_status": None,
            "errors": ["KeyboardInterrupt: private"],
            "attempt_finished": stamp(0.1),
        },
    )
    write(
        root / "summary.json",
        {
            "schema": observation_loop.RUN_SCHEMA,
            "status": "interrupted",
            "planned": 5,
            "attempted": 1,
            "accepted": 0,
            "errors": 1,
            "full_pa_verified": False,
            "live_availability_verified": False,
        },
    )
    result = report.build_report(root)
    assert result["run_status"] == "interrupted"
    assert result["counts"]["error"] == 1
    assert result["counts"]["not_attempted"] == 4
    assert result["observations"][0]["adapter_timing"] is None


def test_unpersisted_dispatched_attempt_cannot_be_called_unattempted(run):
    (run[0] / "events.jsonl").write_text('{"event":"observer_dispatch","index":0}\n')
    with pytest.raises(ValueError, match="incomplete evidence"):
        report.build_report(run[0])


def test_accepted_sidecar_without_published_loop_result_stays_error(run):
    directory = add(run, 0)
    path = run[0] / "attempts/000.json"
    value = read(path)
    value.update(
        status="error", observation_status=None, response_accepted=None, errors=["failure"]
    )
    write(path, value)
    result = report.build_report(run[0])
    assert directory.exists()
    assert result["counts"]["error"] == 1
    assert result["counts"]["candidate"] == 0
    assert result["observations"][0]["sidecar_status"] == "accepted"
    assert result["observations"][0]["publication_seconds"] is None


def test_no_original_source_or_checkpoint_is_required(run, tmp_path):
    add(run, 0)
    output = tmp_path / "public.json"
    assert report.main(["--run", str(run[0]), "--out", str(output)]) == 0
    assert read(output)["counts"]["candidate"] == 1
    with pytest.raises(FileExistsError):
        report.main(["--run", str(run[0]), "--out", str(output)])


def test_run_changes_during_report_are_rejected(run, monkeypatch):
    add(run, 0)
    original = report._artifacts

    def changed(*args):
        result = original(*args)
        (run[0] / "new-file.txt").write_text("changed")
        return result

    monkeypatch.setattr(report, "_artifacts", changed)
    with pytest.raises(ValueError, match="changed"):
        report.build_report(run[0])


def rebind_identity(directory, identity):
    request_path = directory / "request/request.json"
    request = read(request_path)
    request["observation_id"] = identity
    request_hash = write(request_path, request)
    session_path = directory / "session.json"
    saved_session = read(session_path)
    saved_session["request_sha256"] = request_hash
    session_hash = write(session_path, saved_session)
    response_path = directory / "request/response.json"
    response = read(response_path)
    response["observation_id"] = identity
    response_hash = write(response_path, response)
    result_path = directory / "result.json"
    result = read(result_path)
    result.update(
        request_sha256=request_hash,
        session_sha256=session_hash,
        raw_response=response,
        raw_response_sha256=response_hash,
    )
    write(result_path, result)
    sidecar_path = directory / "request/local_detector_result.json"
    sidecar = read(sidecar_path)
    sidecar.update(
        request_sha256=request_hash,
        observation_id=identity,
        response_sha256=response_hash,
    )
    write(sidecar_path, sidecar)


def test_duplicate_ids_are_rejected_even_if_every_local_hash_is_rebound(run):
    first = add(run, 0)
    second = add(run, 1)
    rebind_identity(second, read(first / "request/request.json")["observation_id"])
    with pytest.raises(ValueError, match="Duplicate observation identity"):
        report.build_report(run[0])


@pytest.mark.parametrize("change", ["changed", "removed"])
def test_error_without_sidecar_still_requires_bound_request_image(run, change):
    directory = add(run, 0, failed=True)
    (directory / "request/local_detector_result.json").unlink()
    assert report.build_report(run[0])["counts"]["error"] == 1
    image = directory / "request/image.jpg"
    if change == "changed":
        image.write_bytes(b"changed")
    else:
        image.unlink()
    with pytest.raises(ValueError, match="image byte binding"):
        report.build_report(run[0])


def test_single_glove_cannot_publish_marked_even_with_coherent_response_hashes(run):
    directory = add(run, 0)
    response_path = directory / "request/response.json"
    response = read(response_path)
    response.update(status="marked", mitt=[11, 11], visibility="full")
    response_hash = write(response_path, response)
    path = directory / "result.json"
    result = read(path)
    result.update(raw_response=response, raw_response_sha256=response_hash)
    write(path, result)
    path = directory / "request/local_detector_result.json"
    sidecar = read(path)
    sidecar["response_sha256"] = response_hash
    write(path, sidecar)
    path = run[0] / "attempts/000.json"
    attempt = read(path)
    attempt["observation_status"] = "marked"
    write(path, attempt)
    with pytest.raises(ValueError, match="unverified-mitt"):
        report.build_report(run[0])


def test_failed_sidecar_cannot_claim_a_published_response_hash(run):
    directory = add(run, 0, failed=True)
    path = directory / "request/local_detector_result.json"
    value = read(path)
    value["response_sha256"] = "0" * 64
    write(path, value)
    with pytest.raises(ValueError, match="Failed adapter"):
        report.build_report(run[0])


def test_reordered_or_duplicate_json_keys_do_not_change_bound_inputs_silently(run):
    directory = add(run, 0)
    path = directory / "request/local_detector_result.json"
    raw = path.read_text(encoding="utf-8")
    path.write_text(raw.replace('{"schema":', '{"schema":"duplicate","schema":', 1))
    with pytest.raises(ValueError, match="Duplicate JSON key"):
        report.build_report(run[0])


def test_fourteen_input_schedule_keeps_missing_rows_and_neutral_scope(run):
    root = run[0]
    manifest = read(root / "run_manifest.json")
    plan = manifest["plan"]
    plan["cutoffs"] = [str(180 + 5 * i) for i in range(14)]
    write(root / "plan.json", plan)
    write(root / "run_manifest.json", manifest)
    add(run, 0)
    result = report.build_report(root)
    assert result["planned"] == 14
    assert len(result["observations"]) == 14
    assert result["counts"]["accepted"] == 1
    assert result["counts"]["not_attempted"] == 13
    assert result["rates_per_planned"]["candidate"] == pytest.approx(1 / 14)
    assert "ten-cutoff" not in result["study_scope"]
    assert not result["full_pa_verified"]

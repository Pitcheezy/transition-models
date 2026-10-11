"""Synthetic spawned workers only; no torch model or GPU is loaded."""

import hashlib
import json
import os
import subprocess
import sys
import time
from dataclasses import replace
from pathlib import Path

import pytest
from PIL import Image

from intent import local_glove_detector as detector
from intent import local_glove_observer as observer
from intent import local_glove_worker as worker

MODEL = "ssdlite320_mobilenet_v3_large"
WEIGHTS = b"synthetic checkpoint: never deserialized"


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def read(path):
    return json.loads(path.read_bytes())


def write(path, value):
    path.write_text(json.dumps(value), encoding="utf-8")


def patch_spec():
    observer.SPECS = {MODEL: replace(detector.SPECS[MODEL], sha256_prefix=sha(WEIGHTS)[:8])}


class FakeEngine:
    def __init__(self, model_id, weights, weights_sha256, *, device, threads):
        self.model_id, self.weights, self.weights_sha256 = model_id, Path(weights), weights_sha256
        self.device, self.threads = device, threads
        self.loaded = False

    def load(self):
        if not self.loaded:
            with self.weights.with_name("synthetic_loads.jsonl").open(
                "a", encoding="utf-8"
            ) as stream:
                stream.write(json.dumps({"pid": os.getpid()}) + "\n")
            self.loaded = True
        return self

    def predict(self, data, *, image_sha256, crop, threshold):
        assert image_sha256 == sha(data) and crop is None
        self.load()
        result = detector.select_glove_detections(
            [[2, 2, 12, 12]], [0.9], [40], image_size=[20, 16], threshold=threshold
        )
        spec = observer.SPECS[self.model_id]
        result.update(
            model_name=self.model_id,
            weights_name=f"{spec.weights_enum}.COCO_V1",
            weights_url=spec.weights_url,
            weights_sha256=self.weights_sha256,
            runtime_versions={"torch": "2.6.0", "torchvision": "0.21.0"},
            device=self.device,
            threads=self.threads,
            batch_size=1,
            decode_seconds=0.001,
            preprocess_seconds=0.001,
            model_seconds=0.001,
            postprocess_seconds=0.001,
        )
        return result


def synthetic_worker(connection, staging_dir, engine_factory):
    patch_spec()
    worker._worker_main(connection, staging_dir, engine_factory)


class AlterConnection:
    def __init__(self, connection, staging_dir, mode):
        self.connection, self.staging_dir, self.mode = connection, Path(staging_dir), mode
        self.first_reply = None

    def recv_bytes(self, maximum):
        return self.connection.recv_bytes(maximum)

    def close(self):
        self.connection.close()

    def send_bytes(self, raw):
        value = json.loads(raw)
        if value.get("kind") == "result" and value.get("status") == "completed":
            directory = self.staging_dir / f"request_{value['index']:03d}"
            if self.mode == "nonce":
                value["nonce"] = "0" * 32
            elif self.mode == "stale":
                if self.first_reply is None:
                    self.first_reply = dict(value)
                else:
                    value = self.first_reply
            elif self.mode == "response_id":
                response = read(directory / "response.json")
                response["observation_id"] = "f" * 32
                write(directory / "response.json", response)
                sidecar = read(directory / "local_detector_result.json")
                sidecar["response_sha256"] = sha((directory / "response.json").read_bytes())
                write(directory / "local_detector_result.json", sidecar)
            elif self.mode == "marked":
                response = read(directory / "response.json")
                response.update(status="marked", mitt=[7, 7], visibility="full")
                write(directory / "response.json", response)
                sidecar = read(directory / "local_detector_result.json")
                sidecar["response_sha256"] = sha((directory / "response.json").read_bytes())
                write(directory / "local_detector_result.json", sidecar)
            elif self.mode == "ready_marker":
                (self.staging_dir / "ready.marker").write_text("private response complete")
            elif self.mode == "config_snapshot":
                path = directory / "local_detector_config.json"
                path.write_bytes(path.read_bytes() + b"\n")
        self.connection.send_bytes(worker._encode(value))


def nonce_worker(connection, staging_dir, engine_factory):
    patch_spec()
    worker._worker_main(
        AlterConnection(connection, staging_dir, "nonce"), staging_dir, engine_factory
    )


def stale_worker(connection, staging_dir, engine_factory):
    patch_spec()
    worker._worker_main(
        AlterConnection(connection, staging_dir, "stale"), staging_dir, engine_factory
    )


def response_id_worker(connection, staging_dir, engine_factory):
    patch_spec()
    worker._worker_main(
        AlterConnection(connection, staging_dir, "response_id"), staging_dir, engine_factory
    )


def marked_worker(connection, staging_dir, engine_factory):
    patch_spec()
    worker._worker_main(
        AlterConnection(connection, staging_dir, "marked"), staging_dir, engine_factory
    )


def ready_worker(connection, staging_dir, engine_factory):
    patch_spec()
    worker._worker_main(
        AlterConnection(connection, staging_dir, "ready_marker"), staging_dir, engine_factory
    )


def config_snapshot_worker(connection, staging_dir, engine_factory):
    patch_spec()
    worker._worker_main(
        AlterConnection(connection, staging_dir, "config_snapshot"), staging_dir, engine_factory
    )


def hanging_worker(connection, staging_dir, engine_factory):
    worker._receive(connection)
    (Path(staging_dir) / "worker_started.marker").write_text("waiting")
    time.sleep(20)
    (Path(staging_dir) / "late.marker").write_text("must never be reached")


def crashing_worker(connection, staging_dir, engine_factory):
    worker._receive(connection)
    os._exit(7)


class AdjustableClock:
    def __init__(self, marker=None):
        self.marker, self.expired = marker, False
        self.initial = time.monotonic_ns()

    def monotonic_ns(self):
        if self.expired or (self.marker is not None and self.marker.exists()):
            return self.initial + 100_000_000_000
        return time.monotonic_ns()


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    monkeypatch.setattr(
        observer, "SPECS", {MODEL: replace(detector.SPECS[MODEL], sha256_prefix=sha(WEIGHTS)[:8])}
    )
    checkpoint = tmp_path / "weights.pth"
    checkpoint.write_bytes(WEIGHTS)
    config_path = tmp_path / "config.json"
    config = {
        "schema": observer.CONFIG_SCHEMA,
        "model_id": MODEL,
        "weights": str(checkpoint),
        "weights_sha256": sha(WEIGHTS),
        "device": "cpu",
        "threads": 1,
        "threshold": 0.5,
        "input_view": "full_frame",
        "crop_xyxy": None,
    }
    write(config_path, config)
    return tmp_path, config_path


def request(fixture, index):
    root, config_path = fixture
    public = root / f"public_{index}"
    public.mkdir()
    Image.new("RGB", (20, 16), (index, 0, 0)).save(public / "image.jpg")
    value = {
        "schema": observer.session.MAPPED_REQUEST_SCHEMA,
        "observation_id": f"{index + 1:032x}",
        "image_sha256": sha((public / "image.jpg").read_bytes()),
        "width": 20,
        "height": 16,
        "source_time_seconds": 180 + index * 5,
        "source_time_seconds_exact": str(180 + index * 5),
        "requested_cutoff_seconds_exact": str(180 + index * 5),
        "source_time_basis": "decoded_pts",
        "prompt": observer.session.PROMPT,
        "response_schema": observer.session.RESPONSE_FIELDS,
    }
    write(public / "request.json", value)
    argv = [
        sys.executable,
        "-m",
        "intent.local_glove_observer",
        "--request",
        "request.json",
        "--image",
        "image.jpg",
        "--config",
        str(config_path),
        "--response",
        "response.json",
    ]
    return public, argv


def runner(fixture, *, target=synthetic_worker, clock=time):
    return worker.PersistentGloveRunner(
        fixture[0] / "worker_private",
        worker_target=target,
        engine_factory=FakeEngine,
        clock=clock,
        shutdown_timeout=2,
    )


def call(instance, item, timeout=30):
    public, argv = item
    return instance(
        argv, cwd=public, timeout=timeout, stdin=subprocess.DEVNULL, shell=False, check=False
    )


def test_lazy_spawn_load_once_reuse_and_confirmed_cleanup(fixture):
    first, second = request(fixture, 0), request(fixture, 1)
    instance = runner(fixture)
    assert not instance.staging_dir.exists()
    with instance:
        assert call(instance, first).returncode == 0
        assert call(instance, second).returncode == 0
        receipts = [
            read(instance.staging_dir / f"request_{index:03d}/request_receipt.json")
            for index in (0, 1)
        ]
        assert [item["spawned_this_request"] for item in receipts] == [True, False]
        assert [item["engine_reused"] for item in receipts] == [False, True]
        assert receipts[0]["worker_pid"] == receipts[1]["worker_pid"]
        assert all(
            item["ipc_sent"] and item["ipc_received"] and item["published"] for item in receipts
        )
        assert all(
            item["publication_monotonic_ns"] < item["deadline_monotonic_ns"] for item in receipts
        )
        loads = (fixture[0] / "synthetic_loads.jsonl").read_text().splitlines()
        assert len(loads) == 1
        assert all(
            read(public / "response.json")["status"] == "unknown" for public, _ in (first, second)
        )
        assert all(read(public / "response.json")["mitt"] is None for public, _ in (first, second))
    final = read(instance.staging_dir / "lifecycle_final.json")
    assert final["worker_exit_confirmed"] and final["worker_exitcode"] == 0
    assert final["requests_completed"] == 2
    instance.close()
    with pytest.raises(RuntimeError, match="closed"):
        call(instance, request(fixture, 2))


@pytest.mark.parametrize("changed", ["config_bytes", "arguments", "weights"])
def test_reuse_requires_identical_config_arguments_and_verified_weights(fixture, changed):
    first, second = request(fixture, 0), request(fixture, 1)
    with runner(fixture) as instance:
        call(instance, first)
        if changed == "config_bytes":
            fixture[1].write_bytes(fixture[1].read_bytes() + b"\n")
        elif changed == "arguments":
            second[1][3:7] = ["--image", "image.jpg", "--request", "request.json"]
        else:
            (fixture[0] / "weights.pth").write_bytes(b"changed")
        with pytest.raises((ValueError, RuntimeError)):
            call(instance, second)
        receipt = read(instance.staging_dir / "request_001/request_receipt.json")
        assert not receipt["published"]
        assert not (second[0] / "response.json").exists()
        assert receipt["worker_exit_confirmed"]
        with pytest.raises(RuntimeError, match="permanently failed"):
            call(instance, request(fixture, 2))
        assert len((fixture[0] / "synthetic_loads.jsonl").read_text().splitlines()) == 1


def test_timeout_kills_child_and_prevents_restart_and_late_output(fixture):
    first = request(fixture, 0)
    with runner(fixture, target=hanging_worker) as instance:
        with pytest.raises(subprocess.TimeoutExpired):
            call(instance, first, timeout=2)
        receipt = read(instance.staging_dir / "request_000/request_receipt.json")
        assert receipt["worker_exit_confirmed"]
        assert not receipt["published"]
        assert not (first[0] / "response.json").exists()
        assert not (instance.staging_dir / "late.marker").exists()
        with pytest.raises(RuntimeError, match="permanently failed"):
            call(instance, request(fixture, 1))
        assert (
            read(instance.staging_dir / "request_001/request_receipt.json")["status"]
            == "blocked_after_failure"
        )
    assert read(instance.staging_dir / "lifecycle_final.json")["worker_exit_confirmed"]


def test_ready_private_response_after_deadline_is_never_published(fixture):
    first = request(fixture, 0)
    clock = AdjustableClock(fixture[0] / "worker_private/ready.marker")
    with runner(fixture, target=ready_worker, clock=clock) as instance:
        with pytest.raises(subprocess.TimeoutExpired):
            call(instance, first)
        assert (instance.staging_dir / "request_000/response.json").is_file()
        assert not (first[0] / "response.json").exists()
        assert not (first[0] / "local_detector_result.json").exists()
        assert read(instance.staging_dir / "request_000/request_receipt.json")[
            "worker_exit_confirmed"
        ]


@pytest.mark.parametrize(
    "target", [nonce_worker, response_id_worker, marked_worker, config_snapshot_worker]
)
def test_untrusted_reply_or_artifact_cannot_be_published(fixture, target):
    first = request(fixture, 0)
    with runner(fixture, target=target) as instance:
        with pytest.raises(ValueError):
            call(instance, first)
        assert not (first[0] / "response.json").exists()
        assert read(instance.staging_dir / "request_000/request_receipt.json")[
            "worker_exit_confirmed"
        ]


def test_stale_reply_from_previous_request_is_rejected(fixture):
    with runner(fixture, target=stale_worker) as instance:
        call(instance, request(fixture, 0))
        second = request(fixture, 1)
        with pytest.raises(ValueError, match="identity/nonce/SHA"):
            call(instance, second)
        assert not (second[0] / "response.json").exists()


@pytest.mark.parametrize("name", worker._OUTPUT_NAMES)
def test_existing_public_file_is_never_overwritten(fixture, name):
    item = request(fixture, 0)
    path = item[0] / name
    path.write_bytes(b"preserve existing")
    with runner(fixture) as instance:
        with pytest.raises(FileExistsError):
            call(instance, item)
        assert path.read_bytes() == b"preserve existing"
        receipt = read(instance.staging_dir / "request_000/request_receipt.json")
        assert not receipt["spawned_this_request"]


def test_atomic_publication_does_not_overwrite_a_racing_file(fixture, monkeypatch):
    item = request(fixture, 0)
    original = os.link

    def raced(source, destination):
        if Path(destination).name == "response.json":
            Path(destination).write_bytes(b"belongs to another writer")
        original(source, destination)

    monkeypatch.setattr(worker.os, "link", raced)
    with runner(fixture) as instance:
        with pytest.raises(FileExistsError):
            call(instance, item)
        assert (item[0] / "response.json").read_bytes() == b"belongs to another writer"
        assert read(instance.staging_dir / "request_000/request_receipt.json")[
            "worker_exit_confirmed"
        ]


def test_expiry_during_publication_withdraws_only_own_response(fixture, monkeypatch):
    item = request(fixture, 0)
    clock = AdjustableClock()
    original = os.link

    def expire_after_link(source, destination):
        original(source, destination)
        if Path(destination).name == "response.json":
            clock.expired = True

    monkeypatch.setattr(worker.os, "link", expire_after_link)
    with runner(fixture, clock=clock) as instance:
        with pytest.raises(subprocess.TimeoutExpired):
            call(instance, item)
        assert not (item[0] / "response.json").exists()
        assert (item[0] / "local_detector_result.json").is_file()
        receipt = read(instance.staging_dir / "request_000/request_receipt.json")
        assert not receipt["published"] and receipt["worker_exit_confirmed"]


@pytest.mark.parametrize("filename", ["request.json", "image.jpg"])
def test_public_input_mutation_after_worker_completion_is_rejected(fixture, monkeypatch, filename):
    item = request(fixture, 0)
    original = worker._validate_staged

    def change_after_validation(*args):
        result = original(*args)
        (item[0] / filename).write_bytes(b"changed")
        return result

    monkeypatch.setattr(worker, "_validate_staged", change_after_validation)
    with runner(fixture) as instance:
        with pytest.raises(ValueError, match="inputs changed"):
            call(instance, item)
        assert not (item[0] / "response.json").exists()


def test_child_crash_is_not_an_abstention_and_exit_is_confirmed(fixture):
    item = request(fixture, 0)
    with runner(fixture, target=crashing_worker) as instance:
        with pytest.raises((EOFError, OSError, RuntimeError)):
            call(instance, item)
        assert not (item[0] / "response.json").exists()
        assert read(instance.staging_dir / "request_000/request_receipt.json")[
            "worker_exit_confirmed"
        ]
    final = read(instance.staging_dir / "lifecycle_final.json")
    assert final["worker_exitcode"] == 7


def test_audit_write_failure_retracts_response_and_closes_worker(fixture, monkeypatch):
    item = request(fixture, 0)
    original = worker._write

    def fail_receipt(path, raw):
        if path.name == "request_receipt.json":
            raise OSError("synthetic receipt failure")
        return original(path, raw)

    monkeypatch.setattr(worker, "_write", fail_receipt)
    with runner(fixture) as instance:
        with pytest.raises(OSError, match="receipt failure"):
            call(instance, item)
        assert not (item[0] / "response.json").exists()
    assert read(instance.staging_dir / "lifecycle_final.json")["worker_exit_confirmed"]


def test_launcher_requires_frozen_implementation_modules(fixture, monkeypatch):
    plan_path = fixture[0] / "plan.json"
    write(plan_path, {"observer_code_files": []})
    called = []
    monkeypatch.setattr(
        worker.observation_loop, "run_plan", lambda *args, **kwargs: called.append(True)
    )
    with pytest.raises(ValueError, match="Freeze worker"):
        worker.run_worker_plan(plan_path, fixture[0] / "run")
    assert not called
    assert not (fixture[0] / "run").exists()


def test_launcher_injects_runner_without_starting_a_worker_before_dispatch(fixture, monkeypatch):
    plan_path = fixture[0] / "plan.json"
    write(
        plan_path,
        {
            "observer_code_files": [
                str(Path(module.__file__).resolve())
                for module in (worker, observer, detector, worker.observer_report)
            ]
        },
    )
    output = fixture[0] / "run"

    def fake_plan(plan, out, *, runner):
        assert isinstance(runner, worker.PersistentGloveRunner)
        assert not runner.staging_dir.exists()
        out.mkdir()
        return {"status": "completed"}

    monkeypatch.setattr(worker.observation_loop, "run_plan", fake_plan)
    assert worker.main(["--plan", str(plan_path), "--out", str(output)]) == 0
    final = read(output / "worker_private/lifecycle_final.json")
    assert not final["worker_spawned"] and final["worker_exit_confirmed"]


def test_launcher_never_touches_an_existing_output(fixture, monkeypatch):
    plan_path = fixture[0] / "plan.json"
    write(
        plan_path,
        {
            "observer_code_files": [
                str(Path(module.__file__).resolve())
                for module in (worker, observer, detector, worker.observer_report)
            ]
        },
    )
    output = fixture[0] / "existing_run"
    output.mkdir()
    (output / "keep.json").write_bytes(b"existing evidence")
    monkeypatch.setattr(
        worker.observation_loop,
        "run_plan",
        lambda *args, **kwargs: pytest.fail("must not enter old run"),
    )
    with pytest.raises(FileExistsError, match="new directory"):
        worker.run_worker_plan(plan_path, output)
    assert {path.name for path in output.iterdir()} == {"keep.json"}
    assert (output / "keep.json").read_bytes() == b"existing evidence"


def test_duplicate_observation_id_cannot_be_submitted_twice(fixture):
    first, second = request(fixture, 0), request(fixture, 1)
    value = read(second[0] / "request.json")
    value["observation_id"] = read(first[0] / "request.json")["observation_id"]
    write(second[0] / "request.json", value)
    with runner(fixture) as instance:
        call(instance, first)
        with pytest.raises(ValueError, match="already submitted"):
            call(instance, second)
        assert not (second[0] / "response.json").exists()
        assert read(instance.staging_dir / "request_001/request_receipt.json")[
            "worker_exit_confirmed"
        ]


def test_locked_response_rollback_still_kills_worker_and_disables_reuse(fixture, monkeypatch):
    first = request(fixture, 0)
    clock = AdjustableClock()
    original_link, original_unlink = os.link, Path.unlink

    def expire_after_link(source, destination):
        original_link(source, destination)
        if Path(destination).name == "response.json":
            clock.expired = True

    def locked_unlink(path, *args, **kwargs):
        if path == first[0] / "response.json":
            raise PermissionError("synthetic locked public response")
        return original_unlink(path, *args, **kwargs)

    monkeypatch.setattr(worker.os, "link", expire_after_link)
    monkeypatch.setattr(Path, "unlink", locked_unlink)
    with runner(fixture, clock=clock) as instance:
        with pytest.raises(PermissionError, match="locked public response"):
            call(instance, first)
        receipt = read(instance.staging_dir / "request_000/request_receipt.json")
        assert receipt["status"] == "error" and not receipt["published"]
        assert receipt["worker_exit_confirmed"]
        assert receipt["cleanup_error"]["type"] == "PermissionError"
        with pytest.raises(RuntimeError, match="permanently failed"):
            call(instance, request(fixture, 1))
    final = read(instance.staging_dir / "lifecycle_final.json")
    assert final["worker_exit_confirmed"] and final["requests_completed"] == 0


@pytest.mark.parametrize("expired", [False, True])
def test_existing_loop_and_strict_report_preserve_success_and_timeout_denominators(
    fixture, monkeypatch, expired
):
    from fractions import Fraction

    loop = worker.observation_loop
    root, config_path = fixture
    capture = root / "capture"
    capture.mkdir()
    source = capture / "source.txt"
    source.write_text("synthetic mapped source")
    plan_path, output = root / "loop_plan.json", root / "loop_run"
    argv = [
        sys.executable,
        "-m",
        "intent.local_glove_observer",
        "--request",
        "{request}",
        "--image",
        "{image}",
        "--config",
        str(config_path),
        "--response",
        "{response}",
    ]
    write(
        plan_path,
        {
            "schema": loop.PLAN_SCHEMA,
            "capture_dir": str(capture),
            "cutoffs": ["180", "180.01"],
            "observer_argv": argv,
            "observer_code_files": [
                str(Path(module.__file__).resolve())
                for module in (worker, observer, detector, worker.observer_report)
            ]
            + [str(config_path)],
            "observer_timeout_seconds": 30,
            "ffmpeg": "unused",
            "extract_timeout_seconds": 30,
        },
    )
    monkeypatch.setattr(
        loop.clip_frames,
        "_capture_inputs",
        lambda _: ({}, None, [(source, sha(source.read_bytes()), source.stat().st_size)], {}),
    )
    monkeypatch.setattr(loop.clip_clock, "latest_mapped_frame", lambda *_: {})
    monkeypatch.setattr(worker.observer_report, "SPECS", observer.SPECS)

    def extract(**kwargs):
        kwargs["out"].mkdir()
        (kwargs["out"] / "cutoff.txt").write_text(str(kwargs["source_seconds"]))
        return {"status": "extracted"}

    def begin(frame, directory):
        public = directory / "request"
        public.mkdir(parents=True)
        index = int(directory.name.rsplit("_", 1)[1])
        cutoff = Fraction((frame / "cutoff.txt").read_text())
        Image.new("RGB", (20, 16)).save(public / "image.jpg")
        value = {
            "schema": observer.session.MAPPED_REQUEST_SCHEMA,
            "observation_id": f"{index + 10:032x}",
            "image_sha256": sha((public / "image.jpg").read_bytes()),
            "width": 20,
            "height": 16,
            "source_time_seconds": float(cutoff),
            "source_time_seconds_exact": str(cutoff),
            "requested_cutoff_seconds_exact": str(cutoff),
            "source_time_basis": "decoded_pts",
            "prompt": observer.session.PROMPT,
            "response_schema": observer.session.RESPONSE_FIELDS,
        }
        write(public / "request.json", value)
        write(
            directory / "session.json",
            {
                "schema": observer.session.MAPPED_SESSION_SCHEMA,
                "request_sha256": sha((public / "request.json").read_bytes()),
                "image_sha256": value["image_sha256"],
            },
        )
        return value

    def finish(directory, response_path):
        value = read(directory / "request/request.json")
        response = read(response_path)
        result = {
            "schema": "intent_visual_observation_result_v2",
            "request_sha256": sha((directory / "request/request.json").read_bytes()),
            "session_sha256": sha((directory / "session.json").read_bytes()),
            "raw_response_sha256": sha(response_path.read_bytes()),
            "raw_response": response,
            "human_label": False,
            "independent_validation": False,
            "live_availability_verified": False,
            "finished_monotonic_ns": time.monotonic_ns(),
            **{key: value[key] for key in observer.session.MAPPED_TIME_FIELDS},
        }
        write(directory / "result.json", result)
        return result

    monkeypatch.setattr(loop.clip_frames, "extract_frame", extract)
    monkeypatch.setattr(loop.observation_session, "begin_mapped", begin)
    monkeypatch.setattr(loop.observation_session, "finish", finish)
    clock = AdjustableClock(output / "worker_private/ready.marker") if expired else time
    with worker.PersistentGloveRunner(
        output / "worker_private",
        worker_target=ready_worker if expired else synthetic_worker,
        engine_factory=FakeEngine,
        clock=clock,
        shutdown_timeout=2,
    ) as instance:
        summary = loop.run_plan(plan_path, output, runner=instance)
    result = worker.observer_report.build_report(output)
    assert result["planned"] == 2 and result["counts"]["attempted"] == 2
    assert result["counts"]["verified_mitt"] == 0
    if expired:
        assert summary["status"] == "completed_with_errors"
        assert result["counts"]["error"] == 2
        assert result["counts"]["accepted"] == 0
        assert result["counts"]["candidate"] == 0
        assert result["counts"]["not_attempted"] == 0
        assert not any(output.glob("outputs/*/request/response.json"))
    else:
        assert summary["status"] == "completed"
        assert result["counts"]["candidate"] == 2
        assert result["counts"]["error"] == 0


def test_spawn_failure_closes_pipe_and_cannot_restart(fixture, monkeypatch):
    first = request(fixture, 0)
    instance = runner(fixture)

    def fail_start(process):
        raise RuntimeError("synthetic spawn failure")

    monkeypatch.setattr(instance.context.Process, "start", fail_start)
    with instance:
        with pytest.raises(RuntimeError, match="synthetic spawn failure"):
            call(instance, first)
        assert instance._connection.closed
        assert not (first[0] / "response.json").exists()
        with pytest.raises(RuntimeError, match="permanently failed"):
            call(instance, request(fixture, 1))
    final = read(instance.staging_dir / "lifecycle_final.json")
    assert final["worker_exit_confirmed"] and final["requests_completed"] == 0

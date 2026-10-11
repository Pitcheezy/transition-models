"""Explicit readiness with synthetic spawned engines; no real models or GPU."""

import io
import json
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

import pytest
import test_local_glove_worker as synthetic
from PIL import Image
from test_local_glove_worker import fixture as fixture

from intent import local_glove_ready as ready
from intent import local_glove_worker as worker


class ReadyEngine(synthetic.FakeEngine):
    def predict(self, data, *, image_sha256, crop, threshold):
        result = super().predict(data, image_sha256=image_sha256, crop=crop, threshold=threshold)
        with Image.open(io.BytesIO(data)) as image:
            size = image.size
            if size == worker.WARMUP_SIZE:
                assert image.getextrema() == ((0, 0), (0, 0), (0, 0))
            result["image_size"] = list(size)
        with self.weights.with_name("synthetic_inputs.jsonl").open("a", encoding="utf-8") as stream:
            stream.write(json.dumps({"size": list(size), "sha256": image_sha256}) + "\n")
        return result


class UnavailableEngine(ReadyEngine):
    def load(self):
        raise RuntimeError("synthetic model unavailable")


class ReadyConnection:
    def __init__(self, connection, directory, mode):
        self.connection, self.directory, self.mode = connection, Path(directory), mode

    def recv_bytes(self, maximum):
        return self.connection.recv_bytes(maximum)

    def close(self):
        self.connection.close()

    def send_bytes(self, raw):
        value = json.loads(raw)
        if value.get("kind") == "ready" and value.get("status") == "ready":
            if self.mode == "id":
                value["prepare_id"] = "0" * 32
            elif self.mode == "sequence":
                value["sequence"] = 1
            elif self.mode == "marker":
                (self.directory / "ready.marker").write_text("complete private readiness")
            elif self.mode in ("warmup_count", "image"):
                path = self.directory / "startup/startup_result.json"
                result = synthetic.read(path)
                if self.mode == "warmup_count":
                    result["warmups"].pop()
                else:
                    image_path = self.directory / "startup/warmup_black.jpg"
                    Image.new("RGB", worker.WARMUP_SIZE, "red").save(image_path)
                    result["warmup_image_sha256"] = synthetic.sha(image_path.read_bytes())
                synthetic.write(path, result)
                value["startup_sha256"] = synthetic.sha(path.read_bytes())
        self.connection.send_bytes(worker._encode(value))


def wrong_id_worker(connection, directory, engine_factory):
    synthetic.patch_spec()
    worker._worker_main(ReadyConnection(connection, directory, "id"), directory, engine_factory)


def wrong_sequence_worker(connection, directory, engine_factory):
    synthetic.patch_spec()
    worker._worker_main(
        ReadyConnection(connection, directory, "sequence"), directory, engine_factory
    )


def late_ready_worker(connection, directory, engine_factory):
    synthetic.patch_spec()
    worker._worker_main(ReadyConnection(connection, directory, "marker"), directory, engine_factory)


def missing_warmup_worker(connection, directory, engine_factory):
    synthetic.patch_spec()
    worker._worker_main(
        ReadyConnection(connection, directory, "warmup_count"), directory, engine_factory
    )


def nonblack_worker(connection, directory, engine_factory):
    synthetic.patch_spec()
    worker._worker_main(ReadyConnection(connection, directory, "image"), directory, engine_factory)


def runner(fixture, *, target=synthetic.synthetic_worker, engine=ReadyEngine, clock=time):
    return worker.PersistentGloveRunner(
        fixture[0] / "explicit.startup",
        worker_target=target,
        engine_factory=engine,
        clock=clock,
        shutdown_timeout=2,
    )


def inputs(fixture):
    return [
        json.loads(line)
        for line in (fixture[0] / "synthetic_inputs.jsonl").read_text().splitlines()
    ]


def test_prepare_uses_only_five_black_frames_and_reuses_one_engine_for_ten_requests(fixture):
    with runner(fixture) as instance:
        prepared = instance.prepare(fixture[1], 30)
        assert prepared["status"] == "ready" and prepared["warmup_count_completed"] == 5
        assert len(inputs(fixture)) == 5
        assert all(row["size"] == [1280, 720] for row in inputs(fixture))
        assert len({row["sha256"] for row in inputs(fixture)}) == 1
        assert not list(instance.staging_dir.glob("request_*"))
        assert not list(fixture[0].glob("public_*"))
        for index in range(10):
            assert synthetic.call(instance, synthetic.request(fixture, index)).returncode == 0
            receipt = synthetic.read(
                instance.staging_dir / f"request_{index:03d}/request_receipt.json"
            )
            assert receipt["engine_reused"] is True
            assert receipt["spawned_this_request"] is False
            assert receipt["worker_pid"] == prepared["worker_pid"]
        assert [row["size"] for row in inputs(fixture)] == [[1280, 720]] * 5 + [[20, 16]] * 10
        assert len((fixture[0] / "synthetic_loads.jsonl").read_text().splitlines()) == 1
    final = synthetic.read(instance.staging_dir / "lifecycle_final.json")
    assert final["pre_input_ready"] and final["worker_exit_confirmed"]
    assert final["requests_completed"] == 10 and final["worker_exitcode"] == 0
    execution = synthetic.read(instance.staging_dir / "execution.json")
    assert execution["initialization_mode"] == "explicit_pre_input" and not execution["lazy_start"]


def test_unavailable_model_preserves_failure_instead_of_claiming_readiness(fixture):
    with runner(fixture, engine=UnavailableEngine) as instance:
        with pytest.raises(RuntimeError, match="model unavailable"):
            instance.prepare(fixture[1], 30)
        receipt = synthetic.read(instance.staging_dir / "startup/prepare_receipt.json")
        assert receipt["status"] == "failed" and receipt["worker_exit_confirmed"]
        assert "model unavailable" in receipt["child_error"]["message"]
        with pytest.raises(RuntimeError, match="permanently failed"):
            synthetic.call(instance, synthetic.request(fixture, 0))
        assert not (fixture[0] / "synthetic_inputs.jsonl").exists()


@pytest.mark.parametrize(
    "target", [wrong_id_worker, wrong_sequence_worker, missing_warmup_worker, nonblack_worker]
)
def test_ready_identity_sequence_and_synthetic_input_contracts_are_strict(fixture, target):
    with runner(fixture, target=target) as instance:
        with pytest.raises(ValueError):
            instance.prepare(fixture[1], 30)
        assert not instance._prepared
        assert synthetic.read(instance.staging_dir / "startup/prepare_receipt.json")[
            "worker_exit_confirmed"
        ]
        with pytest.raises(RuntimeError, match="permanently failed"):
            synthetic.call(instance, synthetic.request(fixture, 0))


def test_ready_response_after_deadline_is_not_accepted_or_retried(fixture):
    clock = synthetic.AdjustableClock(fixture[0] / "explicit.startup/ready.marker")
    with runner(fixture, target=late_ready_worker, clock=clock) as instance:
        with pytest.raises(subprocess.TimeoutExpired):
            instance.prepare(fixture[1], 30)
        assert (instance.staging_dir / "startup/startup_result.json").is_file()
        assert not instance._prepared
        assert synthetic.read(instance.staging_dir / "startup/prepare_receipt.json")[
            "worker_exit_confirmed"
        ]
        with pytest.raises(RuntimeError, match="once"):
            instance.prepare(fixture[1], 30)


def test_startup_timeout_kills_child_and_keeps_requests_unexposed(fixture):
    with runner(fixture, target=synthetic.hanging_worker) as instance:
        with pytest.raises(subprocess.TimeoutExpired):
            instance.prepare(fixture[1], 2)
        assert synthetic.read(instance.staging_dir / "startup/prepare_receipt.json")[
            "worker_exit_confirmed"
        ]
        assert not list(instance.staging_dir.glob("request_*"))
        assert not (instance.staging_dir / "late.marker").exists()


def test_request_cannot_switch_configuration_after_readiness(fixture):
    with runner(fixture) as instance:
        instance.prepare(fixture[1], 30)
        fixture[1].write_bytes(fixture[1].read_bytes() + b"\n")
        item = synthetic.request(fixture, 0)
        with pytest.raises(ValueError, match="prepared config"):
            synthetic.call(instance, item)
        assert len(inputs(fixture)) == 5
        assert not (item[0] / "response.json").exists()


def test_readiness_cannot_be_repeated_or_follow_a_study_request(fixture):
    with runner(fixture) as instance:
        synthetic.call(instance, synthetic.request(fixture, 0))
        with pytest.raises(RuntimeError, match="once"):
            instance.prepare(fixture[1], 30)
        assert [row["size"] for row in inputs(fixture)] == [[20, 16]]


def test_ready_receipt_write_failure_never_exposes_a_ready_worker(fixture, monkeypatch):
    original = worker._write

    def failed(path, raw):
        if path.name == "prepare_receipt.json":
            raise OSError("synthetic readiness receipt failure")
        return original(path, raw)

    monkeypatch.setattr(worker, "_write", failed)
    with runner(fixture) as instance:
        with pytest.raises(OSError, match="receipt failure"):
            instance.prepare(fixture[1], 30)
        assert not instance._prepared
        with pytest.raises(RuntimeError, match="permanently failed"):
            synthetic.call(instance, synthetic.request(fixture, 0))
    assert synthetic.read(instance.staging_dir / "lifecycle_final.json")["worker_exit_confirmed"]


def plan_fixture(fixture, monkeypatch):
    root, config_path = fixture
    plan_path = root / "ready_plan.json"
    plan_path.write_text('{"synthetic": true}')
    capture = root / "capture"
    capture.mkdir()
    output = root / "ready_run"
    module_paths = [
        Path(module.__file__).resolve()
        for module in (ready, worker, worker.observer, worker.detector, worker.observer_report)
    ]
    bound_paths = [*module_paths, config_path, plan_path]
    bindings = [
        (path, synthetic.sha(path.read_bytes()), path.stat().st_size) for path in bound_paths
    ]
    command = [
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
    frozen = {
        "plan_sha256": synthetic.sha(plan_path.read_bytes()),
        "input_code_bindings": [
            {"path": str(path), "sha256": digest, "bytes": size} for path, digest, size in bindings
        ],
    }
    monkeypatch.setattr(
        worker.observation_loop,
        "_prepare",
        lambda plan, out: (
            out,
            capture,
            [Fraction(180 + i * 5) for i in range(10)],
            command,
            bindings,
            frozen,
        ),
    )
    return plan_path, output


def factory(staging, *, clock=time):
    return worker.PersistentGloveRunner(
        staging,
        worker_target=synthetic.synthetic_worker,
        engine_factory=ReadyEngine,
        clock=clock,
        shutdown_timeout=2,
    )


def test_schedule_starts_only_after_ready_and_cold_elapsed_keeps_startup(fixture, monkeypatch):
    plan_path, output = plan_fixture(fixture, monkeypatch)

    def loop(plan, out, *, runner, clock):
        assert runner._prepared and len(inputs(fixture)) == 5
        out.mkdir()
        started = clock.monotonic_ns()
        synthetic.write(out / "run_manifest.json", {"started_monotonic_ns": started})
        synthetic.call(runner, synthetic.request((out, fixture[1]), 0))
        result = {
            "status": "interrupted",
            "planned": 10,
            "attempted": 1,
            "accepted": 1,
            "errors": 0,
            "elapsed_seconds": (clock.monotonic_ns() - started) / 1e9,
        }
        synthetic.write(out / "summary.json", result)
        return result

    monkeypatch.setattr(worker.observation_loop, "run_plan", loop)
    result = ready.run_ready_plan(plan_path, output, startup_timeout=30, runner_factory=factory)
    assert result["schema"] == ready.SCHEMA and result["startup_ready"]
    assert result["planned"] == 10 and result["not_attempted"] == 9
    assert (
        result["cold_user_elapsed_seconds"]
        >= result["startup_elapsed_seconds"] + result["loop_elapsed_seconds"]
    )
    assert result["readiness_to_schedule_seconds"] >= 0
    assert result["worker_exit_confirmed"] and not result["live_availability_verified"]
    assert result["evidence_sha256"]["startup_result"] and result["evidence_sha256"]["loop_summary"]
    saved = synthetic.read(output.with_name(output.name + ".startup") / "readiness_run.json")
    assert saved == result
    assert str(fixture[0]) not in json.dumps(result)


def test_startup_failure_preserves_all_ten_not_attempted_and_original_error(fixture, monkeypatch):
    plan_path, output = plan_fixture(fixture, monkeypatch)
    monkeypatch.setattr(
        worker.observation_loop,
        "run_plan",
        lambda *args, **kwargs: pytest.fail("study must not begin"),
    )

    def unavailable(staging, *, clock=time):
        return worker.PersistentGloveRunner(
            staging,
            worker_target=synthetic.synthetic_worker,
            engine_factory=UnavailableEngine,
            clock=clock,
            shutdown_timeout=2,
        )

    with pytest.raises(RuntimeError, match="model unavailable"):
        ready.run_ready_plan(plan_path, output, startup_timeout=30, runner_factory=unavailable)
    assert not output.exists()
    result = synthetic.read(output.with_name(output.name + ".startup") / "readiness_run.json")
    assert result["status"] == "startup_failed" and not result["startup_ready"]
    assert result["attempted"] == 0 and result["not_attempted"] == result["planned"] == 10
    assert result["worker_exit_confirmed"] and result["cold_user_elapsed_seconds"] > 0


@pytest.mark.parametrize("which", ["output", "startup"])
def test_existing_output_or_sibling_is_rejected_before_model_preparation(
    fixture, monkeypatch, which
):
    plan_path, output = plan_fixture(fixture, monkeypatch)
    target = output if which == "output" else output.with_name(output.name + ".startup")
    target.mkdir()
    (target / "keep.txt").write_text("existing")
    with pytest.raises(FileExistsError, match="both be fresh"):
        ready.run_ready_plan(
            plan_path,
            output,
            startup_timeout=30,
            runner_factory=lambda *args, **kwargs: pytest.fail("must not prepare"),
        )
    assert {path.name for path in target.iterdir()} == {"keep.txt"}


def test_foreign_sibling_created_during_preflight_is_never_modified(fixture, monkeypatch):
    plan_path, output = plan_fixture(fixture, monkeypatch)

    def raced(staging, *, clock=time):
        staging.mkdir()
        (staging / "keep.txt").write_text("foreign")
        return factory(staging, clock=clock)

    with pytest.raises(FileExistsError):
        ready.run_ready_plan(plan_path, output, startup_timeout=30, runner_factory=raced)
    sibling = output.with_name(output.name + ".startup")
    assert {path.name for path in sibling.iterdir()} == {"keep.txt"}
    assert not output.exists()


def test_plan_change_after_ready_prevents_any_study_input(fixture, monkeypatch):
    plan_path, output = plan_fixture(fixture, monkeypatch)
    monkeypatch.setattr(
        worker.observation_loop,
        "run_plan",
        lambda *args, **kwargs: pytest.fail("changed plan must not run"),
    )

    class ChangedPlanRunner(worker.PersistentGloveRunner):
        def prepare(self, config_path, timeout):
            result = super().prepare(config_path, timeout)
            plan_path.write_bytes(plan_path.read_bytes() + b"\n")
            return result

    def changed(staging, *, clock=time):
        return ChangedPlanRunner(
            staging,
            worker_target=synthetic.synthetic_worker,
            engine_factory=ReadyEngine,
            clock=clock,
            shutdown_timeout=2,
        )

    with pytest.raises(ValueError):
        ready.run_ready_plan(plan_path, output, startup_timeout=30, runner_factory=changed)
    assert not output.exists() and len(inputs(fixture)) == 5
    result = synthetic.read(output.with_name(output.name + ".startup") / "readiness_run.json")
    assert result["status"] == "run_failed" and result["not_attempted"] == 10


def test_readiness_receipt_saved_after_deadline_is_failed_and_child_stopped(fixture, monkeypatch):
    marker = fixture[0] / "explicit.startup/ready.marker"
    clock = synthetic.AdjustableClock(marker)
    original = worker._write

    def delayed(path, raw):
        original(path, raw)
        if path.name == "prepare_receipt.json" and json.loads(raw)["status"] == "ready":
            marker.write_text("receipt write crossed the deadline")

    monkeypatch.setattr(worker, "_write", delayed)
    with runner(fixture, clock=clock) as instance:
        with pytest.raises(subprocess.TimeoutExpired):
            instance.prepare(fixture[1], 30)
        assert not instance._prepared and instance._state == "failed"
        receipt = synthetic.read(instance.staging_dir / "startup/prepare_receipt.json")
        assert receipt["status"] == "failed" and receipt["worker_exit_confirmed"]
        assert receipt["error"]["type"] == "TimeoutExpired"
        assert not list(instance.staging_dir.glob("request_*"))


@pytest.mark.parametrize("field,value", [("status", "failed"), ("config_sha256", "0" * 64)])
def test_wrapper_never_claims_ready_for_mismatched_prepare_result(
    fixture, monkeypatch, field, value
):
    plan_path, output = plan_fixture(fixture, monkeypatch)
    monkeypatch.setattr(
        worker.observation_loop,
        "run_plan",
        lambda *args, **kwargs: pytest.fail("unverified preparation must not begin study"),
    )

    class MismatchedRunner(worker.PersistentGloveRunner):
        def prepare(self, config_path, timeout):
            result = super().prepare(config_path, timeout)
            return dict(result, **{field: value})

    def mismatched(staging, *, clock=time):
        return MismatchedRunner(
            staging,
            worker_target=synthetic.synthetic_worker,
            engine_factory=ReadyEngine,
            clock=clock,
            shutdown_timeout=2,
        )

    with pytest.raises(ValueError, match="differs from frozen"):
        ready.run_ready_plan(plan_path, output, startup_timeout=30, runner_factory=mismatched)
    result = synthetic.read(output.with_name(output.name + ".startup") / "readiness_run.json")
    assert result["status"] == "startup_failed" and not result["startup_ready"]
    assert result["not_attempted"] == 10 and result["attempted"] == 0
    assert result["worker_exit_confirmed"] and not output.exists()
    assert not list(fixture[0].glob("public_*"))

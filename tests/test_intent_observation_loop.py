"""Synthetic dependency/clock tests; no real observer or FFmpeg is invoked."""

import json
import subprocess
import sys
from fractions import Fraction
from pathlib import Path

import pytest

from intent import observation_loop as loop


class FakeClock:
    def __init__(self):
        self.ns, self.sleeps = 10_000_000_000, []

    def monotonic_ns(self):
        return self.ns

    def time_ns(self):
        return 1_700_000_000_000_000_000 + self.ns

    def sleep(self, seconds):
        assert 0 < seconds <= 0.1
        self.sleeps.append(seconds)
        self.advance(seconds)

    def advance(self, seconds):
        self.ns += round(seconds * 1e9)


def load(path):
    return json.loads(path.read_text())


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    capture = tmp_path / "capture"
    capture.mkdir()
    (capture / "receipt.json").write_text("synthetic capture")
    adapter = tmp_path / "adapter.py"
    adapter.write_text("# synthetic observer adapter")
    plan_path = tmp_path / "plan.json"
    plan = {
        "schema": loop.PLAN_SCHEMA,
        "capture_dir": "capture",
        "cutoffs": ["180", "180.5", "181"],
        "observer_argv": [sys.executable, "adapter.py", "{request}", "{image}", "{response}"],
        "observer_code_files": ["adapter.py"],
        "observer_timeout_seconds": 10,
        "ffmpeg": "ffmpeg",
        "extract_timeout_seconds": 10,
    }
    plan_path.write_text(json.dumps(plan))
    clock, seen = FakeClock(), []
    source = capture / "receipt.json"
    monkeypatch.setattr(
        loop.clip_frames,
        "_capture_inputs",
        lambda path: (
            {},
            None,
            [(source, loop.clip_capture._sha256(source), source.stat().st_size)],
            {},
        ),
    )
    monkeypatch.setattr(loop.clip_clock, "latest_mapped_frame", lambda report, cutoff: {})

    def extract(**kwargs):
        assert kwargs["capture_dir"] == capture
        kwargs["out"].mkdir()
        (kwargs["out"] / "cutoff.txt").write_text(str(kwargs["source_seconds"]))
        seen.append((kwargs["source_seconds"], clock.monotonic_ns()))
        clock.advance(0.1)
        return {"status": "extracted"}

    def begin(frame, session):
        assert session.parent.name == "outputs" and session.name.startswith("cv_observation_")
        public = session / "request"
        public.mkdir(parents=True)
        cutoff = Fraction((frame / "cutoff.txt").read_text())
        request = {
            "source_time_seconds_exact": str(cutoff - Fraction(1, 100)),
            "requested_cutoff_seconds_exact": str(cutoff),
        }
        (public / "request.json").write_text(json.dumps(request))
        (public / "image.jpg").write_bytes(b"synthetic image")
        return request

    def finish(session, response):
        payload = load(response)
        if set(payload) != {"status"} or payload["status"] != "unavailable":
            raise ValueError("synthetic schema failure")
        clock.advance(0.05)
        return {"raw_response": payload}

    monkeypatch.setattr(loop.clip_frames, "extract_frame", extract)
    monkeypatch.setattr(loop.observation_session, "begin_mapped", begin)
    monkeypatch.setattr(loop.observation_session, "finish", finish)

    def run(command, **kwargs):
        assert kwargs["shell"] is False and kwargs["check"] is False
        assert kwargs["cwd"].name == "request"
        assert command[1] == str(adapter)
        assert command[2:] == ["request.json", "image.jpg", "response.json"]
        (kwargs["cwd"] / "response.json").write_text(json.dumps({"status": "unavailable"}))
        clock.advance(0.1)
        return subprocess.CompletedProcess(command, 0)

    return plan_path, tmp_path / "run", plan, clock, run, seen


def test_exact_schedule_order_anonymous_paths_and_frozen_inputs(fixture):
    path, out, _, clock, run, seen = fixture
    original = path.read_bytes()
    result = loop.run_plan(path, out, clock=clock, runner=run)
    assert result["status"] == "completed" and result["accepted"] == 3
    assert [time for _, time in seen] == [10_000_000_000, 10_500_000_000, 11_000_000_000]
    assert [cutoff for cutoff, _ in seen] == [Fraction(180), Fraction(361, 2), Fraction(181)]
    assert clock.sleeps
    row = load(out / "attempts/001.json")
    assert row["dispatch_lateness_seconds"] == pytest.approx(0.1)
    assert row["accepted_latency_from_schedule_seconds"] == pytest.approx(0.25)
    assert row["actual_source_seconds_exact"] == "18049/100"
    assert row["observation_status"] == "unavailable"
    assert not result["live_availability_verified"] and not result["full_pa_verified"]
    manifest = load(out / "run_manifest.json")
    assert manifest["protocol_sha256"] and manifest["input_code_bindings"]
    assert path.read_bytes() == original


def test_late_sequential_work_does_not_reset_schedule(fixture):
    path, out, _, clock, run, seen = fixture

    def slow(command, **kwargs):
        result = run(command, **kwargs)
        clock.advance(1)
        return result

    loop.run_plan(path, out, clock=clock, runner=slow)
    rows = [load(out / f"attempts/{i:03d}.json") for i in range(3)]
    assert [row["scheduled_input_monotonic_ns"] for row in rows] == [
        10_000_000_000,
        10_500_000_000,
        11_000_000_000,
    ]
    assert rows[1]["dispatch_lateness_seconds"] == pytest.approx(0.85)
    assert rows[2]["dispatch_lateness_seconds"] == pytest.approx(1.6)
    assert seen[1][1] > rows[1]["scheduled_input_monotonic_ns"]


@pytest.mark.parametrize("failure", ["nonzero", "missing", "invalid", "timeout"])
def test_observer_failures_are_errors_never_abstentions(fixture, failure):
    path, out, _, clock, _, _ = fixture

    def fail(command, **kwargs):
        response = kwargs["cwd"] / "response.json"
        if failure == "timeout":
            raise subprocess.TimeoutExpired(command, 10)
        if failure != "missing":
            response.write_text(
                json.dumps({"status": "unavailable"} if failure == "nonzero" else {"fake": True})
            )
        return subprocess.CompletedProcess(command, 3 if failure == "nonzero" else 0)

    result = loop.run_plan(path, out, clock=clock, runner=fail)
    assert result["accepted"] == 0 and result["errors"] == 3
    for i in range(3):
        row = load(out / f"attempts/{i:03d}.json")
        assert row["observation_status"] is None and row["response_accepted"] is None
        assert row["errors"]
        assert all(
            row[phase] is not None
            for phase in ("input_bindings_verified", "frame_extracted", "request_ready")
        )
        assert (row["output_bindings_verified"] is not None) == (failure == "invalid")


def test_interrupt_preserves_attempt_and_does_not_start_more(fixture):
    path, out, _, clock, _, seen = fixture

    def stop(*args, **kwargs):
        raise KeyboardInterrupt()

    result = loop.run_plan(path, out, clock=clock, runner=stop)
    assert result["status"] == "interrupted" and result["attempted"] == 1
    assert len(seen) == 1
    row = load(out / "attempts/000.json")
    assert row["status"] == "error"
    assert all(
        row[phase] is not None
        for phase in ("input_bindings_verified", "frame_extracted", "request_ready")
    )
    assert row["output_bindings_verified"] is None and row["response_accepted"] is None


@pytest.mark.parametrize(
    "change",
    [
        "duplicate",
        "reverse",
        "over_limit",
        "float",
        "empty_command",
        "shell_string",
        "placeholder",
        "no_code",
        "timeout",
    ],
)
def test_bad_plan_refused_before_new_run(fixture, change):
    path, out, plan, clock, run, seen = fixture
    if change == "duplicate":
        plan["cutoffs"] = ["180", "180"]
    elif change == "reverse":
        plan["cutoffs"] = ["181", "180"]
    elif change == "over_limit":
        plan["cutoffs"] = list(range(51))
    elif change == "float":
        plan["cutoffs"] = [180.1]
    elif change == "empty_command":
        plan["observer_argv"] = []
    elif change == "shell_string":
        plan["observer_argv"] = "do something"
    elif change == "placeholder":
        plan["observer_argv"].append("{private}")
    elif change == "no_code":
        plan["observer_code_files"] = []
    else:
        plan["observer_timeout_seconds"] = 0
    path.write_text(json.dumps(plan))
    with pytest.raises(ValueError):
        loop.run_plan(path, out, clock=clock, runner=run)
    assert not out.exists() and not seen


def test_no_overwrite_or_silent_resume(fixture):
    path, out, _, clock, run, _ = fixture
    out.mkdir()
    marker = out / "keep"
    marker.write_text("unchanged")
    with pytest.raises(FileExistsError):
        loop.run_plan(path, out, clock=clock, runner=run)
    assert marker.read_text() == "unchanged"


def test_future_actual_frame_is_not_sent_to_observer(fixture, monkeypatch):
    path, out, _, clock, _, _ = fixture
    original = loop.observation_session.begin_mapped

    def future(frame, session):
        request = original(frame, session)
        request["source_time_seconds_exact"] = "999"
        return request

    monkeypatch.setattr(loop.observation_session, "begin_mapped", future)
    result = loop.run_plan(
        path, out, clock=clock, runner=lambda *a, **k: pytest.fail("must not run")
    )
    assert result["accepted"] == 0 and result["errors"] == 3
    for index in range(3):
        row = load(out / f"attempts/{index:03d}.json")
        assert row["input_bindings_verified"] is not None and row["frame_extracted"] is not None
        assert row["request_ready"] is None and row["output_bindings_verified"] is None


def test_changed_adapter_is_rejected_before_response_acceptance(fixture):
    path, out, _, clock, run, _ = fixture

    def mutate(command, **kwargs):
        result = run(command, **kwargs)
        Path(command[1]).write_text("# changed adapter")
        return result

    result = loop.run_plan(path, out, clock=clock, runner=mutate)
    assert result["accepted"] == 0 and result["errors"] == 3
    first = load(out / "attempts/000.json")
    assert first["input_bindings_verified"] is not None and first["request_ready"] is not None
    assert first["output_bindings_verified"] is None
    for index in (1, 2):
        row = load(out / f"attempts/{index:03d}.json")
        assert all(
            row[phase] is None
            for phase in (
                "input_bindings_verified",
                "frame_extracted",
                "request_ready",
                "output_bindings_verified",
            )
        )


def test_extraction_failure_never_invokes_observer(fixture, monkeypatch):
    path, out, _, clock, _, _ = fixture
    monkeypatch.setattr(loop.clip_frames, "extract_frame", lambda **kwargs: {"status": "failed"})
    result = loop.run_plan(
        path, out, clock=clock, runner=lambda *a, **k: pytest.fail("must not run")
    )
    assert result["accepted"] == 0 and result["errors"] == 3
    row = load(out / "attempts/000.json")
    assert row["observer_dispatch"] is None and row["input_bindings_verified"] is not None
    assert all(
        row[phase] is None
        for phase in ("frame_extracted", "request_ready", "output_bindings_verified")
    )


def test_completed_phase_stamps_split_local_pipeline_without_extra_guards(fixture, monkeypatch):
    path, out, _, clock, run, _ = fixture
    verify = loop.clip_frames._verify_files
    begin = loop.observation_session.begin_mapped
    calls = []

    def measured_verify(bindings):
        verify(bindings)
        calls.append("verify")
        clock.advance(0.2)

    def measured_begin(frame, session):
        result = begin(frame, session)
        calls.append("begin")
        clock.advance(0.3)
        return result

    def measured_run(command, **kwargs):
        calls.append("observer")
        return run(command, **kwargs)

    monkeypatch.setattr(loop.clip_frames, "_verify_files", measured_verify)
    monkeypatch.setattr(loop.observation_session, "begin_mapped", measured_begin)
    loop.run_plan(path, out, clock=clock, runner=measured_run)
    assert calls == ["verify", "begin", "observer", "verify"] * 3
    phases = [
        "preparation_started",
        "input_bindings_verified",
        "frame_extracted",
        "request_ready",
        "observer_dispatch",
        "observer_exit",
        "output_bindings_verified",
        "response_accepted",
    ]
    for index in range(3):
        row = load(out / f"attempts/{index:03d}.json")
        offsets = [
            (row[phase]["monotonic_ns"] - row["preparation_started"]["monotonic_ns"]) / 1e9
            for phase in phases
        ]
        assert offsets == pytest.approx([0, 0.2, 0.3, 0.6, 0.6, 0.7, 0.9, 0.95])
        assert row["phase_timing_version"] == 1
        assert row["request_ready"] == row["frame_ready"]
        assert row["scheduled_input_monotonic_ns"] == 10_000_000_000 + index * 500_000_000
    events = [json.loads(line) for line in (out / "events.jsonl").read_text().splitlines()]
    assert [event["event"] for event in events if event["index"] == 0] == [
        phase for phase in phases if phase != "observer_exit"
    ]


@pytest.mark.parametrize("failure", ["input_bindings", "request", "output_bindings", "finish"])
def test_phase_stamp_only_records_completed_stages(fixture, monkeypatch, failure):
    path, out, _, clock, run, _ = fixture
    verify = loop.clip_frames._verify_files
    calls = []

    def checked_verify(bindings):
        calls.append("verify")
        if failure == "input_bindings" or (failure == "output_bindings" and len(calls) % 2 == 0):
            raise ValueError("synthetic binding failure")
        verify(bindings)

    def fail_stage(*args):
        raise ValueError("synthetic stage failure")

    monkeypatch.setattr(loop.clip_frames, "_verify_files", checked_verify)
    if failure == "request":
        monkeypatch.setattr(loop.observation_session, "begin_mapped", fail_stage)
    elif failure == "finish":
        monkeypatch.setattr(loop.observation_session, "finish", fail_stage)
    result = loop.run_plan(path, out, clock=clock, runner=run)
    assert result["errors"] == 3 and result["accepted"] == 0
    assert len(calls) == (3 if failure in {"input_bindings", "request"} else 6)
    events = [json.loads(line) for line in (out / "events.jsonl").read_text().splitlines()]
    completed = {
        "input_bindings_verified": failure != "input_bindings",
        "frame_extracted": failure != "input_bindings",
        "request_ready": failure in {"output_bindings", "finish"},
        "output_bindings_verified": failure == "finish",
    }
    for index in range(3):
        row = load(out / f"attempts/{index:03d}.json")
        assert row["response_accepted"] is None and row["observation_status"] is None
        event_names = [event["event"] for event in events if event["index"] == index]
        for phase, expected in completed.items():
            assert (row[phase] is not None) == expected
            assert (phase in event_names) == expected

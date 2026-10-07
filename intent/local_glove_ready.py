"""Explicit pre-input readiness followed by the unchanged local observation loop.

Five generated black frames warm one owned worker. Startup is reported separately
and remains part of the cold user-facing elapsed time. This is development replay,
not a live service readiness or latency guarantee.
"""

from __future__ import annotations

import argparse
import json
import math
import time
from pathlib import Path

from intent import local_glove_worker as worker

SCHEMA = "local_glove_ready_run_v1"


def _paths(out):
    output = Path(out).absolute()
    worker._no_links(output)
    if not output.name or output.parent == output:
        raise ValueError("A named fresh run directory is required")
    startup = output.with_name(output.name + ".startup")
    worker._no_links(startup)
    if startup.parent != output.parent or startup == output:
        raise ValueError("Unsafe readiness sibling path")
    if output.exists() or startup.exists():
        raise FileExistsError("Run output and its .startup sibling must both be fresh")
    if not output.parent.is_dir():
        raise ValueError("Run parent directory must already exist")
    return output, startup


def _file_hash(path):
    return worker._sha(worker._read(path)) if path.is_file() else None


def run_ready_plan(
    plan_path, out, *, startup_timeout, runner_factory=worker.PersistentGloveRunner, clock=time
):
    """Prepare on synthetic inputs, then start the fixed replay schedule exactly once."""
    cold_started = clock.monotonic_ns()
    if (
        type(startup_timeout) not in (int, float)
        or not math.isfinite(startup_timeout)
        or not 0 < startup_timeout <= 3600
    ):
        raise ValueError("Startup timeout must be finite and at most 3600 seconds")
    output, startup = _paths(out)
    plan_path = Path(plan_path).absolute()
    # Read-only plan/source/code preflight; no study frame is extracted or sent to a worker.
    _, capture, cutoffs, command, bindings, frozen = worker.observation_loop._prepare(
        plan_path, output
    )
    if startup.is_relative_to(capture) or capture.is_relative_to(startup):
        raise ValueError("Readiness staging must not overlap capture inputs")
    declared = {Path(item["path"]).resolve() for item in frozen["input_code_bindings"]}
    required = {
        Path(module.__file__).resolve()
        for module in (worker, worker.observer, worker.detector, worker.observer_report)
    } | {Path(__file__).resolve()}
    if not required.issubset(declared):
        raise ValueError("Freeze ready, worker, observer, detector and observer-report modules")
    resolved_command = command.copy()
    for placeholder, filename in worker.observation_loop._PLACEHOLDERS.items():
        resolved_command = [value.replace(placeholder, filename) for value in resolved_command]
    _, config_path = worker._command(resolved_command, output.parent)
    config_bindings = [
        item for item in frozen["input_code_bindings"] if item["path"] == str(config_path)
    ]
    if len(config_bindings) != 1:
        raise ValueError("Readiness config needs exactly one frozen input byte binding")
    config_sha = config_bindings[0]["sha256"]
    preflight_finished = clock.monotonic_ns()
    summary = {
        "schema": SCHEMA,
        "execution_mode": "explicit_pre_input_readiness",
        "status": "startup_failed",
        "planned": len(cutoffs),
        "attempted": 0,
        "accepted": 0,
        "errors": 0,
        "not_attempted": len(cutoffs),
        "startup_ready": False,
        "startup_timeout_seconds": startup_timeout,
        "warmup_count_planned": worker.WARMUP_COUNT,
        "warmup_size": list(worker.WARMUP_SIZE),
        "warmup_source": "generated_black_rgb",
        "study_frame_inputs_before_ready": 0,
        "preflight_elapsed_seconds": (preflight_finished - cold_started) / 1e9,
        "startup_elapsed_seconds": None,
        "loop_elapsed_seconds": None,
        "readiness_to_schedule_seconds": None,
        "cold_user_elapsed_seconds": None,
        "development_only": True,
        "live_availability_verified": False,
        "full_pa_verified": False,
        "accuracy_evaluated": False,
        "catcher_association_verified": False,
        "error_type": None,
        "evidence_sha256": {"plan": frozen["plan_sha256"], "config": config_sha},
        "timing_notice": "Startup is before the replay schedule, not free. Cold elapsed includes preflight, startup, replay and worker cleanup; excludes interpreter launch/import and final summary write. Loop latency after readiness is not cold-start or live latency.",
    }
    startup_started, ready_ns = None, None
    phase = "startup"
    runner = None
    try:
        with runner_factory(startup, clock=clock) as runner:
            startup_started = clock.monotonic_ns()
            prepared = runner.prepare(config_path, startup_timeout)
            ready_ns = clock.monotonic_ns()
            summary.update(startup_elapsed_seconds=(ready_ns - startup_started) / 1e9)
            if prepared.get("status") != "ready" or prepared.get("config_sha256") != config_sha:
                raise ValueError("Accepted readiness differs from frozen plan configuration")
            summary["startup_ready"] = True
            phase = "pre_schedule"
            # A ready worker must not silently run a subsequently edited study plan.
            worker.observation_loop.clip_frames._verify_files(bindings)
            if output.exists():
                raise FileExistsError("Run output appeared during readiness")
            phase = "loop"
            result = worker.observation_loop.run_plan(plan_path, output, runner=runner, clock=clock)
            summary.update(
                status=result["status"],
                attempted=result["attempted"],
                accepted=result["accepted"],
                errors=result["errors"],
                not_attempted=len(cutoffs) - result["attempted"],
                loop_elapsed_seconds=result["elapsed_seconds"],
            )
    except (Exception, KeyboardInterrupt) as exc:
        if phase == "loop":
            summary.update(attempted=None, accepted=None, errors=None, not_attempted=None)
        summary.update(
            status="startup_failed" if phase == "startup" else "run_failed",
            error_type=type(exc).__name__,
        )
        raise
    finally:
        if runner is not None and runner._owns_staging and startup.is_dir():
            finished = clock.monotonic_ns()
            if summary["startup_elapsed_seconds"] is None and startup_started is not None:
                summary["startup_elapsed_seconds"] = (finished - startup_started) / 1e9
            summary["cold_user_elapsed_seconds"] = (finished - cold_started) / 1e9
            final_path = startup / "lifecycle_final.json"
            final = worker.observer._json(worker._read(final_path)) if final_path.is_file() else {}
            summary["worker_exit_confirmed"] = final.get("worker_exit_confirmed") is True
            summary["worker_exitcode"] = final.get("worker_exitcode")
            summary["evidence_sha256"].update(
                prepare_receipt=_file_hash(startup / "startup/prepare_receipt.json"),
                startup_result=_file_hash(startup / "startup/startup_result.json"),
                worker_lifecycle=_file_hash(final_path),
                loop_manifest=_file_hash(output / "run_manifest.json"),
                loop_summary=_file_hash(output / "summary.json"),
            )
            if (output / "run_manifest.json").is_file() and ready_ns is not None:
                manifest = worker.observer._json(worker._read(output / "run_manifest.json"))
                schedule_ns = manifest["started_monotonic_ns"]
                if schedule_ns < ready_ns:
                    raise ValueError("Replay schedule started before readiness completed")
                summary["readiness_to_schedule_seconds"] = (schedule_ns - ready_ns) / 1e9
            worker._write(startup / "readiness_run.json", worker._encode(summary))
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--startup-timeout", type=float, required=True)
    args = parser.parse_args(argv)
    result = run_ready_plan(args.plan, args.out, startup_timeout=args.startup_timeout)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

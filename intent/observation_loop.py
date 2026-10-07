"""Sequential measured local replay with an explicitly supplied observer command.

This trusted local runner is not a filesystem sandbox. A replay schedule is not actual
broadcast arrival, and response acceptance is not live availability or accuracy evidence.
"""

from __future__ import annotations

import argparse
import json
import math
import os
import shutil
import subprocess
import sys
import time
from fractions import Fraction
from pathlib import Path

from intent import clip_capture, clip_clock, clip_frames, observation_session

PLAN_SCHEMA = "intent_observation_loop_plan_v1"
RUN_SCHEMA = "intent_observation_loop_run_v1"
_FIELDS = {
    "schema",
    "capture_dir",
    "cutoffs",
    "observer_argv",
    "observer_code_files",
    "observer_timeout_seconds",
    "ffmpeg",
    "extract_timeout_seconds",
}
_PLACEHOLDERS = {"{request}": "request.json", "{image}": "image.jpg", "{response}": "response.json"}


def _write(path, document):
    with path.open("x", encoding="utf-8") as stream:
        json.dump(document, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")


def _path(value, base):
    if not isinstance(value, str) or not value.strip():
        raise ValueError("Expected a nonempty file/directory path")
    return clip_capture._plain_path(base / value)


def _launcher_binding(value):
    """Allow only this process's venv launcher links, without changing its argv path."""
    launcher = Path(os.path.abspath(value))
    clip_capture._plain_path(launcher.parent)
    config = None
    if launcher.is_symlink():
        prefix = Path(os.path.abspath(sys.prefix))
        if (
            launcher != Path(os.path.abspath(sys.executable))
            or sys.prefix == sys.base_prefix
            or launcher.parent.parent != prefix
            or launcher.parent.name not in {"bin", "Scripts"}
        ):
            raise ValueError("Only the current virtualenv Python launcher may be a symlink")
        config = clip_capture._plain_path(prefix / "pyvenv.cfg")
        if not config.is_file():
            raise ValueError("Current virtualenv must have a regular pyvenv.cfg")
    current, links, seen = launcher, [], set()
    while current.is_symlink():
        if current in seen or len(links) >= 40:
            raise ValueError("Cyclic or excessive Python launcher link chain")
        seen.add(current)
        clip_capture._plain_path(current.parent)
        target = current.readlink()
        links.append({"path": str(current), "target": str(target)})
        current = Path(os.path.abspath(current.parent / target))
    current = clip_capture._plain_path(current)
    if not current.is_file():
        raise ValueError("Observer executable is unavailable")
    return {
        "launcher": str(launcher),
        "resolved": str(current),
        "links": links,
        "venv_config": str(config) if config is not None else None,
    }


def _verify_launcher(binding):
    if _launcher_binding(binding["launcher"]) != binding:
        raise ValueError("Frozen observer launcher link chain or target changed")


def _prepare(plan_path, out):
    plan_path, out = (clip_capture._plain_path(value) for value in (plan_path, out))
    if out.exists():
        raise FileExistsError("Run output must be a new directory; no implicit resume")
    raw = plan_path.read_bytes()
    plan = json.loads(raw)
    if not isinstance(plan, dict) or set(plan) != _FIELDS or plan["schema"] != PLAN_SCHEMA:
        raise ValueError("Unexpected loop plan schema/fields")
    values = plan["cutoffs"]
    if (
        not isinstance(values, list)
        or not 1 <= len(values) <= 50
        or any(type(v) not in (str, int) for v in values)
    ):
        raise ValueError("Plan needs 1..50 exact decimal/rational string or integer cutoffs")
    try:
        cutoffs = [Fraction(v) for v in values]
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("Invalid rational cutoff") from exc
    if cutoffs[0] < 0 or any(a >= b for a, b in zip(cutoffs, cutoffs[1:], strict=False)):
        raise ValueError("Cutoffs must be nonnegative and strictly ascending")
    capture_dir = _path(plan["capture_dir"], plan_path.parent)
    if out.is_relative_to(capture_dir) or capture_dir.is_relative_to(out):
        raise ValueError("Run output must not overlap capture inputs")
    _, _, bindings, mapping = clip_frames._capture_inputs(capture_dir)
    for cutoff in cutoffs:
        clip_clock.latest_mapped_frame(mapping, cutoff)
    argv, files = plan["observer_argv"], plan["observer_code_files"]
    if (
        not isinstance(argv, list)
        or not argv
        or any(not isinstance(v, str) or not v or "\x00" in v for v in argv)
    ):
        raise ValueError("Observer command must be an explicit nonempty argv list")
    if not isinstance(files, list) or not files:
        raise ValueError("Declare observer code files to freeze the explicit adapter")
    resolved = {value: _path(value, plan_path.parent) for value in files}
    executable = shutil.which(argv[0])
    if executable is None:
        executable = str(plan_path.parent / argv[0])
    launcher = _launcher_binding(executable)
    command = [str(resolved.get(value, value)) for value in argv]
    command[0] = launcher["launcher"]
    used = set()
    for value in command:
        for placeholder in _PLACEHOLDERS:
            if placeholder in value:
                used.add(placeholder)
                value = value.replace(placeholder, "")
        if "{" in value or "}" in value:
            raise ValueError("Only request/image/response placeholders are supported")
    if used != set(_PLACEHOLDERS):
        raise ValueError("Observer argv must explicitly reference request, image and response")
    for field in ("observer_timeout_seconds", "extract_timeout_seconds"):
        if not 0 < clip_capture._number(plan[field], field) <= 3600:
            raise ValueError("Timeout must be at most 3600 seconds")
    if (
        not isinstance(plan["ffmpeg"], str)
        or not plan["ffmpeg"].strip()
        or "\x00" in plan["ffmpeg"]
    ):
        raise ValueError("Expected an explicit ffmpeg executable")
    code = [
        Path(__file__),
        *(
            Path(module.__file__)
            for module in (clip_capture, clip_clock, clip_frames, observation_session)
        ),
        *resolved.values(),
        Path(launcher["resolved"]),
        *([Path(launcher["venv_config"])] if launcher["venv_config"] is not None else []),
    ]
    bindings += [(path, clip_capture._sha256(path), path.stat().st_size) for path in code]
    bindings.append((plan_path, clip_clock._sha(raw), len(raw)))
    protocol = {
        "prompt": observation_session.PROMPT,
        "response_schema": observation_session.RESPONSE_FIELDS,
        "request_schema": observation_session.MAPPED_REQUEST_SCHEMA,
    }
    frozen = {
        "schema": RUN_SCHEMA,
        "plan_sha256": clip_clock._sha(raw),
        "plan": plan,
        "protocol": protocol,
        "protocol_sha256": clip_clock._sha(json.dumps(protocol, sort_keys=True).encode()),
        "input_code_bindings": [{"path": str(p), "sha256": h, "bytes": n} for p, h, n in bindings],
        "observer_argv": command,
        "observer_launcher_binding": launcher,
        "full_pa_verified": False,
        "live_availability_verified": False,
        "notice": "Sequential 1x local replay. Scheduled input times are a fixed simulation clock; extraction, validation, process and acceptance delays are included. No model provider is selected implicitly.",
    }
    return out, capture_dir, cutoffs, command, bindings, frozen


def run_plan(plan_path, out, *, clock=time, runner=subprocess.run):
    """Run each exact cutoff once, preserving its original schedule even when the queue is late."""
    out, capture_dir, cutoffs, command, bindings, frozen = _prepare(plan_path, out)
    out.mkdir(parents=True, exist_ok=False)
    for child in ("frames", "outputs", "attempts"):
        (out / child).mkdir()
    _write(out / "plan.json", frozen["plan"])
    start_ns, start_utc_ns = clock.monotonic_ns(), clock.time_ns()
    frozen.update(started_monotonic_ns=start_ns, started_utc_ns=start_utc_ns)
    _write(out / "run_manifest.json", frozen)
    attempts, interrupted = [], False

    def stamp():
        now = clock.monotonic_ns()
        return {
            "monotonic_ns": now,
            "utc_ns": clock.time_ns(),
            "elapsed_seconds": (now - start_ns) / 1e9,
        }

    with (out / "events.jsonl").open("x", encoding="utf-8") as events:

        def event(kind, index, **extra):
            events.write(json.dumps({"event": kind, "index": index, **stamp(), **extra}) + "\n")
            events.flush()

        for index, cutoff in enumerate(cutoffs):
            delay_ns = math.ceil((cutoff - cutoffs[0]) * 1_000_000_000)
            scheduled = start_ns + delay_ns
            record = {
                "index": index,
                "cutoff_seconds_exact": str(cutoff),
                "status": "error",
                "scheduled_input_monotonic_ns": scheduled,
                "scheduled_input_utc_ns": start_utc_ns + delay_ns,
                "scheduled_offset_seconds_exact": str(cutoff - cutoffs[0]),
                "phase_timing_version": 1,
                "preparation_started": None,
                "input_bindings_verified": None,
                "frame_extracted": None,
                "request_ready": None,
                "observer_dispatch": None,
                "output_bindings_verified": None,
                "response_accepted": None,
                "observation_status": None,
                "errors": [],
            }
            try:
                while True:
                    remaining_ns = scheduled - clock.monotonic_ns()
                    if remaining_ns <= 0:
                        break
                    clock.sleep(min(0.1, remaining_ns / 1e9))
                record["preparation_started"] = stamp()
                event("preparation_started", index)
                _verify_launcher(frozen["observer_launcher_binding"])
                clip_frames._verify_files(bindings)
                record["input_bindings_verified"] = stamp()
                event("input_bindings_verified", index)
                frame_dir, session = (
                    out / "frames" / f"frame_{index:03d}",
                    out / "outputs" / f"cv_observation_{index:03d}",
                )
                extraction = clip_frames.extract_frame(
                    capture_dir=capture_dir,
                    source_seconds=cutoff,
                    out=frame_dir,
                    ffmpeg=frozen["plan"]["ffmpeg"],
                    timeout=frozen["plan"]["extract_timeout_seconds"],
                )
                if extraction.get("status") != "extracted":
                    raise ValueError("Frame extraction failed; no observation was submitted")
                record["frame_extracted"] = stamp()
                event("frame_extracted", index)
                request = observation_session.begin_mapped(frame_dir, session)
                actual = Fraction(request["source_time_seconds_exact"])
                if actual > cutoff or Fraction(request["requested_cutoff_seconds_exact"]) != cutoff:
                    raise ValueError("Mapped request violates the planned causal cutoff")
                record["actual_source_seconds_exact"] = str(actual)
                record["frame_ready"] = stamp()
                # Keep the legacy name while making the completed request stage explicit.
                record["request_ready"] = record["frame_ready"]
                event("request_ready", index)
                public = session / "request"
                response = public / "response.json"
                if response.exists() or response.is_symlink():
                    raise ValueError("Observer response must be fresh")
                argv = command.copy()
                for placeholder, name in _PLACEHOLDERS.items():
                    argv = [value.replace(placeholder, name) for value in argv]
                record["observer_dispatch"] = stamp()
                record["dispatch_lateness_seconds"] = (
                    record["observer_dispatch"]["monotonic_ns"] - scheduled
                ) / 1e9
                event("observer_dispatch", index)
                with (
                    (session / "observer.stdout.txt").open("xb") as stdout,
                    (session / "observer.stderr.txt").open("xb") as stderr,
                ):
                    _verify_launcher(frozen["observer_launcher_binding"])
                    try:
                        completed = runner(
                            argv,
                            cwd=public,
                            stdin=subprocess.DEVNULL,
                            stdout=stdout,
                            stderr=stderr,
                            shell=False,
                            check=False,
                            timeout=frozen["plan"]["observer_timeout_seconds"],
                        )
                    finally:
                        _verify_launcher(frozen["observer_launcher_binding"])
                record["observer_exit"] = stamp()
                record["observer_exit_code"] = completed.returncode
                if completed.returncode != 0:
                    raise RuntimeError(f"Observer process failed with exit {completed.returncode}")
                if not response.is_file() or response.is_symlink():
                    raise ValueError("Observer did not write a fresh regular response file")
                clip_frames._verify_files(bindings)
                record["output_bindings_verified"] = stamp()
                event("output_bindings_verified", index)
                result = observation_session.finish(session, response)
                record["response_accepted"] = stamp()
                record["accepted_latency_from_schedule_seconds"] = (
                    record["response_accepted"]["monotonic_ns"] - scheduled
                ) / 1e9
                record["observation_status"] = result["raw_response"]["status"]
                record["status"] = "accepted"
                event("response_accepted", index)
            except (Exception, KeyboardInterrupt) as exc:
                record["status"] = "error"
                record["errors"].append(f"{type(exc).__name__}: {exc}")
                interrupted = isinstance(exc, KeyboardInterrupt)
                event("error", index, message=record["errors"][-1])
            finally:
                record["attempt_finished"] = stamp()
                _write(out / "attempts" / f"{index:03d}.json", record)
                attempts.append(record)
            if interrupted:
                break
    accepted = sum(record["status"] == "accepted" for record in attempts)
    summary = {
        "schema": RUN_SCHEMA,
        "status": "interrupted"
        if interrupted
        else "completed"
        if accepted == len(cutoffs)
        else "completed_with_errors",
        "planned": len(cutoffs),
        "attempted": len(attempts),
        "accepted": accepted,
        "errors": len(attempts) - accepted,
        "elapsed_seconds": (clock.monotonic_ns() - start_ns) / 1e9,
        "full_pa_verified": False,
        "live_availability_verified": False,
    }
    _write(out / "summary.json", summary)
    return summary


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run_plan(args.plan, args.out)
    print(json.dumps(result, indent=2))
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

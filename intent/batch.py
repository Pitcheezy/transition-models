"""Run a few trusted local Python analysis jobs with auditable restart state.

The plan and Python programs are trusted local code, not a security sandbox. Declared
inputs/sources are hashed and declared outputs are restricted to new attempt folders.
Optional ``absent_inputs`` freeze missing files that may affect a job's fallback behavior.
Elapsed time measures subprocess execution only, never video-reader end-to-end latency.
No network, AI provider, or video acquisition is invoked by this module itself.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import json
import os
import re
import subprocess
import sys
import time
from collections.abc import Iterator
from pathlib import Path
from typing import Any

SCHEMA_VERSION = 1
_NAME = re.compile(r"[A-Za-z0-9][A-Za-z0-9_-]*\Z")
_MODULE = re.compile(r"[A-Za-z_]\w*(?:\.[A-Za-z_]\w*)*\Z")


class BatchError(ValueError):
    """A plan, artifact, or resume precondition is invalid."""


def _no_links(path: Path) -> None:
    for candidate in (path, *path.parents):
        is_junction = getattr(candidate, "is_junction", lambda: False)
        if candidate.is_symlink() or is_junction():
            raise BatchError(f"Symlink/junction path is not allowed: {candidate}")


def _absolute(path: str | Path, base: Path) -> Path:
    result = Path(path)
    if not result.is_absolute():
        result = base / result
    _no_links(result)
    return result.resolve()


def _sha(path: Path) -> str:
    _no_links(path)
    if not path.is_file():
        raise BatchError(f"Expected regular file: {path}")
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")


def _save_new(path: Path, value: Any) -> None:
    _no_links(path)
    with path.open("xb") as stream:
        stream.write(_json_bytes(value))


def _save_ledger(run_dir: Path, ledger: dict[str, Any]) -> None:
    target = run_dir / "ledger.json"
    temporary = run_dir / "ledger.next.json"
    _no_links(target)
    _no_links(temporary)
    # The ledger is the only replaceable artifact. Logs and outputs are immutable.
    with temporary.open("wb") as stream:
        stream.write(_json_bytes(ledger))
    os.replace(temporary, target)


def _read_json(path: Path) -> dict[str, Any]:
    _no_links(path)
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise BatchError(f"Expected a JSON object: {path}")
    return value


def _name(value: Any) -> str:
    if not isinstance(value, str) or not _NAME.fullmatch(value):
        raise BatchError(f"Invalid identifier: {value!r}")
    return value


def _relative_output(value: Any) -> str:
    if not isinstance(value, str) or not value:
        raise BatchError("Output paths must be nonempty strings")
    path = Path(value)
    # Reject Windows separators/drive syntax even when validated on another OS.
    if path.is_absolute() or path.drive or ":" in value or "\\" in value:
        raise BatchError(f"Output must be a portable relative path: {value}")
    if any(part in {"", ".", ".."} for part in value.split("/")):
        raise BatchError(f"Output traversal/empty component: {value}")
    reserved = {
        "con",
        "prn",
        "aux",
        "nul",
        *(f"com{i}" for i in range(1, 10)),
        *(f"lpt{i}" for i in range(1, 10)),
    }
    if any(
        part.endswith((" ", "."))
        or part.split(".")[0].casefold() in reserved
        or any(char in part for char in '*?"<>|')
        for part in path.parts
    ):
        raise BatchError(f"Output contains a reserved/nonportable path component: {value}")
    return path.as_posix()


def _entry_source(argv: list[str], project_root: Path) -> Path:
    if argv[0] == "-m":
        if len(argv) < 2 or not _MODULE.fullmatch(argv[1]):
            raise BatchError("Python -m requires a local module name")
        stem = project_root.joinpath(*argv[1].split("."))
        source = stem.with_suffix(".py")
        if not source.is_file():
            source = stem / "__main__.py"
    else:
        if argv[0].startswith("-") or not argv[0].endswith(".py"):
            raise BatchError("argv must start with a local .py script or -m local.module")
        source = _absolute(argv[0], project_root)
    _no_links(source)
    source = source.resolve()
    if not source.is_relative_to(project_root) or not source.is_file():
        raise BatchError(f"Python entry point must be a local project file: {source}")
    return source


def load_plan(path: Path) -> tuple[dict[str, Any], dict[str, Any]]:
    """Validate a plan and return its normalized content and frozen identity."""
    path = _absolute(path, Path.cwd())
    plan = _read_json(path)
    required = {"schema_version", "project_root", "inputs", "source_files", "config", "jobs"}
    allowed = required | {"absent_inputs"}
    if (
        not required.issubset(plan)
        or set(plan) - allowed
        or plan["schema_version"] != SCHEMA_VERSION
    ):
        raise BatchError(f"Plan requires v1 fields {sorted(required)}; absent_inputs is optional")
    root = _absolute(plan["project_root"], path.parent)
    if not root.is_dir():
        raise BatchError(f"Missing project_root: {root}")
    if not isinstance(plan["inputs"], dict) or not isinstance(plan["config"], dict):
        raise BatchError("inputs and config must be objects")
    inputs = {_name(key): str(_absolute(value, root)) for key, value in plan["inputs"].items()}
    absent_inputs = plan.get("absent_inputs", [])
    if not isinstance(absent_inputs, list) or not all(
        isinstance(value, str) and value for value in absent_inputs
    ):
        raise BatchError("absent_inputs must be a list of nonempty path strings")
    absent_paths = sorted({_absolute(value, root) for value in absent_inputs})
    for missing in absent_paths:
        if missing.exists():
            raise BatchError(f"Expected absent input now exists; use a NEW plan/run-dir: {missing}")
    if not isinstance(plan["source_files"], list):
        raise BatchError("source_files must be a list")
    sources = {_absolute(value, root) for value in plan["source_files"]}
    if not all(source.is_relative_to(root) for source in sources):
        raise BatchError("source_files must belong to project_root")
    if not isinstance(plan["jobs"], list) or not plan["jobs"]:
        raise BatchError("jobs must be a nonempty list")
    seen: dict[str, dict[str, str]] = {}
    jobs = []
    for job in plan["jobs"]:
        if not isinstance(job, dict) or set(job) - {"id", "argv", "outputs", "timeout_seconds"}:
            raise BatchError("Unknown job fields")
        if not {"id", "argv", "outputs"}.issubset(job):
            raise BatchError("A job requires id, argv, and outputs")
        job_id = _name(job["id"])
        if job_id in seen:
            raise BatchError(f"Duplicate job id: {job_id}")
        argv = job["argv"]
        if not isinstance(argv, list) or not argv or not all(isinstance(x, str) for x in argv):
            raise BatchError("argv must be a nonempty list of strings, never shell text")
        sources.add(_entry_source(argv, root))
        if not isinstance(job["outputs"], dict) or not job["outputs"]:
            raise BatchError("Each job must declare at least one output file")
        outputs = {_name(key): _relative_output(value) for key, value in job["outputs"].items()}
        paths = [Path(value.casefold()) for value in outputs.values()]
        if any(
            a == b or a.is_relative_to(b) or b.is_relative_to(a)
            for i, a in enumerate(paths)
            for b in paths[i + 1 :]
        ):
            raise BatchError("Output paths must be distinct and cannot contain each other")
        tokens = {f"{{input:{key}}}" for key in inputs}
        tokens.update(f"{{output:{key}}}" for key in outputs)
        tokens.update(f"{{job:{prior}:{key}}}" for prior, out in seen.items() for key in out)
        for token in argv:
            if ("{" in token or "}" in token) and token not in tokens:
                raise BatchError(f"Unknown/embedded placeholder: {token}")
        if any(f"{{output:{key}}}" not in argv for key in outputs):
            raise BatchError("Every declared output must occur as a standalone argv placeholder")
        timeout = job.get("timeout_seconds")
        if timeout is not None and (
            isinstance(timeout, bool)
            or not isinstance(timeout, (int, float))
            or not 0 < timeout < float("inf")
        ):
            raise BatchError("timeout_seconds must be positive and finite")
        seen[job_id] = outputs
        jobs.append({**job, "outputs": outputs})
    normalized = {
        **plan,
        "project_root": str(root),
        "inputs": inputs,
        "absent_inputs": [str(path) for path in absent_paths],
        "source_files": sorted(str(source) for source in sources),
        "jobs": jobs,
    }
    evidence = {
        "schema_version": SCHEMA_VERSION,
        "plan": normalized,
        "input_sha256": {key: _sha(Path(value)) for key, value in inputs.items()},
        "absent_input_state": {str(path): "absent" for path in absent_paths},
        "source_sha256": {str(source): _sha(source) for source in sorted(sources)},
        "runner_sha256": _sha(Path(__file__).resolve()),
        "python_executable": str(Path(sys.executable).resolve()),
        "python_version": sys.version,
    }
    evidence["fingerprint"] = hashlib.sha256(_json_bytes(evidence)).hexdigest()
    return normalized, evidence


def _validate_run_dir(run_dir: Path, plan: dict[str, Any]) -> Path:
    run_dir = _absolute(run_dir, Path.cwd())
    root = Path(plan["project_root"])
    roots = {root, *(parent for parent in run_dir.parents if (parent / ".git").exists())}
    for repository in roots:
        if run_dir.is_relative_to(repository):
            relative = run_dir.relative_to(repository)
            if len(relative.parts) < 2 or relative.parts[0] != "outputs":
                raise BatchError("Inside a project, run-dir must be a new child of outputs/")
    for value in [*plan["inputs"].values(), *plan["source_files"], *plan["absent_inputs"]]:
        if Path(value).is_relative_to(run_dir):
            raise BatchError("run-dir cannot contain an input, source, or absent-input path")
    return run_dir


@contextlib.contextmanager
def _lock(run_dir: Path) -> Iterator[None]:
    """Use an OS-owned lock, which is released even after process termination."""
    path = run_dir / ".batch.lock"
    _no_links(path)
    with path.open("a+b") as stream:
        if stream.tell() == 0:
            stream.write(b"0")
            stream.flush()
        stream.seek(0)
        try:
            if os.name == "nt":
                import msvcrt

                msvcrt.locking(stream.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl

                fcntl.flock(stream.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as exc:
            raise BatchError("Another process holds this run's lock") from exc
        try:
            yield
        finally:
            stream.seek(0)
            if os.name == "nt":
                msvcrt.locking(stream.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(stream.fileno(), fcntl.LOCK_UN)


def _validate_ledger(
    ledger: dict[str, Any], plan: dict[str, Any], identity: dict[str, Any]
) -> None:
    if (
        ledger.get("schema_version") != SCHEMA_VERSION
        or ledger.get("fingerprint") != identity["fingerprint"]
    ):
        raise BatchError("Ledger identity mismatch")
    if not isinstance(ledger.get("jobs"), dict) or set(ledger["jobs"]) != {
        job["id"] for job in plan["jobs"]
    }:
        raise BatchError("Ledger jobs do not match the plan")
    for state in ledger["jobs"].values():
        if not isinstance(state, dict) or state.get("status") not in {
            "pending",
            "running",
            "succeeded",
            "failed",
            "interrupted",
        }:
            raise BatchError("Invalid ledger job state")
        attempts = state.get("attempts")
        if not isinstance(attempts, list) or any(
            not isinstance(attempt, dict) for attempt in attempts
        ):
            raise BatchError("Invalid ledger attempts")
        if (not attempts) != (state["status"] == "pending"):
            raise BatchError("Ledger status/attempts disagree")
        if attempts and attempts[-1].get("status") != state["status"]:
            raise BatchError("Ledger latest attempt/status disagree")


def _verify_outputs(run_dir: Path, job: dict[str, Any], state: dict[str, Any]) -> dict[str, str]:
    attempt = state["attempts"][-1]
    if not isinstance(attempt.get("outputs"), dict) or set(attempt["outputs"]) != set(
        job["outputs"]
    ):
        raise BatchError("Saved successful job has incomplete output records")
    expected_dir = (
        run_dir / "jobs" / job["id"] / f"attempt-{len(state['attempts']):04d}" / "artifacts"
    )
    result = {}
    for key, record in attempt["outputs"].items():
        if not isinstance(record, dict) or set(record) != {"path", "sha256"}:
            raise BatchError("Invalid saved output record")
        path = _absolute(record["path"], run_dir)
        expected = expected_dir / job["outputs"][key]
        if path != expected or _sha(path) != record["sha256"]:
            raise BatchError(f"Saved output missing, changed, or outside run-dir: {path}")
        result[key] = str(path)
    return result


def _same_identity(plan_path: Path, expected: dict[str, Any]) -> None:
    _, current = load_plan(plan_path)
    if current != expected:
        raise BatchError("Plan/config, inputs, source, or Python changed; choose a NEW run-dir")


def check_plan(plan_path: Path, run_dir: Path) -> dict[str, Any]:
    """Check declarations, and identity/artifacts of an existing run, without executing."""
    plan, identity = load_plan(plan_path)
    run_dir = _validate_run_dir(run_dir, plan)
    if run_dir.exists():
        with _lock(run_dir):
            if _read_json(run_dir / "manifest.json") != identity:
                raise BatchError("Existing run identity differs; choose a NEW run-dir")
            ledger = _read_json(run_dir / "ledger.json")
            _validate_ledger(ledger, plan, identity)
            for job in plan["jobs"]:
                state = ledger["jobs"][job["id"]]
                if state["status"] == "succeeded":
                    _verify_outputs(run_dir, job, state)
    return {
        "fingerprint": identity["fingerprint"],
        "jobs": len(plan["jobs"]),
        "run_dir": str(run_dir),
        "executed": False,
    }


def execute_plan(plan_path: Path, run_dir: Path, *, resume: bool = False) -> dict[str, Any]:
    """Execute jobs serially; resume requires an identical manifest and intact artifacts."""
    plan_path = _absolute(plan_path, Path.cwd())
    plan, identity = load_plan(plan_path)
    run_dir = _validate_run_dir(run_dir, plan)
    if resume:
        if not run_dir.is_dir():
            raise BatchError("resume requires an existing run directory")
    else:
        run_dir.mkdir(parents=True, exist_ok=False)
    with _lock(run_dir):
        ledger = None
        if resume:
            if _read_json(run_dir / "manifest.json") != identity:
                raise BatchError(
                    "Plan/config, inputs, source, or Python changed; use a NEW run-dir"
                )
            if (run_dir / "ledger.json").exists():
                ledger = _read_json(run_dir / "ledger.json")
                _validate_ledger(ledger, plan, identity)
        else:
            _save_new(run_dir / "manifest.json", identity)
        if ledger is None:
            # A valid frozen manifest may survive a death before the initial ledger.
            # Recreate only missing state; never replace invalid existing state.
            ledger = {
                "schema_version": SCHEMA_VERSION,
                "fingerprint": identity["fingerprint"],
                "timing_scope": "subprocess_execution_only_not_video_end_to_end",
                "jobs": {job["id"]: {"status": "pending", "attempts": []} for job in plan["jobs"]},
            }
            _save_ledger(run_dir, ledger)
        resolved: dict[str, str] = {
            f"{{input:{key}}}": value for key, value in plan["inputs"].items()
        }
        # Audit all successful jobs before starting any work on resume.
        for job in plan["jobs"]:
            state = ledger["jobs"][job["id"]]
            if state["status"] == "succeeded":
                outputs = _verify_outputs(run_dir, job, state)
                resolved.update(
                    {f"{{job:{job['id']}:{key}}}": value for key, value in outputs.items()}
                )
        for job in plan["jobs"]:
            state = ledger["jobs"][job["id"]]
            if state["status"] == "succeeded":
                continue
            _same_identity(plan_path, identity)
            if state["status"] == "running":
                state["attempts"][-1]["status"] = state["status"] = "interrupted"
            while True:
                attempt_dir = (
                    run_dir / "jobs" / job["id"] / f"attempt-{len(state['attempts']) + 1:04d}"
                )
                _no_links(attempt_dir)
                if not attempt_dir.exists():
                    break
                # Preserve an unrecorded directory from an interrupted older writer.
                # Recording each occupied slot keeps attempt ordinals and paths aligned.
                state["attempts"].append(
                    {
                        "status": "interrupted",
                        "argv": None,
                        "elapsed_seconds": None,
                        "returncode": None,
                        "outputs": {},
                        "error": "Orphan attempt path preserved without executing or trusting its contents",
                    }
                )
                state["status"] = "interrupted"
                _save_ledger(run_dir, ledger)
            outputs = {
                key: attempt_dir / "artifacts" / value for key, value in job["outputs"].items()
            }
            replacements = {
                **resolved,
                **{f"{{output:{key}}}": str(value) for key, value in outputs.items()},
            }
            argv = [sys.executable, *(replacements.get(token, token) for token in job["argv"])]
            attempt: dict[str, Any] = {
                "status": "running",
                "argv": argv,
                "elapsed_seconds": None,
                "returncode": None,
                "stdout": str((attempt_dir / "stdout.log").relative_to(run_dir)),
                "stderr": str((attempt_dir / "stderr.log").relative_to(run_dir)),
                "outputs": {},
            }
            state["attempts"].append(attempt)
            state["status"] = "running"
            # Reserve the attempt durably before creating its directory or artifacts.
            # A process death anywhere after this write consumes the slot on resume.
            _save_ledger(run_dir, ledger)
            started: float | None = None
            try:
                attempt_dir.mkdir(parents=True, exist_ok=False)
                for path in outputs.values():
                    path.parent.mkdir(parents=True, exist_ok=True)
                    _no_links(path)
                    if path.exists():
                        raise BatchError(f"Refusing output overwrite: {path}")
                with (
                    (attempt_dir / "stdout.log").open("xb") as stdout,
                    (attempt_dir / "stderr.log").open("xb") as stderr,
                ):
                    started = time.perf_counter()
                    completed = subprocess.run(
                        argv,
                        cwd=plan["project_root"],
                        shell=False,
                        stdout=stdout,
                        stderr=stderr,
                        timeout=job.get("timeout_seconds"),
                        check=False,
                    )
                attempt["returncode"] = completed.returncode
                attempt["elapsed_seconds"] = time.perf_counter() - started
                if completed.returncode:
                    raise BatchError(f"Subprocess exited with code {completed.returncode}")
                _same_identity(plan_path, identity)
                for previous in plan["jobs"]:
                    previous_state = ledger["jobs"][previous["id"]]
                    if previous_state["status"] == "succeeded":
                        _verify_outputs(run_dir, previous, previous_state)
                attempt["outputs"] = {
                    key: {"path": str(path.relative_to(run_dir)), "sha256": _sha(path)}
                    for key, path in outputs.items()
                }
                attempt["status"] = state["status"] = "succeeded"
                resolved.update(
                    {f"{{job:{job['id']}:{key}}}": str(value) for key, value in outputs.items()}
                )
            except (Exception, KeyboardInterrupt) as exc:
                if attempt["elapsed_seconds"] is None and started is not None:
                    attempt["elapsed_seconds"] = time.perf_counter() - started
                attempt["status"] = state["status"] = (
                    "interrupted" if isinstance(exc, KeyboardInterrupt) else "failed"
                )
                attempt["error"] = f"{type(exc).__name__}: {exc}"
                _save_ledger(run_dir, ledger)
                if isinstance(exc, KeyboardInterrupt):
                    raise
                return ledger
            _save_ledger(run_dir, ledger)
        return ledger


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    commands = parser.add_subparsers(dest="command", required=True)
    template = commands.add_parser(
        "plan", help="Write an editable plan template; does not run jobs"
    )
    template.add_argument("--project-root", type=Path, required=True)
    template.add_argument("--input", action="append", default=[], metavar="NAME=PATH")
    template.add_argument("--absent-input", action="append", default=[], metavar="PATH")
    template.add_argument("--source", action="append", default=[])
    template.add_argument("--output", type=Path, required=True)
    for command in ("check", "run", "resume"):
        sub = commands.add_parser(command)
        sub.add_argument("--plan", type=Path, required=True)
        sub.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "plan":
            inputs = {}
            for value in args.input:
                key, separator, path = value.partition("=")
                if not separator or not path or key in inputs:
                    raise BatchError("--input requires a unique NAME=PATH")
                inputs[_name(key)] = path
            _save_new(
                args.output,
                {
                    "schema_version": SCHEMA_VERSION,
                    "project_root": str(args.project_root.resolve()),
                    "inputs": inputs,
                    "absent_inputs": args.absent_input,
                    "source_files": args.source,
                    "config": {},
                    "jobs": [],
                },
            )
            print("Plan template written. Fill jobs before check/run.")
            return 0
        if args.command == "check":
            result = check_plan(args.plan, args.run_dir)
        else:
            result = execute_plan(args.plan, args.run_dir, resume=args.command == "resume")
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return int(
            "jobs" in result
            and isinstance(result["jobs"], dict)
            and any(job["status"] != "succeeded" for job in result["jobs"].values())
        )
    except (BatchError, OSError, json.JSONDecodeError) as exc:
        print(f"batch: {exc}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    raise SystemExit(main())

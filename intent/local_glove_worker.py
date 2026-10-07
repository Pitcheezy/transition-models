"""One persistent spawn worker for a bounded, sequential local replay.

The runner is a trusted local orchestration adapter, not a filesystem sandbox.
Its deadline gates worker response publication; the unchanged observation loop
performs additional verification afterwards. No end-to-end deadline is claimed.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import multiprocessing
import os
import subprocess
import sys
import threading
import time
import uuid
from pathlib import Path

from intent import local_glove_detector as detector
from intent import local_glove_observer as observer
from intent import local_glove_observer_report as observer_report
from intent import observation_loop, observation_session
from intent.replay import _no_links

EXECUTION_MODE = "persistent_spawn_worker"
RECEIPT_SCHEMA = "local_glove_worker_request_v1"
CONTROL_SCHEMA = "local_glove_worker_control_v1"
MAX_CONTROL_BYTES = 4096
_OUTPUT_NAMES = ("local_detector_config.json", "local_detector_result.json", "response.json")


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _encode(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def _write(path, raw):
    _no_links(path)
    with path.open("xb") as stream:
        stream.write(raw)


def _read(path):
    _no_links(path)
    if not path.is_file():
        raise ValueError("Expected a regular worker input/artifact")
    return path.read_bytes()


def _send(connection, value):
    raw = _encode(value)
    if len(raw) > MAX_CONTROL_BYTES:
        raise ValueError("Worker control message is too large")
    connection.send_bytes(raw)


def _receive(connection):
    return observer._json(connection.recv_bytes(MAX_CONTROL_BYTES))


def _worker_main(connection, staging_dir, engine_factory):
    """Run in the child; only private fixed-name request directories are writable."""
    engine, engine_key, config_sha = None, None, None
    next_index, engine_instances = 0, 0

    def cached_factory(model_id, weights, weights_sha256, *, device, threads):
        nonlocal engine, engine_key, engine_instances
        key = (model_id, str(weights), weights_sha256, device, threads)
        if engine is None:
            engine = engine_factory(
                model_id, weights, weights_sha256, device=device, threads=threads
            )
            engine_key = key
            engine_instances += 1
        elif key != engine_key:
            raise ValueError("Persistent engine arguments changed")
        return engine

    try:
        while True:
            message = _receive(connection)
            if message == {"schema": CONTROL_SCHEMA, "kind": "close"}:
                return
            if (
                message.get("schema") != CONTROL_SCHEMA
                or message.get("kind") != "request"
                or type(message.get("index")) is not int
                or message["index"] != next_index
            ):
                raise ValueError("Unexpected worker control request")
            directory = Path(staging_dir) / f"request_{next_index:03d}"
            reused = engine is not None
            reply = {
                key: message[key]
                for key in (
                    "index",
                    "nonce",
                    "observation_id",
                    "request_sha256",
                    "image_sha256",
                    "config_sha256",
                )
            }
            reply.update(
                schema=CONTROL_SCHEMA,
                kind="result",
                status="error",
                worker_pid=os.getpid(),
                engine_reused=reused,
                engine_instances=engine_instances,
                error=None,
            )
            try:
                for name, key in (
                    ("request.json", "request_sha256"),
                    ("image.jpg", "image_sha256"),
                    ("worker_input_config.json", "config_sha256"),
                ):
                    if _sha(_read(directory / name)) != message[key]:
                        raise ValueError("Private worker input SHA256 mismatch")
                request = observer._json(_read(directory / "request.json"))
                if request.get("observation_id") != message["observation_id"]:
                    raise ValueError("Private worker observation identity mismatch")
                if config_sha is None:
                    config_sha = message["config_sha256"]
                elif config_sha != message["config_sha256"]:
                    raise ValueError("Persistent worker config bytes changed")
                observer.observe(
                    directory / "request.json",
                    directory / "image.jpg",
                    directory / "worker_input_config.json",
                    directory / "response.json",
                    engine_factory=cached_factory,
                )
                reply.update(status="completed", engine_instances=engine_instances)
            except (Exception, KeyboardInterrupt) as exc:
                reply.update(
                    error={"type": type(exc).__name__, "message": str(exc)[:500]},
                    engine_instances=engine_instances,
                )
                _send(connection, reply)
                return
            _send(connection, reply)
            next_index += 1
    finally:
        connection.close()


def _command(argv, cwd):
    if not isinstance(argv, (list, tuple)) or len(argv) != 11:
        raise ValueError("Expected explicit local observer module command")
    if Path(argv[0]).resolve() != Path(sys.executable).resolve() or list(argv[1:3]) != [
        "-m",
        "intent.local_glove_observer",
    ]:
        raise ValueError("Persistent runner requires this interpreter and local observer module")
    options = {}
    for name, value in zip(argv[3::2], argv[4::2], strict=True):
        if name not in ("--request", "--image", "--config", "--response") or name in options:
            raise ValueError("Unexpected or repeated observer argument")
        if not isinstance(value, str) or not value:
            raise ValueError("Invalid observer argument")
        options[name] = value
    if any(
        options.get(key) != value
        for key, value in (
            ("--request", "request.json"),
            ("--image", "image.jpg"),
            ("--response", "response.json"),
        )
    ):
        raise ValueError("Worker requires fixed request/image/response filenames")
    config = Path(options["--config"])
    if not config.is_absolute():
        raise ValueError("Worker config path must be explicitly absolute")
    public = Path(cwd).absolute()
    _no_links(public)
    if not public.is_dir():
        raise ValueError("Expected existing public request directory")
    _no_links(config)
    return public, config.resolve()


def _validate_staged(directory, raw_request, raw_image, raw_config):
    request, config = observer._json(raw_request), observer._json(raw_config)
    observer._request(request, raw_image)
    observer._config(config)
    for name, raw in (
        ("request.json", raw_request),
        ("image.jpg", raw_image),
        ("worker_input_config.json", raw_config),
        ("local_detector_config.json", raw_config),
    ):
        if _read(directory / name) != raw:
            raise ValueError("Private input/config snapshot bytes changed")
    artifacts = {name: _read(directory / name) for name in _OUTPUT_NAMES}
    sidecar = observer._json(artifacts["local_detector_result.json"])
    response = observer._json(artifacts["response.json"])
    if (
        sidecar.get("schema") != observer.SIDECAR_SCHEMA
        or sidecar.get("status") != "accepted"
        or sidecar.get("errors") != []
        or sidecar.get("observation_id") != request["observation_id"]
        or sidecar.get("configuration") != config
        or sidecar.get("config_snapshot_file") != observer.CONFIG_SNAPSHOT_NAME
        or any(sidecar.get(flag) is not False for flag in observer_report._FALSE_FLAGS)
    ):
        raise ValueError("Untrusted worker sidecar contract/identity")
    expected_hashes = {
        "request_sha256": _sha(raw_request),
        "image_sha256": _sha(raw_image),
        "config_sha256": _sha(raw_config),
        "response_sha256": _sha(artifacts["response.json"]),
    }
    if any(sidecar.get(key) != value for key, value in expected_hashes.items()):
        raise ValueError("Worker sidecar file SHA256 mismatch")
    prediction = observer._prediction(sidecar.get("engine_response"), request, config)
    if (
        sidecar.get("selection_status") != prediction["selection_status"]
        or sidecar.get("candidate") != prediction["candidate"]
    ):
        raise ValueError("Worker candidate selection mismatch")
    observation_session._validate_response(response, request)
    expected_status = (
        "unavailable" if prediction["selection_status"] == "no_candidate" else "unknown"
    )
    if (
        response["status"] != expected_status
        or response["mitt"] is not None
        or response["visibility"] != "unknown"
        or response["pose"] != "unknown"
    ):
        raise ValueError("Generic glove cannot become a verified mitt response")
    observer_report._inner_timing(sidecar)
    return artifacts


class PersistentGloveRunner:
    """Subprocess-compatible callback with one lazy child and no restart/retry.

    Injected worker_target/engine_factory are for synthetic tests. Normal use fixes
    both defaults. The worker never receives a public output path.
    """

    def __init__(
        self,
        staging_dir,
        *,
        context=None,
        worker_target=_worker_main,
        engine_factory=detector.LocalGloveDetector,
        clock=time,
        shutdown_timeout=5,
    ):
        self.staging_dir = Path(staging_dir).absolute()
        _no_links(self.staging_dir)
        self.context = context or multiprocessing.get_context("spawn")
        if self.context.get_start_method() != "spawn":
            raise ValueError("Persistent worker must use spawn")
        if (
            type(shutdown_timeout) not in (int, float)
            or not math.isfinite(shutdown_timeout)
            or not 0 < shutdown_timeout <= 30
        ):
            raise ValueError("Shutdown timeout must be finite and bounded")
        self.worker_target, self.engine_factory = worker_target, engine_factory
        self.clock, self.shutdown_timeout = clock, shutdown_timeout
        self._state, self._initialized = "new", False
        self._process, self._connection, self._events = None, None, None
        self._signature, self._index, self._completed = None, 0, 0
        self._ids, self._lock = set(), threading.Lock()
        self._exit_confirmed = False
        self._closed = False

    def __enter__(self):
        return self

    def __exit__(self, *_):
        self.close()

    def _now(self):
        value = self.clock.monotonic_ns()
        if type(value) is not int or value < 0:
            raise ValueError("Invalid parent monotonic clock")
        return value

    def _initialize(self):
        if self._initialized:
            return
        self.staging_dir.mkdir(parents=False, exist_ok=False)
        _write(
            self.staging_dir / "execution.json",
            _encode(
                {
                    "schema": "local_glove_worker_execution_v1",
                    "execution_mode": EXECUTION_MODE,
                    "start_method": "spawn",
                    "max_inflight": 1,
                    "lazy_start": True,
                    "restart_allowed": False,
                    "retry_allowed": False,
                    "deadline_scope": "runner entry through parent response publication; cleanup/audit and outer-loop verification are additional",
                    "outer_observer_process_scope": "persistent-worker request transaction, not worker process lifetime",
                    "clock_contract": "parent monotonic durations and adapter perf_counter durations; no cross-clock absolute subtraction",
                }
            ),
        )
        self._events = (self.staging_dir / "lifecycle.jsonl").open("x", encoding="utf-8")
        self._initialized = True
        self._event("initialized")

    def _event(self, event, **values):
        if self._events is not None:
            self._events.write(
                json.dumps({"event": event, "monotonic_ns": self._now(), **values}, allow_nan=False)
                + "\n"
            )
            self._events.flush()

    def _deadline(self, deadline, argv, timeout):
        now = self._now()
        if now >= deadline:
            raise subprocess.TimeoutExpired(argv, timeout)
        return now

    def _spawn(self):
        parent, child = self.context.Pipe(duplex=True)
        self._connection = parent
        self._process = self.context.Process(
            target=self.worker_target,
            args=(child, self.staging_dir, self.engine_factory),
            daemon=True,
        )
        try:
            self._process.start()
        finally:
            child.close()
        self._state = "ready"
        self._event("worker_started", worker_pid=self._process.pid)

    def _stop(self, *, force):
        process = self._process
        if process is None or process.pid is None:
            if self._connection is not None:
                self._connection.close()
            self._exit_confirmed = True
            return
        if process.is_alive() and not force:
            try:
                _send(self._connection, {"schema": CONTROL_SCHEMA, "kind": "close"})
            except (OSError, EOFError):
                force = True
        if process.is_alive() and force:
            process.terminate()
        process.join(self.shutdown_timeout)
        if process.is_alive():
            process.kill()
            process.join(self.shutdown_timeout)
        self._exit_confirmed = not process.is_alive() and process.exitcode is not None
        self._event(
            "worker_exit",
            worker_pid=process.pid,
            exitcode=process.exitcode,
            confirmed=self._exit_confirmed,
        )
        if self._connection is not None:
            self._connection.close()
        if not self._exit_confirmed:
            raise RuntimeError(
                "Worker exit could not be confirmed; publication and restart disabled"
            )

    def _fail(self, published_response=None, prepared_response=None):
        self._state = "failed"
        try:
            if published_response is not None:
                _no_links(published_response)
                if published_response.exists():
                    if not os.path.samefile(published_response, prepared_response):
                        raise ValueError("Published response was replaced; foreign file preserved")
                    published_response.unlink()
        finally:
            # A locked/replaced response must never keep a timed-out child alive.
            self._stop(force=True)

    def __call__(
        self, argv, *, cwd, timeout, stdin=None, stdout=None, stderr=None, shell=False, check=False
    ):
        if self._closed:
            raise RuntimeError("Worker runner is closed")
        if shell or check or stdin not in (None, subprocess.DEVNULL):
            raise ValueError("Unsupported subprocess invocation options")
        if type(timeout) not in (int, float) or not math.isfinite(timeout) or timeout <= 0:
            raise ValueError("A finite explicit observer timeout is required")
        started = self._now()
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("Only one worker request may be in flight")
        deadline = started + math.ceil(timeout * 1e9)
        receipt, directory, published_response, prepared_response = None, None, None, None
        try:
            if self._closed:
                raise RuntimeError("Worker runner is closed")
            self._initialize()
            index = self._index
            self._index += 1
            directory = self.staging_dir / f"request_{index:03d}"
            directory.mkdir(exist_ok=False)
            receipt = {
                "schema": RECEIPT_SCHEMA,
                "execution_mode": EXECUTION_MODE,
                "index": index,
                "status": "error",
                "started_monotonic_ns": started,
                "deadline_monotonic_ns": deadline,
                "timeout_seconds": timeout,
                "spawned_this_request": False,
                "ipc_sent": False,
                "ipc_received": False,
                "published": False,
                "engine_reused": None,
                "worker_pid": None,
                "error": None,
            }
            if self._state == "failed":
                receipt["status"] = "blocked_after_failure"
                raise RuntimeError("Worker permanently failed; automatic restart/retry disabled")
            public, config_path = _command(argv, cwd)
            if (
                public == self.staging_dir
                or public.is_relative_to(self.staging_dir)
                or self.staging_dir.is_relative_to(public)
            ):
                raise ValueError("Public request and worker staging directories must not overlap")
            for name in _OUTPUT_NAMES:
                path = public / name
                _no_links(path)
                if path.exists():
                    raise FileExistsError("Public observer outputs must be fresh")
            paths = (public / "request.json", public / "image.jpg", config_path)
            raw_request, raw_image, raw_config = (_read(path) for path in paths)
            request = observer._json(raw_request)
            observer._request(request, raw_image)
            identity = request["observation_id"]
            if identity in self._ids:
                raise ValueError("Observation identity was already submitted")
            self._ids.add(identity)
            signature = (str(config_path), _sha(raw_config), tuple(argv))
            if self._signature is None:
                self._signature = signature
            elif self._signature != signature:
                raise ValueError("Persistent worker requires identical config bytes and arguments")
            for name, raw in (
                ("request.json", raw_request),
                ("image.jpg", raw_image),
                ("worker_input_config.json", raw_config),
            ):
                _write(directory / name, raw)
            nonce = uuid.uuid4().hex
            message = {
                "schema": CONTROL_SCHEMA,
                "kind": "request",
                "index": index,
                "nonce": nonce,
                "observation_id": identity,
                "request_sha256": _sha(raw_request),
                "image_sha256": _sha(raw_image),
                "config_sha256": _sha(raw_config),
            }
            receipt.update(
                {key: value for key, value in message.items() if key not in ("schema", "kind")}
            )
            self._deadline(deadline, argv, timeout)
            if self._process is None:
                self._spawn()
                receipt["spawned_this_request"] = True
            receipt["worker_pid"] = self._process.pid
            self._deadline(deadline, argv, timeout)
            if not self._process.is_alive():
                raise RuntimeError("Worker exited before dispatch")
            _send(self._connection, message)
            receipt.update(ipc_sent=True, ipc_sent_monotonic_ns=self._now())
            self._event("request_sent", index=index, nonce=nonce)
            remaining = max(0, (deadline - self._now()) / 1e9)
            if not self._connection.poll(remaining):
                raise subprocess.TimeoutExpired(argv, timeout)
            self._deadline(deadline, argv, timeout)
            reply = _receive(self._connection)
            receipt.update(ipc_received=True, ipc_received_monotonic_ns=self._now())
            self._deadline(deadline, argv, timeout)
            if (
                reply.get("schema") != CONTROL_SCHEMA
                or reply.get("kind") != "result"
                or type(reply.get("index")) is not int
                or any(
                    reply.get(key) != message[key]
                    for key in (
                        "index",
                        "nonce",
                        "observation_id",
                        "request_sha256",
                        "image_sha256",
                        "config_sha256",
                    )
                )
                or type(reply.get("worker_pid")) is not int
                or reply["worker_pid"] != self._process.pid
            ):
                raise ValueError("Worker IPC response identity/nonce/SHA mismatch")
            if reply.get("status") != "completed":
                raise RuntimeError("Worker reported an observation failure")
            if (
                reply.get("error") is not None
                or reply.get("engine_reused") is not (self._completed > 0)
                or type(reply.get("engine_instances")) is not int
                or reply["engine_instances"] != 1
            ):
                raise ValueError("Worker engine reuse receipt mismatch")
            receipt.update(
                engine_reused=reply["engine_reused"], engine_instances=reply["engine_instances"]
            )
            artifacts = _validate_staged(directory, raw_request, raw_image, raw_config)
            self._deadline(deadline, argv, timeout)
            for path, expected in zip(paths, (raw_request, raw_image, raw_config), strict=True):
                if _read(path) != expected:
                    raise ValueError("Public observer inputs changed before publication")
            prepared = directory / "parent_verified"
            prepared.mkdir(exist_ok=False)
            for name, raw in artifacts.items():
                _write(prepared / name, raw)
            receipt["artifact_sha256"] = {name: _sha(raw) for name, raw in artifacts.items()}
            self._deadline(deadline, argv, timeout)
            for name in _OUTPUT_NAMES:
                destination = public / name
                _no_links(destination)
                self._deadline(deadline, argv, timeout)
                # Same-filesystem hard links provide atomic no-overwrite publication
                # of complete parent-owned copies, separate from child-produced files.
                os.link(prepared / name, destination)
                if name == "response.json":
                    published_response, prepared_response = destination, prepared / name
                publication_ns = self._deadline(deadline, argv, timeout)
            receipt.update(
                published=True, publication_monotonic_ns=publication_ns, status="completed"
            )
            self._event("response_published", index=index, nonce=nonce)
            return subprocess.CompletedProcess(argv, 0)
        except (Exception, KeyboardInterrupt) as exc:
            if receipt is not None:
                receipt["error"] = {"type": type(exc).__name__, "message": str(exc)[:500]}
                if receipt["status"] != "blocked_after_failure":
                    receipt["status"] = "error"
                receipt["published"] = False
            try:
                self._fail(published_response, prepared_response)
            except (Exception, KeyboardInterrupt) as cleanup:
                if receipt is not None:
                    receipt["cleanup_error"] = {
                        "type": type(cleanup).__name__,
                        "message": str(cleanup)[:500],
                    }
                raise
            raise
        finally:
            try:
                if receipt is not None:
                    finished = self._now()
                    receipt.update(
                        finished_monotonic_ns=finished,
                        elapsed_seconds=(finished - started) / 1e9,
                        worker_exit_confirmed=self._exit_confirmed,
                    )
                    try:
                        _write(directory / "request_receipt.json", _encode(receipt))
                        if receipt["status"] == "completed":
                            self._completed += 1
                    except (Exception, KeyboardInterrupt):
                        self._fail(published_response, prepared_response)
                        raise
            finally:
                self._lock.release()

    def close(self):
        """Close once and record confirmed worker exit, including failed runs."""
        if self._closed:
            return
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("Cannot close a worker with a request in flight")
        try:
            if not self._initialized:
                if not self.staging_dir.parent.is_dir():
                    self._closed = True
                    return
                self._initialize()
            previous_state = self._state
            self._stop(force=self._state == "failed")
            _write(
                self.staging_dir / "lifecycle_final.json",
                _encode(
                    {
                        "schema": "local_glove_worker_lifecycle_v1",
                        "execution_mode": EXECUTION_MODE,
                        "status": "closed",
                        "prior_state": previous_state,
                        "requests_received": self._index,
                        "requests_completed": self._completed,
                        "worker_spawned": self._process is not None,
                        "worker_pid": self._process.pid if self._process is not None else None,
                        "worker_exitcode": self._process.exitcode
                        if self._process is not None
                        else None,
                        "worker_exit_confirmed": self._exit_confirmed,
                        "finished_monotonic_ns": self._now(),
                    }
                ),
            )
            self._state, self._closed = "closed", True
        finally:
            if self._events is not None:
                self._events.close()
                self._events = None
            if self._process is not None and self._exit_confirmed:
                self._process.close()
            self._lock.release()


def run_worker_plan(plan_path, out):
    """Use the unchanged replay loop with explicitly frozen persistent-worker code."""
    plan_path, out = Path(plan_path).absolute(), Path(out).absolute()
    _no_links(out)
    if out.exists():
        raise FileExistsError("Run output must be a new directory")
    plan = observer._json(_read(plan_path))
    files = plan.get("observer_code_files")
    if not isinstance(files, list) or any(not isinstance(value, str) for value in files):
        raise ValueError("Worker plan must declare its implementation files")
    declared = {(plan_path.parent / value).resolve() for value in files}
    required = {
        Path(module.__file__).resolve() for module in (observer, detector, observer_report)
    } | {Path(__file__).resolve()}
    if not required.issubset(declared):
        raise ValueError(
            "Freeze worker, observer, detector and observer-report modules in the plan"
        )
    with PersistentGloveRunner(out / "worker_private") as runner:
        return observation_loop.run_plan(plan_path, out, runner=runner)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run_worker_plan(args.plan, args.out)
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0 if result["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

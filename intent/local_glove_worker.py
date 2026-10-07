"""One persistent spawn worker for a bounded, sequential local replay.

The runner is a trusted local orchestration adapter, not a filesystem sandbox.
Its deadline gates worker response publication; the unchanged observation loop
performs additional verification afterwards. No end-to-end deadline is claimed.
"""

from __future__ import annotations

import argparse
import hashlib
import io
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
WARMUP_COUNT = 5
WARMUP_SIZE = (1280, 720)
STARTUP_SCHEMA = "local_glove_worker_startup_v1"
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


def _startup(directory, config_raw, prepare_id, cached_factory):
    """Load once and warm only on a generated black frame, never a study request."""
    from PIL import Image

    started = time.perf_counter_ns()
    result = {
        "schema": STARTUP_SCHEMA,
        "prepare_id": prepare_id,
        "status": "failed",
        "config_sha256": _sha(config_raw),
        "clock": "perf_counter_ns",
        "started_perf_counter_ns": started,
        "warmup_source": "generated_black_rgb",
        "warmup_size": list(WARMUP_SIZE),
        "warmup_count_planned": WARMUP_COUNT,
        "study_frame_inputs": 0,
        "warmups": [],
        "error": None,
    }
    try:
        config = observer._json(config_raw)
        weights = observer._config(config)
        result["configuration"] = config
        load_started = time.perf_counter_ns()
        engine = cached_factory(
            config["model_id"],
            weights,
            config["weights_sha256"],
            device=config["device"],
            threads=config["threads"],
        )
        engine.load()
        result["model_load_seconds"] = (time.perf_counter_ns() - load_started) / 1e9
        buffer = io.BytesIO()
        Image.new("RGB", WARMUP_SIZE, (0, 0, 0)).save(
            buffer, format="JPEG", quality=90, subsampling=0, optimize=False, progressive=False
        )
        image_raw = buffer.getvalue()
        image_sha = _sha(image_raw)
        _write(directory / "warmup_black.jpg", image_raw)
        result["warmup_image_sha256"] = image_sha
        for index in range(WARMUP_COUNT):
            begin = time.perf_counter_ns()
            prediction = engine.predict(
                image_raw, image_sha256=image_sha, crop=None, threshold=config["threshold"]
            )
            prediction = observer._prediction(
                prediction, {"width": WARMUP_SIZE[0], "height": WARMUP_SIZE[1]}, config
            )
            raw = _encode(prediction)
            _write(directory / f"warmup_{index:03d}.json", raw)
            end = time.perf_counter_ns()
            result["warmups"].append(
                {
                    "index": index,
                    "prediction_sha256": _sha(raw),
                    "started_perf_counter_ns": begin,
                    "finished_perf_counter_ns": end,
                    "elapsed_seconds": (end - begin) / 1e9,
                    "model_seconds": prediction["model_seconds"],
                }
            )
        if _read(directory / "worker_input_config.json") != config_raw:
            raise ValueError("Startup config bytes changed")
        observer._config(config)
        result["status"] = "ready"
    except (Exception, KeyboardInterrupt) as exc:
        result["error"] = {"type": type(exc).__name__, "message": str(exc)[:500]}
    finished = time.perf_counter_ns()
    result.update(finished_perf_counter_ns=finished, elapsed_seconds=(finished - started) / 1e9)
    return result


def _validate_startup(directory, raw_config, prepare_id, expected_sha):
    """Verify readiness artifacts without performing another prediction."""
    from PIL import Image

    raw = _read(directory / "startup_result.json")
    result = observer._json(raw)
    config = observer._json(raw_config)
    if (
        _sha(raw) != expected_sha
        or result.get("schema") != STARTUP_SCHEMA
        or result.get("prepare_id") != prepare_id
        or result.get("config_sha256") != _sha(raw_config)
        or result.get("status") != "ready"
        or result.get("error") is not None
        or result.get("configuration") != config
        or result.get("warmup_source") != "generated_black_rgb"
        or result.get("warmup_size") != list(WARMUP_SIZE)
        or type(result.get("warmup_count_planned")) is not int
        or result["warmup_count_planned"] != WARMUP_COUNT
        or type(result.get("study_frame_inputs")) is not int
        or result["study_frame_inputs"] != 0
        or type(result.get("engine_instances")) is not int
        or result["engine_instances"] != 1
        or result.get("clock") != "perf_counter_ns"
        or _read(directory / "worker_input_config.json") != raw_config
    ):
        raise ValueError("Readiness artifact/configuration binding mismatch")
    observer._config(config)
    image_raw = _read(directory / "warmup_black.jpg")
    if _sha(image_raw) != result.get("warmup_image_sha256"):
        raise ValueError("Readiness synthetic image SHA256 mismatch")
    with Image.open(io.BytesIO(image_raw)) as image:
        if (
            image.format != "JPEG"
            or image.mode != "RGB"
            or image.size != WARMUP_SIZE
            or image.getextrema() != ((0, 0), (0, 0), (0, 0))
        ):
            raise ValueError("Warmup must use the fixed all-black RGB image")
    begin = observer_report.outer._int(result["started_perf_counter_ns"])
    end = observer_report.outer._int(result["finished_perf_counter_ns"])
    if end < begin:
        raise ValueError("Startup clock moved backwards")
    observer_report.outer._same_number(result["elapsed_seconds"], (end - begin) / 1e9)
    observer._number(result["model_load_seconds"])
    rows = result.get("warmups")
    if not isinstance(rows, list) or len(rows) != WARMUP_COUNT:
        raise ValueError("Readiness needs exactly five completed warmups")
    previous = begin
    for index, row in enumerate(rows):
        if type(row.get("index")) is not int or row["index"] != index:
            raise ValueError("Readiness warmup sequence mismatch")
        raw_prediction = _read(directory / f"warmup_{index:03d}.json")
        if _sha(raw_prediction) != row.get("prediction_sha256"):
            raise ValueError("Readiness warmup prediction hash mismatch")
        prediction = observer._prediction(
            observer._json(raw_prediction),
            {"width": WARMUP_SIZE[0], "height": WARMUP_SIZE[1]},
            config,
        )
        start = observer_report.outer._int(row["started_perf_counter_ns"])
        finish = observer_report.outer._int(row["finished_perf_counter_ns"])
        if not previous <= start <= finish <= end:
            raise ValueError("Readiness warmup timing sequence mismatch")
        observer_report.outer._same_number(row["elapsed_seconds"], (finish - start) / 1e9)
        observer_report.outer._same_number(row["model_seconds"], prediction["model_seconds"])
        previous = finish
    return result


def _worker_main(connection, staging_dir, engine_factory):
    """Run in the child; only private fixed-name request directories are writable."""
    engine, engine_key, config_sha = None, None, None
    next_index, engine_instances = 0, 0
    prepared = False

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
            if message.get("kind") == "prepare":
                if (
                    set(message) != {"schema", "kind", "sequence", "prepare_id", "config_sha256"}
                    or message["schema"] != CONTROL_SCHEMA
                    or type(message["sequence"]) is not int
                    or message["sequence"] != 0
                    or not isinstance(message["prepare_id"], str)
                    or uuid.UUID(message["prepare_id"]).hex != message["prepare_id"]
                    or prepared
                    or next_index != 0
                    or engine is not None
                    or config_sha is not None
                ):
                    raise ValueError("Unexpected readiness control sequence/identity")
                prepared = True
                directory = Path(staging_dir) / "startup"
                raw_config = _read(directory / "worker_input_config.json")
                if _sha(raw_config) != message["config_sha256"]:
                    raise ValueError("Readiness config SHA256 mismatch")
                result = _startup(directory, raw_config, message["prepare_id"], cached_factory)
                result["engine_instances"] = engine_instances
                raw_result = _encode(result)
                _write(directory / "startup_result.json", raw_result)
                _send(
                    connection,
                    {
                        "schema": CONTROL_SCHEMA,
                        "kind": "ready",
                        "sequence": 0,
                        "prepare_id": message["prepare_id"],
                        "config_sha256": message["config_sha256"],
                        "worker_pid": os.getpid(),
                        "status": result["status"],
                        "startup_sha256": _sha(raw_result),
                        "error": result["error"],
                    },
                )
                if result["status"] != "ready":
                    return
                config_sha = message["config_sha256"]
                continue
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
        self._owns_staging = False
        self._process, self._connection, self._events = None, None, None
        self._signature, self._index, self._completed = None, 0, 0
        self._ids, self._lock = set(), threading.Lock()
        self._exit_confirmed = False
        self._closed = False
        self._prepare_requested, self._prepared = False, False
        self._config_binding = None

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
        self._owns_staging = True
        _write(
            self.staging_dir / "execution.json",
            _encode(
                {
                    "schema": "local_glove_worker_execution_v1",
                    "execution_mode": EXECUTION_MODE,
                    "start_method": "spawn",
                    "max_inflight": 1,
                    "lazy_start": not self._prepare_requested,
                    "initialization_mode": "explicit_pre_input"
                    if self._prepare_requested
                    else "first_dispatch",
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

    def prepare(self, config_path, timeout):
        """Explicitly load and warm before exposing any study request to the child."""
        if self._closed:
            raise RuntimeError("Worker runner is closed")
        if (
            type(timeout) not in (int, float)
            or not math.isfinite(timeout)
            or not 0 < timeout <= 3600
        ):
            raise ValueError("Readiness timeout must be finite and bounded")
        started = self._now()
        if not self._lock.acquire(blocking=False):
            raise RuntimeError("Only one worker operation may be in flight")
        deadline = started + math.ceil(timeout * 1e9)
        receipt, directory, binding = None, None, None
        command = ["explicit-readiness"]
        try:
            if (
                self._state == "failed"
                or self._prepare_requested
                or self._process is not None
                or self._index
            ):
                raise RuntimeError("Readiness is allowed once, before the first request")
            self._prepare_requested = True
            self._initialize()
            directory = self.staging_dir / "startup"
            directory.mkdir(exist_ok=False)
            prepare_id = uuid.uuid4().hex
            receipt = {
                "schema": "local_glove_worker_prepare_v1",
                "execution_mode": EXECUTION_MODE,
                "status": "failed",
                "prepare_id": prepare_id,
                "sequence": 0,
                "started_monotonic_ns": started,
                "deadline_monotonic_ns": deadline,
                "timeout_seconds": timeout,
                "study_frame_inputs": 0,
                "warmup_count_planned": WARMUP_COUNT,
                "warmup_size": list(WARMUP_SIZE),
                "ipc_sent": False,
                "ipc_received": False,
                "error": None,
            }
            config_path = Path(config_path)
            if not config_path.is_absolute():
                raise ValueError("Readiness config path must be explicitly absolute")
            _no_links(config_path)
            config_path = config_path.resolve()
            raw_config = _read(config_path)
            config = observer._json(raw_config)
            observer._config(config)
            binding = (str(config_path), _sha(raw_config))
            receipt["config_sha256"] = binding[1]
            _write(directory / "worker_input_config.json", raw_config)
            message = {
                "schema": CONTROL_SCHEMA,
                "kind": "prepare",
                "sequence": 0,
                "prepare_id": prepare_id,
                "config_sha256": binding[1],
            }
            self._deadline(deadline, command, timeout)
            self._spawn()
            self._state = "preparing"
            receipt["worker_pid"] = self._process.pid
            self._deadline(deadline, command, timeout)
            _send(self._connection, message)
            receipt.update(ipc_sent=True, ipc_sent_monotonic_ns=self._now())
            self._event("prepare_sent", prepare_id=prepare_id)
            remaining = max(0, (deadline - self._now()) / 1e9)
            if not self._connection.poll(remaining):
                raise subprocess.TimeoutExpired(command, timeout)
            self._deadline(deadline, command, timeout)
            reply = _receive(self._connection)
            receipt.update(ipc_received=True, ipc_received_monotonic_ns=self._now())
            self._deadline(deadline, command, timeout)
            expected_keys = {
                "schema",
                "kind",
                "sequence",
                "prepare_id",
                "config_sha256",
                "worker_pid",
                "status",
                "startup_sha256",
                "error",
            }
            if (
                set(reply) != expected_keys
                or reply.get("schema") != CONTROL_SCHEMA
                or reply.get("kind") != "ready"
                or type(reply.get("sequence")) is not int
                or reply["sequence"] != 0
                or reply.get("prepare_id") != prepare_id
                or reply.get("config_sha256") != binding[1]
                or type(reply.get("worker_pid")) is not int
                or reply["worker_pid"] != self._process.pid
                or reply.get("status") not in ("ready", "failed")
            ):
                raise ValueError("Readiness IPC identity/sequence/config mismatch")
            raw_result = _read(directory / "startup_result.json")
            if _sha(raw_result) != reply["startup_sha256"]:
                raise ValueError("Readiness IPC artifact SHA256 mismatch")
            result = observer._json(raw_result)
            if (
                result.get("prepare_id") != prepare_id
                or result.get("config_sha256") != binding[1]
                or result.get("status") != reply["status"]
                or result.get("error") != reply["error"]
            ):
                raise ValueError("Readiness error/result binding mismatch")
            receipt["startup_sha256"] = reply["startup_sha256"]
            if reply["status"] != "ready":
                receipt["child_error"] = reply["error"]
                raise RuntimeError(f"Worker startup failed: {reply['error']}")
            result = _validate_startup(directory, raw_config, prepare_id, reply["startup_sha256"])
            if _read(config_path) != raw_config:
                raise ValueError("Original config changed before readiness acceptance")
            ready_ns = self._deadline(deadline, command, timeout)
            receipt.update(
                status="ready",
                ready_monotonic_ns=ready_ns,
                child_elapsed_seconds=result["elapsed_seconds"],
                model_load_seconds=result["model_load_seconds"],
                warmup_model_seconds=[row["model_seconds"] for row in result["warmups"]],
                warmup_count_completed=len(result["warmups"]),
            )
            self._event("pre_input_ready", prepare_id=prepare_id)
            return receipt
        except (Exception, KeyboardInterrupt) as exc:
            self._prepared = False
            if receipt is not None:
                receipt.update(
                    status="failed", error={"type": type(exc).__name__, "message": str(exc)[:500]}
                )
            self._fail()
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
                    receipt_path = directory / "prepare_receipt.json"
                    raw_receipt = _encode(receipt)
                    receipt_written = False
                    try:
                        if receipt["status"] == "ready":
                            self._deadline(deadline, command, timeout)
                        _write(receipt_path, raw_receipt)
                        receipt_written = True
                        if receipt["status"] == "ready":
                            self._deadline(deadline, command, timeout)
                            self._prepared, self._state, self._config_binding = (
                                True,
                                "ready",
                                binding,
                            )
                    except (Exception, KeyboardInterrupt) as exc:
                        self._prepared = False
                        self._fail()
                        if receipt["status"] == "ready":
                            receipt.update(
                                status="failed",
                                error={"type": type(exc).__name__, "message": str(exc)[:500]},
                                worker_exit_confirmed=self._exit_confirmed,
                                finished_monotonic_ns=self._now(),
                            )
                            receipt["elapsed_seconds"] = (
                                receipt["finished_monotonic_ns"] - started
                            ) / 1e9
                            if receipt_written:
                                # Withdraw only this attempt's receipt after a late write.
                                if _read(receipt_path) != raw_receipt:
                                    raise ValueError("Readiness receipt was replaced") from exc
                                receipt_path.unlink()
                            if not receipt_path.exists():
                                _write(receipt_path, _encode(receipt))
                        raise
            finally:
                self._lock.release()

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
            config_binding = (str(config_path), _sha(raw_config))
            if self._config_binding is not None and self._config_binding != config_binding:
                raise ValueError("Request config differs from prepared config bytes/path")
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
                or reply.get("engine_reused") is not (self._prepared or self._completed > 0)
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
                        "explicit_preparation_requested": self._prepare_requested,
                        "pre_input_ready": self._prepared,
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

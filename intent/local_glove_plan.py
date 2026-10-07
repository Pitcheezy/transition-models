"""Generate a fresh machine-bound plan without starting an observer or decoder.

The original config is bound in place and must already contain an absolute local
weights path. File preflight does not verify device, decoder, or model operation.
Existing plans, captures, configs and results are never rewritten.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import sys
from fractions import Fraction
from pathlib import Path

from intent import clip_capture, local_glove_ready, local_glove_worker, observation_loop
from intent import local_glove_observer as observer

SCHEMA = "local_glove_plan_validation_v1"
RECEIPT_NAME = "validation_receipt.json"


def _write(path, value):
    raw = (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
    clip_capture._plain_path(path)
    with path.open("xb") as stream:
        stream.write(raw)


def _receipt(path, value):
    # A failed write must not leave a partially published success receipt.
    pending = path.with_name(f".{path.name}.{value['status']}.pending")
    _write(pending, value)
    clip_capture._plain_path(path)
    # Unlike rename on POSIX, link cannot overwrite a concurrently created receipt.
    os.link(pending, path)
    try:
        pending.unlink()
    except OSError:
        # The complete receipt is already published; only a redundant link remains.
        pass


def _file(value):
    path = clip_capture._plain_path(value)
    if not path.is_file():
        raise ValueError(f"Expected a regular local input file: {path}")
    return path


def _ffmpeg(value):
    if not isinstance(value, str) or not value.strip() or "\x00" in value:
        raise ValueError("ffmpeg must be an explicit executable name or path")
    # Resolving PATH is not an executable launch or a decoder capability check.
    located = Path(shutil.which(value) or value).absolute()
    # Executable-only normalization permits Homebrew links, then freezes the actual
    # file path. It does not relax any capture/config/checkpoint path guard.
    return _file(located.resolve(strict=True)), located


def _cutoffs(values):
    if (
        not isinstance(values, list)
        or not 1 <= len(values) <= 50
        or any(type(value) not in (str, int) for value in values)
    ):
        raise ValueError("Supply 1..50 exact string or integer cutoffs; floats are not accepted")
    try:
        exact = [Fraction(value) for value in values]
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("Invalid exact cutoff") from exc
    if exact[0] < 0 or any(a >= b for a, b in zip(exact, exact[1:], strict=False)):
        raise ValueError("Cutoffs must be nonnegative and strictly ascending")
    return values.copy()


def _json_cutoffs(raw):
    def constant(_):
        raise ValueError("Nonfinite JSON cutoff")

    return _cutoffs(json.loads(raw, parse_constant=constant))


def _code_files(config):
    modules = (
        observer,
        local_glove_worker.detector,
        local_glove_worker.observer_report,
        local_glove_worker,
        local_glove_ready,
    )
    return [str(_file(path)) for path in [*(m.__file__ for m in modules), __file__, config]]


def build_plan(
    *,
    capture_dir,
    config,
    ffmpeg,
    out_directory,
    observer_timeout_seconds,
    extract_timeout_seconds,
    cutoffs=None,
    cutoffs_json=None,
):
    """Write a new plan and receipt; preserve a failed receipt and re-raise failures.

    ``out_directory`` has an existing parent and must be fresh. Its future ``run``
    and ``run.startup`` directories remain absent. The config file is not copied;
    subsequent execution still requires that original file and unchanged bytes.
    """
    output = clip_capture._plain_path(out_directory)
    if output.exists():
        raise FileExistsError("Plan bundle must be a new directory; no implicit resume")
    if not output.parent.is_dir():
        raise ValueError("Plan bundle parent must already exist")
    capture = clip_capture._plain_path(capture_dir)
    if not capture.is_dir():
        raise ValueError("An existing local capture directory is required")
    config_path = _file(config)
    cutoff_path = _file(cutoffs_json) if cutoffs_json is not None else None
    for path in (capture, config_path, cutoff_path):
        if path is not None and (output.is_relative_to(path) or path.is_relative_to(output)):
            raise ValueError("Plan bundle must not overlap its inputs")
    if (cutoffs is None) == (cutoffs_json is None):
        raise ValueError("Supply exactly one of cutoffs or cutoffs_json")
    output.mkdir(exist_ok=False)
    receipt = {
        "schema": SCHEMA,
        "status": "failed",
        "error": None,
        "plan_path": str(output / "plan.json"),
        "run_output": str(output / "run"),
        "config_path": str(config_path),
        "config_sha256": None,
        "cutoffs_input": None,
        "plan_sha256": None,
        "input_code_bindings": [],
        "observer_launcher_binding": None,
        "weights_sha256": None,
        "weights_binding": None,
        "ffmpeg_requested": ffmpeg,
        "ffmpeg_lookup_path": None,
        "ffmpeg_path": None,
        "ffmpeg_resolution": "resolved_existing_file_without_execution",
        "config_copied_or_modified": False,
        "model_calls": 0,
        "decoder_calls": 0,
        "subprocess_calls": 0,
        "device_operation_verified": False,
        "decoder_operation_verified": False,
        "model_operation_verified": False,
        "notice": "File/SHA/PTS preflight only. This new plan is machine-bound, not a portable rewrite of prior evidence. Capture receipts must already be valid on this machine. No extraction, readiness, model load or device check was performed.",
    }
    try:
        raw_config = config_path.read_bytes()
        receipt["config_sha256"] = observer._sha(raw_config)
        config_value = observer._json(raw_config)
        weights = observer._config(config_value)
        if output.is_relative_to(weights) or weights.is_relative_to(output):
            raise ValueError("Plan bundle must not overlap its checkpoint")
        receipt["weights_sha256"] = config_value["weights_sha256"]
        receipt["weights_binding"] = {
            "path": str(weights),
            "sha256": config_value["weights_sha256"],
            "bytes": weights.stat().st_size,
        }
        raw_cutoffs = cutoff_path.read_bytes() if cutoff_path is not None else None
        values = _json_cutoffs(raw_cutoffs) if cutoff_path is not None else _cutoffs(cutoffs)
        if cutoff_path is not None:
            receipt["cutoffs_input"] = {
                "path": str(cutoff_path),
                "sha256": observer._sha(raw_cutoffs),
            }
        decoder, located = _ffmpeg(ffmpeg)
        receipt["ffmpeg_path"] = str(decoder)
        receipt["ffmpeg_lookup_path"] = str(located)
        plan = {
            "schema": observation_loop.PLAN_SCHEMA,
            "capture_dir": str(capture),
            "cutoffs": values,
            # Do not resolve this launcher: doing so can discard the virtualenv.
            "observer_argv": [
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
            ],
            "observer_code_files": _code_files(config_path),
            "observer_timeout_seconds": observer_timeout_seconds,
            "ffmpeg": str(decoder),
            "extract_timeout_seconds": extract_timeout_seconds,
        }
        plan_path, run_output = output / "plan.json", output / "run"
        _write(plan_path, plan)
        receipt["plan_sha256"] = clip_capture._sha256(plan_path)
        _, _, _, command, bindings, frozen = observation_loop._prepare(plan_path, run_output)
        if frozen["plan_sha256"] != receipt["plan_sha256"]:
            raise ValueError("Generated plan changed during validation")
        # Check the same strict argv contract used by the persistent/ready runners.
        for placeholder, filename in observation_loop._PLACEHOLDERS.items():
            command = [value.replace(placeholder, filename) for value in command]
        _, bound_config = local_glove_worker._command(command, output)
        if bound_config != config_path or _file(config_path).read_bytes() != raw_config:
            raise ValueError("Original configuration changed during plan validation")
        if cutoff_path is not None and _file(cutoff_path).read_bytes() != raw_cutoffs:
            raise ValueError("Cutoff input changed during plan validation")
        weights_binding = receipt["weights_binding"]
        observation_loop.clip_frames._verify_files(
            [
                *bindings,
                (_file(weights), weights_binding["sha256"], weights_binding["bytes"]),
            ]
        )
        observation_loop._verify_launcher(frozen["observer_launcher_binding"])
        local_glove_ready._paths(run_output)
        receipt.update(
            status="validated",
            input_code_bindings=frozen["input_code_bindings"],
            observer_launcher_binding=frozen["observer_launcher_binding"],
        )
        _receipt(output / RECEIPT_NAME, receipt)
    except (Exception, KeyboardInterrupt) as exc:
        receipt.update(status="failed", error={"type": type(exc).__name__, "message": str(exc)})
        try:
            _receipt(output / RECEIPT_NAME, receipt)
        except (Exception, KeyboardInterrupt) as receipt_error:
            exc.add_note(
                f"Could not preserve validation receipt: {type(receipt_error).__name__}: {receipt_error}"
            )
        raise
    return receipt


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path, required=True)
    parser.add_argument(
        "--config",
        type=Path,
        required=True,
        help="Original strict config, bound unchanged; weights must already be an absolute path",
    )
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--cutoff", dest="cutoffs", action="append")
    group.add_argument("--cutoffs-json", type=Path, help="JSON array of exact strings or integers")
    parser.add_argument("--ffmpeg", required=True)
    parser.add_argument("--out-directory", type=Path, required=True)
    parser.add_argument("--observer-timeout-seconds", type=float, required=True)
    parser.add_argument("--extract-timeout-seconds", type=float, required=True)
    args = parser.parse_args(argv)
    result = build_plan(**vars(args))
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

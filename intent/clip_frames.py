"""Extract a causally selected, checksum-verified local frame; never a live observation."""

from __future__ import annotations

import argparse
import json
import re
import time
from fractions import Fraction
from pathlib import Path

from PIL import Image

from intent import clip_capture, clip_clock

SCHEMA = "intent_mapped_frame_v1"


def _verify_files(bindings):
    for path, digest, size in bindings:
        if not path.is_file() or (size is not None and path.stat().st_size != size):
            raise ValueError(f"Bound input missing or byte size changed: {path.name}")
        if clip_capture._sha256(path) != digest:
            raise ValueError(f"Bound input SHA256 changed: {path.name}")


def _artifact_bindings(directory, artifacts, required):
    if not isinstance(artifacts, dict) or not required.issubset(artifacts):
        raise ValueError("Required artifact bindings are missing")
    bindings = []
    for name, record in artifacts.items():
        if (
            not isinstance(name, str)
            or not re.fullmatch(r"[A-Za-z0-9_.-]+", name)
            or name in (".", "..", "receipt.json")
        ):
            raise ValueError("Artifact must have a plain filename distinct from its receipt")
        if (
            not isinstance(record, dict)
            or type(record.get("bytes")) is not int
            or record["bytes"] < 0
            or not isinstance(record.get("sha256"), str)
            or not re.fullmatch(r"[a-f0-9]{64}", record["sha256"])
        ):
            raise ValueError("Malformed artifact size/hash")
        bindings.append(
            (clip_capture._plain_path(directory / name), record["sha256"], record["bytes"])
        )
    return bindings


def _capture_inputs(directory):
    receipt_path = clip_capture._plain_path(directory / "receipt.json")
    raw = receipt_path.read_bytes()
    receipt = json.loads(raw)
    if (
        not isinstance(receipt, dict)
        or receipt.get("schema") != "intent_clip_capture_v1"
        or receipt.get("status") != "captured"
        or receipt.get("errors") != []
    ):
        raise ValueError("Expected a successful, error-free intent_clip_capture_v1 receipt")
    if any(not isinstance(receipt.get(role), dict) for role in ("clip", "source")):
        raise ValueError("Capture must contain clip and source records")
    bindings = [(receipt_path, clip_clock._sha(raw), len(raw))]
    clip = clip_capture._plain_path(receipt["clip"]["path"])
    for role, path in (("clip", clip), ("source", None)):
        details = receipt[role]
        if role == "source":
            if details.get("kind") == "url":
                if not isinstance(details.get("value"), str) or not details["value"]:
                    raise ValueError("Missing captured source URL")
                continue
            if details.get("kind") != "local_file":
                raise ValueError("Unsupported captured source kind")
            path = clip_capture._plain_path(details["value"])
        digest = details.get("sha256_before")
        if (
            not isinstance(digest, str)
            or not re.fullmatch(r"[a-f0-9]{64}", digest)
            or digest != details.get("sha256_after")
            or details.get("unchanged") is not True
        ):
            raise ValueError(f"Captured {role} before/after hashes do not prove unchanged bytes")
        bindings.append((path, digest, None))
    artifacts = receipt.get("artifacts")
    bindings.extend(_artifact_bindings(directory, artifacts, {"source.framemd5", "clip.framemd5"}))
    _verify_files(bindings)
    source_data, clip_data = (
        (directory / name).read_bytes() for name in ("source.framemd5", "clip.framemd5")
    )
    report = clip_clock.cached_audit_mapping(source_data, clip_data)
    for role, data in (("source", source_data), ("clip", clip_data)):
        if clip_clock._sha(data) != artifacts[f"{role}.framemd5"]["sha256"]:
            raise ValueError("Checksum table changed while being read")
    return receipt, clip, bindings, report


def _input_hashes(captured, bindings, report):
    return {
        "capture_receipt_sha256": bindings[0][1],
        "source_framemd5_sha256": report["input_hashes"]["source_sha256"],
        "clip_framemd5_sha256": report["input_hashes"]["clip_sha256"],
        "clip_media_sha256": captured["clip"]["sha256_before"],
    }


def _command(ffmpeg, clip, ordinal, output):
    return [
        ffmpeg,
        "-nostdin",
        "-n",
        "-v",
        "error",
        "-i",
        str(clip),
        "-copyts",
        "-filter_complex",
        f"[0:v:0]select=eq(n\\,{ordinal}),split=2[check][image]",
        "-map",
        "[check]",
        "-frames:v",
        "1",
        "-fps_mode",
        "passthrough",
        "-enc_time_base",
        "-1",
        "-f",
        "framemd5",
        str(output / "selected.framemd5"),
        "-map",
        "[image]",
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(output / "image.jpg"),
    ]


def _verify_extraction(output, mapping, report):
    table = clip_clock.parse_framemd5(
        (output / "selected.framemd5").read_text(encoding="utf-8-sig")
    )
    if (
        len(table.frames) != 1
        or table.time_base != Fraction(report["clip"]["time_base"])
        or list(table.dimensions) != report["clip"]["dimensions"]
    ):
        raise ValueError("Selected checksum stream dimensions, time base or count differ")
    frame = table.frames[0]
    if (frame.pts, frame.duration, frame.size, frame.digest) != (
        mapping["clip_pts"],
        mapping["clip_duration"],
        mapping["size"],
        mapping["md5"],
    ):
        raise ValueError("Selected decoded frame PTS/duration/size/checksum differs from mapping")
    image = output / "image.jpg"
    if not image.is_file() or image.stat().st_size == 0:
        raise ValueError("Selected image output missing or empty")
    with Image.open(image) as decoded:
        if decoded.format != "JPEG" or list(decoded.size) != report["clip"]["dimensions"]:
            raise ValueError("Selected image must be a JPEG matching the decoded frame dimensions")
        decoded.verify()
    with Image.open(image) as decoded:
        decoded.load()


def extract_frame(*, capture_dir, source_seconds, out, ffmpeg="ffmpeg", timeout=120):
    """Use a new private directory; preflight errors raise, runtime failures retain a receipt."""
    directory, output = (clip_capture._plain_path(value) for value in (capture_dir, out))
    if output.exists():
        raise FileExistsError("Mapped frame output directory must be new")
    if output.is_relative_to(directory) or directory.is_relative_to(output):
        raise ValueError("Output must not overlap the capture directory")
    timeout = clip_capture._number(timeout, "timeout")
    if timeout > 3600:
        raise ValueError("Timeout must be at most 3600 seconds")
    if not isinstance(ffmpeg, str) or not ffmpeg.strip() or "\x00" in ffmpeg:
        raise ValueError("ffmpeg must be a nonempty executable name or path")
    captured, clip, bindings, report = _capture_inputs(directory)
    mapping = clip_clock.latest_mapped_frame(report, source_seconds)
    requested = Fraction(str(source_seconds))
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    receipt = {
        "schema": SCHEMA,
        "status": "failed",
        "private_receipt": True,
        "capture_directory": str(directory),
        "started_at_utc": clip_capture._utc(),
        "requested_source_seconds_exact": str(requested),
        "actual_source_seconds_exact": mapping["source_seconds_exact"],
        "actual_clip_seconds_exact": mapping["clip_seconds_exact"],
        "mapping": mapping,
        "input_hashes": _input_hashes(captured, bindings, report),
        "source": captured["source"],
        "clip_path": str(clip),
        "code_sha256": {},
        "module_sha256": None,
        "command": None,
        "errors": [],
        "artifacts": {},
        "extraction_verified": False,
        "bindings_verified": False,
        "notice": "Local preparation only, not live frame arrival or an AI observation. Capture hashes do not authenticate broadcast identity. Requested cutoff differs from actual frame time.",
    }
    try:
        receipt["code_sha256"] = {
            module.__name__: clip_capture._sha256(Path(module.__file__))
            for module in (clip_capture, clip_clock)
        }
        receipt["module_sha256"] = clip_capture._sha256(Path(__file__))
        receipt["command"] = clip_capture._run(
            _command(ffmpeg, clip, mapping["clip_decode_ordinal"], output),
            "extract",
            output,
            timeout,
        )
        if receipt["command"]["error"] or receipt["command"]["exit_code"] != 0:
            raise RuntimeError(f"Frame extraction failed: {receipt['command']['error']}")
        _verify_extraction(output, mapping, report)
        receipt["extraction_verified"] = True
    except (Exception, KeyboardInterrupt) as exc:
        receipt["errors"].append(f"{type(exc).__name__}: {exc}")
    finally:
        try:
            _verify_files(bindings)
            receipt["bindings_verified"] = True
        except (Exception, KeyboardInterrupt) as exc:
            receipt["errors"].append(f"Final input check failed: {type(exc).__name__}: {exc}")
        receipt["artifacts"], artifact_errors = clip_capture._artifact_records(output)
        receipt["errors"].extend(artifact_errors)
        receipt.update(
            finished_at_utc=clip_capture._utc(), elapsed_seconds=time.monotonic() - started
        )
        if (
            not receipt["errors"]
            and receipt["extraction_verified"]
            and receipt["bindings_verified"]
            and receipt["command"]["exit_code"] == 0
            and receipt["command"]["error"] is None
        ):
            receipt["status"] = "extracted"
        with (output / "receipt.json").open("x", encoding="utf-8") as stream:
            json.dump(receipt, stream, ensure_ascii=False, indent=2, allow_nan=False)
            stream.write("\n")
    return receipt


def load_verified_frame(mapped_dir):
    """Rebuild source correspondence and recheck every bound file before returning a frame."""
    directory = clip_capture._plain_path(mapped_dir)
    receipt_path = clip_capture._plain_path(directory / "receipt.json")
    raw = receipt_path.read_bytes()
    receipt = json.loads(raw)
    if (
        not isinstance(receipt, dict)
        or receipt.get("schema") != SCHEMA
        or receipt.get("status") != "extracted"
        or receipt.get("errors") != []
        or receipt.get("extraction_verified") is not True
        or receipt.get("bindings_verified") is not True
    ):
        raise ValueError("Expected a successfully verified mapped-frame receipt")
    command = receipt.get("command")
    if (
        not isinstance(command, dict)
        or type(command.get("exit_code")) is not int
        or command["exit_code"] != 0
        or command.get("error") is not None
    ):
        raise ValueError("Mapped frame must have a successful extraction command")
    capture_directory = receipt.get("capture_directory")
    if not isinstance(capture_directory, str) or not capture_directory:
        raise ValueError("Mapped receipt must identify its original capture directory")
    frame_bindings = [(receipt_path, clip_clock._sha(raw), len(raw))]
    frame_bindings.extend(
        _artifact_bindings(directory, receipt.get("artifacts"), {"image.jpg", "selected.framemd5"})
    )
    _verify_files(frame_bindings)
    captured, clip, capture_bindings, report = _capture_inputs(
        clip_capture._plain_path(capture_directory)
    )
    mapping = clip_clock.latest_mapped_frame(report, receipt.get("requested_source_seconds_exact"))
    if (
        receipt.get("input_hashes") != _input_hashes(captured, capture_bindings, report)
        or json.dumps(receipt.get("mapping"), sort_keys=True) != json.dumps(mapping, sort_keys=True)
        or receipt.get("actual_source_seconds_exact") != mapping["source_seconds_exact"]
        or receipt.get("actual_clip_seconds_exact") != mapping["clip_seconds_exact"]
        or receipt.get("source") != captured["source"]
        or receipt.get("clip_path") != str(clip)
    ):
        raise ValueError("Mapped receipt differs from recomputed capture correspondence")
    _verify_extraction(directory, mapping, report)
    _verify_files(capture_bindings)
    _verify_files(frame_bindings)
    return {
        "image_path": directory / "image.jpg",
        "receipt_path": receipt_path,
        "receipt_sha256": frame_bindings[0][1],
        "source_seconds": Fraction(mapping["source_seconds_exact"]),
        "requested_source_seconds": Fraction(receipt["requested_source_seconds_exact"]),
        "dimensions": tuple(report["clip"]["dimensions"]),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", required=True, type=Path)
    parser.add_argument("--source-seconds", required=True, help="exact decimal or rational cutoff")
    parser.add_argument("--out", required=True, type=Path)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--timeout", default=120, type=float)
    args = parser.parse_args(argv)
    try:
        receipt = extract_frame(**vars(args))
    except (OSError, ValueError, KeyError, TypeError) as exc:
        parser.error(str(exc))
    print(json.dumps({"status": receipt["status"], "receipt": str(args.out / "receipt.json")}))
    return 0 if receipt["status"] == "extracted" else 1


if __name__ == "__main__":
    raise SystemExit(main())

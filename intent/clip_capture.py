"""Capture fresh decoded-frame checksums without claiming clip/source alignment."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.parse import urlsplit

from .clip_clock import parse_framemd5


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def _artifact_records(output: Path) -> tuple[dict, list[str]]:
    """Collect output hashes while keeping enumeration/hash failures in a failed receipt."""
    records, errors = {}, []
    try:
        artifacts = sorted(output.iterdir())
    except (Exception, KeyboardInterrupt) as exc:
        return records, [f"Artifact enumeration failed: {type(exc).__name__}: {exc}"]
    for artifact in artifacts:
        try:
            if artifact.is_file():
                records[artifact.name] = {
                    "sha256": _sha256(artifact),
                    "bytes": artifact.stat().st_size,
                }
        except (Exception, KeyboardInterrupt) as exc:
            errors.append(f"{artifact.name}: artifact hash failed: {type(exc).__name__}: {exc}")
    return records, errors


def _utc() -> str:
    return datetime.now(UTC).isoformat()


def _plain_path(value: str | Path) -> Path:
    path = Path(value).absolute()
    for part in (path, *path.parents):
        if part.is_symlink() or getattr(part, "is_junction", lambda: False)():
            raise ValueError(f"Symlinks and junctions are not accepted: {part}")
    return path.resolve()


def _number(value: float, name: str, *, zero: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ValueError(f"{name} must be a finite number")
    if not math.isfinite(value) or (value < 0 if zero else value <= 0):
        raise ValueError(f"{name} must be finite and {'non-negative' if zero else 'positive'}")
    return float(value)


def _source(value: str | Path) -> tuple[str, Path | None]:
    value = str(value)
    parsed = urlsplit(value)
    if parsed.scheme.lower() in ("http", "https"):
        if not parsed.hostname or any(char.isspace() for char in value):
            raise ValueError("Source URL must have a hostname and no whitespace")
        if parsed.username is not None or parsed.password is not None:
            raise ValueError("Credentials in source URLs are not accepted")
        try:
            _ = parsed.port
        except ValueError as exc:
            raise ValueError("Invalid source URL port") from exc
        return value, None
    if parsed.scheme and not (len(parsed.scheme) == 1 and value[1:2] == ":"):
        raise ValueError("Source must be HTTP(S) or a regular local file")
    path = _plain_path(value)
    if not path.is_file():
        raise ValueError("Local source must be a regular file")
    return str(path), path


def _command(ffmpeg: str, source: str, output: Path, interval=None) -> list[str]:
    command = [ffmpeg, "-nostdin", "-n", "-v", "error"]
    if interval is not None:
        command += ["-ss", format(interval[0], ".17g"), "-t", format(interval[1], ".17g")]
    return command + [
        "-i",
        source,
        "-copyts",
        "-map",
        "0:v:0",
        "-an",
        "-fps_mode",
        "passthrough",
        "-enc_time_base",
        "-1",
        "-f",
        "framemd5",
        str(output),
    ]


def _run(command: list[str], name: str, out: Path, timeout: float) -> dict:
    started = time.monotonic()
    record = {"argv": command, "started_at_utc": _utc(), "exit_code": None, "error": None}
    stdout, stderr = out / f"{name}.stdout.txt", out / f"{name}.stderr.txt"
    with stdout.open("xb") as stdout_stream, stderr.open("xb") as stderr_stream:
        try:
            result = subprocess.run(
                command,
                stdin=subprocess.DEVNULL,
                stdout=stdout_stream,
                stderr=stderr_stream,
                shell=False,
                check=False,
                timeout=timeout,
            )
            record["exit_code"] = result.returncode
            if result.returncode:
                record["error"] = {"type": "nonzero_exit", "message": str(result.returncode)}
        except (OSError, subprocess.TimeoutExpired, KeyboardInterrupt) as exc:
            record["error"] = {"type": type(exc).__name__, "message": str(exc)}
    record.update(
        finished_at_utc=_utc(),
        elapsed_seconds=time.monotonic() - started,
        stdout_file=stdout.name,
        stderr_file=stderr.name,
    )
    return record


def capture(
    *,
    source: str | Path,
    source_start: float,
    source_duration: float,
    clip: str | Path,
    out: str | Path,
    ffmpeg: str = "ffmpeg",
    timeout: float = 600,
) -> dict:
    """Write a private receipt and validate decoded-frame tables without aligning them.

    Validation errors occur before any process or directory creation. Runtime failures
    preserve all produced evidence and return a receipt with status='failed'.
    """
    output = _plain_path(out)
    if output.exists():
        raise FileExistsError(f"Output directory must be new: {output}")
    start = _number(source_start, "source_start", zero=True)
    duration = _number(source_duration, "source_duration")
    if not math.isfinite(start + duration):
        raise ValueError("Source interval end must be finite")
    timeout = _number(timeout, "timeout")
    if timeout > 3600:
        raise ValueError("Timeout must be at most 3600 seconds per command")
    clip_path = _plain_path(clip)
    if not clip_path.is_file():
        raise ValueError("Clip must be a regular local file")
    source_value, source_path = _source(source)
    for path in (clip_path, source_path):
        if path is not None and (path.is_relative_to(output) or output.is_relative_to(path)):
            raise ValueError("Output must not overlap a source or clip path")
    if not isinstance(ffmpeg, str) or not ffmpeg.strip() or "\x00" in ffmpeg:
        raise ValueError("ffmpeg must be a nonempty executable name or path")
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    receipt = {
        "schema": "intent_clip_capture_v1",
        "status": "failed",
        "private_receipt": True,
        "started_at_utc": _utc(),
        "module_sha256": None,
        "source": {
            "kind": "url" if source_path is None else "local_file",
            "value": source_value,
            "identity_claim_verified": False,
        },
        "clip": {"path": str(clip_path)},
        "requested_source_interval": {
            "start_seconds": start,
            "duration_seconds": duration,
            "end_seconds": start + duration,
        },
        "timestamp_policy": "copyts; actual PTS and time bases remain in raw framemd5 files",
        "actual_pts_parsed": False,
        "alignment_verified": False,
        "notice": "Requested seek/duration are not measured PTS. URL and hashes do not authenticate media identity.",
        "timeout_seconds_per_command": timeout,
        "commands": {},
        "frame_tables": {},
        "errors": [],
        "artifacts": {},
    }
    try:
        receipt["module_sha256"] = _sha256(Path(__file__))
        receipt["clip"]["sha256_before"] = _sha256(clip_path)
        if source_path is not None:
            receipt["source"]["sha256_before"] = _sha256(source_path)
        version = _run(
            [ffmpeg, "-nostdin", "-n", "-v", "error", "-version"],
            "ffmpeg_version",
            output,
            min(timeout, 30),
        )
        receipt["commands"]["version"] = version
        receipt["ffmpeg_version"] = (
            (output / version["stdout_file"]).read_text(encoding="utf-8", errors="replace").strip()
        )
        if version["exit_code"] == 0 and version["error"] is None:
            for name, value, interval in (
                ("source", source_value, (start, duration)),
                ("clip", str(clip_path), None),
            ):
                artifact = output / f"{name}.framemd5"
                receipt["commands"][name] = _run(
                    _command(ffmpeg, value, artifact, interval), name, output, timeout
                )
                if not artifact.is_file() or artifact.stat().st_size == 0:
                    receipt["errors"].append(f"{name}: framemd5 output missing or empty")
                else:
                    try:
                        table = parse_framemd5(artifact.read_text(encoding="utf-8-sig"))
                        receipt["frame_tables"][name] = {
                            "frame_count": len(table.frames),
                            "time_base": str(table.time_base),
                            "first_pts": table.frames[0].pts,
                            "last_pts": table.frames[-1].pts,
                        }
                    except (ValueError, OSError) as exc:
                        receipt["errors"].append(f"{name}: invalid framemd5: {exc}")
                error = receipt["commands"][name]["error"]
                if error and error["type"] == "KeyboardInterrupt":
                    break
        for name, record in receipt["commands"].items():
            if record["error"]:
                receipt["errors"].append(f"{name}: {record['error']['type']}")
    except (Exception, KeyboardInterrupt) as exc:
        receipt["errors"].append(f"{type(exc).__name__}: {exc}")
    finally:
        for name, path in (("clip", clip_path), ("source", source_path)):
            if path is None:
                continue
            try:
                receipt[name]["sha256_after"] = _sha256(path)
                unchanged = receipt[name]["sha256_after"] == receipt[name].get("sha256_before")
                receipt[name]["unchanged"] = unchanged
                if not unchanged:
                    receipt["errors"].append(f"{name}: bytes changed during capture")
            except (Exception, KeyboardInterrupt) as exc:
                receipt["errors"].append(f"{name}: final hash failed: {type(exc).__name__}: {exc}")
        receipt["artifacts"], artifact_errors = _artifact_records(output)
        receipt["errors"].extend(artifact_errors)
        receipt.update(finished_at_utc=_utc(), elapsed_seconds=time.monotonic() - started)
        commands_ok = all(
            name in receipt["commands"]
            and receipt["commands"][name].get("exit_code") == 0
            and receipt["commands"][name].get("error") is None
            for name in ("version", "source", "clip")
        )
        receipt["actual_pts_parsed"] = all(
            name in receipt["frame_tables"] for name in ("source", "clip")
        )
        unchanged = receipt["clip"].get("unchanged") is True and (
            source_path is None or receipt["source"].get("unchanged") is True
        )
        if not commands_ok:
            receipt["errors"].append("Required version/source/clip command missing or unsuccessful")
        if commands_ok and receipt["actual_pts_parsed"] and unchanged and not receipt["errors"]:
            receipt["status"] = "captured"
        with (output / "receipt.json").open("x", encoding="utf-8") as stream:
            json.dump(receipt, stream, indent=2, ensure_ascii=False, allow_nan=False)
            stream.write("\n")
    return receipt


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    parser.add_argument("--source-start", type=float, required=True)
    parser.add_argument("--source-duration", type=float, required=True)
    parser.add_argument("--clip", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--timeout", type=float, default=600)
    args = parser.parse_args(argv)
    try:
        receipt = capture(**vars(args))
    except (ValueError, OSError) as exc:
        parser.error(str(exc))
    print(json.dumps({"status": receipt["status"], "receipt": str(args.out / "receipt.json")}))
    return 0 if receipt["status"] == "captured" else 1


if __name__ == "__main__":
    raise SystemExit(main())

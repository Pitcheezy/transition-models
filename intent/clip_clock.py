"""Map decoded frame checksums and their declared clocks, without authenticating media.

FFmpeg checksum-output timestamps can differ from native packet timestamps. This module
only audits the supplied tables. It does not decode media, infer frame rate, or run a model.
"""

from __future__ import annotations

import argparse
import json
import re
from bisect import bisect_right
from dataclasses import dataclass
from fractions import Fraction
from pathlib import Path

SCHEMA = "intent_clip_clock_mapping_v1"
_COLUMNS = ["stream#", "dts", "pts", "duration", "size", "hash"]
_REQUIRED = {"format", "version", "hash", "tb 0", "media_type 0", "codec_id 0", "dimensions 0"}
_ALLOWED = _REQUIRED | {"software", "sar 0"}


@dataclass(frozen=True)
class Frame:
    decode_ordinal: int
    dts: int
    pts: int
    duration: int
    size: int
    digest: str


@dataclass(frozen=True)
class FrameTable:
    time_base: Fraction
    dimensions: tuple[int, int]
    sample_aspect_ratio: Fraction | None
    frames: tuple[Frame, ...]


def _positive_fraction(value):
    if not re.fullmatch(r"[1-9]\d*/[1-9]\d*", value):
        raise ValueError("Expected a positive rational time base or aspect ratio")
    return Fraction(value)


def parse_framemd5(text):
    """Parse a strict single-stream raw-video framemd5 v2 table with increasing PTS."""
    if not isinstance(text, str):
        raise ValueError("framemd5 input must be decoded text")
    headers, frames, columns = {}, [], False
    for number, raw in enumerate(text.splitlines(), 1):
        line = raw.strip()
        if not line:
            continue
        if line.startswith("#"):
            if frames:
                raise ValueError(f"Header after frame records at line {number}")
            body = line[1:].strip()
            if body.startswith("stream#"):
                if columns or [part.strip() for part in body.split(",")] != _COLUMNS:
                    raise ValueError("Duplicate or malformed frame column header")
                columns = True
                continue
            key, separator, value = body.partition(":")
            key, value = " ".join(key.split()), value.strip()
            if not separator or key not in _ALLOWED or key in headers or not value:
                raise ValueError(f"Unsupported/duplicate header at line {number}: {key}")
            headers[key] = value
            continue
        parts = [part.strip() for part in line.split(",")]
        if (
            not columns
            or len(parts) != 6
            or any(not re.fullmatch(r"-?\d+", value) for value in parts[:5])
        ):
            raise ValueError(f"Malformed frame record at line {number}")
        stream, dts, pts, duration, size = map(int, parts[:5])
        if stream != 0 or duration <= 0 or size <= 0 or not re.fullmatch(r"[0-9a-f]{32}", parts[5]):
            raise ValueError(f"Expected stream 0, positive duration/size and MD5 at line {number}")
        if frames and pts <= frames[-1].pts:
            raise ValueError("Frame PTS must be strictly increasing; ordinal is not PTS")
        frames.append(Frame(len(frames), dts, pts, duration, size, parts[5]))
    expected = {
        "format": "frame checksums",
        "version": "2",
        "hash": "MD5",
        "media_type 0": "video",
        "codec_id 0": "rawvideo",
    }
    if not _REQUIRED.issubset(headers) or any(headers.get(k) != v for k, v in expected.items()):
        raise ValueError("Expected framemd5 v2 MD5/rawvideo single-stream schema")
    if not frames:
        raise ValueError("Checksum table contains no decoded frames")
    if not re.fullmatch(r"[1-9]\d*x[1-9]\d*", headers["dimensions 0"]):
        raise ValueError("Invalid decoded frame dimensions")
    if len({frame.size for frame in frames}) != 1:
        raise ValueError("Raw-video byte size changed inside a fixed-dimension stream")
    return FrameTable(
        _positive_fraction(headers["tb 0"]),
        tuple(map(int, headers["dimensions 0"].split("x"))),
        _positive_fraction(headers["sar 0"]) if "sar 0" in headers else None,
        tuple(frames),
    )


def _sha(data):
    import hashlib

    return hashlib.sha256(data).hexdigest()


def _table_summary(table):
    gaps, overlaps = [], []
    for previous, current in zip(table.frames, table.frames[1:], strict=False):
        end = previous.pts + previous.duration
        if current.pts == end:
            continue
        target = gaps if current.pts > end else overlaps
        target.append(
            {
                "after_decode_ordinal": previous.decode_ordinal,
                "before_decode_ordinal": current.decode_ordinal,
                "previous_end_pts": end,
                "next_pts": current.pts,
                "delta_ticks": current.pts - end,
                "delta_seconds_exact": str((current.pts - end) * table.time_base),
            }
        )
    return {
        "frame_count": len(table.frames),
        "time_base": str(table.time_base),
        "dimensions": list(table.dimensions),
        "sample_aspect_ratio": str(table.sample_aspect_ratio)
        if table.sample_aspect_ratio
        else None,
        "frame_bytes": table.frames[0].size,
        "first_pts": table.frames[0].pts,
        "last_pts": table.frames[-1].pts,
        "first_seconds_exact": str(table.frames[0].pts * table.time_base),
        "end_seconds_exact": str(
            (table.frames[-1].pts + table.frames[-1].duration) * table.time_base
        ),
        "gaps": gaps,
        "duration_overlaps": overlaps,
    }


def audit_mapping(source_bytes, clip_bytes):
    """Match unique size/MD5 pairs and preserve each table's exact rational presentation clock."""
    if not isinstance(source_bytes, bytes) or not isinstance(clip_bytes, bytes):
        raise ValueError("Pass exact input bytes so input SHA256 remains reproducible")
    source, clip = (parse_framemd5(data.decode("utf-8-sig")) for data in (source_bytes, clip_bytes))
    if (source.dimensions, source.sample_aspect_ratio, source.frames[0].size) != (
        clip.dimensions,
        clip.sample_aspect_ratio,
        clip.frames[0].size,
    ):
        raise ValueError("Decoded dimensions, aspect ratio or frame bytes are incompatible")
    source_index = {(frame.size, frame.digest): frame for frame in source.frames}
    if len(source_index) != len(source.frames) or len(
        {(f.size, f.digest) for f in clip.frames}
    ) != len(clip.frames):
        raise ValueError("Repeated decoded checksums make frame correspondence ambiguous")
    rows, offsets, previous_source = [], [], -1
    for frame in clip.frames:
        match = source_index.get((frame.size, frame.digest))
        if match is None:
            raise ValueError(f"Unmatched clip decoded frame ordinal {frame.decode_ordinal}")
        if match.decode_ordinal <= previous_source:
            raise ValueError("Matched source frames do not preserve presentation order")
        previous_source = match.decode_ordinal
        source_time, clip_time = match.pts * source.time_base, frame.pts * clip.time_base
        offset = source_time - clip_time
        end_pts = match.pts + match.duration
        if match.decode_ordinal + 1 < len(source.frames):
            end_pts = min(end_pts, source.frames[match.decode_ordinal + 1].pts)
        offsets.append(offset)
        rows.append(
            {
                "clip_decode_ordinal": frame.decode_ordinal,
                "source_decode_ordinal": match.decode_ordinal,
                "clip_pts": frame.pts,
                "source_pts": match.pts,
                "clip_duration": frame.duration,
                "source_duration": match.duration,
                "clip_seconds_exact": str(clip_time),
                "source_seconds_exact": str(source_time),
                "source_interval_end_exact": str(end_pts * source.time_base),
                "offset_seconds_exact": str(offset),
                "size": frame.size,
                "md5": frame.digest,
            }
        )
    minimum, maximum = min(offsets), max(offsets)
    return {
        "schema": SCHEMA,
        "input_hashes": {"source_sha256": _sha(source_bytes), "clip_sha256": _sha(clip_bytes)},
        "source": _table_summary(source),
        "clip": _table_summary(clip),
        "matched_frames": len(rows),
        "constant_offset": {"exact": str(minimum), "seconds": float(minimum)}
        if minimum == maximum
        else None,
        "offset_range": {
            "minimum_exact": str(minimum),
            "maximum_exact": str(maximum),
            "span_exact": str(maximum - minimum),
        },
        "rows": rows,
        "limitations": [
            "Only the supplied checksum tables are verified; media identity, capture commands and native packet clocks are not authenticated.",
            "Decode ordinals differ from PTS. Gaps are declared-clock ticks, not inferred missing-frame counts or a constant frame rate.",
            "Varying per-frame offsets never authorize an average/global time correction.",
            "Causal lookup uses mapped source intervals only; it never picks a future frame or fills a missing interval.",
            "No full-PA boundaries, image labels, automatic observer, accuracy or real-time availability are established.",
        ],
    }


def latest_mapped_frame(report, source_seconds):
    """Return the latest mapped frame at/before a time, rejecting absent presentation intervals."""
    if not isinstance(report, dict) or report.get("schema") != SCHEMA or not report.get("rows"):
        raise ValueError("Expected a nonempty decoded-clock mapping report")
    if isinstance(source_seconds, bool):
        raise ValueError("Expected a finite rational source time")
    try:
        requested = Fraction(str(source_seconds))
    except (ValueError, TypeError, ZeroDivisionError) as exc:
        raise ValueError("Expected a finite rational source time") from exc
    rows = report["rows"]
    starts = [Fraction(row["source_seconds_exact"]) for row in rows]
    index = bisect_right(starts, requested) - 1
    if index < 0 or requested >= Fraction(rows[index]["source_interval_end_exact"]):
        raise ValueError("Requested time is outside mapped coverage or lies in a missing interval")
    return dict(rows[index])


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("audit",))
    parser.add_argument("--source-frames", type=Path, required=True)
    parser.add_argument("--clip-frames", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True, help="new output only; never overwrite")
    args = parser.parse_args(argv)
    if args.out.exists():
        parser.error("Output already exists; choose a new report path")
    report = audit_mapping(args.source_frames.read_bytes(), args.clip_frames.read_bytes())
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(
        json.dumps(
            {key: report[key] for key in ("matched_frames", "constant_offset", "offset_range")}
        )
    )


if __name__ == "__main__":
    main()

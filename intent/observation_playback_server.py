"""Validate and serve a private observation replay with immutable HTTP Range media.

Only loopback is supported. Files are frozen after verification; package hashes
bind bytes, not broadcast identity, scientific accuracy or permission to publish.
The total package limit is 512 MiB; the reused reader limits each file to 128 MiB.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path
from types import MappingProxyType

from src.integration.service_review_server import (
    MAX_JSON_BYTES,
    ReviewServer,
    _digest,
    _json,
    _linked,
    _Reader,
    _relative_name,
    _require,
    _sha,
    make_handler,
)
from src.integration.service_review_server import (
    MAX_TOTAL_BYTES as MAX_FILE_BYTES,
)

MAX_PACKAGE_BYTES = 512 * 1024 * 1024
SCHEMA = "intent_observation_playback_v1"
PACKAGE_SCHEMA = "intent_observation_playback_package_v1"
STATIC = {
    "index.html",
    "playback.js",
    "style.css",
    "replay-data.json",
    "PRIVATE.txt",
    "media/clip.mp4",
}
TYPES = {
    "index.html": "text/html; charset=utf-8",
    "playback.js": "text/javascript; charset=utf-8",
    "style.css": "text/css; charset=utf-8",
    "replay-data.json": "application/json; charset=utf-8",
    "media/clip.mp4": "video/mp4",
}
_OBSERVATION_KEYS = {
    "index",
    "cutoff_seconds_exact",
    "frame_seconds_exact",
    "publication_seconds_exact",
    "status",
    "observation_status",
    "candidate_status",
    "reference_pitch_id",
    "image_path",
}
_REFERENCE_KEYS = {
    "pitch_id",
    "decision_seconds_exact",
    "decision_upper_seconds_exact",
    "release_lower_seconds_exact",
    "release_upper_seconds_exact",
    "conservative_temporal_ready",
    "nominal_start_temporal_ready",
    "usable_mitt",
}
_SUMMARY_KEYS = {
    "planned_observations",
    "interval_observations",
    "outside_interval_observations",
    "accepted",
    "errors",
    "not_attempted",
    "verified_mitt",
    "conservative_ready_pitches",
}
_EVIDENCE_KEYS = {
    "saved_run_inventory",
    "capture_receipt_sha256",
    "source_framemd5_sha256",
    "clip_framemd5_sha256",
    "clip_media_sha256",
    "timing",
    "manifest",
    "sources",
    "deadline_report",
}


def _keys(value, keys, label):
    _require(isinstance(value, dict) and set(value) == keys, f"Unexpected {label} fields.")


def _exact(value, *, nullable=False):
    _require(
        (nullable and value is None)
        or (isinstance(value, str) and re.fullmatch(r"(?:0|[1-9]\d*)(?:/[1-9]\d*)?", value)),
        "Playback times must use nonnegative exact rational strings.",
    )


def _data_assets(data, records):
    _keys(data, {"schema", "media", "scope", "observations", "references", "summary"}, "DTO")
    _require(data["schema"] == SCHEMA, "Unsupported playback DTO schema.")
    media, scope = data["media"], data["scope"]
    _keys(
        media, {"path", "sha256", "source_offset_seconds_exact", "clip_end_seconds_exact"}, "media"
    )
    _require(
        media["path"] == "media/clip.mp4"
        and media["sha256"] == records["media/clip.mp4"]["sha256"],
        "Media path or SHA256 differs from the package manifest.",
    )
    for name in ("source_offset_seconds_exact", "clip_end_seconds_exact"):
        _exact(media[name])
    _keys(
        scope,
        {
            "game_pk",
            "pa",
            "start_source_seconds_exact",
            "end_source_seconds_exact",
            "full_pa_verified",
            "live_availability_verified",
            "human_label",
        },
        "scope",
    )
    _require(
        all(type(scope[k]) is int and scope[k] > 0 for k in ("game_pk", "pa"))
        and all(
            scope[k] is False
            for k in ("full_pa_verified", "live_availability_verified", "human_label")
        ),
        "Only an unverified, nonhuman local replay scope is supported.",
    )
    _exact(scope["start_source_seconds_exact"])
    _exact(scope["end_source_seconds_exact"])
    refs, obs = data["references"], data["observations"]
    _require(isinstance(refs, list) and 1 <= len(refs) <= 100, "Invalid reference list.")
    ids = set()
    for ref in refs:
        _keys(ref, _REFERENCE_KEYS, "reference")
        identity = ref["pitch_id"]
        _require(
            isinstance(identity, str)
            and re.fullmatch(rf"{scope['game_pk']}:{scope['pa']}:[1-9]\d*", identity)
            and identity not in ids
            and ref["usable_mitt"] is False,
            "Invalid reference pitch identity or verified-mitt claim.",
        )
        ids.add(identity)
        for name in _REFERENCE_KEYS - {
            "pitch_id",
            "usable_mitt",
            "conservative_temporal_ready",
            "nominal_start_temporal_ready",
        }:
            _exact(ref[name])
        _require(
            type(ref["conservative_temporal_ready"]) is bool
            and type(ref["nominal_start_temporal_ready"]) is bool,
            "Invalid reference timing flags.",
        )
    _require(isinstance(obs, list) and 1 <= len(obs) <= 50, "Invalid observation list.")
    images = set()
    for index, row in enumerate(obs):
        _keys(row, _OBSERVATION_KEYS, "observation")
        _require(type(row["index"]) is int and row["index"] == index, "Observation indices differ.")
        _exact(row["cutoff_seconds_exact"])
        _exact(row["frame_seconds_exact"], nullable=True)
        _exact(row["publication_seconds_exact"], nullable=True)
        _require(
            row["reference_pitch_id"] is None or row["reference_pitch_id"] in ids,
            "Unknown reference pitch.",
        )
        status = row["status"]
        _require(status in {"accepted", "error", "not_attempted"}, "Invalid observation status.")
        if status == "accepted":
            expected = {
                "candidate": "unknown",
                "ambiguous": "unknown",
                "no_candidate": "unavailable",
            }.get(row["candidate_status"])
            _require(
                expected is not None
                and row["observation_status"] == expected
                and row["frame_seconds_exact"] is not None
                and row["publication_seconds_exact"] is not None
                and row["image_path"] == f"frames/{index:03d}.jpg",
                "Invalid accepted image path or unverified observation status.",
            )
            images.add(row["image_path"])
        else:
            _require(
                row["image_path"] is None
                and row["publication_seconds_exact"] is None
                and row["candidate_status"] == status
                and row["observation_status"] in (None, "unavailable"),
                "Unaccepted observations cannot publish an image/result.",
            )
    _keys(data["summary"], _SUMMARY_KEYS, "summary")
    _require(
        all(type(v) is int and v >= 0 for v in data["summary"].values())
        and data["summary"]["planned_observations"] == len(obs)
        and data["summary"]["verified_mitt"] == 0,
        "Invalid playback summary or verified-mitt claim.",
    )
    return images


def load_snapshot(directory):
    """Validate allowlisted package bytes and freeze them before opening a socket."""
    root = Path(directory).absolute()
    for path in (root, *root.parents):
        _require(not _linked(path), "Linked package directory is not accepted.")
    reader = _Reader(root)
    root = reader.root
    total = 0

    def read(name, limit):
        nonlocal total
        # Fresh readers retain inode/reparse/size/open protections without mutating
        # the existing service server's global 128 MiB accumulated-size contract.
        raw = _Reader(root).read(name, min(limit, MAX_PACKAGE_BYTES - total))
        total += len(raw)
        return raw

    receipt = _json(read("manifest.json", MAX_JSON_BYTES))
    _keys(
        receipt,
        {"schema", "private", "input_files_unchanged", "input_evidence_sha256", "artifacts"},
        "manifest",
    )
    _require(
        receipt["schema"] == PACKAGE_SCHEMA
        and receipt["private"] is True
        and receipt["input_files_unchanged"] is True,
        "Expected a private, successfully verified playback package.",
    )
    evidence = receipt["input_evidence_sha256"]
    _keys(evidence, _EVIDENCE_KEYS, "evidence")
    _require(all(_digest(value) for value in evidence.values()), "Invalid input evidence hashes.")
    records = receipt["artifacts"]
    _require(
        isinstance(records, dict) and STATIC <= records.keys() and len(records) <= 56,
        "Missing or excessive package artifacts.",
    )
    for name, record in records.items():
        _relative_name(name)
        _require(
            name in STATIC or re.fullmatch(r"frames/\d{3}\.jpg", name),
            "Unexpected package asset path.",
        )
        _keys(record, {"sha256", "bytes"}, "artifact")
        limit = (
            MAX_FILE_BYTES if name == "media/clip.mp4" or name.endswith(".jpg") else MAX_JSON_BYTES
        )
        _require(
            _digest(record["sha256"])
            and type(record["bytes"]) is int
            and 0 < record["bytes"] <= limit,
            "Invalid asset hash or size.",
        )
    _require(
        total + sum(record["bytes"] for record in records.values()) <= MAX_PACKAGE_BYTES,
        "Package size limit exceeded.",
    )

    def bound(name):
        record = records[name]
        raw = read(name, record["bytes"])
        _require(
            len(raw) == record["bytes"] and _sha(raw) == record["sha256"],
            "Package asset size or SHA256 mismatch.",
        )
        return raw

    raw_data = bound("replay-data.json")
    images = _data_assets(_json(raw_data), records)
    _require(set(records) == STATIC | images, "Unexpected or missing package image path.")
    files = {"/replay-data.json": (raw_data, TYPES["replay-data.json"])}
    for name in records:
        if name == "replay-data.json":
            continue
        raw = bound(name)
        content_type = TYPES.get(name) or ("image/jpeg" if name in images else None)
        if content_type is not None:
            files["/" + name] = (raw, content_type)
    return MappingProxyType(files)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--port", type=int, default=0)
    parser.add_argument("--check", action="store_true")
    args = parser.parse_args(argv)
    if not 0 <= args.port <= 65535:
        parser.error("Port must be between 0 and 65535")
    try:
        snapshot = load_snapshot(args.directory)
    except (OSError, ValueError) as exc:
        print(f"Playback package check failed: {exc}", file=sys.stderr)
        return 1
    print("Private playback package verified; saved observations only.", flush=True)
    if args.check:
        return 0
    try:
        server = ReviewServer(("127.0.0.1", args.port), make_handler(snapshot))
    except OSError as exc:
        print(f"Cannot start loopback playback server: {exc}", file=sys.stderr)
        return 1
    with server:
        print(f"http://127.0.0.1:{server.server_address[1]}/", flush=True)
        try:
            server.serve_forever()
        except KeyboardInterrupt:
            pass
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

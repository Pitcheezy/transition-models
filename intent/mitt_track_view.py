"""Build a private, offline JPEG replay from hash-bound CV37/CV38 development artifacts.

Only derived display data is exported, never source URLs, commands, annotations or local
paths. Checks prove saved-record alignment, not independent decoded PTS or mitt identity.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
from pathlib import Path

from PIL import Image

from intent.mitt_stationary import StationaryParams
from intent.mitt_stationary_pilot import replay

SCHEMA = "pitcheezy-track-frame-view-dev-v1"
ASSETS = Path(__file__).resolve().parents[1] / "web" / "track-review"


PLACEHOLDERS = ("__TRACK_VIEW_DATA__", "__OCR_VIEW_DATA__")


def fill_template(template, values):
    """Fill every placeholder in one pass, so inserted data is never scanned for placeholders."""
    if set(values) != set(PLACEHOLDERS) or any(template.count(p) != 1 for p in PLACEHOLDERS):
        raise ValueError("invalid viewer template")
    pattern = "|".join(re.escape(p) for p in PLACEHOLDERS)
    return re.sub(pattern, lambda match: values[match.group(0)], template)


def sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _unique(rows, key):
    result = {}
    for row in rows:
        value = key(row)
        if value in result:
            raise ValueError("duplicate evidence key")
        result[value] = row
    return result


def _finite(value):
    try:
        return (
            isinstance(value, (int, float)) and not isinstance(value, bool) and math.isfinite(value)
        )
    except OverflowError:
        return False


def build(
    *,
    bundle,
    timing,
    tracking_report,
    tracking_records,
    selection_report,
    selection_records,
    report_sha256,
    out,
    at_bat=3,
):
    if type(at_bat) is not int or at_bat < 1:
        raise ValueError("at_bat must be a positive integer")
    bundle, out = Path(bundle).resolve(), Path(out).resolve()
    if out == bundle or out.is_relative_to(bundle):
        raise ValueError("output must not be inside the source bundle")
    if out.exists():
        raise FileExistsError(out)
    paths = {
        "bundle_manifest": bundle / "manifest.json",
        "timing": Path(timing),
        "tracking_report": Path(tracking_report),
        "tracking_records": Path(tracking_records),
        "selection_report": Path(selection_report),
        "selection_records": Path(selection_records),
    }
    raw = {name: path.read_bytes() for name, path in paths.items()}
    hashes = {name: sha(value) for name, value in raw.items()}
    if hashes["selection_report"] != report_sha256:
        raise ValueError("selection report SHA mismatch")
    data = {name: json.loads(value) for name, value in raw.items()}
    selected_report, tracker_report, manifest = (
        data["selection_report"],
        data["tracking_report"],
        data["bundle_manifest"],
    )
    if (
        selected_report.get("schema") != "pitcheezy-stationary-pilot-dev-v1"
        or tracker_report.get("schema") != "pitcheezy-mitt-tracking-pilot-dev-v2"
        or manifest.get("schema") != "pitcheezy-mitt-dev-bundle-v1"
    ):
        raise ValueError("unsupported evidence schema")
    expected = {
        "tracking_report": selected_report["input_sha256"]["tracking_report"],
        "tracking_records": selected_report["input_sha256"]["cpu"],
        "selection_records": selected_report["devices"]["cpu"]["output_sha256"],
        "bundle_manifest": tracker_report["source_manifest_sha256"],
        "timing": manifest["source"]["timing_file_sha256"],
    }
    if any(hashes[name] != value for name, value in expected.items()):
        raise ValueError("evidence SHA chain mismatch")
    if hashes["tracking_records"] != tracker_report["devices"]["cpu"]["records_sha256"]:
        raise ValueError("tracking report record SHA mismatch")
    if selected_report["params_sha256"] != StationaryParams().digest():
        raise ValueError("unsupported selector parameter digest")
    if (
        manifest["source"]["time_base"] != "1/60000"
        or manifest["source"]["ticks_per_frame"] != 1001
    ):
        raise ValueError("unsupported manifest time basis")
    tracks, selections = data["tracking_records"], data["selection_records"]
    recalculated, summary = replay(tracks)
    if selections != recalculated:
        raise ValueError("selection records disagree with causal replay")
    for report in (tracker_report, selected_report["devices"]["cpu"]):
        if report["frames"] != len(tracks) or report["pitches"] != summary["pitches"]:
            raise ValueError("evidence denominator mismatch")
    annotations = _unique(
        data["timing"]["annotations"],
        lambda a: f"{a['game_pk']}:{a['at_bat_number']}:{a['pitch_number']}",
    )
    selection_meta = _unique(manifest["selection"], lambda p: p["pitch_id"])
    _unique(manifest["pitches"], lambda p: p["pitch_id"])
    corpus = [p for p in manifest["pitches"] if p["status"] == "extracted"][: summary["pitches"]]
    planned = []
    for pitch in corpus:
        pitch_id = pitch["pitch_id"]
        match = re.fullmatch(r"747139:([1-9]\d*):([1-9]\d*)", pitch_id)
        if match is None:
            raise ValueError("unsupported pitch key")
        pa, pn = map(int, match.groups())
        if pitch_id not in selection_meta or pitch_id not in annotations:
            raise ValueError("missing pitch/timing binding")
        meta, timing_row = selection_meta[pitch_id], annotations[pitch_id]
        if (
            meta["included"] is not True
            or meta["timing_status"] != "annotated"
            or timing_row["status"] != "annotated"
        ):
            raise ValueError("pitch lacks timing annotation")
        if not isinstance(meta["play_id"], str) or not meta["play_id"]:
            raise ValueError("play_id required")
        for field in ("play_id", "decision_seconds", "release_seconds", "uncertainty_seconds"):
            if meta[field] != timing_row[field]:
                raise ValueError("pitch/timing metadata mismatch")
        for field in ("decision_seconds", "release_seconds", "uncertainty_seconds"):
            if not _finite(meta[field]) or meta[field] < 0:
                raise ValueError("invalid timing metadata")
        if meta["decision_seconds"] >= meta["release_seconds"]:
            raise ValueError("invalid decision/release ordering")
        frames = [
            f
            for f in pitch["frames"]
            if "grid" in f["roles"] and f["index"] <= pitch["window"]["release_index"]
        ]
        indices = [f["index"] for f in frames]
        if (
            not indices
            or any(type(i) is not int or i < 0 for i in indices)
            or indices != sorted(set(indices))
        ):
            raise ValueError("invalid manifest frame order")
        planned.extend((pitch_id, pa, pn, f) for f in frames)
    if len(planned) != len(tracks):
        raise ValueError("frame coverage differs from manifest grid")
    images, source_files, visible_pitches = {}, {}, {}
    for (pitch_id, pa, pn, frame), track, result in zip(planned, tracks, selections, strict=True):
        index, seconds = frame["index"], frame["pts_time"]
        if (
            track["pitch_id"] != pitch_id
            or track["frame_index"] != index
            or not _finite(seconds)
            or abs(seconds - index * 1001 / 60000) > 1e-9
            or track["frame_seconds"] != seconds
            or track["source_pts_ticks"] != index * 1001
            or track["source_time_base"] != "1/60000"
            or track["source_sha256"] != frame["sha256"]
        ):
            raise ValueError("pitch/frame/time/source binding mismatch")
        point = track["point_px"]
        if point is not None and not (0 <= point[0] < 1280 and 0 <= point[1] < 720):
            raise ValueError("tracked point outside source image")
        current = result["current_candidate"]
        if current is not None and (
            result["pitch_id"] != pitch_id
            or result["selection_state"] != "stationary"
            or current["pitch_id"] != pitch_id
            or current["frame_index"] != index
            or current["frame_seconds"] != seconds
        ):
            raise ValueError("current candidate does not belong to this exact frame")
        image_path = (bundle / f"pa{pa}_p{pn}" / f"frame_{index:06d}.jpg").resolve()
        if not image_path.is_relative_to(bundle):
            raise ValueError("image escapes bundle")
        image_bytes = image_path.read_bytes()
        if len(image_bytes) != frame["bytes"] or sha(image_bytes) != frame["sha256"]:
            raise ValueError("image size/SHA mismatch")
        with Image.open(io.BytesIO(image_bytes)) as image:
            image.load()
            if image.format != "JPEG" or image.size != (1280, 720):
                raise ValueError("source must be a 1280x720 JPEG")
        source_files[image_path] = frame["sha256"]
        if pa == at_bat:
            rel = f"frames/{pitch_id.replace(':', '_')}/{index}.jpg"
            images[rel] = image_bytes
            entry = visible_pitches.setdefault(
                pitch_id,
                {
                    "pitch_id": pitch_id,
                    "play_id": selection_meta[pitch_id]["play_id"],
                    "frames": [],
                },
            )
            entry["frames"].append(
                {
                    "frame_index": index,
                    "frame_seconds": seconds,
                    "image": rel,
                    "sha256": frame["sha256"],
                    "width": 1280,
                    "height": 720,
                    "selection": result,
                }
            )
    expected_pa = {key for key in annotations if key.startswith(f"747139:{at_bat}:")}
    if not expected_pa or set(visible_pitches) != expected_pa:
        raise ValueError("selected plate appearance is incomplete")
    for pitch in visible_pitches.values():
        by_index = {f["frame_index"]: f for f in pitch["frames"]}
        for frame in pitch["frames"]:
            history = frame["selection"]["last_historical_candidate"]
            if history is not None:
                source = by_index.get(history["frame_index"])
                if (
                    source is None
                    or source["frame_index"] > frame["frame_index"]
                    or source["selection"]["event"] != history
                ):
                    raise ValueError("historical event lacks its original past frame")
    if any(path.read_bytes() != raw[name] for name, path in paths.items()) or any(
        sha(path.read_bytes()) != digest for path, digest in source_files.items()
    ):
        raise ValueError("source changed during build")
    payload = {
        "schema": SCHEMA,
        "time_basis": "manifest_index_timebase",
        "independent_decoded_pts_verified": False,
        "pitches": list(visible_pitches.values()),
    }
    payload_text = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    template = (ASSETS / "index.html").read_text(encoding="utf-8")
    files = {
        # This builder carries no OCR observations; the page shows that explicitly.
        "index.html": fill_template(
            template,
            {
                "__TRACK_VIEW_DATA__": payload_text.replace("<", "\\u003c"),
                "__OCR_VIEW_DATA__": "null",
            },
        ).encode(),
        "review.js": (ASSETS / "review.js").read_bytes(),
        "style.css": (ASSETS / "style.css").read_bytes(),
        "payload.json": (payload_text + "\n").encode(),
        **images,
    }
    receipt = {
        "schema": "pitcheezy-track-frame-view-receipt-v1",
        "input_sha256": hashes,
        "validated_frames": len(planned),
        "validated_pitches": summary["pitches"],
        "displayed_frames": len(images),
        "displayed_pitches": len(visible_pitches),
        "at_bat": at_bat,
        "input_unchanged": True,
        "independent_decoded_pts_verified": False,
        "files": {
            name: {"sha256": sha(value), "bytes": len(value)} for name, value in files.items()
        },
    }
    out.mkdir(parents=True, exist_ok=False)
    for name, value in files.items():
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    (out / "receipt.json").write_text(json.dumps(receipt, indent=2) + "\n", encoding="utf-8")
    return receipt


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "bundle",
        "timing",
        "tracking-report",
        "tracking-records",
        "selection-report",
        "selection-records",
        "report-sha256",
        "out",
    ):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--at-bat", type=int, default=3)
    result = build(**vars(parser.parse_args()))
    print(
        json.dumps(
            {k: result[k] for k in ("validated_frames", "displayed_frames", "displayed_pitches")}
        )
    )


if __name__ == "__main__":
    main()

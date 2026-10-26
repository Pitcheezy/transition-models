"""Bind saved reacquisition results to the existing private OCR frame viewer.

This is a saved-record join, not an image tracker or a new OCR/model invocation. Existing
selectors validate the stored snapshots; no pixels are used to infer new coordinates.
Saved-record source_sha256 is the source frame JPEG byte hash, the same value as frame.sha256.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
import math
import re
from collections import Counter
from dataclasses import asdict
from pathlib import Path, PurePosixPath

from PIL import Image

from intent.mitt_ocr_view import _check_rows
from intent.mitt_reacquire import ReacquireParams, SegmentedStationarySelector
from intent.mitt_stationary import StationaryParams, StationarySelector
from intent.mitt_track_view import ASSETS, fill_template
from intent.mitt_tracking import TrackParams

COMPARISON_SCHEMA = "pitcheezy-reacquire-frame-comparison-dev-v1"
RECEIPT_SCHEMA = "pitcheezy-reacquire-frame-view-receipt-v1"
MAX_SAFE_INTEGER = 2**53 - 1


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _encoded(value):
    return json.dumps(value, ensure_ascii=False, sort_keys=True, allow_nan=False).encode()


def _same(left, right):
    # Python equality considers True == 1; evidence keys and snapshots must not do so.
    return _encoded(left) == _encoded(right)


def _json(raw):
    def integer(text):
        if len(text.lstrip("-")) > 16 or abs(value := int(text)) > MAX_SAFE_INTEGER:
            raise ValueError("integer exceeds the exact viewer range")
        return value

    def number(text):
        value = float(text)
        if not math.isfinite(value):
            raise ValueError("nonfinite JSON number")
        return value

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError("duplicate JSON key")
            result[key] = value
        return result

    def invalid(_text):
        raise ValueError("nonfinite JSON constant")

    try:
        if isinstance(raw, bytes):
            raw = raw.decode("utf-8")
        return json.loads(
            raw,
            parse_int=integer,
            parse_float=number,
            parse_constant=invalid,
            object_pairs_hook=unique,
        )
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("invalid JSON input") from None


def _pin(value):
    if not isinstance(value, str) or not re.fullmatch(r"[a-f0-9]{64}", value):
        raise ValueError("expected a lowercase SHA-256 pin")


def _key(row, *, pitch=None, image=False):
    pitch = row.get("pitch_id") if pitch is None else pitch
    index, seconds = row["frame_index"], row["frame_seconds"]
    if (
        not isinstance(pitch, str)
        or not re.fullmatch(r"[1-9]\d{0,9}:[1-9]\d{0,6}:[1-9]\d{0,6}", pitch)
        or type(index) is not int
        or not 0 <= index <= MAX_SAFE_INTEGER // 1001
        or type(seconds) not in (int, float)
        or not math.isfinite(seconds)
        or seconds != index * 1001 / 60000
    ):
        raise ValueError("invalid pitch/frame/time key")
    digest = row["sha256" if image else "source_sha256"]
    _pin(digest)
    if not image and (
        type(row["source_pts_ticks"]) is not int
        or row["source_pts_ticks"] != index * 1001
        or row["source_time_base"] != "1/60000"
    ):
        raise ValueError("invalid manifest timebase binding")
    return pitch, index, seconds, digest


def _point(point):
    if point is not None and (
        not isinstance(point, list)
        or len(point) != 2
        or any(type(v) not in (int, float) or not math.isfinite(v) for v in point)
        or not 0 <= point[0] < 1280
        or not 0 <= point[1] < 720
    ):
        raise ValueError("point outside the source image")


def _pack_files(pack, pin, bindings):
    raw = (pack / "receipt.json").read_bytes()
    if _sha(raw) != pin:
        raise ValueError("OCR pack receipt SHA mismatch")
    bindings[pack / "receipt.json"] = raw
    receipt = _json(raw)
    if (
        receipt["schema"] != "pitcheezy-ocr-frame-view-receipt-v1"
        or receipt["independent_decoded_pts_verified"] is not False
        or receipt["input_unchanged"] is not True
    ):
        raise ValueError("unsupported OCR pack receipt")
    files = {}
    for relative, record in receipt["files"].items():
        name = PurePosixPath(relative)
        if (
            not relative
            or name.is_absolute()
            or "\\" in relative
            or ":" in relative
            or ".." in name.parts
            or name.as_posix() != relative
            or relative == "receipt.json"
        ):
            raise ValueError("unsafe pack path")
        path = (pack / relative).resolve()
        if not path.is_relative_to(pack):
            raise ValueError("pack path escapes its root")
        raw = path.read_bytes()
        if (
            type(record["bytes"]) is not int
            or record["bytes"] != len(raw)
            or record["sha256"] != _sha(raw)
        ):
            raise ValueError("pack file size/SHA mismatch")
        files[relative], bindings[path] = raw, raw
    return receipt, files


def _records(base, candidate, report):
    if not isinstance(base, list) or not base or not isinstance(candidate, list):
        raise ValueError("records must be nonempty lists")
    base_keys, candidate_keys = [_key(r) for r in base], [_key(r) for r in candidate]
    if (
        len(set(base_keys)) != len(base_keys)
        or base_keys != candidate_keys
        or len({k[:2] for k in base_keys}) != len(base_keys)
    ):
        raise ValueError("full-record keys differ, duplicate, or are out of order")
    params = StationaryParams(**report["stationary_params"])
    reacquire = ReacquireParams(**report["reacquire_params"])
    track = TrackParams(**report["track_params"])
    for name, parameter in (("stationary", params), ("reacquire", reacquire), ("track", track)):
        if (
            not _same(asdict(parameter), report[name + "_params"])
            or parameter.digest() != report[name + "_params_sha256"]
        ):
            raise ValueError("parameter definition/digest mismatch")
    totals = report["metrics"]["totals"]
    expected = {
        "frames": len(base),
        "pitches": len({k[0] for k in base_keys}),
        "base_states": dict(Counter(r["state"] for r in base)),
        "candidate_states": dict(Counter(r["state"] for r in candidate)),
    }
    if any(not _same(totals[k], value) for k, value in expected.items()):
        raise ValueError("report counts differ from the saved rows")
    regression = report["base_regression"]
    if regression["equal_to_saved_records"] is not True or not _same(regression["rows"], len(base)):
        raise ValueError("unsupported baseline regression evidence")
    indexed, baseline_selections, seen, pitch = {}, {}, set(), None
    for original, row, key in zip(base, candidate, base_keys, strict=True):
        if key[0] != pitch:
            if key[0] in seen:
                raise ValueError("a pitch reappears after another pitch")
            pitch = key[0]
            seen.add(pitch)
            base_selector, selector = (
                StationarySelector(params),
                SegmentedStationarySelector(params),
            )
            prior, count, segment = "unseeded", 0, 0
        for value in (original["point_px"], row["point_px"], row["reacquire_candidate_px"]):
            _point(value)
        state, reason = row["state"], row["reason"]
        if row["prior_state"] != prior or (prior == "lost" and state != "lost"):
            raise ValueError("invalid recorded prior/terminal state")
        if type(row["reacquisitions"]) is not int:
            raise ValueError("invalid reacquisition count")
        if reason == "reacquired_continuity":
            if prior != "reacquire_candidate":
                raise ValueError("reacquisition lacks its previous candidate frame")
            count += 1
            segment += 1
        elif reason == "external_seed":
            if prior != "unseeded" or segment:
                raise ValueError("implicit reseeding")
            segment = 1
        if row["reacquisitions"] != count or count > reacquire.max_reacquisitions:
            raise ValueError("reacquisition count does not match segment starts")
        if state in ("reacquire_candidate", "reacquire_search") and not segment:
            raise ValueError("search without a previously confirmed segment")
        if state == "tracking" and (
            type(row["segment_id"]) is not int or row["segment_id"] != segment
        ):
            raise ValueError("segment id does not match confirmed starts")
        baseline_selections[key] = base_selector.step(original)
        expected_selection = selector.step(row)
        if not _same(expected_selection, row["stationary"]):
            raise ValueError("stored stationary snapshot differs from validated saved rows")
        indexed[key] = row
        prior = state
    return indexed, baseline_selections, expected


def build(
    *,
    pack,
    pack_receipt_sha256,
    candidate_report,
    candidate_report_sha256,
    candidate_records,
    baseline_records,
    ocr_observations,
    out,
):
    """Create a new comparison pack without changing or re-running any source artifacts."""
    try:
        return _build(
            pack=pack,
            pack_receipt_sha256=pack_receipt_sha256,
            candidate_report=candidate_report,
            candidate_report_sha256=candidate_report_sha256,
            candidate_records=candidate_records,
            baseline_records=baseline_records,
            ocr_observations=ocr_observations,
            out=out,
        )
    except (KeyError, TypeError, IndexError, AttributeError, OverflowError):
        raise ValueError("malformed comparison input") from None


def _build(**args):
    pack, out = Path(args["pack"]).resolve(), Path(args["out"]).resolve()
    if out == pack or out.is_relative_to(pack):
        raise ValueError("output must be outside the input pack")
    if out.exists():
        raise FileExistsError(out)
    _pin(args["pack_receipt_sha256"])
    _pin(args["candidate_report_sha256"])
    bindings = {}
    receipt, files = _pack_files(pack, args["pack_receipt_sha256"], bindings)
    raw = {}
    for name in ("candidate_report", "candidate_records", "baseline_records", "ocr_observations"):
        path = Path(args[name]).resolve()
        raw[name] = bindings[path] = path.read_bytes()
    hashes = {name: _sha(value) for name, value in raw.items()}
    if hashes["candidate_report"] != args["candidate_report_sha256"]:
        raise ValueError("candidate report SHA mismatch")
    report = _json(raw["candidate_report"])
    if (
        report["schema"] != "pitcheezy-mitt-reacquire-pilot-dev-v1"
        or report["device"] != "cpu"
        or report["candidate_records_sha256"] != hashes["candidate_records"]
        or report["saved_tracking_records_sha256"] != hashes["baseline_records"]
        or receipt["input_sha256"]["ocr_observations"] != hashes["ocr_observations"]
    ):
        raise ValueError("saved records do not match their pinned evidence")
    rows, selections, counts = _records(
        _json(raw["baseline_records"]), _json(raw["candidate_records"]), report
    )
    original_payload = _json(files["payload.json"])
    payload = copy.deepcopy(original_payload)
    if (
        payload["schema"] != "pitcheezy-track-frame-view-dev-v1"
        or payload["time_basis"] != "manifest_index_timebase"
        or payload["independent_decoded_pts_verified"] is not False
        or "comparison_schema" in payload
    ):
        raise ValueError("unsupported source frame payload")
    visible, images, all_keys = {}, {}, []
    for pitch in payload["pitches"]:
        pitch_id = pitch["pitch_id"]
        if pitch_id in visible or not pitch["frames"]:
            raise ValueError("duplicate or empty displayed pitch")
        frame_keys = [_key(f, pitch=pitch_id, image=True) for f in pitch["frames"]]
        if frame_keys != [key for key in rows if key[0] == pitch_id]:
            raise ValueError("displayed pitch does not cover its full saved frame stream")
        visible[pitch_id] = []
        for frame, key in zip(pitch["frames"], frame_keys, strict=True):
            if (
                type(frame["width"]) is not int
                or type(frame["height"]) is not int
                or (frame["width"], frame["height"]) != (1280, 720)
                or "reacquire" in frame
                or not _same(frame["selection"], selections[key])
            ):
                raise ValueError("baseline display selection or dimensions differ")
            image = files[frame["image"]]
            if _sha(image) != frame["sha256"] or frame["image"] in images:
                raise ValueError("displayed image binding differs or is reused")
            try:
                with Image.open(io.BytesIO(image)) as decoded:
                    decoded.load()
                    if decoded.format != "JPEG" or decoded.size != (1280, 720):
                        raise ValueError("displayed image must be a 1280x720 JPEG")
            except (OSError, Image.DecompressionBombError):
                raise ValueError("displayed image cannot be safely decoded") from None
            row = rows[key]
            frame["reacquire"] = {
                "tracking": {k: copy.deepcopy(v) for k, v in row.items() if k != "stationary"},
                "selection": copy.deepcopy(row["stationary"]),
            }
            images[frame["image"]] = image
            visible[pitch_id].append((frame, image))
            all_keys.append(key)
    if not visible:
        raise ValueError("empty displayed payload")
    observations, ocr = _json(raw["ocr_observations"]), _json(files["ocr.json"])
    if (
        observations["schema"] != "pitcheezy-frame-name-observations-dev-v1"
        or ocr["schema"] != "pitcheezy-ocr-frame-view-dev-v1"
        or any(x["time_basis"] != "manifest_index_timebase" for x in (observations, ocr))
        or any(x["independent_decoded_pts_verified"] is not False for x in (observations, ocr))
    ):
        raise ValueError("unsupported saved OCR metadata")
    observed_pitch = observations["pitch_id"]
    expected_ocr = [{"pitch_id": observed_pitch, "rows": observations["rows"]}]
    if not _same(ocr["pitches"], expected_ocr) or not _same(
        ocr["pitches_without_observations"], [p for p in visible if p != observed_pitch]
    ):
        raise ValueError("displayed OCR differs from the original observations")
    _check_rows(observations["rows"], visible[observed_pitch], observed_pitch)
    payload["comparison_schema"] = COMPARISON_SCHEMA
    baseline_check = copy.deepcopy(payload)
    del baseline_check["comparison_schema"]
    for pitch in baseline_check["pitches"]:
        for frame in pitch["frames"]:
            del frame["reacquire"]
    if not _same(baseline_check, original_payload):
        raise ValueError("baseline payload changed during the join")
    payload_text = json.dumps(payload, ensure_ascii=False, allow_nan=False)
    page = fill_template(
        (ASSETS / "index.html").read_text(encoding="utf-8"),
        {
            "__TRACK_VIEW_DATA__": payload_text.replace("<", "\\u003c"),
            "__OCR_VIEW_DATA__": files["ocr.json"].decode("utf-8").replace("<", "\\u003c"),
        },
    )
    output = {
        "index.html": page.encode(),
        "review.js": (ASSETS / "review.js").read_bytes(),
        "style.css": (ASSETS / "style.css").read_bytes(),
        "payload.json": (payload_text + "\n").encode(),
        "ocr.json": files["ocr.json"],
        **images,
    }
    if any(path.read_bytes() != value for path, value in bindings.items()):
        raise ValueError("an input changed during the join")
    result = {
        "schema": RECEIPT_SCHEMA,
        "comparison_schema": COMPARISON_SCHEMA,
        "input_sha256": {
            "ocr_pack_receipt": args["pack_receipt_sha256"],
            "ocr_pack_payload": _sha(files["payload.json"]),
            "ocr_pack_observations": _sha(files["ocr.json"]),
            **hashes,
        },
        "all_record_keys_checked": counts["frames"],
        "all_record_pitches": counts["pitches"],
        "displayed_frames": len(all_keys),
        "displayed_pitches": len(visible),
        "observation_rows_bound": len(observations["rows"]),
        "baseline_selections_checked": len(selections),
        "candidate_selections_checked": len(rows),
        "baseline_fields_preserved": True,
        "ocr_bytes_preserved": True,
        "frame_images_unchanged": True,
        "input_unchanged": True,
        "independent_decoded_pts_verified": False,
        "no_new_ocr_calls": True,
        "no_new_tracking_or_model_calls": True,
        "evidence_kind": "saved development record join; not mitt identity or accuracy",
        "files": {
            name: {"sha256": _sha(value), "bytes": len(value)} for name, value in output.items()
        },
    }
    out.mkdir(parents=True, exist_ok=False)
    for name, value in output.items():
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    (out / "receipt.json").write_bytes(_encoded(result) + b"\n")
    return result


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in (
        "pack",
        "pack-receipt-sha256",
        "candidate-report",
        "candidate-report-sha256",
        "candidate-records",
        "baseline-records",
        "ocr-observations",
        "out",
    ):
        parser.add_argument("--" + name, required=True)
    receipt = build(**vars(parser.parse_args()))
    print(
        json.dumps(
            {
                k: receipt[k]
                for k in (
                    "all_record_keys_checked",
                    "displayed_frames",
                    "observation_rows_bound",
                )
            }
        )
    )


if __name__ == "__main__":
    main()

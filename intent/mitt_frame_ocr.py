"""Current-frame name OCR on a private, hash-bound frame pack; no identity inference.

The timestamp basis stays manifest-derived. Literal agreement between adjacent reads is
not player continuity, correctness, or a replacement detector. No name is filled forward.
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
from pathlib import Path

from PIL import Image

ROLES = ("pitcher", "batter")
FIELDS = {"raw_text", "name_text", "lineup_order", "status", "reason"}
ROOT = Path(__file__).resolve().parents[1]
CODE = (
    "intent/mitt_frame_ocr.py",
    "src/vision/sny_player_names.py",
    "src/vision/sny_scoreboard.py",
    "src/vision/windows_ocr.ps1",
)


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _number(value):
    try:
        return type(value) in (int, float) and math.isfinite(value) and value >= 0
    except OverflowError:
        return False


def _encoded(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def _error(reason):
    return {
        "raw_text": "",
        "name_text": None,
        "lineup_order": None,
        "status": "error",
        "reason": reason,
    }


def _reading(value, role):
    """Keep valid current readings; never serialize native exception messages or traces."""
    if not isinstance(value, dict) or set(value) != FIELDS:
        return _error("invalid_reader_output")
    result = copy.deepcopy(value)
    status, name, order = result["status"], result["name_text"], result["lineup_order"]
    if (
        status not in ("read", "abstain", "error")
        or not isinstance(result["raw_text"], str)
        or not isinstance(result["reason"], str)
        or (status == "read") != (isinstance(name, str) and bool(name.strip()))
        or (status != "read" and name is not None)
        or (
            order is not None
            and (role != "batter" or type(order) is not int or not 1 <= order <= 9)
        )
        or (status == "error" and order is not None)
    ):
        return _error("invalid_reader_output")
    if status == "error":
        pieces = result["reason"].split(":")
        category = (
            pieces[1]
            if len(pieces) > 1 and re.fullmatch(r"[A-Za-z][A-Za-z0-9_]{0,80}", pieces[1])
            else "unspecified"
        )
        prefix = pieces[0] if pieces[0] in ("engine_error", "reader_exception") else "engine_error"
        return _error(prefix + ":" + category)
    if not re.fullmatch(r"[a-z][a-z0-9_]{0,100}", result["reason"]):
        result["reason"] = "reader_reason_redacted"
    return result


def _inputs(pack, receipt_sha256, pitch_id):
    if not isinstance(pitch_id, str) or not re.fullmatch(r"747139:[1-9]\d*:[1-9]\d*", pitch_id):
        raise ValueError("invalid requested pitch key")
    receipt_path = pack / "receipt.json"
    receipt_raw = receipt_path.read_bytes()
    if _sha(receipt_raw) != receipt_sha256:
        raise ValueError("receipt SHA mismatch")
    receipt = json.loads(receipt_raw)
    if (
        receipt.get("schema") != "pitcheezy-track-frame-view-receipt-v1"
        or receipt.get("independent_decoded_pts_verified") is not False
    ):
        raise ValueError("unsupported pack receipt")
    bindings = {receipt_path: receipt_raw}

    def bound(relative):
        path = (pack / relative).resolve()
        if not path.is_relative_to(pack):
            raise ValueError("input path escapes pack")
        record = receipt["files"][relative]
        raw = path.read_bytes()
        if (
            type(record["bytes"]) is not int
            or len(raw) != record["bytes"]
            or _sha(raw) != record["sha256"]
        ):
            raise ValueError("pack artifact size/SHA mismatch")
        bindings[path] = raw
        return raw

    payload_raw = bound("payload.json")
    payload = json.loads(payload_raw)
    if (
        payload.get("schema") != "pitcheezy-track-frame-view-dev-v1"
        or payload.get("time_basis") != "manifest_index_timebase"
        or payload.get("independent_decoded_pts_verified") is not False
    ):
        raise ValueError("unsupported payload time basis")
    pitches = payload.get("pitches")
    if not isinstance(pitches, list) or not pitches:
        raise ValueError("pitch list required")
    ids = [p["pitch_id"] for p in pitches]
    if len(set(ids)) != len(ids) or ids.count(pitch_id) != 1:
        raise ValueError("requested pitch missing or duplicated")
    frames = pitches[ids.index(pitch_id)]["frames"]
    if not isinstance(frames, list) or not frames:
        raise ValueError("nonempty frame list required")
    selected, previous_index, previous_time = [], -1, -1
    for frame in frames:
        index, seconds = frame["frame_index"], frame["frame_seconds"]
        if (
            type(index) is not int
            or index < 0
            or not _number(seconds)
            or index <= previous_index
            or seconds <= previous_time
            or abs(seconds - index * 1001 / 60000) > 1e-9
            or (frame["width"], frame["height"]) != (1280, 720)
        ):
            raise ValueError("invalid frame order, dimensions or manifest time")
        selection = frame["selection"]
        if (
            selection["pitch_id"] != pitch_id
            or selection["frame_index"] != index
            or selection["frame_seconds"] != seconds
        ):
            raise ValueError("frame belongs to a different pitch/time")
        expected = f"frames/{pitch_id.replace(':', '_')}/{index}.jpg"
        if frame["image"] != expected:
            raise ValueError("unexpected frame path")
        raw = bound(expected)
        if _sha(raw) != frame["sha256"]:
            raise ValueError("payload image SHA mismatch")
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
            if image.format != "JPEG" or image.size != (1280, 720):
                raise ValueError("expected original 1280x720 JPEG")
        selected.append((frame, raw))
        previous_index, previous_time = index, seconds
    return selected, bindings, _sha(payload_raw)


def run(pack, receipt_sha256, out, pitch_id="747139:3:1", reader=None):
    """Validate every selected frame before initializing or invoking the image-only reader."""
    pack, out = Path(pack).resolve(), Path(out).resolve()
    if out == pack or out.is_relative_to(pack):
        raise ValueError("output must be outside input pack")
    if out.exists():
        raise FileExistsError(out)
    frames, bindings, payload_sha = _inputs(pack, receipt_sha256, pitch_id)
    from src.vision.sny_player_names import CONFIG_V2, SNYPlayerNameReader

    injected = reader is not None
    if reader is None:
        try:
            reader = SNYPlayerNameReader(config=CONFIG_V2)
        except Exception as exc:
            raise RuntimeError("OCR reader initialization failed: " + type(exc).__name__) from None
    metadata = copy.deepcopy(reader.metadata())
    if (
        not isinstance(metadata, dict)
        or metadata.get("config") != CONFIG_V2
        or not isinstance(metadata.get("engine"), dict)
    ):
        raise ValueError("reader must declare the frozen v2 configuration and engine")
    # Engine metadata is an allowlist: executable locations and exception text stay out.
    engine = {}
    for key in ("engine", "language", "os_version", "dll_version"):
        value = metadata["engine"].get(key)
        if isinstance(value, str):
            engine[key] = "redacted" if re.search(r"[\\/]|[A-Za-z]:", value) else value
    if not engine.get("engine"):
        raise ValueError("engine identity required")
    rows, previous = [], {}
    counts = {role: Counter() for role in ROLES}
    for frame, raw in frames:
        with Image.open(io.BytesIO(raw)) as source:
            image = source.convert("RGB")
        try:
            output = reader.read(image)
        except Exception as exc:
            output = {role: _error("reader_exception:" + type(exc).__name__) for role in ROLES}
        finally:
            image.close()
        readings = {}
        for role in ROLES:
            value = _reading(output.get(role) if isinstance(output, dict) else None, role)
            prior = previous.pop(role, None)
            relation, prior_frame = "not_compared", None
            if value["status"] == "read":
                if prior is not None and frame["frame_seconds"] - prior["seconds"] <= 0.25:
                    relation = (
                        "literal_same" if value["name_text"] == prior["name"] else "literal_changed"
                    )
                    prior_frame = prior["frame_index"]
                previous[role] = {
                    "name": value["name_text"],
                    "seconds": frame["frame_seconds"],
                    "frame_index": frame["frame_index"],
                }
            readings[role] = {
                **value,
                "temporal_relation": relation,
                "compared_to_frame": prior_frame,
            }
            counts[role][value["status"]] += 1
            counts[role][relation] += 1
        rows.append(
            {
                "pitch_id": pitch_id,
                "frame_index": frame["frame_index"],
                "frame_seconds": frame["frame_seconds"],
                "image_sha256": frame["sha256"],
                "roles": readings,
            }
        )
    if any(path.read_bytes() != original for path, original in bindings.items()):
        raise ValueError("input changed during OCR")
    observations = {
        "schema": "pitcheezy-frame-name-observations-dev-v1",
        "time_basis": "manifest_index_timebase",
        "independent_decoded_pts_verified": False,
        "pitch_id": pitch_id,
        "rows": rows,
    }
    observations_raw = _encoded(observations)
    report = {
        "schema": "pitcheezy-frame-name-ocr-report-dev-v1",
        "evidence_kind": "injected reader test"
        if injected
        else "local Windows OCR exposed development",
        "pitch_id": pitch_id,
        "frames": len(rows),
        "roles": {role: dict(counts[role]) for role in ROLES},
        "receipt_sha256": receipt_sha256,
        "payload_sha256": payload_sha,
        "reader_metadata": {"engine": engine, "config": copy.deepcopy(CONFIG_V2)},
        "source_sha256": {name: _sha((ROOT / name).read_bytes()) for name in CODE},
        "observations_sha256": _sha(observations_raw),
        "input_unchanged": True,
        "independent_decoded_pts_verified": False,
        "limits": [
            "Current literal readings only; no identity, backfill or confirmed continuity.",
            "Same/changed compares adjacent current reads within 0.25 seconds, not accuracy.",
            "Manifest-derived timestamps; no new decoded PTS, video or human evaluation.",
        ],
    }
    out.mkdir(parents=True, exist_ok=False)
    (out / "observations.json").write_bytes(observations_raw)
    (out / "report.json").write_bytes(_encoded(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for field in ("pack", "receipt-sha256", "out"):
        parser.add_argument("--" + field, required=True)
    parser.add_argument("--pitch-id", default="747139:3:1")
    report = run(**vars(parser.parse_args()))
    print(json.dumps({"frames": report["frames"], "roles": report["roles"]}))


if __name__ == "__main__":
    main()

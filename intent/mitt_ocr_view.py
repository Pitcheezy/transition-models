"""Join saved frame-name OCR observations to the private frame replay, frame by exact frame.

The builder only consumes two hash-bound development artifacts: a CV39a frame-view pack and a
CV39b OCR run (report + observations). Every OCR row must match one displayed frame on
``pitch_id``, ``frame_index``, ``frame_seconds`` and ``image_sha256``; nothing is inferred,
filled forward, corrected or re-read. Pitches without an OCR run are marked as having no
observation data, which the page shows apart from abstentions and engine errors.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import math
import re
from collections import Counter
from pathlib import Path

from intent.mitt_frame_ocr import FIELDS, ROLES, _validated_inputs
from intent.mitt_track_view import ASSETS, fill_template

SCHEMA = "pitcheezy-ocr-frame-view-dev-v1"
RECEIPT_SCHEMA = "pitcheezy-ocr-frame-view-receipt-v1"
OCR_REPORT_SCHEMA = "pitcheezy-frame-name-ocr-report-dev-v1"
OBSERVATIONS_SCHEMA = "pitcheezy-frame-name-observations-dev-v1"
RELATIONS = ("not_compared", "literal_same", "literal_changed")
ROLE_FIELDS = FIELDS | {"temporal_relation", "compared_to_frame"}
COMPARISON_WINDOW_SECONDS = 0.25


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def _load_json(raw):
    try:
        return json.loads(raw)
    except (UnicodeDecodeError, json.JSONDecodeError):
        raise ValueError("invalid JSON input") from None


def _check_role(value, role):
    """Accept only the saved CV39b row shape; reject anything the viewer would have to guess."""
    if not isinstance(value, dict) or set(value) != ROLE_FIELDS:
        raise ValueError("observation role fields differ")
    status, name, order = value["status"], value["name_text"], value["lineup_order"]
    if status not in ("read", "abstain", "error"):
        raise ValueError("unknown observation status")
    if not isinstance(value["raw_text"], str) or not isinstance(value["reason"], str):
        raise ValueError("observation text fields must be strings")
    if (status == "read") != (isinstance(name, str) and bool(name.strip())):
        raise ValueError("read status and name_text disagree")
    if status != "read" and name is not None:
        raise ValueError("non-read rows must not carry a name")
    if order is not None and (
        role != "batter" or type(order) is not int or not 1 <= order <= 9 or status == "error"
    ):
        raise ValueError("invalid lineup_order")
    if value["temporal_relation"] not in RELATIONS:
        raise ValueError("unknown temporal_relation")
    compared = value["compared_to_frame"]
    if compared is not None and (type(compared) is not int or compared < 0):
        raise ValueError("invalid compared_to_frame")


def _check_rows(rows, frames, pitch_id):
    """Rows must be the exact displayed frames in order, with self-consistent comparisons."""
    if not isinstance(rows, list) or len(rows) != len(frames):
        raise ValueError("observation count differs from displayed frames")
    previous = {}
    for row, (frame, _raw) in zip(rows, frames, strict=True):
        if not isinstance(row, dict) or set(row) != {
            "pitch_id",
            "frame_index",
            "frame_seconds",
            "image_sha256",
            "roles",
        }:
            raise ValueError("observation row fields differ")
        if (
            not isinstance(row["pitch_id"], str)
            or type(row["frame_index"]) is not int
            or type(row["frame_seconds"]) not in (int, float)
            or not math.isfinite(row["frame_seconds"])
            or not isinstance(row["image_sha256"], str)
        ):
            raise ValueError("observation key types are invalid")
        if (
            row["pitch_id"] != pitch_id
            or row["frame_index"] != frame["frame_index"]
            or row["frame_seconds"] != frame["frame_seconds"]
            or row["image_sha256"] != frame["sha256"]
        ):
            raise ValueError("observation key does not match the displayed frame")
        roles = row["roles"]
        if not isinstance(roles, dict) or set(roles) != set(ROLES):
            raise ValueError("observation roles differ")
        for role in ROLES:
            value = roles[role]
            _check_role(value, role)
            prior = previous.pop(role, None)
            relation, compared = "not_compared", None
            if value["status"] == "read":
                if (
                    prior is not None
                    and row["frame_seconds"] - prior["seconds"] <= COMPARISON_WINDOW_SECONDS
                ):
                    relation = (
                        "literal_same" if value["name_text"] == prior["name"] else "literal_changed"
                    )
                    compared = prior["frame_index"]
                previous[role] = {
                    "name": value["name_text"],
                    "seconds": row["frame_seconds"],
                    "frame_index": row["frame_index"],
                }
            if (value["temporal_relation"], value["compared_to_frame"]) != (relation, compared):
                raise ValueError("saved comparison does not follow the adjacent-read rule")


def _check_report_counts(report, rows):
    counts = {role: Counter() for role in ROLES}
    comparison = {
        role: {"read": dict.fromkeys(RELATIONS, 0), "non_read_count": 0} for role in ROLES
    }
    for row in rows:
        for role in ROLES:
            value = row["roles"][role]
            counts[role][value["status"]] += 1
            counts[role][value["temporal_relation"]] += 1
            if value["status"] == "read":
                comparison[role]["read"][value["temporal_relation"]] += 1
            else:
                comparison[role]["non_read_count"] += 1
    if report.get("roles") != {role: dict(counts[role]) for role in ROLES}:
        raise ValueError("report role counts differ from observations")
    if "comparison_summary" in report and report["comparison_summary"] != comparison:
        raise ValueError("report comparison summary differs from observations")
    return comparison


def _pitch_frames(pack, receipt_sha256, pitch_id):
    try:
        return _validated_inputs(pack, receipt_sha256, pitch_id)
    except (ValueError, KeyError, TypeError, OSError, AttributeError, OverflowError):
        raise ValueError("malformed frame-view pack") from None


def build(*, pack, pack_receipt_sha256, ocr_dir, ocr_report_sha256, out, ocr_source_receipt=None):
    pack, ocr_dir, out = Path(pack).resolve(), Path(ocr_dir).resolve(), Path(out).resolve()
    for source in (pack, ocr_dir):
        if out == source or out.is_relative_to(source):
            raise ValueError("output must be outside the inputs")
    if out.exists():
        raise FileExistsError(out)
    if not re.fullmatch(r"[a-f0-9]{64}", pack_receipt_sha256 or "") or not re.fullmatch(
        r"[a-f0-9]{64}", ocr_report_sha256 or ""
    ):
        raise ValueError("expected lowercase SHA-256 pins")

    # OCR run: report pin -> observations -> the payload the reader actually saw.
    report_raw = (ocr_dir / "report.json").read_bytes()
    if _sha(report_raw) != ocr_report_sha256:
        raise ValueError("OCR report SHA mismatch")
    report = _load_json(report_raw)
    if (
        not isinstance(report, dict)
        or report.get("schema") != OCR_REPORT_SCHEMA
        or report.get("independent_decoded_pts_verified") is not False
        or report.get("input_unchanged") is not True
    ):
        raise ValueError("unsupported OCR report")
    observations_raw = (ocr_dir / "observations.json").read_bytes()
    if _sha(observations_raw) != report.get("observations_sha256"):
        raise ValueError("observations SHA differs from the OCR report")
    observations = _load_json(observations_raw)
    if (
        not isinstance(observations, dict)
        or observations.get("schema") != OBSERVATIONS_SCHEMA
        or observations.get("time_basis") != "manifest_index_timebase"
        or observations.get("independent_decoded_pts_verified") is not False
    ):
        raise ValueError("unsupported observations file")
    pitch_id = observations.get("pitch_id")
    if report.get("pitch_id") != pitch_id or not isinstance(pitch_id, str):
        raise ValueError("OCR report and observations name different pitches")
    rows = observations.get("rows")
    if not isinstance(rows, list) or report.get("frames") != len(rows):
        raise ValueError("OCR report frame count differs from observations")

    # Display pack: receipt pin -> payload -> every frame image, for every displayed pitch.
    receipt_raw = (pack / "receipt.json").read_bytes()
    if _sha(receipt_raw) != pack_receipt_sha256:
        raise ValueError("frame-view receipt SHA mismatch")
    receipt = _load_json(receipt_raw)
    payload_raw = (pack / "payload.json").read_bytes()
    if _sha(payload_raw) != report.get("payload_sha256"):
        raise ValueError("OCR was produced for a different payload")
    payload = _load_json(payload_raw)
    pitch_ids = [p.get("pitch_id") for p in payload.get("pitches", [])]
    if not pitch_ids or len(set(pitch_ids)) != len(pitch_ids) or pitch_id not in pitch_ids:
        raise ValueError("OCR pitch is not one displayed pitch")
    bound, bindings, images = {}, {}, {}
    for displayed in pitch_ids:
        frames, pitch_bindings, payload_sha = _pitch_frames(pack, pack_receipt_sha256, displayed)
        if payload_sha != report["payload_sha256"]:
            raise ValueError("payload binding changed between pitches")
        bound[displayed] = frames
        bindings.update(pitch_bindings)
        for frame, raw in frames:
            images[frame["image"]] = (raw, frame["sha256"])
    _check_rows(rows, bound[pitch_id], pitch_id)
    comparison = _check_report_counts(report, rows)

    # Optional: the receipt of the pack the OCR actually ran on (v2) must agree on payload and
    # frames with the pack displayed now (v3); only the page files may differ.
    source_receipt_sha = report.get("receipt_sha256")
    source_binding = {
        "ocr_source_receipt_sha256": source_receipt_sha,
        "display_pack_receipt_sha256": pack_receipt_sha256,
        "same_receipt": source_receipt_sha == pack_receipt_sha256,
        "source_receipt_checked": False,
    }
    if ocr_source_receipt is not None:
        source_raw = Path(ocr_source_receipt).read_bytes()
        if _sha(source_raw) != source_receipt_sha:
            raise ValueError("OCR source receipt SHA differs from the OCR report")
        source = _load_json(source_raw)
        names = ["payload.json", *sorted(images)]
        try:
            differing = [
                name
                for name in names
                if {k: source["files"][name][k] for k in ("sha256", "bytes")}
                != {k: receipt["files"][name][k] for k in ("sha256", "bytes")}
            ]
        except (KeyError, TypeError):
            raise ValueError("OCR source receipt lacks a displayed file") from None
        if differing:
            raise ValueError("OCR source pack and display pack differ on data files")
        source_binding.update(source_receipt_checked=True, data_files_compared=len(names))

    ocr_rows = copy.deepcopy(rows)
    ocr_data = {
        "schema": SCHEMA,
        "time_basis": "manifest_index_timebase",
        "independent_decoded_pts_verified": False,
        "evidence_kind": report.get("evidence_kind"),
        "engine": {
            k: v
            for k, v in (report.get("reader_metadata", {}).get("engine") or {}).items()
            if isinstance(v, str) and not re.search(r"[\\/]|[A-Za-z]:", v)
        },
        "pitches": [{"pitch_id": pitch_id, "rows": ocr_rows}],
        "pitches_without_observations": [p for p in pitch_ids if p != pitch_id],
        "display_rule": {
            "join": ["pitch_id", "frame_index", "frame_seconds", "image_sha256"],
            "no_fill_forward": True,
            "no_correction": True,
            "no_identity_or_substitution_claim": True,
        },
    }
    if (
        any(path.read_bytes() != raw for path, raw in bindings.items())
        or (ocr_dir / "observations.json").read_bytes() != observations_raw
    ):
        raise ValueError("input changed during build")
    track_text = payload_raw.decode("utf-8").rstrip("\n")
    ocr_text = json.dumps(ocr_data, ensure_ascii=False, allow_nan=False)
    page = fill_template(
        (ASSETS / "index.html").read_text(encoding="utf-8"),
        {
            "__TRACK_VIEW_DATA__": track_text.replace("<", "\\u003c"),
            "__OCR_VIEW_DATA__": ocr_text.replace("<", "\\u003c"),
        },
    )
    files = {
        "index.html": page.encode(),
        "review.js": (ASSETS / "review.js").read_bytes(),
        "style.css": (ASSETS / "style.css").read_bytes(),
        "payload.json": payload_raw,
        "ocr.json": (ocr_text + "\n").encode(),
        **{name: raw for name, (raw, _digest) in images.items()},
    }
    receipt_out = {
        "schema": RECEIPT_SCHEMA,
        "input_sha256": {
            "frame_view_receipt": pack_receipt_sha256,
            "frame_view_payload": report["payload_sha256"],
            "ocr_report": ocr_report_sha256,
            "ocr_observations": report["observations_sha256"],
        },
        "ocr_source_binding": source_binding,
        "displayed_pitches": len(pitch_ids),
        "displayed_frames": len(images),
        "pitches_with_observations": [pitch_id],
        "pitches_without_observations": ocr_data["pitches_without_observations"],
        "observation_rows_bound": len(rows),
        "comparison_summary_recount": comparison,
        "input_unchanged": True,
        "independent_decoded_pts_verified": False,
        "no_new_ocr_calls": True,
        "files": {
            name: {"sha256": _sha(value), "bytes": len(value)} for name, value in files.items()
        },
    }
    out.mkdir(parents=True, exist_ok=False)
    for name, value in files.items():
        path = out / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_bytes(value)
    (out / "receipt.json").write_text(json.dumps(receipt_out, indent=2) + "\n", encoding="utf-8")
    return receipt_out


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("pack", "pack-receipt-sha256", "ocr-dir", "ocr-report-sha256", "out"):
        parser.add_argument("--" + name, required=True)
    parser.add_argument("--ocr-source-receipt", default=None)
    receipt = build(**vars(parser.parse_args()))
    print(
        json.dumps(
            {
                key: receipt[key]
                for key in (
                    "displayed_pitches",
                    "displayed_frames",
                    "observation_rows_bound",
                    "pitches_without_observations",
                )
            }
        )
    )


if __name__ == "__main__":
    main()

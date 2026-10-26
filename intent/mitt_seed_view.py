"""Join saved CV42 seed-gate decisions and tracks to all development replay frames.

Only the metadata gate and stationary selectors are replayed. Image bytes are checked and
copied, never passed to a tracker or OCR model. Saved AI observations are not human truth.
"""

from __future__ import annotations

import argparse
import copy
import io
import json
import math
from collections import Counter
from pathlib import Path

from PIL import Image

from intent import mitt_tracking_pilot as inputs
from intent.mitt_ocr_view import _check_rows
from intent.mitt_reacquire import ReacquireParams, SegmentedStationarySelector
from intent.mitt_reacquire_view import _encoded, _json, _key, _pack_files, _pin, _point, _same, _sha
from intent.mitt_seed_gate import POLICY, POLICY_SHA256
from intent.mitt_seed_pilot import choose, summarize
from intent.mitt_track_view import ASSETS, fill_template

COMPARISON_SCHEMA = "pitcheezy-seed-gate-frame-comparison-dev-v1"
RECEIPT_SCHEMA = "pitcheezy-seed-gate-frame-view-receipt-v1"


def _rows(rows, keys, seeds, *, gated):
    """Check causal row/segment structure and replay only the stationary selector."""
    if not isinstance(rows, list) or [_key(r) for r in rows] != keys:
        raise ValueError("saved rows differ from the complete manifest frame keys")
    current, seen = None, set()
    for row, key in zip(rows, keys, strict=True):
        pitch, index = key[:2]
        if pitch != current:
            if pitch in seen:
                raise ValueError("pitch reappears after another pitch")
            current = pitch
            seen.add(pitch)
            selector = SegmentedStationarySelector()
            prior, segment, count = "unseeded", 0, 0
        for field in ("point_px", "reacquire_candidate_px", "raw_ai_point_px"):
            _point(row[field])
        _point(row.get("seed_requested_px"))
        seed = seeds[pitch]
        is_seed = seed is not None and index == seed[0]
        if (row["reason"] == "external_seed") != is_seed:
            raise ValueError("saved external seed differs from the current seed decision")
        if is_seed:
            if (
                row["state"] != "tracking"
                or prior != "unseeded"
                or not _same(row["seed_requested_px"], seed[1])
                or not _same(row["point_px"], [math.floor(v + 0.5) for v in seed[1]])
                or (gated and row["seed_source"] != "saved_AI_seed_gate_dev_v1_current_observation")
            ):
                raise ValueError("saved seed point or provenance differs")
            segment = 1
        elif row.get("seed_requested_px") is not None or row["seed_source"] is not None:
            raise ValueError("seed evidence on a non-seed frame")
        if seed is None or index < seed[0]:
            if row["state"] != "unseeded":
                raise ValueError("tracking before seed eligibility")
        elif row["state"] == "unseeded":
            raise ValueError("seeded pitch returned to unseeded")
        if row["prior_state"] != prior or (prior == "lost" and row["state"] != "lost"):
            raise ValueError("invalid prior or terminal tracker state")
        if row["reason"] == "reacquired_continuity":
            if prior != "reacquire_candidate" or not segment:
                raise ValueError("reacquisition lacks a previous candidate")
            segment += 1
            count += 1
        if (
            type(row["reacquisitions"]) is not int
            or row["reacquisitions"] != count
            or count > ReacquireParams().max_reacquisitions
            or (row["state"] == "tracking" and row["segment_id"] != segment)
        ):
            raise ValueError("invalid segment or reacquisition count")
        if not _same(selector.step(row), row["stationary"]):
            raise ValueError("saved stationary snapshot differs from selector replay")
        prior = row["state"]


def build(
    *,
    bundle,
    pilot,
    seed_report,
    seed_report_sha256,
    seed_records,
    gate_decisions,
    baseline_records,
    ocr_pack,
    ocr_pack_receipt_sha256,
    ocr_observations,
    out,
):
    """Build a new private pack; all source artifacts remain byte-for-byte unchanged."""
    try:
        return _build(**locals())
    except (KeyError, TypeError, IndexError, AttributeError, OverflowError):
        raise ValueError("malformed seed comparison input") from None


def _build(**args):
    paths = {
        name: Path(args[name]).resolve()
        for name in (
            "bundle",
            "pilot",
            "seed_report",
            "seed_records",
            "gate_decisions",
            "baseline_records",
            "ocr_pack",
            "ocr_observations",
            "out",
        )
    }
    out = paths.pop("out")
    if any(out == p or (p.is_dir() and out.is_relative_to(p)) for p in paths.values()):
        raise ValueError("output must be outside the inputs")
    if out.exists():
        raise FileExistsError(out)
    for name in ("seed_report_sha256", "ocr_pack_receipt_sha256"):
        _pin(args[name])
    raw = {name: path.read_bytes() for name, path in paths.items() if path.is_file()}
    bindings = {paths[name]: value for name, value in raw.items()}
    hashes = {name: _sha(value) for name, value in raw.items()}
    if hashes["seed_report"] != args["seed_report_sha256"]:
        raise ValueError("seed report SHA mismatch")
    report = _json(raw["seed_report"])
    if (
        report["schema"] != "pitcheezy-seed-gate-pilot-dev-v1"
        or report["policy_sha256"] != POLICY_SHA256
        or not _same(report["policy"], POLICY)
        or report["outputs"]["records_seed_gate.json"] != hashes["seed_records"]
        or report["outputs"]["gate_decisions.json"] != hashes["gate_decisions"]
        or report["source_hashes"]["baseline"] != hashes["baseline_records"]
        or report["baseline_every_field_reproduced"] is not True
        or report["all_input_bytes_unchanged"] is not True
        or report["independent_evaluation"] is not False
        or report["support_observations_are_not_truth"] is not True
        or report["mitt_identity"] != "unverified"
        or report["accuracy"] != "unmeasured"
    ):
        raise ValueError("records or policy differ from the pinned private report")
    selected, old_seeds, observations, preserved, manifest_sha = inputs.load_inputs(
        paths["bundle"], paths["pilot"]
    )
    provenance = inputs.saved_pilot_provenance(paths["pilot"], preserved)
    expected_sources = {
        "manifest": manifest_sha,
        "pilot": provenance["pilot_private_sha256"],
        "answers": provenance["answers_manifest_sha256"],
        "baseline": hashes["baseline_records"],
    }
    if not _same(report["source_hashes"], expected_sources) or not _same(
        report["saved_pilot_inputs"], provenance
    ):
        raise ValueError("source manifest/pilot/answers hashes differ")
    for path, digest in preserved.items():
        path = Path(path).resolve()
        value = path.read_bytes()
        if _sha(value) != digest:
            raise ValueError("source changed during loading")
        bindings[path] = value
        if path.suffix == ".json":
            _json(value)
    keys = [
        _key(
            {"frame_index": f["index"], "frame_seconds": f["pts_time"], "sha256": f["sha256"]},
            pitch=pitch,
            image=True,
        )
        for pitch, f in selected
    ]
    if not keys or len(set(k[:2] for k in keys)) != len(keys):
        raise ValueError("empty or duplicate manifest frame keys")
    if not observations.keys() <= {key[:2] for key in keys}:
        raise ValueError("observation key outside the selected frames")
    seeds, decisions = choose(selected, observations)
    saved_decisions = _json(raw["gate_decisions"])
    if not _same(decisions, saved_decisions):
        raise ValueError("saved gate decisions differ from causal metadata replay")
    base, candidate = _json(raw["baseline_records"]), _json(raw["seed_records"])
    _rows(base, keys, old_seeds, gated=False)
    _rows(candidate, keys, seeds, gated=True)
    for name, rows in (("baseline", base), ("candidate", candidate)):
        if not _same(summarize(rows), report[name]):
            raise ValueError("report row summary differs")
    expected_counts = {
        "baseline_rows": len(base),
        "saved_observation_keys_matched": len(observations),
        "seeded_pitches": sum(seed is not None for seed in seeds.values()),
        "decision_reasons": dict(Counter(d["reason"] for d in decisions)),
    }
    if any(not _same(report[name], value) for name, value in expected_counts.items()):
        raise ValueError("report denominator or decision count differs")
    receipt, files = _pack_files(paths["ocr_pack"], args["ocr_pack_receipt_sha256"], bindings)
    if receipt["input_sha256"]["ocr_observations"] != hashes["ocr_observations"]:
        raise ValueError("OCR observations SHA differs from source receipt")
    manifest = _json(bindings[paths["bundle"] / "manifest.json"])
    meta = {p["pitch_id"]: p for p in manifest["selection"]}
    if len(meta) != len(manifest["selection"]):
        raise ValueError("duplicate manifest selection pitch")
    pitches, images, visible = {}, {}, {}
    for (pitch, source), key, before, after, decision in zip(
        selected, keys, base, candidate, decisions, strict=True
    ):
        source_path = Path(source["path"]).resolve()
        if not source_path.is_relative_to(paths["bundle"]):
            raise ValueError("source image escapes bundle")
        image = bindings[source_path]
        if (
            type(source["bytes"]) is not int
            or len(image) != source["bytes"]
            or _sha(image) != key[3]
        ):
            raise ValueError("source image size/SHA mismatch")
        with Image.open(io.BytesIO(image)) as decoded:
            decoded.load()
            if decoded.format != "JPEG" or decoded.size != (1280, 720):
                raise ValueError("source must be a 1280x720 JPEG")
        play_id = meta[pitch]["play_id"]
        if not isinstance(play_id, str) or not play_id.strip():
            raise ValueError("manifest play id required")
        entry = pitches.setdefault(pitch, {"pitch_id": pitch, "play_id": play_id, "frames": []})
        relative = f"frames/{pitch.replace(':', '_')}/{key[1]}.jpg"
        frame = {
            "frame_index": key[1],
            "frame_seconds": key[2],
            "image": relative,
            "sha256": key[3],
            "width": 1280,
            "height": 720,
            "tracking": {k: v for k, v in before.items() if k != "stationary"},
            "selection": before["stationary"],
            "seed_gate": {
                "tracking": {k: v for k, v in after.items() if k != "stationary"},
                "selection": after["stationary"],
                "decision": decision,
            },
        }
        entry["frames"].append(frame)
        visible.setdefault(pitch, []).append((frame, image))
        images[relative] = image
    source_payload, original_ocr = _json(files["payload.json"]), _json(files["ocr.json"])
    if (
        source_payload["schema"] != "pitcheezy-track-frame-view-dev-v1"
        or original_ocr["schema"] != "pitcheezy-ocr-frame-view-dev-v1"
        or "comparison_schema" in source_payload
        or any(p["time_basis"] != "manifest_index_timebase" for p in (source_payload, original_ocr))
        or any(
            p["independent_decoded_pts_verified"] is not False
            for p in (source_payload, original_ocr)
        )
    ):
        raise ValueError("unsupported source OCR pack metadata")
    overlap, old_pitch_ids = 0, []
    for pitch in source_payload["pitches"]:
        pitch_id = pitch["pitch_id"]
        if pitch_id in old_pitch_ids:
            raise ValueError("duplicate OCR source pitch")
        old_pitch_ids.append(pitch_id)
        old_frames = pitch["frames"]
        new_frames = visible[pitch_id]
        if [_key(f, pitch=pitch_id, image=True) for f in old_frames] != [
            _key(f, pitch=pitch_id, image=True) for f, _ in new_frames
        ]:
            raise ValueError("OCR source frame keys differ from complete displayed pitch")
        for old, (_new, image) in zip(old_frames, new_frames, strict=True):
            if files[old["image"]] != image:
                raise ValueError("OCR source image differs from manifest JPEG")
            overlap += 1
    observations_ocr = _json(raw["ocr_observations"])
    observed_pitch = observations_ocr["pitch_id"]
    if (
        observations_ocr["schema"] != "pitcheezy-frame-name-observations-dev-v1"
        or observations_ocr["time_basis"] != "manifest_index_timebase"
        or observations_ocr["independent_decoded_pts_verified"] is not False
        or observed_pitch not in old_pitch_ids
        or not _same(
            original_ocr["pitches"],
            [{"pitch_id": observed_pitch, "rows": observations_ocr["rows"]}],
        )
        or not _same(
            original_ocr["pitches_without_observations"],
            [p for p in old_pitch_ids if p != observed_pitch],
        )
    ):
        raise ValueError("OCR source rows or coverage metadata differ")
    _check_rows(observations_ocr["rows"], visible[observed_pitch], observed_pitch)
    ocr = copy.deepcopy(original_ocr)
    ocr["pitches_without_observations"] = [p for p in pitches if p != observed_pitch]
    payload = {
        "schema": "pitcheezy-track-frame-view-dev-v1",
        "comparison_schema": COMPARISON_SCHEMA,
        "time_basis": "manifest_index_timebase",
        "independent_decoded_pts_verified": False,
        "pitches": list(pitches.values()),
    }
    payload_raw, ocr_raw = _encoded(payload) + b"\n", _encoded(ocr) + b"\n"
    page = fill_template(
        (ASSETS / "index.html").read_text(encoding="utf-8"),
        {
            "__TRACK_VIEW_DATA__": payload_raw.decode().replace("<", "\\u003c"),
            "__OCR_VIEW_DATA__": ocr_raw.decode().replace("<", "\\u003c"),
        },
    )
    output = {
        "index.html": page.encode(),
        "review.js": (ASSETS / "review.js").read_bytes(),
        "style.css": (ASSETS / "style.css").read_bytes(),
        "payload.json": payload_raw,
        "ocr.json": ocr_raw,
        **images,
    }
    if any(path.read_bytes() != value for path, value in bindings.items()):
        raise ValueError("an input changed during the join")
    result = {
        "schema": RECEIPT_SCHEMA,
        "comparison_schema": COMPARISON_SCHEMA,
        "input_sha256": {
            **hashes,
            **expected_sources,
            "ocr_pack_receipt": args["ocr_pack_receipt_sha256"],
            "ocr_pack_payload": _sha(files["payload.json"]),
            "ocr_pack_observations": _sha(files["ocr.json"]),
        },
        "policy_sha256": POLICY_SHA256,
        "all_record_keys_checked": len(keys),
        "displayed_frames": len(keys),
        "displayed_pitches": len(pitches),
        "gate_decisions_reproduced": len(decisions),
        "baseline_selections_checked": len(base),
        "candidate_selections_checked": len(candidate),
        "seeded_pitches": expected_counts["seeded_pitches"],
        "pitches_without_seed": len(pitches) - expected_counts["seeded_pitches"],
        "observation_rows_bound": len(observations_ocr["rows"]),
        "frames_without_ocr": len(keys) - len(observations_ocr["rows"]),
        "ocr_source_images_checked": overlap,
        "baseline_fields_preserved": True,
        "candidate_fields_preserved": True,
        "ocr_rows_preserved": True,
        "ocr_coverage_metadata_expanded": True,
        "frame_images_unchanged": True,
        "input_unchanged": True,
        "preserved_input_files": len(bindings),
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
        "bundle",
        "pilot",
        "seed-report",
        "seed-report-sha256",
        "seed-records",
        "gate-decisions",
        "baseline-records",
        "ocr-pack",
        "ocr-pack-receipt-sha256",
        "ocr-observations",
        "out",
    ):
        parser.add_argument("--" + name, required=True)
    result = build(**vars(parser.parse_args()))
    print(
        json.dumps(
            {k: result[k] for k in ("displayed_frames", "seeded_pitches", "observation_rows_bound")}
        )
    )


if __name__ == "__main__":
    main()

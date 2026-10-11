"""Compare saved replay publication with declared manual pitch deadlines, offline.

This evaluator never runs a detector or identifies a pitch from an image. Its source
clock is a declared 1x replay clock, not arrival time, live availability, or ground truth.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from fractions import Fraction
from pathlib import Path

from intent import local_glove_observer_report as saved
from intent import observation_report as outer
from intent.replay import _no_links
from src.data.broadcast_timing import validate_annotations

SCHEMA = "intent_replay_pitch_deadlines_v1"


def _time(value):
    if type(value) not in (int, float, str):
        raise ValueError("Expected a finite nonnegative time")
    try:
        result = Fraction(str(value))
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("Expected a finite nonnegative time") from exc
    if result < 0:
        raise ValueError("Expected a finite nonnegative time")
    return result


def _read(path):
    path = Path(path)
    _no_links(path)
    return outer._read(path)


def evaluate(observations, references, *, clock_id):
    """Evaluate explicit intervals without carrying any observation across pitches.

    The nominal-start result uses the recorded decision timestamp; the conservative
    result also requires a frame at/after decision + the recorded timing uncertainty.
    Neither result asserts that a mitt, pitch identity, or target was recognized.
    """
    if not isinstance(clock_id, str) or not clock_id.strip():
        raise ValueError("An explicit reference clock is required")
    observed, seen = [], set()
    for row in observations:
        index = row.get("index")
        if type(index) is not int or index < 0 or index in seen:
            raise ValueError("Observation indices must be unique nonnegative integers")
        seen.add(index)
        if row.get("clock_id") != clock_id:
            raise ValueError("Observation clock mismatch")
        status = row.get("status")
        if status not in {"accepted", "error", "not_attempted"}:
            raise ValueError("Unexpected observation status")
        frame = row.get("frame_seconds_exact")
        publication = row.get("publication_seconds_exact")
        frame = None if frame is None else _time(frame)
        publication = None if publication is None else _time(publication)
        if status == "accepted":
            if frame is None or publication is None or publication < frame:
                raise ValueError("Accepted output requires ordered source/publication times")
            if row.get("observation_status") not in {"marked", "unavailable", "unknown"}:
                raise ValueError("Unexpected accepted observation status")
        elif publication is not None:
            raise ValueError("Unaccepted observation cannot have a publication time")
        observed.append((row, frame, publication))

    pitches, associations, prior_end, ids = [], {}, None, set()
    for ref in references:
        pid = ref.get("pitch_id")
        parts = pid.split(":") if isinstance(pid, str) else []
        if len(parts) != 3 or any(not p.isdigit() or int(p) <= 0 for p in parts) or pid in ids:
            raise ValueError("Expected unique game:PA:pitch reference identities")
        ids.add(pid)
        if ref.get("clock_id") != clock_id:
            raise ValueError("Reference clock mismatch")
        pitch = {"pitch_id": pid, "usable_mitt": False, "observations": []}
        values = [
            ref.get(k) for k in ("decision_seconds", "release_seconds", "uncertainty_seconds")
        ]
        if any(v is None for v in values):
            pitch.update(
                status="unmeasured",
                nominal_start_temporal_ready=False,
                conservative_temporal_ready=False,
            )
            pitches.append(pitch)
            continue
        decision, release, uncertainty = map(_time, values)
        lower, upper = release - uncertainty, release + uncertainty
        if uncertainty <= 0 or not 0 <= decision < release or lower < 0:
            raise ValueError("Invalid decision/release uncertainty bounds")
        if prior_end is not None and decision <= prior_end:
            raise ValueError("Reference pitch intervals overlap or are not chronological")
        prior_end = upper
        pitch.update(
            status="measured_reference",
            decision_seconds_exact=str(decision),
            decision_upper_seconds_exact=str(decision + uncertainty),
            release_lower_seconds_exact=str(lower),
            release_upper_seconds_exact=str(upper),
            conservative_window_empty=decision + uncertainty >= lower,
        )
        for row, frame, publication in observed:
            # No prior-frame carry-forward: an output retains the pitch of its own frame.
            if frame is None or not decision <= frame <= upper:
                continue
            index = row["index"]
            if index in associations:
                raise ValueError("One frame cannot belong to multiple reference windows")
            associations[index] = pid
            input_before = frame < lower
            pub_state = (
                "unmeasured"
                if publication is None
                else "before_lower"
                if publication < lower
                else "after_upper"
                if publication > upper
                else "overlaps_uncertainty"
            )
            temporal = row["status"] == "accepted" and input_before and pub_state == "before_lower"
            pitch["observations"].append(
                {
                    **row,
                    "input_before_release_lower": input_before,
                    "input_overlaps_release_uncertainty": not input_before,
                    "input_overlaps_decision_uncertainty": frame < decision + uncertainty,
                    "publication_relative_to_release": pub_state,
                    "publication_margin_to_lower_seconds_exact": (
                        str(lower - publication) if publication is not None else None
                    ),
                    "nominal_start_temporal_ready": temporal,
                    "conservative_temporal_ready": temporal and frame >= decision + uncertainty,
                    "usable_mitt": False,
                }
            )
        pitch["nominal_start_temporal_ready"] = any(
            row["nominal_start_temporal_ready"] for row in pitch["observations"]
        )
        pitch["conservative_temporal_ready"] = any(
            row["conservative_temporal_ready"] for row in pitch["observations"]
        )
        pitch["definitely_pre_release_inputs"] = sum(
            row["input_before_release_lower"] for row in pitch["observations"]
        )
        pitches.append(pitch)
    return {
        "pitches": pitches,
        "unassigned_observations": [
            row for row, _, _ in observed if row["index"] not in associations
        ],
        "counts": {
            "planned_observations": len(observed),
            "reference_pitches": len(pitches),
            "unmeasured_reference_pitches": sum(p["status"] == "unmeasured" for p in pitches),
            "nominal_start_temporal_ready_pitches": sum(
                p["nominal_start_temporal_ready"] for p in pitches
            ),
            "conservative_temporal_ready_pitches": sum(
                p["conservative_temporal_ready"] for p in pitches
            ),
            "usable_mitt_pitches": 0,
            "observation_status": dict(Counter(row["status"] for row, _, _ in observed)),
        },
    }


def _capture_binding(manifest, capture, capture_hash, timing):
    # Recorded Windows paths are identifiers here, not paths to open on this host.
    recorded = manifest["plan"]["capture_dir"].replace("\\", "/").rstrip("/") + "/receipt.json"
    bindings = [
        r for r in manifest["input_code_bindings"] if r["path"].replace("\\", "/") == recorded
    ]
    if len(bindings) != 1 or bindings[0]["sha256"] != capture_hash:
        raise ValueError("Capture receipt is not bound to the saved run")
    if (
        capture.get("schema") != "intent_clip_capture_v1"
        or capture.get("status") != "captured"
        or capture["source"].get("kind") != "url"
        or capture["source"].get("value") != timing["source"]["media_url"]
        or capture["clip"].get("unchanged") is not True
        or capture["clip"]["sha256_before"] != capture["clip"]["sha256_after"]
    ):
        raise ValueError("Capture and timing must declare the same unchanged media source")
    return {
        "capture_receipt_sha256": capture_hash,
        "source_framemd5_sha256": capture["artifacts"]["source.framemd5"]["sha256"],
        "clip_framemd5_sha256": capture["artifacts"]["clip.framemd5"]["sha256"],
        "clip_media_sha256": capture["clip"]["sha256_after"],
    }


def _frame_binding(run, index, attempt, capture, expected):
    receipt, digest = _read(run / "frames" / f"frame_{index:03d}" / "receipt.json")
    session, _ = _read(run / "outputs" / f"cv_observation_{index:03d}" / "session.json")
    if (
        receipt.get("status") != "extracted"
        or receipt.get("input_hashes") != expected
        or receipt.get("source") != capture["source"]
        or session.get("source_receipt_sha256") != digest
        or receipt.get("actual_source_seconds_exact") != attempt["actual_source_seconds_exact"]
        or receipt.get("requested_source_seconds_exact") != attempt["cutoff_seconds_exact"]
        or receipt.get("artifacts", {}).get("image.jpg", {}).get("sha256")
        != session["image_sha256"]
    ):
        raise ValueError("Saved frame/source receipt binding mismatch")
    return digest


def build_report(run_dir, *, timing_path, manifest_path, sources_path, capture_receipt, pa):
    """Revalidate saved outputs and reference provenance without any model/media calls."""
    if type(pa) is not int or pa <= 0:
        raise ValueError("PA must be a positive integer")
    run = Path(run_dir)
    inventory = saved._inventory(run)
    report = saved.build_report(run)
    manifest, manifest_hash = _read(run / "run_manifest.json")
    documents, hashes = {}, {}
    paths = {
        "timing": timing_path,
        "manifest": manifest_path,
        "sources": sources_path,
        "capture": capture_receipt,
    }
    for key, path in paths.items():
        documents[key], hashes[key] = _read(path)
    timing, capture = documents["timing"], documents["capture"]
    validate_annotations(timing, documents["manifest"], documents["sources"])
    expected = _capture_binding(manifest, capture, hashes["capture"], timing)
    clock_id = (
        "declared_source_playback:"
        + hashlib.sha256(timing["source"]["media_url"].encode()).hexdigest()
    )
    annotations = {
        (r["game_pk"], r["at_bat_number"], r["pitch_number"]): r for r in timing["annotations"]
    }
    references = []
    for pitch in documents["manifest"]["pitches"]:
        if pitch["at_bat_number"] != pa:
            continue
        key = tuple(pitch[k] for k in ("game_pk", "at_bat_number", "pitch_number"))
        ref = annotations.get(key, {})
        references.append(
            {
                "pitch_id": ":".join(map(str, key)),
                "clock_id": clock_id,
                **{
                    k: ref.get(k)
                    for k in ("decision_seconds", "release_seconds", "uncertainty_seconds")
                },
            }
        )
    references.sort(key=lambda r: tuple(map(int, r["pitch_id"].split(":"))))
    if not references:
        raise ValueError("Requested PA is absent from the identity manifest")
    start = outer._int(manifest["started_monotonic_ns"])
    origin = outer._fraction(manifest["plan"]["cutoffs"][0])
    observations, receipt_hashes = [], {}
    for row in report["observations"]:
        index, state = row["index"], row["status"]
        attempt_path = run / "attempts" / f"{index:03d}.json"
        attempt = _read(attempt_path)[0] if state != "not_attempted" else {}
        accepted = attempt.get("status") == "accepted"
        frame = attempt.get("actual_source_seconds_exact")
        if accepted:
            receipt_hashes[str(index)] = _frame_binding(run, index, attempt, capture, expected)
        publication = (
            origin
            + Fraction(outer._int(attempt["response_accepted"]["monotonic_ns"]) - start, 10**9)
            if accepted
            else None
        )
        observations.append(
            {
                "index": index,
                "clock_id": clock_id,
                "status": "accepted"
                if accepted
                else "not_attempted"
                if state == "not_attempted"
                else "error",
                "observation_status": row.get("observation_status"),
                "candidate_status": state,
                "frame_seconds_exact": frame,
                "publication_seconds_exact": str(publication) if publication is not None else None,
                "cutoff_seconds_exact": row["cutoff_seconds_exact"],
                "attempt_sha256": row.get("attempt_sha256"),
            }
        )
    result = evaluate(observations, references, clock_id=clock_id)
    if inventory != saved._inventory(run) or any(
        _read(paths[k])[1] != h for k, h in hashes.items()
    ):
        raise ValueError("Saved run or reference changed while evaluating")
    return {
        "schema": SCHEMA,
        **result,
        "reference_clock_id": clock_id,
        "clock_mapping": {
            "basis": "declared_fixed_1x_replay",
            "source_origin_seconds_exact": str(origin),
            "elapsed_clock": "run_monotonic_ns",
            "uses_feed_utc": False,
        },
        "reference_provenance": {
            "kind": "existing_manual_timing_annotation",
            "annotator": timing["annotator"],
            "reference_files_sha256": hashes,
            "identity_manifest_canonical_sha256": timing["manifest_sha256"],
            "source_identity_independently_attested": False,
        },
        "evidence_sha256": {
            "evaluator_code": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
            "run_manifest": manifest_hash,
            "saved_report": report["evidence_sha256"],
            "frame_receipts": receipt_hashes,
        },
        "live_availability_verified": False,
        "accuracy_evaluated": False,
        "independent_validation": False,
        "full_pa_verified": False,
        "usable_mitt_verified": False,
        "notice": "Retrospective declared source-clock comparison. Nominal-start timing uses the recorded decision; conservative timing also applies decision uncertainty. Input association is by explicit reference window, not recognized pitch identity or scene validity. Every generic glove output remains unverified, including on-time outputs. No prior-pitch carry-forward; no live arrival, target, physical calibration, or accuracy claim.",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run", type=Path, required=True)
    parser.add_argument("--timing", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--sources", type=Path, required=True)
    parser.add_argument("--capture-receipt", type=Path, required=True)
    parser.add_argument("--pa", type=int, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    _no_links(args.out)
    if args.out.exists():
        raise FileExistsError("Report output must be new")
    report = build_report(
        args.run,
        timing_path=args.timing,
        manifest_path=args.manifest,
        sources_path=args.sources,
        capture_receipt=args.capture_receipt,
        pa=args.pa,
    )
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps(report["counts"], ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

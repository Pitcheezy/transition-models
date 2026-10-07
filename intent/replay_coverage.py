"""Audit all mapped presentation intervals without decoding or observing video.

Coverage means supplied source-clock intervals are present in the bound local clip.
It does not authenticate broadcast identity, plate-appearance boundaries or accuracy.
"""

from __future__ import annotations

import argparse
import json
from fractions import Fraction
from pathlib import Path

from intent import clip_capture, clip_clock, clip_frames

SCHEMA = "intent_replay_coverage_v1"


def _exact(value):
    if type(value) not in (str, int):
        raise ValueError("Times must be exact strings or integers, never floats or bools")
    try:
        result = Fraction(value)
    except (ValueError, ZeroDivisionError) as exc:
        raise ValueError("Expected a finite exact rational time") from exc
    if result < 0:
        raise ValueError("Times must be nonnegative")
    return result


def _interval(start, end):
    return {
        "start_seconds_exact": str(start),
        "end_seconds_exact": str(end),
        "duration_seconds_exact": str(end - start),
    }


def _coverage(mapping, start, end):
    cursor, count, gaps = start, 0, []
    for row in mapping["rows"]:
        left = max(start, Fraction(row["source_seconds_exact"]))
        right = min(end, Fraction(row["source_interval_end_exact"]))
        if right <= left:
            continue
        count += 1
        if left > cursor:
            gaps.append(_interval(cursor, left))
        cursor = max(cursor, right)
    if cursor < end:
        gaps.append(_interval(cursor, end))
    missing = sum((Fraction(gap["duration_seconds_exact"]) for gap in gaps), Fraction(0))
    return {
        "covering_frame_count": count,
        "covered_duration_seconds_exact": str(end - start - missing),
        "uncovered_duration_seconds_exact": str(missing),
        "gaps": gaps,
        "fully_covered": not gaps,
    }


def _read_cutoffs(path):
    path = clip_capture._plain_path(path)
    raw = path.read_bytes()

    def reject_constant(_):
        raise ValueError("Nonfinite JSON cutoff")

    values = json.loads(raw, parse_constant=reject_constant)
    if not isinstance(values, list) or not 1 <= len(values) <= 50:
        raise ValueError("Cutoffs must be a nonempty JSON list of at most 50 exact times")
    cutoffs = [_exact(value) for value in values]
    if any(a >= b for a, b in zip(cutoffs, cutoffs[1:], strict=False)):
        raise ValueError("Cutoffs must be strictly increasing")
    return cutoffs, (path, clip_clock._sha(raw), len(raw))


def _lookup(mapping, cutoff, start, end):
    result = {"requested_source_seconds_exact": str(cutoff)}
    if not start <= cutoff < end:
        return {**result, "status": "unavailable", "reason": "outside_requested_interval"}
    try:
        row = clip_clock.latest_mapped_frame(mapping, cutoff)
    except ValueError:
        return {**result, "status": "unavailable", "reason": "outside_mapped_coverage"}
    return {
        **result,
        "status": "mapped",
        "reason": None,
        "frame": {
            key: row[key]
            for key in (
                "clip_decode_ordinal",
                "source_decode_ordinal",
                "source_pts",
                "source_seconds_exact",
                "source_interval_end_exact",
                "md5",
            )
        },
    }


def audit_replay_coverage(*, capture_dir, start, end, out, cutoffs_json=None):
    """Write a fresh path-free report after rechecking bound files; never launch tools.

    Frame count includes every mapped frame whose source presentation interval has
    nonzero intersection with [start, end), even when its PTS precedes start.
    Cutoff success is reported separately from coverage of the entire interval.
    """
    start, end = _exact(start), _exact(end)
    if end <= start:
        raise ValueError("Requested interval must have positive duration")
    directory, output = (clip_capture._plain_path(value) for value in (capture_dir, out))
    if output.exists():
        raise FileExistsError("Coverage output must be a new file")
    if output.is_relative_to(directory):
        raise ValueError("Coverage output must be outside capture inputs")
    if not output.parent.is_dir():
        raise ValueError("Coverage output parent must already exist")
    cutoffs, cutoff_binding = [], None
    if cutoffs_json is not None:
        cutoffs, cutoff_binding = _read_cutoffs(cutoffs_json)
    captured, _, bindings, mapping = clip_frames._capture_inputs(directory)
    hashes = clip_frames._input_hashes(captured, bindings, mapping)
    if captured["source"]["kind"] == "local_file":
        hashes["source_media_sha256"] = captured["source"]["sha256_before"]
    if cutoff_binding is not None:
        bindings.append(cutoff_binding)
        hashes["cutoffs_json_sha256"] = cutoff_binding[1]
    lookups = [_lookup(mapping, cutoff, start, end) for cutoff in cutoffs]
    result = {
        "schema": SCHEMA,
        "requested_interval": {**_interval(start, end), "semantics": "[start,end)"},
        **_coverage(mapping, start, end),
        "mapped_frame_count": mapping["matched_frames"],
        "cutoffs_requested": len(cutoffs),
        "cutoffs_mapped": sum(item["status"] == "mapped" for item in lookups),
        "cutoffs_unavailable": sum(item["status"] == "unavailable" for item in lookups),
        "cutoffs": lookups,
        "input_hashes": hashes,
        "source_kind": captured["source"]["kind"],
        "source_identity_authenticated": False,
        "full_pa_verified": False,
        "accuracy_evaluated": False,
        "live_availability_verified": False,
        "notice": (
            "Bound checksum-table coverage only; no decoder or model was called. "
            "Complete mapped intervals do not prove continuous camera visibility, "
            "correct labels, physical PA boundaries or broadcast identity. "
            "Gaps are durations, not estimated missing-frame counts."
        ),
    }
    clip_frames._verify_files(bindings)
    with output.open("x", encoding="utf-8") as stream:
        json.dump(result, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    return result


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--capture-dir", type=Path, required=True)
    parser.add_argument("--start", required=True)
    parser.add_argument("--end", required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--cutoffs-json", type=Path)
    args = parser.parse_args(argv)
    result = audit_replay_coverage(**vars(args))
    print(json.dumps(result, ensure_ascii=False, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

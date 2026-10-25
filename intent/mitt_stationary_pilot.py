"""Replay CV37 saved tracker rows without decoding video or making model calls.

The caller pins the trusted tracking report SHA. Its record hashes bind the exact input
streams. This is file identification, not source authentication or an independent evaluation.
Outputs must be new; historical rows, reports and source pictures are never rewritten.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from collections import Counter
from dataclasses import asdict
from pathlib import Path

from intent.mitt_stationary import StationaryParams, StationarySelector


def _sha(raw):
    return hashlib.sha256(raw).hexdigest()


def replay(rows):
    """Replay each contiguous pitch once. Tracking validity is not semantic visibility."""
    if not isinstance(rows, list) or not rows:
        raise ValueError("nonempty record list required")
    outputs, summaries, seen = [], [], set()
    selector = None
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError("tracker row must be an object")
        pitch = row.get("pitch_id")
        if not isinstance(pitch, str) or not pitch:
            raise ValueError("pitch_id required")
        if selector is None or pitch != outputs[-1]["pitch_id"]:
            if pitch in seen:
                raise ValueError("noncontiguous pitch")
            seen.add(pitch)
            selector = StationarySelector()
            summaries.append(
                {
                    "pitch_id": pitch,
                    "frames": 0,
                    "events": 0,
                    "current_candidate_frames": 0,
                    "current_intervals": [],
                }
            )
        result = selector.step(row)
        summary = summaries[-1]
        summary["frames"] += 1
        summary["events"] += result["event"] is not None
        current = result["current_candidate"]
        summary["current_candidate_frames"] += current is not None
        if current:
            intervals = summary["current_intervals"]
            if not intervals or intervals[-1]["candidate_id"] != current["candidate_id"]:
                intervals.append(
                    {
                        "candidate_id": current["candidate_id"],
                        "first_seconds": current["frame_seconds"],
                        "last_seconds": current["frame_seconds"],
                        "frames": 0,
                    }
                )
            intervals[-1]["last_seconds"] = current["frame_seconds"]
            intervals[-1]["frames"] += 1
        summary["final_tracker_state"] = result["tracker_state"]
        summary["final_current_candidate_present"] = current is not None
        summary["final_history_present"] = result["last_historical_candidate"] is not None
        outputs.append(result)
    for summary in summaries:
        for interval in summary["current_intervals"]:
            interval["observed_span_seconds"] = interval["last_seconds"] - interval["first_seconds"]
    aggregate = {
        "frames": len(outputs),
        "pitches": len(summaries),
        "events": sum(s["events"] for s in summaries),
        "pitches_with_event": sum(s["events"] > 0 for s in summaries),
        "current_candidate_frames": sum(s["current_candidate_frames"] for s in summaries),
        "history_only_frames": sum(
            r["last_historical_candidate"] is not None and r["current_candidate"] is None
            for r in outputs
        ),
        "selection_states": dict(Counter(r["selection_state"] for r in outputs)),
        "reasons": dict(Counter(r["reason"] for r in outputs)),
        "pitch_summaries": summaries,
    }
    return outputs, aggregate


def build(*, tracking_report, report_sha256, cpu, cuda, out):
    """Bind the whole input bundle before any new output is written."""
    paths = {"tracking_report": Path(tracking_report), "cpu": Path(cpu), "cuda": Path(cuda)}
    raw = {name: path.read_bytes() for name, path in paths.items()}
    hashes = {name: _sha(value) for name, value in raw.items()}
    if hashes["tracking_report"] != report_sha256:
        raise ValueError("tracking report SHA mismatch")
    source = json.loads(raw["tracking_report"])
    if source.get("schema") != "pitcheezy-mitt-tracking-pilot-dev-v2":
        raise ValueError("unsupported tracking report")
    output_rows, summaries = {}, {}
    for device in ("cpu", "cuda"):
        if hashes[device] != source["devices"][device]["records_sha256"]:
            raise ValueError(f"{device} record SHA mismatch")
        output_rows[device], summaries[device] = replay(json.loads(raw[device]))
        if (
            summaries[device]["frames"] != source["frames"]
            or summaries[device]["pitches"] != source["pitches"]
        ):
            raise ValueError("tracking report denominator mismatch")
    if output_rows["cpu"] != output_rows["cuda"]:
        raise ValueError("CPU/CUDA selection outputs differ")
    if any(path.read_bytes() != raw[name] for name, path in paths.items()):
        raise ValueError("input changed during replay")
    params = StationaryParams()
    report = {
        "schema": "pitcheezy-stationary-pilot-dev-v1",
        "evidence_kind": "offline exposed development replay; no new vision/human labels",
        "params": asdict(params),
        "params_sha256": params.digest(),
        "source_files_sha256": {
            name: _sha(Path(__file__).with_name(name).read_bytes())
            for name in ("mitt_stationary.py", "mitt_stationary_pilot.py")
        },
        "input_sha256": hashes,
        "input_unchanged": True,
        "cpu_cuda_selection_equal": True,
        "devices": summaries,
        "limits": [
            "Geometric patch stationarity only; a stable wrong seed can qualify.",
            "No new semantic/view gate was inferred or applied in this saved replay.",
            "720p development thresholds, not calibrated for other resolutions.",
            "Observed interval spans stop at the last qualifying sampled frame; no interpolation.",
            "No release/outcome/future annotation, physical accuracy or independent evaluation.",
            "Timing inherits CV37 manifest-derived assumptions, not independently verified PTS.",
            "CPU/CUDA here identifies saved input streams; selector itself uses standard Python.",
        ],
    }
    out = Path(out)
    out.mkdir(parents=True, exist_ok=False)
    for device, rows in output_rows.items():
        data = (json.dumps(rows, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()
        (out / f"records_{device}.json").write_bytes(data)
        report["devices"][device]["output_sha256"] = _sha(data)
    (out / "report.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for flag in ("tracking-report", "report-sha256", "cpu", "cuda", "out"):
        parser.add_argument("--" + flag, required=True)
    args = parser.parse_args()
    report = build(**vars(args))
    print(
        json.dumps(
            {
                "frames": report["devices"]["cpu"]["frames"],
                "events": report["devices"]["cpu"]["events"],
                "cpu_cuda_selection_equal": report["cpu_cuda_selection_equal"],
            }
        )
    )


if __name__ == "__main__":
    main()

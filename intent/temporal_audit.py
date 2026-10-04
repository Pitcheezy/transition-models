"""Audit legacy CV time dependencies; validate separate, fail-closed timing traces.

This is an offline development diagnostic, not a live detector. Legacy artifacts have
no measured availability clock. A frame before release alone never passes the guard.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from fractions import Fraction
from pathlib import Path

import numpy as np

from intent.geometry import front_edge_similarity, project_point
from intent.plate_feet import hop2_parameters, load_calibration, zone_to_plate_feet
from intent.run import POOLED_WIDTH_TOLERANCE, camera_constants
from intent.schema import validate_intent_estimate

TRACE_SCHEMA = "intent_temporal_trace_v1"
REPORT_SCHEMA = "intent_temporal_audit_v1"
REQUIRED_KINDS = {"pitch_identity", "setup_frame", "camera_calibration", "cv_output"}
ROOT = Path(__file__).resolve().parents[1]


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number")
    if value < 0:
        raise ValueError(f"{name} must be nonnegative")
    return float(value)


def pitch_key(row):
    parts = (row.get("at_bat_number"), row.get("pitch_number"))
    if any(type(v) is not int or v <= 0 for v in parts):
        raise ValueError("pitch key must contain positive integer PA and pitch numbers")
    return parts


def keyed(rows):
    result = {}
    for row in rows:
        key = pitch_key(row)
        if key in result:
            raise ValueError(f"duplicate pitch key: {key}")
        result[key] = row
    return result


def validate_trace(trace, artifact_root):
    """Check measured, same-clock evidence and files without changing IntentEstimate v1.

    The trace is a declaration whose timing must be collected by an instrumented runner.
    Passing checks its consistency; it does not independently attest the measurements.
    Every listed dependency must pass, including artifacts not on the output's direct edge.
    """
    if trace.get("schema") != TRACE_SCHEMA:
        raise ValueError("unsupported temporal trace schema")
    pid = trace.get("pitch_id", "")
    parts = pid.split(":") if isinstance(pid, str) else []
    if len(parts) != 3 or any(not p.isdigit() or int(p) <= 0 for p in parts):
        raise ValueError("pitch_id must be game:PA:pitch")
    clock = trace.get("clock_id")
    if not isinstance(clock, str) or not clock.strip():
        raise ValueError("clock_id must identify one playback/source clock")
    deadline = number(trace.get("decision_deadline_seconds"), "decision deadline")
    root = Path(artifact_root).resolve()
    rows = trace.get("artifacts")
    if not isinstance(rows, list) or not rows:
        raise ValueError("artifacts must be a nonempty list")
    by_id, reasons, output_records = {}, [], {}
    for row in rows:
        ident = row.get("id")
        if not isinstance(ident, str) or not ident.strip() or ident in by_id:
            raise ValueError("artifact IDs must be nonempty and unique")
        by_id[ident] = row
        kind = row.get("kind")
        if not isinstance(kind, str) or not kind:
            raise ValueError("artifact kind is required")
        deps = row.get("depends_on")
        if not isinstance(deps, list) or any(not isinstance(d, str) for d in deps):
            raise ValueError("depends_on must be an explicit list of artifact IDs")
        if len(set(deps)) != len(deps):
            raise ValueError("duplicate dependency")
        raw_path = row.get("path")
        if not isinstance(raw_path, str) or not raw_path or Path(raw_path).is_absolute():
            raise ValueError("artifact paths must be relative to artifact_root")
        path = (root / raw_path).resolve()
        if not path.is_relative_to(root) or not path.is_file():
            raise ValueError("artifact path escapes root or is not a file")
        digest = row.get("sha256")
        if not isinstance(digest, str) or len(digest) != 64 or sha256(path) != digest:
            raise ValueError(f"artifact hash mismatch: {ident}")
        if row.get("clock_id") != clock:
            reasons.append({"artifact": ident, "reason": "clock_mismatch"})
        evidence, available = row.get("evidence_max_seconds"), row.get("available_at_seconds")
        for field, value in (
            ("evidence_max_seconds", evidence),
            ("available_at_seconds", available),
        ):
            if value is None:
                reasons.append({"artifact": ident, "reason": f"unknown_{field}"})
            else:
                number(value, field)
                if value >= deadline:
                    reasons.append({"artifact": ident, "reason": f"not_before_deadline_{field}"})
        if row.get("availability_basis") != "measured":
            reasons.append({"artifact": ident, "reason": "availability_not_measured"})
        if evidence is not None and available is not None and available < evidence:
            reasons.append({"artifact": ident, "reason": "available_before_evidence"})
        if kind == "cv_output":
            outputs = [
                json.loads(line)
                for line in path.read_text(encoding="utf-8-sig").splitlines()
                if line.strip()
            ]
            for output in outputs:
                validate_intent_estimate(output)
            ids = [o.get("pitch_id") for o in outputs]
            if len(set(ids)) != len(ids) or ids.count(pid) != 1:
                raise ValueError(
                    "output must contain the trace pitch exactly once and no duplicate IDs"
                )
            record = next(o for o in outputs if o["pitch_id"] == pid)
            output_records[ident] = record
            if evidence is not None and record["evidence"]["frame_time"] > evidence:
                raise ValueError("output frame is later than its declared evidence maximum")
    missing = REQUIRED_KINDS - {r["kind"] for r in rows}
    reasons.extend({"artifact": None, "reason": f"missing_kind_{k}"} for k in sorted(missing))
    visiting, visited = set(), set()

    def visit(ident):
        if ident in visiting:
            raise ValueError("cyclic evidence dependency")
        if ident in visited:
            return
        visiting.add(ident)
        row = by_id[ident]
        for dep in row["depends_on"]:
            if dep not in by_id:
                raise ValueError(f"missing dependency: {dep}")
            visit(dep)
            own, prior = row.get("available_at_seconds"), by_id[dep].get("available_at_seconds")
            if own is not None and prior is not None and own < prior:
                reasons.append(
                    {"artifact": ident, "reason": "available_before_dependency", "dependency": dep}
                )
        visiting.remove(ident)
        visited.add(ident)

    for ident in by_id:
        visit(ident)
    outputs = [r for r in rows if r["kind"] == "cv_output"]
    if len(outputs) != 1:
        raise ValueError("exactly one cv_output artifact is required")
    ancestors = set()

    def collect(ident):
        for dep in by_id[ident]["depends_on"]:
            if dep not in ancestors:
                ancestors.add(dep)
                collect(dep)

    collect(outputs[0]["id"])
    missing_deps = REQUIRED_KINDS - {"cv_output"} - {by_id[i]["kind"] for i in ancestors}
    reasons.extend(
        {"artifact": outputs[0]["id"], "reason": f"unlinked_kind_{k}"} for k in sorted(missing_deps)
    )
    output_record = output_records[outputs[0]["id"]]
    matching_frames = [
        by_id[i]
        for i in ancestors
        if by_id[i]["kind"] == "setup_frame" and by_id[i]["sha256"] == output_record["clip_sha256"]
    ]
    if not matching_frames:
        reasons.append({"artifact": outputs[0]["id"], "reason": "output_frame_hash_unlinked"})
    for frame in matching_frames:
        at = frame.get("evidence_max_seconds")
        if at is not None and at < output_record["evidence"]["frame_time"]:
            raise ValueError("setup frame is later than its declared evidence maximum")
    return {
        "pitch_id": pid,
        "eligible": not reasons,
        "reasons": reasons,
        "scope": "declared measured timing and artifact consistency; not an independent attestation",
    }


def prefix_camera_constants(frames, cutoff_seconds):
    """Pool only frames at or before cutoff, including valid edges on abstained rows.

    This isolates one pooling decision. Read availability and hop-2 calibration are
    unknown, so this helper alone does not make a causal, real-time pipeline.
    """
    cutoff = number(cutoff_seconds, "cutoff_seconds")
    keyed(frames)
    selected = []
    for row in frames:
        at = number(row.get("frame_seconds"), "frame_seconds")
        if at <= cutoff:
            selected.append(row)
    return camera_constants(selected)


def _edge(row):
    corners = row.get("plate_corners") or {}
    if not all(corners.get(k) is not None for k in ("front_left", "front_right")):
        return False
    values = np.asarray([corners["front_left"], corners["front_right"]], dtype=float)
    if values.shape != (2, 2) or not np.isfinite(values).all():
        raise ValueError("front-edge coordinates must be finite pairs")
    if np.linalg.norm(values[1] - values[0]) <= 0:
        raise ValueError("front edge must have positive length")
    return True


def _project(row, camera, matrix):
    corners = row["plate_corners"]
    width = float(np.linalg.norm(np.asarray(corners["front_right"]) - corners["front_left"]))
    pooled = camera["pa_median_width_px"].get(row["at_bat_number"], width)
    use = abs(width - pooled) <= POOLED_WIDTH_TOLERANCE * pooled
    h, _ = front_edge_similarity(
        corners, roll_radians=camera["roll_radians"], width_px=pooled if use else width
    )
    mitt = np.asarray(row["mitt_center"], dtype=float)
    if mitt.shape != (2,) or not np.isfinite(mitt).all():
        raise ValueError("mitt must be a finite pair")
    return zone_to_plate_feet(project_point(h, mitt), matrix)


def _distribution(values):
    return {
        "n": len(values),
        "min": min(values) if values else None,
        "median": float(np.median(values)) if values else None,
        "max": max(values) if values else None,
    }


def audit_game(game, results_dir):
    """Summarize stored evidence, not a new accuracy evaluation or annotation run."""
    if type(game) is not int or game <= 0:
        raise ValueError("game must be a positive integer")
    directory = Path(results_dir)
    sources = {}

    def read(suffix, required=True):
        path = directory / f"game_{game}_{suffix}.json"
        if not path.exists() and not required:
            return None
        doc = json.loads(path.read_text(encoding="utf-8-sig"))
        if doc.get("game_pk") != game:
            raise ValueError(f"wrong game in {path.name}")
        sources[path.name] = sha256(path)
        return doc

    points = read("intent_points_v0")
    timing = read("timing")
    windows = read("condensed_windows_v0", required=False)
    scan = read("condensed_scan_v0", required=False)
    frames, times = keyed(points["frames"]), keyed(timing["annotations"])
    if frames.keys() - times.keys():
        raise ValueError("points contain a pitch missing from timing")
    for key, row in frames.items():
        at = number(row.get("frame_seconds"), "frame_seconds")
        decision = number(times[key].get("decision_seconds"), "decision_seconds")
        if not math.isclose(at, decision, rel_tol=0, abs_tol=1e-6):
            raise ValueError("point and timing decision clocks disagree")
        index = times[key].get("decision_frame_index")
        if index is not None and row.get("frame_index") != index:
            raise ValueError("point and timing frame indices disagree")
    if windows:
        source = timing.get("source", {})
        if not source.get("media_url") or source["media_url"] != windows.get("media_url"):
            raise ValueError("window and timing media sources disagree")
        video = points["video"]
        fps = Fraction(video["fps_num"], video["fps_den"])
        if fps <= 0 or fps != Fraction(windows["fps"]):
            raise ValueError("window and point fps disagree")
        if source.get("fps") is not None and fps != Fraction(source["fps"]):
            raise ValueError("timing and point fps disagree")
    window_by_key = {}
    for window in windows["windows"] if windows else []:
        key = tuple(int(p) for p in window["pitch"].split(":"))
        if len(key) != 2 or key in window_by_key or key not in frames:
            raise ValueError("unexpected or duplicate window pitch")
        window_by_key[key] = window
        ids = [f["frame_index"] for f in window["frames"]]
        if len(ids) != len(set(ids)):
            raise ValueError("duplicate window frame index")
        selected = [
            f for f in window["frames"] if f["frame_index"] == frames[key].get("frame_index")
        ]
        if len(selected) != 1:
            raise ValueError("point frame missing from window")
        chosen = selected[0]
        if (
            not chosen.get("image_sha256")
            or chosen["image_sha256"] != frames[key].get("image_sha256")
            or not math.isclose(
                number(chosen["frame_time"], "selected window time"),
                frames[key]["frame_seconds"],
                rel_tol=0,
                abs_tol=1e-6,
            )
        ):
            raise ValueError("selected window frame hash/time disagrees with point")
    if windows and window_by_key.keys() != frames.keys():
        raise ValueError("window and point pitch sets disagree")
    rows = list(frames.values())
    for row in rows:
        number(row.get("frame_seconds"), "frame_seconds")
        _edge(row)
    camera = camera_constants(rows)
    edge_rows = [r for r in rows if _edge(r)]
    calib_path = directory / f"game_{game}_intent_plate_calibration_v0.json"
    calibration = load_calibration(calib_path)
    if calibration is not None:
        if calibration.get("game_pk") != game:
            raise ValueError("calibration belongs to another game")
        sources[calib_path.name] = sha256(calib_path)
    matrix = hop2_parameters(calibration)["matrix"]
    records, margins, dx, dz = [], [], [], []
    for key, row in sorted(frames.items()):
        if row.get("status") not in ("estimated", "unavailable"):
            raise ValueError("unexpected point status")
        at = row["frame_seconds"]
        release = times[key].get("release_seconds")
        if release is not None:
            number(release, "release_seconds")
        if row["status"] == "estimated" and release is not None:
            margins.append(release - at)
        win = window_by_key.get(key)
        offered = (
            [number(f["frame_time"], "window frame time") for f in win["frames"]] if win else []
        )
        future_edges = [r for r in edge_rows if r["frame_seconds"] > at]
        rec = {
            "pitch_id": f"{game}:{key[0]}:{key[1]}",
            "status": row["status"],
            "evidence_frame_seconds": at,
            "release_seconds": release,
            "frame_before_release": at < release if release is not None else None,
            "offered_window_max_seconds": max(offered) if offered else None,
            "offered_window_after_release": max(offered) > release
            if offered and release is not None
            else None,
            "available_at_seconds": None,
            "prepitch_eligible": False,
            "ineligibility_reason": "legacy artifacts do not record measured result availability or complete evidence dependencies",
            "later_front_edges_in_roll_pool": len(future_edges) if _edge(row) else None,
            "later_same_pa_width_sources": sum(r["at_bat_number"] == key[0] for r in future_edges)
            if _edge(row)
            else None,
        }
        if row["status"] == "estimated" and _edge(row):
            baseline = _project(row, camera, matrix)
            prefix = _project(row, prefix_camera_constants(rows, at), matrix)
            delta = [prefix[i] - baseline[i] for i in (0, 1)]
            rec["prefix_hop1_only_delta_feet"] = delta
            dx.append(abs(delta[0]))
            dz.append(abs(delta[1]))
        records.append(rec)
    match_statuses = (
        Counter(d.get("match_status", "unknown") for d in scan["detections"]) if scan else {}
    )
    return {
        "game_pk": game,
        "sources_sha256": sources,
        "summary": {
            "rows": len(rows),
            "estimated": sum(r["status"] == "estimated" for r in rows),
            "unavailable": sum(r["status"] == "unavailable" for r in rows),
            "measured_prepitch_availability_rows": 0,
            "estimated_frame_to_release_seconds": _distribution(margins),
            "windows_with_known_release": sum(
                r["offered_window_after_release"] is not None for r in records
            ),
            "windows_offered_after_release": sum(
                r["offered_window_after_release"] is True for r in records
            ),
            "estimated_edges_with_later_roll_sources": sum(
                r["status"] == "estimated" and (r["later_front_edges_in_roll_pool"] or 0) > 0
                for r in records
            ),
            "prefix_hop1_abs_dx_feet": _distribution(dx),
            "prefix_hop1_abs_dz_feet": _distribution(dz),
            "scan_match_statuses": dict(match_statuses),
        },
        "rows": records,
    }


def build_report(games, results_dir):
    if len(set(games)) != len(games):
        raise ValueError("duplicate games")
    reports = [audit_game(g, results_dir) for g in games]
    return {
        "schema": REPORT_SCHEMA,
        "scope": "development audit of already reviewed artifacts",
        "claims": {
            "new_accuracy_evaluation": False,
            "live_latency_measured": False,
            "independent_validation": False,
            "prepitch_pipeline_complete": False,
        },
        "limitations": [
            "Offered windows are not a log of frames actually inspected.",
            "Frame-before-release is different from result availability.",
            "Prefix calculation changes hop-1 pooling only; hop-2 remains frozen and retrospective.",
            "No new detector, frame labeling, human review or service integration is performed.",
        ],
        "source_sha256": {
            f"intent/{p}": sha256(ROOT / "intent" / p)
            for p in (
                "temporal_audit.py",
                "run.py",
                "geometry.py",
                "plate_feet.py",
                "condensed.py",
                "calibrate.py",
            )
        },
        "games": reports,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    audit = sub.add_parser("audit")
    audit.add_argument("--games", type=int, nargs="+", required=True)
    audit.add_argument("--results-dir", type=Path, default=ROOT / "docs/results/mlb_p0")
    audit.add_argument("--out", type=Path, required=True)
    check = sub.add_parser("check")
    check.add_argument("--trace", type=Path, required=True)
    check.add_argument("--artifact-root", type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        if args.command == "check":
            result = validate_trace(
                json.loads(args.trace.read_text(encoding="utf-8-sig")), args.artifact_root
            )
            print(json.dumps(result, ensure_ascii=False, allow_nan=False))
            return 0 if result["eligible"] else 2
        report = build_report(args.games, args.results_dir)
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, ensure_ascii=False, indent=2, allow_nan=False)
            handle.write("\n")
        print(
            json.dumps(
                {
                    "out": str(args.out),
                    "games": [{"game_pk": g["game_pk"], **g["summary"]} for g in report["games"]],
                },
                ensure_ascii=False,
            )
        )
        return 0
    except (ValueError, OSError, KeyError, TypeError) as exc:
        parser.exit(2, f"temporal audit: {exc}\n")


if __name__ == "__main__":
    raise SystemExit(main())

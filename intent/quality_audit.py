"""Audit availability and one-at-a-time x sensitivity without changing M3 artifacts.

    python -m intent.quality_audit --games 849845 823407 --out outputs/quality_new.json

This is a development diagnostic on previously reviewed frames, not a new independent
evaluation, a confidence interval, or a physical-accuracy measurement. Games stay separate.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from collections import Counter
from copy import deepcopy
from pathlib import Path

import numpy as np

from intent.geometry import front_edge_similarity, project_point
from intent.human_labels import game_role, validate_labels
from intent.plate_feet import (
    hop2_parameters,
    load_calibration,
    zone_to_feet_matrix,
    zone_to_plate_feet,
)
from intent.schema import validate_intent_estimate

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs/results/mlb_p0"
SCHEMA = "intent_quality_development_audit_v1"
LIMITS = [
    "Previously reviewed frames; development diagnostic, not new independent validation.",
    "Availability disagreements are not adjudicated errors; labeling rules may differ.",
    "Sensitivity is an assumed parameter perturbation, not physical error or a confidence interval.",
    "Only x is analyzed; nominal mitt depth is assumed, not measured per pitch.",
    "Existing pooled roll/width are held fixed except for the explicitly perturbed variable.",
    "File hashes bind this report to inputs; matching stored frame hashes do not recheck image bytes.",
]


def finite_tree(value, context="input"):
    """Reject nonfinite numeric input even in nested, otherwise unchecked evidence."""
    if isinstance(value, float) and not math.isfinite(value):
        raise ValueError(f"nonfinite number in {context}")
    if isinstance(value, dict):
        for key, item in value.items():
            finite_tree(item, f"{context}.{key}")
    elif isinstance(value, list):
        for index, item in enumerate(value):
            finite_tree(item, f"{context}[{index}]")


def _load(path):
    value = json.loads(Path(path).read_text(encoding="utf-8-sig"))
    finite_tree(value, str(path))
    return value


def _index(rows, name):
    indexed = {}
    for row in rows:
        pid = row.get("pitch_id")
        if not isinstance(pid, str) or not pid:
            raise ValueError(f"missing pitch_id in {name}")
        if pid in indexed:
            raise ValueError(f"duplicate pitch_id {pid} in {name}")
        indexed[pid] = row
    return indexed


def _xy(value, name):
    if not isinstance(value, (list, tuple)) or len(value) != 2:
        raise ValueError(f"{name} must contain two finite coordinates")
    if any(isinstance(v, bool) or not isinstance(v, (int, float)) for v in value):
        raise ValueError(f"{name} must contain numeric coordinates")
    if not all(math.isfinite(v) for v in value):
        raise ValueError(f"nonfinite coordinate in {name}")
    return list(map(float, value))


def _number(value, name):
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{name} must be a finite number, not a numeric string")
    return float(value)


def validate_inputs(game, points, labels, manifest, records, calibration=None):
    """Validate identities and source bindings; return indexed points, labels and records."""
    for name, doc in (("points", points), ("labels", labels), ("manifest", manifest)):
        finite_tree(doc, name)
        if doc.get("game_pk") != game:
            raise ValueError(f"game mismatch in {name}")
    if points.get("schema") != "intent_points_v0":
        raise ValueError("unexpected points schema")
    if manifest.get("schema") != "intent_label_pack_v0":
        raise ValueError("unexpected label manifest schema")
    by_manifest = _index(manifest["frames"], "manifest")
    by_label = _index(validate_labels(labels, manifest), "labels")
    point_rows = []
    for frame in points["frames"]:
        for key in ("at_bat_number", "pitch_number"):
            if type(frame.get(key)) is not int or frame[key] <= 0:
                raise ValueError(f"invalid {key} in points")
        pid = f"{game}:{frame['at_bat_number']}:{frame['pitch_number']}"
        if frame.get("pitch_id", pid) != pid:
            raise ValueError("explicit points pitch_id disagrees with pitch key")
        point_rows.append(dict(frame, pitch_id=pid))
    by_point = _index(point_rows, "points")
    finite_tree(records, "JSONL")
    by_record = _index(records, "JSONL")
    if by_point.keys() != by_record.keys():
        raise ValueError("points and JSONL pitch_id sets differ")
    if not by_manifest.keys() <= by_point.keys():
        raise ValueError("label manifest contains pitch_id absent from points/JSONL")
    for pid, point in by_point.items():
        rec = by_record[pid]
        validate_intent_estimate(rec)
        if point.get("image_sha256") != rec["clip_sha256"]:
            raise ValueError(f"frame hash mismatch in points/JSONL: {pid}")
        if point.get("status") != rec["status"]:
            raise ValueError(f"status mismatch in points/JSONL: {pid}")
        time = _number(point["frame_seconds"], "points frame_seconds")
        if time < 0 or abs(time - rec["evidence"]["frame_time"]) > 1e-6:
            raise ValueError(f"frame time mismatch in points/JSONL: {pid}")
        if point["status"] == "estimated":
            mitt = _xy(point.get("mitt_center"), pid)
            published = rec["points"]["image_pixels"]
            if mitt != [published["x"], published["y"]]:
                raise ValueError(f"mitt coordinate mismatch in points/JSONL: {pid}")
        elif point.get("mitt_center") is not None:
            raise ValueError(f"unavailable point carries a mitt: {pid}")
    for pid, label in by_label.items():
        frame, point = by_manifest[pid], by_point[pid]
        if frame["image_sha256"] != point["image_sha256"]:
            raise ValueError(f"frame hash mismatch in labels/points: {pid}")
        for entry in (frame, label):
            if (
                abs(
                    _number(entry.get("frame_seconds"), "label frame_seconds")
                    - point["frame_seconds"]
                )
                > 1e-6
            ):
                raise ValueError(f"label/manifest frame time mismatch: {pid}")
        if label["mitt_status"] == "marked":
            _xy(label["mitt"], f"human mitt {pid}")
        if label["plate_status"] == "marked":
            front = label["plate_front"]
            left = _xy(front["left_end"], f"human plate {pid}")
            right = _xy(front["right_end"], f"human plate {pid}")
            if math.dist(left, right) <= 1e-9:
                raise ValueError(f"degenerate human plate front: {pid}")
    if calibration is not None:
        finite_tree(calibration, "calibration")
        if calibration.get("schema") != "intent_plate_calibration_v0":
            raise ValueError("unexpected calibration schema")
        if calibration.get("game_pk") != game:
            raise ValueError("calibration game mismatch")
        for key in ("tilt_sin", "pan_tan", "mitt_depth_feet"):
            _number(calibration["hop2"].get(key, 0), f"calibration {key}")
        params = hop2_parameters(calibration)
        expected = zone_to_feet_matrix(
            params["tilt_sin"], params["mitt_depth_feet"], params["pan_tan"]
        )
        if not np.allclose(params["matrix"], expected, atol=1e-10, rtol=0):
            raise ValueError("calibration matrix disagrees with parameters")
        error = calibration.get("rms_error_feet")
        measured = calibration.get("error_status") == "measured"
        if measured != (error is not None) or (error is not None and error < 0):
            raise ValueError("calibration measured status disagrees with rms_error_feet")
    return by_point, by_label, by_record


def availability(points, labels):
    """Cross-tabulate marking decisions without classifying disagreements as errors."""
    cells = {
        "both_marked": 0,
        "both_abstained": 0,
        "ai_only": 0,
        "human_only": 0,
        "human_undecided": 0,
        "human_not_in_pack": 0,
    }
    ai_reasons, human_reasons, disagreements = Counter(), Counter(), []
    ai_marked = human_marked = 0
    for pid, point in points.items():
        a = point["status"] == "estimated"
        ai_marked += a
        if not a:
            ai_reasons[point.get("unavailable_reason") or "unknown"] += 1
        label = labels.get(pid)
        h_status = label.get("mitt_status") if label else None
        if label is None:
            cell = "human_not_in_pack"
        elif h_status is None:
            cell = "human_undecided"
            human_reasons["unknown_undecided"] += 1
        else:
            h = h_status == "marked"
            human_marked += h
            if not h:
                human_reasons[h_status] += 1
            cell = (
                ("both_marked" if h else "ai_only")
                if a
                else ("human_only" if h else "both_abstained")
            )
            if a != h:
                disagreements.append(
                    {
                        "pitch_id": pid,
                        "ai_status": point["status"],
                        "ai_reason": None if a else point.get("unavailable_reason") or "unknown",
                        "human_status": h_status,
                        "adjudication": "unknown_not_reviewed",
                    }
                )
        cells[cell] += 1
    decided = len(labels) - cells["human_undecided"]
    return {
        "denominators": {
            "all_output_pitches": len(points),
            "human_pack_pitches": len(labels),
            "human_decided": decided,
            "both_marked": cells["both_marked"],
        },
        "ai_marked": ai_marked,
        "ai_abstained": len(points) - ai_marked,
        "human_marked": human_marked,
        "human_abstained": decided - human_marked,
        "cells": cells,
        "ai_abstention_reasons": dict(ai_reasons),
        "human_abstention_reasons": dict(human_reasons),
        "disagreements": disagreements,
        "interpretation": "Different marking decisions; unknown correctness until adjudicated "
        "under an agreed target/visibility rule. No error rate is inferred.",
    }


def _parameters(point, record, calibration):
    steps = record["transform_chain"]
    if len(steps) != 2 or steps[0]["method"] != "plate_front_edge_similarity":
        raise ValueError(f"unsupported transform for {record['pitch_id']}")
    first, second = steps[0]["evidence"], steps[1]["evidence"]
    corners = first["plate_corners_image_pixels"]
    for key in ("front_left", "front_right"):
        if _xy(corners[key], key) != _xy(point["plate_corners"][key], key):
            raise ValueError("published plate corners differ from points")
    params = {
        "mitt": _xy(point["mitt_center"], "mitt"),
        "corners": deepcopy(corners),
        "roll": float(first["diagnostics"]["roll_used_radians"]),
        "width": float(first["diagnostics"]["width_used_px"]),
        "tilt": math.asin(float(second["camera_tilt_sin"])),
        "pan": math.atan(float(second["camera_pan_tan"])),
        "depth": float(second["nominal_mitt_depth_feet"]),
    }
    matrix = zone_to_feet_matrix(math.sin(params["tilt"]), params["depth"], math.tan(params["pan"]))
    if not np.allclose(matrix, second["matrix"], rtol=0, atol=1e-10):
        raise ValueError("published hop2 matrix disagrees with its parameters")
    if calibration is not None and not np.allclose(
        matrix, calibration["hop2"]["matrix"], rtol=0, atol=1e-10
    ):
        raise ValueError("published hop2 matrix disagrees with calibration")
    return params


def x_from_parameters(params):
    """Evaluate the existing two-hop mapping with explicit, fixed parameters."""
    if not 0 <= params["tilt"] < math.pi / 2 or abs(params["pan"]) >= math.pi / 2:
        raise ValueError("camera angle outside transform domain")
    h, _ = front_edge_similarity(
        params["corners"], roll_radians=params["roll"], width_px=params["width"]
    )
    matrix = zone_to_feet_matrix(math.sin(params["tilt"]), params["depth"], math.tan(params["pan"]))
    return zone_to_plate_feet(project_point(h, params["mitt"]), matrix)[0]


def perturbations(params):
    """Yield named one-variable perturbations, retaining both signs independently."""
    for sign in (-1, 1):
        for axis in (0, 1):
            p = deepcopy(params)
            p["mitt"][axis] += sign
            yield f"mitt_{'xy'[axis]}_{sign:+d}px", p
            p = deepcopy(params)
            for key in ("front_left", "front_right"):
                p["corners"][key][axis] += sign
            yield f"front_midpoint_{'xy'[axis]}_{sign:+d}px", p
        for suffix, amount in (("px", 1), ("percent", params["width"] * 0.05)):
            p = deepcopy(params)
            p["width"] += sign * amount
            size = sign if suffix == "px" else sign * 5
            yield f"front_width_{size:+d}{suffix}", p
        for key in ("roll", "pan", "tilt"):
            p = deepcopy(params)
            p[key] += math.radians(sign)
            yield f"{key}_{sign:+d}deg", p
        p = deepcopy(params)
        p["depth"] += sign
        yield f"nominal_depth_{sign:+d}ft", p


def sensitivity(point, record, calibration):
    """Reproduce the published x then vary one parameter; abstentions have no fake zeros."""
    if "plate_feet" not in record["points"]:
        return {
            "pitch_id": record["pitch_id"],
            "status": "not_available",
            "reason": "no_published_plate_feet",
            "baseline_x_ft": None,
            "changes": {},
        }
    params = _parameters(point, record, calibration)
    baseline = x_from_parameters(params)
    published = record["points"]["plate_feet"]["x"]
    if not math.isclose(baseline, published, abs_tol=1e-9, rel_tol=0):
        raise ValueError(f"published x cannot be reproduced: {record['pitch_id']}")
    changes = {}
    for name, changed in perturbations(params):
        try:
            x = x_from_parameters(changed)
        except ValueError as exc:
            changes[name] = {"status": "outside_domain", "delta_x_ft": None, "reason": str(exc)}
        else:
            if not math.isfinite(x):
                raise ValueError("nonfinite perturbation result")
            changes[name] = {"status": "computed", "delta_x_ft": x - baseline}
    return {
        "pitch_id": record["pitch_id"],
        "status": "computed",
        "baseline_x_ft": baseline,
        "width_px": params["width"],
        "changes": changes,
    }


def sensitivity_summary(rows):
    """Summarize absolute changes by perturbation within one game only."""
    values, skipped = {}, Counter()
    for row in rows:
        for name, result in row["changes"].items():
            values.setdefault(name, [])
            if result["status"] == "computed":
                values[name].append(abs(result["delta_x_ft"]))
            else:
                skipped[name] += 1
    return {
        name: {
            "n_computed": len(v),
            "n_outside_domain": skipped[name],
            "median_abs_delta_x_ft": float(np.median(v)) if v else None,
            "max_abs_delta_x_ft": max(v) if v else None,
        }
        for name, v in sorted(values.items())
    }


def build_game(game, results_dir):
    """Load one game, validate all joins and return a source-bound diagnostic."""
    results = Path(results_dir)
    suffixes = {
        "points": "points_v0.json",
        "labels": "human_labels_v0.json",
        "manifest": "label_pack_v0.json",
        "calibration": "plate_calibration_v0.json",
        "jsonl": "v0.jsonl",
    }
    paths = {key: results / f"game_{game}_intent_{suffix}" for key, suffix in suffixes.items()}
    loaded = {key: _load(paths[key]) for key in ("points", "labels", "manifest")}
    calibration = None
    if paths["calibration"].is_file():
        _load(paths["calibration"])  # Reject nonfinite nested evidence before matrix validation.
        calibration = load_calibration(paths["calibration"])
    records = [
        json.loads(line)
        for line in paths["jsonl"].read_text(encoding="utf-8-sig").splitlines()
        if line.strip()
    ]
    points, labels, indexed = validate_inputs(
        game, **loaded, records=records, calibration=calibration
    )
    rows = [sensitivity(points[pid], indexed[pid], calibration) for pid in sorted(points)]
    plan = results / "intent_eval_plan_v0.json"
    sources = {
        key: {"path": path.name, "sha256": hashlib.sha256(path.read_bytes()).hexdigest()}
        for key, path in paths.items()
        if path.is_file()
    }
    if plan.is_file():
        sources["plan"] = {
            "path": plan.name,
            "sha256": hashlib.sha256(plan.read_bytes()).hexdigest(),
        }
    return {
        "game_pk": game,
        "original_plan_role": game_role(game, plan),
        "current_use": "development_diagnostic_on_reviewed_frames",
        "sources": sources,
        "calibration": {
            "file_available": calibration is not None,
            "recorded_error_status": calibration.get("error_status", "unknown")
            if calibration
            else "unknown_no_file",
            "recorded_rms_error_feet": calibration.get("rms_error_feet") if calibration else None,
            "interpretation": "Existing metadata only; not remeasured by this audit. "
            "A null value is unmeasured or unknown, never zero error.",
        },
        "availability": availability(points, labels),
        "sensitivity": {
            "eligible_pitches": sum(r["status"] == "computed" for r in rows),
            "summary": sensitivity_summary(rows),
            "per_pitch": rows,
        },
    }, list(paths.values()) + [plan]


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--games", type=int, nargs="+", required=True)
    parser.add_argument("--results-dir", type=Path, default=RESULTS)
    parser.add_argument(
        "--out", type=Path, required=True, help="New output path; never overwritten"
    )
    args = parser.parse_args(argv)
    if len(args.games) != len(set(args.games)) or any(g <= 0 for g in args.games):
        parser.error("games must be unique positive game IDs")
    if args.out.exists():
        parser.error(
            "output already exists; choose a new path (input/output overwrite is forbidden)"
        )
    games, inputs = [], []
    for game in args.games:
        block, paths = build_game(game, args.results_dir)
        games.append(block)
        inputs.extend(paths)
    if args.out.resolve() in {p.resolve() for p in inputs}:
        parser.error("output must not name an input path, including a currently missing input")
    report = {
        "schema": SCHEMA,
        "scope": "development_diagnostic",
        "limitations": LIMITS,
        "pooling": "none: each game stays separate regardless of original role",
        "games": games,
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with args.out.open("x", encoding="utf-8") as stream:
        json.dump(report, stream, ensure_ascii=False, indent=2, allow_nan=False)
        stream.write("\n")
    print(f"Wrote development diagnostic for {len(games)} games: {args.out}")


if __name__ == "__main__":
    main()

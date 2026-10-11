"""Build the M3 accuracy table (``accuracy_report.json``) from the per-game setup checks.

    python -m intent.accuracy_report [--code-commit <hash>]

Reads the committed evaluation plan (``docs/results/mlb_p0/intent_eval_plan_v0.json``: which
games are development and which are evaluation) and, per game, the points file (assistant
abstentions), the condensed-game scan (coverage, when there is one), the plate calibration (the
catch-vs-Statcast camera check), the label-pack manifest and, once the person's labels have been
imported with ``python -m intent.human_labels``, ``game_<g>_intent_setup_check_v0.json``.

Writes ``docs/results/mlb_p0/intent_accuracy_report_v0.json``. Development and evaluation games
sit in separate blocks and are never pooled; the pooled block covers the labeled evaluation games
only. A game without imported labels is reported as ``awaiting_labels`` with no error numbers.

The plan's fallback (``FALLBACK_GAMES``: 849849, then 849851) enters only when both planned
evaluation games are labeled and together have fewer than 50 person-marked pitches, one game at a
time, until the total reaches 50.

Three error families are kept apart because they measure different things:

- ``mitt_reading``: assistant vs person mitt point on the same frame, in pixels and in feet with
  both points mapped through the PERSON's plate edge and the same hop-2 matrix. This isolates the
  mitt reading; the camera transform cancels.
- ``output_vs_person``: the published ``plate_feet`` against the person's mitt through the
  person's plate edge (mitt reading plus plate-edge reading, same matrix). It still shares the
  hop-2 matrix with the assistant, so it says nothing about physical (camera) accuracy.
- ``camera_check``: the catch-vs-Statcast check of ``intent.calibrate`` (assistant-read ball in
  the mitt vs the Statcast trajectory), the only physical check; it has no person in it.

Example pitches are chosen by a fixed rule (``example_cases``), never by hand.
"""

from __future__ import annotations

import argparse
import json
import math
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intent.human_labels import FALLBACK_GAMES, _percentile  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs/results/mlb_p0"
REPORT_SCHEMA = "intent_accuracy_report_v0"
M3_MIN_PERSON_MARKED = 50
M3_MIN_EVAL_GAMES = 2
WORST = 5
EXAMPLE_RULE = (
    "among frames where both marked a mitt: representative = output feet error closest to the "
    "median, best = smallest, worst = largest (mitt pixel distance when no frame reached "
    "plate_feet); ties by pitch_id; chosen by code, never by hand"
)
ERROR_KEYS = (
    "mitt_px",
    "mitt_dx_px",
    "mitt_dy_px",
    "same_plate_dx_ft",
    "same_plate_dz_ft",
    "same_plate_ft",
    "output_dx_ft",
    "output_dz_ft",
    "output_ft",
)


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _summary(values):
    values = [float(v) for v in values]
    return {"n": len(values), "median": _percentile(values, 0.5), "p90": _percentile(values, 0.9)}


def _signed(values):
    values = [float(v) for v in values]
    if not values:
        return {"n": 0, "mean": None, "median": None, "se_of_mean": None}
    sd = statistics.stdev(values) if len(values) > 1 else None
    return {
        "n": len(values),
        "mean": statistics.fmean(values),
        "median": _percentile(values, 0.5),
        "se_of_mean": sd / math.sqrt(len(values)) if sd is not None else None,
    }


def _axis_block(signed_values):
    return {"signed": _signed(signed_values), "absolute": _summary([abs(v) for v in signed_values])}


def _rate(num, den):
    return num / den if den else None


def frame_errors(check):
    """Per-frame error lists from one setup check (frames where both marked)."""
    out = {k: [] for k in ERROR_KEYS}
    for f in check.get("per_frame", []):
        if f.get("mitt_px_diff"):
            dx, dy = f["mitt_px_diff"]
            out["mitt_px"].append(math.hypot(dx, dy))
            out["mitt_dx_px"].append(dx)
            out["mitt_dy_px"].append(dy)
        if f.get("mitt_feet_diff_same_plate"):
            dx, dz = f["mitt_feet_diff_same_plate"]
            out["same_plate_dx_ft"].append(dx)
            out["same_plate_dz_ft"].append(dz)
            out["same_plate_ft"].append(math.hypot(dx, dz))
        if f.get("output_feet_diff"):
            dx, dz = f["output_feet_diff"]
            out["output_dx_ft"].append(dx)
            out["output_dz_ft"].append(dz)
            out["output_ft"].append(math.hypot(dx, dz))
    return out


def error_blocks(errors):
    return {
        "mitt_reading_pixels": {
            "denominator": "frames where both the assistant and the person marked a mitt",
            "distance": _summary(errors["mitt_px"]),
            "dx_assistant_minus_person": _axis_block(errors["mitt_dx_px"]),
            "dy_assistant_minus_person": _axis_block(errors["mitt_dy_px"]),
        },
        "mitt_reading_feet_same_plate": {
            "denominator": "both marked a mitt and the person marked the plate front edge",
            "distance": _summary(errors["same_plate_ft"]),
            "x_assistant_minus_person": _axis_block(errors["same_plate_dx_ft"]),
            "z_assistant_minus_person": _axis_block(errors["same_plate_dz_ft"]),
        },
        "output_vs_person_feet": {
            "denominator": "both marked a mitt, the person marked the plate front edge, and the "
            "published line reached plate_feet",
            "distance": _summary(errors["output_ft"]),
            "x_published_minus_person": _axis_block(errors["output_dx_ft"]),
            "z_published_minus_person": _axis_block(errors["output_dz_ft"]),
        },
    }


def _rel(path):
    try:
        return Path(path).resolve().relative_to(ROOT).as_posix()
    except ValueError:
        return Path(path).as_posix()


def _output_ft(f):
    return math.hypot(*f["output_feet_diff"]) if f.get("output_feet_diff") else None


def example_cases(frames):
    """Fixed-rule examples among frames where both marked a mitt.

    representative: output feet error closest to the median of those frames (mitt pixel distance
    when no frame has an output error); best: smallest; worst: largest. Ties go to the smaller
    pitch_id string.
    """
    both = [f for f in frames if f.get("mitt_px_diff")]
    if not both:
        return {"rule": EXAMPLE_RULE, "cases": []}
    with_out = [f for f in both if f.get("output_feet_diff")]
    pool, metric, key = (
        (with_out, "output_feet_distance", _output_ft)
        if with_out
        else (both, "mitt_pixel_distance", lambda f: math.hypot(*f["mitt_px_diff"]))
    )
    median = _percentile([key(f) for f in pool], 0.5)
    ordered = sorted(pool, key=lambda f: (key(f), f["pitch_id"]))
    rep = min(pool, key=lambda f: (abs(key(f) - median), f["pitch_id"]))
    picks = [
        ("representative", rep),
        ("best (success, not typical)", ordered[0]),
        ("worst (failure)", ordered[-1]),
    ]
    return {
        "rule": EXAMPLE_RULE,
        "metric": metric,
        "median": median,
        "cases": [
            {
                "role": role,
                "pitch_id": f["pitch_id"],
                "value": round(key(f), 4),
                "mitt_px_diff": f["mitt_px_diff"],
                "output_feet_diff": f.get("output_feet_diff"),
            }
            for role, f in picks
        ],
    }


def failure_cases(check):
    frames = check.get("per_frame", [])
    worst = sorted(
        (f for f in frames if f.get("mitt_px_diff")),
        key=lambda f: (-math.hypot(*f["mitt_px_diff"]), f["pitch_id"]),
    )[:WORST]
    disagree = [
        {
            "pitch_id": f["pitch_id"],
            "assistant_status": f["assistant_status"],
            "assistant_reason": f.get("assistant_reason"),
            "person_status": f["person_status"],
        }
        for f in frames
        if f.get("person_status") is not None
        and (f["assistant_status"] == "estimated") != (f["person_status"] == "marked")
    ]
    return {
        "largest_mitt_pixel_differences": [
            {
                "pitch_id": f["pitch_id"],
                "mitt_px_diff": f["mitt_px_diff"],
                "distance_px": round(math.hypot(*f["mitt_px_diff"]), 2),
                "output_feet_diff": f.get("output_feet_diff"),
            }
            for f in worst
        ],
        "availability_disagreements": disagree,
    }


def game_block(entry, results=RESULTS):
    g = entry["game_pk"]
    points = _load(results / f"game_{g}_intent_points_v0.json")
    frames = points["frames"]
    estimated = sum(1 for f in frames if f["status"] == "estimated")
    reasons = Counter(f.get("unavailable_reason") for f in frames if f["status"] != "estimated")
    check_path = results / f"game_{g}_intent_setup_check_v0.json"
    check = _load(check_path) if check_path.is_file() else None
    block = {
        "game_pk": g,
        "role": entry.get("role", "evaluation"),
        "broadcast": entry.get("broadcast"),
        "video": entry.get("video"),
        "files": {
            "jsonl": (check or {}).get("jsonl") or _rel(results / f"game_{g}_intent_v0.jsonl"),
            "points": _rel(results / f"game_{g}_intent_points_v0.json"),
            "calibration": _rel(results / f"game_{g}_intent_plate_calibration_v0.json"),
        },
        "pitches_in_output": len(frames),
        "assistant": {
            "estimated": estimated,
            "unavailable": len(frames) - estimated,
            "abstention_rate": _rate(len(frames) - estimated, len(frames)),
            "abstention_rate_denominator": "lines in the game's output",
            "abstention_reasons": dict(reasons),
        },
    }
    scan_path = results / f"game_{g}_condensed_scan_v0.json"
    if scan_path.is_file():
        scan = _load(scan_path)
        block["coverage"] = {
            "feed_pitches": scan["feed_pitches"],
            "share_of_game": len(frames) / scan["feed_pitches"],
            "selection": "pitches the condensed game shows (mostly plate-appearance-ending)",
        }
    cal_path = results / f"game_{g}_intent_plate_calibration_v0.json"
    if cal_path.is_file():
        cal = _load(cal_path)
        ref = (cal["end_to_end_check"].get("by_depth_y") or {}).get("-1.0") or {}
        measured = cal.get("error_status") == "measured"
        block["camera_check_catch_vs_statcast"] = {
            "rms_error_feet": cal.get("rms_error_feet"),
            "rms_basis": cal.get("rms_basis"),
            "error_status": cal.get("error_status"),
            "pitches_used": cal["end_to_end_check"].get("pitches_used"),
            "min_pitches": cal.get("min_pitches"),
            "x_mean_signed_feet": (ref.get("x") or {}).get("mean_signed_feet")
            if measured
            else None,
            "z_mean_signed_feet": (ref.get("z") or {}).get("mean_signed_feet")
            if measured
            else None,
            "signed_means_note": None
            if measured
            else "omitted: fewer than min_pitches catches; raw values in the calibration file",
            "human_verified_count": cal.get("human_verified_count"),
            "tilt_degrees": (cal.get("camera", {}).get("tilt") or {}).get("degrees"),
            "pan_degrees": (cal.get("hop2", {}).get("pan_estimate") or {}).get("pan_degrees"),
            "pan_readings": (cal.get("hop2", {}).get("pan_estimate") or {}).get("n"),
        }
    pack_path = results / f"game_{g}_intent_label_pack_v0.json"
    pack = _load(pack_path) if pack_path.is_file() else None
    if pack:
        block["label_pack"] = {
            "pack_id": pack["pack_id"],
            "frames": len(pack["frames"]),
            "manifest": _rel(pack_path),
        }
    if check is None:
        block["person"] = {"status": "awaiting_labels"}
        return block, None
    a = check["availability"]
    frames_in_pack = len(pack["frames"]) if pack else check["frames_labeled"]
    decided = check["frames_labeled"] - a["person_undecided"]
    marked = a["both_marked"] + a["person_only"]
    errors = frame_errors(check)
    person_reasons = Counter(
        f["person_status"]
        for f in check.get("per_frame", [])
        if f.get("person_status") not in (None, "marked")
    )
    warnings = []
    if errors["same_plate_ft"] and not errors["output_ft"]:
        warnings.append("same-plate feet errors exist but no output feet error: check the JSONL")
    block["person"] = {
        "status": "labeled",
        "provenance": {
            "labeler": check.get("labeler"),
            "labeler_source": check.get("labeler_source"),
            "exported_at": check.get("exported_at"),
            "exported_at_meaning": "time the person pressed export on the page (UTC); "
            "elapsed_seconds is the time the page was open and visible",
            "elapsed_seconds": check.get("elapsed_seconds"),
            "pack_id": check.get("pack_id"),
            "raw_file": check.get("raw_file"),
            "raw_sha256": check.get("raw_sha256"),
            "labels_file": check.get("labels_file"),
            "setup_check_file": _rel(check_path),
        },
        "frames_in_pack": frames_in_pack,
        "frames_decided": decided,
        "person_undecided": frames_in_pack - decided,
        "person_marked": marked,
        "person_abstained": decided - marked,
        "person_abstention_reasons": dict(person_reasons),
        "person_abstention_rate": _rate(decided - marked, decided),
        "person_abstention_rate_denominator": "frames the person decided",
        "availability": a,
        **error_blocks(errors),
        "example_cases": example_cases(check.get("per_frame", [])),
        "failure_cases": failure_cases(check),
        "warnings": warnings,
    }
    extra = {
        "check": check,
        "errors": errors,
        "decided": decided,
        "marked": marked,
        "frames_in_pack": frames_in_pack,
        "lines": len(frames),
        "estimated": estimated,
        "assistant_reasons": reasons,
        "person_reasons": person_reasons,
    }
    return block, extra


def build(plan, results=RESULTS, code_commit=None):
    development, evaluation = [], []
    pooled = {k: [] for k in ERROR_KEYS}
    totals = Counter()
    availability, assistant_reasons, person_reasons = Counter(), Counter(), Counter()
    pooled_games, per_game, undecided_games, pooled_frames = [], [], [], []

    def add(entry):
        if not (results / f"game_{entry['game_pk']}_intent_points_v0.json").is_file():
            evaluation.append(
                {"game_pk": entry["game_pk"], "role": entry["role"], "status": "not_processed"}
            )
            return None
        block, extra = game_block(entry, results)
        evaluation.append(block)
        if extra is None:
            per_game.append({"game_pk": entry["game_pk"], "status": "awaiting_labels"})
            return None
        per_game.append(
            {
                "game_pk": entry["game_pk"],
                "person_marked": extra["marked"],
                "person_undecided": block["person"]["person_undecided"],
            }
        )
        if block["person"]["person_undecided"]:
            undecided_games.append(entry["game_pk"])
        pooled_games.append(entry["game_pk"])
        totals.update(
            decided=extra["decided"],
            marked=extra["marked"],
            frames_in_pack=extra["frames_in_pack"],
            lines=extra["lines"],
            estimated=extra["estimated"],
        )
        availability.update(extra["check"]["availability"])
        pooled_frames.extend(extra["check"].get("per_frame", []))
        assistant_reasons.update(extra["assistant_reasons"])
        person_reasons.update(extra["person_reasons"])
        for k in pooled:
            pooled[k] += extra["errors"][k]
        return extra

    for entry in plan["development_games"]:
        if (results / f"game_{entry['game_pk']}_intent_points_v0.json").is_file():
            development.append(game_block(dict(entry, role="development"), results)[0])
    planned = [dict(e, role="evaluation") for e in plan["evaluation_games"]["games"]]
    planned_extras = [add(e) for e in planned]
    planned_labeled = all(x is not None for x in planned_extras)
    fallback_triggered = planned_labeled and totals["marked"] < M3_MIN_PERSON_MARKED
    fallback_added, next_fallback = [], None
    if fallback_triggered:
        for g in FALLBACK_GAMES:
            if totals["marked"] >= M3_MIN_PERSON_MARKED:
                break
            fallback_added.append(g)
            if add({"game_pk": g, "role": "evaluation_fallback"}) is None:
                next_fallback = g  # added but not processed or not labeled yet
                break
    games_with_marks = sum(1 for p in per_game if p.get("person_marked"))
    met = games_with_marks >= M3_MIN_EVAL_GAMES and totals["marked"] >= M3_MIN_PERSON_MARKED
    if fallback_triggered and not met and next_fallback is None:
        remaining = [g for g in FALLBACK_GAMES if g not in fallback_added]
        next_fallback = remaining[0] if remaining else None
    decided, marked = totals["decided"], totals["marked"]
    return {
        "schema": REPORT_SCHEMA,
        "plan": "docs/results/mlb_p0/intent_eval_plan_v0.json",
        "code_commit": code_commit,
        "definitions": {
            "mitt_reading_pixels": "assistant mitt point minus the person's on the same decision "
            "frame, source pixels",
            "mitt_reading_feet_same_plate": "both mitt points mapped through the person's plate "
            "front edge and the game's hop-2 matrix; isolates the mitt reading",
            "output_vs_person_feet": "published plate_feet (JSONL) minus the person's mitt mapped "
            "through the person's plate front edge and the game's hop-2 matrix; shares the matrix, "
            "so it is not a physical-accuracy measurement",
            "camera_check_catch_vs_statcast": "the only physical check: assistant-read ball in the "
            "mitt through hops 1-2 vs the Statcast trajectory (intent.calibrate); no person",
            "assistant abstention_rate": "unavailable lines / lines in the game's output",
            "person_abstention_rate": "frames the person marked hidden / not in setup / not centre "
            "field, over the frames the person decided; abstentions are not counted as marked",
            "x, z": "x = statcast_plate_x catcher view (feet), z = height (feet); dx/dy in pixels "
            "are image right/down",
            "percentiles": "nearest-rank median and 90th percentile everywhere; signed blocks add "
            "the mean and the standard error of the mean",
        },
        "m3_requirement": {
            "rule": f"at least {M3_MIN_PERSON_MARKED} person-marked pitches over at least "
            f"{M3_MIN_EVAL_GAMES} evaluation games that each have at least one person-marked pitch "
            "(abstentions do not count)",
            "per_game": per_game,
            "games_with_person_marks": games_with_marks,
            "person_marked": marked,
            "games_with_undecided_frames": undecided_games,
            "met": met,
            "fallback": {
                "rule": "only when both planned evaluation games are labeled and have fewer than "
                f"{M3_MIN_PERSON_MARKED} person-marked pitches together: add {FALLBACK_GAMES[0]}, "
                f"then {FALLBACK_GAMES[1]} if still short (intent_eval_plan_v0.json)",
                "triggered": fallback_triggered,
                "games_added": fallback_added,
                "next_game_to_process": next_fallback,
            },
        },
        "development_games": development,
        "evaluation_games": evaluation,
        "evaluation_pooled": {
            "games": pooled_games,
            "scope": "evaluation games with imported labels only; development games never pooled",
            "lines_in_output": totals["lines"],
            "frames_in_pack": totals["frames_in_pack"],
            "assistant": {
                "estimated": totals["estimated"],
                "unavailable": totals["lines"] - totals["estimated"],
                "abstention_rate": _rate(totals["lines"] - totals["estimated"], totals["lines"]),
                "abstention_rate_denominator": "output lines summed over the pooled games",
                "abstention_reasons": dict(assistant_reasons),
            },
            "frames_decided_by_person": decided,
            "person_marked": marked,
            "person_abstained": decided - marked,
            "person_abstention_reasons": dict(person_reasons),
            "person_abstention_rate": _rate(decided - marked, decided),
            "person_abstention_rate_denominator": "frames the person decided, summed over the "
            "pooled games",
            "availability": dict(availability),
            **error_blocks(pooled),
            "example_cases": example_cases(pooled_frames),
        },
        "limits": [
            "Person-vs-assistant numbers use the same hop-2 matrix on both sides; they measure the "
            "reading, not the physical accuracy of plate_feet.",
            "The person labels the assistant's decision frame; whether that is the right setup "
            "frame is not evaluated.",
            "Condensed games show mostly plate-appearance-ending pitches; the evaluated pitches are "
            "not a random sample of the games.",
            "Catchers in these games rest the glove on the dirt until release; plate_feet.z is the "
            "resting glove height, not a target height.",
            "823407: the pitching rubber is hidden on the low FOX camera, so pan is unmeasured "
            "(0 by rule) and the camera check has 2 catches (unmeasured).",
            "One labeler, one pass; no second person, so person-to-person variation is unmeasured.",
            "The labeling instruction that a resting glove counts as the setup was written after "
            "the assistant outputs were seen (before any label arrived); see the deviations in "
            "docs/INTENT_V0_M3_EVAL.md.",
        ],
        "no_threshold": "no pass/fail threshold was set in advance; the numbers are reported with n",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plan", type=Path, default=RESULTS / "intent_eval_plan_v0.json")
    parser.add_argument("--results", type=Path, default=RESULTS)
    parser.add_argument("--out", type=Path, default=RESULTS / "intent_accuracy_report_v0.json")
    parser.add_argument("--code-commit", default=None, help="commit of the code that built it")
    args = parser.parse_args(argv)
    report = build(_load(args.plan), args.results, args.code_commit)
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=1, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["m3_requirement"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

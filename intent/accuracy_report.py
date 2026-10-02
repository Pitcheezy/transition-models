"""Build the M3 accuracy table (``accuracy_report.json``) from the per-game setup checks.

    python -m intent.accuracy_report

Reads the committed evaluation plan (``docs/results/mlb_p0/intent_eval_plan_v0.json``: which
games are development and which are evaluation) and, per game, the points file (assistant
abstentions), the condensed-game scan (coverage, when there is one), the plate calibration (the
catch-vs-Statcast camera check) and, once the person's labels have been imported with
``python -m intent.human_labels``, ``game_<g>_intent_setup_check_v0.json``.

Writes ``docs/results/mlb_p0/intent_accuracy_report_v0.json``. Development and evaluation games
sit in separate blocks and are never pooled; the pooled block covers evaluation games only. A game
without imported labels is reported as ``awaiting_labels`` with no error numbers.
"""

from __future__ import annotations

import argparse
import json
import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intent.human_labels import _percentile  # noqa: E402

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs/results/mlb_p0"
REPORT_SCHEMA = "intent_accuracy_report_v0"
M3_MIN_PERSON_MARKED = 50
M3_MIN_EVAL_GAMES = 2


def _load(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def _summary(values):
    values = [float(v) for v in values]
    return {
        "n": len(values),
        "median": _percentile(values, 0.5),
        "p90": _percentile(values, 0.9),
    }


def frame_errors(check):
    """Per-frame error lists from one setup check (both marked only)."""
    out = {"mitt_px": [], "output_feet": [], "output_abs_x": [], "output_abs_z": []}
    for f in check.get("per_frame", []):
        if f.get("mitt_px_diff"):
            out["mitt_px"].append(math.hypot(*f["mitt_px_diff"]))
        if f.get("output_feet_diff"):
            dx, dz = f["output_feet_diff"]
            out["output_feet"].append(math.hypot(dx, dz))
            out["output_abs_x"].append(abs(dx))
            out["output_abs_z"].append(abs(dz))
    return out


def person_counts(check):
    a = check["availability"]
    labeled = check["frames_labeled"] - a["person_undecided"]
    marked = a["both_marked"] + a["person_only"]
    return labeled, marked


def game_block(entry, results=RESULTS):
    g = entry["game_pk"]
    points = _load(results / f"game_{g}_intent_points_v0.json")
    frames = points["frames"]
    estimated = sum(1 for f in frames if f["status"] == "estimated")
    block = {
        "game_pk": g,
        "broadcast": entry.get("broadcast"),
        "video": entry.get("video"),
        "pitches_in_output": len(frames),
        "assistant": {
            "estimated": estimated,
            "unavailable": len(frames) - estimated,
            "abstention_rate": (len(frames) - estimated) / len(frames) if frames else None,
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
        block["camera_check_catch_vs_statcast"] = {
            "rms_error_feet": cal.get("rms_error_feet"),
            "rms_basis": cal.get("rms_basis"),
            "pitches_used": cal["end_to_end_check"].get("pitches_used"),
            "human_verified_count": cal.get("human_verified_count"),
        }
    check_path = results / f"game_{g}_intent_setup_check_v0.json"
    if not check_path.is_file():
        block["person"] = {"status": "awaiting_labels"}
        return block, None
    check = _load(check_path)
    labeled, marked = person_counts(check)
    errors = frame_errors(check)
    block["person"] = {
        "status": "labeled",
        "labeler": check.get("labeler"),
        "frames_labeled": check["frames_labeled"],
        "person_marked": marked,
        "person_abstention_rate": (labeled - marked) / labeled if labeled else None,
        "availability": check["availability"],
        "mitt_pixels": _summary(errors["mitt_px"]),
        "output_feet_distance": _summary(errors["output_feet"]),
        "output_feet_abs_x": _summary(errors["output_abs_x"]),
        "output_feet_abs_z": _summary(errors["output_abs_z"]),
    }
    return block, {"check": check, "errors": errors, "labeled": labeled, "marked": marked}


def build(plan, results=RESULTS):
    development, evaluation, pooled = (
        [],
        [],
        {
            "mitt_px": [],
            "output_feet": [],
            "output_abs_x": [],
            "output_abs_z": [],
        },
    )
    labeled_total = marked_total = 0
    eval_games_labeled = 0
    for entry in plan["development_games"]:
        development.append(game_block(entry, results)[0])
    for entry in plan["evaluation_games"]["games"]:
        if not (results / f"game_{entry['game_pk']}_intent_points_v0.json").is_file():
            evaluation.append({"game_pk": entry["game_pk"], "status": "not_processed"})
            continue
        block, extra = game_block(entry, results)
        evaluation.append(block)
        if extra:
            eval_games_labeled += 1
            labeled_total += extra["labeled"]
            marked_total += extra["marked"]
            for k in pooled:
                pooled[k] += extra["errors"][k]
    met = eval_games_labeled >= M3_MIN_EVAL_GAMES and marked_total >= M3_MIN_PERSON_MARKED
    return {
        "schema": REPORT_SCHEMA,
        "plan": "docs/results/mlb_p0/intent_eval_plan_v0.json",
        "definitions": {
            "mitt_pixels": "distance between the assistant's and the person's mitt point on the "
            "same decision frame (both marked), source pixels",
            "output_feet": "assistant's published plate_feet (JSONL) minus the person's mitt "
            "mapped through the person's plate front edge and the game's hop-2 matrix, feet",
            "assistant abstention_rate": "unavailable lines / lines in the game's output",
            "person_abstention_rate": "frames the person marked hidden / not in setup / not "
            "centre field, over the frames the person decided",
            "percentiles": "nearest-rank median and 90th percentile",
        },
        "m3_requirement": {
            "rule": f"at least {M3_MIN_PERSON_MARKED} person-marked pitches over at least "
            f"{M3_MIN_EVAL_GAMES} evaluation games",
            "evaluation_games_labeled": eval_games_labeled,
            "person_marked": marked_total,
            "met": met,
        },
        "development_games": development,
        "evaluation_games": evaluation,
        "evaluation_pooled": {
            "games": eval_games_labeled,
            "frames_decided_by_person": labeled_total,
            "person_marked": marked_total,
            "mitt_pixels": _summary(pooled["mitt_px"]),
            "output_feet_distance": _summary(pooled["output_feet"]),
            "output_feet_abs_x": _summary(pooled["output_abs_x"]),
            "output_feet_abs_z": _summary(pooled["output_abs_z"]),
        },
        "no_threshold": "no pass/fail threshold was set in advance; the numbers are reported with n",
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--plan", type=Path, default=RESULTS / "intent_eval_plan_v0.json")
    parser.add_argument("--out", type=Path, default=RESULTS / "intent_accuracy_report_v0.json")
    args = parser.parse_args(argv)
    report = build(_load(args.plan))
    args.out.write_text(
        json.dumps(report, ensure_ascii=False, indent=1, allow_nan=False) + "\n", encoding="utf-8"
    )
    print(json.dumps(report["m3_requirement"], ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()

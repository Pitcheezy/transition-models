"""Scoreboard-recognition evaluation set built only from human-verified broadcast timing.

The evaluation set lists, for every pitch that a reviewer already timed in
``mlb_broadcast_timing_v1``, the decision frame (playback seconds), the recorded
pre-pitch state from the identity manifest, and whether the reviewer confirmed that
the scoreboard bug was readable in that frame. The recorded state is *label metadata*
(Statcast / MLB feed), never an OCR result; a recognizer is scored against it later.

Scoring conventions (``score_predictions``) keep coverage and error apart so that an
unavailable frame can never inflate a recognition rate:

* ``coverage``     = evaluable pitches / all manifest pitches (occluded and unreviewed
                     pitches stay in the denominator).
* ``attempt_rate`` = attempted / evaluable (``null`` field value = abstention).
* ``accuracy``     = correct / attempted; ``error_rate`` = wrong / evaluable.
* A non-null prediction on an occluded frame is counted as ``occluded_attempts`` and
  is neither correct nor wrong; predictions for pitches outside the set are rejected.
"""

import json
from collections import Counter

from src.data.broadcast_timing import KEYS, validate_annotations

SCHEMA = "mlb_scoreboard_evalset_v1"
LABEL_SOURCE = "manifest_pre_state_recorded_metadata_not_ocr"
LABEL_FIELDS = (
    "balls",
    "strikes",
    "outs",
    "runner_on_1b",
    "runner_on_2b",
    "runner_on_3b",
    "inning",
    "inning_topbot",
    "home_score",
    "away_score",
)
STATUSES = ("visible_checked", "visible_unstated", "occluded")
EVALUABLE = ("visible_checked", "visible_unstated")


def _labels(pre_state):
    return {
        "balls": int(pre_state["balls"]),
        "strikes": int(pre_state["strikes"]),
        "outs": int(pre_state["outs_when_up"]),
        "runner_on_1b": pre_state.get("on_1b") is not None,
        "runner_on_2b": pre_state.get("on_2b") is not None,
        "runner_on_3b": pre_state.get("on_3b") is not None,
        "inning": int(pre_state["inning"]),
        "inning_topbot": str(pre_state["inning_topbot"]),
        "home_score": int(pre_state["home_score"]),
        "away_score": int(pre_state["away_score"]),
    }


def _status(row):
    if row["status"] == "unavailable":
        return "occluded"
    return "visible_checked" if "scoreboard" in row["note"].lower() else "visible_unstated"


def build_evalset(manifest, sources, timing):
    """Derive the evaluation set from validated timing rows; never invent frames."""
    report = validate_annotations(timing, manifest, sources)
    index = {tuple(p[k] for k in KEYS): p for p in manifest["pitches"]}
    entries = []
    for row in timing["annotations"]:
        key = tuple(row[k] for k in KEYS)
        pitch = index[key]
        status = _status(row)
        entries.append(
            {
                **{k: row[k] for k in KEYS},
                "play_id": row["play_id"],
                "scoreboard_status": status,
                "frame_seconds": row["decision_seconds"] if status != "occluded" else None,
                "frame_uncertainty_seconds": (
                    row["uncertainty_seconds"] if status != "occluded" else None
                ),
                "labels": _labels(pitch["pre_state"]),
                "batter": int(pitch["pre_state"]["batter"]),
                "pitcher": int(pitch["pre_state"]["pitcher"]),
                "reviewer_note": row["note"],
            }
        )
    entries.sort(key=lambda e: tuple(e[k] for k in KEYS))
    counts = Counter(e["scoreboard_status"] for e in entries)
    total = len(index)
    return {
        "schema": SCHEMA,
        "game_pk": timing["game_pk"],
        "manifest_sha256": timing["manifest_sha256"],
        "source": timing["source"],
        "timing_schema": timing["schema"],
        "label_source": LABEL_SOURCE,
        "label_fields": list(LABEL_FIELDS),
        "status_rule": {
            "visible_checked": "timed pitch whose reviewer note mentions the scoreboard",
            "visible_unstated": "timed pitch; reviewer note does not state the scoreboard was read",
            "occluded": "reviewer could not establish a pre-delivery frame (timing status unavailable)",
            "unreviewed": "manifest pitch without a timing row; counted in coverage only",
        },
        "coverage": {
            "total_pitches": total,
            "reviewed": len(entries),
            "evaluable": sum(counts[s] for s in EVALUABLE),
            "visible_checked": counts["visible_checked"],
            "visible_unstated": counts["visible_unstated"],
            "occluded": counts["occluded"],
            "unreviewed": total - len(entries),
            "complete_plate_appearances": report["complete_plate_appearances"],
        },
        "entries": entries,
        "note": "Labels are recorded metadata for scoring a recognizer; not OCR output.",
    }


def validate_evalset(document, manifest, sources, timing):
    """Reject an evaluation set that drifted from its manifest or timing annotations."""
    expected = build_evalset(manifest, sources, timing)
    for field in ("schema", "game_pk", "manifest_sha256", "source", "label_source"):
        if document.get(field) != expected[field]:
            raise ValueError(f"Evaluation set {field} does not match the timing annotations")
    if document.get("entries") != expected["entries"]:
        raise ValueError("Evaluation set entries differ from a rebuild")
    if document.get("coverage") != expected["coverage"]:
        raise ValueError("Evaluation set coverage differs from a rebuild")
    return expected["coverage"]


def _is_int(value):
    return type(value) is int


def score_predictions(evalset, predictions):
    """Score recognizer output against the evaluation set with explicit abstention."""
    entries = {tuple(e[k] for k in KEYS): e for e in evalset["entries"]}
    seen = set()
    per_field = {f: {"attempted": 0, "correct": 0} for f in LABEL_FIELDS}
    occluded_attempts = 0
    all_correct = 0
    all_attempted = 0
    for pred in predictions:
        if not isinstance(pred, dict) or set(pred) != {*KEYS, "play_id", "fields"}:
            raise ValueError("Unexpected prediction fields")
        key = tuple(pred[k] for k in KEYS)
        if key not in entries or key in seen:
            raise ValueError("Unknown or duplicate pitch in predictions")
        seen.add(key)
        entry = entries[key]
        if pred["play_id"] != entry["play_id"]:
            raise ValueError("play_id does not match pitch identity")
        fields = pred["fields"]
        if not isinstance(fields, dict) or set(fields) != set(LABEL_FIELDS):
            raise ValueError("Predictions must cover every label field (null = abstain)")
        if entry["scoreboard_status"] == "occluded":
            if any(v is not None for v in fields.values()):
                occluded_attempts += 1
            continue
        labels = entry["labels"]
        row_attempted = all(v is not None for v in fields.values())
        row_correct = row_attempted
        for name in LABEL_FIELDS:
            value = fields[name]
            if value is None:
                row_correct = False
                continue
            truth = labels[name]
            if type(truth) is bool:
                ok = type(value) is bool and value == truth
            elif _is_int(truth):
                ok = _is_int(value) and value == truth
            else:
                ok = isinstance(value, str) and value == truth
            per_field[name]["attempted"] += 1
            per_field[name]["correct"] += int(ok)
            row_correct = row_correct and ok
        all_attempted += int(row_attempted)
        all_correct += int(row_correct)
    coverage = evalset["coverage"]
    evaluable = coverage["evaluable"]

    def rates(attempted, correct):
        wrong = attempted - correct
        return {
            "evaluable": evaluable,
            "attempted": attempted,
            "correct": correct,
            "wrong": wrong,
            "attempt_rate": attempted / evaluable if evaluable else None,
            "accuracy": correct / attempted if attempted else None,
            "error_rate": wrong / evaluable if evaluable else None,
            "abstain_rate": (evaluable - attempted) / evaluable if evaluable else None,
        }

    return {
        "schema": "mlb_scoreboard_evalset_score_v1",
        "coverage": coverage["evaluable"] / coverage["total_pitches"],
        "coverage_counts": coverage,
        "predictions_received": len(predictions),
        "occluded_attempts": occluded_attempts,
        "per_field": {f: rates(v["attempted"], v["correct"]) for f, v in per_field.items()},
        "all_fields": rates(all_attempted, all_correct),
        "note": "coverage and error_rate keep occluded/unreviewed pitches in the denominator",
    }


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

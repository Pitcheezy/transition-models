"""Scoreboard-recognition evaluation set from verified timing plus explicit scoreboard reviews.

Inputs
------
* ``mlb_broadcast_timing_v1`` — human-verified decision frames (playback seconds) per pitch.
* ``mlb_scoreboard_review_v1`` — for a timed pitch, what a human reviewer *read on the
  scoreboard bug* at that decision frame: a readability grade and one observed value per
  label field (``null`` = that field was not legible in the frame). Reviews are typed from
  the video; they are never OCR output and never copied from the manifest.
* identity manifest — the recorded pre-pitch state (Statcast / MLB feed) = label metadata.

A field is **confirmed** when the reviewer's observed value equals the recorded label. Only
confirmed fields are evaluable. Timed pitches without a review row, frames with no confirmed
field and occluded frames are listed apart under ``excluded`` and are never scored as right
or wrong. A review whose reading differs from the label is a ``label_conflict``: that field is
not evaluable and the conflict is reported, not silently resolved either way.

Denominators (the same wording is asserted in the docs and emitted in the score output):

    coverage = evaluable / total_pitches
    attempt_rate = attempted / evaluable
    correct_rate = correct / evaluable
    error_rate = wrong / evaluable
    abstain_rate = abstained / evaluable
    accuracy = correct / attempted

``evaluable`` is per field (pitches whose field is confirmed); ``all_fields`` uses pitches
with every field confirmed. ``abstained = evaluable - attempted``, so
``correct_rate + error_rate + abstain_rate == 1`` for every field. Predictions on excluded
pitches or on unconfirmed fields are counted under ``non_evaluable_attempts`` only.
"""

import json
from collections import Counter

from src.data.broadcast_timing import KEYS, validate_annotations

SCHEMA = "mlb_scoreboard_evalset_v2"
SCORE_SCHEMA = "mlb_scoreboard_evalset_score_v2"
REVIEW_SCHEMA = "mlb_scoreboard_review_v1"
LABEL_SOURCE = "manifest_pre_state_recorded_metadata_not_ocr"
OBSERVED_SOURCE = "human_reading_of_scoreboard_bug_at_decision_frame_not_ocr"
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
READABILITY = ("readable", "partial", "unreadable")
FIELD_STATUS = ("confirmed", "mismatch", "unreadable")
EXCLUSION_REASONS = ("occluded", "scoreboard_unreviewed", "no_confirmed_field")
DENOMINATORS = {
    "coverage": ("evaluable", "total_pitches"),
    "attempt_rate": ("attempted", "evaluable"),
    "correct_rate": ("correct", "evaluable"),
    "error_rate": ("wrong", "evaluable"),
    "abstain_rate": ("abstained", "evaluable"),
    "accuracy": ("correct", "attempted"),
}
REVIEW_ROW_KEYS = {
    *KEYS,
    "play_id",
    "frame_seconds",
    "readability",
    "observed",
    "reviewer",
    "reviewed_at",
    "note",
}
REVIEW_ROW_OPTIONAL = {"bug_text"}


def denominator_lines():
    """The metric definitions as exact strings shared by code, docs and output."""
    return [f"{name} = {num} / {den}" for name, (num, den) in DENOMINATORS.items()]


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


def _same_type_value(value, truth):
    """Strict typed equality: bool never passes as int, "0" never passes as 0."""
    if type(truth) is bool:
        return type(value) is bool and value == truth
    if type(truth) is int:
        return type(value) is int and value == truth
    return isinstance(value, str) and value == truth


def _well_typed(value, truth):
    if type(truth) is bool:
        return type(value) is bool
    if type(truth) is int:
        return type(value) is int
    return isinstance(value, str)


def validate_review(review, manifest, timing):
    """Check a scoreboard review against the timing rows it claims to describe."""
    if not isinstance(review, dict) or review.get("schema") != REVIEW_SCHEMA:
        raise ValueError(f"Scoreboard review schema must be {REVIEW_SCHEMA}")
    for field in ("game_pk", "manifest_sha256"):
        if review.get(field) != timing.get(field):
            raise ValueError(f"Scoreboard review {field} does not match the timing annotations")
    if review.get("observed_source") != OBSERVED_SOURCE:
        raise ValueError("Scoreboard review must declare observed values as human readings")
    rows = {tuple(r[k] for k in KEYS): r for r in timing["annotations"]}
    labels = {tuple(p[k] for k in KEYS): _labels(p["pre_state"]) for p in manifest["pitches"]}
    reviews = {}
    for row in review.get("reviews", []):
        if not isinstance(row, dict) or not REVIEW_ROW_KEYS <= set(row) <= (
            REVIEW_ROW_KEYS | REVIEW_ROW_OPTIONAL
        ):
            raise ValueError("Unexpected scoreboard review row fields")
        key = tuple(row[k] for k in KEYS)
        if key in reviews:
            raise ValueError(f"Duplicate scoreboard review for pitch {key}")
        timed = rows.get(key)
        if timed is None or timed["status"] != "annotated":
            raise ValueError(
                f"Scoreboard review for a pitch without a verified decision frame {key}"
            )
        if row["play_id"] != timed["play_id"]:
            raise ValueError(f"Scoreboard review play_id does not match the timing row {key}")
        if row["frame_seconds"] != timed["decision_seconds"]:
            raise ValueError(f"Scoreboard review frame must be the timing decision frame {key}")
        if row["readability"] not in READABILITY:
            raise ValueError(f"Unknown readability for pitch {key}")
        observed = row["observed"]
        if not isinstance(observed, dict) or set(observed) != set(LABEL_FIELDS):
            raise ValueError(f"Scoreboard review must give every label field for pitch {key}")
        truth = labels[key]
        for name in LABEL_FIELDS:
            value = observed[name]
            if value is not None and not _well_typed(value, truth[name]):
                raise ValueError(f"Observed {name} has the wrong type for pitch {key}")
        legible = sum(observed[name] is not None for name in LABEL_FIELDS)
        expected = {"readable": len(LABEL_FIELDS), "unreadable": 0}
        if row["readability"] in expected and legible != expected[row["readability"]]:
            raise ValueError(f"readability disagrees with the observed fields for pitch {key}")
        if row["readability"] == "partial" and legible in (0, len(LABEL_FIELDS)):
            raise ValueError(f"partial readability needs some but not all fields for pitch {key}")
        if not isinstance(row["reviewer"], str) or not row["reviewer"]:
            raise ValueError(f"Scoreboard review needs a reviewer for pitch {key}")
        reviews[key] = row
    return reviews


def _field_status(observed, labels):
    status = {}
    for name in LABEL_FIELDS:
        value = observed[name]
        if value is None:
            status[name] = "unreadable"
        elif _same_type_value(value, labels[name]):
            status[name] = "confirmed"
        else:
            status[name] = "mismatch"
    return status


def build_evalset(manifest, sources, timing, review):
    """Derive the evaluation set from validated timing rows and explicit scoreboard reviews."""
    report = validate_annotations(timing, manifest, sources)
    reviews = validate_review(review, manifest, timing)
    index = {tuple(p[k] for k in KEYS): p for p in manifest["pitches"]}
    entries, excluded, conflicts = [], [], []
    for row in timing["annotations"]:
        key = tuple(row[k] for k in KEYS)
        pitch = index[key]
        identity = {**{k: row[k] for k in KEYS}, "play_id": row["play_id"]}
        if row["status"] == "unavailable":
            excluded.append({**identity, "reason": "occluded", "readability": None})
            continue
        reviewed = reviews.get(key)
        if reviewed is None:
            excluded.append({**identity, "reason": "scoreboard_unreviewed", "readability": None})
            continue
        labels = _labels(pitch["pre_state"])
        status = _field_status(reviewed["observed"], labels)
        for name, state in status.items():
            if state == "mismatch":
                conflicts.append(
                    {
                        **identity,
                        "field": name,
                        "label": labels[name],
                        "observed": reviewed["observed"][name],
                    }
                )
        confirmed = [name for name in LABEL_FIELDS if status[name] == "confirmed"]
        if not confirmed:
            excluded.append(
                {**identity, "reason": "no_confirmed_field", "readability": reviewed["readability"]}
            )
            continue
        entries.append(
            {
                **identity,
                "frame_seconds": row["decision_seconds"],
                "frame_uncertainty_seconds": row["uncertainty_seconds"],
                "readability": reviewed["readability"],
                "field_status": status,
                "evaluable_fields": confirmed,
                "labels": labels,
                "batter": int(pitch["pre_state"]["batter"]),
                "pitcher": int(pitch["pre_state"]["pitcher"]),
                "reviewer": reviewed["reviewer"],
                "reviewed_at": reviewed["reviewed_at"],
                "review_note": reviewed["note"],
                "timing_note": row["note"],
            }
        )
    sort_key = lambda e: tuple(e[k] for k in KEYS)  # noqa: E731
    entries.sort(key=sort_key)
    excluded.sort(key=sort_key)
    conflicts.sort(key=lambda c: (*sort_key(c), c["field"]))
    total = len(index)
    timing_status = Counter(r["status"] for r in timing["annotations"])
    reasons = Counter(e["reason"] for e in excluded)
    per_field = {
        name: sum(e["field_status"][name] == "confirmed" for e in entries) for name in LABEL_FIELDS
    }
    return {
        "schema": SCHEMA,
        "game_pk": timing["game_pk"],
        "manifest_sha256": timing["manifest_sha256"],
        "source": timing["source"],
        "timing_schema": timing["schema"],
        "review_schema": REVIEW_SCHEMA,
        "label_source": LABEL_SOURCE,
        "observed_source": OBSERVED_SOURCE,
        "label_fields": list(LABEL_FIELDS),
        "denominators": denominator_lines(),
        "status_rule": {
            "entry": "timed pitch with a scoreboard review and at least one confirmed field",
            "confirmed": "reviewer's on-screen reading equals the recorded label",
            "mismatch": "reviewer's reading differs from the label; reported as label_conflict, not evaluable",
            "unreadable": "reviewer could not read that field in the decision frame; not evaluable",
            "occluded": "no verified pre-delivery frame (timing status unavailable)",
            "scoreboard_unreviewed": "timed pitch without a field-level scoreboard review",
            "no_confirmed_field": "reviewed, but no field was both readable and equal to the label",
            "timing_unreviewed": "manifest pitch without a timing row; counted in total_pitches only",
        },
        "coverage": {
            "total_pitches": total,
            "timing_rows": len(timing["annotations"]),
            "timing_annotated": timing_status["annotated"],
            "timing_unavailable": timing_status["unavailable"],
            "timing_unreviewed": total - len(timing["annotations"]),
            "scoreboard_reviewed": len(reviews),
            "evaluable_pitches": len(entries),
            "fully_evaluable_pitches": sum(
                len(e["evaluable_fields"]) == len(LABEL_FIELDS) for e in entries
            ),
            "per_field_evaluable": per_field,
            "excluded": {reason: reasons[reason] for reason in EXCLUSION_REASONS},
            "label_conflicts": len(conflicts),
            "complete_plate_appearances": report["complete_plate_appearances"],
        },
        "entries": entries,
        "excluded": excluded,
        "label_conflicts": conflicts,
        "note": (
            "labels are recorded metadata; field_status comes from a human reading of the bug; "
            "neither is OCR output"
        ),
    }


def validate_evalset(document, manifest, sources, timing, review):
    """Reject an evaluation set that drifted from its manifest, timing or review inputs."""
    expected = build_evalset(manifest, sources, timing, review)
    for field in (
        "schema",
        "game_pk",
        "manifest_sha256",
        "source",
        "label_source",
        "observed_source",
    ):
        if document.get(field) != expected[field]:
            raise ValueError(f"Evaluation set {field} does not match the inputs")
    for field in ("entries", "excluded", "label_conflicts", "coverage", "denominators"):
        if document.get(field) != expected[field]:
            raise ValueError(f"Evaluation set {field} differs from a rebuild")
    return expected["coverage"]


def _rates(evaluable, attempted, correct, total_pitches):
    wrong = attempted - correct
    abstained = evaluable - attempted
    counts = {
        "total_pitches": total_pitches,
        "evaluable": evaluable,
        "attempted": attempted,
        "correct": correct,
        "wrong": wrong,
        "abstained": abstained,
    }
    rates = {}
    for name, (num, den) in DENOMINATORS.items():
        rates[name] = counts[num] / counts[den] if counts[den] else None
    return {**counts, **rates}


def score_predictions(evalset, predictions):
    """Score recognizer output; abstention, excluded pitches and unconfirmed fields stay apart."""
    entries = {tuple(e[k] for k in KEYS): e for e in evalset["entries"]}
    excluded = {tuple(e[k] for k in KEYS): e for e in evalset["excluded"]}
    seen = set()
    per_field = {f: {"attempted": 0, "correct": 0} for f in LABEL_FIELDS}
    non_evaluable = {
        "excluded": {reason: 0 for reason in EXCLUSION_REASONS},
        "unconfirmed_field": 0,
    }
    all_attempted = all_correct = 0
    for pred in predictions:
        if not isinstance(pred, dict) or set(pred) != {*KEYS, "play_id", "fields"}:
            raise ValueError("Unexpected prediction fields")
        key = tuple(pred[k] for k in KEYS)
        target = entries.get(key) or excluded.get(key)
        if target is None or key in seen:
            raise ValueError("Unknown or duplicate pitch in predictions")
        seen.add(key)
        if pred["play_id"] != target["play_id"]:
            raise ValueError("play_id does not match pitch identity")
        fields = pred["fields"]
        if not isinstance(fields, dict) or set(fields) != set(LABEL_FIELDS):
            raise ValueError("Predictions must cover every label field (null = abstain)")
        if key in excluded:
            if any(v is not None for v in fields.values()):
                non_evaluable["excluded"][target["reason"]] += 1
            continue
        labels, status = target["labels"], target["field_status"]
        fully = len(target["evaluable_fields"]) == len(LABEL_FIELDS)
        row_attempted = fully and all(v is not None for v in fields.values())
        row_correct = row_attempted
        for name in LABEL_FIELDS:
            value = fields[name]
            if status[name] != "confirmed":
                if value is not None:
                    non_evaluable["unconfirmed_field"] += 1
                continue
            if value is None:
                continue
            ok = _same_type_value(value, labels[name])
            per_field[name]["attempted"] += 1
            per_field[name]["correct"] += int(ok)
            row_correct = row_correct and ok
        all_attempted += int(row_attempted)
        all_correct += int(row_correct)
    coverage = evalset["coverage"]
    total = coverage["total_pitches"]
    return {
        "schema": SCORE_SCHEMA,
        "denominators": denominator_lines(),
        "coverage_counts": coverage,
        "predictions_received": len(predictions),
        "non_evaluable_attempts": non_evaluable,
        "per_field": {
            f: _rates(coverage["per_field_evaluable"][f], v["attempted"], v["correct"], total)
            for f, v in per_field.items()
        },
        "all_fields": _rates(
            coverage["fully_evaluable_pitches"], all_attempted, all_correct, total
        ),
        "note": (
            "evaluable is per field (confirmed by a human reading); excluded pitches and "
            "unconfirmed fields are never counted as correct or wrong"
        ),
    }


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

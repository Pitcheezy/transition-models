"""The scoreboard evaluation set never invents frames, readings or denominators."""

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

import src.data.scoreboard_evalset as module
from src.data.broadcast_timing import timing_context
from src.data.scoreboard_evalset import (
    DENOMINATORS,
    LABEL_FIELDS,
    OBSERVED_SOURCE,
    REVIEW_SCHEMA,
    build_evalset,
    denominator_lines,
    score_predictions,
    validate_evalset,
    validate_review,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs" / "results" / "mlb_p0"
SCRIPT = ROOT / "scripts" / "64_build_scoreboard_evalset.py"


def pitch(n, **state):
    base = {
        "game_date": "2024-09-30",
        "pitcher": 1,
        "batter": 2,
        "balls": 0,
        "strikes": n - 1 if n <= 3 else 0,
        "outs_when_up": 0,
        "inning": 1,
        "inning_topbot": "Top",
        "on_1b": None,
        "on_2b": None,
        "on_3b": None,
        "stand": "R",
        "p_throws": "R",
        "home_score": 0,
        "away_score": 0,
    }
    base.update(state)
    return {
        "game_pk": 7,
        "at_bat_number": 1,
        "pitch_number": n,
        "identity_status": "verified",
        "pre_state": base,
        "video": {"play_id": f"pitch-{n}"},
    }


def timing_row(n, seconds, status="annotated", note="checked"):
    return {
        "game_pk": 7,
        "at_bat_number": 1,
        "pitch_number": n,
        "play_id": f"pitch-{n}",
        "status": status,
        "decision_seconds": seconds if status == "annotated" else None,
        "release_seconds": seconds + 2.0 if status == "annotated" else None,
        "uncertainty_seconds": 0.25 if status == "annotated" else None,
        "note": note,
    }


def observed(**values):
    base = {
        "balls": 0,
        "strikes": 0,
        "outs": 0,
        "runner_on_1b": False,
        "runner_on_2b": False,
        "runner_on_3b": False,
        "inning": 1,
        "inning_topbot": "Top",
        "home_score": 0,
        "away_score": 0,
    }
    base.update(values)
    return base


def review_row(n, seconds, readability="readable", **values):
    return {
        "game_pk": 7,
        "at_bat_number": 1,
        "pitch_number": n,
        "play_id": f"pitch-{n}",
        "frame_seconds": seconds,
        "readability": readability,
        "observed": observed(**values),
        "reviewer": "test reviewer",
        "reviewed_at": "2026-09-22",
        "note": "read from the bug",
    }


@pytest.fixture
def sample():
    """6 pitches: 1 readable, 2 partial+mismatch, 3 occluded, 4 timed-unreviewed,
    5 no timing row, 6 unreadable."""
    manifest = {
        "schema": "mlb_video_manifest_v1",
        "game_pk": 7,
        "pitches": [pitch(1), pitch(2, on_1b=55), pitch(3), pitch(4), pitch(5), pitch(6)],
    }
    sources = {
        "game_pk": 7,
        "sources": {
            "full_game": {
                "page_url": "https://www.mlb.com/video/x",
                "observed_mp4_urls": ["https://mlb-cuts-diamond.mlb.com/x.mp4"],
                "inspection": {
                    "url": "https://mlb-cuts-diamond.mlb.com/x.mp4",
                    "probe": {"format": {"duration": "100.0"}},
                },
            }
        },
    }
    context = timing_context(manifest, sources)
    timing = {
        **context,
        "annotator": "test",
        "annotations": [
            timing_row(1, 10.0),
            timing_row(2, 20.0),
            timing_row(3, 0.0, status="unavailable", note="graphic hides the mound"),
            timing_row(4, 40.0),
            timing_row(6, 60.0),
        ],
    }
    review = {
        "schema": REVIEW_SCHEMA,
        "game_pk": 7,
        "manifest_sha256": context["manifest_sha256"],
        "observed_source": OBSERVED_SOURCE,
        "reviews": [
            review_row(1, 10.0),
            # balls not legible, outs read as 2 although the label says 0, runner read correctly
            review_row(2, 20.0, "partial", balls=None, outs=2, strikes=1, runner_on_1b=True),
            review_row(6, 60.0, "unreadable", **{name: None for name in LABEL_FIELDS}),
        ],
    }
    return manifest, sources, timing, review


def test_build_splits_confirmed_unconfirmed_and_excluded(sample):
    doc = build_evalset(*sample)
    by = {e["pitch_number"]: e for e in doc["entries"]}
    assert sorted(by) == [1, 2]
    assert by[1]["readability"] == "readable"
    assert set(by[1]["field_status"].values()) == {"confirmed"}
    assert by[1]["evaluable_fields"] == list(LABEL_FIELDS)
    assert by[1]["frame_seconds"] == 10.0 and by[1]["frame_uncertainty_seconds"] == 0.25
    assert by[2]["readability"] == "partial"
    assert by[2]["field_status"]["balls"] == "unreadable"
    assert by[2]["field_status"]["outs"] == "mismatch"
    assert by[2]["field_status"]["strikes"] == "confirmed"
    assert by[2]["field_status"]["runner_on_1b"] == "confirmed"
    assert "balls" not in by[2]["evaluable_fields"] and "outs" not in by[2]["evaluable_fields"]
    assert doc["label_conflicts"] == [
        {
            "game_pk": 7,
            "at_bat_number": 1,
            "pitch_number": 2,
            "play_id": "pitch-2",
            "field": "outs",
            "label": 0,
            "observed": 2,
        }
    ]
    excluded = {e["pitch_number"]: e for e in doc["excluded"]}
    assert excluded[3]["reason"] == "occluded" and excluded[3]["readability"] is None
    assert excluded[4]["reason"] == "scoreboard_unreviewed"
    assert (
        excluded[6]["reason"] == "no_confirmed_field" and excluded[6]["readability"] == "unreadable"
    )
    assert 5 not in excluded and 5 not in by
    assert doc["coverage"] == {
        "total_pitches": 6,
        "timing_rows": 5,
        "timing_annotated": 4,
        "timing_unavailable": 1,
        "timing_unreviewed": 1,
        "scoreboard_reviewed": 3,
        "evaluable_pitches": 2,
        "fully_evaluable_pitches": 1,
        "per_field_evaluable": {
            **{name: 2 for name in LABEL_FIELDS},
            "balls": 1,
            "outs": 1,
        },
        "excluded": {"occluded": 1, "scoreboard_unreviewed": 1, "no_confirmed_field": 1},
        "label_conflicts": 1,
        "complete_plate_appearances": [],
    }
    assert doc["label_source"].endswith("not_ocr") and doc["observed_source"].endswith("not_ocr")
    assert doc["denominators"] == denominator_lines()


def test_review_validation_rejects_wrong_frames_types_and_grades(sample):
    manifest, sources, timing, review = sample

    def bad(mutate):
        broken = deepcopy(review)
        mutate(broken)
        with pytest.raises(ValueError):
            validate_review(broken, manifest, timing)

    bad(lambda r: r["reviews"][0].update(frame_seconds=10.5))  # not the decision frame
    bad(lambda r: r["reviews"][0].update(play_id="other"))
    bad(lambda r: r["reviews"][0].__setitem__("pitch_number", 3))  # occluded pitch
    bad(lambda r: r["reviews"][0].__setitem__("pitch_number", 5))  # no timing row
    bad(lambda r: r["reviews"].append(deepcopy(r["reviews"][0])))  # duplicate
    bad(lambda r: r["reviews"][0]["observed"].update(balls="0"))  # numeric string
    bad(lambda r: r["reviews"][0]["observed"].update(runner_on_1b=0))  # int for bool
    bad(lambda r: r["reviews"][0]["observed"].update(balls=None))  # readable but a null
    bad(lambda r: r["reviews"][0]["observed"].pop("outs"))
    bad(lambda r: r["reviews"][0].update(readability="clear"))
    bad(lambda r: r["reviews"][1].update(readability="readable"))  # partial has nulls
    bad(lambda r: r["reviews"][2].update(readability="partial"))  # all null
    bad(lambda r: r["reviews"][0].update(reviewer=""))
    bad(lambda r: r["reviews"][0].update(extra=1))
    bad(lambda r: r.update(observed_source="ocr"))
    bad(lambda r: r.update(manifest_sha256="0" * 64))
    assert len(validate_review(review, manifest, timing)) == 3


def test_validate_rejects_drift(sample):
    doc = build_evalset(*sample)
    assert validate_evalset(doc, *sample)["evaluable_pitches"] == 2
    for path, value, message in (
        (("entries", 0, "labels", "balls"), 3, "entries differ"),
        (("excluded", 0, "reason"), "scoreboard_unreviewed", "excluded differ"),
        (("coverage", "label_conflicts"), 0, "coverage differ"),
        (("label_conflicts",), [], "label_conflicts differ"),
    ):
        tampered = deepcopy(doc)
        node = tampered
        for step in path[:-1]:
            node = node[step]
        node[path[-1]] = value
        with pytest.raises(ValueError, match=message):
            validate_evalset(tampered, *sample)


def prediction(entry, **overrides):
    fields = dict(entry["labels"])
    fields.update(overrides)
    return {
        "game_pk": entry["game_pk"],
        "at_bat_number": entry["at_bat_number"],
        "pitch_number": entry["pitch_number"],
        "play_id": entry["play_id"],
        "fields": fields,
    }


def abstain(entry):
    """Null on every field; works for entries and excluded pitches alike."""
    return guess(entry)


def guess(entry, **overrides):
    """A prediction for a pitch without labels (excluded): null everywhere unless overridden."""
    fields = dict.fromkeys(LABEL_FIELDS)
    fields.update(overrides)
    return {
        "game_pk": entry["game_pk"],
        "at_bat_number": entry["at_bat_number"],
        "pitch_number": entry["pitch_number"],
        "play_id": entry["play_id"],
        "fields": fields,
    }


def test_score_negatives_abstentions_and_unconfirmed_stay_apart(sample):
    doc = build_evalset(*sample)
    e1, e2 = doc["entries"]
    x3, x4, x6 = doc["excluded"]
    preds = [
        prediction(e1, strikes=1),  # every field attempted, strikes wrong (label 0)
        # balls (unreadable) and outs (mismatch) are guessed: not evaluable; strikes correct,
        # runner_on_1b wrong, inning abstained
        prediction(e2, balls=3, outs=0, runner_on_1b=False, inning=None),
        guess(x3, balls=0),  # attempt on an occluded frame
        abstain(x4),  # abstain on an unreviewed frame: nothing to count
        guess(x6, outs=0),  # attempt on an unreadable frame
    ]
    score = score_predictions(doc, preds)
    assert score["denominators"] == denominator_lines()
    assert score["non_evaluable_attempts"] == {
        "excluded": {"occluded": 1, "scoreboard_unreviewed": 0, "no_confirmed_field": 1},
        "unconfirmed_field": 2,
    }
    strikes = score["per_field"]["strikes"]
    assert strikes == {
        "total_pitches": 6,
        "evaluable": 2,
        "attempted": 2,
        "correct": 1,
        "wrong": 1,
        "abstained": 0,
        "coverage": 2 / 6,
        "attempt_rate": 1.0,
        "correct_rate": 0.5,
        "error_rate": 0.5,
        "abstain_rate": 0.0,
        "accuracy": 0.5,
    }
    balls = score["per_field"]["balls"]
    assert balls["evaluable"] == 1 and balls["attempted"] == 1 and balls["correct"] == 1
    assert balls["coverage"] == 1 / 6 and balls["error_rate"] == 0.0
    runner = score["per_field"]["runner_on_1b"]
    assert runner["attempted"] == 2 and runner["wrong"] == 1 and runner["error_rate"] == 0.5
    inning = score["per_field"]["inning"]
    assert inning["attempted"] == 1 and inning["abstained"] == 1 and inning["abstain_rate"] == 0.5
    assert inning["accuracy"] == 1.0 and inning["correct_rate"] == 0.5
    for name, rates in score["per_field"].items():
        assert rates["correct_rate"] + rates["error_rate"] + rates["abstain_rate"] == pytest.approx(
            1
        ), name
        assert rates["evaluable"] == doc["coverage"]["per_field_evaluable"][name]
    rows = score["all_fields"]
    assert rows["evaluable"] == 1 and rows["attempted"] == 1 and rows["correct"] == 0
    assert rows["error_rate"] == 1.0 and rows["accuracy"] == 0.0 and rows["coverage"] == 1 / 6
    # abstaining everywhere: nothing is wrong, accuracy is undefined, not 0 and not 1
    quiet = score_predictions(doc, [abstain(e1), abstain(e2)])
    assert quiet["per_field"]["balls"]["accuracy"] is None
    assert quiet["per_field"]["balls"]["abstain_rate"] == 1.0
    assert quiet["per_field"]["balls"]["error_rate"] == 0.0
    assert (
        quiet["all_fields"]["abstained"] == 1
        and quiet["non_evaluable_attempts"]["unconfirmed_field"] == 0
    )


def test_score_rejects_identity_and_field_errors(sample):
    doc = build_evalset(*sample)
    e1 = doc["entries"][0]
    with pytest.raises(ValueError, match="play_id"):
        score_predictions(doc, [{**prediction(e1), "play_id": "other"}])
    with pytest.raises(ValueError, match="Unknown or duplicate"):
        score_predictions(doc, [prediction(e1), prediction(e1)])
    with pytest.raises(ValueError, match="Unknown or duplicate"):
        score_predictions(doc, [{**prediction(e1), "pitch_number": 5}])  # no timing row
    bad = prediction(e1)
    del bad["fields"]["outs"]
    with pytest.raises(ValueError, match="every label field"):
        score_predictions(doc, [bad])
    with pytest.raises(ValueError, match="Unexpected prediction"):
        score_predictions(doc, [{**prediction(e1), "extra": 1}])
    typed = score_predictions(doc, [prediction(e1, balls="0", runner_on_1b=0)])
    assert typed["per_field"]["balls"]["wrong"] == 1
    assert typed["per_field"]["runner_on_1b"]["wrong"] == 1


def test_denominators_are_stated_identically_in_code_and_docs():
    lines = denominator_lines()
    assert lines == [
        "coverage = evaluable / total_pitches",
        "attempt_rate = attempted / evaluable",
        "correct_rate = correct / evaluable",
        "error_rate = wrong / evaluable",
        "abstain_rate = abstained / evaluable",
        "accuracy = correct / attempted",
    ]
    assert set(DENOMINATORS) == {line.split(" = ")[0] for line in lines}
    doc = (ROOT / "docs" / "MLB_BROADCAST_TIMING.md").read_text(encoding="utf-8")
    for line in lines:
        assert line in module.__doc__, line
        assert line in doc, line


def run(*args):
    return subprocess.run(
        [sys.executable, str(SCRIPT), *args],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )


def test_real_game_evalset_matches_inputs_and_cli_round_trips(tmp_path):
    names = (
        "game_747139_manifest.json",
        "game_747139_sources.json",
        "game_747139_timing.json",
        "game_747139_scoreboard_review.json",
    )
    manifest, sources, timing, review = (
        json.loads((RESULTS / n).read_text(encoding="utf-8-sig")) for n in names
    )
    doc = build_evalset(manifest, sources, timing, review)
    coverage = doc["coverage"]
    assert coverage["total_pitches"] == 322
    assert coverage["timing_rows"] == len(timing["annotations"])
    assert coverage["timing_unavailable"] == coverage["excluded"]["occluded"]
    assert coverage["scoreboard_reviewed"] == len(review["reviews"])
    assert (
        coverage["evaluable_pitches"] + sum(coverage["excluded"].values())
        == coverage["timing_rows"]
    )
    assert coverage["label_conflicts"] == 0 and doc["label_conflicts"] == []
    assert all(e["reviewer"].startswith("Claude Code") for e in doc["entries"])
    stored = json.loads(
        (RESULTS / "game_747139_scoreboard_evalset.json").read_text(encoding="utf-8-sig")
    )
    assert validate_evalset(stored, manifest, sources, timing, review) == coverage
    assert run("review-check").returncode == 0
    out = tmp_path / "evalset.json"
    built = run("build", "--output", str(out))
    assert built.returncode == 0, built.stderr
    checked = run("check", "--evalset", str(out))
    assert checked.returncode == 0, checked.stderr
    assert json.loads(checked.stdout)["total_pitches"] == 322
    preds = tmp_path / "preds.json"
    preds.write_text(json.dumps([abstain(e) for e in doc["entries"]]), encoding="utf-8")
    scored = run("score", "--evalset", str(out), "--predictions", str(preds))
    assert scored.returncode == 0, scored.stderr
    result = json.loads(scored.stdout)
    assert result["all_fields"]["abstain_rate"] == 1.0 and result["all_fields"]["accuracy"] is None

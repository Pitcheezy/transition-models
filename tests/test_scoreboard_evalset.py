"""The scoreboard evaluation set never invents frames and never hides occlusion."""

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from src.data.broadcast_timing import timing_context
from src.data.scoreboard_evalset import (
    EVALUABLE,
    LABEL_FIELDS,
    build_evalset,
    score_predictions,
    validate_evalset,
)

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs" / "results" / "mlb_p0"


def pitch(n, **state):
    base = {
        "game_date": "2024-09-30",
        "pitcher": 1,
        "batter": 2,
        "balls": 0,
        "strikes": n - 1,
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


@pytest.fixture
def sample():
    manifest = {
        "schema": "mlb_video_manifest_v1",
        "game_pk": 7,
        "pitches": [pitch(1), pitch(2, on_1b=55), pitch(3), pitch(4)],
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
            {
                "game_pk": 7,
                "at_bat_number": 1,
                "pitch_number": 1,
                "play_id": "pitch-1",
                "status": "annotated",
                "decision_seconds": 10.0,
                "release_seconds": 12.0,
                "uncertainty_seconds": 0.25,
                "note": "Scoreboard bug 0-0 visibly checked.",
            },
            {
                "game_pk": 7,
                "at_bat_number": 1,
                "pitch_number": 2,
                "play_id": "pitch-2",
                "status": "annotated",
                "decision_seconds": 20.0,
                "release_seconds": 22.0,
                "uncertainty_seconds": 0.25,
                "note": "Decision frame 20s checked.",
            },
            {
                "game_pk": 7,
                "at_bat_number": 1,
                "pitch_number": 3,
                "play_id": "pitch-3",
                "status": "unavailable",
                "decision_seconds": None,
                "release_seconds": None,
                "uncertainty_seconds": None,
                "note": "Graphic hides scoreboard and mound.",
            },
        ],
    }
    return manifest, sources, timing


def test_build_marks_status_labels_and_coverage(sample):
    doc = build_evalset(*sample)
    by = {e["pitch_number"]: e for e in doc["entries"]}
    assert by[1]["scoreboard_status"] == "visible_checked"
    assert by[2]["scoreboard_status"] == "visible_unstated"
    assert by[3]["scoreboard_status"] == "occluded"
    assert by[3]["frame_seconds"] is None and by[3]["frame_uncertainty_seconds"] is None
    assert by[1]["frame_seconds"] == 10.0
    assert by[2]["labels"]["runner_on_1b"] is True and by[2]["labels"]["strikes"] == 1
    assert doc["coverage"] == {
        "total_pitches": 4,
        "reviewed": 3,
        "evaluable": 2,
        "visible_checked": 1,
        "visible_unstated": 1,
        "occluded": 1,
        "unreviewed": 1,
        "complete_plate_appearances": [],
    }
    assert doc["label_source"].endswith("not_ocr")
    assert set(by[1]["labels"]) == set(LABEL_FIELDS)


def test_validate_rejects_drifted_entries(sample):
    doc = build_evalset(*sample)
    assert validate_evalset(doc, *sample)["evaluable"] == 2
    tampered = deepcopy(doc)
    tampered["entries"][0]["labels"]["balls"] = 3
    with pytest.raises(ValueError, match="entries differ"):
        validate_evalset(tampered, *sample)
    tampered = deepcopy(doc)
    tampered["coverage"]["occluded"] = 0
    with pytest.raises(ValueError, match="coverage differs"):
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


def test_score_keeps_coverage_error_and_abstention_separate(sample):
    doc = build_evalset(*sample)
    e1, e2, e3 = doc["entries"]
    preds = [
        prediction(e1),  # fully correct
        prediction(e2, balls=None, outs=2),  # abstains on balls, wrong on outs
        prediction(e3, balls=0),  # attempt on an occluded frame
    ]
    score = score_predictions(doc, preds)
    assert score["coverage"] == 0.5
    assert score["occluded_attempts"] == 1
    balls = score["per_field"]["balls"]
    assert balls == {
        "evaluable": 2,
        "attempted": 1,
        "correct": 1,
        "wrong": 0,
        "attempt_rate": 0.5,
        "accuracy": 1.0,
        "error_rate": 0.0,
        "abstain_rate": 0.5,
    }
    outs = score["per_field"]["outs"]
    assert outs["attempted"] == 2 and outs["correct"] == 1 and outs["error_rate"] == 0.5
    assert score["all_fields"]["attempted"] == 1 and score["all_fields"]["correct"] == 1
    assert score["coverage_counts"]["unreviewed"] == 1


def test_score_rejects_identity_and_field_errors(sample):
    doc = build_evalset(*sample)
    e1 = doc["entries"][0]
    with pytest.raises(ValueError, match="play_id"):
        score_predictions(doc, [{**prediction(e1), "play_id": "other"}])
    with pytest.raises(ValueError, match="Unknown or duplicate"):
        score_predictions(doc, [prediction(e1), prediction(e1)])
    with pytest.raises(ValueError, match="Unknown or duplicate"):
        score_predictions(doc, [{**prediction(e1), "pitch_number": 4}])
    bad = prediction(e1)
    del bad["fields"]["outs"]
    with pytest.raises(ValueError, match="every label field"):
        score_predictions(doc, [bad])
    with pytest.raises(ValueError, match="Unexpected prediction"):
        score_predictions(doc, [{**prediction(e1), "extra": 1}])
    typed = prediction(e1, balls="0")
    assert score_predictions(doc, [typed])["per_field"]["balls"]["correct"] == 0


def test_real_game_evalset_matches_timing_and_cli_round_trips(tmp_path):
    files = [
        RESULTS / n
        for n in (
            "game_747139_manifest.json",
            "game_747139_sources.json",
            "game_747139_timing.json",
        )
    ]
    manifest, sources, timing = (json.loads(p.read_text(encoding="utf-8-sig")) for p in files)
    doc = build_evalset(manifest, sources, timing)
    assert doc["coverage"]["total_pitches"] == 322
    assert doc["coverage"]["reviewed"] == len(timing["annotations"])
    assert doc["coverage"]["occluded"] == sum(
        r["status"] == "unavailable" for r in timing["annotations"]
    )
    assert all(e["scoreboard_status"] in (*EVALUABLE, "occluded") for e in doc["entries"])
    out = tmp_path / "evalset.json"
    script = ROOT / "scripts" / "64_build_scoreboard_evalset.py"
    run = subprocess.run(
        [sys.executable, str(script), "build", "--output", str(out)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )
    assert run.returncode == 0, run.stderr
    run = subprocess.run(
        [sys.executable, str(script), "check", "--evalset", str(out)],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )
    assert run.returncode == 0, run.stderr
    assert json.loads(run.stdout)["total_pitches"] == 322

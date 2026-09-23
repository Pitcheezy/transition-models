"""Negative frames measure abstention: false reads are counted even when the value is right."""

from copy import deepcopy

import pytest

from src.vision.negatives import LABEL_FIELDS, score_negatives, validate_negatives

EVALSET = {
    "game_pk": 7,
    "manifest_sha256": "abc",
    "observed_source": "human_reading_of_scoreboard_bug_at_decision_frame_not_ocr",
    "source": {"media_url": "https://example.invalid/x.mp4"},
    "entries": [{"frame_seconds": 10.0}],
}
FULL = {
    "balls": 1,
    "strikes": 2,
    "outs": 1,
    "runner_on_1b": True,
    "runner_on_2b": False,
    "runner_on_3b": False,
    "inning": 3,
    "inning_topbot": "Bot",
    "home_score": 0,
    "away_score": 2,
}
DOC = {
    "schema": "mlb_scoreboard_negatives_v1",
    "game_pk": 7,
    "manifest_sha256": "abc",
    "media_url": "https://example.invalid/x.mp4",
    "observed_source": "human_reading_of_scoreboard_bug_at_decision_frame_not_ocr",
    "frames": [
        {"seconds": 20.0, "kind": "graphic", "reason": "panel", "readable": {}},
        {
            "seconds": 30.0,
            "kind": "line_score",
            "reason": "line score",
            "readable": {"inning": 3, "inning_topbot": "Bot", "home_score": 0, "away_score": 2},
        },
        {"seconds": 40.0, "kind": "cutaway_readable", "reason": "dugout", "readable": FULL},
    ],
}


def abstain():
    return dict.fromkeys(LABEL_FIELDS)


def test_validation_binds_media_and_rejects_decision_frames_and_bad_kinds():
    assert len(validate_negatives(DOC, EVALSET)) == 3
    for mutate in (
        lambda d: d.update(media_url="https://example.invalid/other.mp4"),
        lambda d: d.update(manifest_sha256="zzz"),
        lambda d: d.update(observed_source="ocr"),
        lambda d: d["frames"][0].update(seconds=10.0),  # a decision frame
        lambda d: d["frames"].append(dict(d["frames"][0])),  # duplicate
        lambda d: d["frames"][0].update(kind="mystery"),
        lambda d: d["frames"][0].update(readable={"balls": 0}),  # graphic cannot be readable
        lambda d: d["frames"][2]["readable"].pop("outs"),  # cutaway must give every field
        lambda d: d["frames"][1].update(readable={"pitcher": 1}),
    ):
        broken = deepcopy(DOC)
        mutate(broken)
        with pytest.raises(ValueError):
            validate_negatives(broken, EVALSET)


def test_score_counts_false_wrong_correct_and_missed_reads():
    frames = validate_negatives(DOC, EVALSET)
    outputs = {
        20.0: {**abstain(), "outs": 0},  # a confident 0 on a hidden bug is a false read
        30.0: {**abstain(), "inning": 3, "inning_topbot": "Top", "outs": 0},
        40.0: {**FULL, "balls": None, "strikes": "2"},  # one miss, one wrong type
    }
    score = score_negatives(frames, outputs)
    assert score["frames"] == 3
    assert score["unreadable_fields"] == 10 + 6 + 0
    assert score["readable_fields"] == 0 + 4 + 10
    assert score["totals"] == {
        "false_reads": 2,
        "wrong_reads": 2,
        "correct_reads": 1 + 8,
        "missed_reads": 2 + 1,
    }
    assert score["abstain_rate_on_unreadable"] == (16 - 2) / 16
    assert score["correct_rate_on_readable"] == 9 / 14
    by = {row["seconds"]: row for row in score["per_frame"]}
    assert by[20.0]["false_reads"] == ["outs"]
    assert by[30.0]["wrong_reads"] == ["inning_topbot"] and by[30.0]["false_reads"] == ["outs"]
    assert by[40.0]["missed_reads"] == ["balls"] and by[40.0]["wrong_reads"] == ["strikes"]
    perfect = score_negatives(
        frames, {20.0: abstain(), 30.0: {**abstain(), **frames[1]["readable"]}, 40.0: dict(FULL)}
    )
    assert perfect["totals"]["false_reads"] == 0 and perfect["correct_rate_on_readable"] == 1.0

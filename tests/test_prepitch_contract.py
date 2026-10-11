"""Check the information boundary and user-facing probability semantics."""

import math

import pytest

from src.data.point_data import CLASS_NAMES
from src.inference.prepitch_contract import PrePitchState, present_legacy_probabilities


def state():
    return {
        "game_date": "2024-09-30",
        "pitcher": 621242,
        "balls": 1,
        "strikes": 2,
        "outs_when_up": 0,
        "inning": 3,
        "stand": "L",
        "p_throws": "R",
    }


def test_valid_state_and_defaults():
    parsed = PrePitchState.from_dict(state())
    assert parsed.on_1b is None
    assert parsed.to_frame().iloc[0].balls == 1
    assert "pitch_type" not in parsed.to_frame().columns


@pytest.mark.parametrize(
    "key,value",
    [
        ("pitch_type", "FF"),
        ("plate_x", 0.2),
        ("events", "home_run"),
        ("zone", 5),
        ("pitcher", True),
        ("balls", 4),
        ("strikes", -1),
        ("outs_when_up", 3),
        ("inning", 0),
        ("pitcher", 1.5),
        ("pitcher", "42"),
        ("stand", "S"),
        ("on_1b", math.nan),
        ("home_score", math.inf),
        ("game_date", "2024-02-30"),
        ("game_date", "20240930"),
        ("home_team", "<script>"),
        ("inning_topbot", "Bottom"),
    ],
)
def test_invalid_fields_fail_closed(key, value):
    with pytest.raises(ValueError):
        PrePitchState.from_dict({**state(), key: value})


@pytest.mark.parametrize("payload", [None, [], {}, {"balls": 0}])
def test_invalid_objects_and_missing_fields(payload):
    with pytest.raises(ValueError):
        PrePitchState.from_dict(payload)


def test_runner_contradictions():
    for extra in ({"on_1b": 42, "on_2b": 42}, {"on_1b": 42, "batter": 42}):
        with pytest.raises(ValueError, match="Runner"):
            PrePitchState.from_dict({**state(), **extra})


def test_legacy_strike_does_not_become_foul_or_strike_probability():
    result = present_legacy_probabilities(dict.fromkeys(CLASS_NAMES, 0.1))
    assert result["display_probabilities"] == {
        "strike": None,
        "ball": None,
        "foul": None,
        "hit": pytest.approx(0.4),
    }
    assert result["legacy_probabilities"]["Strike"] == 0.1


@pytest.mark.parametrize("value", [math.nan, math.inf, -0.1, 1.1, True, "0.1", 0.2])
def test_bad_probabilities(value):
    probs = dict.fromkeys(CLASS_NAMES, 0.1)
    probs["Ball"] = value
    with pytest.raises(ValueError):
        present_legacy_probabilities(probs)

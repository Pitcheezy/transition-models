"""Preserve physical-pitch labels independently of terminal baseball transitions."""

import pandas as pd
import pytest

from src.data.pitch_observation import build_observation_targets


def test_terminal_events_do_not_swallow_fouls_or_strikes():
    frame = pd.DataFrame(
        {
            "game_pk": [7] * 8,
            "at_bat_number": list(range(1, 9)),
            "pitch_number": [1] * 8,
            "description": [
                "foul",
                "foul_bunt",
                "foul_tip",
                "swinging_strike",
                "ball",
                "hit_into_play",
                "hit_into_play",
                "called_strike",
            ],
            "events": [
                None,
                "strikeout",
                "strikeout",
                "strikeout",
                "walk",
                "single",
                "field_error",
                "strikeout",
            ],
        }
    )
    result = build_observation_targets(frame)
    assert result.observation.tolist() == [
        "foul",
        "foul",
        "caught_foul_tip",
        "swinging_strike",
        "ball",
        "hit",
        "in_play_no_hit",
        "called_strike",
    ]
    assert result.loc[1, "pa_event"] == "strikeout"
    assert result.at_bat_number.tolist() == list(range(1, 9))


def test_unknown_and_administrative_rows_not_silently_mapped():
    frame = pd.DataFrame(
        {
            "game_pk": [7] * 4,
            "at_bat_number": [1, 2, 3, 4],
            "pitch_number": [1] * 4,
            "description": ["automatic_ball", "automatic_strike", "hit_into_play", "new_event"],
            "events": ["walk", "strikeout", "catcher_interf", None],
        }
    )
    result = build_observation_targets(frame)
    assert (result.target == -1).all()
    assert (result.exclusion_reason != "").all()


def test_duplicate_pitch_targets_rejected():
    frame = pd.DataFrame(
        {
            "game_pk": [7, 7],
            "at_bat_number": [1, 1],
            "pitch_number": [1, 1],
            "description": ["ball", "foul"],
            "events": [None, None],
        }
    )
    with pytest.raises(ValueError, match="unique"):
        build_observation_targets(frame)

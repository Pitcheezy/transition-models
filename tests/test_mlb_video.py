"""Guard against the historical positional video/label pairing bug."""

import pandas as pd
import pytest

from src.data.mlb_video import build_game_manifest


def examples():
    rows = [
        {
            "game_pk": 7,
            "at_bat_number": 1,
            "pitch_number": n,
            "pitcher": 42,
            "batter": 43,
            "pitch_type": "FF",
        }
        for n in (1, 2)
    ]
    events = [
        {
            "isPitch": True,
            "pitchNumber": n,
            "playId": f"00000000-0000-0000-0000-{n:012d}",
            "details": {"type": {"code": "FF"}},
        }
        for n in (2, 1)
    ]
    feed = {
        "gamePk": 7,
        "liveData": {
            "plays": {
                "allPlays": [
                    {
                        "about": {"atBatIndex": 0},
                        "matchup": {"pitcher": {"id": 42}, "batter": {"id": 43}},
                        "playEvents": events,
                    }
                ]
            }
        },
    }
    return pd.DataFrame(rows), feed


def test_identity_not_order():
    rows, feed = examples()
    result = build_game_manifest(rows.iloc[::-1], feed)
    assert result["counts"] == {"verified": 2}
    assert result["pitches"][0]["video"]["play_id"].endswith("000001")
    assert result["pitches"][1]["video"]["play_id"].endswith("000002")
    assert "pitch_type" not in result["pitches"][0]["pre_state"]
    assert result["pitches"][0]["video"]["broadcast_offset_seconds"] is None


def test_missing_and_conflicting_records_are_not_verified():
    rows, feed = examples()
    rows.loc[0, "pitch_type"] = "SL"
    rows.loc[1, "pitch_number"] = 3
    result = build_game_manifest(rows, feed)
    assert result["counts"] == {"metadata_conflict": 1, "missing_statcast": 1, "missing_feed": 1}


def test_duplicate_keys_fail_closed():
    rows, feed = examples()
    with pytest.raises(ValueError, match="duplicate"):
        build_game_manifest(pd.concat([rows, rows]), feed)


def test_duplicate_play_ids_fail_closed():
    rows, feed = examples()
    events = feed["liveData"]["plays"]["allPlays"][0]["playEvents"]
    events[0]["playId"] = events[1]["playId"]
    with pytest.raises(ValueError, match="Duplicate"):
        build_game_manifest(rows, feed)

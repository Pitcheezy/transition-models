"""Recorded heights require exact pitch/player joins and pinned source bytes."""

import copy
import hashlib
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "zones_export", ROOT / "scripts/export_pitch_studio_zones.py"
)
EXPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPORT)


@pytest.fixture
def source():
    game = json.loads((ROOT / "web/pitch-studio/game-849843.json").read_bytes())
    game["pitches"] = game["pitches"][:2]
    rows, events = [], []
    for index, pitch in enumerate(game["pitches"], 1):
        rows.append(
            {
                "game_pk": "849843",
                "at_bat_number": str(pitch["at_bat_number"]),
                "pitch_number": str(pitch["pitch_number"]),
                "batter": str(pitch["batter"]["id"]),
                "pitcher": str(pitch["pitcher"]["id"]),
                "sz_bot": "1.616190945",
                "sz_top": "3.202452428",
                "pitch_type": "DO_NOT_PROJECT",
                "local_path": "DO_NOT_PROJECT",
            }
        )
        events.append(
            {
                "isPitch": True,
                "pitchNumber": pitch["pitch_number"],
                "playId": f"00000000-0000-0000-0000-{index:012d}",
                "pitchData": {"strikeZoneBottom": 1.616, "strikeZoneTop": 3.202},
            }
        )
    feed = {
        "gamePk": 849843,
        "liveData": {
            "plays": {
                "allPlays": [
                    {
                        "about": {"atBatIndex": 0},
                        "matchup": {
                            "batter": {"id": game["pitches"][0]["batter"]["id"]},
                            "pitcher": {"id": game["pitches"][0]["pitcher"]["id"]},
                        },
                        "playEvents": events,
                    }
                ]
            }
        },
    }
    return rows, feed, game


def test_order_independent_exact_join_preserves_sources_and_exports_only_heights(source):
    baseline = copy.deepcopy(source)
    result = EXPORT.project(*source)
    assert source == baseline
    source[0].reverse()
    source[1]["liveData"]["plays"]["allPlays"][0]["playEvents"].reverse()
    source[2]["pitches"].reverse()
    assert EXPORT.project(*source) == result
    assert result["source_pitch_count"] == 2
    assert result["pitches"][0] == {
        "pitch_id": "849843:1:1",
        "batter_id": 691718,
        "pitcher_id": 650633,
        "bottom_ft": 1.616190945,
        "top_ft": 3.202452428,
    }
    assert "DO_NOT_PROJECT" not in EXPORT.serialize(result).decode()
    assert result["timing"] == "historical_record"
    assert result["units"] == {"height": "feet", "reference": "ground", "perspective": "catcher"}


@pytest.mark.parametrize(
    ("field", "value", "reason"),
    [
        ("batter", "17", "batter_id_mismatch"),
        ("pitcher", "17", "pitcher_id_mismatch"),
        ("game_pk", "849845", "wrong_statcast_game"),
        ("pitch_number", "30", "statcast_pitch_coverage_mismatch"),
        ("at_bat_number", "1.0", "invalid_csv_identity"),
        ("sz_bot", "", "missing_zone_height"),
        ("sz_top", "not_a_height", "invalid_zone_height"),
        ("sz_top", "NaN", "invalid_zone_heights"),
        ("sz_top", "Infinity", "invalid_zone_heights"),
        ("sz_top", "1.5", "invalid_zone_heights"),
        ("sz_top", "6.5", "invalid_zone_heights"),
        ("sz_bot", "0.1", "invalid_zone_heights"),
        ("sz_bot", "3.1", "invalid_zone_heights"),
        ("sz_bot", "1.9", "feed_statcast_zone_mismatch"),
    ],
)
def test_bad_statcast_identity_or_height_is_rejected(source, field, value, reason):
    source[0][0][field] = value
    with pytest.raises(ValueError, match=reason):
        EXPORT.project(*source)


def test_missing_duplicate_or_extra_pitch_fails_closed(source):
    rows, feed, game = source
    missing = rows[:1]
    with pytest.raises(ValueError, match="statcast_pitch_coverage_mismatch"):
        EXPORT.project(missing, feed, game)
    with pytest.raises(ValueError, match="duplicate_statcast_key"):
        EXPORT.project(rows + [rows[0]], feed, game)
    game["pitches"].append(copy.deepcopy(game["pitches"][0]))
    with pytest.raises(ValueError, match="duplicate_or_wrong_game_key"):
        EXPORT.project(rows, feed, game)


def test_feed_uses_pitch_number_not_event_ordinal_and_keeps_rounded_precision(source):
    events = source[1]["liveData"]["plays"]["allPlays"][0]["playEvents"]
    events.insert(0, {"isPitch": False, "type": "pickoff"})
    result = EXPORT.project(*source)
    assert len(result["pitches"]) == 2
    assert result["pitches"][0]["bottom_ft"] == 1.616190945
    assert result["pitches"][0]["top_ft"] == 3.202452428


@pytest.mark.parametrize("kind", ["missing", "duplicate_key", "duplicate_play_id", "wrong_player", "bad_height", "zone_mismatch"])
def test_feed_must_corroborate_every_key_player_and_height(source, kind):
    play = source[1]["liveData"]["plays"]["allPlays"][0]
    events = play["playEvents"]
    if kind == "missing":
        events.pop()
    elif kind == "duplicate_key":
        events[1]["pitchNumber"] = 1
    elif kind == "duplicate_play_id":
        events[1]["playId"] = events[0]["playId"]
    elif kind == "wrong_player":
        play["matchup"]["batter"]["id"] = 17
    elif kind == "bad_height":
        events[0]["pitchData"]["strikeZoneBottom"] = True
    else:
        events[0]["pitchData"]["strikeZoneTop"] = 3.3
    with pytest.raises(ValueError):
        EXPORT.project(*source)


@pytest.mark.parametrize("which", ["game", "feed"])
def test_only_fixed_development_game_is_accepted(source, which):
    if which == "game":
        source[2]["game"]["game_pk"] = 849845
    else:
        source[1]["gamePk"] = 849845
    with pytest.raises(ValueError, match="wrong_.*game"):
        EXPORT.project(*source)


def test_invalid_game_bytes_are_rejected_before_reading_private_sources(tmp_path):
    game = tmp_path / "game.json"
    game.write_bytes(b"{}")
    with pytest.raises(ValueError, match="game_asset_changed"):
        EXPORT.export_game(tmp_path / "not-present", game)


@pytest.mark.parametrize("changed", ["feed", "statcast"])
def test_changed_source_bytes_are_rejected_before_parsing(tmp_path, monkeypatch, changed):
    root = tmp_path / "registry"
    source_dir = root / "sources/849843"
    source_dir.mkdir(parents=True)
    feed_bytes, statcast_bytes = b"not JSON", b"not CSV"
    (source_dir / "feed.json").write_bytes(feed_bytes)
    (source_dir / "statcast.csv").write_bytes(statcast_bytes)
    monkeypatch.setattr(EXPORT, "FEED_SHA256", hashlib.sha256(feed_bytes).hexdigest())
    monkeypatch.setattr(EXPORT, "STATCAST_SHA256", hashlib.sha256(statcast_bytes).hexdigest())
    (source_dir / ("feed.json" if changed == "feed" else "statcast.csv")).write_bytes(b"changed")
    with pytest.raises(ValueError, match=f"{changed}_asset_changed"):
        EXPORT.export_game(root, ROOT / "web/pitch-studio/game-849843.json")


def test_committed_sidecar_has_full_identity_coverage_and_preserves_separate_type_conflict():
    game_bytes = (ROOT / "web/pitch-studio/game-849843.json").read_bytes()
    game = json.loads(game_bytes)
    packet = json.loads((ROOT / "web/pitch-studio/game-849843-zones.json").read_bytes())
    assert packet["game_sha256"] == hashlib.sha256(game_bytes).hexdigest() == EXPORT.GAME_SHA256
    assert packet["source"]["statcast_sha256"] == EXPORT.STATCAST_SHA256
    assert packet["source"]["feed_sha256"] == EXPORT.FEED_SHA256
    assert packet["source_pitch_count"] == len(packet["pitches"]) == 262
    pitches = {pitch["pitch_id"]: pitch for pitch in game["pitches"]}
    zones = {pitch["pitch_id"]: pitch for pitch in packet["pitches"]}
    assert len(zones) == 262 and zones.keys() == pitches.keys()
    for key, record in zones.items():
        pitch = pitches[key]
        assert record["batter_id"] == pitch["batter"]["id"]
        assert record["pitcher_id"] == pitch["pitcher"]["id"]
        EXPORT.height_pair(record["bottom_ft"], record["top_ft"])
    assert len({p["batter_id"] for p in packet["pitches"]}) == 20
    assert zones["849843:1:1"]["top_ft"] == zones["849843:1:3"]["top_ft"] == 3.202452428
    assert zones["849843:2:1"]["top_ft"] == 3.126099081
    assert pitches["849843:69:2"]["post"]["actual"]["pitch_type"] == "FC"
    assert "pitch_type" not in zones["849843:69:2"]

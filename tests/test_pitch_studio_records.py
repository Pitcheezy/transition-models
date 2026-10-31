"""Archived records keep pre-pitch context, observed results and absent AI separate."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "records_export", ROOT / "scripts/export_pitch_studio_records.py"
)
EXPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPORT)


@pytest.fixture
def source(tmp_path):
    gid = 849845
    rows, registry, events = [], [], []
    for n in (1, 2):
        row = {
            "game_pk": str(gid),
            "at_bat_number": "1",
            "pitch_number": str(n),
            "inning": "1",
            "inning_topbot": "Top",
            "pitcher": "10",
            "batter": "20",
            "p_throws": "R",
            "stand": "L",
            "balls": str(n - 1),
            "strikes": "0",
            "outs_when_up": "1",
            "on_1b": "30",
            "on_2b": "",
            "on_3b": "40",
            "home_score": "2",
            "away_score": "3",
            "pitch_type": "FF",
            "pitch_name": "4-Seam Fastball",
            "release_speed": "0" if n == 1 else "92.3",
            "plate_x": "1.2",
            "plate_z": "2.0",
            "description": "ball" if n == 1 else "hit_into_play",
            "events": "" if n == 1 else "home_run",
            "sz_bot": "1.5",
            "sz_top": "3.5",
        }
        rows.append(row)
        play_id = f"00000000-0000-0000-0000-{n:012d}"
        events.append(
            {
                "isPitch": True,
                "pitchNumber": n,
                "playId": play_id,
                "details": {"type": {"code": "FF"}},
                "count": {"balls": 4, "strikes": 3, "outs": 3},
                "pitchData": {"strikeZoneBottom": 1.5, "strikeZoneTop": 3.5},
            }
        )
        video = f"https://sporty-clips.mlb.com/example_{n}.mp4"
        raw = f"synthetic clip {n}".encode()
        page = f'<link rel="canonical" href="https://baseballsavant.mlb.com/sporty-videos?playId={play_id}"><video src="{video}"></video>'.encode()
        (tmp_path / f"{n}.mp4").write_bytes(raw)
        (tmp_path / f"{n}.html").write_bytes(page)
        registry.append(
            {
                "game_pk": gid,
                "at_bat_number": 1,
                "pitch_number": n,
                "play_id": play_id,
                "pitcher_id": 10,
                "batter_id": 20,
                "inning": 1,
                "inning_topbot": "Top",
                "pitch_type": "FF",
                "status": "downloaded",
                "media_url": video,
                "media_candidates": json.dumps([video]),
                "page_path": f"{n}.html",
                "page_sha256": EXPORT.digest(page),
                "file_path": f"{n}.mp4",
                "file_sha256": EXPORT.digest(raw),
                "bytes": len(raw),
                "duration_s": 7.0,
                "private_path": "DO_NOT_PUBLISH",
            }
        )
    play = {
        "about": {"atBatIndex": 0, "inning": 1, "halfInning": "top"},
        "matchup": {
            "pitcher": {"id": 10, "fullName": "Test Pitcher"},
            "batter": {"id": 20, "fullName": "Test Batter"},
            "postOnFirst": {"id": 99},
        },
        "result": {"eventType": "home_run", "event": "Home Run", "homeScore": 9, "awayScore": 9},
        "count": {"balls": 4, "strikes": 3, "outs": 3},
        "playEvents": events,
    }
    feed = {
        "gamePk": gid,
        "gameData": {
            "datetime": {"dateTime": "2026-09-29T18:00:00Z"},
            "teams": {
                "away": {"name": "Philadelphia Phillies"},
                "home": {"name": "Atlanta Braves"},
            },
        },
        "liveData": {"plays": {"allPlays": [play]}},
    }
    return rows, feed, registry, tmp_path


def project(source):
    return EXPORT.project_records(source[0], source[1], source[1]["gamePk"], "a" * 64, "b" * 64)


def test_pre_context_never_uses_final_feed_count_score_or_bases(source):
    game = project(source)
    assert game["game"]["date"] == "2026-09-30"
    p = game["pitches"][0]
    assert p["situation"] == {
        "inning": 1,
        "half": "Top",
        "outs": 1,
        "balls": 0,
        "strikes": 0,
        "bases": 5,
        "home_score": 2,
        "away_score": 3,
    }
    assert p["post"]["actual"]["event"] is None
    assert p["post"]["actual"]["event_label"] is None
    assert p["post"]["actual"]["speed_mph"] == 0
    assert game["pitches"][1]["post"]["actual"]["event"] == "home_run"
    for row in game["pitches"]:
        assert row["pre"] == {
            "status": "missing",
            "provenance": "absent",
            "recorded_at": None,
            "policy": None,
            "candidates": [],
        }
        assert row["post"]["setup"] is None
    assert game["source"]["model_id"] is None
    assert game["source"]["kind"] == "official_record"
    assert not any(game["claims"].values())


def test_keyed_order_and_input_immutability(source):
    original = copy.deepcopy(source[:3])
    baseline = project(source)
    source[0].reverse()
    source[1]["liveData"]["plays"]["allPlays"][0]["playEvents"].reverse()
    assert project(source) == baseline
    source[0].reverse()
    source[1]["liveData"]["plays"]["allPlays"][0]["playEvents"].reverse()
    assert source[:3] == original


@pytest.mark.parametrize(
    "field,value",
    [
        ("balls", "4"),
        ("strikes", "3"),
        ("outs_when_up", "3"),
        ("on_1b", "-1"),
        ("pitcher", "11"),
        ("batter", "21"),
        ("pitch_type", "SL"),
        ("inning", "2"),
        ("inning_topbot", "Bot"),
        ("plate_x", "nan"),
        ("release_speed", "inf"),
    ],
)
def test_invalid_context_identity_and_nonfinite_values_fail(source, field, value):
    source[0][0][field] = value
    with pytest.raises(ValueError):
        project(source)


def test_terminal_result_cannot_leak_to_an_earlier_pitch(source):
    source[0][0]["events"] = "home_run"
    with pytest.raises(ValueError, match="pa_result_before_terminal_record"):
        project(source)


@pytest.mark.parametrize("which", ["csv", "feed"])
def test_duplicate_identity_rejected(source, which):
    target = (
        source[0] if which == "csv" else source[1]["liveData"]["plays"]["allPlays"][0]["playEvents"]
    )
    target.append(copy.deepcopy(target[0]))
    with pytest.raises(ValueError, match="duplicate"):
        project(source)


def test_unregistered_game_rejected_before_filesystem_access(tmp_path):
    for gid in (849844, 849843, 123):
        with pytest.raises(ValueError, match="game_not_approved"):
            EXPORT.export_game(tmp_path / "does-not-exist", gid)


def test_missing_physical_pitch_is_not_silently_omitted(source):
    source[1]["liveData"]["plays"]["allPlays"][0]["playEvents"].pop(0)
    with pytest.raises(ValueError, match="unapproved_missing_feed_pitch"):
        project(source)


def test_verified_media_join_and_source_pins(source):
    game = project(source)
    _, _, events = EXPORT.keyed_sources(source[0], source[1], 849845)
    EXPORT.verify_registry_play_ids(source[2], events, 849845)
    game_sha = EXPORT.digest(EXPORT.serialize(game))
    result = EXPORT.project_media(source[2][::-1], game, source[3], game_sha, "b" * 64)
    assert [r["pitch_id"] for r in result["records"]] == [p["pitch_id"] for p in game["pitches"]]
    assert result["game_sha256"] == game_sha and result["source_pitch_count"] == 2
    assert "DO_NOT_PUBLISH" not in EXPORT.serialize(result).decode()
    assert str(source[3]) not in EXPORT.serialize(result).decode()
    zones = EXPORT.project_zones(source[0][::-1], source[1], game, game_sha, "c" * 64, "a" * 64)
    assert zones["source_pitch_count"] == len(zones["pitches"]) == 2
    assert zones["game_sha256"] == game_sha and zones["source"]["feed_sha256"] == "a" * 64


def test_swapped_clip_uuids_fail_even_with_matching_player_type(source):
    _, _, events = EXPORT.keyed_sources(source[0], source[1], 849845)
    source[2][0]["play_id"], source[2][1]["play_id"] = (
        source[2][1]["play_id"],
        source[2][0]["play_id"],
    )
    with pytest.raises(ValueError, match="registry_feed_play_id_mismatch"):
        EXPORT.verify_registry_play_ids(source[2], events, 849845)


@pytest.mark.parametrize("which", ["clip_bytes", "page_bytes", "identity", "path", "url"])
def test_unverified_clip_metadata_fails_export(source, which):
    game = project(source)
    if which == "clip_bytes":
        (source[3] / "1.mp4").write_bytes(b"synthetic clip X")
    elif which == "page_bytes":
        (source[3] / "1.html").write_bytes(b"different")
    elif which == "identity":
        source[2][0]["batter_id"] = 21
    elif which == "path":
        source[2][0]["file_path"] = "../outside.mp4"
    else:
        source[2][0]["media_url"] = "https://private.example.test/clip.mp4"
    with pytest.raises(ValueError):
        EXPORT.project_media(source[2], game, source[3], "a" * 64, "b" * 64)


def test_zone_disagreement_is_rejected(source):
    game = project(source)
    source[0][0]["sz_bot"] = "1.6"
    with pytest.raises(ValueError, match="feed_statcast_zone_mismatch"):
        EXPORT.project_zones(source[0], source[1], game, "a" * 64, "b" * 64, "c" * 64)


def automatic_source(source):
    rows, feed, _, path = copy.deepcopy(source)
    feed["gamePk"] = 823407
    play = feed["liveData"]["plays"]["allPlays"][0]
    play["about"]["atBatIndex"] = 34
    play["result"] = {"eventType": "intent_walk", "event": "Intent Walk"}
    play["playEvents"] = [
        {
            "type": "no_pitch",
            "isPitch": False,
            "pitchNumber": 0,
            "details": {"code": "VB"},
            "count": {"balls": n, "strikes": 0},
        }
        for n in range(1, 5)
    ]
    records = []
    for n in range(1, 5):
        row = dict(
            rows[0],
            game_pk="823407",
            at_bat_number="35",
            pitch_number=str(n),
            balls=str(n - 1),
            pitch_type="",
            pitch_name="",
            release_speed="",
            plate_x="",
            plate_z="",
            sz_bot="",
            sz_top="",
            description="automatic_ball",
            events="intent_walk" if n == 4 else "",
        )
        records.append(row)
    return records, feed, [], path


def test_automatic_balls_remain_records_without_video_or_zone(source):
    source = automatic_source(source)
    game = project(source)
    assert len(game["pitches"]) == 4
    assert [p["situation"]["balls"] for p in game["pitches"]] == [0, 1, 2, 3]
    assert [p["post"]["actual"]["event"] for p in game["pitches"]] == [
        None,
        None,
        None,
        "intent_walk",
    ]
    for pitch in game["pitches"]:
        assert all(
            pitch["post"]["actual"][k] is None
            for k in ("pitch_type", "pitch_label", "x", "z", "speed_mph")
        )
    media = EXPORT.project_media([], game, source[3], "a" * 64, "b" * 64)
    zones = EXPORT.project_zones(source[0], source[1], game, "a" * 64, "b" * 64, "c" * 64)
    assert media["source_pitch_count"] == zones["source_pitch_count"] == 4
    assert media["records"] == zones["pitches"] == []
    assert media["excluded"] == [
        {
            "pitch_id": f"823407:35:{n}",
            "reason": "automatic_ball_no_video",
            "registry_pitch_type": None,
            "received_pitch_type": None,
        }
        for n in range(1, 5)
    ]


def test_automatic_ball_without_feed_corroboration_fails(source):
    source = automatic_source(source)
    source[1]["liveData"]["plays"]["allPlays"][0]["playEvents"].pop()
    with pytest.raises(ValueError, match="automatic_ball_not_corroborated"):
        project(source)


def test_pinned_archive_sha_is_checked_before_db_read(tmp_path):
    (tmp_path / "registry.sqlite").write_bytes(b"not the pinned registry")
    with pytest.raises(ValueError, match="registry_asset_changed"):
        EXPORT.export_game(tmp_path, 849845)

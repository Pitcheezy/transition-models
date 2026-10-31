"""Export two approved archived games without inventing recommendation results.

Statcast's pre-pitch columns supply situation; its observed pitch columns supply
post.actual. Feed identity corroborates the join, never supplies a final PA count
as a pre-pitch count. Four intentional automatic balls retain their records but
have no physical-pitch clip or recorded zone. No network or registry writes.
"""

import argparse
import csv
import hashlib
import importlib.util
import io
import json
import re
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path


def _sibling(name):
    spec = importlib.util.spec_from_file_location(name, Path(__file__).with_name(name + ".py"))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


MEDIA = _sibling("export_pitch_studio_media")
GAME = _sibling("export_pitch_studio_game")
ZONES = _sibling("export_pitch_studio_zones")
require = MEDIA.require
serialize = GAME.serialize
REGISTRY_SHA256 = "9555b95171a6232b849b74e4784edf62c210b7a64c72e8b84b5cf5ec48ead3b6"
SOURCES = {
    849845: {
        "feed": "8498af56aa1c4ef9bf9f7e3126b271d4d44c24dd2ea3edda41fc4082e7e4a75e",
        "statcast": "8bb2722a2ac1299f57c977c14ae5690e235bb2d9b170c23b57df3c47ad72d02e",
        "manifest": "676cf2baf0012e3f2f1be16ce26bfba80e3bb5d57976006751d8118a562759e8",
        "records": 250,
        "physical": 250,
        "pa": 70,
        "automatic": (),
    },
    823407: {
        "feed": "1431b296b3ad0ff7aeee83f908e76ab86d9109b9ed0c79d638fc1fdb6281d799",
        "statcast": "b6f8f6eafa969f228fdf994b816b28c9765afc6c267929cbcf01bf920ed43258",
        "manifest": "8f0be1debe9e01b35da1585151ad90e90c316f7fe7d5d014ff1627b4816e81c7",
        "records": 359,
        "physical": 355,
        "pa": 88,
        "automatic": tuple(f"823407:35:{n}" for n in range(1, 5)),
    },
}
PITCH_LABELS = {
    "FF": "포심 패스트볼",
    "SI": "싱커",
    "FC": "커터",
    "SL": "슬라이더",
    "ST": "스위퍼",
    "CU": "커브",
    "KC": "너클 커브",
    "CH": "체인지업",
    "FS": "스플리터",
    "SV": "슬러브",
    "KN": "너클볼",
    "EP": "이퓨스",
}
RESULT_LABELS = {
    "ball": "볼",
    "blocked_ball": "볼",
    "called_strike": "루킹 스트라이크",
    "swinging_strike": "헛스윙",
    "swinging_strike_blocked": "헛스윙",
    "foul": "파울",
    "foul_tip": "파울 팁",
    "foul_bunt": "번트 파울",
    "missed_bunt": "번트 헛스윙",
    "hit_into_play": "인플레이",
    "hit_by_pitch": "몸에 맞는 공",
    "automatic_ball": "자동 볼",
}
EVENT_LABELS = {
    "strikeout": "삼진",
    "walk": "볼넷",
    "intent_walk": "고의사구",
    "single": "안타",
    "double": "2루타",
    "triple": "3루타",
    "home_run": "홈런",
    "field_out": "아웃",
    "force_out": "포스 아웃",
    "grounded_into_double_play": "병살타",
    "double_play": "병살",
    "field_error": "실책",
    "fielders_choice": "야수 선택",
    "fielders_choice_out": "야수 선택 아웃",
    "sac_fly": "희생 플라이",
    "sac_bunt": "희생 번트",
    "hit_by_pitch": "몸에 맞는 공",
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def integer(value, low=0, high=999999999):
    require(isinstance(value, str) and re.fullmatch(r"0|[1-9][0-9]*", value), "invalid_csv_integer")
    return GAME._int(int(value), low, high)


def number(value, low=-20, high=20):
    if value == "":
        return None
    require(isinstance(value, str), "invalid_csv_number")
    return GAME._number(float(value), low, high)


def text_or_none(value):
    return None if value == "" or value is None else GAME._text(value)


def keyed_sources(rows, feed, game_pk):
    require(game_pk in SOURCES, "game_not_approved")
    require(feed.get("gamePk") == game_pk, "wrong_feed_game")
    recorded, plays, events, play_ids = {}, {}, {}, set()
    for row in rows:
        require(integer(row["game_pk"], 1) == game_pk, "wrong_statcast_game")
        pa, n = integer(row["at_bat_number"], 1, 999), integer(row["pitch_number"], 1, 100)
        key = f"{game_pk}:{pa}:{n}"
        require(key not in recorded, "duplicate_statcast_key")
        recorded[key] = row
    require(0 < len(recorded) <= 2000, "empty_or_oversized_game")
    for play in feed["liveData"]["plays"]["allPlays"]:
        pa = GAME._int(play["about"]["atBatIndex"], 0, 998) + 1
        require(pa not in plays, "duplicate_feed_pa")
        plays[pa] = play
        for event in play["playEvents"]:
            if event.get("isPitch") is not True:
                continue
            n = GAME._int(event["pitchNumber"], 1, 100)
            key, play_id = f"{game_pk}:{pa}:{n}", event.get("playId")
            require(
                isinstance(play_id, str) and MEDIA.UUID_PATTERN.fullmatch(play_id),
                "invalid_play_id",
            )
            require(key not in events and play_id not in play_ids, "duplicate_feed_identity")
            events[key] = event
            play_ids.add(play_id)
    require(set(events) <= set(recorded), "missing_statcast_record")
    return recorded, plays, events


def project_records(rows, feed, game_pk, feed_sha, registry_sha):
    """Pure projection; non-pitch automatic balls are retained without fake locations."""
    require(
        MEDIA.SHA_PATTERN.fullmatch(feed_sha) and MEDIA.SHA_PATTERN.fullmatch(registry_sha),
        "invalid_source_sha",
    )
    recorded, plays, events = keyed_sources(rows, feed, game_pk)
    ordered = sorted(
        recorded.items(),
        key=lambda item: (int(item[1]["at_bat_number"]), int(item[1]["pitch_number"])),
    )
    ends = {int(row["at_bat_number"]): key for key, row in ordered}
    output = []
    for index, (key, row) in enumerate(ordered):
        pa, n = int(row["at_bat_number"]), int(row["pitch_number"])
        require(pa in plays, "missing_feed_pa")
        play = plays[pa]
        matchup = play["matchup"]
        people = {}
        for who, hand in (("pitcher", "p_throws"), ("batter", "stand")):
            person = matchup[who]
            require(integer(row[who], 1) == person["id"], f"{who}_id_mismatch")
            people[who] = GAME._person(
                {"id": person["id"], "name": person["fullName"], "hand": text_or_none(row[hand])},
                "hand",
            )
        situation = {
            "inning": integer(row["inning"], 1, 99),
            "outs": integer(row["outs_when_up"], 0, 2),
            "balls": integer(row["balls"], 0, 3),
            "strikes": integer(row["strikes"], 0, 2),
            "bases": sum(
                1 << i
                for i, name in enumerate(("on_1b", "on_2b", "on_3b"))
                if row[name] != "" and integer(row[name], 1)
            ),
            "home_score": integer(row["home_score"], 0, 100),
            "away_score": integer(row["away_score"], 0, 100),
            "half": row["inning_topbot"],
        }
        require(situation["half"] in ("Top", "Bot"), "invalid_half")
        require(
            situation["inning"] == play["about"]["inning"]
            and {"Top": "top", "Bot": "bottom"}[situation["half"]] == play["about"]["halfInning"],
            "feed_inning_mismatch",
        )
        kind, description = text_or_none(row["pitch_type"]), text_or_none(row["description"])
        speed, x, z = (
            number(row["release_speed"], 0, 150),
            number(row["plate_x"]),
            number(row["plate_z"]),
        )
        if key in events:
            require(
                kind == events[key]["details"].get("type", {}).get("code"),
                "feed_pitch_type_mismatch",
            )
        else:
            require(
                key in SOURCES[game_pk]["automatic"] and description == "automatic_ball",
                "unapproved_missing_feed_pitch",
            )
            require(
                kind is None
                and speed is None
                and x is None
                and z is None
                and row["sz_bot"] == row["sz_top"] == "",
                "automatic_ball_has_physical_data",
            )
            # Count matches an explicit feed no_pitch event, never an array offset.
            automatic = [
                e
                for e in play["playEvents"]
                if e.get("type") == "no_pitch"
                and e.get("isPitch") is False
                and e.get("details", {}).get("code") == "VB"
                and e.get("count", {}).get("balls") == situation["balls"] + 1
                and e.get("count", {}).get("strikes") == situation["strikes"]
            ]
            require(len(automatic) == 1, "automatic_ball_not_corroborated")
        event = text_or_none(row["events"])
        require(event is None or key == ends[pa], "pa_result_before_terminal_record")
        require(event is None or event == play["result"]["eventType"], "feed_pa_result_mismatch")
        output.append(
            {
                "index": index,
                "pitch_id": key,
                "at_bat_number": pa,
                "pitch_number": n,
                "situation": situation,
                **people,
                "pre": {
                    "status": "missing",
                    "provenance": "absent",
                    "recorded_at": None,
                    "policy": None,
                    "candidates": [],
                },
                "post": {
                    "actual": {
                        "pitch_type": kind,
                        "pitch_label": PITCH_LABELS.get(kind, text_or_none(row.get("pitch_name"))),
                        "description": description,
                        "result_label": RESULT_LABELS.get(description, description),
                        "event": event,
                        "event_label": EVENT_LABELS.get(event, play["result"].get("event"))
                        if event
                        else None,
                        "speed_mph": speed,
                        "x": x,
                        "z": z,
                    },
                    "setup": None,
                },
            }
        )
    data = feed["gameData"]
    start = datetime.fromisoformat(data["datetime"]["dateTime"].replace("Z", "+00:00"))
    require(start.utcoffset() == timedelta(0), "feed_time_not_utc")
    return {
        "schema": GAME.SCHEMA,
        "source": {
            "kind": "official_record",
            "sha256": feed_sha,
            "report_sha256": registry_sha,
            "revision": None,
            "exported_at": None,
            "model_id": None,
            "upstream_kind": "archive",
        },
        "game": {
            "game_pk": game_pk,
            "date": (start + timedelta(hours=9)).date().isoformat(),
            "away_team": GAME._text(data["teams"]["away"]["name"]),
            "home_team": GAME._text(data["teams"]["home"]["name"]),
        },
        "units": {
            "position": "feet",
            "speed": "mph",
            "probability": "pitch_type_selection_share",
            "setup": "feet_catcher_view_right_positive",
        },
        "claims": {
            "live_timing_verified": False,
            "complete_game_verified": False,
            "human_mitt_accuracy_measured": False,
        },
        "pitches": output,
    }


def verify_registry_play_ids(rows, events, game_pk):
    """The registry's media UUID must be the feed UUID at that exact pitch key."""
    observed = set()
    for row in rows:
        require(row["game_pk"] == game_pk, "wrong_registry_game")
        key = f"{game_pk}:{row['at_bat_number']}:{row['pitch_number']}"
        require(key not in observed, "duplicate_registry_identity")
        observed.add(key)
        require(
            key in events and row["play_id"] == events[key]["playId"],
            "registry_feed_play_id_mismatch",
        )
    require(observed == set(events), "registry_feed_coverage_mismatch")


def project_media(rows, game, root, game_sha, registry_sha):
    game_pk = game["game"]["game_pk"]
    require(game_pk in SOURCES, "game_not_approved")
    registry, play_ids = {}, set()
    for row in rows:
        require(row["game_pk"] == game_pk, "wrong_registry_game")
        key = f"{game_pk}:{row['at_bat_number']}:{row['pitch_number']}"
        require(
            key not in registry and row["play_id"] not in play_ids, "duplicate_registry_identity"
        )
        registry[key] = row
        play_ids.add(row["play_id"])
    result, excluded = [], []
    expected = {p["pitch_id"] for p in game["pitches"]}
    require(set(registry) <= expected, "unexpected_registry_pitch")
    for pitch in game["pitches"]:
        key = pitch["pitch_id"]
        if key in SOURCES[game_pk]["automatic"]:
            require(
                key not in registry and pitch["post"]["actual"]["description"] == "automatic_ball",
                "automatic_ball_registry_conflict",
            )
            excluded.append(
                {
                    "pitch_id": key,
                    "reason": "automatic_ball_no_video",
                    "registry_pitch_type": None,
                    "received_pitch_type": None,
                }
            )
            continue
        require(key in registry, "registry_pitch_missing")
        row = registry[key]
        for field in ("pitcher", "batter"):
            require(row[field + "_id"] == pitch[field]["id"], f"{field}_id_mismatch")
        require(
            row["inning"] == pitch["situation"]["inning"]
            and row["inning_topbot"] == pitch["situation"]["half"],
            "registry_inning_mismatch",
        )
        require(
            row["pitch_type"] == pitch["post"]["actual"]["pitch_type"],
            "registry_pitch_type_mismatch",
        )
        clip = MEDIA._clip(Path(root), row)
        result.append(
            {
                "pitch_id": key,
                "at_bat_number": pitch["at_bat_number"],
                "pitch_number": pitch["pitch_number"],
                "pitcher_id": row["pitcher_id"],
                "batter_id": row["batter_id"],
                "pitch_type": row["pitch_type"],
                **clip,
            }
        )
    return {
        "schema": MEDIA.SCHEMA,
        "game_pk": game_pk,
        "game_sha256": game_sha,
        "registry_sha256": registry_sha,
        "source_pitch_count": len(game["pitches"]),
        "records": result,
        "excluded": excluded,
    }


def project_zones(rows, feed, game, game_sha, statcast_sha, feed_sha):
    game_pk = game["game"]["game_pk"]
    recorded, _, events = keyed_sources(rows, feed, game_pk)
    require(
        set(recorded) == {p["pitch_id"] for p in game["pitches"]}, "zone_game_coverage_mismatch"
    )
    output = []
    for pitch in game["pitches"]:
        key = pitch["pitch_id"]
        row = recorded[key]
        if key not in events:
            require(
                key in SOURCES[game_pk]["automatic"] and row["sz_bot"] == row["sz_top"] == "",
                "unapproved_missing_zone",
            )
            continue
        for who in ("batter", "pitcher"):
            require(integer(row[who], 1) == pitch[who]["id"], "zone_player_mismatch")
        bottom, top = ZONES.height_pair(number(row["sz_bot"]), number(row["sz_top"]))
        pd = events[key].get("pitchData", {})
        fb, ft = ZONES.height_pair(pd.get("strikeZoneBottom"), pd.get("strikeZoneTop"))
        require(
            abs(bottom - fb) <= 0.000500001 and abs(top - ft) <= 0.000500001,
            "feed_statcast_zone_mismatch",
        )
        output.append(
            {
                "pitch_id": key,
                "batter_id": pitch["batter"]["id"],
                "pitcher_id": pitch["pitcher"]["id"],
                "bottom_ft": bottom,
                "top_ft": top,
            }
        )
    return {
        "schema": ZONES.SCHEMA,
        "game_pk": game_pk,
        "game_sha256": game_sha,
        "source": {
            "kind": "statcast_record",
            "statcast_sha256": statcast_sha,
            "feed_sha256": feed_sha,
        },
        "units": {"height": "feet", "reference": "ground", "perspective": "catcher"},
        "timing": "historical_record",
        "source_pitch_count": len(game["pitches"]),
        "pitches": output,
    }


def export_game(registry_root, game_pk):
    """Allowlist before any filesystem access, pin sources, then check every clip."""
    require(type(game_pk) is int and game_pk in SOURCES, "game_not_approved")
    expected = SOURCES[game_pk]
    root = Path(registry_root).resolve(strict=True)
    db = root / "registry.sqlite"
    require(MEDIA.sha256(db) == REGISTRY_SHA256, "registry_asset_changed")
    connection = sqlite3.connect(db.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        require(
            connection.execute("SELECT value FROM meta WHERE key='schema'").fetchone()[0]
            == "pitcheezy-clip-registry-v1",
            "wrong_registry_schema",
        )
        meta = dict(
            connection.execute("SELECT * FROM games WHERE game_pk=?", (game_pk,)).fetchone()
        )
        require(
            meta["split"] == "dev"
            and meta["verified"] == expected["physical"]
            and meta["issues"] == len(expected["automatic"]),
            "registry_game_metadata_mismatch",
        )
        for kind in ("feed", "statcast", "manifest"):
            require(meta[kind + "_sha256"] == expected[kind], "registry_source_sha_mismatch")
        issues = list(
            connection.execute(
                "SELECT at_bat_number,pitch_number,status,play_id FROM identity_issues WHERE game_pk=?",
                (game_pk,),
            )
        )
        require(
            {f"{game_pk}:{r['at_bat_number']}:{r['pitch_number']}" for r in issues}
            == set(expected["automatic"])
            and all(r["status"] == "missing_feed" and r["play_id"] is None for r in issues),
            "registry_issues_changed",
        )
        registry = [
            dict(row)
            for row in connection.execute(
                "SELECT p.game_pk,p.at_bat_number,p.pitch_number,p.play_id,p.pitcher_id,p.batter_id,p.inning,p.inning_topbot,o.pitch_type,c.status,c.media_url,c.media_candidates,c.page_path,c.page_sha256,c.file_path,c.file_sha256,c.bytes,c.duration_s FROM pitches p LEFT JOIN outcomes o USING(play_id) LEFT JOIN clips c USING(play_id) WHERE p.game_pk=?",
                (game_pk,),
            )
        ]
    finally:
        connection.close()
    source = {}
    for kind, relative in (
        ("feed", f"sources/{game_pk}/feed.json"),
        ("statcast", f"sources/{game_pk}/statcast.csv"),
        ("manifest", f"manifests/{game_pk}.json"),
    ):
        path = MEDIA._verified_file(root, relative, expected[kind], 40_000_000)
        source[kind] = path.read_bytes()
        require(digest(source[kind]) == expected[kind], "source_changed_during_read")
    feed = json.loads(source["feed"])
    rows = list(csv.DictReader(io.StringIO(source["statcast"].decode("utf-8-sig"))))
    _, _, events = keyed_sources(rows, feed, game_pk)
    verify_registry_play_ids(registry, events, game_pk)
    game = project_records(rows, feed, game_pk, expected["feed"], REGISTRY_SHA256)
    require(
        len(game["pitches"]) == expected["records"]
        and len({p["at_bat_number"] for p in game["pitches"]}) == expected["pa"],
        "record_coverage_changed",
    )
    game_sha = digest(serialize(game))
    media = project_media(registry, game, root, game_sha, REGISTRY_SHA256)
    zones = project_zones(rows, feed, game, game_sha, expected["statcast"], expected["feed"])
    require(
        len(media["records"]) == len(zones["pitches"]) == expected["physical"],
        "sidecar_coverage_changed",
    )
    require(MEDIA.sha256(db) == REGISTRY_SHA256, "registry_changed_during_export")
    return game, media, zones


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry-root", type=Path, required=True)
    parser.add_argument("--game-pk", type=int, choices=tuple(SOURCES), required=True)
    parser.add_argument("--out-dir", type=Path, required=True)
    args = parser.parse_args()
    require(
        not args.out_dir.resolve().is_relative_to(args.registry_root.resolve()),
        "output_inside_registry",
    )
    bundle = export_game(args.registry_root, args.game_pk)
    args.out_dir.mkdir(parents=True, exist_ok=True)
    summary = {
        "game_pk": args.game_pk,
        "records": len(bundle[0]["pitches"]),
        "pa": len({p["at_bat_number"] for p in bundle[0]["pitches"]}),
        "clips": len(bundle[1]["records"]),
        "zones": len(bundle[2]["pitches"]),
        "excluded": bundle[1]["excluded"],
        "first_pitch": bundle[0]["pitches"][0]["pitch_id"],
        "hashes": {},
    }
    for suffix, value in zip(("", "-media", "-zones"), bundle, strict=True):
        data = serialize(value)
        name = f"game-{args.game_pk}{suffix}.json"
        (args.out_dir / name).write_bytes(data)
        summary["hashes"][name] = digest(data)
    print(json.dumps(summary, ensure_ascii=False))


if __name__ == "__main__":
    main()

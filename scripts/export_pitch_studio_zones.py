"""Export recorded batter strike-zone heights for the fixed 849843 replay.

Only previously saved source bytes are read. This sidecar does not recalculate
recommendations, correct supplied outcomes, or establish pre-pitch availability.
"""

import argparse
import csv
import hashlib
import io
import json
import math
import re
from pathlib import Path

GAME_SHA256 = "89e14e12e0f0a2ae2475aff16b8757486143f6a4586239434a1f8b0be6bb3c22"
STATCAST_SHA256 = "0513145c760741abef96fa295a97c1ba80106dfc0db4301544af782277eefd9b"
FEED_SHA256 = "30b82143aff97f2f85c065a7eaec6d574f8a8fe7765789197b766157c4b0fc56"
SCHEMA = "pitcheezy-strike-zones-v1"


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def positive_int(value):
    require(type(value) is int and value > 0, "invalid_identity_integer")
    return value


def csv_int(value):
    require(isinstance(value, str) and re.fullmatch(r"[1-9][0-9]*", value), "invalid_csv_identity")
    return int(value)


def height_pair(bottom, top):
    require(
        type(bottom) in (int, float)
        and type(top) in (int, float)
        and math.isfinite(bottom)
        and math.isfinite(top)
        and 0.5 <= bottom < top <= 5
        and 0.5 <= top - bottom <= 4,
        "invalid_zone_heights",
    )
    return bottom, top


def csv_height(value):
    require(isinstance(value, str) and bool(value.strip()), "missing_zone_height")
    try:
        return float(value)
    except ValueError as error:
        raise ValueError("invalid_zone_height") from error


def project(rows, feed, game):
    """Join by game/PA/pitch and both player IDs; never by row order or name."""
    require(game.get("schema") == "pitcheezy-static-game-v1", "wrong_game_schema")
    require(game.get("game", {}).get("game_pk") == 849843, "wrong_game")
    require(feed.get("gamePk") == 849843, "wrong_feed_game")
    require(isinstance(game.get("pitches"), list) and game["pitches"], "empty_game")
    pitches = {}
    for pitch in game["pitches"]:
        pa = positive_int(pitch["at_bat_number"])
        number = positive_int(pitch["pitch_number"])
        key = f"849843:{pa}:{number}"
        require(pitch["pitch_id"] == key and key not in pitches, "duplicate_or_wrong_game_key")
        positive_int(pitch["batter"]["id"])
        positive_int(pitch["pitcher"]["id"])
        pitches[key] = pitch

    recorded, plays, play_ids = {}, {}, set()
    for row in rows:
        require(csv_int(row["game_pk"]) == 849843, "wrong_statcast_game")
        key = f"849843:{csv_int(row['at_bat_number'])}:{csv_int(row['pitch_number'])}"
        require(key not in recorded, "duplicate_statcast_key")
        recorded[key] = row
    for play in feed["liveData"]["plays"]["allPlays"]:
        index = play["about"]["atBatIndex"]
        require(type(index) is int and index >= 0, "invalid_feed_at_bat_index")
        for event in play["playEvents"]:
            if event.get("isPitch") is not True:
                continue
            number = positive_int(event["pitchNumber"])
            key = f"849843:{index + 1}:{number}"
            play_id = event.get("playId")
            require(
                isinstance(play_id, str)
                and re.fullmatch(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}", play_id)
                and play_id not in play_ids
                and key not in plays,
                "duplicate_or_invalid_feed_identity",
            )
            play_ids.add(play_id)
            plays[key] = (event, play["matchup"])
    require(set(recorded) == set(pitches), "statcast_pitch_coverage_mismatch")
    require(set(plays) == set(pitches), "feed_pitch_coverage_mismatch")

    result = []
    for key, pitch in sorted(
        pitches.items(), key=lambda item: (item[1]["at_bat_number"], item[1]["pitch_number"])
    ):
        row, (event, matchup) = recorded[key], plays[key]
        for player in ("batter", "pitcher"):
            require(
                csv_int(row[player])
                == positive_int(matchup[player]["id"])
                == pitch[player]["id"],
                f"{player}_id_mismatch",
            )
        bottom, top = height_pair(csv_height(row["sz_bot"]), csv_height(row["sz_top"]))
        pd = event.get("pitchData", {})
        feed_bottom, feed_top = height_pair(pd.get("strikeZoneBottom"), pd.get("strikeZoneTop"))
        require(
            abs(bottom - feed_bottom) <= 0.000500001 and abs(top - feed_top) <= 0.000500001,
            "feed_statcast_zone_mismatch",
        )
        result.append(
            {
                "pitch_id": key,
                "batter_id": pitch["batter"]["id"],
                "pitcher_id": pitch["pitcher"]["id"],
                "bottom_ft": bottom,
                "top_ft": top,
            }
        )
    return {
        "schema": SCHEMA,
        "game_pk": 849843,
        "game_sha256": GAME_SHA256,
        "source": {
            "kind": "statcast_record",
            "statcast_sha256": STATCAST_SHA256,
            "feed_sha256": FEED_SHA256,
        },
        "units": {"height": "feet", "reference": "ground", "perspective": "catcher"},
        "timing": "historical_record",
        "source_pitch_count": len(result),
        "pitches": result,
    }


def export_game(registry_root, game_path):
    """Pin all three source files before parsing; never open another game's source."""
    game_bytes = Path(game_path).read_bytes()
    require(hashlib.sha256(game_bytes).hexdigest() == GAME_SHA256, "game_asset_changed")
    root = Path(registry_root)
    feed_bytes = (root / "sources/849843/feed.json").read_bytes()
    statcast_bytes = (root / "sources/849843/statcast.csv").read_bytes()
    require(hashlib.sha256(feed_bytes).hexdigest() == FEED_SHA256, "feed_asset_changed")
    require(hashlib.sha256(statcast_bytes).hexdigest() == STATCAST_SHA256, "statcast_asset_changed")
    rows = list(csv.DictReader(io.StringIO(statcast_bytes.decode("utf-8-sig"))))
    result = project(rows, json.loads(feed_bytes), json.loads(game_bytes))
    require(result["source_pitch_count"] == 262, "wrong_game_count")
    return result


def serialize(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry-root", type=Path, required=True)
    parser.add_argument("--game", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    require(not args.out.resolve().is_relative_to(args.registry_root.resolve()), "output_inside_registry")
    require(args.out.resolve() != args.game.resolve(), "output_is_game_source")
    data = serialize(export_game(args.registry_root, args.game))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(data)
    print(json.dumps({"pitches": 262, "bytes": len(data), "sha256": hashlib.sha256(data).hexdigest()}))


if __name__ == "__main__":
    main()

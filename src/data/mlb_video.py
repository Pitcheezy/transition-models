"""Identity-checked MLB video manifests; never pair clips by list position."""

import hashlib
import json
from pathlib import Path
from uuid import UUID

import pandas as pd

PITCH_KEYS = ["game_pk", "at_bat_number", "pitch_number"]
PREPITCH_COLUMNS = [
    "game_date",
    "pitcher",
    "batter",
    "balls",
    "strikes",
    "outs_when_up",
    "inning",
    "inning_topbot",
    "on_1b",
    "on_2b",
    "on_3b",
    "stand",
    "p_throws",
    "home_score",
    "away_score",
    "home_team",
    "away_team",
]
TRUTH_COLUMNS = ["pitch_type", "description", "events", "plate_x", "plate_z", "zone"]


def feed_pitch_index(feed):
    """Read explicit PA/pitch numbers and play IDs from an official game feed."""
    rows = []
    for play in feed["liveData"]["plays"]["allPlays"]:
        for event in play["playEvents"]:
            if not event.get("isPitch"):
                continue
            play_id = str(UUID(event["playId"]))
            rows.append(
                {
                    "game_pk": int(feed["gamePk"]),
                    "at_bat_number": int(play["about"]["atBatIndex"]) + 1,
                    "pitch_number": int(event["pitchNumber"]),
                    "play_id": play_id,
                    "feed_pitch_type": event["details"].get("type", {}).get("code"),
                    "feed_batter": play["matchup"]["batter"]["id"],
                    "feed_pitcher": play["matchup"]["pitcher"]["id"],
                    "event_start_utc": event.get("startTime"),
                    "event_end_utc": event.get("endTime"),
                }
            )
    result = pd.DataFrame(rows)
    if result.empty:
        raise ValueError("No pitch events in MLB feed")
    if result.duplicated(PITCH_KEYS).any() or result.play_id.duplicated().any():
        raise ValueError("Duplicate pitch key or playId in MLB feed")
    return result


def build_game_manifest(statcast, feed):
    """Join by identity and corroborate player/type fields, with explicit missing rows."""
    game_pk = int(feed["gamePk"])
    frame = statcast.loc[statcast.game_pk == game_pk].copy()
    if frame.empty:
        raise ValueError("No Statcast rows for requested game")
    if frame[PITCH_KEYS].isna().any().any() or frame.duplicated(PITCH_KEYS).any():
        raise ValueError("Missing or duplicate Statcast pitch keys")
    index = feed_pitch_index(feed)
    joined = frame.merge(index, on=PITCH_KEYS, how="outer", validate="one_to_one", indicator=True)
    both = joined._merge.eq("both")
    conflicts = both & (
        joined.pitcher.ne(joined.feed_pitcher)
        | joined.batter.ne(joined.feed_batter)
        | (joined.feed_pitch_type.notna() & joined.pitch_type.ne(joined.feed_pitch_type))
    )
    # A row is usable only after both identity and independent metadata agree.
    records = []
    for _, row in joined.sort_values(PITCH_KEYS).iterrows():
        key = {k: int(row[k]) for k in PITCH_KEYS}
        if row["_merge"] != "both":
            status = "missing_feed" if row["_merge"] == "left_only" else "missing_statcast"
        elif conflicts.loc[row.name]:
            status = "metadata_conflict"
        else:
            status = "verified"
        play_id = None if pd.isna(row.get("play_id")) else row.play_id
        records.append(
            {
                **key,
                "identity_status": status,
                "pre_state": {k: _json_value(row.get(k)) for k in PREPITCH_COLUMNS},
                "ground_truth": {k: _json_value(row.get(k)) for k in TRUTH_COLUMNS},
                "video": {
                    "play_id": play_id,
                    "page_url": f"https://baseballsavant.mlb.com/sporty-videos?playId={play_id}"
                    if play_id
                    else None,
                    "event_start_utc": _json_value(row.get("event_start_utc")),
                    "event_end_utc": _json_value(row.get("event_end_utc")),
                    "broadcast_offset_seconds": None,
                    "pre_pitch_visible_seconds": None,
                    "inspection_status": "not_inspected",
                },
            }
        )
    counts = pd.Series([r["identity_status"] for r in records]).value_counts().to_dict()
    return {
        "schema": "mlb_video_manifest_v1",
        "game_pk": game_pk,
        "purpose": "development_and_demo; not a new held-out performance claim",
        "identity_method": "game_pk + atBatIndex+1 + pitchNumber, corroborated by players/type",
        "timing_note": "Feed event timestamps are not broadcast video offsets or release times.",
        "source": f"https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live",
        "counts": counts,
        "pitches": records,
    }


def _json_value(value):
    """Convert scalar data values to portable, strictly valid JSON values."""
    if value is None or pd.isna(value):
        return None
    return value.item() if hasattr(value, "item") else value


def write_game_manifest(statcast_path, feed_path, output):
    """Save source checksums and an auditable manifest without copying media."""
    feed_path, output = Path(feed_path), Path(output)
    feed = json.loads(feed_path.read_text(encoding="utf-8"))
    frame = pd.read_parquet(
        statcast_path,
        columns=PITCH_KEYS + PREPITCH_COLUMNS + TRUTH_COLUMNS,
        filters=[("game_pk", "==", int(feed["gamePk"]))],
    )
    manifest = build_game_manifest(frame, feed)
    manifest["feed_sha256"] = hashlib.sha256(feed_path.read_bytes()).hexdigest()
    # Hash only the selected source rows, independent of the absolute storage path.
    selected = frame.sort_values(PITCH_KEYS).to_json(orient="records", date_format="iso")
    manifest["statcast_rows_sha256"] = hashlib.sha256(selected.encode()).hexdigest()
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text(
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False), encoding="utf-8"
    )
    return manifest

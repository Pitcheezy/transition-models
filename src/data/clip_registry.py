"""Per-pitch official clip registry: identity-checked metadata, private clips, one SQLite file.

Clips are paired only through the official feed playId that ``build_game_manifest`` has
corroborated with Statcast (game, PA and pitch numbers, players, pitch type); never by list
position or file order. Pre-pitch state and post-pitch outcomes live in separate tables so a
later analysis cannot read a result as a pre-pitch input. Video and page bytes stay outside Git.
"""

from __future__ import annotations

import hashlib
import io
import json
import math
import shutil
import sqlite3
import subprocess
import time
from datetime import UTC, datetime
from pathlib import Path
from urllib.request import HTTPRedirectHandler, Request, build_opener

import pandas as pd

from src.data.mlb_sources import media_urls, validate_mlb_url
from src.data.mlb_video import PITCH_KEYS, PREPITCH_COLUMNS, TRUTH_COLUMNS, build_game_manifest

SCHEMA = "pitcheezy-clip-registry-v1"
FEED_URL = "https://statsapi.mlb.com/api/v1.1/game/{game_pk}/feed/live"
STATCAST_URL = (
    "https://baseballsavant.mlb.com/statcast_search/csv?all=true&type=details&game_pk={game_pk}"
)
PAGE_URL = "https://baseballsavant.mlb.com/sporty-videos?playId={play_id}"
SPLITS = ("dev", "eval_locked")
OUTCOME_EXTRA = ["release_speed", "type", "bb_type", "launch_speed", "launch_angle"]
USER_AGENT = "SmartPitch-clip-registry/1.0"
PAGE_LIMIT = 5_000_000
CLIP_LIMIT = 80_000_000
SOURCE_LIMIT = 40_000_000

TABLES = """
CREATE TABLE IF NOT EXISTS meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS games (
  game_pk INTEGER PRIMARY KEY, split TEXT NOT NULL, official_date TEXT, season TEXT,
  game_type TEXT, away_team TEXT, home_team TEXT, away_abbr TEXT, home_abbr TEXT, venue TEXT,
  feed_sha256 TEXT NOT NULL, statcast_sha256 TEXT NOT NULL, manifest_sha256 TEXT NOT NULL,
  verified INTEGER NOT NULL, issues INTEGER NOT NULL, registered_utc TEXT NOT NULL
);
CREATE TABLE IF NOT EXISTS pitches (
  play_id TEXT PRIMARY KEY, game_pk INTEGER NOT NULL REFERENCES games(game_pk),
  at_bat_number INTEGER NOT NULL, pitch_number INTEGER NOT NULL, game_date TEXT,
  inning INTEGER, inning_topbot TEXT, pitcher_id INTEGER, pitcher_name TEXT, p_throws TEXT,
  batter_id INTEGER, batter_name TEXT, stand TEXT, balls INTEGER, strikes INTEGER,
  outs_when_up INTEGER, on_1b INTEGER, on_2b INTEGER, on_3b INTEGER, home_score INTEGER,
  away_score INTEGER, home_team TEXT, away_team TEXT,
  UNIQUE (game_pk, at_bat_number, pitch_number)
);
CREATE TABLE IF NOT EXISTS outcomes (
  play_id TEXT PRIMARY KEY REFERENCES pitches(play_id), pitch_type TEXT, release_speed REAL,
  plate_x REAL, plate_z REAL, zone INTEGER, description TEXT, events TEXT, type TEXT,
  bb_type TEXT, launch_speed REAL, launch_angle REAL
);
CREATE TABLE IF NOT EXISTS identity_issues (
  game_pk INTEGER NOT NULL, at_bat_number INTEGER NOT NULL, pitch_number INTEGER NOT NULL,
  status TEXT NOT NULL, play_id TEXT, PRIMARY KEY (game_pk, at_bat_number, pitch_number)
);
CREATE TABLE IF NOT EXISTS clips (
  play_id TEXT PRIMARY KEY REFERENCES pitches(play_id), status TEXT NOT NULL,
  attempts INTEGER NOT NULL DEFAULT 0, last_error TEXT, page_path TEXT, page_sha256 TEXT,
  page_retrieved_utc TEXT, media_candidates TEXT, media_url TEXT, file_path TEXT,
  file_sha256 TEXT, bytes INTEGER, duration_s REAL, r_frame_rate TEXT, avg_frame_rate TEXT,
  time_base TEXT, start_time_s REAL, width INTEGER, height INTEGER, codec TEXT,
  downloaded_utc TEXT
);
"""


def now():
    return datetime.now(UTC).isoformat(timespec="seconds")


def sha256(data):
    return hashlib.sha256(data).hexdigest()


def connect(db_path):
    db_path = Path(db_path)
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON")
    conn.executescript(TABLES)
    conn.execute("INSERT OR IGNORE INTO meta VALUES ('schema', ?)", (SCHEMA,))
    stored = conn.execute("SELECT value FROM meta WHERE key = 'schema'").fetchone()[0]
    if stored != SCHEMA:
        raise ValueError(f"registry schema {stored!r} is not {SCHEMA!r}")
    conn.commit()
    return conn


class MlbOnlyRedirect(HTTPRedirectHandler):
    """Refuse a redirect before it is followed unless the next hop is HTTPS on mlb.com."""

    def redirect_request(self, req, fp, code, msg, headers, newurl):
        validate_mlb_url(newurl)
        return super().redirect_request(req, fp, code, msg, headers, newurl)


_OPENER = build_opener(MlbOnlyRedirect)


def safe_open(request, timeout):
    return _OPENER.open(request, timeout=timeout)


def fetch(url, limit, opener=safe_open, timeout=60):
    """Read at most ``limit`` bytes from an HTTPS mlb.com URL; every redirect hop stays on mlb.com."""
    validate_mlb_url(url)
    with opener(Request(url, headers={"User-Agent": USER_AGENT}), timeout=timeout) as response:
        validate_mlb_url(response.url)
        data = response.read(limit + 1)
    if len(data) > limit:
        raise ValueError("response exceeds size limit")
    return data


def write_once(path, data):
    """Write new bytes; an existing file must already hold exactly these bytes."""
    path = Path(path)
    if path.exists():
        if path.read_bytes() != data:
            raise ValueError(f"refusing to overwrite different bytes at {path.name}")
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".part")
    tmp.write_bytes(data)
    tmp.replace(path)


def game_meta(feed):
    data = feed["gameData"]
    teams = data["teams"]
    return {
        "official_date": data.get("datetime", {}).get("officialDate"),
        "season": str(data.get("game", {}).get("season") or ""),
        "game_type": data.get("game", {}).get("type"),
        "away_team": teams["away"].get("name"),
        "home_team": teams["home"].get("name"),
        "away_abbr": teams["away"].get("abbreviation"),
        "home_abbr": teams["home"].get("abbreviation"),
        "venue": data.get("venue", {}).get("name"),
    }


def player_names(feed):
    return {
        int(p["id"]): p.get("fullName")
        for p in feed["gameData"].get("players", {}).values()
        if "id" in p
    }


def read_statcast_csv(data):
    frame = pd.read_csv(io.BytesIO(data), low_memory=False)
    missing = [c for c in PITCH_KEYS + PREPITCH_COLUMNS + TRUTH_COLUMNS if c not in frame.columns]
    if missing:
        raise ValueError(f"Statcast CSV lacks columns: {missing}")
    return frame


def _value(row, key):
    value = row.get(key) if row is not None else None
    if value is None or (not isinstance(value, str) and pd.isna(value)):
        return None
    return value.item() if hasattr(value, "item") else value


def _occupied(value):
    return None if value is None else int(value)


def register_game(conn, root, game_pk, split, feed_bytes, statcast, statcast_sha):
    """Store one identity-checked game; re-registering must reproduce the same manifest."""
    if split not in SPLITS:
        raise ValueError(f"split must be one of {SPLITS}")
    feed = json.loads(feed_bytes)
    if int(feed["gamePk"]) != int(game_pk):
        raise ValueError("feed gamePk does not match the requested game")
    manifest = build_game_manifest(statcast, feed)
    manifest["feed_sha256"] = sha256(feed_bytes)
    manifest["statcast_sha256"] = statcast_sha
    manifest_bytes = (
        json.dumps(manifest, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode()
    root = Path(root)
    existing = conn.execute(
        "SELECT manifest_sha256, split FROM games WHERE game_pk = ?", (game_pk,)
    ).fetchone()
    # Check the registry before touching disk, so a refused call leaves no file behind.
    if existing and existing != (sha256(manifest_bytes), split):
        raise ValueError("game already registered with a different manifest or split")
    write_once(root / "manifests" / f"{game_pk}.json", manifest_bytes)
    if existing:
        return manifest["counts"]
    names = player_names(feed)
    keyed = statcast.loc[statcast.game_pk == int(game_pk)].set_index(PITCH_KEYS)
    verified = [r for r in manifest["pitches"] if r["identity_status"] == "verified"]
    issues = [r for r in manifest["pitches"] if r["identity_status"] != "verified"]
    meta = game_meta(feed)
    with conn:
        conn.execute(
            "INSERT INTO games VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
            (
                int(game_pk),
                split,
                meta["official_date"],
                meta["season"],
                meta["game_type"],
                meta["away_team"],
                meta["home_team"],
                meta["away_abbr"],
                meta["home_abbr"],
                meta["venue"],
                manifest["feed_sha256"],
                statcast_sha,
                sha256(manifest_bytes),
                len(verified),
                len(issues),
                now(),
            ),
        )
        for r in verified:
            pre, truth = r["pre_state"], r["ground_truth"]
            key = (r["game_pk"], r["at_bat_number"], r["pitch_number"])
            row = keyed.loc[key] if key in keyed.index else None
            play_id = r["video"]["play_id"]
            conn.execute(
                "INSERT INTO pitches VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    play_id,
                    *key,
                    pre["game_date"],
                    pre["inning"],
                    pre["inning_topbot"],
                    pre["pitcher"],
                    names.get(pre["pitcher"]),
                    pre["p_throws"],
                    pre["batter"],
                    names.get(pre["batter"]),
                    pre["stand"],
                    pre["balls"],
                    pre["strikes"],
                    pre["outs_when_up"],
                    _occupied(pre["on_1b"]),
                    _occupied(pre["on_2b"]),
                    _occupied(pre["on_3b"]),
                    pre["home_score"],
                    pre["away_score"],
                    pre["home_team"],
                    pre["away_team"],
                ),
            )
            conn.execute(
                "INSERT INTO outcomes VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    play_id,
                    truth["pitch_type"],
                    _value(row, "release_speed"),
                    truth["plate_x"],
                    truth["plate_z"],
                    truth["zone"],
                    truth["description"],
                    truth["events"],
                    _value(row, "type"),
                    _value(row, "bb_type"),
                    _value(row, "launch_speed"),
                    _value(row, "launch_angle"),
                ),
            )
            conn.execute("INSERT INTO clips (play_id, status) VALUES (?, 'pending')", (play_id,))
        for r in issues:
            conn.execute(
                "INSERT INTO identity_issues VALUES (?,?,?,?,?)",
                (
                    r["game_pk"],
                    r["at_bat_number"],
                    r["pitch_number"],
                    r["identity_status"],
                    r["video"]["play_id"],
                ),
            )
    return manifest["counts"]


def probe_file(path):
    """Read stream timing of a saved clip with ffprobe (no network)."""
    result = subprocess.run(
        [
            "ffprobe",
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_entries",
            "stream=codec_name,width,height,r_frame_rate,avg_frame_rate,time_base,start_time:"
            "format=duration",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        text=True,
        timeout=60,
        check=True,
    )
    data = json.loads(result.stdout)
    stream = (data.get("streams") or [{}])[0]
    duration = data.get("format", {}).get("duration")
    start = stream.get("start_time")
    return {
        "codec": stream.get("codec_name"),
        "width": stream.get("width"),
        "height": stream.get("height"),
        "r_frame_rate": stream.get("r_frame_rate"),
        "avg_frame_rate": stream.get("avg_frame_rate"),
        "time_base": stream.get("time_base"),
        "start_time_s": float(start) if start not in (None, "N/A") else None,
        "duration_s": float(duration) if duration not in (None, "N/A") else None,
    }


def clip_name(game_pk, at_bat_number, pitch_number, play_id):
    return f"clips/{game_pk}/{at_bat_number:03d}_{pitch_number:02d}_{play_id}.mp4"


def fetch_clip(conn, root, play_id, *, opener=safe_open, probe=probe_file, pause=lambda: None):
    """Fetch one official page and the mp4 it shows; record success or the reason it failed.

    ``pause`` runs between the page request and the media request so each request is paced.
    """
    root = Path(root)
    game_pk, ab, pn = conn.execute(
        "SELECT game_pk, at_bat_number, pitch_number FROM pitches WHERE play_id = ?", (play_id,)
    ).fetchone()
    conn.execute("UPDATE clips SET attempts = attempts + 1 WHERE play_id = ?", (play_id,))
    conn.commit()
    fields = {}
    try:
        page = fetch(PAGE_URL.format(play_id=play_id), PAGE_LIMIT, opener)
        # Pages change between visits; a content-addressed name never collides, even after the
        # registry file is rebuilt over an existing root.
        page_path = f"pages/{game_pk}/{play_id}.{sha256(page)[:12]}.html"
        write_once(root / page_path, page)
        candidates = media_urls(page.decode("utf-8", errors="replace"))
        fields = {
            "page_path": page_path,
            "page_sha256": sha256(page),
            "page_retrieved_utc": now(),
            "media_candidates": json.dumps(candidates),
        }
        if not candidates:
            _update(
                conn, play_id, status="no_media", last_error="no official mp4 on page", **fields
            )
            return "no_media"
        if len(set(candidates)) > 1:
            _update(
                conn,
                play_id,
                status="ambiguous_media",
                last_error=f"{len(set(candidates))} different mp4 URLs on page",
                **fields,
            )
            return "ambiguous_media"
        fields["media_url"] = candidates[0]
        pause()
        media = fetch(candidates[0], CLIP_LIMIT, opener, timeout=120)
        name = clip_name(game_pk, ab, pn, play_id)
        final = root / name
        if final.exists():
            if final.read_bytes() != media:
                raise ValueError(f"refusing to overwrite different bytes at {final.name}")
            info = probe(final)
        else:
            # Probe before the file takes its final name, so a broken body never blocks a retry.
            final.parent.mkdir(parents=True, exist_ok=True)
            tmp = final.with_suffix(".mp4.part")
            tmp.write_bytes(media)
            try:
                info = probe(tmp)
            except BaseException:
                tmp.unlink(missing_ok=True)
                raise
            tmp.replace(final)
        _update(
            conn,
            play_id,
            status="downloaded",
            last_error=None,
            file_path=name,
            file_sha256=sha256(media),
            bytes=len(media),
            downloaded_utc=now(),
            **fields,
            **info,
        )
        return "downloaded"
    except Exception as exc:  # recorded per clip; the run decides whether to stop
        _update(
            conn,
            play_id,
            status="failed",
            last_error=f"{type(exc).__name__}: {exc}"[:500],
            **fields,
        )
        return "failed"
    except BaseException:
        # An interrupt is not an attempt: give it back and keep the row retryable.
        conn.execute(
            "UPDATE clips SET attempts = attempts - 1, last_error = 'interrupted' "
            "WHERE play_id = ?",
            (play_id,),
        )
        conn.commit()
        raise


def _update(conn, play_id, **fields):
    columns = ", ".join(f"{k} = ?" for k in fields)
    conn.execute(f"UPDATE clips SET {columns} WHERE play_id = ?", (*fields.values(), play_id))
    conn.commit()


def verify_downloaded(conn, root, play_id):
    """A downloaded row counts only if the file still has the recorded size and SHA."""
    row = conn.execute(
        "SELECT file_path, file_sha256, bytes FROM clips WHERE play_id = ? AND status = 'downloaded'",
        (play_id,),
    ).fetchone()
    if not row:
        return False
    path = Path(root) / row[0]
    return path.is_file() and path.stat().st_size == row[2] and sha256(path.read_bytes()) == row[1]


def run_clips(
    conn,
    root,
    *,
    games=None,
    limit=None,
    delay=1.0,
    max_attempts=2,
    max_consecutive_failures=8,
    max_consecutive_no_media=8,
    retry_no_media=False,
    opener=safe_open,
    probe=probe_file,
    sleep=time.sleep,
):
    """Sequential fetch with ``delay`` before every request; stops on repeated bad results.

    A run of pages without a video is treated like a run of failures (a block or interstitial
    page also has no video), and ``retry_no_media`` re-selects those rows in a later run.
    """
    if not isinstance(delay, (int, float)) or not math.isfinite(delay) or delay < 0:
        raise ValueError("delay must be a finite, non-negative number of seconds")
    if probe is probe_file and shutil.which("ffprobe") is None:
        raise RuntimeError("ffprobe is required before any clip is downloaded")
    states = ("pending", "failed", "no_media") if retry_no_media else ("pending", "failed")
    query = (
        "SELECT p.play_id FROM pitches p JOIN clips c USING (play_id) "
        f"WHERE c.status IN ({','.join('?' * len(states))}) AND c.attempts < ?"
    )
    args = [*states, max_attempts]
    if games:
        query += f" AND p.game_pk IN ({','.join('?' * len(games))})"
        args += [int(g) for g in games]
    query += " ORDER BY p.game_pk, p.at_bat_number, p.pitch_number"
    todo = [r[0] for r in conn.execute(query, args)]
    if limit is not None:
        todo = todo[:limit]
    counts, failures, empties = {}, 0, 0
    for i, play_id in enumerate(todo):
        if i:
            sleep(delay)
        result = fetch_clip(
            conn, root, play_id, opener=opener, probe=probe, pause=lambda: sleep(delay)
        )
        counts[result] = counts.get(result, 0) + 1
        failures = failures + 1 if result == "failed" else 0
        empties = empties + 1 if result == "no_media" else 0
        if failures >= max_consecutive_failures:
            counts["stopped_after_consecutive_failures"] = failures
            break
        if empties >= max_consecutive_no_media:
            counts["stopped_after_consecutive_no_media"] = empties
            break
    return counts


def status(conn, root=None):
    """Counts per game; with ``root`` a downloaded row counts only if its file still verifies."""
    rows = conn.execute(
        "SELECT g.game_pk, g.split, g.official_date, g.away_abbr, g.home_abbr, g.verified, "
        "g.issues, c.status, c.play_id, COALESCE(c.bytes, 0) "
        "FROM games g LEFT JOIN pitches p USING (game_pk) LEFT JOIN clips c USING (play_id) "
        "ORDER BY g.game_pk"
    ).fetchall()
    games = {}
    for pk, split, date, away, home, verified, issues, state, play_id, size in rows:
        entry = games.setdefault(
            pk,
            {
                "split": split,
                "date": date,
                "matchup": f"{away}@{home}",
                "verified": verified,
                "identity_issues": issues,
                "clips": {},
                "bytes": 0,
                "files_checked": root is not None,
            },
        )
        if not state:
            continue
        if (
            state == "downloaded"
            and root is not None
            and not verify_downloaded(conn, root, play_id)
        ):
            state = "downloaded_missing_or_changed"
        entry["clips"][state] = entry["clips"].get(state, 0) + 1
        if state == "downloaded":
            entry["bytes"] += size
    return {"schema": SCHEMA, "games": games}

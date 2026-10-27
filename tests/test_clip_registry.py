"""Clip registry: identity-checked rows, separate pre/post tables, bounded and honest fetching."""

import io
import json
import sqlite3

import pandas as pd
import pytest

from src.data import clip_registry as reg

PLAY_IDS = [
    "11111111-1111-4111-8111-111111111111",
    "22222222-2222-4222-8222-222222222222",
    "33333333-3333-4333-8333-333333333333",
]


def feed(game_pk=900001, pitch_type_override=None):
    events = []
    for n, play_id in enumerate(PLAY_IDS[:2], start=1):
        events.append(
            {
                "isPitch": True,
                "playId": play_id,
                "pitchNumber": n,
                "details": {"type": {"code": pitch_type_override or "FF"}},
                "startTime": "2025-10-01T00:00:00Z",
                "endTime": "2025-10-01T00:00:03Z",
            }
        )
    return {
        "gamePk": game_pk,
        "gameData": {
            "datetime": {"officialDate": "2025-10-01"},
            "game": {"season": "2025", "type": "F"},
            "teams": {
                "away": {"name": "Away Club", "abbreviation": "AWY"},
                "home": {"name": "Home Club", "abbreviation": "HOM"},
            },
            "venue": {"name": "Synthetic Park"},
            "players": {
                "ID10": {"id": 10, "fullName": "Pitcher Ten"},
                "ID20": {"id": 20, "fullName": "Batter Twenty"},
            },
        },
        "liveData": {
            "plays": {
                "allPlays": [
                    {
                        "about": {"atBatIndex": 0},
                        "matchup": {"batter": {"id": 20}, "pitcher": {"id": 10}},
                        "playEvents": events + [{"isPitch": False}],
                    }
                ]
            }
        },
    }


def statcast(game_pk=900001, rows=2):
    base = {
        "game_pk": game_pk,
        "at_bat_number": 1,
        "game_date": "2025-10-01",
        "pitcher": 10,
        "batter": 20,
        "outs_when_up": 0,
        "inning": 1,
        "inning_topbot": "Top",
        "on_1b": None,
        "on_2b": None,
        "on_3b": 30.0,
        "stand": "R",
        "p_throws": "L",
        "home_score": 0,
        "away_score": 0,
        "home_team": "HOM",
        "away_team": "AWY",
        "pitch_type": "FF",
        "events": None,
        "zone": 5,
        "release_speed": 95.1,
        "type": "S",
        "bb_type": None,
        "launch_speed": None,
        "launch_angle": None,
    }
    data = [
        {
            **base,
            "pitch_number": 1,
            "balls": 0,
            "strikes": 0,
            "description": "called_strike",
            "plate_x": -0.1,
            "plate_z": 2.4,
        },
        {
            **base,
            "pitch_number": 2,
            "balls": 0,
            "strikes": 1,
            "description": "hit_into_play",
            "plate_x": 0.3,
            "plate_z": 2.9,
            "type": "X",
            "bb_type": "fly_ball",
            "launch_speed": 99.0,
            "launch_angle": 31.0,
            "events": "flyout",
        },
    ][:rows]
    return pd.DataFrame(data)


def register(tmp_path, **kwargs):
    conn = reg.connect(tmp_path / "registry.sqlite")
    data = json.dumps(feed(**kwargs)).encode()
    counts = reg.register_game(conn, tmp_path, 900001, "dev", data, statcast(), "c" * 64)
    return conn, counts, data


def test_verified_pitches_land_in_separate_pre_and_post_tables(tmp_path):
    conn, counts, _ = register(tmp_path)
    assert counts == {"verified": 2}
    game = conn.execute("SELECT split, away_abbr, home_abbr, venue, verified FROM games").fetchone()
    assert game == ("dev", "AWY", "HOM", "Synthetic Park", 2)
    pre = conn.execute(
        "SELECT play_id, pitcher_name, batter_name, balls, strikes, on_3b FROM pitches ORDER BY pitch_number"
    ).fetchall()
    assert pre[0] == (PLAY_IDS[0], "Pitcher Ten", "Batter Twenty", 0, 0, 30)
    pre_columns = {r[1] for r in conn.execute("PRAGMA table_info(pitches)")}
    assert not pre_columns & {"description", "plate_x", "plate_z", "events", "zone", "bb_type"}
    post = conn.execute(
        "SELECT play_id, description, bb_type, launch_angle FROM outcomes WHERE play_id = ?",
        (PLAY_IDS[1],),
    ).fetchone()
    assert post == (PLAY_IDS[1], "hit_into_play", "fly_ball", 31.0)
    assert conn.execute("SELECT COUNT(*) FROM clips WHERE status = 'pending'").fetchone()[0] == 2
    assert (tmp_path / "manifests" / "900001.json").is_file()


def test_identity_conflicts_are_kept_out_of_the_pitch_table(tmp_path):
    conn, counts, _ = register(tmp_path, pitch_type_override="SL")
    assert counts == {"metadata_conflict": 2}
    assert conn.execute("SELECT COUNT(*) FROM pitches").fetchone()[0] == 0
    issues = conn.execute("SELECT status FROM identity_issues").fetchall()
    assert issues == [("metadata_conflict",), ("metadata_conflict",)]


def test_reregistering_is_idempotent_but_a_changed_split_or_manifest_is_refused(tmp_path):
    conn, _, data = register(tmp_path)
    assert reg.register_game(conn, tmp_path, 900001, "dev", data, statcast(), "c" * 64) == {
        "verified": 2
    }
    with pytest.raises(ValueError, match="different manifest or split"):
        reg.register_game(conn, tmp_path, 900001, "eval_locked", data, statcast(), "c" * 64)
    with pytest.raises(ValueError, match="overwrite different bytes"):
        reg.register_game(conn, tmp_path, 900001, "dev", data, statcast(rows=1), "c" * 64)
    with pytest.raises(ValueError, match="split must be"):
        reg.register_game(conn, tmp_path, 900001, "test", data, statcast(), "c" * 64)
    with pytest.raises(ValueError, match="gamePk"):
        reg.register_game(conn, tmp_path, 900002, "dev", data, statcast(), "c" * 64)


class Response(io.BytesIO):
    def __init__(self, data, url):
        super().__init__(data)
        self.url = url

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False


def opener_for(pages, media, calls):
    def opener(request, timeout):
        url = request.full_url
        calls.append(url)
        if url in media:
            payload = media[url]
            if isinstance(payload, Exception):
                raise payload
            return Response(payload, url)
        play_id = url.rsplit("=", 1)[1]
        page = pages[play_id]
        if isinstance(page, Exception):
            raise page
        return Response(page.encode(), url)

    return opener


def fake_probe(path):
    return {
        "codec": "h264",
        "width": 1280,
        "height": 720,
        "r_frame_rate": "60000/1001",
        "avg_frame_rate": "60000/1001",
        "time_base": "1/60000",
        "start_time_s": 0.0,
        "duration_s": 7.0,
    }


def test_clip_fetch_records_hashes_and_pairs_only_by_play_id(tmp_path):
    conn, _, _ = register(tmp_path)
    url0 = f"https://sporty-clips.mlb.com/{PLAY_IDS[0]}.mp4"
    pages = {PLAY_IDS[0]: f'<video src="{url0}"></video>', PLAY_IDS[1]: "<p>no video</p>"}
    calls, sleeps = [], []
    counts = reg.run_clips(
        conn,
        tmp_path,
        opener=opener_for(pages, {url0: b"mp4-bytes"}, calls),
        probe=fake_probe,
        sleep=sleeps.append,
        delay=1.0,
    )
    assert counts == {"downloaded": 1, "no_media": 1}
    assert sleeps == [1.0]
    row = conn.execute(
        "SELECT status, file_path, file_sha256, bytes, time_base, media_url FROM clips WHERE play_id = ?",
        (PLAY_IDS[0],),
    ).fetchone()
    assert row[0] == "downloaded" and row[1] == f"clips/900001/001_01_{PLAY_IDS[0]}.mp4"
    assert row[2] == reg.sha256(b"mp4-bytes") and row[3] == 9 and row[4] == "1/60000"
    assert row[5] == url0
    assert reg.verify_downloaded(conn, tmp_path, PLAY_IDS[0])
    (tmp_path / row[1]).write_bytes(b"tampered")
    assert not reg.verify_downloaded(conn, tmp_path, PLAY_IDS[0])
    assert conn.execute(
        "SELECT status FROM clips WHERE play_id = ?", (PLAY_IDS[1],)
    ).fetchone() == ("no_media",)
    again = reg.run_clips(
        conn, tmp_path, opener=opener_for(pages, {}, calls), probe=fake_probe, sleep=sleeps.append
    )
    assert again == {}


def test_failures_are_recorded_bounded_and_stop_a_run(tmp_path):
    conn, _, _ = register(tmp_path)
    boom = OSError("network down")
    pages = {PLAY_IDS[0]: boom, PLAY_IDS[1]: boom}
    calls = []
    counts = reg.run_clips(
        conn,
        tmp_path,
        opener=opener_for(pages, {}, calls),
        probe=fake_probe,
        sleep=lambda _: None,
        max_consecutive_failures=2,
    )
    assert counts == {"failed": 2, "stopped_after_consecutive_failures": 2}
    rows = conn.execute("SELECT status, attempts, last_error FROM clips").fetchall()
    assert all(r[0] == "failed" and r[1] == 1 and "network down" in r[2] for r in rows)
    reg.run_clips(
        conn, tmp_path, opener=opener_for(pages, {}, calls), probe=fake_probe, sleep=lambda _: None
    )
    assert conn.execute("SELECT MAX(attempts) FROM clips").fetchone()[0] == 2
    assert (
        reg.run_clips(
            conn,
            tmp_path,
            opener=opener_for(pages, {}, calls),
            probe=fake_probe,
            sleep=lambda _: None,
        )
        == {}
    )


def test_off_site_media_and_redirects_are_refused(tmp_path):
    conn, _, _ = register(tmp_path)
    evil = "https://example.com/clip.mp4"
    pages = {PLAY_IDS[0]: f'<video src="{evil}"></video>', PLAY_IDS[1]: "<p></p>"}
    counts = reg.run_clips(
        conn, tmp_path, opener=opener_for(pages, {}, []), probe=fake_probe, sleep=lambda _: None
    )
    assert counts == {"no_media": 2}
    with pytest.raises(ValueError, match="mlb.com"):
        reg.fetch("http://statsapi.mlb.com/api", 10)


def test_schema_mismatch_is_refused(tmp_path):
    path = tmp_path / "registry.sqlite"
    reg.connect(path).close()
    with sqlite3.connect(path) as conn:
        conn.execute("UPDATE meta SET value = 'other' WHERE key = 'schema'")
    with pytest.raises(ValueError, match="schema"):
        reg.connect(path)


def test_status_counts_clips_per_game(tmp_path):
    conn, _, _ = register(tmp_path)
    summary = reg.status(conn)
    game = summary["games"][900001]
    assert game["matchup"] == "AWY@HOM" and game["clips"] == {"pending": 2}


def test_a_retry_keeps_its_own_page_snapshot_when_the_page_changed(tmp_path):
    conn, _, _ = register(tmp_path)
    url0 = f"https://sporty-clips.mlb.com/{PLAY_IDS[0]}.mp4"
    first = {PLAY_IDS[0]: f'<video src="{url0}"></video> v1', PLAY_IDS[1]: "<p></p>"}
    media_error = {url0: OSError("reset")}
    reg.run_clips(
        conn,
        tmp_path,
        games=[900001],
        limit=1,
        opener=opener_for(first, media_error, []),
        probe=fake_probe,
        sleep=lambda _: None,
    )
    assert conn.execute(
        "SELECT status, attempts FROM clips WHERE play_id = ?", (PLAY_IDS[0],)
    ).fetchone() == (
        "failed",
        1,
    )
    changed = {PLAY_IDS[0]: f'<video src="{url0}"></video> v2', PLAY_IDS[1]: "<p></p>"}
    reg.run_clips(
        conn,
        tmp_path,
        games=[900001],
        limit=1,
        opener=opener_for(changed, {url0: b"mp4"}, []),
        probe=fake_probe,
        sleep=lambda _: None,
    )
    row = conn.execute(
        "SELECT status, attempts, page_path FROM clips WHERE play_id = ?", (PLAY_IDS[0],)
    ).fetchone()
    assert row == ("downloaded", 2, f"pages/900001/{PLAY_IDS[0]}.a2.html")
    assert (tmp_path / f"pages/900001/{PLAY_IDS[0]}.html").read_text().endswith("v1")
    assert (tmp_path / row[2]).read_text().endswith("v2")

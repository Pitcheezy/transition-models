"""Clip registry: identity-checked rows, separate pre/post tables, bounded and honest fetching."""

import email.message
import importlib.util
import io
import json
import sqlite3
import subprocess
import urllib.request
import urllib.response
from pathlib import Path

import pandas as pd
import pytest

from src.data import clip_registry as reg

ROOT = Path(__file__).resolve().parents[1]

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
    with pytest.raises(ValueError, match="different manifest or split"):
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
            if isinstance(payload, BaseException):
                raise payload
            return Response(payload, url)
        play_id = url.rsplit("=", 1)[1]
        page = pages[play_id]
        if isinstance(page, BaseException):
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
    calls = []
    counts = reg.run_clips(
        conn,
        tmp_path,
        opener=opener_for(pages, {url0: b"mp4-bytes"}, calls),
        probe=fake_probe,
        sleep=lambda d: calls.append(("sleep", d)),
        delay=1.0,
    )
    assert counts == {"downloaded": 1, "no_media": 1}
    # Every request after the first waits: page, pause, media, pause, next page.
    assert calls == [
        reg.PAGE_URL.format(play_id=PLAY_IDS[0]),
        ("sleep", 1.0),
        url0,
        ("sleep", 1.0),
        reg.PAGE_URL.format(play_id=PLAY_IDS[1]),
    ]
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
        conn, tmp_path, opener=opener_for(pages, {}, calls), probe=fake_probe, sleep=calls.append
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


def page_name(play_id, page):
    return f"pages/900001/{play_id}.{reg.sha256(page.encode())[:12]}.html"


def clip_row(conn, play_id, columns):
    return conn.execute(f"SELECT {columns} FROM clips WHERE play_id = ?", (play_id,)).fetchone()


def test_a_retry_keeps_its_own_page_snapshot_and_a_failure_keeps_its_page_fields(tmp_path):
    conn, _, _ = register(tmp_path)
    url0 = f"https://sporty-clips.mlb.com/{PLAY_IDS[0]}.mp4"
    v1, v2 = f'<video src="{url0}"></video> v1', f'<video src="{url0}"></video> v2'
    run = dict(games=[900001], limit=1, probe=fake_probe, sleep=lambda _: None)
    first = opener_for({PLAY_IDS[0]: v1}, {url0: OSError("reset")}, [])
    reg.run_clips(conn, tmp_path, opener=first, **run)
    columns = "status, attempts, page_path, page_sha256, media_candidates, media_url"
    assert clip_row(conn, PLAY_IDS[0], columns) == (
        "failed",
        1,
        page_name(PLAY_IDS[0], v1),
        reg.sha256(v1.encode()),
        json.dumps([url0]),
        url0,
    )
    reg.run_clips(conn, tmp_path, opener=opener_for({PLAY_IDS[0]: v2}, {url0: b"mp4"}, []), **run)
    row = clip_row(conn, PLAY_IDS[0], "status, attempts, page_path")
    assert row == ("downloaded", 2, page_name(PLAY_IDS[0], v2))
    assert (tmp_path / page_name(PLAY_IDS[0], v1)).read_text().endswith("v1")
    assert (tmp_path / row[2]).read_text().endswith("v2")


class FakeHttps(urllib.request.BaseHandler):
    """Answers HTTPS requests from a route table so redirects run through the real handler chain."""

    handler_order = 100  # ahead of the stdlib HTTPS handler, so nothing reaches the network

    def __init__(self, routes):
        self.routes, self.seen = routes, []

    def https_open(self, req):
        self.seen.append(req.full_url)
        code, location, body = self.routes[req.full_url]
        headers = email.message.Message()
        if location:
            headers["Location"] = location
        response = urllib.response.addinfourl(io.BytesIO(body), headers, req.full_url, code)
        response.msg = "fake"
        return response


def opener_through(routes):
    fake = FakeHttps(routes)
    chain = urllib.request.build_opener(reg.MlbOnlyRedirect, fake)
    return fake, lambda request, timeout: chain.open(request, timeout=timeout)


def test_off_site_media_is_ignored(tmp_path):
    conn, _, _ = register(tmp_path)
    evil = "https://example.com/clip.mp4"
    pages = {PLAY_IDS[0]: f'<video src="{evil}"></video>', PLAY_IDS[1]: "<p></p>"}
    counts = reg.run_clips(
        conn, tmp_path, opener=opener_for(pages, {}, []), probe=fake_probe, sleep=lambda _: None
    )
    assert counts == {"no_media": 2}
    with pytest.raises(ValueError, match="mlb.com"):
        reg.fetch("http://statsapi.mlb.com/api", 10)


def test_an_off_site_redirect_is_refused_before_it_is_followed():
    start = "https://statsapi.mlb.com/a"
    fake, opener = opener_through(
        {
            start: (302, "https://example.com/b", b""),
            "https://example.com/b": (200, None, b"never"),
        }
    )
    with pytest.raises(ValueError, match="mlb.com"):
        reg.fetch(start, 100, opener=opener)
    assert fake.seen == [start]
    assert any(isinstance(h, reg.MlbOnlyRedirect) for h in reg._OPENER.handlers)


def test_an_on_site_redirect_is_followed_and_the_final_url_is_checked():
    start, hop = "https://statsapi.mlb.com/a", "https://cdn.mlb.com/b"
    fake, opener = opener_through({start: (302, hop, b""), hop: (200, None, b"body")})
    assert reg.fetch(start, 100, opener=opener) == b"body"
    assert fake.seen == [start, hop]

    def lands_off_site(request, timeout):
        return Response(b"x", "https://example.com/elsewhere")

    with pytest.raises(ValueError, match="mlb.com"):
        reg.fetch(start, 100, opener=lands_off_site)


def test_size_limit_is_enforced():
    def big(request, timeout):
        return Response(b"x" * 11, request.full_url)

    with pytest.raises(ValueError, match="size limit"):
        reg.fetch("https://statsapi.mlb.com/a", 10, opener=big)


def test_status_counts_a_downloaded_row_only_while_its_file_verifies(tmp_path):
    conn, _, _ = register(tmp_path)
    url0 = f"https://sporty-clips.mlb.com/{PLAY_IDS[0]}.mp4"
    pages = {PLAY_IDS[0]: f'<video src="{url0}"></video>', PLAY_IDS[1]: "<p></p>"}
    reg.run_clips(
        conn,
        tmp_path,
        opener=opener_for(pages, {url0: b"mp4-bytes"}, []),
        probe=fake_probe,
        sleep=lambda _: None,
    )
    checked = reg.status(conn, tmp_path)["games"][900001]
    assert checked["clips"] == {"downloaded": 1, "no_media": 1}
    assert checked["bytes"] == 9 and checked["files_checked"] is True
    (tmp_path / clip_row(conn, PLAY_IDS[0], "file_path")[0]).write_bytes(b"tampered!")
    checked = reg.status(conn, tmp_path)["games"][900001]
    assert checked["clips"] == {"downloaded_missing_or_changed": 1, "no_media": 1}
    assert checked["bytes"] == 0
    unchecked = reg.status(conn)["games"][900001]
    assert unchecked["clips"]["downloaded"] == 1 and unchecked["files_checked"] is False


def test_an_interrupt_gives_the_attempt_back(tmp_path):
    conn, _, _ = register(tmp_path)
    pages = {PLAY_IDS[0]: KeyboardInterrupt(), PLAY_IDS[1]: "<p></p>"}
    with pytest.raises(KeyboardInterrupt):
        reg.run_clips(
            conn, tmp_path, opener=opener_for(pages, {}, []), probe=fake_probe, sleep=lambda _: None
        )
    assert clip_row(conn, PLAY_IDS[0], "status, attempts, last_error") == (
        "pending",
        0,
        "interrupted",
    )


def test_a_run_of_pages_without_video_stops_and_can_be_retried_on_request(tmp_path):
    conn, _, _ = register(tmp_path)
    empty = {PLAY_IDS[0]: "<p>consent</p>", PLAY_IDS[1]: "<p>consent</p>"}
    run = dict(probe=fake_probe, sleep=lambda _: None)
    counts = reg.run_clips(
        conn, tmp_path, opener=opener_for(empty, {}, []), max_consecutive_no_media=2, **run
    )
    assert counts == {"no_media": 2, "stopped_after_consecutive_no_media": 2}
    assert reg.run_clips(conn, tmp_path, opener=opener_for(empty, {}, []), **run) == {}
    url0 = f"https://sporty-clips.mlb.com/{PLAY_IDS[0]}.mp4"
    url1 = f"https://sporty-clips.mlb.com/{PLAY_IDS[1]}.mp4"
    pages = {PLAY_IDS[0]: f'<video src="{url0}">', PLAY_IDS[1]: f'<video src="{url1}">'}
    counts = reg.run_clips(
        conn,
        tmp_path,
        opener=opener_for(pages, {url0: b"a", url1: b"b"}, []),
        retry_no_media=True,
        **run,
    )
    assert counts == {"downloaded": 2}


def test_a_page_with_two_different_videos_is_left_ambiguous(tmp_path):
    conn, _, _ = register(tmp_path)
    a, b = "https://sporty-clips.mlb.com/a.mp4", "https://sporty-clips.mlb.com/b.mp4"
    pages = {PLAY_IDS[0]: f'<video src="{a}"></video><video src="{b}"></video>'}
    calls = []
    reg.run_clips(
        conn,
        tmp_path,
        limit=1,
        opener=opener_for(pages, {a: b"a", b: b"b"}, calls),
        probe=fake_probe,
        sleep=lambda _: None,
    )
    row = clip_row(conn, PLAY_IDS[0], "status, media_candidates, media_url, file_path")
    assert row == ("ambiguous_media", json.dumps([a, b]), None, None)
    assert calls == [reg.PAGE_URL.format(play_id=PLAY_IDS[0])]
    assert not (tmp_path / "clips").exists()


def test_a_clip_that_fails_to_probe_leaves_no_file_and_can_be_retried(tmp_path):
    conn, _, _ = register(tmp_path)
    url0 = f"https://sporty-clips.mlb.com/{PLAY_IDS[0]}.mp4"
    pages = {PLAY_IDS[0]: f'<video src="{url0}"></video>'}

    def broken(path):
        raise subprocess.CalledProcessError(1, "ffprobe")

    run = dict(limit=1, sleep=lambda _: None)
    truncated = opener_for(pages, {url0: b"truncated"}, [])
    reg.run_clips(conn, tmp_path, opener=truncated, probe=broken, **run)
    assert clip_row(conn, PLAY_IDS[0], "status, file_path") == ("failed", None)
    assert list((tmp_path / "clips" / "900001").iterdir()) == []
    whole = opener_for(pages, {url0: b"whole"}, [])
    reg.run_clips(conn, tmp_path, opener=whole, probe=fake_probe, **run)
    row = clip_row(conn, PLAY_IDS[0], "status, file_sha256")
    assert row == ("downloaded", reg.sha256(b"whole"))


def test_a_refused_reregistration_writes_no_manifest(tmp_path):
    conn, _, data = register(tmp_path)
    manifest = tmp_path / "manifests" / "900001.json"
    manifest.unlink()
    with pytest.raises(ValueError, match="different manifest or split"):
        reg.register_game(conn, tmp_path, 900001, "dev", data, statcast(rows=1), "c" * 64)
    assert not manifest.exists()


def test_bad_delay_and_missing_ffprobe_are_refused_before_any_request(tmp_path, monkeypatch):
    conn, _, _ = register(tmp_path)
    calls = []
    for delay in (float("nan"), float("inf"), -1.0):
        with pytest.raises(ValueError, match="delay"):
            reg.run_clips(conn, tmp_path, delay=delay, opener=opener_for({}, {}, calls))
    monkeypatch.setattr(reg.shutil, "which", lambda _: None)
    with pytest.raises(RuntimeError, match="ffprobe"):
        reg.run_clips(conn, tmp_path, opener=opener_for({}, {}, calls), sleep=lambda _: None)
    assert calls == []


def load_cli():
    spec = importlib.util.spec_from_file_location(
        "clip_registry_cli", ROOT / "scripts" / "75_clip_registry.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_cli_refuses_a_game_given_twice_and_saves_no_source_that_fails_validation(tmp_path):
    cli = load_cli()
    with pytest.raises(SystemExit, match="more than once"):
        cli.pairs(["900001:dev", "900001:eval_locked"], ":")
    feed_file = tmp_path / "feed.json"
    feed_file.write_text(json.dumps(feed(game_pk=900001)))
    with pytest.raises(SystemExit, match="not game 900002"):
        cli.feed_source(tmp_path / "root", 900002, feed_file)
    parquet = tmp_path / "rows.parquet"
    statcast().to_parquet(parquet)
    with pytest.raises(SystemExit, match="no Statcast rows"):
        cli.statcast_source(tmp_path / "root", 900002, parquet)
    assert not (tmp_path / "root" / "sources").exists()
    frame, _ = cli.statcast_source(tmp_path / "root", 900001, parquet)
    assert len(frame) == 2
    assert (tmp_path / "root" / "sources" / "900001" / "statcast_rows.csv").is_file()

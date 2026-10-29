import importlib.util
import sqlite3
import sys
from pathlib import Path

import pytest

from src.data import replay_feasibility as f


def probe(pts):
    return {"streams": [{"time_base": "1/90000"}], "frames": [{"pts": x} for x in pts]}


def test_decoded_pts_not_nominal_fps():
    tb, rows = f.decode_index(probe([3000, 4502, 7505]))
    assert tb == "1/90000"
    assert rows[2]["clip_seconds"] == pytest.approx(4505 / 90000)
    assert rows[2]["seconds"] == pytest.approx(7505 / 90000)
    assert rows[2]["ordinal"] == 2


@pytest.mark.parametrize("pts", [[], [1, 1], [2, 1], [None], ["100"], [True]])
def test_invalid_pts_fail_closed(pts):
    with pytest.raises(ValueError):
        f.decode_index(probe(pts))


def test_sample_includes_last_and_uses_pts():
    _, rows = f.decode_index(probe([0, 1500, 45000, 46000, 90000, 91000]))
    assert [r["ordinal"] for r in f.sample_frames(rows)] == [0, 2, 4, 5]


@pytest.mark.parametrize(
    "data",
    [
        None,
        {"streams": [None]},
        {"streams": [{}]},
        {"streams": [{"time_base": "1/0"}]},
        {"streams": [{"time_base": "1/90000"}], "frames": [None]},
    ],
)
def test_malformed_decoder_output_is_classified_not_uncaught(data):
    with pytest.raises(ValueError):
        f.decode_index(data)


@pytest.mark.parametrize("n", [0, 6, True])
def test_investigation_bound_precedes_database_open(n):
    with pytest.raises(ValueError, match="limited"):
        f.read_candidates("does-not-exist", n)


def test_eval_locked_game_rejected_before_pitch_query(tmp_path):
    with sqlite3.connect(tmp_path / "registry.sqlite") as conn:
        conn.execute("create table games(game_pk integer, split text)")
        conn.execute("insert into games values(849843,'eval_locked')")
    before = (tmp_path / "registry.sqlite").read_bytes()
    with pytest.raises(ValueError, match="development"):
        f.read_candidates(tmp_path)
    assert (tmp_path / "registry.sqlite").read_bytes() == before


def test_clip_escape_and_wrong_bytes_refused(tmp_path):
    clip = tmp_path / "clip.mp4"
    clip.write_bytes(b"clip")
    row = {
        "status": "downloaded",
        "file_path": str(clip),
        "bytes": 4,
        "file_sha256": f.digest(clip),
    }
    with pytest.raises(ValueError, match="outside"):
        f.clip_file(tmp_path, row)
    row.update(file_path="clip.mp4", file_sha256="0" * 64)
    with pytest.raises(ValueError, match="mismatch"):
        f.clip_file(tmp_path, row)


def test_failed_pitch_stays_in_denominator(tmp_path, monkeypatch):
    root = tmp_path / "source"
    root.mkdir()
    (root / "registry.sqlite").write_bytes(b"test")
    row = {"pitch_key": "849843:1:1", "play_id": "a", "file_sha256": "a" * 64}
    monkeypatch.setattr(f, "read_candidates", lambda *_, **__: [row])

    def reject(*_):
        raise ValueError("not decoded")

    monkeypatch.setattr(f, "inspect_clip", reject)
    report = f.build_audit(root, tmp_path / "out", "unused", "unused")
    assert report["examined"] == 1 and report["decoded"] == 0
    assert report["records"][0]["decode_status"] == "failed"
    assert "from_pa" not in report  # Existing v1 default evidence remains unchanged.


@pytest.fixture
def scoped_registry(tmp_path):
    root = tmp_path / "registry"
    root.mkdir()
    with sqlite3.connect(root / "registry.sqlite") as conn:
        conn.executescript(
            "CREATE TABLE games(game_pk INTEGER, split TEXT);"
            "CREATE TABLE pitches(play_id TEXT,game_pk INTEGER,at_bat_number INTEGER,"
            "pitch_number INTEGER,pitcher_name TEXT,batter_name TEXT);"
            "CREATE TABLE clips(play_id TEXT,status TEXT,file_path TEXT,file_sha256 TEXT,"
            "bytes INTEGER);"
        )
        conn.executemany(
            "INSERT INTO games VALUES(?,?)", [(849843, "dev"), (849844, "eval_locked")]
        )
        for game, pa, count in [(849843, 1, 3), (849843, 2, 5), (849843, 3, 2), (849844, 2, 5)]:
            for pitch in range(1, count + 1):
                play = f"{game}-{pa}-{pitch}"
                conn.execute(
                    "INSERT INTO pitches VALUES(?,?,?,?,?,?)", (play, game, pa, pitch, "P", "B")
                )
                conn.execute(
                    "INSERT INTO clips VALUES(?,?,?,?,?)",
                    (play, "downloaded", "not-opened.mp4", "a" * 64, 123),
                )
    return root


def test_pa2_query_excludes_pa1_later_pa_and_locked_game(scoped_registry):
    before = (scoped_registry / "registry.sqlite").read_bytes()
    rows = f.read_candidates(scoped_registry, 2, from_pa=2)
    assert [r["pitch_key"] for r in rows] == [f"849843:2:{n}" for n in range(1, 6)]
    assert [r["play_id"] for r in rows] == [f"849843-2-{n}" for n in range(1, 6)]
    assert (scoped_registry / "registry.sqlite").read_bytes() == before
    assert len(f.read_candidates(scoped_registry, 2)) == 8
    assert len(f.read_candidates(scoped_registry)) == 3


@pytest.mark.parametrize(
    "start,end",
    [(0, 2), (6, 6), (3, 2), (True, 2), (2, True), (2.0, 2), (2, 2.0), ("2", 2), (2, "2")],
)
def test_bad_range_rejected_before_database_open(start, end):
    with pytest.raises(ValueError, match="limited"):
        f.read_candidates("missing-registry", end, from_pa=start)


def test_audit_only_decodes_selected_pa_and_records_start(scoped_registry, tmp_path, monkeypatch):
    seen = []

    def inspect(root, row, *_):
        seen.append(row["pitch_key"])
        return {"pitch_key": row["pitch_key"], "decode_status": "decoded"}

    monkeypatch.setattr(f, "inspect_clip", inspect)
    report = f.build_audit(scoped_registry, tmp_path / "out", "unused", "unused", 2, from_pa=2)
    assert seen == [f"849843:2:{n}" for n in range(1, 6)]
    assert report["from_pa"] == report["through_pa"] == 2
    assert report["examined"] == report["decoded"] == 5
    assert report["schema"] == f.SCHEMA


def test_cli_propagates_explicit_range_and_rejects_inversion(monkeypatch, tmp_path):
    spec = importlib.util.spec_from_file_location(
        "audit_replay_cli", Path(__file__).resolve().parents[1] / "scripts/76_audit_replay_clips.py"
    )
    cli = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(cli)
    calls = []

    def audit(*args, **kwargs):
        calls.append((args, kwargs))
        return {"examined": 5, "decoded": 5}

    monkeypatch.setattr(cli, "build_audit", audit)
    argv = ["audit", "--root", str(tmp_path), "--out", str(tmp_path / "out")]
    monkeypatch.setattr(sys, "argv", argv + ["--from-pa", "2", "--through-pa", "2"])
    assert cli.main() == 0
    assert calls[-1][0][-1] == 2 and calls[-1][1] == {"from_pa": 2}
    monkeypatch.setattr(sys, "argv", argv)
    assert cli.main() == 0
    assert calls[-1][0][-1] == 1 and calls[-1][1] == {"from_pa": 1}
    monkeypatch.setattr(sys, "argv", argv + ["--from-pa", "3", "--through-pa", "2"])
    with pytest.raises(SystemExit) as error:
        cli.main()
    assert error.value.code == 2
    assert len(calls) == 2

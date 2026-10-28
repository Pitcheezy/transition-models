import json
import re
import sqlite3
import subprocess
from contextlib import closing
from pathlib import Path

import pytest
from PIL import Image

from src.data import replay_context as context
from src.data import replay_interval as interval
from src.data.replay_feasibility import decode_index, digest


def synthetic_index(key):
    lower, upper, count, representative = interval.INTERVALS[key]
    pts = [lower + (upper - lower) * n // (count - 1) for n in range(count)]
    nearest = min(range(1, count - 1), key=lambda n: abs(pts[n] - representative))
    pts[nearest] = representative
    return decode_index(
        {
            "streams": [{"time_base": "1/90000"}],
            "frames": [{"pts": x} for x in [1170, *pts, upper + 1501]],
        }
    )[1]


def reindex(rows):
    return [{**row, "ordinal": n} for n, row in enumerate(rows)]


@pytest.mark.parametrize("key,count", [("849843:1:1", 24), ("849843:1:2", 25), ("849843:1:3", 31)])
def test_all_decoded_frames_are_retained_inclusive_with_nonzero_origin(key, count):
    rows = synthetic_index(key)
    chosen = interval.select_interval(key, "1/90000", rows)
    assert chosen == rows[1:-1]
    assert len(chosen) == count
    lower, upper, _, representative = interval.INTERVALS[key]
    assert chosen[0]["pts"] == lower and chosen[-1]["pts"] == upper
    assert representative in {row["pts"] for row in chosen}
    assert chosen[0]["clip_seconds"] == (lower - 1170) / 90000
    # The selection copies rows so downstream raster metadata cannot change the decoder index.
    chosen[0]["image"] = "synthetic.png"
    assert "image" not in rows[1]


@pytest.mark.parametrize("end", [1, -2])
def test_missing_boundary_is_not_rounded_or_replaced(end):
    rows = synthetic_index("849843:1:1")
    del rows[end]
    with pytest.raises(ValueError, match="boundaries"):
        interval.select_interval("849843:1:1", "1/90000", reindex(rows))


def test_missing_interior_frame_is_not_filled_from_fps():
    rows = synthetic_index("849843:1:1")
    del rows[2]
    with pytest.raises(ValueError, match="count"):
        interval.select_interval("849843:1:1", "1/90000", reindex(rows))


def test_missing_representative_refuses_same_count_interval():
    rows = synthetic_index("849843:1:1")
    representative = interval.INTERVALS["849843:1:1"][3]
    next(row for row in rows if row["pts"] == representative)["pts"] += 1
    with pytest.raises(ValueError, match="representative"):
        interval.select_interval("849843:1:1", "1/90000", rows)


@pytest.mark.parametrize("problem", ["duplicate_pts", "reverse_pts", "ordinal_gap", "bool_pts"])
def test_disordered_or_incomplete_decoder_index_is_rejected(problem):
    rows = synthetic_index("849843:1:1")
    if problem == "duplicate_pts":
        rows[2]["pts"] = rows[1]["pts"]
    elif problem == "reverse_pts":
        rows[1]["pts"], rows[2]["pts"] = rows[2]["pts"], rows[1]["pts"]
    elif problem == "ordinal_gap":
        rows[2]["ordinal"] += 1
    elif problem == "bool_pts":
        rows[0]["pts"] = True
    with pytest.raises(ValueError, match="strictly ordered"):
        interval.select_interval("849843:1:1", "1/90000", rows)


@pytest.mark.parametrize("key", ["849844:1:1", "849843:2:1", "747139:1:1"])
def test_unselected_games_or_pas_are_rejected(key):
    with pytest.raises(ValueError, match="fixed development"):
        interval.select_interval(key, "1/90000", synthetic_index("849843:1:1"))


@pytest.mark.parametrize("time_base", ["1/1000", "1/180000", "90000", None])
def test_wrong_clock_is_rejected(time_base):
    with pytest.raises(ValueError, match="clock"):
        interval.select_interval("849843:1:1", time_base, synthetic_index("849843:1:1"))


def make_registry(tmp_path, *, game=849843, split="dev"):
    root = tmp_path / "registry"
    root.mkdir()
    with closing(sqlite3.connect(root / "registry.sqlite")) as conn, conn:
        conn.executescript(
            "CREATE TABLE games(game_pk INTEGER, split TEXT);"
            "CREATE TABLE pitches(play_id TEXT, game_pk INTEGER, at_bat_number INTEGER, "
            "pitch_number INTEGER, pitcher_name TEXT, batter_name TEXT);"
            "CREATE TABLE clips(play_id TEXT, status TEXT, file_path TEXT, file_sha256 TEXT, bytes INTEGER);"
        )
        conn.execute("INSERT INTO games VALUES (?, ?)", (game, split))
        for number in (1, 2, 3):
            clip = root / f"clip_{number}.mp4"
            clip.write_bytes(f"synthetic interval clip {number}".encode())
            conn.execute(
                "INSERT INTO pitches VALUES (?, ?, 1, ?, 'Pitcher', 'Batter')",
                (str(number), game, number),
            )
            conn.execute(
                "INSERT INTO clips VALUES (?, 'downloaded', ?, ?, ?)",
                (str(number), clip.name, digest(clip), clip.stat().st_size),
            )
    return root


@pytest.mark.parametrize("game,split", [(849844, "dev"), (849843, "eval_locked")])
def test_build_rejects_wrong_game_and_eval_split_before_decoding(
    tmp_path, monkeypatch, game, split
):
    monkeypatch.setattr(context, "OUTPUT_ROOT", tmp_path / "outputs")
    root = make_registry(tmp_path, game=game, split=split)
    before = (root / "registry.sqlite").read_bytes()
    target = tmp_path / "outputs" / "interval"
    with pytest.raises(ValueError, match="development"):
        interval.build_intervals(root, target, "unused", "unused")
    assert not target.exists()
    assert (root / "registry.sqlite").read_bytes() == before


def test_build_rejects_nonprivate_or_existing_output_before_reading_source(tmp_path, monkeypatch):
    monkeypatch.setattr(context, "OUTPUT_ROOT", tmp_path / "outputs")
    with pytest.raises(ValueError, match="private outputs"):
        interval.build_intervals("missing", tmp_path / "docs", "unused", "unused")
    target = tmp_path / "outputs" / "old"
    target.mkdir(parents=True)
    marker = target / "keep.txt"
    marker.write_text("preserve")
    with pytest.raises(ValueError, match="fresh"):
        interval.build_intervals("missing", target, "unused", "unused")
    assert marker.read_text() == "preserve"


def test_synthetic_build_extracts_exact_eighty_frames_with_reused_pts_and_sha_checks(
    tmp_path, monkeypatch
):
    monkeypatch.setattr(context, "OUTPUT_ROOT", tmp_path / "outputs")
    root = make_registry(tmp_path)
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    calls = []

    def fake_run(command, **kwargs):
        calls.append(command)
        filename = command[-1] if command[0] == "ffprobe" else command[command.index("-i") + 1]
        number = int(Path(filename).stem.split("_")[-1])
        rows = synthetic_index(f"849843:1:{number}")
        if command[0] == "ffprobe":
            probe = {
                "streams": [{"time_base": "1/90000", "width": 1280, "height": 720}],
                "frames": [{"pts": row["pts"]} for row in rows],
            }
            return subprocess.CompletedProcess(command, 0, json.dumps(probe).encode(), b"")
        assert "-copyts" in command
        expression = command[command.index("-vf") + 1]
        assert expression.endswith(",showinfo")
        ordinals = [int(n) for n in re.findall(r"eq\(n\\,(\d+)\)", expression)]
        assert ordinals == list(range(1, len(rows) - 1))
        log = "[Parsed_showinfo_1] [info] config in time_base: 1/90000, frame_rate: 0/0\n"
        for n, ordinal in enumerate(ordinals):
            Image.new("RGB", context.FRAME_SIZE, "blue").save(command[-1] % n)
            log += f"[Parsed_showinfo_1] [info] n: {n} pts: {rows[ordinal]['pts']} pts_time: 1\n"
        return subprocess.CompletedProcess(command, 0, b"", log.encode())

    monkeypatch.setattr(context.subprocess, "run", fake_run)
    out = tmp_path / "outputs" / "interval"
    report = interval.build_intervals(root, out, "ffprobe", "ffmpeg")
    assert len(calls) == 6
    assert report["schema"] == interval.SCHEMA
    assert report["selection"]["expected_total_frames"] == 80
    assert "not_visual_or_human_truth" in report["evidence_kind"]
    assert [len(row["sampled_frames"]) for row in report["records"]] == [24, 25, 31]
    assert {p.name: p.read_bytes() for p in root.iterdir()} == before
    assert json.loads((out / "audit.json").read_text()) == report
    for row in report["records"]:
        assert row["extraction"]["selected_pts"] == [f["pts"] for f in row["sampled_frames"]]
        assert row["interval"]["representative_pts"] in row["extraction"]["selected_pts"]
        assert row["first_pts"] == 1170
        for frame in row["sampled_frames"]:
            assert digest(out / frame["image"]) == frame["image_sha256"]
            assert frame["context_crop"]["source_rectangle_xyxy"] == list(context.CROP)
            assert "point" not in frame and "label" not in frame
        assert sum(len(sheet["tiles"]) for sheet in row["sheets"]) == 2 * len(row["sampled_frames"])

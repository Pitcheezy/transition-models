import json
import re
import sqlite3
import subprocess
from fractions import Fraction

import pytest
from PIL import Image

from src.data import replay_context as c
from src.data.replay_feasibility import decode_index, digest


def decoded(pts, time_base="1/1000"):
    return decode_index(
        {"streams": [{"time_base": time_base}], "frames": [{"pts": x} for x in pts]}
    )


def registry(tmp_path, game=849843, split="dev"):
    root = tmp_path / "registry"
    root.mkdir()
    with sqlite3.connect(root / "registry.sqlite") as conn:
        conn.executescript(
            "CREATE TABLE games(game_pk INTEGER, split TEXT);"
            "CREATE TABLE pitches(play_id TEXT, game_pk INTEGER, at_bat_number INTEGER, "
            "pitch_number INTEGER, pitcher_name TEXT, batter_name TEXT);"
            "CREATE TABLE clips(play_id TEXT, status TEXT, file_path TEXT, file_sha256 TEXT, bytes INTEGER);"
        )
        conn.execute("INSERT INTO games VALUES (?,?)", (game, split))
        for pitch in (1, 2, 3):
            path = root / f"clip_{pitch}.mp4"
            path.write_bytes(f"synthetic clip {pitch}".encode())
            conn.execute(
                "INSERT INTO pitches VALUES (?,?,1,?,'Pitcher','Batter')", (str(pitch), game, pitch)
            )
            conn.execute(
                "INSERT INTO clips VALUES (?,'downloaded',?,?,?)",
                (str(pitch), path.name, digest(path), path.stat().st_size),
            )
    return root


def test_exact_cutoff_excludes_a_future_pts_even_when_float_rounds_to_2_5():
    future = 2_500_000_000_000_000_001
    tb, rows = decoded(
        [0, 100_000_000_000_000_000, 2_490_000_000_000_000_000, future], "1/1000000000000000000"
    )
    assert rows[-1]["clip_seconds"] == 2.5
    chosen = c.select_frames(tb, rows)
    assert future not in {row["pts"] for row in chosen}
    assert all(row["pts"] * Fraction(tb) <= Fraction(5, 2) for row in chosen)


def test_nonzero_origin_dense_interval_and_last_eligible_boundary_are_bounded():
    tb, rows = decoded([*range(500, 3000, 100), 2999, 3001])
    chosen = c.select_frames(tb, rows)
    assert len(chosen) == 26
    assert chosen[0]["pts"] == 500 and chosen[-1]["pts"] == 2999
    assert chosen[-1]["clip_seconds"] == 2.499
    assert all(b["pts"] - a["pts"] >= 100 for a, b in zip(chosen[:-2], chosen[1:-1], strict=True))
    assert chosen[-1]["pts"] - chosen[-2]["pts"] == 99


@pytest.mark.parametrize("game,split", [(849844, "dev"), (849843, "eval_locked")])
def test_wrong_game_and_evaluation_registry_are_refused_without_output(
    tmp_path, monkeypatch, game, split
):
    monkeypatch.setattr(c, "OUTPUT_ROOT", tmp_path / "outputs")
    root = registry(tmp_path, game, split)
    before = (root / "registry.sqlite").read_bytes()
    out = tmp_path / "outputs" / "context"
    with pytest.raises(ValueError, match="development"):
        c.build_context(root, out, "unused", "unused")
    assert not out.exists()
    assert (root / "registry.sqlite").read_bytes() == before


def test_incomplete_first_pa_is_not_replaced_by_another_pa(tmp_path):
    root = registry(tmp_path)
    with sqlite3.connect(root / "registry.sqlite") as conn:
        conn.execute("UPDATE pitches SET at_bat_number=2 WHERE pitch_number=3")
    with pytest.raises(ValueError, match="exactly"):
        c.first_three(root)


@pytest.mark.parametrize("filename", ["../outside.mp4", "absolute"])
def test_clip_paths_cannot_leave_registry(tmp_path, monkeypatch, filename):
    monkeypatch.setattr(c, "OUTPUT_ROOT", tmp_path / "outputs")
    root = registry(tmp_path)
    outside = tmp_path / "outside.mp4"
    outside.write_bytes(b"outside")
    if filename == "absolute":
        filename = str(outside)
    with sqlite3.connect(root / "registry.sqlite") as conn:
        conn.execute(
            "UPDATE clips SET file_path=?,file_sha256=?,bytes=? WHERE play_id='1'",
            (filename, digest(outside), outside.stat().st_size),
        )
    out = tmp_path / "outputs" / "context"
    with pytest.raises(ValueError, match="outside"):
        c.build_context(root, out, "unused", "unused")
    assert not out.exists()


@pytest.mark.parametrize(
    "relative", ["docs/context", "web/context", "outputs/../docs/context", "outputs"]
)
def test_output_scope_is_checked_before_opening_registry(tmp_path, monkeypatch, relative):
    monkeypatch.setattr(c, "OUTPUT_ROOT", tmp_path / "outputs")
    with pytest.raises(ValueError, match="private outputs"):
        c.build_context("missing-registry", tmp_path / relative, "unused", "unused")


def test_existing_output_is_preserved(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "OUTPUT_ROOT", tmp_path / "outputs")
    out = tmp_path / "outputs" / "context"
    out.mkdir(parents=True)
    marker = out / "existing.txt"
    marker.write_text("keep")
    with pytest.raises(ValueError, match="fresh"):
        c.build_context("missing-registry", out, "unused", "unused")
    assert marker.read_text() == "keep"


@pytest.mark.parametrize(
    "rectangle",
    [
        (-1, 240, 660, 470),
        (450, 240, 450, 470),
        (450, 240, 1281, 470),
        (450, 240, 660, 721),
        (True, 240, 660, 470),
    ],
)
def test_invalid_crop_is_refused(rectangle):
    with pytest.raises(ValueError, match="crop"):
        c.validate_crop(rectangle, (1280, 720))


def test_synthetic_extraction_preserves_full_frame_crop_identity_and_pts(tmp_path, monkeypatch):
    monkeypatch.setattr(c, "OUTPUT_ROOT", tmp_path / "outputs")
    root = registry(tmp_path)
    before = {p.name: p.read_bytes() for p in root.iterdir()}
    commands = []
    probe = {
        "streams": [{"time_base": "1/90000", "width": 1280, "height": 720}],
        "frames": [{"pts": value} for value in [90000, 94500, 99000, 314100, 315001]],
    }

    def fake_run(command, **kwargs):
        commands.append(command)
        if command[0] == "ffprobe":
            assert "-show_frames" in command
            return subprocess.CompletedProcess(command, 0, json.dumps(probe).encode(), b"")
        assert command[command.index("-map") + 1] == "0:v:0"
        select = command[command.index("-vf") + 1]
        ordinals = [int(value) for value in re.findall(r"eq\(n\\,(\d+)\)", select)]
        assert ordinals == [0, 2, 3]
        assert command[command.index("-frames:v") + 1] == "3"
        for index in range(len(ordinals)):
            image = Image.new("RGB", (1280, 720), "blue")
            image.putpixel((450, 240), (255, 0, 0))
            image.putpixel((451, 240), (0, 255, 0))
            image.save(command[-1] % index)
        assert "-copyts" in command and select.endswith(",showinfo")
        log = "[Parsed_showinfo_1] [info] config in time_base: 1/90000, frame_rate: 0/0\n"
        log += "".join(
            f"[Parsed_showinfo_1] [info] n: {n} pts: {probe['frames'][ordinal]['pts']} pts_time: 1\n"
            for n, ordinal in enumerate(ordinals)
        )
        return subprocess.CompletedProcess(command, 0, b"", log.encode())

    monkeypatch.setattr(c.subprocess, "run", fake_run)
    out = tmp_path / "outputs" / "context"
    report = c.build_context(root, out, "ffprobe", "ffmpeg")
    assert len(commands) == 6 and len(report["records"]) == 3
    assert json.loads((out / "audit.json").read_text()) == report
    assert {p.name: p.read_bytes() for p in root.iterdir()} == before
    for record in report["records"]:
        assert record["decoded_frames"] == 5
        assert record["extraction"]["selected_pts"] == [90000, 99000, 314100]
        assert [frame["pts"] for frame in record["sampled_frames"]] == [90000, 99000, 314100]
        for frame in record["sampled_frames"]:
            assert frame["clip_seconds"] <= 2.5
            full, crop = frame["full_frame"], frame["context_crop"]
            assert frame["image"] == full["path"] and frame["image_sha256"] == digest(
                out / full["path"]
            )
            assert full["size"] == [1280, 720] and crop["size"] == [210, 230]
            assert crop["source_rectangle_xyxy"] == [450, 240, 660, 470]
            with Image.open(out / crop["path"]) as image:
                assert image.getpixel((0, 0)) == (255, 0, 0)
        crop_sheet = record["sheets"][1]
        assert crop_sheet["resampling"] == "NEAREST" and crop_sheet["display_size"] == [420, 460]
        with Image.open(out / crop_sheet["path"]) as image:
            assert image.getpixel((0, 0)) == image.getpixel((1, 1)) == (255, 0, 0)
            assert image.getpixel((2, 0)) == (0, 255, 0)
        assert all(
            record["pitch_key"] in tile["label"] and "PTS=" in tile["label"]
            for sheet in record["sheets"]
            for tile in sheet["tiles"]
        )


def test_contact_sheet_pages_have_at_most_twelve_labeled_tiles(tmp_path):
    image = Image.new("RGB", (210, 230), "blue")
    image.save(tmp_path / "crop.png")
    frames = [
        {"ordinal": i, "pts": i * 100, "clip_seconds": i / 10, "context_crop": {"path": "crop.png"}}
        for i in range(13)
    ]
    pages = c.contact_sheets(tmp_path, tmp_path, "849843:1:1", frames, "crop_nearest_2x")
    assert [len(page["tiles"]) for page in pages] == [12, 1]
    assert [page["size"] for page in pages] == [[1260, 1984], [1260, 496]]
    assert [tile["ordinal"] for page in pages for tile in page["tiles"]] == list(range(13))


@pytest.mark.parametrize("problem", ["missing", "shifted", "reordered", "clock", "warning"])
def test_extraction_pts_must_match_probe_without_warnings(problem):
    rows = [{"pts": 1170}, {"pts": 10179}]
    pts = [1170, 10179]
    clock = "1/90000"
    if problem == "missing":
        pts.pop()
    elif problem == "shifted":
        pts = [0, 9009]
    elif problem == "reordered":
        pts.reverse()
    elif problem == "clock":
        clock = "1/1000"
    log = f"[Parsed_showinfo_1] [info] config in time_base: {clock}, frame_rate: 0/0\n"
    log += "".join(
        f"[Parsed_showinfo_1] [info] n: {n} pts: {value} pts_time: 1\n"
        for n, value in enumerate(pts)
    )
    if problem == "warning":
        log += "[h264] [warning] damaged picture concealed\n"
    with pytest.raises(ValueError):
        c.verify_extracted_pts(log.encode(), rows, "1/90000")

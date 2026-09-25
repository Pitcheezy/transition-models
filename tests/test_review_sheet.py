"""The review sheet composes synthetic frames into the documented grid without any grab."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

from src.vision import review_sheet as rs

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "71_timing_review_sheet.py"


def frame(shade):
    image = Image.new("RGB", (1280, 720), (shade, shade, shade))
    image.paste(Image.new("RGB", (255, 110), (20, 40, 120)), (55, 25))
    return image


def strip_height(n, tile, per_row):
    rows = (n + per_row - 1) // per_row
    return rows * tile[1] + (rows - 1) * rs.GAP


def test_compose_sheet_layout_rows_and_size():
    decision = [(t, frame(60)) for t in (10.0, 10.25, 10.5)]
    prep = [(t, frame(90)) for t in (11.0, 11.5, 12.0, 12.5, 13.0)]
    release = [(t, frame(120)) for t in (14.0, 14.05, 14.1, 14.15, 14.2, 14.25, 14.3)]
    sheet, layout = rs.compose_sheet(decision, prep, release, title="unit")
    assert [(s["name"], s["rows"]) for s in layout["sections"]] == [
        ("decision", 1),
        ("bug", 2),
        ("prep", 2),
        ("release", 2),
    ]
    width = 3 * rs.DECISION_TILE[0] + 2 * rs.GAP
    height = rs.TITLE + 4 * (rs.HEADER + rs.GAP)
    height += strip_height(3, rs.DECISION_TILE, rs.DECISION_PER_ROW)
    height += strip_height(3, rs.BUG_TILE, rs.BUG_PER_ROW)
    height += strip_height(5, rs.PREP_TILE, rs.PREP_PER_ROW)
    height += strip_height(7, rs.RELEASE_TILE, rs.RELEASE_PER_ROW)
    assert (layout["width"], layout["height"]) == (width, height)
    assert sheet.size == (width, height)
    # the bug crop is the navy panel enlarged: sample its middle
    y = rs.TITLE + rs.HEADER + rs.DECISION_TILE[1] + rs.GAP + rs.HEADER + rs.BUG_TILE[1] // 2
    assert sheet.getpixel((rs.BUG_TILE[0] // 2, y)) == (20, 40, 120)


def test_compose_sheet_skips_empty_sections_and_rejects_nothing():
    sheet, layout = rs.compose_sheet([], [], [(1.0, frame(50))], title="rel only")
    assert [s["name"] for s in layout["sections"]] == ["release"]
    assert sheet.size == (rs.RELEASE_TILE[0], rs.TITLE + rs.HEADER + rs.RELEASE_TILE[1] + rs.GAP)
    with pytest.raises(ValueError):
        rs.compose_sheet([], [], [], title="empty")


def test_cached_frame_prefers_review_grabs_over_ocr_caches(tmp_path):
    assert rs.cached_frame(tmp_path, 5.0) is None
    (tmp_path / "evalset_5.00.jpg").write_bytes(b"x")
    assert rs.cached_frame(tmp_path, 5.0).name == "evalset_5.00.jpg"
    (tmp_path / "neg_5.00.jpg").write_bytes(b"x")
    (tmp_path / "p22_scan_5.00.jpg").write_bytes(b"x")
    assert rs.cached_frame(tmp_path, 5.0).name == "p22_scan_5.00.jpg"
    assert rs.cached_frame(tmp_path, 5.5) is None


def test_cli_reuses_cached_frames_without_ffmpeg(tmp_path):
    frames = tmp_path / "frames"
    frames.mkdir()
    for t in (20.0, 20.25):
        frame(70).save(frames / f"scan_{t:.2f}.jpg", quality=90)
    frame(70).save(frames / "evalset_21.00.jpg", quality=90)
    timing = tmp_path / "timing.json"
    timing.write_text(
        json.dumps(
            {"source": {"media_url": "https://example.invalid/x.mp4", "duration_seconds": 30}}
        )
    )
    command = [
        sys.executable,
        str(SCRIPT),
        "--label",
        "unit",
        "--dec",
        "20",
        "20.25",
        "--rel",
        "21",
        "--timing",
        str(timing),
        "--frames-dir",
        str(frames),
        "--out-dir",
        str(tmp_path / "out"),
        "--ffmpeg",
        "ffmpeg-that-does-not-exist",
    ]
    run = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, encoding="utf-8")
    assert run.returncode == 0, run.stderr
    sheet = tmp_path / "out" / "unit_review_sheet.png"
    assert sheet.exists() and "scan_20.25.jpg" in run.stdout and "evalset_21.00.jpg" in run.stdout
    assert Image.open(sheet).width == 2 * rs.BUG_TILE[0] + rs.GAP  # widest strip
    # a time without any cached frame needs ffmpeg
    run = subprocess.run(command + ["--prep", "22"], cwd=ROOT, capture_output=True, text=True)
    assert run.returncode != 0


def test_script_importable_with_defaults():
    spec = importlib.util.spec_from_file_location("review_sheet_cli", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    assert module.DEFAULT_OUT == Path("outputs/verification")

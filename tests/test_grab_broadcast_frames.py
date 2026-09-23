"""Frame-grab montages reuse existing frames, stay bound to the timing source, and never call
ffmpeg when every frame is already on disk."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest
from PIL import Image

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "65_grab_broadcast_frames.py"


def load_module():
    spec = importlib.util.spec_from_file_location("grab_frames", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def synthetic_frame(path, shade):
    image = Image.new("RGB", (1280, 720), (shade, shade, shade))
    image.paste(Image.new("RGB", (255, 110), (20, 40, 120)), (55, 25))
    image.save(path, quality=90)


def test_montages_from_existing_frames(tmp_path):
    module = load_module()
    frames = []
    for i, t in enumerate((10.0, 10.5, 11.0)):
        path = module.frame_path(tmp_path, "unit", t)
        synthetic_frame(path, 60 + 40 * i)
        assert module.grab_frame("https://example.invalid/none.mp4", t, path) is False
        frames.append((t, path))
    full_path, bug_path = module.build_montages(frames, tmp_path, "unit")
    full = Image.open(full_path)
    assert full.size == (1280, 720)  # 3 frames -> 2 columns x 2 rows of 640x360
    bug = Image.open(bug_path)
    assert bug.size == (765, 3 * 336)


def test_cli_reuses_frames_and_rejects_out_of_range(tmp_path):
    module = load_module()
    timing = tmp_path / "timing.json"
    timing.write_text(
        json.dumps(
            {
                "source": {
                    "media_url": "https://example.invalid/none.mp4",
                    "duration_seconds": 100.0,
                }
            }
        ),
        encoding="utf-8",
    )
    out = tmp_path / "frames"
    out.mkdir()
    synthetic_frame(module.frame_path(out, "cli", 5.0), 90)
    run = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--label",
            "cli",
            "--times",
            "5",
            "--timing",
            str(timing),
            "--out",
            str(out),
            "--ffmpeg",
            "ffmpeg-that-does-not-exist",
        ],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=ROOT,
    )
    assert run.returncode == 0, run.stderr
    assert (out / "cli_full.png").exists() and (out / "cli_bug.png").exists()
    for times in (["500"], ["-1"], [str(i) for i in range(9)]):
        bad = subprocess.run(
            [
                sys.executable,
                str(SCRIPT),
                "--label",
                "x",
                "--times",
                *times,
                "--timing",
                str(timing),
                "--out",
                str(out),
            ],
            capture_output=True,
            text=True,
            encoding="utf-8",
            cwd=ROOT,
        )
        assert bad.returncode != 0


def test_missing_ffmpeg_is_an_error_not_a_silent_skip(tmp_path):
    module = load_module()
    with pytest.raises(RuntimeError, match="not found"):
        module.grab_frame(
            "https://example.invalid/none.mp4", 1.0, tmp_path / "f.jpg", "ffmpeg-nope"
        )

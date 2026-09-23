"""Grab broadcast frames at playback seconds with ffmpeg and build eye-review montages.

Usage::

    uv run --frozen python scripts/65_grab_broadcast_frames.py --label p6scan --times 470 480 490
    uv run --frozen python scripts/65_grab_broadcast_frames.py --label p6a --times 531.9 532.1 532.3 --out outputs/frames

The media URL is read from the timing document (``docs/results/mlb_p0/game_747139_timing.json``
by default), so frames always come from the inspected MP4 that the annotations are bound to.
Per call it writes ``<out>/<label>_<t>.jpg`` (one 1280x720 frame per time), ``<label>_full.png``
(half-size frames in two columns, time-stamped) and ``<label>_bug.png`` (the scoreboard bug
crop enlarged for reading the count / outs / runners / inning / score by eye).

These montages are review aids for manual timing and scoreboard reading. They are not OCR and
they produce no labels. Times are playback seconds of that MP4; never derive them from feed UTC.
Existing frame files are reused, so re-running with the same label and times costs nothing.
"""

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.scoreboard_evalset import read_json

DEFAULT_TIMING = Path("docs/results/mlb_p0/game_747139_timing.json")
DEFAULT_OUT = Path("outputs/frames")
SNY_BUG_BOX = (55, 25, 310, 135)
FULL_TILE = (640, 360)
BUG_TILE = (765, 330)
MAX_TIMES = 8


def frame_path(out, label, t):
    return out / f"{label}_{t:.2f}.jpg"


def grab_frame(media_url, t, path, ffmpeg="ffmpeg", attempts=3):
    """Extract one frame at playback second ``t`` unless the file already exists.

    Remote HTTP range reads of the MP4 fail intermittently ("partial file"); a failed attempt
    writes nothing, so it is retried up to ``attempts`` times before raising.
    """
    if path.exists():
        return False
    if shutil.which(ffmpeg) is None:
        raise RuntimeError(f"{ffmpeg} not found on PATH")
    path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{t:.3f}",
        "-i",
        media_url,
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(path),
    ]
    for attempt in range(1, attempts + 1):
        run = subprocess.run(command, capture_output=True, text=True, timeout=180)
        if run.returncode == 0 and path.exists() and path.stat().st_size > 0:
            return True
        path.unlink(missing_ok=True)
        if attempt == attempts:
            raise RuntimeError(
                f"ffmpeg failed {attempts} times at t={t}: {run.stderr.strip()[-400:]}"
            )
    return True


def build_montages(frames, out, label, bug_box=SNY_BUG_BOX):
    """Write ``<label>_full.png`` and ``<label>_bug.png`` from (time, path) pairs."""
    from PIL import Image, ImageDraw

    cols = 2
    rows = (len(frames) + cols - 1) // cols
    full = Image.new("RGB", (FULL_TILE[0] * cols, FULL_TILE[1] * rows), "white")
    for i, (t, path) in enumerate(frames):
        x, y = (i % cols) * FULL_TILE[0], (i // cols) * FULL_TILE[1]
        full.paste(Image.open(path).convert("RGB").resize(FULL_TILE), (x, y))
        draw = ImageDraw.Draw(full)
        draw.rectangle((x, y + FULL_TILE[1] - 24, x + 120, y + FULL_TILE[1]), fill="black")
        draw.text((x + 4, y + FULL_TILE[1] - 18), f"t={t:.2f}", fill="yellow")
    crops = []
    for t, path in frames:
        crop = Image.open(path).convert("RGB").crop(bug_box).resize(BUG_TILE, Image.LANCZOS)
        draw = ImageDraw.Draw(crop)
        draw.rectangle((0, 0, 110, 22), fill="black")
        draw.text((4, 4), f"t={t:.2f}", fill="yellow")
        crops.append(crop)
    bug = Image.new("RGB", (BUG_TILE[0], sum(c.height + 6 for c in crops)), "white")
    y = 0
    for crop in crops:
        bug.paste(crop, (0, y))
        y += crop.height + 6
    full_path, bug_path = out / f"{label}_full.png", out / f"{label}_bug.png"
    full.save(full_path)
    bug.save(bug_path)
    return full_path, bug_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--label", required=True, help="prefix for this batch; use a new one per call"
    )
    parser.add_argument("--times", type=float, nargs="+", required=True, help="playback seconds")
    parser.add_argument("--timing", type=Path, default=DEFAULT_TIMING)
    parser.add_argument("--out", type=Path, default=DEFAULT_OUT)
    parser.add_argument(
        "--bug-box", type=int, nargs=4, default=SNY_BUG_BOX, metavar=("X0", "Y0", "X1", "Y1")
    )
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args()
    if not 1 <= len(args.times) <= MAX_TIMES:
        parser.error(f"give 1..{MAX_TIMES} times per call")
    if any(t < 0 for t in args.times):
        parser.error("times must be non-negative playback seconds")
    timing = read_json(args.timing)
    media_url = timing["source"]["media_url"]
    duration = timing["source"]["duration_seconds"]
    if any(t > duration for t in args.times):
        parser.error(f"times must not exceed the source duration {duration}")
    args.out.mkdir(parents=True, exist_ok=True)
    frames = []
    for t in args.times:
        path = frame_path(args.out, args.label, t)
        grab_frame(media_url, t, path, args.ffmpeg)
        frames.append((t, path))
    full_path, bug_path = build_montages(frames, args.out, args.label, tuple(args.bug_box))
    print(full_path)
    print(bug_path)
    for _, path in frames:
        print(path)


if __name__ == "__main__":
    main()

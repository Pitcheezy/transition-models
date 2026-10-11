"""Grab broadcast frames at playback seconds with ffmpeg and build eye-review montages.

Usage::

    uv run --frozen python scripts/65_grab_broadcast_frames.py --label p6scan --times 470 480 490
    uv run --frozen python scripts/65_grab_broadcast_frames.py --label p6a --times 531.9 532.1 532.3 --out outputs/frames

The media URL is read from the timing document (``docs/results/mlb_p0/game_747139_timing.json``
by default), so frames always come from the inspected MP4 that the annotations are bound to.
Per call it writes source-bound cached JPGs and receipts, ``<label>_full.png``
(half-size frames in two columns, time-stamped) and ``<label>_bug.png`` (the scoreboard bug
crop enlarged for reading the count / outs / runners / inning / score by eye).

These montages are review aids for manual timing and scoreboard reading. They are not OCR and
they produce no labels. Times are playback seconds of that MP4; never derive them from feed UTC.
Only source/time/hash-verified frames are reused; unbound legacy files are preserved.
"""

import argparse
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.scoreboard_evalset import read_json
from src.vision.frames import (  # noqa: F401
    SNY_BUG_BOX,
    build_montages,
    frame_path,
    grab_frame,
    resolve_frame,
)

DEFAULT_TIMING = Path("docs/results/mlb_p0/game_747139_timing.json")
DEFAULT_OUT = Path("outputs/frames")
MAX_TIMES = 8


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--label", required=True, help="prefix for this batch; use a new one per call"
    )
    parser.add_argument(
        "--times",
        type=float,
        nargs="+",
        required=True,
        help="source video playback seconds observed directly; never derive from feed UTC",
    )
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
        path = resolve_frame(media_url, t, args.out, args.label, ffmpeg=args.ffmpeg)
        frames.append((t, path))
    full_path, bug_path = build_montages(frames, args.out, args.label, tuple(args.bug_box))
    print(full_path)
    print(bug_path)
    for _, path in frames:
        print(path)


if __name__ == "__main__":
    main()

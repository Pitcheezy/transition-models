r"""Build one per-pitch review sheet (decision, bug, preparation and release frames) (H-4).

Usage::

    uv run --frozen python scripts/71_timing_review_sheet.py --label pa27_1 \
        --dec 2208.75 2209.0 2209.25 --prep 2209.5 2210 --rel 2211.45 2211.5 2211.55
    uv run --frozen python scripts/71_timing_review_sheet.py --label pa27_1 --dec 2209.0 \
        --title "PA27/1 decision" --pitcher-box 430 190 850 610 --out-dir outputs/verification

``--dec`` lists the boundary frames around the decision frame together with the decision
frame itself; ``--prep`` the preparation frames and ``--rel`` the release candidates. Frames
are grabbed with ffmpeg from the timing document's ``source.media_url`` unless a frame of the
same source/time has a verified image hash. New grabs use a source-specific directory and
millisecond filenames with receipts; unbound legacy JPGs are preserved and never reused.
The sheet is ``<out-dir>/<label>_review_sheet.png``: decision frames three per row at half
size, their scoreboard bugs enlarged, preparation frames four per row and release crops of the
pitcher box five per row. It is a review aid for manual timing and produces no labels.

All --dec, --prep and --rel values are playback seconds observed directly in the source
video. Broadcasts may be edited: never convert, extrapolate, or interpolate them from feed UTC.
"""

import argparse
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.scoreboard_evalset import read_json  # noqa: E402
from src.vision.frames import SNY_BUG_BOX, resolve_frame  # noqa: E402
from src.vision.review_sheet import DEFAULT_PITCHER_BOX, compose_sheet  # noqa: E402

DEFAULT_TIMING = Path("docs/results/mlb_p0/game_747139_timing.json")
DEFAULT_FRAMES = Path("outputs/frames")
DEFAULT_OUT = Path("outputs/verification")


def load_frames(times, args, media_url):
    """Return ``(t, image, path)`` per time, reusing cached frames and grabbing the rest."""
    frames = []
    for t in times:
        path = resolve_frame(
            media_url, t, args.frames_dir, args.label, ffmpeg=args.ffmpeg, no_grab=args.no_grab
        )
        frames.append((t, Image.open(path).convert("RGB"), path))
    return frames


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    parser.add_argument("--label", required=True, help="name of this sheet and of new grabs")
    parser.add_argument(
        "--dec",
        type=float,
        nargs="*",
        default=[],
        help="decision frame playback seconds; never derive from feed UTC",
    )
    parser.add_argument(
        "--prep",
        type=float,
        nargs="*",
        default=[],
        help="preparation frame playback seconds; never derive from feed UTC",
    )
    parser.add_argument(
        "--rel",
        type=float,
        nargs="*",
        default=[],
        help="release frame playback seconds; never derive from feed UTC",
    )
    parser.add_argument("--title", help="sheet title (default: the label)")
    parser.add_argument(
        "--pitcher-box",
        type=int,
        nargs=4,
        default=DEFAULT_PITCHER_BOX,
        metavar=("X0", "Y0", "X1", "Y1"),
    )
    parser.add_argument(
        "--bug-box", type=int, nargs=4, default=SNY_BUG_BOX, metavar=("X0", "Y0", "X1", "Y1")
    )
    parser.add_argument("--timing", type=Path, default=DEFAULT_TIMING)
    parser.add_argument("--frames-dir", type=Path, default=DEFAULT_FRAMES)
    parser.add_argument("--out-dir", type=Path, default=DEFAULT_OUT)
    parser.add_argument("--ffmpeg", default="ffmpeg")
    parser.add_argument("--no-grab", action="store_true", help="require verified cached frames")
    args = parser.parse_args()
    times = [*args.dec, *args.prep, *args.rel]
    if not times:
        parser.error("give at least one of --dec, --prep, --rel")
    timing = read_json(args.timing)
    duration = timing["source"]["duration_seconds"]
    if any(not 0 <= t <= duration for t in times):
        parser.error(f"times must be playback seconds within 0..{duration}")
    groups = [
        load_frames(getattr(args, name), args, timing["source"]["media_url"])
        for name in ("dec", "prep", "rel")
    ]
    sheet, layout = compose_sheet(
        *[[(t, image) for t, image, _ in group] for group in groups],
        title=args.title or args.label,
        bug_box=tuple(args.bug_box),
        pitcher_box=tuple(args.pitcher_box),
    )
    args.out_dir.mkdir(parents=True, exist_ok=True)
    sheet_path = args.out_dir / f"{args.label}_review_sheet.png"
    sheet.save(sheet_path)
    print(f"sheet: {sheet_path} ({layout['width']}x{layout['height']})")
    for section in layout["sections"]:
        print(f"  {section['name']}: {section['rows']} row(s) of {section['tile']}")
    for name, group in zip(("dec", "prep", "rel"), groups, strict=True):
        for t, _, path in group:
            print(f"{name} t={t:.2f}: {path}")


if __name__ == "__main__":
    main()

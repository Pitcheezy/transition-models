"""Run the scoreboard reader + state tracker over a sequence of frames (F-4 demo).

Usage::

    uv run --frozen python scripts/67_track_scoreboard_state.py --label track --times 460 465 470 475 480 485 490 495 \
        --templates docs/results/mlb_p0/sny_digit_templates_v0.json --output docs/results/mlb_p0/game_747139_scoreboard_track_demo.json

Frames are ``<frames-dir>/<label>_<t>.jpg`` (grabbed with scripts/65; missing ones are grabbed
from the timing document's media_url). For every frame the reader's fields (null = abstain)
and the tracker's held state with per-field age / stale flags are written. This is a
demonstration of holding state through cutaways and graphics; it is not a benchmark and the
readings are not labels.
"""

import argparse
import json
import sys
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.scoreboard_evalset import read_json
from src.vision.frames import frame_path, grab_frame
from src.vision.sny_scoreboard import DigitTemplates, read_scoreboard
from src.vision.state_tracker import FIELDS, ScoreboardTracker

RESULTS = Path("docs/results/mlb_p0")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--timing", type=Path, default=RESULTS / "game_747139_timing.json")
    parser.add_argument("--templates", type=Path, required=True)
    parser.add_argument("--frames-dir", type=Path, default=Path("outputs/frames"))
    parser.add_argument("--label", default="track")
    parser.add_argument("--times", type=float, nargs="+", required=True)
    parser.add_argument("--stale-after", type=float, default=10.0)
    parser.add_argument("--no-grab", action="store_true")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    timing = read_json(args.timing)
    media_url = timing["source"]["media_url"]
    templates = DigitTemplates.from_json(read_json(args.templates))
    tracker = ScoreboardTracker(args.stale_after)
    rows = []
    from PIL import Image

    for t in sorted(args.times):
        path = frame_path(args.frames_dir, args.label, t)
        if not path.exists():
            if args.no_grab:
                raise FileNotFoundError(path)
            grab_frame(media_url, t, path)
        reading = read_scoreboard(np.asarray(Image.open(path).convert("RGB")), templates)
        state = tracker.update(t, reading)
        rows.append(
            {
                "seconds": t,
                "reading": {name: reading[name] for name in FIELDS},
                "held": {name: state["fields"][name] for name in FIELDS},
                "all_fresh": state["all_fresh"],
            }
        )
    document = {
        "schema": "mlb_scoreboard_track_demo_v1",
        "game_pk": timing["game_pk"],
        "manifest_sha256": timing["manifest_sha256"],
        "media_url": media_url,
        "stale_after_seconds": args.stale_after,
        "templates": str(args.templates),
        "note": "reader output + held state per frame; a demonstration, not labels and not a benchmark",
        "rows": rows,
        "rejected": tracker.rejected,
        "suspect": tracker.suspect,
    }
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
            encoding="utf-8",
        )
    for row in rows:
        read = {k: v for k, v in row["reading"].items() if v is not None}
        ages = {k: row["held"][k]["age_seconds"] for k in ("balls", "outs", "inning")}
        print(
            f"{row['seconds']:7.1f}  read={read if read else 'abstain'}  age={ages}  fresh={row['all_fresh']}"
        )


if __name__ == "__main__":
    main()

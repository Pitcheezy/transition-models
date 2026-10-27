"""Build the private per-pitch clip registry and fetch official clips for chosen games.

    python scripts/75_clip_registry.py register --root D:/pitcheezy_clips --game 849843:dev \
        --game 849844:eval_locked --feed-file 747139=data/raw/mlb_video/747139/feed.json \
        --statcast-parquet 747139=data/raw/2024/statcast_2024.parquet --game 747139:dev
    python scripts/75_clip_registry.py clips --root D:/pitcheezy_clips --delay 1.0
    python scripts/75_clip_registry.py status --root D:/pitcheezy_clips [--out SUMMARY.json]

Video, page and feed bytes stay under --root (outside Git). The summary holds counts and
hashes only.
"""

import argparse
import json
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from src.data import clip_registry as reg
from src.data.mlb_video import PITCH_KEYS, PREPITCH_COLUMNS, TRUTH_COLUMNS

SOURCE_PAUSE_SECONDS = 1.0


def pairs(values, sep):
    result = {}
    for value in values or []:
        key, _, rest = value.partition(sep)
        if not rest:
            raise SystemExit(f"expected KEY{sep}VALUE, got {value!r}")
        if int(key) in result:
            raise SystemExit(f"game {key} given more than once")
        result[int(key)] = rest
    return result


def statcast_source(game_pk, parquet, sleep=time.sleep):
    """Read and validate this game's Statcast rows; nothing is written here."""
    if parquet:
        columns = PITCH_KEYS + PREPITCH_COLUMNS + TRUTH_COLUMNS + reg.OUTCOME_EXTRA
        frame = pd.read_parquet(parquet, columns=columns, filters=[("game_pk", "==", game_pk)])
        data = frame.sort_values(PITCH_KEYS).to_csv(index=False).encode("utf-8")
        name = "statcast_rows.csv"
    else:
        sleep(SOURCE_PAUSE_SECONDS)
        data = reg.fetch(reg.STATCAST_URL.format(game_pk=game_pk), reg.SOURCE_LIMIT)
        name = "statcast.csv"
    frame = reg.read_statcast_csv(data)
    if not (frame.game_pk == game_pk).any():
        raise SystemExit(f"no Statcast rows for game {game_pk}; nothing was saved")
    return frame, data, name


def feed_source(game_pk, feed_file, sleep=time.sleep):
    """Read and validate this game's feed; nothing is written here."""
    if feed_file:
        data = Path(feed_file).read_bytes()
    else:
        sleep(SOURCE_PAUSE_SECONDS)
        data = reg.fetch(reg.FEED_URL.format(game_pk=game_pk), reg.SOURCE_LIMIT)
    if int(json.loads(data)["gamePk"]) != game_pk:
        raise SystemExit(f"feed is not game {game_pk}; nothing was saved")
    return data


def keep_sources(root, game_pk, files):
    """Write the validated source bytes only after every source of the game passed."""
    folder = Path(root) / "sources" / str(game_pk)
    for name, data in files.items():
        reg.write_once(folder / name, data)


def main():
    parser = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawTextHelpFormatter
    )
    sub = parser.add_subparsers(dest="command", required=True)
    register = sub.add_parser("register")
    register.add_argument("--root", type=Path, required=True)
    register.add_argument("--game", action="append", required=True, help="GAME_PK:SPLIT")
    register.add_argument("--feed-file", action="append", help="GAME_PK=PATH")
    register.add_argument("--statcast-parquet", action="append", help="GAME_PK=PATH")
    clips = sub.add_parser("clips")
    clips.add_argument("--root", type=Path, required=True)
    clips.add_argument("--game", action="append", type=int)
    clips.add_argument("--limit", type=int)
    clips.add_argument("--delay", type=float, default=1.0)
    clips.add_argument("--max-attempts", type=int, default=2)
    clips.add_argument(
        "--retry-no-media", action="store_true", help="also retry pages that showed no video"
    )
    report = sub.add_parser("status")
    report.add_argument("--root", type=Path, required=True)
    report.add_argument("--out", type=Path)
    report.add_argument(
        "--no-file-check", action="store_true", help="skip re-hashing downloaded files"
    )
    args = parser.parse_args()

    conn = reg.connect(args.root / "registry.sqlite")
    if args.command == "register":
        games = pairs(args.game, ":")
        feeds, parquets = pairs(args.feed_file, "="), pairs(args.statcast_parquet, "=")
        for game_pk, split in games.items():
            feed = feed_source(game_pk, feeds.get(game_pk))
            frame, statcast, name = statcast_source(game_pk, parquets.get(game_pk))
            keep_sources(args.root, game_pk, {"feed.json": feed, name: statcast})
            counts = reg.register_game(
                conn, args.root, game_pk, split, feed, frame, reg.sha256(statcast)
            )
            print(json.dumps({"game_pk": game_pk, "split": split, "counts": counts}))
    elif args.command == "clips":
        if not math.isfinite(args.delay) or not 1.0 <= args.delay <= 60.0:
            raise SystemExit("delay must be between 1 and 60 seconds")
        counts = reg.run_clips(
            conn,
            args.root,
            games=args.game,
            limit=args.limit,
            delay=args.delay,
            max_attempts=args.max_attempts,
            retry_no_media=args.retry_no_media,
        )
        print(json.dumps(counts))
    else:
        summary = reg.status(conn, None if args.no_file_check else args.root)
        text = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
        print(text)


if __name__ == "__main__":
    main()

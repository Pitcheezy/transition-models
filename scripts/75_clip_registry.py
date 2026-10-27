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
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import pandas as pd

from src.data import clip_registry as reg
from src.data.mlb_video import PITCH_KEYS, PREPITCH_COLUMNS, TRUTH_COLUMNS


def pairs(values, sep):
    result = {}
    for value in values or []:
        key, _, rest = value.partition(sep)
        if not rest:
            raise SystemExit(f"expected KEY{sep}VALUE, got {value!r}")
        result[int(key)] = rest
    return result


def statcast_source(root, game_pk, parquet):
    folder = Path(root) / "sources" / str(game_pk)
    if parquet:
        columns = PITCH_KEYS + PREPITCH_COLUMNS + TRUTH_COLUMNS + reg.OUTCOME_EXTRA
        frame = pd.read_parquet(parquet, columns=columns, filters=[("game_pk", "==", game_pk)])
        data = frame.sort_values(PITCH_KEYS).to_csv(index=False).encode("utf-8")
        reg.write_once(folder / "statcast_rows.csv", data)
    else:
        data = reg.fetch(reg.STATCAST_URL.format(game_pk=game_pk), reg.SOURCE_LIMIT)
        reg.write_once(folder / "statcast.csv", data)
    return reg.read_statcast_csv(data), reg.sha256(data)


def feed_source(root, game_pk, feed_file):
    folder = Path(root) / "sources" / str(game_pk)
    data = (
        Path(feed_file).read_bytes()
        if feed_file
        else reg.fetch(reg.FEED_URL.format(game_pk=game_pk), reg.SOURCE_LIMIT)
    )
    reg.write_once(folder / "feed.json", data)
    return data


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
    report = sub.add_parser("status")
    report.add_argument("--root", type=Path, required=True)
    report.add_argument("--out", type=Path)
    args = parser.parse_args()

    conn = reg.connect(args.root / "registry.sqlite")
    if args.command == "register":
        games = pairs(args.game, ":")
        feeds, parquets = pairs(args.feed_file, "="), pairs(args.statcast_parquet, "=")
        for game_pk, split in games.items():
            feed = feed_source(args.root, game_pk, feeds.get(game_pk))
            frame, statcast_sha = statcast_source(args.root, game_pk, parquets.get(game_pk))
            counts = reg.register_game(conn, args.root, game_pk, split, feed, frame, statcast_sha)
            print(json.dumps({"game_pk": game_pk, "split": split, "counts": counts}))
    elif args.command == "clips":
        if args.delay < 1.0:
            raise SystemExit("delay below 1 second is not allowed")
        counts = reg.run_clips(
            conn,
            args.root,
            games=args.game,
            limit=args.limit,
            delay=args.delay,
            max_attempts=args.max_attempts,
        )
        print(json.dumps(counts))
    else:
        summary = reg.status(conn)
        text = json.dumps(summary, ensure_ascii=False, indent=2) + "\n"
        if args.out:
            args.out.parent.mkdir(parents=True, exist_ok=True)
            args.out.write_text(text, encoding="utf-8")
        print(text)


if __name__ == "__main__":
    main()

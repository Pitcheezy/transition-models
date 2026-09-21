"""Reproduce the P0 game identity audit and inspect public MLB video input sources."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.mlb_sources import fetch_source, media_urls, probe_media
from src.data.mlb_video import write_game_manifest

DEFAULT_PAGE = "https://www.mlb.com/video/9-30-24-mets-win-epic-game-in-playoff-clincher"


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--game-pk", type=int, default=747139)
    parser.add_argument(
        "--statcast", type=Path, default=Path("data/raw/2024/statcast_2024.parquet")
    )
    parser.add_argument("--output-dir", type=Path)
    parser.add_argument(
        "--full-game-page",
        default=None,
        help="Public MLB video page; the known default is used only for game 747139",
    )
    parser.add_argument("--probe", action="store_true", help="Use ffprobe to check playable inputs")
    parser.add_argument("--refresh", action="store_true", help="Replace cached metadata snapshots")
    args = parser.parse_args()
    if args.game_pk <= 0:
        parser.error("game-pk must be positive")
    root = args.output_dir or Path(f"data/raw/mlb_video/{args.game_pk}")
    root.mkdir(parents=True, exist_ok=True)
    feed_path = root / "feed.json"
    if args.refresh or not feed_path.exists():
        fetch_source(f"https://statsapi.mlb.com/api/v1.1/game/{args.game_pk}/feed/live", feed_path)
    if json.loads(feed_path.read_text(encoding="utf-8"))["gamePk"] != args.game_pk:
        parser.error("Cached feed belongs to a different game; select a different output directory")
    manifest = write_game_manifest(args.statcast, feed_path, root / "manifest.json")
    if set(manifest["counts"]) != {"verified"}:
        raise SystemExit("Pitch identity conflicts: inspect manifest before using videos")
    pages = {"first_pitch": manifest["pitches"][0]["video"]["page_url"]}
    full_game = args.full_game_page or (DEFAULT_PAGE if args.game_pk == 747139 else None)
    if full_game:
        pages["full_game"] = full_game
    result = {"game_pk": args.game_pk, "identity_counts": manifest["counts"], "sources": {}}
    for name, url in pages.items():
        path = root / f"{name}_source.html"
        # Pages are refreshed because a user may change the full-game source URL.
        page = fetch_source(url, path).decode("utf-8")
        urls = media_urls(page)
        if not urls:
            raise SystemExit(f"No public MP4 source found on {url}; inspect page manually")
        result["sources"][name] = {
            "page_url": url,
            "observed_mp4_urls": urls,
            "inspection": probe_media(urls[0]) if args.probe else None,
        }
    (root / "sources.json").write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()

"""Bind the fixed 849843 replay to previously downloaded official pitch clips.

No network requests or registry writes. Local SHA checks identify the archived bytes;
they do not assert that a remote server will always return those same bytes. Identity
conflicts are excluded explicitly rather than changing either source's pitch result.
"""

import argparse
import hashlib
import html
import json
import math
import re
import sqlite3
from html.parser import HTMLParser
from pathlib import Path, PurePosixPath
from urllib.parse import urlsplit

GAME_SHA256 = "89e14e12e0f0a2ae2475aff16b8757486143f6a4586239434a1f8b0be6bb3c22"
SCHEMA = "pitcheezy-static-game-media-v1"
SHA_PATTERN = re.compile(r"[0-9a-f]{64}\Z")
UUID_PATTERN = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}\Z")


class CanonicalLinks(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.urls = []

    def handle_starttag(self, tag, attrs):
        values = dict(attrs)
        if tag == "link" and values.get("rel") == "canonical":
            self.urls.append(values.get("href"))


def require(condition, reason):
    if not condition:
        raise ValueError(reason)


def sha256(path):
    digest = hashlib.sha256()
    with Path(path).open("rb") as source:
        for chunk in iter(lambda: source.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _inside(root, value):
    require(isinstance(value, str) and bool(value), "invalid_local_path")
    path = PurePosixPath(value)
    require(
        not path.is_absolute()
        and ".." not in path.parts
        and not any(c in value for c in ("\\", ":", "\x00")),
        "unsafe_local_path",
    )
    full = (root / path).resolve(strict=True)
    require(full.is_relative_to(root.resolve()), "unsafe_local_path")
    require(full.is_file(), "local_file_missing")
    return full


def _verified_file(root, relative, expected_sha, max_bytes, expected_bytes=None):
    require(isinstance(expected_sha, str) and SHA_PATTERN.fullmatch(expected_sha), "invalid_sha256")
    full = _inside(root, relative)
    size = full.stat().st_size
    require(0 < size <= max_bytes, "local_file_size_invalid")
    if expected_bytes is not None:
        require(type(expected_bytes) is int and size == expected_bytes, "local_file_size_mismatch")
    require(sha256(full) == expected_sha, "local_file_sha_mismatch")
    return full


def _video_url(value):
    require(isinstance(value, str) and 0 < len(value) < 2048, "invalid_media_url")
    require(not any(ord(c) < 33 or ord(c) > 126 for c in value), "invalid_media_url")
    parsed = urlsplit(value)
    require(
        parsed.scheme == "https"
        and parsed.netloc == "sporty-clips.mlb.com"
        and not parsed.query
        and not parsed.fragment
        and re.fullmatch(r"/[A-Za-z0-9_=-]+\.mp4", parsed.path),
        "unsafe_media_url",
    )
    return value


def _clip(root, row):
    require(row["status"] == "downloaded", "clip_not_downloaded")
    play = row["play_id"]
    require(isinstance(play, str) and UUID_PATTERN.fullmatch(play), "invalid_play_id")
    video = _video_url(row["media_url"])
    require(json.loads(row["media_candidates"]) == [video], "ambiguous_media_candidates")
    page = _verified_file(root, row["page_path"], row["page_sha256"], 5_000_000)
    raw_page = page.read_text(encoding="utf-8")
    canonical = CanonicalLinks()
    canonical.feed(raw_page)
    page_url = f"https://baseballsavant.mlb.com/sporty-videos?playId={play}"
    require(canonical.urls == [page_url], "page_play_id_mismatch")
    page_text = html.unescape(raw_page)
    observed = set(re.findall(r"https://[^\s<>\"'\\]+\.mp4(?:\?[^\s<>\"'\\]*)?", page_text))
    require(observed == {video}, "page_media_mismatch")
    _verified_file(root, row["file_path"], row["file_sha256"], 80_000_000, row["bytes"])
    duration = row["duration_s"]
    require(
        type(duration) in (int, float) and math.isfinite(duration) and 0 < duration <= 300,
        "invalid_clip_duration",
    )
    return {
        "play_id": play,
        "video": video,
        "page_url": page_url,
        "video_sha256": row["file_sha256"],
        "bytes": row["bytes"],
        "duration_seconds": duration,
    }


def project(rows, game, root, game_sha256, registry_sha256):
    """Produce allowlisted metadata, keeping each excluded pitch in the denominator."""
    require(game["schema"] == "pitcheezy-static-game-v1", "wrong_game_schema")
    require(game["game"]["game_pk"] == 849843, "wrong_game")
    require(
        SHA_PATTERN.fullmatch(game_sha256) and SHA_PATTERN.fullmatch(registry_sha256),
        "invalid_source_sha",
    )
    pitches, registry, play_ids = {}, {}, set()
    for pitch in game["pitches"]:
        pa, number = pitch["at_bat_number"], pitch["pitch_number"]
        require(
            type(pa) is int and type(number) is int and pa > 0 and number > 0, "invalid_pitch_key"
        )
        key = f"849843:{pa}:{number}"
        require(pitch["pitch_id"] == key and key not in pitches, "duplicate_or_wrong_game_pitch_id")
        pitches[key] = pitch
    require(pitches, "empty_game")
    for row in rows:
        require(row["game_pk"] == 849843, "wrong_registry_game")
        pa, number = row["at_bat_number"], row["pitch_number"]
        require(
            type(pa) is int and type(number) is int and pa > 0 and number > 0,
            "invalid_registry_key",
        )
        key = f"849843:{pa}:{number}"
        require(
            key not in registry and row["play_id"] not in play_ids, "duplicate_registry_identity"
        )
        require(key in pitches, "unexpected_registry_pitch")
        registry[key] = row
        play_ids.add(row["play_id"])
    result, excluded = [], []
    for key, pitch in sorted(
        pitches.items(), key=lambda item: (item[1]["at_bat_number"], item[1]["pitch_number"])
    ):
        if key not in registry:
            excluded.append({"pitch_id": key, "reason": "registry_pitch_missing"})
            continue
        row = registry[key]
        try:
            clip = _clip(Path(root), row)
            require(
                isinstance(row["pitch_type"], str) and re.fullmatch(r"[A-Z]{2}", row["pitch_type"]),
                "invalid_pitch_type",
            )
            require(row["pitcher_id"] == pitch["pitcher"]["id"], "pitcher_id_mismatch")
            require(row["batter_id"] == pitch["batter"]["id"], "batter_id_mismatch")
            require(row["inning"] == pitch["situation"]["inning"], "inning_mismatch")
            require(row["inning_topbot"] == pitch["situation"]["half"], "inning_half_mismatch")
            actual = pitch["post"]["actual"]
            require(actual is not None, "actual_result_missing")
            if row["pitch_type"] != actual["pitch_type"]:
                excluded.append(
                    {
                        "pitch_id": key,
                        "reason": "pitch_type_mismatch",
                        "registry_pitch_type": row["pitch_type"],
                        "received_pitch_type": actual["pitch_type"],
                    }
                )
                continue
            result.append(
                {
                    "pitch_id": key,
                    "at_bat_number": pitch["at_bat_number"],
                    "pitch_number": pitch["pitch_number"],
                    "pitcher_id": row["pitcher_id"],
                    "batter_id": row["batter_id"],
                    "pitch_type": row["pitch_type"],
                    **clip,
                }
            )
        except (OSError, UnicodeError):
            excluded.append({"pitch_id": key, "reason": "local_file_unreadable"})
        except (ValueError, TypeError) as error:
            # Only fixed reason codes are published; never OS errors or local paths.
            reason = str(error)
            if not re.fullmatch(r"[a-z_]+", reason):
                reason = "invalid_registry_metadata"
            excluded.append({"pitch_id": key, "reason": reason})
    require(len(result) + len(excluded) == len(pitches), "coverage_mismatch")
    return {
        "schema": SCHEMA,
        "game_pk": 849843,
        "game_sha256": game_sha256,
        "registry_sha256": registry_sha256,
        "source_pitch_count": len(pitches),
        "records": result,
        "excluded": excluded,
    }


def export_game(registry_root, game_path):
    """Read only the fixed development game. Never initialize or update the registry."""
    game_bytes = Path(game_path).read_bytes()
    game_sha = hashlib.sha256(game_bytes).hexdigest()
    require(game_sha == GAME_SHA256, "game_asset_changed")
    game = json.loads(game_bytes)
    require(len(game["pitches"]) == 262, "wrong_game_count")
    root = Path(registry_root).resolve(strict=True)
    db_path = root / "registry.sqlite"
    before = sha256(db_path)
    connection = sqlite3.connect(db_path.as_uri() + "?mode=ro", uri=True)
    connection.row_factory = sqlite3.Row
    try:
        connection.execute("PRAGMA query_only=ON")
        require(
            connection.execute("SELECT value FROM meta WHERE key='schema'").fetchone()[0]
            == "pitcheezy-clip-registry-v1",
            "wrong_registry_schema",
        )
        rows = [
            dict(row)
            for row in connection.execute(
                "SELECT p.game_pk,p.at_bat_number,p.pitch_number,p.play_id,p.pitcher_id,p.batter_id,"
                "p.inning,p.inning_topbot,o.pitch_type,c.status,c.media_url,c.media_candidates,"
                "c.page_path,c.page_sha256,c.file_path,c.file_sha256,c.bytes,c.duration_s "
                "FROM pitches p LEFT JOIN outcomes o USING(play_id) LEFT JOIN clips c USING(play_id) "
                "WHERE p.game_pk=849843"
            )
        ]
        output = project(rows, game, root, game_sha, before)
    finally:
        connection.close()
    require(sha256(db_path) == before, "registry_changed_during_export")
    return output


def serialize(value):
    return (json.dumps(value, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode("utf-8")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--registry-root", type=Path, required=True)
    parser.add_argument("--game", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()
    require(
        not args.out.resolve().is_relative_to(args.registry_root.resolve()),
        "output_inside_registry",
    )
    require(args.out.resolve() != args.game.resolve(), "output_is_source_game")
    value = export_game(args.registry_root, args.game)
    data = serialize(value)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_bytes(data)
    print(
        json.dumps(
            {
                "source_pitches": value["source_pitch_count"],
                "linked": len(value["records"]),
                "excluded": value["excluded"],
                "bytes": len(data),
                "sha256": hashlib.sha256(data).hexdigest(),
            },
            ensure_ascii=False,
        )
    )


if __name__ == "__main__":
    main()

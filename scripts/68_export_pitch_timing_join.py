"""Export the pitch-timing join table we hand to the teammate's Video Lab (schema v2 proposal §6).

Usage::

    uv run --frozen python scripts/68_export_pitch_timing_join.py --output docs/results/mlb_p0/game_747139_pitch_timing_join.json

One file per game. Rows exist only for pitches that have a human-verified timing row; every
row carries ``pitch_id = "{game_pk}:{at_bat_number}:{pitch_number}"`` (the teammate catalog's
id format), the MLB ``play_id``, the Statcast play page, the timing status and, for annotated
pitches, decision / release / uncertainty seconds on the bound media plus the derived lead.
Unavailable pitches keep null times; unreviewed pitches are not listed. Nothing is invented.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.broadcast_timing import KEYS, validate_annotations
from src.data.scoreboard_evalset import read_json

RESULTS = Path("docs/results/mlb_p0")
JOIN_SCHEMA = "transition_models_p0_pitch_timing_join_v1"


def build_join(manifest, sources, timing):
    """Rows for every timing row, joined to the manifest by pitch key and play_id."""
    report = validate_annotations(timing, manifest, sources)
    index = {tuple(p[k] for k in KEYS): p for p in manifest["pitches"]}
    rows = []
    for row in sorted(timing["annotations"], key=lambda r: tuple(r[k] for k in KEYS)):
        key = tuple(row[k] for k in KEYS)
        pitch = index[key]
        annotated = row["status"] == "annotated"
        rows.append(
            {
                "pitch_id": ":".join(str(v) for v in key),
                **{k: row[k] for k in KEYS},
                "play_id": row["play_id"],
                "play_page_url": pitch["video"].get("page_url"),
                "status": row["status"],
                "decision_seconds": row["decision_seconds"],
                "release_seconds": row["release_seconds"],
                "uncertainty_seconds": row["uncertainty_seconds"],
                "lead_seconds": (
                    round(row["release_seconds"] - row["decision_seconds"], 3)
                    if annotated
                    else None
                ),
                "note": row["note"],
            }
        )
    return {
        "schema": JOIN_SCHEMA,
        "game_pk": timing["game_pk"],
        "manifest_sha256": timing["manifest_sha256"],
        "timing_schema": timing["schema"],
        "source": timing["source"],
        "annotator": timing["annotator"],
        "counts": {
            "manifest_verified": report["total_pitches"],
            "timing_rows": len(rows),
            "annotated": report["annotated"],
            "unavailable": report["unavailable"],
            "unreviewed": report["unreviewed"],
        },
        "rules": [
            "times are playback seconds of source.media_url; never apply them to another clip",
            "unavailable rows have null decision/release/uncertainty; unreviewed pitches are absent",
            "feed UTC is not playback time; pitch identity is the key plus play_id",
        ],
        "rows": rows,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=RESULTS / "game_747139_manifest.json")
    parser.add_argument("--sources", type=Path, default=RESULTS / "game_747139_sources.json")
    parser.add_argument("--timing", type=Path, default=RESULTS / "game_747139_timing.json")
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    document = build_join(*(read_json(p) for p in (args.manifest, args.sources, args.timing)))
    rendered = json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False)
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered + "\n", encoding="utf-8")
    print(json.dumps(document["counts"], indent=2))


if __name__ == "__main__":
    main()

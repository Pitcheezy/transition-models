"""Export or check the frozen demo snapshot without images or reader metadata."""

import argparse
import hashlib
import json
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
SOURCES = (
    "game_849843_intent_v0.jsonl",
    "game_849843_intent_calibration_readings_v0.json",
    "game_849843_condensed_scan_v0.json",
    "intent_accuracy_report_v0.json",
)


def keyed(items, key):
    """Reject duplicate identities rather than silently overwrite a pitch."""
    result = {}
    for item in items:
        identity = key(item)
        if identity in result:
            raise ValueError(f"Duplicate pitch: {identity}")
        result[identity] = item
    return result


def build(source):
    """Join only identical pitch keys in the fixed 39-pitch demonstration."""

    def read(name):
        return json.loads((source / name).read_bytes())

    records = keyed(
        [json.loads(line) for line in (source / SOURCES[0]).read_text().splitlines()],
        lambda row: row["pitch_id"],
    )

    def pitch_key(row):
        return f"849843:{row['at_bat_number']}:{row['pitch_number']}"

    catches = keyed(read(SOURCES[1])["catch_pitches"], pitch_key)
    matches = keyed(
        [d["match"] for d in read(SOURCES[2])["detections"] if d.get("match")], pitch_key
    )
    if len(records) != 39 or set(records) != set(catches) or set(records) != set(matches):
        raise ValueError("Expected the same 39 unique pitch keys in all three artifacts.")
    pitches = {}
    for key, row in records.items():
        mitt = row["points"].get("plate_feet", {}).get("x")
        if row["status"] not in {"estimated", "unavailable"} or (
            (mitt is not None) != (row["status"] == "estimated")
        ):
            raise ValueError(f"Invalid coordinate availability: {key}")
        pitches[key] = {
            "pitch_id": key,
            "status": row["status"],
            "unavailable_reason": row["unavailable_reason"],
            "mitt_x_ft": mitt,
            "actual_plate_x_ft": catches[key]["statcast_front"]["pX"],
            "pitch_type": catches[key]["pitch_type"],
            **{
                k: matches[key][k]
                for k in ("batter", "pitcher", "inning", "half", "balls_before", "strikes_before")
            },
        }
    pooled = read(SOURCES[3])["evaluation_pooled"]
    if sum(p["mitt_x_ft"] is not None for p in pitches.values()) != 27:
        raise ValueError("Frozen demo must contain 27 mitt coordinates and 12 abstentions.")
    if (pooled["lines_in_output"], pooled["assistant"]["estimated"]) != (86, 58):
        raise ValueError("The website copy is bound to the frozen M3 report (86/58).")
    return {
        "game": 849843,
        "pitch_count": 262,
        "pitches": pitches,
        "schema": "pitcheezy_demo_display_v1",
        "is_intent_proxy": True,
        "catcher_intent_verified": False,
        "independent_ground_truth": False,
        "live_analysis": False,
        "human_review_demo_game": 0,
        "sources": {n: hashlib.sha256((source / n).read_bytes()).hexdigest() for n in SOURCES},
        "evaluation": {
            "games": pooled["games"],
            "frames": pooled["lines_in_output"],
            "ai_marked": pooled["assistant"]["estimated"],
            "ai_abstained": pooled["assistant"]["unavailable"],
            "human_marked": pooled["person_marked"],
            "human_abstained": pooled["person_abstained"],
            "both_marked": pooled["availability"]["both_marked"],
            "pixel_median": pooled["mitt_reading_pixels"]["distance"]["median"],
            "output_median_ft": pooled["output_vs_person_feet"]["distance"]["median"],
        },
    }


def main():
    """Check by default; require --write to regenerate the derived snapshot."""
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", type=Path, default=ROOT / "docs/results/mlb_p0")
    parser.add_argument("--output", type=Path, default=ROOT / "web/pitch-studio/data.js")
    parser.add_argument("--write", action="store_true")
    args = parser.parse_args()
    payload = build(args.source)
    if args.write:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(
            "window.DEMO_DATA = " + json.dumps(payload, ensure_ascii=False, indent=2) + ";\n",
            encoding="utf-8",
        )
    else:
        readback = subprocess.run(
            [
                "node",
                "-e",
                "const fs=require('node:fs'),vm=require('node:vm');"
                "const context={window:{}};"
                "vm.runInNewContext(fs.readFileSync(process.argv[1],'utf8'),context,{timeout:1000});"
                "process.stdout.write(JSON.stringify(context.window.DEMO_DATA));",
                str(args.output.resolve()),
            ],
            check=True,
            capture_output=True,
            encoding="utf-8",
        )
        if json.loads(readback.stdout) != payload:
            raise ValueError("Snapshot differs from its sources; review before regenerating.")
    print("Verified 39 keyed pitches, 27 coordinates, 12 abstentions and frozen M3 provenance.")


if __name__ == "__main__":
    main()

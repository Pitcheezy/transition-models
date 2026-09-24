"""Append verified candidate rows to the broadcast timing and scoreboard-review files.

Usage::

    uv run --frozen python scripts/69_append_timing_rows.py \
        --candidates docs/results/mlb_p0/game_747139_timing_candidates_pa11_15.json --pa 13
    uv run --frozen python scripts/69_append_timing_rows.py --candidates ... --pa 13 --write

A candidates file (``mlb_broadcast_timing_candidates_v1``) holds annotated rows that are NOT
yet part of ``game_747139_timing.json``. A row may be merged only when its
``verification.status`` is ``"verified"`` (both verifier lenses passed and a person or the
session re-grabbed and looked at the decision and release frames). Every pitch of each
requested plate appearance must be present and verified; a plate appearance already present
in the timing file is refused. Existing rows are never modified or reordered.

Without ``--write`` the merge is only validated in memory. With ``--write`` the timing and
review files are saved and the derived files are rebuilt (validation report, eval set, join
table) unless ``--no-rebuild`` is given.
"""

import argparse
import json
import os
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.data.broadcast_timing import KEYS, validate_annotations  # noqa: E402
from src.data.scoreboard_evalset import (  # noqa: E402
    LABEL_FIELDS,
    build_evalset,
    read_json,
    validate_review,
)

CANDIDATES_SCHEMA = "mlb_broadcast_timing_candidates_v1"
TIMING_FIELDS = ("status", "decision_seconds", "release_seconds", "uncertainty_seconds", "note")
TOPBOT = {"top": "Top", "bot": "Bot", "bottom": "Bot"}


def merge(
    manifest, sources, timing, review, candidates, pas, reviewer, date, allow_unverified=False
):
    """Return (timing, review, report) with the requested plate appearances appended."""
    if candidates.get("schema") != CANDIDATES_SCHEMA:
        raise ValueError(f"Expected {CANDIDATES_SCHEMA}")
    for field in ("game_pk", "manifest_sha256"):
        if candidates.get(field) != timing.get(field):
            raise ValueError(f"Candidates {field} does not match the timing file")
    index = {tuple(p[k] for k in KEYS): p for p in manifest["pitches"]}
    present = {r["at_bat_number"] for r in timing["annotations"]}
    reviewed = {r["at_bat_number"] for r in review["reviews"]}
    by_pa = {}
    for row in candidates["rows"]:
        by_pa.setdefault(row["at_bat_number"], []).append(row)
    new_timing, new_review = [], []
    for pa in sorted(pas):
        if pa in present or pa in reviewed:
            raise ValueError(f"PA {pa} is already in the timing or review file")
        rows = sorted(by_pa.get(pa, []), key=lambda r: r["pitch_number"])
        expected = sorted(k[2] for k in index if k[1] == pa)
        if [r["pitch_number"] for r in rows] != expected:
            raise ValueError(f"PA {pa} candidates do not cover pitches {expected}")
        for row in rows:
            status = row.get("verification", {}).get("status")
            if status != "verified" and not allow_unverified:
                raise ValueError(
                    f"PA {pa} pitch {row['pitch_number']} is not verified (status {status!r})"
                )
            key = (timing["game_pk"], pa, row["pitch_number"])
            play_id = index[key]["video"]["play_id"]
            if row.get("play_id") not in (None, play_id):
                raise ValueError(f"PA {pa} pitch {row['pitch_number']} play_id mismatch")
            base = dict(zip(KEYS, key, strict=True)) | {"play_id": play_id}
            new_timing.append({**base, **{f: row[f] for f in TIMING_FIELDS}})
            if row["status"] == "annotated" and row.get("readability") and row.get("observed"):
                observed = {k: row["observed"].get(k) for k in LABEL_FIELDS}
                half = observed.get("inning_topbot")
                if isinstance(half, str):
                    observed["inning_topbot"] = TOPBOT.get(half.lower(), half)
                new_review.append(
                    {
                        **base,
                        "frame_seconds": row["decision_seconds"],
                        "readability": row["readability"],
                        "observed": observed,
                        "bug_text": row.get("bug_text") or "",
                        "reviewer": reviewer,
                        "reviewed_at": date,
                        "note": "read from the ffmpeg frame grab at the decision frame",
                    }
                )
    timing_new = {**timing, "annotations": [*timing["annotations"], *new_timing]}
    review_new = {**review, "reviews": [*review["reviews"], *new_review]}
    report = validate_annotations(timing_new, manifest, sources)
    validate_review(review_new, manifest, timing_new)
    build_evalset(manifest, sources, timing_new, review_new)
    return timing_new, review_new, report


def dump(path, document):
    path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main():
    results = Path("docs/results/mlb_p0")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--pa", type=int, action="append", required=True)
    parser.add_argument("--manifest", type=Path, default=results / "game_747139_manifest.json")
    parser.add_argument("--sources", type=Path, default=results / "game_747139_sources.json")
    parser.add_argument("--timing", type=Path, default=results / "game_747139_timing.json")
    parser.add_argument(
        "--review", type=Path, default=results / "game_747139_scoreboard_review.json"
    )
    parser.add_argument("--reviewer", required=True, help="who verified the rows, and how")
    parser.add_argument("--annotator-suffix", required=True, help="appended to timing annotator")
    parser.add_argument("--date", required=True, help="YYYY-MM-DD of the verification")
    parser.add_argument("--write", action="store_true")
    parser.add_argument("--no-rebuild", action="store_true")
    args = parser.parse_args()
    manifest, sources, timing, review, candidates = (
        read_json(p)
        for p in (args.manifest, args.sources, args.timing, args.review, args.candidates)
    )
    timing_new, review_new, report = merge(
        manifest, sources, timing, review, candidates, args.pa, args.reviewer, args.date
    )
    if args.annotator_suffix not in timing_new["annotator"]:
        timing_new["annotator"] = timing_new["annotator"] + " + " + args.annotator_suffix
    summary = {k: report[k] for k in ("annotated", "unavailable", "unreviewed")}
    summary["complete_plate_appearances"] = report["complete_plate_appearances"]
    print(json.dumps(summary, indent=2))
    if not args.write:
        print("(dry run; pass --write to save)")
        return
    dump(args.timing, timing_new)
    dump(args.review, review_new)
    if args.no_rebuild:
        return
    env = {**os.environ, "PYTHONIOENCODING": "utf-8"}
    run = [sys.executable]
    commands = [
        [*run, "scripts/63_annotate_broadcast.py", "check", "--annotations", str(args.timing),
         "--output", str(results / "game_747139_timing_validation.json")],
        [*run, "scripts/64_build_scoreboard_evalset.py", "review-check"],
        [*run, "scripts/64_build_scoreboard_evalset.py", "build", "--output",
         str(results / "game_747139_scoreboard_evalset.json")],
        [*run, "scripts/64_build_scoreboard_evalset.py", "check", "--evalset",
         str(results / "game_747139_scoreboard_evalset.json")],
        [*run, "scripts/68_export_pitch_timing_join.py", "--output",
         str(results / "game_747139_pitch_timing_join.json")],
    ]  # fmt: skip
    for command in commands:
        done = subprocess.run(command, cwd=ROOT, capture_output=True, text=True, env=env)
        print(" ".join(command[1:3]), "->", done.returncode)
        if done.returncode != 0:
            sys.exit(done.stderr[-1500:])


if __name__ == "__main__":
    main()

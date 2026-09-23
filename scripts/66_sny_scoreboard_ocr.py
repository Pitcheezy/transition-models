"""SNY scoreboard reader prototype (F-3): templates -> predictions -> score on the eval set.

Usage::

    uv run --frozen python scripts/66_sny_scoreboard_ocr.py templates --template-pas 1 2 --output docs/results/mlb_p0/sny_digit_templates_v0.json
    uv run --frozen python scripts/66_sny_scoreboard_ocr.py predict --templates docs/results/mlb_p0/sny_digit_templates_v0.json --output outputs/scoreboard_ocr/predictions.json
    uv run --frozen python scripts/66_sny_scoreboard_ocr.py score --predictions outputs/scoreboard_ocr/predictions.json --exclude-pas 1 2 --output docs/results/mlb_p0/game_747139_scoreboard_ocr_v0.json

``templates`` cuts digit glyphs from the decision frames of the given plate appearances, paired
with the eval set's verified labels (those frames are then in-sample). ``predict`` reads every
eval-set frame (grabbing missing ones with ffmpeg from the eval set's media_url) and writes one
prediction per pitch with ``null`` for every abstention. ``score`` runs
``score_predictions``; with ``--exclude-pas`` the template-source plate appearances are removed
from the review before the eval set is rebuilt, so they count as ``scoreboard_unreviewed`` and
the reported rates are held-out. Frames are read from ``<frames-dir>/<label>_<t>.jpg``.
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.broadcast_timing import KEYS
from src.data.scoreboard_evalset import (
    LABEL_FIELDS,
    build_evalset,
    read_json,
    score_predictions,
    validate_evalset,
)
from src.vision.frames import frame_path, grab_frame
from src.vision.sny_scoreboard import (
    DIGIT_FIELDS,
    DigitTemplates,
    glyphs_for_label,
    masks,
    read_scoreboard,
)

RESULTS = Path("docs/results/mlb_p0")


def load_frame(entry, args, media_url):
    path = frame_path(args.frames_dir, args.frames_label, entry["frame_seconds"])
    if not path.exists():
        if args.no_grab:
            raise FileNotFoundError(path)
        grab_frame(media_url, entry["frame_seconds"], path)
    from PIL import Image

    return np.asarray(Image.open(path).convert("RGB"))


def write(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, indent=2, ensure_ascii=False, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def inputs(args):
    manifest, sources, timing, review = (
        read_json(p) for p in (args.manifest, args.sources, args.timing, args.review)
    )
    evalset = read_json(args.evalset)
    validate_evalset(evalset, manifest, sources, timing, review)
    return manifest, sources, timing, review, evalset


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("templates", "predict", "score"))
    parser.add_argument("--manifest", type=Path, default=RESULTS / "game_747139_manifest.json")
    parser.add_argument("--sources", type=Path, default=RESULTS / "game_747139_sources.json")
    parser.add_argument("--timing", type=Path, default=RESULTS / "game_747139_timing.json")
    parser.add_argument(
        "--review", type=Path, default=RESULTS / "game_747139_scoreboard_review.json"
    )
    parser.add_argument(
        "--evalset", type=Path, default=RESULTS / "game_747139_scoreboard_evalset.json"
    )
    parser.add_argument("--frames-dir", type=Path, default=Path("outputs/frames"))
    parser.add_argument("--frames-label", default="evalset")
    parser.add_argument(
        "--no-grab", action="store_true", help="fail instead of grabbing missing frames"
    )
    parser.add_argument("--template-pas", type=int, nargs="*", default=[1, 2])
    parser.add_argument("--templates", type=Path)
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--exclude-pas", type=int, nargs="*", default=[])
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    manifest, sources, timing, review, evalset = inputs(args)
    media_url = evalset["source"]["media_url"]

    if args.mode == "templates":
        templates = DigitTemplates()
        used, skipped = [], []
        for entry in evalset["entries"]:
            if entry["at_bat_number"] not in args.template_pas:
                continue
            white, _, _ = masks(load_frame(entry, args, media_url))
            for name in DIGIT_FIELDS:
                if entry["field_status"][name] != "confirmed":
                    continue
                pairs = glyphs_for_label(white, name, entry["labels"][name])
                key = f"PA{entry['at_bat_number']}/{entry['pitch_number']}:{name}"
                if pairs is None:
                    skipped.append(key)
                    continue
                for digit, glyph in pairs:
                    templates.add(digit, glyph)
                used.append(key)
        document = {
            **templates.to_json(),
            "source": {
                "evalset_manifest_sha256": evalset["manifest_sha256"],
                "template_plate_appearances": sorted(args.template_pas),
                "fields_used": used,
                "fields_skipped": skipped,
                "note": "glyphs cut from verified decision frames; these plate appearances are in-sample",
            },
        }
        if args.output:
            write(args.output, document)
        print(
            json.dumps(
                {
                    "digits": {d: len(g) for d, g in templates.templates.items()},
                    "fields_used": len(used),
                    "fields_skipped": skipped,
                },
                indent=2,
            )
        )
        return

    if args.mode == "predict":
        if not args.templates:
            parser.error("predict requires --templates")
        templates = DigitTemplates.from_json(read_json(args.templates))
        predictions, abstain = [], Counter()
        for entry in evalset["entries"]:
            fields = read_scoreboard(load_frame(entry, args, media_url), templates)
            for name in LABEL_FIELDS:
                abstain[name] += fields[name] is None
            predictions.append(
                {
                    **{k: entry[k] for k in KEYS},
                    "play_id": entry["play_id"],
                    "fields": {name: fields[name] for name in LABEL_FIELDS},
                }
            )
        if args.output:
            write(args.output, predictions)
        print(json.dumps({"predictions": len(predictions), "abstained": dict(abstain)}, indent=2))
        return

    if not args.predictions:
        parser.error("score requires --predictions")
    predictions = read_json(args.predictions)
    if args.exclude_pas:
        review = {
            **review,
            "reviews": [r for r in review["reviews"] if r["at_bat_number"] not in args.exclude_pas],
        }
        evalset = build_evalset(manifest, sources, timing, review)
        predictions = [p for p in predictions if p["at_bat_number"] not in args.exclude_pas]
    result = score_predictions(evalset, predictions)
    result["holdout"] = {
        "excluded_plate_appearances": sorted(args.exclude_pas),
        "note": (
            "template-source plate appearances removed from the review before scoring; "
            "their pitches count as scoreboard_unreviewed"
            if args.exclude_pas
            else "no plate appearance excluded; template-source pitches are in-sample"
        ),
    }
    if args.output:
        write(args.output, result)
    summary = {
        name: {
            k: result["per_field"][name][k]
            for k in ("evaluable", "attempted", "correct", "wrong", "abstained")
        }
        for name in LABEL_FIELDS
    }
    print(
        json.dumps(
            {
                "per_field": summary,
                "all_fields": result["all_fields"],
                "non_evaluable_attempts": result["non_evaluable_attempts"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()

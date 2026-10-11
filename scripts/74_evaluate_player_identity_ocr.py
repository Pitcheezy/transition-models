"""Predict and score a development-only player-name OCR baseline on frozen frame evidence."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.blind_review import read_json  # noqa: E402
from src.data.player_identity import ROOT, check_player_identity_evalset  # noqa: E402
from src.evaluation.player_identity_ocr import build_predictions, score_predictions  # noqa: E402

RESULTS = ROOT / "docs/results/mlb_p0"
DEFAULT_EVALSET = RESULTS / "game_747139_player_identity_evalset_pa6.json"
# Canonical PA6 outputs per reader. v2 became the default reader on 2026-09-29 (CHECKLIST
# F-4g: pre-registered criterion met on 13 differing rows, all correct); v1 stays frozen and
# selectable with --reader v1, and no reader may write over another reader's canonical files.
CANONICAL = {
    "v1": (
        RESULTS / "game_747139_player_identity_ocr_v1_predictions.json",
        RESULTS / "game_747139_player_identity_ocr_v1_report.json",
    ),
    "v2": (
        RESULTS / "game_747139_player_identity_ocr_v2_predictions.json",
        RESULTS / "game_747139_player_identity_ocr_v2_report.json",
    ),
}
DEFAULT_READER = "v2"
DEFAULT_PREDICTIONS, DEFAULT_REPORT = CANONICAL[DEFAULT_READER]
PROTECTED_INPUTS = (
    DEFAULT_EVALSET,
    RESULTS / "game_747139_manifest.json",
    RESULTS / "game_747139_timing.json",
    RESULTS / "game_747139_player_identity_review_pa6.json",
    ROOT / "data/raw/mlb_video/747139/feed.json",
)


def _same_file(left, right):
    return left.resolve() == right.resolve() or (
        left.exists() and right.exists() and left.samefile(right)
    )


def _write(path, document):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(
        json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n",
        encoding="utf-8",
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("predict", "score", "check"))
    parser.add_argument("--evalset", type=Path, default=DEFAULT_EVALSET)
    parser.add_argument("--predictions", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument(
        "--verify-frames",
        action="store_true",
        help="also verify local frame bytes/source binding when scoring/checking; predict always does",
    )
    parser.add_argument(
        "--reader",
        choices=("v1", "v2", "v3", "v4"),
        default=DEFAULT_READER,
        help=(
            "v2 (default, current reader: v1 + pre-registered parser options), the frozen v1 "
            "baseline, the v3 preprocessing candidate recorded as failed (F-4d/F-4e), or the "
            "pre-registered v4 reader rules (F-4h: dynamic pitcher crop edge, accent fold). Also "
            "selects which canonical PA6 prediction/report files are used when none is given; "
            "v3 and v4 have no canonical files and always need explicit --predictions/--report"
        ),
    )
    args = parser.parse_args()
    canonical_predictions, canonical_report = CANONICAL.get(args.reader, (None, None))
    other_canonical = [
        path for key, pair in CANONICAL.items() if key != args.reader for path in pair
    ]
    custom_evalset = not _same_file(args.evalset, DEFAULT_EVALSET)
    if args.command == "predict" and custom_evalset and args.predictions is None:
        parser.error("predict with a custom evalset requires explicit --predictions")
    if args.predictions is None and canonical_predictions is None:
        parser.error(f"reader {args.reader} has no canonical predictions; give --predictions")
    args.predictions = args.predictions or canonical_predictions
    custom_predictions = canonical_predictions is None or not _same_file(
        args.predictions, canonical_predictions
    )
    if args.command == "predict" and custom_evalset and not custom_predictions:
        parser.error("custom evalset must not overwrite canonical PA6 predictions")
    if args.command == "predict" and any(_same_file(args.predictions, p) for p in other_canonical):
        parser.error("a reader must not write over another reader's canonical files")
    custom_inputs = custom_evalset or custom_predictions
    if args.command == "score" and custom_inputs and args.report is None:
        parser.error("score with custom inputs requires explicit --report")
    if args.command != "predict" and args.report is None and canonical_report is None:
        parser.error(f"reader {args.reader} has no canonical report; give --report")
    args.report = args.report or canonical_report
    if args.command == "score" and custom_inputs and canonical_report is not None:
        if _same_file(args.report, canonical_report):
            parser.error("custom inputs must not overwrite canonical PA6 report")
    if args.command == "score" and any(_same_file(args.report, p) for p in other_canonical):
        parser.error("a reader must not write over another reader's canonical files")
    if args.command in ("predict", "score"):
        output = args.predictions if args.command == "predict" else args.report
        inputs = (
            args.evalset,
            *[
                p
                for p in (
                    args.report if args.command == "predict" else args.predictions,
                    canonical_report if args.command == "predict" else canonical_predictions,
                )
                if p
            ],
            *PROTECTED_INPUTS,
        )
        if any(_same_file(output, path) for path in inputs):
            parser.error(
                "output must not alias evalset, predictions/report or manual source inputs"
            )
    evalset = read_json(args.evalset)
    check_player_identity_evalset(evalset, verify_frames=args.verify_frames)
    if args.command == "predict":
        # Import/initialize Windows OCR only for actual prediction; scoring remains portable.
        from src.vision.sny_player_names import (
            CONFIG,
            CONFIG_V2,
            CONFIG_V3,
            CONFIG_V4,
            SNYPlayerNameReader,
        )

        configs = {"v1": CONFIG, "v2": CONFIG_V2, "v3": CONFIG_V3, "v4": CONFIG_V4}
        reader = SNYPlayerNameReader(config=configs[args.reader])
        predictions = build_predictions(evalset, reader)
        report = score_predictions(evalset, predictions)
        _write(args.predictions, predictions)
    else:
        predictions = read_json(args.predictions)
        report = score_predictions(evalset, predictions)
        if args.command == "score":
            _write(args.report, report)
        elif read_json(args.report) != report:
            raise ValueError("Saved OCR report differs from a fresh keyed score of frozen inputs")
    summary = {
        "command": args.command,
        "names": report["names"],
        "identities": report["identities"],
        "lineup": report["lineup"],
        "context_diagnostics": {
            key: value for key, value in report["context_diagnostics"].items() if key != "rows"
        },
        "reader_errors": report["reader_errors"],
        "pipeline_matches_current_code": report["pipeline_matches_current_code"],
        "local_frames_reverified": args.command == "predict" or args.verify_frames,
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

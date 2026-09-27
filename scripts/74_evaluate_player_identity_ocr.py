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
DEFAULT_PREDICTIONS = RESULTS / "game_747139_player_identity_ocr_v1_predictions.json"
DEFAULT_REPORT = RESULTS / "game_747139_player_identity_ocr_v1_report.json"
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
    args = parser.parse_args()
    custom_evalset = not _same_file(args.evalset, DEFAULT_EVALSET)
    if args.command == "predict" and custom_evalset and args.predictions is None:
        parser.error("predict with a custom evalset requires explicit --predictions")
    args.predictions = args.predictions or DEFAULT_PREDICTIONS
    custom_predictions = not _same_file(args.predictions, DEFAULT_PREDICTIONS)
    if args.command == "predict" and custom_evalset and not custom_predictions:
        parser.error("custom evalset must not overwrite canonical PA6 predictions")
    custom_inputs = custom_evalset or custom_predictions
    if args.command == "score" and custom_inputs and args.report is None:
        parser.error("score with custom inputs requires explicit --report")
    args.report = args.report or DEFAULT_REPORT
    if args.command == "score" and custom_inputs and _same_file(args.report, DEFAULT_REPORT):
        parser.error("custom inputs must not overwrite canonical PA6 report")
    if args.command in ("predict", "score"):
        output = args.predictions if args.command == "predict" else args.report
        inputs = (
            args.evalset,
            args.report if args.command == "predict" else args.predictions,
            DEFAULT_REPORT if args.command == "predict" else DEFAULT_PREDICTIONS,
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
        from src.vision.sny_player_names import SNYPlayerNameReader

        predictions = build_predictions(evalset, SNYPlayerNameReader())
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

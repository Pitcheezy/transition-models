"""Prepare a resumable manual annotation page or validate exported pitch timings.

Annotation times are playback seconds observed directly in the source video. Broadcasts may
be edited: never convert, extrapolate, or interpolate playback seconds from feed UTC.
"""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.broadcast_timing import timing_context, validate_annotations

ROOT = Path(__file__).resolve().parents[1]


def read_json(path):
    return json.loads(path.read_text(encoding="utf-8-sig"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("mode", choices=("prepare", "check"))
    parser.add_argument(
        "--manifest", type=Path, default=Path("docs/results/mlb_p0/game_747139_manifest.json")
    )
    parser.add_argument(
        "--sources", type=Path, default=Path("docs/results/mlb_p0/game_747139_sources.json")
    )
    parser.add_argument("--annotations", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument(
        "--require-pa", type=int, help="Fail unless every pitch in this PA is annotated"
    )
    args = parser.parse_args()
    manifest, sources = read_json(args.manifest), read_json(args.sources)
    context = timing_context(manifest, sources)
    if args.mode == "prepare":
        if args.annotations or args.require_pa is not None:
            parser.error("--annotations and --require-pa are for check mode")
        payload = {
            "context": context,
            "pitches": [
                {
                    **{k: p[k] for k in ("game_pk", "at_bat_number", "pitch_number")},
                    "play_id": p["video"]["play_id"],
                    "pre_state": p["pre_state"],
                }
                for p in manifest["pitches"]
            ],
        }
        static = ROOT / "src/web/static"
        page = (static / "annotation.html").read_text(encoding="utf-8")
        # JSON must not terminate the inert script element, even with hostile metadata.
        data = json.dumps(payload, ensure_ascii=False, allow_nan=False).replace("<", "\\u003c")
        page = page.replace("__ANNOTATION_DATA__", data)
        page = page.replace(
            "__ANNOTATION_SCRIPT__", (static / "annotation.js").read_text(encoding="utf-8")
        )
        output = args.output or Path("outputs/annotation/index.html")
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(page, encoding="utf-8")
        print(f"Prepared {output}; no video downloaded. Serve this directory on localhost.")
    else:
        if not args.annotations:
            parser.error("check requires --annotations")
        report = validate_annotations(read_json(args.annotations), manifest, sources)
        if (
            args.require_pa is not None
            and args.require_pa not in report["complete_plate_appearances"]
        ):
            parser.error(f"PA {args.require_pa} does not have complete timing annotations")
        rendered = json.dumps(report, indent=2, ensure_ascii=False, allow_nan=False)
        if args.output:
            args.output.parent.mkdir(parents=True, exist_ok=True)
            args.output.write_text(rendered, encoding="utf-8")
        print(rendered)


if __name__ == "__main__":
    main()

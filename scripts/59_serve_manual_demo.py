"""Serve the real operational model with manual pre-pitch state input on localhost."""

import argparse
import json
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.inference.prepitch_contract import PrePitchState
from src.inference.recommendation import OperationalRecommender
from src.web.manual_server import create_server


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, default=Path("data/operational_20260921_v2"))
    parser.add_argument(
        "--evaluation-dir", type=Path, default=Path("outputs/operational_20260921/evaluation")
    )
    parser.add_argument(
        "--nuisance-dir", type=Path, default=Path("outputs/operational_20260921/policy_nuisance_v2")
    )
    parser.add_argument("--runs-dir", type=Path)
    parser.add_argument(
        "--state-json",
        type=Path,
        default=Path("docs/results/operational_20260921/example_state.json"),
    )
    parser.add_argument("--port", type=int, default=8770)
    video_options = parser.add_mutually_exclusive_group()
    video_options.add_argument(
        "--video-url", help="Optional broadcast media URL; never used as model input"
    )
    video_options.add_argument(
        "--with-example-video",
        action="store_true",
        help="Use the inspected public MLB full-game source",
    )
    args = parser.parse_args()
    if not 1 <= args.port <= 65535:
        parser.error("port must be 1–65535")
    torch.set_num_threads(1)
    state = json.loads(args.state_json.read_text(encoding="utf-8"))
    PrePitchState.from_dict(state)
    predictor = OperationalRecommender(
        args.data_dir, args.evaluation_dir, args.nuisance_dir, args.runs_dir
    )
    video_url = args.video_url
    if args.with_example_video:
        media = json.loads(
            (
                Path(__file__).resolve().parents[1] / "docs/results/mlb_p0/media_inspection.json"
            ).read_text()
        )
        video_url = media["full_game_page"]["url"]
    server = create_server(predictor, state, args.port, video_url)
    print(f"SmartPitch manual demo: http://127.0.0.1:{args.port} (OCR not enabled)", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()


if __name__ == "__main__":
    main()

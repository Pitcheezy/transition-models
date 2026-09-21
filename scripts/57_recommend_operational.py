"""Run a saved operational policy on a JSON pre-pitch state using the verified shared builder."""

import argparse
import json
import sys
from pathlib import Path

import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.inference.recommendation import OperationalRecommender


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--evaluation-dir", type=Path, required=True)
    parser.add_argument("--nuisance-dir", type=Path, required=True)
    parser.add_argument("--state-json", type=Path, required=True)
    parser.add_argument("--runs-dir", type=Path, help="Override model root after moving artifacts")
    args = parser.parse_args()
    torch.set_num_threads(1)
    model = OperationalRecommender(
        args.data_dir, args.evaluation_dir, args.nuisance_dir, args.runs_dir
    )
    state = json.loads(args.state_json.read_text(encoding="utf-8"))
    print(json.dumps(model.predict(state), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()

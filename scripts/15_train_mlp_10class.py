"""Train the MLP 10-class baseline using verified point identities.

Use --data-dir and a new --run-dir. CE is the probability-estimation default.
Historical loss/weighting choices remain explicit CLI options.
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.training.point_baselines import main

if __name__ == "__main__":
    main("mlp")

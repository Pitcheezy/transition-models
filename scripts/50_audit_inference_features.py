"""Measure the production 135d builder's feature shift on verified test pitches."""

import argparse
import json
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.point_data import PITCH_KEYS, identity_hash, load_point_data
from src.evaluation.point_metrics import probability_metrics
from src.inference.transition_model import build_135dim_feature
from src.models.otremba_mlp import OtrembaMLP
from src.training.point_baselines import predict_mlp


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", type=Path, required=True)
    parser.add_argument("--raw-test-year", type=Path, required=True)
    parser.add_argument(
        "--arsenal", type=Path, default=Path("outputs/arsenal_by_pitcher_cluster.json")
    )
    parser.add_argument("--checkpoints", nargs="+", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError(args.output)
    torch.set_num_threads(2)
    data = load_point_data(args.data_dir, "test", 135)
    raw = pd.read_parquet(args.raw_test_year, columns=PITCH_KEYS + ["pitcher"])
    rows = pd.DataFrame(data["pitch_ids"], columns=PITCH_KEYS).merge(
        raw, on=PITCH_KEYS, how="left", sort=False, validate="one_to_one"
    )
    if rows["pitcher"].isna().any():
        raise ValueError("Test pitch missing pitcher identity")
    arsenal = json.loads(args.arsenal.read_text(encoding="utf-8"))
    pitchers = rows["pitcher"].astype(int).astype(str)
    cluster_ids = pitchers.map(arsenal["pitcher_to_cluster"])
    fallback_count = int(cluster_ids.isna().sum())
    cluster_ids = cluster_ids.fillna("0").astype(str)
    observed = data["vectors"]
    builder = observed.copy()
    for cluster in cluster_ids.unique():
        template = build_135dim_feature(
            np.zeros(77, dtype=np.float32), arsenal, pitcher_cluster=int(cluster)
        )
        builder[cluster_ids.to_numpy() == cluster, 77:] = template[77:]
    # Validate the grouped fast path against the real per-pitch inference builder.
    for i in np.linspace(0, len(rows) - 1, 100, dtype=int):
        actual = build_135dim_feature(observed[i, :77], arsenal, pitcher_id=int(pitchers.iloc[i]))
        np.testing.assert_array_equal(builder[i], actual)
    report = {
        "test_pitch_ids_sha256": identity_hash(data["pitch_ids"]),
        "n": len(rows),
        "unknown_pitcher_fallback_rows": fallback_count,
        "scope": "Sensitivity diagnostic. Observed pitch type and realized zone retained in all "
        "modes; this is not a pre-pitch policy evaluation or execution-error model.",
        "mean_physics": "Zeros equal normalized global training means, the RL builder fallback "
        "when no pitch-specific feature means are supplied.",
        "count_cluster_feature_changed_fraction": float(np.mean(observed[:, 82] != builder[:, 82])),
        "checkpoints": {},
    }
    for path in args.checkpoints:
        state = torch.load(path, map_location="cpu", weights_only=False)
        model = OtrembaMLP(135, 128, 10, dropout=0.2)
        model.load_state_dict(state["model_state"])
        result = {}
        for mode in (
            "observed",
            "umap_mean_only",
            "cluster_builder",
            "cluster_builder_mean_physics",
        ):
            features = observed.copy() if mode in ("observed", "umap_mean_only") else builder.copy()
            if mode == "umap_mean_only":
                features[:, 77:82] = 0
            elif mode == "cluster_builder_mean_physics":
                features[:, :15] = 0
            probs = predict_mlp(model, features, torch.device("cpu"))
            result[mode] = probability_metrics(probs, data["labels"])
            print(path.name, mode, result[mode]["top1"], result[mode]["ce"], flush=True)
            del features, probs
        report["checkpoints"][str(path)] = result
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2), encoding="utf-8")


if __name__ == "__main__":
    main()

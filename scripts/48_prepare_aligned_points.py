"""Recover verified common 77/135d cohorts without changing legacy artifacts."""

import argparse
import gc
import hashlib
import json
import pickle
import shutil
import sys
from pathlib import Path

import numpy as np
import pandas as pd
import torch

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.features import CONTINUOUS_FEATURES
from src.data.point_data import PITCH_KEYS, identity_hash, make_point_data
from src.data.preprocess import build_vectors_batch, clean_dataframe, split_by_season


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--raw-dir", type=Path, default=Path("data/raw"))
    parser.add_argument("--legacy-dir", type=Path, default=Path("data/processed"))
    parser.add_argument("--handoff", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()
    args.output_dir.mkdir(parents=True, exist_ok=False)
    columns = list(
        dict.fromkeys(
            CONTINUOUS_FEATURES
            + PITCH_KEYS
            + [
                "game_date",
                "description",
                "events",
                "pitch_type",
                "zone",
                "balls",
                "strikes",
                "outs_when_up",
                "on_1b",
                "on_2b",
                "on_3b",
                "stand",
                "p_throws",
                "inning",
            ]
        )
    )
    raw = pd.concat(
        [
            pd.read_parquet(args.raw_dir / str(y) / f"statcast_{y}.parquet", columns=columns)
            for y in (2022, 2023, 2024)
        ],
        ignore_index=True,
    )
    splits = split_by_season(clean_dataframe(raw), train_years=[2022, 2023])
    del raw
    extra = (
        [f"umap_5d_{i}" for i in range(5)]
        + ["count_cluster_id"]
        + [f"arsenal_func_{i:02d}" for i in range(32)]
        + [f"arsenal_moment_{i:02d}" for i in range(20)]
    )
    handoff = pd.read_parquet(args.handoff, columns=PITCH_KEYS + extra)
    if handoff.duplicated(PITCH_KEYS).any():
        raise ValueError("Duplicate handoff pitch keys; resolve upstream instead of keeping first")
    with open(args.legacy_dir / "scaler.pkl", "rb") as handle:
        scaler = pickle.load(handle)
    with open(args.legacy_dir / "scaler_new58.pkl", "rb") as handle:
        scaler58 = pickle.load(handle)
    pitch_types = json.loads((args.legacy_dir / "pitch_types.json").read_text())
    preprocessing_hashes = {}
    for filename in ("scaler.pkl", "scaler_new58.pkl", "pitch_types.json"):
        source = args.legacy_dir / filename
        preprocessing_hashes[filename] = hashlib.sha256(source.read_bytes()).hexdigest()
        shutil.copyfile(source, args.output_dir / filename)
    audit = {
        "schema_version": 1,
        "scope": "retrospective observed-pitch classification",
        "upstream_feature_time_provenance": "not established",
        "preprocessing_sha256": preprocessing_hashes,
        "splits": {},
    }
    all_ids = []
    for name, frame in splits.items():
        print(f"Verifying {name}: {len(frame):,} raw-clean rows", flush=True)
        vectors = build_vectors_batch(frame, scaler, pitch_types, model="B")
        legacy = torch.load(args.legacy_dir / f"model_b_{name}.pt", weights_only=False)
        if not np.array_equal(vectors, np.asarray(legacy["vectors"])):
            raise ValueError(f"{name}: reconstructed 77d vectors differ from legacy")
        point = make_point_data(frame, vectors)
        old_targets = np.load(args.legacy_dir / f"labels_10_{name}.npy")
        mismatches = int(np.sum(point["labels_10"] != old_targets))
        joined = frame[PITCH_KEYS].merge(
            handoff, on=PITCH_KEYS, how="left", sort=False, validate="one_to_one"
        )
        raw58 = joined[extra].to_numpy(dtype=np.float32)
        valid = np.isfinite(raw58).all(axis=1)
        normalized58 = scaler58.transform(raw58[valid]).astype(np.float32)
        combined = np.concatenate([vectors[valid], normalized58], axis=1)
        reference = np.load(args.legacy_dir / f"vectors_b3_10cls_{name}.npy", mmap_mode="r")
        labels = np.load(args.legacy_dir / f"labels_10_b3_{name}.npy")
        if not np.array_equal(combined, reference):
            raise ValueError(f"{name}: reconstructed 135d vectors differ from legacy")
        if not np.array_equal(point["labels_10"][valid], labels):
            raise ValueError(f"{name}: reconstructed 135d targets differ from legacy")
        common = {
            key: value[valid] if key in ("labels_4", "labels_10", "pitch_ids") else value
            for key, value in point.items()
            if key != "vectors"
        }
        common["vectors"] = combined
        np.savez(args.output_dir / f"point_{name}.npz", **common)
        all_ids.append(common["pitch_ids"])
        audit["splits"][name] = {
            "clean_rows": len(frame),
            "common_rows": int(valid.sum()),
            "legacy_77_target_mismatches": mismatches,
            "legacy_77_target_mismatch_fraction": mismatches / len(frame),
            "verified_77_vectors_exact": True,
            "verified_135_vectors_and_targets_exact": True,
            "pitch_ids_sha256": identity_hash(common["pitch_ids"]),
        }
        print(json.dumps(audit["splits"][name]), flush=True)
        del vectors, legacy, point, joined, raw58, normalized58, combined, reference, common
        gc.collect()
    if pd.DataFrame(np.concatenate(all_ids)).duplicated().any():
        raise ValueError("Cross-split duplicate pitch IDs")
    (args.output_dir / "audit.json").write_text(json.dumps(audit, indent=2), encoding="utf-8")
    print("Verified common cohorts saved.", flush=True)


if __name__ == "__main__":
    main()

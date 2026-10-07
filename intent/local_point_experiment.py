"""Frozen cross-game development regression on legacy marked points only.

All six final checkpoints are sealed before evaluation. The training function sees
only its declared training game's RGB crops and normalized points. No detector,
negative, abstention-quality, current-protocol, or unseen-accuracy claim is made.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import io
import json
import math
import re
import statistics
import time
from collections import Counter
from pathlib import Path

import numpy as np
from PIL import Image

from intent.replay import _no_links

PLAN_SCHEMA = "local_point_experiment_plan_v1"
REPORT_SCHEMA = "local_point_experiment_report_v1"
EXPECTED_COUNTS = {823407: (29, 28), 849845: (57, 56)}
DIRECTIONS = [
    {"train_game": 823407, "test_game": 849845},
    {"train_game": 849845, "test_game": 823407},
]
SETTINGS = {
    "seeds": [42, 43, 44],
    "epochs": 20,
    "batch_size": 8,
    "lr": 0.001,
    "weight_decay": 0.0001,
    "threads": 4,
    "input_size": [192, 128],
    "input_view": "legacy_main_crop",
}
PLAN_FIELDS = {
    "schema",
    "manifest",
    "manifest_sha256",
    "references",
    "references_sha256",
    "device",
    "directions",
    "code_files",
    *SETTINGS,
}
REQUIRED_CODE_FILES = {
    Path(__file__).resolve(),
    Path(__file__).with_name("local_point_model.py").resolve(),
}
LIMITATIONS = [
    "Previously reviewed legacy single-labeler points; conditional development comparison only.",
    "Fixed manual camera crops and known marked frames; not glove detection or automatic ROI selection.",
    "Legacy abstentions are excluded, not negatives or current-protocol abstention labels.",
    "Neither unseen nor independent validation; no current mitt-body protocol accuracy claim.",
    "Three seeds repeat the same 84 marked frames; 252 predictions are not 252 independent samples.",
    "No physical-coordinate accuracy, intent, pre-pitch availability, or policy-utility claim.",
]


class FrozenInputError(ValueError):
    """A source or sealed checkpoint changed during the experiment."""


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _file(value):
    path = Path(value).absolute()
    _no_links(path)
    if not path.is_file():
        raise ValueError("Expected a regular existing file")
    return path.resolve()


def _digest(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Full lowercase SHA256 required")
    return value


def _json(path):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise ValueError("Duplicate JSON field")
            result[key] = value
        return result

    def constant(_):
        raise ValueError("Nonfinite JSON value")

    raw = _file(path).read_bytes()
    document = json.loads(raw, object_pairs_hook=pairs, parse_constant=constant)
    if not isinstance(document, dict):
        raise ValueError("Expected JSON object")
    return document, raw


def _write(path, value):
    raw = (json.dumps(value, indent=2, allow_nan=False) + "\n").encode()
    _no_links(path)
    with path.open("xb") as stream:
        stream.write(raw)
    return _sha(raw)


def _number(value):
    if type(value) not in (float, int) or not math.isfinite(value):
        raise ValueError("Finite numeric value required")
    return float(value)


def _index(rows, name):
    if not isinstance(rows, list):
        raise ValueError(f"{name} must be a list")
    result = {}
    for row in rows:
        identity = row.get("observation_id") if isinstance(row, dict) else None
        if not isinstance(identity, str) or not re.fullmatch(
            r"[1-9]\d*:[1-9]\d*:[1-9]\d*", identity
        ):
            raise ValueError(f"Invalid {name} observation ID")
        if identity in result:
            raise ValueError(f"Duplicate {name} observation ID")
        result[identity] = row
    return result


def _image(frame):
    raw = _file(frame["image_path"]).read_bytes()
    if _sha(raw) != frame["image_sha256"]:
        raise FrozenInputError("Original image SHA256 mismatch")
    with Image.open(io.BytesIO(raw)) as image:
        if image.format != "JPEG" or image.size != (frame["width"], frame["height"]):
            raise ValueError("Original full-frame JPEG dimensions mismatch")
        image.load()
        return image.convert("RGB")


def _inputs(plan_path):
    plan, raw_plan = _json(plan_path)
    if set(plan) != PLAN_FIELDS or plan.get("schema") != PLAN_SCHEMA:
        raise ValueError("Unexpected point-experiment plan")
    if plan["device"] not in ("cpu", "cuda") or plan["directions"] != DIRECTIONS:
        raise ValueError("Explicit supported device and fixed cross-game directions required")
    for key, expected in SETTINGS.items():
        if type(plan[key]) is not type(expected) or plan[key] != expected:
            raise ValueError(f"Experiment setting differs from frozen protocol: {key}")
    bindings = [(str(_file(plan_path)), _sha(raw_plan), "plan")]
    code_paths = set()
    if not isinstance(plan["code_files"], list):
        raise ValueError("Code bindings required")
    for row in plan["code_files"]:
        if not isinstance(row, dict) or set(row) != {"path", "sha256"}:
            raise ValueError("Invalid code binding")
        path = _file(row["path"])
        if path in code_paths or _sha(path.read_bytes()) != _digest(row["sha256"]):
            raise ValueError("Duplicate or changed code binding")
        code_paths.add(path)
        bindings.append((str(path), row["sha256"], "code"))
    if not REQUIRED_CODE_FILES <= code_paths:
        raise ValueError("Actual experiment and model source must be hash-bound")
    manifest, raw_manifest = _json(plan["manifest"])
    references, raw_references = _json(plan["references"])
    if (
        _sha(raw_manifest) != _digest(plan["manifest_sha256"])
        or _sha(raw_references) != _digest(plan["references_sha256"])
        or manifest.get("schema") != "local_glove_frames_v1"
        or references.get("schema") != "local_glove_references_v1"
        or references.get("manifest_sha256") != plan["manifest_sha256"]
    ):
        raise ValueError("Manifest/reference schema or SHA256 binding mismatch")
    for name, raw in (("manifest", raw_manifest), ("references", raw_references)):
        bindings.append((str(_file(plan[name])), _sha(raw), name))
    frames = _index(manifest.get("frames"), "frames")
    refs = _index(references.get("references"), "references")
    if frames.keys() != refs.keys():
        raise ValueError("Frame/reference ID sets differ")
    cohorts = {game: [] for game in EXPECTED_COUNTS}
    totals, crops, seen_hashes, excluded = Counter(), {}, set(), []
    for identity in sorted(frames, key=lambda key: tuple(map(int, key.split(":")))):
        frame, reference = frames[identity], refs[identity]
        game = frame.get("game_pk")
        if (
            type(game) is not int
            or game not in cohorts
            or reference.get("game_pk") != game
            or int(identity.split(":")[0]) != game
        ):
            raise ValueError("Frame/reference game mismatch")
        totals[game] += 1
        digest = _digest(frame.get("image_sha256"))
        if digest in seen_hashes or reference.get("image_sha256") != digest:
            raise ValueError("Duplicate or mismatched source image hash")
        seen_hashes.add(digest)
        if any(type(frame.get(k)) is not int or frame[k] <= 0 for k in ("width", "height")):
            raise ValueError("Invalid full-frame dimensions")
        if (
            not isinstance(frame.get("image_path"), str)
            or not Path(frame["image_path"]).is_absolute()
        ):
            raise ValueError("Original image path must be explicit and absolute")
        crop = frame.get("legacy_main_crop")
        if not isinstance(crop, list) or len(crop) != 4 or any(type(v) is not int for v in crop):
            raise ValueError("Fixed crop must contain four integer edges")
        left, top, right, bottom = crop
        if not 0 <= left < right <= frame["width"] or not 0 <= top < bottom <= frame["height"]:
            raise ValueError("Crop outside original frame")
        if game in crops and crops[game] != crop:
            raise ValueError("Crop must be fixed per game, not per reference point")
        crops[game] = crop
        with _image(frame):
            pass
        bindings.append((str(_file(frame["image_path"])), digest, "image"))
        status, point = reference.get("legacy_mitt_status"), reference.get("mitt")
        if status not in ("marked", "hidden", "not_in_setup", "not_centre_field"):
            raise ValueError("Unexpected legacy reference status")
        if status != "marked":
            if point is not None:
                raise ValueError("Legacy abstention must not carry a point")
            excluded.append(
                {
                    "observation_id": identity,
                    "game_pk": game,
                    "legacy_mitt_status": status,
                    "reason": "legacy_nonmarked_is_not_a_negative",
                }
            )
            continue
        if not isinstance(point, list) or len(point) != 2:
            raise ValueError("Marked legacy reference needs two coordinates")
        x, y = map(_number, point)
        if not left <= x < right or not top <= y < bottom:
            raise ValueError("Legacy marked point outside fixed crop")
        cohorts[game].append(
            {
                "frame": frame,
                "point": [x, y],
                "normalized_point": [(x - left) / (right - left), (y - top) / (bottom - top)],
            }
        )
    for game, (total, marked) in EXPECTED_COUNTS.items():
        if totals[game] != total or len(cohorts[game]) != marked:
            raise ValueError("Frozen 86-frame/84-marked cohort count differs")
    return plan, raw_plan, cohorts, excluded, bindings


def _verify(bindings):
    for path, expected, kind in bindings:
        try:
            actual = _sha(_file(path).read_bytes())
        except Exception as exc:
            raise FrozenInputError(f"Frozen {kind} unavailable") from exc
        if actual != expected:
            raise FrozenInputError(f"Frozen {kind} changed")


def _arrays(rows):
    images = []
    for row in rows:
        frame = row["frame"]
        with _image(frame) as image:
            crop = image.crop(frame["legacy_main_crop"]).resize(
                (192, 128), Image.Resampling.BILINEAR
            )
            array = np.asarray(crop, dtype=np.float32) / np.float32(255)
            images.append(np.ascontiguousarray(array.transpose(2, 0, 1)))
    return np.stack(images), np.asarray([row["normalized_point"] for row in rows], dtype=np.float32)


def _save_checkpoint(checkpoint, path):
    importlib.import_module("src")
    torch = importlib.import_module("torch")
    with path.open("xb") as stream:
        torch.save(checkpoint, stream)


def _arms():
    return [
        dict(direction, seed=seed, arm_id=f"train_{direction['train_game']}_seed_{seed}")
        for direction in DIRECTIONS
        for seed in SETTINGS["seeds"]
    ]


def _prediction_array(value, count):
    if hasattr(value, "detach"):
        value = value.detach().cpu().numpy()
    array = np.asarray(value)
    if array.shape != (count, 2) or array.dtype.kind != "f":
        raise ValueError("Predictions must be a floating [planned_count,2] array")
    return array


def _stats(values):
    values = sorted(float(v) for v in values)
    if not values:
        return {"n": 0, "mean": None, "median": None, "p90": None}
    return {
        "n": len(values),
        "mean": statistics.fmean(values),
        "median": statistics.median(values),
        "p90": values[math.ceil(0.9 * len(values)) - 1],
    }


def _errors(prediction, reference):
    frame = reference["frame"]
    left, top, right, bottom = frame["legacy_main_crop"]
    x, y = left + prediction[0] * (right - left), top + prediction[1] * (bottom - top)
    dx, dy = x - reference["point"][0], y - reference["point"][1]
    du, dv = (
        prediction[0] - reference["normalized_point"][0],
        prediction[1] - reference["normalized_point"][1],
    )
    return {
        "dx_pixels": dx,
        "dy_pixels": dy,
        "distance_pixels": math.hypot(dx, dy),
        "du_crop": du,
        "dv_crop": dv,
        "distance_crop": math.hypot(du, dv),
    }


def _metrics(rows):
    return {
        key: _stats([row[key] for row in rows])
        for key in (
            "dx_pixels",
            "dy_pixels",
            "distance_pixels",
            "du_crop",
            "dv_crop",
            "distance_crop",
        )
    }


def _summarize(cohorts, evaluations, training, *, usable):
    results = []
    per_seed = {
        seed: {
            "states": Counter(),
            "model": [],
            "baselines": {"crop_center": [], "training_game_mean": []},
            "paired": {
                name: {"distance_pixels": [], "distance_crop": []}
                for name in ("crop_center", "training_game_mean")
            },
        }
        for seed in SETTINGS["seeds"]
    }
    for arm in _arms():
        key = arm["arm_id"]
        seed_pool = per_seed[arm["seed"]]
        expected = {row["frame"]["observation_id"]: row for row in cohorts[arm["test_game"]]}
        evaluation = evaluations[key]
        indexed = _index(evaluation["predictions"], "predictions")
        if indexed.keys() != expected.keys():
            raise ValueError("Evaluation rows must preserve every planned marked reference")
        mean = np.mean(
            [row["normalized_point"] for row in cohorts[arm["train_game"]]], axis=0
        ).tolist()
        baselines = {"crop_center": [0.5, 0.5], "training_game_mean": mean}
        baseline_errors = {name: [] for name in baselines}
        paired = {name: {"distance_pixels": [], "distance_crop": []} for name in baselines}
        model, states = [], Counter()
        for identity, ref in expected.items():
            prediction = indexed[identity]
            if prediction.get("image_sha256") != ref["frame"]["image_sha256"]:
                raise ValueError("Evaluation row image hash differs from the frozen reference")
            status = prediction.get("status")
            if status not in ("completed", "error", "not_attempted"):
                raise ValueError("Unknown point prediction state")
            states[status] += 1
            seed_pool["states"][status] += 1
            errors = {name: _errors(point, ref) for name, point in baselines.items()}
            for name, error in errors.items():
                baseline_errors[name].append(error)
                seed_pool["baselines"][name].append(error)
            if status != "completed":
                if prediction.get("normalized_point") is not None:
                    raise ValueError("Failed/missing prediction cannot carry a point")
                continue
            point = prediction.get("normalized_point")
            if (
                not isinstance(point, list)
                or len(point) != 2
                or any(not 0 <= _number(v) <= 1 for v in point)
            ):
                raise ValueError("Completed normalized prediction outside unit crop")
            error = _errors(point, ref)
            model.append(error)
            seed_pool["model"].append(error)
            for name, baseline in errors.items():
                for metric in paired[name]:
                    paired[name][metric].append(error[metric] - baseline[metric])
                    seed_pool["paired"][name][metric].append(error[metric] - baseline[metric])
        results.append(
            {
                **arm,
                "planned_marked": len(expected),
                "prediction_states": dict(states),
                "training_status": training[key]["status"],
                "training_seconds": training[key].get("training_seconds"),
                "inference_seconds": evaluation.get("inference_seconds"),
                "model_errors": _metrics(model) if usable else None,
                "baselines_all_marked": {
                    name: {"normalized_point": baselines[name], "errors": _metrics(errors)}
                    for name, errors in baseline_errors.items()
                }
                if usable
                else None,
                "paired_model_minus_baseline": {
                    name: {metric: _stats(values) for metric, values in metrics.items()}
                    for name, metrics in paired.items()
                }
                if usable
                else None,
            }
        )
    seed_results = []
    for seed, pool in per_seed.items():
        seed_results.append(
            {
                "seed": seed,
                "planned_marked": sum(len(rows) for rows in cohorts.values()),
                "scope": "both cross-game test folds; same unique marked frames repeated across seeds",
                "prediction_states": dict(pool["states"]),
                "model_errors": _metrics(pool["model"]) if usable else None,
                "baselines_all_marked": {
                    name: _metrics(errors) for name, errors in pool["baselines"].items()
                }
                if usable
                else None,
                "paired_model_minus_baseline": {
                    name: {metric: _stats(values) for metric, values in metrics.items()}
                    for name, metrics in pool["paired"].items()
                }
                if usable
                else None,
            }
        )
    return results, seed_results


def run(plan_path, out, *, backend=None, checkpoint_writer=None, clock=time.perf_counter):
    """Train all fixed folds/seeds before sealing checkpoints and evaluating held-out rows."""
    out = Path(out).absolute()
    _no_links(out)
    if out.exists():
        raise FileExistsError("Fresh experiment output directory required")
    plan, raw_plan, cohorts, excluded, bindings = _inputs(plan_path)
    if any(Path(path).is_relative_to(out) for path, _, _ in bindings):
        raise ValueError("Output cannot contain an input")
    if backend is None:
        importlib.import_module("src")
        backend = importlib.import_module("intent.local_point_model")
    writer = checkpoint_writer or _save_checkpoint
    _verify(bindings)
    out.mkdir(parents=True, exist_ok=False)
    for child in ("checkpoints", "training", "evaluation"):
        (out / child).mkdir()
    artifact_sha256 = {}

    def write_artifact(relative_path, document):
        digest = _write(out / relative_path, document)
        artifact_sha256[relative_path] = digest
        return digest

    with (out / "plan.json").open("xb") as stream:
        stream.write(raw_plan)
    artifact_sha256["plan.json"] = _sha(raw_plan)
    write_artifact(
        "run_manifest.json",
        {
            "schema": "local_point_experiment_run_v1",
            "plan_sha256": _sha(raw_plan),
            "input_bindings": [list(row) for row in bindings],
        },
    )
    started, events, integrity, interrupted = clock(), [], True, False
    training, evaluations, ledger, frozen_hash = {}, {}, [], None
    for arm in _arms():
        key = arm["arm_id"]
        record = {
            **arm,
            "status": "not_attempted",
            "training_seconds": None,
            "checkpoint_sha256": None,
            "error_type": None,
        }
        if integrity and not interrupted:
            try:
                _verify(bindings)
                rows = cohorts[arm["train_game"]]
                if any(row["frame"]["game_pk"] != arm["train_game"] for row in rows):
                    raise ValueError("Training cohort contains another game")
                images, targets = _arrays(rows)
                events.append({"event": "training_started", "arm_id": key})
                before = clock()
                try:
                    model, checkpoint = backend.train_point_model(
                        images, targets, seed=arm["seed"], device=plan["device"]
                    )
                finally:
                    record["training_seconds"] = clock() - before
                del model
                metadata = checkpoint.get("metadata") if isinstance(checkpoint, dict) else None
                if (
                    not isinstance(metadata, dict)
                    or metadata.get("seed") != arm["seed"]
                    or metadata.get("train_count") != len(rows)
                    or metadata.get("epochs_completed") != 20
                ):
                    raise ValueError("Final checkpoint training metadata mismatch")
                metadata = json.loads(json.dumps(metadata, allow_nan=False))
                checkpoint_path = out / "checkpoints" / f"{key}.pt"
                writer(checkpoint, checkpoint_path)
                checkpoint_hash = _sha(_file(checkpoint_path).read_bytes())
                _verify(bindings)
                record.update(
                    status="completed",
                    checkpoint_sha256=checkpoint_hash,
                    metadata=metadata,
                    training_observation_ids=[row["frame"]["observation_id"] for row in rows],
                )
                ledger.append({**arm, "path": f"checkpoints/{key}.pt", "sha256": checkpoint_hash})
                events.append({"event": "training_completed", "arm_id": key})
            except (Exception, KeyboardInterrupt) as exc:
                record.update(status="error", error_type=type(exc).__name__)
                interrupted = isinstance(exc, KeyboardInterrupt)
                try:
                    _verify(bindings)
                except Exception:
                    integrity = False
        training[key] = record
        write_artifact(f"training/{key}.json", record)
    if integrity and not interrupted and len(ledger) == 6:
        try:
            _verify(
                bindings + [(str(out / row["path"]), row["sha256"], "checkpoint") for row in ledger]
            )
            frozen_hash = write_artifact(
                "checkpoint_ledger.json",
                {
                    "schema": "local_point_checkpoint_ledger_v1",
                    "plan_sha256": _sha(raw_plan),
                    "selection": "final epoch only; all six complete before evaluation",
                    "checkpoints": ledger,
                },
            )
            events.append({"event": "all_checkpoints_frozen", "ledger_sha256": frozen_hash})
        except Exception:
            integrity = False
    for arm in _arms():
        key, rows = arm["arm_id"], cohorts[arm["test_game"]]
        result = {
            **arm,
            "status": "not_attempted",
            "inference_seconds": None,
            "error_type": None,
            "checkpoint_sha256": training[key]["checkpoint_sha256"],
            "checkpoint_ledger_sha256": frozen_hash,
            "predictions": [
                {
                    "observation_id": row["frame"]["observation_id"],
                    "status": "not_attempted",
                    "image_sha256": row["frame"]["image_sha256"],
                    "normalized_point": None,
                }
                for row in rows
            ],
        }
        if frozen_hash is not None and integrity and not interrupted:
            checkpoint = next(row for row in ledger if row["arm_id"] == key)
            current_bindings = bindings + [
                (str(out / row["path"]), row["sha256"], "checkpoint") for row in ledger
            ]
            current_bindings.append(
                (str(out / "checkpoint_ledger.json"), frozen_hash, "checkpoint ledger")
            )
            try:
                _verify(current_bindings)
                events.append({"event": "evaluation_started", "arm_id": key})
                images, _ = _arrays(rows)
                model, loaded_metadata = backend.load_point_model(
                    out / checkpoint["path"],
                    device=plan["device"],
                    expected_sha256=checkpoint["sha256"],
                )
                if loaded_metadata != training[key]["metadata"]:
                    raise ValueError(
                        "Loaded checkpoint metadata differs from its sealed training record"
                    )
                before = clock()
                try:
                    raw = backend.predict_points(model, images, device=plan["device"])
                finally:
                    result["inference_seconds"] = clock() - before
                predictions = _prediction_array(raw, len(rows))
                del model
                _verify(current_bindings)
                for entry, prediction in zip(result["predictions"], predictions, strict=True):
                    if (
                        not np.isfinite(prediction).all()
                        or not ((prediction >= 0) & (prediction <= 1)).all()
                    ):
                        entry.update(status="error", error_type="InvalidNormalizedPoint")
                    else:
                        entry.update(
                            status="completed", normalized_point=[float(v) for v in prediction]
                        )
                result["status"] = "completed"
                events.append({"event": "evaluation_completed", "arm_id": key})
            except (Exception, KeyboardInterrupt) as exc:
                result.update(status="error", error_type=type(exc).__name__)
                for entry in result["predictions"]:
                    entry.update(
                        status="error", normalized_point=None, error_type=type(exc).__name__
                    )
                interrupted = isinstance(exc, KeyboardInterrupt)
                try:
                    _verify(current_bindings)
                except Exception:
                    integrity = False
        evaluations[key] = result
        write_artifact(f"evaluation/{key}.json", result)
    write_artifact("events.json", {"events": events})
    final_bindings = bindings + [
        (str(out / row["path"]), row["sha256"], "checkpoint") for row in ledger
    ]
    final_bindings.extend(
        (str(out / path), digest, "output artifact") for path, digest in artifact_sha256.items()
    )
    try:
        _verify(final_bindings)
    except Exception:
        integrity = False
    status = (
        "invalid_frozen_inputs"
        if not integrity
        else "interrupted"
        if interrupted
        else "training_incomplete"
        if frozen_hash is None
        else "completed_with_errors"
        if any(
            r["status"] != "completed" or any(p["status"] != "completed" for p in r["predictions"])
            for r in evaluations.values()
        )
        else "completed"
    )
    arms, per_seed = _summarize(
        cohorts, evaluations, training, usable=integrity and frozen_hash is not None
    )
    report = {
        "schema": REPORT_SCHEMA,
        "scope": "legacy_marked_point_conditional_development",
        "status": status,
        "results_usable": integrity and frozen_hash is not None,
        "plan_sha256": _sha(raw_plan),
        "manifest_sha256": plan["manifest_sha256"],
        "references_sha256": plan["references_sha256"],
        "checkpoint_ledger_sha256": frozen_hash,
        "device": plan["device"],
        "threads": 4,
        "elapsed_seconds": clock() - started,
        "unique_marked_frames": sum(len(rows) for rows in cohorts.values()),
        "unique_original_frames": sum(count[0] for count in EXPECTED_COUNTS.values()),
        "seed_repetitions": 3,
        "prediction_rows_planned": 3 * sum(len(rows) for rows in cohorts.values()),
        "seed_repetitions_are_independent_samples": False,
        "excluded": excluded,
        "limitations": LIMITATIONS,
        "quantiles": {"median": "midpoint for even n", "p90": "nearest rank"},
        "preprocessing": "fixed per-game crop; Pillow RGB/BILINEAR 192x128; float32 /255 CHW",
        "arms": arms,
        "per_seed": per_seed,
        "checkpoints": [
            {key: value for key, value in row.items() if key != "path"} for row in ledger
        ],
    }
    report["artifact_sha256"] = artifact_sha256
    _write(out / "report.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--plan", type=Path, required=True)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    report = run(args.plan, args.out)
    print(
        json.dumps(
            {"status": report["status"], "unique_marked_frames": report["unique_marked_frames"]}
        )
    )
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

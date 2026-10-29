"""Run six frozen CV49b predictions; no reference-guided selection or network access."""

import argparse
import hashlib
import io
import json
import re
import sys
from pathlib import Path

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intent.local_glove_detector import LocalGloveDetector
from src.data.object_reference import IDENTITY_FIELDS, loads_json, validate_input

ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "pitcheezy-glove-diagnostic-plan-v1"
MODEL = "fasterrcnn_mobilenet_v3_large_fpn"
RUNTIME = {"torch": "2.6.0+cu124", "torchvision": "0.21.0+cu124"}
REQUIRED_CODE = {
    "scripts/80_diagnose_glove_candidates.py",
    "intent/local_glove_detector.py",
    "src/data/object_reference.py",
}
PLAN_FIELDS = {
    "schema",
    "input_sha256",
    "model_name",
    "weights_sha256",
    "threshold",
    "device",
    "threads",
    "warmups",
    "passes",
    "code_files",
    "expected_runtime",
    "readings_sha256",
}


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _sha(value):
    if type(value) is not str or re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise ValueError("full lowercase SHA256 required")
    return value


def _path(path):
    path = Path(path).absolute()
    if any(
        p.is_symlink() or getattr(p, "is_junction", lambda: False)() for p in (path, *path.parents)
    ):
        raise ValueError("linked paths are not allowed")
    return path


def _snapshot(path, limit=8 * 1024 * 1024):
    with _path(path).open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("input exceeds size limit")
    return raw


def _write(path, value):
    raw = (json.dumps(value, ensure_ascii=False, allow_nan=False, indent=2) + "\n").encode()
    with path.open("xb") as stream:
        stream.write(raw)
    return digest(raw)


def _preflight(plan_path, input_path, weights_path, output, private_root):
    output = _path(output)
    allowed = _path(private_root if private_root is not None else ROOT / "outputs").resolve()
    if output.resolve() == allowed or not output.resolve().is_relative_to(allowed):
        raise ValueError("output must be a private subdirectory")
    if output.exists():
        raise FileExistsError("fresh output directory required")
    raw_plan, raw_input = _snapshot(plan_path), _snapshot(input_path)
    plan, manifest = loads_json(raw_plan), validate_input(loads_json(raw_input))
    if set(plan) != PLAN_FIELDS or plan["schema"] != SCHEMA:
        raise ValueError("unexpected plan schema or fields")
    fixed = {
        "model_name": MODEL,
        "threshold": 0.5,
        "device": "cuda",
        "threads": 4,
        "warmups": 0,
        "passes": 1,
        "expected_runtime": RUNTIME,
    }
    if any(
        plan[key] != value or type(plan[key]) is not type(value) for key, value in fixed.items()
    ):
        raise ValueError("CV49b configuration must remain fixed")
    readings = plan["readings_sha256"]
    if type(readings) is not dict or set(readings) != {"codex", "claude"}:
        raise ValueError("two saved reading hashes required; readings are not opened")
    for value in readings.values():
        _sha(value)
    if digest(raw_input) != _sha(plan["input_sha256"]):
        raise ValueError("input SHA mismatch")
    frames = manifest["frames"]
    if manifest["game_pk"] != 849843 or {f["pitch_key"] for f in frames} != {
        "849843:1:1",
        "849843:1:2",
        "849843:1:3",
    }:
        raise ValueError("exactly the three frozen first-PA pitches required")
    checks = [(Path(plan_path), digest(raw_plan)), (Path(input_path), digest(raw_input))]
    code = plan["code_files"]
    if type(code) is not dict or not REQUIRED_CODE <= set(code):
        raise ValueError("required code bindings missing")
    for name, expected in code.items():
        if (
            type(name) is not str
            or re.fullmatch(r"(?:[A-Za-z0-9_-]+/)*[A-Za-z0-9_.-]+", name) is None
        ):
            raise ValueError("code binding must be a repository-relative file")
        path = _path(ROOT / name)
        if not path.resolve().is_relative_to(ROOT.resolve()):
            raise ValueError("code binding escapes repository")
        if digest(_snapshot(path)) != _sha(expected):
            raise ValueError("code SHA mismatch")
        checks.append((path, expected))
    weights = _snapshot(weights_path, 256 * 1024 * 1024)
    if digest(weights) != _sha(plan["weights_sha256"]):
        raise ValueError("weights SHA mismatch")
    checks.append((Path(weights_path), plan["weights_sha256"]))
    images = {}
    for frame in frames:
        if (frame["width"], frame["height"], frame["context_crop"]) != (
            1280,
            720,
            [450, 240, 660, 470],
        ):
            raise ValueError("original frame dimensions and existing crop must remain fixed")
        path = _path(Path(input_path).parent / frame["image"])
        if not path.resolve().is_relative_to(Path(input_path).parent.resolve()):
            raise ValueError("image escapes source directory")
        raw = _snapshot(path, 32 * 1024 * 1024)
        if digest(raw) != frame["image_sha256"]:
            raise ValueError("image SHA mismatch")
        with Image.open(io.BytesIO(raw)) as image:
            if (
                image.format != "PNG"
                or image.size != (1280, 720)
                or getattr(image, "n_frames", 1) != 1
            ):
                raise ValueError("single original-size PNG required")
            image.verify()
        with Image.open(io.BytesIO(raw)) as image:
            image.load()
        images[frame["pitch_key"]] = raw
        checks.append((path, frame["image_sha256"]))
    return plan, manifest, raw_plan, raw_input, images, checks, output


def run(
    plan_path,
    input_path,
    weights_path,
    output,
    *,
    engine_factory=LocalGloveDetector,
    private_root=None,
):
    """Load once, retain each first attempt, and invalidate changed source bindings."""
    plan, manifest, raw_plan, raw_input, images, checks, output = _preflight(
        plan_path, input_path, weights_path, output, private_root
    )
    output.mkdir(parents=True, exist_ok=False)
    (output / "attempts").mkdir()
    (output / "plan.json").write_bytes(raw_plan)
    (output / "input.json").write_bytes(raw_input)
    engine, first_error, interrupted = None, None, False
    try:
        engine = engine_factory(
            MODEL, weights_path, plan["weights_sha256"], device="cuda", threads=4
        )
        engine.load()
        if engine.runtime_versions != plan["expected_runtime"]:
            raise ValueError("loaded runtime differs from frozen plan")
    except (Exception, KeyboardInterrupt) as exc:
        first_error = {"stage": "load", "type": type(exc).__name__}
        engine = None
    rows = []
    for frame in sorted(manifest["frames"], key=lambda f: f["pitch_key"]):
        for view, crop in (("full_frame", None), ("context_crop", frame["context_crop"])):
            row = {
                **{key: frame[key] for key in IDENTITY_FIELDS},
                "view": view,
                "crop_xyxy": crop,
                "status": "not_run",
                "error": None,
                "engine_response": None,
            }
            if engine is not None and not interrupted:
                try:
                    response = engine.predict(
                        images[frame["pitch_key"]],
                        image_sha256=frame["image_sha256"],
                        crop=crop,
                        threshold=0.5,
                    )
                    if (
                        type(response) is not dict
                        or response.get("schema") != "local_glove_detection_v1"
                        or response.get("selection_status")
                        not in ("candidate", "no_candidate", "ambiguous")
                    ):
                        raise ValueError("unexpected detector response")
                    # Preserve original float coordinates and every returned detection.
                    row["engine_response"] = json.loads(json.dumps(response, allow_nan=False))
                    row["status"] = "completed"
                except (Exception, KeyboardInterrupt) as exc:
                    row["status"], row["error"] = "error", type(exc).__name__
                    first_error = first_error or {
                        "stage": view,
                        "pitch_key": frame["pitch_key"],
                        "type": type(exc).__name__,
                    }
                    interrupted = isinstance(exc, KeyboardInterrupt)
            name = f"attempts/{len(rows):02d}.json"
            row_hash = _write(output / name, row)
            rows.append({**row, "attempt_file": name, "attempt_sha256": row_hash})
    frozen = []
    for path, expected in checks:
        try:
            actual = digest(_snapshot(path, 256 * 1024 * 1024))
        except (OSError, ValueError):
            actual = None
        frozen.append(
            {
                "path": str(path),
                "expected_sha256": expected,
                "actual_sha256": actual,
                "unchanged": actual == expected,
            }
        )
    unchanged = all(item["unchanged"] for item in frozen)
    counts = {
        name: sum(row["status"] == name for row in rows)
        for name in ("completed", "error", "not_run")
    }
    report = {
        "schema": "pitcheezy-glove-diagnostic-result-v1",
        "plan_sha256": digest(raw_plan),
        "input_sha256": digest(raw_input),
        "planned_predictions": 6,
        "counts": counts,
        "status": "invalidated"
        if not unchanged
        else "completed"
        if counts["completed"] == 6
        else "incomplete",
        "first_error": first_error,
        "frozen_inputs_unchanged": unchanged,
        "frozen_checks": frozen,
        "frames": rows,
        "development_only": True,
        "catcher_association_verified": False,
        "accuracy_measured": False,
    }
    _write(output / "result.json", report)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("plan", "input", "weights", "output"):
        parser.add_argument("--" + name, type=Path, required=True)
    args = parser.parse_args(argv)
    try:
        report = run(args.plan, args.input, args.weights, args.output)
    except (ValueError, OSError) as exc:
        parser.exit(2, f"diagnostic rejected: {str(exc)[:300]}\n")
    print(json.dumps({key: report[key] for key in ("status", "counts", "first_error")}))
    return 0 if report["status"] == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())

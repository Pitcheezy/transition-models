"""Run the service's own ``validate_intent_estimate`` on our JSONL files.

    python -m intent.service_check --validator <pitcheezy>/apps/observer/backend/observer_app/intent.py \
        docs/results/mlb_p0/game_849845_intent_v0.jsonl docs/results/mlb_p0/game_823407_intent_v0.jsonl \
        --out docs/results/mlb_p0/intent_service_check_v0.json

The validator file is the service repository's (SongRoute/pitcheezy); it is read, not copied
into this repository. Only ``validate_intent_estimate`` runs. Its two sibling imports are
replaced: ``domain.ZONES`` and ``video_lab._number`` by the same definitions as the service at
8771c06, and the ``video_lab`` helpers the validator never calls by stubs that raise.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import math
import sys
import types
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _number(value, label):  # same as observer_app/video_lab.py at 8771c06
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError(f"{label} must be finite")
    return float(value)


def _unused(*args, **kwargs):
    raise RuntimeError("not used by validate_intent_estimate")


def load_validator(path):
    pkg = types.ModuleType("observer_app")
    pkg.__path__ = []
    domain = types.ModuleType("observer_app.domain")
    domain.ZONES = tuple(range(1, 10))
    video_lab = types.ModuleType("observer_app.video_lab")
    video_lab._number = _number
    video_lab.image_to_zone = _unused
    video_lab.validate_corners = _unused
    saved = {
        k: sys.modules.get(k)
        for k in ("observer_app", "observer_app.domain", "observer_app.video_lab")
    }
    sys.modules.update(
        {"observer_app": pkg, "observer_app.domain": domain, "observer_app.video_lab": video_lab}
    )
    try:
        module = types.ModuleType("observer_app.intent")
        module.__package__ = "observer_app"
        source = Path(path).read_text(encoding="utf-8")
        exec(compile(source, "observer_app/intent.py", "exec"), module.__dict__)
    finally:
        for k, v in saved.items():
            if v is None:
                sys.modules.pop(k, None)
            else:
                sys.modules[k] = v
    return module.validate_intent_estimate


def check_file(validate, path):
    lines = [
        json.loads(x) for x in Path(path).read_text(encoding="utf-8").splitlines() if x.strip()
    ]
    failures = []
    for record in lines:
        try:
            validate(record)
        except ValueError as exc:
            failures.append({"pitch_id": record.get("pitch_id"), "error": str(exc)})
    return {
        "file": Path(path).resolve().relative_to(ROOT).as_posix()
        if Path(path).resolve().is_relative_to(ROOT)
        else str(path),
        "sha256": hashlib.sha256(Path(path).read_bytes()).hexdigest(),
        "lines": len(lines),
        "passed": len(lines) - len(failures),
        "failed": len(failures),
        "failures": failures[:20],
        "deepest_frame": dict(Counter(str(r.get("deepest_frame")) for r in lines)),
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--validator", type=Path, required=True)
    parser.add_argument("--validator-commit", default="8771c06")
    parser.add_argument("jsonl", type=Path, nargs="+")
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args(argv)
    validate = load_validator(args.validator)
    result = {
        "schema": "intent_service_check_v0",
        "validator": {
            "repository": "SongRoute/pitcheezy",
            "path": "apps/observer/backend/observer_app/intent.py",
            "commit": args.validator_commit,
            "sha256": hashlib.sha256(args.validator.read_bytes()).hexdigest(),
            "function": "validate_intent_estimate",
        },
        "files": [check_file(validate, p) for p in args.jsonl],
    }
    if args.out:
        args.out.write_text(
            json.dumps(result, ensure_ascii=False, indent=1) + "\n", encoding="utf-8"
        )
    print(json.dumps(result, ensure_ascii=False, indent=1))
    if any(f["failed"] for f in result["files"]):
        raise SystemExit(1)


if __name__ == "__main__":
    main()

"""CV46: apply the seed identity cue to the saved seeds and replay a holding candidate.

Same 625 frames, same saved observations and the same frozen inputs as CV42. The cue reads the
RGB seed frame only. A seed that is not ``mitt_like`` is held with its reason; nothing is
re-identified. AI readings of the seed crops (Claude, Codex) can be merged afterwards and count
as agreement only when all three sources say the same thing; they are never human truth.
"""

from __future__ import annotations

import argparse
import copy
import hashlib
import io
import json
from collections import Counter
from pathlib import Path

import numpy as np
import torch
from PIL import Image

from intent import mitt_reacquire_pilot as replay
from intent import mitt_seed_pilot as gate_pilot
from intent import mitt_tracking_pilot as inputs
from intent.mitt_seed_gate import POLICY_SHA256
from intent.mitt_seed_identity import SCHEMA as CUE_SCHEMA
from intent.mitt_seed_identity import IdentityParams, accepts, assess_patch

SCHEMA = "pitcheezy-seed-identity-pilot-dev-v1"
READING_VALUES = ("mitt", "hand", "unclear")
CUE_TO_READING = {"mitt_like": "mitt", "hand_like": "hand", "unclear": "unclear"}
CROP_HALF = 40
CROP_SCALE = 3
SOURCE_SIZE = (1280, 720)


def encoded(value):
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")


def load_rgb(frame):
    """Verified source bytes, decoded once as RGB in source pixels."""
    raw = frame["path"].read_bytes()
    if hashlib.sha256(raw).hexdigest() != frame["sha256"]:
        raise ValueError("frame changed after integrity check")
    with Image.open(io.BytesIO(raw)) as image:
        if image.size != SOURCE_SIZE:
            raise ValueError("source dimensions changed")
        return np.asarray(image.convert("RGB"), dtype=np.uint8).copy()


def assess_seed(selected, pitch, seed, params, pending_crops=None, label=None):
    """Cue for one (frame_index, point) seed; optionally queue a private crop for AI reading."""
    if seed is None:
        return None
    if pending_crops is None:
        pending_crops = []
    frame = next(f for p, f in selected if p == pitch and f["index"] == seed[0])
    rgb = load_rgb(frame)
    cue = assess_patch(rgb, seed[1], params)
    record = {
        "pitch_id": pitch,
        "frame_index": frame["index"],
        "frame_seconds": frame["pts_time"],
        "source_sha256": frame["sha256"],
        "seed_point_px": [float(v) for v in seed[1]],
        "cue": cue,
    }
    if label is not None and cue["patch_box"] is not None:
        x, y = cue["point_px"]
        x0, y0 = max(0, x - CROP_HALF), max(0, y - CROP_HALF)
        x1, y1 = min(rgb.shape[1], x + CROP_HALF + 1), min(rgb.shape[0], y + CROP_HALF + 1)
        crop = Image.fromarray(rgb[y0:y1, x0:x1])
        crop = crop.resize((crop.width * CROP_SCALE, crop.height * CROP_SCALE), Image.NEAREST)
        name = f"{pitch.replace(':', '_')}_{frame['index']:06d}_{label}.png"
        record["crop"] = {
            "file": name,
            "box_px": [x0, y0, x1 - 1, y1 - 1],
            "scale": CROP_SCALE,
            "note": "private development crop without markers; the 21 px patch is centred",
        }
        # Written by run() only after every check passed, so a failed run leaves no folder.
        pending_crops.append((name, crop))
    return record


def filtered_seeds(seeds, assessments):
    """Keep a seed only when its cue accepts; record the hold reason otherwise."""
    kept, holds = {}, {}
    for pitch, seed in seeds.items():
        record = assessments.get(pitch)
        if seed is None or record is None:
            kept[pitch], holds[pitch] = None, "no_seed"
        elif accepts(record["cue"]):
            kept[pitch], holds[pitch] = seed, None
        else:
            kept[pitch], holds[pitch] = (
                None,
                record["cue"]["verdict"] + ":" + record["cue"]["reason"],
            )
    return kept, holds


def labelled_replay(selected, seeds, observations, source_label, prefix_check=False):
    """Replay; the prefix check compares unlabelled rows so the label is never the difference."""
    rows, times = replay.replay_candidate(selected, seeds, observations, "cpu")
    checked = (
        replay.prefix_invariance(selected, seeds, observations, rows, "cpu")
        if prefix_check
        else None
    )
    for row in rows:
        if row["seed_source"] is not None:
            row["seed_source"] = source_label
    return rows, times, checked


READER_KEYS = {"reading", "evidence", "model"}


def _reader_entry(entry, who):
    """A present reader entry carries only an allowlisted verdict, a short note and a model."""
    if not isinstance(entry, dict) or not entry.keys() <= READER_KEYS or "reading" not in entry:
        raise ValueError(f"{who} reading must be a dict with reading[, evidence, model]")
    if entry["reading"] not in READING_VALUES:
        raise ValueError("reading must be mitt, hand or unclear")
    for key in ("evidence", "model"):
        if key in entry:
            value = entry[key]
            if not isinstance(value, str) or len(value) > 500 or any(c in value for c in "\\/"):
                raise ValueError(f"{who} {key} must be a short string without path separators")
    return {key: entry[key] for key in READER_KEYS if key in entry}


def agreement(cue_verdict, readings):
    """All three sources must say the same thing; anything else stays undetermined."""
    if not isinstance(readings, dict) or not readings.keys() <= {"claude", "codex"}:
        raise ValueError("readings must map claude/codex to reader entries")
    values = {"cue": CUE_TO_READING[cue_verdict]}
    for who in ("claude", "codex"):
        # An absent reader is missing; a present reader, even null, must be a valid entry.
        values[who] = _reader_entry(readings[who], who)["reading"] if who in readings else None
    present = [v for v in values.values() if v is not None]
    if len(present) == 3 and len(set(present)) == 1:
        return {"status": "ai_agreement", "value": present[0], "values": values}
    return {"status": "undetermined", "value": None, "values": values}


def merge_readings(report, readings):
    """Attach per-seed AI readings to a fresh report copy; agreement is not human truth."""
    if (
        not isinstance(readings, dict)
        or readings.get("schema") != "pitcheezy-seed-identity-readings-dev-v1"
    ):
        raise ValueError("readings schema mismatch")
    if "readings" in report or "agreement_summary" in report:
        raise ValueError("report already carries readings; merge into the original report")
    merged = copy.deepcopy(report)
    merged["readings"] = {
        "schema": readings["schema"],
        "models": readings.get("models"),
        "note": "AI development readings of private crops; not human labels or independent accuracy",
    }
    table = {}
    for key, entry in readings.get("seeds", {}).items():
        pitch, source = key.rsplit(":", 1)
        record = merged["per_pitch"].get(pitch, {}).get(source + "_seed")
        if record is None:
            raise ValueError(f"reading for unknown seed {key}")
        record["agreement"] = agreement(record["cue"]["verdict"], entry)
        record["readings"] = {
            who: _reader_entry(entry[who], who) for who in ("claude", "codex") if who in entry
        }
        table[key] = record["agreement"]
    merged["agreement_summary"] = {
        "seeds_with_readings": len(table),
        "ai_agreement": sum(a["status"] == "ai_agreement" for a in table.values()),
        "undetermined": sum(a["status"] == "undetermined" for a in table.values()),
        "note": "ai_agreement means cue, Claude and Codex coincide; it is not mitt identification",
    }
    return merged


def public_copy(report):
    """Drop seed coordinates and crop boxes from the private report."""
    public = copy.deepcopy(report)
    for pitch in public["per_pitch"].values():
        for key in ("baseline_seed", "gate_seed"):
            record = pitch.get(key)
            if record:
                record.pop("seed_point_px", None)
                record.pop("crop", None)
                record["cue"].pop("point_px", None)
                record["cue"].pop("patch_box", None)
    public["public_redaction"] = "seed coordinates, patch boxes and crop references removed"
    return public


def run(bundle, pilot, baseline, out, expected, params=None):
    if out.exists():
        raise ValueError("output must be new")
    params = IdentityParams() if params is None else params
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    selected, old_seeds, observations, preserved, manifest_sha = inputs.load_inputs(bundle, pilot)
    frame_keys = {(pitch, frame["index"]) for pitch, frame in selected}
    if len(frame_keys) != len(selected) or not observations.keys() <= frame_keys:
        raise ValueError("saved observation keys do not match selected frames")
    if baseline.resolve() in {Path(p).resolve() for p in preserved}:
        raise ValueError("baseline must be separate from source inputs")
    provenance = inputs.saved_pilot_provenance(pilot, preserved)
    actual = {
        "manifest": manifest_sha,
        "pilot": provenance["pilot_private_sha256"],
        "answers": provenance["answers_manifest_sha256"],
        "baseline": inputs.sha(baseline),
    }
    if actual != expected:
        raise ValueError("frozen input hashes differ")
    preserved[str(baseline)] = actual["baseline"]
    original = copy.deepcopy((old_seeds, observations))
    saved = json.loads(baseline.read_text(encoding="utf-8"))
    base_rows, base_times = replay.replay_candidate(selected, old_seeds, observations, "cpu")
    if base_rows != saved:
        raise ValueError("existing seed policy does not reproduce every saved field")
    gate_seeds, decisions = gate_pilot.choose(selected, observations)
    pending_crops = []
    baseline_cues = {
        p: assess_seed(selected, p, s, params, pending_crops, "baseline")
        for p, s in old_seeds.items()
    }
    gate_cues = {
        p: assess_seed(selected, p, s, params, pending_crops, "gate") for p, s in gate_seeds.items()
    }
    cv46_seeds, cv46_holds = filtered_seeds(gate_seeds, gate_cues)
    cued_baseline_seeds, cued_baseline_holds = filtered_seeds(old_seeds, baseline_cues)
    gate_rows, gate_times, _ = labelled_replay(
        selected, gate_seeds, observations, "saved_AI_seed_gate_dev_v1_current_observation"
    )
    rows, times, prefix_rows = labelled_replay(
        selected,
        cv46_seeds,
        observations,
        "saved_AI_seed_gate_dev_v1_identity_cue_dev_v1",
        prefix_check=True,
    )
    cued_rows, cued_times, _ = labelled_replay(
        selected, cued_baseline_seeds, observations, "saved_AI_first_usable_identity_cue_dev_v1"
    )
    if original != (old_seeds, observations):
        raise ValueError("input objects changed")
    if any(inputs.sha(Path(p)) != h for p, h in preserved.items()):
        raise ValueError("input files changed")
    violations = replay._consistency(rows)
    if any(violations.values()):
        raise ValueError("candidate tracking/selector consistency violation")
    per_pitch = {}
    for pitch in old_seeds:
        per_pitch[pitch] = {
            "baseline_seed": baseline_cues[pitch],
            "gate_seed": gate_cues[pitch],
            "cv46_seed_used": cv46_seeds[pitch] is not None,
            "cv46_hold_reason": cv46_holds[pitch],
            "cued_baseline_seed_used": cued_baseline_seeds[pitch] is not None,
            "cued_baseline_hold_reason": cued_baseline_holds[pitch],
        }

    def verdicts(cues):
        return dict(Counter(c["cue"]["verdict"] for c in cues.values() if c is not None))

    def reasons(cues):
        return dict(Counter(c["cue"]["reason"] for c in cues.values() if c is not None))

    record_bytes = encoded(rows)
    cued_bytes = encoded(cued_rows)
    report = {
        "schema": SCHEMA,
        "cue_schema": CUE_SCHEMA,
        "params": IdentityParams.__dataclass_fields__ and vars(params),
        "params_sha256": params.digest(),
        "seed_gate_policy_sha256": POLICY_SHA256,
        "evidence_kind": "exposed development replay on saved frames; the cue reads the seed frame only",
        "source_hashes": actual,
        "saved_pilot_inputs": provenance,
        "baseline_every_field_reproduced": True,
        "baseline_rows": len(saved),
        "preserved_input_files": len(preserved),
        "all_input_bytes_unchanged": True,
        "frames": len(selected),
        "pitches": len(old_seeds),
        "cue_inputs": "RGB seed frame patch only; no past/future frame, observation, tracking result or outcome",
        "baseline_seed_verdicts": verdicts(baseline_cues),
        "baseline_seed_reasons": reasons(baseline_cues),
        "gate_seed_verdicts": verdicts(gate_cues),
        "gate_seed_reasons": reasons(gate_cues),
        "gate_seeded_pitches": sum(s is not None for s in gate_seeds.values()),
        "cv46_seeded_pitches": sum(s is not None for s in cv46_seeds.values()),
        "cv46_hold_reasons": dict(Counter(r for r in cv46_holds.values() if r)),
        "cued_baseline_seeded_pitches": sum(s is not None for s in cued_baseline_seeds.values()),
        "cued_baseline_hold_reasons": dict(Counter(r for r in cued_baseline_holds.values() if r)),
        "summaries": {
            "baseline_first_usable": gate_pilot.summarize(base_rows),
            "gate_cv42": gate_pilot.summarize(gate_rows),
            "cv46_gate_plus_cue": gate_pilot.summarize(rows),
            "first_usable_plus_cue": gate_pilot.summarize(cued_rows),
        },
        "prefix_invariance_rows_checked": prefix_rows,
        "consistency_violations": violations,
        "per_pitch": per_pitch,
        "timing_ms": {
            "baseline": base_times,
            "gate_cv42": gate_times,
            "cv46": times,
            "first_usable_plus_cue": cued_times,
            "scope": "single CPU replay tracker steps after decode; not live latency",
        },
        "outputs": {
            "records_cv46.json": hashlib.sha256(record_bytes).hexdigest(),
            "records_first_usable_plus_cue.json": hashlib.sha256(cued_bytes).hexdigest(),
        },
        "mitt_identity": "unverified",
        "accuracy": "unmeasured",
        "independent_evaluation": False,
        "limits": [
            "the cue assumes a dark leather mitt; light or tan mitts are refused, not identified",
            "thresholds come from a published skin rule and fixed gates, not from fitting these pitches",
            "the three known development cases are regression checks, not a success rate",
            "AI readings, when merged, are development observations and never human labels",
            "fewer seeds or fewer tracked frames are not accuracy",
        ],
    }
    out.mkdir(parents=True)
    (out / "crops").mkdir()
    for name, crop in pending_crops:
        crop.save(out / "crops" / name)
    (out / "records_cv46.json").write_bytes(record_bytes)
    (out / "records_first_usable_plus_cue.json").write_bytes(cued_bytes)
    (out / "report.json").write_bytes(encoded(report))
    (out / "report_public.json").write_bytes(encoded(public_copy(report)))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    runner = sub.add_parser("run")
    for name in ("bundle", "pilot", "baseline", "out"):
        runner.add_argument("--" + name, type=Path, required=True)
    for name in ("manifest", "pilot", "answers", "baseline"):
        runner.add_argument("--" + name + "-sha256", required=True)
    merger = sub.add_parser("merge")
    merger.add_argument("--report", type=Path, required=True)
    merger.add_argument("--readings", type=Path, required=True)
    merger.add_argument("--out", type=Path, required=True)
    args = vars(parser.parse_args())
    command = args.pop("command")
    if command == "run":
        expected = {
            name: args.pop(name + "_sha256")
            for name in ("manifest", "pilot", "answers", "baseline")
        }
        result = run(**args, expected=expected)
        print(
            json.dumps(
                {
                    k: result[k]
                    for k in (
                        "baseline_seed_verdicts",
                        "gate_seed_verdicts",
                        "cv46_seeded_pitches",
                        "cv46_hold_reasons",
                    )
                }
            )
        )
    else:
        if args["out"].exists():
            raise ValueError("output must be new")
        report = json.loads(args["report"].read_text(encoding="utf-8"))
        readings = json.loads(args["readings"].read_text(encoding="utf-8"))
        merged = merge_readings(report, readings)
        args["out"].write_bytes(encoded(merged))
        print(json.dumps(merged["agreement_summary"]))


if __name__ == "__main__":
    main()

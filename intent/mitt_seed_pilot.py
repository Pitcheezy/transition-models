"""CV42: frozen seed eligibility on exposed saved observations; no inference or accuracy claim."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
from collections import Counter
from pathlib import Path

import torch

from intent import mitt_reacquire_pilot as replay
from intent import mitt_tracking_pilot as inputs
from intent.mitt_seed_gate import POLICY, POLICY_SHA256, SeedGate


def encoded(value):
    return (
        json.dumps(value, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")


def choose(selected, observations):
    """Only present/past observations enter the gate, including at every prefix replay."""
    gate, decisions, seeds = SeedGate(), [], {pitch: None for pitch, _ in selected}
    for pitch, frame in selected:
        result = gate.update(
            pitch, frame["index"], frame["pts_time"], observations.get((pitch, frame["index"]))
        )
        decisions.append(result)
        if result["seed"] is not None:
            event = result["seed"]
            seeds[pitch] = (event["frame_index"], list(event["point_px"]))
    return seeds, decisions


def gated_replay(selected, seeds, observations):
    rows, times = replay.replay_candidate(selected, seeds, observations, "cpu")
    for row in rows:
        if row["seed_source"] is not None:
            row["seed_source"] = "saved_AI_seed_gate_dev_v1_current_observation"
    return rows, times


def subset_observations(selected, observations):
    return {
        key: observations[key]
        for pitch, f in selected
        if (key := (pitch, f["index"])) in observations
    }


def prefix_check(selected, observations, decisions, rows):
    """All gate prefixes; sampled tracker prefixes recompute seeds, never reuse future seeds."""
    gate_count = tracker_count = 0
    for pitch in dict.fromkeys(p for p, _ in selected):
        frames = [(p, f) for p, f in selected if p == pitch]
        full_decisions = [d for d in decisions if d["pitch_id"] == pitch]
        full_rows = [r for r in rows if r["pitch_id"] == pitch]
        seed_positions = [i + 1 for i, d in enumerate(full_decisions) if d["seed"] is not None]
        cuts = {1, len(frames) // 2, len(frames), *seed_positions, *(i - 1 for i in seed_positions)}
        for count in range(1, len(frames) + 1):
            part = frames[:count]
            obs = subset_observations(part, observations)
            seeds, prefix = choose(part, obs)
            if prefix != full_decisions[:count]:
                raise ValueError("seed gate depends on future observations")
            gate_count += count
            if count in cuts:
                reproduced, _ = gated_replay(part, seeds, obs)
                if reproduced != full_rows[:count]:
                    raise ValueError("gated tracker prefix differs")
                tracker_count += count
    return {"gate_prefix_rows": gate_count, "tracker_prefix_rows": tracker_count}


def summarize(rows):
    per_pitch = {}
    for pitch in dict.fromkeys(r["pitch_id"] for r in rows):
        group = [r for r in rows if r["pitch_id"] == pitch]
        per_pitch[pitch] = {
            "frames": len(group),
            "states": dict(Counter(r["state"] for r in group)),
            "reacquisitions": group[-1]["reacquisitions"],
            "stationary_events": group[-1]["stationary"]["events_total"],
        }
    return {
        "frames": len(rows),
        "pitches": len(per_pitch),
        "states": dict(Counter(r["state"] for r in rows)),
        "reacquisitions": sum(p["reacquisitions"] for p in per_pitch.values()),
        "stationary_events": sum(p["stationary_events"] for p in per_pitch.values()),
        "per_pitch": per_pitch,
    }


def run(bundle, pilot, baseline, out, expected):
    if out.exists():
        raise ValueError("output must be new")
    torch.set_num_threads(4)
    torch.backends.cuda.matmul.allow_tf32 = False
    torch.backends.cudnn.allow_tf32 = False
    torch.backends.cudnn.benchmark = False
    torch.backends.cudnn.deterministic = True
    selected, old_seeds, observations, preserved, manifest_sha = inputs.load_inputs(bundle, pilot)
    frame_keys = {(pitch, frame["index"]) for pitch, frame in selected}
    if len(frame_keys) != len(selected) or not observations.keys() <= frame_keys:
        raise ValueError("saved observation keys do not match selected frames")
    pitch_keys = {pitch for pitch, _ in frame_keys}
    if old_seeds.keys() != pitch_keys or any(
        seed is not None and (pitch, seed[0]) not in frame_keys for pitch, seed in old_seeds.items()
    ):
        raise ValueError("baseline seed frame is not in selected frames")
    original_file_count = len(preserved)
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
    seeds, decisions = choose(selected, observations)
    rows, times = gated_replay(selected, seeds, observations)
    prefix = prefix_check(selected, observations, decisions, rows)
    if original != (old_seeds, observations):
        raise ValueError("input objects changed")
    if any(inputs.sha(Path(p)) != h for p, h in preserved.items()):
        raise ValueError("input files changed")
    violations = replay._consistency(rows)
    if any(violations.values()):
        raise ValueError("candidate tracking/selector consistency violation")
    per_pitch = {}
    for pitch in seeds:
        group = [d for d in decisions if d["pitch_id"] == pitch]
        event = next((d["seed"] for d in group if d["seed"] is not None), None)
        first = (
            next(
                f["pts_time"]
                for p, f in selected
                if p == pitch and old_seeds[p] and f["index"] == old_seeds[p][0]
            )
            if old_seeds[pitch]
            else None
        )
        per_pitch[pitch] = {
            "baseline_seed_frame": old_seeds[pitch][0] if old_seeds[pitch] else None,
            "gate_seed": event,
            "delay_from_baseline_seconds": event["frame_seconds"] - first
            if event is not None and first is not None
            else None,
            "decision_reasons": dict(Counter(d["reason"] for d in group)),
        }
    record_bytes, decision_bytes = encoded(rows), encoded(decisions)
    report = {
        "schema": "pitcheezy-seed-gate-pilot-dev-v1",
        "policy": POLICY,
        "policy_sha256": POLICY_SHA256,
        "evidence_kind": "exposed development, saved frame-time replay; not accuracy or online availability",
        "source_hashes": actual,
        "saved_pilot_inputs": provenance,
        "baseline_every_field_reproduced": True,
        "baseline_rows": len(saved),
        "preserved_input_files": len(preserved),
        "original_input_files_excluding_baseline": original_file_count,
        "saved_observation_keys_matched": len(observations),
        "all_input_bytes_unchanged": True,
        "prefix_invariance": prefix,
        "consistency_violations": violations,
        "baseline": summarize(base_rows),
        "candidate": summarize(rows),
        "seeded_pitches": sum(s is not None for s in seeds.values()),
        "per_pitch": per_pitch,
        "decision_reasons": dict(Counter(d["reason"] for d in decisions)),
        "timing_ms": {
            "baseline": base_times,
            "candidate": times,
            "scope": "single CPU replay tracker steps after decode; not live latency",
        },
        "outputs": {
            "records_seed_gate.json": hashlib.sha256(record_bytes).hexdigest(),
            "gate_decisions.json": hashlib.sha256(decision_bytes).hexdigest(),
        },
        "mitt_identity": "unverified",
        "accuracy": "unmeasured",
        "independent_evaluation": False,
        "support_observations_are_not_truth": True,
        "limits": [
            "stable wrong object may pass",
            "thresholds were proposed after seeing these development pitches",
            "AI response arrival times unavailable",
            "no new model calls or human labels",
            "fixed backend resets per pitch, consumes current frame observations only, and reports cumulative per-pitch counters",
        ],
    }
    out.mkdir(parents=True)
    (out / "records_seed_gate.json").write_bytes(record_bytes)
    (out / "gate_decisions.json").write_bytes(decision_bytes)
    (out / "report.json").write_bytes(encoded(report))
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("bundle", "pilot", "baseline", "out"):
        parser.add_argument("--" + name, type=Path, required=True)
    for name in ("manifest", "pilot", "answers", "baseline"):
        parser.add_argument("--" + name + "-sha256", required=True)
    args = vars(parser.parse_args())
    expected = {
        name: args.pop(name + "_sha256") for name in ("manifest", "pilot", "answers", "baseline")
    }
    result = run(**args, expected=expected)
    print(
        json.dumps(
            {k: result[k] for k in ("seeded_pitches", "baseline", "candidate", "prefix_invariance")}
        )
    )


if __name__ == "__main__":
    main()

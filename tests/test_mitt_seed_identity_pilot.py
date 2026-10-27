"""Identity cue on saved seeds: holds are recorded, readings merge only as agreement."""

import copy
import json

import numpy as np
import pytest
import torch
from PIL import Image

from intent import mitt_seed_identity_pilot as pilot

HAND_RGB = (188, 152, 144)
MITT_RGB = (84, 81, 96)


def save(path, value):
    path.write_text(json.dumps(value, allow_nan=False), encoding="utf-8")


def frame_pixels(colour, noise, seed):
    rng = np.random.default_rng(seed)
    image = np.empty((720, 1280, 3), np.uint8)
    image[...] = (40, 90, 40)
    patch = np.array(colour, np.int16) + rng.integers(-noise, noise + 1, (21, 21, 1), np.int16)
    image[290:311, 590:611] = np.clip(patch, 0, 255).astype(np.uint8)
    return image


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    """Three twelve-frame pitches: dark textured, skin coloured, and flat dark seed patches.

    The gate seeds at the fifth frame sit inside the half-length prefix replay on purpose.
    """
    torch.set_num_threads(4)
    bundle, answers_dir = tmp_path / "bundle", tmp_path / "pilot"
    bundle.mkdir()
    (answers_dir / "answers").mkdir(parents=True)
    manifest = bundle / "manifest.json"
    metadata = answers_dir / "pilot_private.json"
    answer_file = answers_dir / "answers" / "b01.json"
    save(manifest, {"fixture": "three pitches"})
    save(metadata, {"fixture": "saved development observations"})
    save(answer_file, {"fixture": "not human labels"})
    selected, observations, old_seeds = [], {}, {}
    preserved = {str(p): pilot.inputs.sha(p) for p in (manifest, metadata, answer_file)}
    colours = {1: (MITT_RGB, 20), 2: (HAND_RGB, 20), 3: (MITT_RGB, 0)}
    for number, (colour, noise) in colours.items():
        pitch = f"747139:{number}:1"
        old_seeds[pitch] = (0, [600, 300])
        folder = bundle / f"pa{number}_p1"
        folder.mkdir()
        pixels = frame_pixels(colour, noise, number)
        for ordinal in range(12):
            index = ordinal * 6
            seconds = index * 1001 / 60000
            path = folder / f"frame_{index:06d}.jpg"
            Image.fromarray(pixels).save(path, quality=95)
            digest = pilot.inputs.sha(path)
            selected.append(
                (
                    pitch,
                    {
                        "index": index,
                        "pts_time": seconds,
                        "path": path,
                        "bytes": path.stat().st_size,
                        "sha256": digest,
                        "roles": ["grid"],
                    },
                )
            )
            preserved[str(path)] = digest
            if ordinal % 2 == 0:
                observations[(pitch, index)] = {
                    "pitch_id": pitch,
                    "frame_index": index,
                    "frame_seconds": seconds,
                    "view": "live_centre_field",
                    "catcher": "set",
                    "mitt_visibility": "full",
                    "occluder": None,
                    "mitt_center_px": [600, 300],
                    "pitcher_phase": "before_delivery",
                    "uncertainty_px": 2,
                }
    manifest_sha = pilot.inputs.sha(manifest)
    monkeypatch.setattr(
        pilot.inputs,
        "load_inputs",
        lambda *_: (selected, old_seeds, observations, dict(preserved), manifest_sha),
    )
    rows, _ = pilot.replay.replay_candidate(selected, old_seeds, observations, "cpu")
    baseline = tmp_path / "records_candidate_cpu.json"
    baseline.write_text(json.dumps(rows, indent=2, allow_nan=False) + "\n", encoding="utf-8")
    provenance = pilot.inputs.saved_pilot_provenance(answers_dir, preserved)
    expected = {
        "manifest": manifest_sha,
        "pilot": provenance["pilot_private_sha256"],
        "answers": provenance["answers_manifest_sha256"],
        "baseline": pilot.inputs.sha(baseline),
    }
    return bundle, answers_dir, baseline, expected


def test_cue_holds_hand_and_flat_seeds_and_keeps_the_dark_textured_one(inputs, tmp_path):
    bundle, answers_dir, baseline, expected = inputs
    out = tmp_path / "out"
    report = pilot.run(bundle, answers_dir, baseline, out, expected)
    assert report["baseline_every_field_reproduced"] and report["all_input_bytes_unchanged"]
    assert report["baseline_seed_verdicts"] == {"mitt_like": 1, "hand_like": 1, "unclear": 1}
    assert report["gate_seed_verdicts"] == {"mitt_like": 1, "hand_like": 1, "unclear": 1}
    assert report["gate_seeded_pitches"] == 3 and report["cv46_seeded_pitches"] == 1
    assert report["cv46_hold_reasons"] == {
        "hand_like:skin_fraction_high": 1,
        "unclear:low_texture": 1,
    }
    assert report["cued_baseline_seeded_pitches"] == 1
    per = report["per_pitch"]
    assert per["747139:1:1"]["cv46_seed_used"] and per["747139:1:1"]["cv46_hold_reason"] is None
    assert per["747139:2:1"]["cv46_hold_reason"] == "hand_like:skin_fraction_high"
    assert per["747139:3:1"]["cv46_hold_reason"] == "unclear:low_texture"
    assert per["747139:1:1"]["gate_seed"]["frame_index"] == 24
    assert per["747139:1:1"]["gate_seed"]["cue"]["params_sha256"] == report["params_sha256"]
    summaries = report["summaries"]
    assert (
        summaries["gate_cv42"]["states"]["tracking"]
        > summaries["cv46_gate_plus_cue"]["states"]["tracking"]
    )
    assert summaries["cv46_gate_plus_cue"]["per_pitch"]["747139:2:1"]["states"] == {"unseeded": 12}
    assert set(report["consistency_violations"].values()) == {0}
    assert report["prefix_invariance_rows_checked"] == 18
    assert report["mitt_identity"] == "unverified" and report["accuracy"] == "unmeasured"
    records = json.loads((out / "records_cv46.json").read_text(encoding="utf-8"))
    assert len(records) == 36
    assert {r["seed_source"] for r in records if r["seed_source"]} == {
        "saved_AI_seed_gate_dev_v1_identity_cue_dev_v1"
    }
    crops = sorted(p.name for p in (out / "crops").iterdir())
    assert len(crops) == 6 and crops[0] == "747139_1_1_000000_baseline.png"
    public = json.loads((out / "report_public.json").read_text(encoding="utf-8"))
    gate = public["per_pitch"]["747139:1:1"]["gate_seed"]
    assert "seed_point_px" not in gate and "crop" not in gate and "point_px" not in gate["cue"]
    assert "seed_point_px" in report["per_pitch"]["747139:1:1"]["gate_seed"]


def test_frozen_hash_mismatch_and_existing_output_are_rejected(inputs, tmp_path):
    bundle, answers_dir, baseline, expected = inputs
    wrong = dict(expected, baseline="0" * 64)
    with pytest.raises(ValueError, match="frozen input hashes"):
        pilot.run(bundle, answers_dir, baseline, tmp_path / "out2", wrong)
    assert not (tmp_path / "out2").exists()
    with pytest.raises(ValueError, match="must be new"):
        pilot.run(bundle, answers_dir, baseline, tmp_path, expected)
    broken = tmp_path / "out3"
    with pytest.raises(ValueError, match="frozen input hashes"):
        pilot.run(bundle, answers_dir, baseline, broken, dict(expected, manifest="1" * 64))
    assert not broken.exists()


def test_changed_frame_is_rejected_at_decode():
    frame = {"path": None, "sha256": "0" * 64}

    class Fake:
        def read_bytes(self):
            return b"not the frame"

    frame["path"] = Fake()
    with pytest.raises(ValueError, match="integrity"):
        pilot.load_rgb(frame)


def readings(**seeds):
    return {
        "schema": "pitcheezy-seed-identity-readings-dev-v1",
        "models": {"claude": "claude-fable-5-1", "codex": "gpt-6-astra"},
        "seeds": seeds,
    }


def report_stub():
    def cue(verdict):
        return {
            "cue": {
                "verdict": verdict,
                "reason": "x",
                "point_px": [1, 1],
                "patch_box": [0, 0, 2, 2],
            },
            "seed_point_px": [1.0, 1.0],
        }

    return {
        "per_pitch": {
            "747139:1:1": {"baseline_seed": cue("mitt_like"), "gate_seed": cue("hand_like")}
        }
    }


def test_merge_requires_all_three_sources_to_agree():
    merged = pilot.merge_readings(
        report_stub(),
        readings(
            **{
                "747139:1:1:baseline": {
                    "claude": {"reading": "mitt"},
                    "codex": {"reading": "mitt"},
                },
                "747139:1:1:gate": {"claude": {"reading": "hand"}, "codex": {"reading": "unclear"}},
            }
        ),
    )
    per = merged["per_pitch"]["747139:1:1"]
    assert per["baseline_seed"]["agreement"]["status"] == "ai_agreement"
    assert per["baseline_seed"]["agreement"]["value"] == "mitt"
    assert per["gate_seed"]["agreement"]["status"] == "undetermined"
    assert merged["agreement_summary"] == {
        "seeds_with_readings": 2,
        "ai_agreement": 1,
        "undetermined": 1,
        "note": "ai_agreement means cue, Claude and Codex coincide; it is not mitt identification",
    }
    missing = pilot.merge_readings(
        report_stub(), readings(**{"747139:1:1:baseline": {"claude": {"reading": "mitt"}}})
    )
    assert (
        missing["per_pitch"]["747139:1:1"]["baseline_seed"]["agreement"]["status"] == "undetermined"
    )
    with pytest.raises(ValueError, match="reading must be"):
        pilot.merge_readings(
            report_stub(), readings(**{"747139:1:1:baseline": {"claude": {"reading": "glove"}}})
        )
    with pytest.raises(ValueError, match="unknown seed"):
        pilot.merge_readings(report_stub(), readings(**{"747139:9:9:gate": {}}))
    with pytest.raises(ValueError, match="schema"):
        pilot.merge_readings(report_stub(), {"seeds": {}})
    stub = report_stub()
    pilot.merge_readings(copy.deepcopy(stub), readings())
    assert "readings" not in stub


def test_merge_rejects_private_fields_malformed_readers_and_repeated_merges():
    base = "747139:1:1:baseline"
    with pytest.raises(ValueError, match=r"reading[, evidence, model]"):
        pilot.merge_readings(
            report_stub(),
            readings(**{base: {"claude": {"reading": "mitt", "seed_point_px": [600, 300]}}}),
        )
    with pytest.raises(ValueError, match="path separators"):
        pilot.merge_readings(
            report_stub(),
            readings(**{base: {"claude": {"reading": "mitt", "evidence": "see C:/private/x.png"}}}),
        )
    with pytest.raises(ValueError, match="claude reading must be a dict"):
        pilot.merge_readings(report_stub(), readings(**{base: {"claude": "glove"}}))
    with pytest.raises(ValueError, match="codex reading must be a dict"):
        pilot.merge_readings(report_stub(), readings(**{base: {"codex": None}}))
    with pytest.raises(ValueError, match="evidence must be a short string"):
        pilot.merge_readings(
            report_stub(), readings(**{base: {"claude": {"reading": "mitt", "evidence": None}}})
        )
    with pytest.raises(ValueError, match="model must be a short string"):
        pilot.merge_readings(
            report_stub(), readings(**{base: {"claude": {"reading": "mitt", "model": 3}}})
        )
    with pytest.raises(ValueError, match="claude/codex"):
        pilot.merge_readings(report_stub(), readings(**{base: {"human": {"reading": "mitt"}}}))
    merged = pilot.merge_readings(
        report_stub(),
        readings(
            **{base: {"claude": {"reading": "mitt", "evidence": "dark leather", "model": "x"}}}
        ),
    )
    assert merged["per_pitch"]["747139:1:1"]["baseline_seed"]["readings"] == {
        "claude": {"reading": "mitt", "evidence": "dark leather", "model": "x"}
    }
    public = pilot.public_copy(merged)
    assert "seed_point_px" not in public["per_pitch"]["747139:1:1"]["baseline_seed"]
    with pytest.raises(ValueError, match="already carries readings"):
        pilot.merge_readings(
            merged, readings(**{"747139:1:1:gate": {"codex": {"reading": "hand"}}})
        )

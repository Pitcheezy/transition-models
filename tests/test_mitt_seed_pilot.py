"""Small real tracker replays for seed-gate provenance, denominators and causality."""

import copy
import json

import numpy as np
import pytest
import torch
from PIL import Image

from intent import mitt_seed_pilot as pilot


def save(path, value):
    path.write_text(json.dumps(value, allow_nan=False), encoding="utf-8")


@pytest.fixture
def inputs(tmp_path, monkeypatch):
    """Two six-frame pitches; only the first can qualify at the fifth frame."""
    torch.set_num_threads(4)
    bundle, answers_dir = tmp_path / "bundle", tmp_path / "pilot"
    bundle.mkdir()
    (answers_dir / "answers").mkdir(parents=True)
    manifest = bundle / "manifest.json"
    metadata = answers_dir / "pilot_private.json"
    answer_file = answers_dir / "answers" / "b01.json"
    save(manifest, {"fixture": "two pitches, six frames each"})
    save(metadata, {"fixture": "saved development observations"})
    save(answer_file, {"fixture": "not human labels"})
    pixels = np.full((720, 1280), 30, dtype=np.uint8)
    pixels[290:311, 590:611] = np.random.default_rng(42).integers(40, 200, (21, 21), dtype=np.uint8)
    selected, observations, old_seeds = [], {}, {}
    preserved = {str(p): pilot.inputs.sha(p) for p in (manifest, metadata, answer_file)}
    for number in (1, 2):
        pitch = f"747139:{number}:1"
        old_seeds[pitch] = (0, [600, 300])
        folder = bundle / f"pa{number}_p1"
        folder.mkdir()
        for ordinal in range(6):
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
                    "uncertainty_px": 2 if number == 1 else None,
                }
    manifest_sha = pilot.inputs.sha(manifest)
    monkeypatch.setattr(
        pilot.inputs,
        "load_inputs",
        lambda *_: (selected, old_seeds, observations, dict(preserved), manifest_sha),
    )
    rows, _ = pilot.replay.replay_candidate(selected, old_seeds, observations, "cpu")
    baseline = tmp_path / "records_candidate_cpu.json"
    save(baseline, rows)
    provenance = pilot.inputs.saved_pilot_provenance(answers_dir, preserved)
    expected = {
        "manifest": manifest_sha,
        "pilot": provenance["pilot_private_sha256"],
        "answers": provenance["answers_manifest_sha256"],
        "baseline": pilot.inputs.sha(baseline),
    }
    return {
        "bundle": bundle,
        "pilot": answers_dir,
        "baseline": baseline,
        "out": tmp_path / "output",
        "expected": expected,
        "selected": selected,
        "observations": observations,
        "old_seeds": old_seeds,
        "preserved": preserved,
        "answer_file": answer_file,
    }


def run_inputs(data):
    return pilot.run(
        **{key: data[key] for key in ("bundle", "pilot", "baseline", "out", "expected")}
    )


def test_run_preserves_unseeded_pitch_denominator_and_source_inputs(inputs):
    objects_before = copy.deepcopy(
        (inputs["selected"], inputs["old_seeds"], inputs["observations"])
    )
    paths = [*inputs["preserved"], str(inputs["baseline"])]
    bytes_before = {path: open_bytes(path) for path in paths}
    report = run_inputs(inputs)
    assert report["baseline_every_field_reproduced"] is True
    assert report["baseline_rows"] == report["baseline"]["frames"] == 12
    assert report["candidate"]["frames"] == 12
    assert report["candidate"]["pitches"] == 2
    assert report["candidate"]["per_pitch"]["747139:2:1"]["states"] == {"unseeded": 6}
    assert report["seeded_pitches"] == 1
    assert report["per_pitch"]["747139:1:1"]["gate_seed"]["frame_index"] == 24
    assert report["per_pitch"]["747139:1:1"]["delay_from_baseline_seconds"] == pytest.approx(
        24 * 1001 / 60000
    )
    assert report["per_pitch"]["747139:2:1"]["gate_seed"] is None
    assert report["prefix_invariance"]["gate_prefix_rows"] == 42
    assert set(report["consistency_violations"].values()) == {0}
    assert report["all_input_bytes_unchanged"] is True
    assert report["accuracy"] == "unmeasured"
    assert report["independent_evaluation"] is False
    assert objects_before == (inputs["selected"], inputs["old_seeds"], inputs["observations"])
    assert bytes_before == {path: open_bytes(path) for path in paths}
    rows = json.loads((inputs["out"] / "records_seed_gate.json").read_text(encoding="utf-8"))
    assert len(rows) == 12
    assert all(row["mitt_identity"] == "unverified" for row in rows)
    assert str(inputs["bundle"]) not in json.dumps(report)


def open_bytes(path):
    from pathlib import Path

    return Path(path).read_bytes()


@pytest.mark.parametrize(
    "change",
    [
        lambda row: row.update(source_sha256="f" * 64),
        lambda row: row["stationary"].update(events_total=999),
        lambda row: row["quality"].update(unexpected_diagnostic=123),
        lambda row: row.update(raw_ai_point_px=[601, 300]),
        lambda row: row.update(seed_source="wrong_saved_source"),
    ],
    ids=["source-sha", "nested-stationary", "nested-quality", "raw-ai-point", "seed-source"],
)
def test_baseline_gate_compares_every_saved_field_not_a_small_projection(inputs, change):
    rows = json.loads(inputs["baseline"].read_text(encoding="utf-8"))
    change(rows[0])
    save(inputs["baseline"], rows)
    inputs["expected"]["baseline"] = pilot.inputs.sha(inputs["baseline"])
    with pytest.raises(ValueError, match="every saved field"):
        run_inputs(inputs)
    assert not inputs["out"].exists()


@pytest.mark.parametrize("field", ["manifest", "pilot", "answers", "baseline"])
def test_frozen_input_hash_mismatch_blocks_before_replay(inputs, monkeypatch, field):
    inputs["expected"][field] = "0" * 64

    def forbidden(*_args, **_kwargs):
        pytest.fail("tracker was invoked before frozen input hash verification")

    monkeypatch.setattr(pilot.replay, "replay_candidate", forbidden)
    with pytest.raises(ValueError, match="frozen input hashes"):
        run_inputs(inputs)
    assert not inputs["out"].exists()


def test_prefix_check_reselects_seed_without_future_rows(inputs, monkeypatch):
    selected, observations = inputs["selected"][:6], inputs["observations"]
    seeds, decisions = pilot.choose(selected, observations)
    rows, _ = pilot.gated_replay(selected, seeds, observations)
    assert seeds["747139:1:1"][0] == 24
    real_replay, observed_cuts = pilot.gated_replay, []

    def checked(part, prefix_seeds, obs):
        keys = {(pitch, frame["index"]) for pitch, frame in part}
        assert set(obs).issubset(keys)
        if part[-1][1]["index"] < 24:
            assert prefix_seeds["747139:1:1"] is None
        observed_cuts.append(part[-1][1]["index"])
        return real_replay(part, prefix_seeds, obs)

    monkeypatch.setattr(pilot, "gated_replay", checked)
    counts = pilot.prefix_check(selected, observations, decisions, rows)
    assert 18 in observed_cuts and 24 in observed_cuts
    assert counts["gate_prefix_rows"] == 21
    assert counts["tracker_prefix_rows"] > 0


def test_future_observation_changes_do_not_change_earlier_decisions(inputs):
    selected, observations = inputs["selected"][:4], inputs["observations"]
    before = pilot.choose(selected, observations)
    changed = copy.deepcopy(observations)
    changed[("747139:1:1", 24)].update(mitt_center_px=[800, 500], uncertainty_px=None)
    assert pilot.choose(selected, changed) == before
    assert before[0] == {"747139:1:1": None}


def test_prefix_check_rejects_changed_nested_earlier_output(inputs):
    selected, observations = inputs["selected"][:6], inputs["observations"]
    seeds, decisions = pilot.choose(selected, observations)
    rows, _ = pilot.gated_replay(selected, seeds, observations)
    rows[0]["stationary"]["events_total"] = 1
    with pytest.raises(ValueError, match="tracker prefix differs"):
        pilot.prefix_check(selected, observations, decisions, rows)


def test_gated_seed_source_is_current_gate_observation_not_old_first_usable(inputs):
    seeds, _ = pilot.choose(inputs["selected"], inputs["observations"])
    rows, _ = pilot.gated_replay(inputs["selected"], seeds, inputs["observations"])
    seeded = [row for row in rows if row["seed_source"] is not None]
    assert [(row["pitch_id"], row["frame_index"]) for row in seeded] == [("747139:1:1", 24)]
    assert seeded[0]["seed_source"] == "saved_AI_seed_gate_dev_v1_current_observation"
    assert all(row["seed_source"] is None for row in rows if row["frame_index"] < 24)


def test_input_file_changed_during_replay_is_detected_before_outputs(inputs, monkeypatch):
    real_choose = pilot.choose
    changed = False

    def modify_after_loading(selected, observations):
        nonlocal changed
        if not changed:
            inputs["answer_file"].write_text("{}", encoding="utf-8")
            changed = True
        return real_choose(selected, observations)

    monkeypatch.setattr(pilot, "choose", modify_after_loading)
    with pytest.raises(ValueError, match="input files changed"):
        run_inputs(inputs)
    assert not inputs["out"].exists()


def test_existing_output_directory_is_preserved(inputs):
    inputs["out"].mkdir()
    sentinel = inputs["out"] / "do-not-overwrite.txt"
    sentinel.write_text("existing result", encoding="utf-8")
    with pytest.raises(ValueError, match="output must be new"):
        run_inputs(inputs)
    assert sentinel.read_text(encoding="utf-8") == "existing result"

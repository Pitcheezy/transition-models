"""Source identity and unannotated-pixel boundaries of the offline pilot."""

import hashlib
import json

import numpy as np
import pytest
from PIL import Image

from intent import mitt_tracking_pilot as pilot


def save(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


@pytest.fixture
def inputs(tmp_path):
    bundle, answers_dir = tmp_path / "bundle", tmp_path / "pilot"
    bundle.mkdir()
    (answers_dir / "answers").mkdir(parents=True)
    pitches, mapping, answers = [], [], []
    for number in range(1, 11):
        pitch = f"747139:{number}:1"
        folder = bundle / f"pa{number}_p1"
        folder.mkdir()
        rows = []
        for index in (0, 6, 12):
            path = folder / f"frame_{index:06d}.jpg"
            Image.fromarray(np.full((720, 1280), 80, np.uint8)).save(path)
            raw = path.read_bytes()
            rows.append(
                {
                    "index": index,
                    "pts_time": index * 1001 / 60000,
                    "roles": ["grid"],
                    "sha256": hashlib.sha256(raw).hexdigest(),
                    "bytes": len(raw),
                }
            )
            # Deliberately wrong crop: the loader must never consume a drawn-grid surrogate.
            (folder / f"crop_{index:06d}.jpg").write_bytes(b"not the source image")
        pitches.append(
            {
                "pitch_id": pitch,
                "status": "extracted",
                "window": {"release_index": 12},
                "frames": rows,
            }
        )
        for index in (0, 12):
            identifier = f"{number}_{index}"
            mapping.append(
                {"pitch_id": pitch, "index": index, "id": identifier, "kind": "sequence"}
            )
            answers.append(
                {
                    "id": identifier,
                    "view": "live_centre_field",
                    "catcher": "set",
                    "mitt_visibility": "full",
                    "occluder": None,
                    "mitt_center_px": [600, 300],
                    "pitcher_phase": "before_delivery",
                    "uncertainty_px": None,
                    "plate_front": None,
                }
            )
    manifest = {"source": {"time_base": "1/60000", "ticks_per_frame": 1001}, "pitches": pitches}
    save(bundle / "manifest.json", manifest)
    meta = {
        "bundle_manifest_sha256": pilot.sha(bundle / "manifest.json"),
        "pitches": [p["pitch_id"] for p in pitches],
        "mapping": mapping,
    }
    save(answers_dir / "pilot_private.json", meta)
    save(answers_dir / "answers" / "b01.json", {"frames": answers})
    return bundle, answers_dir


def test_loader_reads_original_frames_and_frozen_sequence_plan(inputs):
    selected, seeds, observations, preserved, _ = pilot.load_inputs(*inputs)
    assert len(selected) == 30 and len(seeds) == 10 and len(observations) == 20
    assert all(f["path"].name.startswith("frame_") for _, f in selected)
    assert not any("crop_" in path for path in preserved)
    assert all(value == (0, [600.0, 300.0]) for value in seeds.values())


def test_replaced_source_is_rejected(inputs):
    bundle, _ = inputs
    (bundle / "pa1_p1" / "frame_000000.jpg").write_bytes(b"changed")
    with pytest.raises(ValueError, match="integrity"):
        pilot.load_inputs(*inputs)


def test_missing_sequence_cannot_silently_change_evaluation_denominator(inputs):
    _, saved = inputs
    meta_path = saved / "pilot_private.json"
    meta = json.loads(meta_path.read_text())
    meta["mapping"][0]["kind"] = "v0_reread"
    save(meta_path, meta)
    with pytest.raises(ValueError, match="frozen frame plan"):
        pilot.load_inputs(*inputs)


def test_wrong_pts_even_with_new_manifest_hash_is_rejected(inputs):
    bundle, saved = inputs
    path = bundle / "manifest.json"
    manifest = json.loads(path.read_text())
    manifest["pitches"][0]["frames"][0]["pts_time"] = 7.0
    save(path, manifest)
    meta_path = saved / "pilot_private.json"
    meta = json.loads(meta_path.read_text())
    meta["bundle_manifest_sha256"] = pilot.sha(path)
    save(meta_path, meta)
    with pytest.raises(ValueError, match="PTS"):
        pilot.load_inputs(*inputs)


def test_output_directory_must_be_new(inputs):
    with pytest.raises(ValueError, match="must be new"):
        pilot.run(*inputs, inputs[0], ["cpu"])

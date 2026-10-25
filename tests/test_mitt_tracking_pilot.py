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


def test_saved_answers_are_bound_without_local_paths_and_changes_are_visible(inputs):
    _, saved = inputs
    *_, preserved, _ = pilot.load_inputs(*inputs)
    before = pilot.saved_pilot_provenance(saved, preserved)
    assert before["pilot_private_sha256"] == pilot.sha(saved / "pilot_private.json")
    assert before["answer_files"] == 1
    assert before["answers_sha256"] == {"answers/b01.json": pilot.sha(saved / "answers/b01.json")}
    encoded = json.dumps(before["answers_sha256"], sort_keys=True, separators=(",", ":")).encode()
    assert before["answers_manifest_sha256"] == hashlib.sha256(encoded).hexdigest()
    assert str(saved) not in json.dumps(before)

    path = saved / "answers/b01.json"
    answer = json.loads(path.read_text())
    answer["frames"][0]["mitt_center_px"] = [601, 300]
    save(path, answer)
    _, seeds, _, preserved, _ = pilot.load_inputs(*inputs)
    after = pilot.saved_pilot_provenance(saved, preserved)
    assert seeds["747139:1:1"] == (0, [601.0, 300.0])
    assert after["pilot_private_sha256"] == before["pilot_private_sha256"]
    assert after["answers_manifest_sha256"] != before["answers_manifest_sha256"]
    assert after["answers_sha256"] != before["answers_sha256"]


def test_environment_records_observed_cpu_and_thread_settings(monkeypatch):
    monkeypatch.setattr(pilot.platform, "processor", lambda: "synthetic CPU")
    monkeypatch.setattr(pilot.os, "cpu_count", lambda: 12)
    monkeypatch.setattr(pilot.torch, "get_num_threads", lambda: 3)
    monkeypatch.setattr(pilot.torch, "get_num_interop_threads", lambda: 2)
    environment = pilot.environment_info(["cpu"])
    assert environment["cpu_model"] == "synthetic CPU"
    assert environment["cpu_logical_cores"] == 12
    assert environment["cpu_threads"] == 3
    assert environment["cpu_interop_threads"] == 2
    assert environment["gpu"] is None


def test_replay_partitions_loss_events_timing_and_raw_ai_comparisons(tmp_path, monkeypatch):
    """A first loss is an active attempt; later LOST rows are idle, not new failures."""
    pitch = "747139:1:1"
    patch = np.random.default_rng(37).integers(40, 200, (21, 21), dtype=np.uint8)
    selected = []
    for ordinal in range(7):
        image = np.full((720, 1280), 30, np.uint8)
        if 1 <= ordinal <= 4:
            x = 599 + ordinal
            image[290:311, x - 10 : x + 11] = patch
        path = tmp_path / f"frame_{ordinal * 6:06d}.jpg"
        Image.fromarray(image).save(path, quality=95)
        selected.append(
            (
                pitch,
                {
                    "index": ordinal * 6,
                    "pts_time": ordinal * 6 * 1001 / 60000,
                    "path": path,
                    "sha256": pilot.sha(path),
                },
            )
        )

    def observation(point, catcher="set"):
        return {
            "view": "live_centre_field",
            "catcher": catcher,
            "mitt_visibility": "full",
            "mitt_center_px": point,
        }

    observations = {
        (pitch, 6): observation([600, 300]),
        (pitch, 12): observation([601, 300]),
        (pitch, 18): observation([999, 600], "not_set"),
    }
    # Distinct deterministic totals make an accidental all-row/active mix observable.
    ticks = iter(
        value
        for ordinal in range(7)
        for value in (ordinal, ordinal + 0.003, ordinal + (ordinal + 1) * 0.01)
    )
    monkeypatch.setattr(pilot.time, "perf_counter", lambda: next(ticks))
    rows, report = pilot.replay(selected, {pitch: (6, [600, 300])}, observations, "cpu")

    assert [r["prior_state"] for r in rows] == [
        "unseeded",
        "unseeded",
        "tracking",
        "tracking",
        "tracking",
        "tracking",
        "lost",
    ]
    assert [r["state"] for r in rows] == [
        "unseeded",
        "tracking",
        "tracking",
        "tracking",
        "tracking",
        "lost",
        "lost",
    ]
    assert report["first_loss_reasons"] == {"low_texture": 1}
    assert report["reasons"]["low_texture"] == 2
    assert report["seed_rejection_reasons"] == {}
    assert report["post_loss_rows"] == 1 and report["post_loss_matching"] is False
    assert report["active_read_to_host_result_ms"]["n"] == 4
    assert report["active_read_to_host_result_ms"]["median"] == pytest.approx(45)
    assert report["seed_read_to_host_result_ms"]["n"] == 1
    assert report["seed_read_to_host_result_ms"]["median"] == pytest.approx(20)
    assert report["idle_read_to_host_result_ms"]["n"] == 2
    assert report["idle_read_to_host_result_ms"]["median"] == pytest.approx(40)
    assert report["read_to_host_result_ms"]["n"] == 7
    assert report["active_attempt_ms"]["n"] == 4
    assert report["seed_ms"]["n"] == 1
    assert rows[3]["raw_ai_point_px"] == [999, 600]
    assert rows[3]["ai_unusable_reason"] == "catcher_not_set"
    assert rows[4]["ai_unusable_reason"] == "no_saved_observation"
    assert report["same_frame_AI_disagreement_px_not_accuracy"]["n"] == 2
    assert report["same_frame_usable_AI_disagreement_px_not_accuracy"]["n"] == 1
    assert report["same_frame_unusable_AI_disagreement_px_not_accuracy"]["n"] == 1
    assert report["unusable_AI_pair_reasons"] == {"catcher_not_set": 1}


def test_seed_rejection_is_not_counted_as_an_active_tracking_loss(inputs):
    selected, seeds, observations, _, _ = pilot.load_inputs(*inputs)
    rows, report = pilot.replay(selected[:3], seeds, observations, "cpu")
    assert [r["state"] for r in rows] == ["lost", "lost", "lost"]
    assert report["first_loss_reasons"] == {}
    assert report["seed_rejection_reasons"] == {"seed_low_texture": 1}
    assert report["active_read_to_host_result_ms"]["n"] == 0
    assert report["seed_read_to_host_result_ms"]["n"] == 1
    assert report["idle_read_to_host_result_ms"]["n"] == 2
    assert report["same_frame_AI_disagreement_px_not_accuracy"]["n"] == 0

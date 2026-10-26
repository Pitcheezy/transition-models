"""Base regression gate, bounded metrics and prefix invariance of the re-search replay."""

import hashlib
import json

import numpy as np
import pytest
from PIL import Image

from intent import mitt_reacquire_pilot as pilot
from intent import mitt_tracking_pilot as base_pilot

PATCH = np.random.default_rng(37).integers(40, 200, (21, 21), dtype=np.uint8)


def save(path, data):
    path.write_text(json.dumps(data), encoding="utf-8")


def frame_pixels(ordinal):
    """A patch drifting 1 px per frame, hidden on the fourth frame, then back in view."""
    image = np.full((720, 1280), 30, np.uint8)
    if ordinal != 3:
        x = 600 + ordinal
        image[290:311, x - 10 : x + 11] = PATCH
    return image


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
        for ordinal in range(7):
            index = ordinal * 6
            path = folder / f"frame_{index:06d}.jpg"
            Image.fromarray(frame_pixels(ordinal)).save(path, quality=95)
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
        pitches.append(
            {
                "pitch_id": pitch,
                "status": "extracted",
                "window": {"release_index": 36},
                "frames": rows,
            }
        )
        for index in (0, 12, 24, 36):
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
                    "mitt_center_px": [600 + index // 6, 300],
                    "pitcher_phase": "before_delivery",
                    "uncertainty_px": None,
                    "plate_front": None,
                }
            )
    manifest = {"source": {"time_base": "1/60000", "ticks_per_frame": 1001}, "pitches": pitches}
    save(bundle / "manifest.json", manifest)
    meta = {
        "bundle_manifest_sha256": base_pilot.sha(bundle / "manifest.json"),
        "pitches": [p["pitch_id"] for p in pitches],
        "mapping": mapping,
    }
    save(answers_dir / "pilot_private.json", meta)
    save(answers_dir / "answers" / "b01.json", {"frames": answers})
    selected, seeds, observations, _, _ = base_pilot.load_inputs(bundle, answers_dir)
    rows, _ = base_pilot.replay(selected, seeds, observations, "cpu")
    saved = tmp_path / "records_cpu.json"
    saved.write_text(json.dumps(rows, indent=2) + "\n", encoding="utf-8")
    return bundle, answers_dir, saved


def test_run_gates_on_base_regression_and_reports_bounded_reacquisition(inputs, tmp_path):
    bundle, answers_dir, saved = inputs
    out = tmp_path / "out"
    report = pilot.run(bundle, answers_dir, saved, out)
    totals = report["metrics"]["totals"]
    assert report["base_regression"] == {
        "equal_to_saved_records": True,
        "compared_fields": list(pilot.COMPARED),
        "rows": 70,
    }
    assert totals["frames"] == 70 and totals["pitches"] == 10
    assert totals["base_states"] == {"tracking": 30, "lost": 40}
    assert totals["candidate_states"] == {
        "tracking": 50,
        "reacquire_search": 10,
        "reacquire_candidate": 10,
    }
    assert totals["windows"] == 10 and totals["window_frames"] == 20
    assert totals["search_frames"] == 20
    assert totals["candidates"] == 10 and totals["accepted"] == 10
    assert totals["window_outcomes"] == {"reacquired": 10}
    assert totals["abstain_reasons"] == {"reacquire_low_texture": 10}
    assert totals["reacquired_segments"] == 10
    assert totals["anchor_distance_px"]["median"] == pytest.approx(2.0)
    assert totals["seed_template_ncc_at_candidates_diagnostic_only"]["n"] == 10
    assert set(report["metrics"]["consistency_violations"].values()) == {0}
    pitch = report["metrics"]["per_pitch"]["747139:1:1"]
    assert pitch["base"]["first_loss"] == {
        "frame_index": 18,
        "seconds_after_seed": pytest.approx(18 * 1001 / 60000),
        "reason": "low_texture",
    }
    assert pitch["candidate"]["first_segment_loss_same_as_base"] is True
    assert [s["start_reason"] for s in pitch["candidate"]["segments"]] == [
        "external_seed",
        "reacquired_continuity",
    ]
    assert pitch["candidate"]["segments"][1]["start_frame"] == 30
    assert pitch["candidate"]["windows"][0]["loss_reason"] == "low_texture"
    assert pitch["base"]["stationary_events"] == 0 and pitch["candidate"]["stationary_events"] == 0
    assert report["prefix_invariance_rows_checked"] == 30
    disagreement = report["metrics"]["same_frame_AI_disagreement"]
    assert disagreement["first_segment"]["all_px_not_accuracy"]["n"] == 10
    assert disagreement["reacquired_segments"]["all_px_not_accuracy"]["n"] == 10
    assert (
        report["timing_ms"]["candidate_tracker_step_by_prior_state"]["reacquire_search"]["n"] == 10
    )
    assert (out / "report.json").exists()
    records = json.loads((out / "records_candidate_cpu.json").read_text(encoding="utf-8"))
    assert len(records) == 70 and all(r["mitt_identity"] == "unverified" for r in records)
    assert str(bundle) not in json.dumps(report)


def test_saved_record_mismatch_blocks_the_comparison(inputs, tmp_path):
    bundle, answers_dir, saved = inputs
    rows = json.loads(saved.read_text(encoding="utf-8"))
    rows[1]["state"] = "lost"
    saved.write_text(json.dumps(rows), encoding="utf-8")
    with pytest.raises(ValueError, match="reproduce"):
        pilot.run(bundle, answers_dir, saved, tmp_path / "out")
    assert not (tmp_path / "out").exists()


def test_output_directory_must_be_new(inputs, tmp_path):
    bundle, answers_dir, saved = inputs
    with pytest.raises(ValueError, match="must be new"):
        pilot.run(bundle, answers_dir, saved, tmp_path)


def test_compare_requires_the_same_frames():
    with pytest.raises(ValueError, match="same frames"):
        pilot.compare([{"pitch_id": "a", "frame_index": 0}], [{"pitch_id": "a", "frame_index": 1}])


def test_exhaustion_after_a_rejected_candidate_is_counted_as_a_rejection():
    rows = []
    quality = {}
    for index, (state, reason, end) in enumerate(
        [
            ("tracking", "external_seed", None),
            ("reacquire_search", "reacquire_low_texture", "low_texture"),
            ("reacquire_search", "reacquire_low_texture", None),
            ("reacquire_search", "reacquire_low_texture", None),
            ("reacquire_candidate", "reacquire_candidate", None),
            ("lost", "reacquire_exhausted", None),
        ]
    ):
        quality = {"reacquire_attempt": index, "reacquire_searched": state != "lost"}
        if state == "reacquire_candidate":
            quality.update(anchor_distance_px=1.0, seed_template_ncc_diagnostic_only=0.5)
        if state == "lost":
            quality = {
                "reacquire_attempt": 5,
                "last_attempt_reason": "reacquire_candidate_low_texture",
            }
        rows.append(
            {
                "pitch_id": "p",
                "frame_index": index,
                "frame_seconds": index / 10,
                "state": state,
                "reason": reason,
                "point_px": [1, 1] if state == "tracking" else None,
                "segment_id": 1 if state == "tracking" else None,
                "segment_end_reason": end,
                "quality": quality,
            }
        )
    segments, windows = pilot._segments_and_windows(rows)
    assert len(segments) == 1 and len(windows) == 1
    assert windows[0]["rejected_reasons"] == {"reacquire_candidate_low_texture": 1}
    assert windows[0]["abstain_reasons"] == {"reacquire_low_texture": 3}
    assert windows[0]["window_frames"] == 5 and windows[0]["search_frames"] == 4
    assert windows[0]["outcome"] == "reacquire_exhausted"


def test_prefix_invariance_rejects_any_changed_earlier_output(inputs, monkeypatch):
    bundle, answers_dir, _ = inputs
    selected, seeds, observations, _, _ = base_pilot.load_inputs(bundle, answers_dir)
    rows, _ = pilot.replay_candidate(selected, seeds, observations, "cpu")
    assert pilot.prefix_invariance(selected, seeds, observations, rows, "cpu") == 30
    tampered = json.loads(json.dumps(rows))
    tampered[1]["stationary"]["events_total"] += 1
    with pytest.raises(ValueError, match="earlier output"):
        pilot.prefix_invariance(selected, seeds, observations, tampered, "cpu")
    tampered = json.loads(json.dumps(rows))
    tampered[0]["stationary"]["last_historical_candidate"] = {"frame_index": 99}
    with pytest.raises(ValueError, match="earlier output"):
        pilot.prefix_invariance(selected, seeds, observations, tampered, "cpu")

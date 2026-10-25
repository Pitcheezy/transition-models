"""Track a known patch, and abstain when continuity is not supported."""

import numpy as np
import pytest
import torch

from intent.mitt_tracking import PatchTracker, TrackParams


@pytest.fixture(autouse=True)
def bounded_cpu_threads():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


def scene(x=60, y=60, *, duplicate=None, bright=0):
    rng = np.random.default_rng(17)
    patch = rng.integers(40, 200, (21, 21), dtype=np.uint8)
    image = np.full((140, 160), 30, np.uint8)
    image[y - 10 : y + 11, x - 10 : x + 11] = patch
    if duplicate:
        a, b = duplicate
        image[b - 10 : b + 11, a - 10 : a + 11] = patch
    return np.clip(image.astype(int) + bright, 0, 255).astype(np.uint8)


def step(tracker, image, i, **kwargs):
    return tracker.step(image, pitch_id="747139:3:1", frame_index=i, frame_seconds=i / 10, **kwargs)


def test_translation_brightness_source_coordinates_and_no_semantic_claim():
    tracker = PatchTracker(origin=(330, 100))
    first = step(tracker, scene(), 0, seed=[390.2, 160.4])
    assert first["point_px"] == [390, 160]
    assert first["seed_requested_px"] == [390.2, 160.4]
    for i in range(1, 5):
        row = step(tracker, scene(60 + i * 2, 60 + i, bright=10), i)
        assert row["state"] == "tracking"
        assert row["point_px"] == [390 + i * 2, 160 + i]
        assert row["quality"]["fb_error_px"] == 0
        assert row["mitt_identity"] == "unverified"


@pytest.mark.parametrize("failure", ["hidden", "duplicate", "boundary", "cut", "gap", "gate"])
def test_failure_never_republishes_a_stale_point_or_reacquires(failure):
    tracker = PatchTracker()
    step(tracker, scene(), 0, seed=[60, 60])
    image, i, kwargs = scene(), 1, {}
    if failure == "hidden":
        image = np.full_like(image, 30)
    elif failure == "duplicate":
        image = scene(48, 60, duplicate=(72, 60))
    elif failure == "boundary":
        image = scene(84, 60)
    elif failure == "cut":
        image = 255 - image
    elif failure == "gap":
        i = 4
    elif failure == "gate":
        kwargs = {"usable": False}
    row = step(tracker, image, i, **kwargs)
    assert row["state"] == "lost" and row["point_px"] is None
    expected = {
        "duplicate": "ambiguous_peak",
        "boundary": "search_boundary",
        "cut": "appearance_discontinuity",
        "gap": "time_gap",
        "gate": "external_view_gate",
    }
    if failure in expected:
        assert row["reason"] == expected[failure]
    resumed = step(tracker, scene(), i + 1)
    assert resumed["state"] == "lost" and resumed["point_px"] is None
    with pytest.raises(ValueError, match="reseed"):
        step(tracker, scene(), i + 2, seed=[60, 60])


def test_seed_quality_border_and_no_seed_are_distinct():
    assert step(PatchTracker(), scene(), 0)["state"] == "unseeded"
    assert (
        step(PatchTracker(), np.zeros((140, 160), np.uint8), 0, seed=[60, 60])["reason"]
        == "seed_low_texture"
    )
    assert step(PatchTracker(), scene(), 0, seed=[1, 1])["reason"] == "seed_border"


def test_seed_on_gated_frame_is_rejected_without_consuming_the_frame():
    tracker = PatchTracker()
    with pytest.raises(ValueError, match="seed cannot be applied on a gated frame"):
        step(tracker, scene(), 0, seed=[60, 60], usable=False)
    assert tracker.last_index is None and tracker.state == "unseeded"
    assert step(tracker, scene(), 0, seed=[60, 60])["state"] == "tracking"


def test_outer_cpu_autocast_does_not_change_tracking_precision():
    def run():
        tracker = PatchTracker()
        return [
            step(tracker, scene(60 + i, 60), i, seed=[60, 60] if i == 0 else None) for i in range(3)
        ]

    expected = run()
    with torch.autocast("cpu", dtype=torch.bfloat16):
        assert run() == expected


@pytest.mark.skipif(not torch.cuda.is_available(), reason="physical CUDA device required")
def test_caller_tf32_and_autocast_do_not_change_threshold_decisions():
    previous = torch.backends.cudnn.allow_tf32
    rows = []
    try:
        for allow in (False, True):
            torch.backends.cudnn.allow_tf32 = allow
            for autocast in (False, True):
                tracker = PatchTracker(device="cuda", params=TrackParams(min_ncc=0.999985))
                with torch.autocast("cuda", enabled=autocast):
                    step(tracker, scene(), 0, seed=[60, 60])
                    row = step(tracker, scene(), 1)
                assert torch.backends.cudnn.allow_tf32 is allow
                rows.append(row)
        assert rows[0]["state"] == "tracking"
        assert all(row == rows[0] for row in rows[1:])
    finally:
        torch.backends.cudnn.allow_tf32 = previous


def test_future_frames_do_not_change_any_prefix_or_seed_in_the_past():
    frames = [scene(60 + i, 60) for i in range(5)] + [np.full((140, 160), 30, np.uint8)]

    def run(count):
        tracker = PatchTracker()
        return [
            step(tracker, f, i, seed=[62, 60] if i == 2 else None)
            for i, f in enumerate(frames[:count])
        ]

    whole = run(len(frames))
    assert [r["state"] for r in whole[:2]] == ["unseeded", "unseeded"]
    for k in range(len(frames) + 1):
        assert run(k) == whole[:k]


@pytest.mark.parametrize("bad", [float("nan"), float("inf"), True, -1, "0.1"])
def test_invalid_time_is_rejected(bad):
    with pytest.raises(ValueError, match="frame_seconds"):
        PatchTracker().step(scene(), pitch_id="p", frame_index=0, frame_seconds=bad)


def test_pitch_frame_shape_and_coordinate_mismatch_are_rejected():
    tracker = PatchTracker()
    step(tracker, scene(), 0, seed=[60, 60])
    with pytest.raises(ValueError, match="pitch_id"):
        tracker.step(scene(), pitch_id="another", frame_index=1, frame_seconds=0.1)
    with pytest.raises(ValueError, match="increase"):
        step(tracker, scene(), 0)
    with pytest.raises(ValueError, match="shape"):
        step(tracker, scene()[:-1], 1)
    with pytest.raises(ValueError, match="outside"):
        step(PatchTracker(origin=(330, 100)), scene(), 0, seed=[60, 60])


def test_a_non_mitt_patch_can_pass_so_identity_remains_unverified():
    tracker = PatchTracker()
    for i in range(4):
        row = step(tracker, scene(), i, seed=[60, 60] if i == 0 else None)
        assert row["state"] == "tracking"
        assert row["mitt_identity"] == "unverified"


def test_configuration_digest_and_rejection():
    assert TrackParams().digest() == TrackParams().digest()
    assert TrackParams(min_ncc=0.7).digest() != TrackParams().digest()
    for kwargs in (
        {"patch_size": 20},
        {"search_radius": 0},
        {"max_gap_seconds": float("nan")},
        {"min_ncc": True},
    ):
        with pytest.raises(ValueError):
            TrackParams(**kwargs)


@pytest.mark.skipif(not torch.cuda.is_available(), reason="physical CUDA device required")
def test_cuda_and_cpu_same_states_and_coordinates():
    cpu, gpu = PatchTracker(), PatchTracker(device="cuda")
    for i in range(5):
        args = {"seed": [60, 60]} if i == 0 else {}
        a, b = step(cpu, scene(60 + i, 60), i, **args), step(gpu, scene(60 + i, 60), i, **args)
        assert (a["state"], a["point_px"]) == (b["state"], b["point_px"])
        if "ncc" in a["quality"]:
            assert abs(a["quality"]["ncc"] - b["quality"]["ncc"]) < 0.001

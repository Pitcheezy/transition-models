"""Bounded re-search after a loss: candidates are not points, and loss stays conservative."""

import numpy as np
import pytest
import torch

from intent.mitt_reacquire import (
    ReacquireParams,
    ReacquiringTracker,
    SegmentedStationarySelector,
)
from intent.mitt_stationary import StationaryParams
from intent.mitt_tracking import PatchTracker, TrackParams, match_template


@pytest.fixture(autouse=True)
def bounded_cpu_threads():
    previous = torch.get_num_threads()
    torch.set_num_threads(1)
    yield
    torch.set_num_threads(previous)


def scene(x=60, y=60, *, duplicate=None, bright=0, hidden=False):
    rng = np.random.default_rng(17)
    patch = rng.integers(40, 200, (21, 21), dtype=np.uint8)
    image = np.full((140, 160), 30, np.uint8)
    if not hidden:
        image[y - 10 : y + 11, x - 10 : x + 11] = patch
    if duplicate:
        a, b = duplicate
        image[b - 10 : b + 11, a - 10 : a + 11] = patch
    return np.clip(image.astype(int) + bright, 0, 255).astype(np.uint8)


# 0.05 s between frames keeps five search frames inside the 0.25 s stream-gap limit.
def step(tracker, image, i, **kwargs):
    return tracker.step(image, pitch_id="747139:3:1", frame_index=i, frame_seconds=i / 20, **kwargs)


def replay(frames, **kwargs):
    tracker = ReacquiringTracker(origin=(330, 100), **kwargs)
    rows = []
    for i, image in enumerate(frames):
        rows.append(step(tracker, image, i, seed=[390, 160] if i == 0 else None))
    return rows


def summary(rows):
    return [
        (r["state"], r["reason"], r["point_px"], r["reacquire_candidate_px"], r["segment_id"])
        for r in rows
    ]


def test_hidden_frame_then_candidate_then_new_segment_only_after_continuity():
    frames = [scene()] * 3 + [scene(hidden=True)] + [scene(62, 61)] * 3
    rows = replay(frames)
    assert summary(rows)[3:] == [
        ("reacquire_search", "reacquire_low_texture", None, None, None),
        ("reacquire_candidate", "reacquire_candidate", None, [392, 161], None),
        ("tracking", "reacquired_continuity", [392, 161], None, 2),
        ("tracking", "patch_continuity", [392, 161], None, 2),
    ]
    loss, candidate, confirmed = rows[3], rows[4], rows[5]
    assert loss["segment_end_reason"] == "low_texture" and loss["quality"]["reacquire_attempt"] == 1
    assert candidate["quality"]["reacquire_attempt"] == 2
    assert candidate["quality"]["anchor_distance_px"] == pytest.approx(5**0.5)
    assert candidate["quality"]["seed_template_ncc_diagnostic_only"] == pytest.approx(1.0)
    assert candidate["mitt_identity"] == confirmed["mitt_identity"] == "unverified"
    assert confirmed["reacquisitions"] == 1 and confirmed["quality"]["candidate_frame_index"] == 4
    assert all(r["reacquisitions"] == 0 for r in rows[:5])


@pytest.mark.parametrize("failure", ["hidden", "jump", "duplicate"])
def test_no_support_keeps_lost_and_exhausts_without_any_point(failure):
    after = {
        "hidden": scene(hidden=True),
        "jump": scene(120, 60),
        "duplicate": scene(48, 60, duplicate=(72, 60)),
    }[failure]
    rows = replay([scene()] * 3 + [after] * 8)
    states = [r["state"] for r in rows]
    assert states[3:8] == ["reacquire_search"] * 4 + ["lost"]
    assert rows[7]["reason"] == "reacquire_exhausted"
    assert rows[7]["quality"]["reacquire_attempt"] == 5
    expected = {"hidden": "reacquire_low_texture", "jump": "reacquire_low_texture"}
    expected["duplicate"] = "reacquire_ambiguous_peak"
    assert {r["reason"] for r in rows[3:7]} == {expected[failure]}
    assert rows[7]["quality"]["last_attempt_reason"] == expected[failure]
    assert all(r["point_px"] is None and r["reacquire_candidate_px"] is None for r in rows[3:])
    assert all(r["state"] == "lost" and r["reason"] == "reacquire_exhausted" for r in rows[8:])
    # A late reappearance does not reopen the search.
    tracker = ReacquiringTracker(origin=(330, 100))
    for i, image in enumerate([scene()] * 3 + [after] * 5 + [scene()] * 2):
        row = step(tracker, image, i, seed=[390, 160] if i == 0 else None)
    assert row["state"] == "lost" and row["point_px"] is None


def test_candidate_rejected_on_its_next_frame_counts_as_an_attempt():
    # The candidate frame shows the patch, then it vanishes again for good.
    rows = replay(
        [scene()] * 2 + [scene(hidden=True), scene(), scene(hidden=True)] + [scene(hidden=True)] * 4
    )
    assert summary(rows)[2:7] == [
        ("reacquire_search", "reacquire_low_texture", None, None, None),
        ("reacquire_candidate", "reacquire_candidate", None, [390, 160], None),
        ("reacquire_search", "reacquire_candidate_low_texture", None, None, None),
        ("reacquire_search", "reacquire_low_texture", None, None, None),
        ("lost", "reacquire_exhausted", None, None, None),
    ]
    assert [r["quality"]["reacquire_attempt"] for r in rows[2:7]] == [1, 2, 3, 4, 5]


@pytest.mark.parametrize("failure", ["cut", "gap", "gate"])
def test_stream_breaks_end_the_pitch_without_a_search(failure):
    tracker = ReacquiringTracker()
    step(tracker, scene(), 0, seed=[60, 60])
    image, i, kwargs = scene(), 1, {}
    if failure == "cut":
        image = 255 - image
    elif failure == "gap":
        i = 6
    else:
        kwargs = {"usable": False}
    row = step(tracker, image, i, **kwargs)
    expected = {"cut": "appearance_discontinuity", "gap": "time_gap", "gate": "external_view_gate"}
    assert (row["state"], row["reason"], row["segment_end_reason"]) == (
        "lost",
        expected[failure],
        expected[failure],
    )
    assert "reacquire_attempt" not in row["quality"]
    assert step(tracker, scene(), i + 1)["state"] == "lost"


def test_search_window_closes_on_a_gate_a_gap_or_a_cut():
    for failure in ("gate", "gap", "cut"):
        tracker = ReacquiringTracker()
        step(tracker, scene(), 0, seed=[60, 60])
        assert step(tracker, scene(hidden=True), 1)["state"] == "reacquire_search"
        image, i, kwargs = scene(hidden=True), 2, {}
        if failure == "gate":
            kwargs = {"usable": False}
        elif failure == "gap":
            i = 8
        else:
            image = 255 - image
        row = step(tracker, image, i, **kwargs)
        expected = {
            "gate": "external_view_gate",
            "gap": "reacquire_gap",
            "cut": "reacquire_appearance_discontinuity",
        }
        assert (row["state"], row["reason"]) == ("lost", expected[failure])


def test_reacquisitions_are_capped_per_pitch():
    frames = [scene()]
    for _ in range(4):
        frames += [scene()] * 2 + [scene(hidden=True)]
    frames += [scene()] * 3
    rows = replay(frames)
    starts = [
        (r["frame_index"], r["segment_id"]) for r in rows if r["reason"] == "reacquired_continuity"
    ]
    assert starts == [(5, 2), (8, 3), (11, 4)]
    assert rows[12]["state"] == "lost" and rows[12]["reason"] == "reacquire_limit"
    assert rows[12]["segment_end_reason"] == "low_texture" and rows[12]["reacquisitions"] == 3
    assert all(r["state"] == "lost" for r in rows[13:])
    rows = replay(frames, reacquire=ReacquireParams(max_reacquisitions=4))
    assert rows[14]["state"] == "tracking" and rows[14]["segment_id"] == 5


def test_no_loss_matches_the_plain_tracker_exactly():
    frames = [scene(60 + i * 2, 60 + i, bright=i) for i in range(6)]
    plain = PatchTracker(origin=(330, 100))
    expected = [
        step(plain, image, i, seed=[390, 160] if i == 0 else None) for i, image in enumerate(frames)
    ]
    rows = replay(frames)
    keys = ("pitch_id", "frame_index", "frame_seconds", "state", "reason", "point_px", "quality")
    assert [{k: r[k] for k in keys} for r in rows] == [{k: r[k] for k in keys} for r in expected]
    assert all(r["segment_id"] == 1 and r["reacquisitions"] == 0 for r in rows)


def test_future_frames_never_change_earlier_outputs():
    frames = [scene()] * 3 + [scene(hidden=True)] + [scene(62, 61)] * 3 + [scene(hidden=True)] * 6
    full = replay(frames)
    for cut in (4, 5, 8, 10):
        assert replay(frames[:cut]) == full[:cut]


def test_seed_rejection_and_reseed_rules_follow_the_plain_tracker():
    tracker = ReacquiringTracker()
    row = step(tracker, np.zeros((140, 160), np.uint8), 0, seed=[60, 60])
    assert (row["state"], row["reason"], row["segment_end_reason"]) == (
        "lost",
        "seed_low_texture",
        None,
    )
    assert step(tracker, scene(), 1)["state"] == "lost"
    tracker = ReacquiringTracker()
    assert step(tracker, scene(), 0)["state"] == "unseeded"
    assert step(tracker, scene(), 1, usable=False)["reason"] == "external_view_gate"
    step(tracker, scene(), 2, seed=[60, 60])
    with pytest.raises(ValueError, match="reseed"):
        step(tracker, scene(), 3, seed=[60, 60])


def test_input_format_errors_are_rejected_in_every_state():
    tracker = ReacquiringTracker()
    step(tracker, scene(), 0, seed=[60, 60])
    assert step(tracker, scene(hidden=True), 1)["state"] == "reacquire_search"
    with pytest.raises(ValueError, match="pitch_id"):
        tracker.step(scene(), pitch_id="", frame_index=2, frame_seconds=0.1)
    with pytest.raises(ValueError, match="cross"):
        tracker.step(scene(), pitch_id="other", frame_index=2, frame_seconds=0.1)
    with pytest.raises(ValueError, match="frame_index"):
        tracker.step(scene(), pitch_id="747139:3:1", frame_index=2.0, frame_seconds=0.1)
    with pytest.raises(ValueError, match="increase"):
        step(tracker, scene(), 1)
    with pytest.raises(ValueError, match="frame_seconds"):
        tracker.step(scene(), pitch_id="747139:3:1", frame_index=2, frame_seconds=float("nan"))
    with pytest.raises(ValueError, match="uint8"):
        step(tracker, scene().astype(np.float32), 2)
    with pytest.raises(ValueError, match="shape"):
        step(tracker, scene()[:-1], 2)
    assert step(tracker, scene(hidden=True), 2)["state"] == "reacquire_search"


def test_params_are_validated_and_digested():
    with pytest.raises(ValueError):
        ReacquireParams(max_attempt_frames=0)
    with pytest.raises(ValueError):
        ReacquireParams(search_radius=True)
    with pytest.raises(ValueError, match="peak exclusion"):
        ReacquiringTracker(reacquire=ReacquireParams(search_radius=3))
    with pytest.raises(ValueError, match="ReacquireParams"):
        ReacquiringTracker(reacquire={"search_radius": 32})
    assert ReacquireParams().digest() == ReacquireParams(max_attempt_frames=5).digest()
    assert ReacquireParams().digest() != ReacquireParams(search_radius=24).digest()


def test_match_template_is_the_plain_tracker_matcher():
    params = TrackParams()
    image = torch.as_tensor(scene(66, 63)).float()[None, None] / 255.0
    template = torch.as_tensor(scene()).float()[None, None][..., 50:71, 50:71] / 255.0
    point, evidence = match_template(image, template, (60, 60), params)
    assert point == (66, 63) and evidence["ncc"] == pytest.approx(1.0, abs=1e-4)
    assert match_template(image, template, (60, 60), TrackParams(search_radius=5))[0] is None


def stationary_rows():
    frames = [scene()] * 7 + [scene(hidden=True)] + [scene()] * 9
    return replay(frames)


def test_segmented_selector_requalifies_and_keeps_past_events():
    selector = SegmentedStationarySelector()
    out = [selector.step(row) for row in stationary_rows()]
    states = [(o["tracker_state"], o["selection_state"]) for o in out]
    assert states[5:11] == [
        ("tracking", "warming"),
        ("tracking", "stationary"),
        ("reacquire_search", "unavailable"),
        ("reacquire_candidate", "unavailable"),
        ("tracking", "warming"),
        ("tracking", "warming"),
    ]
    assert states[-1] == ("tracking", "stationary")
    first = next(o for o in out if o["event"] is not None)
    second = next(o for o in out if o["event"] is not None and o["segment_id"] == 2)
    assert first["event"]["segment_id"] == 1 and first["frame_index"] == 6
    assert second["event"]["segment_id"] == 2
    assert second["event"]["segment_start_frame"] == 9 and second["frame_index"] >= 15
    assert all(o["current_candidate"] is None for o in out[7 : second["frame_index"]])
    assert all(
        o["last_historical_candidate"] == first["event"] for o in out[6 : second["frame_index"]]
    )
    assert out[-1]["last_historical_candidate"] == second["event"]
    assert [o["events_total"] for o in out] == sorted(o["events_total"] for o in out)
    assert out[-1]["events_total"] == 2
    assert all(o["current_track_point_px"] is None for o in out[7:9])
    assert out[8]["reason"] == "reacquire_candidate"
    assert all(o["mitt_identity"] == "unverified" for o in out)


def test_segmented_selector_rejects_stale_points_and_implicit_segments():
    rows = stationary_rows()
    selector = SegmentedStationarySelector()
    for row in rows[:7]:
        selector.step(row)
    with pytest.raises(ValueError, match="point or segment"):
        selector.step({**rows[7], "point_px": [390, 160]})
    with pytest.raises(ValueError, match="candidate point"):
        selector.step({**rows[7], "reacquire_candidate_px": [390, 160]})
    selector.step(rows[7])
    with pytest.raises(ValueError, match="started segment"):
        selector.step({**rows[9], "reason": "patch_continuity"})
    with pytest.raises(ValueError, match="new segment id"):
        selector.step({**rows[9], "segment_id": 1})
    with pytest.raises(ValueError, match="mitt identity"):
        selector.step({**rows[9], "mitt_identity": "verified"})
    with pytest.raises(ValueError, match="missing"):
        selector.step({k: v for k, v in rows[9].items() if k != "segment_end_reason"})
    with pytest.raises(ValueError, match="increase"):
        selector.step({**rows[9], "frame_index": 7})
    with pytest.raises(ValueError, match="params"):
        SegmentedStationarySelector(params={"max_diameter_px": 8})
    assert SegmentedStationarySelector(StationaryParams()).params == StationaryParams()


def test_cut_between_two_search_frames_is_refused_even_when_each_is_near_the_anchor():
    """Review case: opposite brightness swings stay within the anchor threshold but not the
    consecutive-frame threshold; the window must close like PatchTracker would."""
    params = TrackParams(max_appearance_change=0.15)
    tracker = ReacquiringTracker(params=params)
    step(tracker, scene(bright=98), 0, seed=[60, 60])
    assert step(tracker, np.full((140, 160), 102, np.uint8), 1)["state"] == "reacquire_search"
    row = step(tracker, scene(bright=124), 2)
    assert (row["state"], row["reason"]) == ("lost", "reacquire_appearance_discontinuity")
    assert row["quality"]["anchor_appearance_change"] < 0.15 < row["quality"]["appearance_change"]
    assert step(tracker, scene(bright=124), 3)["state"] == "lost"


def test_confirmation_frame_after_the_last_search_frame_is_not_counted_as_a_search():
    rows = replay(
        [scene(), scene(hidden=True), scene(), scene(hidden=True), scene(hidden=True)],
        reacquire=ReacquireParams(max_attempt_frames=2),
    )
    assert summary(rows)[1:] == [
        ("reacquire_search", "reacquire_low_texture", None, None, None),
        ("reacquire_candidate", "reacquire_candidate", None, [390, 160], None),
        ("lost", "reacquire_exhausted", None, None, None),
        ("lost", "reacquire_exhausted", None, None, None),
    ]
    assert [r["quality"].get("reacquire_attempt") for r in rows[1:4]] == [1, 2, 2]
    assert [bool(r["quality"].get("reacquire_searched")) for r in rows[1:4]] == [True, True, False]
    assert rows[3]["quality"]["last_attempt_reason"] == "reacquire_candidate_low_texture"


def test_segmented_selector_rejects_malformed_candidate_points_in_every_state():
    rows = stationary_rows()
    for bad in ([-1, 160], [], [float("nan"), 160], "390,160"):
        selector = SegmentedStationarySelector()
        for row in rows[:7]:
            selector.step(row)
        with pytest.raises(ValueError, match="candidate"):
            selector.step({**rows[7], "reacquire_candidate_px": bad})
        selector.step(rows[7])
        with pytest.raises(ValueError, match="candidate"):
            selector.step({**rows[8], "reacquire_candidate_px": bad})

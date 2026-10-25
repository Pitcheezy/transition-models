"""Causal geometric candidates must never masquerade as a lost current observation."""

import copy
import inspect
from dataclasses import FrozenInstanceError

import pytest

from intent.mitt_stationary import StationaryParams, StationarySelector


def row(i, *, t=None, point=(600.0, 300.0), state="tracking", reason=None, **changes):
    if reason is None:
        reason = {
            "tracking": "external_seed" if i == 0 else "patch_continuity",
            "unseeded": "no_seed",
            "lost": "low_similarity",
        }[state]
    return {
        "pitch_id": "747139:3:1",
        "frame_index": i,
        "frame_seconds": i / 10 if t is None else t,
        "state": state,
        "reason": reason,
        "point_px": list(point) if point is not None else None,
        "mitt_identity": "unverified",
        **changes,
    }


def run(rows, *, params=None):
    selector = StationarySelector(params)
    return [selector.step(item) for item in rows]


def test_seed_is_not_a_candidate_and_first_event_requires_observed_time_and_count():
    rows = [row(i, t=t) for i, t in enumerate([0.0, 0.15, 0.30, 0.31])]
    result = run(rows)
    assert all(item["current_candidate"] is None for item in result[:3])
    assert all(item["event"] is None for item in result[:3])
    candidate = result[-1]["event"]
    assert candidate is not None
    assert candidate["observations"] == 4
    assert candidate["continuity_observations"] == 3
    assert candidate["span_seconds"] == pytest.approx(0.31)
    assert candidate["segment_start_frame"] == 0
    assert candidate["available_frame"] == 3
    assert candidate["available_seconds"] == pytest.approx(0.31)
    # Enough observations without enough elapsed time must also abstain.
    assert run([row(i, t=i / 100) for i in range(10)])[-1]["current_candidate"] is None


def test_current_candidate_updates_but_first_event_and_history_stay_frozen():
    rows = [row(i, point=(600 + i, 300)) for i in range(6)]
    result = run(rows)
    first = result[3]["event"]
    assert first is not None
    assert [item["event"] is not None for item in result] == [False] * 3 + [True, False, False]
    assert first["point_px"] == [603.0, 300.0]
    current = result[5]["current_candidate"]
    assert current["point_px"] == [605.0, 300.0]
    assert current["frame_index"] == 5
    assert current["frame_seconds"] == pytest.approx(0.5)
    assert current["candidate_id"] == first["candidate_id"]
    assert current["available_frame"] == 3
    assert result[5]["last_historical_candidate"] == first
    assert result[5]["current_track_point_px"] == [605.0, 300.0]


@pytest.mark.parametrize("failure", ["lost", "gate", "gap", "motion"])
def test_interruption_clears_current_on_that_row_but_keeps_historical_event(failure):
    selector = StationarySelector()
    initial = [selector.step(row(i)) for i in range(4)]
    first = copy.deepcopy(initial[-1]["event"])
    kwargs = {}
    next_row = row(4)
    if failure == "lost":
        next_row = row(4, state="lost", point=None)
    elif failure == "gate":
        kwargs["usable"] = False
    elif failure == "gap":
        next_row = row(4, t=0.56)
    else:
        next_row = row(4, point=(609, 300))
    result = selector.step(next_row, **kwargs)
    assert result["current_candidate"] is None
    assert result["event"] is None
    assert result["last_historical_candidate"] == first
    assert result["selection_state"] != "stationary"
    if failure in {"lost", "gate"}:
        assert result["current_track_point_px"] is None
    else:
        assert result["current_track_point_px"] == next_row["point_px"]


def test_gated_row_does_not_contribute_to_a_later_candidate():
    selector = StationarySelector()
    for i in range(4):
        before = selector.step(row(i))
    historical = copy.deepcopy(before["event"])
    selector.step(row(4), usable=False)
    after = [selector.step(row(i)) for i in range(5, 9)]
    assert all(item["current_candidate"] is None for item in after[:3])
    assert after[0]["last_historical_candidate"] == historical
    event = after[-1]["event"]
    assert event["segment_start_frame"] == 5
    assert event["observations"] == 4
    assert event["continuity_observations"] == 4
    assert event["candidate_id"] != historical["candidate_id"]


def test_motion_starts_a_new_segment_without_reusing_old_support():
    result = run([row(i) for i in range(4)] + [row(i, point=(620, 300)) for i in range(4, 8)])
    assert all(item["current_candidate"] is None for item in result[4:7])
    assert result[7]["event"]["segment_start_frame"] == 4
    assert result[7]["event"]["available_frame"] == 7
    assert result[7]["event"]["observations"] == 4


def test_cumulative_drift_and_opposite_side_oscillation_cannot_pass_as_stationary():
    drift = run([row(i, point=(600 + 3 * i, 300)) for i in range(12)])
    assert all(item["event"] is None for item in drift)
    # Each point is within 8 px of the first, but the whole segment spans 16 px.
    oscillation = run([row(i, point=(x, 300)) for i, x in enumerate([600, 608, 592, 608, 592])])
    assert all(item["event"] is None for item in oscillation)


@pytest.mark.parametrize(
    "dx,dy,qualifies", [(8.0, 0.0, True), (8.0001, 0.0, False), (6.0, 6.0, False)]
)
def test_entire_bounding_box_diagonal_not_axis_wise_or_anchor_radius(dx, dy, qualifies):
    points = [(600, 300), (600 + dx, 300), (600, 300 + dy), (600 + dx, 300 + dy)]
    result = run([row(i, point=point) for i, point in enumerate(points)])
    assert (result[-1]["event"] is not None) is qualifies
    if qualifies:
        assert result[-1]["event"]["diameter_px"] == pytest.approx(8.0)


@pytest.mark.parametrize("last,qualifies", [(0.2999, False), (0.30, True), (0.3001, True)])
def test_hold_duration_boundary(last, qualifies):
    result = run([row(i, t=t) for i, t in enumerate([0.0, 0.1, 0.2, last])])
    assert (result[-1]["event"] is not None) is qualifies


@pytest.mark.parametrize("last,qualifies", [(0.45, True), (0.4501, False)])
def test_time_gap_boundary(last, qualifies):
    result = run([row(i, t=t) for i, t in enumerate([0.0, 0.1, 0.2, last])])
    assert (result[-1]["event"] is not None) is qualifies


def test_prefix_invariance_across_all_segment_boundaries_and_no_outcome_argument():
    rows = [row(0, state="unseeded", point=None)]
    rows += [row(1, reason="external_seed")]
    rows += [row(i) for i in range(2, 6)]
    rows += [row(i, point=(620, 300)) for i in range(6, 10)]
    rows += [row(i, state="lost", point=None) for i in range(10, 13)]
    original = copy.deepcopy(rows)
    full = run(rows)
    for end in range(len(rows) + 1):
        assert run(rows[:end]) == full[:end]
    assert rows == original
    assert list(inspect.signature(StationarySelector.step).parameters) == ["self", "row", "usable"]
    assert all(item["current_candidate"] is None for item in full[10:])


@pytest.mark.parametrize(
    "change",
    [
        {"pitch_id": "another-pitch"},
        {"pitch_id": ""},
        {"pitch_id": 1},
        {"frame_index": True},
        {"frame_index": -1},
        {"frame_index": 2},
        {"frame_index": 3.0},
        {"frame_seconds": 0.2},
        {"frame_seconds": -1},
        {"frame_seconds": True},
        {"frame_seconds": float("nan")},
        {"frame_seconds": float("inf")},
        {"point_px": None},
        {"point_px": [600, float("nan")]},
        {"point_px": [600, float("inf")]},
        {"point_px": [600, True]},
        {"point_px": [600, -1]},
        {"point_px": [600]},
        {"point_px": "600,300"},
        {"state": "unknown"},
        {"reason": ""},
        {"reason": "external_view_gate"},
        {"reason": "external_seed"},
        {"mitt_identity": "verified"},
    ],
)
def test_bad_record_is_rejected_atomically_and_corrected_same_frame_can_be_processed(change):
    selector = StationarySelector()
    for i in range(3):
        selector.step(row(i))
    bad = {**row(3), **change}
    with pytest.raises(ValueError):
        selector.step(bad)
    assert selector.step(row(3)) == run([row(i) for i in range(4)])[-1]


def test_missing_fields_and_invalid_gate_do_not_consume_a_frame():
    for field in row(0):
        selector = StationarySelector()
        bad = row(0)
        del bad[field]
        with pytest.raises(ValueError):
            selector.step(bad)
        assert selector.step(row(0)) == run([row(0)])[0]
    selector = StationarySelector()
    with pytest.raises(ValueError):
        selector.step(row(0), usable="false")
    assert selector.step(row(0)) == run([row(0)])[0]


@pytest.mark.parametrize(
    "bad",
    [
        row(0, reason="patch_continuity"),
        row(0, state="unseeded", point=(600, 300)),
        row(0, state="unseeded", point=None, reason="low_similarity"),
        row(0, state="lost", point=(600, 300)),
        row(0, state="lost", point=None, reason="patch_continuity"),
        row(0, state="lost", point=None, reason="external_seed"),
    ],
)
def test_inconsistent_initial_state_or_point_is_rejected(bad):
    with pytest.raises(ValueError):
        StationarySelector().step(bad)


def test_lost_is_terminal_and_tracking_cannot_return_to_unseeded():
    selector = StationarySelector()
    selector.step(row(0))
    with pytest.raises(ValueError):
        selector.step(row(1, state="unseeded", point=None))
    selector.step(row(1, state="lost", point=None))
    for bad in [row(2), row(2, reason="external_seed"), row(2, state="unseeded", point=None)]:
        with pytest.raises(ValueError):
            selector.step(bad)
    assert selector.step(row(2, state="lost", point=None))["current_candidate"] is None


def test_input_and_output_mutations_cannot_rewrite_selector_history():
    selector = StationarySelector()
    seed = row(0)
    seed_result = selector.step(seed)
    seed["point_px"][0] = 9999
    seed_result["current_track_point_px"][0] = 8888
    for i in range(1, 4):
        result = selector.step(row(i))
    historical = copy.deepcopy(result["event"])
    result["event"]["point_px"][0] = 7777
    result["current_candidate"]["point_px"][0] = 6666
    result["last_historical_candidate"]["point_px"][0] = 5555
    following = selector.step(row(4))
    assert following["current_candidate"]["point_px"] == [600.0, 300.0]
    assert following["last_historical_candidate"] == historical


@pytest.mark.parametrize(
    "params",
    [
        {"max_diameter_px": 0},
        {"max_diameter_px": float("inf")},
        {"max_diameter_px": True},
        {"min_hold_seconds": -1},
        {"min_hold_seconds": float("nan")},
        {"max_gap_seconds": 0},
        {"max_gap_seconds": "0.25"},
        {"min_observations": 1},
        {"min_observations": True},
        {"min_observations": 4.0},
        {"min_continuity": 0},
        {"min_continuity": True},
        {"min_continuity": 2.0},
        {"min_continuity": 4},
    ],
)
def test_bad_parameters_are_rejected(params):
    with pytest.raises(ValueError):
        StationaryParams(**params)


def test_parameters_are_immutable():
    params = StationaryParams()
    with pytest.raises(FrozenInstanceError):
        params.min_hold_seconds = 0.01


def test_selector_parameters_cannot_be_rebound_with_an_old_digest():
    selector = StationarySelector()
    digest = selector.params.digest()
    with pytest.raises(AttributeError):
        selector.params = StationaryParams(max_diameter_px=999)
    assert selector.params.digest() == digest

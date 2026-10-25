"""CV-33 temporal candidate: layer separation, causality (prefix invariance) and conversion limits."""

import inspect

import pytest

from intent import mitt_temporal as mt

STEP = 0.1


def obs(
    i,
    centre=(600.0, 300.0),
    *,
    view="live_centre_field",
    catcher="set",
    vis="full",
    phase="before_delivery",
    plate=None,
    occluder=None,
):
    return {
        "pitch_id": "747139:3:1",
        "frame_index": 1000 + 6 * i,
        "frame_seconds": round(10.0 + STEP * i, 4),
        "view": view,
        "catcher": catcher,
        "mitt_visibility": vis,
        "occluder": occluder,
        "mitt_center_px": None if centre is None else list(centre),
        "pitcher_phase": phase,
        **({"plate_front": plate} if plate else {}),
    }


def sequence():
    """Not set -> raise -> held 0.5 s -> delivery with the mitt lowered -> hidden -> release."""
    s = [obs(0, None, catcher="not_set", vis="unknown"), obs(1, (600, 330)), obs(2, (601, 315))]
    s += [obs(i, (602 + (i % 2), 300 + (i % 3))) for i in range(3, 9)]
    s += [obs(9, (604, 318), phase="delivery"), obs(10, (606, 340), phase="delivery")]
    s += [
        obs(11, None, vis="hidden", occluder="batter", phase="delivery"),
        obs(12, (610, 345), phase="after_release"),
    ]
    return s


def test_prefix_invariance_later_frames_never_change_earlier_records():
    full = mt.run(sequence())
    for k in range(len(sequence()) + 1):
        assert mt.run(sequence()[:k]) == full[:k]


def test_selector_cannot_receive_release_or_outcome():
    assert list(inspect.signature(mt.run).parameters) == ["observations", "params"]


def test_held_segment_emits_one_candidate_at_the_moment_the_hold_is_long_enough():
    records = mt.run(sequence())
    events = [r["event"] for r in records if r["event"]]
    assert len(events) == 1
    event = events[0]
    assert event["segment_start_frame"] == 1000 + 6 * 3
    # emitted once min_hold_seconds (0.3 s) of the held segment has been observed, not later
    assert event["emitted_seconds"] == pytest.approx(10.0 + STEP * 6)
    assert event["spread_px"] <= mt.PARAMS_DEV_V1["hold_radius_px"]
    states = [r["state"] for r in records]
    assert states[0] == "unclear:catcher_not_set"
    assert states[2] == "raising"
    assert states[10] == "lowering"
    assert states[11] == "unclear:mitt_hidden"


def test_before_delivery_and_before_release_are_separate_cutoffs():
    summary = mt.summarize_pitch(sequence(), release_seconds=10.0 + STEP * 11.5)
    assert summary["delivery_start_seconds"] == pytest.approx(10.9)
    assert summary["delivery_start_source"] == "layer_a_pitcher_phase"
    annotated = mt.summarize_pitch(sequence(), delivery_start_seconds=10.55)
    assert annotated["delivery_start_source"] == "posthoc_annotation"
    assert annotated["candidate_before_delivery_start"] is None
    assert summary["candidate_before_delivery_start"]["emitted_seconds"] == pytest.approx(10.6)
    assert summary["candidate_before_release"] == summary["candidate_before_delivery_start"]
    early = mt.summarize_pitch(sequence(), release_seconds=10.55)
    assert early["candidate_before_release"] is None
    assert early["undeterminable_reason"] == "no_held_segment_reached_min_hold"


def test_layer_a_rejects_target_or_resting_judgements_and_bad_values():
    with pytest.raises(ValueError):
        mt.validate_observation({**obs(0), "resting": True})
    with pytest.raises(ValueError):
        mt.validate_observation(obs(0, vis="hidden"))  # centre without visibility
    with pytest.raises(ValueError):
        mt.validate_observation({**obs(0), "view": "live"})
    with pytest.raises(ValueError):
        mt.run([obs(1), obs(0)])


def test_a_gap_or_cut_breaks_the_segment():
    s = (
        [obs(i, (600, 300)) for i in range(3)]
        + [obs(6, (600, 300))]
        + [obs(i, (600, 300)) for i in range(7, 9)]
    )
    records = mt.run(s)
    assert records[2]["event"] is None or records[2]["event"]["segment_start_frame"] == 1000
    assert records[3]["state"].endswith("|after_gap")
    cut = [obs(0), obs(1), obs(2, view="other_view", vis="unknown", centre=None), obs(3), obs(4)]
    assert all(r["event"] is None for r in mt.run(cut))


def test_conversion_uses_only_a_plate_edge_in_the_same_live_run_before_the_candidate():
    plate = {"left_end": [560.0, 360.0], "right_end": [640.0, 360.0]}
    s = sequence()
    s[1] = {**s[1], "plate_front": plate}
    summary = mt.summarize_pitch(s)
    conv = summary["conversion_before_delivery_start"]
    assert conv["status"] == "front_edge_units" and conv["plate_frame"] == s[1]["frame_index"]
    assert 0.0 < conv["uv"][0] < 1.0 and conv["uv"][1] > 0
    assert "feet" in conv["not_claimed"]
    late = sequence()
    late[10] = {**late[10], "plate_front": plate}  # after the candidate: not usable
    assert mt.summarize_pitch(late)["conversion_before_delivery_start"]["status"] == "pixels_only"


def test_params_are_hashed_for_freezing():
    other = {**mt.PARAMS_DEV_V1, "hold_radius_px": 9.0}
    assert mt.params_sha256(mt.PARAMS_DEV_V1) != mt.params_sha256(other)
    assert mt.params_sha256(dict(reversed(list(mt.PARAMS_DEV_V1.items())))) == mt.params_sha256(
        mt.PARAMS_DEV_V1
    )


def test_abstention_reason_uses_only_frames_before_each_cutoff():
    not_set = [obs(i, None, catcher="not_set", vis="unknown") for i in range(5)]
    alone = mt.summarize_pitch(not_set, release_seconds=10.45)
    assert alone["undeterminable_before_release"] == "no_usable_frame:catcher_not_set"
    later = not_set + [obs(i, (600, 300)) for i in range(5, 9)]
    extended = mt.summarize_pitch(later, release_seconds=10.45)
    assert extended["undeterminable_before_release"] == "no_usable_frame:catcher_not_set"
    # a candidate exists before release but not before an earlier delivery start
    split = mt.summarize_pitch(sequence(), release_seconds=11.25, delivery_start_seconds=10.55)
    assert split["candidate_before_release"] is not None
    assert split["candidate_before_delivery_start"] is None
    assert split["undeterminable_before_delivery_start"] == "no_held_segment_reached_min_hold"
    assert split["undeterminable_before_release"] is None
    assert mt.why_none_before([], None) == "no_cutoff"


def test_holds_that_start_after_an_unusable_frame_or_at_the_first_frame_are_left_censored():
    first = mt.run([obs(i, (600, 300)) for i in range(4)])
    assert [r["event"]["left_censored"] for r in first if r["event"]] == [True]
    moved = mt.run([obs(0, (560, 300))] + [obs(i, (600, 300 + i % 2)) for i in range(1, 5)])
    assert [r["event"]["left_censored"] for r in moved if r["event"]] == [False]
    hidden = mt.run(
        [obs(0, (560, 300)), obs(1, None, vis="hidden")] + [obs(i, (600, 300)) for i in range(2, 6)]
    )
    assert [r["event"]["left_censored"] for r in hidden if r["event"]] == [True]

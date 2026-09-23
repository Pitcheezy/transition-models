"""The tracker holds confirmed values through abstentions, ages them, and never invents."""

import pytest

from src.vision.state_tracker import FIELDS, ScoreboardTracker, track_sequence

READ = {
    "balls": 1,
    "strikes": 2,
    "outs": 1,
    "runner_on_1b": True,
    "runner_on_2b": False,
    "runner_on_3b": False,
    "inning": 3,
    "inning_topbot": "Bot",
    "home_score": 2,
    "away_score": 0,
}


def blank():
    return dict.fromkeys(FIELDS)


def test_holds_values_through_abstention_and_ages_them():
    tracker = ScoreboardTracker(stale_after_seconds=10.0)
    first = tracker.update(100.0, blank())
    assert not first["any_confirmed"] and all(f["stale"] for f in first["fields"].values())
    assert all(f["value"] is None for f in first["fields"].values())
    state = tracker.update(101.0, READ)
    assert state["all_fresh"] and state["fields"]["balls"] == {
        "value": 1,
        "confirmed_at": 101.0,
        "age_seconds": 0.0,
        "stale": False,
    }
    held = tracker.update(106.0, blank())  # graphic: nothing readable
    assert held["fields"]["balls"]["value"] == 1
    assert held["fields"]["balls"]["age_seconds"] == 5.0 and not held["fields"]["balls"]["stale"]
    stale = tracker.update(112.0, blank())
    assert stale["fields"]["balls"]["value"] == 1 and stale["fields"]["balls"]["stale"]
    assert not stale["all_fresh"]
    partial = tracker.update(113.0, {**blank(), "inning": 3, "inning_topbot": "Bot"})
    assert (
        partial["fields"]["inning"]["age_seconds"] == 0.0
        and not partial["fields"]["inning"]["stale"]
    )
    assert partial["fields"]["balls"]["stale"]


def test_rejects_impossible_values_and_flags_backward_transitions():
    tracker = ScoreboardTracker()
    tracker.update(10.0, READ)
    state = tracker.update(11.0, {**blank(), "balls": 4, "strikes": "2", "inning_topbot": "Mid"})
    assert state["fields"]["balls"]["value"] == 1 and state["fields"]["strikes"]["value"] == 2
    assert [r["field"] for r in tracker.rejected] == ["balls", "strikes", "inning_topbot"]
    tracker.update(12.0, {**blank(), "inning": 2, "home_score": 1})
    reasons = sorted(s["reason"] for s in tracker.suspect)
    assert reasons == ["home_score_decreased", "inning_decreased"]
    # the new reading is still held (the earlier reading may have been the wrong one)
    assert tracker.values["inning"] == 2 and tracker.values["home_score"] == 1
    with pytest.raises(ValueError):
        tracker.update(5.0, READ)


def test_track_sequence_orders_by_time_and_reports_logs():
    result = track_sequence([(20.0, blank()), (10.0, READ), (15.0, {**blank(), "balls": 9})])
    assert [s["seconds"] for s in result["states"]] == [10.0, 15.0, 20.0]
    assert result["states"][-1]["fields"]["balls"]["value"] == 1
    assert result["rejected"] == [{"seconds": 15.0, "field": "balls", "value": 9}]
    assert result["suspect"] == []

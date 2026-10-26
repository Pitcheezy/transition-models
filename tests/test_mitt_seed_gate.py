"""The frozen seed gate has causal support, strict keys, and no identity guarantee."""

import copy
import hashlib
import json

import pytest

from intent.mitt_seed_gate import POLICY, POLICY_SHA256, SeedGate


def observation(index, seconds, *, pitch="747139:3:1", point=None, **changes):
    return {
        "pitch_id": pitch,
        "frame_index": index,
        "frame_seconds": seconds,
        "view": "live_centre_field",
        "catcher": "set",
        "mitt_visibility": "full",
        "occluder": None,
        "mitt_center_px": [600, 300] if point is None else point,
        "pitcher_phase": "before_delivery",
        "uncertainty_px": 8,
        **changes,
    }


def step(gate, index, seconds, **changes):
    obs = observation(index, seconds, **changes)
    return gate.update(obs["pitch_id"], index, seconds, obs)


def test_emits_current_point_once_and_freezes_support_after_seeding():
    gate = SeedGate()
    assert step(gate, 0, 0)["seed"] is None
    assert step(gate, 2, 0.2, point=[601, 301])["seed"] is None
    accepted = step(gate, 4, 0.4, point=[602, 302])
    assert accepted["state"] == "seeded"
    assert accepted["seed"] == {
        "frame_index": 4,
        "frame_seconds": 0.4,
        "point_px": [602, 302],
        "support_keys": accepted["support_keys"],
    }
    assert [key["frame_index"] for key in accepted["support_keys"]] == [0, 2, 4]
    after = step(gate, 6, 0.6, point=[700, 400], view="other_view")
    assert after["state"] == "seeded" and after["reason"] == "already_seeded"
    assert after["seed"] is None and after["support_keys"] == accepted["support_keys"]
    assert accepted["mitt_identity"] == after["mitt_identity"] == "unverified"


def test_missing_frames_never_add_support_or_seed_and_only_expire_a_gap():
    gate = SeedGate()
    step(gate, 0, 0)
    first_missing = gate.update("747139:3:1", 1, 0.1)
    assert first_missing["state"] == "collecting" and len(first_missing["support_keys"]) == 1
    step(gate, 2, 0.2)
    no_seed = gate.update("747139:3:1", 3, 0.35)
    assert no_seed["seed"] is None and len(no_seed["support_keys"]) == 2
    expired = gate.update("747139:3:1", 4, 0.451)
    assert expired["state"] == "waiting" and expired["reason"] == "gap_expired"
    assert expired["support_keys"] == []
    assert step(gate, 5, 0.5)["support_keys"] == [
        {
            "pitch_id": "747139:3:1",
            "frame_index": 5,
            "frame_seconds": 0.5,
        }
    ]


def test_observed_gap_restarts_at_current_point_not_the_old_support():
    gate = SeedGate()
    step(gate, 0, 0)
    gap = step(gate, 1, 0.251)
    assert gap["reason"] == "gap_restart" and gap["seed"] is None
    assert [k["frame_index"] for k in gap["support_keys"]] == [1]
    step(gate, 2, 0.451)
    assert step(gate, 3, 0.651)["seed"]["frame_index"] == 3


def test_cumulative_slow_drift_cannot_pass_small_per_step_displacements():
    gate = SeedGate()
    step(gate, 0, 0, point=[600, 300])
    step(gate, 1, 0.2, point=[605, 300])
    moved = step(gate, 2, 0.4, point=[610, 300])
    assert moved["seed"] is None and moved["reason"] == "movement_restart"
    assert [k["frame_index"] for k in moved["support_keys"]] == [2]


def test_diameter_uses_the_whole_bounding_box_and_time_threshold_is_inclusive():
    gate = SeedGate()
    step(gate, 0, 1000, point=[600, 300])
    step(gate, 1, 1000.15, point=[608, 300])
    accepted = step(gate, 2, 1000.3, point=[608, 300])
    assert accepted["seed"] is not None
    gate = SeedGate()
    step(gate, 0, 0, point=[600, 300])
    step(gate, 1, 0.2, point=[606, 300])
    assert step(gate, 2, 0.4, point=[606, 306])["reason"] == "movement_restart"


@pytest.mark.parametrize(
    ("change", "reason"),
    [
        ({"view": "graphic_or_transition"}, "view_not_live_centre_field"),
        ({"catcher": "unknown"}, "catcher_not_set"),
        ({"mitt_visibility": "partial"}, "mitt_not_full"),
        ({"occluder": "catcher_body"}, "occluded"),
        ({"pitcher_phase": "delivery"}, "pitcher_not_before_delivery"),
        ({"mitt_center_px": None}, "no_centre"),
        ({"uncertainty_px": None}, "uncertainty_unavailable"),
        ({"uncertainty_px": 10.001}, "uncertainty_exceeds_limit"),
    ],
)
def test_ineligible_observation_clears_support(change, reason):
    gate = SeedGate()
    step(gate, 0, 0)
    rejected = step(gate, 1, 0.2, **change)
    assert rejected["reason"] == reason
    assert rejected["state"] == "waiting" and rejected["support_keys"] == []
    assert step(gate, 2, 0.4)["seed"] is None


@pytest.mark.parametrize("bad", [True, float("nan"), float("inf"), 10**400, -1])
def test_bad_uncertainty_is_rejected_before_state_changes(bad):
    gate = SeedGate()
    step(gate, 0, 0)
    with pytest.raises(ValueError):
        step(gate, 1, 0.2, uncertainty_px=bad)
    assert len(step(gate, 1, 0.2)["support_keys"]) == 2


@pytest.mark.parametrize(
    "point",
    [
        [True, 300],
        [float("nan"), 300],
        [10**400, 300],
        [-1, 300],
        [1280, 300],
        [600, 720],
        [600],
        "600,300",
    ],
)
def test_malformed_or_out_of_image_points_are_rejected(point):
    with pytest.raises(ValueError):
        step(SeedGate(), 0, 0, point=point)


@pytest.mark.parametrize(
    ("pitch", "index", "seconds"),
    [
        (True, 0, 0),
        ("", 0, 0),
        ("p", True, 0),
        ("p", 10**400, 0),
        ("p", -1, 0),
        ("p", 0, True),
        ("p", 0, float("nan")),
        ("p", 0, 10**400),
    ],
)
def test_malformed_frame_keys_are_rejected_even_without_observations(pitch, index, seconds):
    with pytest.raises(ValueError):
        SeedGate().update(pitch, index, seconds)


def test_exact_observation_key_no_future_fields_and_unchanged_on_validation_failure():
    gate = SeedGate()
    step(gate, 0, 0)
    bad = observation(2, 0.4)
    with pytest.raises(ValueError, match="exact current frame"):
        gate.update("747139:3:1", 1, 0.2, bad)
    with pytest.raises(ValueError, match="fields"):
        step(gate, 1, 0.2, release_seconds=1)
    assert len(step(gate, 1, 0.2)["support_keys"]) == 2


def test_new_pitch_resets_and_reentry_or_reverse_order_fails():
    gate = SeedGate()
    step(gate, 0, 0)
    step(gate, 1, 0.2)
    with pytest.raises(ValueError, match="increase"):
        step(gate, 1, 0.3)
    new = step(gate, 0, 0, pitch="747139:3:2")
    assert new["seed"] is None and len(new["support_keys"]) == 1
    with pytest.raises(ValueError, match="re-entered"):
        step(gate, 2, 0.4)


def test_each_prefix_recomputes_its_own_seed_and_future_changes_do_not_leak():
    stream = [observation(i, i * 0.2) for i in range(6)]

    def run(items):
        gate = SeedGate()
        return [gate.update(r["pitch_id"], r["frame_index"], r["frame_seconds"], r) for r in items]

    expected = run(stream)
    for length in range(1, len(stream) + 1):
        assert run(stream[:length]) == expected[:length]
    changed = copy.deepcopy(stream)
    changed[2]["view"] = "other_view"
    assert run(changed)[:2] == expected[:2]
    assert all(r["seed"] is None for r in run(stream[:2]))


def test_stable_wrong_object_can_pass_but_never_gains_verified_identity():
    gate = SeedGate()
    # The synthetic point represents a bare hand mistakenly labelled as a mitt by the reader.
    rows = [step(gate, i, i * 0.2, point=[620, 250], uncertainty_px=10) for i in range(3)]
    assert rows[-1]["seed"]["point_px"] == [620, 250]
    assert all(r["mitt_identity"] == "unverified" for r in rows)


def test_no_observation_pitch_never_initializes():
    gate = SeedGate()
    rows = [gate.update("p", i, i * 0.1) for i in range(12)]
    assert all(r["state"] == "waiting" and r["seed"] is None for r in rows)


def test_outputs_and_input_points_do_not_alias_internal_support():
    gate = SeedGate()
    obs = observation(0, 0)
    out = gate.update("747139:3:1", 0, 0, obs)
    obs["mitt_center_px"][0] = 700
    out["support_keys"].clear()
    step(gate, 1, 0.2)
    accepted = step(gate, 2, 0.4)
    accepted["seed"]["support_keys"].clear()
    accepted["support_keys"][0]["frame_index"] = 999
    after = gate.update("747139:3:1", 3, 0.5)
    assert [k["frame_index"] for k in after["support_keys"]] == [0, 1, 2]


def test_policy_digest_and_fixed_instance_do_not_follow_mutated_module_constants(monkeypatch):
    assert hashlib.sha256(json.dumps(POLICY, sort_keys=True).encode()).hexdigest() == POLICY_SHA256
    gate = SeedGate()
    monkeypatch.setitem(POLICY, "max_uncertainty_px", 100)
    with pytest.raises(ValueError, match="modified"):
        SeedGate()
    assert step(gate, 0, 0, uncertainty_px=20)["reason"] == "uncertainty_exceeds_limit"

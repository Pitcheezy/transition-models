"""Synthetic S-contract checks, not evidence of a real API response or live integration."""

import hashlib
import json
from copy import deepcopy

import pytest

from src.integration.service_game import (
    EXPORT_PROFILE,
    PROFILE,
    ServiceGameError,
    build_pitch_view,
    normalize_service_game,
)


def _candidate(rank, pitch_type, probability):
    return {
        "rank": rank,
        "pitch_type": pitch_type,
        "pitch_label": f"Synthetic {pitch_type}",
        "zone_id": "high_left",
        "zone_label": "Synthetic location proxy",
        "target": {"x": -0.5, "z": 3.0},
        "detail": {"probability": probability},
    }


def _pitch(index=19, pa=8, number=1):
    return {
        "index": index,
        "key": f"999001:{pa}:{number}",
        "pa_key": f"999001:{pa}",
        "at_bat_number": pa,
        "pitch_number": number,
        "inning": 2,
        "half": "Top",
        "situation_before": {
            "inning": 2,
            "half": "Top",
            "outs": 1,
            "balls": 2,
            "strikes": 1,
            "bases": 5,
            "runners": {"first": True, "second": False, "third": True},
            "home_score": 1,
            "away_score": 0,
        },
        "pitcher": {"id": 900001, "name": "Synthetic Pitcher", "hand": "L", "jersey": "1"},
        "batter": {"id": 900002, "name": "Synthetic Batter", "side": "S", "jersey": "2"},
        "rec": {
            "status": "ready",
            "reason": None,
            "provenance": "asof_replay",
            "recorded_at": "2026-10-07T01:00:00Z",
            "policy": {"name": "Synthetic policy only", "identity": "synthetic-policy-id"},
            "candidates": [
                _candidate(3, "CH", 0.15),
                _candidate(1, "FF", 0.45),
                _candidate(4, "CU", None),
                _candidate(2, "SL", 0.20),
            ],
        },
        "actual": {
            "pitch_type": "FF",
            "pitch_label": "Synthetic actual pitch",
            "description": "SYNTHETIC_POST_ONLY_RESULT",
            "result_label": "Synthetic result",
            "event": None,
            "event_label": None,
            "play_text": "SYNTHETIC_POST_ONLY_PLAY",
            "speed_mph": 96.25,
            "x": -1.125,
            "z": 2.0625,
            "zone_label": "Synthetic actual location",
            "catcher_setup": None,
        },
    }


@pytest.fixture
def synthetic_snapshot():
    """Use invented identifiers and values; this fixture is not a captured S export."""
    return {
        "schema": "pitcheezy-service-game-v2",
        "source": {"kind": "archive"},
        "game": {
            "game_pk": 999001,
            "date": "2026-10-06",
            "away_team": "Synthetic Away",
            "home_team": "Synthetic Home",
        },
        "feed": {"as_of": "2026-10-07T01:01:00+00:00", "ok": True, "stale_s": 2.5},
        "cutoff": None,
        "zone_bounds": {"bottom": 1.6, "top": 3.4},
        "pitches": [_pitch()],
    }


def _normalize(payload, **overrides):
    # Direct mapping tests also exercise values a strict JSON CLI should reject.
    # This digest is test metadata, not authentication of any remote response.
    digest = hashlib.sha256(json.dumps(payload, sort_keys=True).encode("utf-8")).hexdigest()
    arguments = {"input_kind": "synthetic", "source_sha256": digest}
    arguments.update(overrides)
    return normalize_service_game(payload, **arguments)


def _set_path(payload, path, value):
    target = payload
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = value


def test_snapshot_preserves_meaning_without_asserting_unverified_capabilities(synthetic_snapshot):
    report = _normalize(synthetic_snapshot, reported_revision="abcdef1")
    row = report["pitches"][0]
    rec = row["pre"]["recommendation"]
    assert report["schema"] == "pitcheezy-service-review-v1"
    assert "provisional" in report["profile"]
    assert report["source"]["input_kind"] == "synthetic"
    assert report["source"]["reported_revision"] == "abcdef1"
    assert report["source"]["upstream_kind"] == "archive"
    assert all(value is False for value in report["claims"].values())
    assert report["units"]["candidate_probability"] == "pitch_type_selection_share"
    assert report["units"]["target_x_z"] == report["units"]["actual_x_z"] == "feet"
    assert report["units"]["speed"] == "mph"
    assert rec["policy"] == synthetic_snapshot["pitches"][0]["rec"]["policy"]
    assert rec["event_probabilities"] is None
    assert rec["distribution_complete"] is None
    assert "proxy" in rec["location_basis"]
    assert row["post"]["actual"]["speed_mph"] == 96.25
    assert report["summary"]["ready"] == report["summary"]["actual_available"] == 1
    assert report["warnings"]


def test_original_indexes_and_gaps_survive_unsorted_input(synthetic_snapshot):
    synthetic_snapshot["pitches"] = [_pitch(30, 10, 2), _pitch(23, 8, 4), _pitch(19, 8, 1)]
    before = deepcopy(synthetic_snapshot)
    report = _normalize(synthetic_snapshot)
    assert [(p["index"], p["key"]) for p in report["pitches"]] == [
        (19, "999001:8:1"),
        (23, "999001:8:4"),
        (30, "999001:10:2"),
    ]
    assert synthetic_snapshot == before
    view = build_pitch_view(report, "999001:8:4")
    assert view["index"] == 23
    with pytest.raises(ServiceGameError):
        build_pitch_view(report, "999001:8:2")


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("key", "999002:8:1"),
        ("key", "999001:8:2"),
        ("key", "999001:08:1"),
        ("pa_key", "999001:9"),
        ("pa_key", "999002:8"),
        ("pitch_number", 2),
        ("at_bat_number", 9),
    ],
)
def test_redundant_pitch_identifiers_must_agree(synthetic_snapshot, field, value):
    synthetic_snapshot["pitches"][0][field] = value
    with pytest.raises(ServiceGameError):
        _normalize(synthetic_snapshot)


@pytest.mark.parametrize(
    "rows",
    [
        [_pitch(19, 8, 1), _pitch(20, 8, 1)],
        [_pitch(19, 8, 1), _pitch(19, 8, 2)],
        [_pitch(20, 8, 1), _pitch(19, 8, 2)],
        [_pitch(20, 8, 1), _pitch(19, 9, 1)],
    ],
    ids=["duplicate-key", "duplicate-index", "reversed-pitch-order", "reversed-pa-order"],
)
def test_duplicate_and_conflicting_original_order_is_rejected(synthetic_snapshot, rows):
    synthetic_snapshot["pitches"] = deepcopy(rows)
    with pytest.raises(ServiceGameError):
        _normalize(synthetic_snapshot)


@pytest.mark.parametrize("status", ["unsupported", "missing"])
def test_unavailable_recommendations_preserve_reason_without_inventing_candidates(
    synthetic_snapshot, status
):
    synthetic_snapshot["pitches"][0]["rec"] = {
        "status": status,
        "reason": "Synthetic unsupported or unavailable reason",
        "candidates": [],
    }
    report = _normalize(synthetic_snapshot)
    rec = report["pitches"][0]["pre"]["recommendation"]
    assert rec["status"] == status
    assert rec["reason"] == "Synthetic unsupported or unavailable reason"
    assert rec["candidates"] == []
    assert rec["provenance"] == "absent"
    assert rec["recorded_at"] is rec["policy"] is rec["event_probabilities"] is None
    assert report["summary"][status] == 1
    assert report["summary"]["ready"] == 0


@pytest.mark.parametrize(
    ("status", "candidates"),
    [
        ("ready", []),
        ("unsupported", [_candidate(1, "FF", 0.5)]),
        ("missing", [_candidate(1, "FF", 0.5)]),
        ("unavailable", []),
        ("ready", None),
    ],
)
def test_recommendation_status_and_candidates_cannot_contradict(
    synthetic_snapshot, status, candidates
):
    synthetic_snapshot["pitches"][0]["rec"].update(status=status, candidates=candidates)
    with pytest.raises(ServiceGameError):
        _normalize(synthetic_snapshot)


def test_candidate_sorting_preserves_partial_mass_nulls_and_all_four_candidates(synthetic_snapshot):
    original = deepcopy(synthetic_snapshot)
    rec = _normalize(synthetic_snapshot)["pitches"][0]["pre"]["recommendation"]
    assert [
        (c["rank"], c["pitch_type"], c["selection_probability"]) for c in rec["candidates"]
    ] == [
        (1, "FF", 0.45),
        (2, "SL", 0.20),
        (3, "CH", 0.15),
        (4, "CU", None),
    ]
    assert rec["known_selection_mass"] == pytest.approx(0.8)
    assert sum(c["selection_probability"] for c in rec["candidates"][:3]) == pytest.approx(0.8)
    assert rec["distribution_complete"] is None
    assert synthetic_snapshot == original


@pytest.mark.parametrize("probability", [0, None])
def test_zero_or_unknown_selection_share_is_never_filled(synthetic_snapshot, probability):
    synthetic_snapshot["pitches"][0]["rec"]["candidates"] = [_candidate(1, "FF", probability)]
    rec = _normalize(synthetic_snapshot)["pitches"][0]["pre"]["recommendation"]
    assert rec["candidates"][0]["selection_probability"] == probability
    assert rec["known_selection_mass"] == 0
    assert rec["distribution_complete"] is None


@pytest.mark.parametrize("field", ["rank", "pitch_type"])
def test_duplicate_candidate_identity_is_not_silently_deduplicated(synthetic_snapshot, field):
    candidates = synthetic_snapshot["pitches"][0]["rec"]["candidates"]
    candidates[1][field] = candidates[0][field]
    with pytest.raises(ServiceGameError):
        _normalize(synthetic_snapshot)


@pytest.mark.parametrize(
    "bad",
    [True, "0.5", -0.1, 1.1, float("nan"), float("inf"), 10**1000],
    ids=["boolean", "numeric-text", "negative", "above-one", "nan", "infinity", "huge-integer"],
)
def test_invalid_selection_share_raises_contract_error_without_coercion(synthetic_snapshot, bad):
    synthetic_snapshot["pitches"][0]["rec"]["candidates"][0]["detail"]["probability"] = bad
    with pytest.raises(ServiceGameError):
        _normalize(synthetic_snapshot)


def test_known_selection_mass_above_one_is_rejected_even_with_unknown_share(synthetic_snapshot):
    synthetic_snapshot["pitches"][0]["rec"]["candidates"] = [
        _candidate(1, "FF", 0.7),
        _candidate(2, "SL", 0.4),
        _candidate(3, "CH", None),
    ]
    with pytest.raises(ServiceGameError):
        _normalize(synthetic_snapshot)


@pytest.mark.parametrize("missing_field", ["probability", "target"])
def test_unknown_probability_and_location_must_be_explicit(synthetic_snapshot, missing_field):
    candidate = synthetic_snapshot["pitches"][0]["rec"]["candidates"][0]
    if missing_field == "probability":
        del candidate["detail"][missing_field]
    else:
        del candidate[missing_field]
    with pytest.raises(ServiceGameError):
        _normalize(synthetic_snapshot)


def test_location_unavailability_does_not_destroy_supported_pitch_recommendation(
    synthetic_snapshot,
):
    candidate = synthetic_snapshot["pitches"][0]["rec"]["candidates"][0]
    candidate.update(target=None, zone_id=None, zone_label=None)
    rec = _normalize(synthetic_snapshot)["pitches"][0]["pre"]["recommendation"]
    normalized = next(c for c in rec["candidates"] if c["pitch_type"] == candidate["pitch_type"])
    assert rec["status"] == "ready"
    assert normalized["target"] is normalized["zone_id"] is None
    assert normalized["selection_probability"] == 0.15


@pytest.mark.parametrize("zone", [None, 1, "unknown_zone"])
def test_coordinates_require_a_supported_explicit_named_zone(synthetic_snapshot, zone):
    synthetic_snapshot["pitches"][0]["rec"]["candidates"][0]["zone_id"] = zone
    with pytest.raises(ServiceGameError):
        _normalize(synthetic_snapshot)


@pytest.mark.parametrize("bases", range(8))
def test_all_runner_bitmasks_are_consistent_without_reordering_bases(synthetic_snapshot, bases):
    situation = synthetic_snapshot["pitches"][0]["situation_before"]
    situation["bases"] = bases
    situation["runners"] = {
        "first": bool(bases & 1),
        "second": bool(bases & 2),
        "third": bool(bases & 4),
    }
    assert _normalize(synthetic_snapshot)["pitches"][0]["pre"]["situation"]["bases"] == bases


@pytest.mark.parametrize("bad", [False, 1, "true", None])
def test_runner_occupancy_is_boolean_and_must_match_mask(synthetic_snapshot, bad):
    synthetic_snapshot["pitches"][0]["situation_before"]["runners"]["first"] = bad
    with pytest.raises(ServiceGameError):
        _normalize(synthetic_snapshot)


@pytest.mark.parametrize(("field", "value"), [("inning", 3), ("half", "Bot"), ("inning", True)])
def test_redundant_row_situation_must_agree(synthetic_snapshot, field, value):
    synthetic_snapshot["pitches"][0][field] = value
    with pytest.raises(ServiceGameError):
        _normalize(synthetic_snapshot)


@pytest.mark.parametrize(
    ("person", "field", "value"),
    [
        ("pitcher", "hand", "S"),
        ("batter", "side", "switch"),
        ("pitcher", "hand", True),
        ("batter", "side", "l"),
    ],
)
def test_player_sides_are_not_guessed_or_coerced(synthetic_snapshot, person, field, value):
    synthetic_snapshot["pitches"][0][person][field] = value
    with pytest.raises(ServiceGameError):
        _normalize(synthetic_snapshot)


@pytest.mark.parametrize("hand", ["L", "R", None])
def test_supported_pitcher_hands_and_switch_hitting_batter_are_preserved(synthetic_snapshot, hand):
    synthetic_snapshot["pitches"][0]["pitcher"]["hand"] = hand
    pre = _normalize(synthetic_snapshot)["pitches"][0]["pre"]
    assert pre["pitcher"]["hand"] == hand
    assert pre["batter"]["side"] == "S"


@pytest.mark.parametrize(
    ("path", "value"),
    [
        (("game", "game_pk"), True),
        (("pitches", 0, "index"), False),
        (("pitches", 0, "pitch_number"), "1"),
        (("pitches", 0, "situation_before", "outs"), 3),
        (("pitches", 0, "situation_before", "balls"), 4),
        (("pitches", 0, "situation_before", "strikes"), 3),
        (("pitches", 0, "situation_before", "bases"), 8),
        (("pitches", 0, "situation_before", "home_score"), -1),
        (("pitches", 0, "situation_before", "half"), "Bottom"),
        (("pitches", 0, "rec", "candidates", 0, "rank"), True),
        (("pitches", 0, "actual", "speed_mph"), float("nan")),
        (("pitches", 0, "actual", "x"), float("inf")),
        (("feed", "ok"), 1),
        (("feed", "stale_s"), -0.1),
        (("cutoff",), True),
        (("zone_bounds", "top"), 1.5),
    ],
)
def test_malformed_values_fail_instead_of_becoming_valid_state(synthetic_snapshot, path, value):
    _set_path(synthetic_snapshot, path, value)
    with pytest.raises(ServiceGameError):
        _normalize(synthetic_snapshot)


@pytest.mark.parametrize(
    ("container", "field"),
    [
        ("situation_before", "actual"),
        ("situation_before", "result"),
        ("rec", "we"),
        ("rec", "post"),
        ("pitcher", "catcher_setup"),
        ("batter", "actual"),
    ],
)
def test_post_fields_are_rejected_even_inside_unknown_nested_pre_data(
    synthetic_snapshot, container, field
):
    synthetic_snapshot["pitches"][0][container]["extra"] = [{"nested": {field: None}}]
    with pytest.raises(ServiceGameError, match="post-pitch"):
        _normalize(synthetic_snapshot)


def test_missing_pre_state_never_falls_back_to_final_or_actual_state(synthetic_snapshot):
    synthetic_snapshot["game"].update(home_score=12, away_score=9)
    synthetic_snapshot["pitches"][0]["actual"]["home_score"] = 12
    del synthetic_snapshot["pitches"][0]["situation_before"]["home_score"]
    with pytest.raises(ServiceGameError):
        _normalize(synthetic_snapshot)


def test_future_game_sections_and_unknown_fields_are_never_copied_into_pre_view(synthetic_snapshot):
    sentinel = "SYNTHETIC_FUTURE_METADATA"
    synthetic_snapshot["game"].update(home_score=12, away_score=9, final={"note": sentinel})
    for section in ("current", "next", "pas", "linescore", "pregame"):
        synthetic_snapshot[section] = {"unknown": sentinel}
    synthetic_snapshot["pitches"][0]["rec"]["outcome_probabilities"] = {"hit": 0.9}
    synthetic_snapshot["pitches"][0]["extra"] = sentinel
    report = _normalize(synthetic_snapshot)
    view = build_pitch_view(report, "999001:8:1")
    assert set(report["uninterpreted_sections"]) == {
        "current",
        "next",
        "pas",
        "linescore",
        "pregame",
    }
    assert sentinel not in json.dumps(report)
    assert "outcome_probabilities" not in json.dumps(view)
    assert view["pre"]["situation"]["home_score"] == 1
    assert view["pre"]["situation"]["away_score"] == 0
    assert view["pre"]["recommendation"]["event_probabilities"] is None
    assert "we" not in view


def test_live_metadata_and_cutoff_do_not_certify_timing_or_filter_pitches(synthetic_snapshot):
    synthetic_snapshot["source"]["kind"] = "live"
    synthetic_snapshot["cutoff"] = 0
    synthetic_snapshot["feed"] = {"as_of": None, "ok": False, "stale_s": None}
    rec = synthetic_snapshot["pitches"][0]["rec"]
    rec["provenance"] = "captured_live"
    rec["recorded_at"] = "2099-01-01T00:00:00Z"
    report = _normalize(synthetic_snapshot, reported_revision="abcdef1")
    assert report["feed"] == synthetic_snapshot["feed"]
    assert report["cutoff"] == 0
    assert report["pitches"][0]["index"] == 19
    assert report["pitches"][0]["pre"]["recommendation"]["recorded_at"] == rec["recorded_at"]
    assert report["pitches"][0]["pre"]["recommendation"]["provenance"] == "captured_live"
    assert all(value is False for value in report["claims"].values())
    assert build_pitch_view(report, "999001:8:1")["live_timing_verified"] is False


def test_live_source_cannot_invent_recommendation_provenance_or_model_identity(synthetic_snapshot):
    synthetic_snapshot["source"]["kind"] = "live"
    rec = synthetic_snapshot["pitches"][0]["rec"]
    for field in ("provenance", "recorded_at", "policy"):
        rec.pop(field)
    normalized = _normalize(synthetic_snapshot)["pitches"][0]["pre"]["recommendation"]
    assert normalized["provenance"] == "absent"
    assert normalized["recorded_at"] is normalized["policy"] is None


@pytest.mark.parametrize("path", [("feed", "as_of"), ("pitches", 0, "rec", "recorded_at")])
@pytest.mark.parametrize("timestamp", ["2026-10-07T01:00:00", "2026-99-99T01:00:00Z"])
def test_present_timestamps_need_valid_dates_and_explicit_timezone(
    synthetic_snapshot, path, timestamp
):
    _set_path(synthetic_snapshot, path, timestamp)
    with pytest.raises(ServiceGameError):
        _normalize(synthetic_snapshot)


@pytest.mark.parametrize("setup", [None, {}, {"x": 0.25}, {"setup_x": -0.5}, [0.1, 0.2], 0, False])
def test_unknown_setup_shape_is_reported_only_as_raw_presence(synthetic_snapshot, setup):
    synthetic_snapshot["pitches"][0]["actual"]["catcher_setup"] = deepcopy(setup)
    report = _normalize(synthetic_snapshot)
    actual = report["pitches"][0]["post"]["actual"]
    assert actual["has_setup_estimate"] is (setup is not None)
    assert actual["setup_x_ft"] is None
    assert actual["setup_interpretation"] == "unverified_upstream_shape"
    assert "catcher_setup" not in actual
    assert report["summary"]["uninterpreted_setup"] == int(setup is not None)
    assert any("setup" in warning.lower() for warning in report["warnings"])


@pytest.mark.parametrize("actual_mode", ["absent", "null"])
def test_absent_actual_is_not_synthesized_for_reveal(synthetic_snapshot, actual_mode):
    if actual_mode == "absent":
        del synthetic_snapshot["pitches"][0]["actual"]
    else:
        synthetic_snapshot["pitches"][0]["actual"] = None
    report = _normalize(synthetic_snapshot)
    assert report["summary"]["actual_available"] == 0
    assert build_pitch_view(report, "999001:8:1", revealed=True)["actual"] is None


def test_actual_and_setup_stay_hidden_until_explicit_reveal(synthetic_snapshot):
    synthetic_snapshot["pitches"][0]["actual"]["catcher_setup"] = {"x": -0.3}
    report = _normalize(synthetic_snapshot)
    hidden = build_pitch_view(report, "999001:8:1")
    shown = build_pitch_view(report, "999001:8:1", revealed=True)
    hidden_again = build_pitch_view(report, "999001:8:1", revealed=False)
    assert hidden == hidden_again
    assert hidden["actual"] is None
    assert hidden["revealed"] is False
    assert "SYNTHETIC_POST_ONLY" not in json.dumps(hidden)
    assert "setup_x_ft" not in json.dumps(hidden)
    assert shown["actual"]["description"] == "SYNTHETIC_POST_ONLY_RESULT"
    assert shown["actual"]["has_setup_estimate"] is True
    assert shown["actual"]["setup_x_ft"] is None
    assert shown["pre"] == hidden["pre"]


@pytest.mark.parametrize("revealed", [None, 0, 1, "true", []])
def test_reveal_requires_boolean_not_truthiness(synthetic_snapshot, revealed):
    report = _normalize(synthetic_snapshot)
    with pytest.raises(ServiceGameError):
        build_pitch_view(report, "999001:8:1", revealed=revealed)


def test_projections_are_repeatable_and_have_no_mutable_aliases(synthetic_snapshot):
    original = deepcopy(synthetic_snapshot)
    report = _normalize(synthetic_snapshot)
    baseline = deepcopy(report)
    assert _normalize(synthetic_snapshot) == report
    view = build_pitch_view(report, "999001:8:1", revealed=True)
    view["pre"]["situation"]["balls"] = 0
    view["pre"]["recommendation"]["candidates"][0]["target"]["x"] = 9
    view["actual"]["x"] = 9
    assert report == baseline
    report["feed"]["ok"] = False
    report["pitches"][0]["pre"]["recommendation"]["policy"]["name"] = "changed"
    report["pitches"][0]["pre"]["recommendation"]["candidates"][0]["target"]["x"] = 8
    assert synthetic_snapshot == original
    synthetic_snapshot["pitches"][0]["actual"]["x"] = 7
    assert report["pitches"][0]["post"]["actual"]["x"] == -1.125


@pytest.mark.parametrize(
    "schema", ["pitcheezy-receiver-v1", "pitcheezy-watch-along-v1", "unknown", None]
)
def test_old_or_unknown_contracts_cannot_be_silently_upgraded(synthetic_snapshot, schema):
    synthetic_snapshot["schema"] = schema
    with pytest.raises(ServiceGameError):
        _normalize(synthetic_snapshot)


@pytest.mark.parametrize(
    "overrides",
    [
        {"input_kind": "live"},
        {"source_sha256": "0" * 63},
        {"source_sha256": "A" * 64},
        {"reported_revision": "release-main"},
    ],
)
def test_declared_source_metadata_is_required_in_its_own_namespace(synthetic_snapshot, overrides):
    with pytest.raises(ServiceGameError):
        _normalize(synthetic_snapshot, **overrides)


def test_empty_snapshot_remains_empty_without_fabricated_current_pitch(synthetic_snapshot):
    synthetic_snapshot["pitches"] = []
    report = _normalize(synthetic_snapshot)
    assert report["pitches"] == []
    assert all(count == 0 for count in report["summary"].values())
    with pytest.raises(ServiceGameError):
        build_pitch_view(report, "999001:8:1")


@pytest.fixture
def synthetic_export(synthetic_snapshot):
    """Model the supplied contract shape using invented, non-private values."""
    synthetic_snapshot["game"]["date_kst"] = "2026-10-09"
    synthetic_snapshot["cutoff"] = {"index": 19, "pitch_key": "999001:8:1"}
    return synthetic_snapshot


def _normalize_export(payload, **overrides):
    return _normalize(payload, profile=EXPORT_PROFILE, **overrides)


def test_export_requires_explicit_profile_and_preserves_legacy_interpretation(synthetic_export):
    with pytest.raises(ServiceGameError, match="cutoff"):
        _normalize(synthetic_export)
    report = _normalize_export(synthetic_export, input_kind="provided_export")
    assert report["profile"] == EXPORT_PROFILE
    assert report["cutoff"] == synthetic_export["cutoff"]
    assert report["cutoff_interpretation"] == "snapshot_release_boundary_not_training_cutoff"
    assert report["index_scope"] == "supplied_snapshot_only_join_by_pitch_key"
    assert report["game"]["kst_date"] == "2026-10-09"
    assert all(value is False for value in report["claims"].values())
    warnings = " ".join(report["warnings"])
    for phrase in ("post-game", "unvalidated", "not authentication", "complete-game"):
        assert phrase in warnings
    rec = report["pitches"][0]["pre"]["recommendation"]
    assert rec["event_probabilities"] is None
    assert rec["known_selection_mass"] == pytest.approx(0.8)
    assert rec["distribution_complete"] is None
    synthetic_export["cutoff"] = 19
    synthetic_export["pitches"][0]["actual"]["catcher_setup"] = {"old": "unknown"}
    legacy = _normalize(synthetic_export)
    assert legacy["profile"] == PROFILE
    assert legacy["summary"]["uninterpreted_setup"] == 1
    assert "cutoff_interpretation" not in legacy
    assert "setup_status" not in legacy["pitches"][0]["post"]["actual"]


@pytest.mark.parametrize("profile", ["unknown", "", None, True, []])
def test_unknown_profiles_are_rejected_without_guessing(synthetic_snapshot, profile):
    with pytest.raises(ServiceGameError, match="profile"):
        _normalize(synthetic_snapshot, profile=profile)


@pytest.mark.parametrize(
    "cutoff",
    [
        19,
        True,
        {},
        {"index": 19},
        {"pitch_key": "999001:8:1"},
        {"index": True, "pitch_key": "999001:8:1"},
        {"index": -1, "pitch_key": "999001:8:1"},
        {"index": 100001, "pitch_key": None},
        {"index": 19.0, "pitch_key": "999001:8:1"},
        {"index": 19, "pitch_key": "999002:8:1"},
        {"index": 19, "pitch_key": "999001:08:1"},
        {"index": 19, "pitch_key": "999001:8:2"},
        {"index": 20, "pitch_key": "999001:8:1"},
        {"index": 18, "pitch_key": None},
    ],
)
def test_export_rejects_invalid_or_inconsistent_release_boundaries(synthetic_export, cutoff):
    synthetic_export["cutoff"] = cutoff
    with pytest.raises(ServiceGameError, match="cutoff"):
        _normalize_export(synthetic_export)


def test_export_cutoff_null_is_unknown_and_never_filled(synthetic_export):
    synthetic_export["cutoff"] = None
    report = _normalize_export(synthetic_export)
    assert report["cutoff"] is None
    assert report["cutoff_interpretation"] == "unknown"
    assert report["summary"]["pitches"] == 1
    assert report["claims"]["complete_game_verified"] is False


def test_export_null_cutoff_key_preserves_only_declared_boundary(synthetic_export):
    synthetic_export["cutoff"]["pitch_key"] = None
    report = _normalize_export(synthetic_export)
    assert report["cutoff"] == {"index": 19, "pitch_key": None}


def test_export_cutoff_joins_by_key_not_array_position_or_previous_snapshot(synthetic_export):
    synthetic_export["pitches"] = [_pitch(30, 10, 2), _pitch(23, 8, 4), _pitch(19, 8, 1)]
    synthetic_export["cutoff"] = {"index": 30, "pitch_key": "999001:10:2"}
    original = deepcopy(synthetic_export)
    first = _normalize_export(synthetic_export)
    assert synthetic_export == original
    assert [p["index"] for p in first["pitches"]] == [19, 23, 30]
    assert build_pitch_view(first, "999001:8:4")["index"] == 23
    for pitch in synthetic_export["pitches"]:
        pitch["index"] += 100
    synthetic_export["cutoff"]["index"] += 100
    second = _normalize_export(synthetic_export)
    assert build_pitch_view(second, "999001:8:4")["index"] == 123
    assert (
        build_pitch_view(second, "999001:8:4")["pre"]
        == build_pitch_view(first, "999001:8:4")["pre"]
    )
    synthetic_export["cutoff"] = {"index": 123, "pitch_key": "999001:8:4"}
    with pytest.raises(ServiceGameError, match="beyond"):
        _normalize_export(synthetic_export)


def test_export_rejects_index_order_conflicting_with_pitch_identity(synthetic_export):
    synthetic_export["pitches"] = [_pitch(20, 8, 1), _pitch(19, 8, 2)]
    synthetic_export["cutoff"] = {"index": 20, "pitch_key": "999001:8:1"}
    with pytest.raises(ServiceGameError, match="order"):
        _normalize_export(synthetic_export)


@pytest.mark.parametrize("invalid_date", ["2026-02-30", "2026-9-30", "20261009", True, 20261009])
def test_export_calendar_date_is_checked_without_using_other_date_fields(
    synthetic_export, invalid_date
):
    synthetic_export["game"]["date_kst"] = invalid_date
    synthetic_export["game"]["kst_date"] = "2026-10-09"
    with pytest.raises(ServiceGameError, match="date_kst"):
        _normalize_export(synthetic_export)


def test_export_missing_date_is_not_replaced_with_legacy_date(synthetic_export):
    del synthetic_export["game"]["date_kst"]
    synthetic_export["game"]["kst_date"] = "2026-10-09"
    with pytest.raises(ServiceGameError, match="date_kst"):
        _normalize_export(synthetic_export)
    synthetic_export["game"]["date_kst"] = None
    assert _normalize_export(synthetic_export)["game"]["kst_date"] is None


@pytest.mark.parametrize(
    ("setup", "status", "displayable", "summary_field"),
    [
        (None, None, False, "setup_not_supplied"),
        (
            {"status": "unavailable", "x_band": None, "plate_x_feet": None},
            "unavailable",
            False,
            "setup_unavailable",
        ),
        (
            {"status": "estimated", "x_band": "middle", "plate_x_feet": None},
            "estimated",
            False,
            "setup_estimated",
        ),
        (
            {"status": "estimated", "x_band": "middle", "plate_x_feet": 0},
            "estimated",
            True,
            "setup_estimated",
        ),
        (
            {"status": "estimated", "x_band": "off_left", "plate_x_feet": -1.1},
            "estimated",
            True,
            "setup_estimated",
        ),
    ],
)
def test_export_setup_is_reveal_only_and_preserves_null_zero_and_unavailability(
    synthetic_export, setup, status, displayable, summary_field
):
    synthetic_export["pitches"][0]["actual"]["catcher_setup"] = setup
    report = _normalize_export(synthetic_export)
    hidden = build_pitch_view(report, "999001:8:1")
    shown = build_pitch_view(report, "999001:8:1", revealed=True)
    assert hidden["actual"] is None
    assert "setup_" not in json.dumps(hidden)
    assert "SYNTHETIC_POST_ONLY" not in json.dumps(hidden)
    assert hidden["pre"] == shown["pre"]
    actual = shown["actual"]
    assert actual["has_setup_estimate"] is displayable
    assert actual["setup_status"] == status
    assert actual["setup_x_ft"] == (setup["plate_x_feet"] if setup else None)
    assert actual["setup_x_band"] == (setup["x_band"] if setup else None)
    assert (
        actual["setup_interpretation"] == "upstream_unreviewed_horizontal_setup_not_pitcher_intent"
    )
    assert report["summary"][summary_field] == 1
    assert report["summary"]["setup_displayable"] == int(displayable)
    assert report["summary"]["uninterpreted_setup"] == 0
    assert "catcher_setup" not in actual
    shown["actual"]["setup_x_ft"] = 8
    assert build_pitch_view(report, "999001:8:1", revealed=True)["actual"] == actual | {
        "setup_x_ft": setup["plate_x_feet"] if setup else None
    }
    assert build_pitch_view(report, "999001:8:1", revealed=False) == hidden


@pytest.mark.parametrize(
    "setup",
    [
        {},
        [],
        False,
        0,
        {"status": "estimated", "x_band": "middle"},
        {"status": "estimated", "plate_x_feet": 0},
        {"x_band": "middle", "plate_x_feet": 0},
        {"status": "unavailable", "x_band": "middle", "plate_x_feet": None},
        {"status": "unavailable", "x_band": None, "plate_x_feet": 0},
        {"status": "ready", "x_band": "middle", "plate_x_feet": 0},
        {"status": "estimated", "x_band": "unknown", "plate_x_feet": 0},
        {"status": "estimated", "x_band": None, "plate_x_feet": 0},
        {"status": "estimated", "x_band": "middle", "plate_x_feet": True},
        {"status": "estimated", "x_band": "middle", "plate_x_feet": "0.1"},
        {"status": "estimated", "x_band": "middle", "plate_x_feet": float("nan")},
        {"status": "estimated", "x_band": "middle", "plate_x_feet": float("inf")},
    ],
)
def test_export_setup_requires_documented_status_shape_and_finite_coordinate(
    synthetic_export, setup
):
    synthetic_export["pitches"][0]["actual"]["catcher_setup"] = setup
    with pytest.raises(ServiceGameError, match="catcher_setup"):
        _normalize_export(synthetic_export)


def test_export_missing_setup_is_not_silently_treated_as_explicit_null(synthetic_export):
    del synthetic_export["pitches"][0]["actual"]["catcher_setup"]
    with pytest.raises(ServiceGameError, match="catcher_setup"):
        _normalize_export(synthetic_export)

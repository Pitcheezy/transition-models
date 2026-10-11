"""Focused checks for saved-route semantics and ambiguous-evidence rejection."""

import importlib.util
from copy import deepcopy
from pathlib import Path

import pytest

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/audit_cv6b_saved_reasons.py"
SPEC = importlib.util.spec_from_file_location("cv6b_audit", SCRIPT)
audit = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(audit)


def reading(*, frame=10, mitt=True, plate=True, reason=None):
    return {
        "setup_frame": frame,
        "mitt_center": [20, 30] if mitt else None,
        "setup_plate_front": {"left_end": [0, 0], "right_end": [10, 0]} if plate else None,
        "setup_reason": reason,
    }


def rejected(reason):
    return reading(frame=None, mitt=False, plate=False, reason=reason)


def test_saved_routes_match_exact_predicates_without_modifying_rows():
    one = "only_one_reader_found_a_setup_frame"
    disagree = "readers_disagree_on_mitt"
    cases = [
        (reading(), rejected("not_centre_field"), one, "camera_rejection_one_candidate"),
        (reading(), rejected("slow_motion_replay_not_live"), one, "replay_rejection_one_candidate"),
        (reading(), reading(plate=False), one, "plate_missing_with_two_mitt_readings"),
        (reading(), reading(frame=11), disagree, "different_frame_mitt_disagreement"),
        (reading(), reading(), disagree, "same_frame_mitt_disagreement"),
        (
            rejected("not_centre_field"),
            reading(plate=False),
            "not_centre_field",
            "camera_rejection_and_plate_missing",
        ),
    ]
    cases.extend(
        (reading(), rejected(reason), one, "reported_not_presented_or_lowered")
        for reason in audit.REPORTED_SETUP_REASONS
    )
    for a, b, reason, expected in cases:
        before = deepcopy((a, b))
        for first, second in ((a, b), (b, a)):
            assert audit.classify(first, second, {"reason": reason}) == expected
        assert (a, b) == before


def test_notes_do_not_invent_a_reported_abstention_reason():
    b = rejected(None)
    b["note"] = "glove_resting_on_dirt_not_presented"
    with pytest.raises(ValueError, match="unclassified"):
        audit.classify(reading(), b, {"reason": "only_one_reader_found_a_setup_frame"})


def test_ambiguous_or_unconfirmed_routes_are_rejected():
    cases = [
        (reading(), reading(frame=11, plate=False), "only_one_reader_found_a_setup_frame"),
        (reading(), reading(), None),
    ]
    for a, b, reason in cases:
        with pytest.raises(ValueError, match="unclassified"):
            audit.classify(a, b, {"reason": reason})


def raw_document():
    row = {"at_bat_number": 1, "pitch_number": 2}
    return {"schema": "intent_condensed_read_reads_v0", "reads": [{"A": [row], "B": [row]}]}


def test_duplicate_keys_fail_before_existing_overwriting_loader():
    with pytest.raises(ValueError, match="duplicate"):
        audit.index_unique(
            [{"observation_id": "one"}, {"observation_id": "one"}],
            "observation_id",
            "private observation",
        )
    document = raw_document()
    document["reads"][0]["A"] *= 2
    with pytest.raises(ValueError, match="duplicate raw A"):
        audit.validate_raw(document, {(1, 2)})


def test_missing_reader_key_is_not_a_visual_abstention():
    document = raw_document()
    document["reads"][0]["B"] = None
    with pytest.raises(ValueError, match="raw B and frozen points keys differ"):
        audit.validate_raw(document, {(1, 2)})

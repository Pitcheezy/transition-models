"""CV-32 cause split: exact rules only, saved decisions reproduce, nothing guessed from notes."""

import importlib.util
from copy import deepcopy
from pathlib import Path

from intent import mitt_inventory as inv

SCRIPT = Path(__file__).resolve().parents[1] / "scripts/audit_cv6b_saved_reasons.py"
SPEC = importlib.util.spec_from_file_location("cv6b_audit_for_inventory", SCRIPT)
cv6b = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(cv6b)


def reading(*, frame=10, mitt=True, plate=True, reason=None, release=13, live=1):
    return {
        "setup_frame": frame,
        "mitt_center": [20, 30] if mitt else None,
        "setup_plate_front": {"left_end": [0, 0], "right_end": [10, 0]} if plate else None,
        "setup_reason": reason,
        "release_frame": release,
        "live_cf_first_frame": live,
    }


def rejected(reason):
    return reading(frame=None, mitt=False, plate=False, reason=reason)


def route(a, b, reason):
    return inv.classify_pair(a, b, {"status": "unavailable", "reason": reason}, cv6b.classify)


def test_tables_name_only_the_six_categories_and_cover_the_cv6b_routes():
    assert set(inv.REASON_TABLE.values()) <= set(inv.CATEGORIES)
    assert {c for cats in inv.ROUTE_CATEGORIES.values() for c in cats} <= set(inv.CATEGORIES)
    assert set(inv.ROUTE_CATEGORIES) == set(cv6b.PREDICATES)
    for reason in cv6b.REPORTED_SETUP_REASONS:
        assert inv.REASON_TABLE[reason] == "C2_target_not_presented_or_undeterminable"


def test_cv6b_routes_are_reused_and_extensions_use_exact_reason_strings():
    one = "only_one_reader_found_a_setup_frame"
    a, b = reading(), rejected("not_centre_field")
    before = deepcopy((a, b))
    assert route(a, b, one) == (
        "camera_rejection_one_candidate",
        ["C5_no_pitch_link_or_time_evidence"],
    )
    assert (a, b) == before
    assert route(reading(), rejected("glove_hidden_by_batter"), one) == (
        "one_candidate_other_reason:glove_hidden_by_batter",
        ["C1_mitt_not_visible"],
    )
    both = route(rejected("cut_after_release"), rejected("cut_after_release"), "cut_after_release")
    assert both == ("both_no_setup:cut_after_release", ["C5_no_pitch_link_or_time_evidence"])
    # different frames, other reader has a mitt but no plate: two causes, both kept
    assert route(reading(), reading(frame=7, plate=False), one) == (
        "plate_missing_on_other_reader_different_frame",
        ["C4_no_transform_reference", "C3_reader_disagreement"],
    )


def test_unknown_or_free_text_reasons_stay_unclassified():
    one = "only_one_reader_found_a_setup_frame"
    for reason in ("glove hidden by batter", "glove_not_visible_maybe", None, ""):
        assert route(reading(), rejected(reason), one) == ("unclassified", [])
    assert route(rejected("glove_hidden_by_umpire"), rejected("novel_reason"), "x") == (
        "unclassified",
        [],
    )


def test_live_view_lead_excludes_rows_whose_setup_or_view_start_follows_release():
    fps = float(inv.FPS)
    pairs = {
        "1:1": {
            "A": reading(frame=97, release=100, live=40),
            "B": reading(frame=98, release=100, live=70),
        },
        "2:1": {"A": reading(frame=150, release=100, live=40)},
    }
    out = inv.live_view_lead(pairs)
    assert out["inconsistent_rows_excluded"] == ["2:1:A"]
    live = out["live_centre_view_before_release_seconds"]
    assert live["n"] == 2 and abs(live["max"] - round(60 / fps, 3)) < 1e-9
    assert out["chosen_setup_frame_before_release_seconds"]["max"] == round(3 / fps, 3)


def test_frame_digest_is_order_independent():
    rows = [("a/frame_000001.jpg", 10, "x" * 64), ("b/frame_000002.jpg", 11, "y" * 64)]
    assert inv.digest_lines(rows) == inv.digest_lines(list(reversed(rows)))
    assert inv.digest_lines(rows) != inv.digest_lines(rows[:1])


def test_saved_m3_abstentions_reproduce_and_split_without_unclassified():
    report, rows = inv.bottleneck(games=(849845, 823407))
    games = report["games"]
    # the M3 86 frames: 58 AI outputs and 28 abstentions on 849845 + 823407
    assert sum(g["estimated"] for g in games.values()) == 58
    assert sum(g["unavailable"] for g in games.values()) == 28
    assert all(g["unclassified"] == 0 for g in games.values())
    assert games["849845"]["category_counts"]["C2_target_not_presented_or_undeterminable"] == 8
    assert games["849845"]["category_counts"]["C3_reader_disagreement"] == 6
    c823 = games["823407"]["category_counts"]
    assert (
        c823["C3_reader_disagreement"],
        c823["C4_no_transform_reference"],
        c823["C5_no_pitch_link_or_time_evidence"],
    ) == (3, 6, 8)
    assert len(rows) == 28 and all(r["categories"] for r in rows)


def test_reader_release_drops_inconsistent_rows_and_flags_disagreement():
    a = reading(frame=59856, release=59859, live=59700)
    b = reading(
        frame=59835, release=56856, live=59799
    )  # setup and view start after its own release
    assert inv.inconsistent_row(b) and not inv.inconsistent_row(a)
    assert inv.reader_release({"A": a, "B": b}) == (59859, "ok_inconsistent_row_dropped")
    c = reading(frame=100, release=103, live=40)
    d = reading(frame=100, release=120, live=40)
    assert inv.reader_release({"A": c, "B": d}) == (None, "readers_disagree_on_release")
    e = reading(frame=100, release=106, live=40)
    assert inv.reader_release({"A": c, "B": e}) == (103, "ok")
    assert inv.reader_release({}) == (None, "no_release")


def test_nearest_rank_percentile():
    values = list(range(1, 11))
    assert inv.nearest_rank(values, 0.9) == 9 and inv.nearest_rank(values, 0.1) == 1
    assert inv.nearest_rank([5], 0.9) == 5

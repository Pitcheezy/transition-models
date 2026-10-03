"""Condensed-game pipeline (scan matching, consensus rule) and the M3 accuracy table."""

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from intent.accuracy_report import build as build_report  # noqa: E402
from intent.condensed import (  # noqa: E402
    apply_resolutions,
    decide_setup,
    find_condensed,
    graphic_agreement,
    graphic_types,
    load_reader_results,
    match_detections,
    outcome_category,
    pair_readers,
    scan_ranges,
    surname_from_bug,
    usable,
)
from intent.human_labels import game_role  # noqa: E402


def _pitch(pa, pn, balls, strikes, call, ptype="FF", speed=95.0, batter="Pete Crow-Armstrong"):
    return {
        "at_bat_number": pa,
        "pitch_number": pn,
        "play_id": f"p{pa}-{pn}",
        "half": "top",
        "inning": 1,
        "batter": batter,
        "pitcher": "Michael King",
        "balls_before": balls,
        "strikes_before": strikes,
        "call": call,
        "pitch_type": ptype,
        "start_speed": speed,
    }


def _seen(t, balls, strikes, outcome, graphic=None, batter="1. CROW-ARMSTRONG", inning=1):
    return {
        "release_t": t,
        "half": "top",
        "inning": inning,
        "balls_before": balls,
        "strikes_before": strikes,
        "batter_text": batter,
        "outcome_seen": outcome,
        "post_pitch_graphic": graphic,
    }


def test_text_helpers():
    assert surname_from_bug("2. BREGMAN") == "BREGMAN"
    assert surname_from_bug("1. CROW-ARMSTRONG") == "CROW-ARMSTRONG"
    assert surname_from_bug("A. Rodríguez Jr.") == "RODRIGUEZ"
    assert outcome_category("Foul Tip") == "swinging_strike"
    assert outcome_category("In play, out(s)") == "in_play"
    assert outcome_category("ground ball to short") == "in_play"
    assert outcome_category("called strike three") == "called_strike"
    assert outcome_category("Ball In Dirt") == "ball"
    assert outcome_category("foul ball") == "foul"
    assert graphic_types("FOUR SEAM") == {"FF"}
    assert graphic_types("Knuckle Curve") == {"KC"}
    assert graphic_types("") is None
    p = _pitch(1, 1, 0, 0, "Ball", "SL", 86.6)
    assert graphic_agreement({"type_text": "SLIDER", "mph": 87}, p) is True
    assert graphic_agreement({"type_text": "SLIDER", "mph": 89}, p) is False
    assert graphic_agreement({"type_text": None, "mph": None}, p) is None
    assert graphic_agreement(None, p) is None


def test_find_condensed_needs_the_mp4_playback():
    content = {
        "highlights": {
            "highlights": {
                "items": [
                    {"title": "Recap: CHC@SD", "playbacks": [{"name": "mp4Avc", "url": "r"}]},
                    {"title": "Condensed Game: CHC@SD", "playbacks": [{"name": "hls", "url": "h"}]},
                    {
                        "title": "Condensed Game: CHC@SD - Game 1",
                        "duration": "00:13:51",
                        "id": "x",
                        "playbacks": [{"name": "mp4Avc", "url": "https://cdn/x.mp4"}],
                    },
                ]
            }
        }
    }
    found = find_condensed(content)
    assert found["media_url"] == "https://cdn/x.mp4" and found["duration"] == "00:13:51"
    assert find_condensed({"highlights": {"highlights": {"items": []}}}) is None


def test_scan_ranges_cover_the_video():
    names = [(i * 8.0, f"sheet_{i * 8.0:06.1f}.jpg") for i in range(23)]
    ranges = scan_ranges(names, 23 * 16 - 5)
    assert [len(r["sheets"]) for r in ranges] == [10, 10, 3]
    assert ranges[0]["start"] == 0.0 and ranges[0]["end"] == 80.0
    assert ranges[-1]["end"] == pytest.approx((23 * 16 - 5 - 1) / 2)


def test_reader_results_from_journal_and_from_returned_json(tmp_path):
    journal = tmp_path / "journal.jsonl"
    rows = [
        {"type": "started", "agentId": "a1", "label": "scan-A:1"},
        {"type": "started", "agentId": "b1", "label": "scan-B:1"},
        {"type": "result", "agentId": "a1", "result": {"pitches": [{"release_t": 1.0}]}},
        {"type": "result", "agentId": "b1", "result": {"pitches": [{"release_t": 1.5}]}},
    ]
    journal.write_text("\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8")
    got = load_reader_results(journal)
    assert got["A"][0]["pitches"][0]["release_t"] == 1.0 and len(got["B"]) == 1
    returned = tmp_path / "reads.json"
    returned.write_text(
        json.dumps({"reads": [{"chunk": 1, "A": [{"x": 1}], "B": None}]}), encoding="utf-8"
    )
    got = load_reader_results(returned)
    assert got["A"] == [{"items": [{"x": 1}]}] and got["B"] == []


def test_matching_breaks_ties_by_graphic_then_outcome_and_flags_the_rest():
    pitches = [
        _pitch(1, 1, 0, 0, "Called Strike", "FF", 95.1),
        _pitch(1, 2, 0, 1, "Foul", "SL", 86.0),
        _pitch(1, 3, 0, 2, "Foul", "FF", 96.0),
        _pitch(1, 4, 0, 2, "Swinging Strike", "SL", 87.0),
        _pitch(2, 1, 0, 0, "In play, out(s)", "CH", 88.0, batter="Alex Bregman"),
        _pitch(3, 1, 0, 0, "Ball", "FF", 95.0, batter="Michael Busch"),
        _pitch(3, 2, 1, 0, "Ball", "FF", 95.0, batter="Michael Busch"),
    ]
    by_reader = {
        "A": [
            {
                "pitches": [
                    _seen(10.0, 0, 0, "called strike"),
                    # two 0-2 pitches: the graphic picks the slider
                    _seen(30.0, 0, 2, "strikeout swinging", {"type_text": "SLIDER", "mph": 87}),
                    _seen(50.0, 0, 0, "ground ball", batter="2. BREGMAN"),
                    _seen(70.0, None, None, "replay"),
                ]
            }
        ],
        "B": [
            {
                "pitches": [
                    _seen(10.5, 0, 0, "called strike"),
                    _seen(30.5, 0, 2, "swinging strike three"),
                    _seen(50.5, 0, 0, "grounder", batter="2. BREGMAN"),
                ]
            }
        ],
    }
    for p in by_reader["A"][0]["pitches"]:
        if p["release_t"] == 70.0:
            p.update(half=None, inning=None, batter_text=None)
    merged = pair_readers(by_reader)
    assert [m["A"]["release_t"] if m["A"] else None for m in merged] == [10.0, 30.0, 50.0, 70.0]
    det = match_detections(merged, pitches)
    assert det[0]["match_status"] == "unique" and det[0]["match"]["pitch_number"] == 1
    assert det[1]["match_status"] == "resolved_by_pitch_graphic"
    assert det[1]["match"]["pitch_number"] == 4 and det[1]["pitch_graphic"]["agrees"] is True
    assert det[2]["match"]["at_bat_number"] == 2 and det[2]["outcome_consistent"] is True
    assert det[3]["match_status"] == "no_scoreboard" and not usable(det[3])
    # without the graphic, the outcome breaks the 0-2 tie
    by_reader["A"][0]["pitches"][1]["post_pitch_graphic"] = None
    det = match_detections(pair_readers(by_reader), pitches)
    assert det[1]["match_status"] == "resolved_by_outcome" and det[1]["match"]["pitch_number"] == 4
    # a graphic that contradicts a unique count match is held back for the operator
    by_reader["A"][0]["pitches"][0]["post_pitch_graphic"] = {"type_text": "CHANGEUP", "mph": 85}
    det = match_detections(pair_readers(by_reader), pitches)
    assert det[0]["match_status"] == "check_graphic_conflict" and not usable(det[0])
    det = apply_resolutions(
        det,
        pitches,
        [
            {
                "release_t": 10.25,
                "action": "assign",
                "at_bat_number": 1,
                "pitch_number": 1,
                "reason": "score bug 0-0 and the batter's first pitch; graphic belongs to a replay",
            },
            {"release_t": 70.0, "action": "drop", "status": "dropped", "reason": "replay"},
        ],
    )
    assert usable(det[0]) and det[0]["resolution"]["action"] == "assign"
    with pytest.raises(ValueError):
        apply_resolutions(det, pitches, [{"release_t": 30.25, "action": "drop", "reason": ""}])


def _reader(frame, mitt, front=((600, 470), (640, 470)), unc=8):
    return {
        "setup_frame": frame,
        "mitt_center": list(mitt),
        "setup_plate_front": {"left_end": list(front[0]), "right_end": list(front[1])},
        "setup_uncertainty_pixels": unc,
        "release_frame": frame + 10,
        "setup_reason": None,
    }


def test_consensus_rule_is_the_849843_rule():
    s = decide_setup(_reader(100, (620, 400)), _reader(100, (624, 404)))
    assert s["status"] == "estimated" and s["mitt"] == [622.0, 402.0] and s["unc"] == 8
    s = decide_setup(_reader(100, (620, 400)), _reader(103, (626, 400)))
    assert s["status"] == "estimated" and s["mitt"] == [620, 400] and s["frame_index"] == 100
    s = decide_setup(_reader(100, (620, 400)), _reader(100, (640, 400)))
    assert s["status"] == "unavailable" and s["reason"] == "readers_disagree_on_mitt"
    lone = {"setup_frame": None, "setup_reason": "glove_hidden_by_batter", "release_frame": 130}
    s = decide_setup(_reader(100, (620, 400)), lone)
    assert s["reason"] == "only_one_reader_found_a_setup_frame" and s["frame_index"] == 100
    s = decide_setup(lone, dict(lone, setup_reason="cut_after_release"))
    assert s["reason"] == "glove_hidden_by_batter" and s["frame_index"] == 130


def test_plan_roles_and_report_blocks(tmp_path):
    assert game_role(747139) == "development" and game_role(849843) == "development"
    assert game_role(849845) == "evaluation" and game_role(823407) == "evaluation"
    assert game_role(1) == "unplanned"
    plan = {
        "development_games": [{"game_pk": 1, "broadcast": "X"}],
        "evaluation_games": {"games": [{"game_pk": 2}, {"game_pk": 3}]},
    }

    def points(g, statuses):
        frames = [{"status": s} for s in statuses]
        (tmp_path / f"game_{g}_intent_points_v0.json").write_text(
            json.dumps({"frames": frames}), encoding="utf-8"
        )

    points(1, ["estimated", "unavailable"])
    points(2, ["estimated"] * 3 + ["unavailable"])
    check = {
        "frames_labeled": 4,
        "availability": {
            "both_marked": 3,
            "both_abstained": 1,
            "assistant_only": 0,
            "person_only": 0,
            "person_undecided": 0,
        },
        "per_frame": [
            {
                "pitch_id": "2:1:1",
                "assistant_status": "estimated",
                "person_status": "marked",
                "mitt_px_diff": [3, 4],
                "mitt_feet_diff_same_plate": [0.1, 0.1],
                "output_feet_diff": [0.3, 0.4],
            },
            {
                "pitch_id": "2:2:1",
                "assistant_status": "estimated",
                "person_status": "marked",
                "mitt_px_diff": [6, 8],
                "mitt_feet_diff_same_plate": [0.2, -0.2],
                "output_feet_diff": [-0.6, 0.8],
            },
            {
                "pitch_id": "2:3:1",
                "assistant_status": "estimated",
                "person_status": "marked",
                "mitt_px_diff": [0, 1],
                "output_feet_diff": [0.0, -0.1],
            },
            {"pitch_id": "2:4:1", "assistant_status": "unavailable", "person_status": "hidden"},
        ],
    }
    (tmp_path / "game_2_intent_setup_check_v0.json").write_text(json.dumps(check), encoding="utf-8")
    report = build_report(plan, tmp_path)
    assert report["development_games"][0]["person"]["status"] == "awaiting_labels"
    e2, e3 = report["evaluation_games"]
    assert e3["status"] == "not_processed"
    assert e2["assistant"]["abstention_rate"] == pytest.approx(0.25)
    assert e2["person"]["person_abstention_rate"] == pytest.approx(0.25)
    assert e2["person"]["mitt_reading_pixels"]["distance"] == {"n": 3, "median": 5.0, "p90": 10.0}
    assert e2["person"]["output_vs_person_feet"]["distance"]["median"] == pytest.approx(0.5)
    out_x = e2["person"]["output_vs_person_feet"]["x_published_minus_person"]
    assert out_x["signed"]["mean"] == pytest.approx(-0.1) and out_x["absolute"]["median"] == 0.3
    assert e2["person"]["mitt_reading_feet_same_plate"]["distance"]["n"] == 2
    assert e2["person"]["person_abstention_reasons"] == {"hidden": 1}
    worst = e2["person"]["failure_cases"]["largest_mitt_pixel_differences"]
    assert worst[0]["pitch_id"] == "2:2:1" and worst[0]["distance_px"] == 10.0
    assert e2["person"]["failure_cases"]["availability_disagreements"] == []
    pooled = report["evaluation_pooled"]
    assert pooled["person_marked"] == 3 and pooled["games"] == [2]
    assert pooled["availability"]["both_marked"] == 3
    assert pooled["assistant"]["abstention_rate"] == pytest.approx(0.25)
    assert pooled["person_abstention_rate"] == pytest.approx(0.25)
    assert pooled["person_abstention_reasons"] == {"hidden": 1}
    cases = {c["role"]: c["pitch_id"] for c in e2["person"]["example_cases"]["cases"]}
    assert cases == {
        "representative": "2:1:1",
        "best (success, not typical)": "2:3:1",
        "worst (failure)": "2:2:1",
    }
    m3 = report["m3_requirement"]
    assert m3["met"] is False and m3["fallback"]["triggered"] is False  # game 3 not labeled
    # both planned games labeled but short of 50 -> the plan's fallback game is next, in order
    points(3, ["estimated"])
    one = dict(check, frames_labeled=1, per_frame=check["per_frame"][:1])
    one["availability"] = dict(check["availability"], both_marked=1, both_abstained=0)
    (tmp_path / "game_3_intent_setup_check_v0.json").write_text(json.dumps(one), encoding="utf-8")
    m3 = build_report(plan, tmp_path)["m3_requirement"]
    assert m3["games_with_person_marks"] == 2 and m3["person_marked"] == 4 and m3["met"] is False
    assert m3["fallback"] == dict(
        m3["fallback"], triggered=True, games_added=[849849], next_game_to_process=849849
    )
    assert game_role(849849) == "evaluation_fallback" and game_role(849851) == "evaluation_fallback"


def test_fallback_games_are_the_plans_and_unmeasured_camera_means_are_withheld(tmp_path):
    from intent.accuracy_report import game_block
    from intent.human_labels import FALLBACK_GAMES

    plan = json.loads(
        (
            Path(__file__).resolve().parents[1] / "docs/results/mlb_p0/intent_eval_plan_v0.json"
        ).read_text(encoding="utf-8")
    )
    text = plan["evaluation_games"]["fallback"]
    assert text.index(str(FALLBACK_GAMES[0])) < text.index(str(FALLBACK_GAMES[1]))
    (tmp_path / "game_5_intent_points_v0.json").write_text(
        json.dumps({"frames": [{"status": "estimated"}]}), encoding="utf-8"
    )
    cal = {
        "rms_error_feet": None,
        "error_status": "unmeasured",
        "min_pitches": 10,
        "end_to_end_check": {
            "pitches_used": 2,
            "by_depth_y": {"-1.0": {"x": {"mean_signed_feet": -0.4}, "z": {"mean_signed_feet": 0}}},
        },
    }
    (tmp_path / "game_5_intent_plate_calibration_v0.json").write_text(
        json.dumps(cal), encoding="utf-8"
    )
    camera = game_block({"game_pk": 5}, tmp_path)[0]["camera_check_catch_vs_statcast"]
    assert camera["x_mean_signed_feet"] is None and camera["signed_means_note"]


def test_service_check_runs_a_validator_file_with_the_sibling_imports_stubbed(tmp_path):
    from intent.service_check import check_file, load_validator

    validator = tmp_path / "intent.py"
    validator.write_text(
        "from .domain import ZONES\n"
        "from .video_lab import _number\n"
        "def validate_intent_estimate(doc):\n"
        "    _number(doc['x'], 'x')\n"
        "    if doc['x'] < 0:\n"
        "        raise ValueError('negative')\n"
        "    return doc\n",
        encoding="utf-8",
    )
    jsonl = tmp_path / "a.jsonl"
    jsonl.write_text(
        '{"pitch_id": "1:1:1", "x": 1, "deepest_frame": "plate_feet"}\n'
        '{"pitch_id": "1:1:2", "x": -1, "deepest_frame": null}\n',
        encoding="utf-8",
    )
    result = check_file(load_validator(validator), jsonl)
    assert result["lines"] == 2 and result["passed"] == 1
    assert result["failures"] == [{"pitch_id": "1:1:2", "error": "negative"}]
    assert "observer_app" not in sys.modules

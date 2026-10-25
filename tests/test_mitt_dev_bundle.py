"""CV-32 development bundle: fixed selection rule and presentation-time frame verification."""

import pytest

from intent import mitt_dev_bundle as bundle


def annotation(ab, pn, status="annotated", decision=10.0, release=13.0):
    return {
        "game_pk": 747139,
        "at_bat_number": ab,
        "pitch_number": pn,
        "play_id": f"p{ab}-{pn}",
        "status": status,
        "decision_seconds": decision if status == "annotated" else None,
        "release_seconds": release if status == "annotated" else None,
        "uncertainty_seconds": 0.2,
    }


def test_selection_is_ordered_from_the_first_key_and_keeps_exclusions_in_the_denominator():
    rows = [
        annotation(4, 1),
        annotation(2, 3),
        annotation(3, 2, status="unavailable"),
        annotation(3, 1),
        annotation(3, 3, decision=5.0, release=5.0),
        annotation(5, 1),
    ]
    rule = {**bundle.RULE, "count": 4}
    chosen = bundle.select_pitches(rows, rule)
    assert [c["pitch_id"] for c in chosen] == [
        "747139:3:1",
        "747139:3:2",
        "747139:3:3",
        "747139:4:1",
    ]
    assert [c["exclusion_reason"] for c in chosen] == [
        None,
        "timing_unavailable_in_annotations",
        "release_not_after_decision",
        None,
    ]
    with pytest.raises(ValueError):
        bundle.select_pitches(rows, {**bundle.RULE, "count": 6})
    with pytest.raises(ValueError):
        bundle.select_pitches(rows + [annotation(3, 1)], rule)


def test_window_keeps_the_grid_plus_the_decision_and_release_frames():
    item = {"decision_seconds": 249.75, "release_seconds": 255.9}
    win = bundle.window(item)
    assert win["decision_index"] == 14970  # the index v0 recorded; v0 read D+1 for this pitch
    assert win["first_index"] == bundle.frame_at(248.75)
    assert win["last_index"] == bundle.frame_at(256.4)
    grid = [i for i, r in win["roles"].items() if "grid" in r]
    assert grid == list(range(win["first_index"], win["last_index"] + 1, 6))
    assert "decision" in win["roles"][win["decision_index"]]
    assert "release_nearest" in win["roles"][win["release_index"]]
    assert list(win["roles"]) == sorted(win["roles"])


def test_showinfo_parsing_maps_presentation_time_to_whole_source_frames():
    log = "\n".join(
        [
            "[showinfo@all @ 000001926f014f00] n:   0 pts:14976962 pts_time:249.616033 duration:1001",
            "[showinfo@all @ 000001926f014f00]   side data - SMPTE 12-1 timecode: 00:04:09:37",
            "[showinfo@kept @ 000001926f015340] n:   0 pts:14976962 pts_time:249.616033",
            "[showinfo@all @ 000001926f014f00] n:   1 pts:14977963 pts_time:249.632717",
        ]
    )
    assert bundle.parse_showinfo(log) == {"all": [14962, 14963], "kept": [14962]}
    with pytest.raises(ValueError):
        bundle.parse_showinfo("[showinfo@all @ 0x1] n:   0 pts:14976963 pts_time:249.6")


def test_decode_check_rejects_gaps_partial_coverage_and_unexpected_kept_frames():
    win = {
        "first_index": 10,
        "last_index": 16,
        "roles": {10: ["grid"], 13: ["decision"], 16: ["grid"]},
    }
    good = {"all": list(range(5, 20)), "kept": [10, 13, 16]}
    assert bundle.verify_decode(good, win) == {
        "decoded_first": 5,
        "decoded_last": 19,
        "window_covered": True,
        "index_gaps_in_window": 0,
        "kept_equals_expected": True,
    }
    gap = {"all": [9, 10, 11, 13, 14, 15, 16, 17], "kept": [10, 13, 16]}
    assert bundle.verify_decode(gap, win)["index_gaps_in_window"] == 1
    short = {"all": list(range(11, 20)), "kept": [13, 16]}
    check = bundle.verify_decode(short, win)
    assert not check["window_covered"] and not check["kept_equals_expected"]


def test_selector_expression_escapes_filtergraph_commas():
    win = {"first_index": 10, "last_index": 16, "decision_index": 13, "release_index": 15}
    expression = bundle.select_expression(win, 6)
    assert "," not in expression.replace("\\,", "")
    command = bundle.ffmpeg_command(
        "ffmpeg", "https://example.invalid/v.mp4", win, 6, "out_%05d.jpg"
    )
    assert command[command.index("-ss") + 1] == f"{float(bundle.Fraction(0) / bundle.FPS):.6f}"
    assert "-copyts" in command and command[command.index("-fps_mode") + 1] == "passthrough"


def test_rule_on_the_saved_747139_timing_gives_forty_keys_with_one_exclusion():
    timing = bundle.read_json(bundle.RESULTS / "game_747139_timing.json")
    chosen = bundle.select_pitches(timing["annotations"])
    assert len(chosen) == 40
    assert (chosen[0]["pitch_id"], chosen[-1]["pitch_id"]) == ("747139:3:1", "747139:12:2")
    assert [c["pitch_id"] for c in chosen if not c["included"]] == ["747139:5:5"]
    old = bundle.existing_method(chosen)
    assert old["status_counts"] == {"estimated": 38, "unavailable": 1, "no_output_row": 1}
    assert (
        sum(1 for r in old["rows"] if r.get("v0_recorded_index_equals_bundle_decision_index")) == 39
    )

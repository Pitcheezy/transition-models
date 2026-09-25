"""The SNY scoreboard reader abstains instead of guessing, and reads a synthetic bug correctly."""

import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw

from src.vision import sny_scoreboard as sb

ROOT = Path(__file__).resolve().parents[1]
NAVY = (18, 40, 96)
WHITE = (255, 255, 255)
GOLD = (232, 196, 110)


def synthetic_frame(
    balls="0",
    strikes="1",
    inning="1",
    top=True,
    outs=1,
    runners=(True, False, False),
    away="0",
    home="0",
    panel=True,
):
    """Draw a bug that follows the measured SNY layout with the default bitmap font."""
    image = Image.new("RGB", (1280, 720), (60, 120, 60))
    draw = ImageDraw.Draw(image)
    if panel:
        draw.rectangle((55, 28, 305, 108), fill=NAVY)
        draw.rectangle((55, 32, 305, 33), fill=WHITE)  # the bug's white top border line
    else:
        return np.asarray(image)

    def digits(text, name):
        x0, y0, x1, y1 = sb.WINDOWS[name]
        width = 7 * len(text)
        x = x0 + (x1 - x0 - width) // 2
        for i, ch in enumerate(text):
            # 5x9 block digits: solid rectangle with a hole for 0, bar for 1, others distinct
            gx, gy = x + 7 * i, y0 + 6
            if ch == "0":
                draw.rectangle((gx, gy, gx + 5, gy + 10), fill=WHITE)
                draw.rectangle((gx + 2, gy + 2, gx + 3, gy + 8), fill=NAVY)
            elif ch == "1":
                draw.rectangle((gx + 2, gy, gx + 3, gy + 10), fill=WHITE)
            elif ch == "2":
                draw.rectangle((gx, gy, gx + 5, gy + 1), fill=WHITE)
                draw.rectangle((gx + 4, gy, gx + 5, gy + 5), fill=WHITE)
                draw.rectangle((gx, gy + 4, gx + 5, gy + 5), fill=WHITE)
                draw.rectangle((gx, gy + 5, gx + 1, gy + 10), fill=WHITE)
                draw.rectangle((gx, gy + 9, gx + 5, gy + 10), fill=WHITE)
            elif ch == "3":
                draw.rectangle((gx, gy, gx + 5, gy + 1), fill=WHITE)
                draw.rectangle((gx + 4, gy, gx + 5, gy + 10), fill=WHITE)
                draw.rectangle((gx, gy + 4, gx + 5, gy + 5), fill=WHITE)
                draw.rectangle((gx, gy + 9, gx + 5, gy + 10), fill=WHITE)
            elif ch == "7":
                draw.rectangle((gx, gy, gx + 5, gy + 1), fill=WHITE)
                draw.rectangle((gx + 4, gy, gx + 5, gy + 10), fill=WHITE)

    digits(balls, "balls")
    digits(strikes, "strikes")
    digits(inning, "inning")
    digits(away, "away_score")
    digits(home, "home_score")
    x0, y0, x1, y1 = sb.WINDOWS["arrow"]
    cx = (x0 + x1) // 2
    if top:
        draw.polygon([(cx, y0 + 3), (x0 + 1, y1 - 4), (x1 - 2, y1 - 4)], fill=WHITE)
    else:
        draw.polygon([(x0 + 1, y0 + 3), (x1 - 2, y0 + 3), (cx, y1 - 4)], fill=WHITE)
    for i, name in enumerate(("out_1", "out_2")):
        x0, y0, x1, y1 = sb.WINDOWS[name]
        draw.ellipse((x0, y0, x1, y1), fill=GOLD if i < outs else NAVY, outline=WHITE)
    for filled, name in zip(runners, ("runner_on_1b", "runner_on_2b", "runner_on_3b"), strict=True):
        x0, y0, x1, y1 = sb.WINDOWS[name]
        draw.rectangle((x0, y0, x1, y1), fill=GOLD if filled else NAVY, outline=WHITE)
    return np.asarray(image)


def templates_from(frame, labels):
    white, _, _ = sb.masks(frame)
    templates = sb.DigitTemplates()
    for name, value in labels.items():
        pairs = sb.glyphs_for_label(white, name, value)
        assert pairs is not None, name
        for digit, glyph in pairs:
            templates.add(digit, glyph)
    return templates


def test_reads_synthetic_bug_and_abstains_on_unknown_digits():
    source = synthetic_frame(balls="2", strikes="1", inning="3", away="0", home="1")
    templates = templates_from(
        source, {"balls": 2, "strikes": 1, "inning": 3, "away_score": 0, "home_score": 1}
    )
    assert set(templates.templates) == {"0", "1", "2", "3"}
    probe = synthetic_frame(
        balls="3",
        strikes="2",
        inning="1",
        top=False,
        outs=2,
        runners=(False, True, True),
        away="1",
        home="0",
    )
    fields = sb.read_scoreboard(probe, templates)
    assert fields == {
        "balls": 3,
        "strikes": 2,
        "outs": 2,
        "runner_on_1b": False,
        "runner_on_2b": True,
        "runner_on_3b": True,
        "inning": 1,
        "inning_topbot": "Bot",
        "home_score": 0,
        "away_score": 1,
    }
    unknown = synthetic_frame(balls="7", strikes="0", inning="1")
    fields = sb.read_scoreboard(unknown, templates)
    assert fields["balls"] is None and fields["strikes"] == 0 and fields["inning_topbot"] == "Top"
    assert (
        fields["outs"] == 1 and fields["runner_on_1b"] is True and fields["runner_on_2b"] is False
    )


def test_no_bug_and_no_templates_abstain_everywhere():
    empty = sb.DigitTemplates()
    fields = sb.read_scoreboard(synthetic_frame(panel=False), empty)
    assert all(v is None for v in fields.values())
    # a navy panel full of white text without the top border line (line-score graphic) is not
    # the count bug: everything abstains, including the structural fields
    frame = synthetic_frame().copy()
    frame[32:34, 55:306] = NAVY
    frame[40:100:4, 140:290] = WHITE
    fields = sb.read_scoreboard(frame, empty)
    assert all(v is None for v in fields.values())
    fields = sb.read_scoreboard(synthetic_frame(), empty)
    assert all(fields[name] is None for name in sb.DIGIT_FIELDS)
    assert fields["outs"] == 1 and fields["inning_topbot"] == "Top"


def test_template_round_trip_and_schema_guard(tmp_path):
    source = synthetic_frame(balls="1", strikes="0")
    templates = templates_from(source, {"balls": 1, "strikes": 0})
    document = templates.to_json()
    path = tmp_path / "t.json"
    path.write_text(json.dumps(document), encoding="utf-8")
    loaded = sb.DigitTemplates.from_json(json.loads(path.read_text(encoding="utf-8")))
    assert set(loaded.templates) == {"0", "1"}
    white, _, _ = sb.masks(synthetic_frame(balls="0", strikes="1"))
    assert sb.read_number(white, "balls", loaded) == 0
    assert sb.read_number(white, "strikes", loaded) == 1
    with pytest.raises(ValueError):
        sb.DigitTemplates.from_json({**document, "schema": "other"})
    with pytest.raises(ValueError):
        sb.DigitTemplates.from_json({**document, "glyph_shape": [4, 4]})


def test_partial_fill_and_out_order_abstain():
    frame = synthetic_frame(outs=1)
    _, gold, _ = sb.masks(frame)
    # second circle filled without the first is not a valid out display
    x0, y0, x1, y1 = sb.WINDOWS["out_2"]
    gold = gold.copy()
    gold[y0:y1, x0:x1] = True
    ax0, ay0, ax1, ay1 = sb.WINDOWS["out_1"]
    gold[ay0:ay1, ax0:ax1] = False
    assert sb.read_outs(gold) is None
    # a half-filled diamond is uncertain
    rx0, ry0, rx1, ry1 = sb.WINDOWS["runner_on_2b"]
    gold[ry0:ry1, rx0:rx1] = False
    gold[ry0 : ry0 + (ry1 - ry0) // 6, rx0:rx1] = True
    assert sb.read_runners(gold)["runner_on_2b"] is None


REAL = ROOT / "outputs" / "frames"


@pytest.mark.skipif(
    not (REAL / "evalset_76.00.jpg").exists(), reason="eval-set frames not grabbed locally"
)
def test_real_frames_structural_fields_match_labels():
    evalset = json.loads(
        (ROOT / "docs/results/mlb_p0/game_747139_scoreboard_evalset.json").read_text(
            encoding="utf-8-sig"
        )
    )
    empty = sb.DigitTemplates()
    checked = 0
    for entry in evalset["entries"]:
        path = REAL / f"evalset_{entry['frame_seconds']:.2f}.jpg"
        if not path.exists():
            continue
        fields = sb.read_scoreboard(np.asarray(Image.open(path).convert("RGB")), empty)
        for name in ("outs", "runner_on_1b", "runner_on_2b", "runner_on_3b", "inning_topbot"):
            assert fields[name] in (None, entry["labels"][name]), (
                entry["pitch_number"],
                name,
                fields[name],
            )
        checked += 1
    assert checked > 0


@pytest.mark.parametrize("version", ["v1", "v2", "v3"])
def test_stored_heldout_score_excludes_its_template_plate_appearances(version):
    """A stored held-out score must exclude every plate appearance its templates were cut from."""
    results = ROOT / "docs/results/mlb_p0"
    templates = json.loads(
        (results / f"sny_digit_templates_{version}.json").read_text(encoding="utf-8")
    )
    sb.DigitTemplates.from_json(templates)
    sources = sorted(templates["source"]["template_plate_appearances"])
    score = json.loads(
        (results / f"game_747139_scoreboard_ocr_{version}.json").read_text(encoding="utf-8")
    )
    assert sorted(score["holdout"]["excluded_plate_appearances"]) == sources
    assert score["all_fields"]["wrong"] == 0
    if version == "v2":
        assert "3" in templates["templates"]
        comparison = json.loads(
            (results / "game_747139_scoreboard_ocr_v2_comparison.json").read_text(encoding="utf-8")
        )
        assert comparison["heldout_identical_for_v1_and_v2"] is True
        assert sorted(comparison["heldout_excluded_pas"]) == sources
        assert comparison["preregistration"]["decided_before_any_v2_prediction"] is True
    # v1/v2 documents carry no reader options: they take the default code path
    if version in ("v1", "v2"):
        assert "reader_options" not in templates
        assert sb.DigitTemplates.from_json(templates).reader_options == {}
    if version == "v3":
        assert sources == [1, 2, 9, 18, 29] and "4" in templates["templates"]
        assert templates["reader_options"] == V3_READER_OPTIONS
        assert sb.DigitTemplates.from_json(templates).reader_options == V3_READER_OPTIONS
        comparison = json.loads(
            (results / "game_747139_scoreboard_ocr_v3_comparison.json").read_text(encoding="utf-8")
        )
        assert sorted(comparison["excluded_pas"]) == sources
        assert comparison["preregistration"]["reader_options"] == V3_READER_OPTIONS
        # the 94-pitch exclude-pas set is mixed (75 held-out + 19 seen/diagnosed): it is never
        # called held-out, and the held-out headline is reported on the 75 alone
        mixed = comparison["exclude_pas_scored_set_94"]
        assert mixed["identical_for_v2_and_v3"] is True
        assert "not the held-out" in mixed["label"] and mixed["composition"] == {
            "heldout_headline_75": 75,
            "seen_diagnosed_fully_evaluable": 19,
        }
        assert (
            mixed["all_fields"]["v2"]["evaluable"] == mixed["all_fields"]["v3"]["evaluable"] == 94
        )
        assert mixed["wrong_reads_v3"] == [] and comparison["wrong_reads_v3_insample"] == []
        headline = comparison["heldout_headline_75"]
        assert len(headline["pitches"]) == 75 and headline["result"]["pitches"] == 75
        assert headline["result"]["v3_wrong_fields"] == 0 and headline["wrong_reads_v3"] == []
        assert (
            headline["result"]["v3_all_fields_correct"]
            + headline["result"]["v3_pitches_with_new_abstention"]
            == 75
        )
        assert not any(k.startswith("heldout") for k in comparison if k != "heldout_headline_75")


# ---- opt-in reader options (F-3c, OCR v3) ----------------------------------------------------

V3_READER_OPTIONS = {
    "top_line_gate": {"aggregate": "max_row", "threshold": 0.6},
    "border_sliver_max_width": 2,
}


def test_reader_options_absent_or_empty_is_the_default_path():
    """A v1/v2-style document (no ``reader_options`` key) must behave exactly like before."""
    source = synthetic_frame(balls="2", strikes="1", inning="3", away="0", home="1")
    plain = templates_from(
        source, {"balls": 2, "strikes": 1, "inning": 3, "away_score": 0, "home_score": 1}
    )
    document = plain.to_json()
    assert "reader_options" not in document  # v1/v2 file layout is unchanged
    loaded = sb.DigitTemplates.from_json(json.loads(json.dumps(document)))
    assert loaded.reader_options == {}
    explicit = sb.DigitTemplates(document["templates"], {})
    assert explicit.reader_options == {} and "reader_options" not in explicit.to_json()
    frames = [
        synthetic_frame(balls="3", strikes="2", inning="1", top=False, outs=2, away="1"),
        synthetic_frame(balls="7", strikes="0", inning="1"),
        synthetic_frame(panel=False),
    ]
    for frame in frames:
        expected = sb.read_scoreboard(frame, plain)
        assert sb.read_scoreboard(frame, loaded) == expected
        assert sb.read_scoreboard(frame, explicit) == expected
    # the same glyphs/gate under the v3 options: identical on frames that need neither option
    with_options = sb.DigitTemplates(document["templates"], V3_READER_OPTIONS)
    for frame in frames:
        assert sb.read_scoreboard(frame, with_options) == sb.read_scoreboard(frame, plain)
    # function defaults reproduce the module thresholds
    white, _, navy = sb.masks(frames[0])
    assert sb.bug_present(navy, white) is sb.bug_present(navy, white, {})
    assert sb.top_line_passes(white) is True
    glyph_window = sb.window(white, "balls")
    assert len(sb.segment_glyphs(glyph_window)) == len(sb.segment_glyphs(glyph_window, {}))


def test_reader_options_round_trip_and_validation():
    templates = sb.DigitTemplates({"1": [np.zeros(sb.GLYPH_SHAPE)]}, V3_READER_OPTIONS)
    document = templates.to_json()
    assert document["reader_options"] == V3_READER_OPTIONS
    assert sb.DigitTemplates.from_json(document).reader_options == V3_READER_OPTIONS
    assert sb.validate_reader_options(None) == {}
    assert sb.validate_reader_options({"border_sliver_max_width": 0}) == {
        "border_sliver_max_width": 0
    }
    bad = [
        {"probe_edge_trim_max_pixels": 1},  # not a v3 option
        {"top_line_gate": {"aggregate": "median", "threshold": 0.6}},
        {"top_line_gate": {"aggregate": "max_row", "threshold": 1.5}},
        {"top_line_gate": {"aggregate": "max_row", "rows": [33]}},
        {"top_line_gate": "max_row"},
        {"border_sliver_max_width": -1},
        {"border_sliver_max_width": 2.5},
        {"border_sliver_max_width": True},
        ["top_line_gate"],
    ]
    for options in bad:
        with pytest.raises(ValueError):
            sb.validate_reader_options(options)
        with pytest.raises(ValueError):
            sb.DigitTemplates.from_json({**document, "reader_options": options})


def test_top_line_gate_max_row_passes_a_single_bright_row_only():
    """Camera-cut frame: the white border sits on one of the two top_line rows (11/2, 19/2)."""
    source = synthetic_frame(balls="1", strikes="2", inning="3")
    labels = {"balls": 1, "strikes": 2, "inning": 3, "away_score": 0, "home_score": 0}
    plain = templates_from(source, labels)
    max_row = sb.DigitTemplates(plain.to_json()["templates"], V3_READER_OPTIONS)
    frame = synthetic_frame(balls="1", strikes="2", inning="3").copy()
    x0, y0, x1, y1 = sb.WINDOWS["top_line"]
    frame[y0, :, :] = NAVY  # row 32 dark, row 33 still white -> mean 0.5, max row 1.0
    white, _, navy = sb.masks(frame)
    assert 0.4 < float(sb.window(white, "top_line").mean()) < sb.TOP_LINE_WHITE
    assert sb.bug_present(navy, white) is False
    assert sb.bug_present(navy, white, V3_READER_OPTIONS) is True
    assert all(v is None for v in sb.read_scoreboard(frame, plain).values())
    fields = sb.read_scoreboard(frame, max_row)
    assert fields["balls"] == 1 and fields["strikes"] == 2 and fields["inning"] == 3
    assert fields["outs"] == 1 and fields["inning_topbot"] == "Top"
    # both rows half white: mean 0.5 and max row 0.5 -> neither gate passes
    frame[y0:y1, x0 + (x1 - x0) // 2 : x1, :] = NAVY
    frame[y0, x0:x1, :] = frame[y0 + 1, x0:x1, :]
    white, _, navy = sb.masks(frame)
    assert float(sb.window(white, "top_line").mean(axis=1).max()) < 0.6
    assert sb.bug_present(navy, white, V3_READER_OPTIONS) is False
    # an explicit mean aggregate is the default test with its own threshold
    lenient = {"top_line_gate": {"aggregate": "mean", "threshold": 0.4}}
    mean_white = float(sb.window(white, "top_line").mean())
    assert sb.top_line_passes(white, lenient) is (mean_white >= 0.4)
    # the navy and panel-white tests are untouched by the option
    no_panel = synthetic_frame(panel=False)
    white, _, navy = sb.masks(no_panel)
    assert sb.bug_present(navy, white, V3_READER_OPTIONS) is False


def test_border_sliver_drops_only_narrow_edge_touching_groups():
    """A 2-px border column entering the inning window after a wipe (4/1, 11/1)."""
    source = synthetic_frame(inning="2")
    labels = {"balls": 0, "strikes": 1, "inning": 2, "away_score": 0, "home_score": 0}
    plain = templates_from(source, labels)
    with_sliver = sb.DigitTemplates(plain.to_json()["templates"], V3_READER_OPTIONS)
    frame = synthetic_frame(inning="2").copy()
    x0, y0, x1, y1 = sb.WINDOWS["inning"]
    frame[y0:y1, x1 - 2 : x1, :] = WHITE  # 2-px group at the window's last two columns
    white, _, _ = sb.masks(frame)
    window = sb.window(white, "inning")
    assert len(sb.segment_glyphs(window)) == 2
    assert len(sb.segment_glyphs(window, V3_READER_OPTIONS)) == 1
    # default path: two glyphs; the synthetic 2-px sliver even matches the 2-px synthetic "1"
    assert sb.read_scoreboard(frame, plain)["inning"] in (None, 21)
    assert sb.read_scoreboard(frame, with_sliver)["inning"] == 2
    # a sliver on the LEFT edge is dropped too; a 3-px edge group is a glyph and stays
    left = synthetic_frame(inning="2").copy()
    left[y0:y1, x0 : x0 + 2, :] = WHITE
    assert len(sb.segment_glyphs(sb.window(sb.masks(left)[0], "inning"), V3_READER_OPTIONS)) == 1
    wide = synthetic_frame(inning="2").copy()
    wide[y0:y1, x1 - 3 : x1, :] = WHITE
    assert len(sb.segment_glyphs(sb.window(sb.masks(wide)[0], "inning"), V3_READER_OPTIONS)) == 2
    # a narrow group that does not touch an edge is a digit (the synthetic "1" is 2 px wide)
    one = synthetic_frame(strikes="1")
    strikes = sb.window(sb.masks(one)[0], "strikes")
    assert len(sb.segment_glyphs(strikes)) == 1
    assert len(sb.segment_glyphs(strikes, V3_READER_OPTIONS)) == 1
    assert sb.read_scoreboard(one, with_sliver)["strikes"] == 1
    # options never apply when templates are cut: glyphs_for_label sees the sliver
    assert sb.glyphs_for_label(white, "inning", 2) is None
    # width 0 (or the key absent) drops nothing
    assert len(sb.segment_glyphs(window, {"border_sliver_max_width": 0})) == 2


@pytest.mark.skipif(
    not (REAL / "evalset_76.00.jpg").exists(), reason="eval-set frames not grabbed locally"
)
def test_templates_command_writes_reader_options_only_when_asked(tmp_path):
    import subprocess
    import sys

    script = ROOT / "scripts" / "66_sny_scoreboard_ocr.py"
    base = [sys.executable, str(script), "templates", "--template-pas", "9", "--no-grab"]
    plain, with_options = tmp_path / "plain.json", tmp_path / "options.json"
    flag = ["--reader-options", json.dumps(V3_READER_OPTIONS)]
    for output, extra in ((plain, []), (with_options, flag)):
        run = subprocess.run(
            [*base, *extra, "--output", str(output)],
            cwd=ROOT,
            capture_output=True,
            text=True,
            encoding="utf-8",
        )
        assert run.returncode == 0, run.stderr
    a = json.loads(plain.read_text(encoding="utf-8"))
    b = json.loads(with_options.read_text(encoding="utf-8"))
    assert "reader_options" not in a
    assert b["reader_options"] == V3_READER_OPTIONS
    assert a["templates"] == b["templates"] and a["source"] == b["source"]  # same glyphs
    assert list(b) == ["schema", "glyph_shape", "templates", "reader_options", "source"]
    bad = subprocess.run(
        [*base, "--reader-options", '{"probe_edge_trim_max_pixels": 1}', "--output", str(plain)],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert bad.returncode == 2 and "Unknown reader option" in bad.stderr

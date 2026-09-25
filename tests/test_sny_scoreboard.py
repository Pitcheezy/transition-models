"""The SNY scoreboard reader abstains instead of guessing, and reads a synthetic bug correctly."""

import hashlib
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
    # Structural fields do not use templates, so the default reader reads them like v2; the
    # v2 entries of the known-misread register are the only wrong reads allowed here.
    register = json.loads(
        (ROOT / "docs/results/mlb_p0/game_747139_scoreboard_known_misreads.json").read_text(
            encoding="utf-8"
        )
    )
    structural = ("outs", "runner_on_1b", "runner_on_2b", "runner_on_3b", "inning_topbot")
    listed = {
        (m["at_bat_number"], m["pitch_number"], m["field"]): m["read"]
        for m in register["misreads"]
        if "v2" in m["versions"] and m["field"] in structural
    }
    empty = sb.DigitTemplates()
    checked, found, expected = 0, {}, {}
    for entry in evalset["entries"]:
        path = REAL / f"evalset_{entry['frame_seconds']:.2f}.jpg"
        if not path.exists():
            continue
        fields = sb.read_scoreboard(np.asarray(Image.open(path).convert("RGB")), empty)
        pitch = (entry["at_bat_number"], entry["pitch_number"])
        for name in structural:
            if fields[name] not in (None, entry["labels"][name]):
                found[(*pitch, name)] = fields[name]
            if (*pitch, name) in listed:
                expected[(*pitch, name)] = listed[(*pitch, name)]
        checked += 1
    assert checked > 0
    assert found == expected


@pytest.mark.parametrize("version", ["v1", "v2", "v3", "v4"])
def test_stored_heldout_score_excludes_its_template_plate_appearances(version):
    """A stored exclude-pas score must exclude every plate appearance its templates were cut from.

    Held-out for v1/v2; a mixed set for v3 and a DEVELOPMENT set (0 held-out pitches) for v4,
    see ``ocr_reports.SCORE_SET_NOTES``.
    """
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
    if version == "v4":
        # v4 = the v3 template document plus three opt-in options; its exclude-pas score is a
        # DEVELOPMENT set (0 held-out pitches), pre-registered before any 6th-inning frame
        v3 = json.loads((results / "sny_digit_templates_v3.json").read_text(encoding="utf-8"))
        assert sources == [1, 2, 9, 18, 29] and templates["templates"] == v3["templates"]
        assert templates["source"] == v3["source"]
        assert templates["reader_options"] == V4_READER_OPTIONS
        assert sb.DigitTemplates.from_json(templates).reader_options == V4_READER_OPTIONS
        prereg = json.loads(
            (results / "game_747139_scoreboard_ocr_v4_preregistration.json").read_text(
                encoding="utf-8"
            )
        )
        assert prereg["schema"] == "mlb_scoreboard_ocr_preregistration_v1"
        assert prereg["template_plate_appearances"] == sources
        assert prereg["reader_options"] == V4_READER_OPTIONS
        # files_as_built hashes LF-normalised bytes: this tree checks out CRLF (core.autocrlf)
        # while git, CI and macOS/Linux clones hold LF, and the registered hash must verify on
        # every checkout. The templates file is the one that must stay fixed after the A-10
        # merge (predictions and score files legitimately grow by the new rows).
        assert prereg["files_as_built_hashing"].startswith("sha256 of the file bytes with CRLF")
        digest = hashlib.sha256(
            (results / "sny_digit_templates_v4.json").read_bytes().replace(b"\r\n", b"\n")
        ).hexdigest()
        assert prereg["files_as_built"]["docs/results/mlb_p0/sny_digit_templates_v4.json"] == digest
        assert prereg["files_as_built"]["docs/results/mlb_p0/sny_digit_templates_v3.json"] == (
            hashlib.sha256(
                (results / "sny_digit_templates_v3.json").read_bytes().replace(b"\r\n", b"\n")
            ).hexdigest()
        )
        assert prereg["amendments"][0]["before_any_sixth_inning_frame_was_seen"] is True
        # The development numbers are pinned in the pre-registration record, not in the live
        # score file, which the A-10 refresh rewrites with the 6th-inning rows. Whether v4 then
        # misreads is judged by the pre-registered criterion; a misread is recorded in the
        # known-misread register like any other (the register test covers every version).
        dev = prereg["development_set_results"]
        assert dev["held_out_pitches"] == 0 and dev["blind"] is False
        assert "development" in dev["label"].lower()
        registered = dev["score_file_exclude_pas_1_2_9_18_29"]
        assert registered["all_fields"] == {
            "evaluable": 122,
            "correct": 93,
            "abstained": 29,
            "wrong": 0,
        }
        assert not any(registered["per_field_wrong"].values())


# ---- opt-in reader options (F-3c, OCR v3) ----------------------------------------------------

V3_READER_OPTIONS = {
    "top_line_gate": {"aggregate": "max_row", "threshold": 0.6},
    "border_sliver_max_width": 2,
}
# F-3d, OCR v4: the v3 keys plus a per-count-window margin floor, a wider arrow window and the
# blob-slope top/bottom rule (see the module comment block).
V4_READER_OPTIONS = {
    **V3_READER_OPTIONS,
    "min_margin_by_field": {"balls": 0.1, "strikes": 0.1},
    "arrow_window": [262, 46, 279, 64],
    "topbot_rule": {"method": "blob_slope", "min_slope": 0.4, "min_rows": 6},
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
    # and under the v4 options: the synthetic arrows are not clipped and no count margin is
    # between 0.10 and 0.15, so every field reads the same
    with_v4 = sb.DigitTemplates(document["templates"], V4_READER_OPTIONS)
    for frame in frames:
        assert sb.read_scoreboard(frame, with_v4) == sb.read_scoreboard(frame, plain)
    white, _, _ = sb.masks(frames[0])
    assert sb.read_topbot(white) == sb.read_topbot(white, {}) == "Bot"
    assert sb.read_topbot(white, V4_READER_OPTIONS) == "Bot"
    glyph = sb.segment_glyphs(sb.window(white, "balls"))[0]
    assert plain.match(glyph) == plain.match(glyph, min_margin=sb.MIN_MARGIN)
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


# ---- opt-in reader options (F-3d, OCR v4) ----------------------------------------------------


def test_v4_reader_options_validation_names_the_option():
    assert sb.READER_OPTION_KEYS == (
        "top_line_gate",
        "border_sliver_max_width",
        "min_margin_by_field",
        "arrow_window",
        "topbot_rule",
    )
    assert sb.validate_reader_options(V4_READER_OPTIONS) == V4_READER_OPTIONS
    assert list(sb.validate_reader_options(dict(reversed(V4_READER_OPTIONS.items())))) == list(
        sb.READER_OPTION_KEYS
    )
    # partial documents are fine: absent keys mean the v0-v3 behaviour
    assert sb.validate_reader_options({"arrow_window": (262, 46, 279, 64)}) == {
        "arrow_window": (262, 46, 279, 64)
    }
    assert sb.validate_reader_options({"min_margin_by_field": {}}) == {"min_margin_by_field": {}}
    # a key set to null is kept but counts as absent on the read path (like the other options)
    nulls = dict.fromkeys(sb.READER_OPTION_KEYS)
    assert sb.validate_reader_options(nulls) == nulls
    bad = {
        "min_margin_by_field": [
            {"outs": 0.1},  # not a digit field
            {"balls": 1.5},
            {"balls": -0.1},
            {"balls": True},
            {"balls": "0.1"},
            [0.1],
        ],
        "arrow_window": [
            [262, 46, 279],  # three items
            [279, 46, 262, 64],  # x0 >= x1
            [262, 64, 279, 64],  # y0 >= y1
            [262, 46, 1281, 64],  # outside the frame
            [-1, 46, 279, 64],
            [262, 46, True, 64],
            [262.0, 46, 279, 64],
            "262,46,279,64",
        ],
        "topbot_rule": [
            {"method": "thirds", "min_slope": 0.4, "min_rows": 6},  # unknown method
            {"method": "blob_slope", "min_slope": 0, "min_rows": 6},
            {"method": "blob_slope", "min_slope": float("inf"), "min_rows": 6},  # not finite
            {"method": "blob_slope", "min_slope": float("nan"), "min_rows": 6},
            {"method": "blob_slope", "min_slope": -0.4, "min_rows": 6},
            {"method": "blob_slope", "min_slope": True, "min_rows": 6},
            {"method": "blob_slope", "min_slope": 0.4, "min_rows": 1},
            {"method": "blob_slope", "min_slope": 0.4, "min_rows": 6.0},
            {"method": "blob_slope", "min_slope": 0.4, "min_rows": True},
            {"method": "blob_slope", "min_slope": 0.4, "min_rows": 6, "ratio": 1.5},  # unknown
            {"method": "blob_slope", "min_rows": 6},  # min_slope missing
            {"min_slope": 0.4, "min_rows": 6},  # method missing
            "blob_slope",
        ],
    }
    document = sb.DigitTemplates({"1": [np.zeros(sb.GLYPH_SHAPE)]}, V4_READER_OPTIONS).to_json()
    for name, values in bad.items():
        for value in values:
            options = {**V4_READER_OPTIONS, name: value}
            with pytest.raises(ValueError, match=name):
                sb.validate_reader_options(options)
            with pytest.raises(ValueError, match=name):
                sb.DigitTemplates.from_json({**document, "reader_options": options})
    with pytest.raises(ValueError, match="Unknown reader option"):
        sb.validate_reader_options({**V4_READER_OPTIONS, "arrow_x0": 262})


def test_template_documents_of_every_layout_round_trip_without_new_keys():
    """v1/v2 (no reader_options), v3 (two keys) and v4 (five keys) documents keep their layout."""
    results = ROOT / "docs/results/mlb_p0"
    for version, options in (
        ("v1", None),
        ("v2", None),
        ("v3", V3_READER_OPTIONS),
        ("v4", V4_READER_OPTIONS),
    ):
        document = json.loads(
            (results / f"sny_digit_templates_{version}.json").read_text(encoding="utf-8")
        )
        expected = ["schema", "glyph_shape", "templates"]
        expected += ["reader_options"] if options else []
        assert list(document) == [*expected, "source"], version
        loaded = sb.DigitTemplates.from_json(document)
        assert loaded.reader_options == (options or {})
        again = loaded.to_json()
        assert list(again) == expected
        assert (
            again["reader_options" if options else "templates"]
            == document["reader_options" if options else "templates"]
        )
        if options:
            assert list(again["reader_options"]) == list(document["reader_options"])
        assert again["templates"] == document["templates"]


def _arrow_mask(rows_cols, stray_column=None):
    """A 720x1280 white mask holding an arrow given as (row, first col, last col) triples."""
    white = np.zeros((720, 1280), dtype=bool)
    for row, c0, c1 in rows_cols:
        white[row, c0 : c1 + 1] = True
    if stray_column is not None:  # the inning digit's 1-px left edge next to the arrow
        white[46:64, stray_column] = True
    return white


# An up arrow whose left edge (x 262-265) lies left of the default window (x 266-278): inside
# the window the base rows tie at 7 px from row 3 on, so the widest-row rule takes the first
# tie at 3/9 of the span (< 0.4) and reads Bot. Its true row widths grow 2, 4, 6, ..., 11.
CLIPPED_UP_ARROW = [
    (50, 268, 269),
    (51, 267, 270),
    (52, 266, 271),
    (53, 265, 272),
    (54, 264, 272),
    (55, 263, 272),
    (56, 262, 272),
    (57, 262, 272),
    (58, 262, 272),
]
DOWN_ARROW = [(50 + i, c0, c1) for i, (_, c0, c1) in enumerate(reversed(CLIPPED_UP_ARROW))]


def test_read_topbot_v4_options_read_a_clipped_up_arrow_with_tied_base_rows():
    white = _arrow_mask(CLIPPED_UP_ARROW, stray_column=278)
    widths = sb.window(white, "arrow").sum(axis=1)
    assert list(widths[4:13]) == [3, 5, 7, 8, 8, 8, 8, 8, 8]  # clipped + the stray column
    assert sb.read_topbot(white) == "Bot"  # the v1-v3 misread of 34/3
    assert sb.read_topbot(white, {}) == "Bot"
    assert sb.read_topbot(white, V3_READER_OPTIONS) == "Bot"
    assert sb.read_topbot(white, V4_READER_OPTIONS) == "Top"
    # the rule alone (current window) already sees the widening trend; the window alone
    # still ties the base rows at 11 and reads Top because the widest row is now at the base
    assert sb.read_topbot(white, {"topbot_rule": V4_READER_OPTIONS["topbot_rule"]}) == "Top"
    assert sb.read_topbot(white, {"arrow_window": [262, 46, 279, 64]}) == "Top"
    # the stray column is not the arrow: with the arrow gone it is the widest group but has
    # width 1 in every row (slope 0) -> abstain; without any white -> abstain
    assert sb.read_topbot(_arrow_mask([], stray_column=278), V4_READER_OPTIONS) is None
    assert sb.read_topbot(_arrow_mask([]), V4_READER_OPTIONS) is None
    assert sb.read_topbot(_arrow_mask([])) is None
    # a down arrow is Bot under both rules
    down = _arrow_mask(DOWN_ARROW, stray_column=278)
    assert sb.read_topbot(down) == "Bot"
    assert sb.read_topbot(down, V4_READER_OPTIONS) == "Bot"
    # fewer than min_rows rows abstain; a rectangle (slope 0) abstains under the slope rule
    short = _arrow_mask(CLIPPED_UP_ARROW[:5])
    assert sb.read_topbot(short, V4_READER_OPTIONS) is None
    assert (
        sb.read_topbot(
            short,
            {
                **V4_READER_OPTIONS,
                "topbot_rule": {"method": "blob_slope", "min_slope": 0.4, "min_rows": 2},
            },
        )
        == "Top"
    )
    block = _arrow_mask([(50 + i, 264, 273) for i in range(9)])
    assert sb.read_topbot(block, V4_READER_OPTIONS) is None
    # a synthetic frame's arrows are inside the default window: both rules agree
    for top in (True, False):
        white, _, _ = sb.masks(synthetic_frame(top=top))
        expected = "Top" if top else "Bot"
        assert sb.read_topbot(white) == expected
        assert sb.read_topbot(white, V4_READER_OPTIONS) == expected


def test_blob_slope_takes_the_leftmost_widest_group_and_needs_the_full_slope_both_ways():
    """Ties between equally wide column groups go left; |slope| < min_slope abstains either way."""
    rule = {"arrow_window": [262, 46, 279, 64], "topbot_rule": V4_READER_OPTIONS["topbot_rule"]}
    # two 7-px-wide groups: a down arrow on the left (x 262-268), an up arrow on the right
    # (x 270-276); the arrow blob is the leftmost of the widest groups -> Bot
    up = [(50 + i, 273 - min(i, 3), 273 + min(i, 3)) for i in range(7)]
    down = [(50 + i, 265 - (3 - min(i, 3)), 265 + (3 - min(i, 3))) for i in range(7)]
    assert sb.read_topbot(_arrow_mask(up), rule) == "Top"
    assert sb.read_topbot(_arrow_mask(down), rule) == "Bot"
    assert sb.read_topbot(_arrow_mask(up + down), rule) == "Bot"
    # mirror image: the up arrow on the left wins the tie -> Top
    mirrored = [(r, 538 - c1, 538 - c0) for r, c0, c1 in up + down]
    assert sb.read_topbot(_arrow_mask(mirrored), rule) == "Top"
    # a wider group beats a leftmost narrower one whatever their order
    assert sb.read_topbot(_arrow_mask(down + [(50 + i, 270, 278) for i in range(7)]), rule) is None
    # widths 5,5,5,4,4,4 (slope -0.257) and 4,4,4,5,5,5 (+0.257) abstain at 0.4 and read at 0.2
    shallow_down = [(50 + i, 264, 268 if i < 3 else 267) for i in range(6)]
    shallow_up = [(50 + i, 264, 267 if i < 3 else 268) for i in range(6)]
    assert sb.read_topbot(_arrow_mask(shallow_down), rule) is None
    assert sb.read_topbot(_arrow_mask(shallow_up), rule) is None
    looser = {**rule, "topbot_rule": {"method": "blob_slope", "min_slope": 0.2, "min_rows": 6}}
    assert sb.read_topbot(_arrow_mask(shallow_down), looser) == "Bot"
    assert sb.read_topbot(_arrow_mask(shallow_up), looser) == "Top"
    # widths 5,5,4,4,3,3 (slope -0.457) and its mirror clear 0.4
    steeper_down = [(50 + i, 264, 268 - i // 2) for i in range(6)]
    steeper_up = [(50 + i, 264, 266 + i // 2) for i in range(6)]
    assert sb.read_topbot(_arrow_mask(steeper_down), rule) == "Bot"
    assert sb.read_topbot(_arrow_mask(steeper_up), rule) == "Top"


def test_min_margin_by_field_lowers_only_the_listed_fields():
    """Framed 16x12 glyphs (no crop or resize): a probe with margin 0.146 abstains at 0.15 only."""

    def framed(columns):
        glyph = np.zeros(sb.GLYPH_SHAPE, dtype=bool)
        glyph[[0, -1], :] = True
        glyph[:, [0, -1]] = True
        glyph[:, columns] = True
        return glyph

    a, b, probe = framed([]), framed([1, 2, 3, 4]), framed([1])
    templates = sb.DigitTemplates({"2": [a], "3": [b]})
    assert np.array_equal(sb.normalise(probe), probe.astype(np.float32))
    digit, distance, margin = templates.match(probe)
    assert digit is None and distance == pytest.approx(14 / 192)
    assert margin == pytest.approx(28 / 192)  # 0.146: below MIN_MARGIN, above the v4 floor
    assert templates.match(probe, min_margin=0.10)[0] == "2"
    assert templates.match(probe, min_margin=0.146)[0] is None
    assert templates.match(probe, min_margin=sb.MIN_MARGIN) == templates.match(probe)
    white = np.zeros((720, 1280), dtype=bool)
    for name in ("balls", "strikes"):
        x0, y0, x1, y1 = sb.WINDOWS[name]
        white[y0 + 4 : y0 + 20, x0 + 3 : x0 + 15] = probe
    assert sb.read_number(white, "balls", templates) is None
    options = {"min_margin_by_field": {"balls": 0.10}}
    assert sb.read_number(white, "balls", templates, options) == 2
    # strikes is not listed: it keeps MIN_MARGIN; an empty mapping changes nothing
    assert sb.read_number(white, "strikes", templates, options) is None
    assert sb.read_number(white, "balls", templates, {"min_margin_by_field": {}}) is None
    assert sb.read_number(white, "balls", templates, {"min_margin_by_field": None}) is None
    # diagnostics report the best digit and the floor even where the read abstains
    (diag,) = sb.digit_field_diagnostics(white, "balls", templates)
    assert diag == {
        "best": "2",
        "distance": pytest.approx(14 / 192),
        "margin": pytest.approx(28 / 192),
        "min_margin": sb.MIN_MARGIN,
        "read": None,
    }
    (diag,) = sb.digit_field_diagnostics(white, "balls", templates, options)
    assert diag["min_margin"] == 0.10 and diag["read"] == "2" and diag["best"] == "2"
    assert templates.nearest(probe) == templates.match(probe, min_margin=0.0)
    assert sb.digit_field_diagnostics(np.zeros((720, 1280), dtype=bool), "balls", templates) == []
    # MAX_DISTANCE is untouched: a far probe abstains whatever the floor
    far = np.ones(sb.GLYPH_SHAPE, dtype=bool)
    assert templates.match(far, min_margin=0.0)[0] is None


def load_frame(seconds):
    return np.asarray(Image.open(REAL / f"evalset_{seconds:.2f}.jpg").convert("RGB"))


@pytest.mark.skipif(
    not (REAL / "evalset_3314.50.jpg").exists(), reason="eval-set frames not grabbed locally"
)
def test_v4_reads_the_diagnosed_frames_and_v3_document_reproduces_its_predictions():
    """DEVELOPMENT check on seen frames: the six rows v4 changes, and the v3 path unchanged."""
    results = ROOT / "docs/results/mlb_p0"
    evalset = json.loads(
        (results / "game_747139_scoreboard_evalset.json").read_text(encoding="utf-8-sig")
    )
    entries = {(e["at_bat_number"], e["pitch_number"]): e for e in evalset["entries"]}
    v3 = sb.DigitTemplates.from_json(
        json.loads((results / "sny_digit_templates_v3.json").read_text(encoding="utf-8"))
    )
    v4 = sb.DigitTemplates.from_json(
        json.loads((results / "sny_digit_templates_v4.json").read_text(encoding="utf-8"))
    )
    changed = {
        (20, 5): ("balls", None, 2),
        (20, 7): ("balls", None, 2),
        (33, 5): ("balls", None, 2),
        (35, 5): ("balls", None, 2),
        (34, 3): ("inning_topbot", "Bot", "Top"),
        (37, 5): ("inning_topbot", None, "Top"),
    }
    for key, (field, before, after) in changed.items():
        frame = load_frame(entries[key]["frame_seconds"])
        old, new = sb.read_scoreboard(frame, v3), sb.read_scoreboard(frame, v4)
        assert old[field] == before and new[field] == after, key
        assert entries[key]["labels"][field] == after
        assert {k: v for k, v in old.items() if k != field} == {
            k: v for k, v in new.items() if k != field
        }
    # 13/3 balls '2' is 0.1234 > MAX_DISTANCE from every template: abstains under v4 too
    frame = load_frame(entries[(13, 3)]["frame_seconds"])
    assert sb.read_scoreboard(frame, v4)["balls"] is None
    white, _, _ = sb.masks(frame)
    (glyph,) = sb.segment_glyphs(sb.window(white, "balls"), v4.reader_options)
    digit, distance, _ = v4.match(glyph, min_margin=0.1)
    assert digit is None and distance > sb.MAX_DISTANCE
    (diag,) = sb.digit_field_diagnostics(white, "balls", v4, v4.reader_options)
    assert diag["read"] is None and diag["best"] == "2" and diag["distance"] == distance
    assert diag["min_margin"] == 0.1 and diag["distance"] == pytest.approx(0.1234, abs=5e-4)
    # a null option key reads like the v3 document (null = absent on the read path)
    v3_with_nulls = sb.DigitTemplates(
        v3.templates, {**v3.reader_options, **dict.fromkeys(sb.READER_OPTION_KEYS[2:])}
    )
    for key in ((13, 3), (34, 3), (20, 5)):
        frame = load_frame(entries[key]["frame_seconds"])
        assert sb.read_scoreboard(frame, v3_with_nulls) == sb.read_scoreboard(frame, v3)
    # the committed v3 document still produces the committed v3 predictions on every frame
    committed = json.loads(
        (results / "game_747139_scoreboard_ocr_v3_predictions.json").read_text(encoding="utf-8")
    )
    assert len(committed) == len(entries)
    for row in committed:
        entry = entries[(row["at_bat_number"], row["pitch_number"])]
        assert sb.read_scoreboard(load_frame(entry["frame_seconds"]), v3) == row["fields"]

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


@pytest.mark.parametrize("version", ["v1", "v2"])
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

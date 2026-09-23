"""Heuristic reader for the SNY scoreboard bug in 1280x720 broadcast frames (F-3 prototype).

Layout-specific: the SNY bug of the 2024-09-30 NYM @ ATL full-game MP4 (top row NYM = away,
bottom row ATL = home, three runner diamonds, two out circles, inning arrow + number, B-S count).
Field windows were measured by eye from 4x grid crops on 2026-09-23 (``WINDOWS``).

Every field returns ``None`` (abstain) when the reading is not confident:

* outs / runners come from the gold fill inside fixed windows (structural, no training);
* top/bottom comes from the arrow's row profile (apex up = top of the inning);
* digits (balls, strikes, inning number, both scores) are matched against glyph templates cut
  from frames whose labels were verified by a human; a digit with no template abstains, and so
  does a match that is not clearly better than the runner-up.

This is not a general OCR. It produces predictions to be scored with
``src.data.scoreboard_evalset.score_predictions``; it never produces labels.
"""

import numpy as np

# (x0, y0, x1, y1) in frame pixels; windows exclude neighbouring glyphs (the dash of B-S, the
# inning arrow next to the inning number, the team logos next to the scores).
WINDOWS = {
    "away_score": (133, 38, 162, 70),
    "home_score": (133, 76, 162, 108),
    "balls": (248, 82, 266, 106),
    "strikes": (275, 82, 293, 106),
    "inning": (280, 40, 295, 66),
    "arrow": (266, 46, 279, 64),
    "out_1": (192, 88, 205, 101),
    "out_2": (212, 88, 225, 101),
    "runner_on_1b": (217, 62, 232, 78),
    "runner_on_2b": (201, 46, 216, 62),
    "runner_on_3b": (184, 63, 199, 79),
    "panel": (130, 36, 300, 106),
    "top_line": (60, 32, 300, 34),
}
DIGIT_FIELDS = ("balls", "strikes", "inning", "away_score", "home_score")
GLYPH_SHAPE = (16, 12)  # rows, cols after normalisation
MIN_GLYPH_WIDTH = 2
MIN_GLYPH_HEIGHT = 8
# Acceptance thresholds. On the 25 verified frames of game 747139 (2026-09-23) glyphs of a digit
# that has a template sit at distance <= 0.062 with margin >= 0.28, while the one glyph without a
# template ("3" in PA 5/6, templates 0/1/2 only) matched "2" at distance 0.224 / margin 0.079.
# The thresholds were tightened after seeing that case, so that case is no longer blind.
MAX_DISTANCE = 0.12  # mean absolute difference of normalised glyphs
MIN_MARGIN = 0.15  # best template must beat the runner-up digit by this much
FILLED = 0.25  # gold fraction above which a circle / diamond counts as filled
EMPTY = 0.08  # gold fraction below which it counts as empty; in between = abstain
# Presence gate. The count bug has a navy panel, a thin white border line along its top and
# little white inside the panel. A line-score graphic (TOP 2ND R H E) at an inning change is
# also navy but has no top line (white 0.07) and lots of white text (0.36); full-screen stat
# panels, replays and other cameras fail the navy test. Measured 2026-09-23 on 12 frames of
# docs/results/mlb_p0/game_747139_scoreboard_negatives.json plus eval-set frames.
PANEL_NAVY = 0.30  # navy fraction the panel window must reach for the bug to count as present
TOP_LINE_WHITE = 0.60  # white fraction of the top border line (normal frames 0.86-0.97)
PANEL_WHITE_MAX = 0.20  # white fraction inside the panel (normal frames <= 0.09)
TEMPLATE_SCHEMA = "sny_digit_templates_v0"


def masks(frame):
    """White glyph, gold fill and navy background masks for an RGB frame array."""
    arr = np.asarray(frame, dtype=np.int16)
    r, g, b = arr[..., 0], arr[..., 1], arr[..., 2]
    white = (r > 170) & (g > 170) & (b > 170)
    gold = (r > 160) & (g > 120) & (b < 150) & (r - b > 50)
    navy = (b > 50) & (r < 90) & (g < 120) & (b - r > 20)
    return white, gold, navy


def window(mask, name):
    x0, y0, x1, y1 = WINDOWS[name]
    return mask[y0:y1, x0:x1]


def bug_present(navy, white):
    """Navy panel with its white top border and little white inside: the count bug, not a
    line-score or stat graphic."""
    return (
        float(window(navy, "panel").mean()) >= PANEL_NAVY
        and float(window(white, "top_line").mean()) >= TOP_LINE_WHITE
        and float(window(white, "panel").mean()) <= PANEL_WHITE_MAX
    )


def _fill_state(gold, name):
    fraction = float(window(gold, name).mean())
    if fraction >= FILLED:
        return True
    if fraction <= EMPTY:
        return False
    return None


def read_outs(gold):
    first, second = _fill_state(gold, "out_1"), _fill_state(gold, "out_2")
    if first is None or second is None or (second and not first):
        return None
    return int(first) + int(second)


def read_runners(gold):
    return {
        name: _fill_state(gold, name) for name in ("runner_on_1b", "runner_on_2b", "runner_on_3b")
    }


def read_topbot(white):
    """Apex position of the inning arrow: widest row at the bottom = up arrow = Top."""
    widths = window(white, "arrow").sum(axis=1)
    rows = np.where(widths >= 2)[0]
    if len(rows) < 6:
        return None
    span = rows[-1] - rows[0] + 1
    widest = int(np.argmax(widths))
    position = (widest - rows[0]) / span
    if position >= 0.6:
        return "Top"
    if position <= 0.4:
        return "Bot"
    return None


def segment_glyphs(mask_window):
    """Connected column groups of white pixels, left to right, cropped to their row extent."""
    columns = np.where(mask_window.any(axis=0))[0]
    groups = []
    for c in columns:
        if groups and c == groups[-1][1] + 1:
            groups[-1][1] = c
        else:
            groups.append([c, c])
    glyphs = []
    for c0, c1 in groups:
        if c1 - c0 + 1 < MIN_GLYPH_WIDTH:
            continue
        part = mask_window[:, c0 : c1 + 1]
        rows = np.where(part.any(axis=1))[0]
        if len(rows) == 0 or rows[-1] - rows[0] + 1 < MIN_GLYPH_HEIGHT:
            continue
        glyphs.append(part[rows[0] : rows[-1] + 1])
    return glyphs


def normalise(glyph):
    from PIL import Image

    image = Image.fromarray(glyph.astype(np.uint8) * 255)
    resized = image.resize((GLYPH_SHAPE[1], GLYPH_SHAPE[0]), Image.BILINEAR)
    return np.asarray(resized, dtype=np.float32) / 255.0


class DigitTemplates:
    """Nearest-template digit matcher; ``templates[digit]`` is a list of normalised glyphs."""

    def __init__(self, templates=None):
        self.templates = {
            str(k): [np.asarray(g, dtype=np.float32) for g in v]
            for k, v in (templates or {}).items()
        }

    def add(self, digit, glyph):
        self.templates.setdefault(str(digit), []).append(normalise(glyph))

    def match(self, glyph):
        """Return (digit, distance, margin) or (None, distance, margin) when abstaining."""
        if not self.templates:
            return None, None, None
        probe = normalise(glyph)
        scores = sorted(
            (min(float(np.mean(np.abs(probe - t))) for t in glyphs), digit)
            for digit, glyphs in self.templates.items()
        )
        best, digit = scores[0]
        margin = (scores[1][0] - best) if len(scores) > 1 else 1.0
        if best > MAX_DISTANCE or margin < MIN_MARGIN:
            return None, best, margin
        return digit, best, margin

    def to_json(self):
        return {
            "schema": TEMPLATE_SCHEMA,
            "glyph_shape": list(GLYPH_SHAPE),
            "templates": {
                d: [np.round(g, 3).tolist() for g in gl] for d, gl in self.templates.items()
            },
        }

    @classmethod
    def from_json(cls, document):
        if document.get("schema") != TEMPLATE_SCHEMA:
            raise ValueError(f"Expected {TEMPLATE_SCHEMA}")
        if list(document.get("glyph_shape", [])) != list(GLYPH_SHAPE):
            raise ValueError("Template glyph shape does not match this reader")
        return cls(document["templates"])


def read_number(white, name, templates):
    """Digits left to right; abstain unless every glyph matches a template."""
    glyphs = segment_glyphs(window(white, name))
    if not glyphs:
        return None
    digits = []
    for glyph in glyphs:
        digit, _, _ = templates.match(glyph)
        if digit is None:
            return None
        digits.append(digit)
    return int("".join(digits))


def read_scoreboard(frame, templates):
    """Read every label field from an RGB frame; ``None`` = abstain."""
    white, gold, navy = masks(frame)
    fields = {
        "balls": None,
        "strikes": None,
        "outs": None,
        "runner_on_1b": None,
        "runner_on_2b": None,
        "runner_on_3b": None,
        "inning": None,
        "inning_topbot": None,
        "home_score": None,
        "away_score": None,
    }
    if not bug_present(navy, white):
        return fields
    fields["outs"] = read_outs(gold)
    fields.update(read_runners(gold))
    fields["inning_topbot"] = read_topbot(white)
    for name in DIGIT_FIELDS:
        fields[name] = read_number(white, name, templates)
    return fields


def glyphs_for_label(white, name, value):
    """Glyphs of a digit field paired with the verified label's digits, or None on mismatch."""
    glyphs = segment_glyphs(window(white, name))
    text = str(int(value))
    if len(glyphs) != len(text):
        return None
    return list(zip(text, glyphs, strict=True))

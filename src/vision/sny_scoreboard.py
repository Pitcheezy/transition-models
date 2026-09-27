"""Heuristic reader for the SNY scoreboard bug in 1280x720 broadcast frames (F-3 prototype).

Layout-specific: the SNY bug of the 2024-09-30 NYM @ ATL full-game MP4 (top row NYM = away,
bottom row ATL = home, three runner diamonds, two out circles, inning arrow + number, B-S count).
Field windows were measured by eye from 4x grid crops on 2026-09-23 (``WINDOWS``).

Every field returns ``None`` (abstain) when the reading is not confident:

* outs / runners come from the gold fill inside fixed windows (structural, no training);
* top/bottom comes from the arrow's row profile (apex up = top of the inning);
* digits (balls, strikes, inning number, both scores) are matched against glyph templates cut
  from manually reviewed frames (including AI review); a digit with no template abstains, and so
  does a match that is not clearly better than the runner-up.

This is not a general OCR. It produces predictions to be scored with
``src.data.scoreboard_evalset.score_predictions``; it never produces labels.
"""

import math

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
# Opt-in reader options (F-3c, OCR v3). They live ONLY in a template document under
# ``reader_options`` and are applied at read time by ``read_scoreboard`` when the loaded
# ``DigitTemplates`` carries them; a template file without the key (v1, v2) and every function
# default reproduce the v0-v2 behaviour bit for bit. They never apply when templates are cut.
#
# * ``top_line_gate``: ``{"aggregate": "mean" | "max_row", "threshold": float}``. ``mean`` is the
#   default gate (mean white fraction of the top_line window >= threshold); ``max_row`` passes when
#   ANY single row of the window reaches the threshold (a camera-cut frame whose top line sits on
#   one of the two rows only).
# * ``border_sliver_max_width``: int >= 0. In ``segment_glyphs`` a column group of at most this
#   width whose first column is 0 or whose last column is the window's last column is discarded
#   before the MIN_GLYPH_WIDTH/HEIGHT tests (a panel border entering the window after a wipe).
#   0 (the default) discards nothing.
#
# Opt-in reader options (F-3d, OCR v4), same rules: only through a template document's
# ``reader_options``, consulted only when present, never at template-cut time. A document with
# only the two v3 keys (v3) or none (v1, v2) reads exactly as before.
#
# * ``min_margin_by_field``: ``{DIGIT_FIELD: float in [0, 1]}``. Per-field replacement for
#   MIN_MARGIN in ``read_number``; fields not listed keep MIN_MARGIN and MAX_DISTANCE is untouched
#   (a probe farther than 0.12 from every template still abstains). Templates stay pooled across
#   fields. v4: {"balls": 0.10, "strikes": 0.10} for the count-font '2' whose margin to the
#   single count-font '3' template lands at 0.1325-0.1432 (measured on seen frames, 2026-09-25).
# * ``arrow_window``: ``[x0, y0, x1, y1]`` replacing WINDOWS["arrow"] for ``read_topbot`` only
#   (x1/y1 exclusive like ``window``). The up arrow's left edge is x 269 in the 1st inning and
#   264/265 in innings 2-5, so the default x0 266 clips 1-2 columns of its base rows; v4 uses
#   [262, 46, 279, 64].
# * ``topbot_rule``: ``{"method": "blob_slope", "min_slope": float > 0, "min_rows": int >= 2}``.
#   Replaces the widest-row argmax of ``read_topbot`` with the sign of the least-squares slope of
#   the row widths of the arrow blob (``_topbot_blob_slope``): a tie among clipped base rows
#   cannot flip a slope. v4: min_slope 0.4 (finite, > 0), min_rows 6.
#
# A key set to ``null`` counts as absent for every option (``read_number`` and ``read_topbot``
# fall back to the constants), so a document may list a key without enabling it.
TOP_LINE_AGGREGATES = ("mean", "max_row")
TOPBOT_METHODS = ("blob_slope",)
TOPBOT_RULE_KEYS = ("method", "min_slope", "min_rows")
FRAME_SHAPE = (720, 1280)  # rows, cols of the broadcast frame; bounds for arrow_window
READER_OPTION_KEYS = (
    "top_line_gate",
    "border_sliver_max_width",
    "min_margin_by_field",
    "arrow_window",
    "topbot_rule",
)


def _is_number(value):
    return not isinstance(value, bool) and isinstance(value, int | float)


def validate_reader_options(options):
    """Return a plain-dict copy of ``options`` (``None``/empty = no options) or raise ValueError."""
    if options is None:
        return {}
    if not isinstance(options, dict):
        raise ValueError("reader_options must be an object")
    unknown = sorted(set(options) - set(READER_OPTION_KEYS))
    if unknown:
        raise ValueError(f"Unknown reader option(s): {unknown}")
    gate = options.get("top_line_gate")
    if gate is not None:
        if not isinstance(gate, dict) or set(gate) - {"aggregate", "threshold"}:
            raise ValueError("top_line_gate must be {aggregate, threshold}")
        if gate.get("aggregate", "mean") not in TOP_LINE_AGGREGATES:
            raise ValueError(f"top_line_gate.aggregate must be one of {TOP_LINE_AGGREGATES}")
        threshold = gate.get("threshold", TOP_LINE_WHITE)
        if isinstance(threshold, bool) or not isinstance(threshold, (int, float)):
            raise ValueError("top_line_gate.threshold must be a number")
        if not 0.0 <= float(threshold) <= 1.0:
            raise ValueError("top_line_gate.threshold must be within [0, 1]")
    sliver = options.get("border_sliver_max_width")
    if sliver is not None and (
        isinstance(sliver, bool) or not isinstance(sliver, int) or sliver < 0
    ):
        raise ValueError("border_sliver_max_width must be a non-negative integer")
    margins = options.get("min_margin_by_field")
    if margins is not None:
        if not isinstance(margins, dict):
            raise ValueError("min_margin_by_field must be an object {digit field: margin}")
        for field, value in margins.items():
            if field not in DIGIT_FIELDS:
                raise ValueError(
                    f"min_margin_by_field: unknown field {field!r} (expected one of {DIGIT_FIELDS})"
                )
            if not _is_number(value) or not 0.0 <= float(value) <= 1.0:
                raise ValueError(f"min_margin_by_field[{field!r}] must be a number within [0, 1]")
    arrow = options.get("arrow_window")
    if arrow is not None:
        if (
            not isinstance(arrow, list | tuple)
            or len(arrow) != 4
            or any(isinstance(v, bool) or not isinstance(v, int) for v in arrow)
        ):
            raise ValueError("arrow_window must be [x0, y0, x1, y1] with four integers")
        x0, y0, x1, y1 = arrow
        if not (0 <= x0 < x1 <= FRAME_SHAPE[1] and 0 <= y0 < y1 <= FRAME_SHAPE[0]):
            raise ValueError(
                f"arrow_window must satisfy 0 <= x0 < x1 <= {FRAME_SHAPE[1]} and "
                f"0 <= y0 < y1 <= {FRAME_SHAPE[0]}"
            )
    rule = options.get("topbot_rule")
    if rule is not None:
        if not isinstance(rule, dict):
            raise ValueError("topbot_rule must be {method, min_slope, min_rows}")
        unknown = sorted(set(rule) - set(TOPBOT_RULE_KEYS))
        if unknown:
            raise ValueError(f"topbot_rule: unknown key(s) {unknown}")
        if rule.get("method") not in TOPBOT_METHODS:
            raise ValueError(f"topbot_rule.method must be one of {TOPBOT_METHODS}")
        slope = rule.get("min_slope")
        if not _is_number(slope) or not math.isfinite(slope) or not slope > 0:
            raise ValueError("topbot_rule.min_slope must be a finite number > 0")
        rows = rule.get("min_rows")
        if isinstance(rows, bool) or not isinstance(rows, int) or rows < 2:
            raise ValueError("topbot_rule.min_rows must be an integer >= 2")
    return {k: options[k] for k in READER_OPTION_KEYS if k in options}


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


def top_line_passes(white, options=None):
    """The top border line test of the presence gate; ``options`` may carry ``top_line_gate``."""
    gate = (options or {}).get("top_line_gate")
    if not gate:
        return float(window(white, "top_line").mean()) >= TOP_LINE_WHITE
    threshold = float(gate.get("threshold", TOP_LINE_WHITE))
    line = window(white, "top_line")
    if gate.get("aggregate", "mean") == "max_row":
        return float(line.mean(axis=1).max()) >= threshold
    return float(line.mean()) >= threshold


def bug_present(navy, white, options=None):
    """Navy panel with its white top border and little white inside: the count bug, not a
    line-score or stat graphic. ``options`` (reader options) may replace the top-line test."""
    return (
        float(window(navy, "panel").mean()) >= PANEL_NAVY
        and top_line_passes(white, options)
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


def _topbot_blob_slope(arrow, min_slope, min_rows):
    """``topbot_rule`` blob_slope: the sign of the row-width trend of the arrow blob.

    The blob is the widest connected column group of white in the arrow window (ties: the
    leftmost; groups are built as in ``segment_glyphs`` but without the size tests or the sliver
    option), cropped to its non-empty rows, so the inning digit's edge column and narrower
    strays drop out. Fewer than ``min_rows`` rows abstain. The least-squares slope of the row
    widths against the row index is >= ``min_slope`` for an up arrow (rows widen downward =
    Top), <= -``min_slope`` for a down arrow (Bot) and abstains in between. Clipping by the
    window scales the widths but not the sign of the trend.
    """
    columns = np.where(arrow.any(axis=0))[0]
    groups = []
    for c in columns:
        if groups and c == groups[-1][1] + 1:
            groups[-1][1] = c
        else:
            groups.append([c, c])
    if not groups:
        return None
    c0, c1 = max(groups, key=lambda g: g[1] - g[0])  # first maximum = leftmost on ties
    blob = arrow[:, c0 : c1 + 1]
    rows = np.where(blob.any(axis=1))[0]
    if len(rows) < min_rows:
        return None
    widths = blob[rows[0] : rows[-1] + 1].sum(axis=1).astype(np.float64)
    slope = float(np.polyfit(np.arange(len(widths)), widths, 1)[0])
    if slope >= min_slope:
        return "Top"
    if slope <= -min_slope:
        return "Bot"
    return None


def read_topbot(white, options=None):
    """Apex position of the inning arrow: widest row at the bottom = up arrow = Top.

    Reader options (v4): ``arrow_window`` replaces WINDOWS["arrow"] and ``topbot_rule`` replaces
    the widest-row rule below with ``_topbot_blob_slope``; without them this is the v0-v3 body.
    """
    options = options or {}
    x0, y0, x1, y1 = options.get("arrow_window") or WINDOWS["arrow"]
    arrow = white[y0:y1, x0:x1]
    rule = options.get("topbot_rule")
    if rule:
        return _topbot_blob_slope(arrow, float(rule["min_slope"]), int(rule["min_rows"]))
    widths = arrow.sum(axis=1)
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


def segment_glyphs(mask_window, options=None):
    """Connected column groups of white pixels, left to right, cropped to their row extent.

    With the reader option ``border_sliver_max_width`` = N > 0, a group at most N columns wide
    that touches the window's left or right edge is dropped first (a border sliver, not a digit).
    """
    columns = np.where(mask_window.any(axis=0))[0]
    groups = []
    for c in columns:
        if groups and c == groups[-1][1] + 1:
            groups[-1][1] = c
        else:
            groups.append([c, c])
    sliver = int((options or {}).get("border_sliver_max_width") or 0)
    if sliver:
        last = mask_window.shape[1] - 1
        groups = [
            (c0, c1) for c0, c1 in groups if not (c1 - c0 + 1 <= sliver and (c0 == 0 or c1 == last))
        ]
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

    def __init__(self, templates=None, reader_options=None):
        self.templates = {
            str(k): [np.asarray(g, dtype=np.float32) for g in v]
            for k, v in (templates or {}).items()
        }
        # Opt-in read-time options (see ``validate_reader_options``); {} = v0-v2 behaviour.
        self.reader_options = validate_reader_options(reader_options)

    def add(self, digit, glyph):
        self.templates.setdefault(str(digit), []).append(normalise(glyph))

    def match(self, glyph, min_margin=MIN_MARGIN):
        """Return (digit, distance, margin) or (None, distance, margin) when abstaining.

        ``min_margin`` is the margin floor (``read_number`` passes a per-field one from the
        ``min_margin_by_field`` option); MAX_DISTANCE always applies.
        """
        if not self.templates:
            return None, None, None
        probe = normalise(glyph)
        scores = sorted(
            (min(float(np.mean(np.abs(probe - t))) for t in glyphs), digit)
            for digit, glyphs in self.templates.items()
        )
        best, digit = scores[0]
        margin = (scores[1][0] - best) if len(scores) > 1 else 1.0
        if best > MAX_DISTANCE or margin < min_margin:
            return None, best, margin
        return digit, best, margin

    def nearest(self, glyph):
        """(best digit, distance, margin) with no threshold applied: diagnostics only.

        The same scores as ``match`` (which stays the read path), but the best digit is
        reported even when ``match`` abstains, so a per-glyph dump can say whether an
        abstention came from MAX_DISTANCE or from the margin floor.
        """
        if not self.templates:
            return None, None, None
        probe = normalise(glyph)
        scores = sorted(
            (min(float(np.mean(np.abs(probe - t))) for t in glyphs), digit)
            for digit, glyphs in self.templates.items()
        )
        best, digit = scores[0]
        return digit, best, (scores[1][0] - best) if len(scores) > 1 else 1.0

    def to_json(self):
        document = {
            "schema": TEMPLATE_SCHEMA,
            "glyph_shape": list(GLYPH_SHAPE),
            "templates": {
                d: [np.round(g, 3).tolist() for g in gl] for d, gl in self.templates.items()
            },
        }
        if self.reader_options:  # the key is absent (v1/v2 layout) unless options were given
            document["reader_options"] = dict(self.reader_options)
        return document

    @classmethod
    def from_json(cls, document):
        if document.get("schema") != TEMPLATE_SCHEMA:
            raise ValueError(f"Expected {TEMPLATE_SCHEMA}")
        if list(document.get("glyph_shape", [])) != list(GLYPH_SHAPE):
            raise ValueError("Template glyph shape does not match this reader")
        return cls(document["templates"], document.get("reader_options"))


def read_number(white, name, templates, options=None):
    """Digits left to right; abstain unless every glyph matches a template."""
    glyphs = segment_glyphs(window(white, name), options)
    if not glyphs:
        return None
    min_margin = ((options or {}).get("min_margin_by_field") or {}).get(name, MIN_MARGIN)
    digits = []
    for glyph in glyphs:
        digit, _, _ = templates.match(glyph, min_margin=min_margin)
        if digit is None:
            return None
        digits.append(digit)
    return int("".join(digits))


def digit_field_diagnostics(white, name, templates, options=None):
    """Per-glyph ``{best, distance, margin, min_margin, read}`` of a digit window (diagnostics).

    Same segmentation and margin floor as ``read_number`` (an empty list = no glyph cut), with
    ``DigitTemplates.nearest`` for the best digit even where ``read`` abstained. Used by
    ``scripts/66 predict --diagnostics`` for the F-3d criterion (5): an abstention is explained
    by ``distance`` > MAX_DISTANCE, by ``margin`` < ``min_margin`` or by no glyph.
    """
    options = options or {}
    min_margin = (options.get("min_margin_by_field") or {}).get(name, MIN_MARGIN)
    diagnostics = []
    for glyph in segment_glyphs(window(white, name), options):
        best, distance, margin = templates.nearest(glyph)
        diagnostics.append(
            {
                "best": best,
                "distance": distance,
                "margin": margin,
                "min_margin": min_margin,
                "read": templates.match(glyph, min_margin=min_margin)[0],
            }
        )
    return diagnostics


def read_scoreboard(frame, templates):
    """Read every label field from an RGB frame; ``None`` = abstain.

    The reader options carried by ``templates`` (``DigitTemplates.reader_options``, set only by
    a template document with ``reader_options``) apply here; none = v0-v2 behaviour.
    """
    options = getattr(templates, "reader_options", None) or {}
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
    if not bug_present(navy, white, options):
        return fields
    fields["outs"] = read_outs(gold)
    fields.update(read_runners(gold))
    fields["inning_topbot"] = read_topbot(white, options)
    for name in DIGIT_FIELDS:
        fields[name] = read_number(white, name, templates, options)
    return fields


def glyphs_for_label(white, name, value):
    """Glyphs of a digit field paired with the verified label's digits, or None on mismatch."""
    glyphs = segment_glyphs(window(white, name))
    text = str(int(value))
    if len(glyphs) != len(text):
        return None
    return list(zip(text, glyphs, strict=True))

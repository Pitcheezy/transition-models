"""Compose a per-pitch review sheet from already loaded frames (no ffmpeg, testable with PIL).

A sheet stacks four labelled sections: decision frames (boundary frames and the chosen
decision frame, half size), the scoreboard bug of those same frames enlarged, preparation
frames (small) and release crops of the pitcher box. It is a review aid for manual timing; it
produces no labels.
"""

from pathlib import Path

from PIL import Image, ImageDraw

from src.vision.frames import SNY_BUG_BOX

DEFAULT_PITCHER_BOX = (430, 190, 850, 610)
DECISION_TILE, DECISION_PER_ROW = (640, 360), 3
BUG_TILE, BUG_PER_ROW = (765, 330), 2
PREP_TILE, PREP_PER_ROW = (316, 178), 4
RELEASE_TILE, RELEASE_PER_ROW = (252, 252), 5
GAP = 6
HEADER = 24
TITLE = 28
SKIP_PREFIXES = ("evalset_", "neg_")


def cached_frame(frames_dir, t, skip_prefixes=SKIP_PREFIXES):
    """An existing ``<frames_dir>/*_<t>.jpg`` for the same second, or ``None``.

    Frames grabbed for eye review are preferred; eval-set and negatives frames (``skip_prefixes``)
    are used only when nothing else exists, so review batches never depend on the OCR caches.
    """
    matches = sorted(Path(frames_dir).glob(f"*_{t:.2f}.jpg"))
    preferred = [p for p in matches if not p.name.startswith(skip_prefixes)]
    return (preferred or matches or [None])[0]


def _stamp(image, text):
    draw = ImageDraw.Draw(image)
    draw.rectangle((0, image.height - 18, 8 + 7 * len(text), image.height), fill="black")
    draw.text((4, image.height - 15), text, fill="yellow")
    return image


def _grid(tiles, tile, per_row):
    """Paste equally sized tiles left to right, ``per_row`` per row; return (image, rows)."""
    rows = (len(tiles) + per_row - 1) // per_row
    cols = min(len(tiles), per_row)
    width = cols * tile[0] + (cols - 1) * GAP
    height = rows * tile[1] + (rows - 1) * GAP
    strip = Image.new("RGB", (width, height), "white")
    for i, image in enumerate(tiles):
        x, y = (i % per_row) * (tile[0] + GAP), (i // per_row) * (tile[1] + GAP)
        strip.paste(image, (x, y))
    return strip, rows


def _tiles(frames, tile, box=None):
    tiles = []
    for t, image in frames:
        image = image.convert("RGB")
        if box is not None:
            image = image.crop(box)
        tiles.append(_stamp(image.resize(tile, Image.LANCZOS), f"t={t:.2f}"))
    return tiles


def compose_sheet(
    decision, prep, release, *, title, bug_box=SNY_BUG_BOX, pitcher_box=DEFAULT_PITCHER_BOX
):
    """Return (sheet image, layout) from ``(t, PIL image)`` lists; empty sections are skipped.

    ``layout`` lists every section with its tile size and row count and the sheet size, so the
    composition can be checked without looking at pixels.
    """
    sections = [
        ("decision", _tiles(decision, DECISION_TILE), DECISION_TILE, DECISION_PER_ROW),
        ("bug", _tiles(decision, BUG_TILE, bug_box), BUG_TILE, BUG_PER_ROW),
        ("prep", _tiles(prep, PREP_TILE), PREP_TILE, PREP_PER_ROW),
        ("release", _tiles(release, RELEASE_TILE, pitcher_box), RELEASE_TILE, RELEASE_PER_ROW),
    ]
    strips = []
    for name, tiles, tile, per_row in sections:
        if tiles:
            strip, rows = _grid(tiles, tile, per_row)
            strips.append((name, strip, {"name": name, "tile": tile, "rows": rows}))
    if not strips:
        raise ValueError("A review sheet needs at least one frame")
    width = max(strip.width for _, strip, _ in strips)
    height = TITLE + sum(HEADER + strip.height + GAP for _, strip, _ in strips)
    sheet = Image.new("RGB", (width, height), "white")
    draw = ImageDraw.Draw(sheet)
    draw.rectangle((0, 0, width, TITLE), fill="black")
    draw.text((6, 8), title, fill="white")
    y = TITLE
    for name, strip, _ in strips:
        draw.rectangle((0, y, width, y + HEADER), fill=(40, 40, 40))
        draw.text((6, y + 6), name, fill="white")
        y += HEADER
        sheet.paste(strip, (0, y))
        y += strip.height + GAP
    layout = {"width": width, "height": height, "sections": [meta for _, _, meta in strips]}
    return sheet, layout

"""Single-frame grabs from the inspected broadcast MP4 and eye-review montages.

Frames are review aids for manual timing and scoreboard reading (and inputs to the scoreboard
reader prototype). They are never labels. Times are playback seconds of the MP4 named in the
timing document; they are never derived from feed UTC.
"""

import shutil
import subprocess
from pathlib import Path

SNY_BUG_BOX = (55, 25, 310, 135)
FULL_TILE = (640, 360)
BUG_TILE = (765, 330)


def frame_path(out, label, t):
    return Path(out) / f"{label}_{t:.2f}.jpg"


def grab_frame(media_url, t, path, ffmpeg="ffmpeg", attempts=3):
    """Extract one frame at playback second ``t`` unless the file already exists.

    Remote HTTP range reads of the MP4 fail intermittently ("partial file"); a failed attempt
    writes nothing, so it is retried up to ``attempts`` times before raising.
    """
    path = Path(path)
    if path.exists():
        return False
    if shutil.which(ffmpeg) is None:
        raise RuntimeError(f"{ffmpeg} not found on PATH")
    path.parent.mkdir(parents=True, exist_ok=True)
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        f"{t:.3f}",
        "-i",
        media_url,
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(path),
    ]
    for attempt in range(1, attempts + 1):
        run = subprocess.run(command, capture_output=True, text=True, timeout=180)
        if run.returncode == 0 and path.exists() and path.stat().st_size > 0:
            return True
        path.unlink(missing_ok=True)
        if attempt == attempts:
            raise RuntimeError(
                f"ffmpeg failed {attempts} times at t={t}: {run.stderr.strip()[-400:]}"
            )
    return True


def build_montages(frames, out, label, bug_box=SNY_BUG_BOX):
    """Write ``<label>_full.png`` and ``<label>_bug.png`` from (time, path) pairs."""
    from PIL import Image, ImageDraw

    out = Path(out)
    cols = 2
    rows = (len(frames) + cols - 1) // cols
    full = Image.new("RGB", (FULL_TILE[0] * cols, FULL_TILE[1] * rows), "white")
    for i, (t, path) in enumerate(frames):
        x, y = (i % cols) * FULL_TILE[0], (i // cols) * FULL_TILE[1]
        full.paste(Image.open(path).convert("RGB").resize(FULL_TILE), (x, y))
        draw = ImageDraw.Draw(full)
        draw.rectangle((x, y + FULL_TILE[1] - 24, x + 120, y + FULL_TILE[1]), fill="black")
        draw.text((x + 4, y + FULL_TILE[1] - 18), f"t={t:.2f}", fill="yellow")
    crops = []
    for t, path in frames:
        crop = Image.open(path).convert("RGB").crop(bug_box).resize(BUG_TILE, Image.LANCZOS)
        draw = ImageDraw.Draw(crop)
        draw.rectangle((0, 0, 110, 22), fill="black")
        draw.text((4, 4), f"t={t:.2f}", fill="yellow")
        crops.append(crop)
    bug = Image.new("RGB", (BUG_TILE[0], sum(c.height + 6 for c in crops)), "white")
    y = 0
    for crop in crops:
        bug.paste(crop, (0, y))
        y += crop.height + 6
    full_path, bug_path = out / f"{label}_full.png", out / f"{label}_bug.png"
    full.save(full_path)
    bug.save(bug_path)
    return full_path, bug_path

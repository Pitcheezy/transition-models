"""Single-frame grabs from the inspected broadcast MP4 and eye-review montages.

Frames are review aids for manual timing and scoreboard reading (and inputs to the scoreboard
reader prototype). They are never labels. Times are playback seconds of the MP4 named in the
timing document; they are never derived from feed UTC.
"""

import json
import math
import re
import shutil
import subprocess
import tempfile
from functools import lru_cache
from pathlib import Path

SNY_BUG_BOX = (55, 25, 310, 135)
FULL_TILE = (640, 360)
BUG_TILE = (765, 330)
ROOT = Path(__file__).resolve().parents[2]
CACHE_SCHEMA = "broadcast_frame_cache_v1"


def _sha256(content):
    import hashlib

    return hashlib.sha256(content).hexdigest()


def _seek(t):
    if type(t) not in (int, float) or not math.isfinite(t) or t < 0:
        raise ValueError("Playback time must be finite and non-negative")
    seconds = f"{t:.3f}"
    if not math.isclose(t, float(seconds), rel_tol=0, abs_tol=1e-9):
        raise ValueError("Playback time must have at most millisecond precision")
    return seconds


def _source_dir(out, media_url):
    if not isinstance(media_url, str) or not media_url.strip():
        raise ValueError("A media URL is required to bind cached frames")
    return Path(out) / f"source_{_sha256(media_url.encode('utf-8'))}"


def frame_path(out, label, t, media_url):
    """Use a source-specific namespace and the exact millisecond seek sent to ffmpeg."""
    if not isinstance(label, str) or not re.fullmatch(r"[A-Za-z0-9_.-]+", label):
        raise ValueError(
            "Frame label must contain only letters, digits, underscores, dots or hyphens"
        )
    return _source_dir(out, media_url) / f"{label}_{_seek(t)}.jpg"


def _receipt_path(path):
    return Path(path).with_suffix(".jpg.json")


def _verified(path, media_url, t):
    """A filename alone never proves where a frame came from."""
    try:
        receipt = json.loads(_receipt_path(path).read_text(encoding="utf-8"))
        return (
            receipt["schema"] == CACHE_SCHEMA
            and receipt["media_url"] == media_url
            and type(receipt["frame_seconds"]) in (int, float)
            and receipt["frame_seconds"] == float(_seek(t))
            and receipt["sha256"] == _sha256(Path(path).read_bytes())
        )
    except (OSError, ValueError, TypeError, KeyError):
        return False


@lru_cache(maxsize=8)
def _legacy_receipts(root):
    """Read only committed provenance; working reports cannot authorize their own cache."""
    receipts = {}
    for version in range(1, 5):
        name = f"docs/results/mlb_p0/game_747139_scoreboard_ocr_v{version}_provenance.json"
        try:
            run = subprocess.run(
                ["git", "show", f"HEAD:{name}"], cwd=root, capture_output=True, check=False
            )
        except FileNotFoundError:
            return {}  # Portable runtime: receipts work even when Git is not installed.
        if run.returncode:
            continue
        document = json.loads(run.stdout.decode("utf-8"))
        media_url = document["source"]["media_url"]
        for frame in document.get("frame_cache", {}).get("frames", []):
            if frame.get("sha256"):
                key = (media_url, _seek(frame["frame_seconds"]))
                receipts.setdefault(key, set()).add((Path(frame["path"]).name, frame["sha256"]))
    return receipts


def cached_frame(out, media_url, t, label=None, root=ROOT):
    """Reuse only source/time/hash-verified frames, including recorded legacy eval frames."""
    second = _seek(t)
    # Historical OCR inputs retain their exact bytes when provenance authorizes them.
    legacy = sorted(_legacy_receipts(str(Path(root).resolve())).get((media_url, second), ()))
    for name, digest in legacy:
        path = Path(out) / name
        if path.is_file() and _sha256(path.read_bytes()) == digest:
            return path
    candidates = sorted(_source_dir(out, media_url).glob(f"*_{second}.jpg"))
    if label is not None:
        preferred = frame_path(out, label, t, media_url)
        candidates = [preferred, *(p for p in candidates if p != preferred)]
    return next((p for p in candidates if _verified(p, media_url, t)), None)


def resolve_frame(media_url, t, out, label, *, ffmpeg="ffmpeg", no_grab=False, root=ROOT):
    """Resolve a verified frame or capture a new source-bound frame without replacing old files."""
    path = cached_frame(out, media_url, t, label, root)
    if path is not None:
        return path
    path = frame_path(out, label, t, media_url)
    if no_grab:
        raise FileNotFoundError(f"No source/time/hash-verified cached frame at {t}: {path}")
    grab_frame(media_url, t, path, ffmpeg)
    return path


def grab_frame(media_url, t, path, ffmpeg="ffmpeg", attempts=3):
    """Extract one frame at playback second ``t`` or reuse its verified receipt.

    Remote HTTP range reads of the MP4 fail intermittently ("partial file"); a failed attempt
    writes nothing, so it is retried up to ``attempts`` times before raising.
    """
    path = Path(path)
    second = _seek(t)
    if _verified(path, media_url, t):
        return False
    if path.exists() or _receipt_path(path).exists():
        raise FileExistsError(f"Refusing to overwrite an unverified cached frame: {path}")
    if shutil.which(ffmpeg) is None:
        raise RuntimeError(f"{ffmpeg} not found on PATH")
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile(dir=path.parent, suffix=".jpg", delete=False) as temporary:
        temporary_path = Path(temporary.name)
    command = [
        ffmpeg,
        "-hide_banner",
        "-loglevel",
        "error",
        "-y",
        "-ss",
        second,
        "-i",
        media_url,
        "-frames:v",
        "1",
        "-q:v",
        "2",
        str(temporary_path),
    ]
    try:
        for attempt in range(1, attempts + 1):
            run = subprocess.run(command, capture_output=True, text=True, timeout=180)
            if run.returncode == 0 and temporary_path.stat().st_size > 0:
                from PIL import Image

                with Image.open(temporary_path) as image:
                    image.verify()
                content = temporary_path.read_bytes()
                with path.open("xb") as target:
                    target.write(content)
                receipt = {
                    "schema": CACHE_SCHEMA,
                    "media_url": media_url,
                    "frame_seconds": float(second),
                    "sha256": _sha256(content),
                }
                with _receipt_path(path).open("x", encoding="utf-8") as target:
                    target.write(json.dumps(receipt, indent=2, allow_nan=False) + "\n")
                return True
            temporary_path.write_bytes(b"")
            if attempt == attempts:
                raise RuntimeError(
                    f"ffmpeg failed {attempts} times at t={t}: {run.stderr.strip()[-400:]}"
                )
    finally:
        temporary_path.unlink(missing_ok=True)


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

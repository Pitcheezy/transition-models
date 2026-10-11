"""Cut per-pitch frame windows from a broadcast video and build reading aids.

    python -m intent.broadcast_windows --game 849843 --media-url <mp4> --pitches <json> \
        --out outputs/frames/849843_windows

For each pitch (``at_bat_number``, ``pitch_number``, ``release_t`` in playback seconds) one
ffmpeg call decodes from ``release_t - before`` to ``release_t + after`` (accurate seek, default 1.5 s
each side because condensed-game cuts reach the live view late) and keeps every
``step``-th source frame (default 3, about 20 per second). Frames are named by their source frame index
``round(t * fps)``, so ``evidence.frame_index`` needs no rounding later. For each window it
writes 2x gridded crops of the plate area and one strip sheet of all frames, all under
``outputs/`` (git-ignored: the video is MLB's). The manifest it prints/writes carries frame
indices, times and sha256 only.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import shutil
import subprocess
import tempfile
import time
from fractions import Fraction
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def window_indices(release_t, fps, before=1.5, after=1.5, step=3):
    """Source frame indices kept for one pitch: every ``step``-th frame in the window."""
    start = int(round(Fraction(str(release_t - before)) * fps))
    end = int(round(Fraction(str(release_t + after)) * fps))
    start = max(0, start)
    return list(range(start, end + 1, step))


def _grid(image, box, zoom, minor=20, major=100):
    from PIL import Image, ImageDraw

    crop = image.crop(box).resize(
        ((box[2] - box[0]) * zoom, (box[3] - box[1]) * zoom), Image.Resampling.LANCZOS
    )
    d = ImageDraw.Draw(crop)
    for x in range(box[0] - box[0] % minor, box[2] + 1, minor):
        if x < box[0]:
            continue
        X = (x - box[0]) * zoom
        d.line((X, 0, X, crop.height), fill=(255, 255, 0) if x % major == 0 else (100, 100, 100))
        if x % major == 0:
            d.text((X + 2, 2), str(x), fill=(255, 255, 0))
            d.text((X + 2, crop.height - 12), str(x), fill=(255, 255, 0))
    for y in range(box[1] - box[1] % minor, box[3] + 1, minor):
        if y < box[1]:
            continue
        Y = (y - box[1]) * zoom
        d.line((0, Y, crop.width, Y), fill=(255, 255, 0) if y % major == 0 else (100, 100, 100))
        if y % major == 0:
            d.text((2, Y + 2), str(y), fill=(255, 255, 0))
    return crop


def cut_window(
    media_url,
    pitch,
    out_dir,
    fps,
    box,
    *,
    ffmpeg="ffmpeg",
    before=1.5,
    after=1.5,
    step=3,
    retries=4,
):
    from PIL import Image, ImageDraw

    keep = window_indices(pitch["release_t"], fps, before, after, step)
    start = keep[0]
    n_frames = keep[-1] - start + 1
    name = f"pa{pitch['at_bat_number']}_p{pitch['pitch_number']}"
    target = Path(out_dir) / name
    target.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory() as tmp:
        seek = float(Fraction(start) / fps)
        for attempt in range(retries + 1):
            for stale in Path(tmp).glob("f_*.jpg"):
                stale.unlink()
            try:
                subprocess.run(
                    [
                        ffmpeg,
                        "-v",
                        "error",
                        "-y",
                        "-ss",
                        f"{seek:.6f}",
                        "-i",
                        media_url,
                        "-frames:v",
                        str(n_frames),
                        "-q:v",
                        "2",
                        str(Path(tmp) / "f_%05d.jpg"),
                    ],
                    check=True,
                )
                break
            except subprocess.CalledProcessError:
                # the CDN sometimes cuts a ranged read short ("partial file"); the same seek
                # decodes the same frames, so a retry cannot change any output
                if attempt == retries:
                    raise
                time.sleep(3 * (attempt + 1))
        decoded = sorted(Path(tmp).glob("f_*.jpg"))
        frames = []
        for offset, path in enumerate(decoded):
            index = start + offset
            if index not in keep:
                continue
            dest = target / f"frame_{index:06d}.jpg"
            shutil.copyfile(path, dest)
            frames.append(
                {
                    "frame_index": index,
                    "frame_time": float(Fraction(index) / fps),
                    "path": dest.as_posix(),
                    "image_sha256": hashlib.sha256(dest.read_bytes()).hexdigest(),
                }
            )
    thumbs = []
    for f in frames:
        with Image.open(f["path"]) as im:
            im = im.convert("RGB")
            _grid(im, box, 2).save(target / f"crop_{f['frame_index']:06d}.jpg", quality=88)
            t = im.crop(box).resize(((box[2] - box[0]) // 2, (box[3] - box[1]) // 2))
            d = ImageDraw.Draw(t)
            d.rectangle((0, 0, 120, 13), fill=(0, 0, 0))
            d.text(
                (2, 1),
                f"#{f['frame_index']} {f['frame_time'] - pitch['release_t']:+.2f}s",
                fill=(255, 255, 0),
            )
            thumbs.append(t)
    if thumbs:
        cols = 6
        w, h = thumbs[0].size
        rows = (len(thumbs) + cols - 1) // cols
        sheet = Image.new("RGB", (w * cols, h * rows), (20, 20, 20))
        for i, t in enumerate(thumbs):
            sheet.paste(t, ((i % cols) * w, (i // cols) * h))
        sheet.save(target / "strip.jpg", quality=85)
    return {
        "pitch": f"{pitch['at_bat_number']}:{pitch['pitch_number']}",
        "dir": target.as_posix(),
        "frames": frames,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--game", type=int, required=True)
    parser.add_argument("--media-url", required=True)
    parser.add_argument(
        "--pitches",
        type=Path,
        required=True,
        help="JSON list of {at_bat_number, pitch_number, release_t}",
    )
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--fps", default="60000/1001")
    parser.add_argument(
        "--box", default="300,200,960,520", help="crop x0,y0,x1,y1 in source pixels"
    )
    parser.add_argument("--ffmpeg", default="ffmpeg")
    args = parser.parse_args(argv)
    if "outputs" not in args.out.resolve().parts:
        parser.error("frames are MLB video; write them under outputs/ (git-ignored)")
    num, den = (int(v) for v in args.fps.split("/"))
    fps = Fraction(num, den)
    box = tuple(int(v) for v in args.box.split(","))
    pitches = json.loads(args.pitches.read_text(encoding="utf-8"))
    windows = [
        cut_window(args.media_url, p, args.out, fps, box, ffmpeg=args.ffmpeg) for p in pitches
    ]
    manifest = {
        "schema": "intent_broadcast_windows_v0",
        "game_pk": args.game,
        "media_url": args.media_url,
        "fps": args.fps,
        "window": {"before_s": 1.5, "after_s": 1.5, "step_frames": 3},
        "crop_box": list(box),
        "windows": windows,
    }
    args.manifest.write_text(json.dumps(manifest, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({"windows": len(windows), "frames": sum(len(w["frames"]) for w in windows)}))


if __name__ == "__main__":
    main()

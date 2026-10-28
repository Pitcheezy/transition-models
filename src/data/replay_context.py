"""Fixed, private frame evidence for game 849843 PA 1; no posture or outcome inference."""

from __future__ import annotations

import json
import re
import subprocess
from fractions import Fraction
from pathlib import Path

from src.data.replay_feasibility import clip_file, decode_index, digest, read_candidates

SCHEMA = "pitcheezy-replay-context-v1"
GAME = 849843
FRAME_SIZE = (1280, 720)
CROP = (450, 240, 660, 470)
CUTOFF = Fraction(5, 2)
INTERVAL = Fraction(1, 10)
MAX_FRAMES = 26
TILES_PER_PAGE = 12
OUTPUT_ROOT = Path(__file__).resolve().parents[2] / "outputs"


def select_frames(time_base, rows):
    """Use exact PTS differences; the final eligible boundary may be less than 0.1s apart."""
    tick = Fraction(time_base)
    if tick <= 0 or not rows:
        raise ValueError("invalid decoded frame index")
    start = rows[0]["pts"]
    eligible = [row for row in rows if 0 <= (row["pts"] - start) * tick <= CUTOFF]
    chosen = [eligible[0]]
    for row in eligible[1:]:
        if (row["pts"] - chosen[-1]["pts"]) * tick >= INTERVAL:
            chosen.append(row)
    if chosen[-1]["ordinal"] != eligible[-1]["ordinal"]:
        chosen.append(eligible[-1])
    if len(chosen) > MAX_FRAMES:
        raise ValueError("frame selection exceeds fixed bound")
    return [dict(row) for row in chosen]


def validate_crop(rectangle, size):
    if len(rectangle) != 4 or any(type(value) is not int for value in rectangle):
        raise ValueError("crop must contain four integer coordinates")
    left, top, right, bottom = rectangle
    if not (0 <= left < right <= size[0] and 0 <= top < bottom <= size[1]):
        raise ValueError("crop must lie inside the full frame")
    return right - left, bottom - top


def private_destination(destination):
    path = Path(destination).resolve()
    if path == OUTPUT_ROOT or not path.is_relative_to(OUTPUT_ROOT):
        raise ValueError("a private outputs subdirectory is required")
    if path.exists() or Path(destination).is_symlink():
        raise ValueError("a fresh output directory is required")
    return path


def first_three(root):
    rows = read_candidates(root, through_pa=1)
    expected = [(GAME, 1, pitch) for pitch in (1, 2, 3)]
    actual = [(row["game_pk"], row["at_bat_number"], row["pitch_number"]) for row in rows]
    if actual != expected or any(type(value) is not int for key in actual for value in key):
        raise ValueError("exactly game 849843 PA 1 pitches 1, 2, 3 are required")
    if any(row["pitch_key"] != f"{GAME}:1:{pitch}" for pitch, row in enumerate(rows, 1)):
        raise ValueError("pitch key does not match the fixed selection")
    return rows


def image_record(path, destination, size):
    return {
        "path": path.relative_to(destination).as_posix(),
        "sha256": digest(path),
        "size": list(size),
    }


def verify_extracted_pts(stderr, frames, time_base):
    """Bind the selected rasters to the filter's actual input clock, not ordinal alone."""
    log = stderr.decode("utf-8", errors="replace")
    if re.search(r"\[(?:warning|error|fatal|panic)\]", log):
        raise ValueError("ffmpeg reported a decoder warning or error")
    clock = re.findall(r"Parsed_showinfo[^\n]*config in time_base:\s*(\d+/\d+)", log)
    observations = re.findall(
        r"Parsed_showinfo[^\n]*\bn:\s*(\d+)\s+pts:\s*(-?\d+)\s+pts_time:", log
    )
    if clock != [time_base]:
        raise ValueError("extraction time base differs from the probed stream")
    actual = [(int(n), int(pts)) for n, pts in observations]
    expected = [(n, row["pts"]) for n, row in enumerate(frames)]
    if actual != expected:
        raise ValueError("extracted frame PTS differs from the probed selection")
    return {"time_base": clock[0], "selected_pts": [pts for _, pts in actual]}


def contact_sheets(folder, destination, pitch_key, frames, kind):
    from PIL import Image, ImageDraw

    crop_size = validate_crop(CROP, FRAME_SIZE)
    display = (480, 270) if kind == "full_frame" else (crop_size[0] * 2, crop_size[1] * 2)
    resampling = Image.Resampling.LANCZOS if kind == "full_frame" else Image.Resampling.NEAREST
    tile_width, image_height = display
    tile_height = image_height + 36
    pages = []
    for offset in range(0, len(frames), TILES_PER_PAGE):
        group = frames[offset : offset + TILES_PER_PAGE]
        size = (tile_width * 3, tile_height * ((len(group) + 2) // 3))
        sheet = Image.new("RGB", size, "#14202c")
        draw = ImageDraw.Draw(sheet)
        tiles = []
        for index, frame in enumerate(group):
            x, y = index % 3 * tile_width, index // 3 * tile_height
            source = frame["full_frame" if kind == "full_frame" else "context_crop"]
            with Image.open(destination / source["path"]) as im:
                sheet.paste(im.resize(display, resampling), (x, y))
            label = (
                f"{pitch_key}  n={frame['ordinal']}\n"
                f"PTS={frame['pts']}  clip t={frame['clip_seconds']:.6f}s"
            )
            draw.text((x + 5, y + image_height + 3), label, fill="white")
            tiles.append({"ordinal": frame["ordinal"], "image_origin_xy": [x, y], "label": label})
        path = folder / f"{kind}_sheet_{len(pages):02d}.png"
        sheet.save(path)
        pages.append(
            {
                **image_record(path, destination, size),
                "kind": kind,
                "resampling": resampling.name,
                "display_size": list(display),
                "tiles": tiles,
            }
        )
    return pages


def extract_context(root, row, destination, ffprobe, ffmpeg):
    from PIL import Image

    path = clip_file(root, row)
    probe = subprocess.run(
        [
            str(ffprobe),
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_frames",
            "-show_entries",
            "frame=pts:stream=time_base,width,height",
            "-of",
            "json",
            str(path),
        ],
        capture_output=True,
        check=True,
        timeout=90,
    )
    if probe.stderr.strip():
        raise ValueError("ffprobe reported a decoder error")
    decoded = json.loads(probe.stdout)
    time_base, index = decode_index(decoded)
    stream = decoded["streams"][0]
    size = (stream.get("width"), stream.get("height"))
    if any(type(value) is not int for value in size) or size != FRAME_SIZE:
        raise ValueError("the fixed context crop requires 1280x720 video")
    crop_size = validate_crop(CROP, size)
    frames = select_frames(time_base, index)
    folder = destination / row["pitch_key"].replace(":", "_")
    folder.mkdir()
    probe_path = folder / "ffprobe.json"
    probe_path.write_bytes(probe.stdout)
    expression = "+".join(f"eq(n\\,{frame['ordinal']})" for frame in frames)
    process = subprocess.run(
        [
            str(ffmpeg),
            "-nostdin",
            "-n",
            "-loglevel",
            "level+info",
            "-xerror",
            "-noautorotate",
            "-copyts",
            "-i",
            str(path),
            "-map",
            "0:v:0",
            "-an",
            "-sn",
            "-dn",
            "-vf",
            f"select={expression},showinfo",
            "-fps_mode",
            "vfr",
            "-frames:v",
            str(len(frames)),
            "-start_number",
            "0",
            str(folder / "frame_%03d.png"),
        ],
        capture_output=True,
        check=True,
        timeout=90,
    )
    extraction = verify_extracted_pts(process.stderr, frames, time_base)
    extraction_log = folder / "ffmpeg_showinfo.log"
    extraction_log.write_bytes(process.stderr)
    images = sorted(folder.glob("frame_*.png"))
    if [path.name for path in images] != [f"frame_{i:03d}.png" for i in range(len(frames))]:
        raise ValueError("decoded image count or sequence mismatch")
    for image_path, frame in zip(images, frames, strict=True):
        crop_path = image_path.with_name(image_path.name.replace("frame_", "crop_"))
        with Image.open(image_path) as im:
            if im.size != FRAME_SIZE:
                raise ValueError("decoded image dimensions differ from the probed stream")
            im.crop(CROP).save(crop_path)
        frame["full_frame"] = image_record(image_path, destination, size)
        frame["image"] = frame["full_frame"]["path"]
        frame["image_sha256"] = frame["full_frame"]["sha256"]
        frame["image_size"] = list(size)
        frame["context_crop"] = {
            **image_record(crop_path, destination, crop_size),
            "source_rectangle_xyxy": list(CROP),
            "full_frame_origin_xy": list(CROP[:2]),
        }
    sheets = contact_sheets(folder, destination, row["pitch_key"], frames, "full_frame")
    sheets += contact_sheets(folder, destination, row["pitch_key"], frames, "crop_nearest_2x")
    clip_file(root, row)  # Reject a source that changed while it was being decoded.
    return {
        "pitch_key": row["pitch_key"],
        "play_id": row["play_id"],
        "clip_sha256": row["file_sha256"],
        "clip_bytes": row["bytes"],
        "time_base": time_base,
        "decoded_frames": len(index),
        "first_pts": index[0]["pts"],
        "last_pts": index[-1]["pts"],
        "probe": {
            "path": probe_path.relative_to(destination).as_posix(),
            "sha256": digest(probe_path),
        },
        "extraction": {
            **extraction,
            "log_path": extraction_log.relative_to(destination).as_posix(),
            "log_sha256": digest(extraction_log),
        },
        "sampled_frames": frames,
        "sheets": sheets,
    }


def build_context(root, destination, ffprobe, ffmpeg):
    destination = private_destination(destination)
    validate_crop(CROP, FRAME_SIZE)
    root = Path(root).resolve(strict=True)
    registry = root / "registry.sqlite"
    registry_sha = digest(registry)
    rows = first_three(root)
    # Verify all three source paths and hashes before making output or invoking a decoder.
    for row in rows:
        clip_file(root, row)
    destination.mkdir(parents=True)
    records = [extract_context(root, row, destination, ffprobe, ffmpeg) for row in rows]
    if digest(registry) != registry_sha:
        raise ValueError("source registry changed during extraction")
    report = {
        "schema": SCHEMA,
        "game_pk": GAME,
        "at_bat_number": 1,
        "source_registry_sha256": registry_sha,
        "evidence_kind": "offline_decoded_frames_and_derived_crops",
        "selection": {
            "clock": "decoded PTS relative to first decoded PTS; exact rational comparisons",
            "cutoff_seconds": float(CUTOFF),
            "minimum_interval_seconds": float(INTERVAL),
            "boundary": "also include last decoded frame at or before cutoff, even if closer",
            "max_frames_per_clip": MAX_FRAMES,
        },
        "crop_rectangle_xyxy": list(CROP),
        "crop_coordinates": "left/top inclusive, right/bottom exclusive; crop xy + origin = full-frame xy",
        "records": records,
    }
    (destination / "audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return report

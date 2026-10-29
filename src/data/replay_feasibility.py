"""Bounded offline evidence for the exhibition's first five development PAs.

This tool measures decoded timestamps, not camera/set/mitt identity. Those fields
remain unreviewed until someone actually inspects the saved images.
"""

from __future__ import annotations

import hashlib
import json
import sqlite3
import subprocess
from fractions import Fraction
from pathlib import Path

GAME = 849843
SCHEMA = "pitcheezy-replay-feasibility-v1"


def digest(path):
    with Path(path).open("rb") as stream:
        return hashlib.file_digest(stream, "sha256").hexdigest()


def read_candidates(root, through_pa=1, *, from_pa=1):
    if (
        type(from_pa) is not int
        or type(through_pa) is not int
        or not 1 <= from_pa <= through_pa <= 5
    ):
        raise ValueError("investigation is limited to 1 <= from_pa <= through_pa <= 5")
    root = Path(root).resolve(strict=True)
    with sqlite3.connect((root / "registry.sqlite").as_uri() + "?mode=ro", uri=True) as conn:
        conn.row_factory = sqlite3.Row
        game = conn.execute("SELECT * FROM games WHERE game_pk=?", (GAME,)).fetchone()
        if not game or game["split"] != "dev":
            raise ValueError("849843 must be a registered development game")
        rows = conn.execute(
            "SELECT p.play_id,p.game_pk,p.at_bat_number,p.pitch_number,p.pitcher_name,"
            "p.batter_name,c.status,c.file_path,c.file_sha256,c.bytes FROM pitches p "
            "JOIN clips c USING(play_id) WHERE p.game_pk=? AND p.at_bat_number BETWEEN ? AND ? "
            "ORDER BY p.at_bat_number,p.pitch_number",
            (GAME, from_pa, through_pa),
        ).fetchall()
    if not rows:
        raise ValueError("no registered pitches in investigation")
    result = []
    for record in rows:
        row = dict(record)
        row["pitch_key"] = f"{GAME}:{row['at_bat_number']}:{row['pitch_number']}"
        result.append(row)
    return result


def decode_index(probe):
    if not isinstance(probe, dict):
        raise ValueError("invalid_probe_structure")
    streams = probe.get("streams", [])
    if not isinstance(streams, list) or len(streams) != 1 or not isinstance(streams[0], dict):
        raise ValueError("expected one selected video stream")
    try:
        time_base = Fraction(streams[0]["time_base"])
    except (KeyError, TypeError, ValueError, ZeroDivisionError):
        raise ValueError("invalid_time_base") from None
    if time_base <= 0:
        raise ValueError("invalid time base")
    rows = []
    decoded = probe.get("frames", [])
    if not isinstance(decoded, list) or any(not isinstance(frame, dict) for frame in decoded):
        raise ValueError("invalid_frame_list")
    for ordinal, frame in enumerate(decoded):
        pts = frame.get("pts")
        if type(pts) is not int:
            raise ValueError("frame lacks an integer decoded PTS")
        if rows and pts <= rows[-1]["pts"]:
            raise ValueError("decoded PTS must increase strictly")
        rows.append({"ordinal": ordinal, "pts": pts, "seconds": float(pts * time_base)})
    if not rows:
        raise ValueError("no decoded frames")
    start = rows[0]["pts"]
    for row in rows:
        row["clip_seconds"] = float((row["pts"] - start) * time_base)
    return str(time_base), rows


def sample_frames(rows, interval=0.5):
    """Select decoded frames; never infer frame number from advertised FPS."""
    chosen = [rows[0]]
    for row in rows[1:]:
        if row["clip_seconds"] - chosen[-1]["clip_seconds"] >= interval:
            chosen.append(row)
    if chosen[-1] != rows[-1]:
        chosen.append(rows[-1])
    return chosen


def clip_file(root, row):
    if row["status"] != "downloaded":
        raise ValueError("clip_not_downloaded")
    root = Path(root).resolve(strict=True)
    rel = Path(row["file_path"])
    path = (root / rel).resolve(strict=True)
    if rel.is_absolute() or not path.is_relative_to(root):
        raise ValueError("clip_path_outside_registry")
    if path.stat().st_size != row["bytes"] or digest(path) != row["file_sha256"]:
        raise ValueError("clip_bytes_mismatch")
    return path


def inspect_clip(root, row, destination, ffprobe, ffmpeg):
    from PIL import Image, ImageDraw

    path = clip_file(root, row)
    proc = subprocess.run(
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
    if proc.stderr.strip():
        raise ValueError("decoder_reported_error")
    time_base, frames = decode_index(json.loads(proc.stdout))
    folder = Path(destination) / row["pitch_key"].replace(":", "_")
    folder.mkdir()
    (folder / "ffprobe.json").write_bytes(proc.stdout)
    selected = sample_frames(frames)
    expression = "+".join(f"eq(n\\,{f['ordinal']})" for f in selected)
    subprocess.run(
        [
            str(ffmpeg),
            "-v",
            "error",
            "-i",
            str(path),
            "-vf",
            f"select={expression}",
            "-fps_mode",
            "vfr",
            "-start_number",
            "0",
            str(folder / "frame_%03d.png"),
        ],
        check=True,
        capture_output=True,
        timeout=90,
    )
    images = sorted(folder.glob("frame_*.png"), key=lambda p: int(p.stem.split("_")[-1]))
    if len(images) != len(selected):
        raise ValueError("decoded_image_count_mismatch")
    sheet = Image.new("RGB", (1440, ((len(images) + 2) // 3) * 300), "#14202c")
    draw = ImageDraw.Draw(sheet)
    for index, (image_path, frame) in enumerate(zip(images, selected, strict=True)):
        with Image.open(image_path) as im:
            image_size = list(im.size)
            sheet.paste(im.resize((480, 270)), ((index % 3) * 480, (index // 3) * 300))
        text = f"{row['pitch_key']} n={frame['ordinal']} PTS={frame['pts']} t={frame['clip_seconds']:.3f}s"
        draw.text(((index % 3) * 480 + 5, (index // 3) * 300 + 274), text, fill="white")
        frame["image"] = image_path.relative_to(destination).as_posix()
        frame["image_sha256"] = digest(image_path)
        frame["image_size"] = image_size
    sheet_path = folder / "sheet.jpg"
    sheet.save(sheet_path, quality=92)
    return {
        "pitch_key": row["pitch_key"],
        "play_id": row["play_id"],
        "clip_sha256": row["file_sha256"],
        "clip_bytes": row["bytes"],
        "decode_status": "decoded",
        "time_base": time_base,
        "decoded_frames": len(frames),
        "first_pts": frames[0]["pts"],
        "last_pts": frames[-1]["pts"],
        "pts_source": "ffprobe frame.pts; ffmpeg select decoded ordinal; not nominal fps",
        "probe_sha256": digest(folder / "ffprobe.json"),
        "sampled_frames": selected,
        "sheet": sheet_path.relative_to(destination).as_posix(),
        "sheet_sha256": digest(sheet_path),
        "semantic_review": {
            "status": "unreviewed",
            "setup": "unknown",
            "release": "unknown",
            "replay": "unknown",
            "mitt_identity": "unverified",
        },
    }


def build_audit(root, destination, ffprobe, ffmpeg, through_pa=1, *, from_pa=1):
    from PIL import Image  # noqa: F401 -- fail before creating output if dependency is missing

    destination = Path(destination)
    repo = Path(__file__).resolve().parents[2]
    if any(destination.resolve().is_relative_to(repo / name) for name in ("docs", "web")):
        raise ValueError("private images must stay outside docs and web")
    if destination.exists():
        raise ValueError("new output directory required; preserve previous evidence")
    rows = read_candidates(root, through_pa, from_pa=from_pa)
    destination.mkdir(parents=True)
    records = []
    for row in rows:
        try:
            records.append(inspect_clip(root, row, destination, ffprobe, ffmpeg))
        except (ValueError, OSError, subprocess.SubprocessError) as exc:
            # Keep known, path-free failure codes; do not publish OS paths or tool stderr.
            known = {
                "clip_not_downloaded",
                "clip_path_outside_registry",
                "clip_bytes_mismatch",
                "decoder_reported_error",
                "decoded_image_count_mismatch",
                "invalid_probe_structure",
                "expected one selected video stream",
                "invalid_time_base",
                "invalid time base",
                "invalid_frame_list",
                "frame lacks an integer decoded PTS",
                "decoded PTS must increase strictly",
                "no decoded frames",
            }
            reason = (
                str(exc)
                if isinstance(exc, ValueError) and str(exc) in known
                else type(exc).__name__
            )
            records.append(
                {
                    "pitch_key": row["pitch_key"],
                    "play_id": row["play_id"],
                    "clip_sha256": row["file_sha256"],
                    "decode_status": "failed",
                    "reason": reason,
                    "semantic_review": {"status": "unreviewed"},
                }
            )
    report = {
        "schema": SCHEMA,
        "game_pk": GAME,
        "through_pa": through_pa,
        "source_registry_sha256": digest(Path(root) / "registry.sqlite"),
        "evidence_kind": "offline_decoded_frames_not_human_evaluation",
        "examined": len(rows),
        "decoded": sum(r["decode_status"] == "decoded" for r in records),
        "records": records,
    }
    if from_pa != 1:
        # Missing from_pa continues to mean 1 in existing v1 evidence packs.
        report["from_pa"] = from_pa
    (destination / "audit.json").write_text(
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n", encoding="utf-8"
    )
    return report

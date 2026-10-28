"""Compare saved object references and export private, source-raster SVG overlays."""

import argparse
import base64
import hashlib
import io
import json
import sys
import textwrap
import warnings
from pathlib import Path
from xml.sax.saxutils import escape

from PIL import Image

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.data.object_reference import compare_readings, loads_json, validate_input

ROOT = Path(__file__).resolve().parents[1]
JSON_LIMIT = 8 * 1024 * 1024
IMAGE_LIMIT = 32 * 1024 * 1024


def digest(raw):
    return hashlib.sha256(raw).hexdigest()


def _snapshot(path, limit):
    with Path(path).open("rb") as stream:
        raw = stream.read(limit + 1)
    if len(raw) > limit:
        raise ValueError("input exceeds the size limit")
    return raw


def _is_link(path):
    return path.is_symlink() or getattr(path, "is_junction", lambda: False)()


def _without_links(path):
    absolute = Path(path).absolute()
    if any(_is_link(part) for part in (absolute, *absolute.parents)):
        raise ValueError("symlink/junction paths are not allowed")
    return absolute


def _image_snapshot(frame, source_dir):
    path = _without_links(source_dir / frame["image"])
    try:
        path.resolve().relative_to(source_dir.resolve())
    except ValueError as exc:
        raise ValueError("image escapes the input directory") from exc
    raw = _snapshot(path, IMAGE_LIMIT)
    if digest(raw) != frame["image_sha256"]:
        raise ValueError("image SHA-256 mismatch: " + frame["pitch_key"])
    with warnings.catch_warnings():
        warnings.simplefilter("error", Image.DecompressionBombWarning)
        try:
            with Image.open(io.BytesIO(raw)) as image:
                if image.format != "PNG" or getattr(image, "n_frames", 1) != 1:
                    raise ValueError("only single-frame PNG evidence is supported")
                if image.size != (frame["width"], frame["height"]):
                    raise ValueError("image dimensions mismatch: " + frame["pitch_key"])
                image.verify()
            with Image.open(io.BytesIO(raw)) as image:
                image.load()
        except (
            OSError,
            SyntaxError,
            Image.DecompressionBombError,
            Image.DecompressionBombWarning,
        ) as exc:
            raise ValueError("invalid PNG evidence: " + frame["pitch_key"]) from exc
    return raw


def _xml(value):
    # JSON can contain control characters that XML 1.0 does not permit. Keep the
    # original text in comparison.json; replace only those display characters.
    text = str(value)
    text = "".join(
        ch
        if ch in "\t\n\r"
        or 0x20 <= ord(ch) <= 0xD7FF
        or 0xE000 <= ord(ch) <= 0xFFFD
        or 0x10000 <= ord(ch) <= 0x10FFFF
        else "\ufffd"
        for ch in text
    )
    return escape(text, {'"': "&quot;", "'": "&apos;"})


def overlay_svg(frame, comparison, image_bytes, reviewers):
    """Return an inert SVG containing the exact PNG bytes and source coordinates."""
    width, height = frame["width"], frame["height"]
    left, top, right, bottom = frame["context_crop"]
    crop_width, crop_height = right - left, bottom - top
    canvas_width = max(width, crop_width * 2, 960)
    notes = [
        "AI development references only. Overlap is not accuracy, identity verification, target or intent.",
        "A: " + reviewers["a"]["reviewer_id"] + " / " + reviewers["a"]["model"],
        "B: " + reviewers["b"]["reviewer_id"] + " / " + reviewers["b"]["model"],
    ]
    for obj in comparison["objects"]:
        value = "unavailable" if obj["max_iou"] is None else f"{obj['max_iou']:.6f}"
        notes.append(f"{obj['kind']}: {obj['classification']}; max pair IoU={value}")
        notes.extend(
            f"{side.upper()} {obj['status_' + side]}: {obj['reason_' + side]}"
            for side in ("a", "b")
        )
    lines = [
        line for note in notes for line in textwrap.wrap(note, width=110, replace_whitespace=True)
    ]
    note_y = height + 140 + crop_height * 2
    canvas_height = note_y + 24 * len(lines) + 30
    raster = base64.b64encode(image_bytes).decode("ascii")
    parts = [
        f'<svg xmlns="http://www.w3.org/2000/svg" width="{canvas_width}" height="{canvas_height}" viewBox="0 0 {canvas_width} {canvas_height}">',
        '<rect width="100%" height="100%" fill="#111827"/>',
        "<style>text{font-family:Arial,sans-serif;fill:#fff} .boxlabel{font-size:10px;paint-order:stroke;stroke:#111;stroke-width:2px}</style>",
        f'<text x="12" y="25" font-size="20">{_xml(frame["pitch_key"])} | PTS {_xml(frame["frame_pts"])} | source raster {_xml(width)} x {_xml(height)}</text>',
        '<text x="12" y="50" font-size="16">A cyan solid / B magenta dashed; M=mitt, H=bare hand, G=protective gear. Approximate boxes.</text>',
        '<defs><g id="scene">',
        f'<image width="{width}" height="{height}" href="data:image/png;base64,{raster}"/>',
    ]
    for side, color, dash in (("a", "#00e5ff", ""), ("b", "#ff5de4", ' stroke-dasharray="5 3"')):
        for obj in comparison["objects"]:
            for index, box in enumerate(obj["boxes_" + side], 1):
                x1, y1, x2, y2 = box
                parts.append(
                    f'<rect x="{x1}" y="{y1}" width="{x2 - x1}" height="{y2 - y1}" fill="none" stroke="{color}" stroke-width="2"{dash}/>'
                )
                symbol = {"mitt": "M", "bare_hand": "H", "protective_gear": "G"}[obj["kind"]]
                suffix = str(index) if len(obj["boxes_" + side]) > 1 else ""
                label = f"{side.upper()} {symbol}{suffix}"
                label_y = max(12, y1 - 3) if side == "a" else min(height - 2, y2 + 13)
                parts.append(
                    f'<text class="boxlabel" x="{x1}" y="{label_y}" style="fill:{color}">{_xml(label)}</text>'
                )
    parts.extend(
        [
            "</g></defs>",
            '<use href="#scene" x="0" y="65"/>',
            f'<text x="12" y="{height + 95}" font-size="17">Same source raster: context crop ({left}, {top}) to ({right}, {bottom}), 2x display</text>',
            f'<svg x="0" y="{height + 110}" width="{crop_width * 2}" height="{crop_height * 2}" viewBox="{left} {top} {crop_width} {crop_height}" overflow="hidden"><use href="#scene"/></svg>',
        ]
    )
    parts.extend(
        f'<text x="12" y="{note_y + 24 * i}" font-size="16">{_xml(line)}</text>'
        for i, line in enumerate(lines)
    )
    parts.append("</svg>")
    return ("\n".join(parts) + "\n").encode("utf-8")


def export_comparison(
    input_path, reading_a_path, reading_b_path, destination, *, private_root=None
):
    """Validate all inputs first; never replace a pack or modify any source file."""
    input_path = _without_links(Path(input_path))
    destination = _without_links(Path(destination))
    allowed = _without_links(
        Path(private_root) if private_root is not None else ROOT / "outputs"
    ).resolve()
    try:
        relative = destination.resolve().relative_to(allowed)
    except ValueError as exc:
        raise ValueError("output must be inside the private outputs directory") from exc
    if relative == Path(".") or destination.exists():
        raise ValueError("output must be a new private subdirectory")
    raw_input = _snapshot(input_path, JSON_LIMIT)
    raw_a = _snapshot(_without_links(Path(reading_a_path)), JSON_LIMIT)
    raw_b = _snapshot(_without_links(Path(reading_b_path)), JSON_LIMIT)
    manifest = validate_input(loads_json(raw_input))
    reading_a, reading_b = loads_json(raw_a), loads_json(raw_b)
    report = compare_readings(manifest, digest(raw_input), reading_a, reading_b)
    by_key = {row["pitch_key"]: row for row in report["frames"]}
    exports = {}
    for frame in manifest["frames"]:
        raw_image = _image_snapshot(frame, input_path.parent)
        name = frame["pitch_key"].replace(":", "_") + ".svg"
        exports[name] = overlay_svg(
            frame, by_key[frame["pitch_key"]], raw_image, report["reviewers"]
        )
    report["provenance"] = {
        "source_commit": manifest["source_commit"],
        "source_review_sha256_lf": manifest["source_review_sha256_lf"],
        "input_sha256": digest(raw_input),
        "reading_a_sha256": digest(raw_a),
        "reading_b_sha256": digest(raw_b),
        "hash_meaning": "exact file identity, not source or reviewer authentication",
    }
    report["artifacts"] = [{"path": name, "sha256": digest(raw)} for name, raw in exports.items()]
    exports["comparison.json"] = (
        json.dumps(report, ensure_ascii=False, indent=2, allow_nan=False) + "\n"
    ).encode("utf-8")
    # Validation and rendering finish before any output directory is created.
    destination.mkdir(parents=True, exist_ok=False)
    for name, raw in exports.items():
        with (destination / name).open("xb") as stream:
            stream.write(raw)
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--reading-a", required=True, type=Path)
    parser.add_argument("--reading-b", required=True, type=Path)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args(argv)
    try:
        report = export_comparison(args.input, args.reading_a, args.reading_b, args.out)
    except (ValueError, OSError) as exc:
        parser.exit(2, "comparison rejected: " + str(exc)[:500] + "\n")
    print(json.dumps({"schema": report["schema"], "counts": report["counts"]}))


if __name__ == "__main__":
    main()

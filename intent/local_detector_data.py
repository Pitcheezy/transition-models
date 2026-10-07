"""Prepare private full-frame development inputs and separate legacy point references.

No model runs and no frozen artifact is rewritten. Legacy setup/camera abstentions
are not current mitt-body visibility negatives. The runner must recheck image hashes.
"""

from __future__ import annotations

import argparse
import hashlib
import io
import json
import math
import re
from collections import Counter
from pathlib import Path

from PIL import Image

from intent.human_labels import validate_labels
from intent.replay import _inside, _no_links

ROOT = Path(__file__).resolve().parents[1]
EXPECTED_COUNTS = {823407: 29, 849845: 57}
SCOPE = "development_comparison_to_legacy_single_labeler_points"
LIMITATIONS = [
    "Previously reviewed games; not unseen or independent validation.",
    "Legacy points are not certified equivalent to the current visible mitt-body center.",
    "Legacy setup/camera abstentions are not current-protocol visibility negatives.",
    "Fixed game crops are manual camera regions, not automatic catcher localization.",
    "Point labels provide neither bounding boxes nor segmentation masks.",
    "Post-hoc selected condensed-video frames cannot establish pre-pitch availability.",
]


def _sha(data):
    return hashlib.sha256(data).hexdigest()


def _read(path):
    _no_links(path)
    data = path.read_bytes()
    value = json.loads(data.decode("utf-8-sig"))
    return value, _sha(data)


def _finite(value):
    return type(value) in (int, float) and math.isfinite(value)


def _point(value, width, height, name):
    if (
        not isinstance(value, list)
        or len(value) != 2
        or not all(_finite(v) for v in value)
        or not 0 <= value[0] < width
        or not 0 <= value[1] < height
    ):
        raise ValueError(f"{name} must be a finite in-bounds point")


def _rows(rows, name):
    if not isinstance(rows, list):
        raise ValueError(f"{name} frames must be a list")
    indexed = {}
    for row in rows:
        if not isinstance(row, dict):
            raise ValueError(f"{name} frames must contain objects")
        pid = row.get("pitch_id")
        if not isinstance(pid, str) or not re.fullmatch(r"[1-9]\d*:[1-9]\d*:[1-9]\d*", pid):
            raise ValueError(f"invalid pitch_id in {name}")
        if pid in indexed:
            raise ValueError(f"duplicate pitch_id in {name}: {pid}")
        indexed[pid] = row
    return indexed


def _crop(value, width, height, name):
    if (
        not isinstance(value, list)
        or len(value) != 4
        or any(type(v) is not int for v in value)
        or not 0 <= value[0] < value[2] <= width
        or not 0 <= value[1] < value[3] <= height
    ):
        raise ValueError(f"{name} crop must be an in-bounds integer box")


def _collect_game(results, root, game, expected_count):
    suffixes = {
        "manifest": "intent_label_pack_v0.json",
        "labels": "intent_human_labels_v0.json",
        "raw_labels": "intent_human_labels_raw_v0.json",
        "points": "intent_points_v0.json",
        "source": "condensed_source_v0.json",
    }
    docs, hashes = {}, {}
    for name, suffix in suffixes.items():
        docs[name], hashes[name] = _read(results / f"game_{game}_{suffix}")
    manifest, labels, raw, points, source = (docs[k] for k in suffixes)
    schemas = {
        "manifest": "intent_label_pack_v0",
        "labels": "intent_human_labels_v0",
        "raw_labels": "intent_human_labels_v0",
        "points": "intent_points_v0",
        "source": "intent_condensed_source_v0",
    }
    for name, document in docs.items():
        if document.get("schema") != schemas[name] or document.get("game_pk") != game:
            raise ValueError(f"source schema/game mismatch: {name}")
    if labels.get("raw_sha256") != hashes["raw_labels"]:
        raise ValueError("raw label SHA256 mismatch")
    by_manifest = _rows(manifest.get("frames"), "manifest")
    by_label = _rows(labels.get("frames"), "labels")
    _rows(raw.get("frames"), "raw labels")
    if len(by_manifest) != expected_count or manifest["selection"].get("all_frames") is not True:
        raise ValueError("unexpected frozen development pack count or selection")
    body = json.dumps([[f["pitch_id"], f["image_sha256"]] for f in manifest["frames"]])
    if _sha(body.encode("utf-8"))[:16] != manifest.get("pack_id"):
        raise ValueError("pack_id does not bind the manifest frames")
    if validate_labels(raw, manifest) != validate_labels(labels, manifest):
        raise ValueError("raw/imported human labels disagree")
    point_rows = []
    for point in points["frames"]:
        pa, pitch = point.get("at_bat_number"), point.get("pitch_number")
        if type(pa) is not int or pa <= 0 or type(pitch) is not int or pitch <= 0:
            raise ValueError("invalid points pitch key")
        pid = f"{game}:{pa}:{pitch}"
        if point.get("pitch_id", pid) != pid:
            raise ValueError("points pitch_id disagrees with pitch key")
        point_rows.append(dict(point, pitch_id=pid))
    by_point = _rows(point_rows, "points")
    if by_manifest.keys() != by_label.keys() or by_manifest.keys() != by_point.keys():
        raise ValueError("manifest/labels/points pitch keys differ")
    probe = source["condensed_game"]["probe"]
    width, height = probe.get("width"), probe.get("height")
    if type(width) is not int or type(height) is not int or width <= 0 or height <= 0:
        raise ValueError("invalid source dimensions")
    for name in ("main", "plate"):
        _crop(manifest["crops"][name]["box"], width, height, name)
    frames, references, seen_hashes = [], [], set()
    for pid, frame in by_manifest.items():
        if int(pid.split(":")[0]) != game:
            raise ValueError("pitch_id game mismatch")
        point, label = by_point[pid], by_label[pid]
        digest = frame.get("image_sha256")
        if not isinstance(digest, str) or not re.fullmatch(r"[0-9a-f]{64}", digest):
            raise ValueError("invalid image SHA256")
        if digest in seen_hashes:
            raise ValueError("duplicate source image hash")
        seen_hashes.add(digest)
        if point.get("path") != frame.get("path"):
            raise ValueError("points/manifest image path mismatch")
        for row in (frame, point, label):
            if row.get("image_sha256") != digest:
                raise ValueError("source image hash correspondence mismatch")
            time = row.get("frame_seconds")
            if not _finite(time) or time < 0 or time != frame.get("frame_seconds"):
                raise ValueError("source frame time mismatch")
        path = _inside(root, frame["path"])
        data = path.read_bytes()
        if _sha(data) != digest:
            raise ValueError(f"image SHA256 mismatch for {pid}")
        with Image.open(io.BytesIO(data)) as image:
            if image.format != "JPEG" or image.size != (width, height):
                raise ValueError("full-frame image dimensions/format mismatch")
            image.load()
        if label["mitt_status"] is None:
            raise ValueError("legacy human reference is undecided")
        if label["mitt_status"] == "marked":
            _point(label["mitt"], width, height, "human mitt")
        if label["plate_status"] == "marked":
            for endpoint in ("left_end", "right_end"):
                _point(label["plate_front"][endpoint], width, height, "human plate")
        frames.append(
            {
                "observation_id": pid,
                "game_pk": game,
                "image_path": str(path),
                "image_sha256": digest,
                "width": width,
                "height": height,
                "legacy_main_crop": manifest["crops"]["main"]["box"],
            }
        )
        references.append(
            {
                "observation_id": pid,
                "game_pk": game,
                "image_sha256": digest,
                "legacy_mitt_status": label["mitt_status"],
                "mitt": label["mitt"],
            }
        )
    return (
        frames,
        references,
        {
            "game_pk": game,
            "source_sha256": hashes,
            "frames": len(frames),
            "legacy_mitt_status_counts": dict(Counter(r["legacy_mitt_status"] for r in references)),
        },
    )


def _encode(document):
    return (json.dumps(document, ensure_ascii=False, indent=2, allow_nan=False) + "\n").encode()


def prepare(results_dir, frames_root, out):
    """Validate all 86 source frames before writing a fresh private three-file package."""
    results, root, out = (Path(p).absolute() for p in (results_dir, frames_root, out))
    for path in (results, root, out):
        _no_links(path)
    results, root, out = results.resolve(), root.resolve(), out.resolve()
    if not results.is_relative_to(root):
        raise ValueError("source results directory must stay inside frames-root")
    if out.exists():
        raise ValueError("output already exists; choose a fresh directory")
    if not out.is_relative_to(root / "outputs") or out == root / "outputs":
        raise ValueError("private package must be a new directory inside frames-root/outputs")
    frames, references, games = [], [], []
    for game, count in EXPECTED_COUNTS.items():
        f, r, audit = _collect_game(results, root, game, count)
        frames.extend(f)
        references.extend(r)
        games.append(audit)
    if len({f["image_sha256"] for f in frames}) != len(frames):
        raise ValueError("duplicate source image hash across games")
    manifest = _encode({"schema": "local_glove_frames_v1", "scope": SCOPE, "frames": frames})
    reference_bytes = _encode(
        {
            "schema": "local_glove_references_v1",
            "manifest_sha256": _sha(manifest),
            "scope": SCOPE,
            "limitations": LIMITATIONS,
            "sources": games,
            "references": references,
        }
    )
    audit = {
        "schema": "local_glove_data_audit_v1",
        "scope": SCOPE,
        "limitations": LIMITATIONS,
        "manifest_sha256": _sha(manifest),
        "references_sha256": _sha(reference_bytes),
        "frames": len(frames),
        "source_image_bytes_verified": len(frames),
        "games": games,
    }
    # All input checks and serialization precede the first filesystem mutation.
    payloads = {
        "manifest.json": manifest,
        "references.json": reference_bytes,
        "audit.json": _encode(audit),
    }
    out.mkdir(parents=True, exist_ok=False)
    for name, data in payloads.items():
        with (out / name).open("xb") as stream:
            stream.write(data)
    return audit


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--results-dir", type=Path, default=ROOT / "docs/results/mlb_p0")
    parser.add_argument("--frames-root", type=Path, default=ROOT)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args(argv)
    audit = prepare(args.results_dir, args.frames_root, args.out)
    print(json.dumps(audit, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()

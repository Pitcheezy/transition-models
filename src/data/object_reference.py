"""Compare bounded AI object references; overlap is not identity or accuracy evidence.

The pure validators bind readings to a fixed manifest. The caller must separately
verify manifest/image bytes and record actual model invocation evidence.
"""

from __future__ import annotations

import json
import math
import re
from pathlib import Path
from uuid import UUID

INPUT_SCHEMA = "pitcheezy-object-reference-input-v1"
READING_SCHEMA = "pitcheezy-object-reference-reading-v1"
COMPARISON_SCHEMA = "pitcheezy-object-reference-comparison-v1"
COORDINATE_SYSTEM = "source_raster_xyxy_half_open"
KINDS = ("mitt", "bare_hand", "protective_gear")
STATUSES = ("located", "unclear", "not_visible")
CLASSIFICATIONS = (
    "located_pair_disjoint",
    "located_pair_with_overlap",
    "both_not_visible",
    "one_or_both_unresolved",
)
IDENTITY_FIELDS = (
    "pitch_key",
    "play_id",
    "clip_sha256",
    "frame_pts",
    "time_base",
    "image_sha256",
)
INPUT_FIELDS = {"schema", "source_commit", "source_review_sha256_lf", "game_pk", "frames"}
FRAME_FIELDS = set(IDENTITY_FIELDS) | {"image", "width", "height", "context_crop"}
READING_FIELDS = {
    "schema",
    "input_sha256",
    "reviewer_id",
    "model",
    "prior_exposure",
    "coordinate_system",
    "frames",
}
OBJECT_FIELDS = {"kind", "status", "boxes", "reason"}


def _object_pairs(pairs):
    obj = {}
    for key, value in pairs:
        if key in obj:
            raise ValueError(f"duplicate JSON key: {key}")
        obj[key] = value
    return obj


def _constant(value):
    raise ValueError(f"nonfinite JSON number: {value}")


def _finite_float(value):
    number = float(value)
    if not math.isfinite(number):
        raise ValueError("nonfinite JSON number")
    return number


def loads_json(raw):
    """Parse captured UTF-8 bytes/text without accepting duplicate keys or NaN."""
    try:
        if type(raw) is bytes:
            raw = raw.decode("utf-8")
        if type(raw) is not str:
            raise ValueError("JSON must be UTF-8 bytes or text")
        value = json.loads(
            raw,
            object_pairs_hook=_object_pairs,
            parse_constant=_constant,
            parse_float=_finite_float,
        )
    except UnicodeDecodeError as exc:
        raise ValueError("JSON must be UTF-8") from exc
    except RecursionError as exc:
        raise ValueError("JSON nesting too deep") from exc
    if type(value) is not dict:
        raise ValueError("JSON root must be an object")
    return value


def load_json(path):
    """Read and parse one immutable snapshot of the file bytes."""
    return loads_json(Path(path).read_bytes())


def _fields(value, expected, label):
    if type(value) is not dict or set(value) != expected:
        raise ValueError(f"{label}: unexpected or missing fields")


def _text(value, label, limit=200):
    if (
        type(value) is not str
        or not value.strip()
        or len(value) > limit
        or any(ord(char) < 32 and char not in "\n\t" for char in value)
    ):
        raise ValueError(f"{label}: expected nonempty bounded text")
    try:
        value.encode("utf-8")
    except UnicodeEncodeError as exc:
        raise ValueError(f"{label}: invalid Unicode scalar") from exc


def _hex(value, length, label):
    if type(value) is not str or re.fullmatch(rf"[0-9a-f]{{{length}}}", value) is None:
        raise ValueError(f"{label}: expected lowercase hexadecimal digest")


def _integer(value, label, minimum=0, maximum=2**63 - 1):
    if type(value) is not int or not minimum <= value <= maximum:
        raise ValueError(f"{label}: expected bounded integer")


def _box(value, width, height, label):
    if type(value) is not list or len(value) != 4 or any(type(x) is not int for x in value):
        raise ValueError(f"{label}: expected four integer coordinates")
    left, top, right, bottom = value
    if not (0 <= left < right <= width and 0 <= top < bottom <= height):
        raise ValueError(f"{label}: box must lie inside source frame")


def _image_name(value):
    # Use a deliberately narrow POSIX relative-path language on every platform.
    if type(value) is not str or not 1 <= len(value) <= 240:
        raise ValueError("image: invalid relative path")
    parts = value.split("/")
    if any(
        part in {"", ".", ".."}
        or re.fullmatch(r"[A-Za-z0-9_-][A-Za-z0-9_.-]*", part) is None
        or part.endswith(".")
        or part.split(".", 1)[0].upper()
        in {
            "CON",
            "PRN",
            "AUX",
            "NUL",
            *(f"COM{i}" for i in range(10)),
            *(f"LPT{i}" for i in range(10)),
        }
        for part in parts
    ):
        raise ValueError("image: unsafe relative path")


def _identity(frame, game):
    pitch = frame["pitch_key"]
    if (
        type(pitch) is not str
        or re.fullmatch(r"[1-9][0-9]{0,10}:[1-9][0-9]{0,5}:[1-9][0-9]{0,5}", pitch) is None
        or int(pitch.split(":")[0]) != game
    ):
        raise ValueError("pitch_key: invalid game or pitch identity")
    play = frame["play_id"]
    try:
        if type(play) is not str or str(UUID(play)) != play:
            raise ValueError("noncanonical UUID")
    except (ValueError, AttributeError) as exc:
        raise ValueError("play_id: expected canonical UUID") from exc
    _hex(frame["clip_sha256"], 64, "clip_sha256")
    _hex(frame["image_sha256"], 64, "image_sha256")
    _integer(frame["frame_pts"], "frame_pts")
    tb = frame["time_base"]
    if type(tb) is not str or re.fullmatch(r"[1-9][0-9]{0,11}/[1-9][0-9]{0,11}", tb) is None:
        raise ValueError("time_base: expected positive integer ratio")


def validate_input(manifest):
    """Validate identity/shape only, without changing the manifest or opening images."""
    _fields(manifest, INPUT_FIELDS, "input")
    if manifest["schema"] != INPUT_SCHEMA:
        raise ValueError("input: wrong schema")
    _hex(manifest["source_commit"], 40, "source_commit")
    _hex(manifest["source_review_sha256_lf"], 64, "source_review_sha256_lf")
    game = manifest["game_pk"]
    _integer(game, "game_pk", 1, 99_999_999_999)
    if game == 849844:
        raise ValueError("evaluation-locked game must not be used for development")
    frames = manifest["frames"]
    if type(frames) is not list or not 1 <= len(frames) <= 100:
        raise ValueError("frames: expected 1..100 frames")
    seen_keys, seen_plays, seen_images = set(), set(), set()
    for frame in frames:
        _fields(frame, FRAME_FIELDS, "input frame")
        _identity(frame, game)
        _integer(frame["width"], "width", 1, 32768)
        _integer(frame["height"], "height", 1, 32768)
        _box(frame["context_crop"], frame["width"], frame["height"], "context_crop")
        _image_name(frame["image"])
        image = frame["image"].casefold()
        if (
            frame["pitch_key"] in seen_keys
            or frame["play_id"] in seen_plays
            or image in seen_images
        ):
            raise ValueError("input frames: duplicate pitch, play or image")
        seen_keys.add(frame["pitch_key"])
        seen_plays.add(frame["play_id"])
        seen_images.add(image)
    return manifest


def validate_reading(reading, manifest, input_sha256):
    """Bind one response to all exact source identities, independent of list order."""
    validate_input(manifest)
    _hex(input_sha256, 64, "input_sha256 argument")
    _fields(reading, READING_FIELDS, "reading")
    if reading["schema"] != READING_SCHEMA:
        raise ValueError("reading: wrong schema")
    if reading["input_sha256"] != input_sha256:
        raise ValueError("reading: input_sha256 mismatch")
    if reading["coordinate_system"] != COORDINATE_SYSTEM:
        raise ValueError("reading: wrong coordinate_system")
    for name in ("reviewer_id", "model", "prior_exposure"):
        _text(reading[name], name)
    rows = reading["frames"]
    if type(rows) is not list or len(rows) != len(manifest["frames"]):
        raise ValueError("reading frames: missing or extra frame")
    expected = {frame["pitch_key"]: frame for frame in manifest["frames"]}
    seen = set()
    for row in rows:
        _fields(row, set(IDENTITY_FIELDS) | {"objects"}, "reading frame")
        _identity(row, manifest["game_pk"])
        key = row["pitch_key"]
        if key not in expected or key in seen:
            raise ValueError("reading frames: unknown or duplicate pitch")
        seen.add(key)
        frame = expected[key]
        if any(row[name] != frame[name] for name in IDENTITY_FIELDS):
            raise ValueError("reading frame: source identity mismatch")
        objects = row["objects"]
        if type(objects) is not list or len(objects) != len(KINDS):
            raise ValueError("objects: each of the three kinds is required")
        kinds = set()
        for obj in objects:
            _fields(obj, OBJECT_FIELDS, "object")
            kind, status, boxes = obj["kind"], obj["status"], obj["boxes"]
            if type(kind) is not str or kind not in KINDS or kind in kinds:
                raise ValueError("object: unknown or duplicate kind")
            kinds.add(kind)
            if type(status) is not str or status not in STATUSES:
                raise ValueError("object: unknown status")
            _text(obj["reason"], "reason", 2000)
            if type(boxes) is not list:
                raise ValueError("boxes: expected list")
            if status == "located":
                if not 1 <= len(boxes) <= 4:
                    raise ValueError("located: 1..4 boxes required")
            elif boxes:
                raise ValueError("unresolved/not_visible objects must not have boxes")
            for box in boxes:
                _box(box, frame["width"], frame["height"], "object box")
            if len({tuple(box) for box in boxes}) != len(boxes):
                raise ValueError("boxes: duplicate box")
    return reading


def _iou(a, b):
    intersection = max(0, min(a[2], b[2]) - max(a[0], b[0])) * max(
        0, min(a[3], b[3]) - max(a[1], b[1])
    )
    area_a = (a[2] - a[0]) * (a[3] - a[1])
    area_b = (b[2] - b[0]) * (b[3] - b[1])
    return intersection / (area_a + area_b - intersection)


def compare_readings(manifest, input_sha256, a, b):
    """Describe geometric overlap, never a score of correctness or model agreement."""
    validate_reading(a, manifest, input_sha256)
    validate_reading(b, manifest, input_sha256)
    if a["reviewer_id"] == b["reviewer_id"]:
        raise ValueError("two distinct reviewer IDs required; this is not model authentication")
    indexes = [{row["pitch_key"]: row for row in reading["frames"]} for reading in (a, b)]
    counts = dict.fromkeys(CLASSIFICATIONS, 0)
    frames = []
    for frame in manifest["frames"]:
        key = frame["pitch_key"]
        pairs = [{obj["kind"]: obj for obj in index[key]["objects"]} for index in indexes]
        compared = []
        for kind in KINDS:
            first, second = pairs[0][kind], pairs[1][kind]
            matrix, maximum = [], None
            if first["status"] == second["status"] == "located":
                matrix = [[_iou(x, y) for y in second["boxes"]] for x in first["boxes"]]
                maximum = max(max(row) for row in matrix)
                classification = (
                    "located_pair_with_overlap" if maximum > 0 else "located_pair_disjoint"
                )
            elif first["status"] == second["status"] == "not_visible":
                classification = "both_not_visible"
            else:
                classification = "one_or_both_unresolved"
            counts[classification] += 1
            compared.append(
                {
                    "kind": kind,
                    "status_a": first["status"],
                    "status_b": second["status"],
                    "boxes_a": [box[:] for box in first["boxes"]],
                    "boxes_b": [box[:] for box in second["boxes"]],
                    "reason_a": first["reason"],
                    "reason_b": second["reason"],
                    "pairwise_ious": matrix,
                    "max_iou": maximum,
                    "classification": classification,
                }
            )
        frames.append({**{name: frame[name] for name in IDENTITY_FIELDS}, "objects": compared})
    return {
        "schema": COMPARISON_SCHEMA,
        "input_sha256": input_sha256,
        "coordinate_system": COORDINATE_SYSTEM,
        "reviewers": {
            slot: {name: reading[name] for name in ("reviewer_id", "model", "prior_exposure")}
            for slot, reading in (("a", a), ("b", b))
        },
        "counts": {
            "frames": len(frames),
            "object_comparisons": len(frames) * len(KINDS),
            "classifications": counts,
        },
        "frames": frames,
    }

"""Source-bound, identity-checked manual broadcast timing annotations."""

import json
import math
from collections import Counter, defaultdict

SCHEMA = "mlb_broadcast_timing_v1"
KEYS = ("game_pk", "at_bat_number", "pitch_number")


def _positive_integer(value):
    return type(value) is int and value > 0


def _number(value, name):
    if type(value) not in (int, float) or not math.isfinite(value) or value < 0:
        raise ValueError(f"{name} must be a finite nonnegative number")
    return value


def timing_context(manifest, sources):
    """Bind annotations to an exact manifest and inspected full-game media URL."""
    # Loading crypto/network DLLs before Torch + Arrow hangs on the Windows runtime.
    # Offline annotation helpers need these only when validating an actual source.
    import hashlib

    from src.data.mlb_sources import validate_mlb_url

    if manifest.get("schema") != "mlb_video_manifest_v1":
        raise ValueError("Unsupported video manifest")
    game = manifest.get("game_pk")
    if not _positive_integer(game) or sources.get("game_pk") != game:
        raise ValueError("Source game does not match manifest")
    pitches = manifest.get("pitches", [])
    seen, play_ids = set(), set()
    for pitch in pitches:
        key = tuple(pitch.get(k) for k in KEYS)
        play_id = pitch.get("video", {}).get("play_id")
        if (
            not all(_positive_integer(v) for v in key)
            or key[0] != game
            or pitch.get("identity_status") != "verified"
            or not isinstance(play_id, str)
            or not play_id
            or key in seen
            or play_id in play_ids
        ):
            raise ValueError("Expected unique verified pitch identities")
        seen.add(key)
        play_ids.add(play_id)
    if not pitches:
        raise ValueError("Empty manifest")
    source = sources["sources"]["full_game"]
    inspection = source.get("inspection")
    if not inspection or inspection["url"] not in source["observed_mp4_urls"]:
        raise ValueError("Full-game source requires an inspected observed media URL")
    duration = float(inspection["probe"]["format"]["duration"])
    if _number(duration, "duration") <= 0:
        raise ValueError("duration must be positive")
    canonical = json.dumps(manifest, sort_keys=True, ensure_ascii=False, allow_nan=False)
    return {
        "schema": SCHEMA,
        "game_pk": game,
        "manifest_sha256": hashlib.sha256(canonical.encode()).hexdigest(),
        "source": {
            "page_url": validate_mlb_url(source["page_url"]),
            "media_url": validate_mlb_url(inspection["url"]),
            "duration_seconds": duration,
        },
    }


def validate_annotations(document, manifest, sources):
    """Reject wrong identities, sources, timing, and false coverage claims."""
    context = timing_context(manifest, sources)
    if set(document) != {*context, "annotator", "annotations"}:
        raise ValueError("Unexpected annotation document fields")
    for field, expected in context.items():
        if document[field] != expected:
            raise ValueError(f"Annotation {field} does not match the inspected source")
    if not isinstance(document["annotator"], str) or not document["annotator"].strip():
        raise ValueError("annotator is required")
    if not isinstance(document["annotations"], list):
        raise ValueError("annotations must be a list")
    index = {tuple(p[k] for k in KEYS): p for p in manifest["pitches"]}
    seen, timed, counts = set(), [], Counter()
    required = {
        *KEYS,
        "play_id",
        "status",
        "decision_seconds",
        "release_seconds",
        "uncertainty_seconds",
        "note",
    }
    for row in document["annotations"]:
        if not isinstance(row, dict) or set(row) != required:
            raise ValueError("Unexpected annotation row fields")
        key = tuple(row[k] for k in KEYS)
        if not all(_positive_integer(v) for v in key) or key not in index or key in seen:
            raise ValueError("Unknown or duplicate pitch identity")
        seen.add(key)
        if row["play_id"] != index[key]["video"]["play_id"]:
            raise ValueError("play_id does not match pitch identity")
        if not isinstance(row["note"], str) or not row["note"].strip():
            raise ValueError("An observation note is required")
        status = row["status"]
        if status == "annotated":
            decision = _number(row["decision_seconds"], "decision_seconds")
            release = _number(row["release_seconds"], "release_seconds")
            uncertainty = _number(row["uncertainty_seconds"], "uncertainty_seconds")
            if uncertainty <= 0:
                raise ValueError("Manual timing requires positive uncertainty")
            if not 0 <= decision - uncertainty < decision + uncertainty < release - uncertainty:
                raise ValueError("Decision must precede release outside the uncertainty bounds")
            if release + uncertainty > context["source"]["duration_seconds"]:
                raise ValueError("Release exceeds source duration")
            timed.append((key, decision - uncertainty, release + uncertainty))
        elif status == "unavailable":
            if any(
                row[k] is not None
                for k in ("decision_seconds", "release_seconds", "uncertainty_seconds")
            ):
                raise ValueError("Unavailable pitches must not have invented timestamps")
        else:
            raise ValueError("Expected annotated or unavailable status")
        counts[status] += 1
    ordered = sorted(timed)
    if any(b[1] <= a[2] for a, b in zip(ordered, ordered[1:], strict=False)):
        raise ValueError("Pitch intervals overlap or contradict chronological pitch order")
    by_pa = defaultdict(set)
    for key in index:
        by_pa[key[1]].add(key)
    timed_keys = {key for key, _, _ in timed}
    return {
        "schema": "mlb_broadcast_timing_validation_v1",
        "game_pk": context["game_pk"],
        "manifest_sha256": context["manifest_sha256"],
        "source": context["source"],
        "total_pitches": len(index),
        "annotated": counts["annotated"],
        "unavailable": counts["unavailable"],
        "unreviewed": len(index) - len(seen),
        "complete_plate_appearances": sorted(
            pa for pa, keys in by_pa.items() if keys <= timed_keys
        ),
        "note": "Manual visual timing only; reference states are recorded metadata, not OCR.",
    }

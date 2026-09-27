"""Prepare answer-free broadcast review packages and validate independent responses."""

import json
import math
import re
from collections import Counter
from datetime import date
from pathlib import Path
from zipfile import ZIP_DEFLATED, ZipFile

from src.data.broadcast_timing import KEYS, timing_context, validate_annotations
from src.data.scoreboard_evalset import LABEL_FIELDS, validate_review

SCHEMA = "mlb_blind_review_v2"
STUDY = "game_747139_ay_v1"
SEED = "ay-v1|20260927"
ROOT = Path(__file__).resolve().parents[2]
REVIEWER_ASSETS = (
    "src/web/static/blind_review.html",
    "src/web/static/blind_review.js",
    "docs/templates/BLIND_REVIEW_README.md",
)
INPUTS = {
    name: f"docs/results/mlb_p0/game_747139_{suffix}.json"
    for name, suffix in (
        ("manifest", "manifest"),
        ("sources", "sources"),
        ("timing", "timing"),
        ("review", "scoreboard_review"),
    )
}
BOUNDARIES = (
    (1, 3, "Historical off-grid reference; retain and disclose when comparing"),
    (6, 2, "Earlier search lower bound"),
    (8, 1, "Partial line score"),
    (14, 1, "Long preparation interval"),
    (20, 4, "Rubber arrival interpretation"),
    (24, 4, "Rubber arrival interpretation"),
    (39, 2, "Alternate live angle omits batter"),
    (56, 1, "Stationary interval shorter than decision grid"),
    (66, 2, "Short valid preparation window"),
    (80, 7, "Late camera return"),
    (81, 3, "Wide low-resolution live view"),
    (82, 5, "Earlier preparation interrupted by cutaway"),
)
TIMES = ("decision_seconds", "release_seconds", "uncertainty_seconds")
IDENTITY = (*KEYS, "play_id")


def canonical_hash(value):
    """Hash canonical JSON, independently of indentation or platform newlines."""
    import hashlib

    return hashlib.sha256(
        json.dumps(value, sort_keys=True, ensure_ascii=False, allow_nan=False).encode("utf-8")
    ).hexdigest()


def _reviewer_assets():
    """Read reviewer instructions and renderer with platform-independent newlines."""
    return {
        path: (ROOT / path).read_bytes().decode("utf-8").replace("\r\n", "\n").replace("\r", "\n")
        for path in REVIEWER_ASSETS
    }


def _reviewer_assets_hash(assets):
    """Bind the normalized content of every reviewer asset, including instructions."""
    import hashlib

    return canonical_hash(
        {
            path: hashlib.sha256(content.encode("utf-8")).hexdigest()
            for path, content in assets.items()
        }
    )


def read_json(path):
    """Reject duplicate object fields and non-standard JSON numeric constants."""

    def unique(pairs):
        result = {}
        for key, value in pairs:
            if key in result:
                raise ValueError(f"Duplicate JSON field: {key}")
            result[key] = value
        return result

    def bad_constant(value):
        raise ValueError(f"Non-finite JSON value: {value}")

    return json.loads(
        Path(path).read_text(encoding="utf-8"),
        object_pairs_hook=unique,
        parse_constant=bad_constant,
    )


def core_sample(pitches, count=32):
    """Rank only pitch identities; selection never reads timings or outcomes."""
    import hashlib

    def rank(row):
        key = tuple(row[k] for k in KEYS)
        digest = hashlib.sha256(f"{SEED}|{'|'.join(map(str, key))}".encode()).hexdigest()
        return digest, key

    if len(pitches) < count:
        raise ValueError("Population is smaller than the registered core sample")
    return sorted(sorted(pitches, key=rank)[:count], key=lambda r: tuple(r[k] for k in KEYS))


def freeze_protocol(inputs, baseline_commit):
    """Register the fixed study before independent responses are examined."""
    if not re.fullmatch(r"[0-9a-f]{40}", baseline_commit):
        raise ValueError("A full baseline commit SHA is required")
    manifest, sources, timing, review = (inputs[k] for k in INPUTS)
    context = timing_context(manifest, sources)
    validation = validate_annotations(timing, manifest, sources)
    reviews = validate_review(review, manifest, timing)
    if (
        context["game_pk"] != 747139
        or validation["total_pitches"] != 322
        or validation["unreviewed"]
        or len(reviews) != validation["annotated"]
    ):
        raise ValueError("Study requires the complete game 747139 baseline")
    index = {tuple(p[k] for k in KEYS): p for p in manifest["pitches"]}

    def identity(p):
        return {**{k: p[k] for k in KEYS}, "play_id": p["video"]["play_id"]}

    return {
        "schema": "mlb_blind_review_protocol_v1",
        "study_id": STUDY,
        "registered_at": "2026-09-27",
        "baseline_commit": baseline_commit,
        "baseline_kind": "AI-assisted manual reference; not frame-exact ground truth",
        "inputs": {
            name: {"path": path, "canonical_sha256": canonical_hash(inputs[name])}
            for name, path in INPUTS.items()
        },
        "manifest_sha256": context["manifest_sha256"],
        "source": context["source"],
        "selection": {
            "population": 322,
            "core_size": 32,
            "rank": "SHA256(UTF8(seed|game_pk|at_bat_number|pitch_number)); ascending hex, key tie-break",
            "seed": SEED,
            "core": [identity(p) for p in core_sample(manifest["pitches"])],
            "boundary": [
                {**identity(index[(747139, pa, pitch)]), "reason": reason}
                for pa, pitch, reason in BOUNDARIES
            ],
            "overlap": "Keep overlap in each stratum; one review per unique identity. Do not pool.",
        },
        "comparison": {
            "status": "Report all selected rows: annotated/unavailable/unreviewed cross-tab and counts",
            "timing_population": "Both annotated only; report denominator and all exclusions",
            "timing_difference": "New reviewer minus frozen reference; signed/absolute median and max",
            "decision_absolute_thresholds_seconds": [0.25, 0.5],
            "release_absolute_thresholds_seconds": [0.15, 0.3],
            "threshold_role": "Descriptive shares, not acceptance gates; do not change after review",
            "scoreboard": "Per field: both readable agreement; one-null and both-null counts separately",
            "null_rule": "Null/null is never a correct reading; preserve false, zero and null separately",
            "frame_confound": "Readings at each reviewer's own frame conflate timing and reading differences",
            "strata": "Core and diagnostic boundary results separate; no whole-game or OCR accuracy claim",
            "blindness": "Cooperative blinding in a public repo; disclose prior exposure and human/ai/mixed",
            "reference_exception": "PA 1/3 reference decision is off the 0.25s grid; retain it and flag",
            "missing": "Never drop unlocated pitches or infer unavailable from playback/extraction failure",
            "blank": "No agreement output for blank forms; receipt validation is not agreement measurement",
        },
    }


def template_from_protocol(protocol):
    """Use an explicit allow-list, never serialize the reference or organizer document."""
    return _template_from_protocol(protocol, _reviewer_assets_hash(_reviewer_assets()))


def _template_from_protocol(protocol, reviewer_assets_sha256):
    """Bind a blank response to a frozen protocol and the reviewed asset version."""
    from src.data.mlb_sources import validate_mlb_url

    if protocol.get("schema") != "mlb_blind_review_protocol_v1" or protocol["study_id"] != STUDY:
        raise ValueError("Unsupported blind review protocol")
    if not isinstance(protocol.get("manifest_sha256"), str) or not re.fullmatch(
        r"[0-9a-f]{64}", protocol["manifest_sha256"]
    ):
        raise ValueError("Invalid protocol manifest hash")
    source = {k: protocol["source"][k] for k in ("page_url", "media_url", "duration_seconds")}
    for name in ("page_url", "media_url"):
        validate_mlb_url(source[name])
    duration = source["duration_seconds"]
    if type(duration) not in (int, float) or not math.isfinite(duration) or duration <= 0:
        raise ValueError("Source duration must be finite and positive")
    for name, size in (("core", 32), ("boundary", 12)):
        rows = protocol["selection"][name]
        if len(rows) != size or len({tuple(r[k] for k in KEYS) for r in rows}) != size:
            raise ValueError("Protocol stratum has wrong size or duplicate identities")
    index = {}
    for row in protocol["selection"]["core"] + protocol["selection"]["boundary"]:
        identity = {k: row[k] for k in IDENTITY}
        if (
            not all(type(identity[k]) is int and identity[k] > 0 for k in KEYS)
            or identity["game_pk"] != 747139
            or not isinstance(identity["play_id"], str)
            or not identity["play_id"].strip()
        ):
            raise ValueError("Invalid protocol identity")
        key = tuple(identity[k] for k in KEYS)
        if key in index and index[key] != identity:
            raise ValueError("Conflicting protocol identities")
        index[key] = identity
    if len({r["play_id"] for r in index.values()}) != len(index):
        raise ValueError("Protocol play IDs must be unique")
    immutable = {
        "schema": SCHEMA,
        "study_id": protocol["study_id"],
        "protocol_sha256": canonical_hash(protocol),
        "manifest_sha256": protocol["manifest_sha256"],
        "reviewer_assets_sha256": reviewer_assets_sha256,
        "source": source,
        "identities": [index[k] for k in sorted(index)],
    }
    return {
        **{k: v for k, v in immutable.items() if k != "identities"},
        "package_id": canonical_hash(immutable),
        "reviewer": {
            "name": "",
            "kind": None,
            "reviewed_at": None,
            "prior_reference_exposure": None,
        },
        "rows": [
            {
                **identity,
                "status": "unreviewed",
                **dict.fromkeys(TIMES),
                "readability": None,
                "observed": dict.fromkeys(LABEL_FIELDS),
                "note": "",
            }
            for identity in immutable["identities"]
        ],
    }


def _fields(value, expected, description):
    if not isinstance(value, dict) or set(value) != set(expected):
        raise ValueError(f"Unexpected {description} fields")


def _observed(observed):
    _fields(observed, LABEL_FIELDS, "observed")
    for name, value in observed.items():
        if value is None:
            continue
        if name.startswith("runner_on_"):
            valid = type(value) is bool
        elif name == "inning_topbot":
            valid = value in ("Top", "Bot")
        else:
            minimum = 1 if name == "inning" else 0
            maximum = {"balls": 3, "strikes": 2, "outs": 2}.get(name)
            valid = type(value) is int and value >= minimum
            if maximum is not None:
                valid = valid and value <= maximum
        if not valid:
            raise ValueError(f"Invalid observed value: {name}")


def validate_response(document, template, require_complete=False):
    """Validate source, exact identities and typed readings without scoring agreement."""
    if not isinstance(document, dict) or document.get("schema") != SCHEMA:
        raise ValueError(
            f"Expected asset-bound response schema {SCHEMA}; unbound v1 responses are unsupported"
        )
    _fields(document, template, "document")
    for name in set(template) - {"reviewer", "rows"}:
        if canonical_hash(document[name]) != canonical_hash(template[name]):
            raise ValueError(f"Response {name} does not match package")
    reviewer = document["reviewer"]
    _fields(reviewer, template["reviewer"], "reviewer")
    if not isinstance(reviewer["name"], str):
        raise ValueError("Reviewer name must be text")
    if reviewer["kind"] not in (None, "human", "ai", "mixed"):
        raise ValueError("Invalid reviewer kind")
    if (
        reviewer["prior_reference_exposure"] is not None
        and type(reviewer["prior_reference_exposure"]) is not bool
    ):
        raise ValueError("Exposure must be true, false or null")
    if reviewer["reviewed_at"] is not None:
        value = reviewer["reviewed_at"]
        if not isinstance(value, str) or not re.fullmatch(r"\d{4}-\d{2}-\d{2}", value):
            raise ValueError("Review date must be YYYY-MM-DD")
        date.fromisoformat(value)
    expected = {tuple(r[k] for k in KEYS): r for r in template["rows"]}
    if not isinstance(document["rows"], list):
        raise ValueError("Rows must be a list")
    seen, intervals, counts = set(), [], Counter()
    for row in document["rows"]:
        _fields(row, template["rows"][0], "row")
        if not all(type(row[k]) is int and row[k] > 0 for k in KEYS):
            raise ValueError("Pitch keys must be positive integers")
        key = tuple(row[k] for k in KEYS)
        if key not in expected or key in seen or row["play_id"] != expected[key]["play_id"]:
            raise ValueError("Unknown, duplicate or mismatched pitch identity")
        seen.add(key)
        status = row["status"]
        if status not in ("unreviewed", "annotated", "unavailable"):
            raise ValueError("Invalid review status")
        if not isinstance(row["note"], str) or (status != "unreviewed" and not row["note"].strip()):
            raise ValueError("Reviewed rows require evidence or an unavailable reason in note")
        _observed(row["observed"])
        legible = sum(value is not None for value in row["observed"].values())
        if status == "annotated":
            for field in TIMES:
                value = row[field]
                if type(value) not in (float, int) or not math.isfinite(value) or value < 0:
                    raise ValueError(f"Invalid finite timestamp: {field}")
            decision, release, uncertainty = (row[f] for f in TIMES)
            if not (
                uncertainty > 0
                and 0 <= decision - uncertainty < decision + uncertainty < release - uncertainty
                and release + uncertainty <= template["source"]["duration_seconds"]
            ):
                raise ValueError("Timing exceeds source or uncertainty bounds")
            if not math.isclose(decision * 4, round(decision * 4), abs_tol=1e-7, rel_tol=0):
                raise ValueError("Decision must follow the registered 0.25 second grid")
            if not (
                (row["readability"] == "readable" and legible == len(LABEL_FIELDS))
                or (row["readability"] == "partial" and 0 < legible < len(LABEL_FIELDS))
            ):
                raise ValueError("Readability does not match observed fields")
            intervals.append((key, decision - uncertainty, release + uncertainty))
        elif any(row[f] is not None for f in TIMES) or row["readability"] is not None or legible:
            raise ValueError("Unreviewed/unavailable rows must have blank measurements")
        counts[status] += 1
    if seen != set(expected):
        raise ValueError("Response must retain every selected pitch, including unreviewed rows")
    intervals.sort()
    if any(b[1] <= a[2] for a, b in zip(intervals, intervals[1:], strict=False)):
        raise ValueError("Pitch intervals overlap or contradict chronological order")
    if counts["annotated"] + counts["unavailable"] or require_complete:
        if not reviewer["name"].strip() or any(
            reviewer[k] is None for k in ("kind", "reviewed_at", "prior_reference_exposure")
        ):
            raise ValueError("Reviewer identity, kind, date and exposure disclosure are required")
    if require_complete and counts["unreviewed"]:
        raise ValueError("Review is incomplete; unreviewed pitches remain")
    return {
        "package_id": template["package_id"],
        "selected": len(expected),
        **{s: counts[s] for s in ("annotated", "unavailable", "unreviewed")},
        "complete": counts["unreviewed"] == 0,
        "prior_reference_exposure": reviewer["prior_reference_exposure"],
        "note": "Format validation only; no agreement score or independent-review certification",
    }


def package_files(protocol):
    """Render only reviewer files; organizer selection and reference answers stay out."""
    assets = _reviewer_assets()
    template = _template_from_protocol(protocol, _reviewer_assets_hash(assets))
    validate_response(template, template)
    data = json.dumps(template, ensure_ascii=False, indent=2, allow_nan=False)
    html = assets["src/web/static/blind_review.html"]
    js = assets["src/web/static/blind_review.js"]
    html = html.replace("__BLIND_REVIEW_JS__", js).replace(
        "__BLIND_REVIEW_JSON__", data.replace("<", "\\u003c")
    )
    return {
        "index.html": html.encode("utf-8"),
        "review.json": (data + "\n").encode("utf-8"),
        "README.md": assets["docs/templates/BLIND_REVIEW_README.md"].encode("utf-8"),
    }


def build_package(protocol, output):
    """Write an idempotent package; never overwrite edited reviewer artifacts."""
    output = Path(output)
    files = package_files(protocol)
    if output.exists() and set(p.name for p in output.iterdir()) - {*files, "reviewer.zip"}:
        raise ValueError("Output contains unexpected files; choose an empty output directory")
    for name, data in files.items():
        target = output / name
        if target.exists() and target.read_bytes() != data:
            raise ValueError(f"Refusing to overwrite changed reviewer file: {name}")
    archive = output / "reviewer.zip"
    if archive.exists():
        with ZipFile(archive) as handle:
            if sorted(handle.namelist()) != sorted(files) or any(
                handle.read(name) != data for name, data in files.items()
            ):
                raise ValueError("Refusing to overwrite changed reviewer archive")
    output.mkdir(parents=True, exist_ok=True)
    for name, data in files.items():
        (output / name).write_bytes(data)
    if not archive.exists():
        with ZipFile(archive, "w", compression=ZIP_DEFLATED) as handle:
            for name, data in files.items():
                handle.writestr(name, data)
    return check_package(protocol, output)


def check_package(protocol, output):
    """Check exact content and archive allow-list; this is not a response scorer."""
    output = Path(output)
    files = package_files(protocol)
    if set(p.name for p in output.iterdir()) != {*files, "reviewer.zip"}:
        raise ValueError("Unexpected package files")
    for name, data in files.items():
        if (output / name).read_bytes() != data:
            raise ValueError(f"Package content changed: {name}")
    with ZipFile(output / "reviewer.zip") as handle:
        if sorted(handle.namelist()) != sorted(files) or any(
            handle.read(name) != data for name, data in files.items()
        ):
            raise ValueError("Archive contains changed or unexpected files")
    template = template_from_protocol(protocol)
    return {"files": sorted(files), **validate_response(template, template)}

"""Evaluate image-only player-name OCR separately from frozen-roster identity resolution."""

import re
from collections import Counter
from copy import deepcopy
from pathlib import Path

from PIL import Image

from src.data.blind_review import canonical_hash
from src.data.broadcast_timing import KEYS
from src.data.player_identity import (
    ROLES,
    ROOT,
    bytes_hash,
    check_player_identity_evalset,
    normalize_name,
    resolve_name,
)
from src.vision.frames import verify_cached_frame

PREDICTION_SCHEMA = "mlb_player_identity_ocr_predictions_v1"
REPORT_SCHEMA = "mlb_player_identity_ocr_report_v1"
READ_FIELDS = {"raw_text", "name_text", "lineup_order", "status", "reason"}
CODE_PATHS = (
    "src/evaluation/player_identity_ocr.py",
    "src/data/player_identity.py",
    "src/vision/frames.py",
    "src/vision/sny_player_names.py",
    "src/vision/sny_scoreboard.py",
    "src/vision/windows_ocr.ps1",
    "scripts/74_evaluate_player_identity_ocr.py",
)


def _fields(value, names, label):
    if not isinstance(value, dict) or set(value) != set(names):
        raise ValueError(f"Unexpected {label} fields")


def _sha(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise ValueError("Expected a SHA256 hex digest")


def _code_hashes():
    return {
        path: bytes_hash((ROOT / path).read_text(encoding="utf-8").encode("utf-8"))
        for path in CODE_PATHS
        if (ROOT / path).is_file()
    }


def _main_key(row):
    values = tuple(row.get(k) for k in KEYS)
    if (
        any(type(value) is not int or value <= 0 for value in values)
        or row.get("role") not in ROLES
    ):
        raise ValueError("Expected positive integer pitch keys and a player role")
    return (*values, row["role"])


def _context_key(row):
    if (
        type(row.get("scope_at_bat_number")) is not int
        or row["scope_at_bat_number"] <= 0
        or row.get("role") not in ROLES
    ):
        raise ValueError("Expected a positive context PA and a player role")
    return row["scope_at_bat_number"], row["role"], canonical_hash(row["evidence"])


def _reading(reading, role):
    _fields(reading, READ_FIELDS, "OCR reading")
    if reading["status"] not in ("read", "abstain", "error"):
        raise ValueError("Invalid OCR status")
    if not isinstance(reading["raw_text"], str) or not isinstance(reading["reason"], str):
        raise ValueError("Raw OCR and reason must be strings")
    name, order = reading["name_text"], reading["lineup_order"]
    if name is not None and (not isinstance(name, str) or not normalize_name(name)):
        raise ValueError("OCR name must be literal nonempty text or null")
    if order is not None and (type(order) is not int or not 1 <= order <= 9 or role != "batter"):
        raise ValueError("OCR lineup slot must be a batter integer 1..9 or null")
    if (reading["status"] == "read") != (name is not None):
        raise ValueError("Name status must distinguish a literal name from a name abstention")
    if reading["status"] == "error" and order is not None:
        raise ValueError("Error readings must not claim a lineup slot")


def _image(evidence, root):
    root = Path(root).resolve()
    path = (root / evidence["path"]).resolve()
    if not path.is_relative_to(root) or Path(evidence["path"]).is_absolute():
        raise ValueError("Frame path must stay inside the supplied root")
    if bytes_hash(path.read_bytes()) != evidence["image_sha256"]:
        raise ValueError("OCR frame image bytes differ from frozen evidence")
    if not verify_cached_frame(path, evidence["media_url"], evidence["frame_seconds"], root=root):
        raise ValueError("OCR frame lacks exact source/time/hash proof")
    with Image.open(path) as source:
        return source.convert("RGB")


def build_predictions(evalset, reader, *, root=ROOT):
    """Give the reader only a PIL image; never pass names, IDs, labels or expected players."""
    check_player_identity_evalset(evalset)
    metadata = deepcopy(reader.metadata())
    if not isinstance(metadata, dict) or not metadata:
        raise ValueError("Reader must provide engine/version/config metadata")
    metadata_hash = canonical_hash(metadata)
    cache = {}

    def infer(observation, context=False):
        evidence = observation["evidence"]
        image_key = canonical_hash(evidence)
        if image_key not in cache:
            result = reader.read(_image(evidence, root))
            _fields(result, ROLES, "reader role outputs")
            for role in ROLES:
                _reading(result[role], role)
            cache[image_key] = deepcopy(result)
        identity = (
            {"scope_at_bat_number": observation["scope_at_bat_number"], "role": observation["role"]}
            if context
            else {key: observation[key] for key in (*KEYS, "play_id", "role")}
        )
        return {
            **identity,
            "evidence": deepcopy(evidence),
            **deepcopy(cache[image_key][observation["role"]]),
        }

    return {
        "schema": PREDICTION_SCHEMA,
        "game_pk": evalset["game_pk"],
        "evalset_sha256": canonical_hash(evalset),
        "roster_sha256": canonical_hash(evalset["roster"]),
        "source": deepcopy(evalset["source"]),
        "reader_metadata": metadata,
        "reader_metadata_sha256": metadata_hash,
        "pipeline_code_sha256": _code_hashes(),
        "predictions": [infer(row) for row in evalset["review"]["rows"]],
        "context_predictions": [
            infer(row, True) for row in evalset["review"]["context_observations"]
        ],
    }


def _index_predictions(expected, predicted, *, context=False):
    key_of = _context_key if context else _main_key
    identity_fields = {"scope_at_bat_number", "role"} if context else {*KEYS, "play_id", "role"}
    required = {*identity_fields, "evidence", *READ_FIELDS}
    wanted = {key_of(row): row for row in expected}
    if len(wanted) != len(expected):
        raise ValueError("Duplicate reference opportunities")
    if not isinstance(predicted, list):
        raise ValueError("Predictions must be a complete list of keyed records")
    indexed = {}
    for row in predicted:
        _fields(row, required, "keyed prediction")
        key = key_of(row)
        if key in indexed or key not in wanted:
            raise ValueError("Duplicate or unexpected prediction identity")
        if any(row[name] != wanted[key][name] for name in identity_fields) or canonical_hash(
            row["evidence"]
        ) != canonical_hash(wanted[key]["evidence"]):
            raise ValueError("Prediction play_id or evidence differs from the frozen source frame")
        _reading({name: row[name] for name in READ_FIELDS}, row["role"])
        indexed[key] = row
    if set(indexed) != set(wanted):
        raise ValueError("Missing prediction opportunities; retain explicit abstentions/errors")
    return indexed


def _verdict(attempted, comparable, equal):
    return "abstain" if not attempted else "correct" if comparable and equal else "wrong"


def _tally(records, prefix):
    counts = Counter(row[f"{prefix}_verdict"] for row in records)
    attempted = counts["correct"] + counts["wrong"]
    return {
        "opportunities": len(records),
        "reference_evaluable": sum(row[f"{prefix}_reference_evaluable"] for row in records),
        "attempt": attempted,
        "correct": counts["correct"],
        "wrong": counts["wrong"],
        "abstain": counts["abstain"],
        "coverage": attempted / len(records) if records else None,
        "correct_given_attempt": counts["correct"] / attempted if attempted else None,
        "false_reads_without_evaluable_reference": sum(
            row[f"{prefix}_verdict"] == "wrong" and not row[f"{prefix}_reference_evaluable"]
            for row in records
        ),
    }


def score_predictions(evalset, predictions):
    """Score literal names and resolved identities separately; context never joins main totals."""
    check_player_identity_evalset(evalset)
    _fields(
        predictions,
        {
            "schema",
            "game_pk",
            "evalset_sha256",
            "roster_sha256",
            "source",
            "reader_metadata",
            "reader_metadata_sha256",
            "pipeline_code_sha256",
            "predictions",
            "context_predictions",
        },
        "prediction document",
    )
    if (
        predictions["schema"] != PREDICTION_SCHEMA
        or type(predictions["game_pk"]) is not int
        or predictions["game_pk"] != evalset["game_pk"]
    ):
        raise ValueError("Prediction schema or game differs from the evaluation contract")
    if not isinstance(predictions["reader_metadata"], dict) or not predictions["reader_metadata"]:
        raise ValueError("Reader must provide engine/version/config metadata")
    for field, value in (
        ("evalset_sha256", evalset),
        ("roster_sha256", evalset["roster"]),
        ("reader_metadata_sha256", predictions["reader_metadata"]),
    ):
        if predictions[field] != canonical_hash(value):
            raise ValueError(f"Prediction {field} mismatch")
    if canonical_hash(predictions["source"]) != canonical_hash(evalset["source"]):
        raise ValueError("Prediction source differs from the evaluation source")
    hashes = predictions["pipeline_code_sha256"]
    if (
        not isinstance(hashes, dict)
        or not set(CODE_PATHS[:3]).issubset(hashes)
        or set(hashes) - set(CODE_PATHS)
    ):
        raise ValueError("Unexpected pipeline code hash manifest")
    for digest in hashes.values():
        _sha(digest)
    main = _index_predictions(evalset["review"]["rows"], predictions["predictions"])
    context = _index_predictions(
        evalset["review"]["context_observations"], predictions["context_predictions"], context=True
    )
    references = {_main_key(row): row for row in evalset["rows"]}
    records = []
    for manual in evalset["review"]["rows"]:
        key = _main_key(manual)
        predicted = main[key]
        candidates = resolve_name(predicted["name_text"], "readable", None, evalset["roster"])
        resolved = candidates[0] if len(candidates) == 1 else None
        reference_candidates = resolve_name(
            manual["name_text"], manual["readability"], None, evalset["roster"]
        )
        name_evaluable, id_evaluable = (
            manual["readability"] == "readable",
            len(reference_candidates) == 1,
        )
        lineup_evaluable = manual["lineup_order"] is not None
        name_equal = (
            predicted["name_text"] is not None
            and manual["name_text"] is not None
            and normalize_name(predicted["name_text"]) == normalize_name(manual["name_text"])
        )
        record = {
            **deepcopy(predicted),
            "expected_name_text": manual["name_text"],
            "name_reference_evaluable": name_evaluable,
            "name_verdict": _verdict(
                predicted["name_text"] is not None, name_evaluable, name_equal
            ),
            "candidate_ids": candidates,
            "resolved_player_id": resolved,
            "id_reference_evaluable": id_evaluable,
            "id_verdict": _verdict(
                resolved is not None, id_evaluable, reference_candidates == [resolved]
            ),
            "expected_lineup_order": manual["lineup_order"],
            "lineup_reference_evaluable": lineup_evaluable,
            "lineup_verdict": _verdict(
                predicted["lineup_order"] is not None,
                lineup_evaluable,
                predicted["lineup_order"] == manual["lineup_order"],
            ),
            "matches_hindsight_reference": None
            if resolved is None
            else resolved == references[key]["reference_player_id"],
        }
        records.append(record)
    diagnostics = []
    for manual in evalset["review"]["context_observations"]:
        if manual["readability"] == "readable":
            raise ValueError("Context diagnostics require partial/unreadable identity evidence")
        predicted = context[_context_key(manual)]
        candidates = resolve_name(predicted["name_text"], "readable", None, evalset["roster"])
        resolved = candidates[0] if len(candidates) == 1 else None
        diagnostics.append(
            {
                **deepcopy(predicted),
                "reference_fragment": manual["name_text"],
                "candidate_ids": candidates,
                "resolved_player_id": resolved,
                "name_false_read": predicted["name_text"] is not None,
                "id_false_read": resolved is not None,
                "lineup_false_read": predicted["lineup_order"] is not None,
            }
        )
    return {
        "schema": REPORT_SCHEMA,
        "evalset_sha256": canonical_hash(evalset),
        "predictions_sha256": canonical_hash(predictions),
        "reader_metadata_sha256": predictions["reader_metadata_sha256"],
        "pipeline_matches_current_code": hashes == _code_hashes(),
        "names": _tally(records, "name"),
        "identities": _tally(records, "id"),
        "lineup": _tally([row for row in records if row["role"] == "batter"], "lineup"),
        "reader_errors": sum(row["status"] == "error" for row in records),
        "context_diagnostics": {
            "opportunities": len(diagnostics),
            "reader_errors": sum(row["status"] == "error" for row in diagnostics),
            **{
                field: sum(row[field] for row in diagnostics)
                for field in ("name_false_read", "id_false_read", "lineup_false_read")
            },
            "rows": diagnostics,
        },
        "rows": records,
        "limitations": [
            "Manual PA6 development references on one SNY layout, not new blind validation or general OCR accuracy.",
            "Reader receives images only; exact whole-game roster resolution runs afterward with no expected-player or role filter.",
            "Wrong literal names remain wrong when identity resolution abstains; absent/partial names are not successful identity targets.",
            "Lineup totals include batter roles only. Context frames are separate diagnostic negatives.",
            "Final-feed agreement is hindsight context, not evidence of live player availability or automatic substitution tracking.",
        ],
    }

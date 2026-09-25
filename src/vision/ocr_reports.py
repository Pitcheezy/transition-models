"""Pure helpers behind ``scripts/70_refresh_ocr_reports.py`` (no subprocess, no git).

Every scoreboard OCR version has a fixed set of report files (``VERSIONS``). After the eval set
changes, the reports are regenerated with the documented ``scripts/66`` commands and a provenance
document (``mlb_scoreboard_ocr_provenance_v1``) records exact hashes, a repeat check, the
comparison with the predictions of a reference commit and the results on the new pitches. The
helpers here compare prediction rows, evaluate new rows against confirmed labels only, hash files
and assemble the provenance document while carrying forward what an existing one already holds
(keys tied to the replaced reference move under ``carried_from_previous``).
"""

import hashlib
import json
import platform
import re
import sys
from collections import Counter
from pathlib import Path

import numpy as np
import PIL

from src.data.broadcast_timing import KEYS
from src.data.scoreboard_evalset import LABEL_FIELDS, _same_type_value
from src.vision.frames import frame_path

RESULTS_DIR = "docs/results/mlb_p0"
PROVENANCE_SCHEMA = "mlb_scoreboard_ocr_provenance_v1"
CODE_PATHS = ("src/vision/sny_scoreboard.py", "scripts/66_sny_scoreboard_ocr.py")
SHARED_INPUTS = (
    "game_747139_scoreboard_evalset.json",
    "game_747139_scoreboard_review.json",
    "game_747139_timing.json",
)
FRAMES_DIR = "outputs/frames"
FRAMES_LABEL = "evalset"
# Register of wrong reads that were looked at and kept on record (a version is a fixed
# measurement; a reader fix becomes a new version). scripts/70 fails on any other wrong read.
KNOWN_MISREADS = "game_747139_scoreboard_known_misreads.json"
KNOWN_MISREADS_SCHEMA = "mlb_scoreboard_known_misreads_v1"

# 파일 이름표: negatives v1은 과거 이름(v0)을 그대로 쓴다.
VERSIONS = {
    "v1": {
        "templates": "sny_digit_templates_v1.json",
        "predictions": "game_747139_scoreboard_ocr_v1_predictions.json",
        "score": "game_747139_scoreboard_ocr_v1.json",
        "negatives": "game_747139_scoreboard_negatives_score_v0.json",
        "provenance": "game_747139_scoreboard_ocr_v1_provenance.json",
    },
    "v2": {
        "templates": "sny_digit_templates_v2.json",
        "predictions": "game_747139_scoreboard_ocr_v2_predictions.json",
        "score": "game_747139_scoreboard_ocr_v2.json",
        "negatives": "game_747139_scoreboard_negatives_score_v2.json",
        "provenance": "game_747139_scoreboard_ocr_v2_provenance.json",
    },
    # v3 (F-3c): templates PA 1 2 9 18 29 plus opt-in reader_options inside the template file.
    "v3": {
        "templates": "sny_digit_templates_v3.json",
        "predictions": "game_747139_scoreboard_ocr_v3_predictions.json",
        "score": "game_747139_scoreboard_ocr_v3.json",
        "negatives": "game_747139_scoreboard_negatives_score_v3.json",
        "provenance": "game_747139_scoreboard_ocr_v3_provenance.json",
    },
    # v4 (F-3d): the v3 templates plus min_margin_by_field / arrow_window / topbot_rule options
    # inside the template file; pre-registered before any 6th-inning frame was annotated.
    "v4": {
        "templates": "sny_digit_templates_v4.json",
        "predictions": "game_747139_scoreboard_ocr_v4_predictions.json",
        "score": "game_747139_scoreboard_ocr_v4.json",
        "negatives": "game_747139_scoreboard_negatives_score_v4.json",
        "provenance": "game_747139_scoreboard_ocr_v4_provenance.json",
    },
}
# What the ``score --exclude-pas`` set of a version is, when it is NOT purely held-out. A version
# listed here has its provenance ``scope`` say "exclude-pas score (<kind>, see limitations)"
# instead of "held-out score" and gets the note appended to a fresh document's ``limitations``;
# versions without an entry (v1, v2) keep their documents bit for bit.
SCORE_SET_KINDS = {"v3": "a mixed set", "v4": "a development set"}
SCORE_SET_NOTES = {
    "v3": (
        "The v3 score file (score --exclude-pas 1 2 9 18 29) covers 94 fully evaluable pitches "
        "= 75 held-out headline pitches + 19 seen/diagnosed pitches whose v2 failure was "
        "pixel-diagnosed before the v3 rule was fixed. It is a mixed set: only the 75 are "
        "held-out evidence, and the split is in game_747139_scoreboard_ocr_v3_comparison.json."
    ),
    "v4": (
        "The v4 score file (score --exclude-pas 1 2 9 18 29; 122 fully evaluable pitches of "
        "PA 1-40, 93 all-fields-correct) is a DEVELOPMENT set with 0 held-out pitches: every "
        "eval-set and negatives frame that existed on 2026-09-25 was seen and its v1-v3 "
        "failures diagnosed before the v4 reader options were chosen, so nothing in it is "
        "held-out, blind or generalisation evidence. The first blind evidence for v4 is the "
        "new-row comparison on the A-10 6th-inning rows (PA 41-49), judged by the criterion in "
        "game_747139_scoreboard_ocr_v4_preregistration.json."
    ),
}

# 재계산되는 최상위 키의 표준 순서. 기존 파일의 다른 키는 제자리에 그대로 옮긴다.
PROVENANCE_ORDER = (
    "schema",
    "game_pk",
    "recorded_at",
    "recorded_by",
    "scope",
    "git_reference",
    "runtime",
    "source",
    "manifest_sha256",
    "code_and_templates",
    "artifacts",
    "frame_cache",
    "current_repeat_check",
    "previous_prediction_comparison",
    "new_rows_comparison",
    "carried_from_previous",
    "historical_audit",
    "reproduction_commands",
    "limitations",
)
UNIT_COMPARISON_KEY = re.compile(r"^new_.+_comparison$")
# 기존 문서의 재계산되지 않는 최상위 키 중, 참조 커밋과 무관하게 버전 전체에 참인 키는 최상위에
# 남긴다(preregistration: v2 템플릿 PA 선정 규칙). 그 외(예: unchanged_since_reference)는 옛
# git_reference와 함께 carried_from_previous 아래로 옮긴다.
VERSION_WIDE_KEYS = ("preregistration",)
DEFAULT_LIMITATIONS = [
    "Same-game development evidence, not an independent benchmark.",
    "Template-source plate appearances are excluded from held-out scoring; the repeat check "
    "covers every prediction row.",
    "Timing and labels come from direct selected-frame AI review; no independent human "
    "inter-rater measurement.",
    "Regenerate provenance when hashed artifacts, code, templates or frames change.",
]


def template_plate_appearances(templates_doc):
    """Plate appearances whose frames the templates were cut from (excluded from scoring)."""
    return sorted(int(pa) for pa in templates_doc["source"]["template_plate_appearances"])


def row_key(row):
    return tuple(row[k] for k in KEYS)


def _by_key(rows):
    index = {}
    for row in rows:
        key = row_key(row)
        if key in index:
            raise ValueError(f"Duplicate prediction row {key}")
        index[key] = row
    return index


def compare_predictions(reference_rows, current_rows):
    """Compare two prediction lists keyed by pitch; ``changes`` lists shared rows whose fields differ."""
    previous, current = _by_key(reference_rows), _by_key(current_rows)
    shared = sorted(set(previous) & set(current))
    changes = [
        {
            **dict(zip(KEYS, key, strict=True)),
            "before": previous[key]["fields"],
            "after": current[key]["fields"],
        }
        for key in shared
        if previous[key]["fields"] != current[key]["fields"]
    ]
    return {
        "previous_rows": len(previous),
        "current_rows": len(current),
        "shared_rows": len(shared),
        "identical_shared_rows": len(shared) - len(changes),
        "changed_shared_rows": len(changes),
        "new_rows": len(set(current) - set(previous)),
        "removed_rows": len(set(previous) - set(current)),
        "changes": changes,
    }


def new_row_keys(reference_rows, current_rows):
    """Keys of ``current_rows`` that are absent from ``reference_rows``, in current order."""
    previous = {row_key(r) for r in reference_rows}
    return [row_key(r) for r in current_rows if row_key(r) not in previous]


def new_rows_comparison(evalset, predictions, keys):
    """Per-pitch result on the given (new) pitches; only human-confirmed fields are counted.

    A new pitch whose key is not in the eval set has no evaluable field and is counted in
    ``totals["new_rows_missing_from_evalset"]``: the eval set was probably not rebuilt after
    the merge that added the pitch.
    """
    entries = {row_key(e): e for e in evalset["entries"]}
    rows = _by_key(predictions)
    pitches = []
    for key in keys:
        entry, row = entries.get(key), rows.get(key)
        evaluable = (
            [f for f in LABEL_FIELDS if entry["field_status"][f] == "confirmed"] if entry else []
        )
        fields = row["fields"] if row else {}
        wrong = [f for f in evaluable if fields.get(f) is not None]
        wrong = [f for f in wrong if not _same_type_value(fields[f], entry["labels"][f])]
        abstained = [f for f in evaluable if fields.get(f) is None]
        pitches.append(
            {
                **dict(zip(KEYS, key, strict=True)),
                "frame_seconds": entry["frame_seconds"] if entry else None,
                "evaluable_fields": len(evaluable),
                "correct_fields": len(evaluable) - len(wrong) - len(abstained),
                "wrong_fields": wrong,
                "abstained_fields": abstained,
            }
        )
    full = len(LABEL_FIELDS)
    totals = {
        "pitch_count": len(pitches),
        "fully_evaluable_pitches": sum(p["evaluable_fields"] == full for p in pitches),
        "all_fields_correct_pitches": sum(p["correct_fields"] == full for p in pitches),
        "pitches_with_wrong_field": sum(bool(p["wrong_fields"]) for p in pitches),
        "pitches_with_abstention": sum(bool(p["abstained_fields"]) for p in pitches),
        "new_rows_missing_from_evalset": sum(key not in entries for key in keys),
    }
    return {"totals": totals, "pitches": pitches}


def sha256_bytes(data):
    return hashlib.sha256(data).hexdigest()


def digest_bytes(path, data):
    return {"path": Path(path).as_posix(), "sha256": sha256_bytes(data), "bytes": len(data)}


def digest_file(root, path):
    """``{path, sha256, bytes}`` for a repository-relative path (forward slashes)."""
    return digest_bytes(path, (Path(root) / path).read_bytes())


def _lf(data):
    return data.replace(b"\r\n", b"\n")


def carried_artifacts(existing, artifacts, root):
    """Extra artifacts of the replaced provenance that still exist on disk, re-hashed.

    An artifact of ``existing`` whose file name is not among the recomputed ``artifacts`` (e.g.
    ``game_747139_scoreboard_ocr_v2_comparison.json``) is hashed again from ``root`` and marked
    ``"carried": true``; one that no longer exists is dropped. Matching by file name keeps a run
    into another ``--out-dir`` from carrying the committed reports as extra artifacts.
    """
    names = {Path(a["path"]).name for a in artifacts}
    carried = []
    for artifact in (existing or {}).get("artifacts", []):
        path = artifact["path"]
        if Path(path).name in names or not (Path(root) / path).is_file():
            continue
        carried.append({**digest_file(root, path), "carried": True})
    return carried


def code_entry(root, path, reference_bytes):
    """Digest plus equality flags against the reference commit's bytes (``None`` = not there)."""
    current = (Path(root) / path).read_bytes()
    entry = digest_bytes(path, current)
    missing = reference_bytes is None
    entry["lf_normalized_equal_to_reference"] = (
        None if missing else _lf(current) == _lf(reference_bytes)
    )
    if path.endswith(".json"):
        entry["json_semantically_equal_to_reference"] = (
            None
            if missing
            else json.loads(current.decode("utf-8-sig"))
            == json.loads(reference_bytes.decode("utf-8-sig"))
        )
    return entry


def frame_cache(evalset, root, frames_dir=FRAMES_DIR, frames_label=FRAMES_LABEL):
    """Exact hashes of the cached eval-set frames; ``complete`` is false when any is missing."""
    frames, complete = [], True
    for entry in evalset["entries"]:
        path = frame_path(frames_dir, frames_label, entry["frame_seconds"])
        frame = {
            **{k: entry[k] for k in (*KEYS, "play_id", "frame_seconds")},
            "path": path.as_posix(),
        }
        if (Path(root) / path).exists():
            frame.update({k: v for k, v in digest_file(root, path).items() if k != "path"})
        else:
            complete = False
            frame.update({"sha256": None, "bytes": None})
        frames.append(frame)
    return {
        "path_rule": f"{frames_dir}/{frames_label}_<frame_seconds:.2f>.jpg",
        "frame_count": len(frames),
        "complete": complete,
        "hash_algorithm": "sha256",
        "scope": "Exact current JPEG bytes, not a full-video hash. Cache must be transferred separately.",
        "frames": frames,
    }


def repeat_check(predictions, repeat_rows, repeat_digest):
    """Row-by-row agreement between the written predictions and a repeat ``predict --no-grab``."""
    current, repeat = _by_key(predictions), _by_key(repeat_rows)
    matching = sum(1 for key, row in current.items() if repeat.get(key) == row)
    return {
        "prediction_rows": len(current),
        "matching_rows": matching,
        "parsed_documents_equal": predictions == repeat_rows,
        "repeat_output": repeat_digest,
    }


def runtime_info():
    return {
        "python_version": platform.python_version(),
        "python_build": sys.version,
        "numpy_version": np.__version__,
        "pillow_version": PIL.__version__,
        "operating_system": platform.system(),
        "machine": platform.machine(),
    }


def reproduction_commands(
    version, template_pas, out_dir=RESULTS_DIR, no_grab=True, repeat_path=None, reader_options=None
):
    """The documented ``scripts/66`` commands for one version.

    The first command rebuilds the templates from their source plate appearances (``scripts/70``
    does not run it: the committed templates are an input); the others are what ``scripts/70``
    runs: predict, ``score --exclude-pas``, negatives and the repeat predict. A template file
    that carries a non-empty ``reader_options`` object (v3) gets it echoed as
    ``--reader-options '<json>'``.
    """
    files = VERSIONS[version]
    templates = f"{RESULTS_DIR}/{files['templates']}"
    grab = " --no-grab" if no_grab else ""
    out = Path(out_dir).as_posix()
    pas = " ".join(str(pa) for pa in template_pas)
    options = (
        f" --reader-options '{json.dumps(reader_options, separators=(',', ':'))}'"
        if reader_options
        else ""
    )
    repeat_path = repeat_path or f"outputs/verification/ocr_{version}_repeat.json"
    return [
        f"python scripts/66_sny_scoreboard_ocr.py templates --template-pas {pas} --no-grab"
        f"{options} --output {templates}",
        f"python scripts/66_sny_scoreboard_ocr.py predict --templates {templates}{grab} "
        f"--output {out}/{files['predictions']}",
        f"python scripts/66_sny_scoreboard_ocr.py score --predictions {out}/{files['predictions']} "
        f"--exclude-pas {pas} --output {out}/{files['score']}",
        f"python scripts/66_sny_scoreboard_ocr.py negatives --templates {templates}{grab} "
        f"--output {out}/{files['negatives']}",
        f"python scripts/66_sny_scoreboard_ocr.py predict --templates {templates} --no-grab "
        f"--output {repeat_path}",
    ]


def _historical_audit(existing, replaced_commit, provenance_path, label):
    previous = existing.get("historical_audit") if existing else None
    if previous is None:
        audit = []
    elif isinstance(previous, dict):
        audit = [previous]
    else:
        audit = list(previous)
    if existing is not None:
        who = existing.get("recorded_by", "unknown")
        when = existing.get("recorded_at", "unknown date")
        audit.append(
            {
                "commit": replaced_commit,
                "path": provenance_path,
                "note": f"Previous provenance ({who}, {when}) replaced by refresh {label!r}; "
                "kept in Git with its own new-row comparison.",
            }
        )
    return audit


def _carried_from_previous(existing):
    """Reference-tied keys of the replaced document, under its own ``git_reference``.

    Every top-level key of ``existing`` that the refresh does not recompute and that is not
    version-wide (``VERSION_WIDE_KEYS``) moves here, so e.g. ``unchanged_since_reference`` is
    never read next to a newer ``git_reference`` it was not computed against. An existing
    ``carried_from_previous`` is passed through unchanged when nothing new is carried and
    nested under the new one otherwise (each level names its own ``git_reference``).
    """
    if not existing:
        return None
    stray = {
        key: value
        for key, value in existing.items()
        if key not in PROVENANCE_ORDER
        and key not in VERSION_WIDE_KEYS
        and not UNIT_COMPARISON_KEY.match(key)
    }
    if not stray:
        return existing.get("carried_from_previous")
    carried = {
        "git_reference": existing.get("git_reference"),
        "recorded_at": existing.get("recorded_at"),
        **stray,
    }
    if "carried_from_previous" in existing:
        carried["carried_from_previous"] = existing["carried_from_previous"]
    return carried


def _ordered_keys(existing, computed):
    """Existing key order with per-unit comparison keys renamed and missing canonical keys inserted.

    Keys that are neither canonical nor version-wide are left out: they live under
    ``carried_from_previous``.
    """
    keys = []
    for key in existing or {}:
        key = "new_rows_comparison" if UNIT_COMPARISON_KEY.match(key) else key
        if key not in keys and (key in PROVENANCE_ORDER or key in VERSION_WIDE_KEYS):
            keys.append(key)
    last = -1
    for key in PROVENANCE_ORDER:
        if key in keys:
            last = keys.index(key)
        else:
            last += 1
            keys.insert(last, key)
    return [k for k in keys if k in computed or (existing and k in existing)]


def build_provenance(
    existing,
    *,
    version,
    recorded_at,
    recorded_by,
    label,
    reference_commit,
    replaced_commit,
    evalset,
    template_pas,
    code_and_templates,
    artifacts,
    frame_cache,
    repeat,
    comparison,
    new_rows,
    commands,
    runtime=None,
):
    """Assemble the provenance document, carrying forward keys the refresh does not recompute.

    ``existing`` is the provenance being replaced (or ``None``). Its ``limitations`` and the
    version-wide ``preregistration`` are kept unchanged and in place; every other top-level key
    the refresh does not recompute (e.g. ``unchanged_since_reference``, computed against the old
    reference) moves into ``carried_from_previous`` together with the replaced document's
    ``git_reference`` and ``recorded_at``; the old per-unit ``new_<label>_comparison`` key is
    replaced by the stable ``new_rows_comparison``; ``historical_audit`` gets one appended entry
    for the replaced document. ``artifacts`` is written as given (``carried_artifacts`` adds the
    replaced document's extra files).
    """
    files = VERSIONS[version]
    provenance_path = f"{RESULTS_DIR}/{files['provenance']}"
    score_note = SCORE_SET_NOTES.get(version)
    score_phrase = "held-out score"
    if score_note:
        score_phrase = f"exclude-pas score ({SCORE_SET_KINDS[version]}, see limitations)"
    computed = {
        "schema": PROVENANCE_SCHEMA,
        "game_pk": evalset["game_pk"],
        "recorded_at": recorded_at,
        "recorded_by": recorded_by,
        "scope": (
            f"Refresh {label!r} of OCR {version} (templates from PAs {template_pas}) by "
            f"scripts/70_refresh_ocr_reports.py: predictions, {score_phrase}, negatives and a "
            "repeat check regenerated after the eval set changed. Code and template equality "
            "with the reference commit is recorded in code_and_templates."
        ),
        "git_reference": {
            "commit": reference_commit,
            "meaning": (
                "Commit whose predictions count as previous and whose code/templates the "
                "lf-normalized equality flags are computed against."
            ),
        },
        "runtime": runtime or runtime_info(),
        "source": evalset["source"],
        "manifest_sha256": evalset["manifest_sha256"],
        "code_and_templates": code_and_templates,
        "artifacts": artifacts,
        "frame_cache": frame_cache,
        "current_repeat_check": repeat,
        "previous_prediction_comparison": {"reference_commit": reference_commit, **comparison},
        "new_rows_comparison": {
            "label": label,
            "reference_commit": reference_commit,
            **new_rows,
        },
        "historical_audit": _historical_audit(existing, replaced_commit, provenance_path, label),
        "reproduction_commands": commands,
    }
    if not existing or "limitations" not in existing:
        computed["limitations"] = list(DEFAULT_LIMITATIONS) + ([score_note] if score_note else [])
    carried = _carried_from_previous(existing)
    if carried is not None:
        computed["carried_from_previous"] = carried
    return {
        key: computed[key] if key in computed else existing[key]
        for key in _ordered_keys(existing, computed)
    }


def score_summary(score):
    """The numbers a person checks after a refresh: all-field counts and the wrong fields."""
    wrong = {f: v["wrong"] for f, v in score["per_field"].items() if v["wrong"]}
    return {
        **{k: score["all_fields"][k] for k in ("evaluable", "correct", "abstained", "wrong")},
        "wrong_per_field": wrong,
    }


def wrong_reads(evalset, predictions):
    """Every human-confirmed field that a prediction row reads with a value other than its label.

    All prediction rows count, including the template-source plate appearances that a held-out
    score leaves out. Abstentions (``None``) are not wrong reads.
    """
    entries = {row_key(e): e for e in evalset["entries"]}
    found = []
    for row in predictions:
        entry = entries.get(row_key(row))
        if entry is None:
            continue
        for field in LABEL_FIELDS:
            value = row["fields"].get(field)
            if entry["field_status"][field] != "confirmed" or value is None:
                continue
            if not _same_type_value(value, entry["labels"][field]):
                found.append(
                    {
                        **dict(zip(KEYS, row_key(row), strict=True)),
                        "field": field,
                        "read": value,
                        "label": entry["labels"][field],
                    }
                )
    return found


def _misread_key(item):
    return (*(item[k] for k in KEYS), item["field"])


def new_rows_field_counts(evalset, block):
    """Per-field ``{correct, abstained, wrong}`` over the pitches of a ``new_rows_comparison`` block.

    A field counts for a pitch only when the eval-set entry confirms it; ``correct`` is the
    confirmed count minus the pitches listing the field in ``abstained_fields`` or
    ``wrong_fields``. Pitches missing from the eval set contribute nothing.
    """
    entries = {row_key(e): e for e in evalset["entries"]}
    counts = {f: {"correct": 0, "abstained": 0, "wrong": 0} for f in LABEL_FIELDS}
    for pitch in block["pitches"]:
        entry = entries.get(row_key(pitch))
        if entry is None:
            continue
        for field in LABEL_FIELDS:
            if entry["field_status"][field] != "confirmed":
                continue
            if field in pitch["wrong_fields"]:
                counts[field]["wrong"] += 1
            elif field in pitch["abstained_fields"]:
                counts[field]["abstained"] += 1
            else:
                counts[field]["correct"] += 1
    return counts


def new_rows_acceptance(evalset, candidate, baselines, negatives_totals=None, wrong_reads=None):
    """The pre-registered F-3d pass/fail rule on new rows (criteria 1-3 of the v4 document).

    ``candidate`` and every value of ``baselines`` (``{version: block}``) are
    ``new_rows_comparison`` blocks over the same new pitches. The candidate passes only when no
    new pitch has a wrong field, ``wrong_reads`` (the candidate's ``wrong_reads`` list over ALL
    its prediction rows, when given) is empty, its per-field correct count is at least every
    baseline's for every label field (no exclusion clause) and, when ``negatives_totals`` is
    given, that document has 0 false and 0 wrong reads. The check is invalid (``valid`` false,
    never a pass) when ``new_rows_missing_from_evalset`` > 0 (the eval set was not rebuilt; the
    check is rerun, not judged) or when a baseline block covers other pitches than the candidate.
    """
    totals = candidate["totals"]
    reasons, invalid = [], []
    if totals.get("new_rows_missing_from_evalset", 0):
        invalid.append(f"{totals['new_rows_missing_from_evalset']} new row(s) not in the eval set")
    keys = {row_key(p) for p in candidate["pitches"]}
    for version, block in baselines.items():
        if {row_key(p) for p in block["pitches"]} != keys:
            invalid.append(f"{version} block covers other pitches than the candidate")
    if totals["pitches_with_wrong_field"]:
        reasons.append(f"{totals['pitches_with_wrong_field']} new pitch(es) have a wrong field")
    if wrong_reads:
        reasons.append(f"{len(wrong_reads)} wrong read(s) over all candidate rows")
    counts = new_rows_field_counts(evalset, candidate)
    per_field = {f: {"candidate": counts[f]["correct"]} for f in LABEL_FIELDS}
    for version, block in baselines.items():
        base = new_rows_field_counts(evalset, block)
        for field in LABEL_FIELDS:
            per_field[field][version] = base[field]["correct"]
            if counts[field]["correct"] < base[field]["correct"]:
                reasons.append(
                    f"{field}: candidate correct {counts[field]['correct']} < "
                    f"{version} {base[field]['correct']}"
                )
    for name in ("false_reads", "wrong_reads"):
        if negatives_totals and negatives_totals.get(name):
            reasons.append(f"negatives have {negatives_totals[name]} {name.replace('_', ' ')}")
    return {
        "valid": not invalid,
        "passes": not invalid and not reasons,
        "reasons": invalid + reasons,
        "per_field_correct": per_field,
    }


def known_misreads(register, version):
    """``{(game_pk, at_bat, pitch, field): read}`` for the register entries that list ``version``."""
    if register.get("schema") != KNOWN_MISREADS_SCHEMA:
        raise ValueError(f"known-misread register schema must be {KNOWN_MISREADS_SCHEMA!r}")
    return {_misread_key(m): m["read"] for m in register["misreads"] if version in m["versions"]}


def _describe(key):
    return f"{key[1]}/{key[2]} {key[3]}"


def wrong_read_problems(version, score, negatives, new_rows, reads=None, known=None):
    """One message per wrong-read source a refresh must fail on (empty list = none).

    ``score["all_fields"]["wrong"]`` counts only pitches on which every field was attempted, so
    a wrong field next to an abstention (v1 abstains on ``inning`` for most pitches) shows up
    only in ``per_field``. The negatives report reads of unreadable frames as ``false_reads``
    and readable-but-wrong ones as ``wrong_reads``. The new-row comparison also covers the
    template-source plate appearances that the held-out score excludes.

    ``known`` (``known_misreads``) holds wrong reads kept on record in ``KNOWN_MISREADS``: they
    are expected in the score, the new rows and ``reads`` and do not fail. ``reads``
    (``wrong_reads`` over all prediction rows) is checked both ways: a wrong read missing from
    the register fails, and so does a register entry that no longer happens with the same value,
    so the register stays true.
    """
    known = known or {}
    problems = []
    excluded = set(score.get("holdout", {}).get("excluded_plate_appearances", []))
    expected = dict(Counter(key[3] for key in known if key[1] not in excluded))
    wrong = score_summary(score)["wrong_per_field"]
    if wrong != expected:
        note = f" (known misreads account for {json.dumps(expected)})" if expected else ""
        problems.append(f"{version}: score has wrong reads per field {json.dumps(wrong)}{note}")
    for name in ("false_reads", "wrong_reads"):
        if negatives["totals"][name]:
            problems.append(
                f"{version}: negatives have {negatives['totals'][name]} {name.replace('_', ' ')}"
            )
    explained = sum(
        bool(p["wrong_fields"])
        and all((*(p[k] for k in KEYS), f) in known for f in p["wrong_fields"])
        for p in new_rows["pitches"]
    )
    unexplained = new_rows["totals"]["pitches_with_wrong_field"] - explained
    if unexplained:
        problems.append(f"{version}: {unexplained} new pitch(es) have a wrong field")
    if reads is not None:
        found = {_misread_key(r): r["read"] for r in reads}
        for key, value in found.items():
            if key not in known:
                problems.append(
                    f"{version}: wrong read {_describe(key)} = {value!r} is not in {KNOWN_MISREADS}"
                )
        for key, value in known.items():
            if found.get(key, None) != value:
                problems.append(
                    f"{version}: known misread {_describe(key)} = {value!r} no longer happens "
                    f"(now {found.get(key)!r}); update {KNOWN_MISREADS}"
                )
    return problems

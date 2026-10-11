"""Prevent wrong-source timing and future-frame leakage into pre-pitch evaluation."""

import json
import subprocess
import sys
from copy import deepcopy
from pathlib import Path

import pytest

from src.data.broadcast_timing import timing_context, validate_annotations


@pytest.fixture
def sample():
    manifest = {
        "schema": "mlb_video_manifest_v1",
        "game_pk": 7,
        "pitches": [
            {
                "game_pk": 7,
                "at_bat_number": 1,
                "pitch_number": n,
                "identity_status": "verified",
                "video": {"play_id": f"pitch-{n}"},
            }
            for n in (1, 2)
        ],
    }
    url = "https://example.mlb.com/full.mp4"
    sources = {
        "game_pk": 7,
        "sources": {
            "full_game": {
                "page_url": "https://www.mlb.com/video/example",
                "observed_mp4_urls": [url],
                "inspection": {"url": url, "probe": {"format": {"duration": "120"}}},
            }
        },
    }
    document = {
        **timing_context(manifest, sources),
        "annotator": "test",
        "annotations": [
            {
                "game_pk": 7,
                "at_bat_number": 1,
                "pitch_number": n,
                "play_id": f"pitch-{n}",
                "status": "annotated",
                "decision_seconds": 10.0 * n,
                "release_seconds": 10.0 * n + 2,
                "uncertainty_seconds": 0.15,
                "note": "Scoreboard and pitch sequence visually checked",
            }
            for n in (2, 1)
        ],
    }
    return manifest, sources, document


def test_short_lead_pitches_are_listed_not_dropped(sample):
    manifest, sources, document = sample
    report = validate_annotations(document, manifest, sources)
    assert report["short_lead_threshold_seconds"] == 1.5
    assert report["short_lead_pitches"] == [] and report["lead_seconds_min"] == 2.0
    late_return = next(r for r in document["annotations"] if r["pitch_number"] == 2)
    late_return["release_seconds"] = late_return["decision_seconds"] + 1.0
    report = validate_annotations(document, manifest, sources)
    assert report["annotated"] == 2 and report["complete_plate_appearances"] == [1]
    assert report["short_lead_pitches"] == [
        {"game_pk": 7, "at_bat_number": 1, "pitch_number": 2, "lead_seconds": 1.0}
    ]
    assert report["lead_seconds_min"] == 1.0


def test_identity_join_and_complete_pa_ignore_file_order(sample):
    manifest, sources, document = sample
    report = validate_annotations(document, manifest, sources)
    assert report["annotated"] == 2
    assert report["complete_plate_appearances"] == [1]
    document["annotations"].pop()
    report = validate_annotations(document, manifest, sources)
    assert report["unreviewed"] == 1
    assert report["complete_plate_appearances"] == []


@pytest.mark.parametrize(
    "field,value",
    [
        ("decision_seconds", 22.0),
        ("decision_seconds", -1),
        ("release_seconds", 121),
        ("release_seconds", float("nan")),
        ("release_seconds", "22"),
        ("release_seconds", True),
        ("uncertainty_seconds", 0),
        ("uncertainty_seconds", 1.1),
        ("play_id", "different"),
        ("pitch_number", True),
        ("pitch_number", 1.0),
        ("note", ""),
        ("status", "verified"),
    ],
)
def test_reject_wrong_identity_or_unsafe_timing(sample, field, value):
    manifest, sources, document = sample
    document["annotations"][0][field] = value
    with pytest.raises(ValueError):
        validate_annotations(document, manifest, sources)


def test_unavailable_is_not_annotated_or_complete(sample):
    manifest, sources, document = sample
    row = document["annotations"][0]
    row.update(
        status="unavailable",
        decision_seconds=None,
        release_seconds=None,
        uncertainty_seconds=None,
        note="Replay obscures pre-pitch scene",
    )
    report = validate_annotations(document, manifest, sources)
    assert report["unavailable"] == 1
    assert report["complete_plate_appearances"] == []
    row["release_seconds"] = 22
    with pytest.raises(ValueError, match="invented"):
        validate_annotations(document, manifest, sources)


def test_reject_reordered_video_and_duplicates(sample):
    manifest, sources, document = sample
    duplicate = deepcopy(document)
    duplicate["annotations"].append(duplicate["annotations"][0])
    with pytest.raises(ValueError, match="duplicate"):
        validate_annotations(duplicate, manifest, sources)
    document["annotations"][0].update(decision_seconds=1, release_seconds=2)
    with pytest.raises(ValueError, match="chronological"):
        validate_annotations(document, manifest, sources)


@pytest.mark.parametrize("field", ["source", "manifest_sha256", "game_pk"])
def test_reject_different_video_or_manifest(sample, field):
    manifest, sources, document = sample
    document[field] = "other"
    with pytest.raises(ValueError, match="does not match"):
        validate_annotations(document, manifest, sources)


def test_reject_bad_manifest_and_uninspected_source(sample):
    manifest, sources, _ = sample
    bad = deepcopy(manifest)
    bad["pitches"][0]["identity_status"] = "metadata_conflict"
    with pytest.raises(ValueError, match="verified"):
        timing_context(bad, sources)
    sources["sources"]["full_game"]["inspection"] = None
    with pytest.raises(ValueError, match="inspected"):
        timing_context(manifest, sources)


def test_reject_extra_prediction_fields(sample):
    manifest, sources, document = sample
    document["annotations"][0]["ground_truth"] = "strike"
    with pytest.raises(ValueError, match="fields"):
        validate_annotations(document, manifest, sources)


def test_committed_visual_annotations_are_source_bound():
    root = Path(__file__).resolve().parents[1] / "docs/results/mlb_p0"

    def read(name):
        return json.loads((root / name).read_text(encoding="utf-8"))

    report = validate_annotations(
        read("game_747139_timing.json"),
        read("game_747139_manifest.json"),
        read("game_747139_sources.json"),
    )
    assert report == read("game_747139_timing_validation.json")
    assert 2 in report["complete_plate_appearances"]
    assert 1 not in report["complete_plate_appearances"]


def test_hashlib_before_src_and_torch_in_fresh_process():
    # Worst known order (docs/H1_ARROW_CRASH_2026-09-23.md): eight TLS slots taken by hashlib,
    # then torch, then the first Arrow-backed string conversion. src/__init__.py must load
    # pyarrow first so this completes instead of dying with an access violation.
    code = (
        "import hashlib; import src.data.broadcast_timing; import torch; import pandas as pd; "
        "assert pd.DataFrame([{'pitch': 'FF'}]).shape == (1, 1); print('ok')"
    )
    run = subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        timeout=60,
    )
    assert run.returncode == 0, (run.returncode, run.stderr[-800:])
    assert "ok" in run.stdout


def test_import_before_model_runtime_in_fresh_process():
    # Exercise the actual import-order regression, not a warmed-up pytest process.
    code = (
        "import src.data.broadcast_timing; import torch; import pandas as pd; "
        "assert pd.DataFrame([{'pitch': 'FF'}]).shape == (1, 1)"
    )
    subprocess.run(
        [sys.executable, "-c", code],
        cwd=Path(__file__).resolve().parents[1],
        capture_output=True,
        text=True,
        check=True,
        timeout=45,
    )

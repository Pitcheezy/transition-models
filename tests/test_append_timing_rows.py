"""Candidate rows reach the timing file only when every pitch of the PA is verified."""

import importlib.util
import json
from copy import deepcopy
from pathlib import Path

import pytest

from src.data.scoreboard_evalset import _labels

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs" / "results" / "mlb_p0"
PA = 20  # Synthetic merge target; merge_inputs isolates it from later real annotations.


def load_module():
    spec = importlib.util.spec_from_file_location(
        "append_rows", ROOT / "scripts" / "69_append_timing_rows.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def inputs():
    names = (
        "game_747139_manifest.json",
        "game_747139_sources.json",
        "game_747139_timing.json",
        "game_747139_scoreboard_review.json",
    )
    return [json.loads((RESULTS / n).read_text(encoding="utf-8-sig")) for n in names]


@pytest.fixture
def merge_inputs(inputs):
    """Keep synthetic merge rows independent of ongoing annotation progress."""
    manifest, sources, timing, review = deepcopy(inputs)
    timing["annotations"] = [r for r in timing["annotations"] if r["at_bat_number"] < PA]
    review["reviews"] = [r for r in review["reviews"] if r["at_bat_number"] < PA]
    return manifest, sources, timing, review


def candidates(manifest, timing, status="verified"):
    pitches = [p for p in manifest["pitches"] if p["at_bat_number"] == PA]
    rows = []
    for i, pitch in enumerate(sorted(pitches, key=lambda p: p["pitch_number"])):
        decision = 5000.0 + 30.0 * i
        rows.append(
            {
                "at_bat_number": PA,
                "pitch_number": pitch["pitch_number"],
                "play_id": pitch["video"]["play_id"],
                "status": "annotated",
                "decision_seconds": decision,
                "release_seconds": decision + 3.0,
                "uncertainty_seconds": 0.15,
                "note": "synthetic test row",
                "readability": "readable",
                "observed": {**_labels(pitch["pre_state"]), "inning_topbot": "bottom"},
                "bug_text": "synthetic",
                "verification": {"status": status},
            }
        )
    return {
        "schema": "mlb_broadcast_timing_candidates_v1",
        "game_pk": timing["game_pk"],
        "manifest_sha256": timing["manifest_sha256"],
        "rows": rows,
    }


def test_verified_rows_are_appended_and_validate(merge_inputs):
    module = load_module()
    manifest, sources, timing, review = merge_inputs
    before = deepcopy(timing)
    new_timing, new_review, report = module.merge(
        manifest, sources, timing, review, candidates(manifest, timing), [PA], "test", "2026-09-24"
    )
    assert timing == before  # inputs are not mutated
    added = [r for r in new_timing["annotations"] if r["at_bat_number"] == PA]
    assert len(added) == len([p for p in manifest["pitches"] if p["at_bat_number"] == PA])
    assert new_timing["annotations"][: len(timing["annotations"])] == timing["annotations"]
    assert PA in report["complete_plate_appearances"]
    reviews = [r for r in new_review["reviews"] if r["at_bat_number"] == PA]
    assert {r["observed"]["inning_topbot"] for r in reviews} == {"Bot"}


def test_refuses_unverified_missing_and_duplicate_rows(merge_inputs):
    module = load_module()
    manifest, sources, timing, review = merge_inputs
    unverified = candidates(manifest, timing, status="two_lens_passed_needs_spot_check")
    with pytest.raises(ValueError, match="not verified"):
        module.merge(manifest, sources, timing, review, unverified, [PA], "t", "d")
    short = candidates(manifest, timing)
    short["rows"].pop()
    with pytest.raises(ValueError, match="do not cover"):
        module.merge(manifest, sources, timing, review, short, [PA], "t", "d")
    already = min(r["at_bat_number"] for r in timing["annotations"])
    with pytest.raises(ValueError, match="already"):
        module.merge(
            manifest, sources, timing, review, candidates(manifest, timing), [already], "t", "d"
        )
    wrong = candidates(manifest, timing)
    wrong["manifest_sha256"] = "0" * 64
    with pytest.raises(ValueError, match="manifest_sha256"):
        module.merge(manifest, sources, timing, review, wrong, [PA], "t", "d")


@pytest.mark.parametrize(
    "path", sorted(RESULTS.glob("game_747139_timing_candidates_pa*.json")), ids=lambda p: p.stem
)
def test_stored_candidates_file_is_well_formed(inputs, path):
    manifest, _, timing, _ = inputs
    doc = json.loads(path.read_text(encoding="utf-8-sig"))
    assert doc["schema"] == "mlb_broadcast_timing_candidates_v1"
    assert doc["manifest_sha256"] == timing["manifest_sha256"]
    in_timing = {(r["at_bat_number"], r["pitch_number"]) for r in timing["annotations"]}
    index = {(p["at_bat_number"], p["pitch_number"]): p for p in manifest["pitches"]}
    for row in doc["rows"]:
        key = (row["at_bat_number"], row["pitch_number"])
        assert key not in in_timing  # candidates never duplicate merged rows
        assert row["play_id"] == index[key]["video"]["play_id"]
        assert row["verification"]["status"] != "verified" or row["verification"].get("by")

"""The join table only re-states verified timing rows, keyed the way the teammate catalog keys."""

import importlib.util
import json
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RESULTS = ROOT / "docs" / "results" / "mlb_p0"


def load_module():
    spec = importlib.util.spec_from_file_location(
        "join", ROOT / "scripts" / "68_export_pitch_timing_join.py"
    )
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_real_game_join_matches_timing_and_manifest():
    module = load_module()
    manifest, sources, timing = (
        json.loads((RESULTS / n).read_text(encoding="utf-8-sig"))
        for n in (
            "game_747139_manifest.json",
            "game_747139_sources.json",
            "game_747139_timing.json",
        )
    )
    doc = module.build_join(manifest, sources, timing)
    assert doc["schema"] == module.JOIN_SCHEMA
    assert doc["counts"]["timing_rows"] == len(timing["annotations"])
    assert doc["counts"]["annotated"] + doc["counts"]["unavailable"] == doc["counts"]["timing_rows"]
    by_key = {(p["at_bat_number"], p["pitch_number"]): p for p in manifest["pitches"]}
    ids = [row["pitch_id"] for row in doc["rows"]]
    assert len(set(ids)) == len(ids)
    for row in doc["rows"]:
        assert re.fullmatch(r"[0-9]+:[0-9]+:[0-9]+", row["pitch_id"])
        assert row["pitch_id"] == f"{row['game_pk']}:{row['at_bat_number']}:{row['pitch_number']}"
        pitch = by_key[(row["at_bat_number"], row["pitch_number"])]
        assert row["play_id"] == pitch["video"]["play_id"]
        assert row["play_page_url"] == pitch["video"]["page_url"]
        if row["status"] == "unavailable":
            assert row["decision_seconds"] is None and row["release_seconds"] is None
            assert row["lead_seconds"] is None
        else:
            assert row["lead_seconds"] == round(row["release_seconds"] - row["decision_seconds"], 3)
    stored = RESULTS / "game_747139_pitch_timing_join.json"
    if stored.exists():
        assert json.loads(stored.read_text(encoding="utf-8-sig")) == doc

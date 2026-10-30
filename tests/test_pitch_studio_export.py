"""Public projection checks without requiring private archive files in CI."""

import copy
import importlib.util
import json
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SPEC = importlib.util.spec_from_file_location(
    "pitch_export", ROOT / "scripts/export_pitch_studio_game.py"
)
EXPORT = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(EXPORT)


def report_fixture():
    public = json.loads((ROOT / "web/pitch-studio/game-849843.json").read_text(encoding="utf-8"))
    rows = []
    for p in public["pitches"]:
        actual = copy.deepcopy(p["post"]["actual"])
        actual.update(
            setup_status=p["post"]["setup"]["status"] if p["post"]["setup"] else None,
            setup_x_ft=p["post"]["setup"]["x"] if p["post"]["setup"] else None,
            play_text="DO_NOT_PUBLISH",
            internal_path="DO_NOT_PUBLISH",
        )
        rec = copy.deepcopy(p["pre"])
        rec.update(
            reason="DO_NOT_PUBLISH",
            event_probabilities=None,
            location_basis="historical_delivery_distribution_proxy_not_optimal_target",
        )
        batter = copy.deepcopy(p["batter"])
        batter["side"] = batter.pop("hand")
        rows.append(
            {
                "index": p["index"],
                "key": p["pitch_id"],
                "pa_key": f"849843:{p['at_bat_number']}",
                "at_bat_number": p["at_bat_number"],
                "pitch_number": p["pitch_number"],
                "pre": {
                    "situation": copy.deepcopy(p["situation"]),
                    "pitcher": copy.deepcopy(p["pitcher"]),
                    "batter": batter,
                    "recommendation": rec,
                },
                "post": {"actual": actual},
            }
        )
    return {
        "schema": "pitcheezy-service-review-v1",
        "profile": "teammate_export_20261009_v1",
        "source": {
            "input_kind": "provided_export",
            "sha256": EXPORT.SOURCE_SHA256,
            "reported_revision": None,
            "upstream_kind": "archive",
            "private": "DO_NOT_PUBLISH",
        },
        "game": {**public["game"], "kst_date": public["game"]["date"]},
        "pitches": rows,
        "private": "DO_NOT_PUBLISH",
    }


def test_projection_omits_private_sections_and_preserves_counts_and_missing_versions():
    value = EXPORT.project(report_fixture())
    assert EXPORT.summary(value) == {
        "pitches": 262,
        "plate_appearances": 71,
        "ready": 246,
        "unsupported": 16,
        "missing": 0,
    }
    assert b"DO_NOT_PUBLISH" not in EXPORT.serialize(value)
    assert value["source"]["revision"] is None
    assert value["source"]["exported_at"] is None
    assert "we" not in value["pitches"][0]["post"]
    assert "reason" not in value["pitches"][0]["pre"]


def test_report_projection_is_deterministic_by_index_and_does_not_mutate_input():
    report = report_fixture()
    before = copy.deepcopy(report)
    result = EXPORT.project(report)
    assert report == before
    report["pitches"].reverse()
    assert EXPORT.serialize(EXPORT.project(report)) == EXPORT.serialize(result)


def test_terminal_events_preserved_without_later_pa_text():
    value = EXPORT.project(report_fixture())
    rows = value["pitches"]
    assert sum(bool(p["post"]["actual"]["event"]) for p in rows) == 71
    assert rows[0]["post"]["actual"]["event"] is None
    assert rows[2]["post"]["actual"]["event"] == "strikeout"
    assert all("play_text" not in p["post"]["actual"] for p in rows)


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: r["pitches"].append(copy.deepcopy(r["pitches"][0])),
        lambda r: r["pitches"][0].update(key="849844:1:1"),
        lambda r: r["pitches"][0].update(pa_key="849843:9"),
        lambda r: r["pitches"][0].update(index=99999),
        lambda r: r["pitches"][0]["post"]["actual"].update(event="strikeout"),
        lambda r: r["pitches"][2]["post"]["actual"].update(setup_status="unavailable"),
        lambda r: r["pitches"][0]["post"]["actual"].update(x=float("nan")),
        lambda r: r["pitches"][0]["pre"]["recommendation"].update(status="unsupported"),
        lambda r: r["source"].update(reported_revision="f" * 40),
    ],
)
def test_corrupt_or_leaky_input_rejected(mutation):
    report = report_fixture()
    mutation(report)
    with pytest.raises(ValueError):
        EXPORT.project(report)


def test_unknown_archive_rejected_before_json_or_extraction(tmp_path):
    path = tmp_path / "different.zip"
    path.write_bytes(b"not the fixed archive")
    with pytest.raises(ValueError, match="ZIP SHA mismatch"):
        EXPORT.read_fixed_zip(path)


def test_checked_in_public_file_equals_projection_with_source_provenance():
    current = (ROOT / "web/pitch-studio/game-849843.json").read_bytes()
    assert EXPORT.serialize(EXPORT.project(report_fixture())) == current

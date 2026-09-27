"""Candidate rows reach the timing file only when every pitch of the PA is verified."""

import importlib.util
import json
import sys
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace

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
        "source": deepcopy(timing["source"]),
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


@pytest.mark.parametrize("field", ["source", "media_url", "page_url", "duration_seconds"])
def test_refuses_candidates_from_another_video(merge_inputs, field):
    module = load_module()
    manifest, sources, timing, review = merge_inputs
    document = candidates(manifest, timing)
    if field == "source":
        document.pop("source")
    else:
        document["source"][field] = "different video" if field != "duration_seconds" else 9999.0
    with pytest.raises(ValueError, match="Candidates source"):
        module.merge(manifest, sources, timing, review, document, [PA], "test", "2026-09-27")


@pytest.mark.parametrize(
    "field,value", [("play_id", None), ("play_id", "other"), ("game_pk", 1), ("game_pk", True)]
)
def test_refuses_wrong_selected_row_identity(merge_inputs, field, value):
    module = load_module()
    manifest, sources, timing, review = merge_inputs
    document = candidates(manifest, timing)
    document["rows"][0][field] = value
    with pytest.raises(ValueError, match=f"{field} mismatch"):
        module.merge(manifest, sources, timing, review, document, [PA], "test", "2026-09-27")


def cli_arguments(*extra):
    return [
        "append_rows",
        "--candidates",
        "candidates.json",
        "--pa",
        str(PA),
        "--reviewer",
        "test",
        "--annotator-suffix",
        "test",
        "--date",
        "2026-09-27",
        *extra,
    ]


def test_main_rebuilds_custom_inputs_from_another_directory(merge_inputs, tmp_path, monkeypatch):
    """Run every offline child CLI against custom copies; the canonical artifacts stay untouched."""
    module = load_module()
    manifest, sources, timing, review = merge_inputs
    documents = {
        "manifest.json": manifest,
        "sources.json": sources,
        "copy_timing.json": timing,
        "review.json": review,
        "candidates.json": candidates(manifest, timing),
    }
    for name, document in documents.items():
        (tmp_path / name).write_text(json.dumps(document), encoding="utf-8")
    protected = [*module.DEFAULT_INPUTS.values(), *module.DEFAULT_OUTPUTS.values()]
    before = {path: path.read_bytes() for path in protected}
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(
        sys,
        "argv",
        cli_arguments(
            "--manifest",
            "manifest.json",
            "--sources",
            "sources.json",
            "--timing",
            "copy_timing.json",
            "--review",
            "review.json",
            "--write",
        ),
    )
    commands = []
    original_run = module.subprocess.run

    def run(command, **kwargs):
        commands.append(command)
        return original_run(command, **kwargs)

    monkeypatch.setattr(module.subprocess, "run", run)
    module.main()
    assert len(commands) == 5
    for command in commands:
        for flag, name in (("--manifest", "manifest.json"), ("--sources", "sources.json")):
            assert command[command.index(flag) + 1] == str(tmp_path / name)
        timing_flag = "--annotations" if "--annotations" in command else "--timing"
        assert command[command.index(timing_flag) + 1] == str(tmp_path / "copy_timing.json")
        if "scripts/64_build_scoreboard_evalset.py" in command:
            assert command[command.index("--review") + 1] == str(tmp_path / "review.json")
    validation = json.loads((tmp_path / "copy_timing_validation.json").read_text(encoding="utf-8"))
    assert PA in validation["complete_plate_appearances"]
    evalset = json.loads((tmp_path / "copy_scoreboard_evalset.json").read_text(encoding="utf-8"))
    assert any(row["at_bat_number"] == PA for row in evalset["entries"])
    assert (tmp_path / "copy_pitch_timing_join.json").is_file()
    assert {path: path.read_bytes() for path in protected} == before


def test_main_default_paths_and_explicit_outputs(monkeypatch, tmp_path):
    """Default inputs keep their old output paths; explicit output flags reach every child."""
    module = load_module()
    report = {"annotated": 1, "unavailable": 0, "unreviewed": 0, "complete_plate_appearances": [PA]}
    monkeypatch.setattr(module, "read_json", lambda path: {})
    monkeypatch.setattr(module, "merge", lambda *args: ({"annotator": "test"}, {}, report))
    monkeypatch.setattr(module, "dump", lambda *args: None)
    commands = []
    monkeypatch.setattr(
        module.subprocess,
        "run",
        lambda cmd, **kwargs: commands.append(cmd) or SimpleNamespace(returncode=0, stderr=""),
    )
    monkeypatch.setattr(sys, "argv", cli_arguments("--write"))
    module.main()
    outputs = [Path(c[c.index("--output") + 1]) for c in commands if "--output" in c]
    assert outputs == list(module.DEFAULT_OUTPUTS.values())
    commands.clear()
    flags = []
    expected = []
    for name in module.DEFAULT_OUTPUTS:
        path = tmp_path / f"{name}.json"
        flags.extend([f"--{name.replace('_', '-')}", str(path)])
        expected.append(path)
    monkeypatch.setattr(sys, "argv", cli_arguments("--write", *flags))
    module.main()
    assert [Path(c[c.index("--output") + 1]) for c in commands if "--output" in c] == expected
    check = commands[3]
    assert Path(check[check.index("--evalset") + 1]) == expected[1]


@pytest.mark.parametrize(
    "case", ["input_alias", "output_alias", "canonical_output", "default_write"]
)
def test_main_rejects_dangerous_paths_before_reading_or_writing(case, tmp_path, monkeypatch):
    module = load_module()
    monkeypatch.chdir(tmp_path)
    flags = [
        "--manifest",
        "manifest.json",
        "--timing",
        "copy_timing.json",
        "--review",
        "review.json",
    ]
    if case == "input_alias":
        flags += ["--evalset-output", "review.json"]
    elif case == "output_alias":
        flags += ["--evalset-output", "same.json", "--join-output", "same.json"]
    elif case == "canonical_output":
        flags += ["--evalset-output", str(module.DEFAULT_OUTPUTS["evalset_output"])]
    else:
        flags = ["--manifest", "manifest.json"]
    monkeypatch.setattr(sys, "argv", cli_arguments("--write", *flags))

    def unexpected(*args, **kwargs):
        pytest.fail("Path validation must happen before reads, writes or child commands")

    for name in ("read_json", "dump"):
        monkeypatch.setattr(module, name, unexpected)
    monkeypatch.setattr(module.subprocess, "run", unexpected)
    with pytest.raises(SystemExit) as error:
        module.main()
    assert error.value.code == 2


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
    assert doc["source"] == timing["source"]
    in_timing = {(r["at_bat_number"], r["pitch_number"]) for r in timing["annotations"]}
    index = {(p["at_bat_number"], p["pitch_number"]): p for p in manifest["pitches"]}
    for row in doc["rows"]:
        key = (row["at_bat_number"], row["pitch_number"])
        assert key not in in_timing  # candidates never duplicate merged rows
        assert row["play_id"] == index[key]["video"]["play_id"]
        assert row["verification"]["status"] != "verified" or row["verification"].get("by")

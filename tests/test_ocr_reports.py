"""OCR report refresh helpers: row comparison, confirmed-field counting and provenance carry-over."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

from src.data.scoreboard_evalset import LABEL_FIELDS, read_json, score_predictions
from src.vision import ocr_reports as reports

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "70_refresh_ocr_reports.py"


def load_script():
    spec = importlib.util.spec_from_file_location("refresh_ocr_reports", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


FIELDS = {
    "balls": 0,
    "strikes": 1,
    "outs": 0,
    "runner_on_1b": False,
    "runner_on_2b": False,
    "runner_on_3b": False,
    "inning": 1,
    "inning_topbot": "Top",
    "home_score": 0,
    "away_score": 0,
}


def row(pa, pitch, **fields):
    return {
        "game_pk": 1,
        "at_bat_number": pa,
        "pitch_number": pitch,
        "play_id": f"p{pa}-{pitch}",
        "fields": {**FIELDS, **fields},
    }


def entry(pa, pitch, unconfirmed=(), **labels):
    return {
        "game_pk": 1,
        "at_bat_number": pa,
        "pitch_number": pitch,
        "play_id": f"p{pa}-{pitch}",
        "frame_seconds": 10.0 * pa + pitch,
        "field_status": {
            f: "unconfirmed" if f in unconfirmed else "confirmed" for f in LABEL_FIELDS
        },
        "labels": {**FIELDS, **labels},
    }


def test_versions_point_at_existing_files():
    for files in reports.VERSIONS.values():
        assert set(files) == {"templates", "predictions", "score", "negatives", "provenance"}
        for name in files.values():
            assert (ROOT / reports.RESULTS_DIR / name).exists(), name
    assert reports.VERSIONS["v1"]["negatives"].endswith("_v0.json")  # legacy name kept
    assert set(reports.VERSIONS) == {"v1", "v2", "v3"}
    for path in reports.CODE_PATHS + reports.SHARED_INPUTS:
        assert (ROOT / (path if "/" in path else f"{reports.RESULTS_DIR}/{path}")).exists()


def test_template_plate_appearances_sorted_ints():
    doc = {"source": {"template_plate_appearances": [9, "2", 1]}}
    assert reports.template_plate_appearances(doc) == [1, 2, 9]


def test_compare_predictions_counts_changed_new_and_removed_rows():
    previous = [row(1, 1), row(1, 2, balls=1), row(2, 1)]
    current = [row(1, 1), row(1, 2, balls=2), row(3, 1)]
    result = reports.compare_predictions(previous, current)
    assert {k: v for k, v in result.items() if k != "changes"} == {
        "previous_rows": 3,
        "current_rows": 3,
        "shared_rows": 2,
        "identical_shared_rows": 1,
        "changed_shared_rows": 1,
        "new_rows": 1,
        "removed_rows": 1,
    }
    (change,) = result["changes"]
    assert (change["at_bat_number"], change["pitch_number"]) == (1, 2)
    assert change["before"]["balls"] == 1 and change["after"]["balls"] == 2
    assert reports.new_row_keys(previous, current) == [(1, 3, 1)]
    assert reports.compare_predictions([], current)["new_rows"] == 3
    with pytest.raises(ValueError):
        reports.compare_predictions([], [row(1, 1), row(1, 1)])


def test_new_rows_comparison_counts_only_confirmed_fields():
    evalset = {
        "entries": [
            entry(5, 1),
            entry(5, 2, unconfirmed=("home_score",), balls=2),
            entry(5, 3, unconfirmed=("outs",)),
        ]
    }
    predictions = [
        row(5, 1, inning=None),  # abstains on a confirmed field
        row(5, 2, balls=2, home_score=7),  # wrong only on the unconfirmed field
        row(5, 3, outs=2, strikes=0),  # wrong on strikes; outs is not evaluable
    ]
    result = reports.new_rows_comparison(evalset, predictions, [(1, 5, 1), (1, 5, 2), (1, 5, 3)])
    p1, p2, p3 = result["pitches"]
    assert p1["frame_seconds"] == 51.0
    assert (p1["evaluable_fields"], p1["correct_fields"]) == (10, 9)
    assert p1["abstained_fields"] == ["inning"] and p1["wrong_fields"] == []
    assert (p2["evaluable_fields"], p2["correct_fields"], p2["wrong_fields"]) == (9, 9, [])
    assert (p3["evaluable_fields"], p3["correct_fields"]) == (9, 8)
    assert p3["wrong_fields"] == ["strikes"] and p3["abstained_fields"] == []
    assert result["totals"] == {
        "pitch_count": 3,
        "fully_evaluable_pitches": 1,
        "all_fields_correct_pitches": 0,
        "pitches_with_wrong_field": 1,
        "pitches_with_abstention": 1,
        "new_rows_missing_from_evalset": 0,
    }
    # a bool never passes as the int 0 and vice versa
    typed = reports.new_rows_comparison(
        {"entries": [entry(6, 1)]}, [row(6, 1, balls=False)], [(1, 6, 1)]
    )
    assert typed["pitches"][0]["wrong_fields"] == ["balls"]


def test_new_rows_comparison_counts_rows_missing_from_evalset():
    """A predicted pitch the eval set does not know (eval set not rebuilt after a merge)."""
    evalset = {"entries": [entry(7, 1)]}
    predictions = [row(7, 1), row(7, 2)]
    result = reports.new_rows_comparison(evalset, predictions, [(1, 7, 1), (1, 7, 2)])
    assert result["totals"]["new_rows_missing_from_evalset"] == 1
    assert result["totals"]["pitch_count"] == 2
    missing = result["pitches"][1]
    assert missing["frame_seconds"] is None and missing["evaluable_fields"] == 0
    assert missing["wrong_fields"] == [] and missing["abstained_fields"] == []


def test_repeat_check_and_code_entry(tmp_path):
    rows = [row(1, 1), row(1, 2)]
    check = reports.repeat_check(rows, [row(1, 1), row(1, 2, balls=3)], {"path": "r.json"})
    assert (check["prediction_rows"], check["matching_rows"]) == (2, 1)
    assert check["parsed_documents_equal"] is False
    (tmp_path / "a.json").write_bytes(b'{"x": [1,\r\n 2]}\r\n')
    (tmp_path / "b.py").write_bytes(b"x = 1\r\n")
    a = reports.code_entry(tmp_path, "a.json", b'{"x": [1, 2]}\n')
    assert a["lf_normalized_equal_to_reference"] is False
    assert a["json_semantically_equal_to_reference"] is True
    b = reports.code_entry(tmp_path, "b.py", b"x = 1\n")
    assert b["lf_normalized_equal_to_reference"] is True and "json_semantically" not in str(b)
    assert reports.code_entry(tmp_path, "b.py", None)["lf_normalized_equal_to_reference"] is None
    assert b["bytes"] == 7 and len(b["sha256"]) == 64


def test_frame_cache_reports_missing_frames(tmp_path):
    evalset = {"entries": [entry(1, 1), entry(1, 2)]}
    frames = tmp_path / "frames"
    frames.mkdir()
    (frames / "evalset_11.00.jpg").write_bytes(b"jpeg")
    cache = reports.frame_cache(evalset, tmp_path, frames_dir="frames")
    assert cache["frame_count"] == 2 and cache["complete"] is False
    assert cache["frames"][0]["path"] == "frames/evalset_11.00.jpg"
    assert cache["frames"][0]["bytes"] == 4 and cache["frames"][1]["sha256"] is None


def test_carried_artifacts_rehashes_extra_files_that_still_exist(tmp_path):
    results = tmp_path / "docs" / "results" / "mlb_p0"
    results.mkdir(parents=True)
    (results / "v2_comparison.json").write_bytes(b"{}\n")
    (results / "v2_predictions.json").write_bytes(b"[]\n")
    existing = {
        "artifacts": [
            {"path": "docs/results/mlb_p0/v2_predictions.json", "sha256": "old", "bytes": 1},
            {"path": "docs/results/mlb_p0/v2_comparison.json", "sha256": "old", "bytes": 1},
            {"path": "docs/results/mlb_p0/gone.json", "sha256": "old", "bytes": 1},
        ]
    }
    # the recomputed predictions live in another out-dir: matched by file name, not carried
    artifacts = [{"path": "outputs/x/v2_predictions.json", "sha256": "new", "bytes": 3}]
    (carried,) = reports.carried_artifacts(existing, artifacts, tmp_path)
    assert carried == {
        "path": "docs/results/mlb_p0/v2_comparison.json",
        "sha256": reports.sha256_bytes(b"{}\n"),
        "bytes": 3,
        "carried": True,
    }
    assert reports.carried_artifacts(None, artifacts, tmp_path) == []


def provenance_kwargs(existing, label="unit"):
    return dict(
        version="v2",
        recorded_at="2026-09-26",
        recorded_by="test",
        label=label,
        reference_commit="abc1234",
        replaced_commit="def5678",
        evalset={"game_pk": 1, "source": {"media_url": "m"}, "manifest_sha256": "0" * 64},
        template_pas=[1, 2],
        code_and_templates=[],
        artifacts=[],
        frame_cache={"frame_count": 0},
        repeat={"parsed_documents_equal": True},
        comparison=reports.compare_predictions([row(1, 1)], [row(1, 1), row(1, 2)]),
        new_rows={"totals": {"pitch_count": 1}, "pitches": []},
        commands=["cmd"],
        runtime={"python_version": "x"},
    )


def test_build_provenance_keeps_legacy_and_extra_keys_and_appends_audit():
    existing = {
        "schema": reports.PROVENANCE_SCHEMA,
        "game_pk": 1,
        "recorded_at": "2026-09-25",
        "recorded_by": "old audit",
        "scope": "old",
        "git_reference": {"commit": "old", "meaning": "old"},
        "runtime": {},
        "source": {},
        "manifest_sha256": "1" * 64,
        "preregistration": {"rule": "fixed"},
        "code_and_templates": [],
        "unchanged_since_reference": {"x": True},
        "artifacts": [],
        "frame_cache": {},
        "current_repeat_check": {},
        "previous_prediction_comparison": {},
        "new_pa20_comparison": {"pitch_count": 6},
        "historical_audit": [{"commit": "1111111", "path": "p", "note": "first"}],
        "reproduction_commands": ["old"],
        "limitations": ["same-game evidence"],
    }
    document = reports.build_provenance(existing, **provenance_kwargs(existing))
    assert list(document) == [
        "schema",
        "game_pk",
        "recorded_at",
        "recorded_by",
        "scope",
        "git_reference",
        "runtime",
        "source",
        "manifest_sha256",
        "preregistration",
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
    ]
    assert document["schema"] == "mlb_scoreboard_ocr_provenance_v1"
    assert document["preregistration"] == {"rule": "fixed"}  # version-wide: stays on top
    # reference-tied keys are never left next to the new git_reference
    assert "unchanged_since_reference" not in document
    assert document["carried_from_previous"] == {
        "git_reference": {"commit": "old", "meaning": "old"},
        "recorded_at": "2026-09-25",
        "unchanged_since_reference": {"x": True},
    }
    assert document["limitations"] == ["same-game evidence"]
    assert document["git_reference"]["commit"] == "abc1234"
    assert document["previous_prediction_comparison"]["reference_commit"] == "abc1234"
    assert document["previous_prediction_comparison"]["new_rows"] == 1
    assert document["new_rows_comparison"] == {
        "label": "unit",
        "reference_commit": "abc1234",
        "totals": {"pitch_count": 1},
        "pitches": [],
    }
    assert "new_pa20_comparison" not in document
    assert document["historical_audit"][0] == existing["historical_audit"][0]
    appended = document["historical_audit"][1]
    assert appended["commit"] == "def5678"
    assert appended["path"] == "docs/results/mlb_p0/game_747139_scoreboard_ocr_v2_provenance.json"
    assert "old audit" in appended["note"] and "2026-09-25" in appended["note"]
    assert len(document["historical_audit"]) == 2
    assert existing["historical_audit"] == [existing["historical_audit"][0]]  # not mutated
    json.dumps(document, allow_nan=False)


def test_build_provenance_with_dict_audit_and_without_existing():
    existing = {
        "schema": reports.PROVENANCE_SCHEMA,
        "historical_audit": {"commit": "2222222", "path": "p", "note": "dict form"},
        "limitations": ["kept"],
    }
    document = reports.build_provenance(existing, **provenance_kwargs(existing))
    assert document["historical_audit"][0] == {
        "commit": "2222222",
        "path": "p",
        "note": "dict form",
    }
    assert document["historical_audit"][1]["commit"] == "def5678"
    assert document["limitations"] == ["kept"]
    assert "carried_from_previous" not in document  # nothing reference-tied to carry
    fresh = reports.build_provenance(None, **provenance_kwargs(None))
    assert list(fresh) == [k for k in reports.PROVENANCE_ORDER if k != "carried_from_previous"]
    assert fresh["historical_audit"] == []
    assert fresh["limitations"] == reports.DEFAULT_LIMITATIONS
    assert "held-out score" in fresh["scope"] and "exclude-pas score" not in fresh["scope"]


def test_score_set_note_labels_only_the_versions_that_carry_one():
    """v3's exclude-pas score is a mixed set (75 held-out + 19 seen); v1/v2 documents unchanged."""
    assert set(reports.SCORE_SET_NOTES) == {"v3"} and set(reports.SCORE_SET_NOTES) <= set(
        reports.VERSIONS
    )
    note = reports.SCORE_SET_NOTES["v3"]
    assert "75 held-out" in note and "19 seen/diagnosed" in note and "mixed set" in note
    for version in ("v1", "v2"):
        document = reports.build_provenance(None, **{**provenance_kwargs(None), "version": version})
        assert "held-out score" in document["scope"]
        assert "exclude-pas" not in document["scope"]
        assert document["limitations"] == reports.DEFAULT_LIMITATIONS
        # an existing document's limitations are kept as they are (v1/v2 refresh path)
        kept = reports.build_provenance(
            {"limitations": ["kept"]}, **{**provenance_kwargs(None), "version": version}
        )
        assert kept["limitations"] == ["kept"]
    v3 = reports.build_provenance(
        None, **{**provenance_kwargs(None), "version": "v3", "template_pas": [1, 2, 9, 18, 29]}
    )
    assert "exclude-pas score (a mixed set, see limitations)" in v3["scope"]
    assert "held-out score" not in v3["scope"]
    assert v3["limitations"] == [*reports.DEFAULT_LIMITATIONS, note]
    # the committed v3 provenance carries exactly this labelling
    stored = json.loads(
        (ROOT / reports.RESULTS_DIR / reports.VERSIONS["v3"]["provenance"]).read_text(
            encoding="utf-8"
        )
    )
    assert "exclude-pas score (a mixed set, see limitations)" in stored["scope"]
    assert stored["limitations"][-1] == note
    for version in ("v1", "v2"):
        committed = json.loads(
            (ROOT / reports.RESULTS_DIR / reports.VERSIONS[version]["provenance"]).read_text(
                encoding="utf-8"
            )
        )
        assert "held-out score" in committed["scope"] and note not in committed["limitations"]


def test_build_provenance_passes_or_nests_an_existing_carried_block():
    """A second refresh keeps the block as is; a third stray key nests it under a new one."""
    old_block = {
        "git_reference": {"commit": "old"},
        "recorded_at": "2026-09-25",
        "unchanged_since_reference": {"x": True},
    }
    existing = {
        "schema": reports.PROVENANCE_SCHEMA,
        "recorded_at": "2026-09-26",
        "git_reference": {"commit": "mid", "meaning": "mid"},
        "carried_from_previous": old_block,
    }
    document = reports.build_provenance(existing, **provenance_kwargs(existing))
    assert document["carried_from_previous"] == old_block
    existing["stray"] = 1
    nested = reports.build_provenance(existing, **provenance_kwargs(existing))
    assert "stray" not in nested
    assert nested["carried_from_previous"] == {
        "git_reference": {"commit": "mid", "meaning": "mid"},
        "recorded_at": "2026-09-26",
        "stray": 1,
        "carried_from_previous": old_block,
    }


def test_reproduction_commands_and_score_summary():
    commands = reports.reproduction_commands("v1", [1, 2, 9], out_dir="out", no_grab=True)
    assert len(commands) == 5
    assert commands[0] == (
        "python scripts/66_sny_scoreboard_ocr.py templates --template-pas 1 2 9 --no-grab "
        "--output docs/results/mlb_p0/sny_digit_templates_v1.json"
    )
    assert (
        "--exclude-pas 1 2 9" in commands[2]
        and "out/game_747139_scoreboard_ocr_v1.json" in commands[2]
    )
    assert commands[1].endswith(
        "--no-grab --output out/game_747139_scoreboard_ocr_v1_predictions.json"
    )
    assert commands[3].endswith("out/game_747139_scoreboard_negatives_score_v0.json")
    assert commands[4].endswith("outputs/verification/ocr_v1_repeat.json")
    assert not any("--reader-options" in c for c in commands)
    # a template file that carries reader_options (v3) has them echoed on the templates command
    options = {
        "top_line_gate": {"aggregate": "max_row", "threshold": 0.6},
        "border_sliver_max_width": 2,
    }
    v3 = reports.reproduction_commands("v3", [1, 2, 9, 18, 29], reader_options=options)
    assert v3[0] == (
        "python scripts/66_sny_scoreboard_ocr.py templates --template-pas 1 2 9 18 29 --no-grab "
        '--reader-options \'{"top_line_gate":{"aggregate":"max_row","threshold":0.6},'
        '"border_sliver_max_width":2}\' --output docs/results/mlb_p0/sny_digit_templates_v3.json'
    )
    assert sum("--reader-options" in c for c in v3) == 1
    assert "--exclude-pas 1 2 9 18 29" in v3[2]
    assert v3[2].endswith("game_747139_scoreboard_ocr_v3.json")
    assert v3[3].endswith("game_747139_scoreboard_negatives_score_v3.json")
    assert reports.reproduction_commands("v3", [1], reader_options={})[0].endswith(
        "--no-grab --output docs/results/mlb_p0/sny_digit_templates_v3.json"
    )
    score = {
        "all_fields": {"evaluable": 5, "correct": 3, "abstained": 1, "wrong": 1, "coverage": 0.1},
        "per_field": {"balls": {"wrong": 1}, "strikes": {"wrong": 0}},
    }
    assert reports.score_summary(score) == {
        "evaluable": 5,
        "correct": 3,
        "abstained": 1,
        "wrong": 1,
        "wrong_per_field": {"balls": 1},
    }


def score_doc(per_field_wrong=(), all_wrong=0):
    per_field = {f: {"wrong": 0} for f in LABEL_FIELDS}
    for field in per_field_wrong:
        per_field[field]["wrong"] += 1
    return {
        "all_fields": {"evaluable": 5, "correct": 3, "abstained": 2, "wrong": all_wrong},
        "per_field": per_field,
    }


def negatives_doc(false_reads=0, wrong_reads=0):
    return {"totals": {"false_reads": false_reads, "wrong_reads": wrong_reads}}


def new_rows_doc(wrong=0):
    return {"totals": {"pitch_count": 6, "pitches_with_wrong_field": wrong}, "pitches": []}


def test_wrong_read_problems_sees_per_field_negatives_and_new_rows():
    assert reports.wrong_read_problems("v1", score_doc(), negatives_doc(), new_rows_doc()) == []
    # a wrong field beside an abstention never reaches all_fields.wrong; per_field catches it
    (problem,) = reports.wrong_read_problems(
        "v1", score_doc(per_field_wrong=["balls"]), negatives_doc(), new_rows_doc()
    )
    assert problem.startswith("v1:") and '"balls": 1' in problem
    problems = reports.wrong_read_problems(
        "v2", score_doc(), negatives_doc(false_reads=2, wrong_reads=1), new_rows_doc(wrong=3)
    )
    assert [p.split(": ", 1)[1] for p in problems] == [
        "negatives have 2 false reads",
        "negatives have 1 wrong reads",
        "3 new pitch(es) have a wrong field",
    ]


def test_wrong_read_on_pitch_with_abstention_is_caught_by_real_scorer():
    """Reviewer case: (747139, 4, 1) with a wrong ``balls`` beside an abstained ``inning``."""
    results = ROOT / reports.RESULTS_DIR
    evalset = read_json(results / "game_747139_scoreboard_evalset.json")
    predictions = read_json(results / reports.VERSIONS["v1"]["predictions"])
    key = (747139, 4, 1)
    (target,) = [p for p in predictions if reports.row_key(p) == key]
    entry = {reports.row_key(e): e for e in evalset["entries"]}[key]
    assert entry["field_status"]["balls"] == "confirmed"
    assert target["fields"]["inning"] is None, "the case needs an abstention on the same pitch"
    target["fields"]["balls"] = (entry["labels"]["balls"] + 1) % 4
    score = score_predictions(evalset, predictions)
    assert score["all_fields"]["wrong"] == 0  # why the old all_fields check missed it
    assert reports.score_summary(score)["wrong_per_field"] == {"balls": 1}
    problems = reports.wrong_read_problems("v1", score, negatives_doc(), new_rows_doc())
    assert len(problems) == 1 and '"balls": 1' in problems[0]


def test_resolve_reference_returns_short_sha_or_none():
    script = load_script()
    head = subprocess.run(
        ["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True, text=True
    ).stdout.strip()
    assert script.resolve_reference("HEAD") == head
    assert script.resolve_reference(head) == head
    for bad in ("ca76e6x", "no-such-branch", "HEAD~999999", "HEAD:AGENTS.md"):
        assert script.resolve_reference(bad) is None, bad


@pytest.mark.parametrize(
    "script, marker",
    [
        (SCRIPT, "OVERWRITES the committed reports"),
        (ROOT / "scripts" / "71_timing_review_sheet.py", "--dec 2208.75"),
    ],
)
def test_script_help_keeps_usage_examples_readable(script, marker):
    run = subprocess.run(
        [sys.executable, str(script), "--help"],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert run.returncode == 0
    assert "Usage::" in run.stdout and marker in run.stdout
    # RawDescriptionHelpFormatter + raw docstring: the example keeps its line break
    assert " \\\n        --" in run.stdout


def test_script_rejects_unknown_reference_before_running_anything(tmp_path):
    out_dir = tmp_path / "out"
    run = subprocess.run(
        [
            sys.executable,
            str(SCRIPT),
            "--reference",
            "ca76e6x",
            "--label",
            "unit",
            "--date",
            "2026-09-26",
            "--out-dir",
            str(out_dir),
            "--no-grab",
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        encoding="utf-8",
    )
    assert run.returncode == 2
    assert "ca76e6x" in run.stderr and "does not name a commit" in run.stderr
    assert not out_dir.exists()

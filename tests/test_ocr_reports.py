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
    assert set(reports.VERSIONS) == {"v1", "v2", "v3", "v4"}
    assert reports.VERSIONS["v4"]["negatives"] == "game_747139_scoreboard_negatives_score_v4.json"
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
    """v3's exclude-pas score is a mixed set (75 held-out + 19 seen), v4's a development set
    (0 held-out); v1/v2 documents unchanged."""
    assert set(reports.SCORE_SET_NOTES) == {"v3", "v4"} and set(reports.SCORE_SET_NOTES) <= set(
        reports.VERSIONS
    )
    assert set(reports.SCORE_SET_KINDS) == set(reports.SCORE_SET_NOTES)
    note = reports.SCORE_SET_NOTES["v3"]
    assert "75 held-out" in note and "19 seen/diagnosed" in note and "mixed set" in note
    v4_note = reports.SCORE_SET_NOTES["v4"]
    assert "DEVELOPMENT set" in v4_note and "0 held-out" in v4_note and "A-10" in v4_note
    v4 = reports.build_provenance(
        None, **{**provenance_kwargs(None), "version": "v4", "template_pas": [1, 2, 9, 18, 29]}
    )
    assert "exclude-pas score (a development set, see limitations)" in v4["scope"]
    assert "held-out score" not in v4["scope"] and "mixed" not in v4["scope"]
    assert v4["limitations"] == [*reports.DEFAULT_LIMITATIONS, v4_note]
    stored_v4 = json.loads(
        (ROOT / reports.RESULTS_DIR / reports.VERSIONS["v4"]["provenance"]).read_text(
            encoding="utf-8"
        )
    )
    assert "exclude-pas score (a development set, see limitations)" in stored_v4["scope"]
    assert stored_v4["limitations"][-1] == v4_note
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
    v4_options = {**options, "arrow_window": [262, 46, 279, 64]}
    v4 = reports.reproduction_commands("v4", [1, 2, 9, 18, 29], reader_options=v4_options)
    assert '"arrow_window":[262,46,279,64]' in v4[0]
    assert v4[0].endswith("--output docs/results/mlb_p0/sny_digit_templates_v4.json")
    assert v4[3].endswith("game_747139_scoreboard_negatives_score_v4.json")
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


def known_register():
    return read_json(ROOT / reports.RESULTS_DIR / reports.KNOWN_MISREADS)


def test_wrong_read_on_pitch_with_abstention_is_caught_by_real_scorer():
    """Reviewer case: (747139, 4, 1) with a wrong ``balls`` beside an abstained ``inning``."""
    results = ROOT / reports.RESULTS_DIR
    evalset = read_json(results / "game_747139_scoreboard_evalset.json")
    predictions = read_json(results / reports.VERSIONS["v1"]["predictions"])
    known = reports.known_misreads(known_register(), "v1")
    key = (747139, 4, 1)
    (target,) = [p for p in predictions if reports.row_key(p) == key]
    entry = {reports.row_key(e): e for e in evalset["entries"]}[key]
    assert entry["field_status"]["balls"] == "confirmed"
    assert target["fields"]["inning"] is None, "the case needs an abstention on the same pitch"
    before = reports.score_summary(score_predictions(evalset, predictions))["wrong_per_field"]
    target["fields"]["balls"] = (entry["labels"]["balls"] + 1) % 4
    score = score_predictions(evalset, predictions)
    assert score["all_fields"]["wrong"] == 0  # why the old all_fields check missed it
    assert reports.score_summary(score)["wrong_per_field"] == {**before, "balls": 1}
    reads = reports.wrong_reads(evalset, predictions)
    problems = reports.wrong_read_problems(
        "v1", score, negatives_doc(), new_rows_doc(), reads=reads, known=known
    )
    assert len(problems) == 2, problems
    assert '"balls": 1' in problems[0] and "wrong read 4/1 balls = 1 is not in" in problems[1]


def misread(pa, pitch, field, read, label):
    return {
        "game_pk": 747139,
        "at_bat_number": pa,
        "pitch_number": pitch,
        "field": field,
        "read": read,
        "label": label,
    }


def register(*items, versions=("v2",)):
    return {
        "schema": reports.KNOWN_MISREADS_SCHEMA,
        "misreads": [{**m, "versions": list(versions)} for m in items],
    }


def test_known_misreads_pass_and_stale_or_unknown_ones_fail():
    listed = misread(34, 3, "inning_topbot", "Bot", "Top")
    known = reports.known_misreads(register(listed), "v2")
    assert known == {(747139, 34, 3, "inning_topbot"): "Bot"}
    assert reports.known_misreads(register(listed), "v1") == {}
    new_rows = {
        "totals": {"pitch_count": 2, "pitches_with_wrong_field": 1},
        "pitches": [
            {**misread(34, 3, "x", 0, 0), "wrong_fields": ["inning_topbot"]},
            {**misread(34, 4, "x", 0, 0), "wrong_fields": []},
        ],
    }
    score = score_doc(per_field_wrong=["inning_topbot"])
    problems = reports.wrong_read_problems(
        "v2", score, negatives_doc(), new_rows, reads=[listed], known=known
    )
    assert problems == []
    # the same wrong read without the register fails in the score, the new rows and the reads
    problems = reports.wrong_read_problems("v2", score, negatives_doc(), new_rows, reads=[listed])
    assert len(problems) == 3 and "34/3 inning_topbot = 'Bot' is not in" in problems[2]
    # a listed read inside an excluded (template) plate appearance is not expected in the score
    held = {**score_doc(), "holdout": {"excluded_plate_appearances": [34]}}
    problems = reports.wrong_read_problems(
        "v2", held, negatives_doc(), new_rows_doc(), reads=[listed], known=known
    )
    assert problems == []
    # a listed read that no longer happens (or reads another value) fails: the register stays true
    (stale,) = reports.wrong_read_problems(
        "v2", held, negatives_doc(), new_rows_doc(), reads=[], known=known
    )
    assert "known misread 34/3 inning_topbot = 'Bot' no longer happens (now None)" in stale
    with pytest.raises(ValueError, match="schema"):
        reports.known_misreads({"schema": "other", "misreads": []}, "v2")


def test_wrong_reads_skip_abstentions_unconfirmed_fields_and_unknown_rows():
    entry = {
        **misread(1, 1, "x", 0, 0),
        "labels": dict(FIELDS),
        "field_status": {f: "confirmed" for f in LABEL_FIELDS} | {"outs": "unreadable"},
    }
    rows = [
        {**misread(1, 1, "x", 0, 0), "fields": {**FIELDS, "balls": 3, "outs": 2, "strikes": None}},
        {**misread(9, 9, "x", 0, 0), "fields": {**FIELDS, "balls": 3}},
    ]
    assert reports.wrong_reads({"entries": [entry]}, rows) == [misread(1, 1, "balls", 3, 0)]


@pytest.mark.parametrize("version", sorted(reports.VERSIONS))
def test_committed_register_lists_exactly_the_committed_wrong_reads(version):
    """The register and the stored predictions agree, so a refresh starts from a clean gate."""
    results = ROOT / reports.RESULTS_DIR
    evalset = read_json(results / "game_747139_scoreboard_evalset.json")
    predictions = read_json(results / reports.VERSIONS[version]["predictions"])
    reads = {
        (r["game_pk"], r["at_bat_number"], r["pitch_number"], r["field"]): r["read"]
        for r in reports.wrong_reads(evalset, predictions)
    }
    assert reads == reports.known_misreads(known_register(), version)
    for item in known_register()["misreads"]:
        assert set(item["versions"]) <= set(reports.VERSIONS)
        assert item["read"] != item["label"] and item["cause"] and item["evidence"]


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


def test_new_rows_field_counts_and_acceptance_rule():
    """The pre-registered A-10 rule: no wrong field, per-field correct >= every baseline."""
    evalset = {"entries": [entry(41, 1), entry(41, 2, unconfirmed=("home_score",)), entry(41, 3)]}
    keys = [(1, 41, 1), (1, 41, 2), (1, 41, 3)]
    candidate = reports.new_rows_comparison(
        evalset, [row(41, 1, inning=None), row(41, 2, inning=None), row(41, 3, inning=None)], keys
    )
    counts = reports.new_rows_field_counts(evalset, candidate)
    assert counts["inning"] == {"correct": 0, "abstained": 3, "wrong": 0}
    assert counts["home_score"] == {"correct": 2, "abstained": 0, "wrong": 0}
    assert counts["balls"] == {"correct": 3, "abstained": 0, "wrong": 0}
    weaker = reports.new_rows_comparison(
        evalset,
        [row(41, 1, inning=None, balls=None), row(41, 2, inning=None), row(41, 3, inning=None)],
        keys,
    )
    verdict = reports.new_rows_acceptance(evalset, candidate, {"v2": weaker, "v3": weaker})
    assert verdict["passes"] is True and verdict["valid"] is True and verdict["reasons"] == []
    assert verdict["per_field_correct"]["balls"] == {"candidate": 3, "v2": 2, "v3": 2}
    # v2 reading the inning by luck where the candidate abstains fails it (no exclusion clause)
    lucky = reports.new_rows_comparison(evalset, [row(41, 1), row(41, 2), row(41, 3)], keys)
    verdict = reports.new_rows_acceptance(evalset, candidate, {"v2": lucky})
    assert verdict["passes"] is False
    assert verdict["reasons"] == ["inning: candidate correct 0 < v2 3"]
    # any wrong field fails, and so do negatives false/wrong reads
    wrong = reports.new_rows_comparison(
        evalset, [row(41, 1, balls=3), row(41, 2), row(41, 3)], keys
    )
    verdict = reports.new_rows_acceptance(
        evalset, wrong, {}, negatives_totals={"false_reads": 1, "wrong_reads": 0}
    )
    assert verdict["passes"] is False
    assert verdict["reasons"] == [
        "1 new pitch(es) have a wrong field",
        "negatives have 1 false reads",
    ]
    # a wrong read anywhere in the candidate's rows (not only on the new rows) fails too
    verdict = reports.new_rows_acceptance(
        evalset, candidate, {}, wrong_reads=reports.wrong_reads(evalset, [row(41, 1, balls=3)])
    )
    assert verdict["passes"] is False
    assert verdict["reasons"] == ["1 wrong read(s) over all candidate rows"]
    assert reports.new_rows_acceptance(evalset, candidate, {}, wrong_reads=[])["passes"] is True
    # a new row the eval set does not know makes the check invalid, not failed
    stale = reports.new_rows_comparison(evalset, [row(41, 1), row(41, 9)], [(1, 41, 1), (1, 41, 9)])
    verdict = reports.new_rows_acceptance(evalset, stale, {})
    assert verdict["valid"] is False and verdict["passes"] is False
    assert verdict["reasons"] == ["1 new row(s) not in the eval set"]
    # so does a baseline block over other pitches than the candidate's
    partial = reports.new_rows_comparison(evalset, [row(41, 1), row(41, 2)], keys[:2])
    verdict = reports.new_rows_acceptance(evalset, candidate, {"v2": lucky, "v3": partial})
    assert verdict["valid"] is False and verdict["passes"] is False
    assert verdict["reasons"][0] == "v3 block covers other pitches than the candidate"
    assert verdict["reasons"][1:] == [
        "inning: candidate correct 0 < v2 3",
        "inning: candidate correct 0 < v3 2",
    ]

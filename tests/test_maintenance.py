"""Protect relocated experiments, conservative resume, and inference independence."""

import json
from pathlib import Path

import pytest

from src.utils.experiment_paths import resolve_selected_runs
from src.utils.pipeline import prepare_stage


def test_relocated_windows_selection_resolves_without_old_machine_paths(tmp_path):
    run = tmp_path / "experiments" / "mlp135_seed42"
    run.mkdir(parents=True)
    (run / "manifest.json").write_text("{}")
    selection = {"selected": "mlp135", "groups": {"mlp135": [r"C:\old\outputs\mlp135_seed42"]}}
    assert resolve_selected_runs(selection, tmp_path / "experiments" / "evaluation") == [run]


def test_versioned_selection_supports_custom_relative_and_explicit_roots(tmp_path):
    run = tmp_path / "models" / "mlp77_seed42"
    run.mkdir(parents=True)
    (run / "manifest.json").write_text("{}")
    selection = {
        "selected": "mlp77",
        "run_names": {"mlp77": [run.name]},
        "runs_root_relative": "../models",
    }
    assert resolve_selected_runs(selection, tmp_path / "evaluation") == [run]
    assert resolve_selected_runs(selection, tmp_path / "somewhere", run.parent) == [run]


@pytest.mark.parametrize("name", ["..", "../outside", r"..\outside", "C:outside", ""])
def test_run_names_cannot_escape_model_directory(tmp_path, name):
    with pytest.raises(ValueError, match="Invalid"):
        resolve_selected_runs({"selected": "x", "run_names": {"x": [name]}}, tmp_path)


def test_missing_moved_checkpoint_has_actionable_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="--runs-dir"):
        resolve_selected_runs({"selected": "x", "run_names": {"x": ["missing"]}}, tmp_path)


def test_resume_preserves_interrupted_outputs(tmp_path):
    output = tmp_path / "run"
    output.mkdir()
    (output / "partial.pt").write_bytes(b"unfinished checkpoint")
    marker = output / "manifest.json"
    marker.write_text(json.dumps({"status": "running"}))
    assert prepare_stage(output, marker, resume=True)
    assert not output.exists()
    archived = list(tmp_path.glob("run.interrupted-*"))
    assert len(archived) == 1
    assert (archived[0] / "partial.pt").read_bytes() == b"unfinished checkpoint"


def test_resume_skips_only_matching_complete_stages(tmp_path):
    output = tmp_path / "run"
    output.mkdir()
    marker = output / "manifest.json"
    marker.write_text(json.dumps({"status": "complete", "seed": 42}))
    (output / "best.pt").write_bytes(b"complete checkpoint")
    assert not prepare_stage(output, marker, ["best.pt"], resume=True, expected={"seed": 42})
    with pytest.raises(ValueError, match="configuration mismatch"):
        prepare_stage(output, marker, resume=True, expected={"seed": 43})
    with pytest.raises(FileExistsError, match="--resume"):
        prepare_stage(output, marker)


def test_upstream_rebuild_archives_stale_completed_downstream(tmp_path):
    output = tmp_path / "evaluation"
    output.mkdir()
    marker = output / "report.json"
    marker.write_text('{"old_result": true}')
    assert prepare_stage(output, marker, resume=True, force=True)
    assert not output.exists()
    assert len(list(tmp_path.glob("evaluation.superseded-*"))) == 1


def test_missing_required_output_restarts_even_with_completion_marker(tmp_path):
    output = tmp_path / "model"
    output.mkdir()
    marker = output / "manifest.json"
    marker.write_text('{"status":"complete"}')
    assert prepare_stage(output, marker, ["best.pt"], resume=True)


def test_pipeline_propagates_rebuilt_model_to_evaluation_and_policy(tmp_path, monkeypatch):
    import importlib.util
    import sys

    script = Path(__file__).resolve().parents[1] / "scripts/55_run_operational_validation.py"
    spec = importlib.util.spec_from_file_location("pipeline_cli", script)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    data, runs = tmp_path / "data", tmp_path / "runs"
    data.mkdir()
    (data / "dataset_manifest.json").write_text("{}")
    calls = []

    def fake_prepare(output, marker, required=(), **kwargs):
        execute = output.name == "mlp77_seed43" or kwargs.get("force", False)
        output.parent.mkdir(parents=True, exist_ok=True)
        if output.suffix != ".html":
            output.mkdir(exist_ok=True)
            marker.write_text("{}")
        calls.append((output.name, kwargs.get("force", False), execute))
        return execute

    monkeypatch.setattr(module, "prepare_stage", fake_prepare)
    executed = []
    monkeypatch.setattr(
        module.subprocess, "run", lambda command, **kwargs: executed.append(command)
    )
    monkeypatch.setattr(
        sys, "argv", [str(script), "--data-dir", str(data), "--run-dir", str(runs), "--resume"]
    )
    module.main()
    assert ("evaluation", True, True) in calls
    assert ("policy", True, True) in calls
    assert ("demo.html", True, True) in calls
    assert sum("src.training.point_baselines" in c for c in executed) == 1

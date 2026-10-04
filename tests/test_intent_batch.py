"""Local fixture subprocesses exercise immutable artifacts and explicit resumes."""

from __future__ import annotations

import json
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

from intent import batch
from intent.batch import BatchError, _lock, check_plan, execute_plan, load_plan, main

WORKER = """from pathlib import Path
import sys
import time

source, target = Path(sys.argv[1]), Path(sys.argv[2])
print("fixture stdout", flush=True)
print("fixture stderr", file=sys.stderr, flush=True)
if "--sleep" in sys.argv:
    time.sleep(10)
if "--missing" not in sys.argv:
    target.write_text(source.read_text() + "|processed", encoding="utf-8")
if "--fail-first" in sys.argv and "attempt-0001" in target.parts:
    raise SystemExit(7)
"""


@pytest.fixture
def fixture_plan() -> Iterator[tuple[Path, Path, dict]]:
    # check_project places pytest's tmp_path under the real repository's .cache.
    # Use an owned OS temp project so tests do not relax the production rule that
    # every containing Git repository permits run directories only under outputs/.
    temporary_root = Path(tempfile.gettempdir()).resolve()
    with tempfile.TemporaryDirectory(prefix="intent-batch-test-", dir=temporary_root) as directory:
        owned_root = Path(directory).resolve()
        assert owned_root.parent == temporary_root
        assert owned_root.name.startswith("intent-batch-test-")
        project = owned_root / "project"
        project.mkdir()
        (project / "worker.py").write_text(WORKER, encoding="utf-8")
        (project / "input.txt").write_text("frame-reference", encoding="utf-8")
        (project / "helper.py").write_text("VERSION = 1\n", encoding="utf-8")
        plan = {
            "schema_version": 1,
            "project_root": str(project),
            "inputs": {"frames": "input.txt"},
            "source_files": ["helper.py"],
            "config": {"study": "toy-only"},
            "jobs": [
                {
                    "id": "quality",
                    "argv": ["worker.py", "{input:frames}", "{output:report}"],
                    "outputs": {"report": "report.txt"},
                },
            ],
        }
        plan_path = project / "plan.json"
        _write(plan_path, plan)
        yield plan_path, project / "outputs" / "run-001", plan


def _write(path: Path, value: dict) -> None:
    path.write_text(json.dumps(value), encoding="utf-8")


def test_failure_resume_skips_success_and_preserves_partial_output(fixture_plan):
    plan_path, run_dir, plan = fixture_plan
    plan["jobs"].append(
        {
            "id": "temporal",
            "argv": ["worker.py", "{job:quality:report}", "{output:report}", "--fail-first"],
            "outputs": {"report": "nested/report.txt"},
        }
    )
    _write(plan_path, plan)
    initial = execute_plan(plan_path, run_dir)
    assert initial["jobs"]["quality"]["status"] == "succeeded"
    failed = initial["jobs"]["temporal"]["attempts"][0]
    assert failed["status"] == "failed" and failed["returncode"] == 7
    assert failed["elapsed_seconds"] >= 0
    assert "fixture stdout" in (run_dir / failed["stdout"]).read_text()
    assert "fixture stderr" in (run_dir / failed["stderr"]).read_text()
    partial = run_dir / "jobs/temporal/attempt-0001/artifacts/nested/report.txt"
    partial_bytes = partial.read_bytes()
    complete = execute_plan(plan_path, run_dir, resume=True)
    assert complete["jobs"]["temporal"]["status"] == "succeeded"
    assert len(complete["jobs"]["quality"]["attempts"]) == 1
    assert len(complete["jobs"]["temporal"]["attempts"]) == 2
    assert partial.read_bytes() == partial_bytes
    assert check_plan(plan_path, run_dir)["executed"] is False
    repeat = execute_plan(plan_path, run_dir, resume=True)
    assert repeat == complete
    assert complete["timing_scope"] == "subprocess_execution_only_not_video_end_to_end"


@pytest.mark.parametrize("change", ["input", "config", "source", "entry_source", "output"])
def test_hash_change_blocks_resume_before_execution(fixture_plan, change):
    plan_path, run_dir, plan = fixture_plan
    execute_plan(plan_path, run_dir)
    project = plan_path.parent
    if change == "input":
        (project / "input.txt").write_text("changed")
    elif change == "config":
        plan["config"]["study"] = "changed"
        _write(plan_path, plan)
    elif change in {"source", "entry_source"}:
        source = project / ("helper.py" if change == "source" else "worker.py")
        source.write_text(source.read_text() + "\n# changed\n")
    else:
        (run_dir / "jobs/quality/attempt-0001/artifacts/report.txt").write_text("changed")
    with pytest.raises(BatchError):
        execute_plan(plan_path, run_dir, resume=True)
    assert not (run_dir / "jobs/quality/attempt-0002").exists()


@pytest.mark.parametrize("output", ["../bad", "/bad", "C:/bad", "nested\\bad", "a/../b"])
def test_output_traversal_is_rejected(fixture_plan, output):
    plan_path, run_dir, plan = fixture_plan
    plan["jobs"][0]["outputs"]["report"] = output
    _write(plan_path, plan)
    with pytest.raises(BatchError):
        execute_plan(plan_path, run_dir)
    assert not run_dir.exists()


def test_protected_paths_existing_runs_and_input_collision(fixture_plan):
    plan_path, run_dir, _ = fixture_plan
    for forbidden in (plan_path.parent / "docs/results/run", plan_path.parent):
        with pytest.raises(BatchError, match="outputs"):
            execute_plan(plan_path, forbidden)
    execute_plan(plan_path, run_dir)
    with pytest.raises(FileExistsError):
        execute_plan(plan_path, run_dir)
    # An external root may not contain an input/source, either.
    with pytest.raises(BatchError):
        execute_plan(plan_path, plan_path.parent.parent)


def test_containing_git_repository_keeps_cache_and_docs_protected(fixture_plan):
    plan_path, _, _ = fixture_plan
    repository = plan_path.parent.parent
    (repository / ".git").mkdir()
    for relative in (".cache/project-checks/run", "docs/results/run", "src/run"):
        forbidden = repository / relative
        with pytest.raises(BatchError, match="outputs"):
            check_plan(plan_path, forbidden)
        assert not forbidden.exists()
    allowed = repository / "outputs/new-run"
    assert check_plan(plan_path, allowed)["executed"] is False
    assert not allowed.exists()


def test_timeout_and_missing_output_are_failures_with_logs(fixture_plan):
    plan_path, run_dir, plan = fixture_plan
    plan["jobs"][0]["argv"].append("--sleep")
    plan["jobs"][0]["timeout_seconds"] = 0.05
    _write(plan_path, plan)
    failed = execute_plan(plan_path, run_dir)["jobs"]["quality"]["attempts"][0]
    assert failed["status"] == "failed" and "TimeoutExpired" in failed["error"]
    assert (run_dir / failed["stderr"]).is_file()
    plan["jobs"][0]["argv"][-1] = "--missing"
    plan["jobs"][0].pop("timeout_seconds")
    _write(plan_path, plan)
    missing = execute_plan(plan_path, run_dir.with_name("run-002"))
    assert missing["jobs"]["quality"]["status"] == "failed"
    assert "Expected regular file" in missing["jobs"]["quality"]["attempts"][0]["error"]


def test_interrupted_record_retries_in_new_attempt(fixture_plan):
    plan_path, run_dir, _ = fixture_plan
    ledger = execute_plan(plan_path, run_dir)
    state = ledger["jobs"]["quality"]
    state["status"] = state["attempts"][0]["status"] = "running"
    state["attempts"][0]["outputs"] = {}
    _write(run_dir / "ledger.json", ledger)
    resumed = execute_plan(plan_path, run_dir, resume=True)
    attempts = resumed["jobs"]["quality"]["attempts"]
    assert attempts[0]["status"] == "interrupted"
    assert attempts[1]["status"] == "succeeded"
    assert (run_dir / "jobs/quality/attempt-0001/artifacts/report.txt").is_file()


def test_os_lock_blocks_competing_runner_and_releases(fixture_plan):
    plan_path, run_dir, _ = fixture_plan
    execute_plan(plan_path, run_dir)
    with _lock(run_dir), pytest.raises(BatchError, match="lock"):
        execute_plan(plan_path, run_dir, resume=True)
    assert execute_plan(plan_path, run_dir, resume=True)["jobs"]["quality"]["status"] == "succeeded"


def test_symlink_output_is_rejected(fixture_plan, tmp_path):
    plan_path, run_dir, _ = fixture_plan
    execute_plan(plan_path, run_dir)
    output = run_dir / "jobs/quality/attempt-0001/artifacts/report.txt"
    external = tmp_path / "external.txt"
    external.write_bytes(output.read_bytes())
    output.unlink()
    try:
        output.symlink_to(external)
    except OSError:
        pytest.skip("Host does not permit creating test symlinks")
    with pytest.raises(BatchError, match="Symlink"):
        execute_plan(plan_path, run_dir, resume=True)


@pytest.mark.parametrize(
    "argv", ["python worker.py", ["-c", "print(1)"], ["worker.py", "prefix={output:report}"]]
)
def test_shell_text_inline_code_and_embedded_placeholders_are_rejected(fixture_plan, argv):
    plan_path, _, plan = fixture_plan
    plan["jobs"][0]["argv"] = argv
    _write(plan_path, plan)
    with pytest.raises(BatchError):
        load_plan(plan_path)


def test_plan_command_is_non_destructive_and_needs_jobs(fixture_plan):
    plan_path, run_dir, _ = fixture_plan
    template = plan_path.with_name("template.json")
    argv = ["plan", "--project-root", str(plan_path.parent), "--output", str(template)]
    assert main(argv) == 0
    assert main(argv) == 2
    assert main(["check", "--plan", str(template), "--run-dir", str(run_dir)]) == 2
    assert not run_dir.exists()


def test_module_entry_is_hashed_automatically(fixture_plan):
    plan_path, run_dir, plan = fixture_plan
    package = plan_path.parent / "fixture_module"
    package.mkdir()
    (package / "__init__.py").write_text("")
    (package / "__main__.py").write_text(WORKER)
    plan["jobs"][0]["argv"] = ["-m", "fixture_module", "{input:frames}", "{output:report}"]
    _write(plan_path, plan)
    _, identity = load_plan(plan_path)
    assert str(package / "__main__.py") in identity["source_sha256"]
    assert execute_plan(plan_path, run_dir)["jobs"]["quality"]["status"] == "succeeded"


@pytest.mark.parametrize(
    "corruption", ["empty_outputs", "wrong_path", "wrong_fingerprint", "missing_job"]
)
def test_corrupted_ledger_cannot_claim_success(fixture_plan, corruption):
    plan_path, run_dir, _ = fixture_plan
    ledger = execute_plan(plan_path, run_dir)
    attempt = ledger["jobs"]["quality"]["attempts"][0]
    if corruption == "empty_outputs":
        attempt["outputs"] = {}
    elif corruption == "wrong_path":
        attempt["outputs"]["report"]["path"] = "manifest.json"
    elif corruption == "wrong_fingerprint":
        ledger["fingerprint"] = "incorrect"
    else:
        ledger["jobs"] = {}
    _write(run_dir / "ledger.json", ledger)
    with pytest.raises(BatchError):
        execute_plan(plan_path, run_dir, resume=True)
    assert not (run_dir / "jobs/quality/attempt-0002").exists()


class SimulatedProcessDeath(BaseException):
    """Bypass normal exception bookkeeping like abrupt process termination."""


@pytest.mark.parametrize("after_creation", [False, True])
def test_process_death_around_attempt_mkdir_is_resumable(fixture_plan, monkeypatch, after_creation):
    plan_path, run_dir, _ = fixture_plan
    original_mkdir = Path.mkdir

    def crash_around_mkdir(path, *args, **kwargs):
        if path == run_dir / "jobs/quality/attempt-0001":
            if after_creation:
                original_mkdir(path, *args, **kwargs)
            raise SimulatedProcessDeath
        return original_mkdir(path, *args, **kwargs)

    with monkeypatch.context() as patch:
        patch.setattr(Path, "mkdir", crash_around_mkdir)
        with pytest.raises(SimulatedProcessDeath):
            execute_plan(plan_path, run_dir)
    persisted = json.loads((run_dir / "ledger.json").read_text())
    assert persisted["jobs"]["quality"]["status"] == "running"
    assert len(persisted["jobs"]["quality"]["attempts"]) == 1
    resumed = execute_plan(plan_path, run_dir, resume=True)
    attempts = resumed["jobs"]["quality"]["attempts"]
    assert [attempt["status"] for attempt in attempts] == ["interrupted", "succeeded"]
    assert "attempt-0002" in attempts[-1]["outputs"]["report"]["path"]
    assert check_plan(plan_path, run_dir)["executed"] is False


def test_pending_job_preserves_orphan_directory_and_resumes(fixture_plan, monkeypatch):
    plan_path, run_dir, _ = fixture_plan
    original_save = batch._save_ledger
    orphan = run_dir / "jobs/quality/attempt-0001/artifacts/partial.txt"

    def crash_with_orphan(directory, ledger):
        original_save(directory, ledger)
        if ledger["jobs"]["quality"]["status"] == "pending":
            orphan.parent.mkdir(parents=True)
            orphan.write_bytes(b"preserve this unfinished artifact")
            raise SimulatedProcessDeath

    with monkeypatch.context() as patch:
        patch.setattr(batch, "_save_ledger", crash_with_orphan)
        with pytest.raises(SimulatedProcessDeath):
            execute_plan(plan_path, run_dir)
    resumed = execute_plan(plan_path, run_dir, resume=True)
    attempts = resumed["jobs"]["quality"]["attempts"]
    assert [attempt["status"] for attempt in attempts] == ["interrupted", "succeeded"]
    assert "Orphan" in attempts[0]["error"]
    assert orphan.read_bytes() == b"preserve this unfinished artifact"
    assert "attempt-0002" in attempts[-1]["outputs"]["report"]["path"]
    assert execute_plan(plan_path, run_dir, resume=True) == resumed


def test_manifest_only_initialization_can_resume(fixture_plan, monkeypatch):
    plan_path, run_dir, _ = fixture_plan
    original_save = batch._save_new

    def crash_after_manifest(path, value):
        original_save(path, value)
        if path == run_dir / "manifest.json":
            raise SimulatedProcessDeath

    with monkeypatch.context() as patch:
        patch.setattr(batch, "_save_new", crash_after_manifest)
        with pytest.raises(SimulatedProcessDeath):
            execute_plan(plan_path, run_dir)
    assert not (run_dir / "ledger.json").exists()
    resumed = execute_plan(plan_path, run_dir, resume=True)
    assert resumed["jobs"]["quality"]["status"] == "succeeded"
    assert len(resumed["jobs"]["quality"]["attempts"]) == 1


def test_optional_absent_inputs_are_frozen_and_new_file_blocks_reuse(fixture_plan):
    plan_path, run_dir, plan = fixture_plan
    plan["absent_inputs"] = ["optional/condensed_windows.json", "optional/scan.json"]
    _write(plan_path, plan)
    normalized, identity = load_plan(plan_path)
    missing = plan_path.parent / "optional/condensed_windows.json"
    assert str(missing) in normalized["absent_inputs"]
    assert identity["absent_input_state"][str(missing)] == "absent"
    completed = execute_plan(plan_path, run_dir)
    assert execute_plan(plan_path, run_dir, resume=True) == completed
    missing.parent.mkdir()
    missing.write_text("{}")
    for operation in (
        lambda: check_plan(plan_path, run_dir),
        lambda: execute_plan(plan_path, run_dir, resume=True),
        lambda: execute_plan(plan_path, run_dir.with_name("run-002")),
    ):
        with pytest.raises(BatchError, match="Expected absent input now exists"):
            operation()
    assert not (run_dir / "jobs/quality/attempt-0002").exists()


def test_absent_paths_cannot_belong_to_run_directory(fixture_plan):
    plan_path, run_dir, plan = fixture_plan
    plan["absent_inputs"] = [str(run_dir / "future.json")]
    _write(plan_path, plan)
    with pytest.raises(BatchError, match="absent-input"):
        execute_plan(plan_path, run_dir)
    assert not run_dir.exists()


def test_absent_list_change_is_part_of_identity_and_omission_is_compatible(fixture_plan):
    plan_path, run_dir, plan = fixture_plan
    normalized, old_identity = load_plan(plan_path)
    assert normalized["absent_inputs"] == []
    plan["absent_inputs"] = []
    _write(plan_path, plan)
    assert load_plan(plan_path)[1] == old_identity
    execute_plan(plan_path, run_dir)
    plan["absent_inputs"] = ["not-created.json"]
    _write(plan_path, plan)
    with pytest.raises(BatchError, match="changed"):
        execute_plan(plan_path, run_dir, resume=True)


@pytest.mark.parametrize("invalid", ["file.json", None, [42], [""]])
def test_absent_inputs_require_a_path_list(fixture_plan, invalid):
    plan_path, _, plan = fixture_plan
    plan["absent_inputs"] = invalid
    _write(plan_path, plan)
    with pytest.raises(BatchError, match="absent_inputs"):
        load_plan(plan_path)

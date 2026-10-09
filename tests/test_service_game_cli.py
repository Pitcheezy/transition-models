"""CLI boundary tests use synthetic exports only; no real API or model is involved."""

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/inspect_service_game.py"
MAX_INPUT_BYTES = 5 * 1024 * 1024


@pytest.fixture
def synthetic_payload():
    """Return invented service-game v2 data, not an actual API response."""
    return {
        "schema": "pitcheezy-service-game-v2",
        "source": {"kind": "archive"},
        "game": {
            "game_pk": 900001,
            "away_team": "Synthetic Away",
            "home_team": "Synthetic Home",
        },
        "feed": {"as_of": "2026-10-07T00:00:00Z", "ok": True, "stale_s": 0},
        "cutoff": None,
        "zone_bounds": {"bottom": 1.5, "top": 3.5},
        "pitches": [
            {
                "index": 7,
                "key": "900001:2:1",
                "pa_key": "900001:2",
                "at_bat_number": 2,
                "pitch_number": 1,
                "inning": 1,
                "half": "Top",
                "situation_before": {
                    "inning": 1,
                    "half": "Top",
                    "outs": 0,
                    "balls": 0,
                    "strikes": 0,
                    "home_score": 0,
                    "away_score": 0,
                    "bases": 0,
                    "runners": {"first": False, "second": False, "third": False},
                },
                "pitcher": {"id": 900002, "name": "Synthetic Pitcher", "hand": "R"},
                "batter": {"id": 900003, "name": "Synthetic Batter", "side": "L"},
                "rec": {
                    "status": "missing",
                    "reason": "Synthetic pending",
                    "candidates": [],
                    "provenance": "absent",
                    "recorded_at": None,
                    "policy": None,
                },
                "actual": None,
            }
        ],
        "pas": [],
        "current": None,
        "next": None,
    }


@pytest.fixture
def synthetic_input(tmp_path, synthetic_payload):
    path = tmp_path / "synthetic-service.json"
    path.write_text(json.dumps(synthetic_payload), encoding="utf-8")
    return path


def run_cli(tmp_path, *arguments, extra_env=None):
    """Run the actual entry point in a temporary directory with bytecode writes disabled."""
    env = {**os.environ, "PYTHONDONTWRITEBYTECODE": "1", "PYTHONIOENCODING": "utf-8"}
    env.update(extra_env or {})
    return subprocess.run(
        [sys.executable, str(SCRIPT), *map(str, arguments)],
        cwd=tmp_path,
        env=env,
        capture_output=True,
        text=True,
        encoding="utf-8",
        timeout=20,
        check=False,
    )


def assert_rejected(result, output=None, private_text=None):
    assert result.returncode != 0
    assert result.stdout == ""
    assert result.stderr.strip()
    assert "Traceback" not in result.stderr
    if private_text is not None:
        assert private_text not in result.stderr
    if output is not None:
        assert not output.exists()


def test_help_works_without_input(tmp_path):
    result = run_cli(tmp_path, "--help")
    assert result.returncode == 0
    assert "--source-kind" in result.stdout
    assert "provided_export" in result.stdout
    assert result.stderr == ""


def test_source_kind_must_be_explicit(tmp_path, synthetic_input):
    output = tmp_path / "audit.json"
    result = run_cli(tmp_path, "--input", synthetic_input, "--out", output)
    assert_rejected(result, output)
    assert "--source-kind" in result.stderr


def test_default_prints_only_compact_summary_and_original_hash(tmp_path, synthetic_input):
    before = set(tmp_path.iterdir())
    result = run_cli(tmp_path, "--input", synthetic_input, "--source-kind", "synthetic")
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert len(result.stdout.splitlines()) == 1
    summary = json.loads(result.stdout)
    assert set(summary) == {"schema", "source_sha256", "summary", "warnings"}
    assert summary["schema"] == "pitcheezy-service-review-v1"
    assert summary["source_sha256"] == hashlib.sha256(synthetic_input.read_bytes()).hexdigest()
    assert isinstance(summary["summary"], dict)
    assert isinstance(summary["warnings"], list)
    assert "Synthetic Pitcher" not in result.stdout
    assert str(synthetic_input) not in result.stdout
    assert set(tmp_path.iterdir()) == before


@pytest.mark.parametrize("source_kind", ["synthetic", "provided_export"])
def test_new_report_matches_normalizer_and_declared_source_kind(
    tmp_path, synthetic_input, source_kind
):
    # Both variants remain synthetic test fixtures; the flag describes claimed input provenance.
    from src.integration.service_game import normalize_service_game

    revision = "deadbee"  # Synthetic hash-shaped value, not a verified Git revision.
    output = tmp_path / f"{source_kind}-audit.json"
    result = run_cli(
        tmp_path,
        "--input",
        synthetic_input,
        "--source-kind",
        source_kind,
        "--source-revision",
        revision,
        "--out",
        output,
    )
    assert result.returncode == 0, result.stderr
    original = synthetic_input.read_bytes()
    expected = normalize_service_game(
        json.loads(original),
        input_kind=source_kind,
        source_sha256=hashlib.sha256(original).hexdigest(),
        reported_revision=revision,
    )
    assert json.loads(output.read_text(encoding="utf-8")) == expected
    assert json.loads(result.stdout)["summary"] == expected["summary"]
    assert str(synthetic_input) not in output.read_text(encoding="utf-8")


def test_utf8_bom_is_accepted_but_included_in_original_hash(tmp_path, synthetic_input):
    original = b"\xef\xbb\xbf" + synthetic_input.read_bytes()
    synthetic_input.write_bytes(original)
    result = run_cli(tmp_path, "--input", synthetic_input, "--source-kind", "synthetic")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["source_sha256"] == hashlib.sha256(original).hexdigest()


@pytest.mark.parametrize(
    "invalid",
    [
        b'{"secret":"PRIVATE_PAYLOAD", "bad":"\xff"}',
        b'{"secret":"PRIVATE_PAYLOAD", "secret":"duplicate"}',
        b'{"nested":{"secret":"PRIVATE_PAYLOAD", "secret":"duplicate"}}',
        b'{"secret":"PRIVATE_PAYLOAD", "bad":NaN}',
        b'{"secret":"PRIVATE_PAYLOAD", "bad":Infinity}',
        b'{"secret":"PRIVATE_PAYLOAD", "bad":-Infinity}',
        b'{"secret":"PRIVATE_PAYLOAD", "bad":1e999}',
        b'{"secret":"PRIVATE_PAYLOAD", "bad":-1e999}',
        b'{"secret":"PRIVATE_PAYLOAD"} {}',
        b'{"secret":"PRIVATE_PAYLOAD"',
        b'{"secret":"PRIVATE_PAYLOAD", "schema":"unexpected"}',
        b"[" * 2000 + b"0" + b"]" * 2000,
    ],
    ids=[
        "invalid_utf8",
        "duplicate_root_key",
        "duplicate_nested_key",
        "nan",
        "infinity",
        "negative_infinity",
        "overflowing_float",
        "negative_overflowing_float",
        "trailing_document",
        "truncated_json",
        "unsupported_schema",
        "excessive_depth",
    ],
)
def test_invalid_input_is_payload_free_and_does_not_create_output(tmp_path, invalid):
    source = tmp_path / "invalid.json"
    source.write_bytes(invalid)
    output = tmp_path / "audit.json"
    result = run_cli(tmp_path, "--input", source, "--source-kind", "synthetic", "--out", output)
    assert_rejected(result, output, "PRIVATE_PAYLOAD")


def test_oversized_input_is_rejected_before_parsing(tmp_path):
    source = tmp_path / "large.json"
    source.write_bytes(b" " * (MAX_INPUT_BYTES + 1))
    output = tmp_path / "audit.json"
    result = run_cli(tmp_path, "--input", source, "--source-kind", "synthetic", "--out", output)
    assert_rejected(result, output)
    assert "5 MiB" in result.stderr


def test_limit_sized_valid_json_is_accepted(tmp_path, synthetic_input):
    original = synthetic_input.read_bytes()
    original += b" " * (MAX_INPUT_BYTES - len(original))
    synthetic_input.write_bytes(original)
    result = run_cli(tmp_path, "--input", synthetic_input, "--source-kind", "synthetic")
    assert result.returncode == 0, result.stderr
    assert json.loads(result.stdout)["source_sha256"] == hashlib.sha256(original).hexdigest()


@pytest.mark.parametrize("input_kind", ["directory", "missing"])
def test_missing_or_nonregular_input_is_rejected(tmp_path, input_kind):
    source = tmp_path if input_kind == "directory" else tmp_path / "missing.json"
    output = tmp_path / "audit.json"
    result = run_cli(tmp_path, "--input", source, "--source-kind", "synthetic", "--out", output)
    assert_rejected(result, output)


@pytest.mark.skipif(not hasattr(os, "mkfifo"), reason="Named pipe fixture requires POSIX")
def test_named_pipe_is_rejected_without_waiting_for_a_writer(tmp_path):
    source = tmp_path / "pipe.json"
    os.mkfifo(source)
    result = run_cli(tmp_path, "--input", source, "--source-kind", "synthetic")
    assert_rejected(result)


def test_existing_output_is_preserved(tmp_path, synthetic_input):
    output = tmp_path / "audit.json"
    original = b"existing independent audit\n"
    output.write_bytes(original)
    result = run_cli(
        tmp_path, "--input", synthetic_input, "--source-kind", "synthetic", "--out", output
    )
    assert_rejected(result)
    assert output.read_bytes() == original


def test_input_cannot_be_used_as_output(tmp_path, synthetic_input):
    original = synthetic_input.read_bytes()
    result = run_cli(
        tmp_path,
        "--input",
        synthetic_input,
        "--source-kind",
        "synthetic",
        "--out",
        synthetic_input,
    )
    assert_rejected(result)
    assert synthetic_input.read_bytes() == original


def test_output_does_not_create_parent_directory(tmp_path, synthetic_input):
    output = tmp_path / "not-created" / "audit.json"
    result = run_cli(
        tmp_path, "--input", synthetic_input, "--source-kind", "synthetic", "--out", output
    )
    assert_rejected(result, output)
    assert not output.parent.exists()


def test_non_json_output_is_rejected(tmp_path, synthetic_input):
    output = tmp_path / "protected.py"
    result = run_cli(
        tmp_path, "--input", synthetic_input, "--source-kind", "synthetic", "--out", output
    )
    assert_rejected(result, output)


def test_dangling_output_symlink_is_not_followed(tmp_path, synthetic_input):
    output = tmp_path / "audit.json"
    target = tmp_path / "must-not-exist.json"
    try:
        output.symlink_to(target)
    except (OSError, NotImplementedError):
        pytest.skip("Host does not permit unprivileged symlinks")
    result = run_cli(
        tmp_path, "--input", synthetic_input, "--source-kind", "synthetic", "--out", output
    )
    assert_rejected(result)
    assert output.is_symlink()
    assert not target.exists()


@pytest.mark.parametrize(
    "remote",
    ["https://example.invalid/private.json", "//example.invalid/share/private.json", "NUL"],
)
def test_nonlocal_or_device_input_path_is_rejected(tmp_path, remote):
    result = run_cli(tmp_path, "--input", remote, "--source-kind", "synthetic")
    assert_rejected(result)
    assert "example.invalid" not in result.stderr


def test_audit_does_not_access_network_models_processes_or_other_outputs(tmp_path, synthetic_input):
    # Allow src's Windows pyarrow import guard; block actual network/process activity and models.
    hook_directory = tmp_path / "audit-hook"
    hook_directory.mkdir()
    output = tmp_path / "audit.json"
    hook = hook_directory / "sitecustomize.py"
    hook.write_text(
        "import os, sys\n"
        f"allowed = os.path.normcase(os.path.abspath({str(output)!r}))\n"
        "def audit(event, args):\n"
        "    if event.startswith('socket.') or event in "
        "{'subprocess.Popen', 'os.system', 'os.exec', 'os.posix_spawn'}:\n"
        "        raise RuntimeError('Network or process activity is prohibited')\n"
        "    if event == 'import' and args[0].split('.')[0] in "
        "{'torch', 'tensorflow', 'transformers', 'onnxruntime', 'cv2'}:\n"
        "        raise RuntimeError('Model import is prohibited')\n"
        "    if event == 'open':\n"
        "        path, mode, flags = args\n"
        "        writing = isinstance(mode, str) and any(c in mode for c in 'wax+')\n"
        "        writing = writing or bool(flags & (os.O_WRONLY | os.O_RDWR))\n"
        "        if writing and (not isinstance(path, str) or "
        "os.path.normcase(os.path.abspath(path)) != allowed):\n"
        "            raise RuntimeError('Unrequested output is prohibited')\n"
        "sys.addaudithook(audit)\n",
        encoding="utf-8",
    )
    before = set(tmp_path.rglob("*"))
    result = run_cli(
        tmp_path,
        "--input",
        synthetic_input,
        "--source-kind",
        "synthetic",
        "--out",
        output,
        extra_env={"PYTHONPATH": str(hook_directory)},
    )
    assert result.returncode == 0, result.stderr
    assert result.stderr == ""
    assert set(tmp_path.rglob("*")) == before | {output}


def test_supplied_contract_profile_is_explicit_and_report_matches_normalizer(
    tmp_path, synthetic_input, synthetic_payload
):
    from src.integration.service_game import EXPORT_PROFILE, normalize_service_game

    synthetic_payload["game"]["date_kst"] = "2026-10-09"
    synthetic_payload["cutoff"] = {"index": 7, "pitch_key": "900001:2:1"}
    synthetic_input.write_text(json.dumps(synthetic_payload), encoding="utf-8")
    default_result = run_cli(tmp_path, "--input", synthetic_input, "--source-kind", "synthetic")
    assert_rejected(default_result)
    output = tmp_path / "export-audit.json"
    result = run_cli(
        tmp_path,
        "--input",
        synthetic_input,
        "--source-kind",
        "synthetic",
        "--profile",
        EXPORT_PROFILE,
        "--out",
        output,
    )
    assert result.returncode == 0, result.stderr
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report == normalize_service_game(
        synthetic_payload,
        input_kind="synthetic",
        source_sha256=hashlib.sha256(synthetic_input.read_bytes()).hexdigest(),
        profile=EXPORT_PROFILE,
    )
    assert report["profile"] == EXPORT_PROFILE
    assert report["game"]["kst_date"] == "2026-10-09"
    assert json.loads(result.stdout)["summary"] == report["summary"]
    assert "Synthetic Pitcher" not in result.stdout


def test_unknown_profile_is_rejected_without_creating_a_report(tmp_path, synthetic_input):
    output = tmp_path / "invalid-profile.json"
    result = run_cli(
        tmp_path,
        "--input",
        synthetic_input,
        "--source-kind",
        "synthetic",
        "--profile",
        "unrecognized",
        "--out",
        output,
    )
    assert_rejected(result, output)

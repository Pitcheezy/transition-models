"""Synthetic offline evidence only: no Cloudflare, network or authentication operations."""

import json
import subprocess
import sys
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "correlate_exhibit_stage5_logs.py"
PIN = "11111111-1111-4111-8111-111111111111"
OTHER_PIN = "22222222-2222-4222-8222-222222222222"
SHA = "ab" * 32
BASE = datetime(2026, 11, 2, 0, 0, 0, tzinfo=UTC)
HOST = "https://private.invalid"


def iso(value):
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def client(n, pin=PIN):
    method = {1: "HEAD", 2: "POST", 3: "DELETE"}.get(n, "GET")
    started = BASE + timedelta(milliseconds=100 * n)
    return {"sequence": n, "method": method, "path": f"/v1/item-{n % 5}.json",
            "expected_deployment_version": pin, "started_utc": iso(started),
            "finished_utc": iso(started + timedelta(milliseconds=50)),
            "status": 404 if n % 7 == 0 else 200, "ray": f"{'ab' * 12}{n:08x}"}


def build_round(tmp_path, n=24, pin=PIN, cycle_pin=None, result_passed=True):
    private = tmp_path / "private"
    round_dir = private / "round"
    rows = [client(number, pin) for number in range(1, n + 1)]
    for row in rows:
        started = {key: row[key] for key in ("sequence", "method", "path",
                                             "expected_deployment_version", "started_utc")}
        write(round_dir / "cutover" / "requests" / f"request-{row['sequence']:03d}.started.private.json",
              {**started, "outcome": "pending"})
        completed = {**started, "outcome": "response_headers_received",
                     "exchange": {"started_utc": row["started_utc"], "headers_received_utc": row["finished_utc"],
                                  "status": row["status"], "ray": row["ray"]}}
        write(round_dir / "cutover" / "requests" / f"request-{row['sequence']:03d}.completed.private.json",
              completed)
    write(round_dir / "cycle.private.json", {"cutover_input_sha256": SHA, "cutover_version_pin": cycle_pin or pin,
                                              "run_id": "synthetic-run", "schema": "synthetic-cycle"})
    write(round_dir / "cutover" / "result.private.json",
          {"failure": None, "input_sha256": SHA, "passed": result_passed, "phase": "cutover",
           "real_phone": False, "request_limit": 29, "result": "passed" if result_passed else "failed",
           "route_changed_by_tool": False, "schema": "synthetic-result", "server_logs": "not_received",
           "service_requests": 24, "version_basis": "management", "version_pin": pin})
    return private, round_dir, rows


def server_event(row, ray=None, version=None, timestamp=None, request_id=None):
    ray = ray or row["ray"]
    return {"timestamp": timestamp or iso(datetime.fromisoformat(row["started_utc"]) + timedelta(milliseconds=25)),
            "$workers": {"event": {"request": {"url": HOST + row["path"], "method": row["method"],
                                               "headers": {"cf-ray": f"{ray}-ICN", "cookie": "PRIVATE-COOKIE"}},
                                   "response": {"status": row["status"]}},
                         "scriptVersion": {"id": version or row["expected_deployment_version"]},
                         "outcome": "ok", "truncated": False},
            "$metadata": {"rayId": ray, "requestId": request_id or f"provider-{ray}"},
            "secret": "PRIVATE-TOKEN"}


def build_export(rows, extra=0):
    events = [server_event(row) for row in rows]
    for n in range(1, extra + 1):
        phone = {**rows[0], "method": "GET", "path": "/?game=849843&PRIVATE-QUERY=1", "status": 200}
        events.append(server_event(phone, ray=f"{'cd' * 12}{n:08x}"))
    return events


def run(*args):
    result = subprocess.run([sys.executable, "-I", "-B", str(SCRIPT), *map(str, args)],
                            capture_output=True, text=True, timeout=60, check=False)
    return result.returncode, json.loads(result.stdout), result.stderr


def assert_sanitized(text, tmp_path, rows):
    assert "private.invalid" not in text and "PRIVATE" not in text and "provider-" not in text
    assert str(tmp_path) not in text and "game=" not in text
    assert all(row["ray"] not in text for row in rows)


def test_ledger_only_precheck_is_sanitized(tmp_path):
    private, round_dir, rows = build_round(tmp_path)
    output = tmp_path / "precheck.json"
    code, summary, stderr = run("--private-root", private, "--round", round_dir, "--ledger-only", "--output", output)
    assert code == 0 and stderr == "" and summary["passed"] is True
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["schema"] == "pitcheezy-stage5-ledger-precheck-v1"
    assert report["server_logs"] == "not_received" and "requests" not in report
    assert report["ledger"] == summary["ledger"]
    assert report["ledger"]["client_requests"] == 24 and report["ledger"]["version_pin"] == PIN
    assert report["ledger"]["method_counts"] == {"DELETE": 1, "GET": 21, "HEAD": 1, "POST": 1}
    assert report["ledger"]["status_counts"] == {"200": 21, "404": 3}
    assert report["ledger"]["distinct_paths"] == 5
    assert report["ledger"]["window_utc"] == {"first_started": iso(BASE + timedelta(milliseconds=100)),
                                              "last_finished": iso(BASE + timedelta(milliseconds=2450))}
    assert len(report["source_integrity"]) == 50
    assert_sanitized(output.read_text(encoding="utf-8"), tmp_path, rows)


def test_full_run_matches_24_and_counts_phone_extras_without_reassignment(tmp_path):
    private, round_dir, rows = build_round(tmp_path)
    export = write(private / "export.json", build_export(rows, extra=2))
    original = export.read_bytes()
    output = tmp_path / "full.json"
    code, summary, _ = run("--private-root", private, "--round", round_dir, "--logs", export, "--output", output)
    assert code == 0 and summary["passed"] is True
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["schema"] == "pitcheezy-stage5-server-log-correlation-v1"
    assert report["counts"]["client_results"] == {"matched": 24}
    assert report["counts"]["server_http_events"] == 26
    assert report["extra_server_events_not_reassigned"] == 2
    assert report["counts"]["server_unmatched_events"] == 2
    assert report["ledger"]["client_requests"] == 24
    assert "extra_events_such_as_user_phone_requests_are_counted_not_matched" in report["limits"]
    assert "management_version_pin_confirmed_only_per_matched_event" in report["limits"]
    assert export.read_bytes() == original
    assert_sanitized(output.read_text(encoding="utf-8"), tmp_path, rows)


def test_ledger_with_23_journals_is_rejected(tmp_path):
    private, round_dir, _ = build_round(tmp_path, n=23)
    code, summary, _ = run("--private-root", private, "--round", round_dir, "--ledger-only",
                           "--output", tmp_path / "out.json")
    assert code == 2 and summary == {"passed": False, "error": "stage5_ledger_count_invalid"}
    assert not (tmp_path / "out.json").exists()


def test_cycle_pin_conflict_is_rejected(tmp_path):
    private, round_dir, _ = build_round(tmp_path, cycle_pin=OTHER_PIN)
    code, summary, _ = run("--private-root", private, "--round", round_dir, "--ledger-only",
                           "--output", tmp_path / "out.json")
    assert code == 2 and summary == {"passed": False, "error": "stage5_version_pin_conflict"}


def test_result_not_passed_is_rejected(tmp_path):
    private, round_dir, _ = build_round(tmp_path, result_passed=False)
    code, summary, _ = run("--private-root", private, "--round", round_dir, "--ledger-only",
                           "--output", tmp_path / "out.json")
    assert code == 2 and summary == {"passed": False, "error": "stage5_result_not_passed"}


def test_existing_output_is_never_overwritten(tmp_path):
    private, round_dir, _ = build_round(tmp_path)
    output = write(tmp_path / "out.json", {"keep": True})
    code, summary, _ = run("--private-root", private, "--round", round_dir, "--ledger-only", "--output", output)
    assert code == 2 and summary == {"passed": False, "error": "output_exists_do_not_overwrite"}
    assert json.loads(output.read_text(encoding="utf-8")) == {"keep": True}


def test_logs_outside_private_root_are_rejected(tmp_path):
    private, round_dir, rows = build_round(tmp_path)
    export = write(tmp_path / "outside" / "export.json", build_export(rows))
    code, summary, _ = run("--private-root", private, "--round", round_dir, "--logs", export,
                           "--output", tmp_path / "out.json")
    assert code == 2 and summary == {"passed": False, "error": "private_input_outside_root"}
    assert str(tmp_path) not in json.dumps(summary)


def test_server_version_mismatch_fails_only_that_request(tmp_path):
    private, round_dir, rows = build_round(tmp_path)
    events = build_export(rows)
    events[4] = server_event(rows[4], version=OTHER_PIN)
    export = write(private / "export.json", events)
    output = tmp_path / "out.json"
    code, summary, _ = run("--private-root", private, "--round", round_dir, "--logs", export, "--output", output)
    assert code == 1 and summary["passed"] is False
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["counts"]["client_results"] == {"matched": 23, "mismatch": 1}
    row = report["requests"][4]
    assert row["request"] == "stage5-cutover-005" and row["result"] == "mismatch"
    assert row["problems"] == ["version"] and row["server_version"] == OTHER_PIN


def test_ledger_only_refuses_logs(tmp_path):
    private, round_dir, rows = build_round(tmp_path)
    export = write(private / "export.json", build_export(rows))
    code, summary, _ = run("--private-root", private, "--round", round_dir, "--ledger-only", "--logs", export,
                           "--output", tmp_path / "out.json")
    assert code == 2 and summary == {"passed": False, "error": "ledger_only_takes_no_logs"}


def test_full_mode_requires_export(tmp_path):
    private, round_dir, _ = build_round(tmp_path)
    code, summary, _ = run("--private-root", private, "--round", round_dir, "--output", tmp_path / "out.json")
    assert code == 2 and summary == {"passed": False, "error": "server_export_required"}


def test_missing_server_event_is_not_filled_by_time_or_path(tmp_path):
    private, round_dir, rows = build_round(tmp_path)
    events = build_export(rows)
    lookalike = server_event(rows[7], ray=f"{'ef' * 12}{7:08x}")  # same method/path/time, other Ray
    events[7] = lookalike
    export = write(private / "export.json", events)
    output = tmp_path / "out.json"
    code, summary, _ = run("--private-root", private, "--round", round_dir, "--logs", export, "--output", output)
    assert code == 1 and summary["passed"] is False
    report = json.loads(output.read_text(encoding="utf-8"))
    assert report["requests"][7]["result"] == "missing_server_event"
    assert report["counts"]["client_results"] == {"matched": 23, "missing_server_event": 1}
    assert report["extra_server_events_not_reassigned"] == 1


@pytest.mark.parametrize("mode", [("--ledger-only",), ("--logs", "export.json")])
def test_round_outside_private_root_is_rejected(tmp_path, mode):
    private, round_dir, rows = build_round(tmp_path)
    other_root = tmp_path / "other-root"
    other_root.mkdir()
    write(other_root / "export.json", build_export(rows))
    args = [str(other_root / value) if value.endswith(".json") else value for value in mode]
    code, summary, _ = run("--private-root", other_root, "--round", round_dir, *args, "--output", tmp_path / "out.json")
    assert code == 2 and summary == {"passed": False, "error": "private_input_outside_root"}

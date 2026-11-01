"""Synthetic offline evidence only: no Cloudflare or authentication operations."""

import importlib.util
import json
import subprocess
import sys
from pathlib import Path

import pytest

FILE = Path(__file__).parents[1] / "scripts" / "correlate_exhibit_stage34_logs.py"
SPEC = importlib.util.spec_from_file_location("exhibit_stage34_logs", FILE)
logs = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = logs
SPEC.loader.exec_module(logs)

VERSION_ON = "11111111-1111-4111-8111-111111111111"
VERSION_OFF = "22222222-2222-4222-8222-222222222222"
VERSION_FINAL = "33333333-3333-4333-8333-333333333333"
START = "2026-11-02T00:00:00.000Z"
MID = "2026-11-02T00:00:00.500Z"
END = "2026-11-02T00:00:01.000Z"


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


def client(number=1, path="/v1/health.json", status=200, version=VERSION_ON, method="GET"):
    return {"sequence": number, "method": method, "path": path,
            "started_utc": START, "finished_utc": END, "status": status,
            "ray": f"{number:016x}-ICN", "expected_deployment_version": version,
            "outcome": "response_headers_received"}


def server(row, **changes):
    value = {"timestamp": MID,
             "$workers": {"event": {"request": {"url": "https://private-host.invalid" + row["path"],
                                                  "method": row["method"],
                                                  "headers": {"cf-ray": row["ray"], "cookie": "PRIVATE-COOKIE"}},
                                      "response": {"status": row["status"]}},
                          "scriptVersion": {"id": row["expected_deployment_version"]},
                          "outcome": "ok", "truncated": False},
             "$metadata": {"rayId": row["ray"].split("-")[0], "requestId": f"provider-{row['sequence']}"},
             "secret": "PRIVATE-TOKEN", "body": "PRIVATE-BODY"}
    for field, new_value in changes.items():
        obj = value
        parts = field.split("/")
        for part in parts[:-1]:
            obj = obj[part]
        obj[parts[-1]] = new_value
    return value


def normal_request(row=None):
    return logs.request("stage4-read-001", row or client())


def test_exact_ray_match_redacts_all_unapproved_fields():
    row = client(path="/?game=849843&PRIVATE-QUERY=PRIVATE-VALUE")
    report = logs.correlate([normal_request(row)], [server(row)])
    assert report["passed"]
    assert report["requests"][0]["server_version"] == VERSION_ON
    serialized = json.dumps(report)
    for forbidden in ("private-host", "PRIVATE", "provider-", row["ray"], "game=", "/?", "Cookie"):
        assert forbidden not in serialized
    assert report["requests"][0]["version_expectation_source"] == "management_pin_not_server_evidence"


@pytest.mark.parametrize("field,value,check", [
    ("$workers/event/request/method", "HEAD", "method"),
    ("$workers/event/request/url", "https://private.invalid/v1/other.json", "path_and_query"),
    ("$workers/event/response/status", 404, "status"),
    ("$workers/scriptVersion/id", VERSION_OFF, "version"),
    ("timestamp", "2026-11-02T00:00:01.001Z", "utc_within_client_interval"),
    ("$metadata/rayId", "0000000000000099", "ray_fields_agree"),
    ("$workers/outcome", "exception", "outcome_ok"),
    ("$workers/truncated", True, "not_truncated"),
])
def test_concrete_mismatches_are_not_reassigned(field, value, check):
    row = client()
    report = logs.correlate([normal_request(row)], [server(row, **{field: value})])
    assert not report["passed"]
    assert report["counts"]["client_results"] == {"mismatch": 1}
    assert report["requests"][0]["problems"] == [check]


def test_missing_ray_never_falls_back_to_identical_method_path_and_time():
    row = client()
    other = client(number=2)
    report = logs.correlate([normal_request(row)], [server(other)])
    assert report["counts"]["client_results"] == {"missing_server_event": 1}
    row["ray"] = None
    report = logs.correlate([normal_request(row)], [server(other)])
    assert report["counts"]["client_results"] == {"missing_client_ray": 1}


def test_duplicate_server_or_client_ray_is_ambiguous():
    row = client()
    report = logs.correlate([normal_request(row)], [server(row), server(row)])
    assert report["counts"]["client_results"] == {"duplicate_server_ray": 1}
    assert report["counts"]["duplicate_server_ray_groups"] == 1
    second = logs.request("stage4-notice-001", row)
    report = logs.correlate([normal_request(row), second], [server(row)])
    assert report["counts"]["client_results"] == {"duplicate_client_ray": 2}
    assert not report["passed"]


def test_provider_request_id_reuse_is_reported_without_exposure():
    first, second = client(), client(2)
    events = [server(first), server(second, **{"$metadata/requestId": "provider-1"})]
    report = logs.correlate([normal_request(first), logs.request("stage4-read-002", second)], events)
    assert not report["passed"]
    assert report["counts"]["duplicate_provider_request_id_groups"] == 1
    assert all(r["problems"] == ["unique_provider_request_id"] for r in report["requests"])


def test_explicit_tolerance_only_no_clock_reassignment():
    row = client()
    events = [server(row, timestamp="2026-11-02T00:00:01.001Z")]
    assert not logs.correlate([normal_request(row)], events)["passed"]
    report = logs.correlate([normal_request(row)], events, tolerance_ms=1)
    assert report["passed"] and report["timestamp_tolerance_ms"] == 1
    with pytest.raises(logs.InputError, match="timestamp_tolerance_invalid"):
        logs.correlate([normal_request(row)], events, tolerance_ms=-1)


def test_nonhttp_extra_and_malformed_events_are_distinct():
    row = client()
    events = [server(row), {"$workers": {"event": {"cron": "17 3 * * *"}}}, server(client(2))]
    report = logs.correlate([normal_request(row)], events)
    assert report["passed"]
    assert report["counts"]["server_nonhttp_excluded"] == 1
    assert report["counts"]["server_unmatched_events"] == 1
    report = logs.correlate([normal_request(row)], events + [{"arbitrary": "PRIVATE-DATA"}])
    assert not report["passed"] and report["counts"]["server_malformed_records"] == 1
    assert "PRIVATE-DATA" not in json.dumps(report)


def stage3_fixture(tmp_path):
    root = tmp_path / "stage3"
    expected = []
    for n in range(1, 13):
        row = client(n, method="HEAD" if n <= 6 else "PUT", status=404 if n <= 6 else 200)
        pending = {key: row[key] for key in ("sequence", "method", "path", "started_utc")}
        complete = {key: row[key] for key in ("sequence", "method", "path", "started_utc", "finished_utc",
                                            "expected_deployment_version")}
        complete["exchange"] = {"started_utc": START, "headers_received_utc": END,
                                "status": row["status"], "ray": row["ray"]}
        complete["receipt"] = {"authorization": "PRIVATE-IGNORED"}
        write(root / "upload-run" / f"request-{n:02d}.pending.private.json", pending)
        write(root / "upload-run" / f"request-{n:02d}.completed.private.json", complete)
        expected.append(server({**row, "path": "/_publish" + row["path"]}))
    closing = client(13, path="/_publish/v1/health.json", method="HEAD", status=503, version=VERSION_OFF)
    write(root / "closing-head.private.json", {k: v for k, v in closing.items() if k not in {"sequence", "expected_deployment_version"}})
    expected.append(server(closing))
    receipt = write(tmp_path / "summary.json", {"service_requests": 13, "upload_on_version": VERSION_ON,
                                               "upload_off_version": VERSION_OFF, "final_version": VERSION_FINAL})
    return root, receipt, expected


def test_stage3_real_publish_path_and_per_request_versions(tmp_path):
    root, receipt, events = stage3_fixture(tmp_path)
    sources = logs.Sources()
    rows = logs.load_stage3(root, receipt, sources)
    assert len(rows) == 13
    assert {r.version for r in rows[:12]} == {VERSION_ON}
    assert rows[-1].version == VERSION_OFF
    assert all(r.path == "/_publish/v1/health.json" for r in rows)
    report = logs.correlate(rows, events, source_receipts=sources.receipts)
    assert report["passed"]
    assert len(report["source_integrity"]) == 26
    assert all(set(item) == {"input", "bytes", "sha256"} for item in report["source_integrity"])
    assert VERSION_FINAL not in json.dumps(report)


def stage4_fixture(tmp_path):
    root, expected = tmp_path / "stage4", []
    for n, phase in enumerate(("read", "browser", "notice"), 1):
        row = client(n, path="/?game=849843" if phase == "browser" else "/_notice/v1/state" if phase == "notice" else "/v1/health.json")
        if phase == "browser":
            begin = {"number": 1, "method": row["method"], "path": row["path"], "started_at": START,
                     "version_pin": VERSION_ON, "state": "started"}
            complete = {**begin, "state": "completed", "finished_at": END, "status": 304,
                        "cf_ray": row["ray"], "failure_code": "net::ERR_ABORTED",
                        "completion_basis": "bodyless_304_headers_before_client_abort"}
            write(root / phase / "request-001.headers.private.json", {"number": 1, "response_headers_at": END,
                                                                       "response_header_status": 304, "response_header_cf_ray": row["ray"]})
            write(root / phase / "synthetic-001.private.json", {"remote_request": False,
                                                               "evidence_kind": "browser_intercepted_synthetic_response",
                                                               "path": "/v1/health.json", "status": 500})
            row["status"] = 304
        else:
            begin = {**row, "sequence": 1, "finished_utc": None, "status": None, "ray": None, "outcome": "pending"}
            complete = {**row, "sequence": 1}
        write(root / phase / "request-001.started.private.json", begin)
        write(root / phase / "request-001.completed.private.json", complete)
        expected.append(server(row))
    return root, expected


def test_stage4_all_adapters_304_and_synthetic_separation(tmp_path):
    root, events = stage4_fixture(tmp_path)
    sources = logs.Sources()
    rows, synthetic = logs.load_stage4(root, sources)
    report = logs.correlate(rows, events, synthetic_count=synthetic, source_receipts=sources.receipts)
    assert report["passed"]
    assert len(rows) == 3 and synthetic == 1
    assert report["counts"]["synthetic_nonremote_excluded"] == 1
    assert rows[1].status == 304
    assert len({r.key for r in rows}) == 3


def test_missing_completion_never_becomes_success_from_management_pin(tmp_path):
    root, events = stage4_fixture(tmp_path)
    (root / "read" / "request-001.completed.private.json").unlink()
    rows, _ = logs.load_stage4(root, logs.Sources())
    report = logs.correlate(rows, events)
    assert not report["passed"]
    assert report["counts"]["client_results"] == {"incomplete_client": 1, "matched": 2}
    assert report["requests"][0]["server_version"] is None


def test_browser_abort_200_remains_incomplete_and_304_requires_header_evidence(tmp_path):
    root, events = stage4_fixture(tmp_path)
    file = root / "browser" / "request-001.completed.private.json"
    completed = json.loads(file.read_text())
    changed = {**completed, "state": "transport_failed", "status": 200}
    changed.pop("completion_basis")
    write(file, changed)
    rows, _ = logs.load_stage4(root, logs.Sources())
    assert logs.correlate(rows, events)["counts"]["client_results"] == {"incomplete_client": 1, "matched": 2}
    write(file, completed)
    (root / "browser" / "request-001.headers.private.json").unlink()
    with pytest.raises(logs.InputError, match="bodyless_304_header_evidence_missing"):
        logs.load_stage4(root, logs.Sources())


def test_conflicting_started_and_completed_identity_rejected(tmp_path):
    root, _ = stage4_fixture(tmp_path)
    file = root / "read" / "request-001.completed.private.json"
    changed = json.loads(file.read_text())
    changed["path"] = "/v1/other.json"
    write(file, changed)
    with pytest.raises(logs.InputError, match="client_identity_conflict"):
        logs.load_stage4(root, logs.Sources())


def test_cli_writes_only_sanitized_receipt_and_never_overwrites_inputs(tmp_path, capsys):
    root, events = stage4_fixture(tmp_path)
    export = write(tmp_path / "private-export.json", events)
    original = export.read_bytes()
    output = tmp_path / "sanitized.json"
    argv = ["--private-root", str(tmp_path), "--logs", str(export), "--stage4", str(root), "--output", str(output)]
    assert logs.main(argv) == 0
    assert export.read_bytes() == original
    assert "PRIVATE" not in output.read_text() and str(tmp_path) not in output.read_text()
    first = output.read_bytes()
    assert logs.main(argv) == 2
    assert output.read_bytes() == first
    assert "output_exists_do_not_overwrite" in capsys.readouterr().out


def test_duplicate_json_and_naive_times_are_rejected(tmp_path):
    file = tmp_path / "bad.json"
    file.write_text('{"field":1,"field":2}', encoding="utf-8")
    with pytest.raises(logs.InputError, match="duplicate_json_key"):
        logs.Sources().read(file, "synthetic-input")
    with pytest.raises(logs.InputError, match="timestamp_timezone_required"):
        logs.stamp("2026-11-02T00:00:00")


@pytest.mark.parametrize("invalid_row", [[], "PRIVATE-ROW-CONTENT", None])
@pytest.mark.parametrize("stage", [3, 4])
def test_cli_malformed_record_shape_has_safe_stdout_no_stderr_and_preserves_inputs(tmp_path, stage, invalid_row):
    if stage == 3:
        root, receipt, events = stage3_fixture(tmp_path)
        write(root / "closing-head.private.json", invalid_row)
        arguments = ["--stage3", str(root), "--stage3-receipt", str(receipt)]
        expected_error = "stage3_closing_record_invalid"
    else:
        root, events = stage4_fixture(tmp_path)
        write(root / "browser" / "synthetic-001.private.json", invalid_row)
        arguments = ["--stage4", str(root)]
        expected_error = "synthetic_record_invalid"
    export = write(tmp_path / "private-export.json", events)
    originals = {file: file.read_bytes() for file in tmp_path.rglob("*.json")}
    output = tmp_path / "sanitized.json"
    result = subprocess.run(
        [sys.executable, "-B", str(FILE), "--private-root", str(tmp_path), "--logs", str(export),
         *arguments, "--output", str(output)],
        capture_output=True, text=True, timeout=10, check=False,
    )
    assert result.returncode == 2
    assert json.loads(result.stdout) == {"passed": False, "error": expected_error}
    assert result.stderr == ""
    assert str(tmp_path) not in result.stdout and "PRIVATE" not in result.stdout
    assert not output.exists()
    assert all(file.read_bytes() == original for file, original in originals.items())


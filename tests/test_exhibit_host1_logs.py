"""Synthetic offline evidence only: no Cloudflare, network or authentication operations."""

import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from datetime import UTC, datetime, timedelta
from pathlib import Path

import pytest

SCRIPT = Path(__file__).parents[1] / "scripts" / "summarize_exhibit_host1_logs.py"
SPEC = importlib.util.spec_from_file_location("exhibit_host1_logs", SCRIPT)
tool = importlib.util.module_from_spec(SPEC)
sys.modules[SPEC.name] = tool
SPEC.loader.exec_module(tool)

HOST = "https://private.invalid"
VERSIONS = {prefix: f"{prefix}-0000-4000-8000-000000000000"
            for prefix in ("46cf3edc", "dbe8837c", "d4d707d7", "42e265fd", "feed4fc1", "6d652d4b")}
UNDOCUMENTED_VERSION = "0badc0de-0000-4000-8000-000000000000"
DATA_PATHS = [f"/v1/game/{n}.json" for n in range(849823, 849843)] + ["/v1/setup/849843.json", "/v1/dates.json"]
PUBLISH_PATHS = ["/_publish" + path for path in DATA_PATHS] + ["/_publish/v1/manifest.json"]


def iso(value):
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value), encoding="utf-8")
    return path


class Builder:
    """Writes a synthetic dashboard export; every record carries private-looking fields."""

    def __init__(self):
        self.events, self.clock, self.serial = [], datetime(2026, 11, 1, 2, 39, 43, tzinfo=UTC), 0

    def at(self, stamp):
        self.clock = datetime.fromisoformat(stamp.replace("Z", "+00:00"))
        return self

    def event(self, version, method, path, status, outcome="ok", truncated=False, ray=None, request_id=None):
        self.serial += 1
        self.clock += timedelta(milliseconds=137)
        ray = ray or f"{'ab' * 8}{self.serial:016x}"
        record = {"timestamp": iso(self.clock), "dataset": "private-dataset", "source": "private-source",
                  "$workers": {"event": {"request": {"url": HOST + path, "method": method,
                                                     "headers": {"cf-ray": f"{ray}-ICN", "cookie": "PRIVATE-COOKIE",
                                                                 "cf-connecting-ip": "203.0.113.77",
                                                                 "host": "private.invalid"},
                                                     "cf": {"colo": "PRIVATE-COLO", "asn": 64496}},
                                         "response": {"status": status}},
                               "scriptVersion": {"id": VERSIONS.get(version, version)}, "scriptName": "private-worker",
                               "outcome": outcome, "truncated": truncated},
                  "$metadata": {"rayId": ray, "requestId": request_id or f"provider-{self.serial:08d}",
                                "account": "PRIVATE-ACCOUNT"}}
        self.events.append(record)
        return record

    def verifier_run(self, version):
        self.event(version, "POST", "/_access/v1/session", 200)
        self.event(version, "GET", "/v1/manifest.json", 200)
        self.event(version, "GET", "/v1/manifest.json", 200)
        self.event(version, "HEAD", "/v1/manifest.json", 200)
        for path in DATA_PATHS:
            self.event(version, "GET", path, 200)
        self.event(version, "GET", "/v1/health.json", 200)
        self.event(version, "GET", "/v1/game/999999.json", 404)
        self.event(version, "GET", "/v1/games/2026-10-01.json", 404)
        self.event(version, "GET", "/favicon.svg", 200)
        self.event(version, "GET", "/assets/app.js", 200)
        self.event(version, "GET", "/assets/app.css", 200)
        self.event(version, "GET", "/index.html", 307)
        self.event(version, "GET", "/", 200)
        self.event(version, "GET", "/?game=849843", 200)

    def full(self, head_404=23):
        for path in ["/", "/v1/manifest.json", "/v1/health.json", "/favicon.svg"]:
            self.event("46cf3edc", "GET", path, 401)
        self.event("46cf3edc", "HEAD", "/v1/manifest.json", 401)
        self.event("dbe8837c", "HEAD", "/_publish/v1/health.json", 401)
        self.event("dbe8837c", "HEAD", "/_publish/v1/health.json", 200)
        for path in PUBLISH_PATHS[:head_404]:
            self.event("dbe8837c", "HEAD", path, 404)
        for path in PUBLISH_PATHS + ["/_publish/v1/health.json"]:
            self.event("dbe8837c", "PUT", path, 200)
        self.event("d4d707d7", "HEAD", "/_publish/v1/health.json", 503)
        self.event("d4d707d7", "GET", "/v1/manifest.json", 401)
        self.event("42e265fd", "HEAD", "/_publish/v1/health.json", 503)
        self.verifier_run("42e265fd")
        self.event("42e265fd", "GET", "/?token=abc", 200)
        self.event("42e265fd", "GET", "/?game=849843&date=2026-09-30&utm=PRIVATE", 200)
        self.event("42e265fd", "GET", "/v1/games/2026-09-30.json?date=2026-09-30", 200)
        self.event("42e265fd", "GET", "/v1/health.json", 304)
        self.verifier_run("42e265fd")
        # Notice trial under feed4fc1: ON PUT near the documented 12:59:29.6 KST, 503s only while ON,
        # OFF PUT near 13:03:52.9 KST, then the 401 gate (documented 13:04:15 KST).
        self.at("2026-11-01T03:59:29Z")
        self.event("feed4fc1", "GET", "/_notice/v1/state", 200)
        self.event("feed4fc1", "PUT", "/_notice/v1/state", 200)
        self.event("feed4fc1", "GET", "/v1/manifest.json", 503)
        self.event("feed4fc1", "GET", "/", 503)
        self.at("2026-11-01T04:03:52Z")
        self.event("feed4fc1", "PUT", "/_notice/v1/state", 200)
        self.at("2026-11-01T04:04:15Z")
        self.event("feed4fc1", "GET", "/v1/manifest.json", 401)
        self.at("2026-11-01T04:48:59Z")
        self.verifier_run("feed4fc1")
        self.at("2026-11-01T08:37:26Z")
        self.verifier_run("6d652d4b")
        # Maintenance-copy notice trial: ON PUT before the client ON check (08:39:40.739Z), OFF PUT
        # between the last client ON check (08:39:41.051Z) and the client OFF check (08:40:20.271Z).
        self.at("2026-11-01T08:39:20Z")
        self.event("6d652d4b", "PUT", "/_notice/v1/state", 200)
        self.event("6d652d4b", "GET", "/", 503)
        self.at("2026-11-01T08:39:40.500Z")
        self.event("6d652d4b", "GET", "/v1/manifest.json", 503)
        self.at("2026-11-01T08:39:42Z")
        self.event("6d652d4b", "PUT", "/_notice/v1/state", 200)
        self.at("2026-11-01T08:40:20Z")
        self.event("6d652d4b", "GET", "/v1/manifest.json", 401)
        self.event("6d652d4b", "HEAD", "/_publish/v1/health.json", 503)
        return self

    def cron(self):
        self.clock += timedelta(seconds=1)
        self.events.append({"timestamp": iso(self.clock), "$workers": {"event": {"cron": "*/5 * * * *"},
                                                                       "eventType": "scheduled", "outcome": "ok",
                                                                       "scriptVersion": {"id": VERSIONS["feed4fc1"]},
                                                                       "truncated": False},
                            "$metadata": {"requestId": "provider-cron"}})
        return self

    def canceled(self, version="feed4fc1"):
        """Client abort placed right after that version's last event, so the chain order stays intact."""
        saved = self.clock
        self.at(next(r["timestamp"] for r in reversed(self.events)
                     if "request" in r["$workers"]["event"] and r["$workers"]["scriptVersion"]["id"] == VERSIONS[version]))
        self.event(version, "GET", "/v1/health.json", None, outcome="canceled")
        self.clock = saved
        return self

    def write(self, tmp_path, name="export.json"):
        return write(tmp_path / "private" / name, self.events)


def run(*args):
    result = subprocess.run([sys.executable, "-I", "-B", str(SCRIPT), *map(str, args)],
                            capture_output=True, text=True, timeout=60, check=False)
    return result.returncode, json.loads(result.stdout), result.stderr


def run_default(tmp_path, builder):
    export = builder.write(tmp_path)
    output = tmp_path / "receipt.json"
    code, summary, stderr = run("--private-root", tmp_path / "private", "--logs", export, "--output", output)
    assert stderr == ""
    report = json.loads(output.read_text(encoding="utf-8")) if output.exists() else None
    return code, summary, report, output


def assert_sanitized(text, tmp_path):
    for forbidden in ("private.invalid", "PRIVATE", "provider-", "cookie", "Cookie", "rayId", "requestId", "abab",
                      "203.0.113", "http:", "https:", "://", "token=", "utm=", "private-worker", str(tmp_path)):
        assert forbidden not in text, forbidden
    assert not re.search(r"\b\d{1,3}(?:\.\d{1,3}){3}\b", text)
    assert not re.search(r"(?<![0-9a-f-])[0-9a-f]{16,63}(?![0-9a-f-])", text)


def test_full_synthetic_export_passes_with_sanitized_rows(tmp_path):
    builder = Builder().full().cron().canceled()
    code, summary, report, output = run_default(tmp_path, builder)
    assert code == 0 and summary["passed"] is True and summary["failed_expectations"] == []
    assert report["schema"] == "pitcheezy-host1-stage8-server-log-receipt-v1"
    assert report["evidence_kind"] == "offline_dashboard_export_count_correlation_no_rays"
    assert report["completeness"] == "unknown_export_may_be_capped"
    assert report["counts"] == summary["counts"]
    assert report["counts"]["records"] == len(builder.events)
    assert report["counts"]["non_http"] == 1 and report["counts"]["malformed"] == 0
    assert report["counts"]["canceled_without_status"] == 1
    assert report["counts"]["http"] == len(builder.events) - 1
    assert report["counts"]["duplicate_ray_groups"] == 0
    assert report["time_bounds_utc"]["first"] == builder.events[0]["timestamp"]
    assert report["time_bounds_utc"]["last"] == builder.events[-2]["timestamp"]  # the cron record
    assert len(report["source_integrity"]) == 1 and report["source_integrity"][0]["input"] == "server-export-001"
    assert len(report["source_integrity"][0]["sha256"]) == 64
    assert set(report["versions"]) == set(VERSIONS.values())
    assert list(report["versions"]) == [VERSIONS[p] for p in ("46cf3edc", "dbe8837c", "d4d707d7", "42e265fd",
                                                              "feed4fc1", "6d652d4b")]
    step45 = report["versions"][VERSIONS["dbe8837c"]]
    assert step45["by_method_status"] == {"HEAD 200": 1, "HEAD 401": 1, "HEAD 404": 23, "PUT 200": 24}
    assert step45["by_path_class_status"] == {"publish 200": 25, "publish 401": 1, "publish 404": 23}
    assert step45["events"] == 49
    assert report["versions"][VERSIONS["feed4fc1"]]["outcomes"] == {"canceled": 1, "ok": 41}
    assert report["versions"][VERSIONS["feed4fc1"]]["by_method_status"]["GET canceled"] == 1
    assert report["outcome_ok_all"] is False and report["truncated_any"] is False
    assert report["status_401"]["by_version"][VERSIONS["46cf3edc"]] == 5 and report["status_401"]["total"] == 9
    assert report["version_chain"] == {"documented_prefixes_in_order": list(VERSIONS), "undocumented_versions": 0,
                                       "order_violations": 0}
    rows = report["rows"]
    assert len(rows) == report["counts"]["http"]
    assert rows == sorted(rows, key=lambda row: row[0])
    assert all(len(row) == 5 for row in rows)
    targets = [row[2] for row in rows]
    assert "/?game=849843" in targets and "/?<stripped>" in targets
    assert "/?game=849843&date=2026-09-30&<stripped>" in targets
    assert "/v1/games/2026-09-30.json?date=2026-09-30" in targets
    assert [row for row in rows if row[3] is None] == [[builder.events[-1]["timestamp"], "GET", "/v1/health.json",
                                                        None, VERSIONS["feed4fc1"]]]
    assert {e["id"] for e in report["expectations"]} == {e["id"] for e in tool.EXPECTATIONS}
    assert all(e["passed"] for e in report["expectations"])
    step7 = next(e for e in report["expectations"] if e["id"] == "d_step7_verifier_runs")
    # 1 publish 503 + 2 x 35 verifier events + 4 browser-style extras; uncovered = publish 503 + health 304
    # (the upload-OFF check selects publish answers other than 503, so the HEAD 503 stays unselected).
    assert step7["version_events"] == 75 and step7["events_not_covered_by_checks_unattributed"] == 2
    assert step7["notice_put_interval_utc"] is None
    notice = {e["id"]: e for e in report["expectations"]}
    assert notice["e_notice_trial_and_app_host_verify"]["notice_put_interval_utc"] == [
        "2026-11-01T03:59:29.274Z", "2026-11-01T04:03:52.137Z"]
    assert notice["f_maintenance_copy_deploy"]["notice_put_interval_utc"] == [
        "2026-11-01T08:39:20.137Z", "2026-11-01T08:39:42.137Z"]
    assert "notice_put_interval_utc" not in notice["g_global_integrity"]
    assert_sanitized(output.read_text(encoding="utf-8"), tmp_path)
    assert_sanitized(json.dumps(summary), tmp_path)


def failed_checks(report, expectation_id):
    row = next(e for e in report["expectations"] if e["id"] == expectation_id)
    return [{k: v for k, v in c.items() if k not in ("op", "value")} for c in row["checks"] if not c["passed"]]


def test_notice_stuck_on_fails_e_503_outside_put_interval(tmp_path):
    builder = Builder().full().at("2026-11-01T07:00:00Z")
    for _ in range(20):
        builder.event("feed4fc1", "GET", "/v1/manifest.json", 503)
    code, summary, report, _ = run_default(tmp_path, builder)
    assert code == 1 and summary["failed_expectations"] == ["e_notice_trial_and_app_host_verify"]
    failed = failed_checks(report, "e_notice_trial_and_app_host_verify")
    assert failed == [{"metric": "count", "status": 503, "path_class_not": ["publish"],
                       "notice_interval": {"position": "outside", "slack_seconds": 5}, "observed": 20, "passed": False}]


def test_notice_never_switched_off_fails_e_and_f(tmp_path):
    builder = Builder().full()
    builder.events = [r for r in builder.events if not (r["$workers"]["event"]["request"]["method"] == "PUT"
                                                       and "/_notice/" in r["$workers"]["event"]["request"]["url"]
                                                       and r["timestamp"] in ("2026-11-01T04:03:52.137Z",
                                                                              "2026-11-01T08:39:42.137Z"))]
    code, summary, report, _ = run_default(tmp_path, builder)
    assert code == 1
    assert summary["failed_expectations"] == ["e_notice_trial_and_app_host_verify", "f_maintenance_copy_deploy"]
    for expectation_id in summary["failed_expectations"]:
        metrics = failed_checks(report, expectation_id)
        # exactly-two-PUTs fails (1 observed) and the documented OFF window holds no PUT.
        assert any(c.get("path_class") == "notice" and c["observed"] == 1 and "window_utc" not in c for c in metrics)
        assert any("window_utc" in c and c.get("path_class") == "notice" and c["observed"] == 0 for c in metrics)
    # Without the OFF PUT the maintenance-copy 503 at 08:39:40.6Z lies outside [ON PUT, ON PUT + 5s].
    outside = [c for c in failed_checks(report, "f_maintenance_copy_deploy")
               if c.get("notice_interval", {}).get("position") == "outside"]
    assert outside and outside[0]["observed"] == 1


def test_notice_503_after_off_put_fails_f(tmp_path):
    builder = Builder().full().at("2026-11-01T08:41:00Z")
    builder.event("6d652d4b", "GET", "/v1/health.json", 503)
    code, summary, report, _ = run_default(tmp_path, builder)
    assert code == 1 and summary["failed_expectations"] == ["f_maintenance_copy_deploy"]
    failed = failed_checks(report, "f_maintenance_copy_deploy")
    assert len(failed) == 1 and failed[0]["notice_interval"] == {"position": "outside", "slack_seconds": 5}
    assert failed[0]["observed"] == 1


def test_undocumented_version_fails_global_expectation(tmp_path):
    builder = Builder().full()
    builder.event(UNDOCUMENTED_VERSION, "GET", "/v1/health.json", 200)
    code, summary, report, _ = run_default(tmp_path, builder)
    assert code == 1 and summary["failed_expectations"] == ["g_global_integrity"]
    assert report["version_chain"]["undocumented_versions"] == 1 and UNDOCUMENTED_VERSION in report["versions"]
    assert failed_checks(report, "g_global_integrity") == [{"metric": "undocumented_versions", "observed": 1,
                                                            "passed": False}]


def test_version_out_of_chain_order_fails_global_expectation(tmp_path):
    builder = Builder().full()
    builder.event("46cf3edc", "GET", "/v1/manifest.json", 401)  # step-2 version answering after 6d652d4b began
    code, summary, report, _ = run_default(tmp_path, builder)
    assert code == 1 and summary["failed_expectations"] == ["g_global_integrity"]
    assert report["version_chain"]["order_violations"] >= 1
    assert [c["metric"] for c in failed_checks(report, "g_global_integrity")] == ["version_chain_order_violations"]


def test_publish_put_200_under_upload_off_version_fails(tmp_path):
    builder = Builder().full().at("2026-11-01T05:00:00Z")
    for _ in range(5):
        builder.event("feed4fc1", "PUT", "/_publish/v1/game/849843.json", 200)
    builder.event("42e265fd", "HEAD", "/_publish/v1/health.json", 200)
    builder.event("6d652d4b", "PUT", "/_publish/v1/health.json", 200)
    builder.event("46cf3edc", "HEAD", "/_publish/v1/health.json", 401)
    code, summary, report, _ = run_default(tmp_path, builder)
    assert code == 1
    assert set(summary["failed_expectations"]) >= {"a_step2_gate_401", "d_step7_verifier_runs",
                                                   "e_notice_trial_and_app_host_verify", "f_maintenance_copy_deploy"}
    for expectation_id, observed in (("a_step2_gate_401", 1), ("d_step7_verifier_runs", 1),
                                     ("e_notice_trial_and_app_host_verify", 5), ("f_maintenance_copy_deploy", 1)):
        publish = [c for c in failed_checks(report, expectation_id) if c.get("path_class") == "publish"]
        assert publish and publish[0]["status_not"] == [503] and publish[0]["observed"] == observed


def test_notice_activity_under_non_trial_versions_fails_a_to_d(tmp_path):
    builder = Builder().full()

    def just_before(version):
        # Land 1 ms before the version's first event: inside the chain gap, so the order check stays clean.
        first = min(datetime.fromisoformat(r["timestamp"].replace("Z", "+00:00")) for r in builder.events
                    if r["$workers"]["scriptVersion"]["id"] == VERSIONS[version])
        return builder.at(iso(first - timedelta(milliseconds=138)))

    just_before("46cf3edc").event("46cf3edc", "GET", "/v1/manifest.json", 503)
    just_before("dbe8837c").event("dbe8837c", "GET", "/v1/manifest.json", 503)
    just_before("d4d707d7").event("d4d707d7", "PUT", "/_notice/v1/state", 200)
    just_before("42e265fd").event("42e265fd", "PUT", "/_notice/v1/state", 200)
    code, summary, report, output = run_default(tmp_path, builder)
    assert code == 1
    assert set(summary["failed_expectations"]) >= {"a_step2_gate_401", "b_step45_upload_window",
                                                   "c_step6_upload_closed", "d_step7_verifier_runs"}
    assert "g_global_integrity" not in summary["failed_expectations"]
    for expectation_id in ("a_step2_gate_401", "b_step45_upload_window"):
        assert any(c.get("status") == 503 and c.get("path_class_not") == ["publish"] and c["observed"] == 1
                   for c in failed_checks(report, expectation_id))
    for expectation_id in ("c_step6_upload_closed", "d_step7_verifier_runs"):
        assert any(c.get("path_class") == "notice" and c.get("method") == "PUT" and c["observed"] == 1
                   for c in failed_checks(report, expectation_id))
    assert_sanitized(output.read_text(encoding="utf-8"), tmp_path)


def test_timestamp_offset_overflow_is_counted_malformed_not_fatal(tmp_path):
    builder = Builder().full().cron()
    builder.events[1]["timestamp"] = "0001-01-01T00:00:00+01:00"  # step-2 GET 401 (a keeps >= 3 events)
    builder.events[2]["timestamp"] = "9999-12-31T23:59:59-01:00"
    builder.events[-1]["timestamp"] = "0001-01-01T00:00:00+01:00"  # the cron record
    code, summary, report, output = run_default(tmp_path, builder)
    assert code == 1 and summary["passed"] is False and summary["failed_expectations"] == []
    assert report["counts"]["malformed"] == 2 and report["counts"]["non_http"] == 1
    assert report["counts"]["http"] == len(builder.events) - 3
    assert report["time_bounds_utc"]["first"] == builder.events[0]["timestamp"]
    assert_sanitized(output.read_text(encoding="utf-8"), tmp_path)


def test_notice_interval_selector_is_validated():
    base = {"id": "x", "version_prefix": "feed4fc1", "rule": [{"metric": "count", "op": "==", "value": 0}]}
    tool.validate_expectations([base])
    for bad in ({"position": "before"}, {"position": "inside", "slack_seconds": 601}, {"position": "inside", "extra": 1},
                {"position": "after", "slack_seconds": -1}, {"position": "after", "slack_seconds": 1.5}, "inside"):
        rule = [{"metric": "count", "op": "==", "value": 0, "notice_interval": bad}]
        try:
            tool.validate_expectations([{**base, "rule": rule}])
        except tool.InputError as exc:
            assert str(exc) == "expectations_table_invalid"
        else:
            raise AssertionError(bad)
    rule = [{"metric": "count", "op": "==", "value": 0, "notice_interval": {"position": "inside"}}]
    try:
        tool.validate_expectations([{**base, "version_prefix": None, "rule": rule}])
    except tool.InputError as exc:
        assert str(exc) == "expectations_table_invalid"
    else:
        raise AssertionError("notice_interval without a version scope must be rejected")
    for metric in ("undocumented_versions", "version_chain_order_violations"):
        tool.validate_expectations([{"id": "g", "version_prefix": None,
                                     "rule": [{"metric": metric, "op": "==", "value": 0}]}])


def test_head_404_count_22_fails_expectation_b_but_writes_receipt(tmp_path):
    code, summary, report, _ = run_default(tmp_path, Builder().full(head_404=22))
    assert code == 1 and summary["passed"] is False
    assert summary["failed_expectations"] == ["b_step45_upload_window"]
    failed = next(e for e in report["expectations"] if e["id"] == "b_step45_upload_window")
    assert failed["passed"] is False
    check = next(c for c in failed["checks"] if c.get("status") == 404)
    assert check["observed"] == 22 and check["value"] == 23 and check["passed"] is False
    assert report["versions"][VERSIONS["dbe8837c"]]["by_method_status"]["HEAD 404"] == 22


def test_malformed_record_is_counted_and_fails_without_abort(tmp_path):
    builder = Builder().full()
    builder.events.insert(3, {"timestamp": "2026-11-01T02:40:00.000Z", "$workers": {"event": {"request": "PRIVATE"}},
                              "$metadata": {}})
    builder.events.append({"not": "a record"})
    code, summary, report, output = run_default(tmp_path, builder)
    assert code == 1 and summary["passed"] is False and summary["failed_expectations"] == []
    assert report["counts"]["malformed"] == 2 and report["counts"]["http"] == len(builder.events) - 2
    assert all(e["passed"] for e in report["expectations"])
    assert_sanitized(output.read_text(encoding="utf-8"), tmp_path)


def test_non_http_record_is_counted_not_failed(tmp_path):
    code, summary, report, _ = run_default(tmp_path, Builder().full().cron().cron())
    assert code == 0 and summary["passed"] is True
    assert report["counts"]["non_http"] == 2 and report["counts"]["malformed"] == 0
    assert report["time_bounds_utc"]["last"] > report["rows"][-1][0]


def test_canceled_request_without_status_is_not_malformed(tmp_path):
    code, summary, report, _ = run_default(tmp_path, Builder().full().canceled("42e265fd").canceled())
    assert code == 0 and summary["passed"] is True
    assert report["counts"]["canceled_without_status"] == 2 and report["counts"]["malformed"] == 0
    assert report["versions"][VERSIONS["42e265fd"]]["by_path_class_status"]["health canceled"] == 1


def test_unexpected_outcome_fails_global_expectation(tmp_path):
    builder = Builder().full()
    builder.event("feed4fc1", "GET", "/v1/health.json", 500, outcome="exception")
    code, summary, report, _ = run_default(tmp_path, builder)
    assert code == 1 and summary["failed_expectations"] == ["g_global_integrity"]
    assert report["outcome_ok_all"] is False
    assert report["versions"][VERSIONS["feed4fc1"]]["outcomes"]["exception"] == 1


def test_existing_output_is_never_overwritten(tmp_path):
    export = Builder().full().write(tmp_path)
    output = write(tmp_path / "receipt.json", {"keep": True})
    code, summary, _ = run("--private-root", tmp_path / "private", "--logs", export, "--output", output)
    assert code == 2 and summary == {"passed": False, "error": "output_exists_do_not_overwrite"}
    assert json.loads(output.read_text(encoding="utf-8")) == {"keep": True}


def test_logs_outside_private_root_are_rejected(tmp_path):
    export = write(tmp_path / "outside" / "export.json", Builder().full().events)
    (tmp_path / "private").mkdir()
    code, summary, _ = run("--private-root", tmp_path / "private", "--logs", export, "--output", tmp_path / "r.json")
    assert code == 2 and summary == {"passed": False, "error": "private_input_outside_root"}
    assert str(tmp_path) not in json.dumps(summary) and not (tmp_path / "r.json").exists()


def test_export_that_is_not_an_array_is_rejected(tmp_path):
    export = write(tmp_path / "private" / "export.json", {"records": []})
    code, summary, _ = run("--private-root", tmp_path / "private", "--logs", export, "--output", tmp_path / "r.json")
    assert code == 2 and summary == {"passed": False, "error": "server_export_must_be_array"}


def test_duplicate_ray_is_reported_and_fails_global_expectation(tmp_path):
    builder = Builder().full()
    shared = f"{'cd' * 8}{1:016x}"
    builder.event("feed4fc1", "GET", "/v1/health.json", 200, ray=shared)
    builder.event("feed4fc1", "GET", "/v1/health.json", 200, ray=shared, request_id="provider-dup")
    builder.event("feed4fc1", "GET", "/v1/health.json", 200, request_id="provider-dup")
    code, summary, report, output = run_default(tmp_path, builder)
    assert code == 1 and summary["failed_expectations"] == ["g_global_integrity"]
    assert report["counts"]["duplicate_ray_groups"] == 1
    assert report["counts"]["duplicate_provider_request_id_groups"] == 1
    check = next(e for e in report["expectations"] if e["id"] == "g_global_integrity")["checks"][0]
    assert check["metric"] == "duplicate_ray_groups" and check["observed"] == 1 and check["passed"] is False
    assert_sanitized(output.read_text(encoding="utf-8"), tmp_path)


def test_expectations_file_outside_repo_is_rejected(tmp_path):
    export = Builder().full().write(tmp_path)
    # pytest's tmp_path may sit inside the checkout (CI uses a basetemp under the repo), so the table goes to
    # the system temp directory; if even that resolves inside the repo the premise is gone and the test skips.
    with tempfile.TemporaryDirectory() as outside:
        if Path(outside).resolve().is_relative_to(tool.REPO_ROOT):
            pytest.skip("system temp directory is inside the repository; cannot stage an outside file")
        table = write(Path(outside) / "expectations.json", tool.EXPECTATIONS)
        code, summary, _ = run("--private-root", tmp_path / "private", "--logs", export, "--expectations", table,
                               "--output", tmp_path / "r.json")
    assert code == 2 and summary == {"passed": False, "error": "expectations_outside_repo"}


def test_builtin_expectations_table_validates_and_names_every_version():
    tool.validate_expectations(tool.EXPECTATIONS)
    assert {e["version_prefix"] for e in tool.EXPECTATIONS} == set(VERSIONS) | {None}
    assert [e["id"][0] for e in tool.EXPECTATIONS] == list("abcdefg")


def test_public_target_keeps_only_game_and_date():
    assert tool.public_target("/", "game=849843") == "/?game=849843"
    assert tool.public_target("/", "token=abc") == "/?<stripped>"
    assert tool.public_target("/", "game=849843&token=abc") == "/?game=849843&<stripped>"
    assert tool.public_target("/", "game=not-a-number") == "/?<stripped>"
    assert tool.public_target("/", "date=2026-09-30") == "/?date=2026-09-30"
    assert tool.public_target("/", "") == "/"
    assert tool.public_target("/odd pathé", "") == "/<path-redacted>"

"""Offline host-1101 step-8 server-log receipt (count correlation, no Rays); never contacts a server.

The 2026-11-01 client-side ledgers carry no Rays, so this tool does not match single
requests. It reads a Cloudflare dashboard Observability export (private), counts HTTP
events per Worker version, method, path class and status, and checks a fixed table of
count expectations derived from the documented step plan. The receipt is allowlisted:
UTC timestamps, method, URL path, the ``game=``/``date=`` query parameters, status and
version UUID only. Hostnames, Rays, provider request IDs, IPs, headers, cookies, bodies
and local paths never leave the export. Records with ``outcome: canceled`` and no
response status (client aborts) are HTTP events without a status, counted separately;
cron events and malformed records are counted, never fatal. The export may be capped
by the dashboard, so completeness is reported as unknown.

Beyond per-version counts the table ties ``passed`` to the documented chain: every
version in the export must be one the table names, their time ranges must be disjoint
and in table order, ``/_publish`` under the upload-OFF versions may only answer 503,
and each notice trial must have its non-publish 503s confined to the server-side
interval between its notice PUTs, with the 401 gate observed after the OFF PUT.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import sys
from collections import Counter, defaultdict
from datetime import timedelta
from pathlib import Path
from urllib.parse import parse_qsl


def load_stage34():
    file = Path(__file__).resolve().parent / "correlate_exhibit_stage34_logs.py"
    spec = importlib.util.spec_from_file_location("exhibit_stage34_logs", file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


stage34 = load_stage34()
InputError, need = stage34.InputError, stage34.need
REPO_ROOT = Path(__file__).resolve().parents[1]
SCHEMA = "pitcheezy-host1-stage8-server-log-receipt-v1"
EVIDENCE = "offline_dashboard_export_count_correlation_no_rays"
ALLOWED_QUERY = {"game": re.compile(r"[0-9]{1,10}"), "date": re.compile(r"[0-9]{4}-[0-9]{2}-[0-9]{2}")}
SAFE_PATH = re.compile(r"/[A-Za-z0-9._~/-]{0,200}")
CANCELED = "canceled"
OPS = {"==", ">=", "<=", "between"}
GLOBAL_METRICS = {"duplicate_ray_groups", "truncated_events", "unexpected_outcome_events",
                  "undocumented_versions", "version_chain_order_violations"}
NOTICE_POSITIONS = {"inside", "outside", "after"}
MAX_SLACK_SECONDS = 600
UPLOAD_OFF = {"metric": "count", "path_class": "publish", "status_not": [503], "op": "==", "value": 0}
# Notice activity (operator PUT, maintenance 503 on viewer paths) belongs only to the two
# documented trial versions (e, f); under every other version both counts must be zero.
NO_NOTICE_PUT = {"metric": "count", "path_class": "notice", "method": "PUT", "op": "==", "value": 0}
NO_MAINTENANCE_503 = {"metric": "count", "status": 503, "path_class_not": ["publish"], "op": "==", "value": 0}

# Each rule is a list of count checks over the HTTP events of the version named by
# ``version_prefix`` (None = whole export). A check selects events by optional
# path_class / method / status (or the *_not negations), an optional UTC window
# (``window_utc`` keeps events inside it, ``outside_window_utc`` keeps events outside it)
# and an optional ``notice_interval`` position relative to the version's own notice PUTs
# (``inside``: first PUT .. last PUT + slack; ``outside``: everything else, which is every
# event when the version has no notice PUT; ``after``: later than last PUT + slack), then
# compares the selected count with ``value`` using ``op``. Global metrics are named; the
# documented version chain is the table's version_prefix values in table order.
EXPECTATIONS = [
    {"id": "a_step2_gate_401", "version_prefix": "46cf3edc",
     "description": "step 2 post-deploy: every HTTP event is 401 (gate ON, no session); at least 3; "
                    "upload OFF (no publish answer other than 503); no notice PUT, no maintenance 503",
     "rule": [{"metric": "count", "op": ">=", "value": 3},
              {"metric": "count", "status_not": [401], "op": "==", "value": 0},
              UPLOAD_OFF, NO_NOTICE_PUT, NO_MAINTENANCE_503]},
    {"id": "b_step45_upload_window", "version_prefix": "dbe8837c",
     "description": "steps 4-5: publish HEAD 200 x1 (health), HEAD 404 x23, PUT 200 x24, "
                    "HEAD 401 >=1 (window-open check), no other publish methods; no notice PUT, "
                    "no maintenance 503",
     "rule": [{"metric": "count", "path_class": "publish", "method": "HEAD", "status": 200, "op": "==", "value": 1},
              {"metric": "count", "path_class": "publish", "method": "HEAD", "status": 404, "op": "==", "value": 23},
              {"metric": "count", "path_class": "publish", "method": "PUT", "status": 200, "op": "==", "value": 24},
              {"metric": "count", "path_class": "publish", "method": "HEAD", "status": 401, "op": ">=", "value": 1},
              {"metric": "count", "path_class": "publish", "method_not": ["HEAD", "PUT"], "op": "==", "value": 0},
              NO_NOTICE_PUT, NO_MAINTENANCE_503]},
    {"id": "c_step6_upload_closed", "version_prefix": "d4d707d7",
     "description": "step 6: publish events are all 503 (1..2) and no publish 200; no notice PUT, "
                    "no maintenance 503",
     "rule": [{"metric": "count", "path_class": "publish", "status": 503, "op": "between", "value": [1, 2]},
              {"metric": "count", "path_class": "publish", "status_not": [503], "op": "==", "value": 0},
              NO_NOTICE_PUT, NO_MAINTENANCE_503]},
    {"id": "d_step7_verifier_runs", "version_prefix": "42e265fd",
     "description": "step 7 (verifier run 1, body checks, run 2): minimum counts; the plan's 23 data "
                    "files per run are 22 data + health here; events beyond the checks (phone/PC "
                    "browser) are counted without attribution; upload stays OFF; no notice PUT, "
                    "no maintenance 503",
     "rule": [UPLOAD_OFF, NO_NOTICE_PUT, NO_MAINTENANCE_503,
              {"metric": "count", "path_class": "access", "method": "POST", "status": 200, "op": ">=", "value": 1},
              {"metric": "count", "path_class": "manifest", "method": "GET", "status": 200, "op": ">=", "value": 2},
              {"metric": "count", "path_class": "data", "method": "GET", "status": 200, "op": ">=", "value": 44},
              {"metric": "count", "path_class": "health", "method": "GET", "status": 200, "op": ">=", "value": 2},
              {"metric": "count", "path_class": "static", "method": "GET", "status": 200, "op": ">=", "value": 6},
              {"metric": "count", "path_class": "index", "method": "GET", "status": 307, "op": ">=", "value": 1},
              {"metric": "count", "path_class": "root", "method": "GET", "status": 200, "op": ">=", "value": 4},
              {"metric": "count", "path_class": "data", "status": 404, "op": ">=", "value": 4},
              {"metric": "count", "path_class": "manifest", "method": "HEAD", "status": 200, "op": ">=", "value": 2}]},
    {"id": "e_notice_trial_and_app_host_verify", "version_prefix": "feed4fc1",
     "description": "notice ON/OFF trial: exactly 2 notice PUTs, ON PUT within 3s of the documented "
                    "12:59:29.6 KST and OFF PUT within 3s of 13:03:52.9 KST (host-deploy notice_trial); "
                    "every non-publish 503 lies between the ON PUT and the OFF PUT (+5s), at least one "
                    "manifest 503 inside, and the manifest 401 gate is seen after the OFF PUT (documented "
                    "13:04:15 KST); upload stays OFF; app-host verifier run between 04:40Z and 04:55Z "
                    "(22 data + health GET 200)",
     "rule": [UPLOAD_OFF,
              {"metric": "count", "path_class": "notice", "method": "PUT", "op": "==", "value": 2},
              {"metric": "count", "path_class": "notice", "method": "PUT",
               "window_utc": ["2026-11-01T03:59:26Z", "2026-11-01T03:59:33Z"], "op": "==", "value": 1},
              {"metric": "count", "path_class": "notice", "method": "PUT",
               "window_utc": ["2026-11-01T04:03:49Z", "2026-11-01T04:03:56Z"], "op": "==", "value": 1},
              {"metric": "count", "path_class": "notice", "method": "GET", "op": ">=", "value": 1},
              {"metric": "count", "status": 503, "path_class_not": ["publish"],
               "notice_interval": {"position": "outside", "slack_seconds": 5}, "op": "==", "value": 0},
              {"metric": "count", "path_class": "manifest", "status": 503,
               "notice_interval": {"position": "inside", "slack_seconds": 5}, "op": ">=", "value": 1},
              {"metric": "count", "path_class": "manifest", "status": 401,
               "notice_interval": {"position": "after", "slack_seconds": 0},
               "window_utc": ["2026-11-01T04:03:49Z", "2026-11-01T04:05:00Z"], "op": ">=", "value": 1},
              {"metric": "count", "path_class": "data", "method": "GET", "status": 200,
               "window_utc": ["2026-11-01T04:40:00Z", "2026-11-01T04:55:00Z"], "op": ">=", "value": 22},
              {"metric": "count", "path_class": "health", "method": "GET", "status": 200,
               "window_utc": ["2026-11-01T04:40:00Z", "2026-11-01T04:55:00Z"], "op": ">=", "value": 1}]},
    {"id": "f_maintenance_copy_deploy", "version_prefix": "6d652d4b",
     "description": "maintenance-copy deploy: remote verify (22 data + health GET 200); exactly 2 notice "
                    "PUTs, the ON PUT after the documented verifier end (08:37:33Z) and before the client "
                    "ON check (08:39:40.739Z), the OFF PUT between the last client ON check (08:39:41.051Z) "
                    "and the client OFF check (08:40:20.271Z) (notice-deploy receipt); every non-publish "
                    "503 lies between the ON PUT and the OFF PUT (+5s), at least one manifest 503 inside, "
                    "manifest 401 after the OFF PUT; upload stays OFF",
     "rule": [UPLOAD_OFF,
              {"metric": "count", "path_class": "data", "method": "GET", "status": 200, "op": ">=", "value": 22},
              {"metric": "count", "path_class": "health", "method": "GET", "status": 200, "op": ">=", "value": 1},
              {"metric": "count", "path_class": "notice", "method": "PUT", "op": "==", "value": 2},
              {"metric": "count", "path_class": "notice", "method": "PUT",
               "window_utc": ["2026-11-01T08:37:33Z", "2026-11-01T08:39:40.739Z"], "op": "==", "value": 1},
              {"metric": "count", "path_class": "notice", "method": "PUT",
               "window_utc": ["2026-11-01T08:39:41.051Z", "2026-11-01T08:40:20.271Z"], "op": "==", "value": 1},
              {"metric": "count", "status": 503, "path_class_not": ["publish"],
               "notice_interval": {"position": "outside", "slack_seconds": 5}, "op": "==", "value": 0},
              {"metric": "count", "path_class": "manifest", "status": 503,
               "notice_interval": {"position": "inside", "slack_seconds": 5}, "op": ">=", "value": 1},
              {"metric": "count", "path_class": "manifest", "status": 401,
               "notice_interval": {"position": "after", "slack_seconds": 0}, "op": ">=", "value": 1}]},
    {"id": "g_global_integrity", "version_prefix": None,
     "description": "whole export: no duplicate Ray groups, nothing truncated, no outcome other "
                    "than ok/canceled; every Worker version is one of the six documented ones and "
                    "their time ranges are disjoint and in chain order; 401 counts are listed per "
                    "version, not attributed",
     "rule": [{"metric": "duplicate_ray_groups", "op": "==", "value": 0},
              {"metric": "truncated_events", "op": "==", "value": 0},
              {"metric": "unexpected_outcome_events", "op": "==", "value": 0},
              {"metric": "undocumented_versions", "op": "==", "value": 0},
              {"metric": "version_chain_order_violations", "op": "==", "value": 0}]},
]


def path_class(path):
    if path.startswith("/_publish/"):
        return "publish"
    if path.startswith("/_notice/"):
        return "notice"
    if path.startswith("/_access/"):
        return "access"
    if path == "/v1/manifest.json":
        return "manifest"
    if path == "/v1/health.json":
        return "health"
    if path.startswith("/v1/"):
        return "data"
    if path == "/":
        return "root"
    if path == "/index.html":
        return "index"
    if path == "/favicon.svg" or path.startswith("/assets/"):
        return "static"
    return "other"


def public_target(path, query):
    """Path plus only game=/date= with well-formed values; every other parameter is stripped."""
    safe_path = path if SAFE_PATH.fullmatch(path) else "/<path-redacted>"
    kept, stripped = [], False
    for key, value in parse_qsl(query, keep_blank_values=True):
        pattern = ALLOWED_QUERY.get(key)
        if pattern is not None and pattern.fullmatch(value):
            kept.append(f"{key}={value}")
        else:
            stripped = True
    if stripped:
        kept.append("<stripped>")
    return safe_path + ("?" + "&".join(kept) if kept else "")


def canceled_event(row):
    """A request the client aborted: same layout, ``outcome: canceled`` and no status."""
    workers, meta = row.get("$workers"), row.get("$metadata")
    event = workers.get("event")
    req, response = event.get("request"), event.get("response", {})
    need(workers.get("outcome") == CANCELED and isinstance(response, dict) and response.get("status") is None,
         "server_http_value_invalid")
    need(isinstance(req, dict) and isinstance(meta, dict), "server_http_metadata_missing")
    need(req.get("method") in stage34.METHODS, "server_http_value_invalid")
    path, query = stage34.target(req.get("url"), absolute=True)
    headers = req.get("headers", {})
    need(isinstance(headers, dict), "server_http_metadata_missing")
    header_ray = stage34.ray(next((v for k, v in headers.items() if k.lower() == "cf-ray"), None))
    need(header_ray is not None, "server_ray_missing")
    provider_id = meta.get("requestId")
    need(isinstance(provider_id, str) and 0 < len(provider_id) <= 256, "server_request_id_missing")
    ver = workers.get("scriptVersion")
    need(isinstance(ver, dict), "server_version_missing")
    return {"ray": header_ray, "provider_id": provider_id, "method": req["method"], "path": path,
            "query": query, "status": None, "version": stage34.version(ver.get("id")),
            "timestamp": stage34.stamp(row.get("timestamp")), "outcome": CANCELED,
            "not_truncated": workers.get("truncated") is False}


def host_event(row):
    """stage34 ``server_event`` first; only the canceled-without-status shape gets the fallback."""
    try:
        event = stage34.server_event(row)
    except InputError as exc:
        if str(exc) != "server_http_value_invalid":
            raise
        return canceled_event(row)
    if event is not None:
        outcome = row["$workers"].get("outcome")
        event["outcome"] = "ok" if event.pop("outcome_ok") else (outcome if isinstance(outcome, str) else "non_string")
    return event


def iso(value):
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def parse_export(raw_events):
    need(isinstance(raw_events, list), "server_export_must_be_array")
    events, stamps, non_http, malformed = [], [], 0, 0
    for raw in raw_events:
        try:
            event = host_event(raw)
        except (InputError, TypeError, AttributeError, KeyError, OverflowError):
            malformed += 1  # OverflowError: a UTC offset that overflows astimezone() is malformed, not fatal.
            continue
        if event is None:
            non_http += 1
            try:
                stamps.append(stage34.stamp(raw.get("timestamp")))
            except (InputError, OverflowError):
                pass
            continue
        event["path_class"] = path_class(event["path"])
        events.append(event)
        stamps.append(event["timestamp"])
    events.sort(key=lambda e: e["timestamp"])
    return events, stamps, non_http, malformed


def status_key(status):
    return CANCELED if status is None else str(status)


def version_block(events):
    return {"events": len(events), "first_utc": iso(events[0]["timestamp"]), "last_utc": iso(events[-1]["timestamp"]),
            "by_method_status": dict(sorted(Counter(f"{e['method']} {status_key(e['status'])}" for e in events).items())),
            "by_path_class_status": dict(sorted(Counter(f"{e['path_class']} {status_key(e['status'])}"
                                                        for e in events).items())),
            "outcomes": dict(sorted(Counter(e["outcome"] for e in events).items()))}


def notice_put_interval(events):
    """[first notice PUT, last notice PUT] of one version's events, or None without any."""
    puts = [e["timestamp"] for e in events if e["path_class"] == "notice" and e["method"] == "PUT"]
    return (min(puts), max(puts)) if puts else None


def selects(check, event, interval):
    for field in ("path_class", "method", "status"):
        if field in check and event[field] != check[field]:
            return False
        if field + "_not" in check and event[field] in check[field + "_not"]:
            return False
    if "window_utc" in check:
        start, end = (stage34.stamp(v) for v in check["window_utc"])
        if not start <= event["timestamp"] <= end:
            return False
    if "outside_window_utc" in check:
        start, end = (stage34.stamp(v) for v in check["outside_window_utc"])
        if start <= event["timestamp"] <= end:
            return False
    if "notice_interval" in check:
        position, slack = check["notice_interval"]["position"], check["notice_interval"].get("slack_seconds", 0)
        stamp = event["timestamp"]
        inside = interval is not None and interval[0] <= stamp <= interval[1] + timedelta(seconds=slack)
        after = interval is not None and stamp > interval[1] + timedelta(seconds=slack)
        if {"inside": inside, "outside": not inside, "after": after}[position] is False:
            return False
    return True


def compare(op, observed, value):
    if op == "between":
        return value[0] <= observed <= value[1]
    return {"==": observed == value, ">=": observed >= value, "<=": observed <= value}[op]


def validate_expectations(table):
    need(isinstance(table, list) and table, "expectations_table_invalid")
    ids = set()
    for item in table:
        need(isinstance(item, dict) and isinstance(item.get("id"), str) and item["id"] not in ids,
             "expectations_table_invalid")
        ids.add(item["id"])
        prefix = item.get("version_prefix")
        need(prefix is None or (isinstance(prefix, str) and re.fullmatch(r"[0-9a-f]{8}", prefix)),
             "expectations_table_invalid")
        need(isinstance(item.get("rule"), list) and item["rule"], "expectations_table_invalid")
        for check in item["rule"]:
            need(isinstance(check, dict) and check.get("op") in OPS and isinstance(check.get("metric"), str),
                 "expectations_table_invalid")
            if check["op"] == "between":
                need(isinstance(check["value"], list) and len(check["value"]) == 2 and
                     all(type(v) is int for v in check["value"]), "expectations_table_invalid")
            else:
                need(type(check.get("value")) is int, "expectations_table_invalid")
            for key in ("window_utc", "outside_window_utc"):
                if key in check:
                    need(isinstance(check[key], list) and len(check[key]) == 2, "expectations_table_invalid")
                    start, end = (stage34.stamp(v) for v in check[key])
                    need(start <= end, "expectations_table_invalid")
            if "notice_interval" in check:
                spec = check["notice_interval"]
                need(isinstance(spec, dict) and set(spec) <= {"position", "slack_seconds"}
                     and spec.get("position") in NOTICE_POSITIONS and prefix is not None
                     and type(spec.get("slack_seconds", 0)) is int and 0 <= spec.get("slack_seconds", 0) <= MAX_SLACK_SECONDS,
                     "expectations_table_invalid")
            if check["metric"] == "count":
                need(set(check) <= {"metric", "op", "value", "path_class", "method", "status",
                                    "path_class_not", "method_not", "status_not", "window_utc",
                                    "outside_window_utc", "notice_interval"},
                     "expectations_table_invalid")
            else:
                need(check["metric"] in GLOBAL_METRICS and prefix is None and set(check) == {"metric", "op", "value"},
                     "expectations_table_invalid")


def evaluate(table, events, by_version, globals_):
    results = []
    for item in table:
        prefix = item["version_prefix"]
        matches = [v for v in by_version if v.startswith(prefix)] if prefix else [None]
        scoped = events if prefix is None else (by_version[matches[0]] if len(matches) == 1 else [])
        interval = notice_put_interval(scoped) if prefix is not None else None
        checks, covered = [], set()
        for check in item["rule"]:
            if check["metric"] == "count":
                selected = [i for i, e in enumerate(scoped) if selects(check, e, interval)]
                covered.update(selected)
                observed = len(selected)
            else:
                observed = globals_[check["metric"]]
            checks.append({**check, "observed": observed, "passed": compare(check["op"], observed, check["value"])})
        passed = all(c["passed"] for c in checks) and len(matches) == 1
        row = {"id": item["id"], "version_prefix": prefix, "description": item["description"],
               "version_match": "unique" if len(matches) == 1 else ("none" if not matches else "ambiguous"),
               "passed": passed, "checks": checks}
        if prefix is not None:
            row["version_events"] = len(scoped)
            row["events_not_covered_by_checks_unattributed"] = len(scoped) - len(covered)
            row["notice_put_interval_utc"] = [iso(interval[0]), iso(interval[1])] if interval else None
        results.append(row)
    return results


def version_chain_metrics(table, by_version):
    """Versions outside the table's chain, and chain-order / overlap violations between documented ones."""
    chain = [item["version_prefix"] for item in table if item["version_prefix"] is not None]
    ordered = sorted(by_version.items(), key=lambda kv: kv[1][0]["timestamp"])
    documented, undocumented = [], 0
    for ver, es in ordered:
        index = next((i for i, prefix in enumerate(chain) if ver.startswith(prefix)), None)
        if index is None:
            undocumented += 1
        else:
            documented.append((index, es[0]["timestamp"], es[-1]["timestamp"]))
    violations = sum(later[0] <= earlier[0] or later[1] <= earlier[2]
                     for earlier, later in zip(documented, documented[1:], strict=False))
    return {"undocumented_versions": undocumented, "version_chain_order_violations": violations}


def receipt(raw_events, table, source_receipts):
    events, stamps, non_http, malformed = parse_export(raw_events)
    by_version = defaultdict(list)
    for event in events:
        by_version[event["version"]].append(event)
    rays = Counter(e["ray"] for e in events)
    provider_ids = Counter(e["provider_id"] for e in events)
    globals_ = {"duplicate_ray_groups": sum(n > 1 for n in rays.values()),
                "truncated_events": sum(not e["not_truncated"] for e in events),
                "unexpected_outcome_events": sum(e["outcome"] not in {"ok", CANCELED} for e in events),
                **version_chain_metrics(table, by_version)}
    expectations = evaluate(table, events, by_version, globals_)
    counts = {"records": len(raw_events), "http": len(events), "non_http": non_http, "malformed": malformed,
              "canceled_without_status": sum(e["status"] is None for e in events),
              "duplicate_ray_groups": globals_["duplicate_ray_groups"],
              "duplicate_provider_request_id_groups": sum(n > 1 for n in provider_ids.values())}
    failed = [e["id"] for e in expectations if not e["passed"]]
    ordered = sorted(by_version.items(), key=lambda kv: kv[1][0]["timestamp"])
    return {
        "schema": SCHEMA, "evidence_kind": EVIDENCE,
        "passed": not failed and malformed == 0,
        "source_integrity": list(source_receipts),
        "counts": counts,
        "time_bounds_utc": {"first": iso(min(stamps)) if stamps else None, "last": iso(max(stamps)) if stamps else None},
        "completeness": "unknown_export_may_be_capped",
        "canceled_status_representation": "null_in_rows_canceled_in_keys",
        "versions": {v: version_block(es) for v, es in ordered},
        "status_401": {"by_version": {v: sum(e["status"] == 401 for e in es) for v, es in ordered},
                       "total": sum(e["status"] == 401 for e in events),
                       "note": "unexplained_401s_recorded_not_attributed"},
        "outcome_ok_all": all(e["outcome"] == "ok" for e in events),
        "truncated_any": globals_["truncated_events"] > 0,
        "version_chain": {"documented_prefixes_in_order": [i["version_prefix"] for i in table if i["version_prefix"]],
                          "undocumented_versions": globals_["undocumented_versions"],
                          "order_violations": globals_["version_chain_order_violations"]},
        "expectations": expectations, "failed_expectations": failed,
        "rows": [[iso(e["timestamp"]), e["method"], public_target(e["path"], e["query"]), e["status"], e["version"]]
                 for e in events],
        "limits": ["count_correlation_only_no_per_request_ray_matching",
                   "export_count_may_be_capped_by_dashboard_completeness_unknown",
                   "extra_events_are_counted_not_attributed",
                   "does_not_prove_body_bytes_authentication_or_ui_acceptance"],
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", required=True)
    parser.add_argument("--logs", required=True, action="append")
    parser.add_argument("--expectations")
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        output = Path(args.output)
        need(not output.exists(), "output_exists_do_not_overwrite")
        sources, events, table = stage34.Sources(), [], EXPECTATIONS
        if args.expectations:
            file = Path(args.expectations).resolve(strict=True)
            need(file.is_relative_to(REPO_ROOT), "expectations_outside_repo")
            table = sources.read(file, "expectations-table")
        validate_expectations(table)
        for number, file in enumerate(args.logs, 1):
            raw = sources.read(stage34.inside_private(file, args.private_root), f"server-export-{number:03d}")
            need(isinstance(raw, list), "server_export_must_be_array")
            events.extend(raw)  # overlapping exports intentionally remain duplicate evidence.
        report = receipt(events, table, sources.receipts)
        with output.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, ensure_ascii=True, indent=2)
            handle.write("\n")
        print(json.dumps({"passed": report["passed"], "counts": report["counts"],
                          "failed_expectations": report["failed_expectations"]}))
        return 0 if report["passed"] else 1
    except (InputError, OSError, ValueError, TypeError, OverflowError) as exc:
        # Never stringify arbitrary exceptions: OS errors can contain private paths.
        code = str(exc) if isinstance(exc, InputError) else "input_or_output_failed"
        print(json.dumps({"passed": False, "error": code}))
        return 2


if __name__ == "__main__":
    sys.exit(main())

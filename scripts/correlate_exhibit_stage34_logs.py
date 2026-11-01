"""Offline stage3/4 request-to-Workers-log correlation; never contacts a server.

Inputs stay private. The output is an allowlisted receipt with no hostnames, Rays,
provider request IDs, query values, headers, bodies, or local source paths. A
management version pin is an expectation, not server evidence. Timestamp matching
uses the client's recorded interval (zero tolerance by default); no nearest-event
or method/path fallback is permitted when a Ray is absent or ambiguous.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from urllib.parse import urlsplit

UUID = re.compile(r"[0-9a-f]{8}(?:-[0-9a-f]{4}){3}-[0-9a-f]{12}")
RAY = re.compile(r"([0-9a-f]{16,32})(?:-[A-Z0-9]{3,10})?", re.IGNORECASE)
JOURNAL = re.compile(r"request-([0-9]{2,3})\.(pending|started|headers|completed)\.private\.json")
METHODS = {"GET", "HEAD", "POST", "PUT", "DELETE"}
MAX_FILE_BYTES = 128 * 1024 * 1024


class InputError(ValueError):
    """Only fixed error codes, never input content, may be exposed by the CLI."""


def need(condition, code):
    if not condition:
        raise InputError(code)


def unique_object(pairs):
    result = {}
    for key, value in pairs:
        need(key not in result, "duplicate_json_key")
        result[key] = value
    return result


class Sources:
    def __init__(self):
        self.receipts = []

    def read(self, path, label):
        path = Path(path)
        need(path.is_file() and not path.is_symlink(), "input_file_missing_or_link")
        need(path.stat().st_size <= MAX_FILE_BYTES, "input_file_too_large")
        raw = path.read_bytes()
        try:
            value = json.loads(raw.decode("utf-8-sig"), object_pairs_hook=unique_object,
                               parse_constant=lambda _: (_ for _ in ()).throw(InputError("nonfinite_json")))
        except (UnicodeError, json.JSONDecodeError) as exc:
            raise InputError("invalid_json") from exc
        self.receipts.append({"input": label, "bytes": len(raw), "sha256": hashlib.sha256(raw).hexdigest()})
        return value


def stamp(value):
    need(isinstance(value, str), "timestamp_missing_or_invalid")
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError as exc:
        raise InputError("timestamp_missing_or_invalid") from exc
    need(parsed.tzinfo is not None, "timestamp_timezone_required")
    return parsed.astimezone(UTC)


def version(value):
    need(isinstance(value, str) and UUID.fullmatch(value), "version_pin_invalid")
    return value


def ray(value):
    match = RAY.fullmatch(value) if isinstance(value, str) else None
    return match.group(1).lower() if match else None


def target(value, absolute=False):
    need(isinstance(value, str) and len(value) <= 4096, "request_target_invalid")
    parsed = urlsplit(value)
    if absolute:
        need(parsed.scheme in {"https", "http"} and parsed.netloc, "request_target_invalid")
    else:
        need(value.startswith("/") and not value.startswith("//") and not parsed.scheme and not parsed.netloc,
             "request_target_invalid")
    need(not parsed.fragment and not parsed.username and not parsed.password, "request_target_invalid")
    return parsed.path, parsed.query


@dataclass(frozen=True)
class Request:
    key: str
    method: str
    path: str
    query: str
    started: datetime
    finished: datetime | None
    status: int | None
    ray: str | None
    version: str
    complete: bool


def request(key, row, *, browser=False, prefix_publish=False, expected_version=None, completed=True):
    need(isinstance(row, dict), "client_row_invalid")
    method = row.get("method")
    need(method in METHODS, "client_method_invalid")
    path, query = target(row.get("path"))
    if prefix_publish:
        need(path.startswith("/v1/"), "stage3_logical_path_invalid")
        path = "/_publish" + path
    pin = row.get("version_pin") if browser else row.get("expected_deployment_version")
    if expected_version is not None:
        need(pin is None or pin == expected_version, "client_version_pin_conflict")
        pin = expected_version
    pin = version(pin)
    exchange = row.get("exchange", {})
    need(isinstance(exchange, dict), "client_exchange_invalid")
    start = row.get("started_at") if browser else exchange.get("started_utc", row.get("started_utc"))
    end = row.get("finished_at") if browser else exchange.get("headers_received_utc", row.get("finished_utc"))
    started = stamp(start)
    finished = stamp(end) if end else None
    need(finished is None or finished >= started, "client_time_interval_invalid")
    status = row.get("status") if browser else exchange.get("status", row.get("status"))
    need(status is None or (type(status) is int and 100 <= status <= 599), "client_status_invalid")
    response_ray = row.get("cf_ray") if browser else exchange.get("ray", row.get("ray"))
    complete = bool(completed and finished is not None and status is not None)
    if browser:
        complete = complete and row.get("state") == "completed"
    else:
        complete = complete and row.get("outcome") not in {"unknown", "pending"}
    return Request(key, method, path, query, started, finished, status, ray(response_ray), pin, complete)


def journals(directory, phase, sources, *, browser=False, stage3_pin=None):
    directory = Path(directory)
    need(directory.is_dir() and not directory.is_symlink(), "journal_directory_missing_or_link")
    groups = defaultdict(dict)
    for file in directory.glob("request-*.private.json"):
        match = JOURNAL.fullmatch(file.name)
        need(match is not None, "journal_filename_invalid")
        number, kind = int(match[1]), match[2]
        need(kind not in groups[number], "duplicate_client_journal")
        groups[number][kind] = file
    need(groups, "request_journals_missing")
    need(sorted(groups) == list(range(1, len(groups) + 1)), "client_sequence_gap")
    result = []
    for number, files in sorted(groups.items()):
        values = {kind: sources.read(file, f"{phase}-{number:03d}-{kind}") for kind, file in sorted(files.items())}
        begin = values.get("pending" if stage3_pin else "started")
        need(isinstance(begin, dict), "client_start_journal_missing")
        for kind, row in values.items():
            need(isinstance(row, dict), "client_row_invalid")
            field = "number" if browser else "sequence"
            need(row.get(field) == number, "client_sequence_conflict")
            if kind != "headers":
                need(row.get("method") == begin.get("method") and row.get("path") == begin.get("path"),
                     "client_identity_conflict")
                if not stage3_pin:
                    pin_field = "version_pin" if browser else "expected_deployment_version"
                    need(row.get(pin_field) == begin.get(pin_field), "client_version_pin_conflict")
                    time_field = "started_at" if browser else "started_utc"
                    need(row.get(time_field) == begin.get(time_field), "client_start_time_conflict")
        chosen = values.get("completed", begin)
        if browser and "completed" in values:
            headers = values.get("headers")
            if chosen.get("completion_basis") == "bodyless_304_headers_before_client_abort":
                need(isinstance(headers, dict) and headers.get("response_header_status") == 304 and
                     chosen.get("status") == 304 and chosen.get("failure_code") == "net::ERR_ABORTED" and
                     chosen.get("method") in {"GET", "HEAD"}, "bodyless_304_header_evidence_missing")
            if headers and chosen.get("state") == "completed":
                need(headers.get("response_header_status") == chosen.get("status") and
                     ray(headers.get("response_header_cf_ray")) == ray(chosen.get("cf_ray")),
                     "browser_header_completion_conflict")
                need(stamp(begin.get("started_at")) <= stamp(headers.get("response_headers_at")) <=
                     stamp(chosen.get("finished_at")), "browser_header_time_conflict")
        result.append(request(f"{phase}-{number:03d}", chosen, browser=browser,
                              prefix_publish=bool(stage3_pin), expected_version=stage3_pin,
                              completed="completed" in values))
    return result


def load_stage3(directory, receipt_path, sources):
    """Use upload-ON version for twelve requests, OFF version for closing HEAD."""
    receipt = sources.read(receipt_path, "stage3-management-summary")
    need(isinstance(receipt, dict) and receipt.get("service_requests") == 13, "stage3_summary_invalid")
    on, off = version(receipt.get("upload_on_version")), version(receipt.get("upload_off_version"))
    rows = journals(Path(directory) / "upload-run", "stage3-upload", sources, stage3_pin=on)
    need(len(rows) <= 12, "stage3_request_budget_exceeded")
    # A partial run stays visibly incomplete rather than being promoted by a summary.
    need(len(rows) == 12, "stage3_upload_journal_incomplete")
    closing = sources.read(Path(directory) / "closing-head.private.json", "stage3-closing-head")
    need(closing.get("method") == "HEAD" and closing.get("path") == "/_publish/v1/health.json",
         "stage3_closing_target_invalid")
    rows.append(request("stage3-closing-001", closing, expected_version=off))
    return rows


def load_stage4(directory, sources):
    rows, synthetic_count = [], 0
    for phase in ("read", "browser", "notice"):
        phase_dir = Path(directory) / phase
        rows.extend(journals(phase_dir, "stage4-" + phase, sources, browser=phase == "browser"))
        for number, file in enumerate(sorted(phase_dir.glob("synthetic-*.private.json")), 1):
            row = sources.read(file, f"stage4-{phase}-synthetic-{number:03d}")
            need(row.get("remote_request") is False and
                 row.get("evidence_kind") == "browser_intercepted_synthetic_response", "synthetic_record_invalid")
            synthetic_count += 1
    return rows, synthetic_count


def server_event(row):
    """Exact Cloudflare dashboard export layout validated against stage2 export."""
    need(isinstance(row, dict), "server_record_invalid")
    workers, meta = row.get("$workers"), row.get("$metadata")
    need(isinstance(workers, dict), "server_worker_metadata_missing")
    event = workers.get("event", {})
    need(isinstance(event, dict), "server_event_invalid")
    req = event.get("request")
    if req is None:
        return None  # cron/non-HTTP events are explicitly counted, not matched.
    need(isinstance(req, dict) and isinstance(meta, dict), "server_http_metadata_missing")
    path, query = target(req.get("url"), absolute=True)
    headers, response = req.get("headers", {}), event.get("response", {})
    need(isinstance(headers, dict) and isinstance(response, dict), "server_http_metadata_missing")
    header_ray = ray(next((v for k, v in headers.items() if k.lower() == "cf-ray"), None))
    metadata_ray = ray(meta.get("rayId"))
    need(header_ray is not None, "server_ray_missing")
    provider_id = meta.get("requestId")
    need(isinstance(provider_id, str) and 0 < len(provider_id) <= 256, "server_request_id_missing")
    status = response.get("status")
    need(type(status) is int and 100 <= status <= 599 and req.get("method") in METHODS, "server_http_value_invalid")
    ver = workers.get("scriptVersion")
    need(isinstance(ver, dict), "server_version_missing")
    return {"ray": header_ray, "metadata_ray": metadata_ray, "provider_id": provider_id,
            "method": req["method"], "path": path, "query": query, "status": status,
            "version": version(ver.get("id")), "timestamp": stamp(row.get("timestamp")),
            "outcome_ok": workers.get("outcome") == "ok", "not_truncated": workers.get("truncated") is False}


def correlate(clients, raw_events, *, tolerance_ms=0, synthetic_count=0, source_receipts=()):
    need(type(tolerance_ms) is int and 0 <= tolerance_ms <= 5000, "timestamp_tolerance_invalid")
    need(clients and len({c.key for c in clients}) == len(clients), "client_ids_empty_or_duplicate")
    need(isinstance(raw_events, list), "server_export_must_be_array")
    events, non_http, malformed = [], 0, 0
    for raw in raw_events:
        try:
            event = server_event(raw)
            if event is None:
                non_http += 1
            else:
                events.append(event)
        except (InputError, TypeError, AttributeError):
            malformed += 1
    by_ray = defaultdict(list)
    for index, event in enumerate(events):
        by_ray[event["ray"]].append((index, event))
    client_rays = Counter(c.ray for c in clients if c.ray)
    provider_ids = Counter(e["provider_id"] for e in events)
    matched_indices, results = set(), []
    delta = timedelta(milliseconds=tolerance_ms)
    for client in clients:
        row = {"request": client.key, "expected_version": client.version,
               "version_expectation_source": "management_pin_not_server_evidence",
               "server_version": None, "result": None, "checks": {}, "problems": []}
        if not client.complete:
            row["result"] = "incomplete_client"
        elif client.ray is None:
            row["result"] = "missing_client_ray"
        elif client_rays[client.ray] != 1:
            row["result"] = "duplicate_client_ray"
        elif len(by_ray[client.ray]) == 0:
            row["result"] = "missing_server_event"
        elif len(by_ray[client.ray]) != 1:
            row["result"] = "duplicate_server_ray"
        else:
            index, server = by_ray[client.ray][0]
            matched_indices.add(index)
            row["server_version"] = server["version"]
            row["checks"] = {
                "ray_fields_agree": server["metadata_ray"] == client.ray,
                "unique_provider_request_id": provider_ids[server["provider_id"]] == 1,
                "method": server["method"] == client.method,
                "path_and_query": (server["path"], server["query"]) == (client.path, client.query),
                "status": server["status"] == client.status,
                "version": server["version"] == client.version,
                "utc_within_client_interval": client.started - delta <= server["timestamp"] <= client.finished + delta,
                "outcome_ok": server["outcome_ok"], "not_truncated": server["not_truncated"],
            }
            row["problems"] = [key for key, passed in row["checks"].items() if not passed]
            row["result"] = "matched" if not row["problems"] else "mismatch"
        results.append(row)
    counts = dict(sorted(Counter(r["result"] for r in results).items()))
    return {
        "schema": "pitcheezy-stage34-server-log-correlation-v1",
        "evidence_kind": "offline_client_and_exported_server_event_comparison",
        "passed": counts.get("matched", 0) == len(clients) and malformed == 0,
        "matching_rule": "unique_response_ray_only_no_time_or_path_fallback",
        "timestamp_tolerance_ms": tolerance_ms,
        "counts": {"client_remote_requests": len(clients), "synthetic_nonremote_excluded": synthetic_count,
                   "server_http_events": len(events), "server_nonhttp_excluded": non_http,
                   "server_malformed_records": malformed, "server_unmatched_events": len(events) - len(matched_indices),
                   "duplicate_server_ray_groups": sum(len(group) > 1 for group in by_ray.values()),
                   "duplicate_provider_request_id_groups": sum(n > 1 for n in provider_ids.values()),
                   "client_results": counts},
        "source_integrity": list(source_receipts), "requests": results,
        "limits": ["client_version_pin_is_not_server_evidence_without_matching_event",
                   "does_not_prove_body_bytes_authentication_or_ui_acceptance",
                   "unmatched_extra_events_are_not_reassigned_to_client_requests"],
    }


def inside_private(path, root):
    resolved, boundary = Path(path).resolve(strict=True), Path(root).resolve(strict=True)
    need(resolved.is_relative_to(boundary), "private_input_outside_root")
    return resolved


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", required=True)
    parser.add_argument("--logs", required=True, action="append")
    parser.add_argument("--stage3")
    parser.add_argument("--stage3-receipt")
    parser.add_argument("--stage4")
    parser.add_argument("--timestamp-tolerance-ms", type=int, default=0)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        need(bool(args.stage3 or args.stage4), "no_client_journals_requested")
        need(bool(args.stage3) == bool(args.stage3_receipt), "stage3_receipt_required")
        output = Path(args.output)
        need(not output.exists(), "output_exists_do_not_overwrite")
        sources, clients, events, synthetic = Sources(), [], [], 0
        for number, file in enumerate(args.logs, 1):
            raw = sources.read(inside_private(file, args.private_root), f"server-export-{number:03d}")
            need(isinstance(raw, list), "server_export_must_be_array")
            events.extend(raw)  # overlapping exports intentionally remain duplicate evidence.
        if args.stage3:
            clients.extend(load_stage3(inside_private(args.stage3, args.private_root), args.stage3_receipt, sources))
        if args.stage4:
            loaded, synthetic = load_stage4(inside_private(args.stage4, args.private_root), sources)
            clients.extend(loaded)
        report = correlate(clients, events, tolerance_ms=args.timestamp_tolerance_ms,
                           synthetic_count=synthetic, source_receipts=sources.receipts)
        with output.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, ensure_ascii=True, indent=2)
            handle.write("\n")
        print(json.dumps({"passed": report["passed"], "counts": report["counts"]}))
        return 0 if report["passed"] else 1
    except (InputError, OSError, ValueError, TypeError) as exc:
        # Never stringify arbitrary exceptions: OS errors can contain private paths.
        code = str(exc) if isinstance(exc, InputError) else "input_or_output_failed"
        print(json.dumps({"passed": False, "error": code}))
        return 2


if __name__ == "__main__":
    sys.exit(main())

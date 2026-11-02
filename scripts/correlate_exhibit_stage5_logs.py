"""Offline stage5 public-app cutover ledger-to-Workers-log correlation; never contacts a server.

Inputs stay private. The output is an allowlisted receipt with no hostnames, Rays,
provider request IDs, query values, headers, bodies, or local source paths. The fixed
24-request client ledger is validated first (count, completion, distinct Rays, one
version pin, result/cycle agreement); ``--ledger-only`` writes that precheck without
server evidence, and a full run reuses the stage3/4 ``correlate`` rule (unique response
Ray only, zero tolerance by default, no time or path fallback). Extra server events,
such as the user's phone requests, are counted and never reassigned or trimmed.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from collections import Counter
from pathlib import Path


def load_stage34():
    file = Path(__file__).resolve().parent / "correlate_exhibit_stage34_logs.py"
    spec = importlib.util.spec_from_file_location("exhibit_stage34_logs", file)
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


stage34 = load_stage34()
InputError, need = stage34.InputError, stage34.need
PHASE, LEDGER_COUNT = "stage5-cutover", 24
PRECHECK_SCHEMA = "pitcheezy-stage5-ledger-precheck-v1"
FULL_SCHEMA = "pitcheezy-stage5-server-log-correlation-v1"


def load_ledger(round_dir, sources):
    rows = stage34.journals(round_dir / "cutover" / "requests", PHASE, sources)
    need(len(rows) == LEDGER_COUNT, "stage5_ledger_count_invalid")
    need(all(row.complete for row in rows), "stage5_ledger_incomplete")
    need(len({row.ray for row in rows if row.ray}) == LEDGER_COUNT, "stage5_ledger_ray_invalid")
    pins = {row.version for row in rows}
    need(len(pins) == 1, "stage5_ledger_version_pin_invalid")
    pin = pins.pop()
    cycle = sources.read(round_dir / "cycle.private.json", "stage5-cycle")
    result = sources.read(round_dir / "cutover" / "result.private.json", "stage5-result")
    need(isinstance(cycle, dict) and isinstance(result, dict), "stage5_round_record_invalid")
    need(result.get("passed") is True and result.get("service_requests") == LEDGER_COUNT,
         "stage5_result_not_passed")
    need(result.get("version_pin") == cycle.get("cutover_version_pin") == pin, "stage5_version_pin_conflict")
    sha = result.get("input_sha256")
    need(isinstance(sha, str) and sha == cycle.get("cutover_input_sha256"), "stage5_input_sha_conflict")
    return rows, pin


def iso(value):
    return value.isoformat(timespec="milliseconds").replace("+00:00", "Z")


def ledger_block(rows, pin):
    """Public-safe aggregate: counts, pin and UTC window only; no paths, queries or Rays."""
    return {
        "client_requests": len(rows), "version_pin": pin,
        "window_utc": {"first_started": iso(min(row.started for row in rows)),
                       "last_finished": iso(max(row.finished for row in rows))},
        "method_counts": dict(sorted(Counter(row.method for row in rows).items())),
        "status_counts": {str(status): n for status, n in sorted(Counter(row.status for row in rows).items())},
        "distinct_paths": len({row.path for row in rows}),
    }


def precheck(ledger, receipts):
    return {
        "schema": PRECHECK_SCHEMA,
        "evidence_kind": "offline_client_ledger_precheck_without_server_export",
        "passed": True, "server_logs": "not_received", "ledger": ledger,
        "source_integrity": list(receipts),
        "limits": ["client_ledger_without_server_export_is_not_server_evidence",
                   "management_version_pin_is_not_server_evidence",
                   "does_not_prove_body_bytes_authentication_or_ui_acceptance"],
    }


def full(rows, ledger, args, sources):
    events = []
    for number, file in enumerate(args.logs, 1):
        raw = sources.read(stage34.inside_private(file, args.private_root), f"server-export-{number:03d}")
        need(isinstance(raw, list), "server_export_must_be_array")
        events.extend(raw)  # overlapping exports intentionally remain duplicate evidence.
    report = stage34.correlate(rows, events, tolerance_ms=args.timestamp_tolerance_ms,
                               synthetic_count=0, source_receipts=sources.receipts)
    report["schema"] = FULL_SCHEMA
    report["ledger"] = ledger
    report["extra_server_events_not_reassigned"] = report["counts"]["server_unmatched_events"]
    report["limits"].extend(["extra_events_such_as_user_phone_requests_are_counted_not_matched",
                             "management_version_pin_confirmed_only_per_matched_event"])
    return report


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--private-root", required=True)
    parser.add_argument("--round", required=True)
    parser.add_argument("--logs", action="append", default=[])
    parser.add_argument("--ledger-only", action="store_true")
    parser.add_argument("--timestamp-tolerance-ms", type=int, default=0)
    parser.add_argument("--output", required=True)
    args = parser.parse_args(argv)
    try:
        output = Path(args.output)
        need(not output.exists(), "output_exists_do_not_overwrite")
        if args.ledger_only:
            need(not args.logs, "ledger_only_takes_no_logs")
        else:
            need(bool(args.logs), "server_export_required")
        sources = stage34.Sources()
        rows, pin = load_ledger(stage34.inside_private(args.round, args.private_root), sources)
        ledger = ledger_block(rows, pin)
        report = precheck(ledger, sources.receipts) if args.ledger_only else full(rows, ledger, args, sources)
        with output.open("x", encoding="utf-8", newline="\n") as handle:
            json.dump(report, handle, ensure_ascii=True, indent=2)
            handle.write("\n")
        summary = {"passed": report["passed"], "ledger": report["ledger"]}
        if "counts" in report:
            summary["counts"] = report["counts"]
        print(json.dumps(summary))
        return 0 if report["passed"] else 1
    except (InputError, OSError, ValueError, TypeError) as exc:
        # Never stringify arbitrary exceptions: OS errors can contain private paths.
        code = str(exc) if isinstance(exc, InputError) else "input_or_output_failed"
        print(json.dumps({"passed": False, "error": code}))
        return 2


if __name__ == "__main__":
    sys.exit(main())

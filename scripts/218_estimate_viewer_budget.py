"""Estimate a Workers Free daily request budget offline, without account or file access."""

import argparse
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from src.operations.viewer_budget import (  # noqa: E402
    SCHEMA,
    ViewerBudgetError,
    estimate,
    example_report,
)


def integer_argument(value):
    """Parse a bounded-length decimal integer without reflecting arbitrary input."""
    if not value.isascii() or not value.isdecimal() or len(value) > 9:
        raise argparse.ArgumentTypeError("decimal_integer_required")
    return int(value)


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--examples", action="store_true", help="Print 30/50-viewer, three-hour polling-only cases."
    )
    parser.add_argument("--viewers", type=integer_argument, help="Concurrent viewers, 1..50.")
    parser.add_argument("--duration-seconds", type=integer_argument, help="Duration, 1..86400.")
    parser.add_argument("--poll-seconds", type=integer_argument, help="Polling interval, 1..3600.")
    parser.add_argument("--objects-per-poll", type=integer_argument, help="Worker requests, 1..10.")
    parser.add_argument(
        "--extra-worker-requests",
        type=integer_argument,
        help="Additional event requests, 0..100000000; omitted means excluded (zero).",
    )
    parser.add_argument(
        "--other-account-requests",
        type=integer_argument,
        help="Other same-UTC-day account requests, 0..100000000; omitted means unknown.",
    )
    args = parser.parse_args(argv)
    fields = (
        "viewers",
        "duration_seconds",
        "poll_seconds",
        "objects_per_poll",
        "extra_worker_requests",
        "other_account_requests",
    )
    if args.examples:
        if any(getattr(args, field) is not None for field in fields):
            parser.error("examples_cannot_be_combined_with_scenario_arguments")
        result = example_report()
    else:
        if any(getattr(args, field) is None for field in fields[:4]):
            parser.error("viewers_duration_poll_and_objects_are_required")
        scenario = {"schema": SCHEMA, **{field: getattr(args, field) for field in fields}}
        if scenario["extra_worker_requests"] is None:
            scenario["extra_worker_requests"] = 0
        try:
            result = estimate(scenario)
        except ViewerBudgetError as error:
            print(json.dumps({"ok": False, "error": str(error)}))
            return 2
    print(json.dumps(result, indent=2, allow_nan=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

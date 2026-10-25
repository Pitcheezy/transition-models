"""Offline Workers Free daily-request estimates, never measured capacity or approval."""

SCHEMA = "pitcheezy-viewer-budget-scenario-v1"
REPORT_SCHEMA = "pitcheezy-viewer-budget-estimate-v1"
LIMITS_AS_OF = "2026-10-25"
FREE_DAILY_REQUEST_LIMIT = 100_000
SOURCE = "https://developers.cloudflare.com/workers/platform/limits/"
FIELD_BOUNDS = {
    "viewers": (1, 50),
    "duration_seconds": (1, 86_400),
    "poll_seconds": (1, 3_600),
    "objects_per_poll": (1, 10),
    "extra_worker_requests": (0, 100_000_000),
    "other_account_requests": (0, 100_000_000),
}
ASSUMPTIONS = (
    "Each viewer polls immediately at time zero, then at each interval in [0, duration_seconds).",
    "Every viewer stays for the full duration; each object poll invokes one Worker request.",
    "All requests are assigned to one UTC budget day; no cross-midnight reset credit is assumed.",
    "extra_worker_requests is the total additional event traffic, not a per-viewer number.",
    "Login, assets served through Workers, monitoring, publisher requests and retries must be "
    "included in extra_worker_requests; zero excludes all of them from this estimate.",
    "other_account_requests covers all other requests on the account in the same UTC budget "
    "day, including expected later traffic; null means unknown, not zero.",
    "A 304 response or cache hit still counts when the request invokes a Worker; no cache "
    "discount is applied.",
    "The estimate does not measure load, latency, CPU, storage or account usage and is not "
    "launch approval.",
)


class ViewerBudgetError(ValueError):
    """A fixed validation diagnostic that never echoes scenario input."""


def estimate(scenario):
    """Estimate integer requests under an exact, versioned single-budget-day schema."""
    if type(scenario) is not dict or set(scenario) != {"schema", *FIELD_BOUNDS}:
        raise ViewerBudgetError("invalid_scenario_fields")
    if scenario["schema"] != SCHEMA:
        raise ViewerBudgetError("unsupported_schema")
    for field, (minimum, maximum) in FIELD_BOUNDS.items():
        value = scenario[field]
        if field == "other_account_requests" and value is None:
            continue
        # bool, float (including NaN/Infinity), Decimal and strings are not schema integers.
        if type(value) is not int or not minimum <= value <= maximum:
            raise ViewerBudgetError(f"invalid_{field}")

    duration = scenario["duration_seconds"]
    interval = scenario["poll_seconds"]
    polls_per_viewer = (duration + interval - 1) // interval
    polling_requests = polls_per_viewer * scenario["viewers"] * scenario["objects_per_poll"]
    event_requests = polling_requests + scenario["extra_worker_requests"]
    other_requests = scenario["other_account_requests"]
    known_requests = event_requests + (other_requests if other_requests is not None else 0)
    headroom = None if other_requests is None else max(0, FREE_DAILY_REQUEST_LIMIT - known_requests)
    if known_requests > FREE_DAILY_REQUEST_LIMIT:
        status = "exceeds_known_budget"
    elif other_requests is None:
        status = "headroom_unknown"
    elif known_requests == FREE_DAILY_REQUEST_LIMIT:
        status = "at_estimated_daily_limit"
    else:
        status = "within_estimated_daily_limit"
    return {
        "schema": REPORT_SCHEMA,
        "plan": "Workers Free",
        "limits_as_of": LIMITS_AS_OF,
        "source": SOURCE,
        "estimated": True,
        "measurement": False,
        "launch_ready": False,
        "daily_limit_requests": FREE_DAILY_REQUEST_LIMIT,
        "limit_scope": "account_wide",
        "reset_utc": "00:00",
        "reset_kst": "09:00",
        "limit_exceeded_error": 1027,
        "scenario": dict(scenario),
        "polls_per_viewer": polls_per_viewer,
        "polling_worker_requests": polling_requests,
        "estimated_event_worker_requests": event_requests,
        "known_account_request_lower_bound": known_requests,
        "estimated_account_worker_requests": known_requests if other_requests is not None else None,
        "headroom_requests": headroom,
        "known_excess_requests": max(0, known_requests - FREE_DAILY_REQUEST_LIMIT),
        "budget_status": status,
        "assumptions": list(ASSUMPTIONS),
    }


def example_report():
    """Return polling-only 30/50-viewer examples with explicitly unknown account usage."""
    scenarios = []
    for viewers in (30, 50):
        for interval, objects in ((5, 2), (15, 2), (1, 1)):
            scenarios.append(
                estimate(
                    {
                        "schema": SCHEMA,
                        "viewers": viewers,
                        "duration_seconds": 10_800,
                        "poll_seconds": interval,
                        "objects_per_poll": objects,
                        "extra_worker_requests": 0,
                        "other_account_requests": None,
                    }
                )
            )
    return {
        "schema": "pitcheezy-viewer-budget-examples-v1",
        "description": "Three-hour polling-only estimates; all additional event traffic excluded.",
        "estimated": True,
        "measurement": False,
        "launch_ready": False,
        "scenarios": scenarios,
    }

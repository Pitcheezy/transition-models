"""Explicit scenario arithmetic, not a quote, traffic measurement, or spending cap."""

import re
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal

PRICING_DATE = "2026-10-12"
MILLION = Decimal(1000000)
SOURCES = [
    "https://developers.cloudflare.com/workers/platform/pricing/",
    "https://developers.cloudflare.com/r2/pricing/",
    "https://developers.cloudflare.com/d1/platform/pricing/",
]
# allowance, dollars per unit, unit size, round excess up to whole units
RATES = {
    "worker_requests": (10000000, "0.30", 1000000, False),
    "worker_cpu_ms": (30000000, "0.02", 1000000, False),
    "r2_class_a": (1000000, "4.50", 1000000, True),
    "r2_class_b": (10000000, "0.36", 1000000, True),
    "r2_storage_gb_month": (10, "0.015", 1, True),
    "d1_rows_read": (25000000000, "0.001", 1000000, False),
    "d1_rows_written": (50000000, "1.00", 1000000, False),
    "d1_storage_gb_month": (5, "0.75", 1, False),
}
FIELDS = {
    "viewer_hours",
    "peak_viewers",
    "poll_seconds",
    "objects_per_poll",
    "extra_worker_requests",
    "publisher_puts",
    "publisher_deletes",
    "publisher_heads",
    "extra_r2_reads",
    "mean_cpu_ms",
    "mean_json_bytes",
    "r2_storage_gb_month",
    "d1_rows_read",
    "d1_rows_written",
    "d1_storage_gb_month",
}
INTEGER_FIELDS = {
    "peak_viewers",
    "objects_per_poll",
    "extra_worker_requests",
    "publisher_puts",
    "publisher_deletes",
    "publisher_heads",
    "extra_r2_reads",
    "mean_json_bytes",
    "d1_rows_read",
    "d1_rows_written",
}


class EstimateError(ValueError):
    """Fixed diagnostic; do not echo private input."""


def number(value):
    if type(value) not in (int, float, Decimal):
        raise EstimateError("numeric_value_required")
    result = Decimal(str(value))
    if not result.is_finite() or not 0 <= result <= Decimal("1e15"):
        raise EstimateError("numeric_value_out_of_range")
    return result


def rounded(value, places="0.01"):
    return str(value.quantize(Decimal(places), rounding=ROUND_HALF_UP))


def price(usage, *, allowances_available):
    """Compute a full-month paid-plan scenario, not incremental account billing."""
    if set(usage) != set(RATES) or type(allowances_available) is not bool:
        raise EstimateError("invalid_usage")
    charges = {}
    total = Decimal(5)
    for field, (included, rate, unit, ceil_units) in RATES.items():
        amount = number(usage[field])
        excess = max(Decimal(0), amount - (included if allowances_available else 0))
        units = excess / unit
        if ceil_units:
            units = units.to_integral_value(rounding=ROUND_CEILING)
        charge = units * Decimal(rate)
        charges[field] = rounded(charge, "0.000001")
        total += charge
    return {"base_usd": "5.00", "charges_usd": charges, "subtotal_usd": rounded(total)}


def estimate(scenario):
    if not isinstance(scenario, dict) or set(scenario) != FIELDS | {"name"}:
        raise EstimateError("invalid_scenario_fields")
    if not isinstance(scenario["name"], str) or not re.fullmatch(
        r"[a-z0-9][a-z0-9_-]{0,63}", scenario["name"]
    ):
        raise EstimateError("invalid_scenario_name")
    values = {key: number(scenario[key]) for key in FIELDS}
    for key in INTEGER_FIELDS:
        if values[key] != values[key].to_integral_value():
            raise EstimateError("integer_required")
    if not Decimal("0.1") <= values["poll_seconds"] <= 3600:
        raise EstimateError("invalid_poll_interval")
    if not 1 <= values["objects_per_poll"] <= 100:
        raise EstimateError("invalid_objects_per_poll")
    if not 1 <= values["mean_json_bytes"] <= 5 * 1024 * 1024:
        raise EstimateError("invalid_payload_size")
    # This is aggregate viewer-time arithmetic, not per-session/initial-load reconstruction.
    data_reads = (
        values["viewer_hours"] * 3600 * values["objects_per_poll"] / values["poll_seconds"]
    ).to_integral_value(rounding=ROUND_CEILING)
    writes = values["publisher_puts"] + values["publisher_deletes"]
    requests = data_reads + values["extra_worker_requests"] + writes + values["publisher_heads"]
    usage = {
        "worker_requests": requests,
        "worker_cpu_ms": requests * values["mean_cpu_ms"],
        "r2_class_a": writes,
        "r2_class_b": data_reads + values["publisher_heads"] + values["extra_r2_reads"],
        **{
            key: values[key]
            for key in (
                "r2_storage_gb_month",
                "d1_rows_read",
                "d1_rows_written",
                "d1_storage_gb_month",
            )
        },
    }
    costs = {
        "allowances_available": price(usage, allowances_available=True),
        "allowances_exhausted_sensitivity": price(usage, allowances_available=False),
    }
    return {
        "name": scenario["name"],
        "public_reads": int(data_reads),
        "peak_public_requests_per_second": rounded(
            values["peak_viewers"] * values["objects_per_poll"] / values["poll_seconds"], "0.001"
        ),
        "public_json_transfer_gb": rounded(data_reads * values["mean_json_bytes"] / 1000000000),
        "usage": {key: str(value) for key, value in usage.items()},
        "costs": costs,
    }


def report(document):
    if not isinstance(document, dict) or set(document) != {"schema", "scenarios"}:
        raise EstimateError("invalid_document")
    if document["schema"] != "pitcheezy-cost-scenarios-v1":
        raise EstimateError("unsupported_schema")
    scenarios = document["scenarios"]
    if not isinstance(scenarios, list) or not 1 <= len(scenarios) <= 20:
        raise EstimateError("invalid_scenarios")
    results = [estimate(scenario) for scenario in scenarios]
    if len({row["name"] for row in results}) != len(results):
        raise EstimateError("duplicate_scenario")
    return {
        "schema": "pitcheezy-host-cost-estimate-v1",
        "pricing_as_of": PRICING_DATE,
        "currency": "USD",
        "plan": "Workers Paid Standard + R2 Standard + D1 Paid",
        "measurement": False,
        "budget_approved": False,
        "sources": SOURCES,
        "exclusions": [
            "taxes_and_exchange_rates",
            "domain_and_other_products",
            "logs_and_alerts",
            "unmodeled_traffic_and_retries",
            "actual_account_usage_and_contract",
        ],
        "scenarios": results,
    }

"""Independent arithmetic examples and error cases for operating cost assumptions."""

import json
import subprocess
import sys
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest

from src.operations.host_cost import RATES, EstimateError, estimate, price, report

ROOT = Path(__file__).resolve().parents[1]


def usage(**updates):
    value = {key: 0 for key in RATES}
    value.update(updates)
    return value


def scenario(**updates):
    result = {
        "name": "small",
        "viewer_hours": 2100,
        "peak_viewers": 300,
        "poll_seconds": 5,
        "objects_per_poll": 2,
        "extra_worker_requests": 50000,
        "publisher_puts": 10000,
        "publisher_deletes": 10,
        "publisher_heads": 10010,
        "extra_r2_reads": 2000,
        "mean_cpu_ms": 5,
        "mean_json_bytes": 32768,
        "r2_storage_gb_month": 1,
        "d1_rows_read": 0,
        "d1_rows_written": 0,
        "d1_storage_gb_month": 0,
    }
    result.update(updates)
    return result


def test_workers_official_fifteen_million_example_is_eight_dollars():
    result = price(
        usage(worker_requests=15000000, worker_cpu_ms=105000000), allowances_available=True
    )
    assert result["subtotal_usd"] == "8.00"
    assert result["charges_usd"]["worker_requests"] == "1.500000"
    assert result["charges_usd"]["worker_cpu_ms"] == "1.500000"


def test_r2_whole_billing_units_and_allowance_boundary():
    exact = usage(r2_class_a=1000000, r2_class_b=10000000, r2_storage_gb_month=10)
    assert price(exact, allowances_available=True)["subtotal_usd"] == "5.00"
    excess = usage(r2_class_a=1000001, r2_class_b=10000001, r2_storage_gb_month=Decimal("10.1"))
    value = price(excess, allowances_available=True)
    assert value["subtotal_usd"] == "9.88"
    assert value["charges_usd"]["r2_storage_gb_month"] == "0.015000"


def test_r2_official_storage_example():
    result = price(
        usage(r2_storage_gb_month=1000, r2_class_a=1000, r2_class_b=1000000),
        allowances_available=True,
    )
    assert result["charges_usd"]["r2_storage_gb_month"] == "14.850000"


def test_d1_uses_rows_not_events_and_no_worker_allowance_reuse():
    result = price(
        usage(d1_rows_read=25001000000, d1_rows_written=51000000, d1_storage_gb_month=6),
        allowances_available=True,
    )
    assert result["charges_usd"]["d1_rows_read"] == "0.001000"
    assert result["subtotal_usd"] == "6.75"


def test_audience_math_and_tombstone_put_are_explicit():
    result = estimate(scenario())
    assert result["public_reads"] == 3024000
    assert result["peak_public_requests_per_second"] == "120.000"
    assert result["public_json_transfer_gb"] == "99.09"
    assert result["usage"]["worker_requests"] == "3094020"
    assert result["usage"]["r2_class_a"] == "10010"
    assert result["usage"]["r2_class_b"] == "3036010"
    assert result["costs"]["allowances_available"]["subtotal_usd"] == "5.00"


def test_faster_polling_multiplies_load_not_capacity_claim():
    slow = estimate(scenario())
    fast = estimate(scenario(poll_seconds=1))
    assert fast["public_reads"] == slow["public_reads"] * 5
    assert Decimal(fast["peak_public_requests_per_second"]) == Decimal("600")
    assert Decimal(fast["costs"]["allowances_available"]["subtotal_usd"]) > 5


def test_exhausted_allowance_is_separate_sensitivity():
    result = price(usage(r2_class_a=1), allowances_available=False)
    assert result["subtotal_usd"] == "9.50"  # whole class-A unit + monthly base
    assert price(usage(), allowances_available=False)["subtotal_usd"] == "5.00"


@pytest.mark.parametrize(
    ("key", "value"),
    [
        ("viewer_hours", True),
        ("viewer_hours", -1),
        ("viewer_hours", float("nan")),
        ("mean_cpu_ms", float("inf")),
        ("peak_viewers", 0.5),
        ("poll_seconds", 0),
        ("poll_seconds", 0.01),
        ("objects_per_poll", 0),
        ("objects_per_poll", 101),
        ("mean_json_bytes", 5242881),
        ("name", "private https://account.test"),
        ("mean_cpu_ms", "5"),
        ("d1_rows_read", 10**16),
    ],
)
def test_bad_assumptions_do_not_become_plausible_costs(key, value):
    with pytest.raises(EstimateError):
        estimate(scenario(**{key: value}))


def test_frozen_inputs_and_not_a_measurement():
    doc = {"schema": "pitcheezy-cost-scenarios-v1", "scenarios": [scenario()]}
    frozen = deepcopy(doc)
    result = report(doc)
    assert doc == frozen
    assert result["measurement"] is False and result["budget_approved"] is False
    assert result["pricing_as_of"] == "2026-10-12"
    assert json.dumps(result) == json.dumps(report(doc))


@pytest.mark.parametrize("cases", [[], [scenario()] * 2, [scenario()] * 21])
def test_ambiguous_or_unbounded_scenario_lists_are_refused(cases):
    with pytest.raises(EstimateError):
        report({"schema": "pitcheezy-cost-scenarios-v1", "scenarios": cases})


def test_cli_example_and_private_error_not_echoed(tmp_path):
    args = [sys.executable, "-B", "-S", str(ROOT / "scripts/estimate_public_host_cost.py")]
    source = ROOT / "ops/public-host/examples/cost-scenarios.json"
    output = subprocess.run([*args, str(source)], capture_output=True, text=True)
    assert output.returncode == 0, output.stderr
    assert len(json.loads(output.stdout)["scenarios"]) == 4
    private = tmp_path / "private-account.json"
    private.write_text('{"secret":"do-not-echo"}')
    output = subprocess.run([*args, str(private)], capture_output=True, text=True)
    assert output.returncode == 2
    assert "do-not-echo" not in output.stdout + output.stderr
    assert str(private) not in output.stdout + output.stderr

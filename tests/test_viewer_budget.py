"""Integer polling schedules, daily-account uncertainty and offline CLI regression tests."""

import json
import subprocess
import sys
from copy import deepcopy
from decimal import Decimal
from pathlib import Path

import pytest

from src.operations.viewer_budget import (
    FIELD_BOUNDS,
    SCHEMA,
    ViewerBudgetError,
    estimate,
    example_report,
)

ROOT = Path(__file__).resolve().parents[1]
CLI = ROOT / "scripts/218_estimate_viewer_budget.py"


def scenario(**updates):
    value = {
        "schema": SCHEMA,
        "viewers": 30,
        "duration_seconds": 10_800,
        "poll_seconds": 15,
        "objects_per_poll": 2,
        "extra_worker_requests": 0,
        "other_account_requests": None,
    }
    value.update(updates)
    return value


@pytest.mark.parametrize(
    ("duration", "interval", "expected_polls"),
    [
        (1, 1, 1),
        (1, 3600, 1),
        (5, 5, 1),
        (6, 5, 2),
        (9, 5, 2),
        (10, 5, 2),
        (11, 5, 3),
        (86_400, 3599, 25),
        (86_400, 3600, 24),
        (86_400, 1, 86_400),
    ],
)
def test_immediate_poll_and_exclusive_end_use_integer_ceiling(duration, interval, expected_polls):
    result = estimate(scenario(viewers=3, duration_seconds=duration, poll_seconds=interval))
    assert result["polls_per_viewer"] == expected_polls
    assert result["polling_worker_requests"] == expected_polls * 6


def test_each_viewer_rounds_before_aggregation():
    result = estimate(scenario(viewers=3, duration_seconds=1, poll_seconds=5))
    assert result["polling_worker_requests"] == 6
    assert result["estimated_event_worker_requests"] == 6


def test_three_hour_examples_match_independent_arithmetic():
    report = example_report()
    values = {
        (
            row["scenario"]["viewers"],
            row["scenario"]["poll_seconds"],
            row["scenario"]["objects_per_poll"],
        ): row["polling_worker_requests"]
        for row in report["scenarios"]
    }
    assert values == {
        (30, 5, 2): 129_600,
        (30, 15, 2): 43_200,
        (50, 5, 2): 216_000,
        (50, 15, 2): 72_000,
        (30, 1, 1): 324_000,
        (50, 1, 1): 540_000,
    }
    assert report["estimated"] is True and report["measurement"] is False
    assert report["launch_ready"] is False
    assert all(row["headroom_requests"] is None for row in report["scenarios"])


def test_unknown_other_usage_is_not_zero_or_launch_ready():
    result = estimate(scenario())
    assert result["known_account_request_lower_bound"] == 43_200
    assert result["estimated_account_worker_requests"] is None
    assert result["headroom_requests"] is None
    assert result["budget_status"] == "headroom_unknown"
    assert result["known_excess_requests"] == 0
    assert result["launch_ready"] is False


def test_known_excess_still_detected_when_other_usage_unknown():
    result = estimate(scenario(poll_seconds=5))
    assert result["known_account_request_lower_bound"] == 129_600
    assert result["known_excess_requests"] == 29_600
    assert result["estimated_account_worker_requests"] is None
    assert result["headroom_requests"] is None
    assert result["budget_status"] == "exceeds_known_budget"
    assert result["launch_ready"] is False


def test_extra_event_and_other_account_traffic_count_once():
    result = estimate(scenario(extra_worker_requests=500, other_account_requests=1000))
    assert result["polling_worker_requests"] == 43_200
    assert result["estimated_event_worker_requests"] == 43_700
    assert result["estimated_account_worker_requests"] == 44_700
    assert result["headroom_requests"] == 55_300
    assert result["budget_status"] == "within_estimated_daily_limit"
    assert result["launch_ready"] is False


@pytest.mark.parametrize(
    ("extra", "other", "status", "headroom", "excess"),
    [
        (99_998, 0, "within_estimated_daily_limit", 1, 0),
        (99_999, 0, "at_estimated_daily_limit", 0, 0),
        (100_000, 0, "exceeds_known_budget", 0, 1),
        (99_998, 2, "exceeds_known_budget", 0, 1),
        (99_999, None, "headroom_unknown", None, 0),
    ],
)
def test_daily_limit_boundary(extra, other, status, headroom, excess):
    result = estimate(
        scenario(
            viewers=1,
            duration_seconds=1,
            poll_seconds=1,
            objects_per_poll=1,
            extra_worker_requests=extra,
            other_account_requests=other,
        )
    )
    assert result["budget_status"] == status
    assert result["headroom_requests"] == headroom
    assert result["known_excess_requests"] == excess


@pytest.mark.parametrize("field", FIELD_BOUNDS)
@pytest.mark.parametrize(
    "value",
    [True, False, 1.0, 0.5, float("nan"), float("inf"), float("-inf"), Decimal("1"), "1", [], {}],
)
def test_noninteger_and_nonfinite_inputs_are_rejected(field, value):
    with pytest.raises(ViewerBudgetError, match=f"^invalid_{field}$"):
        estimate(scenario(**{field: value}))


@pytest.mark.parametrize("field", FIELD_BOUNDS)
def test_bounds_and_unknown_are_strict(field):
    minimum, maximum = FIELD_BOUNDS[field]
    for value in (minimum, maximum):
        assert estimate(scenario(**{field: value}))["scenario"][field] == value
    for value in (minimum - 1, maximum + 1, 10**400):
        with pytest.raises(ViewerBudgetError, match=f"^invalid_{field}$"):
            estimate(scenario(**{field: value}))
    if field != "other_account_requests":
        with pytest.raises(ViewerBudgetError, match=f"^invalid_{field}$"):
            estimate(scenario(**{field: None}))


@pytest.mark.parametrize("value", [None, [], "scenario", {}, {"schema": SCHEMA}])
def test_incomplete_or_wrong_shape_is_rejected(value):
    with pytest.raises(ViewerBudgetError, match="^invalid_scenario_fields$"):
        estimate(value)


def test_extra_fields_and_schema_drift_are_rejected():
    with pytest.raises(ViewerBudgetError, match="^invalid_scenario_fields$"):
        estimate(scenario(cache_discount=0.5))
    with pytest.raises(ViewerBudgetError, match="^unsupported_schema$"):
        estimate(scenario(schema="pitcheezy-viewer-budget-scenario-v2"))


def test_estimate_preserves_input_and_has_fixed_limit_and_assumptions(monkeypatch):
    def refuse_io(*args, **kwargs):
        raise AssertionError("calculator must not perform I/O")

    monkeypatch.setattr("builtins.open", refuse_io)
    monkeypatch.setattr("socket.socket", refuse_io)
    value = scenario()
    frozen = deepcopy(value)
    result = estimate(value)
    assert value == frozen
    assert result == estimate(value)
    assert result["scenario"] is not value
    assert result["daily_limit_requests"] == 100_000
    assert result["limit_scope"] == "account_wide"
    assert result["reset_utc"] == "00:00" and result["reset_kst"] == "09:00"
    assert result["limit_exceeded_error"] == 1027
    assert result["limits_as_of"] == "2026-10-25"
    assert result["measurement"] is False
    assumptions = " ".join(result["assumptions"])
    for text in (
        "[0, duration_seconds)",
        "Login",
        "assets",
        "monitoring",
        "publisher",
        "retries",
        "zero excludes",
        "304",
        "cache hit",
        "one UTC budget day",
    ):
        assert text in assumptions
    json.dumps(result, allow_nan=False)


def run_cli(*args):
    return subprocess.run(
        [sys.executable, "-B", "-S", str(CLI), *args], capture_output=True, text=True, timeout=15
    )


def test_cli_examples_and_explicit_scenario():
    output = run_cli("--examples")
    assert output.returncode == 0, output.stderr
    assert len(json.loads(output.stdout)["scenarios"]) == 6
    args = (
        "--viewers",
        "50",
        "--duration-seconds",
        "10800",
        "--poll-seconds",
        "15",
        "--objects-per-poll",
        "2",
    )
    output = run_cli(*args)
    assert output.returncode == 0, output.stderr
    value = json.loads(output.stdout)
    assert value["polling_worker_requests"] == 72_000
    assert value["budget_status"] == "headroom_unknown"
    output = run_cli(*args, "--extra-worker-requests", "100", "--other-account-requests", "0")
    assert output.returncode == 0, output.stderr
    assert json.loads(output.stdout)["headroom_requests"] == 27_900


@pytest.mark.parametrize(
    "args",
    [
        (),
        ("--examples", "--viewers", "30"),
        ("--viewers", "nan"),
        ("--viewers", "1.0"),
        ("--viewers", "1e1"),
        ("--viewers", "True"),
    ],
)
def test_cli_refuses_missing_ambiguous_or_noninteger_arguments(args):
    output = run_cli(*args)
    assert output.returncode == 2
    assert output.stdout == ""


def test_cli_range_error_is_stable():
    output = run_cli(
        "--viewers",
        "51",
        "--duration-seconds",
        "10800",
        "--poll-seconds",
        "15",
        "--objects-per-poll",
        "2",
    )
    assert output.returncode == 2
    assert json.loads(output.stdout) == {"ok": False, "error": "invalid_viewers"}

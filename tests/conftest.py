"""Explicit device selection for tests on hosts without reliable GPU access."""

import pytest


def pytest_addoption(parser):
    parser.addoption("--cpu-only", action="store_true", help="Use CPU for inference wrapper tests.")


@pytest.fixture
def inference_device(request):
    """Preserve automatic device selection unless CPU testing was requested."""
    return "cpu" if request.config.getoption("--cpu-only") else None

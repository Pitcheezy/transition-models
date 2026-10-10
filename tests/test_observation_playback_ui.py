"""Exercise publication gates without a browser or private video."""

import shutil
import subprocess
from pathlib import Path

import pytest


def test_observation_playback_javascript():
    node = shutil.which("node")
    if node is None:
        pytest.skip("Node.js is required for browser-independent publication gate checks")
    script = Path(__file__).resolve().parents[1] / "web/observation-playback/playback.test.cjs"
    result = subprocess.run(
        [node, "--test", str(script)], capture_output=True, text=True, encoding="utf-8", timeout=30
    )
    assert result.returncode == 0, result.stdout + result.stderr

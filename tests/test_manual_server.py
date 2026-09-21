"""Verify request boundaries and error handling at the real HTTP interface."""

import json
from threading import Thread
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import pytest

from src.web.manual_server import create_server


class Predictor:
    def predict(self, payload):
        if payload.get("invalid"):
            raise ValueError("Invalid state")
        return {"recommendation": "FF"}


@pytest.fixture
def server():
    instance = create_server(Predictor(), {"balls": 0}, port=0)
    thread = Thread(target=instance.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{instance.server_port}"
    instance.shutdown()
    instance.server_close()
    thread.join(timeout=3)


def post(server, data, **headers):
    return urlopen(
        Request(
            server + "/api/predict",
            data=data,
            headers={"Content-Type": "application/json", **headers},
        ),
        timeout=5,
    )


def test_real_http_predict_and_health(server):
    with urlopen(server + "/api/health", timeout=5) as response:
        assert json.load(response) == {"status": "ready", "mode": "manual", "ocr": False}
    with post(server, b"{}") as response:
        result = json.load(response)
    assert result["input_source"] == "manual"
    assert result["recommendation"] == "FF"
    assert result["elapsed_ms"] >= 0


@pytest.mark.parametrize("body", [b"{", b'{"balls": NaN}', b'{"invalid": true}'])
def test_bad_requests_return_400(server, body):
    with pytest.raises(HTTPError) as error:
        post(server, body)
    assert error.value.code == 400


def test_foreign_origin_rejected(server):
    with pytest.raises(HTTPError) as error:
        post(server, b"{}", Origin="https://example.com")
    assert error.value.code == 403


def test_files_outside_allowlist_not_served(server):
    with pytest.raises(HTTPError) as error:
        urlopen(server + "/AGENTS.md", timeout=5)
    assert error.value.code == 404


def test_static_application_is_served(server):
    with urlopen(server + "/", timeout=5) as response:
        assert b"SmartPitch" in response.read()

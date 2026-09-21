"""Verify request boundaries and error handling at the real HTTP interface."""

import json
import socket
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FutureTimeout
from threading import Event, Thread
from urllib.error import HTTPError
from urllib.parse import urlparse
from urllib.request import Request, urlopen

import pytest

from src.web.manual_server import create_server


class Predictor:
    def predict(self, payload):
        if payload.get("invalid"):
            raise ValueError("Invalid state")
        return {"recommendation": "FF"}


@pytest.fixture
def server_factory():
    instances = []

    def start(predictor=None, timeout=0.25):
        instance = create_server(
            predictor or Predictor(), {"balls": 0}, port=0, request_timeout=timeout
        )
        thread = Thread(target=instance.serve_forever, daemon=True)
        thread.start()
        instances.append((instance, thread))
        return f"http://127.0.0.1:{instance.server_port}"

    yield start
    for instance, thread in instances:
        instance.shutdown()
        instance.server_close()
        thread.join(timeout=3)


@pytest.fixture
def server(server_factory):
    return server_factory()


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


def test_incomplete_headers_do_not_block_other_clients(server_factory):
    # A shorter read timeout alone must not make this pass: health must respond
    # before the unfinished connection's five-second timeout.
    server = server_factory(timeout=5)
    with socket.create_connection(("127.0.0.1", urlparse(server).port), timeout=2) as client:
        client.sendall(b"GET /api/health HTTP/1.1\r\n")
        with urlopen(server + "/api/health", timeout=2) as response:
            assert json.load(response)["status"] == "ready"


def raw_post(server, headers, body, close_write=False):
    """Send controlled malformed requests that urllib would repair automatically."""
    client = socket.create_connection(("127.0.0.1", urlparse(server).port), timeout=2)
    with client:
        request = (
            f"POST /api/predict HTTP/1.1\r\nHost: {urlparse(server).netloc}\r\n"
            f"Content-Type: application/json\r\n{headers}\r\n\r\n"
        ).encode() + body
        client.sendall(request)
        if close_write:
            client.shutdown(socket.SHUT_WR)
        response = client.makefile("rb")
        with response:
            return response.read()


def test_partial_body_times_out_and_server_recovers(server):
    response = raw_post(server, "Content-Length: 100", b"{")
    assert b" 408 " in response.split(b"\r\n")[0]
    with post(server, b"{}") as response:
        assert json.load(response)["recommendation"] == "FF"


def test_truncated_valid_json_is_not_accepted(server):
    response = raw_post(server, "Content-Length: 100", b"{}", close_write=True)
    assert b" 400 " in response.split(b"\r\n")[0]
    assert b"Incomplete request body" in response


@pytest.mark.parametrize(
    "headers",
    [
        "Content-Length: 2\r\nContent-Length: 2",
        "Content-Length: 2\r\nTransfer-Encoding: chunked",
    ],
)
def test_ambiguous_request_framing_is_rejected(server, headers):
    response = raw_post(server, headers, b"{}")
    assert b" 400 " in response.split(b"\r\n")[0]


def test_model_work_is_serialized_without_blocking_health(server_factory):
    first_started, release_first = Event(), Event()

    class BlockingPredictor:
        def predict(self, payload):
            if payload["first"]:
                first_started.set()
                if not release_first.wait(timeout=5):
                    raise ValueError("Test did not release first prediction")
            return {"recommendation": "FF"}

    server = server_factory(BlockingPredictor())

    def predict(first):
        with post(server, json.dumps({"first": first}).encode()) as response:
            return json.load(response)

    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(predict, True)
        try:
            assert first_started.wait(timeout=2)
            second = pool.submit(predict, False)
            with pytest.raises(FutureTimeout):
                second.result(timeout=0.2)
            with urlopen(server + "/api/health", timeout=2) as response:
                assert json.load(response)["status"] == "ready"
        finally:
            release_first.set()
        assert first.result(timeout=2)["recommendation"] == "FF"
        assert second.result(timeout=2)["recommendation"] == "FF"

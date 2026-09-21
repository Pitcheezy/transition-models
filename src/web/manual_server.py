"""A localhost-only manual inference UI with a small, explicit HTTP surface."""

import json
import logging
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Lock
from time import perf_counter
from urllib.parse import urlparse

STATIC = Path(__file__).parent / "static"


def create_server(predictor, example, port=8770, video_url=None, request_timeout=5.0):
    """Construct a local server; the injected predictor is loaded exactly once."""
    inference_lock = Lock()

    class Handler(BaseHTTPRequestHandler):
        def setup(self):
            super().setup()
            self.connection.settimeout(request_timeout)

        def send_bytes(self, code, data, content_type):
            try:
                self.send_response(code)
                self.send_header("Content-Type", content_type + "; charset=utf-8")
                self.send_header("Content-Length", str(len(data)))
                self.send_header("Cache-Control", "no-store")
                self.end_headers()
                self.wfile.write(data)
            except (ConnectionError, TimeoutError):
                # Closing a browser tab while a request runs is a normal disconnect.
                self.close_connection = True

        def send_json(self, code, payload):
            data = json.dumps(payload, ensure_ascii=False, allow_nan=False).encode("utf-8")
            self.send_bytes(code, data, "application/json")

        def valid_host(self):
            return self.headers.get("Host") in {
                f"127.0.0.1:{self.server.server_port}",
                f"localhost:{self.server.server_port}",
            }

        def do_GET(self):
            if not self.valid_host():
                self.send_json(403, {"error": "Local host required"})
                return
            route = urlparse(self.path).path
            if route == "/api/health":
                self.send_json(200, {"status": "ready", "mode": "manual", "ocr": False})
            elif route == "/api/example":
                self.send_json(
                    200,
                    {
                        "state": example,
                        "video_url": video_url,
                        "source": "recorded_metadata; not video recognition",
                    },
                )
            elif route in ("/", "/app.js", "/style.css"):
                filename = {"/": "index.html", "/app.js": "app.js", "/style.css": "style.css"}[
                    route
                ]
                data = (STATIC / filename).read_bytes()
                mime = {"/": "text/html", "/app.js": "text/javascript", "/style.css": "text/css"}
                self.send_bytes(200, data, mime[route])
            else:
                self.send_json(404, {"error": "Not found"})

        def do_POST(self):
            origin = self.headers.get("Origin")
            allowed_origins = {
                f"http://127.0.0.1:{self.server.server_port}",
                f"http://localhost:{self.server.server_port}",
            }
            if not self.valid_host() or (origin is not None and origin not in allowed_origins):
                self.send_json(403, {"error": "Same-origin request required"})
                return
            if self.path != "/api/predict":
                self.send_json(404, {"error": "Not found"})
                return
            if self.headers.get("Content-Type", "").split(";")[0].strip() != "application/json":
                self.send_json(415, {"error": "Expected application/json"})
                return
            try:
                lengths = self.headers.get_all("Content-Length", [])
                if len(lengths) != 1 or self.headers.get("Transfer-Encoding") is not None:
                    raise ValueError("Expected a single Content-Length and no Transfer-Encoding")
                length = int(lengths[0])
                if not 0 < length <= 16384:
                    raise ValueError("Request body must be 1–16384 bytes")
                body = self.rfile.read(length)
                if len(body) != length:
                    raise ValueError("Incomplete request body")
                payload = json.loads(body, parse_constant=_reject_constant)
                # Socket reads must not hold up other clients. Serialize only model work.
                with inference_lock:
                    start = perf_counter()
                    result = predictor.predict(payload)
                    result["elapsed_ms"] = round((perf_counter() - start) * 1000, 2)
                    result["input_source"] = "manual"
                self.send_json(200, result)
            except TimeoutError:
                self.send_json(408, {"error": "Request body timed out"})
            except (ValueError, UnicodeDecodeError) as exc:
                self.send_json(400, {"error": str(exc)})
            except Exception:
                logging.exception("Manual inference failed")
                self.send_json(500, {"error": "Inference failed; inspect server log"})

    return ThreadingHTTPServer(("127.0.0.1", port), Handler)


def _reject_constant(value):
    raise ValueError(f"Non-finite JSON value: {value}")

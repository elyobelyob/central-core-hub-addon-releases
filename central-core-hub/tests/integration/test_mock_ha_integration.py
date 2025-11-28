import json
import os
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import importlib.util

import pytest


def _load_client_module():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)
    return module


class MockHAHandler(BaseHTTPRequestHandler):
    store = {}

    def _set_json(self, code=200):
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.end_headers()

    def do_POST(self):
        # set state
        length = int(self.headers.get("Content-Length", 0))
        body = self.rfile.read(length) if length else b""
        try:
            data = json.loads(body.decode("utf-8") or "{}")
        except Exception:
            data = {}
        # store by path
        MockHAHandler.store[self.path] = data
        resp = {"state": data.get("state"), "attributes": {}}
        self._set_json(200)
        self.wfile.write(json.dumps(resp).encode("utf-8"))

    def do_GET(self):
        # read state
        data = MockHAHandler.store.get(
            self.path, {"state": "unknown", "attributes": {}}
        )
        self._set_json(200)
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def log_message(self, format, *args):
        # suppress default logging during tests
        return


@pytest.mark.skipif(
    os.environ.get("RUN_INTEGRATION_TESTS") is None, reason="Integration tests disabled"
)
def test_set_and_readback_with_mock_ha():
    """Integration-style test: start a mock HA HTTP server and exercise sensors/set flow."""
    mod = _load_client_module()
    CentralCoreClient = mod.CentralCoreClient

    # start server
    server = HTTPServer(("localhost", 0), MockHAHandler)
    port = server.server_port
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()

    options = {
        "client_id": "int-hub",
        "ha_api_url": f"http://localhost:{port}",
        "ha_api_token": "tok",
    }
    c = CentralCoreClient(options)

    # capture publishes
    class DummyClient:
        def __init__(self):
            self.published = []

        def publish(self, topic, payload, qos=0):
            self.published.append({"topic": topic, "payload": payload, "qos": qos})

            class R:
                rc = 0

            return R()

    c._client = DummyClient()

    command = {
        "command_id": "int123",
        "action": "sensors/set",
        "payload": {"sensors": [{"entity_id": "sensor.temp", "state": "21.0"}]},
    }
    msg = type(
        "M",
        (),
        {
            "topic": f"hubs/{c.client_id}/v1/cmd/sensors/set",
            "payload": json.dumps(command).encode("utf-8"),
        },
    )

    # run handler
    c.on_message(None, None, msg)

    # ensure that server received POST and GET
    assert "/api/states/sensor.temp" in MockHAHandler.store
    # ensure telemetry published
    assert any(p["topic"] == c.preferred_sensors_topic for p in c._client.published)

    server.shutdown()

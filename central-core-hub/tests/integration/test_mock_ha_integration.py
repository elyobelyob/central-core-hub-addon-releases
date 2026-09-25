import json
import threading
from http.server import BaseHTTPRequestHandler, HTTPServer
from pathlib import Path
import importlib.util


def _load_client_module():
    repo_root = Path(__file__).resolve().parents[3]
    import sys

    sys.path.append(str(repo_root / "central-core-hub"))
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
        data = MockHAHandler.store.get(self.path, {"state": "unknown", "attributes": {}})
        self._set_json(200)
        self.wfile.write(json.dumps(data).encode("utf-8"))

    def log_message(self, format, *args):
        # suppress default logging during tests
        return


def test_set_with_mock_ha_never_writes_and_list_selects():
    """Integration-style: a mock HA HTTP server sees no request for a write-form
    sensors/set; the list form selects and reports current values."""
    mod = _load_client_module()
    CentralCoreClient = mod.CentralCoreClient

    MockHAHandler.store = {}
    requests_seen = []

    class _Recording(MockHAHandler):
        def do_POST(self):
            requests_seen.append(("POST", self.path))
            super().do_POST()

        def do_GET(self):
            requests_seen.append(("GET", self.path))
            super().do_GET()

    server = HTTPServer(("localhost", 0), _Recording)
    port = server.server_port
    t = threading.Thread(target=server.serve_forever, daemon=True)
    t.start()
    try:
        options = {
            "client_id": "int-hub",
            "ha_api_url": f"http://localhost:{port}",
            "ha_api_token": "tok",
        }
        c = CentralCoreClient(options)

        class DummyClient:
            def __init__(self):
                self.published = []

            def publish(self, topic, payload, qos=0):
                self.published.append({"topic": topic, "payload": payload, "qos": qos})

                class R:
                    rc = 0

                return R()

        c._client = DummyClient()

        def send(cid, payload):
            command = {"command_id": cid, "action": "sensors/set", "payload": payload}
            msg = type(
                "M",
                (),
                {
                    "topic": f"hubs/{c.client_id}/v1/cmd/sensors/set",
                    "payload": json.dumps(command).encode("utf-8"),
                },
            )
            c.on_message(None, None, msg)

        # write form: refused, and nothing reaches Home Assistant
        send("int123", {"sensors": [{"entity_id": "sensor.temp", "state": "21.0"}]})
        assert requests_seen == []
        assert MockHAHandler.store == {}
        final = _secure_final_ack(c._client.published)
        assert final["status"] == "failed"
        assert final["result"]["reason"] == "invalid_payload"

        # list form: selection stored; current values come from GET /api/states
        MockHAHandler.store["/api/states"] = [
            {"entity_id": "sensor.temp", "state": "21.0", "attributes": {"friendly_name": "Temp"}}
        ]
        send("int124", {"sensors": ["sensor.temp"]})
        assert c.selected_sensors == ["sensor.temp"]
        assert not any(method == "POST" for method, _ in requests_seen)
        final = _secure_final_ack(c._client.published)
        assert final["status"] == "completed"
        assert final["result"]["sensors_reported"] == ["sensor.temp"]
        assert final["result"]["data"] == {"sensor.temp": "21.0"}
    finally:
        server.shutdown()


# --- helpers for the secure sensors/set and registry/set behaviour ---------


def _secure_final_ack(records):
    """Last non-"acknowledged" ACK body among recorded publishes (any record shape)."""
    last = None
    for r in records:
        topic, payload = (r["topic"], r["payload"]) if isinstance(r, dict) else (r[0], r[1])
        if "/ack/" not in topic:
            continue
        body = json.loads(payload) if isinstance(payload, (str, bytes)) else payload
        if isinstance(body, dict) and body.get("status") != "acknowledged":
            last = body
    return last


class _RecordingRequests:
    """A `requests` stand-in that records calls and refuses every one."""

    def __init__(self):
        self.calls = []

    def post(self, url, *a, **k):
        self.calls.append(("POST", url))
        raise AssertionError(f"hub must not POST to Home Assistant: {url}")

    def get(self, url, *a, **k):
        self.calls.append(("GET", url))
        raise AssertionError(f"sensors/set must not call Home Assistant per entity: {url}")

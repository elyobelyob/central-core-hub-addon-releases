import importlib.util
import json
import threading
import time
import types
from pathlib import Path


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)
    return module


class _FakeResponse:
    def __init__(self, payload):
        self._payload = payload

    def raise_for_status(self):
        return None

    def json(self):
        return self._payload


class _FakeRequests:
    def __init__(self, responses, fail_first=False):
        self._responses = list(responses)
        self._fail_first = fail_first
        self.calls = 0

    def get(self, url, headers=None, timeout=None):
        self.calls += 1
        if self._fail_first and self.calls == 1:
            raise ValueError("simulated failure")
        if not self._responses:
            raise ValueError("no more responses")
        return _FakeResponse(self._responses.pop(0))


class FakeHAWebSocket:
    """Predetermined websocket session that responds to pings and call_service requests."""

    def __init__(self, listener, timeline):
        self.listener = listener
        self.timeline = list(timeline)
        self.sent = []
        self.closed = False

    def send(self, data):
        payload = {}
        if data:
            try:
                payload = json.loads(data)
            except Exception:
                payload = {}
        self.sent.append(payload)
        msg_type = payload.get("type")
        if msg_type == "ping":
            self.timeline.append({"type": "pong"})
        elif msg_type == "call_service":
            req_id = payload.get("id")
            if req_id is not None:
                self.timeline.insert(
                    0,
                    {"type": "result", "id": req_id, "result": {"status": "success"}},
                )

    def recv(self):
        if not self.timeline:
            try:
                self.listener._stop.set()
            except Exception:
                pass
            return ""
        msg = self.timeline.pop(0)
        return json.dumps(msg)

    def close(self):
        self.closed = True


class FakeWSModule:
    def __init__(self, fake_socket):
        self.fake_socket = fake_socket

    def create_connection(self, *args, **kwargs):
        return self.fake_socket


def test_fetch_sensors_filters_non_sensor_entities(tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    ha_mod = _load_module(repo_root / "central-core-hub" / "ha_client.py", "ha_client_extra")

    sensors_payload = [
        {"entity_id": "sensor.motion", "state": "on", "attributes": {"friendly_name": "Motion Sensor"}},
        {"entity_id": "light.lamp", "state": "off"},
        {"entity_id": "sensor.temperature", "state": "22.5", "attributes": {"friendly_name": "Temp"}},
    ]
    fake_requests = _FakeRequests([sensors_payload])
    sensors = ha_mod.fetch_sensors("http://example.com", "token", requests_mod=fake_requests)
    assert isinstance(sensors, list)
    assert len(sensors) == 2
    assert sensors[0]["entity_id"] == "sensor.motion"
    assert sensors[1]["entity_id"] == "sensor.temperature"
    assert sensors[0]["name"] == "Motion Sensor"


def test_fetch_sensors_missing_config_returns_none():
    repo_root = Path(__file__).resolve().parents[3]
    ha_mod = _load_module(repo_root / "central-core-hub" / "ha_client.py", "ha_client_extra_missing")

    assert ha_mod.fetch_sensors(None, "token") is None
    assert ha_mod.fetch_sensors("http://example", None) is None
    assert ha_mod.fetch_sensors("http://example", "token", requests_mod=None) is None


def test_fetch_sensors_by_ids_skips_errors():
    repo_root = Path(__file__).resolve().parents[3]
    ha_mod = _load_module(repo_root / "central-core-hub" / "ha_client.py", "ha_client_extra_ids")

    responses = [
        {"entity_id": "sensor.temp", "state": "20"},
        {"entity_id": "sensor.humidity", "state": "55"},
    ]
    fake_requests = _FakeRequests(responses, fail_first=True)
    result = ha_mod.fetch_sensors_by_ids(
        "http://example.com",
        "token",
        ["sensor.temp", "sensor.humidity"],
        requests_mod=fake_requests,
    )
    assert len(result) == 1
    assert fake_requests.calls == 2


def test_ws_url_generation():
    repo_root = Path(__file__).resolve().parents[3]
    ha_mod = _load_module(repo_root / "central-core-hub" / "ha_client.py", "ha_client_extra_url")

    listener = ha_mod.HAWebSocketListener("http://example.com", "token", on_event=None)
    assert listener._ws_url() == "ws://example.com/api/websocket"

    listener = ha_mod.HAWebSocketListener("https://ha.local", "token", on_event=None)
    assert listener._ws_url() == "wss://ha.local/api/websocket"

    listener = ha_mod.HAWebSocketListener(None, "token", on_event=None)
    assert listener._ws_url() is None


def test_call_service_returns_result_immediately():
    repo_root = Path(__file__).resolve().parents[3]
    ha_mod = _load_module(repo_root / "central-core-hub" / "ha_client.py", "ha_client_extra_call")

    listener = ha_mod.HAWebSocketListener("http://example.com", "token", on_event=None)
    listener._ws = object()

    req_id = 9
    event = threading.Event()
    event.set()
    listener._pending_requests[req_id] = {"event": event, "result": {"success": True}}

    def fake_register(self):
        return req_id, event

    listener._register_request = types.MethodType(fake_register, listener)
    sent = {}

    def fake_send_json(self, sock, payload):
        sent["payload"] = payload

    listener._send_json = types.MethodType(fake_send_json, listener)
    response = listener.call_service("domain", "service", service_data={"a": 1})
    assert response == {"success": True}
    assert sent["payload"]["service_data"] == {"a": 1}


def test_call_service_without_connection_returns_none():
    repo_root = Path(__file__).resolve().parents[3]
    ha_mod = _load_module(
        repo_root / "central-core-hub" / "ha_client.py",
        "ha_client_extra_call_no_ws",
    )
    listener = ha_mod.HAWebSocketListener("http://example.com", "token", on_event=None)
    listener._ws = None
    assert listener.call_service("domain", "service") is None


def test_persist_ha_version_writes_options(tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    ha_mod = _load_module(repo_root / "central-core-hub" / "ha_client.py", "ha_client_extra_persist")
    opts_path = tmp_path / "options.json"
    ha_mod.OPTIONS_PATH = str(opts_path)

    listener = ha_mod.HAWebSocketListener("http://example.com", "token", on_event=None)
    assert listener._persist_ha_version("2025.99.9") is True
    assert opts_path.exists()
    data = json.loads(opts_path.read_text())
    assert data.get("ha_version") == "2025.99.9"


def test_persist_ha_version_handles_write_failure(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[3]
    ha_mod = _load_module(repo_root / "central-core-hub" / "ha_client.py", "ha_client_extra_persist_fail")
    # Point to a directory that does not exist so writing fails
    missing_dir = tmp_path / "missing"
    opts_path = missing_dir / "options.json"
    ha_mod.OPTIONS_PATH = str(opts_path)

    listener = ha_mod.HAWebSocketListener("http://example.com", "token", on_event=None)
    assert listener._persist_ha_version("2025.99.10") is False


def test_register_and_set_pending_result():
    repo_root = Path(__file__).resolve().parents[3]
    ha_mod = _load_module(repo_root / "central-core-hub" / "ha_client.py", "ha_client_extra_requests")

    listener = ha_mod.HAWebSocketListener("http://example.com", "token", on_event=None)
    req_id, event = listener._register_request()
    assert isinstance(req_id, int)
    assert req_id in listener._pending_requests
    listener._set_pending_result(req_id, {"status": "ok"})
    pending = listener._pending_requests.get(req_id)
    assert pending is not None
    assert pending["result"] == {"status": "ok"}
    assert event.is_set()


def test_set_pending_result_missing_id_does_not_throw():
    repo_root = Path(__file__).resolve().parents[3]
    ha_mod = _load_module(repo_root / "central-core-hub" / "ha_client.py", "ha_client_extra_missing_result")
    listener = ha_mod.HAWebSocketListener("http://example.com", "token", on_event=None)
    # Should not raise
    listener._set_pending_result(None, {"ok": True})


def test_ha_listener_loop_processes_ping_get_config_and_events(monkeypatch, tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    ha_mod = _load_module(
        repo_root / "central-core-hub" / "ha_client.py", "ha_client_extra_loop"
    )

    opts_file = tmp_path / "options.json"
    ha_mod.OPTIONS_PATH = str(opts_file)
    events = []

    pending_event = threading.Event()
    pending_event.clear()

    listener = ha_mod.HAWebSocketListener(
        "http://example.com",
        "token",
        on_event=lambda eid, data: events.append(eid),
        selectors={"sensor.motion"},
    )
    listener._pending_requests[99] = {"event": pending_event, "result": None}

    class FakeWS:
        def __init__(self):
            self.timeline = [
                {"type": "auth_required"},
                {"type": "auth_ok"},
                {"type": "result", "id": 2, "result": {"homeassistant_version": "2026.0.0"}},
                {"type": "result", "id": 99, "result": {"status": "ok"}},
                {
                    "type": "event",
                    "event": {
                        "data": {
                            "entity_id": "sensor.motion",
                            "new_state": {"state": "on"},
                        }
                    },
                },
                {
                    "type": "event",
                    "event": {
                        "data": {
                            "entity_id": "light.kitchen",
                            "new_state": {"state": "off"},
                        }
                    },
                },
            ]
            self.sent = []
            self.closed = False
            self.listener = listener

        def send(self, data):
            try:
                payload = json.loads(data)
            except Exception:
                payload = {}
            self.sent.append(payload)
            if payload.get("type") == "ping":
                self.timeline.append({"type": "pong"})

        def recv(self):
            if not self.timeline:
                self.listener._stop.set()
                return ""
            try:
                msg = self.timeline.pop(0)
            except IndexError:
                self.listener._stop.set()
                return ""
            return json.dumps(msg)

        def close(self):
            self.closed = True

    fake_ws = FakeWS()

    class FakeWSModule:
        def create_connection(self, *args, **kwargs):
            return fake_ws

    monkeypatch.setattr(ha_mod, "websocket", FakeWSModule())

    class TimeSim:
        def __init__(self):
            self.count = 0
            self.value = 0

        def __call__(self):
            self.count += 1
            if self.count == 1:
                self.value = 0
            elif self.count == 2:
                self.value += 40
            else:
                self.value += 1
            return self.value

    time_sim = TimeSim()
    monkeypatch.setattr(ha_mod.time, "time", time_sim)

    listener._stop.clear()
    listener._run()

    assert events == ["sensor.motion"]
    assert pending_event.is_set()
    assert opts_file.exists()
    assert json.loads(opts_file.read_text()).get("ha_version") == "2026.0.0"
    assert any(msg.get("type") == "ping" for msg in fake_ws.sent)
def test_ha_listener_loop_processes_events_and_persists_version(tmp_path):
    repo_root = Path(__file__).resolve().parents[3]
    ha_mod = _load_module(repo_root / "central-core-hub" / "ha_client.py", "ha_client_extra_loop")

    opts_file = tmp_path / "options.json"
    ha_mod.OPTIONS_PATH = str(opts_file)

    event_entity_ids = []
    event_received = threading.Event()

    def on_event(entity_id, data):
        event_entity_ids.append(entity_id)
        event_received.set()

    class FakeWS:
        def __init__(self):
            self.timeline = [
                {"type": "auth_required", "ha_version": "2026.0.0"},
                {"type": "auth_ok"},
                {"type": "result", "id": 2, "result": {"version": "2026.0.0"}},
                {
                    "type": "event",
                    "event": {"data": {"entity_id": "sensor.motion", "new_state": {"state": "on"}}},
                },
                {
                    "type": "event",
                    "event": {"data": {"entity_id": "light.kitchen", "new_state": {"state": "off"}}},
                },
            ]
            self.sent = []
            self.closed = False

        def send(self, data):
            try:
                payload = json.loads(data)
            except Exception:
                payload = {}
            self.sent.append(payload)
            if payload.get("type") == "ping":
                self.timeline.append({"type": "pong"})

        def recv(self):
            if not self.timeline:
                threading.Event().wait(0.01)
                return ""
            return json.dumps(self.timeline.pop(0))

        def close(self):
            self.closed = True

    fake_ws = FakeWS()

    class FakeWSModule:
        def create_connection(self, *args, **kwargs):
            return fake_ws

    ha_mod.websocket = FakeWSModule()

    listener = ha_mod.HAWebSocketListener("http://example.com", "token", on_event=on_event, selectors={"sensor.motion"})
    # Force the timeline to start with ping to ensure ping/pong branch runs quickly
    listener._send_json = types.MethodType(lambda self, sock, obj: sock.send(json.dumps(obj)), listener)

    started = listener.start()
    assert started is True

    assert event_received.wait(1.0), "Expected event callback to fire from fake websocket"

    listener.stop()

    assert opts_file.exists()
    assert json.loads(opts_file.read_text()).get("ha_version") == "2026.0.0"
    assert "sensor.motion" in event_entity_ids
    assert "light.kitchen" not in event_entity_ids

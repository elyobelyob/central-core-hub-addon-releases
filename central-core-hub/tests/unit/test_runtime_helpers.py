import importlib.util
import time
from pathlib import Path


def _load_client_module():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client", str(src))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


mc = _load_client_module()


class DummyClient:
    def __init__(self, raise_on_connect=False):
        self.connected = False
        self.connect_called = False
        self.loop_started = False
        self.raise_on_connect = raise_on_connect

    def connect(self, host, port, keepalive=60):
        self.connect_called = True
        if self.raise_on_connect:
            raise RuntimeError("connect failed")
        return 0

    def loop_start(self):
        self.loop_started = True

    def loop_stop(self):
        self.loop_started = False

    def disconnect(self):
        self.connected = False


def make_client(options=None):
    options = options or {}
    c = mc.CentralCoreClient(options)
    return c


def test_connect_once_success(monkeypatch):
    c = make_client({"client_id": "test"})
    dummy = DummyClient()
    # replace the internal _client with our dummy
    c._client = dummy
    ok = c.connect_once()
    assert ok is True
    assert dummy.connect_called is True
    assert dummy.loop_started is True


def test_connect_once_failure(monkeypatch):
    c = make_client({"client_id": "test2"})
    dummy = DummyClient(raise_on_connect=True)
    c._client = dummy
    ok = c.connect_once()
    assert ok is False
    assert dummy.connect_called is True


def test_wait_for_connected_success():
    c = make_client({"client_id": "test3"})
    c._connected = True
    assert c.wait_for_connected(timeout=1) is True


def test_wait_for_connected_timeout():
    c = make_client({"client_id": "test4"})
    c._connected = False
    assert c.wait_for_connected(timeout=0.5) is False


def test_run_iteration_calls_connect_and_publish(monkeypatch):
    c = make_client({"client_id": "test5"})
    # ensure connected is False so connect path is taken
    c._connected = False

    called = {}

    def fake_connect():
        called["connect"] = True
        # simulate successful connection
        c._connected = True

    def fake_publish_telemetry():
        called["telemetry"] = True

    def fake_publish_sensors():
        called["sensors"] = True

    c.connect = fake_connect
    c.publish_telemetry = fake_publish_telemetry
    c.publish_sensors = fake_publish_sensors
    # set last sensors sent recently so sensors won't be called by default
    c._last_sensors_sent = int(time.time())

    c.run_iteration()
    assert called.get("connect") is True
    assert called.get("telemetry") is True
    # sensors should not be called because _last_sensors_sent just updated
    assert "sensors" not in called


def test_run_iteration_triggers_sensors_when_due(monkeypatch):
    c = make_client({"client_id": "test6"})
    c._connected = True
    called = {}

    def fake_publish_telemetry():
        called["telemetry"] = True

    def fake_publish_sensors():
        called["sensors"] = True

    c.publish_telemetry = fake_publish_telemetry
    c.publish_sensors = fake_publish_sensors
    # set last sensors sent long ago so it's due
    c._last_sensors_sent = int(time.time()) - 3600 - 10

    c.run_iteration()
    assert called.get("telemetry") is True
    assert called.get("sensors") is True

import json
import sys
import time
from pathlib import Path
import importlib.util


def _load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)
    return module


def test_build_telemetry_includes_home_assistant():
    repo_root = Path(__file__).resolve().parents[3]
    tele_path = repo_root / "central-core-hub" / "telemetry.py"
    tele = _load_module(tele_path, "telemetry_testmod")

    ha_info = {
        "installation_method": "Home Assistant OS",
        "core": "2025.11.3",
        "supervisor": "2025.11.5",
        "operating_system": "16.3",
        "frontend": "20251105.1",
    }

    raw = tele.build_telemetry("cid-test", home_assistant=ha_info)
    assert raw is not None
    data = json.loads(raw)
    assert "home_assistant" in data
    assert data["home_assistant"].get("core") == "2025.11.3"
    assert data.get("ha_version") == "2025.11.3"


def test_ha_websocket_writes_version_to_options(tmp_path, monkeypatch):
    # Load the ha_client module from the repo
    repo_root = Path(__file__).resolve().parents[3]
    ha_path = repo_root / "central-core-hub" / "ha_client.py"
    ha = _load_module(ha_path, "ha_client_testmod_ws")

    # Redirect OPTIONS_PATH to a temp file so unit test doesn't touch /data
    opts_file = tmp_path / "options.json"
    monkeypatch.setattr(ha, "OPTIONS_PATH", str(opts_file))

    # Fake websocket object that will return the handshake messages and a
    # get_config result containing the version.
    class FakeWS:
        def __init__(self, msgs):
            self._msgs = msgs[:]

        def send(self, data):
            # accept and ignore
            return None

        def recv(self):
            if self._msgs:
                return json.dumps(self._msgs.pop(0))
            time.sleep(0.05)
            return ""

        def close(self):
            return None

    msgs = [
        {"type": "auth_required"},
        {"type": "auth_ok"},
        {"type": "result", "id": 2, "result": {"version": "2025.11.3"}},
    ]

    # Monkeypatch websocket.create_connection to return our FakeWS
    class FakeWSModule:
        def create_connection(self, *args, **kwargs):
            return FakeWS(msgs)

    monkeypatch.setattr(ha, "websocket", FakeWSModule())

    # Start listener; it should write the ha_version into the options file
    listener = ha.HAWebSocketListener("http://ha.local", "tok", on_event=None, log_fn=lambda m: None)
    started = listener.start()
    assert started is True

    # Wait up to 2s for the options file to be written
    deadline = time.time() + 2.0
    while time.time() < deadline and not opts_file.exists():
        time.sleep(0.05)

    # Stop the listener thread
    listener.stop()

    assert opts_file.exists(), "options.json not written by websocket listener"
    data = json.loads(opts_file.read_text())
    assert data.get("ha_version") == "2025.11.3"
    # Ensure in-memory cache was also populated
    assert ha.get_ha_version() == "2025.11.3"


def test_ha_websocket_auth_message_writes_version(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[3]
    ha_path = repo_root / "central-core-hub" / "ha_client.py"
    ha = _load_module(ha_path, "ha_client_testmod_ws_auth")

    opts_file = tmp_path / "options.json"
    monkeypatch.setattr(ha, "OPTIONS_PATH", str(opts_file))

    class FakeWS:
        def __init__(self, msgs):
            self._msgs = msgs[:]

        def send(self, data):
            return None

        def recv(self):
            if self._msgs:
                return json.dumps(self._msgs.pop(0))
            time.sleep(0.05)
            return ""

        def close(self):
            return None

    msgs = [
        {"type": "auth_required", "ha_version": "2025.12.1"},
        {"type": "auth_ok"},
    ]

    class FakeWSModule:
        def create_connection(self, *args, **kwargs):
            return FakeWS(msgs)

    monkeypatch.setattr(ha, "websocket", FakeWSModule())

    listener = ha.HAWebSocketListener("http://ha.local", "tok", on_event=None, log_fn=lambda m: None)
    assert listener.start() is True

    deadline = time.time() + 2.0
    while time.time() < deadline and not opts_file.exists():
        time.sleep(0.05)

    listener.stop()
    assert opts_file.exists()
    data = json.loads(opts_file.read_text())
    assert data.get("ha_version") == "2025.12.1"
    assert ha.get_ha_version() == "2025.12.1"


def test_resolve_ha_version_uses_mqtt_options(tmp_path, monkeypatch):
    repo_root = Path(__file__).resolve().parents[3]
    ha_path = repo_root / "central-core-hub" / "ha_client.py"
    mqtt_path = repo_root / "central-core-hub" / "mqtt_client.py"

    spec = importlib.util.spec_from_file_location("ha_client", str(ha_path))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load ha_client spec")
    ha_mod = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(ha_mod)
    monkeypatch.setitem(sys.modules, "ha_client", ha_mod)

    opts_file = tmp_path / "mqtt_options.json"
    opts_file.write_text(json.dumps({"ha_version": "2025.12.5"}))
    monkeypatch.setenv("MQTT_OPTIONS_PATH", str(opts_file))
    monkeypatch.setattr(ha_mod, "OPTIONS_PATH", "/tmp/unused-options.json")

    mqtt_mod = _load_module(mqtt_path, "mqtt_client_testmod_for_ha")
    client = object.__new__(mqtt_mod.CentralCoreClient)
    client._ha_version_cache = None
    client.ha_api_url = None
    client.ha_api_token = None

    assert mqtt_mod.CentralCoreClient._resolve_ha_version(client) == "2025.12.5"


def _load_mqtt():
    src = Path(__file__).resolve().parents[3] / "central-core-hub" / "mqtt_client.py"
    return _load_module(src, "mqtt_client_ha_obs")


def test_ha_state_event_payload_contains_observed_key():
    mod = _load_mqtt()
    c = mod.CentralCoreClient({"client_id": "hub1"})
    publishes = []
    c._publish = lambda topic, payload, **kw: publishes.append((topic, payload))
    c.preferred_sensors_topic = "sensors/test"
    c._selected_sensors_set = {"sensor.temperature"}
    c._selected_sensor_cache = {}

    entity_id = "sensor.temperature"
    new_state = {
        "state": "22.5",
        "attributes": {"friendly_name": "Temperature"},
        "last_changed": "2024-01-15T10:30:00Z",
        "last_updated": "2024-01-15T10:30:00Z",
    }
    c._on_ha_state_event(entity_id, new_state)

    assert len(publishes) == 1
    payload = json.loads(publishes[0][1])
    assert "observed" in payload, "Payload must contain 'observed' key"
    assert entity_id in payload["observed"]


def test_publish_sensors_with_default_filter_uses_poll_schema():
    mod = _load_mqtt()
    c = mod.CentralCoreClient({"client_id": "hub1"})
    c.ha_api_url = "http://ha.local"
    c.ha_api_token = "tok"
    c.preferred_sensors_topic = "sensors/test"
    c.safe_device_classes = ["motion"]
    publishes = []
    c._publish = lambda topic, payload, **kw: publishes.append((topic, payload))

    sensors = [
        {
            "entity_id": "binary_sensor.motion",
            "state": "on",
            "attributes": {"device_class": "motion", "friendly_name": "Motion"},
            "last_changed": "2024-01-15T10:30:00Z",
            "last_updated": "2024-01-15T10:30:00Z",
        }
    ]
    c._filter_sensors_by_device_class = lambda s, dc: s

    # Patch fetch_sensors at module level
    orig_fetch = mod.fetch_sensors
    mod.fetch_sensors = lambda url, token: sensors
    try:
        c.publish_sensors_with_default_filter()
    finally:
        mod.fetch_sensors = orig_fetch

    assert len(publishes) == 1, "Expected one publish"
    payload = json.loads(publishes[0][1])
    assert "data" in payload, "Must use poll schema with 'data' key"
    assert "names" in payload
    assert "enabled" in payload
    assert "attributes" in payload
    assert "observed" in payload
    assert "binary_sensor.motion" in payload["data"]

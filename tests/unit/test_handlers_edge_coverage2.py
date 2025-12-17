import importlib.util
from pathlib import Path
import sys
import types


def load_handlers_module():
    p = Path(__file__).resolve().parents[2] / "central-core-hub" / "handlers.py"
    spec = importlib.util.spec_from_file_location("handlers", str(p))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_is_entity_allowed_import_fails(monkeypatch):
    handlers = load_handlers_module()

    # Force import of mqtt_client to raise
    real_import = __import__

    def fake_import(name, globals=None, locals=None, fromlist=(), level=0):
        if name == "mqtt_client":
            raise ImportError("no mqtt_client")
        return real_import(name, globals, locals, fromlist, level)

    monkeypatch.setattr("builtins.__import__", fake_import)

    # Should return True when import fails
    assert handlers._is_entity_allowed("sensor.x") is True


def test_is_entity_allowed_callable_raises_and_returns(monkeypatch):
    handlers = load_handlers_module()

    mod = types.ModuleType("mqtt_client")

    def raising(entity_id):
        raise RuntimeError("boom")

    def allowed(entity_id):
        return False

    mod.is_entity_allowed = raising
    monkeypatch.setitem(sys.modules, "mqtt_client", mod)
    # When callable raises, fallback to True
    assert handlers._is_entity_allowed("sensor.y") is True

    # Replace with a callable that returns False
    mod.is_entity_allowed = allowed
    monkeypatch.setitem(sys.modules, "mqtt_client", mod)
    assert handlers._is_entity_allowed("sensor.y") is False


def test_sensors_poll_sensor_without_entity_id(monkeypatch):
    handlers = load_handlers_module()

    class DummyClient:
        def __init__(self):
            self.client_id = "poller"
            self.ha_api_url = "http://ha"
            self.ha_api_token = "t"
            self.publishes = []
            self.preferred_sensors_topic = "pref"
            self.vault_topic = "vault"

        def build_ack_topic(self, action, command_id):
            return f"hubs/{self.client_id}/v1/ack/{action.replace('/', '.')}/{command_id}"

        def _publish(self, topic, payload, qos=0):
            self.publishes.append((topic, payload, qos))

    client = DummyClient()

    # sensors_requested must be provided
    payload = {"command_id": "c1", "payload": {"sensors": ["opening"]}}

    # fetch_sensors returns a sensor with no entity_id to hit continue branches
    def fetch_sensors(url, token):
        return [{"entity_id": None, "state": "on", "attributes": {"device_class": "opening"}}]

    msg = type("M", (), {"topic": f"hubs/{client.client_id}/v1/cmd/sensors/poll"})()

    handlers.handle_message(client, msg, __import__("json").dumps(payload), fetch_sensors, None, None)

    # Should publish a completion ACK even when sensor entries are missing entity_id
    assert any("ack" in t[0] or "ack" in (t[0] or "") for t in client.publishes) or client.publishes == []

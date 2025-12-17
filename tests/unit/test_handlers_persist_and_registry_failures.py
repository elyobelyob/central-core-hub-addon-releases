import json
import importlib.util
from pathlib import Path
import sys
import os


def load_handlers_module():
    p = Path(__file__).resolve().parents[2] / "central-core-hub" / "handlers.py"
    spec = importlib.util.spec_from_file_location("handlers", str(p))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class DummyClient:
    def __init__(self, client_id="c"):
        self.client_id = client_id
        self.publishes = []
        self.registry_token = None
        self.options = None

    def build_ack_topic(self, action, command_id):
        return f"hubs/{self.client_id}/v1/ack/{action.replace('/', '.')}/{command_id}"

    def _publish(self, topic, payload, qos=0):
        self.publishes.append((topic, payload, qos))


def test_registry_write_failure(monkeypatch, tmp_path):
    handlers = load_handlers_module()
    client = DummyClient("reg1")
    client.registry_token = "tok"

    # Provide mqtt_client module with SENSOR_REGISTRY path
    mod = type("M", (), {})()
    mod.SENSOR_REGISTRY = str(tmp_path / "reg.json")
    sys.modules["mqtt_client"] = mod

    # Make pathlib.Path.replace raise to simulate atomic rename failure
    import pathlib

    def raise_replace(self, target):
        raise OSError("rename failed")

    monkeypatch.setattr(pathlib.Path, "replace", raise_replace)

    payload = {"command_id": "c", "payload": {"entries": [], "token": "tok"}}
    msg = type("M", (), {"topic": f"hubs/{client.client_id}/v1/cmd/registry/set"})()

    handlers.handle_message(client, msg, json.dumps(payload), None, None, None)

    # Should publish a failed completion because replace raised
    joined = "\n".join(p[1] for p in client.publishes)
    assert "failed" in joined.lower()


def test_registry_env_token_auth_fail(monkeypatch):
    handlers = load_handlers_module()
    client = DummyClient("reg2")

    os.environ["REGISTRY_TOKEN"] = "envtok"

    payload = {"command_id": "c2", "payload": {"entries": []}}
    msg = type("M", (), {"topic": f"hubs/{client.client_id}/v1/cmd/registry/set"})()

    handlers.handle_message(client, msg, json.dumps(payload), None, None, None)

    joined = "\n".join(p[1] for p in client.publishes)
    assert "auth_failed" in joined.lower()


def test_sensors_set_string_list_persist_exception(monkeypatch, tmp_path):
    handlers = load_handlers_module()
    client = DummyClient("s1")
    client.vault_topic = "vault"
    client.preferred_sensors_topic = "pref"
    client.client_id = "s1"

    # monkeypatch fetch_sensors to return a simple sensor
    def fetch_sensors(url, token):
        return [{"entity_id": "sensor.a", "state": "on", "attributes": {}}]

    # Force pathlib.Path.replace to raise during persistence
    import pathlib

    def raise_replace(self, target):
        raise OSError("persist fail")

    monkeypatch.setattr(pathlib.Path, "replace", raise_replace)

    payload = {"command_id": "c3", "payload": {"sensors": ["sensor.a"]}}
    msg = type("M", (), {"topic": f"hubs/{client.client_id}/v1/cmd/sensors/set"})()

    # Should not raise despite persistence failure
    handlers.handle_message(client, msg, json.dumps(payload), fetch_sensors, None, None)

    # Completion ACK should be published
    assert any("ack" in t[0] for t in client.publishes) or any("completed" in (p[1] or "") for p in client.publishes)

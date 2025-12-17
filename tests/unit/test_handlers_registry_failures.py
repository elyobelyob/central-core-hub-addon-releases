import importlib.util
import json
import sys
import pathlib
from pathlib import Path
from types import SimpleNamespace


def load_handlers():
    src = Path(__file__).resolve().parents[2] / "central-core-hub" / "handlers.py"
    spec = importlib.util.spec_from_file_location("handlers", str(src))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["handlers"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_registry_auth_failure(monkeypatch):
    handlers = load_handlers()

    published = []

    class FakeClient:
        def __init__(self):
            self.client_id = "test-client"
            self.options = {"registryToken": "secret"}

        def build_ack_topic(self, action, cid):
            return f"hubs/{self.client_id}/v1/ack/{action.replace('/', '.')}/{cid}"

        def _publish(self, topic, payload, qos=0):
            published.append(json.loads(payload))

    client = FakeClient()
    msg = SimpleNamespace()
    msg.topic = f"hubs/{client.client_id}/v1/cmd/registry/set"
    payload = {"command_id": "c1", "payload": {"entries": []}}

    handlers.handle_message(client, msg, json.dumps(payload), None, None, None)

    assert any(obj.get("result", {}).get("reason") == "auth_failed" for obj in published)


def test_registry_atomic_write_failure(monkeypatch, tmp_path):
    handlers = load_handlers()

    published = []

    class FakeMC:
        SENSOR_REGISTRY = str(tmp_path / "registry.json")

        def reload_sensor_registry(self):
            return None

    monkeypatch.setitem(sys.modules, "mqtt_client", FakeMC)

    def _bad_replace(self, target):
        raise RuntimeError("atomic fail")

    monkeypatch.setattr(pathlib.Path, "replace", _bad_replace, raising=True)

    class FakeClient:
        def __init__(self):
            self.client_id = "test-client"

        def build_ack_topic(self, action, cid):
            return f"hubs/{self.client_id}/v1/ack/{action.replace('/', '.')}/{cid}"

        def _publish(self, topic, payload, qos=0):
            try:
                published.append(json.loads(payload))
            except Exception:
                published.append(payload)

    client = FakeClient()

    msg = SimpleNamespace()
    msg.topic = f"hubs/{client.client_id}/v1/cmd/registry/set"
    payload = {"command_id": "c2", "payload": {"entries": []}}

    handlers.handle_message(client, msg, json.dumps(payload), None, None, None)

    assert any(isinstance(obj.get("result"), dict) and not obj["result"].get("success") for obj in published)

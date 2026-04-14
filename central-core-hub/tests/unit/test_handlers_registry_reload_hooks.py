import importlib.util
import pathlib
import json
import sys
import types


def _load_handlers():
    base = pathlib.Path(__file__).parents[2]
    src = base / "handlers.py"
    spec = importlib.util.spec_from_file_location("handlers", str(src))
    mod = importlib.util.module_from_spec(spec)
    if spec is None or spec.loader is None:
        raise ImportError("could not load handlers spec")
    spec.loader.exec_module(mod)
    return mod


handlers = _load_handlers()


class DummyClient:
    def __init__(self):
        self.client_id = "cid"
        self.published = []

    def build_ack_topic(self, action, command_id):
        return f"hubs/{self.client_id}/v1/ack/{action}/{command_id}"

    def _publish(self, topic, payload, qos=0):
        self.published.append((topic, payload, qos))


def test_registry_set_calls_mqtt_reload_and_writes_file(tmp_path, monkeypatch):
    # Prepare fake mqtt_client module with SENSOR_REGISTRY path and reload helper
    mod = types.ModuleType("mqtt_client")
    target = tmp_path / "SENSOR_REGISTRY.json"
    mod.SENSOR_REGISTRY = str(target)

    def _reload():
        mod._reloaded = True

    mod.reload_sensor_registry = _reload
    sys.modules["mqtt_client"] = mod

    client = DummyClient()
    topic = f"hubs/{client.client_id}/v1/cmd/registry/set"
    payload = json.dumps({"command_id": "c-reg", "payload": {"entries": []}})

    handlers.handle_message(client, type("M", (), {"topic": topic})(), payload, None, None, None)

    # ensure file was written and reload called
    assert target.exists()
    assert getattr(mod, "_reloaded", False) is True
    # completion ack should indicate success
    comp = None
    for t, payload_str, qos in client.published:
        try:
            p = json.loads(payload_str)
        except Exception:
            continue
        if p.get("status") == "completed":
            comp = p
            break
    assert comp is not None
    assert comp.get("result", {}).get("success") is True


def test_registry_set_client_reload_hook_exception_handled(tmp_path, monkeypatch):
    # mqtt_client absent, so handlers will write local file and call client.reload_sensor_registry
    if "mqtt_client" in sys.modules:
        del sys.modules["mqtt_client"]

    class ClientWithBadHook(DummyClient):
        def reload_sensor_registry(self):
            raise RuntimeError("boom")

    client = ClientWithBadHook()
    topic = f"hubs/{client.client_id}/v1/cmd/registry/set"
    payload = json.dumps({"command_id": "c-reg2", "payload": {"entries": []}})

    handlers.handle_message(client, type("M", (), {"topic": topic})(), payload, None, None, None)

    # completion ack should still indicate success despite reload hook error
    comp = None
    for t, payload_str, qos in client.published:
        try:
            p = json.loads(payload_str)
        except Exception:
            continue
        if p.get("status") == "completed":
            comp = p
            break
    assert comp is not None
    assert comp.get("result", {}).get("success") is True

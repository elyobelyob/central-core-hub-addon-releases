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
    mod = types.ModuleType("mqtt_client")
    target = tmp_path / "SENSOR_REGISTRY.json"
    mod.SENSOR_REGISTRY = str(target)

    def _reload():
        mod._reloaded = True

    mod.reload_sensor_registry = _reload
    monkeypatch.setitem(sys.modules, "mqtt_client", mod)

    client = DummyClient()
    client.registry_token = "hook-token"
    topic = f"hubs/{client.client_id}/v1/cmd/registry/set"

    # wrong token: nothing written, no reload
    bad = json.dumps({"command_id": "c-reg0", "payload": {"token": "nope", "entries": []}})
    handlers.handle_message(client, type("M", (), {"topic": topic})(), bad, None, None, None)
    assert not target.exists()
    assert not getattr(mod, "_reloaded", False)
    assert _secure_final_ack(client.published)["result"]["reason"] == "auth_failed"

    payload = json.dumps({"command_id": "c-reg", "payload": {"token": "hook-token", "entries": []}})
    handlers.handle_message(client, type("M", (), {"topic": topic})(), payload, None, None, None)
    assert target.exists()
    assert "hook-token" not in target.read_text()
    assert getattr(mod, "_reloaded", False) is True
    comp = _secure_final_ack(client.published)
    assert comp["status"] == "completed"
    assert comp["result"].get("success") is True


def test_registry_set_client_reload_hook_exception_handled(tmp_path, monkeypatch):
    # mqtt_client absent: handlers write next to handlers.py and call client.reload_sensor_registry
    monkeypatch.delitem(sys.modules, "mqtt_client", raising=False)
    import builtins

    real_import = builtins.__import__

    def no_mqtt_client(name, *a, **k):
        if name == "mqtt_client":
            raise ImportError("absent for this test")
        return real_import(name, *a, **k)

    monkeypatch.setattr(builtins, "__import__", no_mqtt_client)

    class ClientWithBadHook(DummyClient):
        registry_token = "hook-token"

        def reload_sensor_registry(self):
            raise RuntimeError("boom")

    client = ClientWithBadHook()
    topic = f"hubs/{client.client_id}/v1/cmd/registry/set"
    payload = json.dumps({"command_id": "c-reg2", "payload": {"token": "hook-token", "entries": []}})
    target = pathlib.Path(__file__).parents[2] / "SENSOR_REGISTRY_from_mqtt.json"
    try:
        handlers.handle_message(client, type("M", (), {"topic": topic})(), payload, None, None, None)
        comp = _secure_final_ack(client.published)
        # still a success despite the reload hook error
        assert comp["status"] == "completed"
        assert comp["result"].get("success") is True
    finally:
        try:
            target.unlink()
        except Exception:
            pass


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

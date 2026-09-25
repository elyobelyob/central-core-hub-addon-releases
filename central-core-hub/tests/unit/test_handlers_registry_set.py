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


class FakeClient:
    def __init__(self, client_id="cid"):
        self.client_id = client_id
        self.publishes = []

    def _publish(self, topic, payload, qos=0):
        self.publishes.append((topic, payload, qos))

    def build_ack_topic(self, action, command_id):
        return f"hubs/{self.client_id}/v1/ack/{action}/{command_id}"


def test_registry_set_auth_failed():
    client = FakeClient()
    # require token on client to force auth check
    client.registry_token = "secret"

    msg = type("M", (), {"topic": f"hubs/{client.client_id}/v1/cmd/registry/set"})
    payload = {"command_id": "r1", "payload": {"token": "wrong", "entries": []}}

    handlers.handle_message(client, msg, json.dumps(payload), None, None, None)

    found = False
    for _, p, _ in client.publishes:
        try:
            obj = json.loads(p)
        except Exception:
            continue
        if obj.get("status") in ("failed", "completed"):
            res = obj.get("result") or {}
            if res.get("reason") == "auth_failed":
                found = True
                break
    assert found


def test_registry_set_success_writes_file(tmp_path, monkeypatch):
    client = FakeClient()
    client.registry_token = "file-token"
    target = tmp_path / "SENSOR_REGISTRY.json"
    called = {"v": False}

    def reload_sensor_registry():
        called["v"] = True

    mc = types.SimpleNamespace()
    mc.SENSOR_REGISTRY = str(target)
    mc.reload_sensor_registry = reload_sensor_registry
    monkeypatch.setitem(sys.modules, "mqtt_client", mc)

    msg = type("M", (), {"topic": f"hubs/{client.client_id}/v1/cmd/registry/set"})
    entries = [{"entity_id": "sensor.foo", "provide": True}]
    payload = {"command_id": "r2", "payload": {"token": "file-token", "entries": entries}}
    handlers.handle_message(client, msg, json.dumps(payload), None, None, None)

    assert target.exists()
    data = json.loads(target.read_text())
    assert data == {"entries": entries}
    assert called["v"] is True
    comp = _secure_final_ack(client.publishes)
    assert comp["status"] == "completed" and comp["result"] == {"success": True, "entries": 1}


def test_registry_set_refused_when_no_token_configured(tmp_path, monkeypatch):
    client = FakeClient()
    target = tmp_path / "SENSOR_REGISTRY.json"
    mc = types.SimpleNamespace(SENSOR_REGISTRY=str(target))
    monkeypatch.setitem(sys.modules, "mqtt_client", mc)
    monkeypatch.delenv("REGISTRY_TOKEN", raising=False)

    msg = type("M", (), {"topic": f"hubs/{client.client_id}/v1/cmd/registry/set"})
    payload = {"command_id": "r3", "payload": {"entries": [{"entity_id": "sensor.foo", "provide": True}]}}
    handlers.handle_message(client, msg, json.dumps(payload), None, None, None)

    assert not target.exists()
    comp = _secure_final_ack(client.publishes)
    assert comp["status"] == "failed"
    assert comp["result"]["reason"] == "registry_updates_disabled"


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

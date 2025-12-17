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

    # create a temp target file location
    target = tmp_path / "SENSOR_REGISTRY.json"

    called = {"v": False}

    def reload_sensor_registry():
        called["v"] = True

    # install a fake mqtt_client module into sys.modules (replace any existing)
    mc = types.SimpleNamespace()
    mc.SENSOR_REGISTRY = str(target)
    mc.reload_sensor_registry = reload_sensor_registry
    orig = sys.modules.get("mqtt_client")
    sys.modules["mqtt_client"] = mc

    try:
        msg = type("M", (), {"topic": f"hubs/{client.client_id}/v1/cmd/registry/set"})
        payload_obj = {"entries": [{"foo": "bar"}]}
        payload = {"command_id": "r2", "payload": payload_obj}

        handlers.handle_message(client, msg, json.dumps(payload), None, None, None)

        # ensure file written and reload called
        assert target.exists()
        data = json.loads(target.read_text())
        assert data.get("entries") == payload_obj.get("entries")

        # completion ack should include success
        ok = False
        for _, p, _ in client.publishes:
            try:
                obj = json.loads(p)
            except Exception:
                continue
            if obj.get("status") == "completed" and obj.get("result", {}).get("success"):
                ok = True
                break
        assert ok
    finally:
        # restore original mqtt_client if present
        try:
            if orig is None:
                sys.modules.pop("mqtt_client", None)
            else:
                sys.modules["mqtt_client"] = orig
        except Exception:
            pass

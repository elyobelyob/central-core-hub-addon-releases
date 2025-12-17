import importlib.util
import pathlib
import json
import sys


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


def test_registry_missing_payload_publishes_failed_ack():
    client = FakeClient()
    msg = type("M", (), {"topic": f"hubs/{client.client_id}/v1/cmd/registry/set"})
    # payload missing 'payload' key
    payload = {"command_id": "rm1"}

    handlers.handle_message(client, msg, json.dumps(payload), None, None, None)

    found = False
    for _, p, _ in client.publishes:
        try:
            obj = json.loads(p)
        except Exception:
            continue
        if obj.get("status") in ("failed", "completed"):
            res = obj.get("result") or {}
            if res.get("reason") == "missing_payload":
                found = True
                break
    assert found


def test_registry_set_with_env_token_succeeds(tmp_path, monkeypatch):
    client = FakeClient()
    # set env token expected
    monkeypatch.setenv("REGISTRY_TOKEN", "envsecret")

    # install fake mqtt_client pointing to tmp file and with reload hook
    target = tmp_path / "REG.json"
    called = {"r": False}

    def reload_sensor_registry():
        called["r"] = True

    mc = type("MC", (), {})()
    mc.SENSOR_REGISTRY = str(target)
    mc.reload_sensor_registry = reload_sensor_registry
    orig = sys.modules.get("mqtt_client")
    sys.modules["mqtt_client"] = mc

    try:
        msg = type("M", (), {"topic": f"hubs/{client.client_id}/v1/cmd/registry/set"})
        payload_obj = {"token": "envsecret", "entries": []}
        payload = {"command_id": "rt1", "payload": payload_obj}

        handlers.handle_message(client, msg, json.dumps(payload), None, None, None)

        assert target.exists()
        # check completion ack with success
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
        if orig is None:
            sys.modules.pop("mqtt_client", None)
        else:
            sys.modules["mqtt_client"] = orig

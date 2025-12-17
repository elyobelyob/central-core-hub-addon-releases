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


def _find_failed_reason(client):
    for _, p, _ in client.publishes:
        try:
            obj = json.loads(p)
        except Exception:
            continue
        if obj.get("status") in ("failed", "completed"):
            res = obj.get("result") or {}
            if res.get("reason"):
                return res.get("reason")
    return None


def test_registry_set_env_token_auth_fails(monkeypatch, tmp_path):
    client = FakeClient()
    # set env token expected
    monkeypatch.setenv("REGISTRY_TOKEN", "envsecret")

    # ensure mqtt_client is not present so handlers will attempt local write
    orig = sys.modules.get("mqtt_client")
    sys.modules["mqtt_client"] = None

    try:
        msg = type("M", (), {"topic": f"hubs/{client.client_id}/v1/cmd/registry/set"})
        payload_obj = {"token": "wrong", "entries": []}
        payload = {"command_id": "rnf1", "payload": payload_obj}

        handlers.handle_message(client, msg, json.dumps(payload), None, None, None)

        reason = _find_failed_reason(client)
        assert reason == "auth_failed"

        # file should NOT be written next to handlers.py
        target = pathlib.Path(__file__).parents[2] / "SENSOR_REGISTRY_from_mqtt.json"
        assert not target.exists()
    finally:
        if orig is None:
            sys.modules.pop("mqtt_client", None)
        else:
            sys.modules["mqtt_client"] = orig


def test_registry_set_client_token_auth_fails():
    client = FakeClient()
    # client provides registry_token via attribute
    client.registry_token = "clientsecret"

    # ensure mqtt_client is not present
    orig = sys.modules.get("mqtt_client")
    sys.modules["mqtt_client"] = None

    try:
        msg = type("M", (), {"topic": f"hubs/{client.client_id}/v1/cmd/registry/set"})
        payload_obj = {"token": "nope", "entries": []}
        payload = {"command_id": "rnf2", "payload": payload_obj}

        handlers.handle_message(client, msg, json.dumps(payload), None, None, None)

        reason = _find_failed_reason(client)
        assert reason == "auth_failed"
    finally:
        if orig is None:
            sys.modules.pop("mqtt_client", None)
        else:
            sys.modules["mqtt_client"] = orig

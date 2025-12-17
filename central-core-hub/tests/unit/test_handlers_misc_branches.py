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
        raise RuntimeError("boom")

    def trigger_addon_update(self, version=None):
        return {"success": True}


def test_config_ack_fallback_when_build_ack_raises():
    client = FakeClient()
    msg = type("M", (), {"topic": f"hubs/{client.client_id}/v1/cmd/config/update"})
    payload = {"command_id": "cfg1", "payload": {"version": "1.2.3"}}

    handlers.handle_message(client, msg, json.dumps(payload), None, None, None)

    # ensure fallback ack topic (config.update) was used and completion published
    expected_ack = f"hubs/{client.client_id}/v1/ack/config.update/cfg1"
    topics = [t for t, _, _ in client.publishes]
    assert expected_ack in topics
    # ensure a completion payload with success exists
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


def test__is_entity_allowed_returns_true_on_mqtt_error(monkeypatch):
    # install a fake mqtt_client that raises from is_entity_allowed
    orig = sys.modules.get("mqtt_client")
    mc = types.SimpleNamespace()

    def is_entity_allowed(_):
        raise Exception("nope")

    mc.is_entity_allowed = is_entity_allowed
    sys.modules["mqtt_client"] = mc
    try:
        assert handlers._is_entity_allowed("sensor.foo") is True
    finally:
        if orig is None:
            sys.modules.pop("mqtt_client", None)
        else:
            sys.modules["mqtt_client"] = orig

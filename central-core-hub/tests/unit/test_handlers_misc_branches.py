import time
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


def test_config_update_sends_no_ack_when_build_ack_raises():
    client = FakeClient()

    class Updater:
        def update(self, expected_version=None, before_install=None):
            return {"outcome": "up_to_date", "installed": "1.2.3", "latest": "1.2.3",
                    "auto_update": False, "reason": None}

    client.addon_updater = lambda: Updater()
    msg = type("M", (), {"topic": f"hubs/{client.client_id}/v1/cmd/config/update"})
    payload = {"command_id": "cfg1", "timestamp": time.time(), "payload": {"version": "1.2.3"}}

    handlers.handle_message(client, msg, json.dumps(payload), None, None, None)
    handlers.wait_for_update_worker(timeout=5)

    # no acknowledgement is sent to a topic nobody checked
    topics = [t for t, _, _ in client.publishes]
    assert not any("/ack/" in t for t in topics)
    assert client.publishes == []  # nothing at all: there is nowhere checked to send the result


def test__is_entity_allowed_denies_on_mqtt_error(monkeypatch):
    # install a fake mqtt_client that raises from is_entity_allowed
    orig = sys.modules.get("mqtt_client")
    mc = types.SimpleNamespace()

    def is_entity_allowed(_):
        raise Exception("nope")

    mc.is_entity_allowed = is_entity_allowed
    sys.modules["mqtt_client"] = mc
    try:
        assert handlers._is_entity_allowed("sensor.foo") is False  # fails closed
    finally:
        if orig is None:
            sys.modules.pop("mqtt_client", None)
        else:
            sys.modules["mqtt_client"] = orig

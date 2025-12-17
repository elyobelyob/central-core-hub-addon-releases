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
        self.preferred_sensors_topic = "tele/ps"
        self.ha_api_url = "http://ha"
        self.ha_api_token = "tok"

    def build_ack_topic(self, action, command_id):
        return f"hubs/{self.client_id}/v1/ack/{action}/{command_id}"

    def _publish(self, topic, payload, qos=0):
        self.published.append((topic, payload, qos))


class Msg:
    def __init__(self, topic):
        self.topic = topic


def test_is_entity_allowed_exception_falls_back_to_allow(monkeypatch):
    # Provide a mqtt_client.is_entity_allowed that raises
    mod = types.ModuleType("mqtt_client")
    def bad_allowed(ent):
        raise RuntimeError("boom")
    mod.is_entity_allowed = bad_allowed
    sys.modules["mqtt_client"] = mod

    client = DummyClient()
    topic = f"hubs/{client.client_id}/v1/cmd/sensors/poll"
    payload = json.dumps({"command_id": "c-allow", "payload": {"sensors": ["temperature"]}})

    def fetch_sensors(url, token):
        return [
            {"entity_id": "sensor.x", "state": "9", "attributes": {"device_class": "temperature"}}
        ]

    handlers.handle_message(client, Msg(topic), payload, fetch_sensors, None, None)

    # telemetry should have been published despite is_entity_allowed raising
    tele = None
    for t, payload_str, qos in client.published:
        if t == client.preferred_sensors_topic:
            tele = json.loads(payload_str)
            break
    assert tele is not None
    assert "sensor.x" in (tele.get("data") or {})

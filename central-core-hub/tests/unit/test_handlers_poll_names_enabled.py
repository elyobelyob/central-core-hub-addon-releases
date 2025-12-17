import importlib.util
import pathlib
import json


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
        self.vault_topic = "tele/vault"
        self.ha_api_url = "http://ha"
        self.ha_api_token = "tok"

    def build_ack_topic(self, action, command_id):
        return f"hubs/{self.client_id}/v1/ack/{action}/{command_id}"

    def _publish(self, topic, payload, qos=0):
        self.published.append((topic, payload, qos))


class Msg:
    def __init__(self, topic):
        self.topic = topic


def test_sensors_poll_names_and_enabled_maps():
    client = DummyClient()
    topic = f"hubs/{client.client_id}/v1/cmd/sensors/poll"
    payload = json.dumps({"command_id": "c-names", "payload": {"sensors": ["humidity"]}})

    # sensor missing friendly_name and disabled_by set -> names_map should use entity_id and enabled False
    def fetch_sensors(url, token):
        return [
            {
                "entity_id": "sensor.h1",
                "state": "5",
                "attributes": {"device_class": "humidity", "disabled_by": "user"},
            }
        ]

    handlers.handle_message(client, Msg(topic), payload, fetch_sensors, None, None)

    # find published telemetry on preferred_sensors_topic
    tele = None
    for t, payload_str, qos in client.published:
        if t == client.preferred_sensors_topic:
            tele = json.loads(payload_str)
            break
    assert tele is not None
    names = tele.get("names") or {}
    enabled = tele.get("enabled") or {}
    assert names.get("sensor.h1") == "sensor.h1"
    assert enabled.get("sensor.h1") is False

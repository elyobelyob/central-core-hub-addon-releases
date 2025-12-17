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
        self.ha_api_url = "http://ha"
        self.ha_api_token = "tok"
        self.preferred_sensors_topic = "tele/ps"

    def build_ack_topic(self, action, command_id):
        return f"hubs/{self.client_id}/v1/ack/{action}/{command_id}"

    def _publish(self, topic, payload, qos=0):
        self.published.append((topic, payload, qos))


class Msg:
    def __init__(self, topic):
        self.topic = topic


def test_sensors_poll_without_requested_sensors_publishes_nothing():
    client = DummyClient()
    topic = f"hubs/{client.client_id}/v1/cmd/sensors/poll"
    # payload has no 'sensors' key -> should return early and publish nothing
    payload = json.dumps({"command_id": "c-none", "payload": {}})

    handlers.handle_message(client, Msg(topic), payload, lambda a, b: [], None, None)

    # only possibly an ack was published; ensure no telemetry topic publish
    assert all(t != client.preferred_sensors_topic for t, *_ in client.published)

import time
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


class DummyClientTriggerFail:
    def __init__(self):
        self.client_id = "cid"
        self.published = []
        self.options = {}

    def build_ack_topic(self, action, command_id):
        return f"hubs/{self.client_id}/v1/ack/{action}/{command_id}"

    def _publish(self, topic, payload, qos=0):
        self.published.append((topic, payload, qos))

    def trigger_addon_update(self, version=None):
        raise RuntimeError("boom")


class DummyClientAckBad:
    def __init__(self):
        self.client_id = "cid"
        self.published = []
        self.preferred_sensors_topic = "tele/ps"
        self.ha_api_url = "http://ha"
        self.ha_api_token = "tok"

    def build_ack_topic(self, action, command_id):
        raise RuntimeError("no ack")

    def _publish(self, topic, payload, qos=0):
        self.published.append((topic, payload, qos))


class Msg:
    def __init__(self, topic):
        self.topic = topic


def test_sensors_poll_sends_no_ack_when_build_ack_topic_raises():
    client = DummyClientAckBad()
    topic = f"hubs/{client.client_id}/v1/cmd/sensors/poll"
    payload = json.dumps({"command_id": "c-poll", "timestamp": time.time(), "payload": {"sensors": ["temperature"]}})

    # provide one sensor that matches device_class 'temperature'
    def fetch_sensors(url, token):
        return [
            {
                "entity_id": "sensor.temp1",
                "state": "10",
                "attributes": {"device_class": "temperature"},
            }
        ]

    handlers.handle_message(client, Msg(topic), payload, fetch_sensors, None, None)

    # build_ack_topic raised: no acknowledgement is sent to a guessed topic
    assert not any("/ack/" in str(t) for t, _p, _q in client.published)

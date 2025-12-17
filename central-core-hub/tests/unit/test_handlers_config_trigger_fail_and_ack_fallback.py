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


def test_config_update_trigger_fails_publishes_failed_completion():
    client = DummyClientTriggerFail()
    topic = f"hubs/{client.client_id}/v1/cmd/config/update"
    payload = json.dumps({"command_id": "c-upd", "payload": {"version": "1.2.3"}})

    handlers.handle_message(client, Msg(topic), payload, None, None, None)

    # completion ack should be published and indicate failure
    comp = None
    for t, payload_str, qos in client.published:
        try:
            p = json.loads(payload_str)
        except Exception:
            continue
        if p.get("status") in ("completed", "failed"):
            comp = p
            break
    assert comp is not None
    res = comp.get("result") or {}
    assert res.get("success") is False
    assert res.get("error") == "trigger_failed"


def test_sensors_poll_build_ack_raises_falls_back_to_string_topic():
    client = DummyClientAckBad()
    topic = f"hubs/{client.client_id}/v1/cmd/sensors/poll"
    payload = json.dumps({"command_id": "c-poll", "payload": {"sensors": ["temperature"]}})

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

    # since build_ack_topic raised, code should publish completion to fallback string
    fallback = f"hubs/{client.client_id}/v1/ack/sensors.poll/c-poll"
    assert any(t == fallback for t, _p, _q in client.published)

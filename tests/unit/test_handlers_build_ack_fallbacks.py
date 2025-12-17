import json
import importlib.util
from pathlib import Path


def load_handlers_module():
    p = Path(__file__).resolve().parents[2] / "central-core-hub" / "handlers.py"
    spec = importlib.util.spec_from_file_location("handlers", str(p))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


class BadAckClient:
    def __init__(self, client_id="bad"):
        self.client_id = client_id
        self.publishes = []
        self.ha_api_url = "http://ha"
        self.ha_api_token = "t"
        self.preferred_sensors_topic = "pref"
        self.vault_topic = "vault"

    def build_ack_topic(self, action, command_id):
        raise RuntimeError("no build")

    def _publish(self, topic, payload, qos=0):
        self.publishes.append((topic, payload, qos))


class Msg:
    def __init__(self, topic):
        self.topic = topic


def test_config_update_build_ack_fallback():
    handlers = load_handlers_module()
    client = BadAckClient("Ccfg")
    cmd = {"command_id": "c1", "payload": {"version": "x"}}
    msg = Msg(f"hubs/{client.client_id}/v1/cmd/config/update")
    handlers.handle_message(client, msg, json.dumps(cmd), None, None, None)
    # Should have attempted to publish completion ack using fallback topic
    assert any("/v1/ack/" in t[0] for t in client.publishes)


def test_sensors_poll_build_ack_fallback():
    handlers = load_handlers_module()
    client = BadAckClient("Cpoll")
    cmd = {"command_id": "c2", "payload": {"sensors": ["opening"]}}
    msg = Msg(f"hubs/{client.client_id}/v1/cmd/sensors/poll")

    def fetch_sensors(url, token):
        return [{"entity_id": "sensor.a", "state": "on", "attributes": {"device_class": "opening"}}]

    handlers.handle_message(client, msg, json.dumps(cmd), fetch_sensors, None, None)
    assert any("/v1/ack/" in t[0] for t in client.publishes)


def test_sensors_set_build_ack_fallback_for_string_list():
    handlers = load_handlers_module()
    client = BadAckClient("Cset")
    cmd = {"command_id": "c3", "payload": {"sensors": ["sensor.a"]}}
    msg = Msg(f"hubs/{client.client_id}/v1/cmd/sensors/set")

    def fetch_sensors(url, token):
        return [{"entity_id": "sensor.a", "state": "off", "attributes": {}}]

    handlers.handle_message(client, msg, json.dumps(cmd), fetch_sensors, None, None)
    assert any("/v1/ack/" in t[0] for t in client.publishes)

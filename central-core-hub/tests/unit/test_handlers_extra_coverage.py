import importlib.util
import pathlib
import json
import sys
import pytest


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
        self.ha_readback_after_set = False
        self.selected_sensors = None

    def build_ack_topic(self, action, command_id):
        # intentionally raise for one test to hit fallback
        if action == "config/update":
            raise RuntimeError("boom")
        return f"hubs/{self.client_id}/v1/ack/{action}/{command_id}"

    def _publish(self, topic, payload, qos=0):
        self.published.append((topic, payload, qos))

    def trigger_addon_update(self, version=None):
        return {"success": True, "version": version}


class Msg:
    def __init__(self, topic):
        self.topic = topic


def test_handle_config_update_ack_and_completion():
    client = DummyClient()
    topic = f"hubs/{client.client_id}/v1/cmd/config/update"
    payload = json.dumps({"command_id": "cid1", "payload": {"version": "1.2.3"}})
    handlers.handle_message(client, Msg(topic), payload, None, None, None)
    # two publishes: ack and completion (ack uses fallback string since build_ack_topic raised)
    assert any("ack" in t for t, _, _ in client.published)


def test_handle_sensors_poll_filters_and_publish():
    client = DummyClient()
    topic = f"hubs/{client.client_id}/v1/cmd/sensors/poll"
    # payload requesting device class 'opening'
    payload = json.dumps({"command_id": "c2", "payload": {"sensors": ["opening"]}})

    def fetch_sensors(url, token):
        return [
            {
                "entity_id": "sensor.a",
                "state": "on",
                "attributes": {"device_class": "opening", "friendly_name": "A"},
            },
            {
                "entity_id": "sensor.b",
                "state": "off",
                "attributes": {"device_class": "motion"},
            },
        ]

    handlers.handle_message(client, Msg(topic), payload, fetch_sensors, None, None)
    # should publish preferred_sensors_topic and a completion ack
    assert any(client.preferred_sensors_topic == t for t, _, _ in client.published)
    assert any("ack" in t for t, _, _ in client.published)


    def test__load_handlers_importerror(monkeypatch):
        monkeypatch.setattr(importlib.util, "spec_from_file_location", lambda *a, **k: None)
        with pytest.raises(ImportError):
            _load_handlers()

def test_handle_sensors_set_selection_list_persistence(tmp_path, monkeypatch):
    client = DummyClient()
    topic = f"hubs/{client.client_id}/v1/cmd/sensors/set"
    payload = json.dumps({"command_id": "c3", "payload": {"sensors": ["sensor.x", "sensor.y"]}})

    # create a fake mqtt_client module with SELECTED_SENSORS_FILE pointing to tmp
    fake_mqtt = type(sys)('mqtt_client')
    fake_mqtt.SELECTED_SENSORS_FILE = str(tmp_path / "selected.json")
    sys.modules['mqtt_client'] = fake_mqtt

    def fetch_sensors(url, token):
        return [
            {"entity_id": "sensor.x", "state": "1", "attributes": {"friendly_name": "X"}},
            {"entity_id": "sensor.y", "state": "2", "attributes": {"friendly_name": "Y"}},
        ]

    handlers.handle_message(client, Msg(topic), payload, fetch_sensors, None, None)
    # selected file should exist
    sel = tmp_path / "selected.json"
    assert sel.exists()
    data = json.loads(sel.read_text())
    assert "sensor.x" in data and "sensor.y" in data
    # cleanup fake module
    del sys.modules['mqtt_client']

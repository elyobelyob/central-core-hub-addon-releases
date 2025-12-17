import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


def load_handlers():
    src = Path(__file__).resolve().parents[2] / "central-core-hub" / "handlers.py"
    spec = importlib.util.spec_from_file_location("handlers", str(src))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["handlers"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_sensors_set_with_missing_entity_and_selection(tmp_path, monkeypatch):
    handlers = load_handlers()

    fake_mc = SimpleNamespace()
    selected_file = tmp_path / "SELECTED_SENSORS.json"
    fake_mc.SELECTED_SENSORS_FILE = str(selected_file)
    fake_mc._log = lambda *a, **k: None
    monkeypatch.setitem(sys.modules, "mqtt_client", fake_mc)

    published = []

    class FakeClient:
        def __init__(self):
            self.client_id = "test-client"
            self.ha_api_url = "http://ha"
            self.ha_api_token = "token"
            self.preferred_sensors_topic = "pref"
            self.vault_topic = "vault"

        def build_ack_topic(self, action, cid):
            return f"hubs/{self.client_id}/v1/ack/{action.replace('/', '.')}/{cid}"

        def _publish(self, topic, payload, qos=0):
            published.append((topic, payload, qos))

    client = FakeClient()

    def fetch_sensors(_ha_url, _ha_token):
        return [
            {"entity_id": None, "state": "unknown"},
            {
                "entity_id": "sensor.ok",
                "state": "on",
                "attributes": {"device_class": "motion", "friendly_name": "OK"},
            },
        ]

    msg = SimpleNamespace()
    msg.topic = f"hubs/{client.client_id}/v1/cmd/sensors/set"
    payload = {"command_id": "c1", "payload": {"sensors": ["sensor.ok", "sensor.missing"]}}

    handlers.handle_message(client, msg, json.dumps(payload), fetch_sensors, None, None)

    assert selected_file.exists()
    ack = [p for p in published if "/ack/sensors.set/" in p[0]]
    assert ack, "expected completion ack"

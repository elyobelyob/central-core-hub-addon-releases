import importlib.util
import json
import sys
from pathlib import Path
from types import SimpleNamespace


def load_handlers():
    src = Path(__file__).resolve().parents[2] / "handlers.py"
    spec = importlib.util.spec_from_file_location("handlers", str(src))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["handlers"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_sensors_set_with_missing_entity_and_selection(tmp_path, monkeypatch):
    handlers = load_handlers()

    # Provide a fake mqtt_client module exposing SELECTED_SENSORS_FILE
    fake_mc = SimpleNamespace()
    selected_file = tmp_path / "SELECTED_SENSORS.json"
    fake_mc.SELECTED_SENSORS_FILE = str(selected_file)
    fake_mc._log = lambda *args, **kwargs: None
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

    # fetch_sensors returns one entry without entity_id and one valid
    def fetch_sensors(ha_url, ha_token):
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

    # Ensure a completion ack was published containing the selected list
    found_comp = False
    for t, p, q in published:
        try:
            obj = json.loads(p)
        except Exception:
            continue
        if isinstance(obj, dict) and obj.get("status") == "completed":
            res = obj.get("result", {})
            if "selected" in res:
                found_comp = True
                assert "sensor.ok" in res.get("selected")
    assert found_comp

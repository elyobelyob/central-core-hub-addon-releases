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
        self.ha_api_url = "http://ha"
        self.ha_api_token = "tok"
        self.preferred_sensors_topic = "pref/topic"
        self.vault_topic = "vault/topic"
        self.selected_sensors = None
        self.publishes = []

    def _publish(self, topic, payload, qos=0):
        self.publishes.append((topic, payload, qos))

    def build_ack_topic(self, action, command_id):
        return f"hubs/{self.client_id}/v1/ack/{action}/{command_id}"


def test_poll_with_no_matching_device_classes():
    client = FakeClient()

    # fetch_sensors returns sensors with device_class that won't match requested
    def fetch_sensors(url, token):
        return [
            {
                "entity_id": "sensor.a",
                "state": "1",
                "attributes": {"device_class": "motion", "friendly_name": "A"},
            },
            {
                "entity_id": "sensor.b",
                "state": "0",
                "attributes": {"device_class": "battery", "friendly_name": "B"},
            },
        ]

    # request device_class 'temperature' which none of the sensors have
    msg = type("M", (), {"topic": f"hubs/{client.client_id}/v1/cmd/sensors/poll"})
    payload = {"command_id": "p1", "payload": {"sensors": ["temperature"]}}

    handlers.handle_message(client, msg, json.dumps(payload), fetch_sensors, None, None)

    # ensure we published preferred_sensors_topic (fallback empty data) and a completion ack
    found_pref = False
    found_ack = False
    for t, p, _ in client.publishes:
        if t == client.preferred_sensors_topic:
            found_pref = True
        try:
            obj = json.loads(p)
        except Exception:
            continue
        if obj.get("status") == "completed":
            found_ack = True
    assert found_pref and found_ack


def test_set_string_list_persists_selected(tmp_path):
    client = FakeClient()

    # create fake mqtt_client with SELECTED_SENSORS_FILE pointing to tmp dir
    mc = types.SimpleNamespace()
    mc.SELECTED_SENSORS_FILE = str(tmp_path / "SELECTED_SENSORS.json")
    orig = sys.modules.get("mqtt_client")
    sys.modules["mqtt_client"] = mc

    try:
        msg = type("M", (), {"topic": f"hubs/{client.client_id}/v1/cmd/sensors/set"})
        payload = {"command_id": "s1", "payload": {"sensors": ["sensor.x", "sensor.y"]}}

        # fetch_sensors returns matching entities so monitor_telemetry constructed
        def fetch_sensors(url, token):
            return [
                {"entity_id": "sensor.x", "state": "on", "attributes": {}},
                {"entity_id": "sensor.y", "state": "off", "attributes": {}},
            ]

        handlers.handle_message(client, msg, json.dumps(payload), fetch_sensors, None, None)

        # ensure file exists at SELECTED_SENSORS_FILE
        target = pathlib.Path(mc.SELECTED_SENSORS_FILE)
        assert target.exists()
        data = json.loads(target.read_text())
        assert isinstance(data, list) and "sensor.x" in data and "sensor.y" in data
    finally:
        if orig is None:
            sys.modules.pop("mqtt_client", None)
        else:
            sys.modules["mqtt_client"] = orig

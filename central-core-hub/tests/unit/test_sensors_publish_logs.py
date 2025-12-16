import json
import importlib.util
import pathlib


def _load_handlers():
    base = pathlib.Path(__file__).resolve().parents[2]
    spec = importlib.util.spec_from_file_location("handlers", str(base / "handlers.py"))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load handlers spec")
    mod = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(mod)
    return mod


# load handlers implementation dynamically so tests work from any CWD
_handlers = _load_handlers()
handle_message = getattr(_handlers, "handle_message")


class Msg:
    def __init__(self, topic):
        self.topic = topic


class DummyClient:
    def __init__(self):
        self.client_id = "test-hub"
        self.preferred_sensors_topic = f"hubs/{self.client_id}/v1/telemetry/sensors"
        self.vault_topic = None
        # attributes used by handlers
        self.ha_api_url = None
        self.ha_api_token = None
        self.ha_readback_after_set = False
        self.published = []

    def _publish(self, topic, payload, qos=0):
        # mimic mqtt_client._publish behavior returning True
        entry = {"topic": topic, "payload": payload, "qos": qos}
        self.published.append(entry)
        # also print to stdout like runtime logging so test output shows it
        print(f"TEST PUBLISH -> topic={topic} payload={payload}")
        return True

    def build_ack_topic(self, action, command_id):
        return f"hubs/{self.client_id}/v1/ack/{action.replace('/', '.')}/{command_id}"


def fetch_sensors_dummy(ha_api_url, ha_api_token):
    # return a few sensors with device_class and timestamps
    return [
        {
            "entity_id": "sensor.temp",
            "state": "21.5",
            "attributes": {
                "device_class": "temperature",
                "friendly_name": "Temp",
                "unit_of_measurement": "°C",
            },
            "last_changed": "2025-12-07T10:00:00Z",
        },
        {
            "entity_id": "sensor.a",
            "state": "on",
            "attributes": {"device_class": "motion", "friendly_name": "Switch A"},
            "last_updated": "2025-12-07T10:00:05Z",
        },
    ]


def test_sensors_poll_prints_and_publishes():
    c = DummyClient()
    topic = f"hubs/{c.client_id}/v1/cmd/sensors/poll"
    # request specific device classes
    cmd = {"payload": {"sensors": ["temperature", "motion"]}}
    msg = Msg(topic)

    handle_message(c, msg, json.dumps(cmd), fetch_sensors_dummy, None, None, None)

    # find published telemetry
    pubs = [p for p in c.published if p["topic"] == c.preferred_sensors_topic]
    assert pubs, "no telemetry published"
    payload = json.loads(pubs[0]["payload"])
    print("PUBLISHED PAYLOAD:", json.dumps(payload, indent=2))
    # ensure per-sensor data present
    assert "data" in payload
    assert "sensor.temp" in payload["data"]
    assert "sensor.a" in payload["data"]
    # ensure observed exists
    assert "observed" in payload
    assert "sensor.temp" in payload["observed"]

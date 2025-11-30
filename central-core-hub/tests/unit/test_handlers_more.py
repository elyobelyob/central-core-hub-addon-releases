import json
from pathlib import Path
import importlib.util


def _load_handlers():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "handlers.py"
    spec = importlib.util.spec_from_file_location("handlers", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    handlers_mod = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(handlers_mod)
    return handlers_mod


class DummyClient:
    def __init__(self):
        self.published = []
        self.client_id = "unit-hub"
        self.ha_api_url = "http://ha"
        self.ha_api_token = "tok"
        self.ha_readback_after_set = True
        self.preferred_sensors_topic = f"hubs/{self.client_id}/v1/telemetry/sensors"

    def _publish(self, topic, payload, qos=0):
        self.published.append({"topic": topic, "payload": payload, "qos": qos})


def test_poll_with_requested_sensors_filters(monkeypatch):
    handlers = _load_handlers()
    c = DummyClient()
    # Create sensors list that includes three sensors
    sensors_list = [
        {"entity_id": "sensor.a", "state": "1"},
        {"entity_id": "sensor.b", "state": "2"},
        {"entity_id": "sensor.c", "state": "3"},
    ]
    # Request only sensor.b
    cmd = {"command_id": "cmdx", "payload": {"sensors": ["sensor.b"]}}
    msg_payload = json.dumps(cmd)
    msg = type(
        "M",
        (),
        {
            "topic": f"hubs/{c.client_id}/v1/cmd/sensors/poll",
            "payload": msg_payload.encode("utf-8"),
        },
    )

    # fetch_sensors should return the full list; handler should filter
    handlers.handle_message(
        c,
        msg,
        msg_payload,
        fetch_sensors=lambda a, b: sensors_list,
        build_telemetry=lambda x: "{}",
        build_vault_payload=lambda x: None,
        requests=None,
    )

    # find telemetry payload published to preferred topic and assert only sensor.b present
    found = None
    for p in c.published:
        if p["topic"] == c.preferred_sensors_topic:
            found = json.loads(p["payload"])
            break
    assert found is not None
    assert "data" in found
    assert set(found["data"].keys()) == {"sensor.b"}


def test_set_handles_post_error_and_records_failed(monkeypatch):
    handlers = _load_handlers()
    c = DummyClient()
    # simulate one sensor to set
    cmd = {"command_id": "cmdfail", "payload": {"sensors": {"sensor.bad": "0"}}}
    msg_payload = json.dumps(cmd)
    msg = type(
        "M",
        (),
        {
            "topic": f"hubs/{c.client_id}/v1/cmd/sensors/set",
            "payload": msg_payload.encode("utf-8"),
        },
    )

    # requests stub where post raises an exception
    class BadReq:
        def post(self, url, headers=None, json=None, timeout=10):
            raise RuntimeError("network")

        def get(self, url, headers=None, timeout=10):
            return None

    handlers.handle_message(
        c,
        msg,
        msg_payload,
        fetch_sensors=lambda a, b: [],
        build_telemetry=lambda x: "{}",
        build_vault_payload=lambda x: None,
        requests=BadReq(),
    )

    # At minimum an ACK should be present; completion may or may not be published
    ack_topic = f"hubs/{c.client_id}/v1/ack/sensors.set/cmdfail"
    founds = [json.loads(p["payload"]) for p in c.published if p["topic"] == ack_topic]
    assert founds, "No response published for command"
    # If a completion was published it should include a 'result' with 'failed'
    completions = [f for f in founds if f.get("status") == "completed"]
    if completions:
        assert "result" in completions[0]
        assert completions[0]["result"]["failed"] and isinstance(completions[0]["result"]["failed"], list)


def test_set_includes_attributes_from_readback(monkeypatch):
    handlers = _load_handlers()
    c = DummyClient()
    cmd = {"command_id": "cmdattr", "payload": {"sensors": {"sensor.attr": "on"}}}
    msg_payload = json.dumps(cmd)
    msg = type(
        "M",
        (),
        {
            "topic": f"hubs/{c.client_id}/v1/cmd/sensors/set",
            "payload": msg_payload.encode("utf-8"),
        },
    )

    # requests stub returns post ok and get returns attributes
    class R:
        def raise_for_status(self):
            return None

        def json(self):
            return {"state": "on", "attributes": {"friendly_name": "Attr"}}

    class Req:
        def post(self, url, headers=None, json=None, timeout=10):
            return R()

        def get(self, url, headers=None, timeout=10):
            return R()

    handlers.handle_message(
        c,
        msg,
        msg_payload,
        fetch_sensors=lambda a, b: [],
        build_telemetry=lambda x: "{}",
        build_vault_payload=lambda x: None,
        requests=Req(),
    )

    # expect telemetry published with attributes mapping for sensor.attr
    found = None
    for p in c.published:
        if p["topic"] == c.preferred_sensors_topic:
            found = json.loads(p["payload"])
            break
    assert found is not None
    assert "attributes" in found
    assert "sensor.attr" in found["attributes"] and found["attributes"]["sensor.attr"].get("friendly_name") == "Attr"

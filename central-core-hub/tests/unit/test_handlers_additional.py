import json
from pathlib import Path
import importlib.util


def _load_handlers():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "handlers.py"
    spec = importlib.util.spec_from_file_location("handlers_x", str(src))
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
        self.client_id = "unit-h"
        self.ha_api_url = ""
        self.ha_api_token = ""
        self.preferred_sensors_topic = f"hubs/{self.client_id}/v1/telemetry/sensors"

    def _publish(self, topic, payload, qos=0):
        self.published.append({"topic": topic, "payload": payload, "qos": qos})


def test_handle_poll_with_publish_exceptions():
    handlers = _load_handlers()
    c = DummyClient()

    # make _publish raise to exercise except branches
    def bad_publish(topic, payload, qos=0):
        raise RuntimeError("pub")

    c._publish = bad_publish

    msg = type("M", (), {"topic": f"hubs/{c.client_id}/v1/cmd/sensors/poll", "payload": b"{}"})
    # should not raise
    handlers.handle_message(
        c,
        msg,
        "{}",
        fetch_sensors=lambda a, b: [],
        build_telemetry=lambda x: "{}",
        build_vault_payload=lambda x: None,
        requests=None,
    )


def test_handle_set_with_dict_payload_and_readback(monkeypatch):
    handlers = _load_handlers()
    c = DummyClient()
    c.ha_api_url = "http://ha"
    c.ha_api_token = "tok"

    # requests stub: post ok, get returns readback
    class R:
        def raise_for_status(self):
            return None

        def json(self):
            return {"state": "on", "attributes": {"friendly_name": "Readback"}}

    class Req:
        def post(self, url, headers=None, json=None, timeout=10):
            return R()

        def get(self, url, headers=None, timeout=10):
            return R()

    cmd = {"command_id": "d1", "payload": {"sensors": {"sensor.x": "on"}}}
    msg = type(
        "M",
        (),
        {
            "topic": f"hubs/{c.client_id}/v1/cmd/sensors/set",
            "payload": json.dumps(cmd).encode("utf-8"),
        },
    )
    handlers.handle_message(
        c,
        msg,
        json.dumps(cmd),
        fetch_sensors=lambda a, b: [],
        build_telemetry=lambda x: "{}",
        build_vault_payload=lambda x: None,
        requests=Req(),
    )
    # should have published at least an ACK
    ack_topic = f"hubs/{c.client_id}/v1/ack/sensors.set/{cmd['command_id']}"
    assert any(p["topic"] == ack_topic for p in c.published)


def test_handle_poll_boolean_and_numeric_coercion():
    handlers = _load_handlers()
    c = DummyClient()
    sensors_list = [
        {"entity_id": "sensor.a", "state": "on"},
        {"entity_id": "sensor.b", "state": "off"},
        {"entity_id": "sensor.c", "state": "true"},
        {"entity_id": "sensor.d", "state": "false"},
        {"entity_id": "sensor.e", "state": "3.14"},
        {"entity_id": "sensor.f", "state": "7"},
    ]
    cmd = {"command_id": "cb", "payload": {}}
    msg = type(
        "M",
        (),
        {
            "topic": f"hubs/{c.client_id}/v1/cmd/sensors/poll",
            "payload": json.dumps(cmd).encode("utf-8"),
        },
    )
    handlers.handle_message(
        c,
        msg,
        json.dumps(cmd),
        fetch_sensors=lambda a, b: sensors_list,
        build_telemetry=lambda x: "{}",
        build_vault_payload=lambda x: None,
        requests=None,
    )
    tele = None
    for p in c.published:
        if p["topic"] == c.preferred_sensors_topic:
            tele = json.loads(p["payload"])
            break
    assert tele is not None
    data = tele.get("data")
    # Preserve raw HA-provided values (no coercion)
    assert data["sensor.a"] == "on"
    assert data["sensor.b"] == "off"
    assert data["sensor.c"] == "true"
    assert data["sensor.d"] == "false"
    assert data["sensor.e"] == "3.14"
    assert data["sensor.f"] == "7"

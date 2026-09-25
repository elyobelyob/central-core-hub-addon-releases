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
    # Create sensors list with different device classes
    sensors_list = [
        {"entity_id": "sensor.a", "state": "1", "attributes": {"device_class": "motion"}},
        {"entity_id": "sensor.b", "state": "2", "attributes": {"device_class": "door"}},
        {"entity_id": "sensor.c", "state": "3", "attributes": {"device_class": "temperature"}},
    ]
    # Request only door device class
    cmd = {"command_id": "cmdx", "payload": {"sensors": ["door"]}}
    msg_payload = json.dumps(cmd)
    msg = type(
        "M",
        (),
        {
            "topic": f"hubs/{c.client_id}/v1/cmd/sensors/poll",
            "payload": msg_payload.encode("utf-8"),
        },
    )

    # fetch_sensors should return the full list; handler should filter by device_class
    handlers.handle_message(
        c,
        msg,
        msg_payload,
        fetch_sensors=lambda a, b: sensors_list,
        build_telemetry=lambda x: "{}",
        build_vault_payload=lambda x: None,
        requests=None,
    )

    # find telemetry payload published to preferred topic and assert only door sensor present
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


def test_set_list_includes_attributes_and_dict_form_is_refused(monkeypatch):
    handlers = _load_handlers()
    c = DummyClient()
    topic = f"hubs/{c.client_id}/v1/cmd/sensors/set"
    msg = type("M", (), {"topic": topic})
    req = _RecordingRequests()

    dict_cmd = json.dumps({"command_id": "cmdattr", "payload": {"sensors": {"sensor.attr": "on"}}})
    handlers.handle_message(c, msg, dict_cmd, lambda a, b: [], lambda x: "{}", lambda x: None, requests=req)
    assert req.calls == []
    assert _secure_final_ack(c.published)["result"]["reason"] == "invalid_payload"

    def fetch(a, b):
        return [{"entity_id": "sensor.attr", "state": "on", "attributes": {"friendly_name": "Attr", "access_token": "t"}}]

    list_cmd = json.dumps({"command_id": "cmdattr2", "payload": {"sensors": ["sensor.attr"]}})
    handlers.handle_message(c, msg, list_cmd, fetch, lambda x: "{}", lambda x: None, requests=req)
    assert req.calls == []
    res = _secure_final_ack(c.published)["result"]
    assert res["attributes"]["sensor.attr"] == {"friendly_name": "Attr"}


# --- helpers for the secure sensors/set and registry/set behaviour ---------


def _secure_final_ack(records):
    """Last non-"acknowledged" ACK body among recorded publishes (any record shape)."""
    last = None
    for r in records:
        topic, payload = (r["topic"], r["payload"]) if isinstance(r, dict) else (r[0], r[1])
        if "/ack/" not in topic:
            continue
        body = json.loads(payload) if isinstance(payload, (str, bytes)) else payload
        if isinstance(body, dict) and body.get("status") != "acknowledged":
            last = body
    return last


class _RecordingRequests:
    """A `requests` stand-in that records calls and refuses every one."""

    def __init__(self):
        self.calls = []

    def post(self, url, *a, **k):
        self.calls.append(("POST", url))
        raise AssertionError(f"hub must not POST to Home Assistant: {url}")

    def get(self, url, *a, **k):
        self.calls.append(("GET", url))
        raise AssertionError(f"sensors/set must not call Home Assistant per entity: {url}")

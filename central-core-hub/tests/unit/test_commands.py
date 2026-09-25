import json
import importlib.util
from pathlib import Path


def _load_client_module():
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    spec = importlib.util.spec_from_file_location("mqtt_client", str(src))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)
    return module


class DummyClient:
    def __init__(self):
        self.published = []

    def publish(self, topic, payload, qos=0):
        # record a tuple; mimic paho return
        self.published.append({"topic": topic, "payload": payload, "qos": qos})

        class R:
            rc = 0

        return R()


class DummyMsg:
    def __init__(self, topic, payload_bytes):
        self.topic = topic
        self.payload = payload_bytes


def test_publish_sensors_calls_publish_and_updates_timestamp(monkeypatch):
    mod = _load_client_module()
    CentralCoreClient = mod.CentralCoreClient
    # stub fetch_sensors to return sample sensors
    sample = [
        {
            "entity_id": "sensor.temp",
            "state": "21.5",
            "attributes": {"friendly_name": "Temp"},
        },
        {
            "entity_id": "sensor.hum",
            "state": "42",
            "attributes": {"friendly_name": "Humidity"},
        },
    ]
    monkeypatch.setattr(mod, "fetch_sensors", lambda url, token, safe_classes=None: sample)

    options = {
        "client_id": "unit-hub",
        "ha_api_url": "http://ha",
        "ha_api_token": "tok",
    }
    c = CentralCoreClient(options)
    dummy = DummyClient()
    c._client = dummy
    assert c._last_sensors_sent == 0
    c.publish_sensors()
    # ensure preferred topic was published (legacy topics are not used in dev)
    topics = [p["topic"] for p in dummy.published]
    assert c.preferred_sensors_topic in topics
    # payloads are JSON; check structure: publish_sensors uses a 'sensors' list
    payload = json.loads(next(p["payload"] for p in dummy.published if p["topic"] == c.preferred_sensors_topic))
    assert "sensors" in payload and "timestamp" in payload
    # sensors list contains entries with entity_id
    ids = [s.get("entity_id") for s in payload["sensors"]]
    assert "sensor.temp" in ids
    assert c._last_sensors_sent > 0


def test_handle_sensors_poll_command_ack_and_completion(monkeypatch):
    mod = _load_client_module()
    CentralCoreClient = mod.CentralCoreClient
    # stub fetch_sensors
    sample = [
        {
            "entity_id": "sensor.temp",
            "state": "21.5",
            "attributes": {"friendly_name": "Temp", "device_class": "temperature"},
        },
    ]
    monkeypatch.setattr(mod, "fetch_sensors", lambda url, token, safe_classes=None: sample)

    options = {
        "client_id": "unit-hub",
        "ha_api_url": "http://ha",
        "ha_api_token": "tok",
    }
    c = CentralCoreClient(options)
    dummy = DummyClient()
    c._client = dummy

    command = {"command_id": "abc123", "action": "sensors/poll", "payload": {"sensors": ["temperature"]}}
    topic = f"hubs/{c.client_id}/v1/cmd/sensors/poll"
    msg = DummyMsg(topic, json.dumps(command).encode("utf-8"))

    c.on_message(None, None, msg)

    # Verify ACK and telemetry (preferred) were published
    topics = [p["topic"] for p in dummy.published]
    ack_topic = f"hubs/{c.client_id}/v1/ack/sensors.poll/{command['command_id']}"
    assert ack_topic in topics
    assert c.preferred_sensors_topic in topics
    # check that telemetry payload contains reported sensor
    tele_payload = json.loads(next(p["payload"] for p in dummy.published if p["topic"] == c.preferred_sensors_topic))
    assert "data" in tele_payload and "sensor.temp" in tele_payload["data"]
    # new: ensure friendly name and enabled status are included
    assert "names" in tele_payload and "sensor.temp" in tele_payload["names"]
    assert "enabled" in tele_payload and isinstance(tele_payload["enabled"].get("sensor.temp"), bool)


def test_handle_sensors_set_list_of_dicts_is_refused_without_calling_ha(monkeypatch):
    mod = _load_client_module()
    CentralCoreClient = mod.CentralCoreClient
    req = _RecordingRequests()
    monkeypatch.setattr(mod, "requests", req)

    c = CentralCoreClient({"client_id": "unit-hub", "ha_api_url": "http://ha", "ha_api_token": "tok"})
    dummy = DummyClient()
    c._client = dummy
    before = c.selected_sensors

    command = {
        "command_id": "set123",
        "action": "sensors/set",
        "payload": {
            "sensors": [
                {"entity_id": "sensor.temp", "state": "22.0"},
                {"entity_id": "sensor.hum", "state": "43"},
            ]
        },
    }
    topic = f"hubs/{c.client_id}/v1/cmd/sensors/set"
    c.on_message(None, None, DummyMsg(topic, json.dumps(command).encode("utf-8")))

    # no request of any kind reaches Home Assistant
    assert req.calls == []
    # ACK then a failed completion on the versioned ACK topic
    ack_topic = f"hubs/{c.client_id}/v1/ack/sensors.set/{command['command_id']}"
    acks = [json.loads(p["payload"]) for p in dummy.published if p["topic"] == ack_topic]
    assert [a["status"] for a in acks] == ["acknowledged", "failed"]
    assert acks[-1]["result"]["reason"] == "invalid_payload"
    # no telemetry is published and the selection is unchanged
    assert c.preferred_sensors_topic not in [p["topic"] for p in dummy.published]
    assert c.selected_sensors == before


def test_handle_sensors_set_string_list_reports_names_and_enabled(monkeypatch):
    mod = _load_client_module()
    CentralCoreClient = mod.CentralCoreClient
    req = _RecordingRequests()
    monkeypatch.setattr(mod, "requests", req)
    monkeypatch.setattr(
        mod,
        "fetch_sensors",
        lambda url, token, safe_classes=None: [
            {"entity_id": "sensor.temp", "state": "22.0", "attributes": {"unit_of_measurement": "°C"}},
            {"entity_id": "sensor.hum", "state": "43", "attributes": {"friendly_name": "Humidity"}},
        ],
    )
    c = CentralCoreClient({"client_id": "unit-hub", "ha_api_url": "http://ha", "ha_api_token": "tok"})
    dummy = DummyClient()
    c._client = dummy

    command = {"command_id": "set124", "action": "sensors/set", "payload": {"sensors": ["sensor.temp", "sensor.hum"]}}
    c.on_message(None, None, DummyMsg(f"hubs/{c.client_id}/v1/cmd/sensors/set", json.dumps(command).encode("utf-8")))

    assert req.calls == []
    assert c.selected_sensors == ["sensor.temp", "sensor.hum"]
    comp = _secure_final_ack(dummy.published)
    assert comp["status"] == "completed"
    res = comp["result"]
    assert res["data"] == {"sensor.temp": "22.0", "sensor.hum": "43"}
    assert res["names"] == {"sensor.temp": "sensor.temp", "sensor.hum": "Humidity"}
    assert isinstance(res["enabled"].get("sensor.temp"), bool)
    assert res["attributes"]["sensor.temp"] == {"unit_of_measurement": "°C"}


def test_handle_sensors_set_single_write_refused_even_without_readback(monkeypatch):
    """ha_readback_after_set no longer matters: a write form is refused outright."""
    mod = _load_client_module()
    CentralCoreClient = mod.CentralCoreClient
    req = _RecordingRequests()
    monkeypatch.setattr(mod, "requests", req)

    c = CentralCoreClient(
        {"client_id": "unit-hub", "ha_api_url": "http://ha", "ha_api_token": "tok", "ha_readback_after_set": False}
    )
    dummy = DummyClient()
    c._client = dummy
    command = {
        "command_id": "setno",
        "action": "sensors/set",
        "payload": {"sensors": [{"entity_id": "sensor.temp", "state": "22.5"}]},
    }
    c.on_message(None, None, DummyMsg(f"hubs/{c.client_id}/v1/cmd/sensors/set", json.dumps(command).encode("utf-8")))

    assert req.calls == []
    comp = _secure_final_ack(dummy.published)
    assert comp["status"] == "failed" and comp["result"]["reason"] == "invalid_payload"
    # the requested state never appears anywhere the hub publishes
    assert not any("22.5" in str(p["payload"]) for p in dummy.published)


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

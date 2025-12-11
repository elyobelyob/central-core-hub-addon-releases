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
            "attributes": {"friendly_name": "Temp"},
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

    command = {"command_id": "abc123", "action": "sensors/poll", "payload": {}}
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


def test_handle_sensors_set_command_calls_ha_and_responds(monkeypatch):
    mod = _load_client_module()
    CentralCoreClient = mod.CentralCoreClient
    # capture posts
    posts = []

    class FakeResp:
        def __init__(self, data=None):
            self._data = data or {}

        def raise_for_status(self):
            return None

        def json(self):
            return self._data

    def fake_post(url, headers=None, json=None, timeout=10):
        posts.append({"url": url, "headers": headers, "json": json})
        return FakeResp()

    def fake_get(url, headers=None, timeout=10):
        # return readback state matching the posted value in tests
        if url.endswith("/api/states/sensor.temp"):
            return FakeResp({"state": "22.0", "attributes": {"unit_of_measurement": "°C"}})
        if url.endswith("/api/states/sensor.hum"):
            return FakeResp({"state": "43", "attributes": {"unit_of_measurement": "%"}})
        return FakeResp({"state": "unknown", "attributes": {}})

    monkeypatch.setattr(
        mod,
        "requests",
        type("R", (), {"post": staticmethod(fake_post), "get": staticmethod(fake_get)}),
    )

    options = {
        "client_id": "unit-hub",
        "ha_api_url": "http://ha",
        "ha_api_token": "tok",
    }
    c = CentralCoreClient(options)
    dummy = DummyClient()
    c._client = dummy

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
    msg = DummyMsg(topic, json.dumps(command).encode("utf-8"))

    c.on_message(None, None, msg)

    # requests.post should be called for each sensor
    assert len(posts) == 2
    assert posts[0]["url"].endswith("/api/states/sensor.temp")
    assert posts[1]["url"].endswith("/api/states/sensor.hum")

    # ACK should be published to versioned ack topic
    ack_topic = f"hubs/{c.client_id}/v1/ack/sensors.set/{command['command_id']}"
    topics = [p["topic"] for p in dummy.published]
    assert ack_topic in topics
    # telemetry should be published to preferred sensors topic with data map
    assert c.preferred_sensors_topic in topics
    tele = json.loads(next(p["payload"] for p in dummy.published if p["topic"] == c.preferred_sensors_topic))
    assert "data" in tele and "sensor.temp" in tele["data"] and "sensor.hum" in tele["data"]
    # include name and enabled maps
    assert "names" in tele and "sensor.temp" in tele["names"] and "sensor.hum" in tele["names"]
    assert "enabled" in tele and isinstance(tele["enabled"].get("sensor.temp"), bool)


def test_handle_sensors_set_without_readback(monkeypatch):
    """When `ha_readback_after_set` is false, the client should not GET readback values
    and should publish telemetry using the requested state values."""
    mod = _load_client_module()
    CentralCoreClient = mod.CentralCoreClient
    posts = []
    get_called = {"count": 0}

    class FakeResp:
        def __init__(self, data=None):
            self._data = data or {}

        def raise_for_status(self):
            return None

        def json(self):
            return self._data

    def fake_post(url, headers=None, json=None, timeout=10):
        posts.append({"url": url, "headers": headers, "json": json})
        return FakeResp()

    def fake_get(url, headers=None, timeout=10):
        get_called["count"] += 1
        return FakeResp({"state": "unexpected", "attributes": {}})

    monkeypatch.setattr(
        mod,
        "requests",
        type("R", (), {"post": staticmethod(fake_post), "get": staticmethod(fake_get)}),
    )

    options = {
        "client_id": "unit-hub",
        "ha_api_url": "http://ha",
        "ha_api_token": "tok",
        "ha_readback_after_set": False,
    }
    c = CentralCoreClient(options)
    dummy = DummyClient()
    c._client = dummy

    command = {
        "command_id": "setno",
        "action": "sensors/set",
        "payload": {"sensors": [{"entity_id": "sensor.temp", "state": "22.5"}]},
    }
    topic = f"hubs/{c.client_id}/v1/cmd/sensors/set"
    msg = DummyMsg(topic, json.dumps(command).encode("utf-8"))

    c.on_message(None, None, msg)

    # POST should have been called
    assert len(posts) == 1
    # GET should NOT have been called because readback is disabled
    assert get_called["count"] == 0

    # Telemetry should be published using the requested state (preserve raw string)
    assert c.preferred_sensors_topic in [p["topic"] for p in dummy.published]
    tele = json.loads(next(p["payload"] for p in dummy.published if p["topic"] == c.preferred_sensors_topic))
    assert "data" in tele
    # value should preserve raw string from the request
    assert tele["data"].get("sensor.temp") == "22.5"
    # names and enabled should also be present
    assert "names" in tele and "sensor.temp" in tele["names"]
    assert "enabled" in tele and isinstance(tele["enabled"].get("sensor.temp"), bool)

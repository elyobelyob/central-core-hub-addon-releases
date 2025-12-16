import importlib.util
import sys
import types
import json
from pathlib import Path
from typing import Any, cast


def _load_fresh_module_with_no_deps():
    """Load a fresh copy of mqtt_client.py with `paho` and `requests` removed
    from sys.modules to exercise import-time fallback branches."""
    repo_root = Path(__file__).resolve().parents[3]
    src = repo_root / "central-core-hub" / "mqtt_client.py"
    # remove any existing paho/requests entries from sys.modules so imports must pass through meta_path
    removed = {}
    for k in list(sys.modules.keys()):
        if k.startswith("paho") or k.startswith("requests"):
            removed[k] = sys.modules.pop(k)

    # install a meta_path finder that raises ImportError for paho and requests
    class Blocker:
        def find_spec(self, fullname, path, target=None):
            if fullname.startswith("paho") or fullname.startswith("requests"):
                raise ImportError("blocked for test")
            return None

    old_meta = list(sys.meta_path)
    sys.meta_path.insert(0, Blocker())
    try:
        spec = importlib.util.spec_from_file_location("fresh_mqtt_client", str(src))
        if spec is None or getattr(spec, "loader", None) is None:
            raise ImportError("could not load spec")
        module = importlib.util.module_from_spec(spec)
        loader = spec.loader
        assert loader is not None
        loader.exec_module(module)
        return module
    finally:
        # restore meta_path and sys.modules
        sys.meta_path[:] = old_meta
        sys.modules.update(removed)


def _load_named_module(name, path):
    spec = importlib.util.spec_from_file_location(name, str(path))
    if spec is None or getattr(spec, "loader", None) is None:
        raise ImportError("could not load spec")
    module = importlib.util.module_from_spec(spec)
    loader = spec.loader
    assert loader is not None
    loader.exec_module(module)
    return module


def test_import_time_missing_paho_and_requests():
    mod = _load_fresh_module_with_no_deps()
    # When paho isn't importable, module should expose mqtt = None
    assert mod.__dict__.get("mqtt") is None
    # And when requests isn't importable, requests should be None
    assert mod.__dict__.get("requests") is None


def test_publish_telemetry_vault_fallback(monkeypatch):
    path = Path(__file__).resolve().parents[3] / "central-core-hub" / "mqtt_client.py"
    m = _load_named_module("m", path)
    CentralCoreClient = m.CentralCoreClient

    calls = []

    def fake_publish(topic, payload, qos=0):
        calls.append((topic, payload, qos))

    # monkeypatch build_vault_payload to return None to force fallback
    monkeypatch.setattr(m, "build_vault_payload", lambda p: None)
    c = CentralCoreClient({"client_id": "vc", "vault_topic": "vault/t"})
    c._publish = lambda topic, payload, qos=0: fake_publish(topic, payload, qos)
    c.publish_telemetry()
    # ensure we published to telemetry topic and also to vault (fallback)
    topics = [t for (t, p, q) in calls]
    assert c.telemetry_topic in topics
    assert c.vault_topic in topics


def test_on_message_malformed_and_binary(monkeypatch):
    # load module normally
    repo_root = Path(__file__).resolve().parents[3]
    m = _load_named_module("m2", repo_root / "central-core-hub" / "mqtt_client.py")
    CentralCoreClient = m.CentralCoreClient

    c = CentralCoreClient({"client_id": "u3"})

    # dummy client to capture publishes
    class Dummy:
        def __init__(self):
            self.published = []

        def publish(self, topic, payload, qos=0):
            self.published.append((topic, payload, qos))

            class R:
                rc = 0

            return R()

    c._client = Dummy()

    # malformed JSON payload
    msg1 = type(
        "M",
        (),
        {"topic": f"hubs/{c.client_id}/v1/cmd/sensors/set", "payload": b"{notjson"},
    )
    # should not raise
    c.on_message(None, None, msg1)

    # binary payload (simulate decode failure)
    msg2 = type(
        "M",
        (),
        {
            "topic": f"hubs/{c.client_id}/v1/cmd/sensors/poll",
            "payload": bytes([0xFF, 0xFE, 0xFD]),
        },
    )
    c.on_message(None, None, msg2)


def test_on_connect_calls_publish_sensors(monkeypatch):
    repo_root = Path(__file__).resolve().parents[3]
    m = _load_named_module("m3", repo_root / "central-core-hub" / "mqtt_client.py")
    CentralCoreClient = m.CentralCoreClient

    called = {"publish_sensors": 0}

    def fake_publish_sensors():
        called["publish_sensors"] += 1

    c = CentralCoreClient({"client_id": "u4"})
    c.publish_sensors = fake_publish_sensors
    # simulate on_connect callback
    c.on_connect(None, None, None, 0)
    assert called["publish_sensors"] >= 1


def test_fetch_sensors_happy_path(monkeypatch):
    path = Path(__file__).resolve().parents[3] / "central-core-hub" / "mqtt_client.py"
    m = _load_named_module("m4", path)

    # fake requests.get to return a list of entities
    class FakeResp:
        def __init__(self, data):
            self._data = data

        def raise_for_status(self):
            return None

        def json(self):
            return self._data

    def fake_get(url, headers=None, timeout=10):
        return FakeResp(
            [
                {
                    "entity_id": "sensor.a",
                    "state": "1",
                    "attributes": {"friendly_name": "A", "device_class": "motion"},
                    "last_changed": "2025-01-01T00:00:00Z",
                    "last_updated": "2025-01-01T00:00:01Z",
                },
                {"entity_id": "device.x", "state": "on", "attributes": {}},
            ]
        )

    fake_requests = types.SimpleNamespace(get=fake_get)
    cast(Any, m).requests = fake_requests
    sensors = m.fetch_sensors("http://ha", "token")
    assert isinstance(sensors, list)
    assert any(s["entity_id"] == "sensor.a" for s in sensors)
    sensor_a = next(s for s in sensors if s["entity_id"] == "sensor.a")
    assert sensor_a.get("last_changed") == "2025-01-01T00:00:00Z"
    assert sensor_a.get("last_updated") == "2025-01-01T00:00:01Z"


def test_sensors_poll_with_requested_subset(monkeypatch):
    # test sensors/poll honoring requested device classes
    path = Path(__file__).resolve().parents[3] / "central-core-hub" / "mqtt_client.py"
    m = _load_named_module("m5", path)
    CentralCoreClient = m.CentralCoreClient

    # stub fetch_sensors with varied device classes
    monkeypatch.setattr(
        m,
        "fetch_sensors",
        lambda url, token, safe_classes=None: [
            {"entity_id": "sensor.a", "state": "on", "attributes": {"device_class": "motion"}},
            {"entity_id": "sensor.b", "state": "12", "attributes": {"device_class": "door"}},
            {"entity_id": "sensor.c", "state": "7.5", "attributes": {"device_class": "temperature"}},
        ],
    )

    c = CentralCoreClient({"client_id": "u5", "ha_api_url": "http://ha", "ha_api_token": "tok"})
    published = []
    c._publish = lambda topic, payload, qos=0: published.append((topic, json.loads(payload)))

    # create poll command requesting only door device class
    cmd = {"command_id": "p1", "payload": {"sensors": ["door"]}}
    msg = type(
        "M",
        (),
        {
            "topic": f"hubs/{c.client_id}/v1/cmd/sensors/poll",
            "payload": json.dumps(cmd).encode("utf-8"),
        },
    )
    c.on_message(None, None, msg)

    # find telemetry publish
    tele = next((p for t, p in published if t == c.preferred_sensors_topic), None)
    assert tele is not None
    assert "data" in tele and "sensor.b" in tele["data"]


def test_sensors_set_mapping_and_no_ha_config(monkeypatch):
    path = Path(__file__).resolve().parents[3] / "central-core-hub" / "mqtt_client.py"
    m = _load_named_module("m6", path)
    CentralCoreClient = m.CentralCoreClient

    # Instantiate without HA config
    c = CentralCoreClient({"client_id": "u6"})
    published = []
    c._publish = lambda topic, payload, qos=0: published.append((topic, json.loads(payload)))

    # mapping-style payload
    cmd = {"command_id": "smap", "payload": {"sensors": {"sensor.x": "9"}}}
    msg = type(
        "M",
        (),
        {
            "topic": f"hubs/{c.client_id}/v1/cmd/sensors/set",
            "payload": json.dumps(cmd).encode("utf-8"),
        },
    )
    c.on_message(None, None, msg)

    # ack should have been published
    ack_topic = f"hubs/{c.client_id}/v1/ack/sensors.set/{cmd['command_id']}"
    comps = [p for t, p in published if t == ack_topic]
    assert comps


def test_publish_telemetry_vault_exception(monkeypatch):
    # Ensure exception in build_vault_payload is handled
    path = Path(__file__).resolve().parents[3] / "central-core-hub" / "mqtt_client.py"
    m = _load_named_module("m7", path)
    CentralCoreClient = m.CentralCoreClient

    # monkeypatch build_vault_payload to raise
    def bad(x):
        raise RuntimeError("boom")

    monkeypatch.setattr(m, "build_vault_payload", bad)
    calls = []
    c = CentralCoreClient({"client_id": "v2", "vault_topic": "vault/t"})
    c._publish = lambda topic, payload, qos=0: calls.append(topic)
    c.publish_telemetry()
    # telemetry and vault publish attempted; vault exception path should not raise
    assert c.telemetry_topic in calls

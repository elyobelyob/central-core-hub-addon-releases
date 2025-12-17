import json
import importlib.util
from pathlib import Path
import pytest


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
        self.published.append({"topic": topic, "payload": payload, "qos": qos})


class DummyMsg:
    def __init__(self, topic, payload_bytes: object = b""):
        self.topic = topic
        self.payload = payload_bytes


def test_poll_data_type_parsing(monkeypatch):
    mc = _load_client_module()
    CentralCoreClient = mc.CentralCoreClient

    sample = [
        {"entity_id": "sensor.on", "state": "on", "attributes": {"device_class": "temperature"}},
        {"entity_id": "sensor.off", "state": "off", "attributes": {"device_class": "temperature"}},
        {"entity_id": "sensor.int", "state": "42", "attributes": {"device_class": "temperature"}},
        {"entity_id": "sensor.float", "state": "3.14", "attributes": {"device_class": "temperature"}},
        {"entity_id": "sensor.text", "state": "n/a", "attributes": {"device_class": "temperature"}},
    ]
    monkeypatch.setattr(mc, "fetch_sensors", lambda url, token, safe_classes=None: sample)

    options = {
        "client_id": "unit-hub",
        "ha_api_url": "http://ha",
        "ha_api_token": "tok",
    }
    c = CentralCoreClient(options)
    dummy = DummyClient()
    c._client = dummy
    c.vault_topic = ""

    cmd = {"command_id": "cid1", "action": "sensors/poll", "payload": {"sensors": ["temperature"]}}
    msg = DummyMsg(f"hubs/{c.client_id}/v1/cmd/sensors/poll", json.dumps(cmd).encode("utf-8"))

    c.on_message(None, None, msg)

    tele_payload = json.loads(
        next(p["payload"] for p in dummy.published if p["topic"] == c.preferred_sensors_topic)
    )
    data = tele_payload.get("data")
    # Preserve raw HA-provided values (no coercion)
    assert data["sensor.on"] == "on"
    assert data["sensor.off"] == "off"
    assert data["sensor.int"] == "42"
    assert data["sensor.float"] == "3.14"
    assert data["sensor.text"] == "n/a"


def test__load_client_module_importerror(monkeypatch):
    monkeypatch.setattr(importlib.util, "spec_from_file_location", lambda *a, **k: None)
    with pytest.raises(ImportError):
        _load_client_module()


def test_on_message_binary_payload_and_set_no_ha_config(monkeypatch):
    mc = _load_client_module()
    CentralCoreClient = mc.CentralCoreClient

    # fetch_sensors returns one
    monkeypatch.setattr(
        mc,
        "fetch_sensors",
        lambda url, token, safe_classes=None: [{"entity_id": "sensor.x", "state": "1", "attributes": {}}],
    )

    options = {"client_id": "unit-hub"}  # no HA config
    c = CentralCoreClient(options)
    dummy = DummyClient()
    c._client = dummy

    # Create a message whose payload.decode will raise to force '<binary>' branch
    class BadPayload:
        def decode(self, *a, **k):
            raise RuntimeError("bad")

    msg = DummyMsg(f"hubs/{c.client_id}/v1/cmd/sensors/poll", BadPayload())
    # Should not raise
    c.on_message(None, None, msg)

    # Now test sensors/set with no HA config -> results.failed should be reported
    cmd = {
        "command_id": "cid2",
        "action": "sensors/set",
        "payload": {"sensors": [{"entity_id": "sensor.x", "state": "2"}]},
    }
    msg2 = DummyMsg(f"hubs/{c.client_id}/v1/cmd/sensors/set", json.dumps(cmd).encode("utf-8"))
    c.on_message(None, None, msg2)

    # find completion response using client's build_ack_topic
    resp_topic = c.build_ack_topic(cmd["action"], cmd["command_id"])
    comps = [p for p in dummy.published if p["topic"] == resp_topic]
    assert comps, "completion response not published"
    comp_payload = json.loads(comps[-1]["payload"])
    assert "result" in comp_payload
    assert comp_payload["result"]["failed"]
